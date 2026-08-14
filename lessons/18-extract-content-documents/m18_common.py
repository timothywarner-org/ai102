#!/usr/bin/env python
"""
AI-103 Lesson 18 - shared plumbing for Content Understanding over REST.

WHY REST AND urllib INSTEAD OF azure-ai-contentunderstanding
------------------------------------------------------------
There IS a stable Python SDK (`azure-ai-contentunderstanding`, GA March 2026),
and the runbook says out loud that it is the right answer in production. This
lesson speaks raw REST for the same reason Lesson 17 does: THE JSON IS THE
LESSON. Objective domain 5 tests whether you can look at an analyzer and say
what it will and will not return, and every one of those answers lives in the
request body:

  * `baseAnalyzerId` accepts exactly FOUR values, and the domain prebuilt you
    actually want (prebuilt-invoice) is not one of them
  * `estimateFieldSourceAndConfidence` is the switch that decides whether
    grounding comes back at all - it is OFF by default
  * `method` on a field is extract | classify | generate, and the choice
    changes the shape of the grounding you get back
  * `models.completion` is mandatory the moment you add a fieldSchema, and
    omitting it fails the BUILD, not the analyze

A typed client turns each of those into a constructor keyword and a docstring
you will not read on camera. Reading them here is the transferable skill.

WHY AzureCliCredential AND NEVER DefaultAzureCredential
-------------------------------------------------------
`DefaultAzureCredential` probes environment variables FIRST. If a stale
`AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` pair is sitting in the shell - and on
a machine that does Azure demos for a living, one usually is - it authenticates
as that service principal, silently, and you lose the take to a 403 that has
nothing to do with your roles. `AzureCliCredential` uses exactly one identity:
whoever ran `az login`.

ONE PLANE, ONE AUDIENCE (UNLIKE LESSON 17)
------------------------------------------
Lesson 17 juggled three token audiences because Search, Storage, and Foundry
are three services. Content Understanding is one data plane on the Foundry
resource, so there is exactly one scope here:
`https://cognitiveservices.azure.com/.default`. Say that out loud on camera -
the contrast with L17 is the point, not an accident.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

HERE = pathlib.Path(__file__).parent
CORPUS = HERE / "assets" / "corpus"

# --- token audience --------------------------------------------------------
# One service, one scope. Content Understanding rides the Foundry (AIServices)
# account's data plane, which is the Cognitive Services audience.
SCOPE_COGNITIVE = "https://cognitiveservices.azure.com/.default"

# --- object names ----------------------------------------------------------
# One prefix so teardown is a prefix match and nothing else on the account is
# ever at risk. L13 also created an analyzer on this shared account, so a
# careless `delete everything` here would take out another lesson's asset.
PREFIX = "ai103L18"
CUSTOM_ANALYZER = f"{PREFIX}AddendumV1"

# --- the prebuilt ladder ---------------------------------------------------
# Deck slide 4: "Prebuilt analyzers ladder from OCR to tuned schemas."
# These three are rungs on that ladder, and Beat 1 runs all three over the SAME
# scanned page so the ladder is visible rather than asserted.
ANALYZER_DIGITAL = "prebuilt-digitalParse"   # skips pixels entirely
ANALYZER_READ = "prebuilt-read"              # text, no layout analysis
ANALYZER_LAYOUT = "prebuilt-layout"          # text + structure + sections

# The four legal base analyzers. This list is short on purpose: it is the whole
# answer to "what can a custom analyzer inherit from", and it is a favorite
# exam distractor because prebuilt-invoice looks like it belongs and does not.
BASE_ANALYZERS = ("prebuilt-document", "prebuilt-audio",
                  "prebuilt-video", "prebuilt-image")


class Fail(SystemExit):
    """A configuration or Azure failure worth stopping for, printed cleanly."""


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@dataclass
class Settings:
    endpoint: str
    api_version: str
    completion_model: str
    embedding_model: str
    _tokens: dict = field(default_factory=dict, repr=False)

    def cu_url(self, path: str, **query) -> str:
        """Build a /contentunderstanding/ URL with the api-version attached."""
        parts = [f"api-version={self.api_version}"]
        parts += [f"{k}={v}" for k, v in query.items()]
        joined = "&".join(parts)
        return f"{self.endpoint}/contentunderstanding/{path.lstrip('/')}?{joined}"

    def token(self, scope: str = SCOPE_COGNITIVE) -> str:
        """
        Cache the token per scope for the life of the process.

        AzureCliCredential shells out to `az` on every call, roughly a second
        each time. A single beat here makes a dozen calls, so without this the
        demo feels sluggish for a reason that has nothing to do with Azure.
        """
        entry = self._tokens.get(scope)
        if entry and entry[1] - time.time() > 120:
            return entry[0]
        from azure.identity import AzureCliCredential
        access = AzureCliCredential().get_token(scope)
        self._tokens[scope] = (access.token, access.expires_on)
        return access.token


def load_settings() -> Settings:
    from dotenv import load_dotenv

    env_path = HERE / ".env"
    if not env_path.exists():
        raise Fail("No .env found. Copy .env.example to .env and fill it in.")
    # override=True: a variable already exported in the shell must NOT win over
    # the file. Otherwise last week's endpoint quietly shadows this week's.
    load_dotenv(env_path, override=True)

    def need(name: str) -> str:
        value = (os.getenv(name) or "").strip().rstrip("/")
        if not value:
            raise Fail(f"{name} is missing or empty in .env")
        return value

    return Settings(
        endpoint=need("CONTENT_UNDERSTANDING_ENDPOINT"),
        api_version=need("CONTENT_UNDERSTANDING_API_VERSION"),
        completion_model=need("CU_COMPLETION_MODEL"),
        embedding_model=need("CU_EMBEDDING_MODEL"),
    )


# ---------------------------------------------------------------------------
# REST
# ---------------------------------------------------------------------------

class HttpError(RuntimeError):
    def __init__(self, status: int, body: str, method: str, url: str):
        self.status, self.body, self.method, self.url = status, body, method, url
        super().__init__(f"HTTP {status} on {method} {url}\n{body}")

    def short(self, limit: int = 400) -> str:
        """
        The message Azure actually returned, collapsed to one line.

        Content Understanding puts the useful sentence in error.innererror.message
        and a useless "Invalid request." in error.message, so read the inner one
        first. The innererror is where the service tells you the actual fix.
        """
        try:
            err = json.loads(self.body)["error"]
            detail = (err.get("innererror") or {}).get("message") or err.get("message")
        except Exception:
            detail = self.body
        detail = " ".join(str(detail).split())
        return f"HTTP {self.status}: {detail[:limit]}"


def request(method: str, url: str, token: str, body=None,
            extra_headers: dict | None = None, timeout: int = 180):
    """One raw HTTPS call. Returns (status, parsed-or-text, headers)."""
    payload = None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    headers.update(extra_headers or {})

    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8") if response.length != 0 else ""
            status = response.status
            got = dict(response.headers)
    except urllib.error.HTTPError as exc:
        raise HttpError(exc.code, exc.read().decode("utf-8", "replace"),
                        method, url) from None
    if not raw:
        return status, None, got
    try:
        return status, json.loads(raw), got
    except json.JSONDecodeError:
        return status, raw, got


class ContentUnderstanding:
    """Thin data-plane client for one Foundry account's CU endpoint."""

    def __init__(self, settings: Settings):
        self.s = settings

    def call(self, method: str, path: str, body=None, **query):
        return request(method, self.s.cu_url(path, **query), self.s.token(), body)

    # -- the long-running-operation pattern ---------------------------------
    # Deck slide 10: "Build and analyze are both long-running operations."
    # Both return 202/201 plus an Operation-Location header, and BOTH can come
    # back Failed with HTTP 200 on the poll. A poll that returns 200 tells you
    # the polling worked, not that the work worked. That distinction is the
    # single most common misread in this API.
    def poll(self, operation_url: str, label: str,
             every: float = 2.0, limit: int = 90) -> dict:
        deadline = time.time() + limit
        seen = None
        while time.time() < deadline:
            _, payload, _ = request("GET", operation_url, self.s.token())
            status = (payload or {}).get("status")
            if status != seen:
                step(f"{label}: {status}")
                seen = status
            if status in ("Succeeded", "Failed", "Canceled"):
                return payload
            time.sleep(every)
        raise Fail(f"{label} did not finish within {limit}s")

    def analyze(self, analyzer_id: str, source: dict, label: str) -> dict:
        """
        Submit one input and wait for the result.

        `source` is {"url": ...} or {"data": <base64>}. Note the shape: the
        service takes an `inputs` ARRAY and then rejects anything other than
        exactly one item on this API version. The array is forward-looking,
        not a batch you can use today.
        """
        status, _, headers = self.call(
            "POST", f"analyzers/{analyzer_id}:analyze", {"inputs": [source]})
        op = headers.get("Operation-Location") or headers.get("operation-location")
        if not op:
            raise Fail(f"No Operation-Location on analyze ({status})")
        result = self.poll(op, label)
        if result.get("status") != "Succeeded":
            detail = json.dumps(result.get("error", {}))[:400]
            raise Fail(f"{label} failed: {detail}")
        return result["result"]

    def delete_analyzer(self, analyzer_id: str) -> bool:
        """Idempotent delete. A 404 means the desired end state already holds."""
        try:
            self.call("DELETE", f"analyzers/{analyzer_id}")
            return True
        except HttpError as exc:
            if exc.status == 404:
                return False
            raise


