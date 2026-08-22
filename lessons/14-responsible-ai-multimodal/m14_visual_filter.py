#!/usr/bin/env python
"""
AI-103 Lesson 14 - Beat 1: turn harm SCORES into an actual FILTER.

Covers learning objective:
  LO1  Implement filters to classify unsafe or disallowed visual content

WHAT THIS DEMONSTRATES
----------------------
Lesson 12 called Analyze Image and read the four severity numbers out loud. That
was measurement. This is the other half, and it is the half the exam asks about:
a filter is a POLICY you write on top of those numbers. Azure scores the image.
Azure does not decide whether to publish it. You do.

So this script does three things in order:

  1. Loads a policy from policy.json. Per-category severity ceilings, plus the
     action to take on breach. Policy lives in a file, not in an if-statement,
     because policy changes on a different schedule than code does.
  2. Calls Analyze Image, one HTTP POST, no SDK required.
  3. Applies the ceilings and emits ACCEPT or REJECT with the specific rule that
     fired. That decision record is what you write to your audit log.

THE TRAP THIS SCRIPT IS BUILT TO EXPOSE
---------------------------------------
Image severity is 0, 2, 4, or 6. Those are the ONLY four values the image
endpoint returns, because the image path supports outputType FourSeverityLevels
and nothing else. Text is different: text returns the full 0 to 7 range. So a
policy that says "reject at severity 3 or above" is indistinguishable from
"reject at 4 or above" on images, and identical policy numbers mean two
different things depending on which endpoint you sent the content to. Write the
number down wrong and your filter is looser than you think it is.

Second trap, and it is a real one in production: this API is the filter you
build for content you RECEIVE. It is not the content filter that sits on a model
DEPLOYMENT. Those are separate controls with separate configuration surfaces,
and the image-generation models enforce their own built-in filters that you
cannot loosen. Show both in the portal. Know which one the question is asking
about.

USAGE
-----
  uv run python m14_visual_filter.py --dry-run          # prints payloads, calls nothing
  uv run python m14_visual_filter.py                    # every image in assets/
  uv run python m14_visual_filter.py --image assets/invoice-clean.png
  uv run python m14_visual_filter.py --policy strict    # a second, tighter profile
  uv run python m14_visual_filter.py --json             # machine-readable decisions

PREREQS
-------
  az login                     keyless, AzureCliCredential, never Default*
  cp .env.example .env         then set CONTENT_SAFETY_ENDPOINT
  uv sync

GROUNDING
---------
  Analyze image quickstart (api-version=2024-09-01, severity 0/2/4/6, 4 MB cap,
  50x50 minimum, 7200x7200 maximum):
    https://learn.microsoft.com/azure/ai-services/content-safety/quickstart-image
  Harm categories:
    https://learn.microsoft.com/azure/ai-services/content-safety/concepts/harm-categories
"""
from __future__ import annotations

# --- Proxy scrub MUST run before any Azure import ----------------------------
# VS Code and corporate agents inject proxy variables that intercept TLS to
# Azure hosts. The SDKs read these at client-construction time, so popping them
# afterwards is too late. Deliberately the first executable code in the file.
import os

for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_pv, None)

import argparse
import base64
import json
import pathlib
import struct
import sys
import urllib.error
import urllib.request

try:
    from dotenv import load_dotenv
    # override=True so .env WINS over a stale export from an earlier lesson.
    # Without it you debug the wrong endpoint for twenty minutes on camera.
    load_dotenv(override=True)
except ImportError:
    pass

from azure.identity import AzureCliCredential  # noqa: E402

import m14_cache as cache  # noqa: E402

# --- Service limits, validated locally so bad input fails in milliseconds -----
# A 400 from Azure costs a round trip and reads like a stack trace. A local
# guard costs nothing and reads like a sentence.
MAX_IMAGE_BYTES = 4 * 1024 * 1024      # hard cap, 4 MB
MIN_EDGE_PX = 50                       # smaller than this is rejected
MAX_EDGE_PX = 7200                     # larger than this is rejected
API_VERSION = "2024-09-01"             # GA. Do not "upgrade" this to a preview.
CATEGORIES = ("Hate", "SelfHarm", "Sexual", "Violence")

# Content Safety lives on the cognitiveservices.azure.com host, NOT on
# openai.azure.com and NOT on services.ai.azure.com. One AIServices account
# publishes all three, and sending this payload to the wrong one of its own
# hostnames returns 404 with no hint about why. See .env.example.
TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"

