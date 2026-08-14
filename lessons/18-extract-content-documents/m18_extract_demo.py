#!/usr/bin/env python
"""
AI-103 Lesson 18 - Extract content from documents with Content Understanding.

Three beats, one per learning objective, each independently runnable so a
retake never costs you the whole demo:

  --only ladder   LO1  OCR, layout, and field extraction in one pipeline
  --only ground   LO2  clean, grounded representations for agents and RAG
  --only analyzer LO3  custom analyzers, structured AND markdown output

Everything is READ-ONLY against Azure except Beat 3, which creates one custom
analyzer under the ai103L18 prefix and deletes it again on the way out. Run it
twice; it is idempotent by construction.

    uv run python m18_extract_demo.py --dry-run
    uv run python m18_extract_demo.py
    uv run python m18_extract_demo.py --only ground

THE CORPUS IS THE ARGUMENT
--------------------------
Two files, chosen so that every claim on the slides is falsifiable on screen:

  wg-addendum-scan.png  a SCAN. Pixels only, no text layer. The Premier
                        Household wire-fee waiver exists nowhere else.
  wg-fee-schedule.pdf   BORN-DIGITAL. A real text layer and a real table.

Same analyzer over both, or three analyzers over the same file, and the
variable under test is always exactly one thing.
"""
from __future__ import annotations

import argparse
import base64
import json

import m18_common as c
from m18_common import (
    ANALYZER_DIGITAL,
    ANALYZER_LAYOUT,
    ANALYZER_READ,
    BASE_ANALYZERS,
    CORPUS,
    CUSTOM_ANALYZER,
    ContentUnderstanding,
    Fail,
    HttpError,
    load_settings,
)

SCAN = CORPUS / "wg-addendum-scan.png"
DIGITAL = CORPUS / "wg-fee-schedule.pdf"


def as_input(path) -> dict:
    """
    Inline the file as base64 under `data`.

    Two things worth saying out loud when this is on screen. First, the key is
    `data`, not `base64Source` -- Document Intelligence used the latter and the
    muscle memory misfires here. Second, the whole thing is wrapped in an
    `inputs` ARRAY that currently rejects a second element. The array is the
    service reserving room for multi-file input, not a batch you can use today.

    The alternative is {"url": "https://..."} for a blob the service can reach.
    Inlining keeps this demo free of a storage account, which is the right call
    when storage is not what the lesson is teaching.
    """
    if not path.exists():
        raise Fail(f"Missing fixture {path.name}. Run: uv run python assets/make_assets.py")
    return {"data": base64.b64encode(path.read_bytes()).decode()}


# ---------------------------------------------------------------------------
# Beat 1 -- LO1. Multimodal pipelines: OCR, layout analysis, field extraction.
# ---------------------------------------------------------------------------

