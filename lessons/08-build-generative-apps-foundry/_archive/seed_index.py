"""
seed_index.py -- Warm the Lesson 8 RAG lab by building a real, retrievable index.

WHAT THIS DOES (and WHY it exists)
----------------------------------
Lesson 8 teaches Retrieval-Augmented Generation (RAG). A RAG demo is only
convincing if the index actually holds content the model can retrieve. This
script stands up that content: it creates a small vector index in Azure AI
Search and loads a fictional "Contoso Cloud" support knowledge base, with each
article embedded by text-embedding-3-large so we can search by *meaning*, not
just keywords.

It is deliberately written as a teaching artifact:
  * Keyless end to end -- Entra ID via AzureCliCredential, no API keys on disk.
  * Idempotent -- create-or-update the index and merge-or-upload the docs, so
    you can re-run it as many times as you like without duplicating anything.
  * Client-side embeddings -- we embed here, at ingest time, because the FREE
    Azure AI Search tier has no managed identity and therefore cannot call the
    embedding model itself (integrated vectorization needs a paid tier). This
    mirrors what a real ingestion pipeline does anyway.

RBAC you need (already granted by infra/modules/search.bicep + the L7 infra):
  * Search Index Data Contributor  -> create the index and upload documents
  * Cognitive Services OpenAI User -> call the embedding deployment

Run it:
    uv run seed_index.py            # build + load the index
    uv run seed_index.py --query "how do I rotate API keys?"   # smoke-test retrieval
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.identity import AzureCliCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
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
)

# -----------------------------------------------------------------------------
# Configuration -- everything comes from .env so no secrets live in the code.
# -----------------------------------------------------------------------------
load_dotenv()

SEARCH_ENDPOINT = os.environ["SEARCH_ENDPOINT"]
AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
INDEX_NAME = os.getenv("SEARCH_INDEX_NAME", "contoso-support")
EMBEDDING_DEPLOYMENT = os.getenv("EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-large")

# text-embedding-3-large returns 3072-dimension vectors. The index vector field
# MUST match this exactly, or uploads are rejected.
EMBEDDING_DIMENSIONS = 3072

# Cognitive Services token audience -- the scope the embedding model expects.
COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"

# One credential, reused for Search AND the embedding model. AzureCliCredential
# is the repo standard: it borrows the identity from `az login`, so the same
# person who deployed the lab is the one seeding it -- no service principals,
# no keys to rotate or leak.
CREDENTIAL = AzureCliCredential()

# A bearer-token provider turns that credential into the short-lived tokens the
# Azure OpenAI client needs, refreshing them automatically. This is the keyless
# equivalent of an API key -- nothing sensitive ever touches disk.
_TOKEN_PROVIDER = get_bearer_token_provider(CREDENTIAL, COGNITIVE_SCOPE)


def openai_client() -> AzureOpenAI:
    """A keyless Azure OpenAI client pointed at the account's embedding deployment."""
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=_TOKEN_PROVIDER,
        api_version=AZURE_OPENAI_API_VERSION,
    )


# -----------------------------------------------------------------------------
# The knowledge base. A deliberately tiny, self-contained support KB for a
# fictional "Contoso Cloud" product. Small enough to read at a glance, varied
# enough that vector search has something interesting to disambiguate.
# -----------------------------------------------------------------------------
KB_DOCS = [
    {
        "id": "kb-001",
        "title": "Rotating your Contoso Cloud API keys",
        "category": "security",
        "content": (
            "You rotate API keys from Portal > Settings > API Keys > Rotate. "
            "Rotation issues a new key immediately and keeps the previous key "
            "valid for a 24-hour grace window, so active sessions do not drop "
            "as long as you swap the key within that window. Rotate keys on a "
            "regular schedule and any time a key may have been exposed."
        ),
    },
    {
        "id": "kb-002",
        "title": "Duplicate charges and refunds",
        "category": "billing",
        "content": (
            "If an invoice is charged twice, Support can flag the duplicate and "
            "Finance issues the refund to the original payment method within 5 "
            "to 7 business days. Have the invoice number ready. Refunds cannot "
            "be redirected to a different card than the one originally charged."
        ),
    },
    {
        "id": "kb-003",
        "title": "Checkout API returning 503 errors",
        "category": "reliability",
        "content": (
            "A 503 from the /v2/checkout endpoint means the service is "
            "temporarily unavailable, usually during a regional incident or a "
            "throttling event. Check the status page first. Client code should "
            "retry with exponential backoff and a capped number of attempts "
            "rather than hammering the endpoint, which prolongs the outage."
        ),
    },
    {
        "id": "kb-004",
        "title": "Where to find platform status and incidents",
        "category": "reliability",
        "content": (
            "Live platform status and active incident history are published at "
            "status.contoso.example. Subscribe there for email or webhook "
            "alerts so your on-call team hears about a regional incident before "
            "your customers do."
        ),
    },
    {
        "id": "kb-005",
        "title": "Rate limits and throttling (429 responses)",
        "category": "reliability",
        "content": (
            "Each Contoso Cloud plan has a per-minute request quota. Exceeding "
            "it returns HTTP 429 with a Retry-After header telling you how many "
            "seconds to wait. Honor Retry-After instead of retrying instantly. "
            "If you consistently hit the limit, upgrade the plan or request a "
            "quota increase rather than working around it with multiple keys."
        ),
    },
    {
        "id": "kb-006",
        "title": "Setting up single sign-on (SSO)",
        "category": "identity",
        "content": (
            "Contoso Cloud supports SSO through any SAML 2.0 or OpenID Connect "
            "identity provider. An administrator configures it under Portal > "
            "Settings > Identity by supplying the provider metadata URL. Once "
            "SSO is enforced, local passwords are disabled and all sign-ins "
            "flow through your identity provider."
        ),
    },
    {
        "id": "kb-007",
        "title": "Data residency and regional storage",
        "category": "compliance",
        "content": (
            "You choose a data residency region when you create a workspace, "
            "and customer data stays in that region at rest. The region cannot "
            "be changed after creation; to move regions you export the "
            "workspace and import it into a new one. Metadata used for billing "
            "is stored separately and is not subject to the residency choice."
        ),
    },
    {
        "id": "kb-008",
        "title": "Exporting your data before you cancel",
        "category": "billing",
        "content": (
            "Before you cancel a subscription, export your data from Portal > "
            "Settings > Export, which produces a downloadable archive. After "
            "cancellation the workspace is retained in a read-only state for 30 "
            "days and then permanently deleted, so export first and confirm the "
            "archive opens before you let the retention window expire."
        ),
    },
]


