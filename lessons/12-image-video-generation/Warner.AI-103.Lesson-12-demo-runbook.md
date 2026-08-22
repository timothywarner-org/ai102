# L12 RECORDING CARD -- Provenance, Image Gen, Mask Edits, Sora, Remix

Full detail (RBAC rebuild, endpoint matrix, complete troubleshooting): **`...-runbook-REFERENCE.md`**
Folder: `lessons/12-image-video-generation/` | ~30 min cut | ~5.4 min of it is service time

**Legend:** fenced block = paste into terminal | `SHOW` = put on screen | `SAY` = trigger bullets, riff them | `WAIT` = expected stall, don't panic | `CHECK` = proof it worked | `FIX` = if it blows up here

---

## PRE-FLIGHT (off camera)

- [ ] `az login` -> `az account show` says `tim@techtrainertim.com`
- [ ] `uv sync` -- `openai` must be **>= 2.44.0** (older has no `client.videos`)
- [ ] `.env` -> `FOUNDRY_ACCOUNT_ENDPOINT=https://aif-ai103-l11-gcn5uizgywfac.openai.azure.com` (**no** `/api/projects/...`)
- [ ] **Delete `out/`** -- stale files let a beat fake-succeed
- [ ] All four `--dry-run`s green. Provenance dry run must report **exactly 2** manifests. Zero = `git checkout -- img/`
- [ ] Windows open: Foundry Deployments blade | VS Code on lesson folder | Photos + video player parked on `out/`
- [ ] **Pick image quality now:** `high` = 133 s stare. `medium` = 53 s. Shoot medium, quote high.

---

## 1 · Beat 1 -- What can Azure tell you about an image? (6 min)

```powershell
uv run python m12_provenance_scan.py --demo
```

`WAIT` ~30 s, 3 files, both APIs each. `[pace] waiting Ns` lines are real quota, leave them in.

`SHOW` `m12_provenance_scan.py` docstring, **L1-30**

`SAY` cold open

- Whole lesson makes media. First, flip it: somebody hands you a PNG.
- **Two questions, two APIs, not the same question.** Is it harmful? Was it AI-made?
- Analyze Image = **GA**, 4 harm categories, severity 0/2/4/6. Knows nothing about AI origin.
- Content Provenance Detection = **preview**, reads C2PA + Microsoft invisible watermark.

`CHECK` 3 files, summary shows **one** `ProvenanceDetected`

`SAY` walking the table

- File 1: Microsoft-signed. Detected, C2PA, provider = Microsoft Designer. It names the *provider*.
- File 2 **(the money row)**: from ChatGPT. `manifest: yes` **and** `NoProvenanceDetected`. Not a bug.
- Microsoft's API detects **Microsoft**-generated content. OpenAI signed it, out of scope.
- File 3: no manifest. Nothing to find.

```powershell
uv run python m12_provenance_scan.py --local-c2pa --only provenance --demo
```

`CHECK` MSFT file: `agent=Azure OpenAI ImageGen`, soft-binding present. ChatGPT file: `agent=GPT-4o`, `digitalSourceType=trainedAlgorithmicMedia`, `issuer=OpenAI`

`SAY` the landing

- `trainedAlgorithmicMedia` = the IPTC code for "a machine made this." File told the truth all along.
- **Absence of provenance proves nothing.** Microsoft says so in their own docs. Write it down.
- Other 19 files: zero metadata. Browser download / editor re-save strips the container wholesale.
- C2PA is fragile. The **invisible watermark rides in the pixels** and survives re-encode. That's why it exists.

`WAIT` Hold the summary table. Two rows say `manifest: yes`, one says detected. The contradiction is the shot.

---

## 2 · The endpoint that isn't the one you've been using (3 min)

`SHOW` `.env.example` **L11-33**, matrix at **L25-29**

`SAY`

- Agents are **project**-scoped. Image and video models are **account**-scoped, not projected under that path.
- Point L10/L11's project endpoint at images -> **404 with no error body**. Message is literally `Error code: 404`.
- Token fine, deployment exists, call correct, path wrong. Cost me the most time building this.
- Both account hostnames work. We use `.openai.azure.com` because that's what MS Learn shows.

`SHOW` `m12_image_gen.py` -> `build_client()` **L90-130**

`SAY` four non-negotiables, all exam-relevant

1. **L123** `AzureCliCredential`, not `DefaultAzureCredential`. Default probes env vars first, a stale `AZURE_CLIENT_ID` hijacks you silently.
2. Audience = `https://ai.azure.com/.default`, **not** cognitiveservices, even though it's a Cognitive Services account under the covers.
3. **L125** plain `OpenAI`, never `AzureOpenAI`. AzureOpenAI appends `api-version`; `/v1` is versionless and rejects it.
4. **L127** `api_key` is a **callable**, not a string. SDK re-calls it every request. Pass a static token and it works right up until you sit in a Sora poll loop and expire mid-render. CLI handed me ~30 min of life, not an hour.