# ---------------------------------------------------------------------------
# Reading results
# ---------------------------------------------------------------------------

def first_content(result: dict) -> dict:
    """Every analyze result nests the real payload one level down in contents."""
    contents = result.get("contents") or []
    if not contents:
        return {}
    return contents[0]


def decode_source(source: str) -> str:
    """
    Turn a `source` string into something a human can hear read aloud.

    The wire format is compact and unlabeled:
        D(1,152.0,336.0,864.3,341.9,864.0,378.1,151.7,372.2)
    which is page 1 followed by FOUR x,y pairs - a bounding polygon, not a
    rectangle, because scanned text is often skewed. Multiple regions are
    joined with ';' when one value was assembled from several places on the
    page. Rendering it as "page 1, 4-point polygon" on screen is the difference
    between a wall of decimals and a point the audience actually gets.
    """
    if not source:
        return "(none)"
    regions = [r for r in source.split(";") if r.strip()]
    pages, shape, unit = [], "region", "page"
    for region in regions:
        body = region.strip()
        kind = body[:1]
        inner = body[body.find("(") + 1:body.rfind(")")]
        numbers = [n for n in inner.split(",") if n]
        if not numbers:
            continue
        pages.append(numbers[0])
        coords = (len(numbers) - 1) // 2
        shape = "4-point polygon" if coords == 4 else f"{coords}-point region"
        unit = "page" if kind == "D" else "time"
    if not pages:
        return source[:60]
    # A `generate` field can ground to a dozen regions. Printing each one turns
    # the most interesting line of the beat into a wall of identical text, so
    # summarize: the COUNT is the teaching point, not the individual polygons.
    distinct = sorted(set(pages), key=pages.index)
    where = f"{unit} {distinct[0]}" if len(distinct) == 1 else f"{unit}s {', '.join(distinct)}"
    if len(pages) == 1:
        return f"{where}, {shape}"
    return f"{where}, {len(pages)} x {shape}"


