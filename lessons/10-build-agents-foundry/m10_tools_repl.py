#!/usr/bin/env python
"""
M10 demo -- a console agent that makes TOOL SCHEMAS and STOP CODES visible.

AI-103 Lesson 10 opens with two frozen objectives, and this one script is built to
put both of them on screen at the same time:

  LO1  "Define agent roles, goals, conversation-tracking approach, and TOOL SCHEMAS"
  LO2  "Build agents that integrate retrieval, FUNCTION-CALLING, and CONVERSATION MEMORY"

The single idea to land on camera: the model NEVER runs your code. It reads your
tool SCHEMA, decides which tool fits, and emits a request to call it. Your process
executes the function, hands the result back, and the model continues. Every turn
in this REPL prints that boundary as it happens.

Three tools, chosen so that tool SELECTION is observable. One tool would prove
nothing -- with a single tool there is nothing to select between:

  add             two required numbers, no enum        -- the baseline
  convert_money   an ENUM on the currency codes        -- schema as a guardrail
  get_ticket_status  an OPTIONAL param with a default  -- required[] vs optional

Ask about arithmetic and `add` fires. Ask about currency and `convert_money` fires.
Ask who wrote Dune and NOTHING fires, because no schema matches. That last case is
the one learners underestimate, so it is worth demoing deliberately.

Setup:  uv sync  ;  az login  ;  cp .env.example .env
Run:    uv run python m10_tools_repl.py
        uv run python m10_tools_repl.py --dry-run   # schemas only, no Azure calls

Idempotent: this demo creates NO Azure resources. There is nothing to clean up,
so it is safe to re-run live as many times as a take requires.

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


# =============================================================================
# THE TOOLS
#
# Read these as PROMPTS, not as plumbing. The docstring becomes the tool
# description and each Field(description=...) becomes a parameter description.
# Those strings are the highest-leverage text in the whole file: the model
# re-reads them on every single turn to decide what to call. Vague descriptions
# are the number one cause of wrong tool selection.
# =============================================================================


@tool(approval_mode="never_require")
def add(
    a: Annotated[float, Field(description="The first number to add.")],
    b: Annotated[float, Field(description="The second number to add.")],
) -> float:
    """Add two numbers and return their exact sum.

    Use this for ANY addition the user asks for, even simple-looking arithmetic.
    Do not compute sums yourself; always call this tool so the answer is exact.
    """
    # A real tool would call your API here. Set a breakpoint on this line to show
    # that execution genuinely lands in YOUR process, not inside the model.
    return a + b


# Fixed rates keep the demo hermetic: no network call, no API key, no flakiness
# on camera. The teaching point is the enum in the schema, not live FX data.
_RATES = {("USD", "EUR"): 0.92, ("EUR", "USD"): 1.09,
          ("USD", "GBP"): 0.79, ("GBP", "USD"): 1.27,
          ("EUR", "GBP"): 0.86, ("GBP", "EUR"): 1.16}


@tool(approval_mode="never_require")
def convert_money(
    amount: Annotated[float, Field(description="How much money to convert.")],
    from_currency: Annotated[str, Field(
        description="Currency to convert FROM.",
        json_schema_extra={"enum": ["USD", "EUR", "GBP"]})],
    to_currency: Annotated[str, Field(
        description="Currency to convert TO.",
        json_schema_extra={"enum": ["USD", "EUR", "GBP"]})],
) -> str:
    """Convert an amount of money from one currency to another.

    Use this whenever the user asks about exchanging or converting currency.
    Only USD, EUR, and GBP are supported.
    """
    # The enum in the schema means the model cannot invent an unsupported currency,
    # so a whole class of runtime error is prevented at the SCHEMA layer rather
    # than being caught down here. This branch should be nearly unreachable.
    rate = _RATES.get((from_currency.upper(), to_currency.upper()))
    if from_currency.upper() == to_currency.upper():
        return f"{amount:.2f} {from_currency.upper()} (same currency, no conversion)"
    if rate is None:
        return f"error: no rate available for {from_currency} -> {to_currency}"
    return f"{amount:.2f} {from_currency.upper()} = {amount * rate:.2f} {to_currency.upper()}"


# Stands in for a real ticketing system. Shared with function_calling.py in this
# same lesson folder so the two demos tell one continuous story.
_TICKETS = {
    "CS-1042": {
        "ticket_id": "CS-1042",
        "status": "awaiting_customer",
        "priority": "P2",
        "owner": "Tim Warner",
        "last_update": "Customer asked for a callback window.",
    }
}


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
    # `detail` has a default, so it is absent from the schema's required[] list
    # while `ticket_id` is present. That is why the model will ask a follow-up
    # question when the user omits a ticket id, but never asks about detail.
    record = _TICKETS.get(ticket_id.upper())
    if not record:
        # Return a STRUCTURED error rather than raising. The model can reason
        # about this and tell the user honestly instead of inventing a status.
        return {"error": "not_found", "ticket_id": ticket_id}
    if detail == "summary":
        return {k: record[k] for k in ("ticket_id", "status", "priority")}
    return record


TOOLS = [add, convert_money, get_ticket_status]

SYSTEM_INSTRUCTIONS = (
    "You are Contoso's support desk assistant. "
    "Use your tools for arithmetic, currency conversion, and ticket lookups, and "
    "never compute those answers yourself. "
    "If no tool fits the question, just answer directly from your own knowledge. "
    "Keep answers to a sentence or two."
)


# =============================================================================
# TRACE HELPERS -- reading the turn back out of the response
# =============================================================================


def tool_schema(fn) -> dict[str, Any]:
    """Return the JSON Schema the service actually receives for one tool.

    to_json_schema_spec() reads the live FunctionTool, so this is the REAL spec
    that goes on the wire, not a hand-assembled lookalike. The framework built it
    from the Python signature: type hints became types, Field(description=...)
    became descriptions, and any parameter without a default landed in required[].
    Printing it is the whole point of LO1, and reading it from the tool itself is
    what guarantees the code and the schema can never drift apart.
    """
    return fn.to_json_schema_spec()


def schema_parameters(fn) -> dict[str, Any]:
    """Return just the parameters block out of a tool's full JSON Schema spec."""
    return tool_schema(fn).get("function", {}).get("parameters", {})


