# Lesson 1 -- Choose Foundry services, models, and integration approach

Welcome! These are the hands-on demos for **Module 1** of the Microsoft Press video
course *Exam AI-103: Developing AI Apps and Agents on Azure*.

Module 1 is about **four decisions**: which model, which Foundry service, which
retrieval method, and which memory/tool/knowledge integration. The main demo here
makes **all four** concrete in a single small agent -- the way AI-103 actually ships.

## The main demo: one grounded agent, all four decisions

`m01_agent_demo.py` builds **one** small Contoso support agent with the
**Microsoft Agent Framework** on Microsoft Foundry (the current, GA path -- the
classic `create_agent`/thread/run API is deprecated and retires in 2027). Every
Lesson-1 decision shows up as one ingredient, exactly like the slide that says
"an agent is memory + tools + knowledge, with guardrails":

| Decision (LO) | How the demo makes it | In the code |
|---|---|---|
| **LO1 -- choose a model** | the agent reasons with your `FOUNDRY_MODEL` (a capable LLM) | `FOUNDRY_MODEL` |
| **LO2 -- choose a service** | the **Agents service** via `FoundryChatClient`, not stateless chat | `FoundryChatClient(...)` |
| **LO3 -- choose retrieval** | grounds answers on a knowledge file (managed vector store) | `get_file_search_tool(...)` |
| **LO4 -- memory + tools + knowledge** | a **thread** (memory), a custom **@tool**, the knowledge source, and an **approval gate** (guardrail) | `get_new_thread()`, `@tool`, `tools=[...]` |

It runs a two-turn conversation: turn 1 forces the agent to **read the policy
(retrieval)** and **open a refund ticket (tool)**; turn 2 omits the customer's name
so the agent must **remember it from the thread (memory)**.

## Bonus: `model_bakeoff.py` -- an LO1 spotlight

Want to go deep on just the model choice? `model_bakeoff.py` sends the same prompt to
a **flagship LLM** (`gpt-5.1`) and a **small model** (`phi-4`) and prints a
side-by-side scoreboard of latency, tokens, and answers -- the "task fit beats brand
name" lesson, proven with a stopwatch.

## What you will need

- A **Microsoft Foundry** project with a **deployed chat model** (e.g. `gpt-5.1`).
- A **basic agent setup** in that project (managed storage + vector store for file search).
- The **Azure CLI**, signed in with `az login` (auth is keyless -- no API keys).
- **uv** ([install guide](https://docs.astral.sh/uv/getting-started/installation/)). You do **not** need to install Python yourself.

## Setup

This project uses **uv**. Why uv here: the **Microsoft Agent Framework** GA wheels publish for **Python 3.10 - 3.13 only**, and `uv` reads the pinned **`.python-version` (3.13)** to build the virtual environment on the right interpreter automatically, so the wheels install even when your system default is Python 3.14.

PowerShell 7:

```powershell
cd lessons/01-choose-foundry-services
uv sync                      # creates the .venv with Python 3.13 and installs deps
az login                     # keyless auth
Copy-Item .env.example .env  # then fill in your Foundry values
```

bash:

```bash
cd lessons/01-choose-foundry-services
uv sync                  # creates the .venv with Python 3.13 and installs deps
az login                 # keyless auth
cp .env.example .env     # then fill in your Foundry values
```

| Variable | Used by | What it is |
|---|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | both | Foundry portal -> project -> Overview -> Endpoint |
| `FOUNDRY_MODEL` | agent demo | deployment **name** of your chat model (e.g. `gpt-5.1`) |
| `FLAGSHIP_DEPLOYMENT` / `SLM_DEPLOYMENT` | bake-off | the two deployment names to compare |

## Run it

```bash
uv run python m01_agent_demo.py     # the main demo -- all four LOs
uv run python model_bakeoff.py      # the LO1 spotlight
```

## What you will see (agent demo, illustrative)

```
LO1  model       : gpt-5.1  (capable LLM for agent reasoning)
LO2  service     : Microsoft Foundry Agents (Agent Framework), keyless auth
LO3  retrieval   : file-search grounding over a managed vector store
LO4  integration : thread (memory) + custom tool + knowledge source + approval gate
========================================================================
User: I'm Dana Lee, a Premium customer. I bought 22 days ago for $80 ...
Agent: You're within the 30-day Premium window, so you qualify for a full refund.
       I've opened ticket RF-3175 for $80.00.
User: Remind me which plan I'm on and what refund you just queued for me.
Agent: You're on the Premium plan, and I queued an $80.00 full refund (ticket RF-3175).
```

## How this maps to the exam

The agent demo touches every Lesson-1 objective group at once: model selection,
service selection, retrieval/indexing, and agent memory/tool/knowledge integration.
When an exam stem describes "an agent that answers from internal docs and takes an
action," you should now see the building blocks behind it.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
