# AI-103 -- Lesson 11 Demo Runbook (Multi-Agent Orchestration + Approval Gates + Observability)

Folder: `lessons/11-build-agents-foundry/`. Keyless, so you sign in once with `az login`.
Runs against Foundry project `proj-agents` on account `aif-ai103-l11-*`, with
Application Insights `appi-ai103-l11` wired up for the observability beat.

**Three demo beats, mapped to the frozen objectives:**

| Beat | Script | Objective |
| --- | --- | --- |
| 1. Hand-off routing | `m11_multi_agent.py` | LO4 -- orchestrated multi-agent solutions |
| 2. Approval gate | `m11_approval_flow.py` | LO5 -- safeguards and approval flow controls |
| 3. Trace the hand-off | `kql/02-multi-agent-handoff.kql` | LO6 -- monitoring and error analysis |

Total on-camera time: roughly 18 to 22 minutes.

---

## Pre-flight (off camera)

1. `cd C:\github\ai103\lessons\11-build-agents-foundry`
2. `az login`
3. `uv sync`
4. `cp .env.example .env`, then fill in the three values. If the environment was rebuilt,
   the Bicep outputs give you all three verbatim:
   `az deployment group show -g rg-ai103-mvp -n l11-agents --query properties.outputs`
5. Smoke-test both demos so you're not discovering a cold-start stall on tape:
   `uv run python m11_multi_agent.py --dry-run` and `uv run python m11_approval_flow.py --dry-run`
6. Open these tabs, already signed in: **Foundry portal -> `proj-agents`**;
   **Application Insights `appi-ai103-l11` -> Logs**; VS Code on the lesson folder.
7. Run `m11_multi_agent.py` once about ten minutes before recording. That primes App Insights
   so Beat 3 has data the moment you need it, instead of you waiting out ingestion on camera.

**If the environment is gone entirely** (the resource group was deleted), rebuild it in one shot:

```powershell
az group create -n rg-ai103-mvp -l eastus2; az deployment group create -g rg-ai103-mvp -n l11-agents -f ../../infra/ai103-l11-agents.bicep -p userObjectId=$(az ad signed-in-user show --query id -o tsv)
```

Give that about five minutes, then copy the outputs into `.env`.

---

## Segment 1: Why one agent isn't enough (~3 min)

[SAY] Welcome back. Tim Warner here. In the last lesson we built a single agent and gave it
tools, and it did a nice job answering questions inside its own little world. Now in this lesson
I'm gonna teach you what happens when one agent isn't enough, and that's really two problems
wearing a trench coat. The first problem is routing, which just means figuring out which
specialist should handle a request. The second problem is control, which means deciding whether
a given action should be allowed to happen at all. Those sound similar, and they're genuinely
different, so we're gonna build both.

[SAY] This assumes you've already got a Foundry project deployed, you've got a chat model
deployment sitting behind it, you've signed in with az login, and you're ready to rock and roll.
Everything in this lesson runs keyless off that az login identity, so there's not an API key
anywhere in this folder.

[DO] VS Code, lesson folder open. Show `m11_multi_agent.py` in the editor, scrolled to the
`TRIAGE_INSTRUCTIONS` / `BILLING_INSTRUCTIONS` / `SUPPORT_INSTRUCTIONS` block.

[SAY] Here's the pattern we're building, and it's called a hand-off. We've got three specialists
sitting behind one front door. Triage reads the incoming request and routes it, and notice that
triage answers absolutely nothing itself. Billing handles money, support handles outages, and
neither of those two ever talks to the customer directly or to each other. They answer, and then
they stop.

[SAY] Now look closely at these instruction strings, because this is the part people get wrong.
In a hand-off workflow, the instructions aren't flavor text. They're the routing logic. The model
reads each participant's instructions to decide where a request belongs, so when your
instructions are vague, you don't get a polite agent, you get a wrong hand-off.

[PAUSE] Clean seam before the first run.

---

## Segment 2: Beat 1 -- watch the routing happen (~5 min)

[DO] Terminal: `uv run python m11_multi_agent.py --dry-run`

[SAY] Let me start with the dry run, because it draws the topology and makes zero Azure calls.
That's my favorite way to open a demo, since I can show you the shape of the thing before I spend
a single token on it.