def render_arguments(arguments: Any) -> str:
    """Render tool arguments as `name=value` pairs, whatever form they arrive in.

    Middleware receives a mapping or a pydantic model; the function_call content
    on the response carries a raw JSON STRING. Normalize all three.
    """
    if hasattr(arguments, "model_dump"):
        arguments = arguments.model_dump()
    if isinstance(arguments, str):
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            arguments = json.loads(arguments)
    if isinstance(arguments, dict):
        return ", ".join(f"{k}={v!r}" for k, v in arguments.items())
    return str(arguments)


def render_result(result: Any) -> str:
    """Render what a tool returned, unwrapping the framework's Content wrapper.

    GOTCHA: by the time middleware sees `context.result`, the framework has
    already wrapped the return value in a list of Content objects with the
    serialized payload on `.text`. It is NOT the raw dict the function returned.
    Reach through the wrapper or the console shows `[<Content object at 0x...>]`.
    """
    if isinstance(result, list):
        return " ".join(str(getattr(item, "text", None) or item) for item in result)
    return str(result)


class BoundaryMiddleware(FunctionMiddleware):
    """Print the request/execute boundary LIVE, while the turn is still running.

    This is the seam the whole lesson is about. Everything before `call_next()`
    happens when the model has REQUESTED a call but nothing has executed yet.
    Everything after it happens once OUR function has returned. Printing on both
    sides of that one await shows request/execute/continue as it happens, rather
    than reconstructing it after the fact.
    """

    async def process(self, context: FunctionInvocationContext,
                      call_next: Callable[[], Awaitable[None]]) -> None:
        print(f"  [call]  model requested {context.function.name}"
              f"({render_arguments(context.arguments)})")
        await call_next()
        print(f"  [exec]  our code returned {render_result(context.result)}")


