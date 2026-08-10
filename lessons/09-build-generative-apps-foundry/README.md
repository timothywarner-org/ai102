# Build generative applications by using Foundry

Part of **Objective domain 2: Implement generative AI and agentic solutions** (30-35%), Lesson 9 (L9).

This objective group spans three lessons, L6, L8, and L9. The full objective list is shown verbatim in Modules 06, 08, and 09 so no module drops a learning objective. L9 also contributes to the "Optimize and operationalize generative AI systems" group, covered in Module 07.

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Deploy and consume LLMs, small models, code models, and multimodal models
2. Implement retrieval-augmented generation (RAG) in an application
3. Design workflows, tool-augmented flows, and multistep reasoning pipelines
4. Evaluate models and apps, including detecting fabrications, relevance, quality, and safety
5. Integrate generative workflows into applications by using Foundry SDKs and connectors
6. Configure an application to connect to a Foundry project

## Demos

Run demos directly from this folder (uv-managed Python, keyless via Entra ID).

### `eval_trace.py` -- evaluate + observe a Foundry RAG app

The code spine of the lesson. Against the Lesson 8 Contoso Cloud RAG index, it
does the two things L9 is about: **evaluate** answer quality with Foundry's
built-in evaluators (Groundedness + Relevance) and gate a release on the score,
and **observe** the app by instrumenting it with OpenTelemetry and shipping
traces, tokens, and latency to Application Insights -- viewable in the Azure
portal, the Foundry portal, and via KQL.

```bash
# One-time setup
az login                 # keyless -- SDKs borrow this identity
cp .env.example .env     # fill in your endpoints + App Insights conn string
uv sync

# EVALUATE: score answers (Groundedness + Relevance, 1-5) and gate on a threshold
uv run eval_trace.py evaluate

# OBSERVE: run traced RAG turns; telemetry ships to Application Insights
uv run eval_trace.py trace

# Then watch the traces land in:
#   * Azure portal   -> appi-ai103-l09 > Transaction search
#   * Foundry portal -> proj-lesson-08 > Tracing
#   * Log Analytics  -> run the queries in kql/traces.kql
```

Infrastructure (Application Insights + Log Analytics, connected to the project
as the `appinsights` connection) is provisioned by
`infra/modules/observability.bicep`. The full click-by-click demo script is in
`Warner.AI-103.Lesson-09-demo-runbook.md`; KQL for the trace/token/latency data
is in `kql/traces.kql`.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
