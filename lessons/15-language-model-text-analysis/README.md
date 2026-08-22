# Apply language model text analysis

Part of **Objective domain 4: Implement text analysis solutions** (10-15%), Lesson 15 (L15).

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Implement solutions to extract entities, topics, summaries, and structured JSON outputs by using generative prompting and Foundry Tools
2. Configure detection of sentiment, tone, safety issues, and sensitive content
3. Build solutions that translate text by using Azure Translator in Foundry Tools or LLM-powered translation flows
4. Customize language model outputs for domain tasks, such as compliance summarization and domain extraction

## The idea

Azure gives you a **catalog** of prebuilt language skills and a **model** you can
hold to a schema. Neither one is the modern choice and the other the legacy
choice. They fail differently, they bill differently, and knowing which to reach
for is the skill this lesson teaches.

- **Catalog** when you need the same answer twice and have to defend it later.
  Fixed categories, confidence scores, a pinnable model version.
- **Schema** when the thing you need extracted is specific to your business and
  no catalog has a category for it.

Most real pipelines run both.

## Setup

```bash
az login
cd lessons/15-language-model-text-analysis
uv sync
cp .env.example .env                        # fill in all five values
uv run python assets/make_assets.py         # regenerate the three fixtures
```

**There is no virtual environment to activate.** `uv run` resolves it from any
shell, and `uv sync` is the only setup step (safe to re-run).

Everything is **keyless**. `AzureCliCredential`, never `DefaultAzureCredential`.
There is no API key anywhere in this lesson and that is deliberate.

## Demos

Beat 1 runs in the Foundry portal with no code. Beats 2 and 3 are scripts.

```bash
uv run python m15_extract.py --dry-run       # show the call shapes, no network
uv run python m15_extract.py                 # catalog vs schema, same document
uv run python m15_extract.py --loose         # strict False, watch the contract soften

uv run python m15_translate.py --dry-run
uv run python m15_translate.py --no-dictionary   # product name drifts
uv run python m15_translate.py                   # dynamic dictionary pins it
```

Results are cached by content hash, so a retake replays instantly and
byte-identically. `--no-cache` forces live calls, `--clean` starts cold.

## Status

**Demo-verified green (2026-08-12).** Validate everything in one shot:

```bash
pwsh -File validate.ps1
```

Twelve steps, cold then warm. It also rebuilds a `.venv` that was built on
another OS, which is the cause of uv's misleading "not a valid Python
environment" error.

## Why the product name is "Dispatch"

`release-note.txt` names the product **Dispatch** on purpose. Current Translator
treats CamelCase as a proper-noun signal, so invented brands like `ShipSense Pro`
pass through untranslated and the dynamic dictionary looks like it does nothing.
**Forty such candidates were probed live and not one was localized.**

A name that collides with an ordinary noun still breaks: plain Translator returns
**Le dispatch** (fr) and **Die Leitstelle** (de), and the dictionary pins it.
Don't "improve" that fixture.

## Files

| File | Purpose |
| --- | --- |
| `m15_extract.py` | `:analyze-text` vs `response_format` json_schema with `strict` |
| `m15_translate.py` | detect / translate / dynamic dictionary; characters vs tokens |
| `m15_cache.py` | content-addressed cache for repeatable takes |
| `assets/make_assets.py` | regenerates the three text fixtures deterministically |
| `offline_harness.py` | 13 request-shape assertions, no network calls |
| `validate.ps1` | one-shot cold + warm validation pass |
| `Warner.AI-103.Lesson-15-demo-runbook.md` | the recording cheatsheet |

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
