#!/usr/bin/env python
"""
AI-103 Lesson 17, Beat 2 - the whole ingestion and enrichment pipeline.

    uv run python m17_ingest.py

WHAT THIS BUILDS, AND WHY IT IS FOUR OBJECTS AND NOT ONE
--------------------------------------------------------
Azure AI Search has two ways to get content in. The PUSH model calls the Index
Documents API from your code: any source you like, but you own the ingestion,
the scheduling, and the change tracking. The PULL model is an indexer -- a
crawler that binds one data source to one index and serializes source records
into search documents with no ingestion code from you.

The fork matters because of one rule: A SKILLSET ATTACHES TO AN INDEXER AND
NEVER RUNS ON ITS OWN. If a solution needs AI enrichment, OCR, or integrated
vectorization, the pull model is mandatory. The push model cannot enrich. That
single sentence disqualifies "just push the documents" on a whole class of exam
questions, and it is why this script creates four objects:

    DATA SOURCE   where the content lives, and how change is detected
    INDEX         the shape the answers come out in
    SKILLSET      what happens to the content on the way through
    INDEXER       the thing that actually runs, binding the other three

THE FOUR STAGES AN INDEXER RUNS, IN FIXED ORDER
-----------------------------------------------
    1. document cracking      open the blob, split text from images
    2. field mappings         source field  -> index field
    3. skillset execution     build the enrichment tree under /document
    4. output field mappings  enrichment node -> index field

Stage order explains two things that confuse everyone. First, a field mapping
can never reference a skill output, because mappings run before the skills do.
Second -- and this is the one that eats an afternoon -- OCR output does not
land in the index by itself. The enrichment tree is in memory and temporary.
Nothing survives unless you route it somewhere, and here that route is an index
projection.

THE CROSS-REGION PROBLEM THIS SCRIPT SOLVES ON PURPOSE
------------------------------------------------------
Attaching a Foundry resource to a skillset is a BILLING METER, not a processing
endpoint -- the search service runs built-in skills on its own internally
managed resources and only uses your resource to charge you. There are two ways
to attach it:

    CognitiveServicesByKey   pins both services to the SAME physical region
    AIServicesByIdentity     no region requirement at all

The key form calls a regional endpoint, so a search service in one region and a
Foundry resource in another returns "Provided key isn't a valid CognitiveServices
type key for the region of your search service." The portal's Import data wizard
attaches the key form automatically. This skillset uses the identity form, which
is the documented escape hatch and the only thing that makes a cross-region
layout work.

FLAGS
-----
    --dry-run         print every JSON body, call nothing
    --reset           clear the indexer's high-water mark, reprocess everything
    --exclude-media   filter the .wav out by extension instead of letting it warn
    --skip-run        create the objects but do not run the indexer
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import m17_common as C
from m17_common import Fail, HttpError, Search, bad, banner, head, kv, ok, step, warn

sys.path.insert(0, str(pathlib.Path(__file__).parent / "assets"))
import make_assets  # noqa: E402  -- the corpus and its ground truth

CORPUS = pathlib.Path(__file__).parent / "assets" / "corpus"

# Chunking in CHARACTERS, not tokens. The `unit` property that switches a split
# skill to token counting is preview-gated and returns HTTP 400 on the stable
# API -- "The property unit does not exist on type
# Microsoft.Skills.Text.SplitSkill or is not present in the API version."
# Worth knowing precisely because the default unit is characters: set
# maximumPageLength to your model's TOKEN limit and leave the unit alone, and
# you have silently configured chunks about four times smaller than you meant.
MAX_PAGE_LENGTH = 1200
PAGE_OVERLAP = 200


# ---------------------------------------------------------------------------
# The four object definitions. Read these; they are the lesson.
# ---------------------------------------------------------------------------

def index_definition(s: C.Settings) -> dict:
    """
    An index shaped for CHUNKS, which needs two identifiers and not one.

    `chunk_id` is the document key. It must be Edm.String and it must use the
    keyword analyzer, so the whole key is one token and nothing tokenizes a
    generated identifier into fragments.

    `parent_id` points back at the source document. It must be filterable, and
    it must NOT be the key. Without it you retrieve a fragment you cannot
    attribute, which is the difference between a citation and a guess.

    Note what a vector field cannot do: it is neither filterable nor facetable.
    Every filter, facet, and security-trimming predicate has to run against a
    companion nonvector field, so the schema has to plan for that up front.
    That is why `source_kind` exists as its own filterable field.
    """
    return {
        "name": C.INDEX,
        "fields": [
            {"name": "chunk_id", "type": "Edm.String", "key": True,
             "searchable": True, "filterable": True, "sortable": True,
             "facetable": False, "analyzer": "keyword"},
            {"name": "parent_id", "type": "Edm.String",
             "searchable": False, "filterable": True, "sortable": False,
             "facetable": False},
            {"name": "title", "type": "Edm.String",
             "searchable": True, "filterable": True, "sortable": False,
             "facetable": False},
            {"name": "chunk", "type": "Edm.String",
             "searchable": True, "filterable": False, "sortable": False,
             "facetable": False},
            {"name": "source_kind", "type": "Edm.String",
             "searchable": False, "filterable": True, "sortable": False,
             "facetable": True},
            {"name": "text_vector", "type": "Collection(Edm.Single)",
             "searchable": True, "filterable": False, "sortable": False,
             "facetable": False, "retrievable": False,
             "dimensions": C.EMBEDDING_DIMENSIONS,
             "vectorSearchProfile": C.VECTOR_PROFILE},
        ],
        # A vector field never names an algorithm. It names a PROFILE, and the
        # profile binds the algorithm, the optional compression, and the
        # optional vectorizer together. That indirection is what lets you A/B
        # two algorithms over the same content inside one index: add a profile,
        # do not edit a field.
        "vectorSearch": {
            "algorithms": [{
                "name": C.VECTOR_ALGORITHM,
                "kind": "hnsw",
                # HNSW builds a navigable graph that stays resident in memory
                # and therefore consumes vector index quota. Exhaustive KNN
                # scans everything and consumes none. Index for HNSW when you
                # want both options: a field indexed for HNSW can be queried
                # exhaustively on demand, but a field indexed for exhaustive
                # KNN can never be served by HNSW -- the graph was never built,
                # and there is no query-time flag that conjures it. That one is
                # a full reindex to undo.
                "hnswParameters": {"m": 4, "efConstruction": 400,
                                   "efSearch": 500, "metric": "cosine"},
            }],
            "profiles": [{
                "name": C.VECTOR_PROFILE,
                "algorithm": C.VECTOR_ALGORITHM,
                "vectorizer": C.VECTORIZER,
            }],
            # The QUERY half of integrated vectorization. The skillset declares
            # the same model as an embedding skill for the INDEXING half. If
            # these two ever drift apart, queries land in a different embedding
            # space and relevance quietly collapses with no error at all.
            "vectorizers": [{
                "name": C.VECTORIZER,
                "kind": "azureOpenAI",
                "azureOpenAIParameters": {
                    "resourceUri": s.foundry_resource_uri,
                    "deploymentId": s.embedding_deployment,
                    "modelName": s.embedding_deployment,
                    # null = the search service's system-assigned identity.
                    "authIdentity": None,
                },
            }],
        },
        # The semantic ranker never reads a whole document. It reads a summary
        # assembled from the fields named here, in the order they are listed.
        # Priority order is truncation order: put a boilerplate field first and
        # you starve the ranker of the text that answers the question.
        "semantic": {
            "defaultConfiguration": C.SEMANTIC_CONFIG,
            "configurations": [{
                "name": C.SEMANTIC_CONFIG,
                "prioritizedFields": {
                    "titleField": {"fieldName": "title"},
                    "prioritizedContentFields": [{"fieldName": "chunk"}],
                    "prioritizedKeywordsFields": [],
                },
            }],
        },
    }


def datasource_definition(s: C.Settings) -> dict:
    """
    A blob data source that connects with an identity and knows about deletes.

    The connection string carries a RESOURCE ID and no secret. That form tells
    the service to authenticate with its own managed identity. An indexer has
    no identity of its own, so the role assignment lives on the SERVICE -- which
    is why standing up a second indexer never fixes an access problem.

    Change detection is free here: every blob carries a LastModified timestamp,
    so incremental indexing works with no policy at all. Database sources have
    no such guarantee and must declare a data change detection policy first.

    DELETION detection is never free. An indexer sees what exists, not what
    vanished, so a deleted blob leaves an orphaned search document behind --
    and an orphan poisons grounding by feeding a model content the business
    already retired. The policy below reads blob metadata: set IsDeleted=true
    on the blob, let the indexer remove the search document, then delete the
    blob for real.

    The sharp edge: a deletion detection policy only governs runs that happen
    AFTER it exists. Documents deleted before the policy was attached stay in
    the index permanently, and resetting the indexer does not evict them. Reset
    is a reprocess instruction, not a cleanup. Getting this wrong is an
    architecture decision disguised as a checkbox.
    """
    return {
        "name": C.DATASOURCE,
        "type": "azureblob",
        "credentials": {"connectionString": f"ResourceId={s.storage_resource_id};"},
        "container": {"name": C.CONTAINER},
        "dataDeletionDetectionPolicy": {
            "@odata.type": "#Microsoft.Azure.Search.SoftDeleteColumnDeletionDetectionPolicy",
            "softDeleteColumnName": "IsDeleted",
            "softDeleteMarkerValue": "true",
        },
    }


def skillset_definition(s: C.Settings) -> dict:
    """
    OCR -> Merge -> Split -> Embed, projected one chunk per search document.

    Every skill has a CONTEXT, and the context does two jobs at once: it sets
    how many times the skill runs, and it sets where the output hangs in the
    enrichment tree. Appending /* turns one invocation per document into one
    invocation per item in a collection. Watch it change between skills below --
    OCR runs once per image, Merge runs once per document, Embed runs once per
    chunk. Context is the single most common source of silent skillset bugs.
    """
    return {
        "name": C.SKILLSET,
        "description": "Woodgrove Bank grounding pipeline: OCR, merge, chunk, vectorize",
        "skills": [
            {
                # Reads NOTHING but normalized images. That node does not exist
                # until the INDEXER is told to produce it -- see the indexer's
                # imageAction below. The dependency runs indexer -> skill, and
                # getting it backwards is why an OCR field comes back empty
                # while the run reports success.
                "@odata.type": "#Microsoft.Skills.Vision.OcrSkill",
                "name": "ocr",
                "description": "characters printed on the page",
                "context": "/document/normalized_images/*",
                "defaultLanguageCode": "en",
                "detectOrientation": True,
                "inputs": [{"name": "image", "source": "/document/normalized_images/*"}],
                "outputs": [{"name": "text", "targetName": "ocr_text"}],
            },
            {
                # Document cracking split text from images before any skill ran,
                # and OCR output does not rejoin the body on its own. Merge is
                # what stitches recognized characters back into the content
                # stream at the right offset. Skip it and you have an OCR field
                # nobody downstream can see: the splitter, the embedder, and
                # every text skill are all reading /document/content.
                "@odata.type": "#Microsoft.Skills.Text.MergeSkill",
                "name": "merge",
                "description": "put the image text back into the document body",
                "context": "/document",
                "insertPreTag": " ",
                "insertPostTag": " ",
                "inputs": [
                    {"name": "text", "source": "/document/content"},
                    {"name": "itemsToInsert", "source": "/document/normalized_images/*/ocr_text"},
                    {"name": "offsets", "source": "/document/normalized_images/*/contentOffset"},
                ],
                "outputs": [{"name": "mergedText", "targetName": "merged_text"}],
            },
            {
                # Chunking exists for two independent reasons: to fit the
                # embedding model's input window, and to make retrieval precise.
                # One chunk becomes one vector and one citation, so a chunk
                # should carry roughly one idea. Overlap trades a little
                # duplicated storage for continuity -- it stops a sentence that
                # straddles a boundary from being invisible to both chunks.
                "@odata.type": "#Microsoft.Skills.Text.SplitSkill",
                "name": "split",
                "description": "one idea per chunk",
                "context": "/document",
                "textSplitMode": "pages",
                "maximumPageLength": MAX_PAGE_LENGTH,
                "pageOverlapLength": PAGE_OVERLAP,
                "inputs": [{"name": "text", "source": "/document/merged_text"}],
                "outputs": [{"name": "textItems", "targetName": "chunks"}],
            },
            {
                # The INDEXING half of integrated vectorization. This skill
                # calls a model YOU deployed, for processing as well as billing,
                # so the Foundry attach below does not cover it -- it needs
                # Cognitive Services OpenAI User on the identity in its own
                # right. Microsoft's guidance is to dedicate a deployment to
                # indexing, because a high-volume indexing run against the same
                # deployment your query path uses will saturate the token quota
                # and throttle both.
                "@odata.type": "#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill",
                "name": "embed",
                "description": "one vector per chunk",
                "context": "/document/chunks/*",
                "resourceUri": s.foundry_resource_uri,
                "deploymentId": s.embedding_deployment,
                "modelName": s.embedding_deployment,
                "dimensions": C.EMBEDDING_DIMENSIONS,
                "authIdentity": None,
                "inputs": [{"name": "text", "source": "/document/chunks/*"}],
                "outputs": [{"name": "embedding", "targetName": "text_vector"}],
            },
        ],
        # The billing attach. Identity form, not key form -- see the module
        # docstring. `identity: null` means the search service's own
        # system-assigned managed identity.
        "cognitiveServices": {
            "@odata.type": "#Microsoft.Azure.Search.AIServicesByIdentity",
            "description": "billing attach for built-in skills, cross-region safe",
            "subdomainUrl": s.foundry_resource_uri,
            "identity": None,
        },
        # Index projections are what turn ONE source document into MANY search
        # documents. A skillset that chunks text but has no projection still
        # writes exactly one search document per file -- the enrichment tree
        # fills with chunks and the index shows one row per PDF, which is the
        # single most confusing outcome in this whole objective.
        "indexProjections": {
            "selectors": [{
                "targetIndexName": C.INDEX,
                "parentKeyFieldName": "parent_id",
                "sourceContext": "/document/chunks/*",
                # EVERY child field must be mapped explicitly. Unlike ordinary
                # indexer field mappings, nothing is inferred by name. And do
                # NOT map the parent key field here -- that breaks change
                # tracking and synchronized refresh.
                "mappings": [
                    {"name": "chunk", "source": "/document/chunks/*"},
                    {"name": "text_vector", "source": "/document/chunks/*/text_vector"},
                    {"name": "title", "source": "/document/metadata_storage_name"},
                    {"name": "source_kind", "source": "/document/metadata_storage_content_type"},
                ],
            }],
            # Chunks ARE the search target here, so do not also write the
            # parent. Mixing whole documents and chunks in one index gives you
            # two populations of rows with different null patterns, and every
            # ranking, filter, and render has to branch on which kind came back.
            "parameters": {"projectionMode": "skipIndexingParentDocuments"},
        },
    }


