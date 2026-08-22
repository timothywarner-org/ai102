# Lesson 6 Demo Runbook -- Build Generative Applications with the Foundry SDK

**On screen, two surfaces:** VS Code in the `ai103` project (where we live this lesson), and Edge in the portal for a glance or two.
**File under the mouse:** `lessons/06-build-generative-apps-foundry/m06_build_app_demo.py`.
This is a BUILD lesson, so code is the surface -- we run it live. Blocks: **[SAY]** - **[DO]** - **[VERIFY]** - **[PAUSE]**.

## Pre-flight (before recording)
- `az login` done; VS Code on the `ai103` workspace, `m06_build_app_demo.py` open, integrated terminal ready.
- `.env` filled: `FOUNDRY_PROJECT_ENDPOINT` = the **proj-lesson-06** project endpoint, `MODEL_DEPLOYMENT_NAME=gpt-5-mini`.
- `uv sync` already run in the lesson folder. Do a silent `uv run python m06_build_app_demo.py --dry-run` once to confirm the plan.

---

## Cold open  (~30s)

[SAY] This is the lesson where we stop clicking and start building. Everything so far set the table -- models deployed, security wired, responsible AI in place. Now we write the code that actually talks to Foundry, and it's four moves: connect to the project, consume a model, integrate a connector, and wrap the whole thing in an agent. All keyless, all in the Foundry SDK. Let's build.

---

## Beat 1: Connect to the project  (LO6, ~3 min)

[SAY] Everything starts with one client. Now you might be thinking, hang on, Tim, I've got the model's endpoint right there on the deployment page, why not point my app at that? Because that model endpoint only reaches the one deployment. What you want is the project endpoint, the front door that reaches every model and every connection in the project. So I build one AIProjectClient from the project URL, keyless with my az login identity, and I prove it works by listing the deployments right at startup, so a bad URL or a missing role fails here, not in front of a user.

[DO] **VS Code** > `m06_build_app_demo.py` > run the **connect cell** (`connect`) with **Shift+Enter**.
[VERIFY] The terminal prints "connected" with the project endpoint and the reachable deployments -- gpt-5-mini and text-embedding-3-small.

[PAUSE] Hold on the project endpoint URL for the zoom.
[IF IT BREAKS] If it can't connect, it's almost always the endpoint form or the role. The endpoint must be the project URL ending in /api/projects/proj-lesson-06, and your identity needs Foundry User on the project -- exactly the role we assigned back in the security lesson.

---

## Beat 2: Consume a deployed model  (LO1, ~3.5 min)

[SAY] The model's already deployed, and that deployment is infrastructure as code -- the SKU, the pinned version, the content filter, all declared in Bicep. What this lesson is about is consuming it. I ask the project for an OpenAI client, and here's the payoff: what comes back is the exact same OpenAI client you'd use anywhere, except it's keyless and already pointed at my project. I send one question, then a follow-up that remembers the first turn, which is conversation memory with no extra plumbing.

[DO] **VS Code** > run the **consume cell** (`consume`).
[VERIFY] The terminal prints a real one-sentence answer to "What is Microsoft Foundry?", then a follow-up that names something Foundry isn't, clearly building on the first turn.

[SAY] And to close the loop on where that model came from, here's the deploy as code.
[DO] **VS Code** > open `infra/ai103-core.mvp.bicep` > the deployment resource > point at **`sku`**, **`versionUpgradeOption: 'NoAutoUpgrade'`**, and **`raiPolicyName`**.
[SAY] SKU is the capacity tier, NoAutoUpgrade pins the version so the model can't shift under me, and raiPolicyName attaches the content filter -- the deploy decisions from Lesson 6's first objective, all version-controlled.

[PAUSE] Hold two beats on the two answers side by side.
[IF IT BREAKS] If the model call errors, it's the deployment name or the model's own quota. Confirm MODEL_DEPLOYMENT_NAME matches a deployment the connect step listed.

---

## Beat 3: Integrate via connectors  (LO5, ~3 min)

[SAY] A real app doesn't just call a model, it reaches other services -- a search index, App Insights, storage. Foundry makes those first-class through connections: you define a connection once, on the project, and every client reuses it, so there's no secret scattered through your code. I list the project's connections from the SDK, and you'll recognize this one -- it's the very same Application Insights we wired up back in the monitoring lesson, now reachable as a first-class connector.

[DO] **VS Code** > run the **connections cell** (`show_connections`).
[VERIFY] The terminal prints the project's connection -- `l06-appinsights`, an Application Insights connector.

[SAY] And because a connection is just configuration, it belongs in your infrastructure code too. Here's what one looks like declared in Bicep.
[DO] **VS Code** > open `infra/modules/observability.bicep` > the **`connections`** resource (`Microsoft.CognitiveServices/accounts/projects/connections`) > point at the **category**, **target**, and **authType**.
[SAY] Category says what kind of service it is, target is the resource it points at, and authType is how we reach it -- keyless where we can. Define it here and every environment gets the same connection with no manual step.

[PAUSE] Hold on the connections resource in Bicep.

---

## Beat 4: Wrap it in an agent  (capstone, ~3 min)

[SAY] Here's where this is all heading. An agent is a model plus instructions -- and later, tools and memory -- that you publish once and call by name. This is the deep dive of the next two lessons; here it's a sixty-second taste so you see the shape. I create an agent version from a prompt definition, run one turn through a conversation, and delete it on the way out, so nothing's left behind.

[DO] **VS Code** > integrated terminal > `uv run python m06_build_app_demo.py --agent` (or run the **agent cell**).
[VERIFY] The terminal prints "created agent m06-hello-agent", the agent's one-sentence answer about retrieval-augmented generation, and "cleaned up: agent version deleted".

[SAY] One heads-up worth teaching: this agent API is in preview, and it moves. The response references the agent through an agent_reference property -- an older agent property was just deprecated. That churn is the price of being on the newest surface, and the demo handles it gracefully either way.

[PAUSE] Hold on the agent's answer.
[IF IT BREAKS] If the preview agent call errors, narrate it honestly -- the connect, consume, and connectors beats are the stable core, and agents are the whole point of Lessons 10 and 11.

---

## Close  (~30s)

[SAY] Four moves, one SDK. We connected to the project through its endpoint, consumed a deployed model with plain OpenAI code, reached a connector the project owns, and wrapped it all in an agent -- every step keyless, every step something you'd actually ship. That's how you build a generative application on Foundry. I'll see you in the next one.
