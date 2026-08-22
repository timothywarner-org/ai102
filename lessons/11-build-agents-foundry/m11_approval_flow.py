#!/usr/bin/env python
"""
M11 demo -- SAFEGUARDS and APPROVAL FLOW CONTROLS (human in the loop).

AI-103 Lesson 11, the objective the other demos do not reach:

  LO5  "Build autonomous or semiautonomous workflows with safeguards and
        approval flow controls"

THE IDEA IN ONE SENTENCE
    An autonomous agent runs every tool it decides to run; a SEMIautonomous
    agent stops at a gate and waits for a human, and this script is that gate.

WHY THIS IS A DIFFERENT DEMO FROM THE HAND-OFF
    m11_multi_agent.py answers "which agent should handle this?" -- routing.
    This one answers "should this action be allowed to happen at all?" -- control.
    Both are agentic; only one of them can spend your money or delete your data.

THE MECHANISM
    Every tool in this course so far has been declared approval_mode="never_require",
    which is why they simply run. Flip a tool to "always_require" and the framework
    stops BEFORE executing it and returns a `function_approval_request` content item
    instead of a result. Your code decides. You then send back a
    `function_approval_response` carrying approved=True or approved=False, and the
    run continues from exactly where it paused.

    That pause is the entire safety story:

        model decides to call refund_invoice
              |
              v
        [ GATE ]  approval_mode="always_require"
              |                                  <-- your code is here, model is blocked
              +-- approved=True  --> tool executes, agent reports the result
              +-- approved=False --> tool NEVER runs, agent reports the refusal

    Note WHERE the gate sits. It is not a prompt asking the model to behave, and
    it is not a check inside the tool body. The model cannot talk its way past it,
    because the executor refuses to invoke the function until a response arrives.
    A safeguard implemented in the system prompt is a suggestion. A safeguard
    implemented here is a control.

THE TWO-TOOL CONTRAST IS THE POINT
    `lookup_invoice`  is read-only  -> never_require -> runs unattended
    `refund_invoice`  moves money   -> always_require -> stops for a human

    Gate everything and you have built a very slow chatbot. Gate nothing and you
    have built an agent that can issue refunds at 3am. Risk-tier your tools.

Setup:  uv sync  ;  az login  ;  cp .env.example .env
Run:    uv run python m11_approval_flow.py              # scripted: approve, then deny
        uv run python m11_approval_flow.py --interactive # you type y/n at the gate
        uv run python m11_approval_flow.py --dry-run     # show the gates, no Azure calls

Idempotent: creates NO Azure resources and moves no real money. The "refund" only
mutates an in-memory dict, so re-run it as often as a take requires.

Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import copy
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

from agent_framework import Agent, Content, Message, tool       # noqa: E402
from agent_framework.foundry import FoundryChatClient           # noqa: E402
from azure.identity import AzureCliCredential                   # noqa: E402
from pydantic import Field                                      # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is convenience only; real env vars still work.
    pass


# =============================================================================
# STATE -- deliberately mutable, so an approved refund has a VISIBLE consequence.
#
# If the gated tool had no side effect, "approved" and "denied" would look
# identical on screen and the demo would prove nothing.
# =============================================================================

# INV-81 is PAID on purpose. An earlier cut of this demo asked the agent to refund
# an *unpaid* invoice, and the model quite reasonably refused to call the tool at
# all -- there is nothing to refund. Correct behavior, useless demo: the gate never
# fired. The fixture has to make the refund a legitimate action so the model
# actually requests it and the SAFEGUARD is what stops it, not the model's judgment.
_INVOICES_SEED: dict[str, dict[str, Any]] = {
    "INV-77": {"total_usd": 420.00, "status": "unpaid", "due": "2026-09-01"},
    "INV-81": {"total_usd": 99.00, "status": "paid", "due": "2026-07-15"},
}

# The invoice the refund scenarios operate on. Paid, therefore refundable.
_REFUND_TARGET = "INV-81"

# Reset between scenarios so each run starts from a known state.
_invoices: dict[str, dict[str, Any]] = copy.deepcopy(_INVOICES_SEED)


# =============================================================================
# TOOLS -- risk-tiered. Read on the left, write on the right.
# =============================================================================


@tool(approval_mode="never_require")
def lookup_invoice(
    invoice_id: Annotated[str, Field(description="The invoice ID, formatted like 'INV-77'.")],
) -> dict[str, Any]:
    """Look up a Contoso invoice total, payment status, and due date by its ID.

    Read-only. Safe to run unattended, which is why it is not gated.
    """
    record = _invoices.get(invoice_id.upper())
    if not record:
        return {"error": "not_found", "invoice_id": invoice_id}
    return {"invoice_id": invoice_id.upper(), **record}


@tool(approval_mode="always_require")
def refund_invoice(
    invoice_id: Annotated[str, Field(description="The invoice ID to refund, formatted like 'INV-77'.")],
    amount_usd: Annotated[float, Field(description="Amount to refund in US dollars.")],
) -> dict[str, Any]:
    """Issue a refund against a Contoso invoice. This moves real money.

    Only call this when the customer has explicitly requested a refund and you
    have confirmed the invoice ID and amount.
    """
    # NOTE FOR THE CAMERA: nothing in this function body checks for approval.
    # It does not need to. The framework guarantees this code is unreachable
    # until an approved=True response comes back through the gate, so the
    # safeguard cannot be bypassed by a tool author who forgot to write a check.
    record = _invoices.get(invoice_id.upper())
    if not record:
        return {"error": "not_found", "invoice_id": invoice_id}
    record["status"] = "refunded"
    record["refunded_usd"] = amount_usd
    return {"invoice_id": invoice_id.upper(), "refunded_usd": amount_usd,
            "status": "refunded", "confirmation": f"RF-{invoice_id.upper()}"}


AGENT_INSTRUCTIONS = (
    "You are Contoso's billing agent. Use lookup_invoice to read invoice details "
    "and refund_invoice to issue a refund when the customer asks for one. "
    "Never guess an amount; look it up first. "
    "If a refund does not go through, tell the customer plainly and do not retry it."
)


# =============================================================================
# THE GATE
# =============================================================================


def find_approval_requests(response: Any) -> list[Content]:
    """Pull every pending approval request out of an agent response.

    `response.user_input_requests` is the framework's supported accessor for
    "the run stopped and needs something from a human". Filtering it down to
    `function_approval_request` matters because it is the general channel for
    user input, and a future demo could raise other kinds through it.

    A response can carry more than one request: a model may batch several tool
    calls into one turn, and each gated call raises its own. Approving one is not
    approving the others, so we collect them all and answer each by id.
    """
    return [
        request
        for request in (getattr(response, "user_input_requests", None) or [])
        if getattr(request, "type", None) == "function_approval_request"
        and getattr(request, "function_call", None) is not None
    ]


def describe_call(request: Content) -> str:
    """Render the pending call as 'name(arg=value, ...)' for the human at the gate.

    This is the security-relevant part of the demo. The human must be shown the
    ARGUMENTS, not just the tool name. "Approve refund_invoice?" is not consent;
    "Approve refund_invoice(invoice_id=INV-77, amount_usd=420.0)?" is.
    """
    call = request.function_call
    name = getattr(call, "name", "?")
    # Arguments arrive as a JSON string from the model. parse_arguments() is the
    # framework's decoder; falling back to the raw value keeps the demo readable
    # if a provider ever hands back something already structured.
    try:
        args = call.parse_arguments() or {}
    except Exception:  # noqa: BLE001 -- display code must not break the gate
        args = getattr(call, "arguments", None) or {}
    if isinstance(args, str):
        return f"{name}({args})"
    rendered = ", ".join(f"{k}={v!r}" for k, v in args.items())
    return f"{name}({rendered})"


def decide(request: Content, interactive: bool, scripted: bool) -> bool:
    """Return the approval decision for one pending call.

    In --interactive mode a human answers. Otherwise the caller's scripted verdict
    is used, which is what keeps the recorded demo deterministic.
    """
    if not interactive:
        return scripted
    answer = input("      approve this call? [y/N] ").strip().lower()
    return answer in ("y", "yes")


async def run_scenario(client: FoundryChatClient, title: str, question: str,
                       *, scripted_verdict: bool, interactive: bool) -> None:
    """Run one request all the way through the gate and report what happened."""
    global _invoices
    _invoices = copy.deepcopy(_INVOICES_SEED)   # fresh state per scenario

    print("-" * 72)
    print(f"  scenario : {title}")
    print(f"  customer : {question}")

    agent = Agent(
        name="billing-agent",
        instructions=AGENT_INSTRUCTIONS,
        client=client,
        tools=[lookup_invoice, refund_invoice],
    )

    # Run inside an AgentSession, which owns the conversation history for us.
    #
    # WHY THIS MATTERS ON A REASONING MODEL (gpt-5-mini, and the gpt-5 family
    # generally): the model emits a `reasoning` item PAIRED with each
    # `function_call` item, and the service rejects any turn that replays the
    # function_call without its reasoning partner:
    #
    #   400 - Item 'fc_...' of type 'function_call' was provided without its
    #         required 'reasoning' item: 'rs_...'
    #
    # The sessionless pattern -- hand-rebuilding [question, assistant_turn,
    # approval] on every round -- drops that reasoning item and fails here. The
    # session keeps the paired items intact, so after the gate we send ONLY the
    # approval response and let the session supply everything before it.
    session = agent.create_session()
    response = await agent.run(question, session=session)

    rounds = 0
    while True:
        pending = find_approval_requests(response)
        if not pending:
            break

        rounds += 1
        replies: list[Content] = []
        for request in pending:
            print(f"    [GATE]  agent wants to call: {describe_call(request)}")
            approved = decide(request, interactive, scripted_verdict)
            print(f"    [HUMAN] {'APPROVED' if approved else 'DENIED'}")
            replies.append(request.to_function_approval_response(approved))

        response = await agent.run(Message("user", replies), session=session)

    if rounds == 0:
        print("    [GATE]  no gated tool was requested (read-only path)")

    print(f"  agent    : {(response.text or '').strip()[:300]}")
    # The state line is the proof. Approved -> 'refunded'. Denied -> still 'paid'.
    print(f"  {_REFUND_TARGET} state after run: {_invoices[_REFUND_TARGET]}")


def required_env(name: str, hint: str) -> str:
    """Return env var ``name`` or exit with a friendly pointer to .env.example."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: environment variable {name} is not set.\n"
                 f"  -> {hint}\n  See .env.example, then: cp .env.example .env")
    return value


