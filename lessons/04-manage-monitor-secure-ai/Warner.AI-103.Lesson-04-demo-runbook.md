# Lesson 4 Demo Runbook -- Secure AI Systems with Zero Trust Identity and Networking

**On screen, only two surfaces:** Edge in the portals, and VS Code in the `ai103` project.
**No SDK here on purpose** -- security is a portal + infrastructure-as-code job, so we click it in the
portal and then **read the Bicep that ships it**. Blocks: **[SAY]** - **[DO]** - **[VERIFY]** - **[PAUSE]**.

## Pre-flight
- Edge signed in: **ai.azure.com** (Foundry) and **portal.azure.com** (Azure).
- VS Code on the `ai103` workspace with the `infra/` folder open; integrated terminal ready; `az login` done.
- Account for the demo: `aif-ai103-mvp-quc6kxy2j2v2q` in `rg-ai103-core`.

---

## Cold open  (~30s)

[SAY] Securing an AI solution in Foundry comes down to three things: identity, network, and roles. I'll show each one twice -- first in the portal where you click it, then in the Bicep where you'd actually ship it. And this time I'm going to slow down and read the code out loud, because infrastructure as code only teaches you something if somebody explains the code instead of just flashing it past you.

---

## Segment 1: Identity and keyless  (~4 min)

[SAY] Security starts with identity, and the goal is simple: no passwords anywhere. A managed identity is an Entra credential that Azure creates for this resource and rotates on its own, so your app proves who it is with a token instead of a key. Let me turn it on, then shut off key-based auth entirely.

[DO] **Edge > portal.azure.com** > the Foundry account > **Identity** > **System assigned** = **On**. Then under **Resource Management > Keys and Endpoint** (or the account's auth setting), disable local authentication.
[VERIFY] System-assigned identity shows an object ID; local auth is off.

[SAY] Now the same two decisions as code you'd commit to a repo. Open infra/ai103-core.mvp.bicep and find the account resource. Read the identity block with me: type is SystemAssigned -- that single line is the managed identity we just toggled in the portal. Right below it, customSubDomainName -- that one is easy to miss, but token authentication doesn't work without it, because it's the hostname Entra binds the identity to. Then disableLocalAuth. On this lab account it's set to false on purpose, so our other demos can still reach it while we teach; in production you flip that single word to true and the keys are dead, so the resource will only ever accept an Entra token. Three properties, and your entire identity posture is version-controlled instead of clicked.

[DO] **VS Code** > `infra/ai103-core.mvp.bicep` > point at `identity: SystemAssigned`, `customSubDomainName`, and `disableLocalAuth` on the account resource.
[PAUSE] Hold on the three properties for the zoom.

---

## Segment 2: Zero Trust networking  (~4 min)

[SAY] Next, the network. Zero Trust says treat the network as already hostile, so we do two things: pull Foundry off the public internet with a private endpoint, and control what Foundry itself is allowed to call outbound with a managed virtual network.

[DO] **Edge > portal.azure.com** > the Foundry account > **Networking** > show the **private endpoint** option and **public network access = Disabled**.
[VERIFY] Public access disabled; a private endpoint listed (or the option to add one).

[SAY] The outbound side has its own control, and it's the exam-relevant one. In the terminal I'll read the managed-network isolation mode.

[DO] **VS Code terminal**:
`az cognitiveservices account managed-network show -g rg-ai103-core -n aif-ai103-mvp-quc6kxy2j2v2q --query isolationMode -o tsv`
[VERIFY] Prints the mode, or reports no managed network on this lab account.

[SAY] Two modes matter here. Allow-internet-outbound lets Foundry call anywhere. Allow-only-approved-outbound is the locked-down one: the only way out is the exact destinations you list, through private endpoints, service tags, and firewall rules. That approved-outbound mode is how you stop data exfiltration, and as code it's just a managedNetworks child resource with isolationMode set to AllowOnlyApprovedOutbound -- same switch, committed instead of clicked.

[PAUSE] Hold on the mode.
[IF IT BREAKS] If this lab account has no managed network, say so plainly: "this one's public for the lab; in production you'd set isolationMode to AllowOnlyApprovedOutbound and add outbound rules."

---

## Segment 3: RBAC -- the right role, as code  (~4 min)

[SAY] Last, roles. This is where people lose exam points, so watch the trap. In Access control, the tempting-looking role is Azure AI Developer -- and it's wrong. Despite the name, it's scoped to Azure Machine Learning and hubs, not Foundry projects. The right role for a developer who needs to build is Foundry User. I'll assign that, and just point at Azure AI Developer so you see the bait.

[DO] **Edge > portal.azure.com** > the Foundry resource > **Access control (IAM)** > **Add role assignment** > **Foundry User** > select a developer. Hover -- but do NOT assign -- **Azure AI Developer**.
[VERIFY] Foundry User assignment created.

[SAY] Same assignment as one command, if you'd rather script it:
`az role assignment create --role "Foundry User" --assignee <dev> --scope <foundry-resource-id>`.

[SAY] And here's the part I really want you to read, not skim. Open infra/modules/observability.bicep and scroll to the roleAssignments resource. Three things make this production-grade. First, the name is a guid of the resource ID, the user, and the role ID -- deterministic, so re-running the template never creates a duplicate assignment. Second, principalType is set to User, which tells Azure this is a person and not an app, so it skips a slow directory lookup. Third -- and this is the good one -- roleDefinitionId uses subscriptionResourceId to reference the built-in role by its stable GUID, not its display name. Names get renamed, like Azure AI User just became Foundry User; the GUID never changes. That's role-based access control as code: reviewable in a pull request, repeatable, and it can't quietly drift.

[DO] **VS Code** > `infra/modules/observability.bicep` (or `search.bicep`) > the `roleAssignments` resource; point at the `guid(...)` name, `principalType`, and `subscriptionResourceId(...roleDefinitions...)`.
[PAUSE] Hold on the roleDefinitionId line.

---

## Close  (~30s)

[SAY] Three controls, two ways to see each one: identity made keyless, the network made private, and roles kept least-privilege -- clicked in the portal, then committed in Bicep. The difference from last time is that you can now read that Bicep instead of just admiring it. That's how you secure an AI solution in Foundry, and I'll see you in the next one.
