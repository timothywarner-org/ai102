#!/usr/bin/env python
"""
AI-103 Lesson 13 - Beat 1: Multimodal chat with a vision-capable model.

Covers learning objectives:
  LO1  Analyze visual context by using multimodal models
  LO2  Produce concise OR detailed captions, for single OR multiple images
  LO3  Question-answering grounded in visual evidence
  LO4  Alt-text and extended descriptions aligned to accessibility guidelines

WHAT THIS DEMONSTRATES
----------------------
A "multimodal model" here is an ordinary chat-completions model that accepts an
image part inside the message content array. There is no separate vision API and
no separate vision endpoint - you send `{"type": "image_url", ...}` alongside
`{"type": "text", ...}` to the SAME /chat/completions route you already know.
That is the single most important idea in this beat: vision is a *message
shape*, not a different service.

Everything the model tells you is a generation, not a measurement. It does not
return bounding boxes, coordinates, or confidence scores. If you need
structured, schema-bound output, that is Content Understanding - see
m13_cu_analyzer.py. Knowing which tool answers which question is exam-relevant.

USAGE
-----
  # No Azure calls at all - prints every request payload it WOULD send.
  python m13_vision_chat.py --dry-run

  # All four passes against the default image from .env
  python m13_vision_chat.py

  # Point at a specific local image
  python m13_vision_chat.py --image ./assets/compass-chart.png

  # Just one pass
  python m13_vision_chat.py --pass caption-concise
  python m13_vision_chat.py --pass qa --question "How many red boxes are there?"

  # Multiple images in ONE call (LO2 "multiple images"); service cap is 10
  python m13_vision_chat.py --image a.jpg --image b.jpg --pass caption-concise

  # Low-detail mode: cheaper and faster, 512x512 downscale
  python m13_vision_chat.py --detail low

  # A publicly reachable URL instead of a local file
  python m13_vision_chat.py --image-url https://example.com/artifact.jpg

PREREQS
-------
  az login                      (keyless - AzureCliCredential, never Default*)
  cp .env.example .env          then edit FOUNDRY_ACCOUNT_ENDPOINT
  pip install -e .

GROUNDING
---------
  Vision-enabled chat models:
    https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/gpt-with-vision
  Limits used below: max 10 images per chat call, 20 MB per image,
  detail = auto | low | high.
"""

from __future__ import annotations

# --- Proxy scrub MUST happen before any Azure/OpenAI import -------------------
# Tim's box sets corporate proxy variables that intercept TLS to Azure hosts and
# surface as bewildering SSL / 407 errors mid-demo. The Azure SDKs and httpx both
# read these at CLIENT CONSTRUCTION time, so popping them after the import is too
# late. This is deliberately the first executable code in the file.
import os

for _proxy_var in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
):
    os.environ.pop(_proxy_var, None)

import argparse
import base64
import mimetypes
import sys
import textwrap
from pathlib import Path

from dotenv import load_dotenv

# override=True so that a value in .env WINS over a stale value already exported
# in the shell. Without this, a leftover FOUNDRY_ACCOUNT_ENDPOINT from a previous
# lesson silently takes precedence and you debug the wrong endpoint for 20 min.
load_dotenv(override=True)

from azure.identity import AzureCliCredential, get_bearer_token_provider  # noqa: E402
from openai import OpenAI  # noqa: E402

# -----------------------------------------------------------------------------
# Constants pulled straight from the service limits doc. We validate against
# these LOCALLY so a bad request fails in milliseconds with a readable message
# instead of costing a round trip and returning a 400 mid-recording.
# -----------------------------------------------------------------------------
MAX_IMAGES_PER_CALL = 10          # hard service cap
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB per image
VALID_DETAIL = ("auto", "low", "high")

# Azure AD scope for the Azure OpenAI data plane on the Foundry (v1) surface.
TOKEN_SCOPE = "https://ai.azure.com/.default"


