# Implement speech solutions

Part of **Objective domain 4: Implement text analysis solutions** (10-15%), Lesson 16 (L16).

## Learning objectives covered

Quoted verbatim from the AI-103 objective domain:

1. Implement workflows to convert speech to text and text to speech for agentic interactions
2. Integrate speech as an agent modality, including custom speech models
3. Enable multimodal reasoning from audio inputs
4. Translate speech into other languages by using language models and Foundry Tools

## Demos

Run demos directly from this folder.

This module contains a **Node.js skeleton** (`speech-to-text-demo.js`), carried over during the AI-103 restructure. It is a scaffold, not a finished demo. It maps to LO1 (convert speech to text).

```bash
cp .env.sample .env   # fill in your Speech key and region
npm install microsoft-cognitiveservices-speech-sdk dotenv chalk
node speech-to-text-demo.js
```

---
Part of the [AI-103 course repository](https://github.com/timothywarner-org/ai103) by Tim Warner.
