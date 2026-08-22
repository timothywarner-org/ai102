# AI-103 -- Lesson 10 Demo Runbook

**Build Agents with Foundry: Roles, Memory, Tools, and Function Calling**

Three beats, one per learning objective. About 19 to 21 minutes.
Surface: **Edge (Foundry portal)** plus **VS Code** for one beat.

---

## Environment

| Thing | Value |
|---|---|
| Resource group | `rg-ai103-mvp` (eastus2) |
| Foundry account | `YOUR-FOUNDRY-RESOURCE` |
| Project | `proj-agents` |
| Project endpoint | `https://YOUR-FOUNDRY-RESOURCE.services.ai.azure.com/api/projects/proj-agents` |
| Model | `gpt-5-mini` 2025-08-07, GlobalStandard, 50K TPM |
| Agent | `l10-support-agent:1` |
| Knowledge store | `file_search` over vector store `vs_nvZOD6q8FIEAKJL8XPT9hoPT` (10 docs) |

No Azure AI Search. No knowledge base. `file_search` is the knowledge store.

**STATUS: BUILT AND VERIFIED 2026-08-07.** The agent returns a grounded answer with a
bracketed citation and a `file_search_call` span. Verified with:

```
cd lessons/10-build-agents-foundry
uv run python ask.py l10-support-agent "How do temperature and top_p differ?"
```

Three API gotchas are baked into `ask.py`, and every one of them is worth a beat on camera. They're
written up in that file's **module docstring**, right at the top:

1. A prompt agent is referenced through **`agent_reference`** inside `extra_body` (the
   `extra_body=` argument in `ask()`), **not** `model=`. Pass an agent name to `model=` and
   you get `DeploymentNotFound`.
2. The token audience is **`https://ai.azure.com/.default`** (the `api_key=` line of the
   `OpenAI(` constructor), not `cognitiveservices.azure.com`. Wrong audience gives you a 401.
3. Use the plain **`OpenAI`** client, not `AzureOpenAI` (the `client = OpenAI(` constructor).
   The `/openai/v1` path rejects an `api-version` query parameter, and `AzureOpenAI` always
   appends one.

> **ON-CAMERA WARNING -- dead air.** The specialist agent's P50 latency is about **12 seconds** per
> answer. That's normal, it isn't a hang, and it's a long time to stare at a spinner on tape. Have a
> line ready every single time you send a question -- the version story, the citation you're about to
> point at, the token cost -- or mark a cut for post. This bites at step 2.2 and anywhere else you
> query the agent.

## Pre-flight (off camera)

1. `az login` and confirm subscription `YOUR-SUBSCRIPTION-NAME`.
2. Open **https://ai.azure.com**, confirm the **New Foundry** toggle is on, and pick project
   **`proj-agents`** in the top-right resource picker. [VERIFY IN PORTAL] -- toggle name and location.
3. Confirm `l10-support-agent` answers a test question in the playground, and **time it** so the
   12-second wait holds no surprises on tape.
4. Delete any leftover `l10-*` agents from a previous take, especially `l10-demo-agent`, since
   Beat 1 creates that name fresh and you can't reuse a name that already exists.
4a. Open `l10-support-agent` once and find where your portal build shows the raw agent definition.
   Beat 1 step 1.9 needs it on screen and the location moves between rollouts.
5. VS Code open on `lessons/10-build-agents-foundry/`.
6. **Warm the function-calling script off camera** so the first on-camera run is fast:

   ```
   cd lessons/10-build-agents-foundry
   uv sync
   uv run python function_calling.py --dry-run    # schemas only, no Azure calls
   uv run python function_calling.py              # one warm live run
   ```

   `--dry-run` is also the fastest pre-flight check: if the schema prints, `.env` resolved and
   the venv is good.

## Files this demo uses

