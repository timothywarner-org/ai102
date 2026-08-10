"""ask.py -- send one question to a Foundry prompt agent and print the result.

Usage:  python ask.py <agent-name> "your question"

Two things that trip people up and are worth knowing for the exam:
  * A prompt agent is NOT referenced as `model=`. That name is for model
    deployments; passing an agent name there returns DeploymentNotFound. Agents
    are referenced through `agent_reference` in the request body.
  * The project endpoint's /openai/v1 path rejects an api-version query
    parameter, so use the plain OpenAI client with a bearer token rather than
    AzureOpenAI, which always appends one.
"""
import os
import sys

# VS Code's integrated terminal injects proxy vars on some setups; strip them so
# httpx doesn't fail with "getaddrinfo failed" against public Azure endpoints.
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

# Config comes from .env, never hardcoded. An earlier cut of this script carried a
# real endpoint as a fallback, and when that account was deleted the "fallback"
# quietly pointed every reader at a resource that no longer exists. Failing loudly
# with a pointer to .env.example is far kinder than a confusing auth error.
PROJECT_ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
if not PROJECT_ENDPOINT:
    sys.exit(
        "ERROR: FOUNDRY_PROJECT_ENDPOINT is not set.\n"
        "  -> https://<account>.services.ai.azure.com/api/projects/<project>\n"
        "  See .env.example, then: cp .env.example .env"
    )

# Guard the arguments before doing anything expensive. Without this, running
# `python ask.py` with no arguments raises a bare IndexError, which is an ugly
# thing to have happen on camera.
if len(sys.argv) < 3:
    sys.exit(f'Usage: python ask.py <agent-name> "your question"\n'
             f'   e.g. python ask.py l10-support-agent "What is few-shot prompting?"')

client = OpenAI(
    base_url=f"{PROJECT_ENDPOINT}/openai/v1",
    api_key=AzureCliCredential().get_token("https://ai.azure.com/.default").token,
    timeout=180.0,
    max_retries=3,
)

agent = sys.argv[1]
question = " ".join(sys.argv[2:])

response = client.responses.create(
    input=question,
    extra_body={"agent_reference": {"name": agent, "type": "agent_reference"}},
)

print(f"AGENT   : {agent}")
print(f"QUESTION: {question}")
print(f"ANSWER  : {(getattr(response, 'output_text', '') or '(none)').strip()[:800]}")
print("SPANS   :", [getattr(i, "type", None) for i in (response.output or [])])
