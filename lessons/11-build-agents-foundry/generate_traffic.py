"""generate_traffic.py -- warm the Lesson 11 observability pipe.

WHY THIS EXISTS
    Every KQL query in the Lesson 11 demo uses a 24-hour window. A freshly built
    Foundry project has zero telemetry and an idle one goes cold in about a day.
    This fires a deliberate mix of requests so the three demo queries return rows:

      Query A (agent KPIs)           needs invoke_agent spans.
      Query C (error taxonomy)       needs an unhappy path, so we deliberately
                                     ask something the knowledge store cannot
                                     answer.

    Query B (multi-agent hand-off) is NOT served by this script. Use
    m11_multi_agent.py, which runs a real HandoffBuilder workflow and emits
    spans from three agents under one operation_Id.

    Read-only against your data. Idempotent -- run it as often as you like; it
    only appends telemetry.

SCOPE
    This script drives ONE portal-provisioned prompt agent, to add volume and a
    second agent shape to the telemetry. The multi-agent story lives in
    m11_multi_agent.py.

API NOTES (these cost real time to discover, so they're written down)
    * A prompt agent is referenced through `agent_reference`, NOT `model=`.
      Passing an agent name as model returns DeploymentNotFound.
    * The token audience is https://ai.azure.com, not cognitiveservices.azure.com.
    * The /openai/v1 path rejects an api-version query parameter, so use the plain
      OpenAI client with a bearer token. AzureOpenAI always appends one and fails.

USAGE
    python generate_traffic.py            # 3 rounds against the specialist agent
    python generate_traffic.py --rounds 5
"""
from __future__ import annotations

import argparse
import os
import sys
import time

# VS Code's integrated terminal injects proxy vars on some setups, which makes
# httpx fail with "getaddrinfo failed". These endpoints are public; strip them.
for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_pv, None)

from azure.identity import AzureCliCredential
from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is convenience only; real env vars still work.
    pass

# Config comes from .env, never hardcoded. The literal is only a fallback so this
# script keeps working in a folder where .env has not been created yet.
PROJECT_ENDPOINT = os.environ.get(
    "FOUNDRY_PROJECT_ENDPOINT",
    "https://aif-ai103-s9qdgp2o.services.ai.azure.com/api/projects/proj-agents",
)
SPECIALIST = os.environ.get("TRAFFIC_AGENT", "l10-support-agent")

# Questions the seeded m365_docs corpus CAN answer. These produce clean, grounded
# traces with citations.
GROUNDED = [
    "How do temperature and top_p differ?",
    "What is few-shot learning and when should I use it?",
    "Why does supporting content help ground a model?",
    "What does chain-of-thought prompting do?",
    "How does asking for citations reduce fabrication?",
]

# Deliberately unanswerable from the corpus. NOT a bug: Query C needs an unhappy
# path to classify, and "the knowledge store has nothing" is the most common real
# failure an agent hits in production.
UNGROUNDED = ["What is our company holiday schedule for next year?"]


def make_client() -> OpenAI:
    return OpenAI(
        base_url=f"{PROJECT_ENDPOINT}/openai/v1",
        api_key=AzureCliCredential().get_token("https://ai.azure.com/.default").token,
        timeout=180.0,
        max_retries=3,
    )


def ask(client: OpenAI, agent: str, question: str) -> str:
    resp = client.responses.create(
        input=question,
        extra_body={"agent_reference": {"name": agent, "type": "agent_reference"}},
    )
    text = getattr(resp, "output_text", "") or "(no text)"
    return text.strip().replace("\n", " ")[:90]


def main() -> int:
    ap = argparse.ArgumentParser(description="Warm the L11 telemetry pipe.")
    ap.add_argument("--rounds", type=int, default=3)
    args = ap.parse_args()

    client = make_client()
    ok = fail = 0

    print(f"[traffic] agent={SPECIALIST}  rounds={args.rounds}\n")

    for r in range(1, args.rounds + 1):
        print(f"--- round {r} ---")
        for q in GROUNDED[:3]:
            try:
                print(f"  [{SPECIALIST}] {q}")
                print(f"      -> {ask(client, SPECIALIST, q)}...")
                ok += 1
            except Exception as exc:                        # noqa: BLE001
                print(f"      !! {type(exc).__name__}: {str(exc)[:120]}")
                fail += 1

        # One deliberate miss per round so Query C has something to classify.
        for q in UNGROUNDED:
            try:
                print(f"  [{SPECIALIST}] (expected miss) {q}")
                print(f"      -> {ask(client, SPECIALIST, q)}...")
                ok += 1
            except Exception as exc:                        # noqa: BLE001
                print(f"      !! {type(exc).__name__}: {str(exc)[:120]}")
                fail += 1

        if r < args.rounds:
            time.sleep(2)

    print(f"\n[traffic] {ok} succeeded, {fail} failed.")
    print("[traffic] Allow 1-3 minutes for App Insights ingestion, then run the")
    print("          Lesson 11 queries against appi-ai103-agents > Logs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
