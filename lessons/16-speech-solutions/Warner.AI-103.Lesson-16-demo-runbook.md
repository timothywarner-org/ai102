# L16 RECORDING CARD -- Speech, a Voice Agent, and Two Routes Out

**3 beats, 3 commands, ~15 min** | folder: `lessons/16-speech-solutions/`

> **Camtasia:** turn **System Audio** ON in the recorder (next to Microphone).
> It defaults to OFF and fails silently. Do one 5-second test before Beat 1.
>
> **Everything below is verified live.** Every `CHECK` is a real string.
> Cache is primed — both commands replay in ~1-3s.

**Voice alignment — use `Aria` everywhere.** The portal, the agent, and the
scripts all speak `en-US-AriaNeural`. Same voice start to finish.

**Model picks:** Voice Live -> **`gpt-realtime`** (managed, nothing to deploy).
Reasoning -> `gpt-5.1`. Both already configured.

---

## PRE-FLIGHT

- [ ] `az login` -> `tim@techtrainertim.com`
- [ ] `pwsh -File validate.ps1` -> green, cache primed
- [ ] Camtasia **System Audio ON**, levels tested
- [ ] Edge on Foundry portal (`proj-agents`) | VS Code on the lesson folder

---

## 1 · Portal — hear it before you code it (5 min)

### 1a. Speech playground (2 min)

`SHOW` Foundry portal -> **Speech playground**

`DO` type a sentence -> **Aria** -> listen -> switch voice -> listen

`SAY`

- Two directions, and you can hear both before writing a line.
- Text in, audio out. Audio in, text out.
- No model deployed, no endpoint, no code. Speech rides the Foundry resource you already have.

### 1b. Voice Live on an agent (3 min) — **the beat that matters**

`SHOW` **proj-agents** -> your agent -> **Voice Live**

`DO` pick **`gpt-realtime`**, voice **Aria**, start talking to it

`CHECK` the agent answers **out loud**, and Camtasia's meter moves on system audio
`CHECK` you can **talk over it** and it stops mid-sentence

`SAY`

- This is the same agent you built earlier in the course. I have not changed it. I gave it **ears and a voice**.
- Watch what I did *not* do: no speech-to-text call, no text-to-speech call, no orchestration between them. **Voice Live is fully managed** — speech in, speech out, one connection.
- Note the interruption. I can talk over it and it stops. That is not something you get by chaining STT to a model to TTS; you would be waiting for a full turn every time.
- **This is the exam's answer for "voice agent."** If a stem describes a real-time spoken conversation with barge-in, the answer is Voice Live — not a pipeline you assemble yourself.

`SAY` handoff

- Managed is the right default. Now let us go under it, because when the base model gets a word wrong, you need to know which layer to fix.

`FIX` Voice Live won't connect -> check mic permission in Edge first, then the agent's model. `--` Keep talking; do not debug on camera.

---

## 2 · The break, and the runtime grammar that fixes it (5 min)

`SHOW` `m16_speech.py` -> the `SCRIPT` and `TERMS` constants

`SAY` "ShipSense Pro" is in no base model's vocabulary. Watch it come apart.

```powershell
uv run python m16_speech.py --no-phrase-list
```

`CHECK` transcript reads **"The Ship Sense Pro dashboard"** — one brand, two words
`CHECK` **2/3 terms intact -> ['Northwind Logistics', 'Dana']**

`DO` **play `out/caller.wav`** — the room hears the source was clean

```powershell
uv run python m16_speech.py
```

`CHECK` **3/3 terms intact**

`SHOW` `transcribe()` -> `PhraseListGrammar.from_recognizer(recognizer)`

`SAY` the landing

- A phrase list is **not a header and not a query parameter.** It is a runtime grammar attached to a live recognizer. That is why this uses the SDK.
- Available on **real-time recognition, fast transcription, and Voice Live** — **not** batch transcription.
- `setWeight` runs 0.0 to 2.0. Zero disables, two is maximum bias.
- **Custom speech training** is the heavy tool: broad vocabulary, permanent, minutes for text and days for audio. Reaching for training when a phrase list would do is the classic overspend on this exam.

`SHOW` `speech_token()`

`SAY`

- Speech has **two surfaces, two token shapes.** Regional endpoints want `aad#`, resource id, `#`, token. The account endpoint takes a plain bearer.
- Miss the prefix and you get a 401 that reads exactly like an expired credential.

`FIX` `401` -> token shape. `403` -> **Cognitive Services User** on the account.

---

## 3 · Two routes out, and where to fix a bad word (4 min)

```powershell
uv run python m16_translate_speech.py
```

`CHECK` Route 1a French: **"Le tableau de bord Ship Sense Pro"** — break rides through
`CHECK` Route 1a **1/2 names intact**, Route 1b **2/2**
`CHECK` Routes 1a/1b print **register: INFORMAL (tu / du)**
`CHECK` Route 2 prints **register: FORMAL (vous / Sie)**

`SAY` the cascade

- Route one: audio in, translated text out, one call. And there is the recognition error, riding into **both** languages verbatim. One bad token upstream, a branding error in every market at once, and nothing flagged it.

`SAY` the upstream fix

- Same one call. The phrase list biased **recognition**, which sits upstream of translation. The fix propagates for free and repairs the transcript too. **Fix terminology as far upstream as you can.**

`SAY` the register discovery — **slow down here, this is the best moment**

- Now the address form. Azure Translator chose **informal** on its own. "Quand tu as un moment." "Wann immer du einen Moment hast." To a business customer.
- No glossary fixes that. **It is not a terminology problem.**
- Route two: **"vous."** **"Sie."** I never said the word formal — I asked it to hold the register and it worked out that a business caller warrants formal address. It also caught that Dana is a woman: **"je suis sûre"**, where Translator wrote "je suis sûr."

`SAY` the close

1. **Voice Live is the managed answer for a voice agent.** Speech in, speech out, interruptible.
2. **A phrase list is a runtime grammar, not a header.** Training is the heavier tool.
3. **Fix bad terms upstream; buy judgment downstream.** Register and tone are what the extra hop actually buys.

`SAY` I hope you found this lesson helpful. I will see you next time.

---

## PANIC TABLE

| Symptom | Fix on camera |
| --- | --- |
| Voice Live silent | Edge mic permission, then agent model. Keep talking. |
| No audio in Camtasia | System Audio was off. You cannot fix it in post — re-record the beat. |
| `401` Speech | token shape: `aad#<resourceId>#<token>` |
| `403` Speech | **Cognitive Services User** on the account |
| Beat 3 canceled | `--model-only` keeps it moving |
| `caller.wav` missing | run `uv run python m16_speech.py` first |

## DO NOT

- Do not skip playing `caller.wav`. Beat 2 only lands if the room hears the source was clean.
- Do not call a phrase list a header. It is a grammar on the recognizer.
- Do not pass `--clean` mid-take.

## OBJECTIVE COVERAGE

| LO | Where |
| --- | --- |
| 1 speech to text and text to speech | Beat 1a playground, Beat 2 round trip |
| 2 speech as an agent modality, custom speech models | **Beat 1b Voice Live**, Beat 2 phrase list vs training |
| 3 multimodal reasoning from audio inputs | Beat 1b Voice Live (audio in, audio out, no transcript) |
| 4 translate speech using language models and Foundry Tools | Beat 3, both routes |

## CUT FROM CAMERA (still in the repo, still runs)

`m16_audio_reason.py` — transcript-then-text-model vs `input_audio`, one call vs
two. Worth a mention in the lecture, not worth 4 minutes here now that Voice Live
carries the multimodal objective. Verified working if you want it as a bonus clip.
