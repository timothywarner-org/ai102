#!/usr/bin/env python
"""
observability_demo.py -- the signals panel for optimizing & operationalizing GenAI.

Covers two objectives at once, against your REAL deployments:

  LO  "Set up observability by implementing tracing, token analytics, safety
       signals, and latency breakdowns."
        -> for every call we print: a TRACE id + model + fingerprint, the full
           TOKEN accounting (prompt / completion / reasoning / cached), the Azure
           SAFETY SIGNALS (content-filter verdicts on prompt AND completion), and
           a LATENCY breakdown (total wall-clock, effective tokens/sec, and the
           hidden-reasoning-token share that explains where the seconds went).

  LO  "Orchestrate multiple models, flows, or hybrid LLM and rules engines."
        -> a tiny RULES ENGINE inspects the prompt and recommends a model, then we
           fan the SAME prompt out to BOTH deployments and compare the signals.
           That's the hybrid: deterministic rules routing a pair of LLMs.

Auth is KEYLESS (AzureCliCredential -- your `az login` identity).

Setup:  uv sync ; az login ; .env has FOUNDRY_PROJECT_ENDPOINT + MODEL_DEPLOYMENT_NAME
        (reasoning, gpt-5-mini) + MODEL_STANDARD_NAME (standard, gpt-oss-120b)
Run:    uv run python observability_demo.py --example reason
        uv run python observability_demo.py --prompt "your text here"
        uv run python observability_demo.py --list          # show the example prompts
        uv run python observability_demo.py --model reasoning   # just one model
        uv run python observability_demo.py --example reason --trace  # ALSO ship spans to App Insights

Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
"""

from __future__ import annotations

import argparse
import os
import sys
import time

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


# =============================================================================
# Banger example prompts -- each one is TUNED to light up a different signal.
# =============================================================================
EXAMPLES = {
    "reason": {
        "why": "surfaces REASONING TOKENS + high latency on the reasoning model",
        "prompt": "A bat and a ball cost $1.10 total. The bat costs $1.00 more than the "
                  "ball. How much is the ball? Think it through, then give the amount.",
    },
    "runbook": {
        "why": "big COMPLETION TOKENS + a real tokens/sec read",
        "prompt": "Write a step-by-step runbook to rotate an Azure Key Vault secret with "
                  "zero downtime, including the rollback plan. Be specific.",
    },
    "noir": {
        "why": "creative writing that can light up a SAFETY SIGNAL (violence, low severity)",
        "prompt": "Write the tense 150-word opening of a noir detective story: a rain-soaked "
                  "alley, a cornered suspect, a drawn revolver, no one else around.",
    },
    "cache": {
        "why": "run it TWICE -- the second call should show CACHED TOKENS climb",
        "prompt": ("Using this style guide -- 'Contoso writes in plain, calm, precise "
                   "American English, never hypes, always leads with the point, defines a term "
                   "the first time it appears, and closes with the single next action' -- "
                   "rewrite this note: 'hey team the thing is broken again pls fix asap thx'."),
    },
    "json": {
        "why": "clean, short call -- a baseline signal panel to compare against",
        "prompt": "In one sentence, what is a Foundry project?",
    },
}


def load_models() -> list[tuple[str, str]]:
    """Return [(deployment_name, kind)] for orchestration. kind = reasoning | standard."""
    reasoning = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-5-mini")
    standard = os.environ.get("MODEL_STANDARD_NAME", "")
    models = [(reasoning, "reasoning")]
    if standard:
        models.append((standard, "standard"))
    return models


# =============================================================================
# Hybrid rules engine -- deterministic routing recommendation (no LLM call)
# =============================================================================
def rules_router(prompt: str) -> str:
    """A plain-code rule that recommends which model SHOULD get the job."""
    p = prompt.lower()
    reasoning_signals = ("think", "reason", "calculate", "prove", "step", "why", "how much", "puzzle")
    if any(s in p for s in reasoning_signals):
        return "reasoning (the prompt asks for multi-step thinking -> reasoning model earns its cost)"
    if len(prompt) < 80:
        return "standard (short, low-stakes -> the cheaper standard model is plenty)"
    return "standard (no reasoning trigger -> default to the cheaper standard model)"


