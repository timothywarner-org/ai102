#!/usr/bin/env python
"""
function_calling.py -- the function-calling loop, printed step by step.

AI-103 LESSON 10, SEGMENT 2. This is the slow-walk companion to m10_tools_repl.py.
Where the REPL is interactive, this script asks ONE question start to finish and
narrates every stage, so the boundary is impossible to miss on camera.

The one idea to land: THE MODEL NEVER RUNS YOUR CODE. It reads your tool SCHEMA,
decides which tool fits, and emits a REQUEST to call it. Your process executes the
function. The result goes back. The model continues. Request, execute, continue.

Built on the Microsoft Agent Framework, the same SDK as m10_tools_repl.py. Two
reasons that matters here, and both are exam-relevant:

  1. FoundryChatClient is the supported client for a Foundry PROJECT endpoint
     (https://<account>.services.ai.azure.com/api/projects/<project>).
  2. The tool SCHEMA is generated from the Python signature, which removes the
     most common bug in hand-rolled function calling: a hand-written schema that
     drifts out of sync with the function it claims to describe.

Five beats, and each one is a beat in the runbook:
    1. The tool SCHEMA, generated from the decorator, as the service receives it
    2. The model DECIDES -- middleware catches the request BEFORE your code runs
    3. YOUR CODE runs -- the same middleware catches what you returned
    4. The TURN read back -- content sequence, stop signals, token usage
    5. The ANSWER the model composed from your result

Beats 2 and 3 print from inside FunctionMiddleware while the turn is still in
flight. That is deliberate: the seam is shown as it happens rather than
reconstructed afterwards.

The shape of a tool turn, verified live against gpt-5-mini:

    assistant [text_reasoning, function_call]     <- the model thinks, then asks
    tool      [function_result]                   <- YOUR code ran
    assistant [text_reasoning, text]              <- it thinks again, then answers

The spine is fixed: function_call is always followed by function_result. The
text_reasoning items are NOT fixed. gpt-5-mini emits them wherever it stopped to
think, so some turns carry two and some carry one -- m10_tools_repl.py routinely
shows four items where this script shows five. Do not promise a fixed shape on
camera. Ask something no tool matches and there is no call at all.

Setup:  uv sync  ;  az login  ;  cp .env.example .env
Run:    uv run python function_calling.py
        uv run python function_calling.py --dry-run   # schema only, no Azure calls

IDEMPOTENT: this demo creates NO Azure resources and mutates NO state. It is a
read-only conversation against an existing deployment, so it is safe to re-run as
many times as a take requires. There is nothing to clean up between runs.

Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import sys
import warnings
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

# VS Code's integrated terminal injects proxy vars on some setups, which makes
# httpx fail with "getaddrinfo failed". These endpoints are public; strip them
# before any client is constructed.
for _proxy_var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                   "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_proxy_var, None)

# Agent Framework emits experimental-API warnings at import time for the skill and
# harness internals used by the GA Foundry path. Filter those known notices before
# import so the recorded output stays focused, while Python still reports anything
# unrelated.
warnings.filterwarnings("ignore", message=r"\[SKILLS\].*experimental",
                        category=Warning, module=r"agent_framework\._skills")
warnings.filterwarnings("ignore", message=r"\[HARNESS\].*experimental",
                        category=Warning, module=r"agent_framework\._harness\..*")

from agent_framework import (                              # noqa: E402
    Agent,
    FunctionInvocationContext,
    FunctionMiddleware,
    tool,
)
from agent_framework.foundry import FoundryChatClient      # noqa: E402
from azure.identity import AzureCliCredential              # noqa: E402
from pydantic import Field                                 # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is convenience only; real env vars still work.
    pass

# The framework's OpenTelemetry serializer only recognizes FunctionTool / pydantic
# model / dict when building span attributes, so some tool objects make it log a
# benign "Can't parse tool." WARNING on every run. Drop that one message so the
# console stays clean, without muting genuine agent_framework warnings.
logging.getLogger("agent_framework").addFilter(
    lambda record: record.getMessage() != "Can't parse tool."
)

QUESTION = "What's the status of ticket CS-1042? Give me the full detail."

INSTRUCTIONS = (
    "You are Contoso's support desk assistant. "
    "Use your tool to look up ticket status and never guess a status. "
    "Keep answers to a sentence or two."
)


# =============================================================================
# OUR IMPLEMENTATION
# =============================================================================

# Stands in for a real ticketing API. The point on camera is that this dictionary
# is on YOUR side of the boundary. The model never sees it and never reads it.
TICKETS: dict[str, dict[str, Any]] = {
    "CS-1042": {
        "ticket_id": "CS-1042",
        "status": "awaiting_customer",
        "priority": "P2",
        "owner": "Tim Warner",
        "last_update": "Customer asked for a callback window.",
    }
}


# =============================================================================
# THE TOOL
#
# Read this as a PROMPT, not as plumbing. Every part is doing work, and the exam
# tests why. With the Agent Framework you do NOT hand-write JSON: the schema is
# generated from the Python signature, so code and schema cannot drift apart.
#
#   the function name   -- descriptive, not abbreviated. The model reads it first.
#   the DOCSTRING       -- becomes the tool description, the single
#                          highest-leverage string in the whole file. The model
#                          re-reads it on EVERY turn to decide what to call.
#                          Vague descriptions are the number one cause of wrong
#                          tool selection.
#   Field(description=) -- becomes each parameter's description.
#   json_schema_extra   -- carries the enum. An enum turns a class of runtime
#                          failure into a schema constraint: the model cannot
#                          invent a detail level that is not in the list.
#   the DEFAULT value   -- keeps `detail` OUT of the schema's required[] list
#                          while `ticket_id` stays required. Required is what
#                          makes the model ask a follow-up question rather than
#                          guess a ticket number.
# =============================================================================


@tool(approval_mode="never_require")
def get_ticket_status(
    ticket_id: Annotated[str, Field(
        description="The Contoso ticket ID, formatted like 'CS-1042'.")],
    detail: Annotated[str, Field(
        description="How much history to return. Defaults to summary.",
        json_schema_extra={"enum": ["summary", "full"]})] = "summary",
) -> dict[str, Any]:
    """Look up the current status of a Contoso support ticket by its ID.

    Use this whenever the user asks about a specific ticket number.
    Never guess a ticket's status; always call this tool.
    """
    # A real tool would call your ticketing API here. Set a breakpoint on this
    # line to prove that execution genuinely lands in YOUR process.
    record = TICKETS.get(ticket_id.upper())
    if not record:
        # Return a STRUCTURED error rather than raising. The model can reason
        # about this and tell the user honestly instead of inventing a status.
        return {"error": "not_found", "ticket_id": ticket_id}
    if detail == "summary":
        return {k: record[k] for k in ("ticket_id", "status", "priority")}
    return record


def rule(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def as_pretty_json(payload: Any) -> str:
    """Pretty-print a payload that may arrive as a JSON string.

    The framework serializes tool arguments and tool results to JSON strings
    before they cross the wire. Parsing them back keeps the demo readable
    instead of putting one long escaped string on screen.
    """
    if isinstance(payload, str):
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            payload = json.loads(payload)
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, indent=2, default=str)
    return str(payload)


# =============================================================================
# THE BOUNDARY, MADE VISIBLE
#
# FunctionMiddleware sits exactly on the seam this lesson is about. Everything
# before `await call_next()` runs when the model has REQUESTED a call but nothing
# has executed yet. Everything after it runs once YOUR function has returned.
# Printing on both sides of that single await is the clearest way to show
# request / execute / continue as it actually happens.
# =============================================================================


class BoundaryMiddleware(FunctionMiddleware):
    """Narrate both sides of every tool call while the turn is still in flight."""

    async def process(self, context: FunctionInvocationContext,
                      call_next: Callable[[], Awaitable[None]]) -> None:
        rule("2. THE MODEL DECIDED -- it is REQUESTING a call, nothing has run yet")
        print(f"  tool requested : {context.function.name}")
        print(f"  arguments      : {as_pretty_json(context.arguments)}")
        print("\n  The model produced those arguments by reading the SCHEMA above.")
        print("  get_ticket_status has NOT executed at this point.")

        # This single await is where control crosses into your code and returns.
        await call_next()

        rule("3. YOUR CODE ran and returned")
        # GOTCHA worth saying out loud: by the time middleware sees
        # `context.result`, the framework has already wrapped the return value in
        # a list of Content objects and put the serialized payload on `.text`.
        # It is NOT the raw dict the function returned. Reach through the wrapper
        # or you will print `[<Content object at 0x...>]` on camera.
        result = context.result
        if isinstance(result, list):
            for item in result:
                print(as_pretty_json(getattr(item, "text", None) or item))
        else:
            print(as_pretty_json(result))
        print("\n  That ran in OUR process, against OUR dictionary. The framework")
        print("  carried the result back to the model for us. Hand-rolled, this is")
        print("  the second request you would have to build and send yourself.")


# =============================================================================
# READING THE TURN BACK OUT
# =============================================================================


def turn_shape(response) -> list[str]:
    """Return the honest content-type sequence for the whole turn."""
    return [
        content.type
        for message in response.messages
        for content in (getattr(message, "contents", []) or [])
        if getattr(content, "type", None)
    ]


def contents_of_type(response, wanted: str) -> list[Any]:
    """Return every content item of one type, across all messages in the turn."""
    return [
        content
        for message in response.messages
        for content in (getattr(message, "contents", []) or [])
        if getattr(content, "type", None) == wanted
    ]


def stop_signals(response) -> tuple[Any, Any, Any]:
    """Return (finish_reason, status, incomplete_details) for a finished turn.

    There are TWO stop signals here and the exam cares about the difference:

      finish_reason -- the framework's normalized answer, 'stop' on a clean turn.
      status        -- the service's own answer, on the raw OpenAI Response two
                       wrappers down. 'completed' means the model chose to stop.
                       'incomplete', with incomplete_details explaining why, means
                       it was CUT OFF, usually by a token cap. That is the failure
                       mode people misread as "the model just gave a short answer".
    """
    inner = getattr(getattr(response, "raw_representation", None),
                    "raw_representation", None)
    return (
        getattr(response, "finish_reason", None),
        getattr(inner, "status", None) or "unknown",
        getattr(inner, "incomplete_details", None),
    )


def print_usage(response) -> None:
    """Print token usage, including the reasoning tokens people forget to budget.

    usage_details is a plain dict on this path. reasoning_output_token_count is
    the one to call out: gpt-5-mini is a REASONING model, and its hidden thinking
    is billed as OUTPUT and counts against your output cap even though it never
    appears in the answer.
    """
    usage = response.usage_details or {}
    print(f"  tokens in/out  : {usage.get('input_token_count')}/"
          f"{usage.get('output_token_count')}"
          f"   (total {usage.get('total_token_count')})")
    print(f"  of which hidden reasoning: {usage.get('reasoning_output_token_count')}")


# =============================================================================
# THE DEMO
# =============================================================================


def print_schema() -> None:
    """Print the REAL schema the service receives, generated from the decorator.

    to_json_schema_spec() reads the live FunctionTool, so what prints here is
    what actually goes on the wire. Nothing is hand-assembled, so nothing in this
    output can drift away from the function above it.
    """
    rule("1. THE TOOL SCHEMA, generated from the decorator, as the service gets it")
    print(json.dumps(get_ticket_status.to_json_schema_spec(), indent=2))
    print("\n  Every line of that JSON was GENERATED from the Python signature:")
    print("    - description  came from the docstring")
    print("    - enum         came from json_schema_extra on `detail`")
    print("    - required[]   holds ticket_id ONLY, because `detail` has a default")


def required_env(name: str, hint: str) -> str:
    """Return env var ``name`` or exit with a friendly pointer to .env.example."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: environment variable {name} is not set.\n"
                 f"  -> {hint}\n  See .env.example, then: cp .env.example .env")
    return value


