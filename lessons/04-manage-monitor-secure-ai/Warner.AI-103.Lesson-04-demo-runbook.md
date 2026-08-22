# Lesson 4 Demo Runbook -- Secure AI Systems with Zero Trust Identity and Networking

**On screen, only two surfaces:** Edge in the portals, and VS Code in the `ai103` project.
**No SDK here on purpose** -- security is a portal + infrastructure-as-code job, so we click it in the portal and then **read the Bicep that ships it**.

**Block legend:** 🗣️ SAY (talk track) - 🎬 DO (on screen) - ✅ VERIFY - ⏸️ PAUSE - 💥 IF IT BREAKS

---

## Pre-flight ✈️

- Edge signed in: **ai.azure.com** (Foundry) and **portal.azure.com** (Azure).
- VS Code on the `ai103` workspace, `infra/` folder open, integrated terminal ready, `az login` done.
- Demo account: `YOUR-FOUNDRY-RESOURCE` in `rg-ai103-core`.
- Demo developer persona: **Priya Sharma** (`priya@contoso.com`).

---

## Cold open  (~30s)

🗣️ **SAY**

- Securing an AI solution in Foundry comes down to **three things: identity, network, roles**.
- I'll show each one **twice**: first in the **portal** where you click it, then in the **Bicep** where you'd ship it.
- This time I'll **slow down and read the code out loud**. Infrastructure as code only teaches you something if somebody explains it instead of flashing it past you.

---

## Beat 1: Identity and keyless  (~4 min) 🔑

🗣️ **SAY -- the idea**

- Security starts with **identity**. The goal is simple: **no passwords anywhere**.
- A **managed identity** is an Entra credential Azure creates for this resource and rotates for you.
- The app proves who it is with a **token**, not a key.
- I'll show it turned on, then show the switch that shuts off key-based auth entirely.

🎬 **DO -- portal**

- **portal.azure.com** > Foundry account > **Identity** > confirm **System assigned = On**.
- Open the account's authentication setting, point at the **local-auth** control.
- Leave it as-is on this shared lab account so the other demos keep working.

✅ **VERIFY** System-assigned identity shows an **object ID**; the local-auth control is visible.

🗣️ **SAY -- the same thing as code**

Open `infra/ai103-core.mvp.bicep`, find the account resource, read the identity block with me:

- **`type: SystemAssigned`** -- the managed identity we just toggled in the portal.
- **`customSubDomainName`** -- easy to miss, but token auth doesn't work without it. It's the hostname Entra binds the identity to.
- **`disableLocalAuth`** -- set to **false** here on purpose so our other demos still reach the account. In production you flip it to **true** and the keys are dead; the resource then only accepts an Entra token.

**Payoff:** three properties, and your entire identity posture is version-controlled instead of clicked.

🎬 **DO -- VS Code** `infra/ai103-core.mvp.bicep` > point at `identity: SystemAssigned`, `customSubDomainName`, `disableLocalAuth`.

⏸️ **PAUSE** Hold on the three properties for the zoom.

---

## Beat 2: Zero Trust networking  (~4 min) 🛡️

🗣️ **SAY -- the idea**

- Zero Trust says treat the network as **already hostile**.
- Two moves:
  1. Pull Foundry **off the public internet** with a **private endpoint** (inbound).
  2. Control what Foundry is allowed to **call outbound** with a **managed virtual network** (outbound).

🎬 **DO -- portal**

- **portal.azure.com** > Foundry account > **Networking**.
- Show the **Public network access** control and the **Private endpoint connections** tab.

✅ **VERIFY** On this lab account: public access reads **Enabled**, no private endpoints yet. Point at the toggle: in production you flip to **Disabled** and add a private endpoint.

🗣️ **SAY -- read the inbound posture**

I'll read that same inbound posture from the terminal, because this is what our account-based Foundry actually exposes.

🎬 **DO -- terminal**
`az cognitiveservices account show -g rg-ai103-core -n YOUR-FOUNDRY-RESOURCE --query "{publicNetworkAccess:properties.publicNetworkAccess, networkAcls:properties.networkAcls}" -o jsonc`