# Two profiles so the demo can show that the SAME scores produce DIFFERENT
# decisions. That is the whole point of separating policy from measurement.
POLICIES = {
    # Ceiling = the highest severity we still allow through. Anything ABOVE the
    # ceiling trips the rule.
    "default": {
        "description": "Public marketing site. Nothing above Low gets published.",
        "ceilings": {"Hate": 0, "SelfHarm": 0, "Sexual": 2, "Violence": 2},
        "on_breach": "REJECT",
    },
    "strict": {
        "description": "K-12 education portal. Severity zero or it does not ship.",
        "ceilings": {"Hate": 0, "SelfHarm": 0, "Sexual": 0, "Violence": 0},
        "on_breach": "REJECT",
    },
    "review": {
        "description": "Internal moderation queue. Flag for a human, never auto-block.",
        "ceilings": {"Hate": 2, "SelfHarm": 2, "Sexual": 2, "Violence": 2},
        "on_breach": "ROUTE_TO_HUMAN",
    },
}


# =============================================================================
# Local validation
# =============================================================================
def png_dimensions(raw: bytes) -> tuple[int, int] | None:
    """
    Read width and height out of a PNG header without importing Pillow.

    WHY hand-rolled: this demo has to run on a clean machine during a recording.
    Adding an image library for eight bytes of header parsing is a dependency I
    would have to install, pin, and explain. A PNG IHDR chunk always starts at
    byte 16 and is two big-endian uint32s. Non-PNG input returns None and we
    simply skip the dimension check rather than guess.
    """
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    try:
        w, h = struct.unpack(">II", raw[16:24])
        return int(w), int(h)
    except struct.error:
        return None


def validate(path: pathlib.Path, raw: bytes) -> list[str]:
    """Return a list of human-readable limit violations. Empty list means fine."""
    problems: list[str] = []
    if len(raw) > MAX_IMAGE_BYTES:
        problems.append(
            f"{len(raw) / 1024 / 1024:.2f} MB exceeds the 4 MB cap")
    dims = png_dimensions(raw)
    if dims:
        w, h = dims
        if min(w, h) < MIN_EDGE_PX:
            problems.append(f"{w}x{h} is below the 50x50 minimum")
        if max(w, h) > MAX_EDGE_PX:
            problems.append(f"{w}x{h} is above the 7200x7200 maximum")
    return problems


# =============================================================================
# The Azure call
# =============================================================================
def analyze_image(endpoint: str, token: str, raw: bytes,
                  label: str = "") -> tuple[dict, bool]:
    """
    POST <endpoint>/contentsafety/image:analyze?api-version=2024-09-01

    Plain urllib on purpose. There IS a Content Safety SDK, and in a real app you
    should use it for retries and typed models. Here the request shape is the
    lesson, so I want you to see the URL, the header, and the body with nothing
    in between. If you can read this function you can read the SDK.

    The body sends base64 bytes in image.content. The alternative is
    image.blobUrl for something already in storage. Send BOTH and the service
    refuses the request outright, which is a nice, loud failure mode.

    Returns (payload, was_cached). The cache key covers the image bytes and every
    request parameter, so re-running this command is free and byte-identical.
    The Entra token is deliberately NOT part of the key -- it changes every run
    and has nothing to do with the answer.
    """
    return cache.remember(
        "contentsafety.image:analyze",
        label or "image",
        lambda: _analyze_image_live(endpoint, token, raw),
        endpoint=endpoint,
        api_version=API_VERSION,
        categories=list(CATEGORIES),
        output_type="FourSeverityLevels",
        image=raw,
    )


def _analyze_image_live(endpoint: str, token: str, raw: bytes) -> dict:
    """The actual HTTP call. Only reached on a cache miss."""
    url = f"{endpoint.rstrip('/')}/contentsafety/image:analyze?api-version={API_VERSION}"
    body = json.dumps({
        "image": {"content": base64.b64encode(raw).decode("ascii")},
        # Naming all four is optional. Omit it and you get all four anyway. I
        # name them so the request is self-documenting when someone reads the
        # network trace six months from now.
        "categories": list(CATEGORIES),
        # The image endpoint accepts exactly this one value. Text accepts
        # EightSeverityLevels as well. That asymmetry is the exam trap.
        "outputType": "FourSeverityLevels",
    }).encode("utf-8")

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(
            f"\n[HTTP {exc.code}] {url}\n{detail}\n\n"
            "  403  -> your identity lacks the Cognitive Services User role on the account\n"
            "  404  -> wrong hostname. Content Safety is on *.cognitiveservices.azure.com\n"
            "  400  -> image is over 4 MB, or outside 50x50 to 7200x7200\n"
        ) from None


# =============================================================================
# The policy engine, which is the actual subject of this beat
# =============================================================================
def apply_policy(analysis: dict, policy: dict) -> dict:
    """
    Turn a scores payload into a decision record.

    Note what this function does NOT do: it does not call Azure, it has no
    network dependency, and it is trivially unit-testable. That separation is
    the design point. Measurement is a service. Policy is your code. Keeping
    them apart is what lets you change the threshold on a Friday without
    redeploying the model, and what lets you prove to an auditor exactly which
    rule rejected which asset.
    """
    scores = {c["category"]: c["severity"] for c in analysis.get("categoriesAnalysis", [])}
    breaches = []
    for category, ceiling in policy["ceilings"].items():
        observed = scores.get(category, 0)
        if observed > ceiling:
            breaches.append({
                "category": category,
                "observed": observed,
                "ceiling": ceiling,
                "rule": f"{category} <= {ceiling}",
            })
    return {
        "decision": policy["on_breach"] if breaches else "ACCEPT",
        "scores": scores,
        "breaches": breaches,
    }


