# Manage, monitor, and secure AI systems

Part of **Objective domain 1: Plan and manage an Azure AI solution** (25-30%), Lesson 4 (L4).

This objective group spans two lessons, L3 and L4. Module 03 (L3) carries the manage-and-monitor emphasis, Module 04 (L4) carries the secure emphasis. The full objective list is shown in both modules verbatim so neither drops a learning objective.

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Manage quotas, scaling, rate limits, and cost footprints for model and agent workloads
2. Monitor model performance, drift, safety events, and grounding quality
3. Monitor data ingestion quality, search index health, and relevance performance
4. Configure security, including managed identity, private networking, keyless credentials, and role policies

## Demo

Security is a **portal + infrastructure-as-code** job, not an SDK one, so this lesson has **no demo script**. The demo runs from two surfaces -- the Azure/Foundry portals and the Bicep in `infra/` -- and is driven by the SAY/DO/PAUSE runbook in this folder: `Warner.AI-103.Lesson-04-demo-runbook.md`. Each of the three controls is shown twice: clicked in the portal, then read in the code that ships it.

| Clip | Control | Portal | Code (read aloud) |
|---|---|---|---|
| **04 -- Keyless identity** | managed identity, disable local auth | Foundry account > Identity, auth settings | `infra/ai103-core.mvp.bicep`: `identity: SystemAssigned`, `customSubDomainName`, `disableLocalAuth` |
| **05 -- Zero Trust networking** | private endpoint, managed VNet isolation | Foundry account > Networking | `az cognitiveservices account managed-network show ... --query isolationMode` |
| **06 -- RBAC (the Azure AI Developer trap)** | assign **Foundry User**, not Azure AI Developer | Access control (IAM) | `infra/modules/observability.bicep`: the `roleAssignments` resource (`guid(...)` name, `principalType`, `subscriptionResourceId(...)`) |

Pre-flight and the full talk track are in the runbook. Deployed lab account: `aif-ai103-mvp-quc6kxy2j2v2q` in `rg-ai103-core`.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
