# AI-103 -- Lesson 11 Demo Runbook

**Orchestrate Multi-Agent Solutions and Monitor Agent Behavior**

Three beats, one per learning objective. About 19 to 21 minutes.
Surface: **Edge (Foundry portal and Azure portal)**. The only terminal work is
`generate_traffic.py`, and that runs off camera in pre-flight.

---

## Environment

| Thing | Value |
|---|---|
| Resource group | `rg-ai103-mvp` (eastus2) |
| Project | `proj-agents` on `YOUR-FOUNDRY-RESOURCE` |
| Specialist agent | `l10-support-agent:1` -- built and verified |
| Orchestrator agent | `l11-orchestrator:1` -- created, delegation **not yet working** |
| Telemetry | `appi-ai103-l11` over `log-ai103-l11` -- **connected and verified flowing** |
| Traffic generator | `lessons/11-build-agents-foundry/generate_traffic.py` |

**STATUS: TELEMETRY VERIFIED 2026-08-08. Queries A and C return rows. Query B doesn't yet.**

Verified live after 18 agent runs (12 specialist, 6 orchestrator):

**Query A returns:**

| Agent | Version | Runs | P50Ms | P95Ms |
|---|---|---|---|---|
| `l10-support-agent` | 1 | 12 | 12,263 | 18,509 |
| `l11-orchestrator` | 1 | 6 | **1** | **4** |

That 1 ms P50 on the orchestrator is a gift. A healthy agent takes ten seconds; this one is
failing before it does any work at all. On camera, that single number is how you spot a broken
agent without reading a log.

**Query C returns:**

| Cause | Op | Agent | Count |
|---|---|---|---|
| ok | chat | `l10-support-agent` | 12 |
| ok | execute_tool | `l10-support-agent` | 12 |
| ok | invoke_agent | `l10-support-agent` | 12 |
| **span failure** | invoke_agent | `l11-orchestrator` | **6** |

The error taxonomy caught a real failure, not a manufactured one.

**Query B returns nothing.** All 18 traces have exactly one agent, because A2A delegation is
still failing. See Blocker 1.

---

**Remaining blocker.**

**Blocker 1 -- A2A delegation returns 401.** `l11-orchestrator` carries an `a2a_preview` tool
pointing at the specialist, and its managed identity has Cognitive Services User and Cognitive
Services OpenAI User on the account. The call still fails with
`Failed to fetch agent card: 401 (PermissionDenied)`. Root cause is almost certainly that the
specialist has no **incoming A2A endpoint enabled** -- its `protocols` array reads
`["responses"]` only, so there's no agent card to fetch. Fix per
<https://learn.microsoft.com/azure/foundry/agents/how-to/enable-agent-to-agent-endpoint> and
<https://learn.microsoft.com/azure/foundry/agents/concepts/agent-to-agent-authentication>.

**Blocker 2 -- telemetry not connected. RESOLVED 2026-08-08.** `appi-ai103-l11` is now
connected to `proj-agents` and spans are flowing. If you ever rebuild the project and have to
reconnect it: project dropdown > **Project details** > **Connected resources** > **Add
connection** > **Application Insights**, then run `generate_traffic.py` and wait three minutes.
[VERIFY IN PORTAL] There's also a shortcut from **Agents > Traces > Connect**; confirm that entry point still exists in the current build before you rely on it on camera.

**Verified span names now in telemetry.** Get these four on screen in Beat 3; they're the
vocabulary the whole KQL section is built on.

| Span `name` | What emitted it |
|---|---|
| `invoke_agent l10-support-agent:1` | One specialist run, agent and version baked into the name |
| `invoke_agent l11-orchestrator:1` | One orchestrator run, the ones that fail |
| `execute_tool file_search.msearch` | The specialist's knowledge store doing retrieval |
| `chat gpt-5-mini-2025-08-07` | The underlying model call |

**Consequence for the demo:** until Blocker 1 clears, **Query B returns no rows**, because no
trace contains two agent names. Beat 3 handles that head-on instead of hiding it -- see
beat 3.12.

## Files this demo uses

| File | Used in | What it does |
|---|---|---|
| `11-build-agents-foundry\generate_traffic.py` | **Pre-flight + Beat 3** | Fires 18 agent runs (12 specialist, 6 orchestrator) so Queries A and C have something to return |
| `11-build-agents-foundry\README.md` | Reference only | The six L10/L11 objectives, quoted verbatim from the objective domain |
| `10-build-agents-foundry\ask.py` | Beat 1 fallback | One-shot question at a named agent from a terminal, if you'd rather show the 401 in a console than in the playground |

