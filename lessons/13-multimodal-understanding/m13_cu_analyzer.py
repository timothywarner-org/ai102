#!/usr/bin/env python
"""
AI-103 Lesson 13 - Beat 2: A custom Content Understanding IMAGE analyzer.

Covers learning objectives:
  LO5  Configure Azure Content Understanding in Foundry Tools to extract
       visual characteristics
  LO8  Identify objects, components, or regions within images

THE ONE THING TO UNDERSTAND
---------------------------
Content Understanding does NOT do object detection. It returns FIELDS, not
BOUNDING BOXES.

If you ask it "where is the damaged carton", you do not get back
`{"x": 412, "y": 88, "w": 130, "h": 96}`. You get back whatever your field
schema declared - for example a string field named `damage_location` whose value
is "top-left corner of the chart". The localization is expressed in
NATURAL LANGUAGE, because a language model produced it.

That is why LO8 says "identify objects, components, or regions" and not
"detect and localize objects". You satisfy LO8 by DESIGNING A FIELD SCHEMA that
asks for the region in words. If a downstream system genuinely needs pixel
coordinates, Content Understanding is the wrong tool - reach for Azure AI Vision
object detection or a custom model instead. Knowing that boundary is exam-worthy.

TWO MORE IMAGE-SPECIFIC CONSTRAINTS THAT SURPRISE PEOPLE
--------------------------------------------------------
1. `method: "extract"` is NOT available for images. The docs state plainly that
   extract is only supported for document analyzers. Images get `generate` and
   `classify` only. Declaring an extract field on an image analyzer is a
   design-time error, so this script refuses to build one.

2. Image analyzers have the most limited `config` of ANY modality - only
   `returnDetails` and `disableFaceBlurring`. There is no enableOcr, no
   enableLayout, no estimateFieldSourceAndConfidence. Source grounding and
   confidence scores are DOCUMENT-ONLY features. Do not promise a customer
   per-field confidence on an image pipeline; it does not exist.

USAGE
-----
  # Prints the analyzer JSON and validates the schema. No Azure calls.
  python m13_cu_analyzer.py --dry-run

  # Create (or replace) the analyzer, then analyze an image
  python m13_cu_analyzer.py --image-url https://example.com/artifact.jpg

  # Reuse an analyzer that already exists - skip creation
  python m13_cu_analyzer.py --skip-create --image-url https://example.com/artifact.jpg

  # Analyze a LOCAL file (binary upload - no public URL needed)
  python m13_cu_analyzer.py --image ./assets/compass-chart.png

  # Show what the service thinks the analyzer looks like, then clean up
  python m13_cu_analyzer.py --describe
  python m13_cu_analyzer.py --delete

PREREQS
-------
  az login
  pip install azure-ai-contentunderstanding
  .env with CONTENTUNDERSTANDING_ENDPOINT (the services.ai.azure.com host!)

GROUNDING
---------
  Analyzer reference (config per modality, method enum, field types):
    https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/analyzer-reference
  Best practices ("extract is only supported for document analyzers"):
    https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/best-practices
  Service limits (image: <=200 MB, 50x50 to 10k x 10k, 1000 fields, 300 categories):
    https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/service-limits
  Python SDK:
    https://learn.microsoft.com/en-us/python/api/overview/azure/ai-contentunderstanding-readme
"""

from __future__ import annotations

# Proxy scrub before any SDK import - see m13_vision_chat.py for the rationale.
import os

for _proxy_var in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
):
    os.environ.pop(_proxy_var, None)

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

from azure.ai.contentunderstanding import ContentUnderstandingClient  # noqa: E402
from azure.ai.contentunderstanding.models import AnalysisInput  # noqa: E402
from azure.identity import AzureCliCredential  # noqa: E402

# --- Service limits we validate against locally -------------------------------
MAX_IMAGE_BYTES = 200 * 1024 * 1024   # 200 MB
MAX_FIELDS = 1_000
MAX_CLASSIFY_CATEGORIES = 300
MIN_DIM, MAX_DIM = 50, 10_000         # 50x50 min, 10k x 10k max

# `extract` is deliberately absent - it is document-only.
IMAGE_METHODS = ("generate", "classify")
VALID_TYPES = ("string", "number", "boolean", "date", "object", "array")

# Image analyzers support exactly these two config keys. Nothing else.
IMAGE_CONFIG_KEYS = ("returnDetails", "disableFaceBlurring")


