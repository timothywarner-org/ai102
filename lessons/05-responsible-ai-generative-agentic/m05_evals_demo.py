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

  LO2 QUALITY ..... GroundednessEvaluator + RelevanceEvaluator. Both use an LLM-as-a-judge
                    via `model_config` -- here the SAME gpt-5-mini we run the app on, so the
                    lab stays a single deployment. gpt-5 wants max_completion_tokens, so we
                    pass is_reasoning_model=True and the evaluator speaks that dialect. Scores
                    run 1-5; higher is better. These ALWAYS run.
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
import re
import sys
import textwrap

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


def reason_of(result: dict, metric: str):
    """Pull a metric's plain-English justification -- the judge explaining ITS OWN score.

    This ``_reason`` string is the most teachable field the SDK returns: it's the model
    saying, in words, why the answer earned a 5 or a 1. A bare number is a black box; the
    reason is what turns the demo from "trust me" into "watch the judge show its work."
    Same ``gpt_`` prefix fallback as score_of.
    """
    for key in (f"{metric}_reason", f"gpt_{metric}_reason"):
        if key in result:
            return result[key]
    return None


# The CI gate. Groundedness runs 1-5; below this bar we'd fail the build. Picking 3 (the
# midpoint) means "more grounded than not" -- a defensible, teachable release threshold.
QUALITY_BAR = 3


def fmt_score(score) -> str:
    """Render a 5.0 as '5' and a 4.5 as '4.5' -- clean numbers read better on camera."""
    if score is None:
        return "n/a"
    return str(int(score)) if float(score).is_integer() else f"{score:.1f}"


def score_bar(score, out_of: int = 5) -> str:
    """A shape-based meter (filled '#' vs empty '.') so the score's magnitude is visible.

    Deliberately ASCII, not color: length carries the signal, which stays readable for a
    red/green colorblind viewer and never mojibakes on a recording console.
    """
    if score is None:
        return "?" * out_of
    filled = max(0, min(out_of, int(round(float(score)))))
    return "#" * filled + "." * (out_of - filled)


def verdict(score, bar: int = QUALITY_BAR) -> str:
    """PASS / FAIL against the CI gate, as a bracketed label (not a color) for accessibility."""
    if score is None:
        return "[ n/a  ]"
    return "[ PASS ]" if score >= bar else "[ FAIL ]"


def wrap_labeled(label: str, text: str, width: int = 74) -> str:
    """Wrap ``text`` under a leading ``label``, hanging-indented to the label's width.

    Judge reasons and the source context are full sentences; hard-wrapping them keeps the
    output inside a slide-safe column instead of spilling off the right edge on camera.
    """
    pad = " " * len(label)
    lines = textwrap.wrap(text, width=width) or [""]
    return "\n".join([f"{label}{lines[0]}"] + [f"{pad}{ln}" for ln in lines[1:]])


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
    deployment = required("AZURE_OPENAI_DEPLOYMENT", "the JUDGE deployment name, e.g. gpt-5-mini")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

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


def is_reasoning_judge(deployment: str) -> bool:
    """Should the evaluator treat this judge as a reasoning model?

    gpt-5 and the o-series (o1/o3/o4) speak a slightly different dialect: they want
    `max_completion_tokens`, and they reject the plain `max_tokens` the evaluators send by
    default. Passing `is_reasoning_model=True` flips the evaluator to that dialect, which is
    exactly how you use a modern gpt-5 deployment as your judge instead of standing up an
    older model just to grade. Override with AZURE_OPENAI_IS_REASONING=true/false if needed.
    """
    override = os.environ.get("AZURE_OPENAI_IS_REASONING")
    if override is not None:
        return override.strip().lower() in ("1", "true", "yes")
    d = (deployment or "").lower()
    return d.startswith("gpt-5") or bool(re.match(r"^o[134](\b|-)", d))


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
def show_scenario() -> None:
    """Put the whole experiment on screen BEFORE any score lands, so the numbers mean something.

    Without this, a viewer sees 'groundedness: 1' with no idea what was graded. Showing the
    source, the question, and the two answers first is what makes the collapse legible.
    """
    banner("SCENARIO -- one question, one source, two candidate answers")
    print("  The judge model reads the SOURCE, then grades each ANSWER against it.\n")
    print("  " + wrap_labeled("source   : ", SOURCE_CONTEXT))
    print(f'  question : "{QUERY}"\n')
    print("  Same question, answered two ways:")
    print("    GROUNDED   -- stays inside the source")
    print("    FABRICATED -- invents a fact the source never states")
    print("  Watch groundedness collapse on the fabricated one.")


