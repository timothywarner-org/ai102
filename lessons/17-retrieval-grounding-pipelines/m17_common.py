#!/usr/bin/env python
"""
AI-103 Lesson 17 - shared plumbing: names, credentials, REST, and printing.

WHY REST AND urllib INSTEAD OF azure-search-documents
-----------------------------------------------------
The SDK is the right answer in production, and the runbook says so out loud.
This repo speaks raw REST because THE JSON IS THE LESSON. Objective domain 5
tests whether you can look at a pipeline and name what is wrong with it, and
every one of those defects is visible only in the request body:

  * an `outputFieldMapping` reading an enrichment-tree path that does not exist
  * an `indexProjections` block missing a `parentKeyFieldName`
  * a `vectorSearch.profiles` entry that binds an algorithm and a vectorizer
  * a `cognitiveServices` attach of type `AIServicesByIdentity` rather than
    `CognitiveServicesByKey`
  * `imageAction` sitting on the INDEXER while the OCR skill sits in the SKILLSET

A typed client hides every one of those behind a constructor. Reading them here
is the transferable skill; the SDK call is the five minutes afterwards.

WHY AzureCliCredential AND NEVER DefaultAzureCredential
-------------------------------------------------------
`DefaultAzureCredential` probes environment variables FIRST. If a stale
`AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` pair is sitting in the shell -- and on
a machine that does Azure demos for a living, one usually is -- it will
authenticate as that service principal, silently, and you will spend the take
debugging a 403 that has nothing to do with your roles. `AzureCliCredential`
uses exactly one identity: whoever ran `az login`. On camera that is the only
acceptable answer.

TWO PLANES, TWO TOKEN AUDIENCES
-------------------------------
An Azure AI Search service has a control plane (ARM: create the service, set the
SKU, turn on the managed identity) and a data plane (create indexes, run
indexers, issue queries). They take DIFFERENT tokens, and Owner on the control
plane grants nothing on the data plane. That is the single most common 403 in
this service, so the scopes are named as constants below rather than buried.
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

import m17_cache

HERE = pathlib.Path(__file__).parent

# --- token audiences -------------------------------------------------------
SCOPE_SEARCH = "https://search.azure.com/.default"          # search DATA plane
SCOPE_STORAGE = "https://storage.azure.com/.default"        # blob data plane
SCOPE_FOUNDRY = "https://ai.azure.com/.default"             # Foundry projects
SCOPE_COGNITIVE = "https://cognitiveservices.azure.com/.default"

# --- object names ----------------------------------------------------------
# One prefix so a teardown is a prefix match and nothing else on the service is
# ever at risk. Every name is lowercase: index names are case-sensitive in URLs
# and a capital letter here costs you a confusing 404 later.
PREFIX = "l17-woodgrove"
CONTAINER = "l17-grounding"

INDEX = f"{PREFIX}-idx"
DATASOURCE = f"{PREFIX}-ds"
SKILLSET = f"{PREFIX}-ss"
INDEXER = f"{PREFIX}-ixr"
KNOWLEDGE_SOURCE = f"{PREFIX}-ks"
KNOWLEDGE_BASE = f"{PREFIX}-kb"

SEMANTIC_CONFIG = "l17-semantic"
VECTOR_PROFILE = "l17-vector-profile"
VECTOR_ALGORITHM = "l17-hnsw"
VECTORIZER = "l17-vectorizer"

# text-embedding-3-large emits 3072 dimensions. A mismatch here is not a
# relevance problem, it is a schema-level rejection at index-create time.
EMBEDDING_DIMENSIONS = 3072


class Fail(SystemExit):
    """A configuration or Azure failure worth stopping for, printed cleanly."""


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@dataclass
class Settings:
    search_endpoint: str
    subscription_id: str
    resource_group: str
    storage_account: str
    foundry_resource_uri: str
    foundry_openai_endpoint: str
    embedding_deployment: str
    chat_deployment: str
    project_endpoint: str
    api_version: str
    preview_api_version: str
    _tokens: dict = field(default_factory=dict, repr=False)

    @property
    def storage_resource_id(self) -> str:
        return (f"/subscriptions/{self.subscription_id}"
                f"/resourceGroups/{self.resource_group}"
                f"/providers/Microsoft.Storage/storageAccounts"
                f"/{self.storage_account}")

    @property
    def blob_endpoint(self) -> str:
        return f"https://{self.storage_account}.blob.core.windows.net"

    def token(self, scope: str) -> str:
        """
        Cache the token per scope for the life of the process.

        AzureCliCredential shells out to `az` on every call. That is roughly a
        second each time, and a script here makes a dozen calls. Without this
        the demo feels sluggish for a reason that has nothing to do with Azure.
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
        search_endpoint=need("SEARCH_ENDPOINT"),
        subscription_id=need("AZURE_SUBSCRIPTION_ID"),
        resource_group=need("AZURE_RESOURCE_GROUP"),
        storage_account=need("STORAGE_ACCOUNT"),
        foundry_resource_uri=need("FOUNDRY_RESOURCE_URI"),
        foundry_openai_endpoint=need("FOUNDRY_OPENAI_ENDPOINT"),
        embedding_deployment=need("EMBEDDING_DEPLOYMENT"),
        chat_deployment=need("CHAT_DEPLOYMENT"),
        project_endpoint=need("PROJECT_ENDPOINT"),
        api_version=need("SEARCH_API_VERSION"),
        preview_api_version=need("SEARCH_PREVIEW_API_VERSION"),
    )


