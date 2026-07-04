#!/usr/bin/env python
"""
M03 demo -- one Foundry project, THREE ops signals across all three Lesson 3 LOs.

Monitoring is read-only by nature: you observe, you don't mutate. So this demo makes ZERO
changes to your resources -- it's safe to run and safe to record. Auth is keyless throughout
(AzureCliCredential = your `az login` identity), matching the m02 convention.

  LO1  MANAGE quotas/scaling/cost .. read quota usage (TPM current vs limit) per model in a
                                     region, so you can see headroom and know when to scale
                                     (raise TPM, add PTUs, or spread regions) or file a
                                     Request Quota. Control plane: azure-mgmt-cognitiveservices.
  LO2  MONITOR performance/safety .. confirm the Foundry Observability wiring by fetching the
                                     project's Application Insights connection string -- the pipe
                                     that carries latency, safety, and groundedness signals plus
                                     continuous-evaluation scores. Data plane: azure-ai-projects.
  LO3  MONITOR index/relevance ..... read Azure AI Search index health (document count, storage),
                                     the indexer's last run, then run one query and show
                                     @search.score as a live relevance signal.

Every signal is wrapped so a missing piece of config just SKIPS with a friendly note -- you can
run the parts you have configured and record them one at a time.

Setup: uv sync ; az login ; copy .env.example to .env
Run:   uv run python m03_ops_demo.py            # read all three signals
       uv run python m03_ops_demo.py --dry-run  # list what it WOULD read; call nothing

This file uses `# %%` cell markers so you can run one signal at a time in the VS Code
Interactive Window while you narrate -- no separate notebook to keep in sync.

Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
"""

# %%
# ---- imports -------------------------------------------------------------------------
import argparse
import os
import sys

