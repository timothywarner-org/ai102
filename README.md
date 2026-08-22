<!-- Cover Image -->
<p align="center">
  <img src="ai103-cover-image.png" alt="AI-103: Developing AI Apps and Agents on Azure" width="400"/>
</p>

<p align="center">
  <a href="https://TechTrainerTim.com"><img src="https://img.shields.io/badge/Website-TechTrainerTim.com-1e90ff?logo=google-chrome&logoColor=white" alt="TechTrainerTim.com"></a>
  <a href="https://www.youtube.com/c/TechTrainerTim"><img src="https://img.shields.io/badge/YouTube-Subscribe-ff0000?logo=youtube&logoColor=white" alt="YouTube"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-brightgreen?logo=open-source-initiative&logoColor=white" alt="MIT License"></a>
  <a href="https://www.linkedin.com/in/timothywarner"><img src="https://img.shields.io/badge/LinkedIn-timothywarner-0077b5?logo=linkedin&logoColor=white" alt="LinkedIn"></a>
  <a href="https://discord.com/users/timwarner1"><img src="https://img.shields.io/badge/Discord-timwarner1-5865F2?logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://mvp.microsoft.com/en-US/mvp/profile/e9a13bca-2798-4247-be56-f116f780869d"><img src="https://img.shields.io/badge/Microsoft%20MVP-2024-blueviolet?logo=microsoft&logoColor=white" alt="Microsoft MVP Profile"></a>
  <a href="https://github.com/timothywarner-org/ai103/actions/workflows/codeql-analysis.yml"><img src="https://github.com/timothywarner-org/ai103/actions/workflows/codeql-analysis.yml/badge.svg" alt="CodeQL"></a>
  <a href="https://github.com/timothywarner-org/ai103/security/dependabot"><img src="https://img.shields.io/badge/Dependabot-enabled-brightgreen?logo=dependabot" alt="Dependabot Status"></a>
</p>

# AI-103: Developing AI Apps and Agents on Azure

