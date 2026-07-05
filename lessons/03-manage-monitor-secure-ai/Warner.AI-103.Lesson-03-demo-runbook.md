# Lesson 3 Demo Runbook -- Manage and Monitor AI Systems

**On screen, only two surfaces:** Edge in the portals, and VS Code in the `ai103` project.
**File under the mouse in VS Code:** `lessons/03-manage-monitor-secure-ai/m03_ops_demo.py`.
Read-only demo -- nothing gets changed. Blocks: **[SAY]** what I say - **[DO]** what I click - **[VERIFY]** - **[PAUSE]**.

## Pre-flight (before recording)
- Edge open, signed in, two tabs: **ai.azure.com** (Foundry) and **portal.azure.com** (Azure).
- VS Code open on the `ai103` workspace, `m03_ops_demo.py` visible, integrated terminal ready.
- `az login` done; `.env` filled in; `uv sync` already run.

---

## Cold open  (~30s)

[SAY] In this demo we're going to keep an eye on a running Foundry solution, and I'll show you every signal in the two places you'll actually use: my browser in the portals, and VS Code in our project. It's the same three questions the exam keeps asking -- do I have capacity, is the model behaving, and is my search index healthy -- answered live. But first, we need something running to watch, so let's deploy a model.

---

## Segment 0: Deploy the model we'll watch  (~1 min, redemption)

[SAY] Before we can monitor anything, we need something running to monitor, so let's deploy a model, and redeem a stumble from last lesson while we're at it. Last time, quota shut us down. This time I'm shopping for a model that actually has quota on this subscription, gpt-5-mini, and deploying that. The exact click path that failed on a zero-quota model now sails right through, because the fix for "no capacity" is always to pick a model, or a region, that has it.

[DO] **Edge > ai.azure.com** > your project > **Models + endpoints** > **Deploy model** > pick **gpt-5-mini** > **Global Standard** > **Deploy**.
[VERIFY] gpt-5-mini shows **State = Succeeded** (or it's already deployed from earlier).

[PAUSE] Hold on the running deployment -- this is the thing we're going to keep healthy.
[IF IT BREAKS] If a model still errors on quota, narrate it honestly: that IS the lesson -- pick a model or region with granted quota, which is exactly why we're on gpt-5-mini.

---

## Segment 1: Capacity -- quota headroom  (LO1, ~3 min)

[SAY] First question: do I have room to grow? In the Foundry portal, under Operate, then Quota, is where capacity lives. The Token per minute tab shows my standard deployments, and each line is a per-model allowance in a single region. The Provisioned throughput unit tab shows the PTUs I've reserved. When a line creeps toward its limit, that's my cue to scale -- raise the TPM, add PTUs, or spread across regions -- or file a Request Quota, which takes a couple of business days.

[DO] **Edge > ai.azure.com** > **Operate** > **Quota** > **Token per minute** tab, then the **Provisioned throughput unit** tab.
[VERIFY] At least one model's TPM allocation and its usage are visible.

[SAY] Now the very same read in code, so you could wire it straight into an alert instead of eyeballing a blade.

[DO] **VS Code** > `m03_ops_demo.py` > **line 72** (`signal_quota`) > run that cell (through line 99) with **Shift+Enter**.
[VERIFY] The terminal prints each model's TPM used over its limit, with a percent used.

[PAUSE] Hold two beats on the percentages for the zoom edit.

---

## Segment 2: Behavior -- the Observability pipe  (LO2, ~3 min)

[SAY] Second question: is the model behaving once real users show up? Foundry pipes its monitoring into Application Insights, so latency, safety, and groundedness all land in one dashboard. Under Monitoring, the application analytics view is your single pane -- token use, latency, and the quality scores that continuous evaluation writes back.

[DO] **Edge > ai.azure.com** > your project > **Monitoring** > **Application analytics**.
[VERIFY] The dashboard shows latency and token panels (data fills in once traffic flows).

[SAY] And here's that wiring proved from code: I fetch the project's Application Insights connection, the pipe that carries all of it.

[DO] **VS Code** > `m03_ops_demo.py` > **line 102** (`signal_observability`) > run that cell.
[VERIFY] The terminal prints "Application Insights: CONNECTED" with an instrumentation key.

[PAUSE] Hold on the CONNECTED line.
[IF IT BREAKS] If it says NOT connected, narrate it honestly -- that IS the fix, connect Application Insights under Monitoring -- and move on.

---

## Segment 3: Data -- index health and relevance  (LO3, ~3 min)

[SAY] Third question: is the data behind retrieval healthy? A retrieval-augmented app is only as good as its index, and when an index quietly breaks, the answers get worse with no error at all. On the Search service I check two things: the index document count and storage, and the indexer's last run.

[DO] **Edge > portal.azure.com** > your **Azure AI Search** service > **Indexes** (document count, storage), then **Indexers** (last run status).
[VERIFY] The index shows a document count; the indexer shows a success, or a failure with a reason.

[SAY] Then the payoff signal, relevance. I run one query from code and read the top search score, which is how you catch a ranking regression on hard numbers instead of a hunch.

[DO] **VS Code** > `m03_ops_demo.py` > **line 124** (`signal_search`) > run that cell.
[VERIFY] The terminal prints the document count, the indexer status, and the top @search.score values.

[PAUSE] Hold on the scores.

---

## Close  (~30s)

[SAY] Three questions, three answers, all from the two surfaces you'll live in. Capacity from Quota, behavior from Application Insights, and index health from Search -- the portal to see it, the code to automate it. That's how you keep a Foundry solution fast, safe, and grounded once real users show up. I'll see you in the next one.
