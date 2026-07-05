# Fixes Yet To Make

This file documents all outstanding improvements, fixes, and enhancements for the AI-103 repo. It includes both incoming suggestions and action items discussed in this project.

---

## 🛠️ Governance & Documentation

- [ ] Add `CODE_OF_CONDUCT.md` at the repo root (README links expect it)
- [ ] Add `CONTRIBUTING.md` at the repo root (README links expect it)
- [ ] Ensure all referenced files in README.md exist and are up to date
- [ ] Fix broken or outdated documentation links (e.g., image paths in `model_README.md`)
- [ ] Ensure all README files end with a trailing newline and are cleanly formatted

## 🔑 Environment & Configuration

- [x] Add a global `.env.sample` at the repo root (done)
- [ ] Add `.env.sample` files to lesson folders that require them
- [ ] Ensure all setup instructions referencing `.env.sample` are accurate

## 🧩 Demo Coverage (18-module AI-103 domain)

The repo is now aligned to the **frozen 18-module objective domain**. Demo status per module:

- **Real, working demo** (verified green):
  - [x] **01 - Choose the appropriate Foundry services for generative AI and agents**: `m01_agent_demo.py` (all-four-LO grounded agent) + `model_bakeoff.py` (LO1 model bake-off). This is the template all other modules should follow.
  - [x] **02 - Set up AI solutions in Foundry**: `m02_setup_demo.py` (one real model deployment exercising all four LOs: keyless infra, deployment SKU, version pin + content filter, idempotent CI/CD upsert). Follows the Module 01 pattern.
  - [x] **03 - Manage, monitor, and secure AI systems** (manage/monitor emphasis): `m03_ops_demo.py` (read-only ops signals: quota + cost + observability + index recall@k) + `m03_generate_signal.py` (telemetry generator) + `m03_ops_tour.ipynb` (student notebook) + `seed_index.py` (one-time index setup). Aligned to the deck's three demo clips; verified green twice. Runbook `Warner.AI-103.Lesson-03-demo-runbook.md` lives **in the lesson folder** (all lesson assets moved into the repo, 2026-07-04).
  - [x] **04 - Manage, monitor, and secure AI systems** (secure emphasis): **portal + IaC demo, no script by design** (zero-trust identity, private networking, RBAC). Driven by `Warner.AI-103.Lesson-04-demo-runbook.md`, reads the Bicep in `infra/`. Aligned to its three demo clips; the referenced Bicep properties and `az` command are verified present.

- **Real demo, BLOCKED on infra** (1 module):
  - [~] **05 - Implement responsible AI across generative AI and agentic systems**: `m05_evals_demo.py` (Azure AI Evaluation SDK: groundedness/relevance, keyless) + full 4-segment runbook covering all four demo clips (content filter, evaluators, audit trace, agent governance). **Code is correct but cannot run green yet**, blocked on Azure infra:
    - The eval SDK's built-in evaluators send `max_tokens`, which **gpt-5-mini rejects** (wants `max_completion_tokens`). Needs a **non-gpt-5 judge** (gpt-4.1-mini / gpt-4o-mini) deployed GlobalStandard -- but those have **0 GlobalStandard quota** in eastus2 (only Batch), so a **quota request** is required.
    - **`proj-lesson-05` does not exist** yet (only proj-lesson-01/02/03). The project-scoped safety evaluator needs it.
    - Fixed in code meanwhile: the `type: azure_openai` config discriminator, keyless via the evaluator `credential=` kwarg (the SDK validator crashes on a `credential` dict key), and `load_dotenv(override=True)` so the lesson `.env` wins over ambient `AZURE_OPENAI_*` vars.

- **Node skeleton only** (carried over, needs a real demo) (5 modules):
  - [ ] **07 - Optimize and operationalize generative AI systems**: `node-demo/generate.js` (Azure OpenAI call). Scaffold -> build LO1 prompt/parameter tuning demo.
  - [ ] **10 - Build agents by using Foundry**: `node-demo/index.js` (Bot Framework echo bot). Scaffold -> rebuild as a Foundry agent demo.
  - [ ] **13 - Design and implement multimodal understanding workflows**: `node-demo/app.js` (Custom Vision classify). Scaffold -> LO8 object/region identification.
  - [ ] **15 - Apply language model text analysis**: `node-demo/translate.js` (Azure Translator). Scaffold -> maps to LO3 (text translation).
  - [ ] **16 - Implement speech solutions**: `speech-to-text-demo.js` (Speech SDK). Scaffold -> maps to LO1 (speech to text).

- **No demo yet** (README scaffold only) (8 modules):
  - [ ] **06 - Build generative applications by using Foundry**
  - [ ] **08 - Build generative applications by using Foundry**
  - [ ] **09 - Build generative applications by using Foundry**
  - [ ] **11 - Build agents by using Foundry**
  - [ ] **12 - Design and implement image- and video-generation solutions**
  - [ ] **14 - Implement responsible AI for multimodal content**
  - [ ] **17 - Build retrieval and grounding pipelines**
  - [ ] **18 - Extract content from documents**

- [ ] Promote each Node skeleton into a real, runnable demo (or replace with a Python demo matching the Module 01 pattern: keyless Foundry SDK, `.env.example`, runnable from the module folder).
- [ ] Expand module READMEs with detailed run steps and sample code as demos land.
- [ ] Map each imported resource/demo to its corresponding module in the scaffold.

## 🔄 Code Quality & Security

- [x] Remove embedded `.git` directories from imported resources (done)
- [x] Add `.gitattributes` for cross-platform line ending consistency (done)
- [ ] Parameterize all hard-coded service endpoints (e.g., in `analyze_text.py`) to use environment variables
- [ ] Normalize line endings across the repo (optional, after .gitattributes)

## 🚦 CI/CD & Best Practices

- [ ] Add GitHub Actions workflows for:
  - [ ] Linting (e.g., ESLint, flake8)
  - [ ] Testing (unit/integration)
  - [ ] Security scanning (e.g., CodeQL, secret scanning)
- [ ] Document how to run and interpret CI results in the repo

## 🗂️ Resource Centralization & Hygiene

- [ ] Document how each imported resource/demo ties into the lessons
- [ ] Trim or archive unused files/scripts in `imported-resources/`
- [ ] Ensure all images and assets are referenced with correct paths

## 🧠 Learner Experience

- [ ] Ensure all lesson folders have clear, actionable instructions
- [ ] Add teaching notes, tips, and troubleshooting sections where helpful
- [ ] Maintain a neurodivergent-friendly, accessible, and delightful repo structure

---

> This checklist is a living document. Update as you go to keep the repo polished, professional, and learner-friendly!