L11 is a normal uv lesson: it has its own `pyproject.toml` and `uv.lock`, so run everything
from this folder. `uv run` builds and selects the environment for you, no activation needed:

```
cd lessons/11-build-agents-foundry
uv sync
uv run python generate_traffic.py --rounds 3
```

## Pre-flight (off camera)

1. `az login`. Confirm the subscription is `YOUR-SUBSCRIPTION-NAME`.

2. **Generate telemetry.** Run the commands above from this lesson folder.

3. [VERIFY] The script prints its targets, three rounds, then a tally. Expected shape:

   ```
   [traffic] targets=['l10-support-agent', 'l11-orchestrator']  rounds=3

   --- round 1 ---
     [l10-support-agent] How do temperature and top_p differ?
         -> Temperature and top_p both control randomness...
     [l11-orchestrator] How do temperature and top_p differ?
         !! <ErrorType>: ... Failed to fetch agent card: 401 (PermissionDenied)
     [l10-support-agent] (expected miss) What is our company holiday schedule for next year?
         -> The knowledge base doesn't contain...
   ...
   [traffic] 12 succeeded, 6 failed.
   ```

   **12 succeeded, 6 failed is the correct result today.** The 12 are the specialist, the 6 are
   the orchestrator, and those 6 failures are what makes Beat 3 honest instead of staged.
   The exception class name in the `!!` line varies by SDK version; the 401 text is the part
   that matters.

4. **Where 12 and 6 come from** -- worth knowing, because Beat 3 quotes these numbers.
   `generate_traffic.py` builds a target list in `main()` and gives each agent a different
   slice of the question list:

   ```python
   targets = [(SPECIALIST, 3)]
   if not args.skip_orchestrator:
       targets.append((ORCHESTRATOR, 2))
   ```

   Three grounded questions for the specialist plus one deliberate miss, two for the
   orchestrator. Three rounds gives 3 x (3 + 1) = **12 specialist runs** and
   3 x 2 = **6 orchestrator runs**.

   The "expected miss" (`UNGROUNDED`) still **succeeds** as an API call. It is a grounded-
   answer failure, not a transport failure: the agent correctly reports that its knowledge
   store has nothing. The orchestrator's 401s are the opposite -- a transport failure, before
   the agent does any work. Query C separates those two, which is the whole point of the beat.

5. **Wait 3 minutes** for App Insights ingestion before you run any KQL. The script says so
   itself in the closing `[traffic] Allow 1-3 minutes...` line. Every Beat 3 query uses a 24-hour window and this
   environment goes cold in a day, so if you shot Beats 1 and 2 yesterday, re-run the script
   before you shoot Beat 3.

6. Confirm `l10-support-agent` answers a question in the playground. Skip testing
   `l11-orchestrator` -- it fails by design right now, and Beat 1 is built around that.

7. Open two browser tabs and leave them signed in:
   - **https://ai.azure.com** > project **`proj-agents`** > **Agents**
   - **https://portal.azure.com** > **`rg-ai103-mvp`** > **`appi-ai103-l11`** > **Logs**

8. Note `l10-support-agent`'s current version number. Beat 2 changes it twice and you want
   to know where you started.

9. Optional flags, both defined in `parse_args()`: `--rounds 5` gives you 20 specialist and
   10 orchestrator runs if you want fatter percentiles. `--skip-orchestrator` gives you
   specialist traffic only, which you don't want here, because the orchestrator failures are
   the story. Confirm either with `uv run python generate_traffic.py --help`.

10. Delete any leftover `l11-*` agents from a previous take so the agent list is clean on
    camera.

---

# Beat 1 -- Orchestrate two agents (LO 11.4, ~6 min)

> Objective: Implement orchestrated multi-agent solutions

> **SHOOTING NOTE -- READ THIS BEFORE YOU RECORD.** Live A2A delegation is broken right now
> (Blocker 1). **Beats 1.1 through 1.17 are the FALLBACK path and they're what you actually
> shoot today.** They teach the supervisor pattern off the two agents' configuration and then
> show the real 401 on camera, which sets up Beat 3 honestly. The **LIVE path** beats are
> parked at the end of this beat under "Once A2A is fixed" -- shoot those only after the
> 401 clears, and drop them in place of 1.12 through 1.16.

