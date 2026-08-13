#!/usr/bin/env python
"""
AI-103 Lesson 16, Beat 2 - the round trip, and the one thing that fixes it.

    uv run python m16_speech.py --no-phrase-list    # recognizer mangles the product name
    uv run python m16_speech.py                     # phrase list repairs it

WHAT THIS DEMONSTRATES
----------------------
1. Text to speech, then speech to text, on one Foundry account. The caller is
   synthesized here, so the demo needs no microphone and every take is
   byte-identical.
2. A phrase list repairs a product name the base model has never heard -- with
   no training job, no dataset, and no deployment.

TWO AUTH SHAPES, AND THIS IS THE ONE THAT COSTS PEOPLE AN HOUR
--------------------------------------------------------------
Speech has two distinct surfaces and they do NOT take the same token:

  * Regional endpoints  (<region>.tts.speech.microsoft.com, <region>.stt....)
        Authorization: Bearer aad#<resourceId>#<entra-token>
        A plain bearer token here returns 401, and that 401 reads exactly like
        an expired credential. You will debug the wrong thing.

  * Account endpoint    (<account>.cognitiveservices.azure.com/speechtotext/...)
        Authorization: Bearer <entra-token>          <-- plain, no aad# prefix

This script uses the regional surface for both legs, so everything below wants
the composite form. The Speech SDK takes that same composite string via
SpeechConfig(auth_token=...).

WHY THE SDK FOR RECOGNITION AND RAW REST FOR SYNTHESIS
------------------------------------------------------
Synthesis is a single POST that returns audio bytes. REST is the clearer
teaching artifact -- the whole request fits on one screen.

Recognition needs the SDK, because a phrase list is NOT a header and NOT a query
parameter. It is a runtime grammar attached to a live recognizer object
(PhraseListGrammar). There is no way to express it on the short-audio REST
endpoint at all. That is the most misremembered fact in this topic.

Phrase lists are available three ways, and knowing which matters:
  * real-time recognition (Speech SDK / Speech CLI)   <-- what this script uses
  * fast transcription REST ("phraseList": {"phrases": [...]} in the definition)
  * Voice Live API
  ...and NOT batch transcription.

CONTINUOUS, NOT SINGLE-SHOT
---------------------------
recognize_once() stops at the first silence, so on a multi-sentence call it
captures only the opening line and looks exactly like a truncation bug. Any real
recording needs start_continuous_recognition() plus a handler that accumulates
segments. That is the pattern below.

DOCS
    https://learn.microsoft.com/azure/ai-services/speech-service/improve-accuracy-phrase-list
    https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech
    https://learn.microsoft.com/azure/ai-services/speech-service/how-to-recognize-speech
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys
import threading
import urllib.error
import urllib.request

# Force UTF-8 on stdout. Transcripts come back with typographic quotes and a
# default Windows console renders them as mojibake -- on camera, in a course.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import m16_cache as cache  # noqa: E402

# Entra scope for BOTH Speech legs. Note this is the Cognitive Services scope,
# not the ai.azure.com scope that the model endpoints use.
SPEECH_SCOPE = "https://cognitiveservices.azure.com/.default"

HERE = pathlib.Path(__file__).parent
OUT = HERE / "out"

# The fixture. Two properties matter and both are deliberate:
#   1. "ShipSense Pro" is in no base model vocabulary. It WILL break.
#   2. The words minimize ("it's fine", "no rush") while the delivery does not.
#      Beat 3 lives in that gap.
SCRIPT = ("Hi, it's Dana at Northwind Logistics. No, no, it's fine. "
          "The ShipSense Pro dashboard has been down since this morning, "
          "but I'm sure someone will get to it eventually. "
          "Whenever you have a moment. No rush.")

# What we score. "Dana" and "Northwind Logistics" are common enough that the
# base model gets them; "ShipSense Pro" is the one that breaks. Keeping all
# three on the scorecard is the honest presentation -- it shows a phrase list
# repairing the term that actually failed, not implying everything was broken.
TERMS = ["Northwind Logistics", "ShipSense Pro", "Dana"]

DEFAULT_VOICE = "en-US-AriaNeural"
DEFAULT_STYLE = "angry"    # Aria supports expressive styles; multilingual voices largely do not.
DEFAULT_DEGREE = "2"       # 0.01 to 2. Two is maximum intensity.


def speech_token(credential) -> str:
    """
    Build the COMPOSITE token the regional Speech endpoints require.

        aad#<armResourceId>#<entraAccessToken>

    Returning a plain token here is the classic failure. Azure answers 401 and
    says nothing about token shape.
    """
    resource_id = os.getenv("SPEECH_RESOURCE_ID", "").strip()
    if not resource_id:
        raise SystemExit(
            "[config] SPEECH_RESOURCE_ID is required. Speech over Entra needs "
            "aad#<resourceId>#<token>. See .env.example and the AUTH NOTE above.")
    entra = credential.get_token(SPEECH_SCOPE).token
    return f"aad#{resource_id}#{entra}"


def build_ssml(text: str, voice: str, style: str | None, degree: str) -> str:
    """
    SSML with an optional expressive style.

    The mstts namespace declaration is mandatory for <mstts:express-as>. Omit it
    and the service does not error -- it silently ignores the style and returns
    a flat read, which is far harder to notice than a failure would be.
    """
    ns = ("xmlns='http://www.w3.org/2001/10/synthesis' "
          "xmlns:mstts='https://www.w3.org/2001/mstts'")
    inner = (f"<mstts:express-as style='{style}' styledegree='{degree}'>{text}</mstts:express-as>"
             if style else text)
    return (f"<speak version='1.0' {ns} xml:lang='en-US'>"
            f"<voice name='{voice}'>{inner}</voice></speak>")


def synthesize(token: str, region: str, text: str, voice: str,
               style: str | None, degree: str) -> tuple[bytes, bool]:
    """TTS on the REGIONAL endpoint. SSML in, 16 kHz mono PCM WAV out."""
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    ssml = build_ssml(text, voice, style, degree)

    def live() -> bytes:
        req = urllib.request.Request(
            url, data=ssml.encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/ssml+xml",
                # Required. 16 kHz mono PCM is exactly what the recognizer wants
                # back, so the round trip loses nothing to resampling.
                "X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm",
                "User-Agent": "ai103-lesson16",
            }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(
                f"\n[HTTP {exc.code}] {url}\n{detail}\n\n"
                f"401 here is almost always the TOKEN SHAPE, not an expired "
                f"credential. Regional endpoints want aad#<resourceId>#<token>.\n") from exc

    return cache.remember("speech.tts", voice, live,
                          region=region, voice=voice, text=text,
                          style=style or "", degree=degree)


def transcribe(auth_token: str, region: str, audio_path: pathlib.Path,
               phrases: list[str] | None, weight: float | None,
               label: str) -> tuple[str, bool]:
    """
    Speech to text via the SDK, using CONTINUOUS recognition.

    The phrase list attaches to the RECOGNIZER, not to the request. That is the
    whole point: it is a runtime grammar, evaluated during this recognition and
    gone when it ends. Nothing is trained, stored, or deployed.
    """
    def live() -> str:
        # Imported lazily so --dry-run and the offline harness never require the
        # native SDK binaries to be present.
        import azure.cognitiveservices.speech as speechsdk

        config = speechsdk.SpeechConfig(auth_token=auth_token, region=region)
        config.speech_recognition_language = "en-US"
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=config,
            audio_config=speechsdk.audio.AudioConfig(filename=str(audio_path)))

        if phrases:
            grammar = speechsdk.PhraseListGrammar.from_recognizer(recognizer)
            for phrase in phrases:
                grammar.addPhrase(phrase)
            if weight is not None:
                # 0.0 disables, 1.0 is the default, 2.0 is maximum bias toward
                # the list. The weight applies to the whole list, not per phrase.
                for setter in ("set_weight", "setWeight"):
                    if hasattr(grammar, setter):
                        getattr(grammar, setter)(weight)
                        break

        segments: list[str] = []
        finished = threading.Event()
        failure: list[str] = []

        def on_recognized(evt) -> None:
            if (evt.result.reason == speechsdk.ResultReason.RecognizedSpeech
                    and evt.result.text):
                segments.append(evt.result.text)

        def on_canceled(evt) -> None:
            # Cancellation carries the real error (auth, quota, bad audio).
            # Without this handler the run just returns an empty string and you
            # are left guessing.
            detail = getattr(evt, "error_details", "") or ""
            if detail:
                failure.append(detail)
            finished.set()

        recognizer.recognized.connect(on_recognized)
        recognizer.session_stopped.connect(lambda _evt: finished.set())
        recognizer.canceled.connect(on_canceled)

        recognizer.start_continuous_recognition()
        finished.wait(timeout=120)
        recognizer.stop_continuous_recognition()

        if failure:
            raise SystemExit(
                f"\n[speech] recognition canceled: {failure[0]}\n\n"
                f"403 -> the account needs the Cognitive Services User role on "
                f"the data plane. Owner is control plane and does not count.\n")
        return " ".join(segments)

    return cache.remember("speech.stt", label, live,
                          region=region, phrases=phrases or [],
                          weight=weight if phrases else None,
                          audio=audio_path.read_bytes())


def scorecard(text: str, terms: list[str]) -> str:
    kept = [t for t in terms if t.lower() in text.lower()]
    return f"{len(kept)}/{len(terms)} terms intact -> {kept or 'none'}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Beat 2: synthesize a caller, transcribe her back, repair the product name.")
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--style", default=DEFAULT_STYLE,
                        help="expressive style, or 'none' for a flat read")
    parser.add_argument("--degree", default=DEFAULT_DEGREE)
    parser.add_argument("--no-phrase-list", action="store_true",
                        help="skip the repair pass so the break stays visible")
    parser.add_argument("--weight", type=float, default=None,
                        help="phrase list bias, 0.0 to 2.0 (default: service default)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the request shapes without calling Azure")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--clean", action="store_true",
                        help="pre-flight only: delete .cache/ and out/")
    args = parser.parse_args()

    if args.no_cache:
        cache.ENABLED = False
    if args.clean:
        removed = cache.clean()
        print(f"  cleaned: {', '.join(removed) or 'nothing to clean'}\n")

    region = os.getenv("SPEECH_REGION", "").strip()
    style = None if args.style.lower() == "none" else args.style

    if args.dry_run:
        print("\n  Request shapes only. Nothing is called.\n")
        print(f"  TTS -> POST https://{region or '<region>'}.tts.speech.microsoft.com/cognitiveservices/v1")
        print( "         Authorization: Bearer aad#<resourceId>#<token>   <-- composite")
        print( "         Content-Type: application/ssml+xml")
        print( "         X-Microsoft-OutputFormat: riff-16khz-16bit-mono-pcm")
        print(f"  STT -> Speech SDK, continuous recognition, region={region or '<region>'}")
        print( "         PhraseListGrammar.from_recognizer(recognizer).addPhrase(...)")
        print( "         (a phrase list is NOT a header on the REST endpoint)")
        return 0

    if not region:
        raise SystemExit("[config] SPEECH_REGION is required. See .env.example.")

    # AzureCliCredential specifically, never DefaultAzureCredential. Default
    # probes environment variables first and will silently authenticate as
    # whatever service principal happens to be sitting in the shell.
    from azure.identity import AzureCliCredential
    token = speech_token(AzureCliCredential())

    OUT.mkdir(parents=True, exist_ok=True)
    wav_path = OUT / "caller.wav"

    print("\n  Speech round trip")
    print(f"    voice        : {args.voice}")
    print(f"    style        : {style or 'none'} (degree {args.degree})")
    print(f"    region       : {region}")
    print(f"    phrase list  : {'OFF (--no-phrase-list)' if args.no_phrase_list else TERMS}")

    audio, cached = synthesize(token, region, SCRIPT, args.voice, style, args.degree)
    wav_path.write_bytes(audio)
    print(f"\n  TTS  wrote {wav_path.name}  ({len(audio):,} bytes)  "
          f"[{'cached' if cached else 'live'}]")
    print(f"       script: {SCRIPT[:78]}...")

    plain, cached = transcribe(token, region, wav_path, None, None, "off")
    print(f"\n  STT  no phrase list  [{'cached' if cached else 'live'}]")
    print(f"       {plain}")
    print(f"       {scorecard(plain, TERMS)}")

    if args.no_phrase_list:
        print("\n  Stopping here on purpose. Re-run without --no-phrase-list to see the fix.")
    else:
        fixed, cached = transcribe(token, region, wav_path, TERMS, args.weight, "on")
        print(f"\n  STT  WITH phrase list  [{'cached' if cached else 'live'}]")
        print(f"       {fixed}")
        print(f"       {scorecard(fixed, TERMS)}")
        print("\n  No training job. No dataset. No deployment. A runtime grammar.")

    print("\n" + "-" * 72)
    print(f"  {cache.summary()}")
    print("-" * 72 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