def print_metric(name: str, score, reason: str, scale: str) -> None:
    """One metric line: number, shape bar, PASS/FAIL, the 1-5 scale, and the judge's reason."""
    print(f"  {name:<13} {fmt_score(score):>3} / 5   [{score_bar(score)}]   {verdict(score)}")
    print(f"  {'':<13} scale: {scale}")
    if reason:
        print("  " + wrap_labeled(f"{'':<13} why: ", reason))
    print()


def print_scoreboard(rows: list) -> None:
    """The payoff: grounded vs fabricated side by side, with the CI gate applied to each."""
    banner(f"SCOREBOARD -- groundedness is your hallucination alarm (CI gate = {QUALITY_BAR})")
    print(f"  {'answer':<12}{'groundedness':<15}{'relevance':<13}{'CI gate':<10}")
    print("  " + "-" * 56)
    for label, g, r in rows:
        flag = "  <- hallucination caught" if g is not None and g < QUALITY_BAR else ""
        print(f"  {label:<12}{fmt_score(g) + ' / 5':<15}{fmt_score(r) + ' / 5':<13}{verdict(g):<10}{flag}")

    scores = {label: g for label, g, _ in rows}
    grounded, fabricated = scores.get("GROUNDED"), scores.get("FABRICATED")
    if grounded is not None and fabricated is not None:
        print()
        print(f"  Groundedness fell {fmt_score(grounded)} -> {fmt_score(fabricated)} the moment the answer left the source.")
        print(f"  In CI you fail the build when groundedness < {QUALITY_BAR}. A machine caught the")
        print("  hallucination here -- not a customer in production.")


def run_quality(model_config: dict, credential=None) -> None:
    """LO2 QUALITY: score the grounded vs fabricated answer for groundedness and relevance.

    `credential` is passed as the evaluator KWARG (keyless), never inside model_config --
    see build_model_config for why the SDK validator rejects it in the dict.
    """
    from azure.ai.evaluation import GroundednessEvaluator, RelevanceEvaluator

    kw = {"credential": credential} if credential is not None else {}
    # A gpt-5 / o-series judge needs the reasoning-model dialect (max_completion_tokens).
    if is_reasoning_judge(model_config.get("azure_deployment", "")):
        kw["is_reasoning_model"] = True
    groundedness = GroundednessEvaluator(model_config=model_config, **kw)
    relevance = RelevanceEvaluator(model_config=model_config, **kw)

    show_scenario()

    cases = [("GROUNDED", GROUNDED_ANSWER), ("FABRICATED", FABRICATED_ANSWER)]
    rows = []
    for label, answer in cases:
        banner(f"{label} answer -- what the judge saw, and how it scored")
        print("  " + wrap_labeled("answer   : ", f'"{answer}"') + "\n")
        # Groundedness needs the source; relevance needs the question. Both are judge calls.
        g = groundedness(query=QUERY, response=answer, context=SOURCE_CONTEXT)
        r = relevance(query=QUERY, response=answer, context=SOURCE_CONTEXT)
        g_score, r_score = score_of(g, "groundedness"), score_of(r, "relevance")
        print_metric("groundedness", g_score, reason_of(g, "groundedness"),
                     "1 = invents facts    5 = fully supported by the source")
        print_metric("relevance", r_score, reason_of(r, "relevance"),
                     "1 = off-topic        5 = answers the question")
        rows.append((label, g_score, r_score))

    print_scoreboard(rows)


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
        print(f"  CI gate         : PASS/FAIL when groundedness < {QUALITY_BAR} (1-5 scale)")
        print( "  Output          : per-answer score + bar + judge's reason, then a scoreboard")
        print(f"  Safety eval     : {'ContentSafetyEvaluator (opt-in)' if args.safety else 'skipped (no --safety)'}")
        return

    model_config, credential = build_model_config()
    run_quality(model_config, credential)
    if args.safety:
        run_safety()

    banner("DONE -- filter blocks, evaluators verify. Next: tracing (LO3) and governance (LO4).")


if __name__ == "__main__":
    main()
