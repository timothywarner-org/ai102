#!/usr/bin/env python
"""
AI-103 Lesson 15 - Beat 3: Translator or a model, and what each one costs.

Covers learning objective:
  LO3  Build solutions that translate text by using Azure Translator in Foundry
       Tools or LLM-powered translation flows

WHAT THIS DEMONSTRATES
----------------------
The same sentence, translated two ways, billed on two different units. That is
not a footnote, it is the architecture decision.

  Translator  bills CHARACTERS, counted per target language
  a model     bills TOKENS, input and output

Those units do not convert cleanly, so nobody can eyeball which is cheaper for a
given workload. This script prints both meters side by side on your own text.

It also shows the terminology ladder, which is where translation projects
actually live:

  detect         free. Skip the translation entirely when the text is already
                 in the target language.
  plain          Translator with no customization.
  dictionary     <mstrans:dictionary> markup. Case-sensitive, requires an
                 explicit source language, and Microsoft says it is only safe
                 for compound nouns like personal and product names.
  model          an LLM told to preserve the term, which works and costs tokens.

The product name in assets/release-note.txt exists to be mangled. The product is
called "Dispatch", which collides with an ordinary noun, so plain Translator
renders it "Le dispatch" in French and "Die Leitstelle" in German. Then the
dictionary pins it. Both runs are verified live.

Do not "improve" this to a snappier invented name. CamelCase brands like
ShipSense Pro or FleetPulse are read as proper nouns and survive untouched,
which makes the dictionary look like it does nothing.

AUTH NOTE, READ THIS BEFORE YOU RECORD
--------------------------------------
Translator on a multi-service Foundry resource is NOT the same auth shape as
Content Safety or Language. With Microsoft Entra ID you must send three things:

    Authorization: Bearer <token>
    Ocp-Apim-Subscription-Region: <your resource region>
    Ocp-Apim-ResourceId: <full ARM resource id of the account>

Drop the region or the resource id and you get a 401 that reads like a bad
token. Set TRANSLATOR_REGION and TRANSLATOR_RESOURCE_ID in .env.

USAGE
-----
  uv run python m15_translate.py --dry-run
  uv run python m15_translate.py                          # release note -> fr, de
  uv run python m15_translate.py --to fr --to ja
  uv run python m15_translate.py --no-dictionary          # watch the product name drift
  uv run python m15_translate.py --model-only             # skip Translator entirely

GROUNDING
---------
  Translator auth incl. Entra ID headers:
    https://learn.microsoft.com/azure/ai-services/translator/text-translation/reference/authentication
  Character billing, counted per target language:
    https://learn.microsoft.com/azure/ai-services/translator/service-limits
  Dynamic dictionary:
    https://learn.microsoft.com/azure/ai-services/translator/text-translation/how-to/use-dynamic-dictionary
"""
from __future__ import annotations

import os

for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_pv, None)

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from azure.identity import AzureCliCredential, get_bearer_token_provider  # noqa: E402
from openai import OpenAI  # noqa: E402

import m15_cache as cache  # noqa: E402

TRANSLATOR_SCOPE = "https://cognitiveservices.azure.com/.default"
AOAI_SCOPE = "https://ai.azure.com/.default"
TRANSLATOR_HOST = "https://api.cognitive.microsofttranslator.com"
API_VERSION = "3.0"

# The term that must survive translation. In a real shop this list is owned by
# Brand and is stored in a file they review, not in your source.
#
# WHY "Dispatch" AND NOT AN INVENTED CAMELCASE NAME: current Translator reads
# CamelCase as a proper-noun signal and passes those names through untouched, so
# a ShipSense Pro / FleetPulse style term makes the dictionary look like a no-op.
# Forty such candidates were probed live and none were localized. A brand that
# collides with an ordinary noun is the case that genuinely still breaks.
PROTECTED_TERMS = ["Dispatch"]


def protect(text: str, terms: list[str]) -> str:
    """
    Wrap each protected term in dynamic dictionary markup.

    Microsoft's guidance is blunt about the limits: this is case-sensitive, it
    needs an explicit `from` language rather than autodetect, and it is only
    safe for compound nouns. Past a few dozen terms, Custom Translator is the
    right answer instead. Say that out loud rather than implying this scales.
    """
    for term in terms:
        text = text.replace(
            term, f'<mstrans:dictionary translation="{term}">{term}</mstrans:dictionary>')
    return text


# =============================================================================
def translator_headers(token: str) -> dict:
    region = os.getenv("TRANSLATOR_REGION", "").strip()
    resource_id = os.getenv("TRANSLATOR_RESOURCE_ID", "").strip()
    if not region or not resource_id:
        raise SystemExit(
            "[config] Translator over Entra ID needs TRANSLATOR_REGION and "
            "TRANSLATOR_RESOURCE_ID. See .env.example and the AUTH NOTE at the "
            "top of this file.")
    return {
        "Authorization": f"Bearer {token}",
        "Ocp-Apim-Subscription-Region": region,
        "Ocp-Apim-ResourceId": resource_id,
        "Content-Type": "application/json",
    }


def _post(path: str, params: dict, body, headers: dict):
    url = f"{TRANSLATOR_HOST}{path}?{urllib.parse.urlencode(params, doseq=True)}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(
            f"\n[HTTP {exc.code}] {url}\n{detail}\n\n"
            f"401 here is usually a MISSING HEADER, not a bad token. Translator "
            f"on a multi-service resource needs Ocp-Apim-Subscription-Region and "
            f"Ocp-Apim-ResourceId alongside the Bearer token.\n") from exc


