"""m12_image_edit.py -- mask-based inpainting against the /openai/v1/images/edits endpoint.

    uv run python m12_image_edit.py
    uv run python m12_image_edit.py --dry-run          # build the mask, call nothing
    uv run python m12_image_edit.py --region 0.05,0.05,0.45,0.45 --prompt "..."

Beat 2 of Lesson 12, covering LO3: "Configure image-editing workflows, including
inpainting, mask-based edits, and prompt-driven modifications."

The one idea this demo exists to make undeniable:

    IN A MASK, TRANSPARENT MEANS EDITABLE.

Alpha 0 marks the region the model is allowed to repaint. Alpha 255 is protected
and comes back untouched. Everybody gets this backwards the first time, because
"masking something off" in everyday English means protecting it, and here the
transparent hole is the opposite -- it is the opening you cut so the model can
reach through. So we generate the mask in code, save it next to the result, and
print the exact pixel counts, rather than shipping a mystery PNG.

Two more things that are easy to get wrong:

  * This endpoint is multipart/form-data, NOT JSON. You are uploading files, so
    there is no `{"image": "<base64>"}` body here. The SDK handles the encoding,
    but it matters the moment you drop to curl or Postman.
  * The mask must have exactly the same pixel dimensions as the source. A
    1024x1024 source with a 1023x1024 mask is a 400, and the message you get
    back is not especially forthcoming. We assert it locally instead.

Service limits worth knowing: source under 50 MB, PNG or JPG; mask under 4 MB
and must be PNG, because JPG has no alpha channel to carry the hole.
"""
from __future__ import annotations

import argparse
import base64
import os
import pathlib
import sys
import time

for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_pv, None)

from azure.identity import AzureCliCredential, get_bearer_token_provider  # noqa: E402
from openai import OpenAI                          # noqa: E402
from PIL import Image                              # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)      # see m12_image_gen.py for why override=True
except ImportError:
    pass

ACCOUNT_ENDPOINT = os.environ.get("FOUNDRY_ACCOUNT_ENDPOINT")
if not ACCOUNT_ENDPOINT:
    sys.exit(
        "ERROR: FOUNDRY_ACCOUNT_ENDPOINT is not set.\n"
        "  -> https://<account>.openai.azure.com   (ACCOUNT endpoint, not the project endpoint)\n"
        "  See .env.example, then: cp .env.example .env"
    )
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-2")

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
DEFAULT_SOURCE = OUT_DIR / "l12-image-01.png"

# Service-documented ceilings. Checked locally so a bad input fails in
# milliseconds with a sentence you can act on, not in seconds with an HTTP 400.
MAX_SOURCE_BYTES = 50 * 1024 * 1024
MAX_MASK_BYTES = 4 * 1024 * 1024
ALLOWED_SOURCE_SUFFIXES = (".png", ".jpg", ".jpeg")
VALID_QUALITY = ("low", "medium", "high", "auto")

# gpt-image-2 accepts arbitrary output resolutions, but only on a grid: BOTH edges
# must be a multiple of 16 pixels. The edit endpoint renders at the source's own
# dimensions, so an off-grid source image is a 400 -- and the service message does
# not name the constraint. We check it here and name the nearest legal size.
SIZE_GRID = 16

# Upper-right quadrant of the frame, expressed as fractions of width/height so
# the same numbers work whatever size the source turned out to be.
DEFAULT_REGION = "0.55,0.06,0.96,0.47"

DEFAULT_PROMPT = (
    "In the cleared upper-right area, add a small polished brass sextant lying flat "
    "on the same weathered nautical chart, lit by the same warm morning light from the left "
    "and casting a soft shadow to the right. Match the existing grain, focus, and colour. "
    "No people, no text, no logos."
)


def nearest_on_grid(value: int) -> int:
    """Nearest multiple of 16 that is still a usable edge length."""
    return max(SIZE_GRID, round(value / SIZE_GRID) * SIZE_GRID)


def check_size_grid(width: int, height: int) -> bool:
    """Return True if the source can be rendered as-is; else explain the fix.

    This is the difference between "HTTP 400: Invalid value for size" and a
    sentence that tells you the exact number to resize to.
    """
    if width % SIZE_GRID == 0 and height % SIZE_GRID == 0:
        return True
    good_w, good_h = nearest_on_grid(width), nearest_on_grid(height)
    print(f"ERROR: gpt-image-2 needs both edges to be a multiple of {SIZE_GRID} px.")
    print(f"       Your source is {width}x{height}; the nearest valid size is {good_w}x{good_h}.")
    print("       The edit endpoint renders at the source's own dimensions, so resize first:")
    print(f'         uv run python -c "from PIL import Image; im=Image.open(\'SRC\'); '
          f'im.resize(({good_w},{good_h})).save(\'SRC\')"')
    print("       Images produced by m12_image_gen.py are always on-grid already.")
    return False


