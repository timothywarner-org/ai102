# AI-103 — Lesson 8 Demo: Click-by-Click (RAG over your M365 files)

Folder: `lessons/08-build-generative-apps-foundry/`. Keyless — `az login` once.
Corpus = real files from your M365 tenant (`m365_docs.json`): a prompt-engineering
PDF (base) + the Responsible AI report (the reindex "new doc").

## Pre-flight (off camera)
1. `cd lessons/08-build-generative-apps-foundry`
2. `az login`
3. `uv sync`
4. `uv run rag.py ingest`   ← warms the index so step 2 below isn't cold

## On camera
1. **Show the source.** Open `m365_docs.json` — point out the SharePoint URLs (these are your real files).
2. **Run the embedding job (one doc at a time):**
   `uv run rag.py ingest`
   → 10 passages embed + index, one line each: `[3/10] pe-03 ... -> indexed`.
3. **Retrieval in code:**
   `uv run rag.py search "what is few-shot learning?"`
   → top hits ranked, each with its source file.
4. **Full RAG (grounded answer):**
   `uv run rag.py ask "how do temperature and top_p differ?"`
   → grounded answer with a `[cited title]`, then a **[sources]** list of clickable SharePoint URLs.
5. **Force reindex after adding a doc:**
   `uv run rag.py reindex`
   → `[before]` = no responsible-AI doc → adds it → `[after]` = it's now the top hit → **SUCCESS**.
6. **(Optional) Idempotency:** run `uv run rag.py ingest` again → still `10/10`, no duplicates.
7. **(Optional portal)** Foundry portal → `proj-lesson-08` → the `aisearch` connection (the managed knowledge-base view over the same index).

## Notes
- Every command is safe to re-run (upserts). `reindex` self-resets, so it tells the same story each take.
- Azure AI Search has a ~1–2s indexing lag; `reindex` polls through it automatically.
