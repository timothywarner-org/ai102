# Design and implement multimodal understanding workflows

Part of **Objective domain 3: Implement computer vision solutions** (10-15%), Lesson 13 (L13).

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Build a solution that analyzes visual context by using multimodal models
2. Configure apps to produce concise or detailed captions for single or multiple images
3. Implement a solution that enables question-answering grounded in visual evidence
4. Configure generation of alt-text and extended image descriptions aligned to accessibility guidelines
5. Implement visual understanding by configuring Azure Content Understanding in Foundry Tools to extract visual characteristics
6. Implement video analysis workflows to process and interpret video segments
7. Configure single-task and pro-mode Content Understanding pipelines
8. Implement solutions that identify objects, components, or regions within images or video

## Demos

Run demos directly from this folder.

This module contains a **Node.js skeleton** under `node-demo/` (`app.js`), carried over during the AI-103 restructure. It is a scaffold, not a finished demo. Treat it as a starting point for an LO8 object/region identification demo.

```bash
cd node-demo
cp .env.sample .env   # fill in your Foundry / vision values
npm install
node app.js <path-to-image>
```

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
