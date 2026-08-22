"""m12_video_remix.py -- edit a finished Sora render by remixing it.

    uv run python m12_video_remix.py
    uv run python m12_video_remix.py --video-id video_xxxx --prompt "..."
    uv run python m12_video_remix.py --dry-run     # resolve the source id, call nothing

Beat 4 of Lesson 12, covering LO4: "Implement workflows to edit generated videos."

Here is the mental model, and it is the answer to the question every learner
asks: how do you EDIT a generated video? You do not open it in a timeline. You
remix it. `videos.remix` takes a completed video id plus a new prompt and renders
a NEW video that inherits the source's composition, motion, and style, then
applies your change on top.

That has two consequences you should say out loud:

  * The result is a new job with a new id, not a mutation of the old one. Both
    videos exist. The response carries `remixed_from_video_id`, which is the
    provenance link -- and provenance is exactly what an editing workflow needs
    when somebody asks six weeks later where a clip came from.

  * The source must still exist. Renders expire after 24 hours, so a remix
    against yesterday's id fails. Remix is a same-session workflow unless you
    are re-rendering from your own archived prompt.

Because it is a new render, the job lifecycle is identical to Beat 3: create,
poll queued -> in_progress -> completed, download. Same loop, and showing that
the loop is the same is half the value.
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

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
LAST_ID_FILE = OUT_DIR / "last_video_id.txt"

TERMINAL_STATUSES = ("completed", "failed", "cancelled")

# A change to LIGHT and ATMOSPHERE, not to subject matter. That is deliberate:
# remix is strongest when it preserves composition and motion, so a prompt that
# tweaks the grade shows the inheritance clearly. Ask for a different subject and
# you are really just generating a second video with extra steps.
DEFAULT_PROMPT = (
    "Keep the same paper sailboat, the same lagoon, and the same slow push-in, "
    "but change the time of day to late golden afternoon and add a low drifting mist "
    "across the water. Warmer amber light, longer shadows. No people, no text, no logos."
)


def build_client() -> OpenAI:
    """Plain OpenAI client on the ACCOUNT /openai/v1 surface. See m12_image_gen.py.

    api_key is the CALLABLE from get_bearer_token_provider, so the SDK refreshes
    the token before every request. This is the longest-running script in the
    lesson -- a source lookup, a render, and a download, chained -- so it is the
    one where a frozen token string would hurt most.
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
        print("ERROR: the remix PROMPT was blocked before rendering started. Keep the")
        print("       change to lighting, weather, and atmosphere rather than introducing")
        print("       people, faces, or recognizable IP.")


def triage(exc: Exception, *, phase: str) -> None:
    """One error table for every call here: source lookup, remix, poll, download."""
    msg = str(exc)
    low = msg.lower()
    if "401" in msg or "invalid_token" in low or "expired" in low:
        print(f"ERROR: 401 during {phase} -- the access token was rejected.")
        print("       Mid-poll, this almost always means the token expired while the")
        print("       render ran. build_client() passes a token PROVIDER precisely so the")
        print("       SDK refreshes per request; if that was changed back to a static")
        print("       token string, restore it. Otherwise run `az login` and try again.")
    elif "429" in msg:
        print(f"ERROR: rate limited during {phase}, or at the concurrency ceiling")
        print("       (Sora 2 allows two concurrent jobs per account).")
    elif "404" in msg:
        print(f"ERROR: 404 during {phase} -- wrong base_url, or the source id is gone.")
        print("       Video lives on the ACCOUNT endpoint; a /api/projects/ path is the bug.")
    elif is_content_filter(msg):
        explain_content_filter(msg)
    else:
        print(f"ERROR: {type(exc).__name__} during {phase}: {msg[:500]}")


def render_bar(pct: int, width: int = 24) -> str:
    filled = max(0, min(width, round(width * pct / 100)))
    return "[" + "#" * filled + "." * (width - filled) + "]"


def resolve_source_id(explicit: str | None) -> str | None:
    """Use --video-id when given, otherwise the id m12_video_gen.py left behind."""
    if explicit:
        return explicit.strip()
    if LAST_ID_FILE.exists():
        return LAST_ID_FILE.read_text(encoding="utf-8").strip() or None
    return None


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Remix a completed Sora video into a new one.")
    ap.add_argument("--video-id", default=None,
                    help="Source video id. Defaults to the id saved by m12_video_gen.py.")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT, help="The change to apply on top of the source.")
    ap.add_argument("--out", default=None, help="Output path. Defaults to out/l12-video-02-remix.mp4.")
    ap.add_argument("--poll-interval", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--dry-run", action="store_true",
                    help="Resolve and validate the source id, then stop. Make no Azure calls.")
    args = ap.parse_args()
    if not args.prompt.strip():
        ap.error("--prompt cannot be empty")
    return args