| File | Used in | What it does |
|---|---|---|
| `10-build-agents-foundry\ask.py` | Beat 1 (module docstring + the `OpenAI(` constructor and `ask()`), Beat 2 (optional) | One-shot agent question, prints spans |
| `10-build-agents-foundry\function_calling.py` | **Beat 2** (the `@tool` / `get_ticket_status` block) | The function-calling loop, printed step by step. Microsoft Agent Framework, `@tool` |
| `10-build-agents-foundry\m10_tools_repl.py` | **Beat 3** | Interactive REPL: three tools, `:schema`, per-turn stop codes, session memory |
| `10-build-agents-foundry\provision_knowledge.py` | Pre-flight, plus **Beat 1** (the upload loop, `vector_stores.create`, and the closing `VECTOR_STORE_ID=` print) | Rebuilds the vector store from `m365_docs.json` |
| `10-build-agents-foundry\knowledge\*.md` | Pre-flight; named on camera in Beat 1 | The 10 generated source docs behind `vs_nvZOD6q8FIEAKJL8XPT9hoPT` |
| `10-build-agents-foundry\README.md` | Reference only | Lesson scope and the six LOs shared with Lesson 11 |

Lesson 10 now has **its own uv project**, so everything runs from the lesson folder. No more
borrowing the Lesson 9 virtual environment:

```
cd lessons/10-build-agents-foundry
uv run python <script>.py
```

`uv sync` builds the venv from `pyproject.toml` / `uv.lock`, and `.env` supplies
`FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_MODEL`. Nothing is hardcoded.

**SDK note, and say it on camera if it comes up:** the demo scripts use the **Microsoft Agent
Framework** (`agent_framework`), not the raw `openai` client. This is a Microsoft course teaching
Microsoft's own agent stack, and `m01_agent_demo.py`, `function_calling.py`, and
`m10_tools_repl.py` all use the same surface.

---

# Beat 1 -- Define the agent (LO 10.1, ~6 min)

> Objective: Define agent roles, goals, conversation-tracking approach, and tool schemas

**Surface:** Edge on **https://ai.azure.com**, project `proj-agents` in the top-right resource
picker. Portal only until step 1.8a, where we name two files without leaving the browser.

**1.0** [DO] From the top menu select **Build**, then the **Agents** tab.
[VERIFY] The agent list renders and `l10-support-agent` is in it with version `1` in the version
column. If that list comes up empty you're pointed at the wrong project, so fix the resource picker
before you roll.

**1.1** [DO] Select **+ New agent** above the agent list. In the **Name** field type
`l10-demo-agent` and confirm.
[VERIFY IN PORTAL] Button may read **Create agent** or **New agent** depending on your rollout.
[VERIFY] The two-pane agent builder opens: **Setup** on the left with an empty **Instructions** box,
chat pane on the right. The **Name** field is now read-only.

**1.1a** [SAY] Name it once and mean it. Foundry won't let you rename an agent after you create it,
and your code refers to it as name-colon-version, like `l10-demo-agent:1`. So that name is part of
your API surface, not a label you slap on afterward.

**1.2** [DO] In the **Setup** pane, open the **Model** dropdown and select **gpt-5-mini**.
[VERIFY] The dropdown closes reading `gpt-5-mini`, and the deployment detail shows
**GlobalStandard**, version `2025-08-07`, 50K TPM.
[VERIFY IN PORTAL] SKU and version may sit behind a hover card or an info icon instead of showing
inline next to the deployment name.

**1.2a** [SAY] The model is the reasoning engine, and it's a deployment you already own. The agent
doesn't deploy anything -- it points at a deployment that's sitting in this project. That separation
is why you can swap models on an agent without touching a line of application code.

**1.3** [DO] Click into **Instructions** and type this live. Don't paste it; let them watch it land.

```
You are Contoso Support, a senior escalation engineer.
Answer from the knowledge base. Cite the article titles you used in brackets.
If the knowledge base does not contain the answer, say so plainly.
Keep answers to one short paragraph.
```