# =============================================================================
# The one call -- streamed, so we can measure time-to-first-token honestly
# =============================================================================
def run_one(client, model: str, kind: str, prompt: str) -> dict:
    # Non-streaming: Azure returns the completion content-filter verdict reliably here
    # (streaming only emits it intermittently), and we still get honest wall-clock latency.
    reasoning = kind == "reasoning"
    kwargs = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    if reasoning:
        kwargs["max_completion_tokens"] = 2000     # reasoning tokens count against this
        kwargs["reasoning_effort"] = "medium"
    else:
        kwargs["max_tokens"] = 2000
        kwargs["temperature"] = 0.7                # standard models take the classic dials

    t0 = time.perf_counter()
    resp = client.chat.completions.create(**kwargs)
    total = time.perf_counter() - t0

    d = resp.model_dump()
    choice0 = (d.get("choices") or [{}])[0]
    return {
        "model": model, "kind": kind,
        "text": (choice0.get("message", {}).get("content") or "").strip(),
        "id": d.get("id"), "resp_model": d.get("model"),
        "fingerprint": d.get("system_fingerprint"),
        "total": total, "usage": d.get("usage"),
        "prompt_filter": d.get("prompt_filter_results"),     # safety verdict on the PROMPT
        "content_filter": choice0.get("content_filter_results"),  # verdict on the COMPLETION
    }


# =============================================================================
# Rendering the signal panel
# =============================================================================
def _fmt_filter(fr: dict | None) -> str:
    """Flatten a content-filter dict to 'hate=safe violence=low ...', flagging non-safe."""
    if not fr:
        return "(none returned)"
    cats = ("hate", "violence", "sexual", "self_harm")
    out = []
    for c in cats:
        v = fr.get(c) or {}
        sev = v.get("severity", "n/a")
        flag = "  <== FLAGGED" if v.get("filtered") else ""
        out.append(f"{c}={sev}{flag}")
    jb = fr.get("jailbreak")
    if jb:
        out.append(f"jailbreak={'detected' if jb.get('detected') else 'no'}")
    return "  ".join(out)


def print_report(meta: dict) -> None:
    u = meta.get("usage") or {}
    ctd = (u.get("completion_tokens_details") or {})
    ptd = (u.get("prompt_tokens_details") or {})
    prompt_fr = None
    if meta.get("prompt_filter"):
        prompt_fr = (meta["prompt_filter"][0] or {}).get("content_filter_results")

    print("\n" + "=" * 78)
    print(f"MODEL: {meta['model']}   ({meta['kind']})")
    print("=" * 78)

    print("-- TRACING --")
    print(f"   response id     : {meta.get('id')}")
    print(f"   served model    : {meta.get('resp_model')}")
    print(f"   system fingerprint: {meta.get('fingerprint')}")
    print("   (in production this id correlates to an OpenTelemetry trace in App Insights)")

    print("-- TOKEN ANALYTICS --")
    print(f"   prompt tokens     : {u.get('prompt_tokens', '?')}   (cached: {ptd.get('cached_tokens', 0)})")
    print(f"   completion tokens : {u.get('completion_tokens', '?')}   "
          f"(reasoning: {ctd.get('reasoning_tokens', 0)})")
    print(f"   total tokens      : {u.get('total_tokens', '?')}")

    print("-- SAFETY SIGNALS (Azure content filter) --")
    print(f"   prompt    : {_fmt_filter(prompt_fr)}")
    print(f"   completion: {_fmt_filter(meta.get('content_filter'))}")

    print("-- LATENCY BREAKDOWN --")
    total = meta.get("total") or 0
    comp = u.get("completion_tokens") or 0
    reason_tok = ctd.get("reasoning_tokens", 0)
    print(f"   total wall clock : {total:.2f}s")
    if comp and total:
        print(f"   throughput       : {comp / total:.0f} completion tokens/sec (effective)")
    if reason_tok:
        print(f"   >> {reason_tok} of those completion tokens were HIDDEN REASONING -- "
              "that's where the seconds went")

    preview = meta["text"].replace("\n", " ")[:150]
    print(f"-- OUTPUT (preview) --\n   {preview}{'...' if len(meta['text']) > 150 else ''}")


