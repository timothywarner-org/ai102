# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

The public **learner companion repo** for Tim Warner's Microsoft Press video course **Exam AI-103: Developing AI Apps and Agents on Azure** (the Microsoft Foundry + agents successor to AI-102). It ships hands-on demo code, per-lesson READMEs, and deliberately vulnerable sample apps used to teach security scanning. It is **not** a single application: it is a polyglot collection of independent, self-contained demos.

> "AI-102" in Tim's prompts almost always means **AI-103**. He habitually mis-types it. Read it as AI-103 and proceed silently unless he clearly means the retiring predecessor exam.

## Current state (2026-08-10)

- **Recorded/shipped:** Lessons 01 and 02. Lesson 03 deck, demo, and runbook are done and demo-verified (quota + cost, observability, index health + recall@k). **Lessons 03-11 all have in-repo `Warner.AI-103.Lesson-NN-demo-runbook.md` files** (L09 also has a Portal-Health-Check runbook). L05 has a working evals demo; **L10 and L11 are demo-verified green as of 2026-08-10** against the rebuilt environment.
- **Demo pattern per recorded lesson:** (a) a read-only instructor demo script (`mNN_*.py`) run live from the Edge portal + VS Code, and (b) a separate student-facing runnable notebook (`mNN_*_tour.ipynb`, keyless + idempotent). The recording is driven by an **old-school Markdown SAY/DO/PAUSE runbook** -- **not** a Jupyter runbook. (`Lesson-02-runbook.ipynb` reflects the abandoned notebook-runbook approach.)
- **Lesson assets live in the repo, all 18 lessons (rule set 2026-07-04).** Every lesson-specific artifact -- demo scripts, student notebooks, the `Warner.AI-103.Lesson-NN-demo-runbook.md`, per-lesson `.env.example` and config -- lives in this repo under `lessons/NN-*/`, **not** in the private Pearson GPD folder. The GPD folder keeps only authoring source of truth: the `.pptx` decks, `AI-103-OD-baseline.md`, the authoring `CLAUDE.md`, script/outline `.docx` files, deck `.bak` backups, and personal timing tooling (`speak.py`). If a lesson demo asset ever appears at the GPD root, move it into its `lessons/NN-*/` folder.
- **Demo surface rule -- do NOT shoehorn the SDK.** Match the demo surface to how the task is really done: **portal + IaC (Bicep / `az` CLI) for setup and security lessons** (deployments, identity, networking, RBAC); the **Python SDK only when code is the natural, valuable surface** -- building an agent (L1), or reading signals you'd genuinely automate (L3 monitoring). Never write an SDK script just to "show code" for a portal/IaC task -- L2's create-then-delete deployment script was exactly that mistake. And when Bicep or `az` is on screen, **explain it** (walk the resource and its properties), don't just flash it.
- **Deployed Azure env (rebuilt 2026-08-10):** RG `rg-ai103-mvp`, Foundry account **`YOUR-FOUNDRY-RESOURCE`** (eastus2), project **`proj-agents`**, model deployment **gpt-5-mini (2025-08-07)** GlobalStandard @ 50K TPM -- chosen because gpt-5-nano / gpt-5.1 have **0 granted quota** on this subscription. Application Insights **`appi-ai103-l11`** + Log Analytics `log-ai103-l11` are wired to the project for the L11 observability beat. **L10 and L11 share this one environment.** Keyless data-plane roles per the L4 convention: **Foundry User** (`53ca6127-...`) + **Cognitive Services OpenAI User** (`5e0bd9bd-...`) -- deliberately NOT Azure AI Developer. The whole RG had been deleted, and the prior account `aif-ai103-s9qdgp2o` was left **soft-deleted**, so it was purged before the rebuild (deleting alone does not free quota or release the name -- **purge**).
- **IaC (read `infra/README.md` first):** **`infra/ai103-lesson-env.bicep` is the one to reach for** -- a parameterized per-lesson environment (account + project + model, with `deployObservability=false` to skip telemetry). Pass the same `accountName` across lessons to share one quota grant; adding a project to an existing account is non-destructive. `infra/ai103-l11-agents.bicep` is the L10/L11-specific variant, kept because its deployment name (`l11-agents`) is quoted in both runbooks. Also present: `ai103-core.mvp.bicep` (targets rg-ai103-core), `ai103-core.bicep` (4 models, 18 projects, waiting on quota), `ai103-l3-observability.main.bicep`, `modules/{observability,search}.bicep`.
- **Auth in new demos:** keyless via `AzureCliCredential` (the `az login` identity), deterministic vs `DefaultAzureCredential`.
- **Tooling:** the Azure MCP server is wired into Claude Desktop config.

