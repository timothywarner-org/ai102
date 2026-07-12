#!/usr/bin/env python
"""
M06 demo -- Build a generative application on Microsoft Foundry with the SDK.

AI-103 Lesson 6 is a BUILD lesson, so code is the right surface (per our demo-surface
rule -- the SDK is where the real, valuable work happens here, not the portal). We hit
the three objectives this lesson owns, in the order you'd actually write them:

  LO6  CONNECT to the project ..... one AIProjectClient, built from the PROJECT endpoint
                                    (not a model endpoint), keyless via az login. Validate
                                    connectivity at startup so it fails fast, not mid-request.
  LO1  DEPLOY and CONSUME a model .. the deploy is infrastructure-as-code (see the Bicep in
                                    ../../infra/ai103-core.mvp.bicep -- SKU, version pin,
                                    raiPolicyName). Here we CONSUME it: get an OpenAI client
                                    off the project and call the model, then a follow-up that
                                    remembers the first turn.
  LO5  INTEGRATE via connectors ... enumerate the project's connections -- Foundry makes
                                    external services (App Insights, Search, ...) first-class,
                                    defined once and reused, instead of scattered secrets.

Capstone (--agent): wrap the model in a small Foundry AGENT -- the actual "generative
application" you ship. That's the deep dive of Lessons 10-11; here it's a 60-second taste
so you see where the SDK is heading.

Auth is KEYLESS: AzureCliCredential (your `az login` identity), deterministic vs
DefaultAzureCredential. The OpenAI client the SDK hands back is bearer-token authenticated
against https://ai.azure.com/.default -- no API key anywhere. In CI you swap the one
credential line for a federated (OIDC) identity and it still ships secretless.

The demo is READ-MOSTLY and idempotent: it calls the model and lists connections (no
mutation), and the optional agent beat creates one agent version and deletes it on the way
out, so re-running converges to the same state.

Setup:  uv sync   ;   az login   ;   copy .env.example to .env  (fill in project endpoint)
Run:    uv run python m06_build_app_demo.py            # connect + consume + connections
        uv run python m06_build_app_demo.py --agent    # also build+run the agent capstone
        uv run python m06_build_app_demo.py --dry-run   # print the plan, call nothing

The `# %%` markers open this in the VS Code Interactive Window so you can run one beat at a
time while narrating.

Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
"""

# %%
# ---- imports -------------------------------------------------------------------------
import argparse
import os
import sys

from azure.identity import AzureCliCredential
from azure.ai.projects import AIProjectClient

# Model output routinely contains smart quotes, em-dashes, and non-breaking hyphens. On a
# Windows console (cp1252) those raise UnicodeEncodeError on print, which would blow up the
# demo on camera. Force UTF-8 so anything the model says prints cleanly.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)   # this lesson's .env wins over any ambient vars
except ImportError:
    pass