def beat_ladder(cu: ContentUnderstanding) -> None:
    c.banner("BEAT 1 -- the prebuilt ladder",
             "LO1: OCR, layout analysis, and field extraction in one pipeline")

    c.head("The same scanned page through three prebuilt analyzers")
    print("""
  A scan has no text layer. Every character below had to be recovered from
  pixels. Watch what each rung of the ladder does with the identical bytes.
""")

    results = {}
    for analyzer in (ANALYZER_DIGITAL, ANALYZER_READ, ANALYZER_LAYOUT):
        result = cu.analyze(analyzer, as_input(SCAN), analyzer)
        content = c.first_content(result)
        results[analyzer] = content
        markdown = content.get("markdown", "")
        c.kv(f"{analyzer}", f"{len(markdown):>5} markdown characters")

    print()
    digital_len = len(results[ANALYZER_DIGITAL].get("markdown", ""))
    if digital_len == 0:
        c.warn(f"{ANALYZER_DIGITAL} returned ZERO characters -- and reported Succeeded")
        print("""
  This is the failure mode to remember. Nothing errored. The operation polled
  green. digitalParse reads an existing text layer and never looks at pixels,
  so against a scan it correctly does its job and correctly finds nothing.
  A pipeline that only checks status is a pipeline that ships empty documents.
""")
    else:
        c.warn(f"{ANALYZER_DIGITAL} returned {digital_len} chars -- expected 0 on a scan")

    c.head("What OCR recovered (prebuilt-read)")
    c.quote(results[ANALYZER_READ].get("markdown", ""), limit=260)

    c.head("What layout added on top of the same OCR")
    layout = results[ANALYZER_LAYOUT]
    read = results[ANALYZER_READ]
    c.kv("read: paragraphs", len(read.get("paragraphs") or []))
    c.kv("read: sections", len(read.get("sections") or []))
    c.kv("layout: paragraphs", len(layout.get("paragraphs") or []))
    c.kv("layout: sections", len(layout.get("sections") or []))
    print("""
  Same characters, different understanding. read gives you text. layout gives
  you reading order, paragraph boundaries, and a section tree -- the structure
  a chunker needs. That is why the deck says content extraction is a wider net
  than OCR: OCR is one skill inside it, not a synonym for it.
""")

    c.head("Now the born-digital PDF -- same digitalParse, opposite outcome")
    both = {}
    for analyzer in (ANALYZER_DIGITAL, ANALYZER_LAYOUT):
        content = c.first_content(cu.analyze(analyzer, as_input(DIGITAL), analyzer))
        both[analyzer] = content
        markdown = content.get("markdown", "")
        has_table = "<table" in markdown
        c.kv(analyzer, f"{len(markdown):>5} chars | HTML table: {has_table}")

    print()
    c.ok("digitalParse is not broken. It is cheaper, and it needs a text layer.")
    print("""
  One variable changed -- whether the bytes carry text or only pixels -- and
  the analyzer that returned nothing now returns the document. Choosing a rung
  on this ladder is a statement about your INPUT, not about your ambition.
""")

    c.head("Tables: the reason layout is not just prettier read")
    markdown = both[ANALYZER_LAYOUT].get("markdown", "")
    start = markdown.find("<table")
    if start >= 0:
        c.quote(markdown[start:markdown.find("</table>") + 8], limit=420)
        c.ok("HTML, not pipe-markdown -- so caption, header cells, and spans survive")
    else:
        c.warn("No HTML table found. Check tableFormat on the analyzer config.")

    print("""
  Pipe-markdown cannot express a merged cell or a caption. HTML can. When a fee
  table crosses a page break, this is the difference between one coherent table
  and two orphaned fragments that retrieve badly.
""")


# ---------------------------------------------------------------------------
# Beat 2 -- LO2. Clean, grounded representations for agents and RAG.
# ---------------------------------------------------------------------------

def beat_ground(cu: ContentUnderstanding) -> None:
    c.banner("BEAT 2 -- one markdown surface, two coordinate systems",
             "LO2: clean, grounded representations for agents and RAG")

    content = c.first_content(cu.analyze(ANALYZER_LAYOUT, as_input(SCAN), "layout"))
    markdown = content.get("markdown", "")

    c.head("The representation an agent actually consumes")
    c.kv("mimeType in", content.get("mimeType"))
    c.kv("kind out", content.get("kind"))
    c.kv("unit", content.get("unit"))
    c.kv("markdown characters", len(markdown))
    print("""
  A PNG went in. `kind: document` came out, measured in pixels. Audio and video
  land on this same markdown surface. That is the whole grounding story for RAG:
  you write ONE chunker and ONE indexer, and every modality arrives in the shape
  they already understand.
""")

    c.head("Grounding: where a paragraph lives, twice")
    paragraphs = content.get("paragraphs") or []
    target = next((p for p in paragraphs
                   if "Wire Transfer Fee Waiver" in p.get("content", "")),
                  paragraphs[1] if len(paragraphs) > 1 else {})
    print()
    c.quote(target.get("content", ""))
    print()
    span = target.get("span") or {}
    c.kv("span (into markdown)", f"offset {span.get('offset')}, length {span.get('length')}")
    c.kv("source (onto pixels)", c.decode_source(target.get("source", "")))
    c.kv("source, raw", (target.get("source") or "")[:64] + "...")
    print("""
  Two coordinates, and you need both. `span` is a character offset into the
  markdown -- that is how a citation survives chunking. `source` is a page
  number plus a four-point polygon -- that is how you draw a highlight box over
  the original scan for a human reviewer.

  Four points, not two, because scanned paper is skewed. A rectangle cannot
  describe text that sits three degrees off level.
""")

    c.head("Round-trip proof: read the span back out of the markdown")
    offset, length = span.get("offset"), span.get("length")
    if isinstance(offset, int) and isinstance(length, int):
        sliced = markdown[offset:offset + length]
        c.quote(sliced)
        if sliced.strip() == (target.get("content") or "").strip():
            c.ok("span sliced out of the markdown matches the paragraph exactly")
        else:
            c.warn("span slice differs -- check stringEncoding (default is codePoint)")
    print("""
  That match is not cosmetic. It is the guarantee that lets an agent cite a
  source: the offset means the same thing to the service and to your Python.
  Default encoding is Unicode code points, which is exactly how Python 3 indexes
  a string. Pass stringEncoding=utf16 and this line stops lining up.
""")


