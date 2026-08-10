# AI-103 -- Lesson 10 Demo Runbook (Tool Schemas + Function Calling + Conversation Memory)

Folder: `lessons/10-build-agents-foundry/`. Keyless, so you sign in once with `az login`.
Runs against Foundry project `proj-agents` on account `aif-ai103-l11-*`, the same environment
Lesson 11 uses.

**Two demo beats, mapped to the frozen objectives:**

| Beat | Script | Objective |
| --- | --- | --- |
| 1. The slow walkthrough | `function_calling.py` | LO1 -- tool schemas |
| 2. The interactive REPL | `m10_tools_repl.py` | LO2 -- function calling + conversation memory |

Total on-camera time: roughly 16 to 20 minutes.

**The one idea this lesson has to land:** the model never runs your code. It reads your tool
schema, decides which tool fits, and emits a *request* to call it. Your process executes the
function and hands the result back. Every beat below puts that boundary on screen.

---

## Pre-flight (off camera)

1. `cd C:\github\ai103\lessons\10-build-agents-foundry`
2. `az login`
3. `uv sync`
4. `cp .env.example .env`, then fill in the endpoint and model deployment name. This lesson
   shares the L11 environment, so the Bicep outputs give you both values:
   `az deployment group show -g rg-ai103-mvp -n l11-agents --query properties.outputs`
5. Smoke-test both demos so a cold start isn't the first thing on tape:
   `uv run python function_calling.py --dry-run` and `uv run python m10_tools_repl.py --dry-run`
6. Widen the terminal font. The REPL prints `[call]`, `[exec]`, `[turn]`, `[stop]`, and `[usage]`
   lines that need to be legible without a zoom edit.
7. Have `m10_tools_repl.py` open in VS Code, scrolled to the three `@tool` functions.

**If the environment is gone entirely,** rebuild it with the L11 Bicep, which provisions the
shared account and project both lessons use:

```powershell
az group create -n rg-ai103-mvp -l eastus2; az deployment group create -g rg-ai103-mvp -n l11-agents -f ../../infra/ai103-l11-agents.bicep -p userObjectId=$(az ad signed-in-user show --query id -o tsv)
```

---

## Segment 1: The boundary nobody draws correctly (~3 min)

[SAY] Welcome back. Tim Warner here. In this lesson I'm gonna teach you how agents actually use
tools, and I want to start by correcting the mental model most people walk in with. When you give
an agent a tool, the model doesn't run your function. It never touches your code. What actually
happens is the model reads a schema describing your function, decides that function fits the
question, and then emits a request asking your process to run it. Your code runs it, hands the
result back, and the model composes an answer from what you returned.

[SAY] This assumes you've got a Foundry project deployed, a chat model deployment behind it,
you've signed in with az login, and you're ready to rock and roll. Everything here is keyless off
that az login identity, so there's not an API key anywhere in this folder.

[DO] VS Code: `m10_tools_repl.py`, scrolled to the three `@tool` decorated functions.

[SAY] Now notice I've given this agent three tools, and I chose them very deliberately, because
one tool would prove absolutely nothing. With a single tool there's nothing to select between, so
you can't tell whether the model is reasoning or just doing the only thing available to it. So
we've got `add`, which takes two required numbers and is the plain baseline. We've got
`convert_money`, which puts an enum on the currency codes. And we've got `get_ticket_status`,
which has an optional parameter with a default sitting next to a required one.

[SAY] And here's why that middle one matters. That enum on the currency codes isn't decoration,
it's a guardrail. By declaring the valid values in the schema, you prevent an entire class of
runtime error before the model ever emits the call. That's the value proposition of a good tool
schema: you're not just describing your function, you're constraining what can be asked of it.

[PAUSE] Clean seam before the first run.

---

## Segment 2: Beat 1 -- the slow walkthrough (~6 min)

[DO] Terminal: `uv run python function_calling.py --dry-run`

[SAY] Let me start with the dry run, because it prints the actual tool schema and makes zero
Azure calls. What you're looking at is the JSON Schema the model receives, and notice it was
generated from the Python function signature by that `@tool` decorator. I didn't hand-write it.

[SAY] Now you might be thinking, hang on Tim, I've hand-written these JSON schemas before and it
wasn't that bad. Sure, and then you renamed a parameter and forgot to update the schema, and now
your model is confidently calling a function with an argument that doesn't exist. Generating the
schema from the signature means the code and the schema can't drift apart. That's the single most
common bug in rolled-your-own function calling, and this decorator makes it structurally
impossible.

[VERIFY] Schema prints with `ticket_id` in `required` and `detail` carrying a default.

[DO] Terminal: `uv run python function_calling.py`

[PAUSE] The run takes roughly twenty seconds. Let it finish.

[VERIFY] Five numbered beats print in order, ending with the composed answer about ticket CS-1042.

[SAY] Watch the five beats here, because this is the whole loop at half speed. Beat one, we send
the question and the schema. Beat two, the model comes back and it hasn't answered anything, it
has requested a call. Beat three, our code executes against our dictionary, in our process. Beat
four is the one I really want you to look at.

