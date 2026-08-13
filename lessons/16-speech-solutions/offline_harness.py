#!/usr/bin/env python
"""
AI-103 Lesson 16 - offline checks on the parts that can be checked offline.

    uv run python offline_harness.py

READ THIS BEFORE YOU TRUST IT
-----------------------------
An earlier version of this harness asserted that requests were WELL FORMED and
reported nine green checks. Every one of them passed while the demo was broken,
because a well-formed request and a request Azure honours are different claims.
Specifically: a `Phrase-List` header was constructed, asserted, and shipped. No
such header exists. Azure accepted the request and silently ignored it.

So this file no longer pretends to validate the API surface. It tests PURE
FUNCTIONS only -- string builders and local logic -- and it says plainly what it
cannot reach:

    NOT TESTED HERE, ONLY BY validate.ps1 AGAINST LIVE AZURE
      * whether TTS accepts the SSML and returns audio
      * whether the recognizer honours the phrase list
      * whether TranslationRecognizer connects and returns both languages
      * whether the audio model accepts the input_audio content part
      * every string printed on screen during the demo

The rule this cost us: an assertion about YOUR OWN request proves nothing about
the SERVICE. Only a live call does that.
"""
from __future__ import annotations

import sys

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


def main() -> int:
    print("\n  Offline checks -- pure functions only. See the module docstring.\n")

    from m16_speech import build_ssml, scorecard, SCRIPT, TERMS
    from m16_translate_speech import register

    # --- SSML construction -------------------------------------------------
    styled = build_ssml("hello", "en-US-AriaNeural", "angry", "2")
    check("SSML declares the mstts namespace when a style is used",
          "xmlns:mstts=" in styled,
          "without it the service silently ignores express-as")
    check("SSML wraps the text in express-as with the style and degree",
          "<mstts:express-as style='angry' styledegree='2'>hello</mstts:express-as>" in styled)
    check("SSML names the voice", "name='en-US-AriaNeural'" in styled)

    flat = build_ssml("hello", "en-US-AriaNeural", None, "2")
    check("SSML omits express-as when no style is requested",
          "express-as" not in flat)

    # --- the composite Speech token ----------------------------------------
    import os
    import m16_speech

    class FakeToken:
        token = "ENTRA"

    class FakeCredential:
        def get_token(self, _scope):
            return FakeToken()

    os.environ["SPEECH_RESOURCE_ID"] = "/subscriptions/x/resourceGroups/y/providers/z"
    composite = m16_speech.speech_token(FakeCredential())
    check("regional Speech token is aad#<resourceId>#<token>",
          composite == "aad#/subscriptions/x/resourceGroups/y/providers/z#ENTRA",
          composite)
    check("composite token is NOT a bare bearer token",
          not composite.startswith("ENTRA"))

    os.environ["SPEECH_RESOURCE_ID"] = ""
    try:
        m16_speech.speech_token(FakeCredential())
        check("missing SPEECH_RESOURCE_ID fails loudly", False, "no exception raised")
    except SystemExit:
        check("missing SPEECH_RESOURCE_ID fails loudly", True)

    # --- the fixture is built to break -------------------------------------
    check("fixture contains the out-of-vocabulary product name",
          "ShipSense Pro" in SCRIPT)
    check("fixture minimizes in words, so Beat 3 has something to contrast",
          "no rush" in SCRIPT.lower() and "it's fine" in SCRIPT.lower())
    check("scored terms are the three in the script",
          all(t in SCRIPT for t in TERMS))

    # --- scorecard ---------------------------------------------------------
    check("scorecard counts a mangled term as missing",
          scorecard("the Ship Sense Pro dashboard", ["ShipSense Pro"]).startswith("0/1"))
    check("scorecard counts a repaired term as intact",
          scorecard("the ShipSense Pro dashboard", ["ShipSense Pro"]).startswith("1/1"))

    # --- register detection (Beat 4's automatic callout) --------------------
    check("register detects informal French and German",
          "INFORMAL" in register("Quand tu as un moment. Wann immer du einen Moment hast."))
    check("register detects formal French and German",
          "FORMAL" in register("Quand vous aurez un moment. Wenn Sie mal Zeit haben.")
          and "INFORMAL" not in register("Quand vous aurez un moment. Wenn Sie mal Zeit haben."))
    check("register reports mixed rather than guessing",
          "MIXED" in register("Quand tu as un moment. Wenn Sie mal Zeit haben."))

    # --- cache round trip --------------------------------------------------
    import m16_cache

    m16_cache.clean(also_out=False)
    calls = {"n": 0}

    def compute() -> bytes:
        calls["n"] += 1
        return b"AUDIO-BYTES"

    first, cached_first = m16_cache.remember("t.tts", "x", compute, a=1)
    second, cached_second = m16_cache.remember("t.tts", "x", compute, a=1)
    check("cold call computes, warm call replays",
          calls["n"] == 1 and not cached_first and cached_second)
    check("cached audio round-trips byte-identical through base64",
          first == second == b"AUDIO-BYTES")

    third, cached_third = m16_cache.remember("t.tts", "x", compute, a=2)
    check("changing any input part misses the cache",
          calls["n"] == 2 and not cached_third)
    m16_cache.clean(also_out=False)

    print(f"\n  {CHECKS - len(FAILURES)}/{CHECKS} passed\n")
    if FAILURES:
        print("  FAILED: " + ", ".join(FAILURES) + "\n")
        return 1
    print("  These prove the local logic. They prove NOTHING about Azure.")
    print("  Run:  pwsh -File validate.ps1\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