# =============================================================================
# The analyzer definition
# =============================================================================
def build_analyzer_definition(analyzer_id: str, completion_model: str) -> dict:
    """
    Build the analyzer as a plain dict.

    WHY A DICT AND NOT THE ContentAnalyzer MODEL CLASS
    --------------------------------------------------
    `begin_create_analyzer` accepts either a `ContentAnalyzer` object or a
    `MutableMapping[str, Any]`. We use the mapping because it is byte-for-byte
    the same JSON shown in the REST docs and in the Foundry portal, so students
    can copy this straight into a REST call, an ARM template, or the portal's
    JSON editor. It also keeps the snake_case/camelCase translation out of the
    lesson - the wire format is camelCase and this is the wire format.

    Scenario: maritime archive digitization. An archivist photographs an artifact
    -- a chart, an instrument, a logbook page -- and we turn that photo into a
    row in a collections database. Same shape as any real intake pipeline.
    """
    return {
        # Top-level analyzer properties, per the analyzer reference.
        "analyzerId": analyzer_id,
        "description": (
            "AI-103 Lesson 13 demo. Maritime archive intake: turns an artifact "
            "photo into structured catalog fields."
        ),
        # baseAnalyzerId selects the MODALITY. prebuilt-image is the base image
        # analyzer. Using prebuilt-imageSearch instead would optimize the output
        # for RAG indexing rather than for custom field extraction.
        "baseAnalyzerId": "prebuilt-image",
        # Image analyzers accept ONLY these two config keys.
        "config": {
            # returnDetails adds per-segment technical detail to the response.
            # Cheap, and invaluable when you are debugging why a field came back
            # empty - turn it off in production if you do not consume it.
            "returnDetails": True,
            # Faces are blurred by DEFAULT. Set this True only with a documented
            # business justification and a privacy review. An archive holds crew
            # portraits, so you want the default (blurring ON), which means
            # leaving this False.
            "disableFaceBlurring": False,
        },
        # A custom fieldSchema requires a completion model role. The analyzer
        # runs a generative model under the hood; you are telling it which
        # deployment in THIS account to use.
        "models": {"completion": completion_model},
        "fieldSchema": {
            "name": "ArtifactIntake",
            "description": (
                "Catalog attributes visible in a single photograph of a maritime "
                "archive artifact."
            ),
            "fields": {
                # ---------------------------------------------------------------
                # generate: the model writes a value from scratch based on the
                # image. Free-form. Use it when the answer is not a fixed choice.
                # ---------------------------------------------------------------
                "artifact_summary": {
                    "type": "string",
                    "method": "generate",
                    "description": (
                        "One or two sentences summarizing the artifact: what it is, "
                        "its materials, and how it is presented in the frame. "
                        "Describe only what is visible."
                    ),
                },
                "primary_artifact_type": {
                    "type": "string",
                    "method": "generate",
                    "description": (
                        "The dominant object in the frame, for example 'magnetic "
                        "compass', 'navigational chart', or 'ship's logbook'."
                    ),
                },
                # ---- THIS FIELD IS HOW WE SATISFY LO8 --------------------------
                # We want to "identify objects, components, or regions". Content
                # Understanding cannot hand back coordinates, so we ask for the
                # region IN WORDS and make the description do the heavy lifting.
                # The quality of this description IS the quality of the output.
                "damage_locations": {
                    "type": "array",
                    "method": "generate",
                    "description": (
                        "Locations of visible damage, wear, tearing, foxing, or "
                        "discoloration. Describe each location in plain language "
                        "relative to the frame, for example 'top-left corner of the "
                        "chart' or 'along the lower edge'. Return an empty array if "
                        "the artifact is undamaged. NOTE: this returns descriptive "
                        "text, not pixel coordinates."
                    ),
                    "items": {"type": "string"},
                },
                "visible_markings": {
                    "type": "array",
                    "method": "generate",
                    "description": (
                        "Text, numerals, or maker's marks legibly readable in the "
                        "image. Transcribe exactly as printed. Do not infer wording "
                        "from context - if you cannot read it, omit it."
                    ),
                    "items": {"type": "string"},
                },
                # ---------------------------------------------------------------
                # classify: the model must pick from YOUR enum. Use it whenever a
                # downstream system needs a predictable value it can switch on.
                # This is the difference between a demo and a pipeline.
                # ---------------------------------------------------------------
                "condition_grade": {
                    "type": "string",
                    "method": "classify",
                    "description": (
                        "Overall physical condition of the artifact, judged by the "
                        "amount of visible damage, wear, and discoloration."
                    ),
                    "enum": ["excellent", "good", "fair", "poor"],
                },
                "subject_matter": {
                    "type": "string",
                    "method": "classify",
                    "description": (
                        "The archival subject category this artifact belongs to, "
                        "based on what the image actually shows."
                    ),
                    "enum": ["navigation", "cartography", "vessel", "portrait", "other"],
                },
                "image_quality": {
                    "type": "string",
                    "method": "classify",
                    "description": (
                        "Usability of the photograph itself for cataloging. Flag "
                        "blurred, dark, or badly angled photos so a human can "
                        "request a re-shoot instead of trusting bad data."
                    ),
                    "enum": ["good", "blurry", "poorly_lit", "obstructed"],
                },
                "requires_conservator_review": {
                    "type": "boolean",
                    "method": "generate",
                    "description": (
                        "True if the visible damage is severe enough to warrant "
                        "review by a conservator before the artifact is handled."
                    ),
                },
            },
        },
    }