# =============================================================================
# Client construction
# =============================================================================
def build_client() -> tuple[OpenAI, str]:
    """
    Return (client, deployment_name).

    Three choices here are non-obvious, and all three are exam-relevant. They
    match the Lesson 12 client exactly, on purpose - this is house style.

    1. AzureCliCredential, NOT DefaultAzureCredential. DefaultAzureCredential
       probes environment variables first, so a leftover AZURE_CLIENT_ID from
       another project silently hijacks the identity and you authenticate as
       something you did not intend. AzureCliCredential is deterministic: it is
       whoever `az login` says you are.

    2. The plain OpenAI client, NOT AzureOpenAI. AzureOpenAI always appends an
       `api-version` query parameter and the /openai/v1 path rejects it. The v1
       surface is versionless by design - the version moved into the URL.

    3. api_key gets a CALLABLE, not a token string. This is the one that bites
       you in production, and it was a real Lesson 12 defect.
       `get_bearer_token_provider` returns a FUNCTION, and the SDK invokes it
       before every single request, so the token is always fresh. Hand it
       `.token` (a plain string) instead and you freeze one token at
       construction time. Entra tokens are short-lived, so a static string dies
       mid-job - survivable for a fast caption, fatal for a long poll.

    The token audience is ai.azure.com, not cognitiveservices.azure.com. That
    trips people up because the resource is a Cognitive Services account under
    the covers, but the v1 data plane wants the AI Foundry audience.
    """
    account_endpoint = os.getenv("FOUNDRY_ACCOUNT_ENDPOINT", "").strip()
    deployment = os.getenv("CHAT_MODEL", "").strip()

    if not account_endpoint:
        raise SystemExit(
            "[config] FOUNDRY_ACCOUNT_ENDPOINT is not set.\n"
            "         Copy .env.example to .env and fill it in."
        )
    if not deployment:
        raise SystemExit("[config] CHAT_MODEL is not set (try: gpt-5-mini).")

    # Catch the #1 endpoint mistake before it becomes a bare 404. Chat and vision
    # live on the ACCOUNT openai.azure.com host - never the Content Understanding
    # host, and never the project-scoped /api/projects/... path.
    if "services.ai.azure.com" in account_endpoint:
        raise SystemExit(
            "[config] FOUNDRY_ACCOUNT_ENDPOINT points at the Content Understanding\n"
            "         host. Chat/vision lives on:\n"
            "           https://<account>.openai.azure.com\n"
            "         The two data planes are NOT interchangeable."
        )
    if "/api/projects/" in account_endpoint:
        raise SystemExit(
            "[config] Remove the /api/projects/... suffix. Model deployments live\n"
            "         on the ACCOUNT, not the project. The project-scoped path\n"
            "         returns a BARE 404 with an empty body."
        )

    token_provider = get_bearer_token_provider(AzureCliCredential(), TOKEN_SCOPE)

    client = OpenAI(
        base_url=f"{account_endpoint.rstrip('/')}/openai/v1",
        api_key=token_provider,  # a CALLABLE: the SDK refreshes it per request
        timeout=120.0,           # high-detail multi-image calls can be slow
        max_retries=2,
    )
    return client, deployment