def indexer_definition(exclude_media: bool = False) -> dict:
    """
    The thing that actually runs. Note where imageAction lives.

    OCR is an INDEXER configuration decision before it is a skill decision. The
    OCR skill can only read normalized images, and normalized images only exist
    when the indexer is told to produce them. imageAction has three hard
    prerequisites that are easy to forget and that fail QUIETLY rather than
    loudly: a skillset must be attached, dataToExtract must be
    contentAndMetadata, and parsingMode must be default. Miss one and you get
    an empty result, not an error.

    Two meters run on this pipeline, and people budget for one. Extracting TEXT
    from documents is free. Extracting IMAGES is billed by Azure AI Search
    itself, separately from whatever the OCR costs on the Foundry resource.
    That is why imageAction defaults to none, and why the run emits a warning
    the moment you turn it on.

    maxFailedItems is 0 deliberately. A run reports SUCCESS as long as failures
    stay under the threshold, so setting it to -1 for a demo means nothing can
    ever fail visibly. An honest pipeline shows you the real error.

    THE AUDIO FILE STAYS IN, AND THIS IS THE POINT
    ----------------------------------------------
    Learning objective one names audio and video, which invites the assumption
    that a blob indexer cracks them. It does not -- a blob indexer extracts
    text from text-bearing formats and has no codec for anything else.

    What is worth being precise about is HOW it declines, because the behavior
    observed live on this service is not the dramatic failure people expect:

        itemsProcessed 7, itemsFailed 0, status SUCCESS
        WARNING  DocumentExtraction.azureblob.wg-call-recording.wav
                 "Could not extract content or metadata from your document."
        WARNING  Enrichment.SplitSkill.split
                 "Could not execute skill because one or more skill input was
                  invalid."

    The audio file is counted as processed. The run is green. And it contributes
    exactly ZERO searchable content. That is worse than a crash, because a
    crash gets investigated. A pipeline can report perfect health while an
    entire content type silently never makes it into the index, and the only
    place it shows up is the warnings list nobody reads.

    Speech and video become searchable the same way they always have: a
    separate analyzer transcribes them, and the resulting TEXT gets indexed.

    Pass --exclude-media to filter the file out by extension instead, which is
    what you would actually do in production once you know the boundary.
    """
    configuration = {
        "dataToExtract": "contentAndMetadata",
        "parsingMode": "default",
        "imageAction": "generateNormalizedImages",
    }
    if exclude_media:
        configuration["excludedFileNameExtensions"] = ".wav,.mp3,.mp4,.m4a"
    return {
        "name": C.INDEXER,
        "dataSourceName": C.DATASOURCE,
        "targetIndexName": C.INDEX,
        "skillsetName": C.SKILLSET,
        "parameters": {
            "batchSize": 1,
            "maxFailedItems": 0,
            "maxFailedItemsPerBatch": 0,
            "configuration": configuration,
        },
        "fieldMappings": [],
        # Empty on purpose. With skipIndexingParentDocuments there IS no parent
        # document to map onto -- indexProjections.mappings does that job for
        # every chunk instead.
        "outputFieldMappings": [],
    }


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------

