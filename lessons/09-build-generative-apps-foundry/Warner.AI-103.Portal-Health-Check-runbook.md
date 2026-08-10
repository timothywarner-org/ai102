# AI-103 -- Portal Health Check: Instrumentation and Vector Index

Click-by-click verification of the live environment. No talk track, no theory --
this is the "prove it works before you hit record" checklist.

Everything below is written against **your actual resources**, verified live:

| Thing | Name |
|---|---|
| Subscription | `92fd53f2-c38e-461a-9f50-e1ef3382c54c` |
| Resource group | `rg-ai103-mvp` |
| Foundry account / project | `aif-ai103-mvp-gcn5uizg` / `proj-lesson-08` |
| Application Insights (agent + SDK telemetry) | `appi-ai103-l09` |
| Log Analytics workspace behind it | `log-ai103-l09` |
| Search service (in use) | `srch-ai103-basic-gcn5` |
| Index | `m365-knowledge` |
| Knowledge base | `knowledgebase138` |
| Agent | `m365-agent`, latest version `m365-agent:3` |
| Known-good trace to demo | OperationId `44c9e2b5783e48a7bd817761821b8834` |

---

## Part 0 -- Generate fresh telemetry first (2 minutes)

You can't verify instrumentation against an empty pipe. Do one of these, then
wait **1 to 3 minutes** for ingestion before you look at anything.

**Option A, the agent path (this is the one that exercises the knowledge base):**

1. Go to **https://ai.azure.com**.
2. Top-right resource picker, choose project **`proj-lesson-08`**.
3. Left nav, **Build and customize** section, click **Agents**.
4. Click **`m365-agent`** in the list.
5. Click **Try in playground** (top-right of the agent detail pane).
6. Type: `How do the temperature and top_p parameters differ?`
7. Press **Enter**. Wait for the full answer to render.

**Option B, the SDK path:**

1. `cd C:\github\ai103\lessons\09-build-generative-apps-foundry`
2. `uv run eval_trace.py trace`
3. Copy one printed `operation_Id` off the console. That's your trace handle.

Do Option A on camera. It produces the three-span agent tree that makes the
instrumentation story land.

---

## Part A -- Is telemetry actually arriving? (Application Insights)

### A1. Get to the resource

1. Go to **https://portal.azure.com**.
2. In the top search bar, type `rg-ai103-mvp` and click the **resource group** result.
3. In the resource list, click **`appi-ai103-l09`**.

You're now on the Application Insights **Overview** blade.

### A2. The 10-second smoke test

1. On **Overview**, look at the chart strip: **Failed requests**, **Server response
   time**, **Server requests**, **Availability**.
2. Set the time range picker (top of the blade) to **Last 30 minutes**.
3. Click **Refresh**.

If you see any bars or line movement at all, data is landing. If the charts are
flat, that's expected for a resource that only receives **dependency** telemetry,
which is what GenAI spans are. Don't panic on a flat Overview -- go to A3, which
is the real test.

### A3. Transaction search -- the authoritative check

1. Left nav, under **Investigate**, click **Transaction search**.
2. Set the time range to **Last 24 hours**.
3. Click the **Event types** filter dropdown and select **Dependency**. Clear the rest.
4. Click **See all data in the last 24 hours**.

You should see rows named like this:

- `invoke_agent m365-agent:3`
- `execute_tool mcp_kb-knowledgebase138-13gj7.knowledge_base_retrieve`
- `chat gpt-5-mini-2025-08-07`
- `rag.turn`, `embeddings text-embedding-3-large`, and
  `POST /indexes('m365-knowledge')/docs/search.post.search` from the SDK runs

Those names ARE the proof. `invoke_agent`, `execute_tool`, and `chat` are
OpenTelemetry GenAI semantic-convention operation names. If they're present, your
instrumentation is wired correctly end to end.

### A4. Read one trace end to end

1. Still in **Transaction search**, paste `44c9e2b5783e48a7bd817761821b8834` into
   the search box and press **Enter**. (Or just click any `invoke_agent` row.)
2. Click the top result to open the **end-to-end transaction details** view.
3. In the left tree pane, expand the parent span.

