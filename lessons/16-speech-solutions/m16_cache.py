#!/usr/bin/env python
"""
AI-103 Lesson 16 - content-addressed cache so every command is re-runnable.

Same design as Lessons 14 and 15. Speech costs money per character and per
audio second, and a retake shouldn't. Key = hash of the request CONTENT
(endpoint, voice, text, model, audio bytes). Same inputs, same key, instant
replay. Change any input and the call goes live.

Audio payloads are cached as base64 so a synthesized WAV replays byte-identical
across takes -- which matters more here than in any previous lesson, because
the audio IS the fixture for the beats that follow.

    --no-cache   ignore the cache, call Azure every time
    --clean      delete .cache/ and out/, then continue
"""
from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import shutil

ENABLED = True
CACHE_DIR = pathlib.Path(__file__).parent / ".cache"
HITS = 0
MISSES = 0


def key_for(operation: str, **parts) -> str:
    h = hashlib.sha256()
    h.update(operation.encode())
    for name in sorted(parts):
        value = parts[name]
        h.update(name.encode())
        h.update(value if isinstance(value, bytes)
                 else json.dumps(value, sort_keys=True, default=str).encode())
    return h.hexdigest()


def get(key: str):
    global HITS
    if not ENABLED:
        return None
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
        HITS += 1
        payload = entry["payload"]
        # Audio round-trips through base64 so the WAV is byte-identical.
        return base64.b64decode(payload) if entry.get("binary") else payload
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def put(key: str, payload, operation: str = "", label: str = "") -> None:
    if not ENABLED:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    binary = isinstance(payload, bytes)
    body = base64.b64encode(payload).decode("ascii") if binary else payload
    (CACHE_DIR / f"{key}.json").write_text(
        json.dumps({"operation": operation, "label": label,
                    "binary": binary, "payload": body}, indent=2),
        encoding="utf-8")


def remember(operation: str, label: str, compute, **parts):
    """Return (payload, was_cached). `compute` only runs on a miss."""
    global MISSES
    key = key_for(operation, **parts)
    hit = get(key)
    if hit is not None:
        return hit, True
    MISSES += 1
    payload = compute()
    put(key, payload, operation, label)
    return payload, False


def summary() -> str:
    if not ENABLED:
        return "cache: disabled (--no-cache), every call went live"
    return f"cache: {HITS} cached, {MISSES} live"


def clean(also_out: bool = True) -> list[str]:
    removed = []
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        removed.append(".cache/")
    out = pathlib.Path(__file__).parent / "out"
    if also_out and out.exists():
        shutil.rmtree(out)
        removed.append("out/")
    return removed