### The two agents, side by side

**1.1** [DO] Edge to **https://ai.azure.com**. Check the resource picker in the top right reads
**`proj-agents`** on **`YOUR-FOUNDRY-RESOURCE`**. Left nav > **Agents**.
[VERIFY IN PORTAL] Confirm the exact left-nav label and its grouping before you record; this nav moves between builds.

**1.2** [VERIFY] The agent list shows exactly two rows, `l10-support-agent` and
`l11-orchestrator`, each showing version **1**. If you see `l11-` leftovers from an earlier
take, stop and delete them; a cluttered list costs you a re-shoot.

**1.3** [SAY] Microsoft's advice is to build reliable single agents first, then orchestrate.
We built one last lesson. Now we give it a boss.

**1.4** [DO] Click **`l11-orchestrator`**. Put the **Instructions** box on screen full width.
[VERIFY IN PORTAL] Confirm whether the agent opens in a details pane or a full editor page, so you know where to frame the zoom.

**1.5** [VERIFY] The instructions describe classifying the incoming request and handing
documentation questions to `l10-support-agent`. There's no retrieval instruction anywhere in
there, because there's nothing for this agent to retrieve from.

**1.6** [DO] Scroll the same pane to **Knowledge**.
[VERIFY] **Empty.** No file search, no vector store, no index. Say the number out loud on
camera: zero knowledge tools.

**1.7** [DO] Scroll to **Tools**. Click the single entry, **`a2a_preview`**, to open its
configuration.
[VERIFY IN PORTAL] This section may be labelled Tools or Actions depending on the build; confirm before you record.

**1.8** [VERIFY] The tool config names **`l10-support-agent`** as its target. That's the whole
delegation contract on one screen: one agent pointing at another agent by name.

**1.9** [SAY] That's the supervisor pattern in two panes. One orchestrator, one or more
specialists. The supervisor classifies intent and delegates, and it doesn't do the work itself.
The agent you're looking at literally can't do the work, because it owns zero knowledge tools.
Any grounded answer it ever returns has to come from somewhere else.

**1.10** [DO] Back to **Agents**. Click **`l10-support-agent`** and scroll to **Knowledge**.
[VERIFY] **file search** is attached, over vector store **`vs_nvZOD6q8FIEAKJL8XPT9hoPT`**.
That's the same store you built in Lesson 10.

**1.11** [SAY] There's the asymmetry, and it's the entire design. The specialist owns the
documents. The orchestrator owns the routing. You add a second and a third specialist without
touching the supervisor's knowledge config, because the supervisor never had any. That
separation is why this pattern earns its keep.

### The delegation call, and the error it throws today

**1.12** [SAY] Now, full disclosure, because you'd hit this yourself the first time you tried
it. In my environment the delegation call fails. Let me show you the failure, because the error
message teaches you more than a happy path would.

**1.13** [DO] Click **Agents** > **`l11-orchestrator`** > **Try in playground**. Paste this
exact string, don't improvise on tape:

```
What does our documentation say about few-shot learning?
```

[VERIFY IN PORTAL] Confirm the button label reads "Try in playground" on the agent pane in this build.

**1.14** [VERIFY] The run fails almost instantly -- one or two seconds, no streamed text -- with:

```
Failed to fetch agent card: 401 (PermissionDenied)
```

**1.15** [SAY] Here's what that actually means. A2A delegation starts by fetching the target
agent's **agent card**, which is the machine-readable description of what that agent can do and
how to call it. My specialist never publishes one. Its `protocols` array reads `responses` and
nothing else, so there's no incoming A2A endpoint, so there's no card to fetch, so the caller
gets a 401. Notice where the fix lives: on the callee, not the caller. I already gave the
orchestrator Cognitive Services User and Cognitive Services OpenAI User, and more role
assignments won't move this one inch.

**1.16** [SAY] Hold on to how fast that failed. One second, maybe two. In Beat 3 that shows
up as a latency number, and that single number is how you spot a broken agent without opening a
log.

**1.17** [SAY] Two orchestration routes exist and one's on a clock. Connected Agents is the
classic route and it retires March 31, 2027. The current routes are A2A endpoints for direct
delegation, which is what you just watched me attempt, and Workflows for declarative multistep
processes. If the exam gives you a new build, don't pick the one with the retirement date on it.

