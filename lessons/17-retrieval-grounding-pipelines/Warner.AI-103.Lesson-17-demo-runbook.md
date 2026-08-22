# L17 RECORDING CARD -- Retrieval, Grounding, and a Pipeline an Agent Can Call

**3 beats, 4 commands, 13-16 min** | `lessons/17-retrieval-grounding-pipelines/`

> **Verified live 2026-08-14.** Every `CHECK` below is a real string from a real
> run. All ten proof checks green, including the Agent Framework tool call.

## THE ONE THING THAT WILL RUIN THE TAKE

**Beat 2 must run `--reset`.** Not optional.

```powershell
uv run python m17_ingest.py --reset
```

The indexer is **incremental**. Without `--reset` it processes **0 items**, and
the audio-boundary beat -- the whole "reports success while indexing nothing"
teaching moment -- **does not appear on screen at all.** You would be narrating
"seven processed" over a screen that says zero.

| Run | items processed | audio warning | Beat 2 works? |
| --- | --- | --- | --- |
| `m17_ingest.py` | **0** | absent | **NO** |
| `m17_ingest.py --reset` | **7** | present | **YES** |

`--reset` clears the high-water mark and reprocesses. It takes **21 seconds**,
it is safe, and it is idempotent. Run it.

> **Read the ORDER, not the decimals.** BM25 scores shift on a reindex --
> they are corpus statistics. Vector scores, fused scores, and reranker
> scores are stable, and those are the only decimals quoted below.

## TIMING REALITY

Scripts are fast. **Your voice is the runtime.** Do not rush to fill silence.

| Beat | Script time | Talk time | Total |
| --- | --- | --- | --- |
| 1 Portal, four objects | none | ~4 min | **4 min** |
| 2 Ingest `--reset` | 21s | ~4 min | **4-5 min** |
| 3a Retrieve | 0.3s | ~4 min | **4 min** |
| 3b Agent | 2s | ~3 min | **3 min** |

**Beat 3a prints 182 lines in 0.3 seconds.** It is finished before you finish the
sentence that launched it. **Scroll back to the top and narrate section by
section.** The output is pre-sectioned with rule lines for exactly this reason.

**Corpus:** seven blobs of Woodgrove Bank policy. Five markdown, one **scanned
page** (image, no text layer), one **audio file** that cannot be indexed at all.
The Premier Household wire-fee waiver exists **only as pixels** -- if a text
query returns it, six pipeline stages worked.

## PRE-FLIGHT

- [ ] `az login` -> `you@contoso.com`
- [ ] **Token has 30+ min left.** Tokens last 60-90 min. Check before you roll:
      `az account get-access-token --resource https://search.azure.com --query expiresOn -o tsv`
- [ ] `pwsh -File validate.ps1 -SkipCold` -> **ALL GREEN, 9 of 9** (~40s, primes the cache)
- [ ] Search service `YOUR-SEARCH-SERVICE` -> **running**
- [ ] Edge: **Azure portal** on the search service | tab 2 **Foundry**, `proj-agents`
- [ ] VS Code on `m17_ingest.py` at `skillset_definition`
- [ ] Terminal font large, scrollback deep. **Beat 3a is 182 lines.**
- [ ] Remember: **Beat 2 is `--reset`.**

---

## 1 · Portal -- four objects, and why the wizard stays closed (5 min)

`SHOW` **Search management** -> Indexes / Indexers / Data sources / Skillsets,
then **Overview** for the Usage tile

`SAY`

- Four object types. Every ingestion question in this domain is really "which of these four is wrong?"
- **Data source** = where content lives. **Index** = the shape answers come out in. **Skillset** = what happens on the way through. **Indexer** = the only thing that runs.
- A skillset **attaches to an indexer and never runs alone.** Need enrichment, OCR, or vectorization? The **pull** model is mandatory. Push loads documents; it cannot enrich them.
- One replica, one partition, one search unit -- **one indexer job at a time**, no SLA. Indexing competes with queries.

`SHOW` **Import data** -> Azure Blob Storage -> walk to the summary
`DO` **Cancel.** Do not run it.

`SAY`

