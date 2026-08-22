# AI-103 -- Lesson 12 Demo Runbook (Provenance + Image Generation + Mask Edits + Sora Video + Remix)

Folder: `lessons/12-image-video-generation/`. Keyless, so you sign in once with `az login`.
Runs against the **account** `aif-ai103-l11-gcn5uizgywfac` in `rg-ai103-mvp` (eastus2) --
the same account L10 and L11 use, but **not** the same endpoint. See the pre-flight.

**Five demo beats, mapped to the frozen objectives:**

| Beat | Script | Objective |
| --- | --- | --- |
| 1. Harm scan + provenance | `m12_provenance_scan.py` | Responsible AI -- inspect media you were handed |
| 2. Text to image | `m12_image_gen.py` | LO1 -- generate images from text prompts and reference media |
| 3. Mask-based edit | `m12_image_edit.py` | LO3 -- inpainting, mask-based edits, prompt-driven modifications |
| 4. Text to video | `m12_video_gen.py` | LO2 -- generate videos from text prompts and reference media |
| 5. Remix | `m12_video_remix.py` | LO4 -- workflows to edit generated videos |

LO5 (select and apply the platform's generation and editing controls) is not a
separate beat. It is threaded through beats 2-5 and called out on camera: `size`,
`quality`, mask geometry, `seconds`, and the remix prompt are the controls.

Beat 1 is the inverse of the rest of the lesson, which is why it goes first. Beats 2-5
**make** media. Beat 1 asks what Azure can tell you about media somebody hands you --
and the honest answer has a sharp edge on it that learners need before they start
generating.

**Total on-camera time: roughly 26 to 30 minutes.** Machine time inside that, measured
on the smoke runs of 2026-08-11: Beat 1 **30 s** (`--demo`, three fixtures), Beat 2
**132.6 s**, Beat 3 **29.1 s**, Beat 4 **64 s**, Beat 5 **67 s** -- about 5.4 minutes of
the runtime is the services working.

---

## Environment

| Thing | Value |
| --- | --- |
| Subscription | `92fd53f2-c38e-461a-9f50-e1ef3382c54c` (`vs-enterprise-150-monthly-2025`) |
| Signed in as | `tim@techtrainertim.com` |
| Resource group | `rg-ai103-mvp` (eastus2) |
| Foundry account | `aif-ai103-l11-gcn5uizgywfac` (kind `AIServices`) |
| **base_url used** | `https://aif-ai103-l11-gcn5uizgywfac.openai.azure.com/openai/v1` |
| Image deployment | `gpt-image-2`, version `2026-04-21`, GlobalStandard, rate limit `count: 2 / 60 s` |
| Video deployment | `sora-2`, version `2025-12-08`, GlobalStandard, rate limit `count: 9 / 60 s` |
| Auth | `AzureCliCredential`, token audience `https://ai.azure.com/.default` |
| Client | plain `OpenAI` (never `AzureOpenAI` -- it appends `api-version`, which `/v1` rejects) |
| Python | 3.13 via `uv`; `openai==2.53.0`, `pillow==12.3.0`, `azure-identity==1.25.3`, `c2pa-python==0.37.6` |
| Project `proj-agents` | **Not used by this lesson.** It is an L10/L11 thing. |
| **Beat 1 endpoint** | `https://aif-ai103-l11-gcn5uizgywfac.cognitiveservices.azure.com` |
| Beat 1 auth | `AzureCliCredential`, audience `https://cognitiveservices.azure.com/.default` |
| Beat 1 storage | `stai103l12prov92fd53`, container `provenance-input` (eastus2) |

### Beat 1's endpoint is the same account through a different front door

The generation beats use `<acct>.openai.azure.com/openai/v1` with the **ai.azure.com**
token audience. Content Safety uses `<acct>.cognitiveservices.azure.com` with the
**cognitiveservices.azure.com** audience. One resource, two data planes, two audiences.
Mixing them up produces a 401 that looks like a broken login.

**A separate `--kind ContentSafety` resource is not required.** Microsoft's docs walk
you through creating one, and it is reasonable to assume the preview provenance route
only lives there. Verified on 2026-08-11 against this account: the `AIServices` Foundry
account already serves both routes.

| Route | api-version | Status | Verified |
| --- | --- | --- | --- |
| `POST /contentsafety/image:analyze` | `2024-09-01` | GA | HTTP 200 |
| `POST /contentsafety/provenance:detect` | `2026-07-01-preview` | Preview | works, eastus2 |

Microsoft does **not** document which regions support provenance detection, and the
Content Safety region table has no column for it. eastus2 works on this account. That
is an empirical finding, not a documented guarantee -- say it that way on camera.

### The endpoint finding -- this is a teaching moment, not a footnote

Images and video are **account-scoped**. The project endpoint that L10 and L11 use
returns a bare 404 for both. Measured, not guessed:

| `base_url` | `images.generate` | `videos.create` |
| --- | --- | --- |
| `https://<acct>.services.ai.azure.com/api/projects/proj-agents/openai/v1` | `NotFoundError: Error code: 404` | `NotFoundError: Error code: 404` |
| `https://<acct>.openai.azure.com/openai/v1` | **works** | **works** |
| `https://<acct>.services.ai.azure.com/openai/v1` | **works** | **works** |

Note the 404 carries **no error body** -- the message is literally `Error code: 404`.
That is why it reads like a missing deployment when it is really a wrong path.

---

## Pre-flight (off camera)

1. `cd C:\github\ai103\lessons\12-image-video-generation`
2. `az login` (confirm `az account show` says `tim@techtrainertim.com`)
3. `uv sync` -- builds `.venv` on Python 3.13. Confirm `openai` resolves to **2.44.0 or newer**;
   an older one has no `client.videos` at all.
4. `cp .env.example .env`, then set six values. Only the first one is subtle:

   ```
   FOUNDRY_ACCOUNT_ENDPOINT=https://aif-ai103-l11-gcn5uizgywfac.openai.azure.com
   IMAGE_MODEL=gpt-image-2
   VIDEO_MODEL=sora-2
   CONTENT_SAFETY_ENDPOINT=https://aif-ai103-l11-gcn5uizgywfac.cognitiveservices.azure.com
   STORAGE_ACCOUNT_NAME=stai103l12prov92fd53
   PROVENANCE_CONTAINER=provenance-input
   ```

   If the account was rebuilt, read the host straight off ARM:
   `az cognitiveservices account show -n <account> -g rg-ai103-mvp --query "properties.endpoints.\"OpenAI Sora API\"" -o tsv`
5. Confirm both deployments are `Succeeded`:
   `az cognitiveservices account deployment list -n aif-ai103-l11-gcn5uizgywfac -g rg-ai103-mvp -o table`
6. Smoke-test the dry runs -- they validate arguments and make **zero** Azure calls:
   `uv run python m12_provenance_scan.py --dry-run`, `uv run python m12_image_gen.py --dry-run`,
   `uv run python m12_video_gen.py --dry-run`, `uv run python m12_image_edit.py --dry-run`

   The provenance dry run is also your fixture check: it must report **exactly two**
   files carrying a C2PA manifest. If it reports zero, something re-saved the `img/`
   fixtures and Beat 1 has no positive case. Restore them from git.
7. **Delete `out/` before you record.** Beat 3 reads Beat 2's output and Beat 5 reads
   Beat 4's id, so a stale `out/` lets a beat "succeed" without the previous beat running.
   Beat 1 does **not** touch `out/` -- it reads `img/`, which is committed.
8. Open these, already signed in: **Foundry portal -> `aif-ai103-l11-gcn5uizgywfac` -> Deployments**
   (so `gpt-image-2` and `sora-2` are on screen); VS Code on the lesson folder;
   Windows Photos and a video player parked over `out/`.
9. **Decide your image quality before you roll.** `--quality high` took **132.6 s** and
   billed **7,024 output tokens**. `--quality medium` took **52.6 s** and billed **1,756**.
   Same prompt, same size. If the take needs to move, record Beat 2 at `medium` and
   mention the high-quality numbers rather than sitting through them.

**If the environment is gone entirely,** the account is shared with L10/L11 -- rebuild per
that runbook, then add the two model deployments:

```powershell
az cognitiveservices account deployment create -g rg-ai103-mvp -n <account> --deployment-name gpt-image-2 --model-name gpt-image-2 --model-version 2026-04-21 --model-format OpenAI --sku-name GlobalStandard --sku-capacity 2
az cognitiveservices account deployment create -g rg-ai103-mvp -n <account> --deployment-name sora-2 --model-name sora-2 --model-version 2025-12-08 --model-format OpenAI --sku-name GlobalStandard --sku-capacity 9
```

### Rebuilding Beat 1's storage (only if the storage account is gone)

The provenance API accepts a **blob URI only** -- no inline bytes -- so Beat 1 needs a
storage account and two role assignments. Beats 2-5 do not.

```powershell
az storage account create -n stai103l12prov92fd53 -g rg-ai103-mvp -l eastus2 --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 --allow-blob-public-access false
az storage container create -n provenance-input --account-name stai103l12prov92fd53 --auth-mode login
```

Then the RBAC. **Two different roles, and they are not interchangeable:**

| Principal | Role | Why |
| --- | --- | --- |
| The account's managed identity | **Storage Blob Data Reader** | Content Safety fetches the blob as itself |
| You | **Storage Blob Data Contributor** | The script uploads the file |

```powershell
$sub = "92fd53f2-c38e-461a-9f50-e1ef3382c54c"; $scope = "/subscriptions/$sub/resourceGroups/rg-ai103-mvp/providers/Microsoft.Storage/storageAccounts/stai103l12prov92fd53"; $msi = (az cognitiveservices account show -n aif-ai103-l11-gcn5uizgywfac -g rg-ai103-mvp --query identity.principalId -o tsv); $me = (az ad signed-in-user show --query id -o tsv); az rest --method PUT --url "https://management.azure.com$scope/providers/Microsoft.Authorization/roleAssignments/$([guid]::NewGuid())?api-version=2022-04-01" --body "{\"properties\":{\"roleDefinitionId\":\"/subscriptions/$sub/providers/Microsoft.Authorization/roleDefinitions/2a2b9908-6ea1-4ae2-8e65-a410df84e7d1\",\"principalId\":\"$msi\",\"principalType\":\"ServicePrincipal\"}}"; az rest --method PUT --url "https://management.azure.com$scope/providers/Microsoft.Authorization/roleAssignments/$([guid]::NewGuid())?api-version=2022-04-01" --body "{\"properties\":{\"roleDefinitionId\":\"/subscriptions/$sub/providers/Microsoft.Authorization/roleDefinitions/ba92f5b4-2d11-453d-a403-e96b0029c9fe\",\"principalId\":\"$me\",\"principalType\":\"User\"}}"
```

**Why `az rest` instead of `az role assignment create`:** on Azure CLI **2.85.0** every
`az role assignment` subcommand on this machine fails with
`(MissingSubscription) The request did not have a subscription or a valid tenant level
resource provider` -- including read-only `list`, and including when `--subscription` is
passed explicitly. Going straight at the ARM REST endpoint works. If `az role assignment`
starts working again on a newer CLI, prefer it; it is more readable.

**Then wait five minutes.** Role assignments take up to 5 minutes to propagate, and
during that window uploads fail with a 403 that reads exactly like a misconfiguration.
Worse, `az storage blob upload` reported **success** while silently failing during the
gap. Confirm with the dry run plus one real `--demo` pass before you record.

---

## Segment 1: Beat 1 -- what can Azure tell you about an image? (~6 min)

**Run this exact command. It takes 30 seconds and scans three files.**

```powershell
uv run python m12_provenance_scan.py --demo
```

[SAY] Welcome back. Tim Warner here. This whole lesson is about generating media, and
we're gonna do plenty of that. But before we make a single image, I want to flip the
question around. Somebody hands you a PNG. What can Azure actually tell you about it?

[SAY] Because there are two questions hiding in there and they are not the same question.
One: is this image harmful? Two: was this made by AI? Azure answers those with two
completely different APIs, and conflating them is an exam trap.

[DO] VS Code: open `m12_provenance_scan.py`, module docstring on screen, **lines 1 to 30**.

[SAY] Analyze Image is generally available. It gives you four harm categories -- hate,
sexual, violence, self-harm -- each at severity zero, two, four, or six. That is all it
does. It has no idea whether an image was AI-generated and it never claims to. Content
Provenance Detection is a completely separate API, still in preview, and it reads C2PA
Content Credentials plus Microsoft's invisible watermark.

[DO] Terminal: `uv run python m12_provenance_scan.py --demo`

[PAUSE] Roughly 30 seconds. Three files, both APIs on each.

[SAY] Watch the pacing line while this runs. Provenance on this tier allows about one
request every nine seconds, so the script waits rather than earning you a four twenty-nine
in the middle of a take.

[VERIFY] Three files, and the summary shows **one** `ProvenanceDetected`.

[SAY] First file. Microsoft-signed. Provenance detected, type C2PA, provider Microsoft
Designer. That is the happy path, and notice the API told us the *provider* -- it knows
which Microsoft system made it.

[SAY] Second file, and this is the one I want you to remember. This came out of ChatGPT.
Look at the summary column: manifest, **yes**. The file carries a valid C2PA manifest. And
the provenance result says **NoProvenanceDetected**. That is not a bug. Microsoft's
provenance API detects content generated by **Microsoft** AI systems. OpenAI signed this
one, so it is out of scope.

[SAY] Third file, no manifest at all. Nothing to find.

[DO] Terminal: `uv run python m12_provenance_scan.py --local-c2pa --only provenance --demo`

[SAY] Now let's prove the second file really is AI-generated, by reading the manifest
ourselves instead of asking Azure.

[VERIFY] The Microsoft file prints `agent=Azure OpenAI ImageGen`, `issuer=Microsoft
Corporation`, and `soft-binding present`. The ChatGPT file prints `agent=GPT-4o`,
`digitalSourceType=trainedAlgorithmicMedia`, `issuer=OpenAI`.

[SAY] There it is. GPT-4o. Digital source type: trained algorithmic media. That is the
IPTC code that means "a machine made this." The file has been telling us the truth the
whole time. The cloud API said no provenance detected because it only speaks Microsoft.

[SAY] So write this one down, because it is the single most important sentence in this
lesson: **absence of provenance proves nothing.** Microsoft says so in their own docs. A
NoProvenanceDetected result does not mean the content is not AI-generated. It means
*this API* didn't find *its own* markers.

[SAY] And look at the Microsoft file one more time -- soft-binding present, invisible
watermark. Here's why that matters. The other nineteen files in this folder have no
manifest at all. Not even EXIF. Every scrap of metadata is gone, because they were
downloaded through a browser or re-saved out of an editor, and that strips the metadata
container wholesale. C2PA metadata is fragile. The invisible watermark is the part that
rides in the pixels and survives the re-encode. That's the whole reason it exists.

[PAUSE] Let that land. This is the responsible-AI beat of the lesson.

[IF IT BREAKS] A 403 on upload means RBAC hasn't propagated -- wait five minutes. A 404 on
the provenance route means the preview isn't available in your region; fall back to
`--local-c2pa`, which needs no cloud at all and still tells the same story.

---

## Segment 2: The endpoint that isn't the one you've been using (~3 min)

[SAY] Welcome back. Tim Warner here. For the last couple of lessons we've been building
agents, and everything we did pointed at a Foundry project endpoint. In this lesson we're
gonna generate images and we're gonna generate video, and I want to start with the thing
that cost me the most time when I built this demo, because it's gonna cost you time too if
nobody tells you.

[DO] VS Code: open `.env.example`, scroll to the comment block at **lines 11 through 33**,
with the endpoint matrix table at **lines 25 through 29** on screen.

[SAY] Here's the deal. Agents are project-scoped, so agents live under slash api slash
projects slash your project name. Image models and video models are not. They're deployed
on the **account**, and they are not projected underneath that path. So if you take the
endpoint that worked beautifully in lesson ten and lesson eleven and you point image
generation at it, you get a four oh four. And here's the cruel part, look at the table:
that four oh four comes back with no error body at all. The message is literally "Error
code: 404." Your token's fine, your deployment exists, your SDK call is correct, and the
path is just wrong.

[SAY] So I tested all three candidates against this live account, and both account
hostnames work for both images and video. We use the dot openai dot azure dot com form in
this lesson, and the only reason is that's the form Microsoft Learn shows in the image and
video docs, so your code matches the published docs.

[DO] VS Code: open `m12_image_gen.py` and scroll to `build_client()` at **lines 90 to 130**.

[SAY] And here's the client. Four things in here are non-negotiable and every one of them
is exam-relevant. Number one, line one twenty-three, Azure CLI Credential, not Default
Azure Credential, because Default probes environment variables first and a leftover
AZURE_CLIENT_ID from some other project will silently hijack your identity. Number two,
the token audience is ai dot azure dot com, not cognitiveservices dot azure dot com, even
though under the covers this is a Cognitive Services account. And number three, look at
line one twenty-five, that is a plain OpenAI client. Not AzureOpenAI. AzureOpenAI always
appends an api dash version query parameter and the slash v1 path rejects it, because the
v1 surface is versionless by design -- the version moved into the URL.

[SAY] And number four, and this is the one people get wrong in production, so watch line
one twenty-seven. That `api_key` is not a token. It's a **function**. Get bearer token
provider hands you a callable, and the SDK calls it before every single request, so your
token is always fresh. Now compare that to the obvious version of this code, where you call
dot token, get a string, and pass the string. That works. It works all the way through your
image demo. And then you point it at Sora, where you sit in a polling loop for several
minutes, and your token quietly expires halfway through a render you've already paid for,
and you eat a four-oh-one. I checked this machine while I was writing the lesson -- the
token the Azure CLI handed me had about thirty minutes of life left, not an hour. So this
is not theoretical. Microsoft's own v1 guidance says pass the provider *instead of* a
static key, and that's exactly why the v1 OpenAI client no longer needs the AzureOpenAI
client just to refresh tokens for you.

[PAUSE] Clean seam before the first render.

---

## Segment 3: Beat 2 -- text to image (LO1) (~5 min)

[DO] VS Code: `m12_image_gen.py`, scroll to `DEFAULT_PROMPT` at **lines 81 to 88**.

[SAY] Before we run it, look at the prompt. A brass ship's compass on a nautical chart.
No people, no faces, no brands, no named characters. That's not me being squeamish, that's
me being practical, because the second half of this lesson runs on Sora and Sora's content
filter rejects reference images containing a human face outright. Pick subjects that
survive both filters and you can re-shoot a take as many times as you need.

[DO] Terminal: `uv run python m12_image_gen.py --dry-run`

[SAY] Dry run first. That validates every argument and prints exactly what would go on the
wire, and it makes zero Azure calls. That's my favorite way to open a demo.

[VERIFY] Prints the header block and ends with `[dry-run] Arguments valid. No Azure call made.`
The endpoint line reads
`endpoint : https://aif-ai103-l11-gcn5uizgywfac.openai.azure.com/openai/v1`.

[DO] Terminal: `uv run python m12_image_gen.py`

[PAUSE] This takes about **two minutes and thirteen seconds** at `--quality high`. Cut and
resume on the `[saved]` line, or narrate the wait using the quality/cost point below.

[VERIFY] Verbatim from the 2026-08-11 smoke run:

```text
========================================================================
AI-103 L12 Beat 1 -- text to image (LO1)
========================================================================
  endpoint : https://aif-ai103-l11-gcn5uizgywfac.openai.azure.com/openai/v1
  model    : gpt-image-2
  size     : 1024x1024   quality: high   n: 1
  output   : C:\github\ai103\lessons\12-image-video-generation\out\l12-image-01.png
  prompt   : A vintage brass ship's compass resting on a weathered paper nautical chart, warm morning light raking in from the left, shallow depth of field, top-down product photograph on a dark walnut table. No people, no text, no logos.

  [saved] l12-image-01.png  1,873,450 bytes

  [time]  132.6s for 1 image(s)
  [usage] Usage(input_tokens=55, input_tokens_details=UsageInputTokensDetails(image_tokens=0, text_tokens=55), output_tokens=7024, total_tokens=7079, output_tokens_details=UsageOutputTokensDetails(image_tokens=7024, text_tokens=0))

Done. Open C:\github\ai103\lessons\12-image-video-generation\out\l12-image-01.png to review, then feed it to m12_image_edit.py.
```

Byte count will differ on your run; the shape of every line will not.

[DO] Open `out/l12-image-01.png` in Windows Photos.

[SAY] There's our compass. Now I want you to look at that usage line, because this is the
part people skip. **An image is priced in tokens.** Fifty-five input tokens, that's my
prompt. Seven thousand and twenty-four output tokens, that's the picture. And here's the
control worth knowing for the exam: I ran the identical prompt at quality medium and it
came back in fifty-two seconds with one thousand seven hundred fifty-six output tokens.
Same prompt, same size, one parameter changed, and you get a four-x cost difference and a
two-and-a-half-x time difference. That's what "select and apply the appropriate generation
controls" actually means in practice.

[DO] VS Code: `m12_image_gen.py`, **lines 245 to 253**, the decode loop.

[SAY] One more thing and then we move on. Look at line two forty-nine. Base sixty-four
decode. On this model that is not a convenience, that's the contract. The older DALL-E
surface let you ask for response format equals url and hand that link to a browser. That
option **does not exist** on gpt-image-2. Every caller gets bytes and every caller owns the
storage decision. Which honestly is a better default -- no expiring link, no accidental
public blob.

[IF IT BREAKS] A 404 here means your `.env` has a project endpoint in it. The error handler
at **lines 230 to 234** prints the URL it actually used, so read that line out loud and fix
the `.env`.

[PAUSE] Hold two beats on the finished image.

---

## Segment 4: Beat 3 -- mask-based editing (LO3) (~6 min)

[SAY] So we can make an image. Now let's change one. And this is the beat where I need you
to unlearn something, because everybody gets it backwards the first time, myself included.

[DO] VS Code: `m12_image_edit.py`, scroll to `build_mask()` at **lines 132 to 163**, with
**line 147** and **lines 156 to 157** visible together.

[SAY] In a mask, **transparent means editable**. Alpha zero is the region the model is
allowed to repaint. Alpha two fifty-five is protected and comes back untouched. Now that
reads backwards, right? Because in normal English, when you mask something off, you're
protecting it -- you put tape on the trim before you paint the wall. Here it's the
opposite. The transparent part is the hole you cut so the model can reach through.

[SAY] Look at line one forty-seven. We start with alpha two fifty-five everywhere. That means
protect the entire image. Then line one fifty-six, line one fifty-seven, we punch a hole.
And notice the color in that tuple is zero zero zero -- black -- but the color is
completely irrelevant. It could be magenta. The service reads the **alpha channel** and
nothing else. Which, by the way, is exactly why your mask has to be a PNG. JPEG cannot
carry an alpha channel at all, so a JPEG mask is a mask with no hole in it.

[DO] Terminal: `uv run python m12_image_edit.py --dry-run`

[SAY] And the dry run here does something genuinely useful. It builds the real mask and
writes it to disk, and it still makes zero Azure calls. So you can look at the thing before
you spend a request on it.

[VERIFY] Prints the mask line and the alpha split, then
`[dry-run] Mask written to ...\out\l12-image-02-mask.png. No Azure call made.`

[DO] Open `out/l12-image-02-mask.png` in Windows Photos.

[SAY] There it is. That checkerboard square in the upper right, that's the hole. Everything
solid is protected.

[DO] Terminal: `uv run python m12_image_edit.py`

[PAUSE] About thirty seconds. Let it run.

[VERIFY] Verbatim from the 2026-08-11 smoke run:

```text
========================================================================
AI-103 L12 Beat 2 -- mask-based edit / inpainting (LO3)
========================================================================
  endpoint : https://aif-ai103-l11-gcn5uizgywfac.openai.azure.com/openai/v1  (POST /images/edits, multipart/form-data)
  model    : gpt-image-2
  source   : l12-image-01.png  1024x1024  1,873,450 bytes
  quality  : high
  mask     : l12-image-02-mask.png  1024x1024  6,506 bytes
             alpha=0   (EDITABLE)  176,400 px   16.8%
             alpha=255 (protected) 872,176 px   83.2%
  region   : x0,y0,x1,y1 = (0.55, 0.06, 0.96, 0.47)
  output   : C:\github\ai103\lessons\12-image-video-generation\out\l12-image-02-edited.png
  prompt   : In the cleared upper-right area, add a small polished brass sextant lying flat on the same weathered nautical chart, lit by the same warm morning light from the left and casting a soft shadow to the right. Match the existing grain, focus, and colour. No people, no text, no logos.

  [saved] l12-image-02-edited.png  1,812,108 bytes
  [time]  29.1s
  [usage] Usage(input_tokens=1093, input_tokens_details=UsageInputTokensDetails(image_tokens=1024, text_tokens=69), output_tokens=439, total_tokens=1532, output_tokens_details=UsageOutputTokensDetails(image_tokens=439, text_tokens=0))
```

The two numbers to point at are `alpha=0 (EDITABLE) 176,400 px 16.8%` and
`alpha=255 (protected) 872,176 px 83.2%` -- those come straight from the region geometry
and they're deterministic, so they will match exactly on your run.

[DO] Open `out/l12-image-02-edited.png` next to the original.

[SAY] And there's the sextant, sitting in the upper right on the same chart, with the light
coming from the same direction and a shadow falling the right way. Eighty-three percent of
that frame was protected and came back as the same photograph. Sixteen point eight percent
was transparent and got repainted. That is inpainting.

[SAY] Now one honest caveat, and say this on camera because a sharp learner will spot it.
The response is a **full re-render**, not a patched copy of your input file. The protected
region comes back visually equivalent, not byte-identical. If your workflow needs the
untouched pixels to be literally untouched, you composite the result back over the original
yourself using that same mask.

[DO] VS Code: `m12_image_edit.py`, **lines 294 to 303**, the `images.edit` call.

[SAY] Two mechanical details before we leave images. First, look at line two ninety-four --
we open both files in binary and hand them over. This endpoint is **multipart form-data**,
not JSON. There is no base sixty-four on the way in, only on the way out. That matters the
second you drop to curl. And second, the mask has to be **exactly** the same pixel
dimensions as the source. A ten twenty-four by ten twenty-four source with a ten
twenty-three by ten twenty-four mask is a four hundred, and the message you get back is not
especially helpful, so we assert it locally at line two seventy-five instead.

[IF IT BREAKS] If Beat 3 says the source image was not found, Beat 2 didn't run or you
deleted `out/`. Re-run Beat 2, or point at any PNG with `--source`.

[PAUSE] Clean seam before video.

---

## Segment 5: Beat 4 -- text to video, the async job (LO2) (~6 min)

[SAY] Alright. Images are done. Now video, and the reason this gets its own beat isn't the
prompt, it's the **shape of the API**. Because this is where the programming model changes
out from under you.

[DO] VS Code: `m12_video_gen.py`, **lines 218 to 223** (the `videos.create` call) and then
scroll to the polling loop at **lines 236 to 260**.

[SAY] Image generation is one synchronous call. You wait a few seconds and you get bytes
back. Video generation is a **job**. You create it, you get an id and a status back
immediately, and then you poll. Same client, same auth, same base URL -- look, it's the
identical `build_client` from the image demos. Only the resource changes, `client dot
videos` instead of `client dot images`. But if you write video code as though it were
image code, you will build something that blocks an HTTP request for two minutes and dies
behind a load balancer.

[SAY] And notice line two thirty-seven and the `TERMINAL_STATUSES` tuple up at line seventy.
The statuses on this surface are queued, in progress, completed, and failed. I also guard
cancelled, and I want to be explicit about why: an unhandled terminal status is an infinite
loop, and an infinite loop on camera is a bad day.

[DO] Terminal: `uv run python m12_video_gen.py`

[PAUSE] **This is the on-camera moment.** Do not cut. About sixty-five seconds, three
polls. Let the progress bar fill in real time.

[VERIFY] Verbatim from the 2026-08-11 smoke run:

```text
========================================================================
AI-103 L12 Beat 3 -- text to video, the async job (LO2)
========================================================================
  endpoint : https://aif-ai103-l11-gcn5uizgywfac.openai.azure.com/openai/v1
  model    : sora-2
  length   : 4s   size: 1280x720
  output   : C:\github\ai103\lessons\12-image-video-generation\out\l12-video-01.mp4
  prompt   : A stylized 3D-animated paper sailboat drifting across a calm turquoise lagoon at sunrise. Gentle ripples spread behind it, the camera pushes in slowly and steadily. Soft golden light, pastel colour palette. No people, no text, no logos.

  [job]   created  id=video_6a7b42d00b88819080ea65857bb47460
  [job]   status=queued

  Polling. This is the whole difference between image and video generation:
  images return bytes, video returns a job you have to come back for.

  [poll]  +00:22  in_progress  [###########.............]  46%
  [poll]  +00:43  in_progress  [########################]  99%
  [poll]  +01:04  completed    [########################] 100%

  [job]   completed in 64s  (1.1 min, 3 polls)
  [saved] l12-video-01.mp4  2,136,793 bytes
  [saved] l12-video-01-thumb.jpg  18,798 bytes
  [note]  video id written to last_video_id.txt for m12_video_remix.py

Remember: the server-side render expires at 2026-08-12 15:43:29 local (24.0h from now).
The MP4 on disk is yours; the id video_6a7b42d00b88819080ea65857bb47460 is not going to be there tomorrow.
```

Note on that last block: everything above the `Remember:` line is the verbatim 2026-08-11
capture. The expiry line itself was changed in the 2026-08-11 audit pass -- the script now
reads `expires_at` off the job and prints the real timestamp instead of asserting "24
hours", so your run shows a real date and a real countdown. The video demos were **not**
re-run during that pass (a live Sora job is expensive and the auth path was already proven
by the image run), so treat the timestamp shown here as the shape, not a captured value.

The id changes every run. What will not change is the sequence
`queued` -> `in_progress` -> `completed`, three polls at a 20-second interval, and a
completion time in the low sixties for a 4-second 1280x720 clip.

[DO] Play `out/l12-video-01.mp4`.

[SAY] Four seconds, twelve eighty by seven twenty, thirty frames a second, and it ships
with an audio track. That's a real render, not a slideshow.

[SAY] Three constraints on Sora that will shape what you can actually build. Number one,
**two concurrent jobs** per account -- a third create call gets rejected while two are
still running, so if you're fanning out renders you need a queue in front of it. Number
two, **renders expire after twenty-four hours**, so download in the same session; do not
architect something that goes back for yesterday's video id. And number three, the content
filter blocks photorealistic people and recognizable IP, and it rejects any reference image
containing a human face. Objects, landscapes, stylized animation -- that's the safe lane.

[IF IT BREAKS] `AttributeError: 'OpenAI' object has no attribute 'videos'` means your
`openai` package is too old. `uv add "openai>=2.44.0"` and re-run.

[PAUSE] Hold on the completed poll line for the zoom edit.

---

## Segment 6: Beat 5 -- remix, or how you "edit" a generated video (LO4) (~4 min)

[SAY] So the question I always get at this point is: okay, I've got a generated video, how
do I **edit** it? And the answer is not what people expect. You don't open it in a
timeline. You **remix** it.

[DO] VS Code: `m12_video_remix.py`, **line 216** (`client.videos.remix`), then the provenance
print at **lines 223 to 229**.

[SAY] Remix takes a completed video id plus a new prompt, and it renders a **new** video
that inherits the source's composition, its motion, and its style, and then applies your
change on top. And notice at line one sixty-one, we pass the source video id. The result
is a new job with a new id -- the original is not mutated. Both videos exist.

[DO] VS Code: `m12_video_remix.py`, `DEFAULT_PROMPT` at **lines 68 to 73**.

[SAY] And look at what I'm asking for. I'm changing the **time of day** and adding mist.
I am deliberately not changing the subject, and here's why: remix is strongest when it
preserves composition and motion. If you ask it for a completely different subject, you're
not really remixing, you're generating a second video with extra steps.

[DO] Terminal: `uv run python m12_video_remix.py`

[PAUSE] Another ~seventy seconds, three polls. Same loop as Beat 4, and saying "same loop"
out loud is half the value here.

[VERIFY] Verbatim from the 2026-08-11 smoke run:

```text
========================================================================
AI-103 L12 Beat 4 -- remix: editing a generated video (LO4)
========================================================================
  endpoint : https://aif-ai103-l11-gcn5uizgywfac.openai.azure.com/openai/v1
  source   : video_6a7b42d00b88819080ea65857bb47460   (read from last_video_id.txt)
  output   : C:\github\ai103\lessons\12-image-video-generation\out\l12-video-02-remix.mp4
  prompt   : Keep the same paper sailboat, the same lagoon, and the same slow push-in, but change the time of day to late golden afternoon and add a low drifting mist across the water. Warmer amber light, longer shadows. No people, no text, no logos.

  [src]   status=completed  model=sora-2
  [job]   created  id=video_6a7b43203bcc8190b806cc5943708f93
  [job]   status=queued
  [job]   remixed_from_video_id=video_6a7b42d00b88819080ea65857bb47460

  [poll]  +00:25  in_progress  [#################.......]  72%
  [poll]  +00:46  in_progress  [########################]  99%
  [poll]  +01:07  completed    [########################] 100%

  [job]   completed in 67s  (1.1 min, 3 polls)
  [saved] l12-video-02-remix.mp4  2,076,866 bytes

  lineage:
    video_6a7b42d00b88819080ea65857bb47460   (original)
      -> video_6a7b43203bcc8190b806cc5943708f93   (remix, remixed_from_video_id=video_6a7b42d00b88819080ea65857bb47460)
```

The line to point the cursor at is `[job]   remixed_from_video_id=...`, and it must equal
the `source :` id printed at the top of the same run.

[DO] Play `out/l12-video-01.mp4` and `out/l12-video-02-remix.mp4` back to back.

[SAY] Same paper boat. Same lagoon. Same hills on the horizon. Same slow push-in. Different
hour of the day, and now there's mist sitting on the water. **That inheritance is what
separates a remix from a second generation.**

[SAY] And now look back at that `remixed_from_video_id` field, because that's the piece
that turns this from a party trick into a workflow. Every derivative points back at its
parent. Six weeks from now when somebody in legal asks you where a clip came from, that
field is your answer. Provenance is exactly what an editing workflow needs and exactly what
nobody thinks about until they need it.

[SAY] One gotcha the script handles for you at **lines 196 to 211**: before it remixes, it
retrieves the source and checks it's still completed. That's an extra API call every time,
and it earns its keep, because renders expire after twenty-four hours. Without that check
"remix failed" is a mystery. With it, you get told the real reason.

[PAUSE] Hold on the lineage block.

---

## Segment 7: Recap and close (~2 min)

[SAY] Let me give you the one two three four five on this lesson. Number one, Azure will
tell you two different things about an image, and they are not the same thing. Analyze
Image gives you harm categories. Content Provenance Detection tells you whether a
**Microsoft** system made it -- and absence of provenance proves nothing. Number two,
images and video live on the **account** endpoint, not the project endpoint, and the
punishment for getting that wrong is a four oh four with no error body. Number three,
image generation is synchronous and returns base sixty-four -- there is no URL option --
and it's billed in tokens, so quality is a cost dial, not just a look dial. Number four,
in a mask **transparent means editable**, alpha zero is the hole you cut for the model,
and the mask has to be a PNG at exactly the source dimensions. And number five, video is
a **job**: create, poll, download, and you edit it by remixing it, which gives you a new
id plus a `remixed_from_video_id` pointing home.

[SAY] Two things I really want you to carry out of this lesson. The mask one, because it
costs people an afternoon: transparent means editable. Say it out loud once and you'll
never invert it again. And the provenance one, because it costs people their credibility:
when that API comes back "no provenance detected," that is not a verdict that the image
is real. We watched it say exactly that about a file that had "GPT-4o" written inside it.
These tools tell you when something **is** signed. They cannot tell you when something
isn't AI.

[SAY] I hope you found this lesson helpful. I'll see you next time.

---

## If it breaks

| Symptom | What it actually is | Fix |
| --- | --- | --- |
| `NotFoundError: Error code: 404` with **no error body**, on `images.generate` or `videos.create` | `FOUNDRY_ACCOUNT_ENDPOINT` contains `/api/projects/<project>`. Images and video are account-scoped; the project path does not serve them. | Set `FOUNDRY_ACCOUNT_ENDPOINT=https://<account>.openai.azure.com` (no path). The scripts append `/openai/v1` themselves. |
| `AttributeError: 'OpenAI' object has no attribute 'videos'` | `openai` package predates the videos API. | `uv add "openai>=2.44.0"`, then `uv sync`. Verified working on 2.53.0. |
| 401 / `InvalidAuthenticationToken` | Token minted for the wrong audience, or `az login` expired. | Scope must be `https://ai.azure.com/.default`, **not** `cognitiveservices.azure.com`. Re-run `az login`. |
| 400 mentioning `api-version` | Somebody swapped in `AzureOpenAI`. It always appends `api-version`, which the `/openai/v1` path rejects. | Use the plain `OpenAI` client with a bearer token, as in `build_client()`. |
| `httpx` `getaddrinfo failed` / connection error only inside VS Code's terminal | Proxy environment variables injected by the integrated terminal. | Already handled -- every script pops `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` (and lowercase) **before** the `openai` import. If you refactor, keep that pop above the import. |
| Wrong model name in the error even though `.env` looks right | A stale `IMAGE_MODEL`/`VIDEO_MODEL` exported in an earlier shell is shadowing `.env`. | Already handled -- `load_dotenv(override=True)`. If you see it anyway, open a fresh terminal. |
| 429 on an image call | `gpt-image-2` is provisioned at `count: 2 / 60 s`. In testing a burst of four concurrent low-quality requests all succeeded, so this is a floor not a wall -- but repeated takes will find it. | Wait 30-60 s and re-run, or raise `--sku-capacity`. The handler at `m12_image_gen.py` lines 227-229 says this on screen. |
| **401 partway through a video poll**, after `queued`/`in_progress` lines already printed | The Entra access token expired while the render ran. Tokens are short-lived and the Azure CLI often hands back one with well under an hour left. | Already handled -- `build_client()` passes the **callable** from `get_bearer_token_provider`, so the SDK refreshes per request, and the poll loop catches and explains the failure instead of throwing a traceback. If you see this anyway, someone replaced `api_key=token_provider` with a static token string: put the provider back. If the CLI session itself lapsed, re-run `az login`. |
| 429 on `videos.create` while another render is going | Sora allows **two concurrent jobs** per account. | Let the running jobs finish. Do not start Beat 4 and Beat 5 at the same time. |
| `source video is 'queued', not 'completed'` from Beat 5 | You started the remix before Beat 4 finished. | Wait for Beat 4's `[note] video id written to last_video_id.txt` line. |
| Beat 5: "could not retrieve source video ... renders EXPIRE AFTER 24 HOURS" | You are remixing yesterday's id. | Re-run Beat 4 to make a fresh source. Remix is a same-session workflow. |
| Beat 3: `source image not found` | Beat 2 didn't run, or `out/` was cleared between beats. | Re-run Beat 2, or pass `--source <any png>`. |
| 400 on `images.edit` about size/dimensions | Mask is not exactly the source's pixel dimensions, or it's a JPEG. | The generated mask is always correct. If you hand-roll one, it must be PNG at identical dimensions and under 4 MB. |
| Content filter rejection on either model | Prompt drifted toward people, faces, brands, or named characters. Sora is stricter than gpt-image-2 and rejects reference images containing a human face outright. | Move the subject to objects, landscapes, or stylized animation. |
| The edited image's "protected" region looks subtly different | Expected. `images.edit` returns a **full re-render**, not a patched copy. | If you need byte-identical untouched pixels, composite the result over the original using the same mask. |
| **Beat 1:** 403 on blob upload | RBAC has not propagated yet, or you lack **Storage Blob Data Contributor**. Note this is a *different* role than the one the service needs. | Wait 5 minutes after any role assignment. Watch out: `az storage blob upload` reports **success** while silently failing during this window. |
| **Beat 1:** `Access denied to input blob` from `provenance:detect` | The **account's managed identity** lacks **Storage Blob Data Reader** on the storage account. The service fetches the blob as itself, not as you. | Assign it (see the pre-flight rebuild block), then wait 5 minutes. |
| **Beat 1:** 429 on provenance | The preview API allows roughly **one request per 9 s** on this AIServices S0 tier. | Already handled -- the script paces itself at 10 s. If you loosen `PROVENANCE_MIN_INTERVAL`, this comes back. |
| **Beat 1:** 404 on the provenance route | The preview is not available in that region, or the endpoint is wrong. | Fall back to `--local-c2pa`, which reads manifests offline and still tells the whole story. Confirm the endpoint is the `.cognitiveservices.azure.com` host, not `.openai.azure.com`. |
| **Beat 1:** `The provided URL is not a valid Azure Blob Storage endpoint` | The provenance API accepts real Azure Storage URLs only -- no local paths, no third-party hosts, no inline bytes. | Check `STORAGE_ACCOUNT_NAME` in `.env`. |
| **Beat 1:** every file reports `manifest: no` | Something re-saved the `img/` fixtures and stripped their C2PA manifests. | `git checkout -- img/`. Then never open those two files in an editor. |
| **Beat 1:** the ChatGPT file shows `NoProvenanceDetected` | **This is correct and it is the point of the beat.** The API detects Microsoft-generated content only. | Nothing to fix. Say it on camera. |

---

## Runtime estimate

| Segment | On camera | Machine time (measured 2026-08-11) |
| --- | --- | --- |
| 1. Beat 1 -- harm scan + provenance | ~6 min | **30 s** (`--demo`, 3 fixtures; ~7 min for all 22) |
| 2. The endpoint that isn't the one you've been using | ~3 min | 0 |
| 3. Beat 2 -- text to image | ~5 min | **132.6 s** at `--quality high` (52.6 s at `medium`) |
| 4. Beat 3 -- mask-based editing | ~6 min | **29.1 s** |
| 5. Beat 4 -- text to video | ~6 min | **64 s** (3 polls at 20 s) |
| 6. Beat 5 -- remix | ~4 min | **67 s** (3 polls at 20 s) |
| 7. Recap and close | ~2 min | 0 |
| **Total** | **~32 min raw, 26-30 min cut** | **~5.4 min of service time** |

---

## Notes for the editor

- **No Azure resources are created by any of these scripts.** They call model deployments
  that already exist, so every beat is safe to re-run as many times as a take requires.
  Beat 1 uploads a blob per file and deletes it on the way out; verified twice-green with
  zero blobs left behind.
- **Beat 1's summary table is the shot.** Hold on it. Two rows read `manifest: yes` and
  only one reads `ProvenanceDetected` -- the contradiction is visible without narration,
  and that single frame carries the whole responsible-AI point of the lesson.
- **Do not re-save anything in `img/`.** Unlike `out/`, that folder is **committed**, and
  two of its files carry C2PA manifests that make Beat 1 work. Any editor save, format
  conversion, or browser re-download strips the manifest and silently turns the positive
  case into another negative. Rename by moving the file, never by re-saving it.
- Beat 1's `[pace] waiting Ns` lines are real rate limiting, not padding. Leave them in;
  they are a legitimate teaching detail about preview-API quotas.
- **Beat 2 at `--quality high` is a two-minute stare.** Either cut it, or shoot at
  `--quality medium` (52.6 s) and quote the high-quality numbers instead. The
  quality/cost contrast is a stronger teaching point than watching a progress-free wait.
- **The polling output in Beats 3 and 4 is the on-camera moment.** Do not cut inside it.
  The `queued -> in_progress -> completed` transition is the entire concept of the segment.
- The `out/` folder is gitignored. Clear it before recording so no beat can silently
  succeed on a previous take's artifacts.
- Beat 4 writes `out/last_video_id.txt` and Beat 5 reads it, so the two beats chain without
  anyone copy-pasting a video id on camera. If you record them out of order, pass
  `--video-id` explicitly.
- The mask pixel counts in Beat 3 (`176,400` editable / `872,176` protected) are computed
  from the region geometry, so they are deterministic and will match take to take. The
  image byte counts and video ids will not.
