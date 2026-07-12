# Lesson 5 Demo Runbook -- Implement Responsible AI Across Generative and Agentic Systems

**On screen, only two surfaces:** Edge in the portals, and VS Code in the `ai103` project.
**File under the mouse in VS Code:** `lessons/05-responsible-ai-generative-agentic/m05_evals_demo.py`.
Read-only demo -- nothing in production is changed; the one thing we create (a content filter) is cheap and reusable. Blocks: **[SAY]** what I say - **[DO]** what I click - **[VERIFY]** - **[PAUSE]**.

## Pre-flight (before recording)
- Edge open, signed in, two tabs: **ai.azure.com** (Foundry) and **portal.azure.com** (Azure).
- Foundry project `proj-lesson-05` open on the `aif-ai103-mvp-quc6kxy2j2v2q` account, with the **gpt-5-mini** deployment live -- it's both the app model and the eval **judge** (one deployment; see Segment 2).
- VS Code open on the `ai103` workspace, `m05_evals_demo.py` visible, integrated terminal ready.
- `az login` done; `.env` filled in; `uv sync` already run in the lesson folder.

---

## Cold open  (~30s)

[SAY] Responsible AI on this exam isn't a poster on the wall -- it's four concrete controls you configure and prove. So that's exactly what we'll do: I'll set a content filter in the portal, score a real answer with evaluators in code, read an audit trace, and lock down what an agent is allowed to touch. Same two surfaces you already know -- my browser in the portals, and VS Code in our project. Four controls, four defense layers, live.

---

## Segment 1: Configure safety filters and content moderation  (LO1, ~3.5 min)

[SAY] First control: the content filter, which is your front door for safety. Every Foundry deployment already ships with Microsoft's default filter, but the exam wants you to know you can tighten it. In the portal, under Guardrails and controls, is where content filters live. A filter checks four harm categories -- hate, violence, sexual, and self-harm -- and each one gets a severity score, so I decide how strict to be per category. On top of that, Prompt Shields catch injection attacks, and a blocklist enforces my own banned terms.

[DO] **Edge > ai.azure.com** > your project > **Guardrails + controls** (a.k.a. **Content filters**) > **Create content filter**. Walk the four categories with their severity sliders, toggle **Prompt Shields** for jailbreak and indirect attacks, and point at the **blocklist** option.
[VERIFY] The new filter shows the four categories with thresholds set, and Prompt Shields enabled.

[SAY] Now here's the part learners miss: a content filter is just configuration, which means it belongs in your infrastructure code, not in a click you'll forget. Back in Lesson 2 you saw a deployment carry a `raiPolicyName` property -- that one line is how you attach this exact filter to a deployment in Bicep, so every environment gets the same guardrail with no manual step.

[DO] **VS Code** > open `infra/ai103-core.mvp.bicep` > find the deployment resource > highlight the **`raiPolicyName`** property on `properties`.
[SAY] That property names the content-filter policy the deployment enforces. Set it here and the filter travels with the deployment through every pipeline -- that's responsible AI as code, not as a checklist.

[PAUSE] Hold on the four categories for the zoom edit.
[IF IT BREAKS] If the portal blade name differs in your tenant, it's under Guardrails and controls or Safety plus security -- narrate that the location moves but the four categories and Prompt Shields don't.

---

## Segment 2: Apply responsible AI instrumentation -- evaluators  (LO2, ~4 min)

[SAY] Second control: instrumentation. A filter stops the obviously harmful stuff, but it can't tell me whether a good-looking answer is actually grounded in my data or just confidently wrong. That's what evaluators do -- they score quality and safety on real query-and-response pairs. And this is the one place in this lesson where code is genuinely the right surface, because you'll wire these into a pipeline to gate a release, not run them by hand.

[SAY] I'm using the Azure AI Evaluation SDK. Groundedness asks "is this answer supported by the source I retrieved?" and Relevance asks "does it actually address the question?" Both are LLM-as-a-judge, so they need a grader model. Now you might be thinking, hang on, Tim, can gpt-5 even be the judge? Because the eval SDK sends a max_tokens parameter, and the gpt-5 family wants max_completion_tokens instead. And the answer is yes, with one flag: I set is_reasoning_model to true, the evaluator switches to the dialect gpt-5 speaks, and I grade with the very same gpt-5-mini we run the app on -- no second model to stand up. And notice the config carries a credential, not an API key -- keyless, the same posture from the security lesson.

