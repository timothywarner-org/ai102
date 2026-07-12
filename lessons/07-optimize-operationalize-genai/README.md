# Optimize and operationalize generative AI systems

Part of **Objective domain 2: Implement generative AI and agentic solutions** (30-35%), Lesson 7 (L7).

This objective group spans three lessons, L7, L8, and L9. L8 and L9 also contribute to the "Build generative applications by using Foundry" group (Modules 06, 08, 09). The full objective list below is shown verbatim.

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Tune generation behavior, such as prompt engineering and adjusting model parameters
2. Implement model reflection, chain-of-thought evaluations, and self-critique loops
3. Set up observability by implementing tracing, token analytics, safety signals, and latency breakdowns
4. Orchestrate multiple models, flows, or hybrid LLM and rules engines

## The demo: steer the model on purpose

`m07_prompt_demo.py` is a live, keyless, read-only demo that walks the three objectives the
**deck** teaches, in order (full talk track: `Warner.AI-103.Lesson-07-demo-runbook.md`):

| Beat | What the code shows | Key API |
|---|---|---|
| **Tune generation (dials)** | `max_output_tokens` truncates (status=incomplete); `temperature` is REJECTED by the reasoning model; tune `reasoning_effort` (low vs high, with timing) | `responses.create(..., max_output_tokens=, reasoning={"effort":})` |
| **Prompt patterns** | role prompting, few-shot, **structured output** (a JSON schema the model must satisfy), grounding | `responses.create(..., instructions=, text={"format":{"type":"json_schema"}})` |
| **Reflection / self-critique** | draft -> self-score (1-5 as JSON) -> critique-guided retry | a score-then-retry loop |

Runs on **gpt-5-mini**, a reasoning model -- which is *why* temperature is rejected and
`reasoning_effort` is the dial. On a standard model (gpt-4o-mini, gpt-4.1) temperature would be
accepted; the demo adapts either way.

## Setup and run

```bash
cd lessons/07-optimize-operationalize-genai
uv sync
az login
cp .env.example .env        # FOUNDRY_PROJECT_ENDPOINT (proj-lesson-07) + MODEL_DEPLOYMENT_NAME

uv run python m07_prompt_demo.py            # all three beats
uv run python m07_prompt_demo.py --dry-run  # print the plan; call nothing
```

The `# %%` cell markers let you run one beat at a time in the VS Code Interactive Window while you narrate.

> Note: the Node.js `node-demo/` skeleton is superseded by `m07_prompt_demo.py`.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