---

## 3 · Beat 2 -- Text to image, LO1 (5 min)

`SHOW` `m12_image_gen.py` `DEFAULT_PROMPT` **L81-88**

`SAY` Brass compass on a chart. No people, faces, brands, characters. Not squeamish, practical -- **Sora rejects any reference image with a human face**. Pick subjects that survive both filters and you can re-shoot forever.

```powershell
uv run python m12_image_gen.py --dry-run
uv run python m12_image_gen.py
```

`CHECK` dry run ends `[dry-run] Arguments valid. No Azure call made.` and endpoint line reads `.../openai/v1`
`WAIT` **133 s at high, 53 s at medium.** Cut on the `[saved]` line or narrate the cost point below.
`CHECK` `[saved] l12-image-01.png` then `[usage] ... output_tokens=7024`

`SHOW` `out/l12-image-01.png` in Photos

`SAY`

- **An image is priced in tokens.** 55 in (the prompt), 7,024 out (the picture).
- Same prompt at `medium`: **1,756 tokens, 53 s**. One parameter. **4x cost, 2.5x time.**
- *That* is what "apply the appropriate generation controls" means in practice.

`SHOW` decode loop **L245-253**

`SAY` **L249** base64 decode is the contract, not a convenience. DALL-E's `response_format=url` **does not exist** on gpt-image-2. Every caller gets bytes and owns the storage decision. Better default anyway: no expiring link, no accidental public blob.

`FIX` 404 here = project endpoint in `.env`. Handler at **L230-234** prints the URL it used. Read it aloud, fix it.

---

## 4 · Beat 3 -- Mask-based editing, LO3 (6 min)

`SHOW` `m12_image_edit.py` `build_mask()` **L132-163**, with **L147** and **L156-157** both visible

`SAY` the unlearning

- **Transparent means editable.** Alpha 0 = model may repaint. Alpha 255 = protected, comes back untouched.
- Reads backwards on purpose: in English you mask to *protect*, tape on the trim. Here the transparent part is **the hole you cut so the model can reach through**.
- **L147** start at 255 everywhere = protect all. **L156-157** punch the hole.
- Color in that tuple is `0,0,0` but **irrelevant** -- could be magenta. Service reads **alpha only**.
- Which is exactly why the mask must be **PNG**. JPEG carries no alpha, so a JPEG mask is a mask with no hole.

```powershell
uv run python m12_image_edit.py --dry-run
```

`SAY` Dry run **builds the real mask and writes it** with zero Azure calls. Look before you spend a request.

`SHOW` `out/l12-image-02-mask.png` -- checkerboard square upper right is the hole, solid is protected

```powershell
uv run python m12_image_edit.py
```

`WAIT` ~29 s
`CHECK` `alpha=0 (EDITABLE) 176,400 px 16.8%` / `alpha=255 (protected) 872,176 px 83.2%` -- **deterministic, will match exactly**

`SHOW` edited next to original

`SAY`

- Sextant, upper right, same chart, same light direction, shadow falls right. **83.2% protected, 16.8% repainted. That's inpainting.**
- Honest caveat, say it before a sharp learner does: the response is a **full re-render**, not a patched copy. Protected region is visually equivalent, not byte-identical. Need untouched pixels? Composite back over the original with the same mask.

`SHOW` `images.edit` call **L294-303**

`SAY` Two mechanics. **L294** both files opened binary -- this endpoint is **multipart/form-data**, not JSON. No base64 inbound, only outbound. Matters the second you drop to curl. And the mask must be **exactly** the source's dimensions; 1023x1024 against 1024x1024 is a 400 with an unhelpful message, so we assert locally at **L275**.

`FIX` "source image not found" = Beat 2 didn't run or `out/` was cleared. Re-run Beat 2 or `--source <any png>`.

---

## 5 · Beat 4 -- Text to video, the async job, LO2 (6 min)

`SHOW` `m12_video_gen.py` `videos.create` **L218-223**, then polling loop **L236-260**

`SAY`

- It's not the prompt that's different, it's **the shape of the API**.
- Image = one synchronous call, wait, get bytes. Video = **a job**. Create, get an id and status back immediately, poll.
- Same client, same auth, same base URL -- **identical `build_client`**. Only `client.videos` instead of `client.images`.
- Write video code like image code and you build something that blocks an HTTP request for two minutes and dies behind a load balancer.
- **L237** + `TERMINAL_STATUSES` at **L70**: queued, in_progress, completed, failed. I guard `cancelled` too -- an unhandled terminal status is an infinite loop, and an infinite loop on camera is a bad day.

```powershell
uv run python m12_video_gen.py
```

`WAIT` **~64 s, 3 polls at 20 s. DO NOT CUT.** The `queued -> in_progress -> completed` transition is the whole segment.
`CHECK` progress bar fills, `[job] completed in ~64s`, `[saved] l12-video-01.mp4`, `[note] video id written to last_video_id.txt`