# =============================================================================
# Image loading + validation
# =============================================================================
def encode_image_as_data_uri(path: Path) -> str:
    """
    Read a local image and return an RFC 2397 data URI.

    WHY BASE64 INSTEAD OF A URL
    ---------------------------
    Azure OpenAI requires that image URLs be PUBLICLY reachable - it fetches them
    server-side, so private endpoints, VNet-restricted blobs, and firewalled URLs
    all fail. In a classroom or on a locked-down corporate laptop that is a
    guaranteed dead end. Base64 sidesteps it: the bytes travel inside the request
    body, so nothing needs to be internet-reachable.

    The tradeoff is request size. Base64 inflates payloads roughly 4/3, and the
    20 MB per-image cap applies to the encoded image, so validate before sending.
    """
    if not path.exists():
        raise SystemExit(
            f"[image] Not found: {path}\n"
            f"        Drop a .jpg or .png there, or pass --image <path>."
        )

    size = path.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise SystemExit(
            f"[image] {path.name} is {size:,} bytes; the service cap is "
            f"{MAX_IMAGE_BYTES:,} bytes (20 MB).\n"
            f"        Resize it, or use --detail low."
        )
    if size == 0:
        raise SystemExit(f"[image] {path.name} is empty (0 bytes).")

    mime, _ = mimetypes.guess_type(path.name)
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        raise SystemExit(
            f"[image] Unsupported type for {path.name} (detected: {mime}).\n"
            f"        Vision chat accepts JPEG, PNG, GIF (first frame), WEBP."
        )

    # Pillow is a cheap pre-flight: a file can have a .jpg extension and still be
    # a corrupt download. Better to fail here than to burn a request.
    try:
        from PIL import Image

        with Image.open(path) as img:
            width, height = img.size
        print(f"  [image] {path.name}  {width}x{height}px  {size:,} bytes  {mime}")
    except ImportError:
        print(f"  [image] {path.name}  {size:,} bytes  {mime}  (pillow not installed)")
    except Exception as exc:  # noqa: BLE001 - any decode failure is fatal here
        raise SystemExit(f"[image] {path.name} could not be decoded: {exc}") from exc

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def build_image_parts(
    image_paths: list[Path], image_urls: list[str], detail: str
) -> list[dict]:
    """
    Turn local paths and/or public URLs into chat `image_url` content parts.

    Enforces the 10-image ceiling locally. Exceeding it server-side returns a
    400 that does not obviously name the cause, so we name it ourselves.
    """
    total = len(image_paths) + len(image_urls)
    if total == 0:
        raise SystemExit("[image] No images supplied. Use --image or --image-url.")
    if total > MAX_IMAGES_PER_CALL:
        raise SystemExit(
            f"[image] {total} images requested but the service allows at most "
            f"{MAX_IMAGES_PER_CALL} per chat call.\n"
            f"        Batch them, or summarize in two passes and merge the results."
        )

    parts: list[dict] = []
    for p in image_paths:
        # `detail` controls how the model tokenizes the image:
        #   low  -> single 512x512 pass. Cheap, fast, loses fine print.
        #   high -> tiles the image into 512x512 segments, ~2x tokens per tile.
        #   auto -> the service chooses based on image size.
        # For alt-text on a simple photo, low is often indistinguishable from
        # high at a fraction of the cost. For a chart full of tiny place names,
        # high is the difference between working and not.
        parts.append(
            {"type": "image_url", "image_url": {"url": encode_image_as_data_uri(p), "detail": detail}}
        )
    for u in image_urls:
        if not u.lower().startswith(("http://", "https://")):
            raise SystemExit(f"[image] --image-url must be absolute http(s): {u}")
        print(f"  [image] {u}  (server-side fetch - must be publicly reachable)")
        parts.append({"type": "image_url", "image_url": {"url": u, "detail": detail}})

    return parts


# =============================================================================
# The four passes
# =============================================================================
# Each pass is just a different SYSTEM prompt over the SAME image parts. That is
# the teaching point: one multimodal call shape, four business outcomes. The
# prompt is the product.

PASSES: dict[str, dict[str, str]] = {
    # ---- LO2: concise caption -------------------------------------------------
    "caption-concise": {
        "label": "Concise caption (LO2)",
        "system": (
            "You are an image captioning service. Return ONE sentence of at most "
            "20 words describing the single most important thing in the image. "
            "No preamble, no markdown, no trailing period commentary. "
            "Describe only what is visibly present."
        ),
        "user": "Caption this image.",
    },
    # ---- LO2: detailed caption ------------------------------------------------
    "caption-detailed": {
        "label": "Detailed caption (LO2)",
        "system": (
            "You are an image captioning service producing a rich descriptive "
            "paragraph. Cover, in this order: the overall scene, the primary "
            "subjects and their spatial arrangement, notable colors and "
            "materials, any legible text, and the apparent setting. "
            "Aim for 80-150 words. Describe only what is visibly present; do not "
            "speculate about intent, brand, price, or anything off-frame."
        ),
        "user": "Describe this image in detail.",
    },
    # ---- LO3: grounded question answering ------------------------------------
    "qa": {
        "label": "Grounded visual Q&A (LO3)",
        "system": (
            "You answer questions strictly from visual evidence in the supplied "
            "image(s). Rules:\n"
            "1. Answer ONLY from what is visible. Never use outside knowledge.\n"
            "2. After the answer, add a line 'Evidence:' citing the specific "
            "visual details that justify it (position, color, text, shape).\n"
            "3. If the image does not contain enough information, reply exactly "
            "'NOT VISIBLE IN IMAGE' and briefly say what would be needed.\n"
            "4. Never guess counts. If occlusion makes an exact count impossible, "
            "say so and give a range."
        ),
        "user": "",  # supplied by --question
    },
    # ---- LO4: accessibility ---------------------------------------------------
    "alt-text": {
        "label": "Alt-text + extended description (LO4)",
        "system": (
            "You generate accessibility text following WCAG guidance.\n"
            "Return exactly two labeled sections and nothing else:\n"
            "\n"
            "ALT-TEXT: A single sentence under 125 characters conveying the "
            "image's PURPOSE in context. Do not begin with 'Image of', 'Picture "
            "of', or 'Graphic of' - screen readers already announce the element "
            "role, so those words waste the listener's time. No trailing period "
            "is required.\n"
            "\n"
            "EXTENDED DESCRIPTION: A longer description, 100-200 words, for a "
            "reader who cannot see the image at all and needs the same "
            "information a sighted reader gets. Use plain language, describe "
            "spatial relationships explicitly (left/right/above/below), and "
            "transcribe any legible text verbatim in quotes.\n"
            "\n"
            "If the image is purely decorative and conveys no information, "
            "return ALT-TEXT: \"\" (empty) and explain why in the extended "
            "description."
        ),
        "user": "Generate accessibility text for this image.",
    },
}


