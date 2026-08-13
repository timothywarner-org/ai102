# L16 CHEATSHEET -- One WebSocket vs Three Services

`lessons/16-speech-solutions/` | **3 beats, 4 commands** | ~12 min

**Verified green 2026-08-13** against `aif-ai103-l11-gcn5uizgywfac`. Every `CHECK` is a real observed string. Beat 1 is portal-only.

**No microphone anywhere.** Caller audio is a WAV; replies land in `out/`. Retake = replay.

**Legend:** `SHOW` on screen | `SAY` riff it | `CHECK` proof | `FIX` if it blows up

---

## PRE-FLIGHT (off camera)

```powershell
az login
uv sync
uv run python assets/make_assets.py
uv run python m16_voice_live.py --dry-run
```

- [ ] Two WAVs in `assets/` (caller-en, caller-es)
- [ ] Dry-run prints the wss endpoint and `caller-en.wav  ok`
- [ ] **Run both live commands once** so the first take isn't the first call
- [ ] Windows: Edge on Foundry portal | VS Code on the lesson folder | `out/` visible in Explorer

---

## 1 · Beat 1 -- Talk to it in the portal (3 min)

Foundry portal -> **Speech playground** -> **Voice live** -> pick a scenario and voice -> **Start**

`DO` have an actual conversation. Interrupt it mid-sentence.

`CHECK` it stops talking when you cut in and picks up your new thread

### Talk track

- **Interrupt it on purpose.** That's the whole demo. It stops, listens, and recovers, and none of that is code you wrote.
- **Proactive engagement toggle** makes the agent speak first. Worth flipping so they see it's a configuration decision, not a coding one.
- **Nothing was deployed to get here.** No audio model, no endpoint. Say that out loud, because the next beat is about what you'd have built instead.

`FIX` playground won't load -> you need **Cognitive Services User** on the account plus a project. Owner is control plane, doesn't count.

---

## 2 · Beat 2 -- The same call, two architectures (6 min)

`SHOW` `assets/make_assets.py` briefly -- the caller audio is **synthesized from a script**, not recorded, so it's reviewable and identical on every machine.

```powershell
uv run python m16_voice_live.py --pipeline
```

`CHECK` `hops 3` and `round trip` in the **17-23s** range
`CHECK` the split, e.g. `stt 5.5s + model 9.4s + tts 2.0s`
`CHECK` `HEARD Hi, this is Marcus Webb, order number 4471...`

> **The model leg is the variable one** (observed 9-15s across runs); stt and tts are steady at ~5.5s and ~2s. Read whatever is on screen. The ratio against Voice Live stays 3x or better either way, which is the only number the beat depends on.

```powershell
uv run python m16_voice_live.py
```

`CHECK` `hops 1` and `round trip` in the **5-7s** range
`CHECK` `REPLY Hi Marcus, I can hear you're frustrated...`

`SHOW` both WAVs in `out/` -- play them back to back

### Talk track

- **Read the split out loud.** Three hops, and each one is a service you're operating, monitoring, and paying for separately.
- **Now the part that matters.** Compare the two replies. The pipeline says "you sound frustrated" because gpt-5-mini inferred it from *words on a page*. Voice Live says "I can hear you're frustrated" because it got the audio. Same customer, same complaint, and one of those models actually heard him.
- **The transcript is nearly identical.** That's the trap. If you only ever look at transcripts, these two architectures look equivalent, and they are not.
- **3.4x on latency**, and this is a file. On a live call that gap is the difference between a conversation and an interrogation.

`SHOW` the comment block at the audio-buffer loop in `m16_voice_live.py`

- **Do not commit the buffer.** Server VAD is on by default and ends the turn for you. Commit on top of it and you open a second empty turn that cancels the reply you wanted -- you get an empty response and a suspiciously fast round trip. I hit this exact bug building the demo.

`FIX` 401 -> you're pointed at `services.ai.azure.com`. Speech wants `*.cognitiveservices.azure.com`. Reads like a missing role, isn't.

---

## 3 · Beat 3 -- Same code, different language (3 min)

```powershell
uv run python m16_voice_live.py --audio assets/caller-es.wav
```

`CHECK` `HEARD Hola, soy Marcus Webb. pedido 4471...`
`CHECK` `REPLY Parece que estás un poco frustrado, Marcos...`

### Talk track

- **I changed one argument.** No translation call, no language parameter, no second pipeline. It detected Spanish and answered in Spanish.
- **That's the LO4 answer for a live conversation.** When the requirement is a phone call, this is it.
- **When it is NOT the answer:** pre-recorded media. That's video translation, a separate feature that dubs and subtitles in one pass and can keep the original speaker's voice. Different tool, different job.
- **And name the cost model**, because it's an easy exam mark: real-time speech translation covers two target languages, and every language past the second bills as additional text translation.

---

## 4 · Close (30 s)

1. **Voice Live is the default now.** Hand-orchestration is the exception you justify.
2. **Audio carries what text drops.** Reason from the audio when how they said it is the thing you need.
3. **Customization is a ladder.** Phrase list, custom language model, custom acoustic model, custom voice. Climb only as far as your accuracy problem requires.

"I hope you found this lesson helpful. I'll see you next time."

---

## PANIC TABLE

| Symptom | Real cause | Fix |
| --- | --- | --- |
| `401` on Speech | pointed at `services.ai.azure.com` | use `*.cognitiveservices.azure.com` (`SPEECH_ENDPOINT`) |
| Voice Live returns empty, ~1.6s | buffer committed on top of server VAD | don't call `commit()` / `response.create()` |
| Playground won't load | no project, or missing data-plane role | **Cognitive Services User** + a Foundry project |
| `ModuleNotFoundError: audioop` | Python 3.13+ removed it | already hand-rolled here; don't reintroduce it |
| WAV missing | fixtures not generated | `uv run python assets/make_assets.py` |
| Reply wording differs between takes | models aren't deterministic | expected; the latency contrast is the point, not the wording |

## DO NOT

- Do not use a live microphone on camera. The file path is deterministic and Camtasia only has to capture the screen.
- Do not deploy an audio model "for Voice Live." It is fully managed and deploys nothing.
- Do not claim the pipeline is legacy. It's the right call when you need to inspect or correct mid-stream.
- Do not activate or deactivate a venv on camera. `uv run` handles it.

## FILE MAP

| File | Beat | Owns |
| --- | --- | --- |
| *(portal)* | 1 | Voice Live playground, interruption, proactive engagement |
| `m16_voice_live.py` | 2, 3 | Voice Live vs pipeline; language handling |
| `assets/make_assets.py` | pre-flight | synthesizes caller fixtures, no recording needed |

## OBJECTIVE COVERAGE

| LO | Where |
| --- | --- |
| 1 speech to text and text to speech for agentic interactions | Beat 2, both paths |
| 2 speech as an agent modality, custom speech models | Beat 1 portal; customization ladder in the close |
| 3 multimodal reasoning from audio inputs | Beat 2, the tone contrast |
| 4 translate speech using language models and Foundry Tools | Beat 3 |
