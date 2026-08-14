# Build retrieval and grounding pipelines

Part of **Objective domain 5: Implement information extraction solutions** (10-15%), Lesson 17 (L17).

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Ingest and index content, such as documents, images, audio, and video
2. Configure semantic search, hybrid search, and vector search for grounding
3. Implement enrichment by using custom or built-in skills for text, images, and layout
4. Configure RAG ingestion flow, including documents and using optical character recognition (OCR)
5. Connect retrieval pipelines directly to workflows and agent tools

## The idea

A grounding pipeline is one long dependency chain, and almost every failure in
it is **silent**. The indexer reports success while a content type never
arrives. The skillset runs while its output lands nowhere. The query returns
HTTP 200 while the ranker was never invoked. This lesson builds the chain end to
end and then makes each of those failures visible on purpose.

Three fixtures do the heavy lifting:

| Fixture | What it proves |
| --- | --- |
| Five markdown policy documents | ordinary text extraction, chunking, vectorization |
| One **scanned page** with no text layer | the whole OCR chain, in a single query result |
| One **audio file** | that a blob indexer has no codec -- and declines *quietly* |

The Premier Household wire-fee waiver exists **only as pixels** inside
`assets/corpus/wg-addendum-scan.png`. Nothing in the text corpus mentions it.
When a text query returns that content, six stages are proven at once:
image normalization, OCR, text merge, chunking, embedding, and index projection.

## Setup

```bash
az login
cd lessons/17-retrieval-grounding-pipelines
uv sync
cp .env.example .env        # fill in every value, then: pwsh -File validate.ps1
```

Everything is **keyless**. `AzureCliCredential`, never `DefaultAzureCredential` --
the latter probes environment variables first and will happily authenticate as
whatever service principal is sitting in the shell.

### Two things must be true before anything works

Both are pre-flight, both are silent when wrong, and neither is fixed by having
Owner on the subscription.

**1. The search service must honor Microsoft Entra on the data plane.** A search
service ships accepting API keys only. In that state a perfectly valid bearer
token returns HTTP 403 no matter what roles you hold.

```bash
az search service update -n <service> -g <rg> \
    --auth-options aadOrApiKey --aad-auth-failure-mode http403
```

Then assign to your user, on the **service** scope: `Search Service Contributor`,
`Search Index Data Contributor`, `Search Index Data Reader`.

**2. The search service needs a managed identity of its own.** The blob
connection, the skillset billing attach, the embedding skill, the query-time
vectorizer, and the knowledge base's model all authenticate as the **service**,
which is a different security principal from you.

```bash
az search service update -n <service> -g <rg> --identity-type SystemAssigned
```

Grant that identity `Cognitive Services User` and `Cognitive Services OpenAI
User` on the Foundry resource, and `Storage Blob Data Reader` on the storage
account. Role assignments take several minutes to take effect.

`validate.ps1` checks both of these before it spends an Azure call, and prints
the exact command to fix each one.

### Cross-region is the interesting constraint here

The search service and the Foundry resource are in different regions, which is
not the recommended layout but is a completely realistic one. It matters in
exactly one place: a **key-based** skillset billing attach calls a regional
endpoint and requires both services in the same physical region. The
**identity-based** attach carries no region requirement, and that is what
`m17_ingest.py` uses. Integrated vectorization works across the gap either way.

The portal's Import data wizard attaches the key-based form automatically, which
is why the runbook opens the wizard and then closes it.

## Demos

Beat 1 runs in the Azure portal with no code.

```bash
uv run python m17_ingest.py                  # Beat 2: build and run the pipeline
uv run python m17_ingest.py --dry-run        #   all four JSON bodies, nothing sent
uv run python m17_ingest.py --reset          #   clear the high-water mark first
uv run python m17_ingest.py --exclude-media  #   filter the audio out by extension

uv run python m17_retrieve.py                # Beat 3a: keyword, vector, hybrid, semantic
uv run python m17_agent.py                   # Beat 3b: knowledge base, agent tool, MCP
uv run python m17_agent.py --minimal-only    #   just the reasoning-effort contrast

uv run python m17_teardown.py --blobs        # remove everything this lesson created
```

Query results are cached by content hash, so retakes replay instantly and the
scores on screen are byte-identical. `--no-cache` forces live calls, `--clean`
starts cold.

**The cache only ever stands in for read-only calls** -- searches, retrieves, and
GETs. It raises `UnsafeToCache` on anything else. `m17_ingest.py` has no cache at
all; it is idempotent instead, which is the honest equivalent. Run it twice and
the second run is fast because the *service* did less work, not because this
repo pretended.

## Beat 3b is a real agent

Objective 5 says "agent tools," so Beat 3b builds a **Microsoft Agent Framework**
`Agent` over `FoundryChatClient` with the knowledge base registered as a function
tool. The framework runs the tool loop; the retrieve body stays visible inside
the tool, because the JSON is still the lesson.

A script that retrieves and then prompts has **hard-wired** the retrieval: it
runs once, always. An agent with a retrieval **tool** decides. Both are on screen.

| What prints | Why it matters |
| --- | --- |
| `the model invoked the retrieval pipeline N time(s)` | a cited, correct answer that never called the tool is the model reciting training data, and looks identical |
| the agent searches *before* declining the crypto question | it cannot know the corpus is silent until it looks |

The tool's **docstring is the schema** the model sees. Vague wording there is a
retrieval bug.

## Status

**Verified live.** All three beats ran green against `srch-ai103-l17-tw` cold and
then warm, including the Agent Framework tool call in Beat 3b. Every number
quoted in the demo runbook is a real value from that run, captured in
`validation-output.txt`.

Re-prove it any time:

```powershell
pwsh -File validate.ps1          # cold, then warm, then ten proof checks
pwsh -File validate.ps1 -SkipCold
```

There is **no offline harness** in this lesson, deliberately. Lesson 16 shipped
with one that passed nine of nine assertions while three beats were broken,
because it tested the shape of the requests this repo composed rather than what
Azure did with them. An assertion about your own request proves nothing about the
service. Every check in `validate.ps1` is downstream of a real response: did the
indexer report success, how many chunks exist, did text that was only ever pixels
come back from a text query, did the reranker score appear when and only when it
should have, did the planner emit more than one subquery, did the grounded model
decline the question it cannot answer.

## Files

| File | Beat | What it owns |
| --- | --- | --- |
| *(Azure portal)* | 1 | the four object types, and the wizard's billing attach |
| `m17_ingest.py` | 2 | data source, index, skillset, indexer; OCR, chunking, projections |
| `m17_retrieve.py` | 3a | keyword vs vector vs hybrid, the semantic ranker, the silent no-op |
| `m17_agent.py` | 3b | knowledge source, knowledge base, activity log, agent tool, MCP |
| `m17_common.py` | all | settings, `AzureCliCredential`, REST, token audiences |
| `m17_cache.py` | all | content-addressed cache, read-only operations only |
| `m17_teardown.py` | -- | deletes in reverse dependency order |
| `assets/make_assets.py` | -- | builds the corpus, renders the scan, writes the audio |
| `validate.ps1` | pre-flight | environment guard, cold then warm, ten proof checks |

## Cost

The search service is the expensive object, and deleting the pipeline does not
stop the meter. When recording is finished:

```powershell
uv run python m17_teardown.py --blobs
az search service delete -n <search-service> -g <rg> --yes
```

Note also that two meters run during ingestion: extracting **text** from
documents is free, extracting **images** is billed by Azure AI Search itself,
separately from what OCR costs on the Foundry resource. The indexer emits a
warning the moment `imageAction` is turned on.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
