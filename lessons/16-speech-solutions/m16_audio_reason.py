#!/usr/bin/env python
"""
AI-103 Lesson 16, Beat 3 - two architectures for one answer.

    uv run python m16_audio_reason.py

THE EXPERIMENT
--------------
One recording. One question, word for word. Two ways to get an answer:

    Path A   audio -> Speech STT -> transcript -> a TEXT model
             two services, two calls, and a transcript artifact falls out

    Path B   audio -> an AUDIO-CAPABLE model
             one service, one call, no transcript

Both land in the same ballpark. The lesson is not that one wins -- it is what
each architecture costs you.

WHAT PATH A BUYS
    A transcript. You can log it, search it, redact it, diff it, attach it to a
    ticket, or hand it to a cheap text model. Compliance teams want that record
    and Path B does not produce one.
    You can also swap the reasoning model freely. Any text model works.

WHAT PATH B BUYS
    One network hop instead of two, and one less service to hold a role
    assignment on. Lower latency, fewer moving parts, less to break.
    The cost: you are pinned to audio-capable deployments, and there is no
    intermediate artifact to inspect when the answer is wrong.

A MEASURED WARNING, AND THIS IS THE PART TO SAY OUT LOUD
--------------------------------------------------------
The obvious pitch for Path B is "the model hears tone, so it reads the caller
better than words alone." I tested that claim rather than repeating it.

The fixture is synthesized with <mstts:express-as style='angry' styledegree='2'>.
A human hears the sarcasm immediately -- she says "no rush" and plainly does not
mean it. I then asked both audio models to judge the same recording against a
calm delivery of the identical script.

    gpt-audio-mini   low/medium, reasoning almost entirely from the words
    gpt-audio-1.5    identical verdict on both takes, and it described the
                     SHOUTED take as "relaxed and accepting"

Neither model reliably reported the delivery. They read the words.

So: multimodal input is a real capability and it collapses two hops into one.
It is NOT a free upgrade in emotional understanding, and on synthesized speech
it did not deliver one at all. Measure it on your own audio before you design
around it.

DOCS
    https://learn.microsoft.com/azure/ai-foundry/openai/audio-completions-quickstart
    https://learn.microsoft.com/azure/ai-foundry/concepts/models-sold-directly-by-azure
"""
from __future__ import annotations

import argparse
import base64
import os
import pathlib
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import m16_cache as cache  # noqa: E402
from m16_speech import TERMS, speech_token, transcribe  # noqa: E402

# The model endpoints take the ai.azure.com scope. Speech takes the
# cognitiveservices.azure.com scope. Mixing them up is a 401 with a
# perfectly unhelpful message.
AOAI_SCOPE = "https://ai.azure.com/.default"

HERE = pathlib.Path(__file__).parent
OUT = HERE / "out"

# IDENTICAL for both paths. That symmetry is the experiment -- change one word
# on one side and the comparison proves nothing.
QUESTION = ("You triage support calls. Judge both WHAT is said and HOW it is said.\n"
            "Answer in exactly three lines:\n"
            "URGENCY: <low|medium|high>\n"
            "CALLER STATE: <a few words>\n"
            "EVIDENCE: <what drove your read>")


def make_client(endpoint: str, credential):
    """Azure OpenAI v1 surface. Note the /openai/v1 suffix on the base URL."""
    from openai import OpenAI
    return OpenAI(base_url=f"{endpoint.rstrip('/')}/openai/v1",
                  api_key=credential.get_token(AOAI_SCOPE).token)


def reason_over_transcript(client, model: str, transcript: str) -> tuple[str, bool]:
    """Path A. A plain text completion over the transcript Speech produced."""
    def live() -> str:
        result = client.chat.completions.create(
            model=model,
            messages=[{"role": "user",
                       "content": f"{QUESTION}\n\n---\nTRANSCRIPT:\n{transcript}\n---"}])
        return result.choices[0].message.content.strip()

    return cache.remember("reason.text", model, live,
                          model=model, question=QUESTION, transcript=transcript)


def reason_over_audio(client, model: str, audio: bytes) -> tuple[str, bool]:
    """
    Path B. One message, two content parts: the question and the recording.

    That input_audio part is the entire API difference. A text-only deployment
    rejects it outright -- the error names the modality, not the schema.
    """
    def live() -> str:
        result = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": QUESTION},
                {"type": "input_audio",
                 "input_audio": {"data": base64.b64encode(audio).decode(),
                                 "format": "wav"}},
            ]}])
        return result.choices[0].message.content.strip()

    return cache.remember("reason.audio", model, live,
                          model=model, question=QUESTION, audio=audio)