`SHOW` play `out/l12-video-01.mp4`

`SAY` 4 s, 1280x720, 30 fps, **ships with an audio track**. Real render, not a slideshow.

`SAY` three Sora constraints that shape what you can build

1. **Two concurrent jobs** per account. Third create gets rejected. Fanning out? You need a queue in front.
2. **Renders expire in 24 hours.** Download in-session. Never architect around yesterday's video id.
3. Content filter blocks photorealistic people and recognizable IP, and rejects reference images with a human face. Objects, landscapes, stylized animation = the safe lane.

`FIX` `'OpenAI' object has no attribute 'videos'` = old package. `uv add "openai>=2.44.0"`.

---

## 6 · Beat 5 -- Remix, or how you "edit" generated video, LO4 (4 min)

`SHOW` `m12_video_remix.py` `client.videos.remix` **L216**, provenance print **L223-229**

`SAY`

- "How do I **edit** it?" You don't open a timeline. You **remix**.
- Completed video id + new prompt -> a **new** video inheriting composition, motion, style, with your change on top.
- New job, new id. **Original is not mutated.** Both videos exist.

`SHOW` `DEFAULT_PROMPT` **L68-73**

`SAY` I'm changing **time of day** and adding mist, deliberately not the subject. Remix is strongest when it preserves composition and motion. Ask for a different subject and you're just generating a second video with extra steps.

```powershell
uv run python m12_video_remix.py
```

`WAIT` ~67 s, 3 polls. **Say "same loop" out loud** -- that's half the value here.
`CHECK` `[job] remixed_from_video_id=...` **must equal** the `source :` id at the top of the run. Point the cursor at it.

`SHOW` play `l12-video-01.mp4` then `l12-video-02-remix.mp4` back to back

`SAY`

- Same boat, same lagoon, same hills, same push-in. Different hour, mist on the water. **That inheritance is what separates a remix from a second generation.**
- `remixed_from_video_id` turns this from a party trick into a **workflow**. Every derivative points at its parent. Six weeks out when legal asks where a clip came from, that field is your answer.
- **L196-211**: it retrieves the source and confirms `completed` before remixing. Extra API call, earns its keep -- renders expire at 24 h, and without that check "remix failed" is a mystery.

---

## 7 · Recap and close (2 min)

`SAY` the one-through-five

1. Two different questions about an image. Analyze Image = harm. Provenance = did a **Microsoft** system make it. **Absence proves nothing.**
2. Images and video are on the **account** endpoint, not the project. Punishment is a **404 with no body**.
3. Image gen is synchronous, returns **base64 only** (no URL option), billed in **tokens** -- quality is a cost dial, not just a look dial.
4. **Transparent means editable.** Alpha 0 is the hole. PNG, exact source dimensions.
5. Video is a **job**: create, poll, download. You edit by remixing -> new id plus `remixed_from_video_id` pointing home.

`SAY` the two to carry out

- **Mask:** transparent means editable. Say it out loud once, never invert it again.
- **Provenance:** "no provenance detected" is not a verdict that an image is real. We watched it say that about a file with "GPT-4o" written inside. These tools tell you when something **is** signed. They cannot tell you when something isn't AI.

`SAY` I hope you found this lesson helpful. I'll see you next time.

---

## PANIC TABLE (top 8 -- rest in the REFERENCE file)

| Symptom | Real cause | Fix on camera |
| --- | --- | --- |
| `404` with **no error body** | `.env` has a project endpoint | `FOUNDRY_ACCOUNT_ENDPOINT=https://<acct>.openai.azure.com`, no path |
| `no attribute 'videos'` | old `openai` package | `uv add "openai>=2.44.0"` |
| 401 / `InvalidAuthenticationToken` | wrong audience or expired login | scope `https://ai.azure.com/.default`; `az login` |
| 400 mentioning `api-version` | somebody used `AzureOpenAI` | plain `OpenAI` + bearer provider |
| 401 **mid-poll** on video | static token string replaced the provider callable | put `get_bearer_token_provider` back |
| 429 on `videos.create` | Sora = **2 concurrent jobs** | let Beat 4 finish before Beat 5 |
| Beat 5 "source is queued, not completed" | started remix too early | wait for `last_video_id.txt` line |
| Beat 1 all files `manifest: no` | something re-saved `img/` | `git checkout -- img/`, then never open those files |

**Beat 1 `NoProvenanceDetected` on the ChatGPT file is CORRECT.** It's the point of the beat. Nothing to fix.

---

## DO NOT

- Do not re-save anything in `img/` -- committed fixtures, two carry C2PA manifests. Rename by moving, never by re-saving.
- Do not cut inside the video polling output (Beats 4 and 5).
- Do not run Beat 4 and Beat 5 concurrently.
- Do not record with a stale `out/`.
