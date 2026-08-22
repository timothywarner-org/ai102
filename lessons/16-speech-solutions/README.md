# Implement speech solutions

Part of **Objective domain 4: Implement text analysis solutions** (10-15%), Lesson 16 (L16).

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Implement workflows to convert speech to text and text to speech for agentic interactions
2. Integrate speech as an agent modality, including custom speech models
3. Enable multimodal reasoning from audio inputs
4. Translate speech into other languages by using language models and Foundry Tools

## The idea

Text out as audio, audio back as text, and a decision in the middle about how
much of the loop you assemble yourself. Then the question this lesson actually
turns on: **what did the transcript throw away, and did you need it?**

**No microphone required.** Beat 2 synthesizes its own fixture with text to
speech, and every later beat reuses that WAV. Takes are byte-identical.

## Setup

```bash
az login
cd lessons/16-speech-solutions
uv sync
cp .env.example .env        # fill in every value, then: pwsh -File validate.ps1
```

`.env.example` is the authority on which variables are required. The four beats
need six of them; the rest belong to `m16_voice_live.py`, which is not part of
this demo.

Everything is **keyless**. `AzureCliCredential`, never `DefaultAzureCredential`.

### Speech auth is a different shape

Speech over Microsoft Entra does not take a plain bearer token:

```
Authorization: Bearer aad#<SPEECH_RESOURCE_ID>#<ENTRA_ACCESS_TOKEN>
```

The `aad#` prefix and the `#` separator are both required. A plain token returns
a 401 that reads like an expired credential.

### Beat 3 needs an audio deployment

Path B reasons over audio and needs a model that accepts `input_audio` on
`/chat/completions`. If `AUDIO_MODEL` is blank the script runs Path A alone and
prints the exact `az` command to deploy one. Half the beat still lands.

## Demos

Beat 1 runs in the Foundry portal with no code.

```bash
uv run python m16_speech.py --dry-run
uv run python m16_speech.py                     # synth -> transcribe -> phrase list
uv run python m16_speech.py --no-phrase-list    # leave the product name broken

uv run python m16_audio_reason.py               # transcript vs audio, same question
uv run python m16_translate_speech.py           # speech translation vs a model
```

Results are cached by content hash, so retakes replay instantly and identically.
`--no-cache` forces live calls, `--clean` starts cold.

## Status

**Verified live.** All four beats ran green against `YOUR-FOUNDRY-RESOURCE`
in `eastus2` on 2026-08-13. Every result quoted in the demo runbook is a real
string from that run, captured in `validation-output.txt`.

Re-prove it any time:

```powershell
pwsh -File validate.ps1
```

That runs everything cold, then warm, and leaves the cache primed so your first
take is a warm one.

`offline_harness.py` is a separate, weaker check: **18 pure-function assertions,
no network**. It validates SSML shape, token composition, scorecard maths, and
cache behavior. It proves nothing about Azure, and it says so when it runs. An
earlier version asserted HTTP request shapes and passed while three beats were
broken, which is why it no longer touches the transport layer. `validate.ps1` is
the only thing that proves anything.

## Files

| File | Beat | What it owns |
| --- | --- | --- |
| *(Foundry portal)* | 1 | Speech playground: STT, TTS, voice picker |
| `m16_speech.py` | 2 | TTS fixture, STT round trip, phrase list |
| `m16_audio_reason.py` | 3 | transcript vs `input_audio`, same question |
| `m16_translate_speech.py` | 4 | speech translation vs a model |
| `m16_cache.py` | all | content-addressed cache, audio-safe |
| `validate.ps1` | pre-flight | runs all four beats cold then warm; the only live proof |
| `offline_harness.py` | pre-flight | 18 pure-function assertions, no network |
| `m16_voice_live.py` | *(none)* | Voice Live spike, **not part of the four beats** |

`m16_voice_live.py` is a standalone exploration of the Voice Live speech-to-speech
API. It is deliberately outside the recorded demo, is not covered by
`validate.ps1`, and needs a microphone. Leave it closed during a take.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
