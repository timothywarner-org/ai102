#!/usr/bin/env python
"""
M01 demo -- one grounded Foundry agent that makes ALL FOUR Lesson 1 decisions.

AI-103 Lesson 1 is about four choices. Rather than four toy scripts, this builds the
ONE artifact those choices produce -- a small support agent -- the way AI-103 actually
ships: with the Microsoft Agent Framework on Microsoft Foundry. (This is the current,
GA path. The classic create_agent / thread / run agent API is deprecated and retires
in 2027, so we deliberately do not use it.)

Each decision is one ingredient, and they map straight onto the lesson's own slides
("an agent is memory + tools + knowledge, with guardrails"):

  LO1  choose a MODEL ............ the agent reasons with FOUNDRY_MODEL, a capable LLM.
                                   (A small model like Phi-4 would be the call for an
                                   edge or low-latency job; here we want real reasoning.)
  LO2  choose a SERVICE .......... the Agents service via FoundryChatClient -- because
                                   the work needs tools and state, not stateless chat.
  LO3  choose RETRIEVAL .......... ground the agent on a knowledge file with the
                                   file-search tool (a managed vector store).
  LO4  MEMORY + TOOLS + KNOWLEDGE  a conversation session (memory), a custom @tool
                                   (tool), the file-search knowledge source, and an
                                   approval gate on the tool (the guardrail).

Setup:  uv sync  ;  az login  ;  copy .env.example to .env
Run:    uv run python m01_agent_demo.py

Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
"""

import asyncio
import contextlib
import logging
import os
import sys
import warnings
from typing import Annotated

# Agent Framework currently emits experimental API warnings at import time for
# skill and harness internals used by the GA Foundry path. Filter those known
# framework notices before import so the recorded demo output stays focused while
# Python still reports unrelated warnings.
warnings.filterwarnings(
    "ignore",
    message=r"\[SKILLS\].*experimental",
    category=Warning,
    module=r"agent_framework\._skills",
)
warnings.filterwarnings(
    "ignore",
    message=r"\[HARNESS\].*experimental",
    category=Warning,
    module=r"agent_framework\._harness\..*",
)

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential
from pydantic import Field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# The Foundry file-search tool is an Azure SDK object (ProjectsFileSearchTool). The Agent
# Framework's OpenTelemetry serializer only recognizes FunctionTool / pydantic model /
# dict, so on every run it logs a benign "Can't parse tool." WARNING while building span
# attributes. The tool is still sent to the service correctly and grounding works; only
# the telemetry line is noise. Drop that one message so the demo console stays clean,
# without muting genuine agent_framework warnings.
logging.getLogger("agent_framework").addFilter(
    lambda record: record.getMessage() != "Can't parse tool."
)

# A tiny knowledge base the agent will ground on. In production this is your real
# corpus (policies, manuals, tickets); one line keeps the demo self-contained.
KB_FILENAME = "contoso_policy.txt"
KB_CONTENT = (
    b"Contoso support policy: customers on the Premium plan are entitled to a full "
    b"refund within 30 days of purchase. Standard plan refunds are issued as store credit only."
)
# Stable name for the managed vector store, so a re-run can find and sweep prior copies.
VSTORE_NAME = "m01-kb"


async def sweep_kb_resources(client) -> tuple[int, int]:
    """Delete every ``m01-kb`` vector store and KB file; idempotent when none exist.

    Called twice: before create (so a prior crashed run can't leave duplicate stores
    or files behind) and at the end (so the demo leaves nothing behind). Collect each
    list fully before deleting -- deleting mid-iteration invalidates the paging cursor.
    """
    stale_vstores = [vs async for vs in client.client.vector_stores.list() if vs.name == VSTORE_NAME]
    for vs in stale_vstores:
        with contextlib.suppress(Exception):
            await client.client.vector_stores.delete(vector_store_id=vs.id)
    stale_files = [f async for f in client.client.files.list() if f.filename == KB_FILENAME]
    for f in stale_files:
        with contextlib.suppress(Exception):
            await client.client.files.delete(file_id=f.id)
    return len(stale_vstores), len(stale_files)