**[PAUSE]**

### Once A2A is fixed -- swap these in for 1.12 through 1.16

Fix per
<https://learn.microsoft.com/azure/foundry/agents/how-to/enable-agent-to-agent-endpoint>, then:

**1.12L** [DO] **Agents** > **`l11-orchestrator`** > **Try in playground**. Paste:
`What does our documentation say about few-shot learning?`

**1.13L** [VERIFY] The answer takes roughly ten seconds, not one, and comes back with a
bracketed citation naming one of the `pe-*` articles from the specialist's vector store.

**1.14L** [SAY] The orchestrator owns no documents, so that citation could only have come from
delegation. I'm not asking you to take my word for it either -- we'll prove it in telemetry in
a few minutes, with a query that's impossible to run against a single-agent system.

**1.15L** [DO] Re-run `generate_traffic.py` with the fix in place, then re-shoot Beat 3
beats 3.11 and 3.12, because Query B will finally return rows.

---

# Beat 2 -- Approvals and the autonomy dial (LO 11.5, ~6 min)

> Objective: Build autonomous or semiautonomous workflows with safeguards and approval flow
> controls

> **This is the money beat of the lesson.** Everything else is setup for it. If you only get
> one beat right today, get this one. Budget a second take.

### Get to the field

**2.0** [DO] Off camera, confirm `l10-support-agent` actually has an **MCP** tool attached.
Lesson 10 shipped it with **file search** only, so on a fresh rebuild you'll need to add one
before you record.
[VERIFY IN PORTAL] Best guess at the add path is **Agents** > `l10-support-agent` > **Tools** > **Add** > **MCP server**, then a server label, a server URL, and an allowed-tools list. Confirm the labels and the required fields yourself before you shoot.

**2.1** [DO] Foundry portal > left nav **Agents** > click **`l10-support-agent`** > scroll to
**Tools** > click the **MCP** tool entry to open its configuration.
[VERIFY IN PORTAL] Confirm whether the config opens as a right-hand side panel or a centered modal, so you can frame the zoom in advance.

**2.2** [VERIFY] The configuration shows a field literally named **`require_approval`**,
currently set to **`never`**. Get that field name large and centered and hold it for a beat.
The exam names this field, so the audience needs to read it, not just hear it.

**2.3** [SAY] Right now this agent calls that tool whenever it likes. Its instructions say
nothing about asking permission, and even if they did, it wouldn't matter.

**2.4** [DO] Show the doc line on screen:

> "The toolbox MCP endpoint doesn't block `tools/call` when `require_approval` is `always`.
> Your agent runtime must enforce the setting before every invocation. A system-prompt
> instruction alone doesn't enforce approval."

**2.5** [SAY] Instructions are a request. The runtime is the enforcement. Microsoft wrote that
down for us, so quote it back at anybody on your team who wants to ship an approval gate as a
sentence in a system prompt.

### Flip it and watch it stop

**2.6** [DO] Change **`require_approval`** from **`never`** to **`always`**. Click **Save**.
[VERIFY IN PORTAL] Confirm how the values render -- a dropdown of `never` / `always`, a toggle, or a per-tool allow list. Know which one you're clicking before the camera rolls.

**2.7** [VERIFY] The agent's version indicator increments from **1** to **2**, and the agent
list now reads `l10-support-agent:2`.
[VERIFY IN PORTAL] Lesson 10 proved an *instructions* edit bumps the version. Confirm a *tool config* edit does the same, because beat 2.13 and the Beat 3 queries both assume it does.

**2.8** [DO] **Try in playground** on `l10-support-agent`. Paste the question you validated
off camera that forces the **MCP** tool rather than file search. Don't improvise this one on
tape -- if the model picks file search instead, nothing pauses and the beat falls flat.

**2.9** [VERIFY] The run **stops before the tool executes**. In the thread you should see three
things: the **tool name**, the **arguments** it wants to send as JSON, and an **Approve** control
next to a reject control. Nothing streams underneath it until you click.
[VERIFY IN PORTAL] The reject control may read Reject, Decline, or Deny; check the labels so your narration matches the screen.

**2.10** [SAY] There it is. It stopped, it showed me exactly what it wants to do and with what
arguments, and nothing happens until a person decides. That pause is the safeguard. It isn't a
warning banner, it isn't a log line you read tomorrow morning, it's a hard stop sitting in the
execution path.

