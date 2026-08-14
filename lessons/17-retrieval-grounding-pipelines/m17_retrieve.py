#!/usr/bin/env python
"""
AI-103 Lesson 17, Beat 3a - keyword, vector, hybrid, and the semantic ranker.

    uv run python m17_retrieve.py

THE ARGUMENT THIS SCRIPT MAKES
------------------------------
Keyword search and vector search fail in OPPOSITE directions. BM25 wins on
exact tokens -- product codes, part numbers, surnames -- because it matches
characters. Vectors win on paraphrase and concept, because they match meaning
and do not care what words you used. Hybrid search is not a hedge or a
compromise. It is coverage of two different failure modes, and this script shows
both failures happening before it shows the fix.

Then two things everyone gets wrong:

1. A FUSED HYBRID SCORE IS NOT ON THE SAME SCALE AS A BM25 SCORE. Reciprocal
   Rank Fusion throws the raw scores away and keeps only each document's RANK
   POSITION in each list, because an unbounded BM25 score and a bounded
   similarity score cannot be added. A hybrid score that looks tiny can be a
   perfect match. Never put a quality threshold on one.

2. THE SEMANTIC RANKER IS A RERANKER, NOT A RETRIEVER. It reorders a bounded
   window of what the first stage already found. A document that never made the
   initial result set cannot be rescued by it. Fix recall first -- hybrid,
   chunking -- then rerank. Reranking a bad candidate set just reorders wrong
   answers.

AND THE ONE THAT PAYS FOR THE WHOLE LESSON
------------------------------------------
Request D sets queryType to semantic on a pure vector query with a perfectly
valid semantic configuration. It returns HTTP 200 with results and NO reranker
score at all, because on a pure vector query the ranker is invoked by the
`semanticQuery` parameter, not by `queryType`. Nothing errors. Nothing warns.
A 200 proves that Azure accepted your request. It never proves Azure did what
you think you asked for.

    --no-cache   every query goes live
    --clean      drop the cache first
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import m17_cache
import m17_common as C
from m17_common import Fail, HttpError, Search, bad, banner, head, kv, ok, warn

sys.path.insert(0, str(pathlib.Path(__file__).parent / "assets"))
import make_assets  # noqa: E402

# A rare exact token. Nothing to generalize from, everything to match on.
TOKEN_QUERY = make_assets.ADDENDUM_CODE

# Pure concept. "abroad" and "cost" appear nowhere in the corpus; the corpus
# says "outgoing international wire transfer" and "$45.00 per transfer".
CONCEPT_QUERY = make_assets.CONCEPT_QUERY

# The one document that genuinely answers CONCEPT_QUERY. Everything else in
# the corpus talks about wires without ever quoting the international fee.
ANSWER_DOC = "wg-fee-schedule.md"

# The answer to this lives ONLY inside the scanned PNG.
GROUNDING_QUERY = ("do Premier Household customers pay the outgoing "
                   "domestic wire transfer fee")

TOP = 3
K = 50   # the semantic ranker only ever sees the top 50 from stage one; a
         # smaller k starves it, and a restrictive postFilter starves it more.


def vector_query(text: str) -> dict:
    """
    Integrated vectorization at QUERY time.

    `kind: text` means the search service calls the embedding model itself.
    There is no client-side embedding code in this repo, and there is no chance
    of the query being embedded by a different model than the content was --
    which is the silent relevance killer this design removes.
    """
    return {"kind": "text", "text": text, "fields": "text_vector", "k": K}


def show(label: str, response, note: str = "") -> list:
    head(label)
    if note:
        print(f"  {note}")
    rows = response.get("value") or []
    if not rows:
        warn("no results")
        return rows
    print()
    print(f"  {'#':<3}{'@search.score':>15}{'rerankerScore':>16}  document")
    print(f"  {'-' * 3}{'-' * 15:>15}{'-' * 16:>16}  {'-' * 28}")
    for i, row in enumerate(rows[:TOP], 1):
        score = row.get("@search.score")
        rerank = row.get("@search.rerankerScore")
        print(f"  {i:<3}{score:>15.6f}"
              f"{(f'{rerank:.4f}' if rerank is not None else '-- none --'):>16}"
              f"  {row.get('title', '?')}")
    return rows


def rank_of(response, name: str) -> tuple[int | None, int]:
    """Where did the document that actually answers the question land?

    Top-1 is a coin flip on a corpus this small. RANK is the honest measure of
    recall, and it is the number that moves between methods.
    """
    rows = response.get("value") or []
    for i, row in enumerate(rows, 1):
        if row.get("title") == name:
            return i, len(rows)
    return None, len(rows)


def snippet(row: dict, width: int = 190) -> str:
    return " ".join(str(row.get("chunk", "")).split())[:width]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    m17_cache.add_cache_arguments(parser)
    args = parser.parse_args()
    m17_cache.apply_cache_arguments(args)

    settings = C.load_settings()
    search = Search(settings)
    path = f"indexes/{C.INDEX}/docs/search"

    banner("AI-103 L17 Beat 3a -- two ways to fail, one way to cover both",
           f"index {C.INDEX}")
    print()
    print("  Read the ORDER, not the decimals. BM25 scores depend on corpus-wide")
    print("  term statistics, so rebuilding the index can move them without any")
    print("  behavior changing. The cache keeps them identical across retakes of")
    print("  the SAME index; a reindex is allowed to shift them.")

    def q(label: str, body: dict, api_version: str | None = None):
        payload, cached = search.cached("search", label, "POST", path, body,
                                        api_version=api_version)
        return payload

    # -----------------------------------------------------------------------
    # 1. Where KEYWORD wins. A rare exact token.
    # -----------------------------------------------------------------------
    banner("1. exact token -- where BM25 wins")
    kv("query", TOKEN_QUERY)
    rows = show("keyword only (BM25)",
                q("token-bm25", {"search": TOKEN_QUERY, "select": "title,chunk",
                                 "top": TOP, "count": True}),
                "an addendum code. Characters, not meaning.")
    if rows:
        print(f"\n  {snippet(rows[0])}\n")
    show("pure vector (no keyword recall at all)",
         q("token-vector", {"vectorQueries": [vector_query(TOKEN_QUERY)],
                            "select": "title,chunk", "top": TOP}),
         "an embedding of an identifier is an embedding of nothing in particular")
    print("\n  A vector query ALWAYS returns k neighbors, even when nothing is")
    print("  genuinely similar -- the nearest neighbor of a nonsense question is")
    print("  still a neighbor. Pure vector retrieval never comes back empty, so")
    print("  it feeds confident-looking garbage to a model unless keyword recall")
    print("  supplies the 'no good match' signal.")

    # -----------------------------------------------------------------------
    # 2. Where KEYWORD has nothing to match. Pure paraphrase.
    # -----------------------------------------------------------------------
    banner("2. paraphrase -- where BM25 has nothing to match")
    kv("query", CONCEPT_QUERY)
    kv("the answer is in", ANSWER_DOC)
    kv("which says", "outgoing international wire transfer, $45.00")
    kv("shared vocabulary", "none of it -- no 'abroad', no 'cost'")

    bm25 = q("concept-bm25", {"search": CONCEPT_QUERY, "select": "title,chunk",
                              "top": 20, "count": True})
    show("keyword only (BM25)", bm25)
    bm25_rank, bm25_total = rank_of(bm25, ANSWER_DOC)
    print(f"\n  {snippet((bm25.get('value') or [{}])[0])}\n")

    vector = q("concept-vector", {"vectorQueries": [vector_query(CONCEPT_QUERY)],
                                  "select": "title,chunk", "top": 20})
    show("pure vector", vector)
    vector_rank, vector_total = rank_of(vector, ANSWER_DOC)

    head("where did the document that answers the question actually rank?")
    kv(f"{ANSWER_DOC} on BM25", f"rank {bm25_rank} of {bm25_total}")
    kv(f"{ANSWER_DOC} on vector", f"rank {vector_rank} of {vector_total}")
    print()
    print("  Be precise about what just happened, because it is NOT 'the vector")
    print("  got the right answer'. Neither method put it first. What changed is")
    print("  RECALL POSITION: keyword search buried the one document that")
    print("  answers the question at the bottom of the list, and vector search")
    print("  lifted it into the window a reranker can still see.")
    print()
    print("  That is the honest version of the hybrid argument. Recall decides")
    print("  what is REACHABLE. Ranking decides what is FIRST. Fix them in that")
    print("  order -- reranking a candidate set that never contained the answer")
    print("  just reorders wrong answers faster.")

    # -----------------------------------------------------------------------
    # 3. Hybrid, and what happens to the score scale.
    # -----------------------------------------------------------------------
    banner("3. hybrid -- and the score collapse that is not a regression")
    hybrid = q("concept-hybrid",
               {"search": CONCEPT_QUERY,
                "vectorQueries": [vector_query(CONCEPT_QUERY)],
                "select": "title,chunk", "top": TOP, "count": True})
    show("hybrid (BM25 + vector, fused)", hybrid)
    print("\n  Reciprocal Rank Fusion discards both raw scores and keeps only")
    print("  each document's RANK in each list. The fused number therefore lives")
    print("  on its own compressed range, bounded by how many queries were fused.")
    print("  Scores falling by two orders of magnitude while the ORDER stays")
    print("  correct is the tell that nothing regressed. A genuine embedding")
    print("  model mismatch tanks the scores AND scrambles the order.")
    print("\n  Fusion also kicks in whenever more than one query runs in")
    print("  parallel -- including a single vector query across two vector")
    print("  fields. Fusion does not mean 'hybrid'.")

    # -----------------------------------------------------------------------
    # 4. Semantic reranking, captions, and extractive answers.
    # -----------------------------------------------------------------------
    banner("4. the semantic ranker -- a second pass over what stage one found")
    semantic = q("concept-semantic",
                 {"search": CONCEPT_QUERY,
                  "vectorQueries": [vector_query(CONCEPT_QUERY)],
                  "queryType": "semantic",
                  "semanticConfiguration": C.SEMANTIC_CONFIG,
                  "captions": "extractive",
                  "answers": "extractive|count-1",
                  "select": "title,chunk", "top": TOP})
    show("semantic hybrid", semantic)
    semantic_rank, _ = rank_of(semantic, ANSWER_DOC)
    print()
    kv(f"{ANSWER_DOC} now ranks", semantic_rank)
    print("  Last on keyword. Mid-list on vector. First after reranking, and the")
    print("  extractive answer below is the fee table itself.")
    for answer in (semantic.get("@search.answers") or [])[:1]:
        print()
        kv("extractive answer score", f"{answer.get('score', 0):.4f}")
        print(f"  {' '.join(str(answer.get('text', '')).split())[:280]}")
    for row in (semantic.get("value") or [])[:1]:
        for caption in (row.get("@search.captions") or [])[:1]:
            print()
            kv("caption", "")
            print(f"  {' '.join(str(caption.get('text', '')).split())[:280]}")
    print("\n  Captions and answers are pulled VERBATIM out of text already in")
    print("  the index. No model composes them. If the content contains no")
    print("  answer-shaped prose you get no answer back, and that is correct")
    print("  behavior -- an extractive answer is not a RAG response.")

    # -----------------------------------------------------------------------
    # 5. THE SILENT NO-OP. This is the beat that matters.
    # -----------------------------------------------------------------------
    banner("5. the silent no-op -- HTTP 200 proves nothing")
    without = q("noop-without-semanticquery",
                {"vectorQueries": [vector_query(CONCEPT_QUERY)],
                 "queryType": "semantic",
                 "semanticConfiguration": C.SEMANTIC_CONFIG,
                 "select": "title", "top": TOP})
    show("A. pure vector + queryType=semantic + a valid semanticConfiguration",
         without, "HTTP 200. Results. Look at the reranker column.")

    with_sq = q("noop-with-semanticquery",
                {"vectorQueries": [vector_query(CONCEPT_QUERY)],
                 "queryType": "semantic",
                 "semanticConfiguration": C.SEMANTIC_CONFIG,
                 "semanticQuery": CONCEPT_QUERY,
                 "select": "title", "top": TOP})
    show("B. identical request plus semanticQuery", with_sq,
         "one extra property. Same 200.")

    a_ranked = any(r.get("@search.rerankerScore") is not None
                   for r in (without.get("value") or []))
    b_ranked = any(r.get("@search.rerankerScore") is not None
                   for r in (with_sq.get("value") or []))
    print()
    if not a_ranked and b_ranked:
        ok("A was never reranked. B was. Neither request errored.")
        ok("queryType=semantic invokes the ranker for plain-text and hybrid "
           "queries.")
        ok("On a PURE VECTOR query, semanticQuery is the parameter that does it.")
        ok("Raising k would not have fixed A -- the ranker was never called.")
    else:
        warn(f"expected A unranked and B ranked; got A={a_ranked} B={b_ranked}")

    # -----------------------------------------------------------------------
    # 6. Grounding on content that was never text.
    # -----------------------------------------------------------------------
    banner("6. grounding on a fact that only ever existed as pixels")
    kv("question", GROUNDING_QUERY)
    grounded = q("grounding-semantic",
                 {"search": GROUNDING_QUERY,
                  "vectorQueries": [vector_query(GROUNDING_QUERY)],
                  "queryType": "semantic",
                  "semanticConfiguration": C.SEMANTIC_CONFIG,
                  "select": "title,source_kind,chunk", "top": TOP})
    rows = show("semantic hybrid", grounded)
    healthy = bool(rows) and str(rows[0].get("title", "")).endswith(".png")
    if rows:
        print(f"\n  {snippet(rows[0], 320)}\n")
        kv("citation", rows[0].get("title"))
        kv("content type", rows[0].get("source_kind"))
    if healthy:
        ok("the top-ranked grounding chunk came out of the scanned image")
    else:
        bad("the scanned image did not win. Check the OCR chain in Beat 2.")

    print()
    kv("cache", m17_cache.summary())
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
