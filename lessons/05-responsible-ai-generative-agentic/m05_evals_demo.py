#!/usr/bin/env python
"""
M05 demo -- Responsible AI instrumentation with the Azure AI Evaluation SDK.

AI-103 Lesson 5 ("Implement responsible AI across generative and agentic systems")
is four controls: content filters, INSTRUMENTATION, auditing, and agent governance.
This script is the instrumentation control (LO2). A content filter blocks the
obviously harmful stuff, but it can't tell you whether a good-looking answer is
actually *grounded* in your source or just confidently wrong. Evaluators can. They
score quality and safety on real query/response pairs, which is exactly the signal
you'd wire into CI to gate a release -- so code, not a portal click, is the right
surface here. (Content filters, tracing, and agent oversight are portal/IaC tasks;
see Warner.AI-103.Lesson-05-demo-runbook.md.)

We score the SAME question two ways -- one answer grounded in the source context and
one fabricated -- so the groundedness number visibly collapses on the made-up answer.
That low score is a hallucination caught by a machine instead of by a customer.

Auth is KEYLESS (Microsoft Entra ID via AzureCliCredential -- your `az login`
identity). The judge model_config carries a `credential` instead of an API key, so
no secret ever lands in this file or your shell. In CI you swap AzureCliCredential
for DefaultAzureCredential and let the pipeline's federated (OIDC) identity resolve.

  LO2 QUALITY ..... GroundednessEvaluator + RelevanceEvaluator. Both use an
                    LLM-as-a-judge (your gpt-5-mini deployment) via `model_config`.
                    Scores run 1-5; higher is better. These ALWAYS run.
  LO2 SAFETY ...... ContentSafetyEvaluator (optional, --safety). This one calls the
                    Azure AI Evaluation *service* (not your judge model), so it needs
                    an azure_ai_project and is region-gated. It SKIPS GRACEFULLY when
                    the project/region isn't wired, so the core demo never blocks.

The evaluators only READ and score; they mutate nothing, so this is safe to run live,
safe to record, and idempotent -- re-running yields the same verdicts.

Setup:  uv sync   (or: pip install -e .)   ;   az login   ;   copy .env.example to .env
Run:    uv run python m05_evals_demo.py            # groundedness + relevance, 2 answers
        uv run python m05_evals_demo.py --dry-run  # print the eval plan, call nothing
        uv run python m05_evals_demo.py --safety   # also attempt the safety evaluator

The `# %%` markers open this in the VS Code Interactive Window ("Run Cell") so you can
run one evaluator at a time while narrating -- no separate .ipynb to keep in sync.

Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
"""

# %%
# ---- imports -------------------------------------------------------------------------
import argparse
import os
import sys

from azure.identity import AzureCliCredential

try:
    from dotenv import load_dotenv
    # override=True so this lesson's .env WINS over any ambient AZURE_OPENAI_* vars in your
    # shell. Without it, a stray AZURE_OPENAI_ENDPOINT/DEPLOYMENT set elsewhere silently
    # grades against the wrong model -- a nasty surprise on camera. The .env is the source of truth.
    load_dotenv(override=True)
except ImportError:
    pass  # .env is a convenience; real env vars work too.


