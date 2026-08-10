"""
rag.py -- Lesson 8 classic RAG demo, end to end, in code.

This is the "code" half of the Lesson 8 story. The portal half shows the
managed **knowledge base** abstraction (Foundry IQ / agentic retrieval); this
file shows **classic RAG** -- the pattern you own and control:

    ingest  ->  embed  ->  retrieve  ->  inject  ->  generate-grounded

It runs against a dedicated Azure AI Search instance and a Foundry project
that has a chat model (generation) and an embedding model (retrieval). Every
call is keyless: Entra ID via `az login`, no API keys on disk.

FOUR SUBCOMMANDS -- each is one demo beat:

    uv run rag.py ingest
        (a) Run the embedding job. Build the index, embed every knowledge-base
            article with the embedding model, and push the vectors in.

    uv run rag.py search "what is few-shot learning?"
        (b) Retrieval in code. Embed the question, run a HYBRID (keyword +
            vector) query, and print the passages that come back.

    uv run rag.py ask "how do temperature and top_p differ?"
        The full loop. Retrieve, inject the passages as context, and have the
        chat model answer ONLY from that context -- grounded, with citations.

    uv run rag.py reindex
        (c) Force reindexing after adding a new document. Add a brand-new
            article, embed just that one, upload it, and immediately prove it
            is now retrievable. This is the "push model" of indexing: you own
            the write, so a re-upload IS the reindex -- no nightly batch, no
            waiting on an indexer.

Prereqs (provisioned by the L8 infra):
    * Foundry project with a chat deployment + an embedding deployment
    * A dedicated Azure AI Search service, connected to the project
    * Roles: Search Index Data Contributor, Cognitive Services OpenAI User
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import time

from dotenv import load_dotenv
import openai
from openai import AzureOpenAI

# VS Code's integrated terminal (and some shells) can inject HTTP(S)_PROXY vars
# that point at a proxy which doesn't resolve on this network. httpx then tries
# to resolve the PROXY host and fails with "getaddrinfo failed" even though the
# Azure endpoint is reachable directly. These demos hit public Azure endpoints
# with no proxy required, so we strip any inherited proxy vars in-process. This
# is the durable fix for the intermittent connection blips.
import os as _os
for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    _os.environ.pop(_pv, None)
from azure.identity import AzureCliCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
)

# -----------------------------------------------------------------------------
# Configuration -- everything from .env, no secrets in code.
# -----------------------------------------------------------------------------
# override=True makes THIS project's .env authoritative. Without it, a stale
# AZURE_OPENAI_ENDPOINT lingering in the shell (say, from an old project) wins
# over .env and sends every call to a dead endpoint. Hard-won lesson.
load_dotenv(override=True)

SEARCH_ENDPOINT = os.environ["SEARCH_ENDPOINT"]
AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
INDEX_NAME = os.getenv("SEARCH_INDEX_NAME", "m365-knowledge")
EMBEDDING_DEPLOYMENT = os.getenv("EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-large")
CHAT_DEPLOYMENT = os.getenv("CHAT_DEPLOYMENT_NAME", "gpt-5-mini")

# text-embedding-3-large emits 3072-dim vectors; the index field must match.
EMBEDDING_DIMENSIONS = 3072
COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"

# One credential for Search AND the models -- borrowed from `az login`.
CREDENTIAL = AzureCliCredential()
_TOKEN_PROVIDER = get_bearer_token_provider(CREDENTIAL, COGNITIVE_SCOPE)


def openai_client() -> AzureOpenAI:
    """Keyless Azure OpenAI client for both embeddings and chat.

    max_retries lets the SDK ride out transient network/DNS blips and 429s with
    exponential backoff, so a momentary hiccup doesn't abort the whole run.
    """
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=_TOKEN_PROVIDER,
        api_version=AZURE_OPENAI_API_VERSION,
        max_retries=2,   # fail fast -- the requests-based fallback below takes over
        timeout=30.0,
    )


# -----------------------------------------------------------------------------
# Fallback transport. The OpenAI SDK rides on httpx; the Azure Search SDK rides
# on requests. On some machines the httpx path hits transient connection errors
# while requests sails through in the very same process. So when httpx trips,
# we call the identical REST endpoint through requests -- same URL, same Entra
# bearer token, same JSON -- and the demo keeps rolling instead of stack-tracing.
# -----------------------------------------------------------------------------
def _embed_via_requests(texts: list[str]) -> list[list[float]]:
    import requests as _rq
    url = (f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/"
           f"{EMBEDDING_DEPLOYMENT}/embeddings?api-version={AZURE_OPENAI_API_VERSION}")
    r = _rq.post(url, headers={"Authorization": f"Bearer {_TOKEN_PROVIDER()}"},
                 json={"input": texts}, timeout=60)
    r.raise_for_status()
    data = sorted(r.json()["data"], key=lambda d: d["index"])
    return [d["embedding"] for d in data]


def _chat_via_requests(messages: list[dict], max_completion_tokens: int) -> str:
    import requests as _rq
    url = (f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/"
           f"{CHAT_DEPLOYMENT}/chat/completions?api-version={AZURE_OPENAI_API_VERSION}")
    r = _rq.post(url, headers={"Authorization": f"Bearer {_TOKEN_PROVIDER()}"},
                 json={"messages": messages, "max_completion_tokens": max_completion_tokens},
                 timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"] or "(empty)"


def search_client() -> SearchClient:
    return SearchClient(SEARCH_ENDPOINT, INDEX_NAME, credential=CREDENTIAL)


# -----------------------------------------------------------------------------
# The knowledge base: REAL documents pulled from Tim's Microsoft 365 tenant
# (SharePoint / OneDrive). The base docs are chunked from a prompt-engineering
# guide; the "new document" the reindex beat adds is from the 2025 Responsible
# AI Transparency Report. Content + source URLs live in m365_docs.json so the
# corpus is data, not code -- swap the JSON to point the demo at your own files.
# -----------------------------------------------------------------------------
_DATA = json.loads((pathlib.Path(__file__).parent / "m365_docs.json").read_text(encoding="utf-8"))
KB_DOCS = _DATA["docs"]
NEW_DOC = _DATA["new_doc"]


def build_index() -> None:
    """Create or update the vector index. Idempotent."""
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="category", type=SearchFieldDataType.String, filterable=True),
        # Provenance: which M365 file this passage came from, and its SharePoint
        # URL -- so a grounded answer can cite the real source document.
        SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="url", type=SearchFieldDataType.String),
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name="hnsw-cosine",
        ),
    ]
    # HNSW graph + cosine distance -- the standard choice for OpenAI embeddings.
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
        profiles=[VectorSearchProfile(name="hnsw-cosine", algorithm_configuration_name="hnsw-config")],
    )
    # Semantic configuration: tells the semantic RANKER which fields carry the
    # meaning (title vs body vs keywords) so it can re-rank hits by relevance.
    # Foundry knowledge sources require this -- and it needs a Basic-or-higher
    # search tier, because the free tier has no semantic ranker at all.
    semantic = SemanticSearch(
        default_configuration_name="default",
        configurations=[SemanticConfiguration(
            name="default",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="title"),
                content_fields=[SemanticField(field_name="content")],
                keywords_fields=[SemanticField(field_name="category")],
            ),
        )],
    )
    SearchIndexClient(SEARCH_ENDPOINT, credential=CREDENTIAL).create_or_update_index(
        SearchIndex(name=INDEX_NAME, fields=fields,
                    vector_search=vector_search, semantic_search=semantic)
    )
    print(f"[index] '{INDEX_NAME}' ready ({EMBEDDING_DIMENSIONS}-dim vectors, semantic config 'default').")


def embed(client: AzureOpenAI, texts: list[str]) -> list[list[float]]:
    """Embed text with the deployment (pass the DEPLOYMENT name as `model`).

    Belt-and-suspenders on top of the client's own retries: if a network blip
    (DNS/connection/timeout) still slips through, wait and try again with a
    visible message instead of a stack trace. Because uploads are idempotent
    upserts, a retried run never duplicates or corrupts anything.
    """
    try:
        resp = client.embeddings.create(model=EMBEDDING_DEPLOYMENT, input=texts)
        return [item.embedding for item in resp.data]
    except (openai.APIConnectionError, openai.APITimeoutError):
        # httpx path tripped -- switch to the requests transport and keep moving.
        print("  [fallback] primary transport blipped; using alternate transport...")
        return _embed_via_requests(texts)


def upload_one(client: AzureOpenAI, sc: SearchClient, doc: dict, label: str = "") -> bool:
    """Embed and upload a SINGLE document.

    One doc at a time on purpose: you can watch each article get embedded and
    indexed, and test retrieval after any single write. `merge_or_upload` is an
    UPSERT -- insert if the id is new, replace in place if it already exists.
    That is what makes every run IDEMPOTENT: run this ten times and the index
    looks exactly like running it once. No duplicates, no drift, ever.
    """
    vector = embed(client, [doc["content"]])[0]
    result = sc.merge_or_upload_documents(documents=[{**doc, "contentVector": vector}])[0]
    status = "indexed" if result.succeeded else f"FAILED: {result.error_message}"
    print(f"  {label}{doc['id']}  '{doc['title']}'  ({len(vector)}-dim) -> {status}")
    return result.succeeded


def retrieve(client: AzureOpenAI, sc: SearchClient, query: str, k: int = 3) -> list[dict]:
    """Hybrid search: keyword + vector, fused by Reciprocal Rank Fusion."""
    query_vector = embed(client, [query])[0]
    vector_query = VectorizedQuery(vector=query_vector, k_nearest_neighbors=k, fields="contentVector")
    results = sc.search(
        search_text=query,           # keyword arm
        vector_queries=[vector_query],  # vector arm
        select=["id", "title", "category", "content", "source", "url"],
        top=k,
    )
    return list(results)


# -----------------------------------------------------------------------------
# Subcommands
# -----------------------------------------------------------------------------
def cmd_ingest(_args) -> None:
    """(a) Run the embedding job -- ONE DOCUMENT AT A TIME, idempotent."""
    client, sc = openai_client(), search_client()
    build_index()  # create_or_update_index: idempotent, safe on every run.
    print(f"[embed] embedding + uploading {len(KB_DOCS)} articles one at a time "
          f"with '{EMBEDDING_DEPLOYMENT}'...")
    ok = 0
    for i, doc in enumerate(KB_DOCS, 1):
        # Each doc is embedded and upserted on its own, so you see -- and can
        # test -- the index grow one article at a time.
        ok += upload_one(client, sc, doc, label=f"[{i}/{len(KB_DOCS)}] ")
    print(f"[ingest] {ok}/{len(KB_DOCS)} indexed. Re-run any time -- upserts keep it idempotent.")


def cmd_search(args) -> None:
    """(b) Retrieval in code: show what hybrid search returns for a question."""
    client, sc = openai_client(), search_client()
    print(f"[search] {args.query!r}")
    for i, hit in enumerate(retrieve(client, sc, args.query), 1):
        print(f"  {i}. [{hit['category']}] {hit['title']}  (score {hit['@search.score']:.4f})")
        print(f"       source: {hit['source']}")


def cmd_ask(args) -> None:
    """Full RAG: retrieve, inject as context, generate a grounded answer."""
    client, sc = openai_client(), search_client()
    hits = retrieve(client, sc, args.query)

    # Inject: stitch the retrieved passages into a single context block, each
    # tagged with its title so the model can cite by name.
    context = "\n\n".join(f"[{h['title']}]\n{h['content']}" for h in hits)

    # The grounding instruction is the whole ballgame: answer ONLY from context,
    # and admit it when the answer isn't there. That single rule is what turns a
    # confident guesser into a trustworthy assistant.
    system = (
        "You are a knowledge assistant answering from the user's own documents. "
        "Answer the question using ONLY the context below. Cite the article "
        "titles you used in brackets. If the context does not contain the "
        "answer, say you don't have that information -- do not invent anything.\n\n"
        f"Context:\n{context}"
    )
    print(f"[ask] {args.query!r}\n[retrieved] " +
          ", ".join(h["title"] for h in hits) + "\n")

    # gpt-5-mini is a reasoning model: it uses max_completion_tokens (not
    # max_tokens) and ignores temperature. Reasoning tokens count against the
    # budget, so size it generously or the visible answer comes back empty.
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": args.query}]
    try:
        resp = client.chat.completions.create(
            model=CHAT_DEPLOYMENT, messages=messages, max_completion_tokens=1500,
        )
        answer = resp.choices[0].message.content or "(empty)"
    except (openai.APIConnectionError, openai.APITimeoutError):
        print("  [fallback] primary transport blipped; using alternate transport...")
        answer = _chat_via_requests(messages, 1500)
    print("[answer]\n" + answer)
    # Show the real source files behind the answer -- these are the user's own
    # M365 documents, with clickable SharePoint URLs.
    print("\n[sources]")
    for h in hits:
        print(f"  - {h['source']} :: {h['url']}")


def cmd_reindex(_args) -> None:
    """(c) Force reindexing after adding a new doc, and prove it's retrievable."""
    client, sc = openai_client(), search_client()
    probe = "What is Microsoft's approach to responsible AI governance?"

    # Reset the before-state so the demo is self-contained AND idempotent: if a
    # previous run already added the new article, delete it first. delete is a
    # no-op when the doc isn't there, so `reindex` tells the identical story
    # every single run -- that's idempotency applied to the demo itself.
    sc.delete_documents(documents=[{"id": NEW_DOC["id"]}])
    time.sleep(1.5)  # let the delete settle before we read.

    before = retrieve(client, sc, probe, k=1)
    print(f"[before] top hit for the responsible-AI question: "
          f"{before[0]['title'] if before else '(nothing)'}")

    # REINDEX: embed + upsert just the new document, one doc. In the push model
    # a re-upload IS the reindex -- no indexer to reset, no batch to wait for.
    # (With the pull model you'd run or reset an Azure AI Search indexer; here we
    # own the write path, so it's immediate.)
    print(f"[reindex] adding + embedding new article: {NEW_DOC['title']!r}...")
    upload_one(client, sc, NEW_DOC, label="  ")

    # AFTER: push-model writes are near-immediate but NOT synchronous -- a fresh
    # doc takes a beat to become searchable. Poll briefly so the demo lands the
    # same way every take instead of racing the index.
    for _ in range(8):
        after = retrieve(client, sc, probe, k=1)
        if after and after[0]["id"] == NEW_DOC["id"]:
            print(f"[after]  top hit for the responsible-AI question: {after[0]['title']}")
            print("[reindex] SUCCESS -- the new document is live and retrievable.")
            return
        time.sleep(1.5)
    print("[after]  new document still catching up; re-run `search` in a moment.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lesson 8 classic RAG demo.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ingest", help="(a) build the index + run the embedding job")
    p_search = sub.add_parser("search", help="(b) retrieval in code")
    p_search.add_argument("query")
    p_ask = sub.add_parser("ask", help="full RAG: retrieve + grounded answer")
    p_ask.add_argument("query")
    sub.add_parser("reindex", help="(c) add a new doc + force reindex")

    args = parser.parse_args()
    {"ingest": cmd_ingest, "search": cmd_search, "ask": cmd_ask, "reindex": cmd_reindex}[args.command](args)


if __name__ == "__main__":
    main()