def parse_region(raw: str) -> tuple[float, float, float, float]:
    """Parse 'x0,y0,x1,y1' as fractions of the image, and sanity check the box."""
    try:
        x0, y0, x1, y1 = (float(v) for v in raw.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "--region wants four comma-separated fractions: x0,y0,x1,y1 (e.g. 0.55,0.06,0.96,0.47)"
        ) from exc
    for v in (x0, y0, x1, y1):
        if not 0.0 <= v <= 1.0:
            raise argparse.ArgumentTypeError(f"--region values must be between 0 and 1, got {v}")
    if x1 <= x0 or y1 <= y0:
        raise argparse.ArgumentTypeError("--region must be x0<x1 and y0<y1 (top-left then bottom-right)")
    return x0, y0, x1, y1


def build_mask(source_path: pathlib.Path, region: tuple[float, float, float, float],
               mask_path: pathlib.Path) -> tuple[Image.Image, int, int]:
    """Write an RGBA PNG the same size as the source, with alpha 0 over `region`.

    Returns (mask image, editable pixel count, protected pixel count).

    Note what is NOT happening here: we are not painting the region white, or
    black, or magenta. Colour is irrelevant to a mask. The service reads the
    ALPHA channel and nothing else, which is why the mask has to be PNG -- JPEG
    cannot carry alpha at all, so a "JPEG mask" is a mask with no hole in it.
    """
    with Image.open(source_path) as src:
        width, height = src.size

    # Start fully opaque: alpha 255 everywhere means "protect the entire image."
    mask = Image.new("RGBA", (width, height), (0, 0, 0, 255))

    x0 = int(region[0] * width)
    y0 = int(region[1] * height)
    x1 = int(region[2] * width)
    y1 = int(region[3] * height)

    # Punch the hole. (0,0,0,0) -- the RGB is arbitrary, the trailing 0 alpha is
    # the entire point. Everything inside this box becomes fair game for the model.
    hole = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    mask.paste(hole, (x0, y0))

    mask_path.parent.mkdir(parents=True, exist_ok=True)
    mask.save(mask_path, format="PNG")

    editable = (x1 - x0) * (y1 - y0)
    return mask, editable, width * height - editable


def build_client() -> OpenAI:
    """Plain OpenAI client on the ACCOUNT /openai/v1 surface. See m12_image_gen.py.

    api_key gets the CALLABLE returned by get_bearer_token_provider, not a token
    string, so the SDK re-fetches a fresh token before every request instead of
    freezing one at construction time. See m12_image_gen.py for the full why.
    """
    token_provider = get_bearer_token_provider(
        AzureCliCredential(), "https://ai.azure.com/.default"
    )
    return OpenAI(
        base_url=f"{ACCOUNT_ENDPOINT.rstrip('/')}/openai/v1",
        api_key=token_provider,      # a CALLABLE: the SDK refreshes it per request
        timeout=300.0,
        max_retries=2,
    )


def is_content_filter(msg: str) -> bool:
    """True when this error is the documented Azure content-filter shape.

    Learn documents the code as `contentFilter` -- one word, no underscore, no
    space -- so the obvious tests for "content filter" and "content_policy" both
    MISS it and you get a raw traceback instead. Match the code, the
    OpenAI-style code, and the message text.
    """
    low = msg.lower()
    return "contentfilter" in low or "content_policy" in low or "safety system" in low


