# Build agents by using Foundry

Part of **Objective domain 2: Implement generative AI and agentic solutions** (30-35%), Lesson 10 (L10).

This objective group spans two lessons, L10 and L11. The full objective list is shown verbatim in both modules so neither drops a learning objective.

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Define agent roles, goals, conversation-tracking approach, and tool schemas
2. Build agents that integrate retrieval, function-calling, and conversation memory
3. Integrate agent tools, including APIs, knowledge stores, search, content understanding, and custom functions
4. Implement orchestrated multi-agent solutions
5. Build autonomous or semiautonomous workflows with safeguards and approval flow controls
6. Integrate monitoring into deployed agents, evaluate agent behavior, and perform error analysis

## Demos

Run demos directly from this folder.

This module contains a **Node.js skeleton** under `node-demo/` (`index.js`), carried over during the AI-103 restructure. It is a scaffold, not a finished demo. Treat it as a starting point for an agent demo on Foundry.

```bash
cd node-demo
cp .env.sample .env   # fill in your Foundry project values
npm install
node index.js
```

## Parked demo ideas

- **Agent endpoint URIs (parked from Lesson 3):** briefly create an agent and showcase its endpoint URIs -- the stable project/agent endpoint, plus latest-vs-pinned version routing. It came up in the L3 demo but derailed that lesson's monitoring throughline, so it lives here with the agent lessons (L10/L11) where it's on-topic.

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