[VERIFY] All four lines sit in the **Instructions** box and the pane flips to an unsaved state --
the **Save** button goes from dimmed to enabled, or a draft marker appears next to the version
selector. [VERIFY IN PORTAL] Exact unsaved-state affordance.

**1.4** [SAY] Every agent is three things and Microsoft says so: a model that reasons,
instructions that set goals and constraints, and tools that reach data or actions. Line one is
the role, line two is the goal and the grounding rule, line three is the failure behavior, and
line four is the format constraint. Four lines, four jobs, and every one of them is doing work.

**1.5** [DO] Select **Save**, then point at the version indicator in the **Setup** pane header.
[VERIFY] A save confirmation appears and the version indicator flips from draft to `1`.

**1.6** [DO] Go back to **Build** > **Agents**.
[VERIFY] The list shows `l10-demo-agent` at version `1`, which is exactly how you reference it in
code: `l10-demo-agent:1`.

**1.7** [SAY] Version one. Every instruction edit makes a new version, saved versions are immutable,
and that version rides along in telemetry. Hold that thought, because we cash it in next lesson.

### The agent is a document -- open the built one and read its definition

**1.8** [DO] Still in **Build** > **Agents**, open **`l10-support-agent`**, the agent that's already
built and grounded.
[VERIFY] The **Setup** pane shows model `gpt-5-mini`, the Contoso Support instructions, and exactly
one attached tool reading **File search**, bound to vector store `vs_nvZOD6q8FIEAKJL8XPT9hoPT` with
10 files.
[VERIFY IN PORTAL] Whether the vector store id shows on the tool card or only after you expand it.

**1.8a** [SAY] And that vector store didn't come from a wizard. It came from
`provision_knowledge.py` in the repo: the `for p in paths:` loop uploads the 10 markdown files,
`client.vector_stores.create(...)` builds the store, and the closing `VECTOR_STORE_ID=` line
prints the id you're looking at right now. It's the same object whether you reach it through
the portal or the SDK, and that's the whole point.

**1.9** [DO] Open the raw definition for this agent version. Check the **Details** tab first; if it
isn't there, open the version dropdown and use the version-compare view, which renders the
definition as text.
[VERIFY IN PORTAL] I've seen this surfaced as a **YAML definition** in version compare and as JSON
in the REST payload. Use whichever your build shows -- the shape is identical either way, and this
label has moved more than once.
[VERIFY] Four keys are readable on screen: `kind`, `model`, `instructions`, `tools`.

**1.10** [SAY] This right here is the entire agent, and it's declarative. `kind` is `prompt`, which
means Foundry runs it for me. There's no container, no scaling knob, and no code of mine anywhere in
this thing. `model` points at the `gpt-5-mini` deployment. `instructions` is the system message you
just watched me type. And `tools` is an array where every entry carries a `type` string that names
the capability. Right now there's one entry, and its type is `file_search`.

**1.11** [SAY] Here's why that matters for the exam. When a question asks you to give an agent access
to a search index, or to an internal API, it's really asking what goes in that tools array. Roles and
goals live in `instructions`. Capabilities live in `tools`. Keep that split straight and a whole
category of questions gets easy.

**1.12** [DO] If your build has no definition view at all, fall back to the chat pane's **Code** tab
and put that generated snippet on screen instead.
[VERIFY] The snippet references the agent by name and version through `agent_reference`, and there's
no model deployment name being passed as `model=`. That's the same gotcha `ask.py` documents at
**lines 6 to 8**.

**1.13** [SAY] Last piece of the objective, and it's the one people skip: conversation tracking. I'm
not managing chat history anywhere in this definition. Foundry keeps a **conversation** per thread,
stores the messages and the tool calls in it, and truncates to fit the context window. That's the
tracking approach, you get it by default, and we'll watch it work in the next beat.

**[PAUSE]**

---

# Beat 2 -- Retrieval, conversation, and function calling (LO 10.2, ~7 min)

> Objective: Build agents that integrate retrieval, function-calling, and conversation memory

