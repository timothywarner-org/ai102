# 🎬 Lesson 3 Demo Runbook — Manage & Monitor AI Systems

> **Two surfaces only, all demo long:** 🌐 **Edge** (the portals) and 🧑‍💻 **VS Code** (the `ai103` project).
> **File under the mouse in VS Code:** `lessons/03-manage-monitor-secure-ai/m03_ops_demo.py`.
> **Read-only demo — nothing gets changed.**

---

## 🧭 Block legend (every step is one of these)

| Marker | Means | What you do |
| --- | --- | --- |
| 🎙️ **SAY** | Talk track | Read it aloud |
| 🖱️ **DO** | Click / run | Perform the action |
| ✅ **CHECK** | Expected result | Confirm it before moving on |
| ⏸️ **HOLD** | Pause for the edit | Stop talking, hold the shot |
| ⚠️ **IF IT BREAKS** | Recovery line | Narrate honestly, then move on |

> Markers are shapes **and** words, never color — read them by icon or by label, whichever lands first.

---

## 🗺️ The map — you move through these in order

| Step | Segment | Clip | Time | Surface |
| --- | --- | --- | --- | --- |
| 🎬 | Cold open | — | ~30s | 🎙️ |
| 0️⃣ | Deploy the model we'll watch | — | ~1m | 🌐 |
| 1️⃣ | Capacity + cost (two guardrails) | clip 04 | ~4m | 🌐 → 🧑‍💻 |
| 2️⃣ | Behavior (the Observability pipe) | clip 05 | ~3m | 🌐 → 🧑‍💻 |
| 3️⃣ | Data (index health + relevance) | clip 06 | ~3m | 🌐 → 🧑‍💻 |
| 🏁 | Close | — | ~30s | 🎙️ |

**Total: ~12 minutes.** The three big questions: **① capacity + cost · ② behavior · ③ data.**

---

## ✅ Pre-flight — before you hit record

- [ ] 🌐 Edge open, signed in, **two tabs**: `ai.azure.com` (Foundry) and `portal.azure.com` (Azure).
- [ ] 🧑‍💻 VS Code on the `ai103` workspace, `m03_ops_demo.py` visible, terminal ready.
- [ ] 🔑 `az login` done · `.env` filled · `uv sync` already run.
- [ ] 🔍 **Seed the index once:** `uv run python seed_index.py` — do it a few minutes ahead so document count reads **6**, not 0, on camera.
- [ ] 💵 **Warm the cost read once:** `uv run python m03_ops_demo.py --only cost` — gets you past any Cost Management **429** throttle before the camera rolls.
- [ ] 📡 *(Only if recording the 2️⃣ deepening)* `uv run python m03_generate_signal.py --calls 8` a few minutes ahead so traces have landed in `log-ai103-l03` (ingestion lags **2–5 min**).

---

## 🎬 COLD OPEN · ~30s

🎙️ **SAY:** In this demo we're going to keep an eye on a running Foundry solution, and I'll show you every signal in the two places you'll actually use: my browser in the portals, and VS Code in our project. It's the same three questions the exam keeps asking — do I have capacity and what does it cost, is the model behaving, and is my search data healthy and relevant — answered live. But first, we need something running to watch, so let's deploy a model.

---

## 0️⃣ DEPLOY THE MODEL WE'LL WATCH · ~1 min · *(redemption beat)*

> 📍 **Where:** 🌐 Foundry · 🎯 **Goal:** get gpt-5-mini running so there's something to monitor.

🎙️ **SAY:** Before we can monitor anything, we need something running to monitor, so let's deploy a model, and redeem a stumble from last lesson while we're at it. Last time, quota shut us down. This time I'm shopping for a model that actually has quota on this subscription, gpt-5-mini, and deploying that. The exact click path that failed on a zero-quota model now sails right through, because the fix for "no capacity" is always to pick a model, or a region, that has it.

