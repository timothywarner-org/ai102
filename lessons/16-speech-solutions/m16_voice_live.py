#!/usr/bin/env python
"""
AI-103 Lesson 16 - Beat 2: one WebSocket instead of three services.

Covers learning objectives:
  LO1  Implement workflows to convert speech to text and text to speech for
       agentic interactions
  LO3  Enable multimodal reasoning from audio inputs

WHAT THIS DEMONSTRATES
----------------------
The same customer call, handled two ways, and the difference is the lesson.

  --pipeline    speech to text, then a model, then text to speech.
                Three round trips, three services, and the transcript is the
                only thing that survives the first hop.
  (default)     Voice Live. Audio in, audio out, one connection, and the model
                hears the caller rather than reading a transcription of them.

Run both against assets/caller-en.wav and compare two things on screen: the
wall-clock time, and whether the reply reacts to how Marcus SOUNDS versus what
he said. The transcript is identical either way. The answers are not.

NO MICROPHONE. Audio comes from a WAV file and the reply is written to out/, so
a retake is a replay rather than a performance. Everything here works the same
way with a live mic; the file is a recording-safety decision, not a limitation.

USAGE
-----
  uv run python m16_voice_live.py --dry-run
  uv run python m16_voice_live.py                        # Voice Live, one hop
  uv run python m16_voice_live.py --pipeline             # STT -> model -> TTS
  uv run python m16_voice_live.py --audio assets/caller-es.wav

PREREQS
-------
  az login
  cp .env.example .env
  uv sync
  uv run python assets/make_assets.py
"""
from __future__ import annotations

# Proxy scrub before any Azure import. A stale HTTPS_PROXY makes the WebSocket
# handshake fail in a way that reads like an auth problem and is not.
import os

for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_pv, None)

import argparse
import asyncio
import pathlib
import sys
import time
import wave

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)          # a stale shell var must not shadow .env
except ImportError:
    pass

from azure.identity.aio import AzureCliCredential as AsyncCliCredential  # noqa: E402

HERE = pathlib.Path(__file__).parent
OUT = HERE / "out"

# Voice Live speaks raw PCM16 mono. 24 kHz is the service's native rate; the
# fixtures are 16 kHz, so they are resampled on read rather than re-recorded.
TARGET_RATE = 24_000

# The agent persona. Deliberately short: the point of the demo is the audio
# path, not prompt engineering, and a long prompt would bury the lede.
INSTRUCTIONS = (
    "You are a customer service agent for Contoso Shipping. "
    "Listen to the caller and respond in two sentences or fewer. "
    "Acknowledge how the caller sounds before you address the logistics. "
    "Never invent a delivery date you were not given."
)


# =============================================================================
def read_wav_as_pcm(path: pathlib.Path) -> tuple[bytes, int, float]:
    """
    Read a WAV into mono PCM16 at TARGET_RATE. Returns (pcm, rate, seconds).

    Hand-rolled rather than using `audioop`, which was REMOVED from the standard
    library in Python 3.13. Depending on it here would break the lesson on any
    current interpreter, and pulling in numpy or librosa to move some samples
    around is not a trade worth making for 20 lines of arithmetic.
    """
    import array

    with wave.open(str(path), "rb") as w:
        channels, width, rate, frames = (
            w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes())
        raw = w.readframes(frames)
        seconds = frames / float(rate)

    if width != 2:
        raise SystemExit(f"[audio] {path.name} is {width * 8}-bit; this demo expects 16-bit PCM.")

    samples = array.array("h")
    samples.frombytes(raw)
    if sys.byteorder == "big":
        samples.byteswap()                      # WAV is little-endian on disk

    # Downmix to mono by averaging channel pairs.
    if channels > 1:
        mono = array.array("h", (
            sum(samples[i:i + channels]) // channels
            for i in range(0, len(samples) - channels + 1, channels)))
        samples = mono

    # Linear-interpolation resample. Good enough for speech, and every sample
    # here is a voice recording rather than something anyone will master.
    if rate != TARGET_RATE:
        ratio = TARGET_RATE / rate
        n_out = int(len(samples) * ratio)
        out = array.array("h", bytes(2 * n_out))
        for i in range(n_out):
            src = i / ratio
            j = int(src)
            frac = src - j
            a = samples[j]
            b = samples[j + 1] if j + 1 < len(samples) else a
            out[i] = int(a + (b - a) * frac)
        samples = out

    return samples.tobytes(), TARGET_RATE, seconds


