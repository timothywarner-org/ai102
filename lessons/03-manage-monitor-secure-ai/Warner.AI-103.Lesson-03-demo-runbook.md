# Lesson 3 Demo Runbook -- Manage and Monitor AI Systems

**On screen, only two surfaces:** Edge in the portals, and VS Code in the `ai103` project.
**File under the mouse in VS Code:** `lessons/03-manage-monitor-secure-ai/m03_ops_demo.py`.
Read-only demo -- nothing gets changed. Blocks: **[SAY]** what I say - **[DO]** what I click - **[VERIFY]** - **[PAUSE]**.

## Pre-flight (before recording)
- Edge open, signed in, two tabs: **ai.azure.com** (Foundry) and **portal.azure.com** (Azure).
- VS Code open on the `ai103` workspace, `m03_ops_demo.py` visible, integrated terminal ready.
- `az login` done; `.env` filled in; `uv sync` already run.
- **Search index seeded once**: run `seed_index.py` so `ai103-l03-demo` exists with its gold docs. Do this a few minutes ahead so the index stats have refreshed (document count reads 6, not 0, on camera).
- **Warm the cost read** once before recording (run `--only cost`) so you're past any Cost Management 429 throttle when the camera rolls.
- **(Only if recording the LO2 deepening)** run `m03_generate_signal.py --calls 8` a few minutes ahead so traces have already landed in `log-ai103-l03` when you query on camera (ingestion lags 2 to 5 minutes).

---

## Cold open  (~30s)

[SAY] In this demo we're going to keep an eye on a running Foundry solution, and I'll show you every signal in the two places you'll actually use: my browser in the portals, and VS Code in our project. It's the same three questions the exam keeps asking -- do I have capacity and what does it cost, is the model behaving, and is my search data healthy and relevant -- answered live. But first, we need something running to watch, so let's deploy a model.

---

## Segment 0: Deploy the model we'll watch  (~1 min, redemption)

[SAY] Before we can monitor anything, we need something running to monitor, so let's deploy a model, and redeem a stumble from last lesson while we're at it. Last time, quota shut us down. This time I'm shopping for a model that actually has quota on this subscription, gpt-5-mini, and deploying that. The exact click path that failed on a zero-quota model now sails right through, because the fix for "no capacity" is always to pick a model, or a region, that has it.

