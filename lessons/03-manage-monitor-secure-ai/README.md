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

The optional signal **generator** below needs two more (it calls a model and reads telemetry, so
it is not pure-read): **Cognitive Services OpenAI User** on the Foundry account (to call the model)
and **Log Analytics Reader** on `log-ai103-l03` (to run the KQL that catches the trace).

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
uv run python m03_generate_signal.py     # LO2 deep-dive: emit REAL traces, then print the KQL to catch them
```

The `# %%` cell markers let you run one signal at a time in the VS Code Interactive Window while
you narrate. The recording runbook is `Warner.AI-103.Lesson-03-demo-runbook.md` (in this folder).

## Generate and catch a real signal (LO2 deep-dive)

`m03_ops_demo.py` proves the Observability pipe is **wired** (it prints `Application Insights:
CONNECTED`). `m03_generate_signal.py` proves the pipe **carries data**: it makes real `gpt-5-mini`
calls through the Foundry project, auto-instruments them with OpenTelemetry **GenAI semantic
conventions**, exports the spans to the project's Application Insights, and prints the exact KQL to
catch them. Unlike the read-only demo, this script **produces** telemetry, so it lives in its own
file. `uv sync` pulls the two extra packages it needs (`azure-monitor-opentelemetry`,
`opentelemetry-instrumentation-openai-v2`).

```bash
uv run python m03_generate_signal.py --calls 4 --content   # 4 real calls; capture prompt/response text
```

Traces land in the **`log-ai103-l03`** Log Analytics workspace within **2 to 5 minutes**. The script
prints the run's `OperationId`; catch it three ways:

```kql
// 1. One run's spans by OperationId (parent + one child per model call)
AppDependencies
| where OperationId == '<printed-operation-id>'
| project TimeGenerated, Name, DurationMs, Target
| order by TimeGenerated asc

// 2. Per-call token cost, pulled from the GenAI span attributes
AppDependencies
| where Name startswith 'chat gpt-5-mini'
| extend P = parse_json(Properties)
| project TimeGenerated, DurationMs,
          RespModel = tostring(P['gen_ai.response.model']),
          InTokens  = toint(P['gen_ai.usage.input_tokens']),
          OutTokens = toint(P['gen_ai.usage.output_tokens'])

// 3. The dashboard rollup: call count, latency, total tokens by model
AppDependencies
| where Name startswith 'chat gpt-5-mini'
| extend P = parse_json(Properties)
| summarize calls=count(), avg_latency_ms=round(avg(DurationMs),0),
            max_latency_ms=round(max(DurationMs),0),
            total_in_tokens=sum(toint(P['gen_ai.usage.input_tokens'])),
            total_out_tokens=sum(toint(P['gen_ai.usage.output_tokens']))
    by RespModel = tostring(P['gen_ai.response.model'])
```

Run the KQL from the portal (Foundry **Tracing**, or the workspace **Logs** blade) or the CLI:
`az monitor log-analytics query -w <workspace-guid> --analytics-query "<kql>"`.

**Student notebook:** `uvx juv run m03_ops_tour.ipynb` -- the same signals as a runnable,
idempotent, keyless learner notebook (teaching-point markdown + live code). It reads (and, being
idempotent, can re-seed) the shared `ai103-l03-demo` search index that `m03_ops_demo.py` also reads.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