def run_pass(
    client: OpenAI,
    deployment: str,
    pass_name: str,
    image_parts: list[dict],
    question: str | None,
    dry_run: bool,
) -> None:
    """Execute (or, in dry-run, merely print) a single captioning pass."""
    spec = PASSES[pass_name]
    user_text = question if pass_name == "qa" else spec["user"]

    if pass_name == "qa" and not user_text:
        raise SystemExit("[args] --pass qa requires --question \"...\"")

    print()
    print("=" * 78)
    print(f"  {spec['label']}")
    print("=" * 78)

    # Content array order matters more than people expect: putting the TEXT
    # first and the image(s) after generally yields better instruction-following,
    # because the model reads the task before it reads the pixels.
    messages = [
        {"role": "system", "content": spec["system"]},
        {"role": "user", "content": [{"type": "text", "text": user_text}, *image_parts]},
    ]

    if dry_run:
        print("  [dry-run] No Azure call made. Request that WOULD be sent:")
        print(f"  [dry-run]   model            : {deployment}")
        print(f"  [dry-run]   image parts      : {len(image_parts)} "
              f"(cap {MAX_IMAGES_PER_CALL})")
        for i, part in enumerate(image_parts, start=1):
            url = part["image_url"]["url"]
            shown = url if url.startswith("http") else f"{url[:48]}... ({len(url):,} chars)"
            print(f"  [dry-run]   image[{i}]        : detail="
                  f"{part['image_url'].get('detail', 'auto')}  {shown}")
        print("  [dry-run]   system prompt    :")
        for line in textwrap.wrap(spec["system"], width=68):
            print(f"  [dry-run]     {line}")
        print(f"  [dry-run]   user text        : {user_text!r}")
        return

    try:
        response = client.chat.completions.create(model=deployment, messages=messages)
    except Exception as exc:  # noqa: BLE001 - we re-raise after triage
        _triage(exc)
        raise

    choice = response.choices[0]

    # finish_reason is the tell for truncation and for content filtering. Read it
    # before you read the text, or you will demo a half-sentence and blame the model.
    if choice.finish_reason == "content_filter":
        print("  [filtered] Azure content safety blocked this response.")
        print("             Try a different image, or review the filter policy")
        print("             on the deployment in the Foundry portal.")
        return
    if choice.finish_reason == "length":
        print("  [warn] Output hit the token ceiling and was truncated.")

    print()
    print(choice.message.content)
    print()

    usage = response.usage
    if usage:
        # Image tokens land in prompt_tokens. Run the same image at detail=low
        # and detail=high and watch this number move - that is the cost lever.
        print(
            f"  [usage] prompt={usage.prompt_tokens:,}  "
            f"completion={usage.completion_tokens:,}  total={usage.total_tokens:,}"
        )
    print(f"  [finish] {choice.finish_reason}")