def write_wav(path: pathlib.Path, pcm: bytes, rate: int = TARGET_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


# =============================================================================
async def run_voice_live(endpoint: str, model: str, audio: pathlib.Path,
                         voice: str) -> dict:
    """
    One WebSocket. Audio in, audio out, and the model never sees a transcript
    that we produced -- it hears the caller directly.
    """
    from azure.ai.voicelive.aio import connect
    from azure.ai.voicelive.models import (
        AudioInputTranscriptionOptions, AzureStandardVoice, InputAudioFormat,
        Modality, OutputAudioFormat, RequestSession, ServerEventType,
    )

    pcm, _, seconds = read_wav_as_pcm(audio)
    reply_audio, reply_text, heard = bytearray(), [], []

    credential = AsyncCliCredential()
    started = time.perf_counter()
    try:
        async with connect(credential=credential, endpoint=endpoint,
                           model=model) as conn:
            # Ask for BOTH modalities. Requesting the transcript alongside the
            # audio is what lets the demo show you what it heard -- without it,
            # the reply is audio only and there is nothing to put on screen.
            await conn.session.update(session=RequestSession(
                modalities=[Modality.TEXT, Modality.AUDIO],
                instructions=INSTRUCTIONS,
                voice=AzureStandardVoice(name=voice),
                input_audio_format=InputAudioFormat.PCM16,
                output_audio_format=OutputAudioFormat.PCM16,
                input_audio_transcription=AudioInputTranscriptionOptions(
                    model="whisper-1"),
            ))

            # Push the whole file. A live mic would append these same chunks as
            # they are captured; the only difference is where the bytes came from.
            #
            # DO NOT commit the buffer or call response.create() here. Server-side
            # voice activity detection is on by default: the service detects the
            # end of the utterance and starts the response itself. Committing on
            # top of that opens a SECOND turn with no audio in it, and the reply
            # you actually wanted gets cancelled -- you get response.done with
            # empty content and a suspiciously fast round trip. Let VAD drive.
            CHUNK = 4800                      # 100 ms at 24 kHz mono PCM16
            for i in range(0, len(pcm), CHUNK):
                await conn.input_audio_buffer.append(audio=pcm[i:i + CHUNK])

            async for event in conn:
                t = event.type
                if t == ServerEventType.RESPONSE_AUDIO_DELTA:
                    reply_audio.extend(event.delta)
                elif t == ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA:
                    reply_text.append(event.delta)
                elif t == ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED:
                    heard.append(event.transcript)
                elif t == ServerEventType.RESPONSE_DONE:
                    # Only stop once the reply actually carries content. VAD can
                    # emit an early empty response.done on a false turn boundary.
                    if reply_audio or reply_text:
                        break
                elif t == ServerEventType.ERROR:
                    raise SystemExit(f"\n[voice live error] {event.error}\n")
    finally:
        await credential.close()

    return {
        "elapsed": time.perf_counter() - started,
        "source_seconds": seconds,
        "heard": " ".join(heard).strip(),
        "reply_text": "".join(reply_text).strip(),
        "reply_audio": bytes(reply_audio),
        "hops": 1,
    }


def run_pipeline(speech_endpoint: str, foundry: str, model_deployment: str,
                 audio: pathlib.Path, voice: str) -> dict:
    """
    The do-it-yourself path: recognize, reason, synthesize. Three services.

    This is the architecture on slide 4, and running it is the only honest way
    to show what the managed path is actually saving you.
    """
    import azure.cognitiveservices.speech as speechsdk
    from azure.identity import AzureCliCredential, get_bearer_token_provider
    from openai import OpenAI

    credential = AzureCliCredential()
    _, _, seconds = read_wav_as_pcm(audio)
    started = time.perf_counter()

    # --- hop 1: speech to text -------------------------------------------
    cfg = speechsdk.SpeechConfig(token_credential=credential,
                                 endpoint=speech_endpoint)
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=cfg,
        audio_config=speechsdk.audio.AudioConfig(filename=str(audio)))
    stt = recognizer.recognize_once()
    if stt.reason != speechsdk.ResultReason.RecognizedSpeech:
        raise SystemExit(f"[stt failed] {stt.reason} {getattr(stt, 'no_match_details', '')}")
    heard = stt.text
    t_stt = time.perf_counter() - started

    # --- hop 2: the model, reading TEXT ----------------------------------
    # Everything about how Marcus sounded was discarded by the line above.
    client = OpenAI(
        base_url=f"{foundry.rstrip('/')}/openai/v1",
        api_key=get_bearer_token_provider(credential, "https://ai.azure.com/.default"))
    chat = client.chat.completions.create(
        model=model_deployment,
        messages=[{"role": "system", "content": INSTRUCTIONS},
                  {"role": "user", "content": heard}],
    )
    reply_text = chat.choices[0].message.content.strip()
    t_model = time.perf_counter() - started - t_stt

    # --- hop 3: text to speech -------------------------------------------
    tts_cfg = speechsdk.SpeechConfig(token_credential=credential,
                                     endpoint=speech_endpoint)
    tts_cfg.speech_synthesis_voice_name = voice
    tts_cfg.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Raw24Khz16BitMonoPcm)
    synth = speechsdk.SpeechSynthesizer(speech_config=tts_cfg, audio_config=None)
    tts = synth.speak_text_async(reply_text).get()
    if tts.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise SystemExit(f"[tts failed] {tts.reason}")

    total = time.perf_counter() - started
    return {
        "elapsed": total,
        "source_seconds": seconds,
        "heard": heard,
        "reply_text": reply_text,
        "reply_audio": tts.audio_data,
        "hops": 3,
        "split": {"stt": t_stt, "model": t_model, "tts": total - t_stt - t_model},
    }


