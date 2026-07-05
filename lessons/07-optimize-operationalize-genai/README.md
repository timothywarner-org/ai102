# Optimize and operationalize generative AI systems

Part of **Objective domain 2: Implement generative AI and agentic solutions** (30-35%), Lesson 7 (L7).

This objective group spans three lessons, L7, L8, and L9. L8 and L9 also contribute to the "Build generative applications by using Foundry" group (Modules 06, 08, 09). The full objective list below is shown verbatim.

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Tune generation behavior, such as prompt engineering and adjusting model parameters
2. Implement model reflection, chain-of-thought evaluations, and self-critique loops
3. Set up observability by implementing tracing, token analytics, safety signals, and latency breakdowns
4. Orchestrate multiple models, flows, or hybrid LLM and rules engines

## Demos

Run demos directly from this folder.

This module contains a **Node.js skeleton** under `node-demo/` (`generate.js`), carried over during the AI-103 restructure. It is a scaffold, not a finished demo. Treat it as a starting point for an LO1 prompt-and-parameter tuning demo.

```bash
cd node-demo
cp .env.sample .env   # fill in your Foundry project values
npm install
node generate.js "Your prompt"
```

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