def deploy_hint(account_hint: str) -> None:
    print("\n  Path B SKIPPED -- AUDIO_MODEL is not set in .env.\n")
    print("  Deploy an audio-capable model, then set AUDIO_MODEL. Note that the")
    print("  gpt-4o-*-audio-preview family is GONE from the current catalog; the")
    print("  successors are gpt-audio, gpt-audio-mini, and gpt-audio-1.5.\n")
    print("  Check what your account actually offers before you copy anything:\n")
    print(f"    az cognitiveservices account list-models -g <rg> -n {account_hint} \\")
    print("      --query \"[?contains(name,'audio')].[name,version]\" -o tsv\n")
    print("    az cognitiveservices account deployment create -g <rg> -n <account> \\")
    print("      --deployment-name gpt-audio-mini --model-name gpt-audio-mini \\")
    print("      --model-version 2025-12-15 --model-format OpenAI \\")
    print("      --sku-name GlobalStandard --sku-capacity 20\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Beat 3: transcript-then-text-model versus audio-straight-to-model.")
    parser.add_argument("--audio", default=str(OUT / "caller.wav"))
    parser.add_argument("--transcript-only", action="store_true",
                        help="run Path A alone")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    if args.no_cache:
        cache.ENABLED = False

    endpoint = os.getenv("FOUNDRY_ACCOUNT_ENDPOINT", "").strip()
    chat_model = os.getenv("CHAT_MODEL", "").strip()
    audio_model = os.getenv("AUDIO_MODEL", "").strip()
    region = os.getenv("SPEECH_REGION", "").strip()

    if not endpoint or not chat_model:
        raise SystemExit("[config] FOUNDRY_ACCOUNT_ENDPOINT and CHAT_MODEL are required.")

    audio_path = pathlib.Path(args.audio)
    if not audio_path.exists():
        raise SystemExit(
            f"[input] {audio_path} not found. Run Beat 2 first:\n"
            f"    uv run python m16_speech.py\n")
    audio = audio_path.read_bytes()

    from azure.identity import AzureCliCredential
    credential = AzureCliCredential()
    client = make_client(endpoint, credential)

    print("\n  Same caller, two architectures")
    print(f"    Path A  audio -> STT -> transcript -> {chat_model}   (2 calls)")
    print(f"    Path B  audio -> {audio_model or '<AUDIO_MODEL unset>'}"
          f"{' ' * max(0, len(chat_model) - len(audio_model or ''))}   (1 call)")
    print(f"    fixture : {audio_path.name}  ({len(audio):,} bytes)")

    # Path A leg one: the transcript. This hits the cache Beat 2 already filled,
    # so it costs nothing and stays byte-identical across takes.
    token = speech_token(credential)
    transcript, _ = transcribe(token, region, audio_path, TERMS, None, "on")

    print("\n" + "=" * 72)
    print(f"  PATH A  transcript -> {chat_model}")
    print("=" * 72)
    print(f"    the artifact Path B never produces:\n    \"{transcript}\"\n")
    answer_a, cached = reason_over_transcript(client, chat_model, transcript)
    for line in answer_a.splitlines():
        print(f"    {line}")
    print(f"    [{'cached' if cached else 'live'}]")

    if args.transcript_only or not audio_model:
        if not audio_model:
            deploy_hint("<account>")
        return 0

    print("\n" + "=" * 72)
    print(f"  PATH B  audio -> {audio_model}")
    print("=" * 72)
    answer_b, cached = reason_over_audio(client, audio_model, audio)
    for line in answer_b.splitlines():
        print(f"    {line}")
    print(f"    [{'cached' if cached else 'live'}]")

    print("\n  Two calls and a transcript, or one call and no transcript.")
    print("  That is the trade. Not accuracy -- ARTIFACTS and HOPS.")
    print("\n  And note what Path B did NOT do: she is synthesized at maximum")
    print("  'angry' intensity and says 'no rush' with obvious sarcasm. Neither")
    print("  audio model reported it. Multimodal is a capability, not a free")
    print("  upgrade in understanding. Measure it on your own audio.")

    print("\n" + "-" * 72)
    print(f"  {cache.summary()}")
    print("-" * 72 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