# ---------------------------------------------------------------------------
# Beat 3 -- LO3. Custom analyzers, structured or markdown, for downstream work.
# ---------------------------------------------------------------------------

ANALYZER_BODY = {
    "description": "AI-103 Lesson 18. Woodgrove Bank product addendum intake.",
    # Exactly four values are legal here, and prebuilt-invoice is NOT one of
    # them even though it is a document analyzer you can call directly. You
    # inherit from a BASE; you call a PREBUILT. The exam leans on that.
    "baseAnalyzerId": "prebuilt-document",
    "config": {
        "returnDetails": True,
        "enableOcr": True,
        "enableLayout": True,
        # THE switch. Off by default. Without it the fields below come back as
        # bare values with no confidence and no source, and the grounding beat
        # silently evaporates.
        "estimateFieldSourceAndConfidence": True,
        "tableFormat": "html",
    },
    "fieldSchema": {
        "name": "AddendumIntake",
        "description": "Fields a Woodgrove operations analyst needs off a product addendum.",
        "fields": {
            # method: extract -- pull a literal that is physically on the page.
            # Grounded to one spot, because it exists in exactly one spot.
            "addendum_id": {
                "type": "string",
                "method": "extract",
                "estimateSourceAndConfidence": True,
                "description": "The addendum identifier printed in the document header, "
                               "for example WG-ADD-7742. Transcribe exactly as printed.",
            },
            # method: classify -- choose from a closed list. The enum is the
            # contract; downstream code can switch on it without string-matching.
            "product_category": {
                "type": "string",
                "method": "classify",
                "description": "Which banking product this addendum modifies.",
                "enum": ["wire_transfer", "overdraft", "card_dispute",
                         "account_opening", "other"],
            },
            # method: generate -- synthesize. Nothing on the page says this
            # sentence; the model writes it FROM the page. Watch its grounding
            # come back as several polygons, because several places fed it.
            "waiver_summary": {
                "type": "string",
                "method": "generate",
                "description": "One sentence stating exactly what fee is waived and the "
                               "precise condition a household must meet to qualify.",
            },
            # A negative control. The scan says nothing about branch hours, so a
            # well-behaved analyzer must decline rather than invent.
            "branch_hours": {
                "type": "string",
                "method": "generate",
                "description": "The branch lobby hours stated in this document. If the "
                               "document does not state branch hours, return an empty string.",
            },
        },
    },
}


