#!/usr/bin/env python
"""
AI-103 Lesson 13 - Beat 3: Video analysis with Content Understanding.

Covers learning objective:
  LO6  Implement video analysis workflows to process and interpret video segments
  (and extends LO8 - identifying objects and regions - from stills into motion)

WHICH ANALYZER, AND WHY IT MATTERS
----------------------------------
We use `prebuilt-videoSearch`.

You will find `prebuilt-videoAnalysis` referenced on the Content Understanding
video overview page. It is NOT in the prebuilt analyzer catalog. Treat it as a
documentation artifact, not an API contract - calling it is a good way to earn a
404 on camera. The catalog lists exactly four video-capable entries:

    prebuilt-video          base video analyzer
    prebuilt-videoSearch    RAG-oriented: transcript + key frames + descriptions

`prebuilt-videoSearch` is the right default for this lesson because its output is
already shaped for indexing: segment descriptions, a WEBVTT transcript, and
ordered key-frame thumbnails with timestamps. That is precisely the payload you
would push into Azure AI Search to make a video library searchable.

HOW VIDEO ANALYSIS ACTUALLY WORKS (the guardrails that decide your design)
--------------------------------------------------------------------------
The service does not "watch" the video. It:
  1. Samples frames at approximately ONE FRAME PER SECOND.
  2. Scales every sampled frame to 512 x 512 pixels.
  3. Transcribes SPOKEN WORDS only.
  4. Segments the video into scenes, then describes each segment.

Three consequences you must design around, and which make good exam distractors:
  - Anything that happens in under a second can be missed entirely. Do not use
    this to count items on a fast production line.
  - Small text and distant objects vanish at 512x512. A license plate across a
    parking lot is not coming back.
  - Music, sound effects, alarms, and tone of voice are not captured. Only words.

SIZE AND DURATION LIMITS DEPEND ON HOW YOU SUBMIT
-------------------------------------------------
  analyzeBinary (direct byte upload) : <= 200 MB and <= 30 minutes
  analyze       (by URL reference)   : <= 4 GB  and <= 2 hours

That asymmetry is a real architectural decision, not trivia. Anything longer than
30 minutes must land in blob storage first and be passed by URL.

USAGE
-----
  python m13_cu_video.py --dry-run
  python m13_cu_video.py --video-url https://<blob>/clip.mp4
  python m13_cu_video.py --video ./assets/clip.mp4        # binary upload path
  python m13_cu_video.py --video-url <url> --analyzer prebuilt-video
  python m13_cu_video.py --video-url <url> --save-markdown out.md

PREREQS
-------
  az login
  pip install azure-ai-contentunderstanding
  .env with CONTENTUNDERSTANDING_ENDPOINT (services.ai.azure.com host)

GROUNDING
---------
  Video overview (output shape, segmentation, frame sampling):
    https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/video/overview
  Prebuilt analyzer catalog (the authoritative analyzer ID list):
    https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/prebuilt-analyzers
  Service limits (200 MB/30 min vs 4 GB/2 h, 1 FPS, 512x512):
    https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/service-limits
"""

from __future__ import annotations

# Proxy scrub before SDK import - see m13_vision_chat.py.
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
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

from azure.ai.contentunderstanding import ContentUnderstandingClient  # noqa: E402
from azure.ai.contentunderstanding.models import AnalysisInput  # noqa: E402
from azure.identity import AzureCliCredential  # noqa: E402

# --- Limits, straight from the service limits doc -----------------------------
BINARY_MAX_BYTES = 200 * 1024 * 1024      # analyzeBinary: 200 MB
BINARY_MAX_MINUTES = 30                   # analyzeBinary: 30 minutes
URL_MAX_BYTES = 4 * 1024 * 1024 * 1024    # analyze by URL: 4 GB
URL_MAX_HOURS = 2                         # analyze by URL: 2 hours
FRAME_SAMPLE_FPS = 1                      # ~1 frame per second
FRAME_SCALE = "512x512"

SUPPORTED_VIDEO_EXT = (".mp4", ".m4v", ".flv", ".wmv", ".asf", ".avi", ".mkv", ".mov")

# The catalog-verified video analyzers. prebuilt-videoAnalysis is intentionally
# NOT here - see the module docstring.
VIDEO_ANALYZERS = ("prebuilt-videoSearch", "prebuilt-video")


