#!/usr/bin/env python
"""
M11 demo -- an ORCHESTRATED multi-agent hand-off, traced end to end.

AI-103 Lesson 11 continues objective domain 2. Where Lesson 10 built ONE agent
with tools, this lesson answers the next question: what happens when one agent
is not enough? Two frozen objectives drive this script:

  LO4  "Implement orchestrated multi-agent solutions"
  LO6  "Integrate monitoring into deployed agents, evaluate agent behavior,
        and perform error analysis"

THE PATTERN: HANDOFF
    Three specialists, one front door. `triage` reads the request and hands off
    to whichever specialist owns it. The specialists never talk to the customer
    directly and never talk to each other -- they answer and stop. That is the
    decentralized routing pattern: each agent decides its own next hop rather
    than a central controller scripting every step.

    HandoffBuilder is the framework's first-class implementation. The agents are
    in-process objects, so there is no agent card to publish, no separate
    endpoint to authenticate against, and nothing to provision in the portal
    before this runs.

WHY THIS MATTERS FOR THE MONITORING HALF
    Every hand-off in one run shares a single operation_Id in Application
    Insights. That is precisely what makes the multi-agent KQL query work: you
    can follow one customer question across three agents in one trace. Run this
    script, wait for ingestion, then run kql/multi_agent_handoff.kql.

Setup:  uv sync  ;  az login  ;  cp .env.example .env
Run:    uv run python m11_multi_agent.py
        uv run python m11_multi_agent.py --dry-run   # show the topology, no calls
        uv run python m11_multi_agent.py --no-trace  # skip App Insights export

Idempotent: creates NO Azure resources. Re-run it as often as a take requires;
it only appends telemetry.

Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import sys
import warnings
from typing import Annotated, Any

# VS Code's integrated terminal injects proxy vars on some setups, which makes
# httpx fail with "getaddrinfo failed". These endpoints are public; strip them
# before any client is constructed.
for _proxy_var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                   "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_proxy_var, None)

warnings.filterwarnings("ignore", message=r"\[SKILLS\].*experimental",
                        category=Warning, module=r"agent_framework\._skills")
warnings.filterwarnings("ignore", message=r"\[HARNESS\].*experimental",
                        category=Warning, module=r"agent_framework\._harness\..*")

from agent_framework import Agent, tool                          # noqa: E402
from agent_framework.foundry import FoundryChatClient            # noqa: E402
from agent_framework.orchestrations import HandoffBuilder        # noqa: E402
from azure.identity import AzureCliCredential                    # noqa: E402
from pydantic import Field                                       # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is convenience only; real env vars still work.
    pass


# =============================================================================
# TOOLS -- one per specialist, so each hand-off has visible consequences
# =============================================================================


_INVOICES = {
    "INV-77": {"total_usd": 420.00, "status": "unpaid", "due": "2026-09-01"},
    "INV-81": {"total_usd": 99.00, "status": "paid", "due": "2026-07-15"},
}


@tool(approval_mode="never_require")
def lookup_invoice(
    invoice_id: Annotated[str, Field(description="The invoice ID, formatted like 'INV-77'.")],
) -> dict[str, Any]:
    """Look up a Contoso invoice total, payment status, and due date by its ID.

    Use this whenever a customer asks what they owe or whether an invoice is paid.
    Never guess an amount; always call this tool.
    """
    record = _INVOICES.get(invoice_id.upper())
    if not record:
        # Structured error, not an exception. The agent can report this honestly
        # instead of inventing an amount, and Query C can classify it.
        return {"error": "not_found", "invoice_id": invoice_id}
    return {"invoice_id": invoice_id.upper(), **record}


@tool(approval_mode="never_require")
def check_service_health(
    service: Annotated[str, Field(
        description="Which Contoso service to check.",
        json_schema_extra={"enum": ["portal", "api", "email"]})],
) -> dict[str, Any]:
    """Report the current operational health of a named Contoso service.

    Use this when a customer reports an outage or says something is not working.
    """
    # A real tool would query your status page. Fixed values keep the demo
    # hermetic so a recording never depends on live infrastructure.
    health = {"portal": "degraded", "api": "healthy", "email": "healthy"}
    return {"service": service, "state": health.get(service, "unknown"),
            "note": "Portal latency elevated in East US 2." if service == "portal" else "No active incidents."}


# =============================================================================
# THE AGENTS
#
# Instructions are ROUTING LOGIC. In a handoff workflow the model reads each
# participant's instructions to decide where a request belongs, so vague
# instructions produce wrong hand-offs. Name the boundaries explicitly.
# =============================================================================

TRIAGE_INSTRUCTIONS = (
    "You are Contoso's front desk. You do not answer questions yourself. "
    "Read the customer's request and hand off to exactly one specialist: "
    "billing for invoices, payments, refunds, or anything about money; "
    "support for outages, errors, or anything not working. "
    "Hand off immediately without asking clarifying questions."
)

BILLING_INSTRUCTIONS = (
    "You are Contoso's billing specialist. Answer questions about invoices and "
    "payments, using lookup_invoice for any specific invoice. "
    "Keep the answer to one or two sentences. Do not hand off again."
)

SUPPORT_INSTRUCTIONS = (
    "You are Contoso's technical support specialist. Answer questions about "
    "outages and errors, using check_service_health for service status. "
    "Keep the answer to one or two sentences. Do not hand off again."
)


def build_agents(client: FoundryChatClient) -> tuple[Agent, Agent, Agent]:
    """Create the three participants.

    require_per_service_call_history_persistence=True is MANDATORY for every
    participant in a handoff workflow. Without it HandoffBuilder raises a
    ValueError at build time, because middleware can short-circuit a tool call
    and leave the call and its result mismatched in the history.
    """
    common = {"client": client, "require_per_service_call_history_persistence": True}
    triage = Agent(name="triage", instructions=TRIAGE_INSTRUCTIONS, **common)
    billing = Agent(name="billing", instructions=BILLING_INSTRUCTIONS,
                    tools=[lookup_invoice], **common)
    support = Agent(name="support", instructions=SUPPORT_INSTRUCTIONS,
                    tools=[check_service_health], **common)
    return triage, billing, support


# The three requests, chosen so the routing decision is unambiguous on camera.
SCENARIOS = [
    ("billing", "What is the total on invoice INV-77?"),
    ("support", "The Contoso portal is really slow today. Is something wrong?"),
    ("billing", "Can you tell me about invoice INV-999?"),  # deliberate miss
]


def print_events(events: Any) -> tuple[str | None, str | None]:
    """Print the meaningful workflow events; return (routed_to, final answer).

    The event stream IS the teaching artifact: it shows the request entering
    triage, the hand-off firing, and the specialist answering.

    Two details worth knowing, because both produce confusing output if ignored:

      * `executor_invoked` fires for EVERY participant on every superstep, not
        just the one doing work. The idle ones complete immediately with no
        output. Printing them all makes it look like each agent ran three times,
        so we only report an agent when it actually produced output.
      * There is more than one `output` event. Triage emits one when it routes,
        and the specialist emits the real answer later. The LAST one is the
        answer, so we must not stop at the first.
    """
    routed_to: str | None = None
    final_text: str | None = None

    for event in events:
        etype = getattr(event, "type", None)
        data = getattr(event, "data", None)

        if etype == "handoff_sent":
            # The money line for LO4.
            source = getattr(data, "source", "?")
            target = getattr(data, "target", "?")
            routed_to = target
            print(f"    -> HAND-OFF      : {source} -> {target}")
        elif etype == "output":
            who = getattr(event, "executor_id", "?")
            text = (getattr(data, "text", "") or "").strip()
            if not text:
                continue
            if who == routed_to:
                # The specialist's answer. Keep the last one we see.
                final_text = text
                print(f"    -> answered by   : {who}")
    return routed_to, final_text


async def run_scenario(build_workflow: Any, expected: str, question: str) -> bool:
    """Run one customer request through a FRESH workflow and report the routing.

    Each scenario gets its own workflow instance on purpose. A handoff workflow
    ends its turn by emitting a `request_info` event -- it is waiting for the
    customer's next reply. Feeding a new, unrelated question into that same
    instance leaves the previous cycle pending and carries the old conversation
    forward, so every scenario would answer with the FIRST scenario's data.
    Three separate customers means three separate workflows.
    """
    print(f"\n  customer: {question}")
    print(f"  expected route: {expected}")

    workflow = build_workflow()
    # workflow.run() returns a WorkflowRunResult, which is itself a list of events.
    result = await workflow.run(question)
    events = list(result)

    routed_to, final_text = print_events(events)

    ok = routed_to == expected
    print(f"    -> routed to     : {routed_to or '(no hand-off)'}  "
          f"[{'as expected' if ok else 'UNEXPECTED'}]")
    if final_text:
        print(f"  answer: {final_text[:220]}")
    else:
        print("  answer: (no specialist output captured)")
    return ok


def configure_tracing(enabled: bool) -> bool:
    """Wire OpenTelemetry to Application Insights. Returns True if tracing is on.

    Tracing is OPTIONAL by design: if the connection string is missing the demo
    still runs the hand-off, it just says so. A missing env var should never
    take down a live demo.
    """
    if not enabled:
        print("  tracing  : off (--no-trace)")
        return False

    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn or conn.startswith("InstrumentationKey=<"):
        print("  tracing  : off (APPLICATIONINSIGHTS_CONNECTION_STRING not set)")
        return False

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from agent_framework.observability import create_resource, enable_sensitive_telemetry

        # create_resource() stamps the service name onto every span, which is how
        # cloud_RoleName gets set in App Insights. Set OTEL_SERVICE_NAME to control it.
        os.environ.setdefault("OTEL_SERVICE_NAME", "ai103-m11-multi-agent")
        configure_azure_monitor(connection_string=conn, resource=create_resource())
        # Opt in to capturing prompts and completions on the spans. Fine for a
        # teaching subscription; think carefully before enabling on real customer data.
        enable_sensitive_telemetry()
        print(f"  tracing  : ON -> {os.environ['OTEL_SERVICE_NAME']}")
        return True
    except Exception as exc:  # noqa: BLE001 -- telemetry must never break the demo
        print(f"  tracing  : off (setup failed: {type(exc).__name__}: {exc})")
        return False


def required_env(name: str, hint: str) -> str:
    """Return env var ``name`` or exit with a friendly pointer to .env.example."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: environment variable {name} is not set.\n"
                 f"  -> {hint}\n  See .env.example, then: cp .env.example .env")
    return value


