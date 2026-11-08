# 🏦 Woodgrove Bank - Content Safety Groundedness Demo

A simple, interactive Node.js console app that demonstrates how to detect and flag AI-generated content that is not grounded in a provided context—helping you build more responsible, trustworthy AI solutions.

## ✨ What is "Groundedness"?

"Groundedness" means that an AI's response is factually supported by the context it was given. This demo uses Azure AI Content Safety's groundedness detection to:

- Identify when a response is fully supported by the context
- Flag "hallucinations" (unsupported or fabricated content)
- Illustrate Responsible AI practices

## 🚀 Features

- **Interactive Console UI**: Choose from sample prompts and see groundedness analysis in real time
- **Pretty Console Output**: Emojis, color, and clear explanations
- **Responsible AI Focus**: Shows how to detect and handle ungrounded (hallucinated) content
- **Idempotent & Easy to Reset**: Clean console and state on every run

## 🖥️ Example Prompts

1. What is the primary function of a retail bank?
2. What is Know Your Customer (KYC) in banking?
3. Is Woodgrove Bank the oldest bank in the world? *(intentionally hallucinated)*

## 🛠️ Requirements

- Node.js 18+
- An [Azure AI Content Safety](https://learn.microsoft.com/azure/ai-services/content-safety/) resource (for API key and endpoint)

## ⚙️ Setup

1. **Clone this repo**
2. **Install dependencies** (from the repo root):

   ```bash
   npm install
   ```

3. **Create a `.env` file** in `groundedness-api/` with these variables:

   ```env
   CONTENT_SAFETY_KEY=your-azure-content-safety-key
   CONTENT_SAFETY_ENDPOINT=https://your-resource-name.cognitiveservices.azure.com
   # Optional: CONTENT_SAFETY_API_VERSION=2024-09-15-preview
   ```

4. **Run the demo**:

   ```bash
   node groundedness-demo.js
   ```

## 📝 How It Works

- Select a prompt from the menu
- The app sends the prompt, context, and response to Azure Content Safety's groundedness API
- Results are color-coded:
  - ✅ **Green**: All content is grounded
  - ⚠️ **Red/Yellow**: Ungrounded (hallucinated) content detected, with details
- Responsible AI notes and links are shown for further learning

## 📦 Dependencies

- [axios](https://www.npmjs.com/package/axios)
- [chalk](https://www.npmjs.com/package/chalk)
- [dotenv](https://www.npmjs.com/package/dotenv)

## 📚 Learn More

- [Azure AI Content Safety](https://learn.microsoft.com/azure/ai-services/content-safety/)
- [Responsible AI at Microsoft](https://aka.ms/ResponsibleAI)

---

*Demo app for Microsoft AI-102 training. Woodgrove Bank is a fictional institution for educational purposes.*