def turn_shape(response) -> list[str]:
    """Return the honest content-type sequence for one turn.

    A tool turn always contains this spine, in this order:
        function_call -> function_result

    Around it, gpt-5-mini is a REASONING model, so text_reasoning items appear
    wherever it stopped to think. The COUNT VARIES per turn: usually one before
    the call, and sometimes a second before the final answer. Do not promise a
    fixed five-item shape on camera, because the next take will contradict you.
    Ask a question no schema matches and the shape collapses to text -> nothing
    else, with no call at all.
    """
    return [
        content.type
        for message in response.messages
        for content in (getattr(message, "contents", []) or [])
        if getattr(content, "type", None)
    ]


def stop_code(response) -> tuple[Any, str, Any]:
    """Return (finish_reason, status, incomplete_details) for a finished turn.

    TWO stop signals, and the difference is exam-worthy:

      finish_reason -- the framework's normalized signal. 'stop' on a clean turn.
      status        -- the service's own signal, on the raw OpenAI Response two
                       wrappers down, so we reach through both. 'completed' means
                       the model chose to stop. 'incomplete', with
                       incomplete_details explaining why, means it was CUT OFF,
                       usually by a token cap. That is the failure mode people
                       misread as "the model just gave a short answer".
    """
    inner = getattr(getattr(response, "raw_representation", None), "raw_representation", None)
    return (
        getattr(response, "finish_reason", None),
        getattr(inner, "status", None) or "unknown",
        getattr(inner, "incomplete_details", None),
    )


def print_turn(response, verbose: bool) -> None:
    """Print the compact per-turn trace, then the agent's answer.

    The [call] and [exec] lines already printed from middleware while the turn was
    running, so this fills in what can only be known once the turn is complete.
    """
    shape = turn_shape(response)
    finish_reason, status, incomplete = stop_code(response)
    usage = response.usage_details or {}

    if "function_call" not in shape:
        print("  [call]  none selected -- no schema matched this question")

    print(f"  [turn]  {' -> '.join(shape) if shape else '(no content)'}")
    print(f"  [stop]  finish_reason={finish_reason}  status={status}  incomplete={incomplete}")
    # reasoning tokens are billed as OUTPUT and count against your output cap even
    # though they never appear in the answer. Worth surfacing on a reasoning model.
    print(f"  [usage] in={usage.get('input_token_count')} "
          f"out={usage.get('output_token_count')} "
          f"total={usage.get('total_token_count')} "
          f"reasoning={usage.get('reasoning_output_token_count')}")

    if status != "completed":
        # Never let the demo narrate a clean stop when the turn was truncated.
        print("  [warn]  turn did NOT complete cleanly -- read incomplete_details")

    if verbose:
        print("  [raw]   " + "-" * 58)
        print(json.dumps(response.to_dict(), indent=2, default=str)[:4000])
        print("  [raw]   " + "-" * 58)

    print(f"agent> {response.text}\n")


# =============================================================================
# REPL
# =============================================================================

BANNER_HELP = """Commands (all start with a colon, so they never reach the model):
  :tools            list the tools this agent can choose from
  :schema [name]    print the JSON Schema the model actually receives
  :verbose          toggle the full raw response dump
  :reset            start a new session, discarding conversation memory
  :help             show this help
  :quit             exit

Try these in order:
  what is 17.5 plus 4.25          -> add fires
  convert 50 USD to EUR           -> convert_money fires
  what is the status of CS-1042   -> get_ticket_status fires
  who wrote the novel Dune        -> NO tool fires, model answers directly
  now add 100 to that             -> memory: it knows what "that" is
"""


def clear_screen() -> None:
    """Clear the console so a live demo starts from a clean frame."""
    os.system("cls" if os.name == "nt" else "clear")  # noqa: S605


def print_banner(endpoint: str, model: str) -> None:
    print("=" * 72)
    print("  AI-103 Lesson 10 -- tool schemas, function calling, stop codes")
    print("=" * 72)
    print(f"  endpoint : {endpoint}")
    print(f"  model    : {model}   (reasoning model: expect a reasoning item)")
    print(f"  tools    : {', '.join(t.name for t in TOOLS)}")
    print(f"  auth     : AzureCliCredential (az login), keyless")
    print("=" * 72)
    print("Type :help for commands, :quit to exit.\n")