# %%
# ---- small helpers -------------------------------------------------------------------
def required(name: str, hint: str) -> str:
    """Return env var ``name`` or exit with a friendly, copy-pasteable hint. See .env.example."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: environment variable {name} is not set.\n  -> {hint}\n  See .env.example.")
    return value


def banner(text: str) -> None:
    """Print a labeled section header so each evaluator is obvious on screen while recording."""
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


def score_of(result: dict, metric: str):
    """Pull a metric's numeric score out of an evaluator result.

    Evaluators return a dict like {"groundedness": 5.0, "groundedness_reason": "..."}.
    Newer SDKs drop the legacy ``gpt_`` prefix, so we try the plain key first and fall
    back to the prefixed one -- that one line future-proofs the demo across versions.
    """
    for key in (metric, f"gpt_{metric}"):
        if key in result:
            return result[key]
    return None


# %%
# ---- the judge model configuration (keyless) -----------------------------------------
def build_model_config():
    """Assemble the LLM-as-a-judge config, returning (model_config, credential).

    Two SDK quirks drove this shape, both learned the hard way against the current
    azure-ai-evaluation build:

    1. The "type": "azure_openai" discriminator is REQUIRED. Omit it and the SDK's
       validator tries the plain-OpenAI shape and rejects the azure_* keys with a
       confusing "unknown keys" error.
    2. The credential does NOT go in the dict. The SDK's config validator chokes on a
       `credential` key (its type is `Any`, and the naive validator calls isinstance
       against it, which raises). Instead we return the credential separately and pass
       it as the evaluator's `credential=` KWARG -- that's the supported keyless path,
       with NO api_key in this file. Set AZURE_OPENAI_KEY only for a locked-down lab.
    """
    endpoint = required(
        "AZURE_OPENAI_ENDPOINT",
        "your Foundry account endpoint, e.g. https://<account>.services.ai.azure.com",
    )
    deployment = required("AZURE_OPENAI_DEPLOYMENT", "the JUDGE deployment name, e.g. gpt-4.1-mini")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")

    model_config = {
        "type": "azure_openai",
        "azure_endpoint": endpoint,
        "azure_deployment": deployment,
        "api_version": api_version,
    }
    api_key = os.environ.get("AZURE_OPENAI_KEY")
    if api_key:
        model_config["api_key"] = api_key          # opt-in, discouraged
        return model_config, None                  # key auth: no separate credential
    return model_config, AzureCliCredential()      # keyless default (Entra ID) via kwarg


# %%
# ---- the test cases: one grounded answer, one fabricated answer ----------------------
# A single source context plus the same question answered two ways. The grounded answer
# stays inside the source; the fabricated answer invents a fact the source never states.
# This is the whole lesson in three strings -- watch groundedness fall on the second one.
SOURCE_CONTEXT = (
    "Microsoft Foundry deployments ship with a default content filter that inspects four "
    "harm categories: hate, violence, sexual, and self-harm. Each category is assigned a "
    "severity score. Administrators can create custom content filters to tighten thresholds."
)
QUERY = "How many harm categories does the default Foundry content filter inspect?"
GROUNDED_ANSWER = "The default content filter inspects four harm categories: hate, violence, sexual, and self-harm."
FABRICATED_ANSWER = "The default content filter inspects twelve harm categories and automatically emails a compliance officer."


# %%
def run_quality(model_config: dict, credential=None) -> None:
    """LO2 QUALITY: score the grounded vs fabricated answer for groundedness and relevance.

    `credential` is passed as the evaluator KWARG (keyless), never inside model_config --
    see build_model_config for why the SDK validator rejects it in the dict.
    """
    from azure.ai.evaluation import GroundednessEvaluator, RelevanceEvaluator

    kw = {"credential": credential} if credential is not None else {}
    groundedness = GroundednessEvaluator(model_config=model_config, **kw)
    relevance = RelevanceEvaluator(model_config=model_config, **kw)

    cases = [("GROUNDED answer", GROUNDED_ANSWER), ("FABRICATED answer", FABRICATED_ANSWER)]
    for label, answer in cases:
        banner(f"QUALITY -- {label}")
        # Groundedness needs the source; relevance needs the question. Both are judge calls.
        g = groundedness(query=QUERY, response=answer, context=SOURCE_CONTEXT)
        r = relevance(query=QUERY, response=answer, context=SOURCE_CONTEXT)
        print(f"  groundedness : {score_of(g, 'groundedness')}  (1=ungrounded ... 5=fully grounded)")
        print(f"  relevance    : {score_of(r, 'relevance')}  (1=off-topic ... 5=on-point)")
    print("\n  Read the two groundedness numbers: the fabricated answer's score is your")
    print("  hallucination alarm. In CI you'd fail the build when it drops below your bar.")


# %%
def run_safety() -> None:
    """LO2 SAFETY (optional): service-based ContentSafetyEvaluator; skips if not wired.

    Safety evaluators don't use your judge model -- they call the Azure AI Evaluation
    service, which needs a project reference and is only available in some regions. So we
    treat it as opt-in and degrade gracefully: no project, or an unsupported region, prints
    a clear SKIP instead of crashing the recording.
    """
    banner("SAFETY -- ContentSafetyEvaluator (optional)")
    project = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    if not project:
        print("  SKIP: AZURE_AI_PROJECT_ENDPOINT not set. Safety evaluators call the Azure AI")
        print("  Evaluation service and need a project. Set it in .env to enable this beat.")
        return
    try:
        from azure.ai.evaluation import ContentSafetyEvaluator
        evaluator = ContentSafetyEvaluator(credential=AzureCliCredential(), azure_ai_project=project)
        result = evaluator(query=QUERY, response=GROUNDED_ANSWER)
        print(f"  content-safety result: {result}")
        print("  (Severity-style scores per harm category; lower is safer.)")
    except Exception as exc:  # region/preview gaps are common -- narrate, don't crash
        print(f"  SKIP: safety evaluator unavailable here ({type(exc).__name__}: {exc}).")
        print("  This is region-gated and preview in places -- the quality evaluators above")
        print("  are the always-on core of the demo.")


# %%
def parse_args() -> argparse.Namespace:
    """CLI flags that keep this safe to run live and safe to record."""
    parser = argparse.ArgumentParser(description="AI-103 L5 LO2: score answers with the Azure AI Evaluation SDK.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the evaluation plan and exit; make no judge/service calls.")
    parser.add_argument("--safety", action="store_true",
                        help="Also attempt the service-based ContentSafetyEvaluator (skips if unavailable).")
    return parser.parse_args()


# %%
def main() -> None:
    args = parse_args()

    if args.dry_run:
        banner("DRY RUN -- evaluation plan (no calls made)")
        print(f"  Judge endpoint  : {os.environ.get('AZURE_OPENAI_ENDPOINT', '<AZURE_OPENAI_ENDPOINT unset>')}")
        print(f"  Judge deployment: {os.environ.get('AZURE_OPENAI_DEPLOYMENT', '<AZURE_OPENAI_DEPLOYMENT unset>')}")
        print( "  Auth            : keyless (AzureCliCredential) unless AZURE_OPENAI_KEY is set")
        print( "  Quality evals   : GroundednessEvaluator, RelevanceEvaluator")
        print( "  Cases           : GROUNDED answer vs FABRICATED answer, same query+context")
        print(f"  Safety eval     : {'ContentSafetyEvaluator (opt-in)' if args.safety else 'skipped (no --safety)'}")
        return

    model_config, credential = build_model_config()
    run_quality(model_config, credential)
    if args.safety:
        run_safety()

    banner("DONE -- filter blocks, evaluators verify. Next: tracing (LO3) and governance (LO4).")


if __name__ == "__main__":
    main()
