# L13 RECORDING CARD -- Studio, Vision Chat, CU Analyzer, CU Video, Pro-Mode Post-Mortem

Folder: `lessons/13-multimodal-understanding/` | **~23 min cut** | ~1 min is service time
All terminal output below was **captured live 2026-08-12** against `aif-ai103-l11-gcn5uizgywfac`.

**Legend:** fenced block = paste into terminal | `SHOW` = put on screen | `SAY` = trigger bullets, riff them | `WAIT` = expected stall, don't panic | `CHECK` = proof it worked | `FIX` = if it blows up here

## BEAT MAP

| # | Beat | Surface | LOs | Min |
|---|---|---|---|---|
| 1 | Content Understanding Studio | **Portal** | 5 | 4 |
| 2 | Vision is in your chat model | SDK | 1,2,3,4 | 5 |
| 3 | Same analyzer, in code | SDK | 5,8 | 5 |
| 4 | CU video analysis | SDK | 6 | 3 |
| 5 | Video Indexer -- the other video answer | **Portal** | 6 | 3 |
| 6 | Pro mode is gone | SDK | 7 | 2 |
| 7 | Recap | — | — | 1 |

---

## PRE-FLIGHT (off camera)

- [ ] `az login` -> `az account show` says `tim@techtrainertim.com`
- [ ] `uv sync` in the lesson folder
- [ ] **Sign in to Studio first** -> https://contentunderstanding.ai.azure.com/ -> pick `aif-ai103-l11-gcn5uizgywfac`. Do the tenant/consent dance **now**, not on camera.
- [ ] **CU account defaults set.** Once per resource, already done. A rebuilt RG needs it again:
      `PATCH {cu-endpoint}/contentunderstanding/defaults?api-version=2025-11-01`
      header `Content-Type: application/merge-patch+json`, body `{"modelDeployments":{"gpt-5-mini":"gpt-5-mini"}}`
      Skip it and every analyzer create fails `DefaultsNotSet`.