# Blob storage does not sniff content. Whatever MIME type you send at upload
# is exactly what `metadata_storage_content_type` reports forever after, and
# the indexer's document cracker reads that value to decide how to open the
# blob. Upload a PNG with no content type and the whole corpus arrives as
# application/octet-stream -- which still works here, but makes the index lie
# about what kind of thing each chunk came from. Set it at the source.
CONTENT_TYPES = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".png": "image/png",
    ".wav": "audio/wav",
}


def stage_corpus(s: C.Settings) -> tuple[int, int]:
    """Upload the fixture corpus. Idempotent: identical content is skipped."""
    from azure.identity import AzureCliCredential
    from azure.storage.blob import BlobServiceClient, ContentSettings

    import time

    service = BlobServiceClient(s.blob_endpoint, credential=AzureCliCredential())
    container = service.get_container_client(C.CONTAINER)

    # Azure Storage holds a deleted container name for a little while before
    # it can be reused, and returns ContainerBeingDeleted in the meantime. Run
    # teardown and then ingest back to back -- which is exactly what a retake
    # looks like -- and you hit it. Waiting it out is the documented answer.
    for attempt in range(12):
        try:
            container.create_container()
            step(f"created container {C.CONTAINER}")
            break
        except Exception as exc:
            message = str(exc)
            if "ContainerAlreadyExists" in message:
                break
            if "ContainerBeingDeleted" in message:
                if attempt == 0:
                    step("container name is still releasing from a delete, waiting")
                time.sleep(5)
                continue
            raise
    else:
        raise Fail(f"container {C.CONTAINER} never became available")

    existing = {b.name: b for b in container.list_blobs()}
    uploaded = skipped = 0
    for path in sorted(CORPUS.iterdir()):
        data = path.read_bytes()
        mime = CONTENT_TYPES.get(path.suffix, "application/octet-stream")
        current = existing.get(path.name)
        if (current is not None
                and current.size == len(data)
                and (current.content_settings or {}).get("content_type") == mime):
            skipped += 1
            continue
        container.upload_blob(name=path.name, data=data, overwrite=True,
                              content_settings=ContentSettings(content_type=mime))
        uploaded += 1
    if uploaded:
        step(f"uploaded {uploaded} blob(s) with explicit content types")
    return uploaded, skipped