def beat_analyzer(cu: ContentUnderstanding, settings) -> None:
    c.banner("BEAT 3 -- a custom analyzer, built and run",
             "LO3: structured or markdown output for downstream reasoning")

    c.head("What you may inherit from")
    for base in BASE_ANALYZERS:
        c.kv("legal baseAnalyzerId", base)
    c.warn("prebuilt-invoice is NOT on this list. You call it; you cannot inherit it.")

    c.head("The definition")
    body = json.loads(json.dumps(ANALYZER_BODY))
    # models is mandatory the moment a fieldSchema appears. Omit it and the
    # BUILD fails -- not the analyze -- with a message naming this exact fix.
    # The values are model NAMES resolved against the resource defaults, which
    # is why this file never hardcodes a deployment name.
    body["models"] = {"completion": settings.completion_model,
                      "embedding": settings.embedding_model}
    print()
    c.quote(json.dumps({k: body[k] for k in ("baseAnalyzerId", "config", "models")},
                       indent=2))
    print("""
  models is not optional here. The moment a fieldSchema appears, this analyzer
  needs a completion deployment, and Content Understanding is bring-your-own
  model. Leave it out and the BUILD fails -- your analyze call never happens.
""")

    c.head("Build (long-running: 201, then poll)")
    cu.delete_analyzer(CUSTOM_ANALYZER)   # idempotent: a retake must not 409
    status, _, headers = cu.call("PUT", f"analyzers/{CUSTOM_ANALYZER}", body)
    operation = headers.get("Operation-Location") or headers.get("operation-location")
    c.kv("create returned", f"HTTP {status}")
    result = cu.poll(operation, "build")
    if result.get("status") != "Succeeded":
        detail = json.dumps(result.get("error", {}))[:400]
        raise Fail(f"analyzer build failed: {detail}")
    c.ok(f"{CUSTOM_ANALYZER} is ready")
    print("""
  A 201 means accepted, not finished. The poll can come back HTTP 200 carrying
  status Failed -- the poll succeeded, the work did not. Read status, not the
  HTTP code, or you will ship a broken analyzer and never see it.
""")

    c.head("Run it over the scan")
    content = c.first_content(cu.analyze(CUSTOM_ANALYZER, as_input(SCAN), "analyze"))
    fields = content.get("fields") or {}

    for name, meta in fields.items():
        value = meta.get("valueString", meta.get("value", ""))
        confidence = meta.get("confidence")
        spans = meta.get("spans") or []
        source = meta.get("source", "")
        print()
        c.kv("field", name)
        c.kv("  value", (str(value)[:88] + "...") if len(str(value)) > 88 else (str(value) or "(empty)"))
        c.kv("  confidence", confidence if confidence is not None else "(none)")
        c.kv("  grounded to", c.decode_source(source))
        c.kv("  spans", len(spans))

    c.head("Read the grounding, not just the values")
    extract_spans = len((fields.get("addendum_id") or {}).get("spans") or [])
    generate_spans = len((fields.get("waiver_summary") or {}).get("spans") or [])
    c.kv("addendum_id (extract)", f"{extract_spans} span(s)")
    c.kv("waiver_summary (generate)", f"{generate_spans} span(s)")
    if generate_spans > extract_spans:
        c.ok("generate is grounded to MORE of the page than extract -- as it should be")
    print("""
  That difference is the method doing its job. `extract` found a literal in one
  place and points at one place. `generate` wrote a sentence that exists nowhere
  on the page, assembled from several paragraphs, and its grounding names every
  one of them. Same document, same call, different accountability.
""")

    hours = (fields.get("branch_hours") or {}).get("valueString", "")
    if not str(hours).strip():
        c.ok("branch_hours came back empty -- the analyzer declined to invent it")
    else:
        c.warn(f"branch_hours returned '{hours}' -- the document never states hours")
    print("""
  The negative control matters more than the positive ones. A field description
  is a prompt, and a good prompt gives the model explicit permission to return
  nothing. Ask for a fact that is not there without that permission and you get
  a plausible, confident, wrong answer.
""")

    c.head("Both outputs, one call")
    markdown = content.get("markdown", "")
    c.kv("markdown characters", f"{len(markdown)}  -> feeds retrieval")
    c.kv("fields returned", f"{len(fields)}  -> feeds automation")
    print("""
  You did not choose between markdown and structure. One analyze call returned
  the prose surface a RAG index chunks AND the typed object a workflow branches
  on. That is the shape of an extraction pipeline worth building.
""")


def teardown(cu: ContentUnderstanding) -> None:
    c.head("Teardown")
    if cu.delete_analyzer(CUSTOM_ANALYZER):
        c.ok(f"deleted {CUSTOM_ANALYZER}")
    else:
        c.ok(f"{CUSTOM_ANALYZER} already absent")
    print("""
  Deleting needs Content Understanding Owner. Contributor can build and run an
  analyzer but cannot remove one -- a genuinely surprising least-privilege edge
  that turns cleanup scripts into 403s.
""")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=("ladder", "ground", "analyzer"),
                        help="run a single beat")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan and make no Azure calls")
    parser.add_argument("--keep", action="store_true",
                        help="leave the custom analyzer in place after Beat 3")
    args = parser.parse_args()

    settings = load_settings()
    c.banner("AI-103 Lesson 18 -- Extract content from documents",
             f"{settings.endpoint}  |  api-version {settings.api_version}")

    if args.dry_run:
        c.head("Plan (no Azure calls)")
        c.kv("Beat 1 ladder", f"{ANALYZER_DIGITAL} / {ANALYZER_READ} / {ANALYZER_LAYOUT}")
        c.kv("  over", f"{SCAN.name} then {DIGITAL.name}")
        c.kv("Beat 2 ground", f"{ANALYZER_LAYOUT} over {SCAN.name}")
        c.kv("Beat 3 analyzer", f"build + run + delete {CUSTOM_ANALYZER}")
        c.kv("  models", f"{settings.completion_model} / {settings.embedding_model}")
        for path in (SCAN, DIGITAL):
            (c.ok if path.exists() else c.bad)(f"fixture {path.name}")
        return 0

    cu = ContentUnderstanding(settings)
    try:
        if args.only in (None, "ladder"):
            beat_ladder(cu)
        if args.only in (None, "ground"):
            beat_ground(cu)
        if args.only in (None, "analyzer"):
            beat_analyzer(cu, settings)
            if not args.keep:
                teardown(cu)
    except HttpError as exc:
        c.bad(exc.short())
        return 1
    except Fail as exc:
        c.bad(str(exc))
        return 1

    c.banner("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