**2.1** [DO] **Tools** > add **file search** > select the uploaded `m365_docs` set. **Save**.

**2.2** [DO] **Try in playground**. Ask: `How do temperature and top_p differ?`

**2.3** [VERIFY] Answer arrives with a bracketed citation.

**2.4** [SAY] That's retrieval from a knowledge store, and I wrote no code for it.

**2.5** [DO] Ask a follow-up with a pronoun: `Which one should I change first?`

**2.6** [VERIFY] It answers in context without you restating the topic.

**2.7** [SAY] That's the conversation doing its job. A conversation is the durable record of
messages, tool calls, and responses. Foundry stores it and truncates it to fit the context
window. That's short-term memory, and it's free.

**2.8** [SAY] What it will not do is remember you next week in a new session. That's long-term
memory, a separate managed feature with its own store and retention window. Know the difference
for the exam; you don't need to build one today.

**2.9** [DO] Switch to **VS Code**. Open
`lessons/10-build-agents-foundry/function_calling.py`.

### The tool definition -- the `get_ticket_status` block in `function_calling.py`

> Line numbers below are a convenience, not a contract. The anchor is the symbol: search for
> `@tool` and put that whole block on screen.

**2.10** [DO] Scroll to `@tool(approval_mode="never_require")` (**line 159**). Put the whole
function on screen, decorator through the closing docstring (**about line 171**).
[SAY] This is the Microsoft Agent Framework. I am not hand-writing JSON here. The schema the
model receives is **generated from this Python signature**, which means the code and the schema
can never drift apart.

**2.11** [DO] Point at `def get_ticket_status(` (**line 160**).
[SAY] The function name becomes the tool name. Descriptive, not abbreviated. This is the first
thing the model reads.

**2.12** [DO] Point at the docstring (**lines 167 to 171**).
[SAY] The docstring becomes the tool description, and it is the single highest-leverage string
in the schema, because the model re-reads it every turn. Microsoft's docs call out vague
descriptions by name. "Does stuff with data" tells the model nothing. Notice I also wrote
"Never guess a ticket's status; always call this tool."

**2.13** [DO] Point at `json_schema_extra={"enum": ["summary", "full"]}` (**line 165**).
[SAY] An enum turns a class of runtime failure into a schema constraint. The model cannot
invent a detail level that isn't in that list.

**2.14** [DO] Point at the end of that same line, `= "summary"` (**line 165**).
[SAY] That default is what keeps `detail` OUT of the required list, while `ticket_id` stays
required. Required is what makes the model ask a follow-up question instead of guessing.

**2.15** [DO] Scroll to the body of `get_ticket_status`, the `record = TICKETS.get(...)` line
(**line 174**).
[SAY] And here's our implementation. Hold that thought.

### Run the loop

**2.16** [DO] Terminal:

```
cd lessons/10-build-agents-foundry
uv run python function_calling.py
```

**2.17** [VERIFY] Section 1 prints the **generated** JSON Schema, with the enum and
`"required": ["ticket_id"]` visible.
[SAY] I wrote Python. The framework produced this JSON. That is the schema the model sees.

**2.18** [VERIFY] Section 2 prints the turn shape:

```
response.status : completed
incomplete      : None
  message[0] role=assistant contents=['text_reasoning', 'function_call']
  message[1] role=tool      contents=['function_result']
  message[2] role=assistant contents=['text_reasoning', 'text']
```

[SAY] Read those three messages top to bottom, because that IS the loop. The assistant decided
and emitted a **function_call**. The tool message carries the **function_result** -- that is our
code's return value coming back. Only then does the assistant produce text.

[SAY] Notice `text_reasoning` in that first message. `gpt-5-mini` is a **reasoning model**, so it
thinks before it decides which tool to call. You will see that item on every tool turn.

**2.19** [VERIFY] Section 3 prints:

```
call.name       : get_ticket_status
call.call_id    : call_Ot4WPU8HkiQNStHIHfMhI0BZ
call.arguments  : {"ticket_id": "CS-1042", "detail": "full"}
```

