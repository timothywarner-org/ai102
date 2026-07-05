# Apply language model text analysis

Part of **Objective domain 4: Implement text analysis solutions** (10-15%), Lesson 15 (L15).

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Implement solutions to extract entities, topics, summaries, and structured JSON outputs by using generative prompting and Foundry Tools
2. Configure detection of sentiment, tone, safety issues, and sensitive content
3. Build solutions that translate text by using Azure Translator in Foundry Tools or LLM-powered translation flows
4. Customize language model outputs for domain tasks, such as compliance summarization and domain extraction

## Demos

Run demos directly from this folder.

This module contains a **Node.js skeleton** under `node-demo/` (`translate.js`), carried over during the AI-103 restructure. It is a scaffold, not a finished demo. It maps to LO3 (translate text by using Azure Translator).

```bash
cd node-demo
cp .env.sample .env   # fill in your Translator / Foundry values
npm install
node translate.js "Hello world"
```

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
