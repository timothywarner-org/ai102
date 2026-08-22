# AI-103 — Lesson 9 Demo: Click-by-Click (Evaluate + Observe)

Folder: `lessons/09-build-generative-apps-foundry/`. Keyless — `az login` once.
Runs against the same M365 RAG index from Lesson 8, plus Application Insights
(`appi-ai103-l09`, connected to `proj-lesson-08`).

## Pre-flight (off camera)
1. `cd lessons/09-build-generative-apps-foundry`
2. `az login`
3. `uv sync`
4. Make sure the L8 index is warm: from the L8 folder, `uv run rag.py ingest` (once).
5. Open these tabs, logged in: **App Insights `appi-ai103-l09` → Transaction search**; **Foundry portal → `proj-lesson-08` → Tracing**; **App Insights → Logs**; VS Code on `kql/traces.kql`.

## On camera
1. **Evaluate + gate:**
   `uv run eval_trace.py evaluate`
   → table of Groundedness + Relevance (1–5), then `[gate] 4/4 ... SHIP`.
2. **Emit traces:**
   `uv run eval_trace.py trace`
   → each RAG turn prints an `operation_Id`. **Copy one.**
3. **App Insights view:** Transaction search tab → refresh → open your `operation_Id` → expand the span tree (`rag.turn` → retrieval → `chat gpt-5-mini`). *(1–3 min ingestion delay — say so on camera.)*
4. **Foundry portal view:** `proj-lesson-08` → Tracing → same traces, no extra setup.
5. **KQL:** App Insights → Logs. Paste from `kql/traces.kql`:
   - **Query 1** → recent model calls with latency + token counts.
   - **Query 2** → throughput + P95 latency in 5-min buckets.
   - *(optional)* **Query 3** → paste your `operation_Id` to replay one request end to end.

## Notes
- Both subcommands are read-only against your data and safe to re-run.
- If App Insights looks empty, you're inside the 1–3 min ingestion delay — refresh.
- If a KQL column is blank, run **Query 0** first to see the real `customDimensions` keys.