def print_guardrails() -> None:
    """
    Print the limits before we do anything.

    These are shown every run, on purpose. Students who internalize the frame
    sampling rate stop proposing designs the service cannot deliver.
    """
    print("  " + "-" * 74)
    print("  VIDEO GUARDRAILS - design around these, they are not negotiable")
    print("  " + "-" * 74)
    print(f"  Direct upload (analyzeBinary) : <= {BINARY_MAX_BYTES // (1024**2)} MB, "
          f"<= {BINARY_MAX_MINUTES} minutes")
    print(f"  By URL        (analyze)       : <= {URL_MAX_BYTES // (1024**3)} GB, "
          f"<= {URL_MAX_HOURS} hours")
    print(f"  Frame sampling                : ~{FRAME_SAMPLE_FPS} FPS "
          f"(sub-second events can be missed)")
    print(f"  Frame resolution              : scaled to {FRAME_SCALE} "
          f"(small/distant text is lost)")
    print("  Audio                         : SPOKEN WORDS only "
          "(no music, no sound effects)")
    print(f"  Container formats             : {', '.join(SUPPORTED_VIDEO_EXT)}")
    print("  Resolution range              : 320x240 min, 1920x1080 max")
    print("  " + "-" * 74)


def build_client() -> ContentUnderstandingClient:
    """Construct the Content Understanding client. Same host rules as Beat 2."""
    endpoint = os.getenv("CONTENTUNDERSTANDING_ENDPOINT", "").strip()
    if not endpoint:
        raise SystemExit(
            "[config] CONTENTUNDERSTANDING_ENDPOINT is not set.\n"
            "         Expected: https://<account>.services.ai.azure.com/"
        )
    if "openai.azure.com" in endpoint:
        raise SystemExit(
            "[config] That is the Azure OpenAI host. Content Understanding uses\n"
            "         https://<account>.services.ai.azure.com/"
        )

    # AzureCliCredential, never DefaultAzureCredential. The Azure SDK pipeline
    # refreshes this token on every request, which genuinely matters here: a
    # 30-minute video can poll well past the initial token's lifetime. This is
    # the same failure class we fixed by hand for the OpenAI client in Beat 1.
    return ContentUnderstandingClient(endpoint=endpoint, credential=AzureCliCredential())


def validate_local_video(path: Path) -> None:
    """Fail fast on a local file the binary upload path would reject."""
    if not path.exists():
        raise SystemExit(f"[video] Not found: {path}")
    if path.suffix.lower() not in SUPPORTED_VIDEO_EXT:
        raise SystemExit(
            f"[video] '{path.suffix}' is not a supported container.\n"
            f"        Supported: {', '.join(SUPPORTED_VIDEO_EXT)}"
        )

    size = path.stat().st_size
    if size == 0:
        raise SystemExit(f"[video] {path.name} is empty.")
    if size > BINARY_MAX_BYTES:
        raise SystemExit(
            f"[video] {path.name} is {size:,} bytes - over the "
            f"{BINARY_MAX_BYTES:,} byte (200 MB) direct-upload cap.\n"
            f"        Upload it to blob storage and use --video-url instead,\n"
            f"        which raises the ceiling to 4 GB / 2 hours."
        )
    print(f"  [video] {path.name}  {size:,} bytes  ({size / (1024**2):.1f} MB)")
    print(f"  [video] within the {BINARY_MAX_BYTES // (1024**2)} MB direct-upload limit")
    # We cannot read duration without a media library; the 30-minute cap is
    # enforced server-side. Say so rather than pretending we checked.
    print(f"  [video] duration NOT checked locally - the {BINARY_MAX_MINUTES} min")
    print("          cap is enforced by the service and returns a 400 if exceeded")


