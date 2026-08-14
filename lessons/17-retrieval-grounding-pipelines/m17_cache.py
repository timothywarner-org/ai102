#!/usr/bin/env python
"""
AI-103 Lesson 17 - content-addressed cache so retakes replay byte-identically.

Same design as Lessons 14, 15 and 16. The key is a hash of the request CONTENT:
the endpoint, the API version, and the exact request body. Same query against
the same index, same key, instant replay. Change one character of the query and
the call goes live.

WHAT THIS CACHE IS ALLOWED TO TOUCH -- READ THIS BEFORE ADDING A CALL
--------------------------------------------------------------------
Only SAFE, READ-ONLY calls: search queries, retrieve calls, GETs. Nothing that
mutates the service is ever cached, and `remember()` refuses anything that is
not a documented-safe operation.

That restriction is the whole point. A cached PUT would let this repo report
"skillset created" while the service sat empty, which is precisely the failure
mode that cost Lesson 16 a rebuild -- an assertion about a request proving
nothing about the service. `m17_ingest.py` therefore has no cache at all. It is
idempotent instead, which is the honest equivalent: run it twice and the second
run is fast because the SERVICE did less work, not because this file lied about
it.

Scores are what end up on screen in Beat 3, and a reranker score that shifts
between takes is a re-record. That is what this buys.

    --no-cache   ignore the cache, call Azure every time
    --clean      delete .cache/ and out/, then continue
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

# An allowlist, not a blocklist. A blocklist fails open the day someone adds a
# new mutating operation and forgets to exclude it.
SAFE_OPERATIONS = {
    "search",            # POST /indexes/{name}/docs/search
    "retrieve",          # POST /knowledgeBases/{name}/retrieve
    "get",               # any GET
    "count",             # GET /indexes/{name}/docs/$count
    "chat",              # POST /chat/completions -- grounded answer generation
}


class UnsafeToCache(RuntimeError):
    """Raised when something tries to cache a call that changes Azure state."""


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
        return entry["payload"]
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def put(key: str, payload, operation: str = "", label: str = "") -> None:
    if not ENABLED:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(
        json.dumps({"operation": operation, "label": label,
                    "payload": payload}, indent=2),
        encoding="utf-8")


def remember(operation: str, label: str, compute, **parts):
    """
    Return (payload, was_cached). `compute` only runs on a miss.

    Refuses any operation outside SAFE_OPERATIONS, loudly and at call time.
    """
    global MISSES
    if operation not in SAFE_OPERATIONS:
        raise UnsafeToCache(
            f"'{operation}' is not a read-only operation. This cache never "
            f"stands in for a call that changes the service. Safe operations: "
            f"{sorted(SAFE_OPERATIONS)}")
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
        return "cache: disabled (--no-cache), every query went live"
    return f"cache: {HITS} replayed, {MISSES} live"


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


def add_cache_arguments(parser) -> None:
    """Identical flags in every script, so there is one thing to remember."""
    parser.add_argument("--no-cache", action="store_true",
                        help="ignore the cache; every query goes live")
    parser.add_argument("--clean", action="store_true",
                        help="delete .cache/ and out/ first, then continue")


def apply_cache_arguments(args) -> None:
    global ENABLED
    if getattr(args, "clean", False):
        for item in clean():
            print(f"  removed {item}")
    if getattr(args, "no_cache", False):
        ENABLED = False