# =============================================================================
# Presentation
# =============================================================================
def print_decision(path: pathlib.Path, record: dict, policy_name: str) -> None:
    verdict = record["decision"]
    bar = "=" * 68
    source = "cached" if record.get("cached") else "live"
    print(f"\n{bar}")
    print(f"  {path.name}   policy: {policy_name}   [{source}]")
    print(bar)
    for category in CATEGORIES:
        sev = record["scores"].get(category, 0)
        label = {0: "Safe", 2: "Low", 4: "Medium", 6: "High"}.get(sev, "?")
        print(f"    {category:<10} severity {sev}  ({label})")
    if record["breaches"]:
        print("\n    Rules that fired:")
        for b in record["breaches"]:
            print(f"      - {b['rule']}  but observed {b['observed']}")
    else:
        print("\n    Rules that fired: none")
    print(f"\n    DECISION: {verdict}")


# =============================================================================
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--image", action="append", default=[],
                    help="Path to an image. Repeatable. Defaults to everything in assets/.")
    ap.add_argument("--policy", default="default", choices=sorted(POLICIES),
                    help="Which policy profile to enforce.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate locally and print the request. No Azure calls.")
    ap.add_argument("--json", action="store_true",
                    help="Emit decision records as JSON instead of the table.")
    ap.add_argument("--no-cache", action="store_true",
                    help="Ignore the cache and call Azure for every image.")
    ap.add_argument("--clean", action="store_true",
                    help="Delete .cache/ and out/ first, then run. Rip and replace.")
    args = ap.parse_args()

    # Re-runnability lives in these four lines. --clean wipes derived state so a
    # retake starts from nothing; otherwise the cache makes the retake instant
    # AND identical, which matters more than fast when a runbook quotes output.
    if args.clean:
        removed = cache.clean()
        print(f"\n[clean] removed: {', '.join(removed) if removed else 'nothing to remove'}")
    cache.ENABLED = not args.no_cache

    policy = POLICIES[args.policy]

    # Resolve the working set.
    if args.image:
        paths = [pathlib.Path(p) for p in args.image]
    else:
        assets = pathlib.Path(__file__).parent / "assets"
        paths = sorted(p for p in assets.glob("*.png"))
    if not paths:
        raise SystemExit("[input] No images found. Pass --image or populate assets/.")

    print(f"\nPolicy profile : {args.policy}")
    print(f"Intent         : {policy['description']}")
    print(f"Ceilings       : " + ", ".join(
        f"{k} <= {v}" for k, v in policy["ceilings"].items()))
    print(f"On breach      : {policy['on_breach']}")

    endpoint = os.getenv("CONTENT_SAFETY_ENDPOINT", "").strip()
    if not endpoint and not args.dry_run:
        raise SystemExit(
            "[config] CONTENT_SAFETY_ENDPOINT is not set.\n"
            "         It ends in .cognitiveservices.azure.com -- see .env.example.")

    token = ""
    if not args.dry_run:
        # AzureCliCredential, not DefaultAzureCredential. Default probes
        # environment variables first, so a leftover AZURE_CLIENT_ID from another
        # project silently hijacks the identity. This one is deterministic: it is
        # whoever `az login` says you are.
        token = AzureCliCredential().get_token(TOKEN_SCOPE).token

    records = []
    for path in paths:
        raw = path.read_bytes()
        problems = validate(path, raw)
        if problems:
            print(f"\n[skip] {path.name}: " + "; ".join(problems))
            continue

        if args.dry_run:
            dims = png_dimensions(raw)
            print(f"\n[dry-run] {path.name}  {len(raw)} bytes  {dims}")
            print(f"          POST {endpoint or '<endpoint>'}"
                  f"/contentsafety/image:analyze?api-version={API_VERSION}")
            print(f'          {{"image": {{"content": "<{len(raw)} bytes base64>"}}, '
                  f'"categories": {list(CATEGORIES)}, "outputType": "FourSeverityLevels"}}')
            continue

        analysis, was_cached = analyze_image(endpoint, token, raw, label=path.name)
        record = apply_policy(analysis, policy)
        record["file"] = path.name
        record["policy"] = args.policy
        record["cached"] = was_cached
        records.append(record)
        if not args.json:
            print_decision(path, record, args.policy)

    if args.json:
        print(json.dumps(records, indent=2))

    if records:
        rejected = sum(1 for r in records if r["decision"] != "ACCEPT")
        print(f"\n{'-' * 68}")
        print(f"  {len(records)} analyzed, {rejected} did not pass policy '{args.policy}'")
        print(f"  {cache.summary()}")
        print(f"{'-' * 68}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