def print_gates() -> None:
    print("""
  Risk-tiered tools (the gate is declared on the tool, not in the prompt):

      lookup_invoice   read-only   approval_mode="never_require"    runs unattended
      refund_invoice   moves money approval_mode="always_require"   STOPS for a human

  Flow when a gated tool is requested:

      model requests refund_invoice(...)
            |
        [ GATE ]  <- execution blocked here, function body not yet reached
            |
            +-- approved=True  --> tool runs, agent reports the refund
            +-- approved=False --> tool never runs, agent reports the refusal
""")


async def main_async(args: argparse.Namespace) -> int:
    endpoint = required_env(
        "FOUNDRY_PROJECT_ENDPOINT",
        "https://<account>.services.ai.azure.com/api/projects/<project>")
    model = required_env("FOUNDRY_MODEL", "your chat model deployment name, e.g. gpt-5-mini")

    print("=" * 72)
    print("  AI-103 Lesson 11 -- safeguards and approval flow controls (LO5)")
    print("=" * 72)
    print(f"  endpoint : {endpoint}")
    print(f"  model    : {model}")
    print(f"  mode     : {'interactive (you decide)' if args.interactive else 'scripted (approve, then deny)'}")
    print("=" * 72)
    print_gates()

    client = FoundryChatClient(project_endpoint=endpoint, model=model,
                               credential=AzureCliCredential())

    try:
        # Scenario 1: the happy path. Approve, and the refund really happens.
        await run_scenario(
            client,
            title="refund requested -> APPROVED",
            question=f"Please refund invoice {_REFUND_TARGET} in full.",
            scripted_verdict=True,
            interactive=args.interactive,
        )

        # Scenario 2: the same request, denied. This is the one that proves the
        # gate is a control and not a formality -- the invoice stays 'paid'.
        await run_scenario(
            client,
            title="refund requested -> DENIED",
            question=f"Please refund invoice {_REFUND_TARGET} in full.",
            scripted_verdict=False,
            interactive=args.interactive,
        )

        # Scenario 3: read-only. No gate, no interruption. Shows that gating is
        # per-tool, so unattended work is still unattended.
        await run_scenario(
            client,
            title="read-only question -> no gate",
            question=f"What is the total on invoice {_REFUND_TARGET}?",
            # Inert on this path. `lookup_invoice` is never_require, so no gate
            # fires and nothing ever reads this verdict. It is only here because
            # run_scenario takes the parameter -- True and False behave the same.
            scripted_verdict=True,
            interactive=args.interactive,
        )
    finally:
        with contextlib.suppress(Exception):
            await client.client.close()

    print("-" * 72)
    print(f"\nThe approved run left {_REFUND_TARGET} 'refunded'. The denied run left it")
    print("'paid' -- the tool body never executed, so the safeguard held even though")
    print("the model had already decided to call it. Same request, same agent, same")
    print("model: the only variable was the human at the gate. That is the difference")
    print("between a safeguard written in the prompt and one enforced as a control.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AI-103 L11: human-in-the-loop approval gates on a money-moving tool.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the gate topology and exit. Makes no Azure calls.")
    parser.add_argument("--interactive", action="store_true",
                        help="Answer the approval prompt yourself instead of using the script.")
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN -- gate topology only, no Azure calls.")
        print_gates()
        return 0

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