🖱️ **DO:** 🌐 `ai.azure.com` → your project → **Models + endpoints** → **Deploy model** → pick **gpt-5-mini** → **Global Standard** → **Deploy**.

✅ **CHECK:** gpt-5-mini shows **State = Succeeded** (or it's already deployed from earlier).

⏸️ **HOLD** on the running deployment — this is the thing we're going to keep healthy.

⚠️ **IF IT BREAKS:** If a model still errors on quota, narrate it honestly — that IS the lesson: pick a model or region with granted quota, which is exactly why we're on gpt-5-mini.

---

## 1️⃣ CAPACITY + COST — THE TWO GUARDRAILS · clip 04 · ~4 min

> 📍 **Where:** 🌐 Foundry + Azure portal, then 🧑‍💻 code · 🎯 **Goal:** show headroom and spend, and the code that automates both.

### 1a · Capacity 🌐 → 🧑‍💻

🎙️ **SAY:** First question: do I have room to grow, and what is it costing me? Two guardrails, capacity and cost. Capacity first. In the Foundry portal, under Operate, then Quota, is where capacity lives. The Token per minute tab shows my standard deployments, and each line is a per-model allowance in a single region. The Provisioned throughput unit tab shows the PTUs I've reserved. When a line creeps toward its limit, that's my cue to scale — raise the TPM, add PTUs, or spread across regions — or file a Request Quota, which takes a couple of business days.

🖱️ **DO:** 🌐 `ai.azure.com` → **Operate** → **Quota** → **Token per minute** tab, then the **Provisioned throughput unit** tab.

✅ **CHECK:** At least one model's TPM allocation and its usage are visible.

🎙️ **SAY:** Now the very same read in code, so you could wire it straight into an alert instead of eyeballing a blade.

🖱️ **DO:** 🧑‍💻 `m03_ops_demo.py` → **`signal_quota`** (`# %%` cell, ~line 76) → **Shift+Enter**.

✅ **CHECK:** The terminal prints each model's TPM used over its limit, with a percent used.

### 1b · Cost 🌐 → 🧑‍💻

🎙️ **SAY:** Now the other guardrail: cost. Capacity says what I *can* do; cost says what I'm *paying*. I read month-to-date spend attributed by workload — which resource group, and one level deeper which deployment, is actually spending. That's the number you put an Azure budget on, with action-group alerts at thresholds, so you hear about overspend while there's still time. Two habits ride along: tag every resource so cost slices by owner, and cap output with max_tokens so one runaway prompt can't run up the bill.

🖱️ **DO:** 🌐 `portal.azure.com` → **Cost Management + Billing** → **Cost analysis**, grouped by **Resource group** → then 🧑‍💻 `m03_ops_demo.py` → **`signal_cost`** (`# %%` cell, ~line 106) → run it.

✅ **CHECK:** The terminal prints month-to-date cost per resource group and a total; the portal shows the same shape.

⏸️ **HOLD** two beats on the cost total for the zoom edit.

⚠️ **IF IT BREAKS:** A **429** means Cost Management is throttling — wait a minute and re-run just that cell. On a brand-new subscription the data can lag a day; narrate that honestly.

---

## 2️⃣ BEHAVIOR — THE OBSERVABILITY PIPE · clip 05 · ~3 min

> 📍 **Where:** 🌐 Foundry Monitoring, then 🧑‍💻 code · 🎯 **Goal:** show the Application Insights pipe and prove it's connected.

🎙️ **SAY:** Second question: is the model behaving once real users show up? Foundry pipes its monitoring into Application Insights, so latency, safety, and groundedness all land in one dashboard. Under Monitoring, the application analytics view is your single pane — token use, latency, and the quality scores that continuous evaluation writes back.

🖱️ **DO:** 🌐 `ai.azure.com` → your project → **Monitoring** → **Application analytics**.

✅ **CHECK:** The dashboard shows latency and token panels (data fills in once traffic flows).

🎙️ **SAY:** And here's that wiring proved from code: I fetch the project's Application Insights connection, the pipe that carries all of it.

🖱️ **DO:** 🧑‍💻 `m03_ops_demo.py` → **`signal_observability`** (`# %%` cell, ~line 157) → run it.

✅ **CHECK:** The terminal prints **"Application Insights: CONNECTED"** (the key is confirmed present, value hidden — we never print secrets on camera).

⏸️ **HOLD** on the CONNECTED line.

⚠️ **IF IT BREAKS:** If it says NOT connected, narrate it honestly — that IS the fix, connect Application Insights under Monitoring — and move on.

### 🔬 Optional deepening — prove the pipe *carries data* · +~2 min

🎙️ **SAY:** CONNECTED means the pipe is wired. But a wired pipe with nothing flowing is just plumbing, so let's put real traffic through it and then go catch it. This little script makes a handful of real gpt-5-mini calls, tags each one with OpenTelemetry, and ships the traces into that same Application Insights. Then it hands me the exact query to find them.

🖱️ **DO:** 🧑‍💻 terminal → `uv run python m03_generate_signal.py --calls 4 --content`.

✅ **CHECK:** Four calls print with real latency and token counts, then an **`OperationId`** and the KQL.

🎙️ **SAY:** Traces take two to five minutes to land, so this is the honest part of monitoring: you don't watch data arrive in real time. Once it's there, I run the query against the Log Analytics workspace and there's my run: a parent span and one child per model call, each with its latency and its token cost. That's the same data the Foundry dashboard draws on, read straight from the source.

🖱️ **DO:** 🌐 `ai.azure.com` → project → **Tracing** (or the workspace **Logs** blade) → paste the `OperationId` query the script printed.

✅ **CHECK:** The `chat gpt-5-mini` spans appear with `DurationMs` and, expanded, the `gen_ai.usage` token counts.

⏸️ **HOLD** on the dashboard rollup (call count, average latency, total tokens).

⚠️ **IF IT BREAKS:** Empty query result = the 2–5 min ingestion lag, not a failure. Say so and re-run the query. *(Pre-generate a batch before recording so rows are already waiting.)*

---

## 3️⃣ DATA — INDEX HEALTH + RELEVANCE · clip 06 · ~3 min

> 📍 **Where:** 🌐 Azure AI Search, then 🧑‍💻 code · 🎯 **Goal:** show the index is healthy and relevance is measured, not guessed.

🎙️ **SAY:** Third question: is the data behind retrieval healthy? A retrieval-augmented app is only as good as its index, and when an index quietly breaks, the answers get worse with no error at all. On the Search service I check two things: the index document count and storage, and the indexer's last run.

🖱️ **DO:** 🌐 `portal.azure.com` → your **Azure AI Search** service → **Indexes** (document count, storage), then **Indexers** (last run status).

✅ **CHECK:** The index shows a document count; the indexer shows a success, or a failure with a reason.

🎙️ **SAY:** Then the payoff signal, relevance, measured not assumed. I keep a small labeled query set — a gold set — where I already know the right answer for each query. The code runs each one and checks whether that right answer landed in the top results. That gives me recall on hard numbers, which is exactly how you diff a ranking change, or prove one helped, instead of trusting a hunch.

🖱️ **DO:** 🧑‍💻 `m03_ops_demo.py` → **`signal_search`** (`# %%` cell, ~line 179) → run it.

✅ **CHECK:** The terminal prints the document count, then **recall@3** per labeled query and a **mean recall**.

⏸️ **HOLD** on the mean recall line.

⚠️ **IF IT BREAKS:** If document count reads 0 right after seeding, that's the stats endpoint lagging — the query results are still correct; narrate it and move on.

---

## 🏁 CLOSE · ~30s

🎙️ **SAY:** Three questions, answered from the two surfaces you'll live in. Capacity and cost from Quota and Cost analysis, behavior from Application Insights, and index health and relevance from Search — the portal to see it, the code to automate it. That's how you keep a Foundry solution fast, safe, affordable, and grounded once real users show up. I'll see you in the next one.
