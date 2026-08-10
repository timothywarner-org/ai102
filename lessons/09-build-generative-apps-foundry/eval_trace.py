"""
eval_trace.py -- Lesson 9 demo: EVALUATE + OBSERVE a Foundry RAG app.

This is the code spine of Lesson 9. It does the two things L9 is about, against
the same Contoso Cloud RAG index you built in Lesson 8:

  OBSERVE   Instrument a real RAG turn with OpenTelemetry and ship the traces,
            token counts, and latency to Application Insights. You then watch
            them two ways: in the Azure portal (App Insights > Transaction
            search) and in the Foundry portal (your project > Tracing), and you
            slice them with KQL in Log Analytics (see kql/traces.kql).

  EVALUATE  Score the app's answers with Foundry's built-in evaluators --
            Groundedness (does the answer stick to its sources?) and Relevance
            (does it address the question?) -- then gate on a pass threshold.

Everything is keyless (Entra ID via `az login`) and idempotent -- re-run any
subcommand as many times as you like; it only ever reads the index and appends
fresh telemetry, never mutating state.

SUBCOMMANDS
    uv run eval_trace.py trace        # emit traced RAG turns to App Insights
    uv run eval_trace.py evaluate     # score answers + gate on a threshold
"""

from __future__ import annotations

import argparse
import os
import time

from dotenv import load_dotenv

# override=True makes THIS project's .env authoritative over any stale shell vars.
load_dotenv(override=True)

# Strip inherited HTTP(S)_PROXY vars (VS Code's integrated terminal injects them
# on some setups) -- they point at a proxy that may not resolve, which makes
# httpx fail with "getaddrinfo failed". These demos hit public Azure endpoints
# directly, no proxy needed.
for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_pv, None)

# Capture prompt/response content on the spans BEFORE instrumenting -- this env
# var is read at instrumentation time, so it must be set first.
os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")

from openai import AzureOpenAI
from azure.identity import AzureCliCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

# --- Observability wiring -----------------------------------------------------
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor

# -----------------------------------------------------------------------------
# Config -- all from .env, keyless.
# -----------------------------------------------------------------------------
SEARCH_ENDPOINT = os.environ["SEARCH_ENDPOINT"]
AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
INDEX_NAME = os.getenv("SEARCH_INDEX_NAME", "contoso-support")
EMBEDDING_DEPLOYMENT = os.getenv("EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-large")
CHAT_DEPLOYMENT = os.getenv("CHAT_DEPLOYMENT_NAME", "gpt-5-mini")
APPINSIGHTS_CONN = os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
GROUNDEDNESS_GATE = float(os.getenv("GROUNDEDNESS_GATE", "3.0"))  # 1-5 scale

COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"
CREDENTIAL = AzureCliCredential()
_TOKEN_PROVIDER = get_bearer_token_provider(CREDENTIAL, COGNITIVE_SCOPE)

# One-time telemetry setup: route OTel to App Insights, then auto-instrument the
# OpenAI client so every embedding and chat call becomes a span with token and
# latency attributes -- no per-call tracing code required.
configure_azure_monitor(connection_string=APPINSIGHTS_CONN)
OpenAIInstrumentor().instrument()
tracer = trace.get_tracer("ai103.lesson09")

# Sample questions -- answerable from Tim's M365 prompt-engineering knowledge base.
SAMPLE_QUESTIONS = [
    "What is few-shot learning and when should I use it?",
    "How do the temperature and top_p parameters differ?",
    "How does asking the model for citations reduce fabrication?",
    "Why should I provide grounding context to a model?",
]

# Evaluation set: questions we already know the index can answer. The RAG app
# generates the response and context at run time; the evaluators score them.
EVAL_QUESTIONS = SAMPLE_QUESTIONS


def openai_client() -> AzureOpenAI:
    # max_retries rides out transient network/DNS blips and 429s with backoff,
    # so a momentary hiccup doesn't abort a traced run mid-flight.
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=_TOKEN_PROVIDER,
        api_version=AZURE_OPENAI_API_VERSION,
        max_retries=6,
        timeout=30.0,
    )


def search_client() -> SearchClient:
    return SearchClient(SEARCH_ENDPOINT, INDEX_NAME, credential=CREDENTIAL)


def rag_turn(client: AzureOpenAI, sc: SearchClient, question: str) -> dict:
    """One full RAG turn: retrieve -> inject -> generate. Returns answer+context.

    The whole turn runs inside a parent span, so retrieval and the model call
    show up as its children in App Insights and the Foundry tracing view -- one
    tidy tree per question.
    """
    with tracer.start_as_current_span("rag.turn") as span:
        span.set_attribute("rag.question", question)

        # Retrieve (hybrid: keyword + vector).
        qvec = client.embeddings.create(model=EMBEDDING_DEPLOYMENT, input=[question]).data[0].embedding
        hits = list(sc.search(
            search_text=question,
            vector_queries=[VectorizedQuery(vector=qvec, k_nearest_neighbors=3, fields="contentVector")],
            select=["title", "content"], top=3,
        ))
        context = "\n\n".join(f"[{h['title']}]\n{h['content']}" for h in hits)
        span.set_attribute("rag.retrieved_titles", ", ".join(h["title"] for h in hits))

        # Generate, grounded strictly in the retrieved context.
        system = ("You are a knowledge assistant answering from the user's own documents. "
                  "Answer using ONLY the context below; cite the article titles you used in "
                  f"brackets. If the answer isn't in the context, say so.\n\nContext:\n{context}")
        answer = client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": question}],
            # gpt-5-mini is a reasoning model: reasoning tokens count against this
            # budget, so keep it generous or the visible answer comes back empty.
            max_completion_tokens=1500,
        ).choices[0].message.content or "(empty)"

        # Surface the trace id so you can find this exact turn in App Insights
        # (it lands as operation_Id) and in the Foundry portal Tracing view.
        trace_id = format(span.get_span_context().trace_id, "032x")
        return {"question": question, "answer": answer, "context": context, "trace_id": trace_id}


