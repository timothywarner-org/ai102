# Lesson 11 -- Multi-agent orchestration (AI-103 LO4 / LO5 / LO6)

Diagrams for the L11 deck and runbook, grounded in the Microsoft Agent Framework
[workflow orchestrations](https://learn.microsoft.com/agent-framework/workflows/orchestrations/) docs
and the [AI-103 skills measured](https://learn.microsoft.com/credentials/certifications/resources/study-guides/ai-103)
list (April 16, 2026).

---

## 1. The five built-in patterns (pick-the-pattern slide)

Exam-relevant framing: AI-103 LO4 says "implement orchestrated multi-agent solutions." The
exam expects you to **choose** the right pattern, so this is the decision slide.

```mermaid
flowchart TB
    Q["<b>How should the agents coordinate?</b>"]

    Q --> S["<b>Sequential</b><br/>one after another,<br/>each builds on the last"]
    Q --> C["<b>Concurrent</b><br/>parallel, independent,<br/>results aggregated"]
    Q --> H["<b>Handoff</b><br/>control transfers<br/>to a specialist"]
    Q --> G["<b>Group chat</b><br/>shared conversation,<br/>debate and review"]
    Q --> M["<b>Magentic</b><br/>manager agent plans<br/>and directs"]

    S --> SU["Document review,<br/>approval pipelines"]
    C --> CU["Fan-out data gathering,<br/>latency reduction"]
    H --> HU["Customer support,<br/>routing to expertise"]
    G --> GU["Writer/reviewer loops,<br/>multi-perspective analysis"]
    M --> MU["Open-ended tasks needing<br/>dynamic planning"]

    H:::chosen
    HU:::chosen

    classDef chosen stroke-width:3px,stroke-dasharray:0
    linkStyle default stroke-width:1.5px
```

**L11 demos the Handoff pattern** (the one with the heavier border). It is the clearest
teaching case because the routing decision is visible on every single turn.

---

## 2. What L11 actually builds

Three specialists behind one front door, in `m11_multi_agent.py`.

```mermaid
flowchart LR
    subgraph client["Your process"]
        direction TB
        CUST(["Customer request"])
    end

    subgraph wf["HandoffBuilder workflow (in-process objects)"]
        direction TB
        TRIAGE["<b>triage</b><br/><i>start agent</i><br/>routes only, answers nothing"]
        BILLING["<b>billing</b><br/>tool: lookup_invoice"]
        SUPPORT["<b>support</b><br/>tool: check_service_health"]
    end

    subgraph foundry["Microsoft Foundry"]
        direction TB
        MODEL["gpt-5-mini deployment<br/><i>proj-agents</i>"]
    end

    CUST -->|"workflow.run(question)"| TRIAGE
    TRIAGE -->|"handoff_sent<br/>money question"| BILLING
    TRIAGE -->|"handoff_sent<br/>outage report"| SUPPORT
    BILLING -->|"output event"| ANS(["Answer"])
    SUPPORT -->|"output event"| ANS

    TRIAGE -.->|"AzureCliCredential<br/>keyless"| MODEL
    BILLING -.-> MODEL
    SUPPORT -.-> MODEL

    classDef start stroke-width:3px
    class TRIAGE start
```

**Say this out loud:** the specialists never talk to the customer directly and never hand off
again. They answer and stop.

---

## 3. The correction worth making on camera

The picture above is the **logical routing view**. The docs are explicit that handoff is
implemented as a **mesh with no central orchestrator**, and that every participant broadcasts
its response so all agents keep a consistent conversation history.

```mermaid
flowchart TB
    subgraph wrong["Mental model most people arrive with"]
        direction TB
        O(["Orchestrator"])
        A1["agent A"]
        A2["agent B"]
        A3["agent C"]
        O --> A1
        O --> A2
        O --> A3
        A1 --> O
        A2 --> O
        A3 --> O
    end

    subgraph right["How Handoff actually works"]
        direction TB
        B1["<b>triage</b>"]
        B2["<b>billing</b>"]
        B3["<b>support</b>"]
        B1 <-->|"context broadcast"| B2
        B2 <-->|"context broadcast"| B3
        B1 <-->|"context broadcast"| B3
    end

    wrong ~~~ right
```

Two consequences that are genuinely exam-relevant:

1. **There is no central authority.** Each agent decides its own next hop, which is why adding a
   fourth specialist means adding one participant rather than editing a routing table.
2. **Handoff tool calls are filtered out** of the history before the next agent sees them, so the
   internal workflow mechanics never confuse the model. Only user and agent messages sync.

Contrast with **agent-as-tools**, where a primary agent delegates a subtask and control *returns*
to it. In handoff, the receiving agent takes **full ownership** of the task.

---

## 4. LO5 -- where the approval gate sits

This is `m11_approval_flow.py`. The gate is on the executor, not in the prompt.

```mermaid
sequenceDiagram
    autonumber
    actor Human
    participant Agent as billing agent
    participant FW as Agent Framework<br/>(executor)
    participant Tool as refund_invoice()

    Human->>Agent: "Refund invoice INV-81 in full"
    Agent->>FW: requests refund_invoice(INV-81, 99.0)
    Note over FW,Tool: approval_mode="always_require"<br/>function body NOT yet reached
    FW-->>Human: function_approval_request<br/>(tool name + arguments)

    alt Approved
        Human->>FW: to_function_approval_response(True)
        FW->>Tool: execute
        Tool-->>Agent: status = refunded
        Agent-->>Human: "Refunded $99.00, confirmation RF-INV-81"
    else Denied
        Human->>FW: to_function_approval_response(False)
        Note over Tool: never executes
        Agent-->>Human: "The refund could not be processed"
    end
```

**The teaching line:** a safeguard written in the system prompt is a suggestion the model can
reason its way around. A gate declared on the tool is a control it cannot reach past. Same
request, same agent, same model -- the only variable is the human.

Risk-tier the tools rather than gating everything:

| Tool | `approval_mode` | Behavior |
| --- | --- | --- |
| `lookup_invoice` | `never_require` | Read-only, runs unattended |
| `refund_invoice` | `always_require` | Moves money, stops for a human |

---

## 5. LO6 -- why one operation_Id makes this observable

```mermaid
flowchart LR
    subgraph run["One customer request = one operation_Id"]
        direction TB
        W["workflow.run"]
        T["executor.process<br/><b>triage</b>"]
        B["executor.process<br/><b>billing</b>"]
        X["execute_tool<br/>lookup_invoice"]
        I["invoke_agent<br/>chat completion"]

        W --> T --> B --> X
        B --> I
    end

    run -->|"OpenTelemetry via<br/>configure_azure_monitor"| AI[("Application Insights<br/><i>appi-ai103-l11</i>")]
    AI -->|"kql/02-multi-agent-handoff.kql"| RESULT["agents: triage, billing, support<br/>tools: lookup_invoice<br/>spans: 10  total_ms: 18381"]
```

Every agent in a single hand-off shares **one `operation_Id`**. That is exactly what lets the KQL
query follow a request across three agents instead of correlating three disconnected logs by
timestamp.

If `02-multi-agent-handoff.kql` returns **nothing**, that is not an empty result, it is a
diagnosis: distributed tracing is not wired up correctly. When it returns rows, your multi-agent
telemetry is genuinely correct.

---

## Sources

- [Workflow orchestrations](https://learn.microsoft.com/agent-framework/workflows/orchestrations/) -- the five patterns
- [Handoff orchestration](https://learn.microsoft.com/agent-framework/workflows/orchestrations/handoff) -- mesh topology, context sync, tool approval, `HandoffAgentExecutor`
- [Human-in-the-loop](https://learn.microsoft.com/agent-framework/workflows/human-in-the-loop) -- approval request/response model
- [AI-103 study guide](https://learn.microsoft.com/credentials/certifications/resources/study-guides/ai-103) -- skills measured as of April 16, 2026