# ---------------------------------------------------------------------------
# Printing. Structured, bold-free, no color - every cue is positional or
# textual, because color is not a channel this course uses.
# ---------------------------------------------------------------------------

WIDTH = 78


def banner(title: str, subtitle: str = "") -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print()
    print("=" * WIDTH)
    print(f"  {title}")
    if subtitle:
        print(f"  {subtitle}")
    print("=" * WIDTH)


def head(title: str) -> None:
    print()
    print(f"-- {title} " + "-" * max(0, WIDTH - len(title) - 4))


def kv(label: str, value, width: int = 26) -> None:
    print(f"  {label:<{width}} {value}")


def ok(message: str) -> None:
    print(f"  [OK]   {message}")


def warn(message: str) -> None:
    print(f"  [WARN] {message}")


def bad(message: str) -> None:
    print(f"  [FAIL] {message}")


def step(message: str) -> None:
    print(f"  ...    {message}")


def quote(text: str, indent: str = "  | ", limit: int | None = None) -> None:
    """Print a block of extracted text so it reads as evidence, not output."""
    body = text if limit is None else text[:limit]
    for line in body.splitlines() or [""]:
        print(f"{indent}{line}")
    if limit is not None and len(text) > limit:
        print(f"{indent}... ({len(text) - limit} more characters)")
