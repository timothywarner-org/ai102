# Design and implement multimodal understanding workflows

Part of **Objective domain 3: Implement computer vision solutions** (10-15%), Lesson 13 (L13).

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Build a solution that analyzes visual context by using multimodal models
2. Configure apps to produce concise or detailed captions for single or multiple images
3. Implement a solution that enables question-answering grounded in visual evidence
4. Configure generation of alt-text and extended image descriptions aligned to accessibility guidelines
5. Implement visual understanding by configuring Azure Content Understanding in Foundry Tools to extract visual characteristics
6. Implement video analysis workflows to process and interpret video segments
7. Configure single-task and pro-mode Content Understanding pipelines
8. Implement solutions that identify objects, components, or regions within images or video

## The idea

Two different answers to "understand this image," and the lesson is really about
knowing which one you reach for.

**Your chat model already sees.** Vision is not a separate service you bolt on; it
is a content part in the same `/chat/completions` call you already make. That covers
captions, grounded question-answering, and alt-text with no new resource.

**Content Understanding is the other answer.** When you want the *same fields* out of
every image, you stop prompting and define an **analyzer**: a schema the service fills
in, consistently, at scale. That is a different tool for a different job, and the
exam expects you to tell them apart.

Then video, where the transcript-versus-segments distinction from L16 shows up again
in visual form.

## Setup

```bash
az login
cd lessons/13-multimodal-understanding
uv sync
cp .env.example .env        # then fill in every value
```

`.env.example` is the authority on which variables are required. Everything is
**keyless** via `AzureCliCredential`, never `DefaultAzureCredential`.

### Two endpoints, and they are not the same host

This trips people up, and Beat 3 is built on the distinction:

```
FOUNDRY_ACCOUNT_ENDPOINT=https://<account>.openai.azure.com
CONTENTUNDERSTANDING_ENDPOINT=https://<account>.services.ai.azure.com/
```

Same Foundry account, two different data planes. Point a Content Understanding call at
the `openai.azure.com` host and it fails in a way that reads like an auth problem.

### Content Understanding needs its defaults set once

Once per resource, and a rebuilt resource group needs it again:

```
PATCH {CONTENTUNDERSTANDING_ENDPOINT}contentunderstanding/defaults?api-version=2025-11-01
Content-Type: application/merge-patch+json

{"modelDeployments":{"gpt-5-mini":"gpt-5-mini"}}
```

Skip it and **every analyzer create fails with `DefaultsNotSet`**.

One more sharp edge: a custom `analyzerId` **must not contain hyphens**. The service
rejects them, which is why `CU_IMAGE_ANALYZER_ID` is `ai103L13ImageV1` and not
`ai103-l13-image-v1`.

## Demos

Beat 1 runs in Content Understanding Studio with no code. Beat 5 runs in Video Indexer.
Every script takes `--dry-run`, which prints the plan and calls nothing.

```bash
uv run python m13_vision_chat.py            # vision in the chat model: caption, Q&A, alt-text

uv run python m13_cu_analyzer.py --dry-run  # the plan, no calls
uv run python m13_cu_analyzer.py            # create the analyzer, then analyze an image
uv run python m13_cu_analyzer.py --describe # show the analyzer definition the service stored
uv run python m13_cu_analyzer.py --delete   # remove it when you are done

uv run python m13_cu_video.py               # segment a video and read the markdown it emits
uv run python m13_agentic_mode.py --show    # what pro mode became
```

`m13_cu_analyzer.py` also takes `--image` / `--image-url` to point at your own file, and
`--skip-create` to reuse the analyzer you already made. `m13_cu_video.py` takes
`--video` / `--video-url`, `--analyzer`, and `--save-markdown`.

## Status

**Verified live.** All beats ran green against `YOUR-FOUNDRY-RESOURCE` in `eastus2`
on **2026-08-12**. Every terminal result quoted in the demo runbook is a real string from
that run, not a reconstruction.

Content Understanding is at **GA `2025-11-01`**. Two API details worth knowing, because
both fail quietly rather than loudly: the request body takes an **`inputs` array** whose
entries carry `url` or `data` (there is no `base64Source` field), and there are exactly
**four legal `baseAnalyzerId` values**.

## Files

| File | Beat | What it owns |
| --- | --- | --- |
| *(Content Understanding Studio)* | 1 | Where analyzers actually get built, by hand |
| `m13_vision_chat.py` | 2 | Caption, grounded Q&A, and alt-text from the chat model |
| `m13_cu_analyzer.py` | 3 | The same analyzer from code: create, analyze, describe, delete |
| `m13_cu_video.py` | 4 | Video segmentation and the markdown it produces |
| *(Video Indexer portal)* | 5 | The other video answer, and when to prefer it |
| `m13_agentic_mode.py` | 6 | What happened to pro mode |

Pre-index your clip in Video Indexer **before** you record Beat 5. Indexing takes real
minutes, and there is nothing to look at while it runs.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
