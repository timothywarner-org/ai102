#!/usr/bin/env python
"""
AI-103 Lesson 13 - Beat 4: Single-task pipelines, and what replaced pro mode.

Covers learning objective:
  LO7  Configure single-task and pro-mode Content Understanding pipelines

READ THIS BEFORE YOU RUN IT
---------------------------
The exam objective still says "pro mode". The service no longer has one.

Pro mode shipped only in the preview API version `2025-05-01-preview`. That
preview version was retired on 15 July 2026, and pro mode was explicitly NOT
carried forward into the GA API `2025-11-01`. The migration guidance states it
plainly: "AnalysisMode is being deprecated and standard is the only mode
supported in the GA API." So there is no supported way to call pro mode today,
and this script deliberately does not try. Any code you find online that sets
`"mode": "pro"` is dead code.

What pro mode DID: multi-file reasoning. You handed it several related files at
once - a claim form plus supporting invoices plus a policy document - and it
reasoned ACROSS them, aggregating one schema over the whole bundle and
optionally consulting a reference knowledge base.

What replaces it: agentic mode. You enable it at analyzer creation time with
`config.workflow = "agentic"`. It is DOCUMENTS ONLY, it processes ONE FILE PER
REQUEST, and Microsoft is explicit that it is NOT a drop-in replacement for pro
mode. That last point is the whole migration story: if your pro-mode pipeline
depended on cross-file aggregation, agentic mode does not restore it. You
re-architect - fan out per file, then aggregate in your own orchestration layer.

    +---------------------+----------------------+-------------------------+
    |                     | pro mode (RETIRED)   | agentic mode            |
    +---------------------+----------------------+-------------------------+
    | Status              | gone with            | preview                 |
    |                     | 2025-05-01-preview   |                         |
    | Modalities          | documents            | documents ONLY          |
    | Files per request   | many (cross-file)    | ONE                     |
    | Enabled by          | mode = "pro"         | config.workflow =       |
    |                     |                      | "agentic"               |
    | Cross-file schema   | yes                  | NO - do it yourself     |
    +---------------------+----------------------+-------------------------+

Note the modality trap, because it is exactly the kind of thing an exam tests:
Lesson 13 is a MULTIMODAL lesson, but neither pro mode nor agentic mode ever
worked on images or video. Both are document-side features. Your image and video
pipelines (Beats 2 and 3) are single-task standard analyzers, full stop.

WHY THIS SCRIPT IS DRY-RUN BY DEFAULT
-------------------------------------
Two independent reasons:
  1. Pro mode cannot be called at all - it no longer exists.
  2. Agentic mode is preview-only, so it requires a preview API version and a
     document workload that is out of scope for a multimodal lesson.

So the agentic path here is a DEFINITION BUILDER and a migration explainer, not
a caller. The single-task (standard) path is a real analyzer you may optionally
create live with --create-single-task, which is the half of LO7 that is fully
supported today.

USAGE
-----
  python m13_agentic_mode.py --dry-run              # everything, no Azure calls
  python m13_agentic_mode.py --show single-task     # just the standard analyzer
  python m13_agentic_mode.py --show agentic         # just the agentic definition
  python m13_agentic_mode.py --show migration       # just the migration guidance
  python m13_agentic_mode.py --create-single-task   # LIVE: create the standard one

GROUNDING
---------
  What's new (pro mode not carried forward to GA; preview retirement):
    https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/whats-new
  Preview-to-GA migration ("AnalysisMode is being deprecated"):
    https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/how-to/migration-preview-to-ga
  Standard and pro modes (historical context):
    https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/standard-pro-modes
  Analyzer reference (top-level shape, config, methods):
    https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/analyzer-reference

  !! VERIFICATION NOTE - READ BEFORE RECORDING !!
  The exact spelling `config.workflow = "agentic"` came from course research
  notes and could NOT be re-confirmed at authoring time:

    - No public Learn page surfaced by search mentions "agentic mode" for
      Content Understanding. The standard-and-pro-modes page and the
      preview-to-GA migration page both contain no occurrence of "agentic".
    - The installed GA SDK (azure-ai-contentunderstanding 1.1.0, targeting API
      2025-11-01) exposes a ContentAnalyzerConfig with NO `workflow` property.
      Its config properties are: annotation_format, chart_format,
      content_categories, disable_face_blurring, enable_figure_analysis,
      enable_figure_description, enable_formula, enable_layout, enable_ocr,
      enable_segment, estimate_field_source_and_confidence, locales,
      omit_content, return_details, segment_per_page, table_format.

  That absence is CONSISTENT with agentic mode being preview-only (a GA SDK
  would not model a preview-only property), so it is not evidence against the
  feature - but it is also not confirmation. This is precisely why this script
  builds the definition as a plain dict rather than a typed ContentAnalyzerConfig:
  an unknown key passes straight through to the wire, so the code survives
  either outcome.

  RE-VERIFY the property name against the Content Understanding REST reference
  for the current preview API version before teaching it as fact. Everything
  else in this file is doc-confirmed. This is the single riskiest string in the
  Lesson 13 asset set.
"""