def print_tools() -> None:
    """List each tool with the metadata that drives selection."""
    for fn in TOOLS:
        params = schema_parameters(fn)
        required = params.get("required", [])
        print(f"\n  {fn.name}")
        # The description is what the model reads first when choosing a tool.
        print(f"    description : {fn.description.strip().splitlines()[0]}")
        for pname, pspec in params.get("properties", {}).items():
            flag = "required" if pname in required else "optional"
            enum = pspec.get("enum")
            enum_note = f", enum={enum}" if enum else ""
            print(f"    - {pname} ({pspec.get('type', '?')}, {flag}{enum_note})")
    print()


def required_env(name: str, hint: str) -> str:
    """Return env var ``name`` or exit with a friendly pointer to .env.example."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: environment variable {name} is not set.\n"
                 f"  -> {hint}\n  See .env.example, then: cp .env.example .env")
    return value


async def repl(endpoint: str, model: str) -> None:
    """Run the interactive loop against one agent and one session."""
    # One client, one agent, one session for the whole REPL. The session is what
    # carries conversation memory, so "now add 100 to that" resolves correctly.
    client = FoundryChatClient(
        project_endpoint=endpoint,
        model=model,
        credential=AzureCliCredential(),
    )
    # BoundaryMiddleware prints the [call] / [exec] pair live, from inside the
    # tool invocation, so the request/execute seam is visible as it happens.
    agent = Agent(client=client, instructions=SYSTEM_INSTRUCTIONS, tools=TOOLS,
                  middleware=[BoundaryMiddleware()])
    session = agent.create_session()

    clear_screen()
    print_banner(endpoint, model)

    verbose = False
    try:
        while True:
            try:
                line = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                # Ctrl+C / Ctrl+D during a take should exit cleanly, not dump a
                # traceback across the screen.
                print("\nBye.")
                return

            if not line:
                continue

            if line.startswith(":"):
                command, _, argument = line[1:].partition(" ")
                command, argument = command.lower(), argument.strip()

                if command in ("quit", "exit", "q"):
                    print("Bye.")
                    return
                if command == "help":
                    print(BANNER_HELP)
                elif command == "tools":
                    print_tools()
                elif command == "schema":
                    targets = [t for t in TOOLS if t.name == argument] if argument else TOOLS
                    if not targets:
                        print(f"  no tool named '{argument}'. Try :tools.\n")
                    for fn in targets:
                        print(json.dumps(tool_schema(fn), indent=2))
                    print()
                elif command == "verbose":
                    verbose = not verbose
                    print(f"  verbose = {verbose}\n")
                elif command == "reset":
                    session = agent.create_session()
                    print("  new session: conversation memory cleared\n")
                else:
                    print(f"  unknown command ':{command}'. Try :help.\n")
                continue

            try:
                response = await agent.run(line, session=session)
            except Exception as exc:  # noqa: BLE001 -- a live demo must not crash out
                print(f"  [error] {type(exc).__name__}: {exc}\n")
                continue

            print_turn(response, verbose)
    finally:
        with contextlib.suppress(Exception):
            await client.client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI-103 L10: an agent REPL that shows tool schemas and stop codes.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the tool schemas and exit. Makes no Azure calls.")
    args = parser.parse_args()

    if args.dry_run:
        # Offline path: prove the schemas without spending a token or needing
        # az login. Useful for a pre-flight check right before recording.
        print("DRY RUN -- tool schemas only, no Azure calls.\n")
        for fn in TOOLS:
            print(json.dumps(tool_schema(fn), indent=2))
        print_tools()
        return

    endpoint = required_env(
        "FOUNDRY_PROJECT_ENDPOINT",
        "https://<account>.services.ai.azure.com/api/projects/<project>")
    model = required_env("FOUNDRY_MODEL", "your chat model deployment name, e.g. gpt-5-mini")

    asyncio.run(repl(endpoint, model))


if __name__ == "__main__":
    main()