Your reference tree, with the real measured numbers:

```
invoke_agent m365-agent:3                                       15,207.5 ms
  +- execute_tool mcp_kb-knowledgebase138-13gj7.knowledge_base_retrieve   8,530.1 ms
       +- chat gpt-5-mini-2025-08-07                             1,415.4 ms
```

4. Click the **`chat`** span in the tree.
5. In the right-hand details pane, scroll to **Custom Properties**.
6. Confirm these keys are populated:
   - `gen_ai.usage.input_tokens` = **6364**
   - `gen_ai.usage.output_tokens` = **439**
   - `gen_ai.usage.cached_tokens` = **4103**
   - `gen_ai.response.finish_reasons` = **["stop"]**
   - `gen_ai.input.messages` and `gen_ai.output.messages` (the actual prompt and
     completion text)

That last pair is the money. If `gen_ai.input.messages` is present, content
capture is on. In the SDK path that comes from
`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` being set **before**
the instrumentor imports, which `eval_trace.py` handles at line 46.

7. Click the **`execute_tool`** span and look at `gen_ai.tool.call.result`. That
   is the raw retrieval payload -- the exact chunks your agent got back. This is
   where you prove grounding, or catch it going sideways. See the callout at the
   bottom of this file.

### A5. Application map

1. Left nav, under **Investigate**, click **Application map**.
2. Wait for it to render, then click the node in the middle.

You get the dependency topology and per-node failure rate. It's a 20-second beat
on camera, not a deep dive.

### A6. Live metrics (optional, but it films beautifully)

1. Left nav, under **Investigate**, click **Live metrics**.
2. Leave it open, then fire a question at the agent in the Foundry playground.

Live metrics has **no ingestion delay**. You watch the sample stream tick over in
real time while the answer is still generating. If you want one shot that says
"the instrumentation is real," this is it.

---

## Part B -- KQL in Logs (the part that scales)

1. From `appi-ai103-l09`, left nav, under **Monitoring**, click **Logs**.
2. Dismiss the queries-gallery pop-up if it appears.
3. Set the time range picker to **Last 24 hours**.
4. Paste a query, click **Run**.

**Schema note, and this is the thing that trips everybody up.** The table names you
get depend on **which blade you opened Logs from**, not on how the resource was
provisioned. Open **Logs** from the Application Insights resource and you're in
the classic Application Insights experience, where the table is **`dependencies`**
and the property bag column is **`customDimensions`**. Open **Logs** from the
**Log Analytics workspace** (`log-ai103-l09`) and the very same telemetry shows up
as **`AppDependencies`** with a **`Properties`** column. Microsoft publishes the
side-by-side mapping in the telemetry data model article under **Types of
telemetry**, and the scope article spells out why the doorway decides the names:

- <https://learn.microsoft.com/azure/azure-monitor/app/data-model-complete#types-of-telemetry>
- <https://learn.microsoft.com/azure/azure-monitor/logs/scope#query-scope>

Everything in Part B is written in the **classic** dialect, because these steps
start from the Application Insights resource. That also means `kql/traces.kql` was
right all along for this blade. The full conversion table lives at the bottom of
`kql/agent-traces.kql` if you'd rather work from the workspace side.

### B1. Is anything arriving, and how recently?

```kusto
dependencies
| where timestamp > ago(24h)
| extend cd = parse_json(customDimensions)
| where isnotempty(cd["gen_ai.operation.name"])
| summarize Calls = count(), Latest = max(timestamp)
    by Operation = tostring(cd["gen_ai.operation.name"]), name
| order by Latest desc
```

Expected: rows for `invoke_agent`, `execute_tool`, and `chat`, with `Latest`
inside the last few minutes if you just ran Part 0.

### B2. Token burn and latency per model call

```kusto
dependencies
| where timestamp > ago(24h)
| extend cd = parse_json(customDimensions)
| where tostring(cd["gen_ai.operation.name"]) == "chat"
| extend InTok  = toint(cd["gen_ai.usage.input_tokens"]),
         OutTok = toint(cd["gen_ai.usage.output_tokens"]),
         Cached = toint(cd["gen_ai.usage.cached_tokens"]),
         Model  = tostring(cd["gen_ai.response.model"])
| project timestamp, Model, duration, InTok, OutTok, Cached, operation_Id
| order by timestamp desc
| take 25
```