# =============================================================================
# Design-time validation
# =============================================================================
def validate_definition(definition: dict) -> list[str]:
    """
    Check the analyzer against image-modality rules BEFORE sending it.

    Every rule here maps to a real service constraint. Catching these locally
    turns a vague HTTP 400 into a sentence that names the offending field.
    Returns a list of human-readable problems; empty means valid.
    """
    problems: list[str] = []

    base = definition.get("baseAnalyzerId", "")
    if not base.startswith("prebuilt-image"):
        problems.append(
            f"baseAnalyzerId '{base}' is not an image analyzer; these rules assume images."
        )

    # --- config: images support exactly two keys ------------------------------
    for key in definition.get("config", {}):
        if key not in IMAGE_CONFIG_KEYS:
            problems.append(
                f"config.{key} is not supported by IMAGE analyzers. "
                f"Images support only {IMAGE_CONFIG_KEYS}. "
                f"(enableOcr/enableLayout/estimateFieldSourceAndConfidence are document-only.)"
            )

    fields = definition.get("fieldSchema", {}).get("fields", {})
    if not fields:
        problems.append("fieldSchema.fields is empty - the analyzer would return nothing.")
    if len(fields) > MAX_FIELDS:
        problems.append(f"{len(fields)} fields exceeds the {MAX_FIELDS} limit.")

    for name, spec in fields.items():
        method = spec.get("method")
        ftype = spec.get("type")

        # The headline image constraint.
        if method == "extract":
            problems.append(
                f"field '{name}' uses method 'extract', which is DOCUMENT-ONLY. "
                f"Image analyzers support only {IMAGE_METHODS}."
            )
        elif method not in IMAGE_METHODS:
            problems.append(
                f"field '{name}' has method '{method}'; images allow {IMAGE_METHODS}."
            )

        if ftype not in VALID_TYPES:
            problems.append(f"field '{name}' has type '{ftype}'; valid types are {VALID_TYPES}.")

        if not spec.get("description"):
            problems.append(
                f"field '{name}' has no description. The description IS the prompt - "
                f"an undescribed field produces garbage."
            )

        if method == "classify":
            categories = spec.get("enum")
            if not categories:
                problems.append(f"field '{name}' is classify but declares no enum categories.")
            elif len(categories) > MAX_CLASSIFY_CATEGORIES:
                problems.append(
                    f"field '{name}' has {len(categories)} categories; "
                    f"the limit is {MAX_CLASSIFY_CATEGORIES}."
                )

        # Source grounding / confidence is document-only. Guard against a
        # copy-paste from a document analyzer sample.
        if spec.get("estimateSourceAndConfidence"):
            problems.append(
                f"field '{name}' requests source grounding/confidence, which is "
                f"DOCUMENT-ONLY. Images never return confidence scores."
            )

    return problems


