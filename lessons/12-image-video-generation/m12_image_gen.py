"""m12_image_gen.py -- text to image with gpt-image-2 on a Foundry account.

    uv run python m12_image_gen.py
    uv run python m12_image_gen.py --prompt "..." --size 1536x1024 --quality high
    uv run python m12_image_gen.py --dry-run     # validate + print the request, call nothing

Beat 1 of Lesson 12, covering LO1: "Implement a solution that generates images
from text prompts and reference media."

Three things here are worth more than the code itself:

  * The base_url is the ACCOUNT endpoint, not the project endpoint. Image and
    video model deployments live on the account, not under /api/projects/<name>.
    Point this at a project endpoint and you get a bare 404 with no error body,
    which reads like a broken deployment but is really a wrong path. See
    .env.example for the full endpoint matrix we tested.

  * gpt-image-2 ALWAYS returns base64, never a URL. The older DALL-E surface let
    you ask for `response_format="url"` and hand that URL to a browser. That
    option does not exist here, so every caller decodes bytes and owns the
    storage decision. That is a better default anyway: no expiring link, no
    accidental public blob.

  * Image deployments are throttled in REQUESTS per minute, not tokens per
    minute. This one is provisioned at 2 requests / 60 s. The service tolerated a
    burst of four in testing, so treat that as a floor, not a wall -- and the 429
    handler below explains itself rather than dumping a stack trace.
"""
from __future__ import annotations

import argparse
import base64
import os
import pathlib
import sys
import time

# VS Code's integrated terminal injects proxy vars on some setups; strip them so
# httpx doesn't fail with "getaddrinfo failed" against public Azure endpoints.
# This has to happen BEFORE the openai import, because httpx reads the
# environment when it builds its default transport.
for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_pv, None)

from azure.identity import AzureCliCredential, get_bearer_token_provider  # noqa: E402
from openai import OpenAI                          # noqa: E402

try:
    from dotenv import load_dotenv
    # override=True on purpose. A stale IMAGE_MODEL exported in an earlier shell
    # session silently wins over .env otherwise, and you spend twenty minutes
    # debugging a DeploymentNotFound against a name that isn't in your .env file.
    load_dotenv(override=True)
except ImportError:  # dotenv is convenience only; real env vars still work.
    pass

# --- Configuration -----------------------------------------------------------
# Config comes from .env, never hardcoded. An earlier cut of this course carried a
# real endpoint as a fallback, and when that account was deleted the "fallback"
# quietly pointed every reader at a resource that no longer exists. Failing loudly
# with a pointer to .env.example is far kinder than a confusing auth error.
ACCOUNT_ENDPOINT = os.environ.get("FOUNDRY_ACCOUNT_ENDPOINT")
if not ACCOUNT_ENDPOINT:
    sys.exit(
        "ERROR: FOUNDRY_ACCOUNT_ENDPOINT is not set.\n"
        "  -> https://<account>.openai.azure.com   (ACCOUNT endpoint, not the project endpoint)\n"
        "  See .env.example, then: cp .env.example .env"
    )
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-2")

# gpt-image-2 accepts one square and two rectangular aspect ratios, plus "auto".
# Validating locally turns a 400 from the service into an instant, readable error.
VALID_SIZES = ("1024x1024", "1024x1536", "1536x1024", "auto")
VALID_QUALITY = ("low", "medium", "high", "auto")

# Deliberately object-only: no people, no faces, no logos, no trademarked
# characters. Lesson 12's video half runs on Sora 2, whose content filter rejects
# reference images containing a human face, so the whole lesson stays on subjects
# that survive both filters and can be re-shot on any take.
DEFAULT_PROMPT = (
    "A vintage brass ship's compass resting on a weathered paper nautical chart, "
    "warm morning light raking in from the left, shallow depth of field, "
    "top-down product photograph on a dark walnut table. No people, no text, no logos."
)

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"


def build_client() -> OpenAI:
    """Return a plain OpenAI client bound to the Foundry ACCOUNT /openai/v1 surface.

    Three choices in here are non-obvious and all three are exam-relevant:

    1. AzureCliCredential, not DefaultAzureCredential. DefaultAzureCredential
       probes environment variables first, so a leftover AZURE_CLIENT_ID from
       some other project silently hijacks the identity and you authenticate as
       something you did not intend. AzureCliCredential is deterministic: it is
       whoever `az login` says you are.

    2. The plain OpenAI client, not AzureOpenAI. AzureOpenAI always appends an
       `api-version` query parameter, and the /openai/v1 path rejects it. The v1
       surface is versionless by design; the version moved into the URL.

    3. api_key gets a CALLABLE, not a token string. This is the one that bites
       you in production. `get_bearer_token_provider` returns a function, and the
       SDK calls it before every single request, so the token is always fresh.
       Hand it `.token` instead -- a plain string -- and you have frozen one
       token at client-construction time. Entra access tokens are short-lived
       (the Azure CLI hands back a cached one that can have well under an hour
       left), so a static string dies mid-job: the image demos are quick enough
       to get away with it, but a Sora poll runs for minutes and a 401 lands
       halfway through a render you already paid for. Learn's v1 guidance is
       explicit about this -- pass the provider "instead of using a static API
       key" -- and it is the reason the v1 OpenAI() client no longer needs the
       AzureOpenAI() client just to refresh tokens.

    The token audience is ai.azure.com, not cognitiveservices.azure.com. That
    trips people up because the resource is a Cognitive Services account under
    the covers, but the v1 data plane wants the AI Foundry audience.
    """
    token_provider = get_bearer_token_provider(
        AzureCliCredential(), "https://ai.azure.com/.default"
    )
    return OpenAI(
        base_url=f"{ACCOUNT_ENDPOINT.rstrip('/')}/openai/v1",
        api_key=token_provider,      # a CALLABLE: the SDK refreshes it per request
        timeout=300.0,      # high-quality 1536x1024 renders comfortably exceed 60s
        max_retries=2,
    )