- Good tool. One pass, and it emits all four objects. Go read them afterwards -- best way to learn the shapes.
- I am closing it for one reason: the wizard attaches billing with the **key-based** form, which calls a **regional** endpoint and demands both services in the **same region**. Mine are not.
- It would hand me `Provided key isn't a valid CognitiveServices type key for the region of your search service` -- and the word "key" sends people off rotating a key that was never the problem.
- The fix is an **identity-based** attach. No region rule, and no checkbox. So we hand-author the JSON, which you want anyway, because the JSON is what the exam tests.

`FIX` wizard can't see the container -> the **search service's** identity needs
Storage Blob Data Reader, not yours.

---

## 2 · Ingest, enrich, and project (5 min)

`SHOW` `skillset_definition()` -- scroll the four skills

`SAY`

- Watch **context** change: OCR once per image, Merge once per document, Embed once per chunk. Context sets how often a skill runs *and* where its output hangs.
- **imageAction is on the INDEXER, not the skillset.** OCR reads normalized images and nothing else, and that node does not exist until the indexer makes it. Backwards, and OCR returns empty while the run says success.
- Cracking split text from images before any skill ran. OCR output **does not rejoin the body on its own** -- Merge puts it back at the right offset so the splitter and embedder can see it.

```powershell
uv run python m17_ingest.py --reset
```

**`--reset` is mandatory.** Without it: 0 items processed, no audio warning, no beat.
Takes 21 seconds. Talk over it -- the `context` point above fills the gap.

`CHECK` **items processed 7, items failed 0, status success**
`CHECK` warning **`Could not extract content or metadata from your document`** (the .wav)
`CHECK` **audio blob -- counted as PROCESSED, contributed 0 chunks**
`CHECK` **`[WARN] a green run can hide a content type that never made it in`**
`CHECK` **search documents (chunks) 11** -- `text/markdown 10`, `image/png 1`
`CHECK` **came from wg-addendum-scan.png**
`CHECK` **`[OK] text that only ever existed as pixels is now a citable search document`**

> **Two other warnings scroll by. Both are expected. Do not chase them.**
> `SplitSkill.split -- one or more skill input was invalid` is the Split skill
> receiving the audio file's null content. It is the same story as the .wav, one
> stage later. `ImageAction is set on the indexer` is the image-extraction
> **billing** notice, and it is the second meter mentioned in Beat 1.

`SAY` the audio beat -- **slow down here**

- Objective one names audio and video, so people assume an indexer cracks them. It does not. No codec.
- But look at **how** it declined. Seven processed, **zero failed**, status **success** -- and a warning nobody reads. That file contributed **nothing**.
- Worse than a crash. A crash gets investigated. This reports perfect health while a whole content type never arrives.
- Speech and video get searchable the old way: transcribe separately, index the **text**.

`SAY` the OCR landing

- One line proved six stages: normalize, OCR, merge, split, embed, project.
- **Index projections turn one source document into many.** Chunk without one and you still get exactly one search document per file.
- That chunk key is the parent's storage path, base64-encoded, plus an ordinal -- **regenerated when the parent changes**, so never bookmark it from your app.

`FIX` `403` -> data-plane roles, not Owner. `--` `400` naming the region -> the
attach reverted to the key form.

---

## 3 · Retrieval, and hanging it off an agent (6-7 min)

> Two scripts. `m17_retrieve.py` replays instantly from cache; `m17_agent.py`
> runs **~30s** warm because the agent's tool calls go live. Talk over it.

```powershell
uv run python m17_retrieve.py
```

`CHECK` `WG-ADD-7742` on BM25: **wg-addendum-scan.png first, next result an order of magnitude back**
`CHECK` same token on pure vector: **0.596 / 0.580 / 0.556** -- almost flat
`CHECK` **wg-fee-schedule.md on BM25 rank 10 of 10**
`CHECK` **wg-fee-schedule.md on vector rank 4 of 11**
`CHECK` **wg-fee-schedule.md now ranks 1**, reranker **2.2243**, answer **0.988**
`CHECK` hybrid collapses to the **0.03** range, order intact
`CHECK` **`[OK] A was never reranked. B was. Neither request errored.`**
`CHECK` **`[OK] the top-ranked grounding chunk came out of the scanned image`**

`SAY` two opposite failure modes