# %%
# ---- helpers -------------------------------------------------------------------------
def required(name: str, hint: str) -> str:
    """Return env var ``name`` or exit with a friendly, copy-pasteable hint. See .env.example."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: environment variable {name} is not set.\n  -> {hint}\n  See .env.example.")
    return value


def banner(text: str) -> None:
    """Labeled section header so each objective is obvious on screen while recording."""
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


# %%
# ---- LO6: connect to the project (the front door) ------------------------------------
def connect() -> AIProjectClient:
    """Build ONE AIProjectClient from the PROJECT endpoint, keyless, and prove it works.

    The endpoint is the whole lesson's punchline: it's the PROJECT URL
    (https://<account>.services.ai.azure.com/api/projects/<project>), the one address that
    reaches every deployment and connection in the project -- not a single model endpoint.
    We validate connectivity at startup by listing the project's model deployments; if auth
    or the URL is wrong, we find out here, not in the middle of a user's request.
    """
    endpoint = required(
        "FOUNDRY_PROJECT_ENDPOINT",
        "the PROJECT endpoint: https://<account>.services.ai.azure.com/api/projects/<project>",
    )
    banner("LO6 -- CONNECT to the Foundry project (keyless, project endpoint)")
    project = AIProjectClient(endpoint=endpoint, credential=AzureCliCredential())
    # Startup health check: enumerate deployed models through the project.
    names = [d.name for d in project.deployments.list()]
    print(f"  connected: {endpoint}")
    print(f"  deployments reachable from this one client: {names or '(none yet)'}")
    return project


# %%
# ---- LO1: consume a deployed model ---------------------------------------------------
def consume(project: AIProjectClient, deployment: str) -> None:
    """Call the model through the project's OpenAI client, then a follow-up with memory.

    get_openai_client() hands back a standard OpenAI client, already bearer-token
    authenticated -- so the code you write here is the same code you'd write anywhere, only
    keyless and pointed at your Foundry project. previous_response_id threads the second turn
    onto the first, which is conversation memory with zero extra plumbing.
    """
    banner("LO1 -- CONSUME the deployed model (Responses API)")
    with project.get_openai_client() as openai_client:
        first = openai_client.responses.create(
            model=deployment,
            input="In one sentence, what is Microsoft Foundry?",
        )
        print("  Q1: What is Microsoft Foundry?")
        print(f"  A1: {first.output_text.strip()}")

        second = openai_client.responses.create(
            model=deployment,
            input="Now name one thing it is NOT, in one sentence.",
            previous_response_id=first.id,   # <- carries the first turn's context
        )
        print("  Q2 (follow-up): name one thing it is NOT")
        print(f"  A2: {second.output_text.strip()}")
    print("\n  Same OpenAI code you already know -- keyless, pointed at your project.")


# %%
# ---- LO5: integrate via connectors ---------------------------------------------------
def show_connections(project: AIProjectClient) -> None:
    """List the project's connections -- external services made first-class by Foundry."""
    banner("LO5 -- INTEGRATE: the project's connections (connectors)")
    found = False
    for conn in project.connections.list():
        found = True
        ctype = getattr(conn, "type", None) or getattr(conn, "connection_type", "?")
        print(f"  - {getattr(conn, 'name', '?'):<28} type={ctype}")
    if not found:
        print("  (no connections yet -- add one in the portal or via Bicep; see infra/modules/*.bicep)")
    print("\n  Define a connection once, reuse it everywhere -- no secrets scattered in code.")


# %%
# ---- Capstone (--agent): wrap the model in a Foundry agent ---------------------------
def run_agent(project: AIProjectClient, deployment: str) -> None:
    """Build a tiny Foundry agent, ask it something, then delete it. Preview API -- graceful.

    This is the L10/L11 deep dive in miniature: an agent is a model plus instructions (and,
    later, tools and memory) that you publish and call. We create one version, run one turn
    through a conversation, and clean up, so nothing is left behind.
    """
    banner("CAPSTONE -- build + run a Foundry AGENT, then clean up (preview)")
    agent = None
    try:
        from azure.ai.projects.models import PromptAgentDefinition
        agent = project.agents.create_version(
            agent_name="m06-hello-agent",
            definition=PromptAgentDefinition(
                model=deployment,
                instructions="You are a concise Azure AI tutor. Answer in one short sentence.",
            ),
        )
        print(f"  created agent '{agent.name}' version {agent.version}")
        with project.get_openai_client() as openai_client:
            conv = openai_client.conversations.create(
                items=[{"type": "message", "role": "user",
                        "content": "Give me a one-sentence definition of retrieval-augmented generation."}],
            )
            # The response references the agent by name. NOTE: the key is `agent_reference`
            # (the older `agent` key is deprecated) -- a real churn point in this preview API.
            resp = openai_client.responses.create(
                conversation=conv.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                input="",
            )
            print(f"  agent says: {resp.output_text.strip()}")
            openai_client.conversations.delete(conversation_id=conv.id)
    except Exception as exc:  # preview surface -- narrate, don't crash the recording
        print(f"  SKIP: agent capstone unavailable here ({type(exc).__name__}: {exc}).")
        print("  The connect/consume/connections beats above are the stable core of the demo.")
    finally:
        # Always clean up the agent version we created, even if the call above failed,
        # so re-running the demo never leaves orphaned agents behind.
        if agent is not None:
            try:
                project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
                print("  cleaned up: agent version deleted (idempotent).")
            except Exception:
                pass


# %%
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-103 L6: build a generative app on the Foundry SDK.")
    parser.add_argument("--agent", action="store_true", help="Also build+run the agent capstone (preview).")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan; make no Azure calls.")
    return parser.parse_args()


# %%
def main() -> None:
    args = parse_args()
    deployment = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-5-mini")

    if args.dry_run:
        banner("DRY RUN -- plan (no calls made)")
        print(f"  Project endpoint : {os.environ.get('FOUNDRY_PROJECT_ENDPOINT', '<unset>')}")
        print(f"  Model deployment : {deployment}")
        print( "  Auth             : keyless (AzureCliCredential)")
        print( "  Beats            : LO6 connect -> LO1 consume -> LO5 connections" +
               (" -> agent capstone" if args.agent else ""))
        return

    project = connect()
    consume(project, deployment)
    show_connections(project)
    if args.agent:
        run_agent(project, deployment)

    banner("DONE -- connected, consumed, integrated. Next (L10/11): agents in depth.")


if __name__ == "__main__":
    main()