[DO] **Edge > ai.azure.com** > your project > **Models + endpoints** > **Deploy model** > pick **gpt-5-mini** > **Global Standard** > **Deploy**.
[VERIFY] gpt-5-mini shows **State = Succeeded** (or it's already deployed from earlier).

[PAUSE] Hold on the running deployment -- this is the thing we're going to keep healthy.
[IF IT BREAKS] If a model still errors on quota, narrate it honestly: that IS the lesson -- pick a model or region with granted quota, which is exactly why we're on gpt-5-mini.

---

## Segment 1: Capacity and cost -- the two guardrails  (LO1 / clip 04, ~4 min)

[SAY] First question: do I have room to grow, and what is it costing me? Two guardrails, capacity and cost. Capacity first. In the Foundry portal, under Operate, then Quota, is where capacity lives. The Token per minute tab shows my standard deployments, and each line is a per-model allowance in a single region. The Provisioned throughput unit tab shows the PTUs I've reserved. When a line creeps toward its limit, that's my cue to scale -- raise the TPM, add PTUs, or spread across regions -- or file a Request Quota, which takes a couple of business days.

[DO] **Edge > ai.azure.com** > **Operate** > **Quota** > **Token per minute** tab, then the **Provisioned throughput unit** tab.
[VERIFY] At least one model's TPM allocation and its usage are visible.

[SAY] Now the very same read in code, so you could wire it straight into an alert instead of eyeballing a blade.

[DO] **VS Code** > `m03_ops_demo.py` > **line 76** (`signal_quota`) > run that cell with **Shift+Enter**.
[VERIFY] The terminal prints each model's TPM used over its limit, with a percent used.

[SAY] Now the other guardrail: cost. Capacity says what I *can* do; cost says what I'm *paying*. I read month-to-date spend attributed by workload -- which resource group, and one level deeper which deployment, is actually spending. That's the number you put an Azure budget on, with action-group alerts at thresholds, so you hear about overspend while there's still time. Two habits ride along: tag every resource so cost slices by owner, and cap output with max_tokens so one runaway prompt can't run up the bill.

[DO] **Edge > portal.azure.com** > **Cost Management + Billing** > **Cost analysis**, grouped by **Resource group** (the portal view), then **VS Code** > `m03_ops_demo.py` > **line 106** (`signal_cost`) > run that cell.
[VERIFY] The terminal prints month-to-date cost per resource group and a total; the portal shows the same shape.

[PAUSE] Hold two beats on the cost total for the zoom edit.
[IF IT BREAKS] A 429 means Cost Management is throttling -- wait a minute and re-run just that cell. On a brand-new subscription the data can lag a day; narrate that honestly.

---

## Segment 2: Behavior -- the Observability pipe  (LO2 / clip 05, ~3 min)

[SAY] Second question: is the model behaving once real users show up? Foundry pipes its monitoring into Application Insights, so latency, safety, and groundedness all land in one dashboard. Under Monitoring, the application analytics view is your single pane -- token use, latency, and the quality scores that continuous evaluation writes back.

[DO] **Edge > ai.azure.com** > your project > **Monitoring** > **Application analytics**.
[VERIFY] The dashboard shows latency and token panels (data fills in once traffic flows).

[SAY] And here's that wiring proved from code: I fetch the project's Application Insights connection, the pipe that carries all of it.

[DO] **VS Code** > `m03_ops_demo.py` > **line 157** (`signal_observability`) > run that cell.
[VERIFY] The terminal prints "Application Insights: CONNECTED" with an instrumentation key.

[PAUSE] Hold on the CONNECTED line.
[IF IT BREAKS] If it says NOT connected, narrate it honestly -- that IS the fix, connect Application Insights under Monitoring -- and move on.

### Optional deepening: prove the pipe carries data (~2 min)

[SAY] CONNECTED means the pipe is wired. But a wired pipe with nothing flowing is just plumbing, so let's put real traffic through it and then go catch it. This little script makes a handful of real gpt-5-mini calls, tags each one with OpenTelemetry, and ships the traces into that same Application Insights. Then it hands me the exact query to find them.

[DO] **VS Code** > integrated terminal > `uv run python m03_generate_signal.py --calls 4 --content`.
[VERIFY] The terminal prints four calls with real latency and token counts, then an `OperationId` and the KQL.

[SAY] Traces take two to five minutes to land, so this is the honest part of monitoring: you don't watch data arrive in real time. Once it's there, I run the query against the Log Analytics workspace and there's my run: a parent span and one child per model call, each with its latency and its token cost. That's the same data the Foundry dashboard draws on, read straight from the source.

[DO] **Edge > ai.azure.com** > project > **Tracing** (or the workspace **Logs** blade) > paste the `OperationId` query the script printed.
[VERIFY] The `chat gpt-5-mini` spans appear with `DurationMs` and, expanded, the `gen_ai.usage` token counts.

[PAUSE] Hold on the dashboard rollup (call count, average latency, total tokens).
[IF IT BREAKS] If the query returns nothing, it's the two-to-five-minute ingestion lag, not a failure -- say so and re-run the query. (Pre-generate a batch before recording so rows are already waiting.)

---

## Segment 3: Data -- index health and relevance  (LO3 / clip 06, ~3 min)

[SAY] Third question: is the data behind retrieval healthy? A retrieval-augmented app is only as good as its index, and when an index quietly breaks, the answers get worse with no error at all. On the Search service I check two things: the index document count and storage, and the indexer's last run.

[DO] **Edge > portal.azure.com** > your **Azure AI Search** service > **Indexes** (document count, storage), then **Indexers** (last run status).
[VERIFY] The index shows a document count; the indexer shows a success, or a failure with a reason.

[SAY] Then the payoff signal, relevance, measured not assumed. I keep a small labeled query set -- a gold set -- where I already know the right answer for each query. The code runs each one and checks whether that right answer landed in the top results. That gives me recall on hard numbers, which is exactly how you diff a ranking change, or prove one helped, instead of trusting a hunch.

[DO] **VS Code** > `m03_ops_demo.py` > **line 179** (`signal_search`) > run that cell.
[VERIFY] The terminal prints the document count, then recall@3 per labeled query and a mean recall.

[PAUSE] Hold on the mean recall line.
[IF IT BREAKS] If document count reads 0 right after seeding, that's the stats endpoint lagging -- the query results are still correct; narrate it and move on.

---

## Close  (~30s)

[SAY] Three questions, answered from the two surfaces you'll live in. Capacity and cost from Quota and Cost analysis, behavior from Application Insights, and index health and relevance from Search -- the portal to see it, the code to automate it. That's how you keep a Foundry solution fast, safe, affordable, and grounded once real users show up. I'll see you in the next one.