[VERIFY] ASCII topology renders: triage at the top, billing and support beneath it.

[DO] Terminal: `uv run python m11_multi_agent.py`

[SAY] And now we'll run it for real against three different customer requests.

[PAUSE] The three scenarios take roughly ninety seconds end to end. Let it run, or cut and
resume on the routing summary if you want a tighter edit.

[VERIFY] All three scenarios print `[as expected]`, and the final line reads
`Routing accuracy: 3/3 requests reached the right specialist.`

[SAY] Notice what happened on each request. The customer asked about invoice INV-77, triage
handed off to billing, and billing called its lookup tool and answered. Then somebody complained
the portal was slow, and that one went to support instead. Same front door, completely different
specialist, and nobody hardcoded a keyword match anywhere in that code.

[SAY] Now here's the third one, and this is the one I actually care about. I deliberately asked
about invoice INV-999, which doesn't exist. Look at the answer: the agent says it can't find that
invoice and asks the customer to double-check the number. It didn't invent an amount. That
happened because the tool returns a structured error instead of raising an exception, so the
model has something honest to report. When you're building agents that touch financial data,
that distinction is the whole ball game.

[SAY] Now you might be thinking, hang on Tim, couldn't I just write an if-statement to route
these three cases? For three cases, sure, absolutely you could. The reason this pattern earns its
keep is that each agent decides its own next hop, so adding a fourth specialist means adding one
participant, and it doesn't mean editing a routing table that grows forever. That's the value
proposition of decentralized routing.

[IF IT BREAKS] If a scenario routes somewhere unexpected, that's a live illustration of the
instruction-quality point, so narrate it honestly and re-run. If you get a rate-limit error,
say so plainly and re-run; the model deployment is provisioned at 50K TPM with headroom for this.

[PAUSE] Hold two beats on the 3/3 line for the zoom edit.

---

## Segment 3: Beat 2 -- the approval gate (~6 min)

[SAY] So routing is solved. Now let's talk about control, because routing a request to the right
specialist doesn't say one word about whether that specialist should be allowed to pull the
trigger. An autonomous agent runs every tool it decides to run. A semiautonomous agent stops at a
gate and waits for a human, and that gate is what we're building right now.

[DO] Open `m11_approval_flow.py`. Scroll to the two `@tool` decorators so both are on screen.

[SAY] And here's the money, and it's one parameter. Every tool in this course so far has been
declared approval mode never require, which is exactly why they just run. Look at
`refund_invoice` though, because that one's declared always require. Flip that one parameter and
the framework stops before it executes the function, and it hands control back to your code
instead.

[SAY] Notice where that gate actually sits. It isn't a line in the system prompt asking the model
to please be careful, and it isn't a check inside the function body that a tool author might
forget to write. The executor refuses to invoke the function until an approval response comes
back. The model can't talk its way past it, and that's the difference between a safeguard and a
suggestion.

[DO] Terminal: `uv run python m11_approval_flow.py`

[PAUSE] Three scenarios, roughly two minutes. Cut and resume on the first `[GATE]` line if
you want a tighter edit.

[VERIFY] Scenario 1 shows `[GATE]` then `[HUMAN] APPROVED`, and the state line ends `'status':
'refunded'`. Scenario 2 shows the identical gate line, then `[HUMAN] DENIED`, and the state line
still reads `'status': 'paid'`.

[SAY] Now watch this, because the contrast is the entire lesson. In the first scenario the gate
fires, I approve it, the refund executes, and INV-81 comes back marked refunded. In the second
scenario the customer asks for the exact same thing, the model requests the exact same call with
the exact same arguments, I deny it, and the invoice is still sitting there marked paid. Same
request, same agent, same model. The only variable in that whole run was the human standing at
the gate.

[SAY] And notice the third scenario doesn't stop at all. That's a read-only question, it hits
the ungated lookup tool, and it just answers. That matters, because if you gate every single
tool you've built yourself a very slow chatbot. Gate nothing and you've built an agent that can
issue refunds at three in the morning. You risk-tier your tools, and reads run unattended while
writes stop for a human.

