# Build generative applications by using Foundry

Part of **Objective domain 2: Implement generative AI and agentic solutions** (30-35%), Lesson 6 (L6).

This objective group spans three lessons, L6, L8, and L9. The full objective list is shown verbatim in Modules 06, 08, and 09 so no module drops a learning objective.

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Deploy and consume LLMs, small models, code models, and multimodal models
2. Implement retrieval-augmented generation (RAG) in an application
3. Design workflows, tool-augmented flows, and multistep reasoning pipelines
4. Evaluate models and apps, including detecting fabrications, relevance, quality, and safety
5. Integrate generative workflows into applications by using Foundry SDKs and connectors
6. Configure an application to connect to a Foundry project

## The demo: build a generative app on the Foundry SDK

This is a **build** lesson, so the SDK is the surface (not the portal). `m06_build_app_demo.py`
walks the three objectives this module owns, in the order you'd write them, then a bonus agent
capstone. It's keyless (`az login`) and idempotent (read-mostly; the agent beat creates one
version and deletes it). Full talk track: `Warner.AI-103.Lesson-06-demo-runbook.md`.

| Beat (LO) | What the code does | Key API |
|---|---|---|
| **LO6 -- connect** | one `AIProjectClient` from the **project** endpoint, keyless; health-check by listing deployments | `AIProjectClient(endpoint, credential)` |
| **LO1 -- consume** | call the model + a follow-up that remembers turn 1 | `project.get_openai_client()` -> `responses.create(...)` |
| **LO5 -- connectors** | list the project's connections (define-once, reuse) | `project.connections.list()` |
| **capstone -- agent** | build a Foundry agent, run one turn, delete it | `project.agents.create_version(...)` + `PromptAgentDefinition` |

The deploy itself is infrastructure-as-code: see `infra/ai103-core.mvp.bicep` (SKU, version pin,
`raiPolicyName`) and `infra/modules/observability.bicep` (the `connections` resource).

## Setup and run

```bash
cd lessons/06-build-generative-apps-foundry
uv sync
az login
cp .env.example .env        # fill in FOUNDRY_PROJECT_ENDPOINT (proj-lesson-06) + MODEL_DEPLOYMENT_NAME

uv run python m06_build_app_demo.py            # connect + consume + connections
uv run python m06_build_app_demo.py --agent    # also build+run the agent capstone
uv run python m06_build_app_demo.py --dry-run  # print the plan; call nothing
```

The `# %%` cell markers let you run one beat at a time in the VS Code Interactive Window while you narrate.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
