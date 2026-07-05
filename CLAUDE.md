# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

The public **learner companion repo** for Tim Warner's Microsoft Press video course **Exam AI-103: Developing AI Apps and Agents on Azure** (the Microsoft Foundry + agents successor to AI-102). It ships hands-on demo code, per-lesson READMEs, and deliberately vulnerable sample apps used to teach security scanning. It is **not** a single application: it is a polyglot collection of independent, self-contained demos.

> "AI-102" in Tim's prompts almost always means **AI-103**. He habitually mis-types it. Read it as AI-103 and proceed silently unless he clearly means the retiring predecessor exam.

## Current state (2026-07)

- **Recorded/shipped:** Lessons 01 and 02. Lesson 03 deck, demo, and runbook are done and demo-verified (quota + cost, observability, index health + recall@k). Lessons 04 and 05 have in-repo demo runbooks; L05 has a working evals demo (`m05_evals_demo.py`).
- **Demo pattern per recorded lesson:** (a) a read-only instructor demo script (`mNN_*.py`) run live from the Edge portal + VS Code, and (b) a separate student-facing runnable notebook (`mNN_*_tour.ipynb`, keyless + idempotent). The recording is driven by an **old-school Markdown SAY/DO/PAUSE runbook** -- **not** a Jupyter runbook. (`Lesson-02-runbook.ipynb` reflects the abandoned notebook-runbook approach.)
- **Lesson assets live in the repo, all 18 lessons (rule set 2026-07-04).** Every lesson-specific artifact -- demo scripts, student notebooks, the `Warner.AI-103.Lesson-NN-demo-runbook.md`, per-lesson `.env.example` and config -- lives in this repo under `lessons/NN-*/`, **not** in the private Pearson GPD folder. The GPD folder keeps only authoring source of truth: the `.pptx` decks, `AI-103-OD-baseline.md`, the authoring `CLAUDE.md`, script/outline `.docx` files, deck `.bak` backups, and personal timing tooling (`speak.py`). If a lesson demo asset ever appears at the GPD root, move it into its `lessons/NN-*/` folder.
- **Demo surface rule -- do NOT shoehorn the SDK.** Match the demo surface to how the task is really done: **portal + IaC (Bicep / `az` CLI) for setup and security lessons** (deployments, identity, networking, RBAC); the **Python SDK only when code is the natural, valuable surface** -- building an agent (L1), or reading signals you'd genuinely automate (L3 monitoring). Never write an SDK script just to "show code" for a portal/IaC task -- L2's create-then-delete deployment script was exactly that mistake. And when Bicep or `az` is on screen, **explain it** (walk the resource and its properties), don't just flash it.
- **Deployed Azure MVP env:** Foundry account `aif-ai103-mvp-quc6kxy2j2v2q` (eastus2), model deployment **gpt-5-mini (2025-08-07)** -- chosen because gpt-5-nano / gpt-5.1 have **0 granted quota** on this subscription. Projects `proj-lesson-01/02/03`. L3 add-on: App Insights + free-tier Azure AI Search (westus3). IaC: `infra/ai103-core.mvp.bicep`, `infra/ai103-l3-observability.main.bicep`, `infra/modules/{observability,search}.bicep`. The full `infra/ai103-core.bicep` (4 models, 18 projects) is ready for when quota lands.
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

- `lessons/NN-topic/` -- per-lesson demo code, a learner README, and (for recorded lessons) a `Warner.AI-103.Lesson-NN-demo-runbook.md`. **Lessons 01-03 and 05 have real, runnable demos:** 01 is the flagship (`m01_agent_demo.py` + `model_bakeoff.py`), 02 is `m02_setup_demo.py`, 03 is `m03_ops_demo.py` (read-only ops signals) plus `m03_generate_signal.py` (a telemetry generator that makes real model calls) and the `m03_ops_tour.ipynb` student notebook, 05 is `m05_evals_demo.py`. Several instructor demos ship a paired `mNN_*_tour.ipynb` student notebook and a `seed_index.py`-style one-time setup script where the demo reads a persistent resource. Most later lesson folders are still scaffolds. `fixes-to-make.md` (repo root) tracks which lessons still need demos.
- `lesson-demo-apps/` -- larger standalone demo applications, each with its own toolchain and README:
  - `woodgrove-bank/` -- the most complete: Node demos for document intelligence, image analysis, AI Search + Document Intelligence, and a groundedness API.
  - `tim-chat-front-end/` -- full app with `frontend/`, `backend/`, and `infra/` (azd-deployable via `azure.yaml`).
  - `globomantics-vulnerable-app-1/` and `globomantics-secure-scan-1/` -- **intentionally vulnerable** Express apps + a CodeQL pack, for teaching SAST. Do not "fix" the vulnerabilities; they are the lesson.
  - `azure-appinsights-node-sample-app/` -- Node app with Dockerfile, k6 `loadtest.js`, and a KQL cheat sheet for the monitoring lesson.
  - `rock-band-name-checker/` -- Python content-safety demo.

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

Node demo apps (run from the app folder, e.g. `lesson-demo-apps/woodgrove-bank/`):

```bash
npm install
node <demo>.js                    # e.g. document-analysis-app.js, image-analysis-app.js
```

There is no repo-wide lint or test runner yet (CI/CD scaffolding is on the `fixes-to-make.md` backlog). Lint and test per app where a script exists in that app's `package.json`. To validate a Python demo before recording: `uv run` it live, then execute the paired notebook headless and confirm every cell is green **twice** (the idempotency check).

## Audience and tone

Learner-facing. The README brand is "delight": friendly, neurodivergent-friendly, clear, light on emoji. Match that in any learner-facing README or demo output. Keep teaching value high; these snippets are recited in a paid video course.
