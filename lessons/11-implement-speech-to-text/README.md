# Lesson 11: Implement Speech-to-Text Solutions

## Demo: Azure AI Speech-to-Text (Node.js)

This lesson includes a hands-on demo app that shows how to use Azure AI Speech to transcribe audio to text in real time.

### Files Included
- `speech-to-text-demo.js` — Main Node.js demo script
- `.env.sample` — Example environment variables for Azure Speech

## Setup Instructions

1. Copy `.env.sample` to `.env` and fill in your Azure Speech key and region:
   ```env
   SPEECH_KEY=your-speech-key-here
   SPEECH_REGION=your-region-here
   ```
2. Install dependencies:
   ```bash
   npm install microsoft-cognitiveservices-speech-sdk dotenv chalk
   ```
3. Run the demo:
   ```bash
   node speech-to-text-demo.js
   ```

## Teaching Notes
- Demonstrates real-time and batch transcription
- Shows language detection and error handling
- Teaches best practices for environment variables and secure config

---

> For more info, see the official [Azure Speech Service docs](https://learn.microsoft.com/azure/ai-services/speech-service/).

## Subtopics
- 11.1 Use Azure AI Speech to convert speech to text
- 11.2 Optimize transcription models for accuracy

## Code Samples

> Place your lesson-aligned code samples and demos here.

## Instructions
- Add a brief description of each code sample.
- Include setup or environment variable notes if needed. 