[DO] **VS Code** > `m05_evals_demo.py` > run the **model-config cell** with **Shift+Enter** (`build_model_config` -- the keyless judge), then run the **quality cell** (`run_quality`).
[VERIFY] The terminal prints two blocks -- a grounded answer and a fabricated answer -- each with a groundedness and a relevance score.

[SAY] Here's the move: the fabricated answer invents a fact the source never states, and watch groundedness collapse on it while the grounded answer stays high.
[VERIFY] The GROUNDED answer scores high groundedness; the FABRICATED answer scores low. That low number is the hallucination, caught by a machine.

[SAY] Safety scoring is a sibling of this. The content-safety evaluator calls the Azure evaluation service rather than my judge model, so it's an opt-in beat -- run with the safety flag and it scores harmful-content rates, or skips cleanly if the service isn't wired in this region.
[DO] Optionally run `python m05_evals_demo.py --safety` to add the content-safety score.

[SAY] And this is why it belongs in code: drop these evaluators into CI and you can fail the build the moment groundedness falls below your bar, so a regression like that fabricated answer never ships to a customer in the first place.

[PAUSE] Hold two beats on the two scores side by side.
[IF IT BREAKS] If an evaluator errors on the judge model, narrate it honestly -- evaluators need a deployed judge model, here gpt-5-mini with is_reasoning_model set -- and fall back to the dry-run that prints the schema.

---

## Segment 3: Implement auditing -- trace logging and provenance  (LO3, ~3 min)

[SAY] Third control: auditing. When something goes wrong in production, "the model said something bad" isn't an incident report -- you need the receipt. Foundry tracing gives you that. It's built on OpenTelemetry, and it streams every step -- the prompt, the tool calls with their arguments, and the final response -- into Application Insights, where it's timestamped and queryable.

[DO] **Edge > ai.azure.com** > your project > **Tracing** (under Observability). Open one trace and expand the spans -- prompt, tool call, response.
[VERIFY] A trace shows an ordered set of spans with timing; a tool-call span shows its arguments.

[SAY] And because it lands in Application Insights, the provenance is durable and you can hold it under your retention policy. That's the difference between "we think" and "here's the exact chain, with a timestamp."

[DO] **Edge > portal.azure.com** > the project's **Application Insights** resource > **Logs** > point at the `dependencies` / `traces` tables where the spans arrive.
[VERIFY] The App Insights resource shows recent trace or dependency rows (data fills in as traffic flows).

[PAUSE] Hold on the expanded span tree.
[IF IT BREAKS] If no traces appear yet, narrate that tracing populates once the app emits spans -- that IS the setup step -- and reference the Lesson 3 App Insights connection we already wired.

---

## Segment 4: Govern agent behavior -- oversight and tool access  (LO4, ~3 min)

[SAY] Fourth control: governance, which is where agentic AI raises the stakes. A chat model returns text, but an agent takes actions -- so the responsible-AI question becomes "what is this thing allowed to do, and who signs off." Two levers. First, scope: an agent should only see the specific tools its job requires, gated by role-based access and an allow-list, never every tool in the tenant. Second, oversight mode: supervised means a human approves every action, semi-autonomous means approval only on the sensitive ones, autonomous means it acts within fixed bounds, and shadow means it suggests while a human still decides.

[DO] **Edge > ai.azure.com** > your project > open the **agent** > **Tools** > show the tool allow-list (only the tools this agent needs), then the **approval / require-human-review** setting on a sensitive tool.
[VERIFY] The agent lists a scoped set of tools; a sensitive tool shows a required-approval toggle.

[SAY] Set a tool to require approval and you've turned a fully autonomous action into a human-in-the-loop checkpoint -- semi-autonomous by configuration. Match the oversight mode to the risk: the higher the blast radius of the action, the more human you keep in the loop.

[PAUSE] Hold on the required-approval toggle.
[IF IT BREAKS] If your agent has no sensitive tools wired, narrate the spectrum against the tool list you do have -- the exam tests the four modes and the allow-list principle, not a specific button.

---

## Close  (~30s)

[SAY] Four controls, four layers of defense. A content filter at the front door, evaluators proving the answer is grounded, tracing that gives you the receipt, and agent governance that limits what can happen and who approves it. Responsible AI on the AI-103 isn't a vibe -- it's these four things, configured and verified. Filter, evaluate, audit, govern. I'll see you in the next one.