This is your cost dashboard in five lines. `Cached` matters -- cached input
tokens bill at a discount, so a high cache ratio on a repeated system prompt is a
real win, not a rounding error.

### B3. Agent health by version

```kusto
dependencies
| where timestamp > ago(7d)
| extend cd = parse_json(customDimensions)
| where tostring(cd["gen_ai.operation.name"]) == "invoke_agent"
| summarize Runs = count(), P95Ms = percentile(duration, 95)
    by Agent   = tostring(cd["gen_ai.agent.name"]),
       Version = tostring(cd["gen_ai.agent.version"])
| order by Version asc
```

You'll see both `m365-agent:2` and `m365-agent:3` because you edited the
instructions between runs. That's a nice unplanned teaching moment: agent
versioning shows up in telemetry, so you can A/B a prompt change on latency and
token count instead of arguing about it.

### B4. Did retrieval actually happen, and what came back?

```kusto
dependencies
| where timestamp > ago(24h)
| extend cd = parse_json(customDimensions)
| where tostring(cd["gen_ai.operation.name"]) == "execute_tool"
| extend Tool   = tostring(cd["gen_ai.tool.name"]),
         Result = tostring(cd["gen_ai.tool.call.result"])
| project timestamp, Tool, duration,
          ResultPreview = substring(Result, 0, 500), operation_Id
| order by timestamp desc
| take 10
```

This is the single most useful query in the file. It answers "is my agent
grounding, or is it improvising?" without you having to trust the answer text.

### B5. Replay one request end to end

```kusto
dependencies
| where operation_Id == "44c9e2b5783e48a7bd817761821b8834"
| extend cd = parse_json(customDimensions)
| project timestamp, name, duration,
          Span = tostring(cd["span_type"]),
          Op   = tostring(cd["gen_ai.operation.name"]),
          id, operation_ParentId
| order by timestamp asc
```

Swap in any operation_Id. `id` and `operation_ParentId` are what let you reconstruct the
tree, which is exactly what the Transaction search UI does for you visually.

### B6. Discovery query, for when a column comes back blank

```kusto
dependencies
| where timestamp > ago(24h)
| where isnotempty(customDimensions)
| take 1
| project customDimensions
```

Expand the JSON in the results pane and read the real key names. Never guess at a
property-bag key -- dump it and look.

---

## Part C -- Vector index health (Azure AI Search)

### C1. Get to the service

1. Portal top search bar, type `srch-ai103-basic-gcn5`, click the result.
2. You land on **Overview**.

### C2. Overview -- capacity and tier

On the Overview blade, confirm:

- **Pricing tier** reads **Basic**
- **Semantic ranker** shows as enabled (Basic tier includes the free plan)
- The **Usage** tile shows counts for indexes, indexers, and data sources against
  the tier limits

If **Semantic ranker** shows **Disabled**, click it and turn it on. Your knowledge
base leans on the semantic configuration, and this is the switch behind it.

### C3. Indexes -- the health numbers

1. Left nav, under **Search management**, click **Indexes**.
2. Look at the row for **`m365-knowledge`**.

Three columns tell you everything:

- **Document count** -- must be greater than zero. If it's zero, your ingest never
  committed and every downstream demo will fail.
- **Storage size** -- total index footprint.
- **Vector index size** -- **this is the one to point at on camera.** If this reads
  zero bytes while document count is healthy, you have documents but **no
  embeddings**, which means retrieval will silently degrade to keyword-only. A
  non-zero vector index size is your proof that the `contentVector` field is
  actually populated.

These counters update on a lag of a few minutes after an ingest. Click **Refresh**
at the top of the blade rather than assuming a stale number is the truth.

### C4. Fields -- why your vectors are invisible

1. Click the index name **`m365-knowledge`**.
2. Click the **Fields** tab.

Your verified schema:

| Field | Type | Notes |
|---|---|---|
| `id` | `Edm.String` | key, retrievable |
| `title` | `Edm.String` | searchable, retrievable |
| `content` | `Edm.String` | searchable, retrievable |
| `category` | `Edm.String` | filterable, retrievable |
| `source` | `Edm.String` | filterable, retrievable |
| `url` | `Edm.String` | retrievable |
| `contentVector` | `Collection(Edm.Single)` | searchable, **Retrievable is unchecked** |

Scroll to `contentVector` and show that **Retrievable** checkbox sitting empty.
That is exactly why the vectors never appear in Search explorer results, and it's
deliberate: 3072 floats per document would blow up every response payload for
zero benefit. The field is searchable but not returnable. Students hit this and
conclude their embeddings are missing. They aren't. Vector index size in C3 is how
you check, not the result payload.

### C5. Semantic configuration

1. Still inside the index, click the **Semantic configurations** tab.
2. Confirm a configuration exists and that it names **`title`** as the title field
   and **`content`** as a prioritized content field.

No semantic configuration means the knowledge base falls back to plain hybrid
scoring. That was the fix you made on camera in Lesson 8.

### C6. Search explorer -- prove retrieval works

1. Left nav of the search service, click **Search explorer**.
2. In the **Index** dropdown, select **`m365-knowledge`**.
3. Switch the view toggle to **JSON view**.
4. Paste this and click **Search**:

```json
{
  "search": "*",
  "count": true,
  "top": 3,
  "select": "id,title,category,source"
}
```

Read **`@odata.count`** in the response. That is your live document count,
straight from the query path rather than from a cached portal tile.

5. Now run a real semantic query:

```json
{
  "search": "how do temperature and top_p differ",
  "queryType": "semantic",
  "semanticConfiguration": "<your config name from C5>",
  "count": true,
  "top": 3,
  "select": "title,category,source"
}
```

If the top hit is the temperature and top_p article, your index, your semantic
configuration, and your ranker are all healthy. Note that `@search.score` and
`@search.rerankerScore` come back on each hit -- the reranker score only appears
when semantic ranking actually ran, so its presence is itself a health signal.

---

## Part D -- Confirm it from the Foundry side

Two clicks that prove you don't need the Azure portal at all for day-to-day work.

1. **https://ai.azure.com**, project **`proj-lesson-08`**.
2. Left nav, click **Tracing**. The same spans you just read in Transaction search
   show up here, rendered as a Gantt-style tree, with the prompt and completion
   text inline. Zero extra setup.
3. Left nav, click **Management center**, then **Connected resources**. Confirm all
   three connections:
   - **`aisearch`** -- CognitiveSearch, Entra ID auth, pointing at `srch-ai103-basic-gcn5`
   - **`appinsights`** -- AppInsights, pointing at `appi-ai103-l09`
   - **`kb-knowledgebase138-13gj7`** -- RemoteTool, category `knowledgeBase_MCP`

That third one is worth a beat on camera. Foundry IQ exposes your knowledge base
to the agent as an **MCP remote tool**, which is precisely why retrieval shows up
in telemetry as `execute_tool` and not as a search dependency. The agent doesn't
know it's talking to Azure AI Search. It knows it's calling a tool.

---

## Part E -- Troubleshooting table

| Symptom | Cause | Fix |
|---|---|---|
| Transaction search is empty | You're inside the 1 to 3 minute ingestion window | Wait, then click **Refresh**. Use **Live metrics** if you need instant feedback. |
| Spans arrive but `gen_ai.input.messages` is missing | Content capture was off, or the env var was set after the instrumentor imported | Set `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` before the import, as in `eval_trace.py` line 46 |
| KQL columns come back blank | Dialect mismatch: workspace-style names pasted into the Application Insights Logs blade, or the reverse | From the Application Insights resource use `dependencies` and `customDimensions`. From the `log-ai103-l09` workspace use `AppDependencies` and `Properties`. Run query **B6** to confirm the real keys. |
| SDK script emits nothing at all | Process exited before the batch exporter flushed | `trace.get_tracer_provider().force_flush()` before exit, already in `eval_trace.py` |
| Search calls hit index `contoso-support` | Stale `SEARCH_INDEX_NAME` from a machine-level env var | `load_dotenv(override=True)` so the project `.env` wins |
| Vector index size reads zero | Documents uploaded without embeddings | Re-run the ingest so `contentVector` gets populated |
| `contentVector` never appears in results | **Retrievable** is unchecked by design | Working as intended. Verify vectors via index size, not via the result payload. |
| Agent answers with no citations | Retrieval returned nothing, or the model ignored the context | Run query **B4** and read `gen_ai.tool.call.result` |