[DO] Point at the beat 4 block: `shape`, `call.call_id`, `result.call_id`, `finish_reason`,
`status`, and the token counts.

[SAY] Look at the call ID on the request and the call ID on the result, because they match. That
pairing is how the framework knows which result belongs to which call, and it matters the moment
a model requests two tools in one turn. Then look at `call.arguments`, and notice that's a JSON
string, not a Python dictionary. People trip over that constantly when they're parsing responses
by hand.

[SAY] And here's the money, down in the token counts: hidden reasoning tokens. Those are billed
as output and they count against your output cap, even though they never appear in the answer the
user reads. If you're budgeting tokens for an agent and you're only counting the visible response,
your numbers are gonna be wrong.

[IF IT BREAKS] The turn shape genuinely varies run to run, because `text_reasoning` items appear
wherever the model stopped to think. The `function_call -> function_result` spine is the reliable
part. If the shape reads differently than the last take, that's real behavior, so narrate it.

[PAUSE] Hold on the beat 4 block for the zoom edit.

---

## Segment 3: Beat 2 -- tool selection, live (~7 min)

[DO] Terminal: `uv run python m10_tools_repl.py`

[SAY] Now let's make this interactive, because I want you to watch the model choose. This is a
console agent with those same three tools, and every turn prints the request, the execution, and
the stop code as it happens.

[DO] Type: `:tools`

[SAY] There are our three tools. And if you want to see exactly what the model receives for any
one of them, `:schema` plus the name prints the real spec read off the live tool object, so
what's on screen is genuinely what goes on the wire.

[DO] Type these four, one at a time, letting each answer land:
```
what is 17.5 plus 4.25
convert 50 USD to EUR
what is the status of CS-1042
who wrote the novel Dune
```

[VERIFY] First three each print a `[call]` line naming the matching tool. The fourth prints
`[call] none selected -- no schema matched this question`.

[SAY] So the first three did exactly what you'd expect. Arithmetic went to `add`, currency went
to `convert_money`, and the ticket lookup went to `get_ticket_status`. Notice the
`convert_money` call came back with the currencies as separate arguments, parsed right out of my
plain English sentence.

[SAY] Now that fourth one is the one I really wanted you to see, and it's the case learners
consistently underestimate. I asked who wrote Dune, and look at the call line: nothing fired. No
schema matched, so the model just answered from what it already knows. That's correct behavior,
and it's worth demonstrating deliberately, because there's a persistent assumption out there that
handing an agent tools means it'll always reach for one. It won't. It selects, and sometimes the
right selection is none of them.

[PAUSE] Clean seam before the memory beat.

[SAY] With that, let's talk about conversation memory, because tool calling gets all the
attention and memory is what makes it feel like an agent instead of a calculator.

[DO] Type these three, one at a time:
```
what is 8 plus 9
now add 100 to that
what did I ask you first
```

[VERIFY] Second turn calls `add` with 17 and 100, returning 117. Third turn recalls the original
arithmetic question without calling a tool.

[SAY] Notice what happened on that second turn. I said "add 100 to that," and I never told it
what "that" was. It called `add` with seventeen and one hundred, because it still had the
previous turn in context. And then on the third turn it told me what I'd asked first, without
calling a tool at all, because that answer was already sitting in the conversation.

[DO] Type: `:reset`
[DO] Type: `what did I ask you first`

[VERIFY] The agent reports that this is the only question asked so far in the conversation.

[SAY] And there's the proof. After the reset, it genuinely has no idea what I asked before,
because it's telling me the question I just typed is the only one it's seen. That's exactly what
we want to see, and it confirms the memory in the previous turns was real work rather than the
model being clever.

[IF IT BREAKS] If a tool selection surprises you, run `:verbose` and re-ask. The full response
dump shows what the model actually received and returned.

[DO] Type: `:quit`

---

## Segment 4: Recap and close (~2 min)

[SAY] Let me give you the one two three on this lesson. Number one, the model never runs your
code, it reads a schema and requests a call, and your process does the executing. Number two, the
schema is generated from your function signature, so the code and the schema can't drift apart,
and the constraints you put in that schema, like that currency enum, are guardrails that stop bad
calls before they happen. Number three, tool selection is a real decision, and sometimes the
right answer is to select nothing at all.

[SAY] The thing I want you to carry forward is that boundary between requesting and executing.
That's not a detail of this SDK, that's the shape of every function-calling system you'll build,
and in the next lesson we're gonna put a gate right on that seam and make a human approve what
crosses it.

[SAY] I hope you found this lesson helpful. I'll see you next time.

---

## Notes for the editor

- Both demos create **no Azure resources**, so they're safe to re-run as many times as a take
  requires. There's nothing to clean up.
- The turn shape (`text_reasoning` placement) varies between runs. The
  `function_call -> function_result` spine doesn't.
- REPL commands: `:tools`, `:schema [name]`, `:verbose`, `:reset`, `:help`, `:quit`.
- `provision_knowledge.py` and `ask.py` are supporting scripts and aren't part of this recording.
- `node-demo/` is a Bot Framework scaffold carried over from the restructure. It's not a finished
  demo, so leave it out of the lesson.
