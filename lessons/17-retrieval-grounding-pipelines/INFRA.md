# L17 LIVE INFRASTRUCTURE — read this before writing any code

These values were verified live. They **supersede** anything in a prompt or an
older note. If something here disagrees with what you were told, THIS IS RIGHT.

| What | Value |
| --- | --- |
| subscription | `92fd53f2-c38e-461a-9f50-e1ef3382c54c` (vs-enterprise-150-monthly-2025) |
| identity | `tim@techtrainertim.com` — `az login` already done |
| resource group | `rg-ai103-mvp` |
| **AI Search** | **`srch-ai103-l17-tw`** |
| **Search tier** | **`standard` (S1) — NOT Basic. Do not avoid features on tier grounds.** |
| **Search region** | **`southcentralus` — NOT eastus2.** |
| Search endpoint | `https://srch-ai103-l17-tw.search.windows.net` |
| semantic ranker | enabled, `standard` plan |
| Foundry account | `aif-ai103-l11-gcn5uizgywfac` (eastus2) |
| storage | `stai103l12prov92fd53` (eastus2) |
| embeddings | `text-embedding-3-large` deployment |
| chat | `gpt-5.1`, `gpt-5-mini` |

## Why the region moved

Microsoft Learn states East US 2 **"is experiencing capacity constraints that
prevent the creation of new search services and scaling operations."** A create
there fails. South Central US carries the full matrix — AI enrichment, semantic
ranker, agentic retrieval, and query rewrite.

**Consequence you must handle:** Search is in `southcentralus`, Foundry and the
model deployments are in `eastus2`. That cross-region hop is supported but it is
real. Co-location is the documented recommendation, so if latency shows up on
camera, say so honestly rather than hiding it.

## Auth

`AzureCliCredential` only. Never `DefaultAzureCredential` — it probes environment
variables first and will silently authenticate as whatever service principal is
sitting in the shell.

Data-plane roles needed on the Search service: **Search Service Contributor**
(create indexes/indexers/skillsets) and **Search Index Data Contributor**
(push documents). Owner is control plane and grants NO data actions. Verify with
a live call before assuming; a 403 on camera is unrecoverable.

## Cost — this matters

S1 is roughly **$245/month**, about **$8/day**. It is deliberately oversized so
nothing throttles mid-recording. **It must be deleted after Tim records:**

```powershell
az search service delete -g rg-ai103-mvp -n srch-ai103-l17-tw --yes
```

Put that line in the runbook's cleanup section. Do not let it quietly bill.

## Already done for you — do not re-litigate these

- [x] Search service created, `standard` (S1), `southcentralus`, semantic ranker
      on the `standard` plan.
- [x] **Entra data-plane auth ENABLED.** A Search service defaults to
      **API-key-only**, which rejects `AzureCliCredential` tokens no matter what
      roles you hold. Fixed with:
      `--auth-options aadOrApiKey --aad-auth-failure-mode http403`
      This is the L16-class trap for this lesson. It is closed.
- [x] Tim holds **Search Service Contributor** and **Search Index Data
      Contributor** on the service.
- [x] Unused `gpt-audio-1.5` deployment removed.

## Use the EXISTING Foundry project

Do **not** create a new project. Tim's `proj-agents` project and the agent inside
it are the continuity thread of this course — in Lesson 16 he says on camera
"this is the same agent you built earlier in the course." Lesson 17 should attach
retrieval to **that** agent. A brand-new project breaks the narrative.

---

# VERIFIED LIVE DURING DEMO BUILD -- these supersede everything above

Every line in this section was produced by a real call against real Azure while
building the lab, not read out of documentation.

## Pre-flight that was MISSING and is now DONE

The notes above said the search service had no managed identity. It has one now,
and the lab does not work without it.

```
az search service update -n srch-ai103-l17-tw -g rg-ai103-mvp --identity-type SystemAssigned
```