def render_result(result, save_markdown: str | None) -> None:
    """Print the analysis output: markdown, transcript, key frames, segments."""
    if not result.contents:
        print("  [empty] No contents returned. Check the input decoded correctly.")
        return

    print(f"  [segments] {len(result.contents)} content segment(s) returned")
    print()

    all_markdown: list[str] = []

    for index, content in enumerate(result.contents, start=1):
        print("=" * 78)
        print(f"  SEGMENT {index} of {len(result.contents)}")
        print("=" * 78)

        # Video segments carry start/end timestamps in milliseconds. These are
        # what you store alongside your search index so a hit can deep-link to
        # the right moment in the player.
        start_ms = getattr(content, "start_time_ms", None)
        end_ms = getattr(content, "end_time_ms", None)
        if start_ms is not None and end_ms is not None:
            print(f"  [time] {_fmt_ms(start_ms)} --> {_fmt_ms(end_ms)}  "
                  f"({(end_ms - start_ms) / 1000:.1f}s)")

        # Frame geometry, as the service actually processed it.
        width = getattr(content, "width", None)
        height = getattr(content, "height", None)
        if width and height:
            print(f"  [frame] source {width}x{height} "
                  f"(sampled frames were scaled to {FRAME_SCALE})")

        # The markdown IS the headline deliverable for prebuilt-videoSearch. It
        # bundles the segment description, the transcript, and key-frame refs.
        markdown = getattr(content, "markdown", None)
        if markdown:
            all_markdown.append(markdown)
            print()
            print(markdown)
            print()
        else:
            print("  [markdown] none on this segment")

        # ---- The STRUCTURED companions to the markdown -----------------------
        # Do not scrape the markdown for these - the SDK surfaces them as real
        # typed properties on AudioVisualContent. This is what you persist
        # alongside a search index so a hit can deep-link into the player.

        key_frames = getattr(content, "key_frame_times_ms", None)
        if key_frames:
            print(f"  [keyframes] {len(key_frames)} extracted "
                  f"(~{FRAME_SAMPLE_FPS} FPS sampling)")
            preview = ", ".join(_fmt_ms(t) for t in key_frames[:8])
            more = f" ... (+{len(key_frames) - 8} more)" if len(key_frames) > 8 else ""
            print(f"  [keyframes] {preview}{more}")

        shots = getattr(content, "camera_shot_times_ms", None)
        if shots:
            print(f"  [shots] {len(shots)} camera-shot boundaries detected")

        # transcript_phrases only populates when returnDetails is on. Each phrase
        # carries speaker attribution and its own start/end timestamps.
        phrases = getattr(content, "transcript_phrases", None)
        if phrases:
            print(f"  [transcript] {len(phrases)} phrase(s) - SPOKEN WORDS ONLY")
            for phrase in phrases[:5]:
                speaker = getattr(phrase, "speaker", None) or "unknown"
                start = getattr(phrase, "start_time_ms", 0) or 0
                text = (getattr(phrase, "text", "") or "").strip()
                print(f"    {_fmt_ms(start)}  [{speaker}]  {text[:70]}")
            if len(phrases) > 5:
                print(f"    ... (+{len(phrases) - 5} more phrases)")
        else:
            print("  [transcript] no phrase detail "
                  "(set config returnDetails on a custom analyzer to get it)")

        # Sub-segments, when the analyzer performed scene segmentation.
        segments = getattr(content, "segments", None)
        if segments:
            print(f"  [scenes] {len(segments)} sub-segment(s):")
            for seg in segments[:6]:
                s = getattr(seg, "start_time_ms", 0) or 0
                e = getattr(seg, "end_time_ms", 0) or 0
                category = getattr(seg, "category", None) or ""
                print(f"    {_fmt_ms(s)} --> {_fmt_ms(e)}  {category}")
            if len(segments) > 6:
                print(f"    ... (+{len(segments) - 6} more)")

        # Custom fields only appear if the analyzer declared a fieldSchema.
        # prebuilt-videoSearch does not, so this is normally empty - which is
        # itself the teaching point about prebuilt vs custom.
        fields = getattr(content, "fields", None)
        if fields:
            print()
            print("  [fields] custom schema fields:")
            for name, value in fields.items():
                print(f"    {name} = {value}")
        print()

    if save_markdown and all_markdown:
        out = Path(save_markdown)
        out.write_text("\n\n---\n\n".join(all_markdown), encoding="utf-8")
        print(f"  [saved] {out.name}  {out.stat().st_size:,} bytes")


