#!/usr/bin/env python
"""
M07 demo -- Prompt engineering and optimizing generation behavior on Foundry.

AI-103 Lesson 7 is about STEERING a model, so code is the surface. We walk the three
objectives this lesson owns, live, against a real deployment:

  LO7.1  TUNE GENERATION BEHAVIOR ... the dials. max_output_tokens caps length. And the
                                      catch the exam loves: a reasoning model (gpt-5 /
                                      o-series) REJECTS temperature and top_p -- its knob is
                                      reasoning_effort. We show the actual 400, then tune the
                                      right dial.
  LO7.2  PROMPT PATTERNS ............ role prompting (a persona via instructions), few-shot
                                      (teach by example), STRUCTURED OUTPUT (a JSON schema the
                                      model must satisfy), and grounding (answer only from
                                      supplied context).
  LO7.3  REFLECTION / SELF-CRITIQUE . a loop: draft, have the model score its own draft against
                                      criteria (as JSON), then retry using that critique.

Auth is KEYLESS: AzureCliCredential (your `az login` identity). The OpenAI client the SDK
returns is bearer-token authenticated -- no API key anywhere.

The demo is READ-ONLY (it only calls the model; it creates and deletes nothing) and
idempotent -- re-running produces the same shape of result.

Setup:  uv sync   ;   az login   ;   copy .env.example to .env  (project endpoint + deployment)
Run:    uv run python m07_prompt_demo.py            # all three beats
        uv run python m07_prompt_demo.py --dry-run   # print the plan, call nothing

The `# %%` markers open this in the VS Code Interactive Window so you can run one beat at a
time while narrating.

Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
"""

# %%
import argparse
import json
import os
import sys

# Model output carries smart punctuation; force UTF-8 so a Windows console never crashes on print.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from azure.identity import AzureCliCredential
from azure.ai.projects import AIProjectClient

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass


# %%
def required(name: str, hint: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: environment variable {name} is not set.\n  -> {hint}\n  See .env.example.")
    return value


def banner(text: str) -> None:
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


def connect():
    """One keyless OpenAI client, off the Foundry PROJECT endpoint (LO6 carries over)."""
    endpoint = required(
        "FOUNDRY_PROJECT_ENDPOINT",
        "the PROJECT endpoint: https://<account>.services.ai.azure.com/api/projects/<project>",
    )
    project = AIProjectClient(endpoint=endpoint, credential=AzureCliCredential())
    return project.get_openai_client()


# %%
# ---- LO7.1: tune generation behavior (the dials) -------------------------------------
def beat_parameters(oai, deployment: str) -> None:
    banner("LO7.1 -- TUNE GENERATION BEHAVIOR (the dials)")

    # max_output_tokens: a hard ceiling on length. On a reasoning model the budget also covers
    # the hidden reasoning, so a tight cap TRUNCATES -- we surface that status instead of guessing.
    capped = oai.responses.create(
        model=deployment,
        input="Write three detailed paragraphs about prompt engineering.",
        reasoning={"effort": "low"},
        max_output_tokens=220,
    )
    status = getattr(capped, "status", "completed")
    incomplete = getattr(capped, "incomplete_details", None)
    reason = f" (stopped early: {incomplete.reason})" if incomplete else ""
    print(f"  max_output_tokens=220 -> status={status}{reason}")
    print(f"     the cap is a real cost + UX control: you decide how long an answer can get.")

    # The exam catch: reasoning models reject temperature / top_p.
    print("\n  Now the dial everyone reaches for first -- temperature:")
    try:
        oai.responses.create(model=deployment, input="Say hello.", temperature=0.9)
        print("  temperature accepted (this is a standard, non-reasoning model).")
    except Exception as exc:
        msg = str(exc).split("message':")[-1][:90]
        print(f"  temperature REJECTED -> {type(exc).__name__}: ...{msg}")
        print("  That's because gpt-5 / o-series are REASONING models. Their dial is reasoning_effort,")
        print("  not temperature. So we tune the right knob:")

    # reasoning_effort: the reasoning-model dial. Higher effort = more thinking = more latency/cost.
    import time
    for effort in ("low", "high"):
        start = time.perf_counter()
        r = oai.responses.create(
            model=deployment,
            input="A bat and a ball cost $1.10. The bat costs $1.00 more than the ball. How much is the ball? Answer with just the amount.",
            reasoning={"effort": effort},
        )
        secs = time.perf_counter() - start
        print(f"  reasoning_effort={effort:<4} -> {r.output_text.strip()!r:<10}  ({secs:.1f}s of thinking)")
    print("\n  Standard models tune temperature/top_p; reasoning models tune reasoning_effort. Know both.")


# %%
# ---- LO7.2: prompt engineering patterns ----------------------------------------------
def beat_patterns(oai, deployment: str) -> None:
    banner("LO7.2 -- PROMPT PATTERNS (role, few-shot, structured output, grounding)")

    # 1) ROLE PROMPTING: a persona set via `instructions` steers tone + scope.
    role = oai.responses.create(
        model=deployment,
        instructions="You are a terse senior SRE. Answer in one blunt sentence, no pleasantries.",
        input="Our API latency spiked. What's the first thing to check?",
    )
    print(f"  role prompting -> {role.output_text.strip()!r}")

    # 2) FEW-SHOT: two labeled examples teach the format better than a description.
    few_shot = oai.responses.create(
        model=deployment,
        input=(
            "Classify sentiment as POSITIVE or NEGATIVE.\n"
            "Review: 'Loved every minute.' -> POSITIVE\n"
            "Review: 'Total waste of money.' -> NEGATIVE\n"
            "Review: 'It shipped late but works fine.' ->"
        ),
    )
    print(f"  few-shot classify -> {few_shot.output_text.strip()!r}")

    # 3) STRUCTURED OUTPUT: a JSON schema the model MUST satisfy -> machine-readable, every time.
    schema = {
        "type": "object",
        "properties": {
            "product": {"type": "string"},
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
            "issues": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["product", "sentiment", "issues"],
        "additionalProperties": False,
    }
    structured = oai.responses.create(
        model=deployment,
        input="Extract fields from: 'The Contoso router keeps dropping Wi-Fi and runs hot.'",
        text={"format": {"type": "json_schema", "name": "review", "schema": schema, "strict": True}},
    )
    print(f"  structured output -> {structured.output_text.strip()}")

    # 4) GROUNDING: answer ONLY from supplied context; refuse to invent.
    context = "Foundry content filters inspect four harm categories: hate, violence, sexual, and self-harm."
    grounded = oai.responses.create(
        model=deployment,
        instructions="Answer ONLY from the CONTEXT. If the answer is not in the context, say 'Not in the provided context.'",
        input=f"CONTEXT: {context}\n\nQUESTION: What is the price of a Foundry deployment?",
    )
    print(f"  grounding (out-of-context Q) -> {grounded.output_text.strip()!r}")
    print("\n  Pick the pattern that fits the job; structured output is how you guarantee parseable data.")


# %%
# ---- LO7.3: reflection / self-critique loop ------------------------------------------
def beat_reflection(oai, deployment: str) -> None:
    banner("LO7.3 -- REFLECTION: draft, self-score, retry with the critique")
    question = "Explain retrieval-augmented generation to a new developer."

    # Draft: deliberately terse so the critique has something to catch.
    draft = oai.responses.create(
        model=deployment,
        instructions="Answer in at most 8 words.",
        input=question,
    ).output_text.strip()
    print(f"  draft (constrained) -> {draft!r}")

    # Self-score against defined criteria, returned as JSON the pipeline can branch on.
    score_schema = {
        "type": "object",
        "properties": {
            "score": {"type": "integer"},
            "critique": {"type": "string"},
        },
        "required": ["score", "critique"],
        "additionalProperties": False,
    }
    graded = oai.responses.create(
        model=deployment,
        instructions="Score the ANSWER for completeness from 1 to 5 and give a one-line critique.",
        input=f"QUESTION: {question}\nANSWER: {draft}",
        text={"format": {"type": "json_schema", "name": "grade", "schema": score_schema, "strict": True}},
    )
    grade = json.loads(graded.output_text)
    print(f"  self-score -> {grade['score']}/5  critique: {grade['critique']!r}")

    # Retry only if it fell short, steering the retry with the critique it produced.
    if grade["score"] < 4:
        improved = oai.responses.create(
            model=deployment,
            instructions="Rewrite the answer to fix the critique. Two or three clear sentences.",
            input=f"QUESTION: {question}\nDRAFT: {draft}\nCRITIQUE: {grade['critique']}",
        ).output_text.strip()
        print(f"  retry (critique-guided) -> {improved!r}")
    else:
        print("  score already met the bar -- no retry needed (loop would stop here).")
    print("\n  review, score, retry, cap: the model catches its own misses before a user does.")


# %%
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-103 L7: prompt engineering + optimizing generation.")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan; make no model calls.")
    return parser.parse_args()


# %%
def main() -> None:
    args = parse_args()
    deployment = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-5-mini")
    if args.dry_run:
        banner("DRY RUN -- plan (no calls)")
        print(f"  Project endpoint : {os.environ.get('FOUNDRY_PROJECT_ENDPOINT', '<unset>')}")
        print(f"  Model deployment : {deployment}")
        print( "  Beats            : LO7.1 dials -> LO7.2 patterns -> LO7.3 self-critique")
        return

    oai = connect()
    beat_parameters(oai, deployment)
    beat_patterns(oai, deployment)
    beat_reflection(oai, deployment)
    banner("DONE -- dials, patterns, and self-critique. That's steering a model on purpose.")


if __name__ == "__main__":
    main()
