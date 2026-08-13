# Implement speech solutions

Part of **Objective domain 4: Implement text analysis solutions** (10-15%), Lesson 16 (L16).

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Implement workflows to convert speech to text and text to speech for agentic interactions
2. Integrate speech as an agent modality, including custom speech models
3. Enable multimodal reasoning from audio inputs
4. Translate speech into other languages by using language models and Foundry Tools

## The idea

You can assemble a voice agent out of three services, or you can call one that
already is one. Both work. They fail differently, they bill differently, and
one of them hears your customer while the other reads a transcription of them.

- **Pipeline** (speech to text, then a model, then text to speech) when you need
  to inspect or correct at every stage, or you have a requirement the managed
  path can't meet.
- **Voice Live** when you want a conversation. One WebSocket, no audio model to
  deploy, and the interruption and end-of-turn handling comes with it.

The demo runs the same call both ways so you can watch the difference instead of
taking my word for it.

## Setup

**No new Azure resources.** Speech and Voice Live both ride the Foundry account
this course already uses.

```bash
az login
cd lessons/16-speech-solutions
uv sync
cp .env.example .env                        # fill in the values
uv run python assets/make_assets.py         # synthesize the caller audio
```

**There is no virtual environment to activate.** `uv run` resolves it from any
shell, and `uv sync` is the only setup step (safe to re-run).

Everything is **keyless**. `AzureCliCredential`, never `DefaultAzureCredential`.

## Demos

Beat 1 runs in the Foundry Speech playground with no code. Beats 2 and 3 are scripts.

```bash
uv run python m16_voice_live.py --dry-run             # show the call shapes, no network
uv run python m16_voice_live.py                       # Voice Live, one hop
uv run python m16_voice_live.py --pipeline            # stt -> model -> tts, three hops
uv run python m16_voice_live.py --audio assets/caller-es.wav   # same code, Spanish
```

**No microphone.** The caller audio is a WAV file and the reply is written to
`out/`, so a retake is a replay rather than a performance. Everything here works
identically with a live mic; the file is a recording-safety decision.

## What you should see

Verified live 2026-08-13 against `aif-ai103-l11-gcn5uizgywfac`:

| Path | Hops | Round trip | Reply |
| --- | --- | --- | --- |
| Voice Live | 1 | **6.6s** | "Hi Marcus, I can hear you're frustrated..." |
| Pipeline | 3 | **22.5s** | "You sound really frustrated after being put on hold..." |

The transcripts are nearly identical. The latency is 3.4x apart, and only one of
those replies came from a model that actually heard the caller.

The Spanish fixture needs **no configuration change** at all: Voice Live detects
the language and answers in it, which is LO4 without a separate translation call.

## Files

| File | Purpose |
| --- | --- |
| `m16_voice_live.py` | Voice Live vs the hand-built pipeline, same call, same screen |
| `assets/make_assets.py` | synthesizes the caller fixtures with TTS (no recording needed) |
| `Warner.AI-103.Lesson-16-demo-runbook.md` | the recording cheatsheet |

## Gotchas worth knowing

- **Speech authenticates against `*.cognitiveservices.azure.com`**, not the
  `services.ai.azure.com` host the model APIs use. Mixing them up produces a 401
  that reads like a missing role assignment.
- **Do not commit the input buffer** when server voice activity detection is on
  (it is, by default). VAD ends the turn for you; committing on top opens a
  second empty turn and cancels the reply you wanted.
- **`audioop` was removed in Python 3.13.** The WAV handling here is hand-rolled
  rather than depending on a stdlib module that no longer exists.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