def _triage(exc: Exception) -> None:
    """Map the failures that actually happen to the fix that actually works."""
    text = str(exc)
    status = getattr(exc, "status_code", None)

    print()
    print("  [error] The call failed. Triage:")

    if status == 401 or "401" in text:
        print("  [401] Unauthorized - the token was rejected.")
        print("        - Run: az login   (and az account set --subscription <id>)")
        print("        - Confirm role 'Cognitive Services OpenAI User' on the account.")
        print("        - Confirm the token scope is https://ai.azure.com/.default")
    elif status == 403 or "403" in text:
        print("  [403] Authenticated but not authorized.")
        print("        You are signed in as the wrong principal, or the role")
        print("        assignment has not propagated yet (allow ~5 minutes).")
        print("        Check with: az account show --query user.name -o tsv")
    elif status == 404 or "404" in text:
        print("  [404] Not found - almost always endpoint or deployment shape.")
        print("        - base_url MUST end with /openai/v1")
        print("        - A BARE 404 with an empty body means the project-scoped")
        print("          /api/projects/... path. Use the *.openai.azure.com host.")
        print("        - The model name must be the DEPLOYMENT name, not the")
        print("          model family name. Verify in the Foundry portal.")
    elif status == 429 or "429" in text:
        print("  [429] Rate limited / quota exceeded.")
        print("        - Wait and retry; honor the Retry-After header.")
        print("        - Vision requests are token-heavy: switch --detail high")
        print("          to --detail low, or send fewer images per call.")
        print("        - Raise TPM for the deployment in the Foundry portal.")
    elif "content_filter" in text or "ResponsibleAI" in text:
        print("  [filter] The REQUEST was blocked by content safety before")
        print("           inference. The image or prompt tripped a category.")
    elif "InvalidImage" in text or "image" in text.lower():
        print("  [image] The service rejected the image itself.")
        print("          Check format (JPEG/PNG/GIF/WEBP), size (<=20 MB), and")
        print("          that any --image-url is PUBLICLY reachable.")
    else:
        print("  [??] Unrecognized failure. Full text below.")

    print(f"  [raw] {text[:600]}")
    print()


# =============================================================================
# Entry point
# =============================================================================
def main() -> int:
    parser = argparse.ArgumentParser(
        description="AI-103 L13 Beat 1 - multimodal vision chat (LO1-LO4).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the exact requests without calling Azure. Zero cost, zero auth.",
    )
    parser.add_argument(
        "--image",
        action="append",
        default=[],
        metavar="PATH",
        help="Local image file. Repeat for multiple images (max 10 total).",
    )
    parser.add_argument(
        "--image-url",
        action="append",
        default=[],
        metavar="URL",
        help="Publicly reachable image URL. Repeat for multiple.",
    )
    parser.add_argument(
        "--pass",
        dest="pass_name",
        choices=[*PASSES.keys(), "all"],
        default="all",
        help="Which pass to run. Default: all four, in order.",
    )
    parser.add_argument(
        "--question",
        default="What navigational instrument is shown, and what can you tell me about the chart beneath it?",
        help="Question for the grounded Q&A pass (LO3).",
    )
    parser.add_argument(
        "--detail",
        choices=VALID_DETAIL,
        default="auto",
        help="Image fidelity: low (512x512, cheap) | high (tiled, costly) | auto.",
    )
    args = parser.parse_args()

    print()
    print("AI-103 Lesson 13 | Beat 1 | Multimodal vision chat")
    print("-" * 78)

    image_paths = [Path(p) for p in args.image]
    image_urls = list(args.image_url)

    # Fall back to the .env default only when nothing was passed explicitly.
    if not image_paths and not image_urls:
        default_image = os.getenv("DEMO_IMAGE_PATH", "").strip()
        if not default_image:
            raise SystemExit(
                "[args] No image supplied and DEMO_IMAGE_PATH is unset in .env.\n"
                "       Use --image <path> or --image-url <url>."
            )
        image_paths = [Path(default_image)]

    if args.dry_run:
        # In dry-run we still read and validate local files - that is most of the
        # value. What we do NOT do is contact Azure or acquire a token, so this
        # runs on a plane with no credentials configured.
        print("  [mode] DRY RUN - no Azure calls, no token acquisition")
        deployment = os.getenv("CHAT_MODEL", "gpt-5-mini")
        client = None
    else:
        print("  [mode] LIVE")
        client, deployment = build_client()
        print(f"  [auth] AzureCliCredential -> {TOKEN_SCOPE}")
        print(f"  [endpoint] {os.getenv('FOUNDRY_ACCOUNT_ENDPOINT')}/openai/v1")
        print(f"  [model] {deployment}")

    image_parts = build_image_parts(image_paths, image_urls, args.detail)
    print(f"  [detail] {args.detail}")

    selected = list(PASSES.keys()) if args.pass_name == "all" else [args.pass_name]
    for name in selected:
        run_pass(client, deployment, name, image_parts, args.question, args.dry_run)

    print()
    print("-" * 78)
    print(f"  [done] {len(selected)} pass(es) over {len(image_parts)} image(s).")
    print("  [note] Captions and answers are GENERATED text, not measurements.")
    print("         No bounding boxes, no coordinates, no confidence scores.")
    print("         For schema-bound structured output, see m13_cu_analyzer.py.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