[SAY] Look at the arguments. I said "full detail" in plain English and the model mapped that to
`detail: "full"` -- one of my two enum values. That mapping is the schema doing its job. And
that `call_id` matters: it's how the result gets matched back to this exact request.

**2.20** [VERIFY] Section 4 prints our returned JSON: `awaiting_customer`, `P2`, owner
`Tim Warner`.

[SAY] **The model never ran that.** It asked, my code executed in my process, and the result went
back. That boundary is the security control and the debugging seam.

[SAY] And here the framework is earning its keep. On the raw REST API you would hand-write a
second request that replays the call and its result. The Agent Framework does that hop for you.
One `agent.run` call, and the whole loop is in `response.messages`.

**2.21** [VERIFY] Section 5 prints the final answer with the ticket details, and:

```
response.status : completed
```

[SAY] Completed means the model chose to stop. Worth knowing for the exam and for debugging: on
this path `finish_reason` comes back **None**, so the real stop signal is that `status` on the
underlying response. If it ever says `incomplete`, check `incomplete_details` -- usually a token
cap, not a bug in your tool.

**[PAUSE]**

---

# Beat 3 -- The tool catalog (LO 10.3, ~6 min)

> Objective: Integrate agent tools, including APIs, knowledge stores, search, content
> understanding, and custom functions

**Surface:** Foundry portal only, no code. Two different pages matter here and people mix them up:
the **agent's** own tool picker, and the project-wide **Foundry Tools** catalog under **Build** >
**Tools**. We hit both.

**3.0** [DO] Go to **Build** > **Agents** and open `l10-demo-agent`, the one you created in
Beat 1. In the **Setup** pane, find the tools section and select **+ Add tools**.
[VERIFY IN PORTAL] The section header may read **Tools**, **Knowledge and tools**, or split into
separate **Knowledge** and **Actions** sections, and the button may read **+ Add** instead of
**+ Add tools**.
[VERIFY] A tool picker panel opens listing the built-in tools, with **File search** and **Azure AI
Search** both visible in it.

**3.1** [DO] Leave the picker open on screen and scroll it top to bottom once, slowly, so the whole
catalog lands on tape.
[VERIFY] You can read at minimum: **File search**, **Azure AI Search**, **Code interpreter**,
**Function calling**, **OpenAPI**, **MCP server**, **Web search** or **Grounding with Bing**,
**SharePoint**, **Microsoft Fabric**, **Browser automation**, **Computer use**, and **Memory
search**.
[VERIFY IN PORTAL] Which entries actually render depends on region and on which preview flags this
account has. Read off what's on your screen, not off this list.

**3.2** [SAY] The exam tests picking the right tool, not clicking the button, so let's walk the
categories and I'll tell you what each one is actually for.

**3.2a** [SAY] There are three buckets, and the whole catalog fits in them. **Knowledge tools** bring data in:
file search, Azure AI Search, SharePoint, Fabric, Bing. **Action tools** reach out and do something:
function calling, OpenAPI, MCP, Azure Functions, code interpreter, browser automation. And **memory**
sits off to one side, because it's about what the agent recalls across sessions rather than what it
knows or what it does.

**3.3** [SAY] **Knowledge stores.** File search is what we used, and it's the low-ceremony option:
you upload documents, Foundry chunks and embeds them into a managed vector store, and the agent
queries it. A handful of documents, no infrastructure, no index schema to design, and citations for
free. Scale past that and you want **Azure AI Search**, where you own the index, the analyzers, the
hybrid keyword-plus-vector retrieval, and the semantic ranker. That's the swap point, and it's a
favorite exam distinction.

**3.3a** [SAY] The honest tiebreaker is who owns the index. If Foundry owns it, that's file search.
If you own it -- because you need filters, facets, a refresh schedule, or relevance tuning -- that's
Azure AI Search.