# =============================================================================
# Client + operations
# =============================================================================
def build_client() -> ContentUnderstandingClient:
    """Construct the Content Understanding client against the correct host."""
    endpoint = os.getenv("CONTENTUNDERSTANDING_ENDPOINT", "").strip()
    if not endpoint:
        raise SystemExit(
            "[config] CONTENTUNDERSTANDING_ENDPOINT is not set.\n"
            "         Expected: https://<account>.services.ai.azure.com/"
        )

    # The endpoint trap, guarded explicitly.
    if "openai.azure.com" in endpoint:
        raise SystemExit(
            "[config] CONTENTUNDERSTANDING_ENDPOINT points at the Azure OPENAI host.\n"
            "         Content Understanding lives on:\n"
            "           https://<account>.services.ai.azure.com/\n"
            "         The two data planes are NOT interchangeable."
        )
    if "/openai/v1" in endpoint:
        raise SystemExit(
            "[config] Strip '/openai/v1' from CONTENTUNDERSTANDING_ENDPOINT.\n"
            "         The SDK wants the bare account host with a trailing slash."
        )

    # AzureCliCredential, never DefaultAzureCredential. Note that unlike the
    # OpenAI client, the Azure SDK pipeline takes a TokenCredential directly and
    # its BearerTokenCredentialPolicy already refreshes the token on every
    # request. So there is no get_bearer_token_provider wrapper needed here -
    # the refresh problem we solved by hand in m13_vision_chat.py is solved for
    # us inside the Azure SDK. That matters on video jobs that poll for minutes.
    credential = AzureCliCredential()
    return ContentUnderstandingClient(endpoint=endpoint, credential=credential)


def create_analyzer(client: ContentUnderstandingClient, definition: dict) -> None:
    """Create or replace the analyzer. This is a long-running operation."""
    analyzer_id = definition["analyzerId"]
    print(f"  [create] analyzer '{analyzer_id}' ...")
    print("  [create] this is an LRO - the service compiles the schema first")

    # allow_replace=True makes the demo re-runnable. Without it a second run
    # fails with a conflict, which is a miserable thing to hit on camera.
    poller = client.begin_create_analyzer(analyzer_id, definition, allow_replace=True)
    analyzer = poller.result()

    print(f"  [created] {analyzer.analyzer_id}  status={analyzer.status}")

    # Warnings are where the service tells you it quietly ignored something -
    # a misspelled config key, an unsupported method. Never swallow these.
    warnings = getattr(analyzer, "warnings", None)
    if warnings:
        for w in warnings:
            print(f"  [warn] {w}")
    else:
        print("  [warn] none")


def analyze(
    client: ContentUnderstandingClient,
    analyzer_id: str,
    image_url: str | None,
    image_path: Path | None,
) -> None:
    """Run the analyzer over one image and print the structured result."""
    print(f"  [analyze] analyzer '{analyzer_id}'")

    if image_path is not None:
        size = image_path.stat().st_size
        if size > MAX_IMAGE_BYTES:
            raise SystemExit(
                f"[image] {image_path.name} is {size:,} bytes; limit is "
                f"{MAX_IMAGE_BYTES:,} (200 MB)."
            )
        print(f"  [analyze] binary upload: {image_path.name}  {size:,} bytes")
        # begin_analyze_binary posts the bytes directly - no public URL required.
        poller = client.begin_analyze_binary(
            analyzer_id, image_path.read_bytes(), content_type="application/octet-stream"
        )
    else:
        print(f"  [analyze] url: {image_url}")
        print("  [analyze] the SERVICE fetches this URL - it must be publicly reachable")
        # Note `inputs` is keyword-only and takes a LIST, even for one image.
        poller = client.begin_analyze(analyzer_id, inputs=[AnalysisInput(url=image_url)])

    result = poller.result()
    print("  [analyze] complete")
    print()

    if not result.contents:
        print("  [empty] The result had no contents. Check that the input decoded.")
        return

    content = result.contents[0]

    # ---- The markdown view ---------------------------------------------------
    markdown = getattr(content, "markdown", None)
    if markdown:
        print("=" * 78)
        print("  MARKDOWN VIEW (the human-readable rendering of the image)")
        print("=" * 78)
        print(markdown)
        print()

    # ---- The structured fields - this is the actual product ------------------
    print("=" * 78)
    print("  STRUCTURED FIELDS (this is what your database consumes)")
    print("=" * 78)

    fields = getattr(content, "fields", None)
    if not fields:
        print("  [empty] No fields returned. Usually means the field descriptions")
        print("          were too vague, or the image did not match the schema.")
        return

    # Field values arrive wrapped in a typed envelope: a string field carries
    # `valueString`, a number `valueNumber`, an array `valueArray`, and so on.
    # We unwrap to plain Python so the JSON below is readable on camera.
    simplified = {name: _unwrap(value) for name, value in fields.items()}
    print(json.dumps(simplified, indent=2, ensure_ascii=False))
    print()

    print("  [note] Look at what came back and what did NOT.")
    print("         Present: descriptive strings, enum classifications, arrays.")
    print("         Absent : bounding boxes, x/y coordinates, per-field confidence.")
    print("         Confidence and source grounding are DOCUMENT-ONLY features.")
    print("         'damage_locations' localizes in WORDS - that is LO8 here.")