from azure.identity import AzureCliCredential
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# %%
# ---- helpers -------------------------------------------------------------------------
def required(name: str, hint: str) -> str:
    """Return env var ``name`` or exit with a friendly hint. See .env.example."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: {name} is not set.\n  -> {hint}\n  See .env.example.")
    return value


def banner(text: str) -> None:
    """Labeled section header so each LO is obvious on screen while recording."""
    print("\n" + "=" * 78 + f"\n{text}\n" + "=" * 78)


# One credential for every plane -- your az login identity. In CI/CD you swap this one line
# for DefaultAzureCredential and let the pipeline's federated (OIDC) identity resolve.
CRED = AzureCliCredential()


# %%
# ---- LO1: MANAGE -- read quota headroom (TPM current vs limit) -----------------------
def signal_quota(dry: bool) -> None:
    banner("LO1  Manage  |  quota headroom (TPM used vs limit)")
    sub = required("AZURE_SUBSCRIPTION_ID", "your Azure subscription GUID")
    location = os.environ.get("QUOTA_LOCATION", "eastus2")
    print(f"  region: {location}  (set QUOTA_LOCATION to change)")
    if dry:
        print("  DRY: would list Microsoft.CognitiveServices usages in this region.")
        return
    from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
    arm = CognitiveServicesManagementClient(CRED, sub)
    shown = 0
    for u in arm.usages.list(location):          # each usage line = a per-model TPM quota
        limit = u.limit or 0
        if limit <= 0:
            continue
        name = u.name.localized_value or u.name.value
        used = u.current_value or 0
        pct = (used / limit) * 100 if limit else 0
        print(f"  {name:<48} {used:>10.0f}/{limit:<10.0f} ({pct:4.0f}% used)")
        shown += 1
        if shown >= 12:                          # keep the on-camera list short
            print("  ... (truncated; full list in Foundry > Operate > Quota)")
            break
    if not shown:
        print("  No non-zero quota lines here. Try the region that holds your deployments.")
    print("  EXAM TELL: near 100% means SCALE (raise TPM, add PTUs, spread regions) or Request Quota.")


# %%
# ---- LO2: MONITOR -- confirm the Observability pipe (App Insights) --------------------
def signal_observability(dry: bool) -> None:
    banner("LO2  Monitor  |  Foundry Observability wiring (Application Insights)")
    endpoint = required("FOUNDRY_PROJECT_ENDPOINT",
                        "https://<resource>.services.ai.azure.com/api/projects/<project>")
    if dry:
        print("  DRY: would fetch this project's Application Insights connection string.")
        return
    from azure.ai.projects import AIProjectClient
    project = AIProjectClient(endpoint=endpoint, credential=CRED)
    try:
        conn = project.telemetry.get_application_insights_connection_string()
        head = conn.split(";")[0]                 # show only InstrumentationKey=..., never the whole string
        print(f"  Application Insights: CONNECTED ({head})")
        print("  This pipe carries latency, token, content-filter, and groundedness signals,")
        print("  plus continuous-evaluation scores, into the Foundry monitoring dashboard.")
    except ResourceNotFoundError:
        print("  Application Insights: NOT connected.")
        print("  Connect one in Foundry > Monitoring to turn on production monitoring + continuous eval.")


# %%
# ---- LO3: MONITOR -- index health + a live relevance score ---------------------------
def signal_search(dry: bool) -> None:
    banner("LO3  Monitor  |  Azure AI Search index health + relevance")
    endpoint = os.environ.get("SEARCH_ENDPOINT")
    index = os.environ.get("SEARCH_INDEX_NAME")
    if not endpoint or not index:
        print("  SKIP: set SEARCH_ENDPOINT and SEARCH_INDEX_NAME to read index health.")
        return
    print(f"  service: {endpoint}  index: {index}")
    if dry:
        print("  DRY: would read index statistics, indexer status, and run one sample query.")
        return
    from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
    from azure.search.documents import SearchClient

    # 3a) index health -- documents and storage
    try:
        stats = SearchIndexClient(endpoint, CRED).get_index_statistics(index)
        print(f"  documents: {stats['document_count']:,}   storage: {stats['storage_size']:,} bytes")
    except HttpResponseError as exc:
        print(f"  index stats unavailable: {exc.message.splitlines()[0]}")

    # 3b) indexer status -- ingestion health (optional; only if you use an indexer)
    indexer = os.environ.get("SEARCH_INDEXER_NAME")
    if indexer:
        try:
            st = SearchIndexerClient(endpoint, CRED).get_indexer_status(indexer)
            last = st.last_result
            print(f"  indexer '{indexer}': status={st.status}  last={getattr(last,'status',None)}"
                  f"  items={getattr(last,'item_count',None)}  failed={getattr(last,'failed_item_count',None)}")
        except HttpResponseError as exc:
            print(f"  indexer status unavailable: {exc.message.splitlines()[0]}")

    # 3c) relevance signal -- run one query, show the top @search.score
    query = os.environ.get("SEARCH_SAMPLE_QUERY", "*")
    try:
        results = SearchClient(endpoint, index, CRED).search(search_text=query, top=3,
                                                             include_total_count=True)
        print(f"  query {query!r}: {results.get_count()} hits; top relevance scores:")
        for r in results:
            print(f"    @search.score = {r['@search.score']:.4f}")
    except HttpResponseError as exc:
        print(f"  query unavailable: {exc.message.splitlines()[0]}")
    print("  EXAM TELL: quiet quality drop with no error => check the INDEX first (health + relevance).")


# %%
def main() -> None:
    ap = argparse.ArgumentParser(description="AI-103 L3: one project, three read-only ops signals.")
    ap.add_argument("--dry-run", action="store_true", help="List what it would read; make no Azure calls.")
    ap.add_argument("--only", choices=["quota", "monitor", "search"], help="Run a single signal.")
    args = ap.parse_args()

    steps = {"quota": signal_quota, "monitor": signal_observability, "search": signal_search}
    for key, fn in steps.items():
        if args.only and args.only != key:
            continue
        try:
            fn(args.dry_run)
        except Exception as exc:  # one signal failing never sinks the others (great for recording)
            print(f"  ({key} skipped: {type(exc).__name__}: {exc})")

    banner("Three signals, three LOs: quota headroom (LO1), Observability (LO2), index health (LO3).")


# %%
if __name__ == "__main__":
    main()
