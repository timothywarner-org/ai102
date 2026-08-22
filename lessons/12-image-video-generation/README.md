# Design and implement image- and video-generation solutions

Part of **Objective domain 3: Implement computer vision solutions** (10-15%), Lesson 12 (L12).

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Implement a solution that generates images from text prompts and reference media
2. Implement a solution that generates videos from text prompts and reference media
3. Configure image-editing workflows, including inpainting, mask-based edits, and prompt-driven modifications
4. Implement workflows to edit generated videos
5. Select and apply appropriate generation and editing controls provided by the platform

## The endpoint gotcha -- read this first

**Lesson 12 does not use the Foundry project endpoint.** Every other lesson in this
course points at `https://<account>.services.ai.azure.com/api/projects/<project>`,
because agents are project-scoped. Image and video model deployments are
**account-scoped**, and asking for them under `/api/projects/` returns a bare
`404` with no error body -- which looks exactly like a missing deployment and is
in fact a wrong path.

Verified against this account on 2026-08-11:

| `base_url` | `images.generate` | `videos.create` |
| --- | --- | --- |
| `https://<acct>.services.ai.azure.com/api/projects/<proj>/openai/v1` | **404** | **404** |
| `https://<acct>.openai.azure.com/openai/v1` | works | works |
| `https://<acct>.services.ai.azure.com/openai/v1` | works | works |

Both account hostnames resolve to the same account. The demos use the
`.openai.azure.com` form because that is what Microsoft Learn's image and video
documentation shows.

## Demos

Run demos directly from this folder. Python demos use **uv**, and authentication is **keyless** through `az login`.

```bash
uv sync                  # build the per-lesson venv
az login                 # keyless auth (AzureCliCredential)
cp .env.example .env     # then fill in your Foundry values
```

Every script supports `--dry-run`, which validates arguments and prints exactly what
would be sent without making a single Azure call. Generated media lands in `out/`.

Beats 2-5 need only the Foundry account. **Beat 1 additionally needs a storage account**
for the provenance API, which accepts a blob URI rather than raw bytes. Both Content
Safety APIs run against the **same AIServices account** the rest of the lesson uses --
no separate `--kind ContentSafety` resource is required, verified on 2026-08-11.

| Beat | Script | Objective | Wall clock |
| --- | --- | --- | --- |
| 1 | `m12_provenance_scan.py` | Responsible AI -- inspect media you were handed | ~2 min for the fixture set |
| 2 | `m12_image_gen.py` | LO1 -- generate images from text | ~2 min at `--quality high` |
| 3 | `m12_image_edit.py` | LO3 -- mask-based edit / inpainting | ~30 s |
| 4 | `m12_video_gen.py` | LO2 -- generate video from text | ~65 s for a 4-second clip |
| 5 | `m12_video_remix.py` | LO4 -- edit a generated video | ~70 s |

LO5 (selecting the right generation and editing controls) is threaded through beats
2-5: `size`, `quality`, the mask geometry, `seconds`, and the remix prompt are the
controls, and each script prints the ones it used.

Beat 1 is the inverse of the rest of the lesson. Beats 2-5 **make** media; Beat 1 asks
what Azure can tell you about media somebody hands you.

### `m12_provenance_scan.py` -- harm categories and content provenance

```bash
uv run python m12_provenance_scan.py --folder img/
uv run python m12_provenance_scan.py --dry-run          # enumerate, zero Azure calls
uv run python m12_provenance_scan.py --only harm
uv run python m12_provenance_scan.py --local-c2pa       # parse manifests offline
```

Two different questions, two different APIs, one Foundry account:

| API | Question | Status |
| --- | --- | --- |
| `POST /contentsafety/image:analyze` | Is this image harmful? | **GA**, `api-version=2024-09-01` |
| `POST /contentsafety/provenance:detect` | Was this made by a Microsoft AI system? | **Preview**, `api-version=2026-07-01-preview` |

**Analyze Image has no provenance awareness at all.** It returns four harm categories
(`Hate`, `Sexual`, `Violence`, `SelfHarm`) at severity `0/2/4/6` and nothing else.
Provenance is a completely separate API that reads **C2PA Content Credentials** and
Microsoft's **invisible watermark**. Conflating the two is the exam trap.

#### The three-way split

The `img/` folder is a deliberately chosen fixture set. Verified against this account
on 2026-08-11:

| Fixture | `caBX` chunk? | `provenance:detect` outcome |
| --- | --- | --- |
| `love_the_style_but_the_text.png` | yes, Microsoft-signed | **`ProvenanceDetected`** -- `type: C2PA`, `provider: Microsoft_Designer` |
| `chatgpt-gpt4o-signed.png` | yes, OpenAI-signed | `NoProvenanceDetected` |
| the other 19 | no manifest at all | `NoProvenanceDetected` |

