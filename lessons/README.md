# AI-103 Lesson Code

Lesson-aligned demo code for Tim Warner's Microsoft Press video course
*Exam AI-103: Developing AI Apps and Agents on Azure*. Each subfolder maps to one
module of the **frozen 18-module objective domain** (the folder slug matches the
lesson topic, e.g. `01-choose-foundry-services`).

---

## Lesson index

**Objective domain 1: Plan and manage an Azure AI solution** (25-30%)

- **01** [Choose the appropriate Foundry services for generative AI and agents](./01-choose-foundry-services)
- **02** [Set up AI solutions in Foundry](./02-set-up-ai-solutions-foundry)
- **03** [Manage, monitor, and secure AI systems](./03-manage-monitor-secure-ai) — *manage and monitor: quota, cost, observability, index health*
- **04** [Manage, monitor, and secure AI systems](./04-manage-monitor-secure-ai) — *secure: managed identity, private networking, RBAC*
- **05** [Implement responsible AI across generative AI and agentic systems](./05-responsible-ai-generative-agentic)

**Objective domain 2: Implement generative AI and agentic solutions** (30-35%)

- **06** [Build generative applications by using Foundry](./06-build-generative-apps-foundry) — *connect to a project and consume models*
- **07** [Optimize and operationalize generative AI systems](./07-optimize-operationalize-genai)
- **08** [Build generative applications by using Foundry](./08-build-generative-apps-foundry) — *retrieval-augmented generation*
- **09** [Build generative applications by using Foundry](./09-build-generative-apps-foundry) — *evaluation and tracing*
- **10** [Build agents by using Foundry](./10-build-agents-foundry) — *one agent: roles, memory, tools, function calling*
- **11** [Build agents by using Foundry](./11-build-agents-foundry) — *many agents: orchestration, approvals, monitoring*

**Objective domain 3: Implement computer vision solutions** (10-15%)

- **12** [Design and implement image- and video-generation solutions](./12-image-video-generation)
- **13** [Design and implement multimodal understanding workflows](./13-multimodal-understanding)
- **14** [Implement responsible AI for multimodal content](./14-responsible-ai-multimodal)

**Objective domain 4: Implement text analysis solutions** (10-15%)

- **15** [Apply language model text analysis](./15-language-model-text-analysis)
- **16** [Implement speech solutions](./16-speech-solutions)

**Objective domain 5: Implement information extraction solutions** (10-15%)

- **17** [Build retrieval and grounding pipelines](./17-retrieval-grounding-pipelines)
- **18** [Extract content from documents](./18-extract-content-documents)

---

Each lesson subfolder contains:

- **Demo scripts** named `mNN_*.py`, runnable with `uv run python <script>.py`
- A **`README.md`** with the verbatim learning objectives, setup, and what each demo shows
- **`.env.example`** listing every variable that lesson needs
- A **`Warner.AI-103.Lesson-NN-demo-runbook.md`**, the click-by-click talk track
- **`pyproject.toml`** + **`uv.lock`**, so the lesson builds its own environment

**All 18 lessons ship working demos.** Lesson 04 is deliberately Python-free: securing a
Foundry account is a portal and infrastructure-as-code job, so it runs from the Azure portal
and the Bicep in [`../infra`](../infra) rather than from an SDK script.

Most demo scripts accept `--dry-run`, which prints exactly what the script would do and makes
no Azure calls. That is the cheapest way to confirm your `.env` is wired correctly.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