async def run_demo(endpoint: str, model: str) -> None:
    """Ask one question and narrate every stage of the resulting turn."""
    print_schema()

    client = FoundryChatClient(
        project_endpoint=endpoint,
        model=model,
        credential=AzureCliCredential(),
    )
    # The framework drives the request/execute/continue loop for us. That is the
    # upgrade over hand-rolling two calls: no replaying reasoning items, no
    # call_id bookkeeping, and no chance of dropping an item the service requires.
    # Middleware is how we still SEE every stage of the loop it runs.
    agent = Agent(
        client=client,
        instructions=INSTRUCTIONS,
        tools=[get_ticket_status],
        middleware=[BoundaryMiddleware()],
    )

    print(f"\nquestion       : {QUESTION}")

    try:
        # Beats 2 and 3 print from inside BoundaryMiddleware while this runs.
        response = await agent.run(QUESTION, session=agent.create_session())
    except Exception as exc:  # noqa: BLE001 -- a live demo must fail readably
        print(f"\n[error] {type(exc).__name__}: {exc}")
        print("  Check that `az login` is current and that .env points at a live")
        print("  deployment. Re-running this script is always safe.")
        raise SystemExit(1) from exc
    finally:
        with contextlib.suppress(Exception):
            await client.client.close()

    rule("4. THE TURN, read back out of the response")
    finish_reason, status, incomplete = stop_signals(response)
    print(f"  shape          : {' -> '.join(turn_shape(response))}")

    calls = contents_of_type(response, "function_call")
    results = contents_of_type(response, "function_result")
    if calls:
        call = calls[0]
        # parse_arguments() is the framework's own accessor. `arguments` itself is
        # the raw JSON STRING the model emitted, which is worth showing once so
        # nobody assumes it arrives as a dict.
        print(f"  call.name      : {call.name}")
        print(f"  call.call_id   : {call.call_id}")
        print(f"  call.arguments : {call.arguments}   <- a JSON string, not a dict")
        print(f"  parsed         : {call.parse_arguments()}")
    else:
        print("  call           : none. No schema matched, so the model just answered.")
    if results:
        # call_id is the thread that stitches a result back to its request. When
        # several tools fire in one turn, this is what keeps them straight.
        print(f"  result.call_id : {results[0].call_id}   <- matches the call above")

    print(f"  finish_reason  : {finish_reason}   (the framework's normalized signal)")
    print(f"  status         : {status}   (the service's own signal)")
    print(f"  incomplete     : {incomplete}")
    print_usage(response)

    if status != "completed":
        # Never narrate "the model chose to stop" when it was actually truncated.
        print("\n  WARNING: this turn did NOT complete cleanly. Read incomplete_details.")

    rule("5. THE ANSWER, composed from what YOUR code returned")
    print(response.text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI-103 L10: the function-calling loop, printed step by step.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the tool schema and exit. Makes no Azure calls.")
    args = parser.parse_args()

    if args.dry_run:
        # Offline path: prove the schema without spending a token or needing
        # az login. Useful as a pre-flight check right before recording.
        print("DRY RUN -- schema only, no Azure calls.")
        print_schema()
        return

    endpoint = required_env(
        "FOUNDRY_PROJECT_ENDPOINT",
        "https://<account>.services.ai.azure.com/api/projects/<project>")
    model = required_env(
        "FOUNDRY_MODEL", "your chat model deployment name, e.g. gpt-5-mini")

    asyncio.run(run_demo(endpoint, model))


if __name__ == "__main__":
    main()
