#!/usr/bin/env python
"""
M03 demo -- one Foundry project, the three Lesson 3 LOs read live as ops signals.

Monitoring is read-only by nature: you observe, you don't mutate. So this demo makes ZERO
changes to your resources -- it's safe to run and safe to record. Auth is keyless throughout
(AzureCliCredential = your `az login` identity), matching the m02 convention.

  LO1  MANAGE quota + cost ......... the two guardrails clip 04 promises. First, quota headroom:
                                     TPM current vs limit per model in a region, so you see when to
                                     scale (raise TPM, add PTUs, spread regions) or file a Request
                                     Quota (azure-mgmt-cognitiveservices). Then cost: month-to-date
                                     spend by resource group, the live "cost per workload"
                                     attribution you'd wire to a budget alert
                                     (azure-mgmt-costmanagement).
  LO2  MONITOR performance/safety .. confirm the Foundry Observability wiring by fetching the
                                     project's Application Insights connection string -- the pipe
                                     that carries latency, safety, and groundedness signals plus
                                     continuous-evaluation scores. Data plane: azure-ai-projects.
  LO3  MONITOR index/relevance ..... read Azure AI Search index health (document count, storage),
                                     the indexer's last run, then score top-k precision over a
                                     labeled query set as a live relevance signal.

Every signal is wrapped so a missing piece of config just SKIPS with a friendly note -- you can
run the parts you have configured and record them one at a time.

Setup: uv sync ; az login ; copy .env.example to .env
Run:   uv run python m03_ops_demo.py            # read every signal
       uv run python m03_ops_demo.py --dry-run  # list what it WOULD read; call nothing
       uv run python m03_ops_demo.py --only cost  # one signal: quota | cost | monitor | search

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
# ---- LO1: MANAGE -- read cost guardrails (month-to-date spend by workload) ------------
def signal_cost(dry: bool) -> None:
    banner("LO1  Manage  |  cost guardrails (month-to-date spend by workload)")
    sub = required("AZURE_SUBSCRIPTION_ID", "your Azure subscription GUID")
    if dry:
        print("  DRY: would query month-to-date actual cost grouped by resource group.")
        return
    from azure.mgmt.costmanagement import CostManagementClient
    from azure.mgmt.costmanagement.models import (
        QueryDefinition, QueryDataset, QueryAggregation, QueryGrouping,
        TimeframeType, ExportType,
    )
    # ACTUAL_COST, month-to-date, summed and grouped by resource group = "cost per workload".
    # Grouping by ResourceGroup (not ResourceId) keeps the on-camera list short and legible;
    # the same query with name="ResourceId" is how you'd attribute cost per deployment.
    query = QueryDefinition(
        type=ExportType.ACTUAL_COST,
        timeframe=TimeframeType.MONTH_TO_DATE,
        dataset=QueryDataset(
            aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
            grouping=[QueryGrouping(type="Dimension", name="ResourceGroup")],
        ),
    )
    try:
        result = CostManagementClient(CRED).query.usage(
            scope=f"/subscriptions/{sub}", parameters=query)
    except HttpResponseError as exc:
        first = exc.message.splitlines()[0]
        print(f"  cost query unavailable: {first}")
        if getattr(exc, "status_code", None) == 429:
            print("  (Cost Management throttles queries hard; wait ~60s and re-run this signal.)")
        else:
            print("  (need Cost Management Reader on the subscription; new subs can lag a day.)")
        return

    cols = [c.name for c in result.columns]
    i_cost, i_rg, i_cur = cols.index("Cost"), cols.index("ResourceGroup"), cols.index("Currency")
    rows = sorted(result.rows or [], key=lambda r: r[i_cost], reverse=True)
    if not rows:
        print("  No cost rows yet this month (fresh subscription or no spend).")
        return
    currency = rows[0][i_cur]
    print(f"  month-to-date, by resource group ({currency}):")
    for r in rows[:8]:                            # keep the on-camera list short
        print(f"    {r[i_rg]:<44} {r[i_cost]:>10.4f}")
    print(f"    {'TOTAL (all groups)':<44} {sum(r[i_cost] for r in rows):>10.4f}")
    print("  EXAM TELL: to get alerted BEFORE the bill lands, put an Azure BUDGET with")
    print("  action-group alerts on this scope; cap runaway prompts with max_tokens.")


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

    # 3a) index health -- documents and storage. Newer API versions return camelCase keys
    # (documentCount/storageSize); older ones snake_case. Read whichever is present.
    try:
        stats = SearchIndexClient(endpoint, CRED).get_index_statistics(index)
        docs = stats.get("documentCount", stats.get("document_count", 0))
        size = stats.get("storageSize", stats.get("storage_size", 0))
        print(f"  documents: {docs:,}   storage: {size:,} bytes")
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

    # 3c) relevance signal -- top-k precision over a LABELED query set (the deck's yardstick).
    # A labeled set is a handful of {query, expected key values} pairs whose right answers you
    # know in advance -- a "gold set". Precision@k = of the top k results, how many were expected.
    # That's the number you diff when a ranking change ships, instead of trusting a hunch.
    client = SearchClient(endpoint, index, CRED)
    key_field = os.environ.get("SEARCH_KEY_FIELD", "id")
    labeled_raw = os.environ.get("SEARCH_LABELED_QUERIES")
    if labeled_raw:
        import json
        try:
            labeled = json.loads(labeled_raw)   # [{"query": "...", "expected": ["id1", "id2"]}, ...]
        except json.JSONDecodeError:
            print("  SEARCH_LABELED_QUERIES is not valid JSON; skipping precision.")
            labeled = []
        k = int(os.environ.get("SEARCH_TOP_K", "3"))
        # Score each labeled query by how many of ITS expected docs landed in the top k
        # (hit rate / recall@k). With one expected doc per query, 1.0 means "found it in the
        # top k". Averaging across the gold set gives one relevance number you can trend.
        scores = []
        for case in labeled:
            expected = set(case.get("expected", []))
            if not expected:
                continue
            try:
                hits = client.search(search_text=case["query"], top=k, select=[key_field])
                returned = [h[key_field] for h in hits]
            except HttpResponseError as exc:
                print(f"  query {case['query']!r} failed: {exc.message.splitlines()[0]}")
                continue
            got = sum(1 for r in returned if r in expected)
            score = got / len(expected)          # recall@k against this query's gold answers
            scores.append(score)
            print(f"    recall@{k}={score:.2f}  query={case['query']!r}  found {got}/{len(expected)} expected")
        if scores:
            mean = sum(scores) / len(scores)
            print(f"  MEAN recall@{k} over {len(scores)} labeled queries: {mean:.2f}  (1.00 = every gold answer surfaced)")
    else:
        # Fallback with no gold set: one query, show the top @search.score as a raw relevance signal.
        query = os.environ.get("SEARCH_SAMPLE_QUERY", "*")
        try:
            results = client.search(search_text=query, top=3, include_total_count=True)
            print(f"  query {query!r}: {results.get_count()} hits; top relevance scores:")
            for r in results:
                print(f"    @search.score = {r['@search.score']:.4f}")
            print("  (set SEARCH_LABELED_QUERIES to a gold set for top-k precision instead.)")
        except HttpResponseError as exc:
            print(f"  query unavailable: {exc.message.splitlines()[0]}")
    print("  EXAM TELL: to prove a ranking change actually helped, A/B test against a gold")
    print("  query set -- precision on hard numbers, not a gut call.")


# %%
def main() -> None:
    ap = argparse.ArgumentParser(description="AI-103 L3: one project, read-only ops signals.")
    ap.add_argument("--dry-run", action="store_true", help="List what it would read; make no Azure calls.")
    ap.add_argument("--only", choices=["quota", "cost", "monitor", "search"], help="Run a single signal.")
    args = ap.parse_args()

    # Order follows the deck's clips: quota + cost (LO1/clip 04), Observability (LO2/clip 05),
    # index + relevance (LO3/clip 06).
    steps = {
        "quota": signal_quota,
        "cost": signal_cost,
        "monitor": signal_observability,
        "search": signal_search,
    }
    for key, fn in steps.items():
        if args.only and args.only != key:
            continue
        try:
            fn(args.dry_run)
        except Exception as exc:  # one signal failing never sinks the others (great for recording)
            print(f"  ({key} skipped: {type(exc).__name__}: {exc})")

    banner("LO1 quota + cost, LO2 Observability, LO3 index + relevance -- the three L3 questions.")


# %%
if __name__ == "__main__":
    main()
