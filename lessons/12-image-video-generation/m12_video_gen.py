"""m12_video_gen.py -- text to video with Sora 2: create, poll, download.

    uv run python m12_video_gen.py
    uv run python m12_video_gen.py --seconds 8 --size 1280x720
    uv run python m12_video_gen.py --dry-run     # validate + print the request, call nothing

Beat 3 of Lesson 12, covering LO2: "Implement a solution that generates videos
from text prompts and reference media."

This is the beat where the shape of the API changes, and that is the lesson.
Image generation is one synchronous call: you wait a few seconds and get bytes.
Video generation is a JOB. You create it, you get an id and a status back
immediately, and then you poll. Same SDK, same client, completely different
programming model -- and if you write video code as though it were image code,
you will build something that blocks a web request for two minutes and times out
behind a load balancer.

So the polling loop below is deliberately loud. Every tick prints the elapsed
time, the status, and the service-reported progress, because that transition
from `queued` to `in_progress` to `completed` IS the concept.

Statuses on this surface: queued, in_progress, completed, failed. We also guard
`cancelled`, which the platform can return even though nothing in this demo
cancels anything -- an unhandled terminal status is an infinite loop, and an
infinite loop on camera is a bad day.

Sora 2 constraints that shape what you can demo:
  * TWO concurrent jobs per account. A third create is rejected while two run.
  * Renders EXPIRE AFTER 24 HOURS. Download in the same session; do not plan to
    fetch yesterday's video id.
  * The content filter blocks photorealistic people and recognizable IP, and
    rejects any reference image containing a human face. Objects and stylized
    animation are the safe lane, which is why the default prompt lives there.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys
import time

for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_pv, None)

from azure.identity import AzureCliCredential, get_bearer_token_provider  # noqa: E402
from openai import OpenAI                          # noqa: E402

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
VIDEO_MODEL = os.environ.get("VIDEO_MODEL", "sora-2")

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
# m12_video_remix.py reads this so the two beats chain without you copy-pasting
# an id off the screen mid-take.
LAST_ID_FILE = OUT_DIR / "last_video_id.txt"

TERMINAL_STATUSES = ("completed", "failed", "cancelled")
VALID_SECONDS = ("4", "8", "12")
# Azure Sora 2 documents exactly two output resolutions: portrait and landscape.
# The openai package's VideoSize type is wider than this because it also covers
# OpenAI's own platform, where 1024x1792 and 1792x1024 are legal. They are NOT
# supported on Azure Sora 2, so they are deliberately absent here -- offering a
# choice that 400s at the service is worse than not offering it.
VALID_SIZES = ("720x1280", "1280x720")

DEFAULT_PROMPT = (
    "A stylized 3D-animated paper sailboat drifting across a calm turquoise lagoon at sunrise. "
    "Gentle ripples spread behind it, the camera pushes in slowly and steadily. "
    "Soft golden light, pastel colour palette. No people, no text, no logos."
)


def build_client() -> OpenAI:
    """Plain OpenAI client on the ACCOUNT /openai/v1 surface.

    Identical construction to the image demos, which is the point worth making
    out loud: images and video are the same client, the same auth, the same
    base_url. Only the resource (`client.images` vs `client.videos`) and the
    execution model differ.

    The token provider matters MORE here than it does for images, and this is the
    place to say so on camera. api_key gets a callable, so the SDK fetches a fresh
    token before each request. Freeze a token string instead and it is fine for a
    six-second image call but genuinely dangerous for video: this script will sit
    in its polling loop for minutes, and an Entra token that expires mid-render
    turns into a 401 on a retrieve() call for a video you have already paid for.
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
    MISS it. Match the code, the OpenAI-style code, and the message text.
    """
    low = msg.lower()
    return "contentfilter" in low or "content_policy" in low or "safety system" in low


def explain_content_filter(msg: str) -> None:
    """Two filters, opposite fixes."""
    low = msg.lower()
    if "generated video was filtered" in low or "generated image was filtered" in low:
        print("ERROR: your PROMPT was accepted -- the finished RENDER tripped the filter.")
        print("       Nothing is wrong with your wording. Re-run as-is; generation is")
        print("       non-deterministic and the same prompt often passes on a retry.")
    else:
        print("ERROR: the PROMPT was blocked before rendering started. Sora rejects")
        print("       photorealistic people and recognizable IP outright, and rejects any")
        print("       reference image with a human face. Move to objects or animation.")


def triage(exc: Exception, *, phase: str) -> None:
    """One error table for every call in this script: create, poll, and download.

    Video fails the same handful of ways wherever it fails, and a 401 twelve
    minutes into a poll deserves the same readable sentence as a 401 on the
    create call. Factoring this out is not tidiness -- it is why the poll loop
    below can afford to guard itself instead of throwing a traceback on camera.
    """
    msg = str(exc)
    low = msg.lower()
    if "AttributeError" in type(exc).__name__ or "has no attribute 'videos'" in msg:
        print("ERROR: your openai package predates the videos API.")
        print("       Fix: uv add 'openai>=2.44.0'   (or pip install --upgrade openai)")
    elif "401" in msg or "invalid_token" in low or "expired" in low:
        print(f"ERROR: 401 during {phase} -- the access token was rejected.")
        print("       Mid-poll, this almost always means the token expired while the")
        print("       render ran. build_client() passes a token PROVIDER precisely so the")
        print("       SDK refreshes per request; if that was changed back to a static")
        print("       token string, restore it. Otherwise your CLI session lapsed:")
        print("       run `az login` and try again.")
    elif "429" in msg:
        print(f"ERROR: rate limited during {phase}, or at the concurrency ceiling.")
        print("       Sora 2 allows TWO concurrent jobs per account. Let them finish.")
    elif "404" in msg:
        print(f"ERROR: 404 during {phase} -- wrong base_url. Video lives on the ACCOUNT")
        print("       endpoint; a /api/projects/ path in your URL is the bug.")
    elif is_content_filter(msg):
        explain_content_filter(msg)
    else:
        print(f"ERROR: {type(exc).__name__} during {phase}: {msg[:500]}")


def render_bar(pct: int, width: int = 24) -> str:
    filled = max(0, min(width, round(width * pct / 100)))
    return "[" + "#" * filled + "." * (width - filled) + "]"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate a video from a text prompt with Sora 2.")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT, help="Text prompt. No people, no faces, no IP.")
    ap.add_argument("--seconds", default="4", choices=VALID_SECONDS,
                    help="Clip length. Passed as a STRING, not an int -- the API wants a string.")
    ap.add_argument("--size", default="1280x720", choices=VALID_SIZES)
    ap.add_argument("--out", default=None, help="Output path. Defaults to out/l12-video-01.mp4.")
    ap.add_argument("--poll-interval", type=int, default=20,
                    help="Seconds between status checks. 20 is the documented starting point.")
    ap.add_argument("--timeout", type=int, default=900,
                    help="Give up after this many seconds. Prevents a hung take.")
    ap.add_argument("--no-thumbnail", action="store_true", help="Skip downloading the poster frame.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate arguments and print the request. Make no Azure calls.")
    args = ap.parse_args()
    if not args.prompt.strip():
        ap.error("--prompt cannot be empty")
    if args.poll_interval < 2:
        ap.error("--poll-interval below 2s just burns your RPM budget on status checks")
    return args


def main() -> int:
    args = parse_args()
    out_path = pathlib.Path(args.out) if args.out else OUT_DIR / "l12-video-01.mp4"

    print("=" * 72)
    print("AI-103 L12 Beat 3 -- text to video, the async job (LO2)")
    print("=" * 72)
    print(f"  endpoint : {ACCOUNT_ENDPOINT.rstrip('/')}/openai/v1")
    print(f"  model    : {VIDEO_MODEL}")
    print(f"  length   : {args.seconds}s   size: {args.size}")
    print(f"  output   : {out_path}")
    print(f"  prompt   : {args.prompt}")
    print()

    if args.dry_run:
        print("[dry-run] Arguments valid. No Azure call made.")
        return 0

    client = build_client()

    # --- 1. Create the job -----------------------------------------------------
    wall_start = time.perf_counter()
    try:
        video = client.videos.create(
            model=VIDEO_MODEL,
            prompt=args.prompt,
            seconds=args.seconds,     # string, not int
            size=args.size,
        )
    except Exception as exc:                                    # noqa: BLE001
        triage(exc, phase="create")
        return 1

    print(f"  [job]   created  id={video.id}")
    print(f"  [job]   status={video.status}")
    print()
    print("  Polling. This is the whole difference between image and video generation:")
    print("  images return bytes, video returns a job you have to come back for.")
    print()

    # --- 2. Poll until terminal ------------------------------------------------
    poll_count = 0
    while video.status not in TERMINAL_STATUSES:
        elapsed = time.perf_counter() - wall_start
        if elapsed > args.timeout:
            print(f"  [poll]  gave up after {elapsed:.0f}s (--timeout {args.timeout}). Job {video.id}")
            print("          is still running server-side; retrieve it later with the id above.")
            return 1
        time.sleep(args.poll_interval)
        poll_count += 1
        # Never leave this call bare. It runs for minutes, and any failure here --
        # an expired token, a blip, a throttle -- would otherwise end the take in
        # a traceback with a half-rendered video stranded server-side.
        try:
            video = client.videos.retrieve(video.id)
        except Exception as exc:                                # noqa: BLE001
            print(f"  [poll]  status check failed after {int(elapsed)}s")
            triage(exc, phase="poll")
            print(f"          The job may still be running. Retrieve it with id {video.id}")
            return 1
        elapsed = time.perf_counter() - wall_start
        # `progress` is an int 0-100 on this surface, but treat it as optional so
        # the loop still prints something useful if the field is ever absent.
        pct = int(getattr(video, "progress", 0) or 0)
        print(f"  [poll]  +{int(elapsed) // 60:02d}:{int(elapsed) % 60:02d}  "
              f"{video.status:<12} {render_bar(pct)} {pct:3d}%")

    total = time.perf_counter() - wall_start
    print()

    if video.status != "completed":
        # A failed job carries an `error` object explaining why -- usually the
        # content filter. Print it; do not make the learner go hunting.
        print(f"  [job]   terminal status = {video.status} after {total:.0f}s")
        err = getattr(video, "error", None)
        if err:
            print(f"  [job]   error: {err}")
        return 1

    print(f"  [job]   completed in {total:.0f}s  ({total / 60:.1f} min, {poll_count} polls)")

    # --- 3. Download the rendered asset ---------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        content = client.videos.download_content(video.id, variant="video")
        content.write_to_file(out_path)
    except Exception as exc:                                    # noqa: BLE001
        print(f"  [dl]    download failed for {video.id}")
        triage(exc, phase="download")
        print("          The render succeeded -- only the transfer failed. Re-run the")
        print(f"          download with that id, but remember the 24-hour expiry.")
        return 1
    print(f"  [saved] {out_path.name}  {out_path.stat().st_size:,} bytes")

    if not args.no_thumbnail:
        # A poster frame is free and it is the frame you want on a slide.
        # Wrapped because `thumbnail` is a nice-to-have, not the deliverable.
        try:
            thumb_path = out_path.with_name(f"{out_path.stem}-thumb.jpg")
            client.videos.download_content(video.id, variant="thumbnail").write_to_file(thumb_path)
            print(f"  [saved] {thumb_path.name}  {thumb_path.stat().st_size:,} bytes")
        except Exception as exc:                                # noqa: BLE001
            print(f"  [warn]  thumbnail variant unavailable: {type(exc).__name__}")

    LAST_ID_FILE.write_text(video.id, encoding="utf-8")
    print(f"  [note]  video id written to {LAST_ID_FILE.name} for m12_video_remix.py")
    print()
    # The service TELLS you when the asset dies -- read it off the job rather than
    # repeating "24 hours" and hoping that stays true.
    expires_at = getattr(video, "expires_at", None)
    if expires_at:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expires_at))
        remaining = (expires_at - time.time()) / 3600.0
        print(f"Remember: the server-side render expires at {stamp} local "
              f"({remaining:.1f}h from now).")
    else:
        print("Remember: this render expires server-side in 24 hours.")
    print(f"The MP4 on disk is yours; the id {video.id} is not going to be there tomorrow.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