def _unwrap(value):
    """
    Recursively flatten a Content Understanding field envelope to plain Python.

    WHY THIS IS FIDDLIER THAN IT LOOKS
    ----------------------------------
    `ContentField` is a DISCRIMINATED type. The `type` property selects a
    concrete subclass - StringField, NumberField, IntegerField, BooleanField,
    DateField, TimeField, ArrayField, ObjectField, JsonField - and each one
    carries its value under a DIFFERENT attribute: `value_string`,
    `value_number`, `value_array`, and so on. There is no single `.value`.

    On the wire those same properties are camelCase (`valueString`,
    `valueArray`). The SDK models are MutableMappings over that raw payload, so
    both access styles can appear depending on whether the field was in your
    declared schema and whether the discriminator resolved. We handle BOTH, and
    we recurse, because arrays and objects nest more ContentFields inside.

    Note the deliberate `is not None` checks: a boolean field whose value is
    False must NOT be treated as missing.
    """
    from collections.abc import Mapping

    # --- Typed subclass form (snake_case attributes) --------------------------
    for attr in (
        "value_string",
        "value_number",
        "value_integer",
        "value_boolean",
        "value_date",
        "value_time",
    ):
        v = getattr(value, attr, None)
        if v is not None:
            return v

    v = getattr(value, "value_array", None)
    if v is not None:
        return [_unwrap(item) for item in v]

    v = getattr(value, "value_object", None)
    if v is not None:
        return {k: _unwrap(item) for k, item in v.items()}

    # --- Raw wire form (camelCase keys) ---------------------------------------
    # ContentField is a MutableMapping but NOT a dict subclass, so test Mapping.
    if isinstance(value, Mapping):
        for key in (
            "valueString",
            "valueNumber",
            "valueInteger",
            "valueBoolean",
            "valueDate",
            "valueTime",
        ):
            if value.get(key) is not None:
                return value[key]
        if value.get("valueArray") is not None:
            return [_unwrap(item) for item in value["valueArray"]]
        if value.get("valueObject") is not None:
            return {k: _unwrap(item) for k, item in value["valueObject"].items()}
        # Field was returned but carries no value - the model found nothing.
        return None

    return None


def triage(exc: Exception) -> None:
    """Per-symptom triage for Content Understanding failures."""
    text = str(exc)
    status = getattr(exc, "status_code", None)

    print()
    print("  [error] Content Understanding call failed. Triage:")

    if status == 401 or "401" in text:
        print("  [401] Token rejected. Run 'az login'. Confirm the 'Cognitive")
        print("        Services User' role on the Foundry account.")
    elif status == 403 or "403" in text:
        print("  [403] Wrong principal, or RBAC has not propagated (~5 min).")
        print("        Check: az account show --query user.name -o tsv")
    elif status == 404 or "404" in text:
        print("  [404] Endpoint or analyzer not found.")
        print("        - CONTENTUNDERSTANDING_ENDPOINT must be the")
        print("          *.services.ai.azure.com host, NOT *.openai.azure.com")
        print("        - If analyzing: the analyzer ID does not exist yet.")
        print("          Drop --skip-create so it gets created first.")
        print("        - Content Understanding is not available in every region.")
    elif status == 409 or "409" in text or "Conflict" in text:
        print("  [409] An analyzer with this ID already exists.")
        print("        We pass allow_replace=True, so if you still see this,")
        print("        the existing analyzer is mid-create. Wait, or bump")
        print("        CU_IMAGE_ANALYZER_ID in .env.")
    elif status == 429 or "429" in text:
        print("  [429] Throttled. Content Understanding has per-account limits")
        print("        independent of your OpenAI TPM. Back off and retry.")
    elif "InvalidArgument" in text or "400" in text:
        print("  [400] The service rejected the analyzer or the input.")
        print("        Most likely causes, in order:")
        print("          1. A field used method 'extract' (document-only).")
        print("          2. A config key images do not support.")
        print("          3. models.completion names a deployment that does not")
        print("             exist in THIS account.")
        print("        Re-run with --dry-run to see the exact JSON.")
    else:
        print("  [??] Unrecognized failure.")

    print(f"  [raw] {text[:600]}")
    print()