- BM25 owns **exact tokens** -- part numbers, codes, surnames. Vectors own **paraphrase**. Hybrid is not a hedge, it is coverage of both.
- The addendum code: BM25 puts it an order of magnitude ahead of the runner-up. The vector run is nearly flat -- an embedding of an identifier is an embedding of nothing in particular.
- A vector query **always returns k neighbors**, even when nothing is similar. Pure vector never comes back empty, so it feeds a model confident garbage unless keyword recall supplies the "no good match" signal.

`SAY` the three ranks -- **the most honest moment in the lesson**

- Same question, three numbers. Keyword buries the answering document at **10 of 10**. Vector lifts it to **4**. The reranker puts it **first** and pulls the fee table out verbatim.
- Be precise: the vector did not get the right answer, it made the right answer **reachable**. **Recall decides what is reachable; ranking decides what is first.** In that order.
- Hybrid drops two orders of magnitude, order holds. Rank fusion discards both raw scores and keeps only rank, because an unbounded BM25 score and a bounded similarity score cannot be added. **Never threshold a fused score.**

`SAY` the silent no-op -- **the beat that pays for the lesson**

- A: pure vector, `queryType` semantic, valid configuration. **200**. Results. **No reranker score.**
- B: identical plus `semanticQuery`. Same 200. Scores appear.
- `queryType` invokes the ranker for plain-text and hybrid. On a **pure vector** query, `semanticQuery` does it. Raising `k` would not have fixed A -- the ranker was never called.
- **A 200 means Azure accepted your request. It never meant Azure did what you thought you asked.**

```powershell
uv run python m17_agent.py
```

`CHECK` **query planning gpt-5-mini**, roughly **1k input tokens**
`CHECK` **three or four subqueries**, each a focused rewrite of one clause
`CHECK` **ref_id 0 is wg-addendum-scan.png** -- the scanned page is the top reference
`CHECK` medium **3-4 subqueries, 7-9 references**; minimal **1 subquery, 3 references**
`CHECK` **tool registered search_woodgrove_policy -> l17-woodgrove-kb**
`CHECK` **tool_choice auto** and **approval_mode never_require** print under it
`CHECK` **the model invoked the retrieval pipeline 1 time(s)**
`CHECK` answer cites **[0] [1] [2]** -- `$30.00`, the `$250,000` waiver, `4:00 PM`
`CHECK` out of scope -> tool called again, then **"I don't know based on the Woodgrove Bank policy content I have."**
`CHECK` **tool exposed knowledge_base_retrieve**

`SAY`

- A **knowledge source** is the content. A **knowledge base** is the retrieval **contract** over one or more sources. The agent declares *what* to ground on; the base decides *how*.
- Classic RAG turns one question into one search. The activity log shows one sentence becoming **three focused subqueries**, run in parallel, each reranked, then merged.
- Retrieval that cannot show its work cannot be debugged. That log is which subqueries ran, against what, at what cost.
- The dial: **minimal** effort takes the model out of retrieval entirely. It also refuses chat history -- *Messages input not supported when 'minimal' reasoning effort is requested*. No planner, nothing to read it. More intelligence is not automatically better.
- **Output mode decides who writes the answer.** With an agent downstream, return extractive -- synthesis means two models write the same answer and you pay twice to starve the agent.
- Everything above called retrieve **because the script said so**. Now it is a **function tool** on an Agent Framework agent -- whether retrieval runs is the **model's** decision. Same body, same knowledge base, different owner.
- The tool's **docstring is the schema** the model sees. Vague wording there is a retrieval bug, not a comment.
- Two knobs are printed on purpose. **tool_choice**: `auto` lets the model decide, `required` forces a call, `none` disables calling but keeps the tool in the schema. This demo needs `auto` -- force the call and Beat 4 proves nothing.
- **approval_mode**: `never_require` here because retrieval is read-only. `always_require` pauses the run for human sign-off -- that gate belongs on the tool that moves money, not the one that reads policy.
- A cited, correct answer that **never called the tool** is the model reciting training data. On screen it looks identical. Count the calls.
- The knowledge base is **also an MCP server** with one retrieve tool. The pipeline is a portable tool, not code welded into one app.

`SAY` the close

1. **If it enriches, it is an indexer.** Skillsets never run alone, and the enrichment tree is temporary until you route it somewhere.
2. **Recall first, ranking second.** Hybrid covers two opposite failure modes; the reranker only reorders what stage one already found.
3. **A 200 proves acceptance, not behavior.** Prove retrieval with a score you can see and grounding with a citation you can follow.

