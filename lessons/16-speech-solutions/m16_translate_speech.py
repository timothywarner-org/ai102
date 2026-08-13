#!/usr/bin/env python
"""
AI-103 Lesson 16, Beat 4 - two routes out of one recording.

    uv run python m16_translate_speech.py

    Route 1   audio -> Speech translation -> translated text
              ONE call. Recognition and translation happen together.

    Route 2   transcript -> a language model with instructions
              One more hop, and you get to state the rules in plain English.

THE MOMENT THIS BEAT EXISTS FOR
-------------------------------
Route 1 is fast, and it inherits every recognition error downstream. The
recognizer splits the brand into "Ship Sense Pro", and that mis-split rides into
French AND German verbatim. One bad token upstream becomes a branding error in
every market at once, and nothing in the pipeline flags it.

There is a second difference, and it is the one worth pausing on. Azure
Translator picks INFORMAL address on its own:

    Quand tu as un moment.        Wann immer du einen Moment hast.

For a business support call in French or German that is simply wrong, and no
glossary or term base fixes it, because it is not a terminology problem. Route 2
was told to hold the register and chose "vous" and "Sie". It also inferred that
Dana is a woman and wrote "je suis sure" where Translator wrote "je suis sur".

That is the honest argument for spending the extra hop: not accuracy, but the
rules you can state in a sentence and a translator has no way to accept.

There are two fixes and they operate at different layers, which is exactly the
distinction the exam cares about:

    Fix it UPSTREAM   attach a phrase list to the translation recognizer, so the
                      term is recognized correctly before translation ever runs
    Fix it DOWNSTREAM ask a model to translate and tell it to protect the term

Upstream is cheaper and it fixes the transcript too. Downstream is more flexible
and can hold register, tone, and formatting rules that a translator cannot.

WHY THE SDK
-----------
Speech translation is a recognizer, not a REST POST. There is no plain
"translate this audio" HTTP route on the regional endpoint -- pointing curl at
/speech/universal/v2 returns 400 with a message about an invalid language
parameter, which sends people hunting for a query-string bug that does not
exist. TranslationRecognizer is the API.

DOCS
    https://learn.microsoft.com/azure/ai-services/speech-service/speech-translation
    https://learn.microsoft.com/azure/ai-services/speech-service/get-started-speech-translation
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys
import threading

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import m16_cache as cache  # noqa: E402
from m16_speech import TERMS, speech_token, transcribe  # noqa: E402

AOAI_SCOPE = "https://ai.azure.com/.default"

HERE = pathlib.Path(__file__).parent
OUT = HERE / "out"

TARGETS = ["fr", "de"]

# Stated in plain English, which is the entire argument for Route 2. No markup,
# no term-base upload, no glossary format to learn.
INSTRUCTION = (
    "Translate the support call below into French and German.\n"
    "Rules:\n"
    "  1. Keep these product and company names EXACTLY as written, untranslated: "
    "{terms}.\n"
    "  2. Hold the register of the original -- this caller is being outwardly "
    "polite while clearly annoyed. Do not soften it and do not sharpen it.\n"
    "Return exactly two lines, formatted as:\n"
    "FR: <translation>\n"
    "DE: <translation>")


def translate_speech(auth_token: str, region: str, audio_path: pathlib.Path,
                     targets: list[str], phrases: list[str] | None,
                     label: str) -> tuple[dict, bool]:
    """
    Route 1. TranslationRecognizer: audio in, translated text out, one call.

    Continuous recognition again, for the same reason as Beat 2 -- a
    multi-sentence call would otherwise be cut at the first silence.
    """
    def live() -> dict:
        import azure.cognitiveservices.speech as speechsdk

        config = speechsdk.translation.SpeechTranslationConfig(
            auth_token=auth_token, region=region)
        config.speech_recognition_language = "en-US"
        for target in targets:
            config.add_target_language(target)

        recognizer = speechsdk.translation.TranslationRecognizer(
            translation_config=config,
            audio_config=speechsdk.audio.AudioConfig(filename=str(audio_path)))

        # A phrase list works on a TranslationRecognizer too -- it biases the
        # RECOGNITION step, which is upstream of translation. This is the
        # upstream fix.
        if phrases:
            grammar = speechsdk.PhraseListGrammar.from_recognizer(recognizer)
            for phrase in phrases:
                grammar.addPhrase(phrase)

        recognized: list[str] = []
        collected: dict[str, list[str]] = {t: [] for t in targets}
        finished = threading.Event()
        failure: list[str] = []

        def on_recognized(evt) -> None:
            if evt.result.reason == speechsdk.ResultReason.TranslatedSpeech:
                if evt.result.text:
                    recognized.append(evt.result.text)
                for target in targets:
                    piece = evt.result.translations.get(target)
                    if piece:
                        collected[target].append(piece)

        def on_canceled(evt) -> None:
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
                f"\n[speech] translation canceled: {failure[0]}\n\n"
                f"403 -> Cognitive Services User on the account (data plane).\n"
                f"401 -> the token shape. Regional endpoints want aad#<rid>#<token>.\n")

        return {"recognized": " ".join(recognized),
                "translations": {t: " ".join(v) for t, v in collected.items()}}

    return cache.remember("speech.translate", label, live,
                          region=region, targets=targets,
                          phrases=phrases or [], audio=audio_path.read_bytes())


def translate_model(client, model: str, transcript: str,
                    terms: list[str]) -> tuple[str, bool]:
    """Route 2. One more hop, and the rules are just sentences."""
    instruction = INSTRUCTION.format(terms=", ".join(terms))

    def live() -> str:
        result = client.chat.completions.create(
            model=model,
            messages=[{"role": "user",
                       "content": f"{instruction}\n\n---\n{transcript}\n---"}])
        return result.choices[0].message.content.strip()

    return cache.remember("translate.model", model, live,
                          model=model, instruction=instruction, text=transcript)


def register(text: str) -> str:
    """
    Formal versus informal address, surfaced automatically.

    This is a genuine quality difference between the two routes and it is easy
    to miss on screen, so the script calls it rather than hoping someone spots
    a pronoun in a wall of French.
    """
    padded = f" {text} "
    informal = any(w in padded for w in (" tu ", " du ", " ton ", " dein ", " deine "))
    formal = any(w in padded for w in (" vous ", " Sie ", " votre ", " Ihnen ", " Ihre "))
    if formal and not informal:
        return "register: FORMAL (vous / Sie)   <- right for a business call"
    if informal and not formal:
        return "register: INFORMAL (tu / du)    <- wrong for a business call"
    if formal and informal:
        return "register: MIXED (both forms present)"
    return "register: not detected"


def survived(text: str, terms: list[str]) -> str:
    kept = [t for t in terms if t in text]
    return f"{len(kept)}/{len(terms)} names intact -> {kept or 'none'}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Beat 4: speech translation versus a model, and where to fix a bad term.")
    parser.add_argument("--audio", default=str(OUT / "caller.wav"))
    parser.add_argument("--model-only", action="store_true",
                        help="skip Route 1 if Speech is unavailable on camera")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    if args.no_cache:
        cache.ENABLED = False

    region = os.getenv("SPEECH_REGION", "").strip()
    endpoint = os.getenv("FOUNDRY_ACCOUNT_ENDPOINT", "").strip()
    chat_model = os.getenv("CHAT_MODEL", "").strip()

    audio_path = pathlib.Path(args.audio)
    if not audio_path.exists():
        raise SystemExit(
            f"[input] {audio_path} not found. Run Beat 2 first:\n"
            f"    uv run python m16_speech.py\n")

    from azure.identity import AzureCliCredential
    credential = AzureCliCredential()
    token = speech_token(credential)
    # Only these two names must survive; "Dana" is a common given name and
    # translators leave it alone, so scoring it would flatter the result.
    protect = ["Northwind Logistics", "ShipSense Pro"]

    print("\n  One recording, two routes out")
    print(f"    targets         : {', '.join(TARGETS)}")
    print(f"    protected terms : {protect}")

    if not args.model_only:
        print("\n" + "=" * 72)
        print("  ROUTE 1a  speech translation, NO phrase list")
        print("=" * 72)
        raw, cached = translate_speech(token, region, audio_path, TARGETS, None, "raw")
        print(f"    recognized : {raw['recognized']}")
        for target in TARGETS:
            print(f"    {target} -> {raw['translations'][target]}")
        print(f"    {survived(' '.join(raw['translations'].values()), protect)}")
        print(f"    [{'cached' if cached else 'live'}]")
        print(f"    {register(' '.join(raw['translations'].values()))}")
        print("\n    The recognizer split the brand into 'Ship Sense Pro', and that")
        print("    mis-split rode into BOTH languages verbatim. One bad token")
        print("    upstream, a branding error in every market at once.")

        print("\n" + "=" * 72)
        print("  ROUTE 1b  speech translation, phrase list attached (UPSTREAM fix)")
        print("=" * 72)
        fixed, cached = translate_speech(token, region, audio_path, TARGETS, TERMS, "fixed")
        print(f"    recognized : {fixed['recognized']}")
        for target in TARGETS:
            print(f"    {target} -> {fixed['translations'][target]}")
        print(f"    {survived(' '.join(fixed['translations'].values()), protect)}")
        print(f"    [{'cached' if cached else 'live'}]")
        print(f"    {register(' '.join(fixed['translations'].values()))}")
        print("\n    Same one call. The phrase list biased RECOGNITION, which is")
        print("    upstream of translation, so the fix propagates for free.")
        print("    But look at the address form. Translator chose INFORMAL on its")
        print("    own -- 'tu' and 'du' -- to a business customer. No glossary")
        print("    fixes that, because it is not a terminology problem.")

    if not endpoint or not chat_model:
        raise SystemExit("[config] FOUNDRY_ACCOUNT_ENDPOINT and CHAT_MODEL are required.")

    from openai import OpenAI
    client = OpenAI(base_url=f"{endpoint.rstrip('/')}/openai/v1",
                    api_key=credential.get_token(AOAI_SCOPE).token)

    transcript, _ = transcribe(token, region, audio_path, TERMS, None, "on")

    print("\n" + "=" * 72)
    print(f"  ROUTE 2  transcript -> {chat_model}  (DOWNSTREAM control)")
    print("=" * 72)
    answer, cached = translate_model(client, chat_model, transcript, protect)
    for line in answer.splitlines():
        print(f"    {line}")
    print(f"    {survived(answer, protect)}")
    print(f"    {register(answer)}")
    print(f"    [{'cached' if cached else 'live'}]")

    print("\n  Same names, same meaning -- and 'vous' and 'Sie'. I never said the")
    print("  word formal. I asked it to hold the register and it worked out that a")
    print("  business caller warrants formal address. It also caught that Dana is a")
    print("  woman: 'je suis sure', where Translator wrote 'je suis sur'.")

    print("\n  Two questions, in this order:")
    print("    Is somebody waiting on this?      If yes, Route 1 nearly always.")
    print("    Do the rules go beyond words?     Register, formatting, terms in")
    print("                                      context -- then the hop earns itself.")
    print("\n  And fix bad terminology as far UPSTREAM as you can. A phrase list on")
    print("  the recognizer repairs the transcript AND every translation after it.")

    print("\n" + "-" * 72)
    print(f"  {cache.summary()}")
    print("-" * 72 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