# ---------------------------------------------------------------------------
# REST
# ---------------------------------------------------------------------------

class HttpError(RuntimeError):
    def __init__(self, status: int, body: str, method: str, url: str):
        self.status, self.body, self.method, self.url = status, body, method, url
        super().__init__(f"HTTP {status} on {method} {url}\n{body}")

    def short(self, limit: int = 300) -> str:
        """The message Azure actually returned, collapsed to one line."""
        try:
            detail = json.loads(self.body)["error"]["message"]
        except Exception:
            detail = self.body
        detail = " ".join(str(detail).split())
        return f"HTTP {self.status}: {detail[:limit]}"


def request(method: str, url: str, token: str, body=None,
            extra_headers: dict | None = None, timeout: int = 180):
    """One raw HTTPS call. Returns (status, parsed-or-text)."""
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
    except urllib.error.HTTPError as exc:
        raise HttpError(exc.code, exc.read().decode("utf-8", "replace"),
                        method, url) from None
    if not raw:
        return status, None
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw


class Search:
    """Thin data-plane client for one search service."""

    def __init__(self, settings: Settings):
        self.s = settings

    def url(self, path: str, api_version: str | None = None, **query) -> str:
        version = api_version or self.s.api_version
        parts = [f"api-version={version}"]
        parts += [f"{k}={v}" for k, v in query.items()]
        return f"{self.s.search_endpoint}/{path.lstrip('/')}?{'&'.join(parts)}"

    def call(self, method: str, path: str, body=None,
             api_version: str | None = None, **query):
        """A live call. Never cached -- see cached() for the read-only path."""
        url = self.url(path, api_version, **query)
        return request(method, url, self.s.token(SCOPE_SEARCH), body)

    def cached(self, operation: str, label: str, method: str, path: str,
               body=None, api_version: str | None = None, **query):
        """
        A read-only call that may replay from the cache.

        The cache key covers the URL and the body, so an api-version change or
        a single edited character in the query text is a different key and goes
        live. Returns (payload, was_cached).
        """
        url = self.url(path, api_version, **query)
        return m17_cache.remember(
            operation, label,
            lambda: request(method, url, self.s.token(SCOPE_SEARCH), body)[1],
            url=url, body=body)

    def exists(self, path: str, api_version: str | None = None) -> bool:
        try:
            self.call("GET", path, api_version=api_version)
            return True
        except HttpError as exc:
            if exc.status == 404:
                return False
            raise


# ---------------------------------------------------------------------------
# Printing. Structured, bold-free, no color -- every cue is positional or
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