# ---------------------------------------------------------------------------
# Run and report
# ---------------------------------------------------------------------------

TERMINAL = ("success", "transientFailure", "persistentFailure", "error")


def last_result(search: Search) -> dict:
    _, status = search.call("GET", f"indexers/{C.INDEXER}/status")
    return status.get("lastResult") or {}


def wait_until_idle(search: Search, timeout: int = 420) -> dict:
    """
    Block until no run is in flight.

    This exists because of a race that is easy to hit and very hard to read:
    CREATING an indexer starts it automatically. Issue a reset or a run in the
    next breath -- which is exactly what a rebuild does -- and the service
    answers HTTP 409, "Another indexer invocation is currently in progress;
    concurrent invocations are not allowed."

    That is not a bug, it is capacity. One partition and one replica is one
    search unit, and a search unit runs ONE indexer job at a time. The fix is
    to wait for the job that is already doing your work, not to retry harder.
    """
    deadline = time.time() + timeout
    announced = False
    while time.time() < deadline:
        last = last_result(search)
        if last.get("status") in TERMINAL or not last:
            return last
        if not announced:
            step("a run is already in flight (creating an indexer starts one) "
                 "-- waiting for it")
            announced = True
        time.sleep(5)
    raise Fail("an indexer run was still in flight after 7 minutes")