# =============================================================================
# Entry point
# =============================================================================
def main() -> int:
    parser = argparse.ArgumentParser(
        description="AI-103 L13 Beat 2 - custom Content Understanding image analyzer (LO5, LO8).",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print and validate the analyzer JSON. Zero Azure calls.")
    parser.add_argument("--image-url", help="Publicly reachable image URL to analyze.")
    parser.add_argument("--image", help="Local image file to analyze (binary upload).")
    parser.add_argument("--skip-create", action="store_true",
                        help="Assume the analyzer already exists; go straight to analyze.")
    parser.add_argument("--describe", action="store_true",
                        help="Fetch and print the analyzer as the SERVICE stores it, then exit.")
    parser.add_argument("--delete", action="store_true",
                        help="Delete the analyzer and exit. Use after the demo.")
    args = parser.parse_args()

    analyzer_id = os.getenv("CU_IMAGE_ANALYZER_ID", "ai103L13ImageV1")
    completion_model = os.getenv("CU_COMPLETION_MODEL", "gpt-5-mini")

    print()
    print("AI-103 Lesson 13 | Beat 2 | Content Understanding custom image analyzer")
    print("-" * 78)
    print(f"  [analyzer] {analyzer_id}")
    print(f"  [api-version] {os.getenv('CONTENTUNDERSTANDING_API_VERSION', '2025-11-01')} (GA)")

    definition = build_analyzer_definition(analyzer_id, completion_model)

    # Validate ALWAYS - live or dry-run. A schema error should never reach Azure.
    problems = validate_definition(definition)
    field_count = len(definition["fieldSchema"]["fields"])
    methods = [f["method"] for f in definition["fieldSchema"]["fields"].values()]
    print(f"  [schema] {field_count} fields | "
          f"{methods.count('generate')} generate | {methods.count('classify')} classify | "
          f"0 extract (unavailable for images)")

    if problems:
        print()
        print("  [invalid] The analyzer definition breaks image-modality rules:")
        for p in problems:
            print(f"    - {p}")
        return 1
    print("  [schema] valid for the image modality")

    # ---- DRY RUN -------------------------------------------------------------
    if args.dry_run:
        print("  [mode] DRY RUN - no Azure calls, no token acquisition")
        print()
        print("=" * 78)
        print("  ANALYZER DEFINITION (exactly what would be PUT to the service)")
        print("=" * 78)
        print(json.dumps(definition, indent=2))
        print()
        print("  [dry-run] Would call:")
        print(f"    client.begin_create_analyzer({analyzer_id!r}, <definition>, allow_replace=True)")
        target = args.image_url or args.image or "<--image-url or --image>"
        if args.image:
            print(f"    client.begin_analyze_binary({analyzer_id!r}, <bytes of {target}>)")
        else:
            print(f"    client.begin_analyze({analyzer_id!r}, inputs=[AnalysisInput(url={target!r})])")
        print()
        print("  [dry-run] Reminders:")
        print("    - 'extract' is document-only; this schema uses generate + classify.")
        print("    - Images support only returnDetails + disableFaceBlurring.")
        print("    - Output is FIELDS, not bounding boxes.")
        print()
        return 0

    # ---- LIVE ----------------------------------------------------------------
    print("  [mode] LIVE")
    client = build_client()
    print(f"  [endpoint] {os.getenv('CONTENTUNDERSTANDING_ENDPOINT')}")
    print("  [auth] AzureCliCredential (keyless)")
    print()

    try:
        if args.delete:
            client.delete_analyzer(analyzer_id)
            print(f"  [deleted] {analyzer_id}")
            return 0

        if args.describe:
            analyzer = client.get_analyzer(analyzer_id)
            print(f"  [analyzer] {analyzer.analyzer_id}")
            print(f"  [status] {analyzer.status}")
            print(f"  [base] {analyzer.base_analyzer_id}")
            print(f"  [created] {analyzer.created_at}")
            return 0

        if not args.skip_create:
            create_analyzer(client, definition)
            print()

        if not args.image_url and not args.image:
            print("  [note] No image supplied - analyzer created but nothing analyzed.")
            print("         Re-run with --image-url <url> or --image <path>.")
            return 0

        image_path = Path(args.image) if args.image else None
        if image_path and not image_path.exists():
            raise SystemExit(f"[image] Not found: {image_path}")

        analyze(client, analyzer_id, args.image_url, image_path)

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        triage(exc)
        return 1

    print()
    print("-" * 78)
    print("  [done] Beat 2 complete.")
    print("  [cleanup] python m13_cu_analyzer.py --delete")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
