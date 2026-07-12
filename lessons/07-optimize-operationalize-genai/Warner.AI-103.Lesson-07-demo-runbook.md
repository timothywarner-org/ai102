# Lesson 7 Demo Runbook -- Prompt Engineering and Optimizing Generation Behavior

**On screen, one surface:** VS Code in the `ai103` project. This is a steering lesson, so we live in code and run it live.
**File under the mouse:** `lessons/07-optimize-operationalize-genai/m07_prompt_demo.py`.
Read-only demo -- it only calls the model, mutates nothing. Blocks: **[SAY]** - **[DO]** - **[VERIFY]** - **[PAUSE]**.

## Pre-flight (before recording)
- `az login` done; VS Code on the `ai103` workspace, `m07_prompt_demo.py` open, integrated terminal ready.
- `.env` filled: `FOUNDRY_PROJECT_ENDPOINT` = the **proj-lesson-07** endpoint, `MODEL_DEPLOYMENT_NAME=gpt-5-mini`.
- `uv sync` already run. Do a silent `uv run python m07_prompt_demo.py --dry-run` once to confirm the plan.

---

## Cold open  (~30s)

[SAY] This whole lesson is about one thing: steering a model on purpose instead of hoping for the best. And we do it in three moves. First the dials, the generation parameters underneath every call. Then the patterns, the named prompt moves that turn guesswork into a craft. And finally the self-critique loop, where the model grades and fixes its own work. All keyless, all live. Let's steer.

---

## Segment 1: Tune generation behavior -- the dials  (LO7.1, ~4 min)

[SAY] Start with the ceiling on length. Max output tokens is a hard cap, and on a reasoning model that budget also covers the hidden thinking, so if I set it tight the answer gets cut off. Watch the status come back as incomplete -- that's the cap doing its job, and it's a real cost and user-experience control.

[DO] **VS Code** > `m07_prompt_demo.py` > run the **parameters cell** (`beat_parameters`) with **Shift+Enter**.
[VERIFY] The terminal shows `max_output_tokens=220 -> status=incomplete (stopped early: max_output_tokens)`.

[SAY] Now here's the one everybody reaches for first, and the trap the exam loves. You might go straight for temperature to make the model more or less creative. Watch what happens when I send it.
[VERIFY] The call fails with `temperature REJECTED` -- the model refuses the parameter outright.
[SAY] That's not a bug. gpt-5 and the o-series are reasoning models, and they don't take temperature or top-p at all. Their dial is reasoning_effort. So on a standard model you'd tune temperature and top-p; on a reasoning model you tune effort, and higher effort means more thinking, which you can see in the timing -- low comes back faster than high.

[PAUSE] Hold on the temperature-rejected line and the two effort timings.
[IF IT BREAKS] If your deployment is a standard model, temperature will be accepted instead of rejected -- narrate that, and note the reasoning-model exception is what the exam tests.

---

## Segment 2: Prompt engineering patterns  (LO7.2, ~4 min)

[SAY] Now the patterns, the everyday moves. Role prompting sets a persona through the instructions, so the same question comes back in a different voice. Few-shot teaches by showing two or three worked examples instead of describing what you want. Structured output is the big one: I hand the model a JSON schema and it must return data that fits, every time -- that's how you get an answer another system can actually read. And grounding tells the model to answer only from the context I give it, and to refuse when the answer isn't there.

[DO] **VS Code** > run the **patterns cell** (`beat_patterns`).
[VERIFY] Four results print: a terse SRE answer, a POSITIVE classification, a clean JSON object with product/sentiment/issues, and a grounded reply that says "Not in the provided context."

[SAY] Look at that JSON. No prose to parse, no regex, no hoping -- the schema is a contract the model has to satisfy. That structured-output move is the one the exam points at when a stem says "guarantee the output parses."

[PAUSE] Hold on the JSON object.

---

## Segment 3: Reflection and self-critique  (LO7.3, ~3.5 min)

[SAY] Last move, and it's the one that turns a one-shot guess into a quality process. I have the model draft an answer, then I make it grade its own draft against criteria and hand me a score and a critique as JSON. If the score is low, I don't just rerun the same prompt -- I feed the critique back in so the retry knows exactly what to fix.

[DO] **VS Code** > run the **reflection cell** (`beat_reflection`).
[VERIFY] A deliberately terse draft prints, then a self-score of 1 out of 5 with a pointed critique, then a much stronger critique-guided retry.

[SAY] That's the loop: review, score, retry, and cap the retries so it can't spin forever. The model caught its own thin answer and fixed it before any user saw it -- and that's the answer the exam wants when a stem asks how to raise quality without adding a human reviewer.

[PAUSE] Hold on the one-out-of-five score next to the improved answer.

---

## Close  (~30s)

[SAY] Three moves, one throughline: you're in control. You tune the dials for the model you actually have, you reach for the named pattern that fits the job, and you let the model critique itself before it ships. That's prompt engineering as an engineering discipline, not a vibe. I'll see you in the next one.