`SAY` I hope you found this lesson helpful. I will see you next time.

---

## OPTIONAL 90 SECONDS if you are short

`SHOW` Foundry -> `proj-agents` -> agent -> **Knowledge** -> add the knowledge
base -> ask the compound question -> open the trace.
`SAY` two ways to give an agent search: a **search tool bound to one index**
running a single query, or a **knowledge base** that plans across many sources.

> **[UNVERIFIED]** The portal attach flow was **NOT exercised this session**. The
> knowledge base, retrieve action, query plan, and MCP tool were all verified
> live from code. If the portal disagrees, trust the code and cut this beat.

## PANIC TABLE

| Symptom | Fix on camera |
| --- | --- |
| **`items processed 0`** | You forgot `--reset`. Re-run **`m17_ingest.py --reset`**. 21s. |
| **Numbers moved, cache looks cold** | You ran `--clean` off shell history. Restore in 2s: `Remove-Item .cache -Recurse -Force; Copy-Item .cache-primed .cache -Recurse` |
| **`[FAIL] CredentialUnavailableError`** | Token expired. `az login`, then re-run. The script prints the fix. |
| **No audio warning in Beat 2** | Same cause. Incremental run. `--reset`. |
| `SplitSkill.split ... input was invalid` | **Expected.** The .wav's null content, one stage on. Keep going. |
| BM25 decimals differ from this card | **Expected after any reindex.** Teach 10 -> 4 -> 1, never the decimals. |
| `403` on the first search call | Data-plane auth or roles. **Owner grants nothing here.** |
| `400` mentioning the region | Attach reverted to the key form. Identity form has no region rule. |
| OCR fields empty | `imageAction` on the **indexer**, `contentAndMetadata`, default parsing. |
| Index full of nulls, no chunks | Missing index projection. |
| `409 Another indexer invocation is currently in progress` | One search unit runs one job. The script waits it out; on camera, just wait. |
| Success, but the index looks short | Read the **warnings**. Green hides content that never arrived. |
| No `rerankerScore` on a vector query | `semanticQuery`, not `queryType`. Do not raise `k`. |
| Retrieve returns `206` | One source failed, others succeeded. Open the source, not Azure status. |
| Semantic suddenly billing-errors | Free allowance spent. Do not debug live -- switch takes. |

## DO NOT

- **Do not run the Import data wizard.** Key-based billing plus a region split is a guaranteed failure.
- **Do not quote the BM25 decimals as constants.** Teach the movement: 10, then 4, then 1.
- **Do not call the semantic ranker a retriever.** It reorders; it cannot rescue what stage one never found.
- **Do not say the indexer "fails" on audio.** It reports success and indexes nothing. Better story, and the true one.
- **Do not pass `--clean` or `--no-cache`.** `--clean` wipes the primed cache and
  every retake goes live and slow. `--reset` is the exception: **Beat 2 requires it.**
- **Do not skip the out-of-scope question.** The refusal is the only proof the grounding is real.

## AFTER THE SHOOT

```powershell
uv run python m17_teardown.py --blobs
az search service delete -n <search-service> -g rg-ai103-mvp --yes
```

The service is the expensive object. Deleting the pipeline does not stop the meter.

## OBJECTIVE COVERAGE

| LO | Where |
| --- | --- |
| 1 ingest documents, images, audio, video | Beat 1 four objects, Beat 2 seven blobs + the audio boundary |
| 2 semantic, hybrid, vector search | **Beat 3a**, all six sections |
| 3 enrichment with built-in and custom skills | Beat 1 billing attach, Beat 2 OCR + Merge + Split + Embed |
| 4 RAG ingestion flow including OCR | Beat 2 end to end, chunking and index projections |
| 5 retrieval connected to workflows and agent tools | **Beat 3b** knowledge base, activity log, Agent Framework function tool, MCP tool |

## CUT FROM CAMERA (still runs)

`--dry-run` prints all four JSON bodies with nothing sent (good B-roll).
`--exclude-media` filters the audio by extension. `--minimal-only` is the
low-effort contrast alone. The soft-delete policy is live on the data source:
an indexer sees what exists, not what vanished.