## Two-location workspace (READ THIS FIRST)

You operate across **two folders**, opened together via `C:\Users\timot\Desktop\ai103.code-workspace`:

| Folder | Path | Role |
|---|---|---|
| **Code repo** (this one) | `C:\github\ai103` | Public GitHub repo. Demo code, learner READMEs. |
| **Course development** | `C:\Users\timot\Pearson\GPD Laura L Video Development - Tim Warner - Exam AI-103 (Video)` | Private Pearson/MS Press authoring folder. Slide decks, speaker notes, the frozen objective domain. |

**Study the course folder regularly, not just on request.** It is the source of truth for course structure and exam alignment. It contains:
- `AI-103-OD-baseline.md` -- the **frozen Microsoft skills-measured objective domain** with domain weights and the lesson-to-objective map. This is the diff reference for catching silent Microsoft OD changes.
- `CLAUDE.md` -- authoring-specific instructions (speaker-notes house style, frozen LO rule, deck conventions). Read it before touching any course artifact.
- `lessons/Warner.AI-103.Lesson-01.pptx` ... `Lesson-18.pptx` -- the canonical decks.
- `examplar-speaker-notes/` -- shipped CKA decks used as the voice/format exemplar.

**The course folder's objective domain is the source of truth for lesson count and scope.** The course is **18 lessons** mapped to five objective domains (see `AI-103-OD-baseline.md`); the repo `README.md` and `lessons/README.md` now agree on 18. If any artifact ever reverts to the old 20-lesson AI-102-era list, treat the objective domain as canonical and flag the drift.

**Learning objectives and section headings are CANONICAL and FROZEN.** They map verbatim to the live Microsoft skills-measured list. Never reword them.

## Repo structure

- `lessons/NN-topic/` -- per-lesson demo code, a learner README, and a `Warner.AI-103.Lesson-NN-demo-runbook.md`. **All 18 lessons ship real demo assets** (verified 2026-08-22): demo scripts, `.env.example`, `pyproject.toml` + `uv.lock`. **L01 and L02 are the only lessons without a `-demo-runbook.md`** (L02 has the abandoned `Warner.AI-103.Lesson-02-runbook.ipynb` notebook format instead). Note **L04 is deliberately Python-free** -- it is a portal + PowerShell (`deploy-secure-foundry.ps1`) + Bicep lesson, per the demo-surface rule below, so "no `.py` here" and "no `.env.example`" are both correct rather than missing. Highlights: 01 is the flagship (`m01_agent_demo.py` + `model_bakeoff.py`), 02 is `m02_setup_demo.py`, 03 is `m03_ops_demo.py` (read-only ops signals) plus `m03_generate_signal.py` and the `m03_ops_tour.ipynb` student notebook, 05 is `m05_evals_demo.py`, 07 is `m07_prompt_demo.py` (three beats in one file, `# %%` cells), 08 is `rag.py`, 09 is `eval_trace.py` + `kql/`, **10 is `m10_tools_repl.py` (interactive tool-schema REPL) + `function_calling.py`**, **11 is `m11_multi_agent.py` (HandoffBuilder routing) + `m11_approval_flow.py` (approval gates) + `kql/`**, 12-18 each ship 2-7 `mNN_*.py` scripts (L16 and L17 also ship `validate.ps1` live-proof harnesses). The paired `mNN_*_tour.ipynb` student notebook exists only for **L01, L02, L03, L06**; that pattern was not carried past L06.
- `lesson-demo-apps/` -- larger standalone demo applications, each with its own toolchain and README:
  - `tim-chat-front-end/` -- full app with `frontend/`, `backend/`, and `infra/` (azd-deployable via `azure.yaml`).
  - `contoso-vulnerable-app-1/` and `contoso-secure-scan-1/` -- **intentionally vulnerable** Express apps + a CodeQL pack, for teaching SAST. Do not "fix" the vulnerabilities; they are the lesson. Renamed from `globomantics-*` on 2026-08-22: Globomantics is Pluralsight's sample company and Microsoft Press uses **Contoso**. The rename covered file contents, directory names, CodeQL pack ids, and npm package names.