---

## Callout: your agent is pulling from the open web -- and it is NOT the `web_search` tool

**Corrected 2026-07-26 after live verification. An earlier version of this callout
blamed the agent's `web_search` tool and told you to delete it. That fix would not
have worked.** Read this before you touch anything.

### What is actually true

`m365-agent:3` really does have `{"type": "web_search"}` in its tool list, alongside
the knowledge base MCP tool. That part was right. But **`web_search` never fired.**
Seven days of telemetry contain exactly one kind of `execute_tool` span:

```
execute_tool mcp_kb-knowledgebase138-13gj7.knowledge_base_retrieve
```

No `web_search` span. Not once. The public pages arrive **inside the knowledge
base's own tool result**, because `knowledgebase138` has **two** knowledge sources
attached, not one:

| Knowledge source | Type |
|---|---|
| `m365-knowledge` | `SearchIndexKnowledgeSource` -- your real content |
| `web-search` | **`WebKnowledgeSource` -- the open web** |

Independent confirmation, straight from the Search data plane: an extractive
retrieve against `knowledgebase138` fails with
`The following Knowledge Source does not support extractive output mode: web-search`.
The web source is wired into the knowledge base itself.

### How bad is it

Run **Q3** in `kql/agent-traces.kql` (rewritten 2026-07-26 -- the old hostname
version was broken and always returned an empty row). Verified numbers on the two
captured runs:

| Run | Sources returned | From `m365-knowledge` | From the web | Grounded |
|---|---|---|---|---|
| `m365-agent:3` (`44c9e2b5...`) | 15 | 1 | 14 | **6.7%** |
| `m365-agent:2` (`8251993b...`) | 30 | 1 | 29 | **3.3%** |

**The reference trace baked into Part A4 of this file is not a grounding success
story.** In `44c9e2b5...` the model cites only public pages -- "Top-K vs Top-P
Sampling: The Secret Behind AI Text Generation" and `statsig.com`. It never cites
`pe-08`, even though `pe-08` was sitting at position 12 in the retrieved set. Do
not put that trace on camera as proof of grounding.

### The fix, in priority order

**1. Detach the `web-search` knowledge source from `knowledgebase138`.** This is
the one that matters. Azure portal > `srch-ai103-basic-gcn5` > **Knowledge bases**
> `knowledgebase138` > **Knowledge sources** > remove **`web-search`** > save. The
`web-search` knowledge source object can stay on the service; it just must not be
attached to the knowledge base the agent calls.

**2. Then** remove `web_search` from the agent's tool list: **ai.azure.com** >
`proj-lesson-08` > **Agents** > **`m365-agent`** > **Tools** > trash icon next to
**web_search** > **Save**. This is hygiene, not the cure -- it makes the tool list
match the instructions and creates version 4, which is its own telemetry beat.

**3. Capture a fresh reference trace and update Part A4 of this file.** The
`operation_Id`, the three span durations (15,207.5 / 8,530.1 / 1,415.4 ms) and the
token counts (6364 / 439 / 4103) all belong to the polluted run and will all change.

### The teaching moment worth keeping

This is a better lesson than the one originally written here. The agent's
instructions say "Answer using ONLY our knowledge base." The tool list was the
obvious suspect. Both were red herrings -- **the escape hatch was one layer down,
inside the retrieval service, attached by whoever built the knowledge base.**

That is the point to make on camera: in a Foundry IQ architecture, "what can my
agent reach?" is not answered by reading the agent definition. You have to walk the
knowledge base's source list too. And the only thing that told the truth was
`gen_ai.tool.call.result` in the telemetry -- Q3, on screen, showing 1 of 15.
