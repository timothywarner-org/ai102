#!/usr/bin/env python
"""
Regenerate Lesson 16's audio fixtures with Azure TTS.

WHY SYNTHESIZE INSTEAD OF RECORDING: a recorded WAV is a binary blob nobody can
review in a pull request, it drifts when someone re-records it, and it forces a
microphone into a demo that should not need one. Synthesizing from a script in
this file makes the input auditable, reproducible, and identical on every
machine. The text below IS the fixture.

Two fixtures, each earning its place:

  caller-en.wav   An annoyed customer with a delivery problem. Carries a name,
                  an order number, and an emotional register that a transcript
                  flattens. That last part is the whole point of Beat 3.

  caller-es.wav   The same customer intent in Spanish, for the translation beat.
                  Detection has to earn its keep before translation runs.

Idempotent: skips a fixture that already exists unless --force is passed, so a
pre-flight re-run costs nothing and never surprises you mid-recording.
"""
from __future__ import annotations

import os
import pathlib
import sys

for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_pv, None)

try:
    from dotenv import load_dotenv
    load_dotenv(pathlib.Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

import azure.cognitiveservices.speech as speechsdk  # noqa: E402
from azure.identity import AzureCliCredential  # noqa: E402

HERE = pathlib.Path(__file__).parent

# 16 kHz mono PCM. Voice Live wants raw PCM16 at 24 kHz for input, but a WAV on
# disk is easier to inspect and play, so the demo resamples on read.
OUTPUT_FORMAT = speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm

FIXTURES = {
    "caller-en.wav": {
        "voice": "en-US-AndrewMultilingualNeural",
        # Deliberately escalating. A sentiment score reads this as "negative";
        # only the audio tells you the caller is about to cancel.
        "text": (
            "Hi, this is Marcus Webb, order number four four seven one. "
            "Look, I've been on hold twice already today. "
            "The delivery was supposed to arrive Tuesday and it's now Thursday, "
            "and nobody has called me back. "
            "I need somebody to actually tell me where my order is."
        ),
    },
    "caller-es.wav": {
        "voice": "es-ES-AlvaroNeural",
        "text": (
            "Hola, soy Marcus Webb, pedido cuatro cuatro siete uno. "
            "Mi entrega tenía que llegar el martes y todavía no ha llegado. "
            "Necesito saber dónde está mi pedido."
        ),
    },
}


def synthesize(name: str, spec: dict, endpoint: str, credential, force: bool) -> bool:
    path = HERE / name
    if path.exists() and not force:
        print(f"  skip  {name}  (exists; --force to regenerate)")
        return False

    # Keyless, and note the endpoint: Speech authenticates against the account's
    # *.cognitiveservices.azure.com custom domain, NOT the services.ai.azure.com
    # host the model APIs use. Passing region + a bare token instead of
    # token_credential + endpoint is a 401 that reads like a bad role
    # assignment, which is a genuinely expensive hour to lose.
    cfg = speechsdk.SpeechConfig(token_credential=credential, endpoint=endpoint)
    cfg.speech_synthesis_voice_name = spec["voice"]
    cfg.set_speech_synthesis_output_format(OUTPUT_FORMAT)

    audio_cfg = speechsdk.audio.AudioOutputConfig(filename=str(path))
    synth = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=audio_cfg)
    result = synth.speak_text_async(spec["text"]).get()

    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        detail = ""
        if result.reason == speechsdk.ResultReason.Canceled:
            c = result.cancellation_details
            detail = f"\n    {c.reason}: {c.error_details}"
        raise SystemExit(f"[synthesis failed] {name}{detail}")

    print(f"  wrote {name}  ({path.stat().st_size:,} bytes, {spec['voice']})")
    return True


def main() -> int:
    force = "--force" in sys.argv
    endpoint = os.getenv("SPEECH_ENDPOINT", "").strip()
    if not endpoint:
        raise SystemExit("[config] Set SPEECH_ENDPOINT in .env. See .env.example.")

    # Keyless. The same az login identity every other lesson uses.
    credential = AzureCliCredential()

    made = sum(synthesize(n, s, endpoint, credential, force) for n, s in FIXTURES.items())
    print(f"\n{len(FIXTURES)} fixtures present ({made} generated this run).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