def build_index(index_client: SearchIndexClient) -> None:
    """Create (or update) the vector index. Safe to run repeatedly."""
    fields = [
        # The key. Every document needs a unique, stable id.
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        # Human-readable fields. `searchable` puts them in the keyword index too,
        # which is what makes HYBRID search (keyword + vector) possible.
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        # `filterable` lets a query narrow by category (e.g. only "billing")
        # before ranking -- cheap, deterministic, and exam-relevant.
        SimpleField(name="category", type=SearchFieldDataType.String, filterable=True),
        # The vector field. Its dimensions MUST equal the embedding model's
        # output (3072 for text-embedding-3-large) and it points at a profile
        # that describes the nearest-neighbor algorithm.
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name="hnsw-cosine",
        ),
    ]

    # HNSW (Hierarchical Navigable Small World) is the standard approximate
    # nearest-neighbor graph. Cosine distance is the right metric for OpenAI
    # embeddings, which are normalized to compare well under cosine similarity.
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
        profiles=[
            VectorSearchProfile(
                name="hnsw-cosine",
                algorithm_configuration_name="hnsw-config",
            )
        ],
    )

    index = SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search)
    index_client.create_or_update_index(index)
    print(f"[index] '{INDEX_NAME}' created or updated ({len(fields)} fields, "
          f"{EMBEDDING_DIMENSIONS}-dim vectors).")


def embed(client: AzureOpenAI, texts: list[str]) -> list[list[float]]:
    """Turn text into vectors using the account's embedding deployment.

    We pass the DEPLOYMENT name as `model` -- on Azure OpenAI you address a
    model by the name you gave its deployment, not the base model id.
    """
    response = client.embeddings.create(model=EMBEDDING_DEPLOYMENT, input=texts)
    # The API preserves input order, so response.data[i] matches texts[i].
    return [item.embedding for item in response.data]


def seed(client: AzureOpenAI, search_client: SearchClient) -> None:
    """Embed every KB article and upload it to the index."""
    contents = [doc["content"] for doc in KB_DOCS]
    print(f"[embed] requesting {len(contents)} embeddings from "
          f"'{EMBEDDING_DEPLOYMENT}'...")
    vectors = embed(client, contents)

    # Attach each vector to its document. merge_or_upload means: insert if new,
    # update in place if the id already exists -- that is what makes re-running
    # this script idempotent instead of piling up duplicates.
    payload = []
    for doc, vector in zip(KB_DOCS, vectors):
        payload.append({**doc, "contentVector": vector})

    result = search_client.merge_or_upload_documents(documents=payload)
    succeeded = sum(1 for r in result if r.succeeded)
    print(f"[upload] {succeeded}/{len(payload)} documents indexed.")
    if succeeded != len(payload):
        # Surface partial failures loudly -- a half-seeded index makes a RAG
        # demo look broken in ways that are maddening to diagnose live.
        for r in result:
            if not r.succeeded:
                print(f"  FAILED {r.key}: {r.error_message}", file=sys.stderr)
        sys.exit(1)


def smoke_test(client: AzureOpenAI, search_client: SearchClient, question: str) -> None:
    """Prove retrieval works: embed a question, run a hybrid search, show hits."""
    from azure.search.documents.models import VectorizedQuery

    print(f"\n[query] {question!r}")
    query_vector = embed(client, [question])[0]

    # HYBRID search: the keyword side (search_text) and the vector side
    # (VectorizedQuery) run together and Azure AI Search fuses them with
    # Reciprocal Rank Fusion. On the FREE tier there is no semantic reranker,
    # but hybrid alone already beats either signal on its own.
    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=3,
        fields="contentVector",
    )
    results = search_client.search(
        search_text=question,
        vector_queries=[vector_query],
        select=["title", "category", "content"],
        top=3,
    )

    for i, hit in enumerate(results, 1):
        score = hit.get("@search.score", 0.0)
        print(f"  {i}. [{hit['category']}] {hit['title']}  (score {score:.4f})")
    print("[query] hybrid retrieval returned the passages above.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed and test the L8 RAG index.")
    parser.add_argument(
        "--query",
        help="Skip seeding and just run a retrieval smoke-test with this question.",
    )
    parser.add_argument(
        "--reseed",
        action="store_true",
        help="Force a rebuild + reload even when --query is supplied.",
    )
    args = parser.parse_args()

    client = openai_client()
    index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=CREDENTIAL)
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=CREDENTIAL
    )

    # Default path: build the index and load it. With --query only, we assume the
    # index is already warm and jump straight to proving retrieval.
    if not args.query or args.reseed:
        build_index(index_client)
        seed(client, search_client)

    if args.query:
        smoke_test(client, search_client, args.query)


if __name__ == "__main__":
    main()