| Item | Value |
| --- | --- |
| system-assigned principalId | `0eb870be-af23-441f-aba6-9cccb8129329` |
| role on the Foundry account | `Cognitive Services User` (billing attach) |
| role on the Foundry account | `Cognitive Services OpenAI User` (embedding skill, vectorizer) |
| role on the storage account | `Storage Blob Data Reader` (blob data source) |

Data-plane auth was already `aadOrApiKey`, and a bearer token from
`AzureCliCredential` was confirmed working against `/indexes`. **No admin key is
used anywhere in this lab.**

## API versions actually available on this service

| Version | Probe result |
| --- | --- |
| `2026-04-01` | stable. indexes, indexers, skillsets, datasources, knowledgeSources, knowledgeBases all `200` |
| `2026-05-01-preview` | `200`. Required for knowledge-base query planning with a model, answer synthesis, and configurable reasoning effort |
| `2025-11-01-preview` | `200` |
| `2025-09-01` | works for classic objects, **`400` on knowledgeSources / knowledgeBases** |

The lab uses the stable version for the ingestion pipeline and the preview
version only where the preview feature is the teaching point.

## Region matrix, confirmed against the published table

South Central US carries **AI enrichment, availability zones, agentic retrieval,
semantic ranker, and query rewrite**. Nothing in this lesson is region-blocked
here. East US and East US 2 are both flagged as capacity constrained for new
search service creation, which is why the service lives where it does.

## Cross-region behaviours, proven end to end

- **Integrated vectorization works across the gap.** Search in South Central US
  called `text-embedding-3-large` on the eastus2 Foundry account at both index
  time and query time. 3072 dimensions.
- **The identity-based billing attach works across the gap.**
  `#Microsoft.Azure.Search.AIServicesByIdentity` with `identity: null` was
  accepted and OCR billed successfully. The key-based form is the one with the
  same-region requirement.
- **The knowledge base reached `gpt-5-mini` cross-region** for query planning,
  using the search service's identity.

## Behaviour that contradicts the common assumption -- AUDIO

The expectation was that a blob indexer hard-fails on an audio file. **It does
not.** With the `.wav` left in the container:

```
status success   itemsProcessed 7   itemsFailed 0
WARNING  DocumentExtraction.azureblob.wg-call-recording.wav
         Could not extract content or metadata from your document.
WARNING  Enrichment.SplitSkill.split
         Could not execute skill because one or more skill input was invalid.
```

The audio file is **counted as processed**, the run is **green**, and it
contributes **zero** searchable content. The lab keeps the file in the container
because that silent gap is a better lesson than a crash would be.

Also emitted on every run, and worth quoting on camera:

```
WARNING  IndexerProcessor
         ImageAction is set on the indexer and will incur an additional charge
         for image extraction.
```

## Other live results worth keeping

- **OCR quality on the generated scan is excellent.** The full addendum text,
  including `WG-ADD-7742` and `$250,000`, came back verbatim through OCR ->
  Merge -> Split -> Embed -> index projection.
- **Corpus shape:** 7 blobs -> 6 cracked -> **11 chunks** (`text/markdown` 10,
  `image/png` 1).
- **Minimal reasoning effort rejects conversational input**, with a genuinely
  useful error: `Messages input not supported when 'minimal' reasoning effort is
  requested. Use intents input instead.`
- **The MCP endpoint is real** and exposes exactly one tool,
  `knowledge_base_retrieve`. It answers as a server-sent-event stream, so the
  client must send `Accept: application/json, text/event-stream`.
- **BM25 scores move when the index is rebuilt.** The same query returned a
  different top-1 before and after a `--reset`. Teach rank position, not decimals.

## Objects this lab creates

All prefixed `l17-woodgrove`, plus one blob container `l17-grounding`. Teardown
deletes them in reverse dependency order:

```
uv run python m17_teardown.py --blobs
```

The search service itself is deliberately **not** deleted by any script.