from __future__ import annotations

# Proxy scrub before SDK import - see m13_vision_chat.py.
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

from dotenv import load_dotenv

load_dotenv(override=True)

from azure.ai.contentunderstanding import ContentUnderstandingClient  # noqa: E402
from azure.identity import AzureCliCredential  # noqa: E402

GA_API_VERSION = "2025-11-01"
PREVIEW_API_VERSION = "2026-06-01-preview"
RETIRED_PREVIEW = "2025-05-01-preview"
RETIREMENT_DATE = "2026-07-15"


# =============================================================================
# 1. The single-task pipeline - fully supported, GA, works today
# =============================================================================
def build_single_task_analyzer(analyzer_id: str, completion_model: str) -> dict:
    """
    A standard ("single-task") analyzer.

    "Single-task" means: one analyzer, one file per request, one schema applied
    to that file. It is the ONLY mode in the GA API, and it is what every image
    and video analyzer in this lesson already is. Beats 2 and 3 were single-task
    pipelines - we just did not name them that at the time.
    """
    return {
        "analyzerId": analyzer_id,
        "description": (
            "AI-103 L13 Beat 4. Single-task standard analyzer: one document in, "
            "one structured record out."
        ),
        "baseAnalyzerId": "prebuilt-document",
        "config": {
            "returnDetails": True,
            "enableOcr": True,
            "enableLayout": True,
            # Source grounding + confidence is a DOCUMENT-ONLY capability. This
            # is why the images in Beat 2 could not have it. Worth pointing at
            # on camera - the contrast makes the constraint memorable.
            "estimateFieldSourceAndConfidence": True,
        },
        "models": {"completion": completion_model},
        "fieldSchema": {
            "name": "InspectionReport",
            "description": "Key facts from a single field inspection report.",
            "fields": {
                # extract IS available here, because this is a DOCUMENT analyzer.
                # The same field on an image analyzer would be rejected.
                "site_id": {
                    "type": "string",
                    "method": "extract",
                    "description": "The site or store identifier printed on the report.",
                },
                "inspection_date": {
                    "type": "date",
                    "method": "extract",
                    "description": "The date the inspection was performed.",
                },
                "findings_summary": {
                    "type": "string",
                    "method": "generate",
                    "description": "Two-sentence summary of the inspector's findings.",
                },
                "severity": {
                    "type": "string",
                    "method": "classify",
                    "description": "Overall severity of the issues recorded.",
                    "enum": ["none", "minor", "major", "critical"],
                },
            },
        },
    }


# =============================================================================
# 2. The agentic-mode definition - the pro-mode successor
# =============================================================================
def build_agentic_analyzer(analyzer_id: str, completion_model: str) -> dict:
    """
    Build (do NOT submit) an agentic-mode analyzer definition.

    The ONLY structural difference from a single-task analyzer is one key:
    `config.workflow = "agentic"`. Everything else - baseAnalyzerId, models,
    fieldSchema - is the shape you already know. That is genuinely the whole
    API surface of the feature, which is why the migration effort lives in your
    ORCHESTRATION, not in your analyzer JSON.

    See the VERIFICATION NOTE in the module docstring regarding the exact
    spelling of the `workflow` property.
    """
    return {
        "analyzerId": analyzer_id,
        "description": (
            "AI-103 L13 Beat 4. Agentic-mode analyzer - the successor to the "
            "retired pro mode. Documents only, one file per request."
        ),
        # Documents only. There is no agentic image or video analyzer.
        "baseAnalyzerId": "prebuilt-document",
        "config": {
            # >>> THE ONE KEY THAT CHANGES EVERYTHING <<<
            # Turns on multi-step agentic reasoning over a SINGLE document:
            # the service plans, re-reads, and cross-checks within that file
            # instead of doing one shot of extraction.
            "workflow": "agentic",
            "returnDetails": True,
            "enableOcr": True,
            "enableLayout": True,
            "estimateFieldSourceAndConfidence": True,
        },
        "models": {"completion": completion_model},
        "fieldSchema": {
            "name": "ClaimAdjudication",
            "description": (
                "Fields requiring reasoning across sections of ONE claim document."
            ),
            "fields": {
                "claim_number": {
                    "type": "string",
                    "method": "extract",
                    "description": "The claim reference number.",
                },
                "total_claimed": {
                    "type": "number",
                    "method": "extract",
                    "description": "Total amount claimed, in the document's currency.",
                },
                # This is the kind of field agentic mode exists for: the answer
                # is not printed anywhere. It requires reading the itemized
                # section, summing it, and comparing against the stated total.
                "line_items_reconcile": {
                    "type": "boolean",
                    "method": "generate",
                    "description": (
                        "True if the sum of the itemized charges equals the stated "
                        "total. Add the line items yourself and compare - do not "
                        "assume the printed total is correct."
                    ),
                },
                "adjudication_rationale": {
                    "type": "string",
                    "method": "generate",
                    "description": (
                        "Explain, citing specific sections of this document, whether "
                        "the claim appears internally consistent and complete."
                    ),
                },
            },
        },
    }