def main() -> int:
    args = parse_args()
    out_path = pathlib.Path(args.out) if args.out else OUT_DIR / "l12-video-02-remix.mp4"

    source_id = resolve_source_id(args.video_id)
    if not source_id:
        print("ERROR: no source video id.")
        print(f"       Run m12_video_gen.py first (it writes {LAST_ID_FILE.name}),")
        print("       or pass --video-id video_xxxxxxxx explicitly.")
        return 1

    print("=" * 72)
    print("AI-103 L12 Beat 4 -- remix: editing a generated video (LO4)")
    print("=" * 72)
    print(f"  endpoint : {ACCOUNT_ENDPOINT.rstrip('/')}/openai/v1")
    print(f"  source   : {source_id}" + ("" if args.video_id else f"   (read from {LAST_ID_FILE.name})"))
    print(f"  output   : {out_path}")
    print(f"  prompt   : {args.prompt}")
    print()

    if args.dry_run:
        print("[dry-run] Source id resolved. No Azure call made.")
        return 0

    client = build_client()

    # --- 0. Confirm the source is still there and still completed --------------
    # Cheap, and it turns "remix failed" into the actual diagnosis: the 24-hour
    # expiry. Worth the extra call every single time.
    try:
        source = client.videos.retrieve(source_id)
        print(f"  [src]   status={source.status}  model={getattr(source, 'model', 'n/a')}")
        if source.status != "completed":
            print(f"ERROR: source video is '{source.status}', not 'completed'. You can only remix a")
            print("       finished render. Wait for m12_video_gen.py to finish, then re-run.")
            return 1
    except Exception as exc:                                    # noqa: BLE001
        triage(exc, phase="source lookup")
        print(f"       Could not retrieve source video {source_id}.")
        print("       Renders EXPIRE AFTER 24 HOURS. If this id is from a previous day it is gone,")
        print("       and you need to re-run m12_video_gen.py to make a fresh one.")
        return 1

    # --- 1. Create the remix job ----------------------------------------------
    wall_start = time.perf_counter()
    try:
        remix = client.videos.remix(video_id=source_id, prompt=args.prompt)
    except Exception as exc:                                    # noqa: BLE001
        triage(exc, phase="remix create")
        return 1

    # The provenance link. This is the field that makes remix an editing WORKFLOW
    # rather than a one-off generation: every derivative points back at its parent.
    lineage = getattr(remix, "remixed_from_video_id", None)
    print(f"  [job]   created  id={remix.id}")
    print(f"  [job]   status={remix.status}")
    print(f"  [job]   remixed_from_video_id={lineage}")
    if lineage != source_id:
        print(f"  [warn]  lineage does not match the id we asked for ({source_id}).")
    print()

    # --- 2. Poll -- same loop as Beat 3 ---------------------------------------
    poll_count = 0
    while remix.status not in TERMINAL_STATUSES:
        elapsed = time.perf_counter() - wall_start
        if elapsed > args.timeout:
            print(f"  [poll]  gave up after {elapsed:.0f}s. Job {remix.id} is still running server-side.")
            return 1
        time.sleep(args.poll_interval)
        poll_count += 1
        # Same rule as Beat 3: this call must never be bare. It runs for minutes.
        try:
            remix = client.videos.retrieve(remix.id)
        except Exception as exc:                                # noqa: BLE001
            print(f"  [poll]  status check failed after {int(elapsed)}s")
            triage(exc, phase="poll")
            print(f"          The job may still be running. Retrieve it with id {remix.id}")
            return 1
        elapsed = time.perf_counter() - wall_start
        pct = int(getattr(remix, "progress", 0) or 0)
        print(f"  [poll]  +{int(elapsed) // 60:02d}:{int(elapsed) % 60:02d}  "
              f"{remix.status:<12} {render_bar(pct)} {pct:3d}%")

    total = time.perf_counter() - wall_start
    print()

    if remix.status != "completed":
        print(f"  [job]   terminal status = {remix.status} after {total:.0f}s")
        err = getattr(remix, "error", None)
        if err:
            print(f"  [job]   error: {err}")
        return 1

    print(f"  [job]   completed in {total:.0f}s  ({total / 60:.1f} min, {poll_count} polls)")

    # --- 3. Download -----------------------------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        client.videos.download_content(remix.id, variant="video").write_to_file(out_path)
    except Exception as exc:                                    # noqa: BLE001
        print(f"  [dl]    download failed for {remix.id}")
        triage(exc, phase="download")
        print("          The remix rendered -- only the transfer failed. Retry with that")
        print("          id, but remember the 24-hour expiry.")
        return 1
    print(f"  [saved] {out_path.name}  {out_path.stat().st_size:,} bytes")
    print()
    print("  lineage:")
    print(f"    {source_id}   (original)")
    print(f"      -> {remix.id}   (remix, remixed_from_video_id={getattr(remix, 'remixed_from_video_id', None)})")
    print()
    print("Play them back to back. Same boat, same lagoon, same camera move -- different hour")
    print("of the day. That inheritance is what separates a remix from a second generation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
