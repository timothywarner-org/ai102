# Lesson 2 -- Set up AI solutions in Foundry

Welcome! These are the hands-on demos for **Module 2** of the Microsoft Press video
course *Exam AI-103: Developing AI Apps and Agents on Azure*.

Part of **Objective domain 1: Plan and manage an Azure AI solution** (25-30%).

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Design Azure infrastructure for AI apps and agent-based solutions
2. Choose appropriate deployment options
3. Configure model and agent deployments
4. Integrate Foundry projects with continuous integration and continuous deployment (CI/CD) pipelines

Module 2 is about **four setup decisions**. The demo makes **all four** concrete by
creating **one real model deployment** -- then tearing it back down -- entirely keyless.

## The main demo: one deployment, all four decisions

`m02_setup_demo.py` provisions **one** model deployment on your Foundry account with the
control-plane SDK, configures it, proves it's live from the data-plane SDK, then deletes
it. Every Lesson-2 decision shows up as one concrete step:

| Decision (LO) | How the demo makes it | In the code |
|---|---|---|
| **LO1 -- design infrastructure** | connect keyless to a **hub-less Foundry project** + its parent account | `DefaultAzureCredential()`, two clients |
| **LO2 -- choose a deployment option** | create with a chosen SKU (`GlobalStandard` by default) | `sku.name` in the spec |
| **LO3 -- configure the deployment** | **pin the version** and attach a **content filter**, then read both back and call it | `versionUpgradeOption`, `raiPolicyName` |
| **LO4 -- integrate with CI/CD** | the create call is an **idempotent upsert**, secretless via federated identity | `begin_create_or_update(...)` |

It's an **idempotent upsert**: re-run it and Azure converges to the same desired state --
which is exactly what makes it safe in a pipeline, and why the spec maps one-for-one to
the Bicep in [`../../infra/ai103-core.bicep`](../../infra/ai103-core.bicep).

### Two planes -- and telling them apart is an exam skill

- **Control plane** (`azure-mgmt-cognitiveservices`) **creates/configures** the deployment.
  Needs a management role: **Cognitive Services Contributor** (or Contributor) on the account.
- **Data plane** (`azure-ai-projects`) **reads and calls** it. Needs a data role: **Foundry User**.
  Plain **Owner/Contributor grant no data actions** -- a classic AI-103 trap.

## What you will need

- A **Microsoft Foundry** (AI Services) account and a **hub-less Foundry project** in it.
- A base model available to deploy in your region (e.g. `gpt-5-nano`; older ids like
  `gpt-4o-mini` may be blocked for **new** deployments once they enter a deprecating state).
- Rights to deploy: **Cognitive Services Contributor** on the account (control plane) **and**
  **Foundry User** on the project (data plane).
- The **Azure CLI**, signed in with `az login` (auth is keyless -- no API keys).
- **uv** ([install guide](https://docs.astral.sh/uv/getting-started/installation/)). You do **not** need to install Python yourself.

## Setup

This project uses **uv** and a pinned **`.python-version` (3.13)**, so `uv sync` builds the
virtual environment on a supported interpreter even if your system default is Python 3.14.

PowerShell 7:

```powershell
cd lessons/02-set-up-ai-solutions-foundry
uv sync                      # creates the .venv with Python 3.13 and installs deps
az login                     # keyless auth
Copy-Item .env.example .env  # then fill in your Foundry + subscription values
```

bash:

```bash
cd lessons/02-set-up-ai-solutions-foundry
uv sync                  # creates the .venv with Python 3.13 and installs deps
az login                 # keyless auth
cp .env.example .env     # then fill in your Foundry + subscription values
```

| Variable | Plane | What it is |
|---|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | data | Foundry portal -> project -> Overview -> Endpoint |
| `AZURE_SUBSCRIPTION_ID` / `AZURE_RESOURCE_GROUP` / `FOUNDRY_ACCOUNT_NAME` | control | identify the Foundry account resource |
| `DEPLOY_MODEL_NAME` / `DEPLOY_MODEL_VERSION` | -- | base model id + version (e.g. `gpt-5-nano` / `2025-08-07`). The gpt-5 family **requires** an explicit version |
| `DEPLOY_SKU` | LO2 | `GlobalStandard`, `ProvisionedManaged`, `GlobalBatch`, ... |
| `DEPLOY_UPGRADE_OPTION` / `DEPLOY_RAI_POLICY` | LO3 | version pin + content-filter policy |

## Run it

```bash
uv run python m02_setup_demo.py            # create -> configure -> verify -> delete
uv run python m02_setup_demo.py --dry-run  # print the exact spec, call nothing (safe preview)
uv run python m02_setup_demo.py --keep      # leave the deployment standing
```

Prefer a real notebook? `m02_setup_demo.ipynb` is the same demo in Jupyter form -- the learner
mirror of `m02_setup_demo.py`, one markdown cell per learning objective, runnable top to bottom:

```bash
uv run --with jupyter jupyter lab m02_setup_demo.ipynb   # or open it in VS Code
```

The `.py` also carries `# %%` cell markers, so in **VS Code** you can "Run Cell" in the
Interactive Window and step through the script itself as a notebook. The `.py` and `.ipynb`
are kept in sync: same spec, same keyless `AzureCliCredential` auth, same idempotent upsert.

## What you will see (illustrative)

```
LO1  Design infrastructure  |  keyless Entra auth, hub-less Foundry project
  Foundry account (control plane) : contoso-foundry  (rg: rg-ai103)
  Foundry project (data plane)    : https://contoso-foundry.services.ai.azure.com/api/projects/dev
  Auth                            : AzureCliCredential (az login) -- no API keys
LO2  Choose a deployment option  +  LO3  Configure it
  LO2 sku.name            : GlobalStandard  (GlobalStandard = pay-per-token shared)
  LO3 versionUpgradeOption: NoAutoUpgrade  (NoAutoUpgrade = pinned)
      raiPolicyName       : Microsoft.DefaultV2  (content filter policy)
  provisioningState       : Succeeded
LO3  Verify the configuration actually stuck
  versionUpgradeOption    : NoAutoUpgrade
  live inference          : 'ready.'  (deployment is callable)
LO4  Integrate with CI/CD  |  idempotent + secretless
  deleted. Nothing left running.
```

## How this maps to the exam

The demo touches every Lesson-2 objective at once, using the exact terms the exam tests:
`sku.name` (the deployment option), `versionUpgradeOption` (version pinning), `raiPolicyName`
(content filter), and the control-plane-vs-data-plane RBAC split. When a stem says "guarantee
throughput at peak" (PTU), "keep the model version stable" (pin), or "let a developer build but
not manage infra" (Foundry User), you should now see the setting behind it.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