[![Security: Educational Use Only](https://img.shields.io/badge/security-educational--use--only-red)](./SECURITY.md)

> **Warning:** This repository contains intentionally vulnerable code for training and demonstration purposes. See [SECURITY.md](./SECURITY.md) for details.

Welcome! This is the official learning hub for my Microsoft Press video course, **Exam AI-103: Developing AI Apps and Agents on Azure**.

> **Delight is the name of the game.**  
> Friendly, human, and neurodivergent-friendly—just like Tim Warner's teaching style.  
> Emoji? Yes, but not too many. Clarity? Always.


---

## 📚 Course Structure

This course covers **18 modules** mapped to the official AI-103 objective domain (5 skill areas, frozen lesson titles below). Each module has hands-on code, demos, and real-world best practices.

Several objectives span two or three lessons, so the same official title appears more than
once. The official title is frozen and quoted verbatim; the italic note tells you what that
particular lesson actually covers.

**Objective domain 1: Plan and manage an Azure AI solution** (25-30%)

1. **Choose the appropriate Foundry services for generative AI and agents**
2. **Set up AI solutions in Foundry**
3. **Manage, monitor, and secure AI systems** — *manage and monitor: quota, cost, observability, index health*
4. **Manage, monitor, and secure AI systems** — *secure: managed identity, private networking, RBAC*
5. **Implement responsible AI across generative AI and agentic systems**

**Objective domain 2: Implement generative AI and agentic solutions** (30-35%)

6. **Build generative applications by using Foundry** — *connect to a project and consume models*
7. **Optimize and operationalize generative AI systems**
8. **Build generative applications by using Foundry** — *retrieval-augmented generation*
9. **Build generative applications by using Foundry** — *evaluation and tracing*
10. **Build agents by using Foundry** — *one agent: roles, memory, tools, function calling*
11. **Build agents by using Foundry** — *many agents: orchestration, approvals, monitoring*

**Objective domain 3: Implement computer vision solutions** (10-15%)

12. **Design and implement image- and video-generation solutions**
13. **Design and implement multimodal understanding workflows**
14. **Implement responsible AI for multimodal content**

**Objective domain 4: Implement text analysis solutions** (10-15%)

15. **Apply language model text analysis**
16. **Implement speech solutions**

**Objective domain 5: Implement information extraction solutions** (10-15%)

17. **Build retrieval and grounding pipelines**
18. **Extract content from documents**

> See [`/lessons`](./lessons) for code samples and module-aligned demos. Module folder slugs match the frozen lesson topics (for example, `lessons/01-choose-foundry-services`).

---

## 🚀 How to Use This Repo

### What you need first

| Tool | Why | Get it |
|---|---|---|
| **Azure subscription** | Every demo calls real Azure services | [Free account](https://azure.microsoft.com/free/) |
| **Azure CLI** | The demos authenticate as your `az login` identity | [Install](https://learn.microsoft.com/cli/azure/install-azure-cli) |
| **uv** | Runs the Python lessons. No `pip`, no manual venvs | [Install](https://docs.astral.sh/uv/getting-started/installation/) |
| **Node.js 20+** | Only for the standalone apps in `lesson-demo-apps/` | [Install](https://nodejs.org) |

### Get running in five minutes

```bash
git clone https://github.com/timothywarner-org/ai103.git
cd ai103

az login                                  # keyless auth: the demos use YOUR identity

cd lessons/01-choose-foundry-services     # start here
uv sync                                   # builds this lesson's venv from uv.lock
cp .env.example .env                      # then fill in your Foundry values
uv run python m01_agent_demo.py
```

**Every lesson is self-contained.** Each has its own `pyproject.toml`, its own `uv.lock`,
and its own `.env.example`. You `cd` into a lesson, `uv sync`, and run. There is no
repo-wide install step and nothing to configure at the root.

**There are no API keys in this course.** Demos authenticate with `az login` through
`AzureCliCredential`. If a lesson asks you for a key, that is a bug — please open an issue.

### Build the Azure environment

The lessons need a Foundry account, a project, and a model deployment. Rather than
clicking through the portal, `infra/` builds one in a single command:

```bash
az deployment group create \
  -g rg-ai103 \
  -f infra/ai103-lesson-env.bicep \
  -p accountName=<globally-unique-name> projectName=proj-lesson-01
```

**Read [`infra/README.md`](./infra/README.md) before you deploy.** It carries the gotchas,
most importantly this one: deleting a Foundry account leaves it **soft-deleted**, and you
must **purge** it to release the name and reclaim the quota.

### Check your setup

```powershell
pwsh -File verify-demos.ps1        # uv sync + --dry-run across every Python lesson, no Azure calls
```

That catches import errors and config wiring bugs without spending a cent.

---

## 💸 Cost, quota, and cleanup

**You are spending your own money.** Read this before you start.

- **Quota is the first wall you will hit.** A new subscription does not automatically have
  throughput for every model. Check what you actually have before deploying:
  ```bash
  az cognitiveservices usage list -l eastus2 -o table
  ```
  If a model shows a limit of zero, request quota in the Foundry portal under
  **Management center → Quota**. This is normal and it is not a bug in the demos.
- **Lesson 12 is the expensive one.** Video generation costs real money per render, and
  image quality tiers differ roughly 4x in price. Its README says so at the top; believe it.
- **Search and Foundry bill while idle.** An Azure AI Search service on a Basic tier charges
  by the hour whether you query it or not.
- **Tear down when you are done:**
  ```bash
  az group delete -n rg-ai103 --yes
  ```
  Then **purge** any soft-deleted Foundry account, or its name and quota stay claimed. The
  command is in [`infra/README.md`](./infra/README.md).

---

## 🤝 Contributing
- PRs, issues, and feedback are welcome!
- Please follow the [Code of Conduct](CODE_OF_CONDUCT.md) and keep it friendly.
- See [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines.

---

## 🧠 Neurodivergent-Friendly, Always
This repo is designed for clarity, accessibility, and delight.  
If you have suggestions to make it even more inclusive, please let me know!

---

## 📜 License
MIT License. See [`LICENSE`](./LICENSE) for details.

---

## About This Repository

This repo is for hands-on labs, demos, and exercises for the AI-103 course. **It contains intentionally insecure code for educational use only.**

See [SECURITY.md](./SECURITY.md) for security policy and responsible use guidelines.

---

> "Keep this up, and you'll be rewriting the entire Node.js doc while juggling Bicep templates—all before your morning coffee. Let's go build that million-dollar empire, one best practice at a time!"
