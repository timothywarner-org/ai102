#!/usr/bin/env python
"""
AI-103 Lesson 14 - a content-addressed cache so every script is re-runnable.

WHY THIS EXISTS
---------------
Recording a demo means running the same command eight times. Twice to rehearse,
once for the take, once because you fumbled a word, once because the phone rang.
Without a cache that is eight rounds of vision-model latency and eight rounds of
billing for output nobody watches.

Worse, it is eight slightly DIFFERENT outputs. A vision model is not
deterministic. Take three can word a finding differently than take two, and if
your `CHECK` line in the runbook quotes take two, you are now debugging a demo
that is working correctly.

So: cache on by default, keyed by the CONTENT of the request. Same image, same
prompt, same model, same api-version -> same key -> same answer, instantly.
Change any one of those and the key changes and the call goes live. That is the
whole design, and it is why the key is a hash of the inputs rather than a
filename. Rename the file, get the same cached answer. Edit one pixel, get a
fresh call.

HONESTY ON CAMERA
-----------------
Every script prints a one-line cache summary at the end, and every cached result
is labeled. Nothing is hidden. If you want a provably live take, pass
`--no-cache`. If you want a fast rehearsal, do not.

    --no-cache   ignore the cache completely, call Azure every time
    --clean      delete the cache and out/, then continue with the run

STORAGE
-------
`.cache/<sha256>.json` next to the scripts, gitignored. Each entry carries the
operation name and a human-readable label so you can open one and see what it
was for. Nothing sensitive lands here: the image BYTES are hashed into the key,
never stored.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import time

# Module-level switch. main() flips this from --no-cache. Keeping it here rather
# than threading a boolean through six call sites keeps the demo code readable,
# which matters more than purity in a file people are going to read on screen.
ENABLED = True

CACHE_DIR = pathlib.Path(__file__).parent / ".cache"

# Counters so each script can print an honest one-line summary.
HITS = 0
MISSES = 0


def key_for(operation: str, **parts) -> str:
    """
    Build a stable key from everything that could change the answer.

    Sorted keys, so argument order cannot produce two different hashes for the
    same logical request. Bytes get hashed separately rather than base64'd into
    the key material, because a 4 MB image in a dict you are about to
    json.dumps is a needless copy.
    """
    hasher = hashlib.sha256()
    hasher.update(operation.encode("utf-8"))
    for name in sorted(parts):
        value = parts[name]
        hasher.update(b"\x00" + name.encode("utf-8") + b"\x00")
        if isinstance(value, (bytes, bytearray)):
            hasher.update(hashlib.sha256(value).digest())
        else:
            hasher.update(json.dumps(value, sort_keys=True, default=str).encode("utf-8"))
    return hasher.hexdigest()


def get(key: str):
    """Return the cached payload, or None. None also means caching is off."""
    global HITS
    if not ENABLED:
        return None
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A truncated cache file is not worth a stack trace mid-recording.
        # Treat it as a miss and let the live call overwrite it.
        return None
    HITS += 1
    return entry["payload"]


def put(key: str, payload, operation: str = "", label: str = "") -> None:
    """Write an entry. No-op when caching is off, so callers need no branch."""
    global MISSES
    MISSES += 1
    if not ENABLED:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(
        json.dumps({
            "operation": operation,
            "label": label,
            "cached_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "payload": payload,
        }, indent=2),
        encoding="utf-8",
    )


def remember(operation: str, label: str, compute, **parts):
    """
    The one function the demo scripts actually call.

    `compute` is a zero-argument callable that does the expensive thing. It is
    only invoked on a miss, which is the entire point: the Azure call does not
    happen at all when the answer is already known.

    Returns (payload, was_cached) so the caller can print an honest label.
    """
    key = key_for(operation, **parts)
    hit = get(key)
    if hit is not None:
        return hit, True
    payload = compute()
    put(key, payload, operation=operation, label=label)
    return payload, False


def summary() -> str:
    """One line, printed at the end of every script. No surprises."""
    if not ENABLED:
        return f"cache: OFF, {MISSES} live call(s)"
    return f"cache: {HITS} hit(s), {MISSES} live call(s)"


def clean(also_out: bool = True) -> list[str]:
    """
    Rip and replace. Removes the cache and, by default, out/.

    Returns what it deleted so the caller can print it. Deleting nothing is a
    success, not an error -- `--clean` on a fresh checkout should be quiet, not
    a traceback.
    """
    removed = []
    here = pathlib.Path(__file__).parent
    targets = [CACHE_DIR]
    if also_out:
        targets.append(here / "out")
    for target in targets:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            removed.append(target.name)
    return removed