def explain_content_filter(msg: str) -> None:
    """Two filters, opposite fixes. Prompt-blocked means re-word; output-blocked
    means the prompt was fine and a plain re-run usually works.
    """
    low = msg.lower()
    if "generated image was filtered" in low:
        print("ERROR: your PROMPT was accepted -- the finished IMAGE tripped the filter.")
        print("       Nothing is wrong with your wording. Re-run as-is; image generation")
        print("       is non-deterministic and the same prompt often passes on a retry.")
    else:
        print("ERROR: the edit PROMPT was blocked before generation started.")
        print("       Keep it to objects; drop people, faces, brands, and named characters.")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Mask-based image edit (inpainting) with gpt-image-2.")
    ap.add_argument("--source", default=str(DEFAULT_SOURCE),
                    help="Source image to edit. Defaults to the output of m12_image_gen.py.")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT, help="What to paint into the transparent region.")
    ap.add_argument("--quality", default="high", choices=VALID_QUALITY,
                    help="Render quality. Set explicitly rather than inherited from a default.")
    ap.add_argument("--region", default=DEFAULT_REGION, type=parse_region,
                    help="Editable box as fractions: x0,y0,x1,y1. Default is the upper-right quadrant.")
    ap.add_argument("--out", default=None, help="Output path. Defaults to out/l12-image-02-edited.png.")
    ap.add_argument("--mask-out", default=None, help="Where to write the generated mask PNG.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Build and save the mask, report the pixel split, make no Azure call.")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    source = pathlib.Path(args.source).expanduser().resolve()
    out_path = pathlib.Path(args.out) if args.out else OUT_DIR / "l12-image-02-edited.png"
    mask_path = pathlib.Path(args.mask_out) if args.mask_out else OUT_DIR / "l12-image-02-mask.png"

    print("=" * 72)
    print("AI-103 L12 Beat 2 -- mask-based edit / inpainting (LO3)")
    print("=" * 72)

    # --- Validate the source before touching the network -----------------------
    if not source.exists():
        print(f"ERROR: source image not found: {source}")
        print("       Run m12_image_gen.py first, or pass --source <path>.")
        return 1
    if source.suffix.lower() not in ALLOWED_SOURCE_SUFFIXES:
        print(f"ERROR: source must be PNG or JPG, got '{source.suffix}'.")
        return 1
    source_bytes = source.stat().st_size
    if source_bytes > MAX_SOURCE_BYTES:
        print(f"ERROR: source is {source_bytes / 1e6:.1f} MB; the service limit is 50 MB.")
        return 1

    with Image.open(source) as probe:
        src_w, src_h = probe.size

    print(f"  endpoint : {ACCOUNT_ENDPOINT.rstrip('/')}/openai/v1  (POST /images/edits, multipart/form-data)")
    print(f"  model    : {IMAGE_MODEL}")
    print(f"  source   : {source.name}  {src_w}x{src_h}  {source_bytes:,} bytes")
    print(f"  quality  : {args.quality}")

    # Fail on the size grid BEFORE building a mask or spending a request.
    if not check_size_grid(src_w, src_h):
        return 1

    # --- Build the mask --------------------------------------------------------
    mask, editable_px, protected_px = build_mask(source, args.region, mask_path)
    mask_bytes = mask_path.stat().st_size
    total_px = editable_px + protected_px

    print(f"  mask     : {mask_path.name}  {mask.size[0]}x{mask.size[1]}  {mask_bytes:,} bytes")
    print(f"             alpha=0   (EDITABLE)  {editable_px:,} px  {editable_px / total_px:6.1%}")
    print(f"             alpha=255 (protected) {protected_px:,} px  {protected_px / total_px:6.1%}")
    print(f"  region   : x0,y0,x1,y1 = {args.region}")
    print(f"  output   : {out_path}")
    print(f"  prompt   : {args.prompt}")
    print()

    # The dimension check that saves you from an opaque 400.
    if mask.size != (src_w, src_h):
        print(f"ERROR: mask {mask.size} does not match source ({src_w}, {src_h}). They must be identical.")
        return 1
    if mask_bytes > MAX_MASK_BYTES:
        print(f"ERROR: mask is {mask_bytes / 1e6:.1f} MB; the service limit is 4 MB.")
        return 1

    if args.dry_run:
        print(f"[dry-run] Mask written to {mask_path}. No Azure call made.")
        print("[dry-run] Open it in an image viewer: the checkerboard area is the hole the")
        print("[dry-run] model paints into. Everything solid is protected.")
        return 0

    client = build_client()

    started = time.perf_counter()
    try:
        # Files are opened in binary and passed straight through. The SDK builds
        # the multipart body; there is no base64 on the way IN, only on the way OUT.
        with source.open("rb") as image_fh, mask_path.open("rb") as mask_fh:
            result = client.images.edit(
                model=IMAGE_MODEL,
                image=image_fh,
                mask=mask_fh,
                prompt=args.prompt,
                n=1,
                size=f"{src_w}x{src_h}",
                quality=args.quality,
            )
    except Exception as exc:                                    # noqa: BLE001
        msg = str(exc)
        if "429" in msg:
            print("ERROR: rate limited. gpt-image-2 is deployed at 2 requests per MINUTE here.")
            print("       If you just ran m12_image_gen.py, wait ~30s and re-run this one.")
        elif "404" in msg:
            print("ERROR: 404 -- wrong base_url, not a missing deployment. Images live on the")
            print("       ACCOUNT endpoint; a /api/projects/ path in your URL is the bug.")
        elif is_content_filter(msg):
            explain_content_filter(msg)
        else:
            print(f"ERROR: {type(exc).__name__}: {msg[:500]}")
        return 1
    elapsed = time.perf_counter() - started

    # Same contract as generation: base64 only, no URL.
    image_bytes = base64.b64decode(result.data[0].b64_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(image_bytes)

    print(f"  [saved] {out_path.name}  {len(image_bytes):,} bytes")
    print(f"  [time]  {elapsed:.1f}s")
    usage = getattr(result, "usage", None)
    if usage is not None:
        print(f"  [usage] {usage}")
    print()
    print("Compare the two files side by side. The protected 90-odd percent should be")
    print("recognisably the same photograph; only the transparent box changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