# =============================================================================
# 3. The migration explainer
# =============================================================================
def print_migration_guidance() -> None:
    """Print the pro-mode-to-agentic migration story, on screen, for the camera."""
    print()
    print("=" * 78)
    print("  PRO MODE -> AGENTIC MODE : WHAT ACTUALLY CHANGES")
    print("=" * 78)
    print()
    print(f"  Pro mode shipped ONLY in preview API {RETIRED_PREVIEW}.")
    print(f"  That preview version was retired on {RETIREMENT_DATE}.")
    print(f"  Pro mode was NOT carried forward into GA API {GA_API_VERSION}.")
    print("  The migration doc: 'AnalysisMode is being deprecated and standard")
    print("  is the only mode supported in the GA API.'")
    print()
    print("  Net effect: there is no supported way to invoke pro mode today.")
    print()
    print("  " + "-" * 74)
    print("  FEATURE COMPARISON")
    print("  " + "-" * 74)
    rows = [
        ("Status", "RETIRED", "Preview"),
        ("API version", RETIRED_PREVIEW, PREVIEW_API_VERSION),
        ("Modalities", "Documents", "Documents ONLY"),
        ("Files per request", "Many (cross-file)", "ONE"),
        ("Enabled by", 'mode = "pro"', 'config.workflow = "agentic"'),
        ("Cross-file schema", "Yes", "No"),
        ("Knowledge base", "Yes", "Re-verify in preview docs"),
    ]
    print(f"  {'':<20} {'PRO MODE':<22} {'AGENTIC MODE':<28}")
    print(f"  {'':<20} {'-' * 22:<22} {'-' * 28:<28}")
    for label, pro, agentic in rows:
        print(f"  {label:<20} {pro:<22} {agentic:<28}")
    print()
    print("  " + "-" * 74)
    print("  MIGRATION STEPS")
    print("  " + "-" * 74)
    print()
    print("  1. INVENTORY. Find every analyzer that set mode='pro'. They are")
    print("     already failing - the API version they targeted is retired.")
    print()
    print("  2. SPLIT THE BUNDLE. Pro mode took N related files in one request.")
    print("     Agentic mode takes ONE. Fan out: submit each file separately.")
    print()
    print("  3. REBUILD THE AGGREGATION YOURSELF. This is the real work, and the")
    print("     reason Microsoft says agentic mode is NOT a drop-in replacement.")
    print("     The cross-file reasoning that pro mode did inside the service is")
    print("     now YOUR responsibility. Options:")
    print("       - Collect per-file results, then run one chat-completions call")
    print("         over the combined JSON to do the cross-document reasoning.")
    print("       - Or orchestrate with an agent that calls the analyzer per file")
    print("         and reconciles the outputs as a tool-use loop.")
    print()
    print("  4. ADD config.workflow = 'agentic' where per-document multi-step")
    print("     reasoning genuinely earns its cost. It is slower and pricier than")
    print("     a standard analyzer. Do not switch it on by reflex.")
    print()
    print("  5. LEAVE IMAGE AND VIDEO ALONE. Neither mode ever applied to them.")
    print("     Your multimodal pipelines stay single-task standard analyzers.")
    print()
    print("  EXAM FRAMING")
    print("  " + "-" * 74)
    print("  The objective still says 'pro mode', so you must know what it WAS,")
    print("  that it is gone, and what replaced it. If a question offers pro mode")
    print("  for an IMAGE or VIDEO workload, it is wrong twice over: wrong")
    print("  modality, and a retired feature.")
    print()