[SAY] One more detail worth your attention, and it's the kind of thing that'll bite you on a
reasoning model. Look at the gate line: it prints the tool name AND the arguments. Approve
refund invoice, question mark, isn't consent. Approve refund invoice for INV-81 in the amount of
ninety-nine dollars, that's consent. Always show the human what they're actually approving.

[IF IT BREAKS] If you want to drive the gate by hand instead of using the scripted verdicts,
run `uv run python m11_approval_flow.py --interactive` and type y or n at each prompt.

[PAUSE] Clean seam before the observability beat.

---

## Segment 4: Beat 3 -- follow one request across three agents (~5 min)

[SAY] With that, we've got orchestration working and we've got control working. Now let's make
the whole thing observable, because an agent you can't trace is an agent you can't debug, and
that's true right up until the moment somebody asks you why the bill looks the way it does.

[DO] Browser: Application Insights `appi-ai103-l11` -> Logs.
[DO] VS Code: open `kql/02-multi-agent-handoff.kql` and copy the query.

[SAY] The demo wires OpenTelemetry to Application Insights, so one run emits spans for invoking
each agent, executing each tool, and processing each executor. Here's the part that makes
orchestration traceable: every agent in a single hand-off shares one operation ID.

[DO] Paste the query into the Logs pane. Run it.

[VERIFY] Three rows return. The `agents` column shows `["triage","billing","support"]`, and the
`tools` column shows `lookup_invoice` or `check_service_health`.

[SAY] And there it is. Each row is one customer request, and look at that agents column, because
all three participants are right there in a single trace. That's how you follow a request across
a hand-off instead of staring at three disconnected logs and trying to line them up by timestamp.

[SAY] Now I want you to notice the filter at the bottom of that query, where it keeps only traces
with more than one distinct agent. That's deliberate. If you run this query and you get nothing
back, that's not an empty result, that's a diagnosis: it means your agents ran without
distributed tracing wired up correctly. When this query returns rows, your multi-agent telemetry
is genuinely correct.

[DO] Optionally run `kql/01-agent-kpis.kql` and `kql/03-error-taxonomy.kql`.

[SAY] The other two queries in that folder round out the story. The KPI query tells you which
agent is slow and which one is failing, and the error taxonomy query groups what's going wrong by
kind. Remember that third scenario, the invoice that didn't exist? That's the one that gives the
error query something real to classify.

[IF IT BREAKS] If the Logs pane comes back empty, you're inside the one-to-three-minute
ingestion delay, so say that on camera and refresh. That's exactly why you ran the demo once
before recording.

[PAUSE] Hold on the results grid for the zoom edit.

---

## Segment 5: Recap and close (~2 min)

[SAY] Let me give you the one two three on this lesson. Number one, orchestration answers which
agent should handle this request, and HandoffBuilder gives you decentralized routing where each
agent picks its own next hop. Number two, approval gates answer whether this action should happen
at all, and that's one parameter on the tool decorator, enforced by the executor rather than
suggested in a prompt. Number three, observability ties the whole thing together, because every
agent in one hand-off shares an operation ID and that's what lets you follow a single request
across all of them.

[SAY] The thing I really want you to carry out of this lesson is that middle one. It's genuinely
tempting to write "never issue a refund without permission" in your system prompt and call it
done. That's a suggestion to a model that's very good at finding reasons. Declaring the tool
always require is a control, and the difference between those two shows up on the day it
actually matters.

[SAY] I hope you found this lesson helpful. I'll see you next time.

---

## Notes for the editor

- Both Python demos create **no Azure resources** and move no real money, so they're safe to
  re-run as many times as a take requires. The refund only mutates an in-memory dictionary.
- `m11_approval_flow.py` runs each scenario in a fresh `AgentSession`. Don't refactor that into
  a shared session, because the scenarios would carry each other's conversation forward.
- The approval demo targets **INV-81**, which is seeded as `paid` on purpose. An earlier cut
  aimed at the unpaid INV-77, and the model correctly refused to call the refund tool at all,
  so the gate never fired. Correct model behavior, useless demo.
- Expect roughly 70 dependency spans in App Insights per full `m11_multi_agent.py` run.