def run_indexer(search: Search, reset: bool = False) -> dict:
    # Never issue a command into a busy indexer. One search unit, one job.
    wait_until_idle(search)

    if reset:
        search.call("POST", f"indexers/{C.INDEXER}/reset")
        warn("reset: high-water mark cleared, everything reprocesses")
        warn("       reset does NOT evict orphans -- it is a reprocess "
             "instruction, not a cleanup")

    for attempt in range(6):
        try:
            search.call("POST", f"indexers/{C.INDEXER}/run")
            break
        except HttpError as exc:
            if exc.status != 409:
                raise
            step("run rejected with 409, a job is still finishing -- waiting")
            wait_until_idle(search)
    else:
        raise Fail("could not start the indexer; something else keeps running it")

    step("indexer running")
    deadline = time.time() + 420
    while time.time() < deadline:
        last = last_result(search)
        if last.get("status") in TERMINAL:
            return last
        time.sleep(5)
    raise Fail("indexer did not finish inside 7 minutes")


def report(search: Search, last: dict, exclude_media: bool = False) -> bool:
    """Prove what actually landed. Nothing here is asserted, all of it is read."""
    head("indexer execution")
    kv("status", last.get("status"))
    kv("items processed", last.get("itemsProcessed"))
    kv("items failed", last.get("itemsFailed"))
    # `key` is null on service-level warnings such as the image-extraction
    # billing notice, so it is coalesced rather than indexed directly. A crash
    # in the reporting code would be an embarrassing way to lose a take.
    for warning in (last.get("warnings") or [])[:5]:
        label = (warning.get("name") or warning.get("key") or "run")
        warn(f"{str(label)[:44]:<44} "
             f"{' '.join(str(warning.get('message', '')).split())[:90]}")
    for error in (last.get("errors") or [])[:5]:
        label = (error.get("name") or error.get("key") or "run")
        bad(f"{str(label)[:44]:<44} "
            f"{' '.join(str(error.get('errorMessage') or error.get('message') or '').split())[:120]}")

    head("the media boundary")
    media = [w for w in (last.get("warnings") or [])
             if "wg-call-recording" in str(w.get("name", ""))
             or "wg-call-recording" in str(w.get("key", ""))]
    if media:
        kv("audio blob", "counted as PROCESSED, contributed 0 chunks")
        kv("run status", f"{last.get('status')} -- a warning is not a failure")
        warn("a green run can hide a content type that never made it in")
    elif exclude_media:
        kv("audio blob", "excluded by extension before cracking")
    else:
        # An incremental run that processed nothing emits no per-document
        # warning, so the audio boundary cannot be shown from this run. Say
        # that plainly rather than claiming a filter that was never applied.
        kv("audio blob", "not re-examined -- nothing new to process")
        warn("the audio warning only appears on a run that actually cracks "
             "the blob. Re-run with --reset to show the media boundary.")

    head("what landed in the index")
    _, count = search.call("GET", f"indexes/{C.INDEX}/docs/$count")
    kv("search documents (chunks)", count)

    _, facets = search.call("POST", f"indexes/{C.INDEX}/docs/search", {
        "search": "*", "top": 0, "count": True,
        "facets": ["source_kind,count:10"]})
    for facet in facets.get("@search.facets", {}).get("source_kind", []):
        kv(f"  content type {facet['value']}", f"{facet['count']} chunks")

    # THE PROOF. This phrase exists nowhere in the text corpus. It exists only
    # as pixels inside a PNG. If it comes back, then image normalization ran,
    # OCR ran, Merge reinserted the characters, Split chunked the merged text,
    # Embed vectorized the chunk, and the index projection wrote it as its own
    # search document. One line, six stages.
    head("the OCR proof")
    _, hits = search.call("POST", f"indexes/{C.INDEX}/docs/search", {
        "search": f"\"{make_assets.OCR_ONLY_FACT}\"",
        "select": "title,source_kind,chunk", "top": 1, "count": True})
    found = hits.get("value") or []
    kv("query", f'"{make_assets.OCR_ONLY_FACT}" (appears only inside the PNG)')
    kv("matching chunks", hits.get("@odata.count", 0))
    if not found:
        bad("nothing came back. The OCR chain did not complete.")
        return False
    top = found[0]
    kv("came from", top.get("title"))
    kv("content type", top.get("source_kind"))
    snippet = " ".join(str(top.get("chunk", "")).split())
    print(f"\n  {snippet[:300]}\n")
    if make_assets.OCR_ONLY_PROOF not in snippet:
        warn(f"chunk returned, but the {make_assets.OCR_ONLY_PROOF} threshold "
             f"is not in this chunk -- check the split boundary")
    if not str(top.get("title", "")).endswith(".png"):
        bad("the match did not come from the scanned image")
        return False
    ok("text that only ever existed as pixels is now a citable search document")
    return True


# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="print every JSON body and call nothing")
    parser.add_argument("--reset", action="store_true",
                        help="clear the high-water mark and reprocess everything")
    parser.add_argument("--exclude-media", action="store_true",
                        help="filter the .wav out by extension instead of letting it warn")
    parser.add_argument("--skip-run", action="store_true",
                        help="create the objects but do not run the indexer")
    args = parser.parse_args()

    settings = load = C.load_settings()
    search = Search(settings)

    banner("AI-103 L17 Beat 2 -- ingest, enrich, and project",
           f"{settings.search_endpoint}  api-version {settings.api_version}")

    objects = [
        ("index", f"indexes/{C.INDEX}", index_definition(load)),
        ("data source", f"datasources/{C.DATASOURCE}", datasource_definition(load)),
        ("skillset", f"skillsets/{C.SKILLSET}", skillset_definition(load)),
        ("indexer", f"indexers/{C.INDEXER}",
         indexer_definition(exclude_media=args.exclude_media)),
    ]

    if args.dry_run:
        for label, path, body in objects:
            head(f"{label}  ->  PUT /{path}")
            print(json.dumps(body, indent=2))
        return 0

    head("fixtures")
    for name, size, digest in make_assets.build():
        kv(name, f"{size:>8,} bytes  sha256:{digest}", width=28)

    head("staging to blob storage")
    uploaded, skipped = stage_corpus(load)
    kv("uploaded", uploaded)
    kv("already current", skipped)

    # ORDER MATTERS. The target index must exist BEFORE the skillset that
    # projects into it, and before the indexer that drives it. Creating them
    # out of order fails.
    head("creating the pipeline objects")
    for label, path, body in objects:
        try:
            status, _ = search.call("PUT", path, body)
        except HttpError as exc:
            bad(f"{label}: {exc.short()}")
            if "region of your search service" in exc.body:
                bad("that is the cross-region KEY attach error. This skillset "
                    "uses the identity attach; check the managed identity.")
            if "managed identity" in exc.body.lower():
                bad("enable a system-assigned identity on the search service:")
                bad("  az search service update -n <svc> -g <rg> "
                    "--identity-type SystemAssigned")
            return 1
        ok(f"{label:<12} {C.INDEX if label == 'index' else path.split('/')[-1]}"
           f"  (HTTP {status})")

    if args.skip_run:
        warn("--skip-run: objects created, indexer not started")
        return 0

    head("running the indexer")
    if args.exclude_media:
        warn("--exclude-media: the .wav is filtered out by extension. The "
             "media-boundary warning will not appear.")
    last = run_indexer(search, reset=args.reset)

    healthy = report(search, last, exclude_media=args.exclude_media)

    head("summary")
    kv("index", C.INDEX)
    kv("chunks", search.call("GET", f"indexes/{C.INDEX}/docs/$count")[1])
    if last.get("status") != "success":
        bad(f"indexer status: {last.get('status')}")
        return 1
    return 0 if healthy else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Fail as exc:
        print(f"\n  [FAIL] {exc}")
        raise SystemExit(2)
    except HttpError as exc:
        print(f"\n  [FAIL] {exc.short(600)}")
        raise SystemExit(2)
    # Anything else -- expired az token, DNS, timeout, JSON decode -- must
    # land as the same one-line [FAIL] the panic table trains you to read.
    # A raw traceback mid-take is the loudest way to lose a recording.
    except Exception as exc:
        print(f"\n  [FAIL] {type(exc).__name__}: {exc}")
        if "Credential" in type(exc).__name__:
            print("  [FIX]  run: az login")
        raise SystemExit(2)