✅ **VERIFY** Prints `publicNetworkAccess: Enabled` and `networkAcls: null` -- public, no IP allow-list. Locked-down target: `Disabled` plus a `networkAcls` default-deny rule.

🗣️ **SAY -- the outbound half (exam nuance)**

- Inbound was half the story. The outbound half stops Foundry from calling anywhere it wants.
- **Exam-relevant nuance:** managed-network isolation is a **hub** feature. It lives on the Foundry **hub** (an Azure ML workspace underneath), **not** on a plain Cognitive Services account like this one. So there's no `isolationMode` to read here.
- On a hub you'd read it with `az ml workspace show --query managed_network.isolation_mode`.
- Locked-down value: **`AllowOnlyApprovedOutbound`**. The only way out is the exact destinations you list, via private endpoints, service tags, and firewall rules.
- That's how you stop **data exfiltration**. As code it's a `managedNetwork` block with `isolationMode` set to `AllowOnlyApprovedOutbound` -- same switch, committed instead of clicked.

⏸️ **PAUSE** Hold on the jsonc output.

💥 **IF IT BREAKS** If the command errors, fall back to the portal Networking blade. Be plain about the account type: "this account-based Foundry has no managed network; approved-outbound isolation is a hub feature you'd set with `isolationMode = AllowOnlyApprovedOutbound`."

---

## Beat 3: RBAC -- the right role, as code  (~4 min) 👤

🗣️ **SAY -- the trap**

- Last, **roles**. This is where people lose exam points, so watch closely.
- Our developer is **Priya Sharma**. She needs to build against this Foundry account.
- You might think: there's a role called **Azure AI Developer** -- isn't that obviously the one for Priya?
- **That's the bait, and it's wrong.** Despite the friendly name, Azure AI Developer is scoped to **Azure Machine Learning and hubs**, not Foundry projects.
- The right role for a developer who needs to build is **Foundry User**. I'll assign that to Priya, and just point at Azure AI Developer so you see the trap.

🎬 **DO -- portal**

- **portal.azure.com** > Foundry resource > **Access control (IAM)** > **Add role assignment**.
- Role: **Foundry User** > select **Priya Sharma** (`priya@contoso.com`).
- Hover **Azure AI Developer** to show the bait, but leave it unassigned.

✅ **VERIFY** Foundry User assignment created for Priya Sharma.

🗣️ **SAY -- same thing as one command**
`az role assignment create --role "Foundry User" --assignee priya@contoso.com --scope /subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-ai103-core/providers/Microsoft.CognitiveServices/accounts/YOUR-FOUNDRY-RESOURCE`

🗣️ **SAY -- now read the Bicep (don't skim this)**

Open `infra/modules/observability.bicep`, scroll to the `roleAssignments` resource. Three things make it production-grade:

1. **Deterministic name** -- a `guid()` of the resource ID, the user, and the role ID. Re-running the template never creates a duplicate assignment.
2. **`principalType: User`** -- tells Azure this is a person, not an app, so it skips a slow directory lookup.
3. **`roleDefinitionId` via `subscriptionResourceId(...)`** -- references the built-in role by its **stable GUID**, not its display name. Names get renamed (Azure AI User just became **Foundry User**); the **GUID never changes**.

**Payoff:** RBAC as code -- reviewable in a pull request, repeatable, and it can't quietly drift.

🎬 **DO -- VS Code** `infra/modules/observability.bicep` (or `search.bicep`) > the `roleAssignments` resource; point at the `guid(...)` name, `principalType`, and `subscriptionResourceId(...roleDefinitions...)`.

⏸️ **PAUSE** Hold on the `roleDefinitionId` line.

---

## Close  (~30s) 🎬

🗣️ **SAY**

- **Three controls, two views each:**
  - **Identity** made keyless 🔑
  - **Network** made private 🛡️
  - **Roles** kept least-privilege 👤
- Clicked in the portal, then committed in Bicep.
- The difference from last time: you can now **read** that Bicep instead of just admiring it.
- That's how you secure an AI solution in Foundry, and I'll see you in the next one.