- [ ] `.env` has **both** hosts (they are different, that's Beat 3):
      `FOUNDRY_ACCOUNT_ENDPOINT=https://aif-ai103-l11-gcn5uizgywfac.openai.azure.com`
      `CONTENTUNDERSTANDING_ENDPOINT=https://aif-ai103-l11-gcn5uizgywfac.services.ai.azure.com/`
- [ ] `assets/compass-chart.png` + `assets/clip.mp4` present (both carried from L12)
- [ ] **Delete `out/`** -- stale files let a beat fake-succeed
- [ ] All four `--dry-run`s green
- [ ] **Pre-index `clip.mp4` in Video Indexer off camera** -> https://www.videoindexer.ai/accounts/b75e476d-9682-435b-a8c3-7726df46c77f/ (indexing takes real minutes; open the finished one on camera)
- [ ] Windows: Studio tab | Video Indexer tab | VS Code on lesson folder | Photos on `assets/` | terminal

---

## 1 · Studio -- where analyzers actually get built, LO5 (4 min) · PORTAL

`SHOW` https://contentunderstanding.ai.azure.com/ with `aif-ai103-l11-gcn5uizgywfac` selected

`SAY` Two portals touch Content Understanding and **they are not equivalent**:

| | Studio | Foundry (ai.azure.com) |
| --- | --- | --- |
| Create custom analyzers | **Yes** | **No** |
| Prebuilt analyzers | All | Partial |
| API versions | GA + preview | Preview only |
| Data labeling | Yes | No |

`SAY` So if the task is "build an analyzer," Studio is the answer and the Foundry playground isn't. That's a service-selection question waiting to happen.

`SHOW` the analyzer list. `SAY` 88 prebuilts on this account out of the box -- documents, tax forms, audio, video, images.

`SHOW` **`ai103L13ImageV1`** in the list -- the one we'll run from code in Beat 3

`SAY` Walk the field schema on screen. Three methods and picking between them is the whole skill:

- **extract** -- pull a value that is literally there. **Documents only.**
- **classify** -- choose from *your* enum. Predictable, switchable downstream.
- **generate** -- write something new from what the model sees.

`SAY` Images get generate and classify. No extract, no confidence scores, no source grounding -- those are document-only.

`FIX` Studio shows no resource = wrong tenant in the picker, or you're at `ai.azure.com` instead of `contentunderstanding.ai.azure.com`.
`FIX` **Never** screenshot Foundry **classic** here. Deprecated 2026-07-15.

---

## 2 · Vision is already in your chat model, LO1-LO4 (5 min) · SDK

```powershell
uv run python m13_vision_chat.py
```

`WAIT` ~40 s, four passes. `CHECK` header reads `[endpoint] .../openai/v1` and `[model] gpt-5-mini`

`SAY` No new resource, no vision service. **The model you already deployed for chat reads images.** That's LO1.

`CHECK` concise caption:

```
A brass antique compass resting on a weathered nautical map
  [usage] prompt=753  completion=405  total=1,158
```

`SAY` Concise and detailed aren't two products, they're two prompts. That's LO2 on the current stack.

`CHECK` **the money moment -- the grounded Q&A refuses:**

```
NOT VISIBLE IN IMAGE
Evidence: The visible scene shows a single brass compass placed on an old,
beige nautical map lying on a dark wooden surface.
```

`SAY` I asked it something the picture can't answer and it **said no and cited what it did see**. That's LO3 -- grounded means chained to visible evidence, and when the evidence isn't there you get a refusal instead of a confident fiction.

`SHOW` alt-text pass. `SAY` Alt text short and functional, extended description long and structural. **WCAG 1.1.1 Non-text Content.** Note it never opens with "image of" -- the screen reader already said that.

`FIX` `FOUNDRY_ACCOUNT_ENDPOINT is not set` = `.env` has the old variable names.

---

## 3 · The same analyzer, from code, LO5 + LO8 (5 min) · SDK

`SAY` Studio built it. Now here's the same object as JSON, which is what you'd actually check into a repo.

```powershell
uv run python m13_cu_analyzer.py --dry-run
uv run python m13_cu_analyzer.py --skip-create --image ./assets/compass-chart.png
```

`SAY` **Two hostnames, same Azure account.** Chat and vision go to `*.openai.azure.com` then `/openai/v1`. Content Understanding goes to `*.services.ai.azure.com`. Point the image call at the wrong one and you get a bare `Error code: 404` with **no body** -- reads like a missing deployment, is actually a wrong path.

`CHECK` `[schema] 8 fields | 5 generate | 3 classify | 0 extract (unavailable for images)`

`WAIT` ~20 s. `CHECK` the fields come back:

```json
{
  "artifact_summary": "A brass pocket compass resting on an aged paper nautical chart...",
  "primary_artifact_type": "magnetic compass",
  "damage_locations": [
    "upper-left edge of the chart shows fraying and small tears",
    "left and lower edges display uneven, deckled tears and slight curling",
    "overall chart surface shows light foxing, especially near edges"
  ],
  "condition_grade": "good",
  "subject_matter": "navigation",
  "image_quality": "good",
  "requires_conservator_review": false
}
```

`SAY` **This is LO8, and look at what it is not.** I asked where the damage is and got "upper-left edge of the chart." Words. Not `{"x":412,"y":88}`. Content Understanding returns **fields, not bounding boxes**, and no per-field confidence either. Need pixels? Wrong tool -- that's Azure Vision object detection.

`FIX` `The 'analyzerId' cannot contain '-'` -- custom IDs take no hyphens, even though every prebuilt has one.
`FIX` `DefaultsNotSet` -- you skipped the pre-flight PATCH.

---

## 4 · Video analysis, LO6 (3 min) · SDK

```powershell
uv run python m13_cu_video.py --video ./assets/clip.mp4
```

`SHOW` the guardrail block it prints before calling anything

`SAY` Memorize these. Direct upload **200 MB / 30 min**. By URL **4 GB / 2 h**. Frames sample **~1 FPS**, every frame scaled to **512x512**. Spoken words only -- no music, no sound effects.

`WAIT` ~26 s. `CHECK`

```
# Video: 00:00.000 => 00:04.000
Width: 1280   Height: 720

Key Frames
- 00:00.800 ![](keyFrame.800.jpg)
- 00:01.600 ![](keyFrame.1600.jpg)
- 00:02.400 ![](keyFrame.2400.jpg)
- 00:03.200 ![](keyFrame.3200.jpg)
```

`SAY` Four key frames from four seconds. **You're watching the 1 FPS sampling happen.** Anything faster is invisible to this pipeline -- a design decision up front, not a knob you tune later.

`SAY` Output is Markdown on purpose. It drops into a vector store without a converter.

`FIX` empty contents = you're on `prebuilt-videoSearch`. Use **`prebuilt-video`** (now the default).
`SAY` No transcript because the clip has no speech. Correct behavior, say it out loud.

---

## 5 · Video Indexer -- the other video answer, LO6 (3 min) · PORTAL

`SHOW` https://www.videoindexer.ai/accounts/b75e476d-9682-435b-a8c3-7726df46c77f/

`SAY` Everyone assumes Content Understanding swallowed Video Indexer. **It did not.** Video Indexer is actively shipping -- GPT-5 summarization landed March 2026, a Foundry agents solution in June.

`SAY` This is an **Azure-connected ARM account**, not the free trial. It rides a user-assigned managed identity with Storage Blob Data Contributor on the storage account. That's the production shape, and it's the shape the exam describes.

`SHOW` upload `assets/clip.mp4`, or open an already-indexed video if you pre-loaded one

`SAY` Here's the split, and it's a service-selection question waiting to happen:

| Content Understanding | Video Indexer |
| --- | --- |
| RAG-ready output: scene descriptions, transcript, key frames | **Deep insights**: celebrity ID, speaker enumeration, sentiment |
| Schema-defined fields you design | Prebuilt insight models |
| Segment + custom per-segment metadata | Live / real-time streams, edge via Arc |

`SAY` Microsoft says it plainly: don't use Content Understanding for celebrity identification, speaker enumeration, or sentiment across long-form content. **Use Video Indexer for those.**

`SAY` And this is where the bounding boxes live. CU gave us words. Video Indexer does object and observed-people detection **with coordinates and timestamps**. Same modality, two tools, different answers.

`FIX` Account not listed = wrong tenant in the VI account picker, top right.
`FIX` Indexing a fresh upload takes real minutes. **Pre-index the clip off camera** and open the finished one.

---

## 6 · Pro mode is gone, LO7 (2 min) · SDK

```powershell
uv run python m13_agentic_mode.py
```

`SAY` Straight with you: **this objective describes a feature Microsoft retired.** Pro mode lived only in `2025-05-01-preview`, retired **2026-07-15**. "Single-task" came from Foundry classic, deprecated the same day.

`SAY` The exam still asks -- the skills outline is dated **April 16, 2026**. So learn it as vocabulary: pro mode took multiple documents, reasoned across them in steps, compared against reference data, and gave up grounding and confidence to do it.

`SHOW` the migration block. `SAY` Agentic mode replaces it. `config.workflow = "agentic"`. Documents only, one file per request, and Microsoft says plainly it **isn't a drop-in replacement** -- the cross-file reasoning is now your job.

`SAY` And for this lesson: **neither mode ever applied to images or video.** Your multimodal pipelines were never affected.

---

## 7 · Recap (1 min)

`SAY`

- Analyzers get **built in Studio**, not the Foundry playground.
- Vision is a property of the chat model. No new service.
- Content Understanding gives **fields**. Video Indexer and Azure Vision give **boxes**. Know which the question wants.
- Content Understanding did **not** replace Video Indexer. Deep insights and live streams are still VI.
- Video is 1 FPS at 512 square. Design for it.
- When the objective domain and the product disagree, answer the exam from the objective and build production on what ships.

---

## PANIC TABLE

| Symptom | Cause | Fix |
| --- | --- | --- |
| Studio shows no resource | wrong tenant, or wrong URL | `contentunderstanding.ai.azure.com`, re-pick tenant |
| `FOUNDRY_ACCOUNT_ENDPOINT is not set` | old variable names | wants `FOUNDRY_ACCOUNT_ENDPOINT` + `CHAT_MODEL` |
| bare `Error code: 404`, no body | project path on an image call | account host + `/openai/v1` |
| `DefaultsNotSet` | account never PATCHed | run the pre-flight defaults call |
| `analyzerId cannot contain '-'` | hyphen in custom ID | `ai103L13ImageV1` |
| CU call 401 | wrong token audience | `AzureCliCredential`; both scopes work |
| video returns empty contents | `prebuilt-videoSearch` | switch to `prebuilt-video` |
| no transcript on video | clip has no speech | expected, say so |
| analyzer create hangs ~20 s | LRO compiling the schema | normal |
| VI account not listed | wrong tenant | tenant picker, top right of videoindexer.ai |
| VI indexing still running | real processing time | pre-index off camera, open the finished video |

---

## DO NOT

- Do not promise per-field **confidence** or **bounding boxes** on an image pipeline. Neither exists.
- Do not reference `prebuilt-videoAnalysis`. It's in the docs and **not on the service**.
- Do not screenshot Foundry **classic**. Deprecated 2026-07-15.
- Do not call Image Analysis 4.0 current. Deprecated, retires **2028-09-25**.
- Do not re-create the analyzer on camera. Beat 3 uses `--skip-create` because Beat 1 already showed it.
