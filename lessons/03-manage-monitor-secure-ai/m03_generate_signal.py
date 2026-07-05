#!/usr/bin/env python
"""
M03 signal GENERATOR -- emit REAL GenAI telemetry, then catch it with KQL.

The read-only demo (m03_ops_demo.py) proves the Observability pipe is WIRED: it prints
"Application Insights: CONNECTED". This script proves the pipe CARRIES DATA. It makes real
gpt-5-mini calls through the Foundry project, auto-instruments them with OpenTelemetry GenAI
semantic conventions, and exports the spans to the project's Application Insights resource.

Unlike the read-only demo, this script PRODUCES telemetry (it calls a model and writes traces).
It is still safe -- it creates no Azure resources and deletes nothing -- but it is a WRITER, so
it lives in its own file, not inside the three read-only signals.

  1. Fetch the project's Application Insights connection string (same call LO2 makes).
  2. configure_azure_monitor(...) so every span is exported to that resource.
  3. Auto-instrument the OpenAI client -> each chat call emits a `gen_ai` span with model,
     token usage, and latency, following OpenTelemetry GenAI semantic conventions.
  4. Make a handful of real gpt-5-mini calls under one parent span (one trace = one OperationId).
  5. Print that OperationId and the exact KQL so you can catch the trace on screen.

Traces typically appear in Application Insights within 2-5 minutes.

Setup: uv sync ; az login ; copy .env.example to .env (add MODEL_DEPLOYMENT_NAME)
Run:   uv run python m03_generate_signal.py
       uv run python m03_generate_signal.py --calls 5 --content   # capture prompt/response text

Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
"""

import argparse
import os
import sys
import time

# Content capture (prompt + completion text on the span) must be turned ON *before* the OpenAI
# instrumentation is imported/applied, because the instrumentor reads this flag at instrument time.
# It is OFF by default because prompts can contain personal data -- only enable it for a demo.
if "--content" in sys.argv:
    os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

from azure.identity import AzureCliCredential
from azure.ai.projects import AIProjectClient
from azure.core.exceptions import ResourceNotFoundError

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def required(name: str, hint: str) -> str:
    """Return env var ``name`` or exit with a friendly hint. See .env.example."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: {name} is not set.\n  -> {hint}\n  See .env.example.")
    return value


# One realistic multi-turn set so the traces look like a real workload, not "hello world".
# Contoso is the Microsoft Press house sample company.
PROMPTS = [
    "In one sentence, what does an Azure AI Search index actually store?",
    "Name three signals you'd monitor to catch model quality drift in production.",
    "Contoso's support bot got slower this week. List two Application Insights metrics to check first.",
    "Explain 'groundedness' for a RAG chatbot in one plain sentence.",
    "What is one reason token-per-minute (TPM) quota headroom matters for scaling?",
]


def main() -> None:
    ap = argparse.ArgumentParser(description="AI-103 L3: generate real GenAI telemetry and print the KQL to catch it.")
    ap.add_argument("--calls", type=int, default=3, help="How many model calls to make (default 3).")
    ap.add_argument("--content", action="store_true", help="Capture prompt/response text on spans (dev only).")
    args = ap.parse_args()

    endpoint = required("FOUNDRY_PROJECT_ENDPOINT",
                        "https://<resource>.services.ai.azure.com/api/projects/<project>")
    deployment = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-5-mini")

    cred = AzureCliCredential()
    project = AIProjectClient(endpoint=endpoint, credential=cred)

    # --- 1 + 2: point OpenTelemetry at the project's Application Insights ----------------------
    try:
        conn = project.telemetry.get_application_insights_connection_string()
    except ResourceNotFoundError:
        sys.exit("ERROR: no Application Insights connected to this project.\n"
                 "  -> Connect one in Foundry > Monitoring, then re-run. (Nothing to trace into yet.)")

    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor(connection_string=conn)

    # --- 3: auto-instrument the OpenAI client so each call becomes a gen_ai span ---------------
    from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
    OpenAIInstrumentor().instrument()

    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)

    # Keyless OpenAI client from the project: bearer token from your az login identity, base_url
    # already pointed at the Foundry endpoint. No API key anywhere.
    client = project.get_openai_client()

    n = max(1, args.calls)
    print(f"\nGenerating {n} real '{deployment}' call(s). Content capture: {'ON' if args.content else 'off'}.")

    # --- 4: one parent span => one trace => one OperationId that ties the whole run together ---
    with tracer.start_as_current_span("m03.generate_signal") as parent:
        trace_id = format(parent.get_span_context().trace_id, "032x")
        for i in range(n):
            prompt = PROMPTS[i % len(PROMPTS)]
            started = time.perf_counter()
            try:
                # gpt-5 family: no custom temperature, no max_tokens -- keep the call minimal so the
                # reasoning budget isn't starved and the completion isn't empty.
                resp = client.chat.completions.create(
                    model=deployment,
                    messages=[
                        {"role": "system", "content": "You are Contoso's concise AI ops assistant."},
                        {"role": "user", "content": prompt},
                    ],
                )
                elapsed_ms = (time.perf_counter() - started) * 1000
                usage = resp.usage
                answer = (resp.choices[0].message.content or "").strip().replace("\n", " ")
                print(f"  [{i+1}/{n}] {elapsed_ms:6.0f} ms  "
                      f"tokens(in/out)={usage.prompt_tokens}/{usage.completion_tokens}  "
                      f"| {answer[:70]}{'...' if len(answer) > 70 else ''}")
            except Exception as exc:  # one failed call still leaves a span; keep the run going
                print(f"  [{i+1}/{n}] call failed: {type(exc).__name__}: {exc}")

    # --- 5: flush the exporter so spans leave the process, then hand over the KQL --------------
    print("\nFlushing telemetry to Application Insights...")
    trace.get_tracer_provider().force_flush()

    workspace_guid = "aa91adf2-e06f-4ff6-9038-9807cfb8c970"  # log-ai103-l03 (backs appi-ai103-l03)
    print("Done. Traces usually land in 2-5 minutes.\n")
    print("=" * 78)
    print(f"OperationId for THIS run: {trace_id}")
    print("=" * 78)
    print("Catch it with KQL (Log Analytics workspace log-ai103-l03):\n")
    print("  AppDependencies")
    print(f"  | where OperationId == '{trace_id}'")
    print("  | project TimeGenerated, Name, DurationMs, Properties")
    print("  | order by TimeGenerated asc\n")
    print("Or run it from the CLI:")
    print(f"  az monitor log-analytics query -w {workspace_guid} \\")
    print(f"    --analytics-query \"AppDependencies | where OperationId == '{trace_id}' "
          "| project TimeGenerated, Name, DurationMs | order by TimeGenerated asc\"")


if __name__ == "__main__":
    main()
