# Warner.AI-103.Lesson-07 -- Demo Runbook

**Lesson 7: Prompt Engineering and Optimizing Generation Behavior**
*(Exam mapping: Domain 2 -> "Optimize and operationalize generative AI systems")*
**Runtime target: ~13-15 minutes | Execution context: Microsoft Foundry portal (Edge) + VS Code**
**Model: `gpt-5-mini` (2025-08-07) -- a REASONING model (this changes Beat 1; see the note below)**

---

## Demo surface (why each beat lives where it lives)

| Beat | Deck section | Surface | Why here |
|---|---|---|---|
| 1. Generation parameters + the reasoning-model twist | 7.1 (slides 3-4) | Foundry **playground** + `View code` | The dials are a UI story; the twist is proven in the request |
| 2. Prompt engineering patterns | 7.2 (slide 6) | Foundry **playground** | Role, few-shot, structured output, grounding are visual and iterative |
| 3. Self-critique loop | 7.3 (slides 9-10) | **VS Code** + Python SDK | A loop that scores and retries is naturally code |

> **THE ONE THING that will bite you on camera:** `gpt-5-mini` is a reasoning
> model, so it **ignores `temperature`/`top_p`/penalties and rejects `max_tokens`.**
> Beat 1 is built around that reality on purpose -- we teach the five classic dials
> (they're real and exam-testable on non-reasoning models), then reveal what a
> reasoning model actually gives you: `reasoning_effort`, `verbosity`, and
> `max_completion_tokens`. Do the 60-second dry run in the pre-flight so the
> playground's reasoning-model UI holds no surprises.

---

## Pre-flight checklist (do this BEFORE you hit record)

- [ ] **Env is up.** The lesson environment exists (see `infra/README.md`; `infra/ai103-lesson-env.bicep` builds account + project + model in one deployment). Copy its project endpoint into this folder's `.env`: `cp .env.example .env`, then fill `FOUNDRY_PROJECT_ENDPOINT` and `MODEL_DEPLOYMENT_NAME`.
- [ ] **Quota is clean.** The purge reclaimed the old ~100K TPM; new deployment is 50K TPM GlobalStandard.
- [ ] **Signed in.** `az login` done; you're on subscription `YOUR-SUBSCRIPTION-NAME`.
- [ ] **Roles propagated.** Gave it ~2 minutes after deploy so `Cognitive Services OpenAI User` is live (else the SDK 401s).
- [ ] **Python ready.** `uv sync` from this lesson folder. No venv activation needed; `uv run` handles it.
- [ ] **Smoke test (off camera).** `uv run python m07_prompt_demo.py --dry-run` prints the plan without calling the model. If that is clean, run it live once to confirm the deployment answers.
- [ ] **Browser staged.** Edge at **ai.azure.com** -> your project -> **Playgrounds -> Chat**, `gpt-5-mini` selected in the deployment dropdown.
- [ ] **Dry run the reasoning UI.** In the playground, confirm what controls show for `gpt-5-mini` (reasoning effort / verbosity) and that `View code` reflects them. Know this before you record.
- [ ] **VS Code staged.** `m07_prompt_demo.py` open; terminal at the lesson folder; font bumped for legibility. The `# %%` cell markers let you run one beat at a time in the Interactive Window.
- [ ] **Zoom/scale.** Portal at 100-110%, VS Code at a recording-legible size.

### First-use terms to define on camera (keep it to a clause each -- the audience are engineers)

- **Reasoning model** -- a model that plans internally before it answers; `gpt-5-mini` is one.
- **`reasoning_effort`** -- how hard it thinks: `minimal`, `low`, `medium`, `high`.
- **`verbosity`** -- how much it writes back: `low`, `medium`, `high`.
- **`max_completion_tokens`** -- the response-length ceiling that replaces the old `max_tokens` on these models.
- **Project endpoint** -- the per-project URL the SDK targets, not the raw model endpoint.

### Test strings (paste these -- don't improvise on tape)

- **Params prompt:** `Explain what a Foundry project is to a new Azure developer.`
- **Role message:** `You are a careful cloud cost analyst for Contoso. Be terse.`
- **Grounding question (should refuse):** `What is the DataZoneStandard price?`
- **Reflection task (already in `beat_reflection`):** `Explain the difference between GlobalStandard and Provisioned deployment types in Azure AI Foundry.`

---

## Beat 1 -- The dials, and the reasoning-model twist (~4 min)

[SAY] Let me show you where every model call really starts, which is underneath the
prompt, at the generation parameters. On the slides we met the five classic dials:
temperature, top-p, max tokens, and the two penalties. Those are real, and the exam
loves them. Now here's the twist that catches people, and it's a good one to know
cold: the model we deployed, `gpt-5-mini`, is a reasoning model, and reasoning models
don't play by the classic-dial rules.

[DO] In the Foundry playground, open the parameters/setup panel for the `gpt-5-mini` deployment.
[VERIFY] You see reasoning-model controls (reasoning effort, verbosity). Temperature/top-p are absent or inert for this deployment.

[SAY] Notice what's here and what isn't. On a plain chat model like gpt-4o, you'd
see a temperature slider front and center. On this reasoning model, that dial is
gone, and in its place we get two better ones: reasoning effort, which is how hard
the model thinks before it speaks, and verbosity, which is how much it writes back.
Those are different jobs, and separating them is the whole point.

[DO] Paste the params prompt. Set reasoning effort to `minimal`, send. Then set it to `high`, send again.
[VERIFY] The `high` answer is visibly more worked-through; token usage is higher.

[SAY] Watch the difference. On minimal effort the model gives me a quick, competent
answer. On high effort it thinks longer, and you can see that thinking in the token
count climbing. That's the quality-versus-cost tradeoff made concrete: you're paying
for the reasoning, so you spend it where the problem earns it.

[DO] Click **View code**. Point at the request body.
[VERIFY] The code shows `reasoning_effort` and `max_completion_tokens`; there is no `temperature` and no `max_tokens`.

[SAY] And here's the money: `View code` never lies. Look at the request the playground
actually sends. There's `reasoning_effort`, there's `max_completion_tokens` -- the
ceiling that replaced `max_tokens` on these models -- and there's no temperature to
be found. So if a teammate swears they set temperature on `gpt-5-mini` and nothing
changed, now you know why. It wasn't ignored by accident; the model doesn't take it.

[PAUSE] Hold two beats on the `View code` request body for the zoom edit.

[IF IT BREAKS] If the playground UI for the reasoning model surprises you, cut to VS
Code and run the `beat_parameters` cell in `m07_prompt_demo.py`. It sends temperature on
purpose, catches the rejection, then shows reasoning_effort and the token ceiling live and
deterministically. That's the airtight version of this exact beat.

[SAY] So the one-liner for Beat 1: the five classic dials are exam-real on
non-reasoning models, and on a reasoning model like this one you steer with reasoning
effort, verbosity, and the completion-token ceiling instead. Does that distinction
land? Good, because the exam will absolutely poke at it.

---

## Beat 2 -- Prompt engineering patterns (~4-5 min)

[SAY] With the dials sorted, let's move up to the prompt itself, and to the named
patterns that turn prompt writing from freestyling into a craft. I'll show you four
that you'll reach for on almost every serious prompt.

[DO] In the playground's system/developer message box, paste the role message: `You are a careful cloud cost analyst for Contoso. Be terse.` Send a question like "Why start on GlobalStandard instead of Provisioned?"
[VERIFY] The answer's tone shifts: terse, analyst-flavored.

[SAY] That's role prompting: you tell the model who to be before you tell it what to
do, and it primes the tone and the vocabulary for the whole response. One line of
persona, and every answer after it comes back in character.

[DO] Add two worked examples as prior turns (ticket -> label), then send a new unlabeled ticket.
[VERIFY] The model returns just the label, matching the demonstrated pattern.

[SAY] Next up is few-shot. Instead of describing what I want in a paragraph of
adjectives, I show the model two worked examples and let it infer the pattern. A
couple of concrete demonstrations teach it more than a wall of instructions ever
could. Watch it nail the third one from the two I gave it.

[DO] Switch to grounding: set the developer message to "Answer ONLY from the CONTEXT; if it isn't there, say so." Provide a short SKU context. Ask the grounding question: `What is the DataZoneStandard price?`
[VERIFY] The model refuses -- it says the answer isn't in the context instead of inventing a number.

[SAY] Now here's the pattern that keeps you out of trouble: grounding. I've told the
model to answer only from the context I hand it, and I've asked for a price that isn't
in that context. A model without guardrails would cheerfully make up a number. This
one tells me it's not there. That refusal is the model declining to hallucinate, and
in a real product that's exactly the behavior you want.

[DO] Click **View code**; point at `response_format` with the JSON schema for the structured-output pattern.
[VERIFY] The request carries a `json_schema` with `strict: true`.

[SAY] And the fourth pattern is structured output, which is the exam's favorite. When
another system has to read the model's answer, you can't accept loose prose. You hand
the model a JSON schema through the Responses API's `text={"format": ...}` parameter with
`strict: True`, and it's contractually bound to return data that fits. That's the difference
between politely asking for JSON and actually guaranteeing it. If you want the full code
version, the `beat_patterns` cell in `m07_prompt_demo.py` runs all four of these end to end.

[PAUSE] Clean seam here before we move to code.

[SAY] So that's the toolbox: role prompting to set the frame, few-shot to teach by
example, grounding to keep it honest, and structured output to make the result
machine-readable. Pick the pattern that fits the job instead of improvising.

---

## Beat 3 -- The self-critique loop (~5-6 min)

[SAY] Now let's close the loop, literally. Everything so far has been a single shot:
ask once, take what you get. The professional move on hard problems is to make the
model check its own work before it hands it over. Let me show you a self-critique
loop, and it's only about forty lines of real code.

[DO] In VS Code, open `m07_prompt_demo.py`. Scroll to the `beat_reflection()` function.
[VERIFY] The five steps are visible: generate, critique, retry-with-guidance, cap, log.

[SAY] Here's the shape, and it maps one-to-one to the slide. First we generate a
draft. Then a second call, the critic, scores that draft against explicit criteria
and returns structured numbers, not a vibe. If it passes, we're done. If it doesn't,
we don't just rerun the same prompt -- we hand the critique back to the model so the
retry knows exactly what to fix. And two guardrails wrap the whole thing: a hard cap
on retries so a stubborn case can't spin the meter forever, and a log line on every
attempt so you've got an audit trail.

[DO] Point at the `CRITIC_SCHEMA` and the `reasoning_effort="medium"` on the critic call.
[VERIFY] Critic uses a strict JSON schema and a higher reasoning effort than the generator.

[SAY] Two design choices worth calling out. The critic returns strict JSON -- that's
our structured-output pattern from Beat 2 doing real work, because the loop has to
branch on a number, not parse a paragraph. And I let the critic think a little harder
than the writer, because judging is the part that's worth the extra reasoning.

[DO] Run it: `uv run python m07_prompt_demo.py`. Let the console stream the attempts.
[VERIFY] Console shows attempt lines with scores; it either PASSES on an attempt or hits the retry cap, then prints the final answer.

[PAUSE] Let the loop finish; hold on the final answer for the edit.

[SAY] Watch the loop breathe. Attempt one comes back, the critic scores it, and if
it's short of the bar you can see the guidance it hands back for the next pass. Now
you might be thinking, hang on, Tim, isn't this just three model calls dressed up?
It is, and that's the point -- three cheap calls that catch the model's own mistakes
cost a lot less than one wrong answer reaching a customer.

[SAY] One more thing for the real world. You wouldn't hand-roll this critic forever.
In production you graduate it to the Foundry Evaluation SDK, which runs this same
idea in batch with built-in evaluators for relevance and groundedness, and surfaces
the scores right in the Foundry portal. This plain-Python loop is the concept you
build that on. That's your bridge from Lesson 7 into the observability and evaluation
work coming up next.

[IF IT BREAKS] If a call 401s, your role assignment hasn't propagated -- wait a beat
and rerun. If it can't find the endpoint, this folder's `.env` is missing or incomplete;
copy `.env.example` to `.env` and paste the project endpoint in by hand.

---

## Wrap (~30-45 sec)

[SAY] Let me give you the one-two-three. One, on a reasoning model you steer with
reasoning effort and verbosity, not temperature. Two, the prompt patterns -- role,
few-shot, grounding, and structured output -- are named tools, so reach for the one
that fits. And three, a self-critique loop of generate, score, and retry beats a
single shot every time on the problems that matter. That's how you optimize what a
model produces and start operationalizing it for production.

[PAUSE] Stop recording here.

---

## Cleanup

- **Leave the environment running.** This same account, project, and `gpt-5-mini`
  deployment are reused for Lessons 8 and 9. No teardown between lessons.
- **When you DO want it gone** (end of Domain 2 recording): delete the resource group, then
  **purge** the soft-deleted Foundry account before you rebuild. Deleting alone does NOT free
  the TPM or release the account name; purging does. See `infra/README.md` for the purge
  command and the rebuild path via `infra/ai103-lesson-env.bicep`.
- **Quota check anytime:** the account holds 50K TPM of the 500K gpt-5-mini budget --
  plenty of headroom for L8/L9 without hoarding.