def is_content_filter(msg: str) -> bool:
    """True when this error is the documented Azure content-filter shape.

    Read the substrings carefully, because the obvious version of this check is
    wrong. Learn documents the error code as `contentFilter` -- ONE word, no
    underscore, no space -- so testing for "content filter" or for
    "content_policy" misses it completely and you fall through to a raw
    traceback on the single most likely failure in an image demo. We match the
    Azure code, the OpenAI-style code, and the message text.
    """
    low = msg.lower()
    return "contentfilter" in low or "content_policy" in low or "safety system" in low


def explain_content_filter(msg: str) -> None:
    """Print the right advice for WHICH filter fired. There are two, and the
    correct response to them is opposite.

      * Prompt blocked -- "Your task failed as a result of our safety system."
        The request never reached the model. Re-word it; retrying is pointless.

      * Output blocked -- "Generated image was filtered as a result of our
        safety system." Your prompt was fine. The finished image tripped the
        OUTPUT filter. Generation is non-deterministic, so re-running the very
        same prompt often succeeds.

    Telling a learner to re-word a prompt that was never the problem sends them
    rewriting good input for twenty minutes, which is why this split matters.
    """
    low = msg.lower()
    if "generated image was filtered" in low:
        print("ERROR: your PROMPT was accepted -- the finished IMAGE tripped the filter.")
        print("       Nothing is wrong with your wording. Re-run as-is; image generation")
        print("       is non-deterministic and the same prompt often passes on a retry.")
    else:
        print("ERROR: the PROMPT was blocked before generation started.")
        print("       Re-word toward objects and scenery; drop people, faces, brands, and")
        print("       named characters. Re-running the same prompt will not help.")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate an image from a text prompt with gpt-image-2.")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT, help="Text prompt. Keep it IP-clean and face-free.")
    ap.add_argument("--size", default="1024x1024", choices=VALID_SIZES)
    ap.add_argument("--quality", default="high", choices=VALID_QUALITY)
    ap.add_argument("--n", type=int, default=1, help="How many images to generate (1-4).")
    ap.add_argument("--out", default=None, help="Output path. Defaults to out/l12-image-01.png.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate arguments and print the request. Make no Azure calls.")
    args = ap.parse_args()

    # Validate before spending a request. n is capped locally because the service
    # counts each image against the 2 RPM budget and a typo'd --n 40 is an
    # expensive way to learn that.
    if not 1 <= args.n <= 4:
        ap.error("--n must be between 1 and 4")
    if not args.prompt.strip():
        ap.error("--prompt cannot be empty")
    return args


def main() -> int:
    args = parse_args()
    out_path = pathlib.Path(args.out) if args.out else OUT_DIR / "l12-image-01.png"

    print("=" * 72)
    print("AI-103 L12 Beat 1 -- text to image (LO1)")
    print("=" * 72)
    print(f"  endpoint : {ACCOUNT_ENDPOINT.rstrip('/')}/openai/v1")
    print(f"  model    : {IMAGE_MODEL}")
    print(f"  size     : {args.size}   quality: {args.quality}   n: {args.n}")
    print(f"  output   : {out_path}")
    print(f"  prompt   : {args.prompt}")
    print()

    if args.dry_run:
        print("[dry-run] Arguments valid. No Azure call made.")
        return 0

    client = build_client()

    started = time.perf_counter()
    try:
        result = client.images.generate(
            model=IMAGE_MODEL,
            prompt=args.prompt,
            n=args.n,
            size=args.size,
            quality=args.quality,
        )
    except Exception as exc:                                    # noqa: BLE001
        # Narrow, human-readable triage instead of a traceback. Each of these is
        # a failure we actually hit while building this lesson.
        msg = str(exc)
        if "429" in msg:
            print("ERROR: rate limited. gpt-image-2 is deployed at 2 requests per MINUTE here.")
            print("       Wait 30-60 seconds and re-run, or raise the deployment capacity.")
        elif "404" in msg:
            print("ERROR: 404. This is almost always the wrong base_url, not a missing deployment.")
            print(f"       You used: {ACCOUNT_ENDPOINT.rstrip('/')}/openai/v1")
            print("       Images live on the ACCOUNT endpoint. If your URL contains /api/projects/,")
            print("       that is the bug -- see the endpoint matrix in .env.example.")
        elif is_content_filter(msg):
            explain_content_filter(msg)
        else:
            print(f"ERROR: {type(exc).__name__}: {msg[:500]}")
        return 1
    elapsed = time.perf_counter() - started

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    saved = []
    for i, item in enumerate(result.data):
        # There is NO url option on gpt-image-2. b64_json is the only transport,
        # so decoding is not optional plumbing -- it is the API contract.
        image_bytes = base64.b64decode(item.b64_json)
        p = out_path if i == 0 else out_path.with_name(f"{out_path.stem}-{i + 1}{out_path.suffix}")
        p.write_bytes(image_bytes)
        saved.append(p)
        print(f"  [saved] {p.name}  {len(image_bytes):,} bytes")

    print()
    print(f"  [time]  {elapsed:.1f}s for {len(saved)} image(s)")
    usage = getattr(result, "usage", None)
    if usage is not None:
        # gpt-image-2 bills input tokens (your prompt) and output tokens (the
        # image itself). Worth saying on camera: an image is priced in tokens.
        print(f"  [usage] {usage}")
    print()
    print(f"Done. Open {saved[0]} to review, then feed it to m12_image_edit.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