def show_definition(title: str, definition: dict, notes: list[str]) -> None:
    """Pretty-print an analyzer definition with commentary."""
    print()
    print("=" * 78)
    print(f"  {title}")
    print("=" * 78)
    print(json.dumps(definition, indent=2))
    print()
    for note in notes:
        print(f"  [note] {note}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AI-103 L13 Beat 4 - single-task pipelines and the pro-mode successor (LO7).",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Explicit no-Azure mode. This script defaults to it anyway.")
    parser.add_argument("--show", choices=["all", "single-task", "agentic", "migration"],
                        default="all", help="Which section to print.")
    parser.add_argument("--create-single-task", action="store_true",
                        help="LIVE: actually create the standard analyzer (GA, supported).")
    args = parser.parse_args()

    completion_model = os.getenv("CU_COMPLETION_MODEL", "gpt-5-mini")
    single_id = "ai103-l13-single-task-v1"
    agentic_id = "ai103-l13-agentic-v1"

    print()
    print("AI-103 Lesson 13 | Beat 4 | Single-task pipelines + the pro-mode successor")
    print("-" * 78)
    print(f"  [ga api] {GA_API_VERSION}   [preview api] {PREVIEW_API_VERSION}")
    print(f"  [retired] pro mode, with {RETIRED_PREVIEW}, on {RETIREMENT_DATE}")
    print("  [mode] DEFINITION-ONLY for agentic - it is preview and documents-only")
    print()

    if args.show in ("all", "single-task"):
        show_definition(
            "1. SINGLE-TASK (STANDARD) ANALYZER - GA, supported, works today",
            build_single_task_analyzer(single_id, completion_model),
            [
                "One file in, one structured record out. This is the ONLY mode in GA.",
                "Beats 2 and 3 were both single-task pipelines - image and video.",
                "'extract' is legal HERE because this is a document analyzer.",
                "estimateFieldSourceAndConfidence is document-only - images never get it.",
            ],
        )

    if args.show in ("all", "agentic"):
        show_definition(
            "2. AGENTIC-MODE ANALYZER - preview, documents only, NOT submitted",
            build_agentic_analyzer(agentic_id, completion_model),
            [
                "The ONLY structural difference is config.workflow = 'agentic'.",
                "Documents ONLY. There is no agentic image or video analyzer.",
                "ONE file per request - pro mode's cross-file bundle is gone.",
                "Microsoft: NOT a drop-in replacement for pro mode.",
                f"Requires a preview API version ({PREVIEW_API_VERSION}), not GA.",
                "This script does NOT submit this definition, by design.",
                "VERIFY the 'workflow' property spelling against the current",
                "preview REST reference before relying on it - see the docstring.",
            ],
        )

    if args.show in ("all", "migration"):
        print_migration_guidance()

    # ---- Optional live path: the supported half of LO7 ------------------------
    if args.create_single_task:
        if args.dry_run:
            print("  [skip] --dry-run overrides --create-single-task. Nothing sent.")
            return 0

        endpoint = os.getenv("CONTENTUNDERSTANDING_ENDPOINT", "").strip()
        if not endpoint:
            raise SystemExit("[config] CONTENTUNDERSTANDING_ENDPOINT is not set.")

        print("=" * 78)
        print("  LIVE: creating the single-task analyzer")
        print("=" * 78)
        client = ContentUnderstandingClient(endpoint=endpoint, credential=AzureCliCredential())
        try:
            poller = client.begin_create_analyzer(
                single_id, build_single_task_analyzer(single_id, completion_model),
                allow_replace=True,
            )
            analyzer = poller.result()
            print(f"  [created] {analyzer.analyzer_id}  status={analyzer.status}")
            for w in (getattr(analyzer, "warnings", None) or []):
                print(f"  [warn] {w}")
            print(f"  [cleanup] client.delete_analyzer({single_id!r})")
        except Exception as exc:  # noqa: BLE001
            print(f"  [error] {exc}")
            print("  [hint] 401/403 -> az login and check 'Cognitive Services User'.")
            print("  [hint] 400     -> models.completion must name a deployment in")
            print("                    THIS account. Check CU_COMPLETION_MODEL.")
            return 1

    print("-" * 78)
    print("  [done] Beat 4 complete.")
    print("  [takeaway] Pro mode is gone. Agentic mode is documents-only, one file")
    print("             per request, and explicitly not a drop-in replacement.")
    print("             Your image and video pipelines were never affected.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