**2.11** [DO] Click **Approve**.
[VERIFY] The run resumes in the same thread, the tool result comes back, and the agent finishes
its answer. Total elapsed time now includes however long you sat there deciding, which is worth
a sentence on camera.

**2.12** [SAY] Put that on the autonomy dial. Manual is a human in every step. Assisted is the
agent drafting and a human clicking. This is semi-autonomous: routine reads run free,
consequential calls stop for a person. That's where most production agents belong, and it's the
answer the exam wants any time a scenario describes a human checkpoint on a risky action.

**2.13** [DO] Set **`require_approval`** back to **`never`**. **Save**.
[VERIFY] The version increments again, to **3**. Leave it there and don't edit the agent again
before Beat 3. Every Beat 3 query groups by version, so a stray edit means a stray row on
camera that you'll have to explain.

### FALLBACK -- if the portal doesn't pause

This is a real possibility in the current build. Read this before you shoot 2.8.

**2.F1** If you send the question and the run completes end to end with no approval prompt,
**don't re-record and don't debug it on camera.** The runtime isn't enforcing approval for this
tool type in this build. That's documented behavior, and it's a better teaching moment than a
working button.

**2.F2** [SAY] Watch what just happened. I set `require_approval` to `always`, I saved, the
version incremented, and the tool fired anyway. That's exactly what the documentation warned us
about. The setting is a declaration, and something in the runtime has to honor it. So if your
approval gate is load-bearing, you enforce it in your own orchestration code and you write a
test that proves it stops, because a config field you haven't tested is a config field you
don't have.

**2.F3** [DO] Cut straight back to the doc quote in 2.4, hold it for two beats, then go to 2.12
for the autonomy dial. You lose about a minute of runtime and the beat still lands.

**2.F4** [DO] Either way, finish with 2.13 and put `require_approval` back to `never`.

**[PAUSE]**

---

# Beat 3 -- Prove the orchestration in telemetry (LO 11.6, ~7 min)

> Objective: Integrate monitoring into deployed agents, evaluate agent behavior, and perform
> error analysis

> **Ingestion gate.** Nothing in this beat returns a row until `generate_traffic.py` has run
> and you've waited 3 minutes. If you shot Beats 1 and 2 in a previous session, re-run the
> script now and shoot something else while it lands.

### Open the right blade, in the right dialect

**3.1** [DO] Azure portal at **https://portal.azure.com**. Global search for
**`appi-ai103-l11`** and open the Application Insights resource. Left nav > **Monitoring**
group > **Logs**.
[VERIFY IN PORTAL] Confirm the Logs entry still sits under the Monitoring group in this build's left nav.

**3.2** [DO] If a **Queries** gallery opens over the editor, dismiss it. You want an empty
query tab.
[VERIFY] The editor header shows the scope as **`appi-ai103-l11`**, and the table list in
the left pane includes **`dependencies`**.

**3.3** [SAY] One thing before we write a line of KQL, because it costs people an afternoon.
I'm inside the Application Insights resource, so my table is `dependencies` and my property bag
is `customDimensions`. If you open Logs from the Log Analytics workspace instead, which for me
is `log-ai103-l11`, that same data is `AppDependencies` and `Properties`. Same telemetry,
two dialects, and pasting the wrong one gets you a syntax error or a table of blanks. Every
query in this beat is written for the Application Insights side.

**3.4** [DO] Orientation first. Run this and leave the result on screen while you talk:

```kusto
// 0 -- What span names am I actually collecting?
dependencies
| where timestamp > ago(24h)
| summarize Spans = count() by name
| order by Spans desc
```

**3.5** [VERIFY] These four names are present, and after a default three-round traffic run the
counts read:

| name | Spans |
|---|---|
| `chat gpt-5-mini-2025-08-07` | 12 |
| `execute_tool file_search.msearch` | 12 |
| `invoke_agent l10-support-agent:1` | 12 |
| `invoke_agent l11-orchestrator:1` | 6 |

**3.6** [SAY] Read those names, because they're doing a lot of work for free. The agent name and
the version are baked right into the span name. `invoke_agent l10-support-agent:1` is one run of
version one of my specialist. `execute_tool file_search.msearch` is that agent hitting its
knowledge store. And `chat gpt-5-mini` is the model call underneath all of it. Three layers of
the same request, and I didn't instrument any of it by hand.

