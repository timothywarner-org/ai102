#!/usr/bin/env python
"""
AI-103 Lesson 15 - content-addressed cache so every command is re-runnable.

Same design as Lesson 14's cache, and for the same reason: recording a demo
means running a command eight times, and a generative model is not
deterministic. Take three can word an extraction differently than take two, and
if the runbook quotes take two you are now debugging a demo that works.

Key = hash of the request CONTENT (endpoint, model, prompt, schema, text). Same
inputs, same key, instant replay. Change any input and the call goes live. That
is why the key hashes inputs rather than a filename.

    --no-cache   ignore the cache, call Azure every time
    --clean      delete .cache/ and out/, then continue

Every result is labeled [live] or [cached] and every run ends with a tally.
Nothing is hidden.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil

ENABLED = True
CACHE_DIR = pathlib.Path(__file__).parent / ".cache"
HITS = 0
MISSES = 0


def key_for(operation: str, **parts) -> str:
    """Stable hash over the operation name and every input that can change the answer."""
    h = hashlib.sha256()
    h.update(operation.encode())
    for name in sorted(parts):
        value = parts[name]
        h.update(name.encode())
        if isinstance(value, bytes):
            h.update(value)
        else:
            h.update(json.dumps(value, sort_keys=True, default=str).encode())
    return h.hexdigest()


def get(key: str):
    global HITS
    if not ENABLED:
        return None
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        HITS += 1
        return json.loads(path.read_text(encoding="utf-8"))["payload"]
    except (json.JSONDecodeError, KeyError):
        return None          # a corrupt entry is a miss, not a crash


def put(key: str, payload, operation: str = "", label: str = "") -> None:
    if not ENABLED:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(
        json.dumps({"operation": operation, "label": label, "payload": payload},
                   indent=2),
        encoding="utf-8")


def remember(operation: str, label: str, compute, **parts):
    """Return (payload, was_cached). `compute` is only called on a miss."""
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