# ---- LO4: a custom TOOL, with an approval gate (the guardrail from the slides) ----
# approval_mode="never_require" keeps the demo flowing; use "always_require" in
# production so a human approves any sensitive action before it runs.
@tool(approval_mode="never_require")
def open_refund_ticket(
    customer: Annotated[str, Field(description="Customer's full name.")],
    plan: Annotated[str, Field(description="The customer's plan, e.g. 'Premium' or 'Standard'.")],
    amount_usd: Annotated[float, Field(description="Requested refund amount in US dollars.")],
    reason: Annotated[str, Field(description="One-line reason the refund qualifies under policy.")],
) -> str:
    """Open a refund ticket and return its id. Every argument was extracted by the model."""
    # A real tool would call your ticketing API here. Set a breakpoint on the return below:
    # customer + amount_usd come from the user's plain-English message, while plan + reason
    # come from the model grounding on the policy file -- the whole LO3 + LO4 story in one frame.
    ticket_id = f"RF-{abs(hash(customer)) % 10000:04d}"
    return (f"Ticket {ticket_id} opened for {customer} ({plan} plan): "
            f"${amount_usd:.2f} refund queued -- {reason}.")


def required_env(name: str, hint: str) -> str:
    """Return the value of env var ``name``, or exit with a friendly hint if it is unset."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: environment variable {name} is not set.\n  -> {hint}\n  See .env.example.")
    return value


async def main() -> None:
    """Build the one grounded agent and run the two teaching turns that exercise LO1-LO4."""
    # LO1 -- the MODEL. The agent reasons with the deployment named in FOUNDRY_MODEL.
    model = required_env("FOUNDRY_MODEL", "your chat model deployment name, e.g. gpt-5.1")
    # FoundryChatClient reads FOUNDRY_PROJECT_ENDPOINT from the environment; validate it early.
    required_env("FOUNDRY_PROJECT_ENDPOINT", "https://<resource>.services.ai.azure.com/api/projects/<project>")
    print(f"LO1  model       : {model}  (capable LLM for agent reasoning)")

    # LO2 -- the SERVICE. FoundryChatClient is the Foundry Agents service via the Microsoft
    # Agent Framework, with keyless Entra ID auth (az login). Stateless chat completions
    # could not do the grounding + tool-calling below; that is exactly why we pick agents.
    client = FoundryChatClient(credential=AzureCliCredential())
    print("LO2  service     : Microsoft Foundry Agents (Agent Framework), keyless auth")

    # LO3 -- RETRIEVAL. Upload a knowledge file, index it into a managed vector store,
    # and expose it as a file-search tool the agent grounds its answers on.
    # Idempotent: sweep any leftovers from a prior crashed run first, so re-running
    # never piles up duplicate stores or files.
    swept_vs, swept_f = await sweep_kb_resources(client)
    file = await client.client.files.create(file=(KB_FILENAME, KB_CONTENT), purpose="assistants")
    vstore = await client.client.vector_stores.create(
        name=VSTORE_NAME, expires_after={"anchor": "last_active_at", "days": 1}
    )
    await client.client.vector_stores.files.create_and_poll(vector_store_id=vstore.id, file_id=file.id)
    file_search = client.get_file_search_tool(vector_store_ids=[vstore.id])
    print(f"LO3  retrieval   : file-search grounding over a managed vector store "
          f"(swept {swept_vs} stale store(s), {swept_f} stale file(s))")

    # LO4 -- assemble the agent from MEMORY + TOOLS + KNOWLEDGE (+ the guardrail).
    agent = Agent(
        client=client,
        instructions=(
            "You are Contoso's support agent. Ground every policy answer in the refund "
            "policy via file search, and open a refund ticket with your tool when a refund applies."
        ),
        tools=[file_search, open_refund_ticket],
    )
    session = agent.create_session()  # memory: the session carries conversation state
    print("LO4  integration : session (memory) + custom tool + knowledge source + approval gate")
    print("=" * 72)

    # Turn 1 forces RETRIEVAL (read the policy) and the TOOL (open the ticket).
    q1 = ("I'm Dana Lee, a Premium customer. I bought 22 days ago for $80 and want a "
          "refund. Do I qualify, and if so please process it.")
    print(f"\nUser: {q1}")
    print(f"Agent: {await agent.run(q1, session=session)}")

    # Turn 2 forces MEMORY: the name and amount are not repeated, so the agent must
    # recall them from the session.
    q2 = "Remind me which plan I'm on and what refund you just queued for me."
    print(f"\nUser: {q2}")
    print(f"Agent: {await agent.run(q2, session=session)}")

    print("\n" + "=" * 72)
    print("One agent, four decisions: model (LO1), Agents service (LO2), grounded")
    print("retrieval (LO3), and memory + tool + knowledge integration (LO4).")

    # Tidy up so the demo leaves nothing behind. Sweep by name (not just this run's
    # ids) so a leftover from any earlier run is cleared too, then close the client.
    cleaned_vs, cleaned_f = await sweep_kb_resources(client)
    print(f"Cleanup          : deleted {cleaned_vs} vector store(s), {cleaned_f} file(s)")
    with contextlib.suppress(Exception):
        await client.client.close()


if __name__ == "__main__":
    asyncio.run(main())