**3.4** [SAY] **Content Understanding** is the one people get wrong, because it isn't a retrieval
tool at all. It sits in front of retrieval. You point it at scanned documents, forms, audio, or
video, and it hands you clean structured fields. Those fields are what you index afterward. So when
a question describes messy PDFs or invoices, the answer usually starts with Content Understanding
and ends with Azure AI Search.

### Choosing table -- read this one off camera-right

| You need | Pick | Tool `type` string | Why it wins |
|---|---|---|---|
| Ground on ten to a few hundred docs you can upload, shipping this week | **File search** | `file_search` | Managed vector store, no index to design, citations for free. This is what `l10-support-agent` runs |
| Millions of docs, filters, facets, hybrid keyword-plus-vector, semantic reranking, your own refresh schedule | **Azure AI Search** | `azure_ai_search` | You own the index and the relevance tuning, wired in through a project connection |
| Input is scanned, handwritten, layout-heavy, audio, or video and has to be structured first | **Content Understanding** | *(not an agent tool -- it's a preprocessing service upstream of the index)* | Turns unstructured files into structured fields; you index those fields, then retrieve them |
| Call your own code with typed arguments | **Function calling** | `function` | Your app executes and the model only requests. That's Beat 2 |
| Call a REST API you already have a spec for | **OpenAPI tool** | `openapi` | Hand it the OpenAPI 3.0 spec, pick the auth, done. No wrapper code |
| Reach a tool server somebody else hosts | **MCP** | `mcp` | Remote tool server behind an approval gate |
| Run Python over data in the conversation | **Code interpreter** | `code_interpreter` | Sandboxed execution, good for math and file transforms |
| Recall facts about this user across separate sessions | **Memory search** | `memory_search` | Long-term memory store, separate from conversation history |
| Hand work off to another agent | **Agent-to-agent** | `a2a_preview` | The multi-agent hook. Lesson 11 |
| Answer from the live public web | **Grounding with Bing** | `bing_grounding` | Fresh web data with citations |

[VERIFY IN PORTAL] `memory_search` also shows up as `memory_search_preview` on some API surfaces.
Check the definition of an agent that has it attached before you say the string on camera.

**3.4a** [SAY] Memorize the type strings, not the button labels. Buttons get renamed and moved every
few months. The tools array doesn't. When you see `"type": "azure_ai_search"` in a definition, you
know exactly what that agent can reach and you know somebody had to stand up an index for it.

**3.5** [SAY] **Custom functions and APIs.** There are three ways in, and they grade cleanly by how
much you own. A `function` tool is a schema plus your code, and you run the code -- that's the loop we just
walked in Beat 2. An `openapi` tool is a spec you already have, and Foundry calls the API for
you. An `mcp` tool is an entire tool server somebody else runs, and you just point at it. Least
delegated to most delegated, in that order, and that ordering is worth remembering.

**3.6** [DO] In the tool picker, select **MCP server** and open its configuration form.
[VERIFY] The form asks for a **Server label**, a **Server URL**, an approval setting, and an
authentication choice.
[VERIFY IN PORTAL] Field labels. In the API these are `server_label`, `server_url`,
`require_approval`, and `project_connection_id`, and the portal wording may not match one-to-one.

**3.6a** [DO] Point at the approval control and say its API name out loud: **`require_approval`**.
[VERIFY] The control is on screen, readable at recording zoom, and its options are visible -- ask
every time versus always allow, or `always` versus `never` if the form shows the raw values.

**3.7** [SAY] Authentication is one of three things. Keys, stashed in a project connection so the
secret never lands in your code. Entra ID through a managed identity, which is where you should
start whenever the server supports it, because there's no secret to rotate. Or on-behalf-of, where
the agent acts as the signed-in user and inherits that person's permissions. That last one is how
you keep an agent from reading documents its user can't read.

**3.7a** [SAY] And `require_approval` is where Lesson 11 starts. Set it to always and every tool call
stops for a human. Set it to never and the agent runs unattended. That single field is the line
between a semiautonomous workflow and an autonomous one, and the objective domain names both.

**3.7b** [DO] Close the MCP form without saving. Select **Cancel**, or dismiss the panel.
[VERIFY] `l10-demo-agent` is still at version `1` with no MCP tool attached. You don't want a
half-configured tool sitting in the recording environment for the next take.

**3.7c** [DO] Now show the project-wide catalog: top menu > **Build** > **Tools**.
[VERIFY] Foundry Tools opens with filters for **Publisher**, **Category**, **Registry**, and
**Supported authentication**, and catalog entries typed as **Remote MCP server**, **Local MCP
server**, or **Custom**.
[VERIFY IN PORTAL] Filter names and the exact set of entry types.

**3.7d** [SAY] There are two surfaces here, and this trips people. The picker inside the agent attaches a capability
to that one agent. **Build** then **Tools** is the project's catalog of configured tool servers that
any agent can pull from. Configure a server once there, attach it many times. Same idea as a
connection, applied to tools.

**3.8** [VERIFY] Final frame check for this beat: the agent tool picker was on screen and
scrolled, the choosing table got read, the MCP configuration form was open with `require_approval`
named out loud, `l10-demo-agent` is still at version `1`, and **Build** > **Tools** is the last
thing on screen.

---

## If it breaks

| Symptom | Fix |
|---|---|
| Model dropdown empty | Re-pick `proj-agents` in the top-right resource picker |
| No citation in the answer | The file set didn't attach; re-add file search and save |
| Follow-up loses context | You started a new conversation; stay in the same playground thread |
| Function script fails on auth | `az login` expired; re-auth and re-run |
| Agent name rejected as already in use | You didn't delete `l10-demo-agent` from the last take. Names can't be reused and can't be renamed; delete it and recreate |
| Agent takes about 12 seconds to answer | Not broken. P50 is roughly 12 seconds. Talk through it or mark a cut |
| `DeploymentNotFound` when you call an agent from code | You passed the agent name to `model=`. Agents ride in `extra_body` as `agent_reference`; `model=` is only for model deployments. See the `extra_body=` argument in `ask()` |
| `401 Unauthorized` from any of the scripts | Wrong token audience. It has to be `https://ai.azure.com/.default`, not `cognitiveservices.azure.com`. See the `api_key=` line of the `OpenAI(` constructor. If the audience is already right, your `az login` token is stale -- re-auth |
| `api-version query parameter is not allowed when using the /v1 path` | You built an `AzureOpenAI` client, which always appends `api-version`. Use the plain `OpenAI` client with `base_url=f"{PROJECT_ENDPOINT}/openai/v1"` and a bearer token. See the `client = OpenAI(` constructor in both `ask.py` and `provision_knowledge.py` |
| `Item 'fc_...' of type 'function_call' was provided without its required 'reasoning' item` | Only hits hand-rolled REST loops: `gpt-5-mini` is a reasoning model, so a replayed function call must carry its reasoning item. The Agent Framework handles this for you, so this should not appear in these demos |
| `ModuleNotFoundError: agent_framework` | You are in the wrong folder or skipped `uv sync`. Run from `lessons\10-build-agents-foundry` with `uv run python <script>.py` |
| `ERROR: FOUNDRY_PROJECT_ENDPOINT is not set` | No `.env` in the lesson folder. `cp .env.example .env` and fill it in |
| httpx `getaddrinfo failed` | The VS Code terminal injected proxy vars. Both scripts strip them at import, so make sure you're running the file and not pasting lines into a REPL |
| Tool picker is missing a tool this runbook names | Region or preview flags on this account. Read off what's actually on screen and move on; don't stall on tape |

## Runtime

Roughly 19 to 21 minutes now that Beats 1 and 3 carry their weight. Beat 1 runs about 6,
Beat 2 about 7, Beat 3 about 6, plus the pauses. If you need to claw back time, Beat 3
steps 3.7c and 3.7d are the cut -- the choosing table is the part that earns the exam points.
