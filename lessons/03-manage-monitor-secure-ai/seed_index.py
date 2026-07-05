#!/usr/bin/env python
"""One-time SETUP (not the demo): create the small persistent index the L3 demo reads.

The read-only demo (`m03_ops_demo.py`) reads an Azure AI Search index but never creates one, so it
stays a pure observer -- safe to record. This script stands that index up once: six realistic
ops-knowledge documents with STABLE ids, so the demo's labeled query set (recall@k) has known-right
answers to score against. Idempotent: create-or-update the index, merge-or-upload the docs, so
re-running just converges. Keyless (`az login`).

Run once from this folder:
    uv run python seed_index.py
Then confirm .env has:  SEARCH_INDEX_NAME=ai103-l03-demo

Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
"""
import os

from azure.identity import AzureCliCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField, SearchFieldDataType,
)
from azure.search.documents import SearchClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

INDEX = os.environ.get("SEARCH_INDEX_NAME", "ai103-l03-demo")
endpoint = os.environ["SEARCH_ENDPOINT"]
cred = AzureCliCredential()

fields = [
    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
    SearchableField(name="title", type=SearchFieldDataType.String),
    SearchableField(name="content", type=SearchFieldDataType.String),
    SimpleField(name="topic", type=SearchFieldDataType.String, filterable=True, facetable=True),
]
SearchIndexClient(endpoint, cred).create_or_update_index(SearchIndex(name=INDEX, fields=fields))

# Stable ids double as the gold answers for the demo's labeled query set. Content mirrors the deck.
docs = [
    {"id": "quota-01", "topic": "quota", "title": "Model quota is per-region, per-model TPM",
     "content": "Foundry grants model quota in tokens per minute per subscription, region, and model. "
                "Raise TPM, add PTUs, or spread regions to scale. The Request Quota form takes days."},
    {"id": "cost-01", "topic": "cost", "title": "Cost governance with budgets and tags",
     "content": "Tag resources for attribution, set Azure budgets with action-group alerts at thresholds, "
                "track cost per deployment, and cap output length with max_tokens to stop runaway prompts."},
    {"id": "latency-01", "topic": "monitoring", "title": "Latency percentiles and throttle rate",
     "content": "Track P50, P95, and P99 latency per deployment and watch the 429 throttle rate. "
                "The slow tail at P95 and P99 is what shapes how fast the application feels to users."},
    {"id": "ground-01", "topic": "monitoring", "title": "Groundedness scoring on RAG answers",
     "content": "Groundedness measures how well a retrieval-augmented answer sticks to its source documents. "
                "Foundry ships it as a built-in evaluator; a low score signals hallucination drift."},
    {"id": "index-01", "topic": "index", "title": "Index health signals for search",
     "content": "Watch document-count trends, ingestion latency per source, indexer error rates, "
                "field population coverage, and storage and query-throughput usage in search units."},
    {"id": "relevance-01", "topic": "index", "title": "Relevance with top-k precision and A/B tests",
     "content": "Measure top-k precision against a labeled gold query set, track click-through rate, "
                "monitor freshness, dedup stale content, and A/B test ranking changes before rollout."},
]
SearchClient(endpoint, INDEX, cred).merge_or_upload_documents(docs)
print(f"Seeded index '{INDEX}' with {len(docs)} documents (idempotent).")
print("Index stats (document count) refresh on a delay -- give it a minute before recording.")
