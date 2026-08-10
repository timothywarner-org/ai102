# Build agents by using Foundry

Part of **Objective domain 2: Implement generative AI and agentic solutions** (30-35%), Lesson 10 (L10).

This objective group spans two lessons, L10 and L11. The full objective list is shown verbatim in both modules so neither drops a learning objective.

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Define agent roles, goals, conversation-tracking approach, and tool schemas
2. Build agents that integrate retrieval, function-calling, and conversation memory
3. Integrate agent tools, including APIs, knowledge stores, search, content understanding, and custom functions
4. Implement orchestrated multi-agent solutions
5. Build autonomous or semiautonomous workflows with safeguards and approval flow controls
6. Integrate monitoring into deployed agents, evaluate agent behavior, and perform error analysis

## Demos

Run demos directly from this folder. Python demos use **uv**, and authentication is **keyless** through `az login`.

```bash
uv sync                  # build the per-lesson venv
az login                 # keyless auth (AzureCliCredential)
cp .env.example .env     # then fill in your Foundry values
```

### `m10_tools_repl.py` -- the headline demo

An interactive console agent that makes **tool schemas** (objective 1) and **function calling plus conversation memory** (objective 2) visible while you type.

```bash
uv run python m10_tools_repl.py
uv run python m10_tools_repl.py --dry-run   # print tool schemas, make no Azure calls
```

It loads three deliberately contrasting tools so that tool **selection** is observable. A single tool would prove nothing, because there would be nothing to choose between.

| Tool | What its schema teaches |
| --- | --- |
| `add` | Two required numbers, no enum. The baseline. |
| `convert_money` | An **enum** on the currency codes, so a class of runtime error is prevented in the schema. |
| `get_ticket_status` | An **optional** parameter with a default, contrasted against `required[]`. |

Every turn prints the request/execute/continue boundary, the **stop code**, and token usage:

```text
you> what is 17.5 plus 4.25
  [call]  model requested add(a=17.5, b=4.25)
  [exec]  our code returned 21.75
  [turn]  text_reasoning -> function_call -> function_result -> text
  [stop]  finish_reason=stop  status=completed  incomplete=None
  [usage] in=905 out=138 total=1043 reasoning=64
agent> 17.5 + 4.25 = 21.75.
```

The `[call]` and `[exec]` lines print **live**, from a `FunctionMiddleware` that sits on the seam: everything before its `await call_next()` happens while the model has only *requested* the call, and everything after it happens once your code has returned. That is the request/execute/continue boundary shown as it happens rather than reconstructed afterwards.

Two details worth saying out loud on camera:

- **`reasoning` tokens are billed as output** and count against your output cap even though they never appear in the answer.
- **The turn shape is not fixed.** `function_call -> function_result` is the reliable spine; the `text_reasoning` items appear wherever the model stopped to think, so some turns show one and some show two. `function_calling.py` and this REPL genuinely differ run to run.

Commands inside the REPL: `:tools`, `:schema [name]`, `:verbose`, `:reset`, `:help`, `:quit`.

Four prompts worth demoing in order, because the fourth is the one learners underestimate:

1. `what is 17.5 plus 4.25` -- `add` fires
2. `convert 50 USD to EUR` -- `convert_money` fires
3. `what is the status of CS-1042` -- `get_ticket_status` fires
4. `who wrote the novel Dune` -- **no** tool fires; no schema matches, so the model just answers

Then show memory: `what is 8 plus 9`, `now add 100 to that`, `what did I ask you first`, and finally `:reset` to prove the session was doing real work.

This demo creates **no Azure resources**, so it is safe to re-run live as many times as a take requires.

### `function_calling.py` -- the slow walkthrough

The same loop as a straight-line script: one question, five numbered beats, no typing. Use it when you want to narrate the boundary at half speed before turning the REPL loose.

```bash
uv run python function_calling.py
uv run python function_calling.py --dry-run   # print the tool schema, make no Azure calls
```

Both Python demos in this lesson are built on the **Microsoft Agent Framework** (`agent-framework-foundry`), not the raw `openai` package. Two reasons, and both are exam-relevant:

1. **`FoundryChatClient` is the supported client for a Foundry *project* endpoint** (`https://<account>.services.ai.azure.com/api/projects/<project>`). `AzureOpenAIChatClient` targets `*.openai.azure.com` and does not work against a project URL.
2. **The tool schema is generated from the Python signature** by the `@tool` decorator, so the code and the schema cannot drift apart. Hand-written JSON schemas that no longer match their function are the single most common bug in rolled-your-own function calling.

`to_json_schema_spec()` prints the real spec read off the live tool object, so what you show on screen is what actually goes on the wire.

### Supporting scripts

| Script | Purpose |
| --- | --- |
| `ask.py` | Send one question to a named Foundry prompt agent: `python ask.py <agent-name> "question"`. |
| `provision_knowledge.py` | One-time setup: seeds the `knowledge/` corpus into a vector store for file-search grounding. |

### Node.js skeleton

`node-demo/` holds a Bot Framework echo bot carried over during the AI-103 restructure. It is a scaffold, not a finished demo.

```bash
cd node-demo
cp .env.sample .env   # fill in your Foundry project values
npm install
node index.js
```

## Parked demo ideas

- **Agent endpoint URIs (parked from Lesson 3):** briefly create an agent and showcase its endpoint URIs -- the stable project/agent endpoint, plus latest-vs-pinned version routing. It came up in the L3 demo but derailed that lesson's monitoring throughline, so it lives here with the agent lessons (L10/L11) where it's on-topic.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