- `_archive/` -- **gitignored, local only.** Holds the AI-102-era demo apps (`woodgrove-bank`, `azure-appinsights-node-sample-app`, `rock-band-name-checker`), an `sc100-cert-prep-agent` that belongs to a different certification, video-production artifacts, and dated backups. All of it was removed from the repo on 2026-08-22: those three apps carried **92 stale "AI-102" references and zero AI-103 ones**, ~216 MB of mushroom photos referenced by no code, a live Logic App SAS, and an expired Video Indexer JWT. Nothing in `lessons/` ever linked to them. Nothing is deleted -- it is on disk, just not shipped.

## Architecture conventions that span files

- **Foundry-first, keyless auth.** Demos authenticate to Microsoft Foundry with **`az login`**, not API keys. New demos use **`AzureCliCredential`** (the `az login` identity, deterministic) rather than `DefaultAzureCredential`, whose env-var probing can hijack the identity (see the auth-gotchas memory). The current GA path is the **Microsoft Agent Framework** with `FoundryChatClient`; the classic `create_agent`/thread/run API is deprecated (retires 2027) and should not be used in new demos.
- **Config via `.env`, never hardcoded.** Each demo reads endpoints/deployment names from environment variables and ships a `.env.example`. `.env` is gitignored. Endpoints come from the Foundry portal (project Overview -> Endpoint); model variables hold the **deployment name**, not the model family name.
- **Each demo is self-contained.** Python lessons have their own `pyproject.toml` + `uv.lock` (managed with `uv`); Node demos have their own `package.json`. There is no root-level build, lockfile, or dependency manifest. Install and run from inside the specific lesson/app folder.

## Commands

Python lesson demos use **`uv`** (each lesson has a `pyproject.toml` + `uv.lock`, no `requirements.txt`). Run from the lesson folder, e.g. `lessons/03-manage-monitor-secure-ai/`:

```bash
uv sync                              # build the per-lesson venv from pyproject.toml/uv.lock
az login                             # keyless auth (AzureCliCredential)
cp .env.example .env                 # then fill in Foundry values
uv run python m03_ops_demo.py            # run the instructor demo
uv run python m03_ops_demo.py --dry-run  # list what it would read; make no Azure calls
uv run python m03_ops_demo.py --only cost  # run a single signal (where the script supports --only)
uvx juv run m03_ops_tour.ipynb           # launch the student notebook (uv builds env + kernel)
```

Need the Azure environment itself? `infra/ai103-lesson-env.bicep` rebuilds a whole lesson env (account + project + model + optional App Insights) in one command, and its outputs map 1:1 onto the lesson `.env`. **Read `infra/README.md` before deploying** -- it carries the gotchas, notably that deleting a Foundry account leaves it soft-deleted and you must **purge** it to release the name and quota.

Node demo apps (run from the app folder, e.g. `lesson-demo-apps/woodgrove-bank/`):

```bash
npm install
node <demo>.js                    # e.g. document-analysis-app.js, image-analysis-app.js
```

There is no repo-wide lint or unit-test runner. Lint and test per app where a script exists in that app's `package.json`. Two repo-root health checks do exist, and both are read-only and free:

```powershell
pwsh -File verify-demos.ps1      # uv sync + --dry-run every Python lesson; catches import and config breakage
pwsh -File verify-runbooks.ps1   # every file path and CLI flag a runbook cites must actually resolve
```

`verify-runbooks.ps1` exists because runbook-to-code drift kept shipping silently: L07 cited a `demo\` folder and three scripts that never existed, L11 claimed its own lesson had no venv, and L10 pointed at `@tool` on a line holding `load_dotenv()`. Run it before recording. To validate a Python demo before recording: `uv run` it live, then execute any paired notebook headless and confirm every cell is green **twice** (the idempotency check).

## Audience and tone

Learner-facing. The README brand is "delight": friendly, neurodivergent-friendly, clear, light on emoji. Match that in any learner-facing README or demo output. Keep teaching value high; these snippets are recited in a paid video course.