# =============================================================================
# REAL tracing -- export every model call to Application Insights via OpenTelemetry
# =============================================================================
def enable_tracing() -> bool:
    """
    Turn the local 'response id' line into a REAL distributed trace in Application
    Insights. After this runs, every openai call becomes an OpenTelemetry span
    (model, tokens, latency, status) with NO changes to the call sites.

    The four steps (this is the whole recipe):
      1) Find the App Insights CONNECTION STRING -- the address telemetry ships to.
         The observability Bicep wrote it to .env as APPLICATIONINSIGHTS_CONNECTION_STRING.
         (Equivalent, if App Insights is connected to the project:
              project.telemetry.get_application_insights_connection_string() )
      2) (dev only) Opt in to capturing the actual prompt/response TEXT on the spans.
         It's off by default because message content can be personal data -- turn it
         on in dev, leave it off in production.
      3) configure_azure_monitor() -- one call wires the OpenTelemetry exporter +
         tracer provider to your App Insights resource.
      4) OpenAIInstrumentor().instrument() -- auto-instruments the OpenAI SDK so every
         chat.completions call emits a GenAI span following OpenTelemetry semantic
         conventions. This is why the call sites don't change.

    Grounding: https://learn.microsoft.com/azure/foundry/observability/how-to/trace-agent-setup
    """
    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn:
        print("  [trace] APPLICATIONINSIGHTS_CONNECTION_STRING not set in .env -- "
              "deploy infra/modules/observability.bicep first, then re-run with --trace.")
        return False

    # Step 2: capture prompt/response text on spans (dev convenience; PII-sensitive).
    os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")

    # Steps 3 + 4: point OpenTelemetry at App Insights, then instrument the OpenAI SDK.
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
    configure_azure_monitor(connection_string=conn)   # exporter -> Application Insights
    OpenAIInstrumentor().instrument()                 # every openai call -> a span
    print("  [trace] Azure Monitor wired up; OpenAI calls now export spans to App Insights.")
    return True


# =============================================================================
def main() -> None:
    parser = argparse.ArgumentParser(description="Observability + multi-model orchestration signals.")
    parser.add_argument("--prompt", help="Your own prompt.")
    parser.add_argument("--example", choices=list(EXAMPLES), help="Use a tuned example prompt.")
    parser.add_argument("--model", choices=["all", "reasoning", "standard"], default="all",
                        help="Which deployment(s) to fan out to. Default: all (orchestration).")
    parser.add_argument("--list", action="store_true", help="List the example prompts and exit.")
    parser.add_argument("--trace", action="store_true",
                        help="Also export OpenTelemetry spans to Application Insights.")
    args = parser.parse_args()

    if args.list:
        print("Example prompts (each tuned to surface a signal):")
        for k, v in EXAMPLES.items():
            print(f"  --example {k:<8} {v['why']}")
        return

    prompt = args.prompt or (EXAMPLES[args.example]["prompt"] if args.example else EXAMPLES["reason"]["prompt"])

    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        sys.exit("ERROR: FOUNDRY_PROJECT_ENDPOINT not set. See .env; run `az login`.")
    client = AIProjectClient(endpoint=endpoint, credential=AzureCliCredential()).get_openai_client()

    models = load_models()
    if args.model != "all":
        models = [m for m in models if m[1] == args.model] or models

    # If --trace is set, wire OpenTelemetry -> App Insights BEFORE any model call,
    # so the calls below are captured as spans.
    tracer = None
    if args.trace and enable_tracing():
        from opentelemetry import trace
        tracer = trace.get_tracer("ai103.observability_demo")

    print("=" * 78)
    print("PROMPT:", prompt)
    print("RULES-ENGINE RECOMMENDATION ->", rules_router(prompt))
    print(f"ORCHESTRATING across {len(models)} model(s): {', '.join(m[0] for m in models)}")

    def run_all() -> None:
        for model, kind in models:
            try:
                print_report(run_one(client, model, kind, prompt))
            except Exception as exc:  # keep the panel resilient during a live demo
                print(f"\n[{model}] call failed: {type(exc).__name__}: {str(exc)[:160]}")

    if tracer:
        # One PARENT span groups the whole multi-model fan-out into a single trace,
        # with each model's auto-instrumented call nested underneath it.
        with tracer.start_as_current_span("orchestrate.fan_out"):
            run_all()
        print("\n[trace] Spans sent to Application Insights (appi-ai103-l07). View them in "
              "Foundry portal > Tracing, or the App Insights end-to-end view (allow ~1-2 min).")
    else:
        run_all()


if __name__ == "__main__":
    main()