def detect_language(token: str, text: str) -> tuple[dict, bool]:
    """Detect is free. Worth saying out loud: this call costs nothing."""
    def live():
        return _post("/detect", {"api-version": API_VERSION},
                     [{"Text": text}], translator_headers(token))[0]
    return cache.remember("translator.detect", "detect", live, text=text)


def translate(token: str, text: str, to: list[str], frm: str | None) -> tuple[list, bool]:
    params = {"api-version": API_VERSION, "to": to}
    if frm:
        params["from"] = frm          # dynamic dictionary REQUIRES an explicit from
    def live():
        return _post("/translate", params, [{"Text": text}],
                     translator_headers(token))[0]["translations"]
    return cache.remember("translator.translate", ",".join(to), live,
                          text=text, to=to, frm=frm)


def translate_with_model(client: OpenAI, model: str, text: str,
                         to: str, terms: list[str]) -> tuple[dict, bool]:
    instruction = (
        f"Translate the text below into {to}. Preserve the following product "
        f"names exactly as written, untranslated: {', '.join(terms)}. Keep the "
        f"marketing tone. Return only the translation, with no commentary."
    )
    def live():
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": f"{instruction}\n\n---\n{text}\n---"}],
        )
        usage = resp.usage
        return {
            "text": resp.choices[0].message.content.strip(),
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
        }
    return cache.remember("model.translate", to, live,
                          model=model, instruction=instruction, text=text, to=to)


# =============================================================================
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--file", default="assets/release-note.txt")
    ap.add_argument("--to", action="append", default=[])
    ap.add_argument("--no-dictionary", action="store_true",
                    help="Skip the mstrans:dictionary markup and watch the term drift.")
    ap.add_argument("--model-only", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.clean:
        removed = cache.clean()
        print(f"\n[clean] removed: {', '.join(removed) if removed else 'nothing'}")
    cache.ENABLED = not args.no_cache

    targets = args.to or ["fr", "de"]
    here = pathlib.Path(__file__).parent
    path = (here / args.file) if not pathlib.Path(args.file).is_absolute() \
        else pathlib.Path(args.file)

    print("\n  Translator or a model")
    print(f"    source file       : {path.name}")
    print(f"    target languages  : {', '.join(targets)}")
    print(f"    protected terms   : {PROTECTED_TERMS}")
    print(f"    dictionary markup : {'off (--no-dictionary)' if args.no_dictionary else 'on'}")

    if args.dry_run:
        print("\n[dry-run] no calls made")
        print(f"  detect    -> POST {TRANSLATOR_HOST}/detect          (free)")
        print(f"  translate -> POST {TRANSLATOR_HOST}/translate       (billed per character x target)")
        print( "  model     -> POST <foundry>/openai/v1/chat/completions  (billed per token)")
        print(f"    would read {path.name}  {'ok' if path.exists() else 'MISSING'}")
        return 0

    if not path.exists():
        raise SystemExit(f"[input] {path} not found. Run assets/make_assets.py first.")
    text = path.read_text(encoding="utf-8").strip()

    foundry = os.getenv("FOUNDRY_ACCOUNT_ENDPOINT", "").strip()
    model = os.getenv("CHAT_MODEL", "").strip()
    credential = AzureCliCredential()

    chars = len(text)
    print(f"\n  Source is {chars} characters.")

    if not args.model_only:
        token = credential.get_token(TRANSLATOR_SCOPE).token

        detected, cached = detect_language(token, text)
        print(f"\n  DETECT   language={detected.get('language')} "
              f"score={detected.get('score')}   cost: none   "
              f"[{'cached' if cached else 'live'}]")

        payload = text if args.no_dictionary else protect(text, PROTECTED_TERMS)
        frm = None if args.no_dictionary else detected.get("language", "en")
        results, cached = translate(token, payload, targets, frm)

        print(f"\n  TRANSLATOR   [{'cached' if cached else 'live'}]")
        for item in results:
            body = item.get("text", "")
            kept = all(t in body for t in PROTECTED_TERMS)
            print(f"    -> {item.get('to')}   product name preserved: "
                  f"{'YES' if kept else 'NO'}")
            print(f"       {body[:150]}")
        billed = chars * len(targets)
        print(f"\n    BILLED: {chars} characters x {len(targets)} target languages "
              f"= {billed} characters")
        print( "    Detect and BreakSentence are free. Translate is not.")

    if foundry and model:
        client = OpenAI(base_url=f"{foundry.rstrip('/')}/openai/v1",
                        api_key=get_bearer_token_provider(credential, AOAI_SCOPE))
        print(f"\n  MODEL")
        for to in targets:
            out, cached = translate_with_model(client, model, text, to, PROTECTED_TERMS)
            kept = all(t in out["text"] for t in PROTECTED_TERMS)
            print(f"    -> {to}   product name preserved: {'YES' if kept else 'NO'}"
                  f"   [{'cached' if cached else 'live'}]")
            print(f"       {out['text'][:150]}")
            print(f"       BILLED: {out['prompt_tokens']} prompt + "
                  f"{out['completion_tokens']} completion tokens")
    else:
        print("\n  [skip] model path: set FOUNDRY_ACCOUNT_ENDPOINT and CHAT_MODEL")

    print(f"\n{'-' * 72}")
    print("  Characters versus tokens. Two meters, two units, and they do not")
    print("  convert. Measure on your own content before you choose.")
    print(f"  {cache.summary()}\n{'-' * 72}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