def _fmt_ms(ms: int) -> str:
    """Milliseconds to HH:MM:SS.mmm for readable segment boundaries."""
    seconds, milliseconds = divmod(int(ms), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def triage(exc: Exception) -> None:
    """Per-symptom triage for video analysis failures."""
    text = str(exc)
    status = getattr(exc, "status_code", None)

    print()
    print("  [error] Video analysis failed. Triage:")

    if status == 401 or "401" in text:
        print("  [401] Token rejected. Run 'az login'.")
        print("        On a LONG video this can also mean the token expired")
        print("        mid-poll - but the Azure SDK refreshes automatically, so")
        print("        suspect an expired az login session instead.")
    elif status == 403 or "403" in text:
        print("  [403] Missing 'Cognitive Services User' on the Foundry account,")
        print("        or RBAC has not propagated (~5 minutes).")
        print("        If using --video-url against private blob storage, the")
        print("        SERVICE cannot read it. Use a SAS URL or make it public.")
    elif status == 404 or "404" in text:
        print("  [404] Endpoint or analyzer not found.")
        print("        - Use the *.services.ai.azure.com host.")
        print("        - Analyzer ID: use 'prebuilt-videoSearch'.")
        print("          'prebuilt-videoAnalysis' appears in one doc page but is")
        print("          NOT in the prebuilt catalog and will 404.")
    elif status == 429 or "429" in text:
        print("  [429] Throttled. Video jobs are expensive; run one at a time.")
    elif "400" in text or "InvalidArgument" in text:
        print("  [400] The service rejected the video.")
        print("        - Over 200 MB or 30 min on the direct-upload path?")
        print("          Move to blob + --video-url (4 GB / 2 h).")
        print("        - Unsupported container or codec? Need H.264/AAC for .mp4.")
        print("        - Resolution outside 320x240 .. 1920x1080?")
    elif "timeout" in text.lower():
        print("  [timeout] The poller gave up. Video analysis is slow -")
        print("            roughly real-time or worse. Raise the timeout or")
        print("            use a shorter clip for the demo.")
    else:
        print("  [??] Unrecognized failure.")

    print(f"  [raw] {text[:600]}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AI-103 L13 Beat 3 - Content Understanding video analysis (LO6).",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the plan and guardrails. Zero Azure calls.")
    parser.add_argument("--video-url", help="Publicly reachable video URL (<=4 GB, <=2 h).")
    parser.add_argument("--video", help="Local video file (<=200 MB, <=30 min).")
    parser.add_argument("--analyzer", default="prebuilt-video", choices=VIDEO_ANALYZERS,
                        help="Which prebuilt video analyzer to use.")
    parser.add_argument("--save-markdown", metavar="PATH",
                        help="Write the combined segment markdown to a file.")
    args = parser.parse_args()

    print()
    print("AI-103 Lesson 13 | Beat 3 | Content Understanding video analysis")
    print("-" * 78)
    print(f"  [analyzer] {args.analyzer}")
    print(f"  [api-version] {os.getenv('CONTENTUNDERSTANDING_API_VERSION', '2025-11-01')} (GA)")
    print()
    print_guardrails()
    print()

    video_url = args.video_url or os.getenv("CU_VIDEO_URL", "").strip() or None
    video_path = Path(args.video) if args.video else None

    if video_path is not None:
        validate_local_video(video_path)

    # ---- DRY RUN -------------------------------------------------------------
    if args.dry_run:
        print("  [mode] DRY RUN - no Azure calls, no token acquisition")
        print()
        print("  [dry-run] Would call:")
        if video_path is not None:
            print(f"    client.begin_analyze_binary({args.analyzer!r}, <bytes of {video_path.name}>)")
            print("    -> direct upload path: 200 MB / 30 min ceiling")
        else:
            target = video_url or "<--video-url>"
            print(f"    client.begin_analyze({args.analyzer!r}, "
                  f"inputs=[AnalysisInput(url={target!r})])")
            print("    -> URL path: 4 GB / 2 h ceiling; service fetches the URL,")
            print("       so private blob needs a SAS token")
        print("    result = poller.result()")
        print("    for content in result.contents: print(content.markdown)")
        print()
        print("  [dry-run] Expected output shape from prebuilt-videoSearch:")
        print("    - one content entry per detected SEGMENT (scene)")
        print("    - .markdown  : segment description + WEBVTT transcript +")
        print("                   ordered key-frame references with timestamps")
        print("    - .start_time_ms / .end_time_ms for deep-linking")
        print("    - .fields    : EMPTY, because prebuilt analyzers declare no")
        print("                   custom fieldSchema. Add one (as in Beat 2) to")
        print("                   get structured per-segment fields.")
        print()
        return 0

    # ---- LIVE ----------------------------------------------------------------
    if not video_url and video_path is None:
        raise SystemExit(
            "[args] No video supplied.\n"
            "       Use --video-url <url>, --video <path>, or set CU_VIDEO_URL in .env."
        )

    print("  [mode] LIVE")
    client = build_client()
    print(f"  [endpoint] {os.getenv('CONTENTUNDERSTANDING_ENDPOINT')}")
    print("  [auth] AzureCliCredential (keyless)")
    print()

    started = time.time()
    try:
        if video_path is not None:
            print(f"  [submit] binary upload: {video_path.name}")
            poller = client.begin_analyze_binary(
                args.analyzer, video_path.read_bytes(), content_type="application/octet-stream"
            )
        else:
            print(f"  [submit] url: {video_url}")
            poller = client.begin_analyze(args.analyzer, inputs=[AnalysisInput(url=video_url)])

        # Video analysis runs roughly at real time or slower. The SDK poller
        # blocks here; on camera, this is the moment to talk through the
        # guardrails above rather than watching a cursor blink.
        print("  [poll] long-running operation in progress "
              "(expect roughly real-time or slower)...")
        result = poller.result()
        elapsed = time.time() - started
        print(f"  [done] analysis complete in {elapsed:,.1f}s")
        print()

        render_result(result, args.save_markdown)

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        triage(exc)
        return 1

    print()
    print("-" * 78)
    print("  [done] Beat 3 complete.")
    print("  [note] Every description came from ~1 FPS frames scaled to 512x512")
    print("         plus a spoken-word transcript. If your scenario depends on")
    print("         sub-second events, fine print, or non-speech audio, this")
    print("         pipeline is the wrong shape - and that is a design decision,")
    print("         not a tuning problem.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