### Query A -- agent KPIs by name and version

**3.7** [SAY] Lesson 9 taught you KQL against a single app. Now there are two agents, and that
changes which questions are worth asking.

**3.8** [DO] Run **Query A**:

```kusto
// A -- Agent KPIs by name and version
dependencies
| where timestamp > ago(24h)
| extend cd = parse_json(customDimensions)
| where tostring(cd["gen_ai.operation.name"]) == "invoke_agent"
| summarize Runs  = count(),
            P50Ms = round(percentile(duration, 50)),
            P95Ms = round(percentile(duration, 95))
    by Agent   = tostring(cd["gen_ai.agent.name"]),
       Version = tostring(cd["gen_ai.agent.version"])
| order by Agent asc, Version asc
```

**3.9** [VERIFY] Two rows, one per agent per version. **This is the verified live result from
2026-08-08:**

| Agent | Version | Runs | P50Ms | P95Ms |
|---|---|---|---|---|
| `l10-support-agent` | 1 | 12 | 12263 | 18509 |
| `l11-orchestrator` | 1 | 6 | **1** | **4** |

**Runs counts scale with `--rounds`, so don't chase the exact number.** A 3-round run gives 12
and 6; the 6-round hydration on 2026-08-08 gave **36 and 18** with P50 10,791 and P95 18,509 on
the specialist, and 1 and 4 unchanged on the orchestrator. **The shape is what matters: the
specialist sits around ten to twelve seconds, the orchestrator sits at one millisecond.** That
gap is the teaching moment, and it holds at any sample size.

If your Runs column reads 12 and 6, your traffic run landed correctly. If it reads 20 and 10,
you used `--rounds 5`.

**3.10** [SAY] Success, latency, and cost, sliced per agent per version. Every instruction edit
makes a new version, so a prompt change becomes a measurable comparison instead of an argument
in a stand-up. But look at the second row, because that's the one that should stop you. My
specialist takes twelve seconds at the median and eighteen at the ninety-fifth. My orchestrator
takes one millisecond. One. No agent on earth reads a question, plans, calls a tool, and answers
in one millisecond. That number isn't fast, it's a failure, and it's failing before it does any
work at all. That's the 401 you watched in Beat 1 showing up as a performance metric. Learn to
read latency this way and you'll spot a broken agent from a dashboard without opening a single
log line.

### Query B -- did more than one agent participate?

**3.11** [DO] Run **Query B**, the one that matters:

```kusto
// B -- Traces where MORE THAN ONE agent participated
dependencies
| where timestamp > ago(24h)
| extend cd = parse_json(customDimensions)
| extend Agent = tostring(cd["gen_ai.agent.name"]),
         Op    = tostring(cd["gen_ai.operation.name"])
| where isnotempty(Op)
| summarize Agents  = make_set(Agent),
            Spans   = count(),
            TotalMs = round(sum(duration)),
            Start   = min(timestamp)
    by operation_Id
| where array_length(Agents) > 1
| order by Start desc
```

**3.12** [VERIFY] **Today this returns ZERO ROWS. That is the verified result, and it's
expected.** All 18 traces contain exactly one agent name each, because A2A delegation is still
throwing the 401 from Beat 1. The `where array_length(Agents) > 1` line filters every trace
out.

Handle it on camera in one line, then move on. Don't apologize and don't troubleshoot live:

**3.13** [SAY] Zero rows, and that's the finding. Every one of my eighteen traces has exactly
one agent in it, which tells me my delegation never actually happened, and I'd rather learn that
from a query than from a customer.

**3.14** [SAY] So hold on to what this query is for, because it's the one you'll write the day
you ship a supervisor. One request, one correlation ID, two agent names in the set. That's proof
the orchestrator delegated and the specialist did the work, and it's proof I get without trusting
a word of the answer text. You can't run this query against a single-agent system, which is
exactly why it belongs in this lesson and not back in Lesson 9. When my 401 clears, this table
fills in and nothing else about the query changes.

**3.15** [DO] Optional, and a nice save if you want a non-empty screen: drop the
`| where array_length(Agents) > 1` line and re-run.
[VERIFY] 18 rows come back, every one showing an `Agents` set of length 1. That's the same
evidence from the other direction, and it proves the query itself is sound.

### Query C -- error taxonomy