def cmd_trace(args) -> None:
    """OBSERVE: run sample questions as traced RAG turns; ship telemetry to App Insights."""
    client, sc = openai_client(), search_client()
    questions = SAMPLE_QUESTIONS[: args.n] if args.n else SAMPLE_QUESTIONS
    print(f"[trace] running {len(questions)} traced RAG turns -> App Insights...\n")
    for i, q in enumerate(questions, 1):
        result = rag_turn(client, sc, q)
        print(f"  {i}. {q}")
        print(f"     answer : {result['answer'][:110]}...")
        print(f"     trace  : operation_Id = {result['trace_id']}\n")

    # Force a flush so the batched spans actually leave the process before exit;
    # otherwise a short-lived script can quit before telemetry is sent.
    trace.get_tracer_provider().force_flush()
    print("[trace] telemetry flushed. Allow ~1-3 min for App Insights ingestion, then:")
    print("        * Azure portal  -> appi-ai103-l09 > Transaction search")
    print("        * Foundry portal -> proj-lesson-08 > Tracing")
    print("        * Log Analytics  -> run the queries in kql/traces.kql")


def cmd_evaluate(_args) -> None:
    """EVALUATE: score each answer with Groundedness + Relevance, then gate."""
    # Imported here so the `trace` path doesn't pay for the evaluation SDK.
    from azure.ai.evaluation import GroundednessEvaluator, RelevanceEvaluator

    client, sc = openai_client(), search_client()

    # The evaluators call a judge model to score. gpt-5-mini is a reasoning
    # model, so is_reasoning_model=True adjusts the call (max_completion_tokens,
    # no temperature). Keyless: pass the credential, no api_key.
    model_config = {
        "azure_endpoint": AZURE_OPENAI_ENDPOINT,
        "azure_deployment": CHAT_DEPLOYMENT,
        "api_version": AZURE_OPENAI_API_VERSION,
    }
    groundedness = GroundednessEvaluator(model_config, credential=CREDENTIAL, is_reasoning_model=True)
    relevance = RelevanceEvaluator(model_config, credential=CREDENTIAL, is_reasoning_model=True)

    print(f"[evaluate] scoring {len(EVAL_QUESTIONS)} answers "
          f"(Groundedness + Relevance, 1-5; gate >= {GROUNDEDNESS_GATE})\n")
    print(f"  {'GND':>4} {'REL':>4}  question")
    print(f"  {'-'*4} {'-'*4}  {'-'*40}")

    def fmt(x):
        return f"{x:>4.1f}" if isinstance(x, (int, float)) else f"{'?':>4}"

    passed = 0
    for q in EVAL_QUESTIONS:
        turn = rag_turn(client, sc, q)
        g = groundedness(query=q, response=turn["answer"], context=turn["context"])
        r = relevance(query=q, response=turn["answer"], context=turn["context"])
        g_score = g.get("groundedness", g.get("gpt_groundedness"))
        r_score = r.get("relevance", r.get("gpt_relevance"))
        ok = isinstance(g_score, (int, float)) and g_score >= GROUNDEDNESS_GATE
        passed += int(ok)
        flag = "PASS" if ok else "FAIL"
        print(f"  {fmt(g_score)} {fmt(r_score)}  [{flag}] {q[:44]}")

    rate = passed / len(EVAL_QUESTIONS) * 100
    print(f"\n[gate] {passed}/{len(EVAL_QUESTIONS)} passed the groundedness gate ({rate:.0f}%).")
    # This is the release-gate move from the slides: a build that can't clear the
    # bar doesn't ship. Returning a non-zero-ish signal is what a CI step checks.
    print("[gate] " + ("SHIP -- quality bar met." if rate == 100
                        else "HOLD -- at least one answer fell below the bar."))

    trace.get_tracer_provider().force_flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="Lesson 9: evaluate + observe a Foundry RAG app.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_trace = sub.add_parser("trace", help="emit traced RAG turns to App Insights")
    p_trace.add_argument("--n", type=int, default=0, help="how many sample questions (default: all)")
    sub.add_parser("evaluate", help="score answers with Foundry evaluators + gate")
    args = parser.parse_args()
    {"trace": cmd_trace, "evaluate": cmd_evaluate}[args.command](args)


if __name__ == "__main__":
    main()