def print_topology() -> None:
    print("""
  Handoff topology (decentralized routing, triage decides the hop):

      customer
         |
         v
      [triage]  -- reads the request, routes, answers nothing itself
         |
         +--> [billing]  tools: lookup_invoice
         |
         +--> [support]  tools: check_service_health
""")


async def main_async(args: argparse.Namespace) -> int:
    endpoint = required_env(
        "FOUNDRY_PROJECT_ENDPOINT",
        "https://<account>.services.ai.azure.com/api/projects/<project>")
    model = required_env("FOUNDRY_MODEL", "your chat model deployment name, e.g. gpt-5-mini")

    print("=" * 72)
    print("  AI-103 Lesson 11 -- orchestrated multi-agent hand-off")
    print("=" * 72)
    print(f"  endpoint : {endpoint}")
    print(f"  model    : {model}")
    print(f"  pattern  : HandoffBuilder (triage -> billing | support)")
    traced = configure_tracing(enabled=not args.no_trace)
    print("=" * 72)
    print_topology()

    client = FoundryChatClient(project_endpoint=endpoint, model=model,
                               credential=AzureCliCredential())

    def build_workflow():
        """Build one handoff workflow with a fresh set of participants.

        Decentralized routing: triage is the entry point and every specialist is
        a reachable target. add_handoff() would let you restrict who can reach
        whom if you wanted a stricter topology.
        """
        triage, billing, support = build_agents(client)
        return (
            HandoffBuilder()
            .participants([triage, billing, support])
            .with_start_agent(triage)
            .build()
        )

    correct = 0
    try:
        for expected, question in SCENARIOS:
            print("-" * 72)
            if await run_scenario(build_workflow, expected, question):
                correct += 1
    finally:
        with contextlib.suppress(Exception):
            await client.client.close()

    print("-" * 72)
    print(f"\nRouting accuracy: {correct}/{len(SCENARIOS)} requests reached the right specialist.")
    if traced:
        print("\nTelemetry sent. Allow 1-3 minutes for App Insights ingestion, then run")
        print("the queries in kql/ against your Application Insights resource.")
        print("Every hand-off above shares ONE operation_Id -- that is what makes")
        print("the multi-agent query able to follow a request across three agents.")
    return 0 if correct == len(SCENARIOS) else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AI-103 L11: an orchestrated multi-agent hand-off, traced end to end.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the handoff topology and exit. Makes no Azure calls.")
    parser.add_argument("--no-trace", action="store_true",
                        help="Run the hand-off but do not export telemetry.")
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN -- topology only, no Azure calls.")
        print_topology()
        for expected, question in SCENARIOS:
            print(f"  would ask [{expected:>7}] : {question}")
        return 0

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
