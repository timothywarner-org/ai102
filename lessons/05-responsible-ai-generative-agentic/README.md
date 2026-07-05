# Implement responsible AI across generative AI and agentic systems

Part of **Objective domain 1: Plan and manage an Azure AI solution** (25-30%), Lesson 5 (L5).

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Configure safety filters, guardrails, risk detection, and content moderation
2. Apply responsible AI instrumentation, including evaluators, safety evaluations, and explanation tooling
3. Implement auditing through trace logging, provenance metadata, and approval workflows
4. Govern agent behavior with oversight modes, constraints, and tool-access controls

## The demo: match the surface to the control

Responsible AI here is **four controls, on the surface where each is really done** (full
click-by-click talk track in `Warner.AI-103.Lesson-05-demo-runbook.md` in the course folder):

| Control (LO) | Where it's done | Surface |
|---|---|---|
| **LO1 -- content filters** | create a filter with Prompt Shields; attach via `raiPolicyName` in Bicep | **Portal + IaC** |
| **LO2 -- instrumentation** | score answers with the Azure AI Evaluation SDK | **Python (`m05_evals_demo.py`)** |
| **LO3 -- auditing** | read an OpenTelemetry trace in Foundry / App Insights | **Portal** |
| **LO4 -- agent governance** | tool allow-list + required-approval / oversight modes | **Portal** |

The SDK is used for **only** LO2, because evaluators are a signal you'd genuinely wire into
CI to gate a release -- that's when code is the right surface, not a portal task dressed up
as a script.

## `m05_evals_demo.py` -- responsible AI instrumentation (LO2)

Scores the **same question two ways** -- one answer grounded in the source context, one
fabricated -- so the groundedness number visibly collapses on the made-up answer. It
**mutates nothing** (evaluators only read and score), so it's safe to run, safe to record,
and idempotent. Keyless throughout (`az login`); the judge `model_config` carries a
credential, not an API key.

| Evaluator | What it measures | Auth surface |
|---|---|---|
| `GroundednessEvaluator` | is the answer supported by the source context (1-5) | judge model (`model_config`) |
| `RelevanceEvaluator` | does the answer address the question (1-5) | judge model (`model_config`) |
| `ContentSafetyEvaluator` *(opt-in `--safety`)* | harmful-content rates | Azure AI Evaluation **service** (region-gated; skips gracefully) |

## Setup and run

```bash
cd lessons/05-responsible-ai-generative-agentic
uv sync
az login
cp .env.example .env        # fill in your judge endpoint + deployment

uv run python m05_evals_demo.py            # groundedness + relevance, grounded vs fabricated
uv run python m05_evals_demo.py --dry-run  # print the eval plan; call nothing
uv run python m05_evals_demo.py --safety   # also attempt the service-based safety evaluator
```

The `# %%` cell markers let you run one evaluator at a time in the VS Code Interactive Window
while you narrate.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