# =============================================================================
def render(label: str, r: dict, out_path: pathlib.Path) -> None:
    print(f"\n  {label}")
    print(f"    hops                {r['hops']}")
    print(f"    caller audio        {r['source_seconds']:.1f}s")
    print(f"    round trip          {r['elapsed']:.1f}s")
    if "split" in r:
        s = r["split"]
        print(f"      stt {s['stt']:.1f}s  +  model {s['model']:.1f}s  +  tts {s['tts']:.1f}s")
    print(f"\n    HEARD   {r['heard'][:200]}")
    print(f"    REPLY   {r['reply_text'][:300]}")
    if r["reply_audio"]:
        write_wav(out_path, r["reply_audio"])
        print(f"\n    reply audio -> {out_path.relative_to(HERE)}  "
              f"({len(r['reply_audio']):,} bytes)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--audio", default="assets/caller-en.wav")
    ap.add_argument("--pipeline", action="store_true",
                    help="Run the STT -> model -> TTS path instead of Voice Live.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    audio = HERE / args.audio if not pathlib.Path(args.audio).is_absolute() \
        else pathlib.Path(args.audio)

    foundry = os.getenv("FOUNDRY_ACCOUNT_ENDPOINT", "").strip()
    speech_endpoint = os.getenv("SPEECH_ENDPOINT", "").strip()
    model = os.getenv("VOICE_LIVE_MODEL", "gpt-realtime").strip()
    deployment = os.getenv("CHAT_DEPLOYMENT", "gpt-5-mini").strip()
    voice = os.getenv("SPEECH_VOICE", "en-US-AvaMultilingualNeural").strip()

    mode = "pipeline (stt -> model -> tts)" if args.pipeline else "Voice Live (one hop)"
    print(f"\n  {mode}")
    print(f"    caller audio      : {audio.name}")
    print(f"    voice             : {voice}")
    print(f"    model             : {deployment if args.pipeline else model}")

    if args.dry_run:
        print("\n[dry-run] no calls made")
        if args.pipeline:
            print(f"  hop 1 -> {speech_endpoint or '<speech>'}  (recognize_once)")
            print(f"  hop 2 -> {foundry or '<foundry>'}/openai/v1/chat/completions")
            print(f"  hop 3 -> {speech_endpoint or '<speech>'}  (speak_text)")
        else:
            print(f"  wss   -> {foundry or '<foundry>'}  model={model}")
        print(f"    would read {audio.name}  {'ok' if audio.exists() else 'MISSING'}")
        return 0

    if not audio.exists():
        raise SystemExit(f"[input] {audio} not found. "
                         f"Run: uv run python assets/make_assets.py")
    if not foundry:
        raise SystemExit("[config] Set FOUNDRY_ACCOUNT_ENDPOINT. See .env.example.")

    if args.pipeline:
        if not speech_endpoint:
            raise SystemExit("[config] Set SPEECH_ENDPOINT. See .env.example.")
        result = run_pipeline(speech_endpoint, foundry, deployment, audio, voice)
        render("PIPELINE   three services, three hops", result,
               OUT / f"pipeline-{audio.stem}.wav")
    else:
        result = asyncio.run(run_voice_live(foundry, model, audio, voice))
        render("VOICE LIVE   one connection", result,
               OUT / f"voicelive-{audio.stem}.wav")

    print(f"\n{'-' * 72}")
    print("  Run it the other way and compare. The transcript barely changes.")
    print("  What changes is the latency and whether the reply reacts to TONE.")
    print(f"{'-' * 72}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
