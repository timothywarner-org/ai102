# Implement responsible AI for multimodal content

Part of **Objective domain 3: Implement computer vision solutions** (10-15%), Lesson 14 (L14).

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Implement filters to classify unsafe or disallowed visual content
2. Detect and mitigate indirect prompt injection by using embedded text in images
3. Enforce visual policy rules, such as applying watermarks, flagging prohibited symbols, upholding brand usage requirements, and detecting potentially inappropriate content

## Recording runbook

**`Warner.AI-103.Lesson-14-demo-runbook.md`** in this folder. Three beats, roughly 15 minutes,
about 63 seconds of it actual service time.

## Demos

| Script | Beat | Objective | What it owns |
| --- | --- | --- | --- |
| `m14_visual_filter.py` | 1 | LO1 | Analyze Image, three policy profiles, the ACCEPT/REJECT engine |
| `m14_pixel_injection.py` | 2 | LO2 | Vision OCR into Prompt Shields, `documents` vs `userPrompt` |
| `m14_visual_policy.py` | 3 | LO3 | Four-rule composition, strict JSON schema, watermark remediation |
| `assets/make_assets.py` | setup | -- | Regenerates all three image fixtures, deterministically |
| `m14_cache.py` | all | -- | Content-hashed cache so every command is re-runnable |

### Setup

```bash
uv sync
az login
cp .env.example .env        # then fill in the two endpoints
cd assets && uv run --project .. python make_assets.py && cd ..
```

Every script takes `--dry-run`, which validates locally and prints the exact request it would
send without calling Azure. Start there.

### Re-running

All three scripts are safe to run as many times as you like. Remote results are cached by a
hash of the request content -- the image bytes, the prompt, the model, the api-version -- so a
second run is roughly **10 seconds instead of 76**, costs nothing, and returns **byte-identical**
output. Change the image or the policy and the key changes, so the call goes live again.

Every result is labeled `[live]` or `[cached]`, and every run ends with a `cache:` tally. Nothing
is hidden.

| Flag | Effect |
| --- | --- |
| `--clean` | Delete `.cache/` and `out/`, then run. Rip and replace. |
| `--no-cache` | Ignore the cache, call Azure every time. |
| `--audit <file>` | Write decision records, **replacing** the file. |
| `--audit-append` | Append instead, when you actually want accumulation. |

```bash
uv run python m14_visual_filter.py --dry-run
uv run python m14_visual_filter.py                  # all three fixtures, default policy
uv run python m14_visual_filter.py --policy strict  # same scores, opposite decision

uv run python m14_pixel_injection.py                # clean invoice, then poisoned invoice
uv run python m14_pixel_injection.py --mitigate     # adds the spotlighting delimiters
uv run python m14_pixel_injection.py --wrong-field  # the misconfiguration, on purpose

uv run python m14_visual_policy.py --apply-watermark
uv run python m14_visual_policy.py --image out/invoice-clean-watermarked.png
```

## Three hostnames, one Azure account

This is where the time goes if you get it wrong, so it is worth memorizing:

| Surface | Host | Used by |
| --- | --- | --- |
| Chat and vision | `*.openai.azure.com` (scripts append `/openai/v1`) | Beats 2 and 3 |
| Content Safety | `*.cognitiveservices.azure.com` | Beats 1 and 2 |
| Content Understanding | `*.services.ai.azure.com` | Lesson 13 |

One AIServices account publishes all three. Send an `image:analyze` payload to the wrong one of
its own hostnames and you get a 404 with no explanation. Confirm what yours publishes:

```bash
az cognitiveservices account show -n <account> -g <rg> --query properties.endpoints
```

## RBAC

Every call here is keyless, using `AzureCliCredential`. Your signed-in identity needs
**Cognitive Services User** on the account. Owner is not enough, because Owner is a control-plane
role and these are data-plane calls. A 403 means the role assignment, not the endpoint.

## Fixtures

`assets/make_assets.py` generates three images from code so the attack payload is auditable in
plain text rather than buried in a PNG:

- `invoice-clean.png` -- a benign vendor invoice, the control
- `invoice-poisoned.png` -- the same invoice plus an embedded instruction block
- `poster-violent.png` -- a drawn horror one-sheet, the one fixture that scores above zero
  (Violence severity 2, verified live 2026-08-12)

The generator is seeded, so re-running it produces identical bytes every time.

## Related lessons

Lesson 12 covers Content Credentials, C2PA manifests, and Microsoft's invisible watermark in
`m12_provenance_scan.py`. That material is referenced from Beat 3 on purpose and deliberately not
repeated here.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
