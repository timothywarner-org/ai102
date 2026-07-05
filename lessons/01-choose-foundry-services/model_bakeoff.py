#!/usr/bin/env python
"""
M01 demo -- Model Bake-Off: pick the right model for the job.

AI-103 Lesson 1 ("Choose Foundry services, models, and integration approach")
teaches one durable habit: TASK FIT beats brand name. This script proves it live.
It sends the SAME prompt to two models you have deployed in Microsoft Foundry -- a
flagship large language model (LLM) and a small language model (SLM) -- and prints a
side-by-side scoreboard of latency, token usage, and the answers themselves.

What you should see:
  * the SLM (for example, Phi-4) comes back faster and cheaper,
  * the flagship (for example, GPT-5.1) reasons a little deeper.
The "right" model is the one whose strengths match the workload in front of you,
not the biggest name on the leaderboard.

Auth is KEYLESS (Microsoft Entra ID via the Azure CLI sign-in), which is the
AI-103 security posture -- no API keys live in this file. Run `az login` first.
We use AzureCliCredential (not DefaultAzureCredential) on purpose: it binds to
your `az login` identity directly, so a stray environment or managed-identity
credential on the box cannot silently shadow you and 401 the request.

Setup (see README.md and .env.example):
  uv sync
  az login
Run:
  uv run python model_bakeoff.py
  uv run python model_bakeoff.py --prompt "Summarize the CAP theorem in one sentence."

Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
"""

import argparse
import os
import sys
import time

# Microsoft Foundry SDK: keyless auth plus a ready-made OpenAI client.
# Install with: uv sync
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential

# Optional convenience: load a local .env file so the script "just works" after you
# copy .env.example to .env. Falls back silently if python-dotenv is not installed.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# A small, neutral prompt both model classes can answer, so the comparison is about
# HOW each model answers, not whether it can.
DEFAULT_PROMPT = "In two sentences, explain retrieval-augmented generation to a brand-new developer."


def required_env(name: str, hint: str) -> str:
    """Read an environment variable or exit with a friendly, copy-pasteable hint.

    We fail fast with a clear message because a missing endpoint or deployment name
    is the number-one reason a first run does not work. See .env.example.
    """
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: environment variable {name} is not set.\n  -> {hint}\n  See .env.example in this folder.")
    return value


def run_once(openai_client, deployment: str, prompt: str):
    """Send `prompt` to one deployment; return (answer, seconds, in_tokens, out_tokens).

    Note: `model=` takes the DEPLOYMENT NAME from your Foundry project, not the base
    model id. Routing by deployment name is what lets you swap the underlying model
    later without changing a line of application code.
    """
    started = time.perf_counter()
    response = openai_client.chat.completions.create(
        model=deployment,
        messages=[{"role": "user", "content": prompt}],
        # GPT-5.x are reasoning models: they spend completion tokens on hidden
        # reasoning BEFORE the visible answer. Too small a budget (e.g. 300) can be
        # fully consumed by reasoning, returning an empty answer. 1500 leaves room.
        max_completion_tokens=1500,
    )
    elapsed = time.perf_counter() - started
    answer = response.choices[0].message.content.strip()
    usage = response.usage
    return answer, elapsed, usage.prompt_tokens, usage.completion_tokens


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two Microsoft Foundry model deployments on the same prompt.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="The prompt to send to both models.")
    args = parser.parse_args()

    endpoint = required_env(
        "FOUNDRY_PROJECT_ENDPOINT",
        "Foundry portal -> your project -> Overview -> Endpoint (https://<resource>.services.ai.azure.com/api/projects/<project>)",
    )
    flagship = required_env("FLAGSHIP_DEPLOYMENT", "deployment name of your flagship LLM, e.g. gpt-5.1")
    slm = required_env("SLM_DEPLOYMENT", "deployment name of your small model, e.g. gpt-5-nano")

    print(f"\nPrompt: {args.prompt}")
    print("=" * 72)

    results = []
    # One authenticated, reusable client for the whole project (keyless, Entra ID).
    with (
        AzureCliCredential() as credential,
        AIProjectClient(endpoint=endpoint, credential=credential) as project,
        project.get_openai_client() as client,
    ):
        for label, deployment in (("FLAGSHIP LLM", flagship), ("SMALL MODEL (SLM)", slm)):
            try:
                answer, secs, in_tok, out_tok = run_once(client, deployment, args.prompt)
            except Exception as exc:  # keep the demo resilient on camera
                print(f"\n[{label}] deployment '{deployment}' -> ERROR: {exc}")
                continue
            results.append((label, deployment, secs))
            print(f"\n[{label}]  deployment = {deployment}")
            print(f"  latency : {secs:5.2f}s    tokens: {in_tok} in / {out_tok} out")
            print(f"  answer  : {answer}")

    # The teaching beat: name the winner and the lesson.
    print("\n" + "=" * 72)
    if len(results) == 2:
        fastest = min(results, key=lambda r: r[2])
        print(f"Fastest response: {fastest[0]} ({fastest[1]}) at {fastest[2]:.2f}s.")
    print("Takeaway: match the model to the workload. The SLM usually wins on speed and")
    print("cost; the flagship wins on hard, open-ended reasoning. Task fit beats brand name.")


if __name__ == "__main__":
    main()
