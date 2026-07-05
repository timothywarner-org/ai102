# Lesson 3 -- Manage and Monitor AI Systems

Hands-on demo for **Module 3** of *Exam AI-103: Developing AI Apps and Agents on Azure*.
Part of **Objective domain 1: Plan and manage an Azure AI solution** (25-30%).

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Manage quotas, scaling, rate limits, and cost footprints for model and agent workloads
2. Monitor model performance, drift, safety events, and grounding quality
3. Monitor data ingestion quality, search index health, and relevance performance

## The demo: one project, read-only ops signals mapped to the three demo clips

`m03_ops_demo.py` reads live operational signals -- it **mutates nothing**, so it's safe to run
and safe to record. Keyless throughout (`az login`). The signals follow the deck's three demo clips.

| Signal (LO / clip) | What it reads | SDK |
|---|---|---|
| **LO1 -- quota headroom** | TPM used vs limit per model in a region | `azure-mgmt-cognitiveservices` `usages.list` |
| **LO1 -- cost guardrails** | month-to-date cost by resource group ("cost per workload") | `azure-mgmt-costmanagement` `query.usage` |
| **LO2 -- Observability** | the project's Application Insights connection (the monitoring pipe) | `azure-ai-projects` `telemetry` |
| **LO3 -- index health + relevance** | document count, storage, indexer status, and **recall@k over a labeled gold query set** | `azure-search-documents` |

Each signal skips gracefully if its config is missing, so you can run one at a time.

## Roles you need (read-only)

- **LO1 quota:** any reader on the subscription can list usages.
- **LO1 cost:** **Cost Management Reader** on the subscription (subscription **Reader** usually suffices).
- **LO2:** **Foundry User** on the project.
- **LO3:** **Search Index Data Reader** (query) and **Reader** (stats/indexer) on the Search service.

## Setup and run

```bash
cd lessons/03-manage-monitor-secure-ai
uv sync
az login
cp .env.example .env        # fill in your values
uv run python seed_index.py              # ONE-TIME: create the ai103-l03-demo index the demo reads
uv run python m03_ops_demo.py            # every signal (quota, cost, observability, search)
uv run python m03_ops_demo.py --dry-run  # list what it would read; call nothing
uv run python m03_ops_demo.py --only cost   # one signal: quota | cost | monitor | search
```

The `# %%` cell markers let you run one signal at a time in the VS Code Interactive Window while
you narrate. The recording runbook is `Warner.AI-103.Lesson-03-demo-runbook.md` (in this folder).

**Student notebook:** `uvx juv run m03_ops_tour.ipynb` -- the same signals as a runnable,
idempotent, keyless learner notebook (teaching-point markdown + live code). It reads (and, being
idempotent, can re-seed) the shared `ai103-l03-demo` search index that `m03_ops_demo.py` also reads.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