**Row two is the whole lesson.** That file's own bytes say `softwareAgent: GPT-4o`,
`claim_generator: ChatGPT`, and
`digitalSourceType: .../trainedAlgorithmicMedia`. It is unambiguously AI-generated,
it carries a valid C2PA manifest, and Microsoft's API still answers
`NoProvenanceDetected` -- because the API detects
[Microsoft-generated content only](https://learn.microsoft.com/azure/ai-services/content-safety/concepts/provenance-detection).
Microsoft's own documentation states the corollary plainly: a result indicating that
no provenance was detected **does not** mean the content is not AI-generated.

Row three teaches the other half. Those 19 files have no `caBX` chunk, and no
`eXIf`/`tEXt`/`iTXt` either -- every byte of metadata is gone. That is the signature
of a **re-encode**: a browser download, a paste, a screenshot, or a save-as strips the
manifest wholesale. C2PA metadata is fragile.

Which is exactly why the **invisible watermark** exists. The Microsoft-signed fixture
carries a `c2pa.soft-binding` assertion with `alg: com.microsoft.invismark.1`, plus
`softwareAgent: Azure OpenAI ImageGen` and a second claim from `Microsoft_Designer`
showing a generate-then-edit **chain**. The watermark rides in the pixels and survives
what the metadata does not.

#### Mechanics that bite

- **Provenance takes a blob URI only.** No inline bytes, no base64. The body is
  `{"content": {"uri": "https://<acct>.blob.core.windows.net/..."}}`, and it must be a
  real Azure Storage URL -- anything else is rejected with
  `The provided URL is not a valid Azure Blob Storage endpoint`.
- **The Content Safety resource reads that blob as itself.** Its system-assigned
  managed identity needs **Storage Blob Data Reader** on the storage account. You need
  **Storage Blob Data Contributor** to upload. Both are required, and they are
  different roles on the same account.
- **Role assignments take up to 5 minutes to propagate.** During the gap, uploads and
  detection fail with a 403 that reads like a misconfiguration. It usually is not.
- **It is asynchronous.** `POST` returns an operation `id` **in the response body**,
  not in an `Operation-Location` header. Poll
  `GET /contentsafety/provenance/operations/{id}` until `status` leaves
  `NotStarted`/`Running`. Detection took ~5 s per file in testing.
- **Rate limit is roughly one request per 9 seconds** on an AIServices S0 tier. A
  naive loop over the fixture folder will earn a `429`; the script paces itself.
- **`NoProvenanceDetected` omits the `results` array entirely**, and the elements it
  does return may omit `modelName` and `timestamp`. Treat every field as optional.
- **Analyze Image caps at 4 MB** while provenance allows 100 MB. Several fixtures
  exceed 4 MB, so the script sends a Pillow-downscaled copy to the harm API and prints
  exactly what it resized. The original still goes to provenance untouched.

#### What this beat does not claim

Microsoft does not document which regions support provenance detection, and the
Content Safety region table has no column for it. It works on this account in
**eastus2**, verified empirically rather than from the docs. Google's Gemini and Imagen
use **SynthID**, a separate proprietary watermark that Azure cannot read, so no
Google-generated image will ever come back detected here.

### `m12_image_gen.py` -- text to image

```bash
uv run python m12_image_gen.py
uv run python m12_image_gen.py --size 1536x1024 --quality medium
uv run python m12_image_gen.py --dry-run
```

Three things worth saying out loud:

- **`gpt-image-2` always returns base64.** There is no `response_format="url"` on this
  surface the way there was on DALL-E. Every caller decodes bytes and owns the
  storage decision.
- **Images are billed in tokens.** A `quality=high` 1024x1024 render reported
  `output_tokens=7024`; the same prompt at `quality=medium` reported `1756`. That
  is a 4x cost difference and a 2.5x time difference, from one parameter.
- **Image deployments are throttled in requests per minute, not tokens per minute.**
  `gpt-image-2` here is provisioned at `count: 2, renewalPeriod: 60`. In testing a
  burst of four concurrent requests all succeeded, so treat 2 RPM as the floor you
  are entitled to rather than a hard wall -- but a long recording session with
  repeated takes will find it.

### `m12_image_edit.py` -- mask-based inpainting

```bash
uv run python m12_image_edit.py
uv run python m12_image_edit.py --dry-run      # builds the mask, calls nothing
uv run python m12_image_edit.py --region 0.05,0.55,0.45,0.95 --prompt "..."
```

The one idea: **in a mask, transparent means editable.** Alpha 0 marks the region the
model may repaint; alpha 255 is protected. That reads backwards to most people,
because "masking something off" normally means protecting it, so the script
generates the mask in code and prints the pixel split rather than shipping a
mystery PNG:

```text
  mask     : l12-image-02-mask.png  1024x1024  6,506 bytes
             alpha=0   (EDITABLE)  176,400 px   16.8%
             alpha=255 (protected) 872,176 px   83.2%
```

Mechanics that bite:

- The endpoint is `POST /openai/v1/images/edits` and it is **multipart/form-data**,
  not JSON. There is no base64 on the way *in*, only on the way *out*.
- The mask must be **exactly the same pixel dimensions** as the source, must be
  **PNG** (JPEG has no alpha channel, so a "JPEG mask" has no hole), and must be
  under **4 MB**. The source must be PNG or JPG under **50 MB**.
- The response is a **full re-render**, not a patched copy of your input. The
  protected region comes back visually equivalent, not byte-identical.

### `m12_video_gen.py` -- text to video, the async job

```bash
uv run python m12_video_gen.py
uv run python m12_video_gen.py --seconds 8 --size 1280x720
uv run python m12_video_gen.py --dry-run
```

This is where the *shape* of the API changes, and that is the lesson. Images are one
synchronous call. Video is a **job**: create, poll, download.

```text
  [job]   created  id=video_6a7b42d00b88819080ea65857bb47460
  [job]   status=queued

  [poll]  +00:22  in_progress  [###########.............]  46%
  [poll]  +00:43  in_progress  [########################]  99%
  [poll]  +01:04  completed    [########################] 100%

  [job]   completed in 64s  (1.1 min, 3 polls)
  [saved] l12-video-01.mp4  2,136,793 bytes
```

Statuses are `queued`, `in_progress`, `completed`, `failed`. The loop also guards
`cancelled`, because an unhandled terminal status is an infinite loop.

Sora 2 constraints that shape what you can demo:

- **Two concurrent jobs** per account.
- **Renders expire after 24 hours.** Download in the same session.
- The content filter blocks photorealistic people and recognizable IP, and rejects
  any reference image containing a **human face**. Keep prompts on objects,
  landscapes, and stylized animation.
- Needs a recent `openai` package. On an old one you get
  `AttributeError: 'OpenAI' object has no attribute 'videos'`.

The script writes the finished video id to `out/last_video_id.txt` so Beat 4 chains
without you copy-pasting an id off the screen mid-take.

### `m12_video_remix.py` -- editing a generated video

```bash
uv run python m12_video_remix.py
uv run python m12_video_remix.py --video-id video_xxxx --prompt "..."
```

How do you *edit* a generated video? You do not open it in a timeline. You **remix**
it: `videos.remix` takes a completed video id plus a new prompt and renders a **new**
video that inherits the source's composition, motion, and style.

The result is a new job with a new id, and the response carries
`remixed_from_video_id` -- the provenance link that turns one-off generation into an
editing *workflow*:

```text
  lineage:
    video_6a7b42d00b88819080ea65857bb47460   (original)
      -> video_6a7b43203bcc8190b806cc5943708f93   (remix, remixed_from_video_id=video_6a7b42d00b88819080ea65857bb47460)
```

Because the source must still exist, and renders expire after 24 hours, remix is a
same-session workflow. The script retrieves the source first and says so plainly
when the id has aged out, rather than surfacing a confusing failure on the remix call.

## Prompt hygiene

Every default prompt in this lesson is object-only: no people, no faces, no brands,
no named characters. That is not squeamishness, it is what survives both content
filters on every take. Sora 2 in particular rejects reference images containing a
human face outright.

## The `img/` fixture set -- do not re-save these files

`img/` is **committed on purpose**, unlike `out/`. Beat 1 is not reproducible without
it, and the two signed files cannot simply be downloaded again: any browser download,
editor save, or format conversion destroys the C2PA manifest that makes them useful.

If you need to rename one, **move the file** (`git mv`, or rename in Explorer). Never
open and re-save it. To confirm a fixture still carries its manifest, look for the
`caBX` chunk:

```bash
uv run python m12_provenance_scan.py --dry-run
```

The dry run reads every file locally, reports which ones carry a manifest, and makes
zero Azure calls -- so it is also the fastest pre-recording sanity check.

## Generated output

`out/` holds the rendered media and is gitignored. Nothing in this lesson creates
Azure resources, so all five scripts are safe to re-run as many times as a take
requires -- subject to the 2 RPM image quota and the ~9 s provenance pacing.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
