# Build agents by using Foundry

Part of **Objective domain 2: Implement generative AI and agentic solutions** (30-35%), Lesson 11 (L11).

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
cp .env.example .env     # then fill in your Foundry + App Insights values
```

### `m11_multi_agent.py` -- the headline demo

An orchestrated **multi-agent hand-off**, traced end to end. It covers objective 4 (orchestrated multi-agent solutions) and objective 6 (monitoring and error analysis) in one run.

```bash
uv run python m11_multi_agent.py
uv run python m11_multi_agent.py --dry-run    # show topology, make no Azure calls
uv run python m11_multi_agent.py --no-trace   # run the hand-off, skip telemetry
```

Three specialists behind one front door, built with `HandoffBuilder`:

```text
      customer
         |
         v
      [triage]  -- reads the request, routes, answers nothing itself
         |
         +--> [billing]  tools: lookup_invoice
         |
         +--> [support]  tools: check_service_health
```

The agents are **in-process objects**, so there is no agent card to publish and nothing to provision in the portal before this runs. Each run prints the routing decision as it happens:

```text
  customer: The Contoso portal is really slow today. Is something wrong?
  expected route: support
    -> HAND-OFF      : triage -> support
    -> answered by   : support
    -> routed to     : support  [as expected]
  answer: Our monitoring shows the Contoso portal is currently degraded...
```

Three scenarios run in order: a billing question, a support question, and a deliberate miss (an invoice ID that does not exist) so the error-analysis query has something real to classify.

Two implementation details worth calling out on camera, because both are easy to get wrong:

- Every participant needs `require_per_service_call_history_persistence=True`, or `HandoffBuilder` raises at build time.
- Each scenario builds a **fresh workflow**. A handoff workflow ends its turn waiting for the customer's reply, so reusing one instance carries the previous conversation forward and every scenario answers with the first one's data.

### `m11_approval_flow.py` -- safeguards and approval gates

Human-in-the-loop control, covering objective 5 (safeguards and approval flow controls).

```bash
uv run python m11_approval_flow.py               # scripted: approve, then deny
uv run python m11_approval_flow.py --interactive # you answer y/n at the gate
uv run python m11_approval_flow.py --dry-run     # show the gates, make no Azure calls
```

Where the hand-off demo asks *which agent handles this*, this one asks *should this action
happen at all*. The answer is one parameter on the tool, and the tools are risk-tiered:

| Tool | Mode | Behavior |
| --- | --- | --- |
| `lookup_invoice` | `never_require` | Read-only. Runs unattended. |
| `refund_invoice` | `always_require` | Moves money. Stops for a human. |

The framework halts **before** the function body executes and returns a
`function_approval_request` instead of a result. Your code answers with
`request.to_function_approval_response(approved)` and the run resumes from the pause. That
placement is the whole point: a safeguard in the system prompt is a suggestion the model can
reason its way around, while a gate on the executor is a control it cannot reach past.

Three scenarios run in order, and the first two are the contrast worth pausing on. The same
request, from the same agent, on the same model produces `status: refunded` when approved and
leaves `status: paid` when denied. The third is read-only, so no gate fires at all.

Two implementation details that will bite you:

- **Use an `AgentSession`.** Reasoning models (the gpt-5 family) emit a `reasoning` item paired
  with each `function_call`, and the service rejects a turn that replays the call without its
  partner (`400 ... provided without its required 'reasoning' item`). The docs' sessionless
  pattern of hand-rebuilding the message list fails here; the session keeps the pair intact.
- **Print the arguments at the gate, not just the tool name.** "Approve `refund_invoice`?" is
  not informed consent; "Approve `refund_invoice(invoice_id='INV-81', amount_usd=99.0)`?" is.

The demo refunds **INV-81**, which is seeded as `paid` on purpose. Pointed at the unpaid INV-77,
the model correctly refuses to call the refund tool at all and the gate never fires.

### Observability

The demo wires OpenTelemetry to Application Insights with `configure_azure_monitor`, so one run emits `invoke_agent`, `execute_tool`, and `executor.process` spans. Every agent in a single hand-off shares one `operation_Id`, which is what makes the multi-agent query able to follow a request across three agents.

Set `APPLICATIONINSIGHTS_CONNECTION_STRING` in `.env` to turn tracing on. Leave it unset and the hand-off still runs, reporting that tracing is off.

Ready-to-paste queries are in `kql/`:

| Query | Answers |
| --- | --- |
| `01-agent-kpis.kql` | Which agent is slow, which is failing, how often each runs |
| `02-multi-agent-handoff.kql` | Follow one customer request across all three agents |
| `03-error-taxonomy.kql` | What is going wrong, grouped by kind |

Allow 1-3 minutes for ingestion after a run, then paste a query into **Application Insights -> Logs**.

### `generate_traffic.py`

Adds telemetry volume against a portal-provisioned prompt agent, so the KPI and error queries have more than one agent shape to report on.

```bash
uv run python generate_traffic.py --rounds 3
```

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
