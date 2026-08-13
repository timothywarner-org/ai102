#!/usr/bin/env python
"""
AI-103 Lesson 16 - play the fixture out loud.

Every beat in this lesson reasons over ONE recording, `out/caller.wav`. The
transcript, the phrase-list repair, the two translation routes, the audio model:
all of it is downstream of that file. If the room never hears it, the whole
lesson is people reading strings and taking my word for what the caller sounded
like. So playback is part of the demo, not a nicety.

WHY THE STDLIB AND NOT AN AUDIO PACKAGE
---------------------------------------
`winsound` ships with CPython on Windows and plays a RIFF WAV synchronously with
no dependency, no device enumeration, and no init call. The demo already
produces exactly the format it wants (16 kHz 16-bit mono PCM), so there is
nothing to convert. Adding sounddevice or pygame to a teaching repo would mean a
native wheel, a device-selection failure mode on camera, and a longer `uv sync`
for zero benefit.

Other platforms fall back to whichever system player is present. This repo is
Windows-first but the lesson code should not hard-fail on a Mac.

PLAYBACK NEVER KILLS THE DEMO
-----------------------------
Every failure path here degrades to a printed path and returns False. A missing
audio device is not a reason to lose a take.

CAMTASIA
--------
This plays through the default output device, which Camtasia captures only when
**System Audio** is enabled in the recorder. It defaults to OFF and fails
silently, so there is a one-time nudge printed with the first playback.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import wave

# One-time-per-process flag so the Camtasia reminder appears with the first clip
# and not on every playback in a script that plays more than one.
_NUDGED = False

# Set by validate.ps1 and any headless run. Playing 18 seconds of audio four
# times during an automated validation pass helps nobody.
MUTE_ENV = "AI103_NO_AUDIO"


def duration_seconds(path: pathlib.Path) -> float | None:
    """Read the WAV header for a real duration. Returns None if unreadable."""
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            return handle.getnframes() / rate if rate else None
    except (wave.Error, OSError):
        return None


def muted() -> bool:
    return os.getenv(MUTE_ENV, "").strip().lower() in ("1", "true", "yes")


def _play_windows(path: pathlib.Path) -> bool:
    """
    SND_FILENAME blocks until the clip finishes, which is what a demo wants --
    the next line of output should not scroll past while the caller is talking.
    """
    import winsound

    winsound.PlaySound(str(path), winsound.SND_FILENAME)
    return True


def _play_posix(path: pathlib.Path) -> bool:
    """First system player that exists wins. All of these block."""
    candidates = (
        ["afplay"],                       # macOS, always present
        ["paplay"],                       # PulseAudio / PipeWire
        ["aplay", "-q"],                  # ALSA
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
    )
    for argv in candidates:
        if shutil.which(argv[0]):
            subprocess.run([*argv, str(path)], check=True)
            return True
    return False


def play(path: pathlib.Path, label: str = "the caller") -> bool:
    """
    Play a WAV synchronously and narrate it on screen.

    Returns True if audio actually came out of a device. Callers should treat
    False as informational, never fatal.
    """
    global _NUDGED

    path = pathlib.Path(path)
    seconds = duration_seconds(path)
    length = f"{seconds:.1f}s" if seconds else "unknown length"

    if muted():
        print(f"\n  PLAY skipped ({MUTE_ENV} is set) -- {path.name}, {length}")
        return False

    if not path.exists():
        print(f"\n  PLAY skipped -- {path} not found")
        return False

    print(f"\n  PLAY {label} -- {path.name}, {length}")
    if not _NUDGED:
        print("       (Camtasia captures this only with System Audio ON)")
        _NUDGED = True
    # Flush before blocking, or the banner appears after the audio on a piped
    # or redirected stdout -- which is exactly where validation logs go.
    sys.stdout.flush()

    try:
        played = _play_windows(path) if os.name == "nt" else _play_posix(path)
    except Exception as exc:  # playback is never worth losing a take over
        print(f"       playback unavailable ({exc.__class__.__name__}: {exc})")
        print(f"       open it yourself: {path}")
        return False

    if not played:
        print("       no system audio player found (afplay/paplay/aplay/ffplay)")
        print(f"       open it yourself: {path}")
        return False
    return True


def add_play_argument(parser, default_on: bool) -> None:
    """
    Same flag name and same behaviour in every script in this lesson, so there
    is one thing to remember on camera.

    Beat 2 produces the recording, so it plays by default. The later beats
    consume the same file and default to silence -- replaying an 18-second clip
    the room already heard costs recording time and teaches nothing new.
    """
    if default_on:
        parser.add_argument("--no-play", dest="play", action="store_false",
                            help="do not play the recording out loud")
        parser.set_defaults(play=True)
    else:
        parser.add_argument("--play", dest="play", action="store_true",
                            help="play the source recording out loud before analyzing it")
        parser.set_defaults(play=False)


if __name__ == "__main__":
    # Standalone so you can sound-check levels before a take:
    #     uv run python m16_audio.py
    target = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else (
        pathlib.Path(__file__).parent / "out" / "caller.wav")
    raise SystemExit(0 if play(target) else 1)