**3.16** [DO] Run **Query C**:

```kusto
// C -- Error taxonomy: sort failures by cause
dependencies
| where timestamp > ago(24h)
| extend cd = parse_json(customDimensions)
| extend Op = tostring(cd["gen_ai.operation.name"])
| where isnotempty(Op)
| extend Cause = case(
      success == false,                                                      "span failure",
      Op == "execute_tool" and isempty(tostring(cd["gen_ai.tool.call.result"])), "empty tool result",
      Op == "chat" and tostring(cd["gen_ai.response.finish_reasons"]) has "length", "truncated output",
      "ok")
| summarize Count = count() by Cause, Op
| order by Count desc
```

**3.17** [VERIFY] Four rows. **This is the verified live result from 2026-08-08:**

| Cause | Op | Count |
|---|---|---|
| ok | chat | 12 |
| ok | execute_tool | 12 |
| ok | invoke_agent | 12 |
| **span failure** | invoke_agent | **6** |

Every `ok` row is `l10-support-agent`. Every `span failure` row is `l11-orchestrator`. The
query as written doesn't show that, so either say it out loud or use the variant in 3.18.

**3.18** [DO] Optional, and worth the extra ten seconds on camera: add the agent name to the
summarize so the attribution is on screen rather than in your narration. Change the last two
lines to:

```kusto
| summarize Count = count() by Cause, Op, Agent = tostring(cd["gen_ai.agent.name"])
| order by Count desc
```

[VERIFY] Same four rows, now with an Agent column reading `l10-support-agent` on the three `ok`
rows and `l11-orchestrator` on the `span failure` row.

**3.19** [SAY] That's error analysis, and notice what it did for me. Six span failures, all of
them on `invoke_agent`, all of them on one agent. It found the broken thing and it named it, and
I never told the query what to look for. That failure is a real one too, not one I manufactured
for the camera -- it's the same 401 from Beat 1, sorted into a bucket by cause.

**3.20** [SAY] The buckets matter as much as the count. Four causes, four completely different
fixes. A span failure is an infrastructure or permissions problem. An empty tool result is a
retrieval problem, so you go look at your index. A truncated output is a token-ceiling problem.
Lump all three into one "errors" number on a dashboard and you've hidden every one of them.

**3.21** [SAY] And every confirmed failure becomes a labeled case in your evaluation set. That's
the flywheel, and it's how monitoring turns into improvement instead of just turning into
charts.

---

## If it breaks

| Symptom | Fix |
|---|---|
| Every query returns nothing | You're inside the 1 to 3 minute ingestion window, or traffic wasn't generated. Re-run `generate_traffic.py` from the L9 venv and wait 3 minutes. |
| Query B returns no rows | **Expected today.** A2A is throwing 401, so no trace holds two agent names. Use the beat 3.13 line and keep moving. Don't debug it on camera. |
| Columns come back blank, or KQL throws a syntax error | Wrong dialect. From the **`appi-ai103-l11`** resource use `dependencies` + `customDimensions`. From the **`log-ai103-l11`** workspace it's `AppDependencies` + `Properties`. |
| Query A shows Runs of 20 and 10, not 12 and 6 | You ran `--rounds 5`. Harmless, but your narration says twelve and six, so re-run at the default or change the words. |
| Query A shows only one agent | You ran with `--skip-orchestrator` (script lines 88 and 89). Re-run without it. |
| Orchestrator returns 401 in the playground | **Expected today.** Blocker 1. Shoot the Beat 1 fallback beats 1.12 to 1.16. |
| Approval doesn't pause | The runtime isn't enforcing it for this tool type. **That is the lesson.** Run the Beat 2 FALLBACK at 2.F1 to 2.F4. |
| No MCP tool on the specialist to configure | Lesson 10 shipped it with file search only. Add an MCP tool off camera per beat 2.0, or move the approval beat onto whichever tool this build lets you set `require_approval` on. |
| `python` isn't found, or imports fail | You're in the wrong environment. There's no venv in the L11 folder; run from `09-build-generative-apps-foundry\.venv`. |
| `generate_traffic.py` fails on auth | `az login` expired. Re-auth and re-run. The script wants the `https://ai.azure.com` audience, which is hardcoded at line 70. |

## Runtime

Roughly 19 to 21 minutes on the fallback path. If A2A is fixed and you shoot the live
delegation beats instead, add a minute for the round trip.
