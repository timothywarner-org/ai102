# Build generative applications by using Foundry

Part of **Objective domain 2: Implement generative AI and agentic solutions** (30-35%), Lesson 8 (L8).

This objective group spans three lessons, L6, L8, and L9. The full objective list is shown verbatim in Modules 06, 08, and 09 so no module drops a learning objective. L8 also contributes to the "Optimize and operationalize generative AI systems" group, covered in Module 07.

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

### `rag.py` -- classic RAG, end to end, in code

The code half of the lesson. The portal shows the managed **knowledge base**
abstraction (Foundry IQ / agentic retrieval); this shows **classic RAG** -- the
pattern you own: **ingest -> embed -> retrieve -> inject -> generate-grounded**.
Runs against a dedicated Azure AI Search instance + a Foundry project with a
chat model (`gpt-5-mini`) and an embedding model (`text-embedding-3-large`).
Keyless throughout (Entra ID via `az login`).

```bash
# One-time setup
az login                 # keyless -- SDKs borrow this identity, no keys on disk
cp .env.example .env     # fill in your endpoints
uv sync                  # install dependencies

# (a) Run the embedding job: build the index + embed every KB article
uv run rag.py ingest

# (b) Retrieval in code: hybrid (keyword + vector) search
uv run rag.py search "how do I rotate API keys without dropping sessions?"

# Full RAG loop: retrieve + inject + grounded answer (cites its sources)
uv run rag.py ask "how do I rotate API keys without dropping sessions?"

# (c) Force reindexing after adding a new document, and prove it's retrievable
uv run rag.py reindex
```

Infrastructure (dedicated Azure AI Search + the model deployments) is
provisioned by `infra/modules/search.bicep` and connected to the project as the
`aisearch` connection -- the preferred Azure AI Search connector. The FREE
search tier is used, so there is no semantic reranker; hybrid search alone still
returns strong results. Required roles (**Search Index Data Contributor**,
**Search Service Contributor**, **Cognitive Services OpenAI User**) are granted
by the infra templates. `seed_index.py` remains as a minimal index-only seeder.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
