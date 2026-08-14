# Extract content from documents

Part of **Objective domain 5: Implement information extraction solutions** (10-15%), Lesson 18 (L18).

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Extract information by using multimodal pipelines that combine OCR, layout analysis, and field extraction
2. Produce clean, grounded representations to use with agents and RAG by using Content Understanding
3. Implement analyzers for generating structured or markdown outputs for downstream reasoning by using Content Understanding

## What the demo shows

One script, three beats, one per objective. Every beat is independently
runnable, so you can study them in any order.

| Beat | Command | What it proves |
| --- | --- | --- |
| 1 Ladder | `--only ladder` | The same scanned page through `digitalParse`, `read`, and `layout`, then a born-digital PDF through two of them. |
| 2 Grounding | `--only ground` | A paragraph's **span** into the markdown and its **polygon** onto the page, with a round-trip proof. |
| 3 Analyzer | `--only analyzer` | Building a custom analyzer with `extract`, `classify`, and `generate` fields, running it, and deleting it. |

**Content Understanding is GA.** This lesson targets API version **`2025-11-01`**.
A lot of material still circulating targets `2024-12-01-preview` or
`2025-05-01-preview`, and those differ in breaking ways rather than merely being
older.

## The corpus is the argument

Two files in `assets/corpus/`, and the contrast between them carries the lesson:

| File | What it is |
| --- | --- |
| `wg-addendum-scan.png` | A **scan**. Pixels only, no text layer. The Premier Household wire-fee waiver exists nowhere else. |
| `wg-fee-schedule.pdf` | **Born-digital**. A real text layer and a real table. |

Both describe Woodgrove Bank, a fictitious company. The scan is the same file
Lesson 17 indexed, which lets you see the extraction step that lesson took for
granted.

## Run it

```bash
# 1. Build the per-lesson environment
uv sync

# 2. Keyless auth. These scripts use AzureCliCredential, so this is the identity.
az login

# 3. Copy the env template and fill in your values
cp .env.example .env

# 4. See the plan without calling Azure
uv run python m18_extract_demo.py --dry-run

# 5. Run all three beats
uv run python m18_extract_demo.py

# ...or one at a time
uv run python m18_extract_demo.py --only ladder
uv run python m18_extract_demo.py --only ground
uv run python m18_extract_demo.py --only analyzer

# Keep the custom analyzer around to poke at it in the portal
uv run python m18_extract_demo.py --only analyzer --keep
```

Beat 3 creates exactly one analyzer, `ai103L18AddendumV1`, and deletes it on the
way out. Run the whole thing twice; it is idempotent by construction.

## Things that will bite you

**`prebuilt-digitalParse` returns zero characters from a scan and reports
`Succeeded`.** Nothing errors. It reads an existing text layer and never looks at
pixels, so against an image it correctly finds nothing. A pipeline that checks
only `status` ships empty documents.

**Grounding is off by default.** Without
`estimateFieldSourceAndConfidence: true` in the analyzer config, fields come back
with no `confidence` and no `source`, silently.

**`baseAnalyzerId` accepts exactly four values:** `prebuilt-document`,
`prebuilt-audio`, `prebuilt-video`, `prebuilt-image`. You *call* a prebuilt like
`prebuilt-invoice`; you *inherit* from a base. Those are different verbs.

**`models.completion` is mandatory once you add a `fieldSchema`,** and its
absence fails the **build**, not the analyze.

**Deleting an analyzer needs Content Understanding Owner.** Contributor can
build and run one but cannot remove it.

**A poll returning HTTP 200 does not mean the work succeeded.** Read the `status`
field. Both build and analyze are long-running operations.

## Why REST instead of the SDK

There is a stable Python SDK (`azure-ai-contentunderstanding`) and it is the
right choice in production. These scripts speak raw REST over `urllib` because
the **JSON is the lesson**: objective domain 5 tests whether you can read an
analyzer definition and predict what it will return. A typed client turns every
one of those shapes into a constructor keyword you will never look at.

## Further reading

- [Content Understanding overview](https://learn.microsoft.com/azure/ai-services/content-understanding/overview)
- [Analyzer reference (every `config` property)](https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/analyzer-reference)
- [Prebuilt analyzers](https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/prebuilt-analyzers)
- [Document elements: spans and source](https://learn.microsoft.com/azure/ai-services/content-understanding/document/elements)
- [Choosing between Content Understanding and Document Intelligence](https://learn.microsoft.com/azure/ai-services/content-understanding/choosing-right-ai-tool)

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
