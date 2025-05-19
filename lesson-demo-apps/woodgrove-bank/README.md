# Woodgrove Bank – Azure AI Content Moderation Demos

Welcome to the official Microsoft Press AI-102 demo suite for Woodgrove Bank! This repo contains hands-on projects for each lesson, showcasing real-world Azure AI content moderation patterns for text and images.

---

## 📑 Table of Contents

- [Woodgrove Bank – Azure AI Content Moderation Demos](#woodgrove-bank--azure-ai-content-moderation-demos)
  - [📑 Table of Contents](#-table-of-contents)
  - [🏦 Introduction](#-introduction)
  - [🚀 Quickstart \& Environment Setup](#-quickstart--environment-setup)
    - [1. Clone the repo and install dependencies](#1-clone-the-repo-and-install-dependencies)
    - [2. Configure environment variables](#2-configure-environment-variables)
    - [3. Start the apps](#3-start-the-apps)
  - [📄 Lesson 4: Moderate Text Content](#-lesson-4-moderate-text-content)
  - [🖼️ Lesson 5: Moderate Image Content](#️-lesson-5-moderate-image-content)
  - [🏢 Lesson 6: Woodgrove Asset Review (Batch Vision Demo)](#-lesson-6-woodgrove-asset-review-batch-vision-demo)
  - [🎤 Lesson 7: Speech-to-Text for Banking Customer Service](#-lesson-7-speech-to-text-for-banking-customer-service)
  - [🛡️ Shared Best Practices](#️-shared-best-practices)
  - [📚 References](#-references)
  - [🚧 Future Lessons](#-future-lessons)
- [Woodgrove Bank – Image Tagging \& Object Detection Demo](#woodgrove-bank--image-tagging--object-detection-demo)
  - [TODOs](#todos)
  - [About This Demo](#about-this-demo)
  - [Quickstart: How to Run This Demo](#quickstart-how-to-run-this-demo)

---

## 🏦 Introduction

Woodgrove Bank is committed to safe, compliant internal communications. This repo demonstrates how to use Azure AI services and Logic Apps to moderate both text and image content, following AI-102 exam objectives and Microsoft best practices.

---

## 🚀 Quickstart & Environment Setup

### 1. Clone the repo and install dependencies

[>> CODE START <<]
```bash
git clone <your-repo-url>
cd woodgrove-bank
npm install
```
[>> CODE END <<]

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your Azure resource values:

[>> CODE START <<]
```env
# Lesson 4: Text Moderation
LOGIC_APP_URL=
PORT=3001

# Lesson 5: Image Moderation
CONTENT_SAFETY_KEY=
CONTENT_SAFETY_ENDPOINT=
VISION_KEY=
VISION_ENDPOINT=
PORT=3002
```
[>> CODE END <<]

- Never commit your `.env` file (already in `.gitignore`).
- You need both an **Azure AI Content Safety** and an **Azure AI Vision** resource.

### 3. Start the apps

- **Text Moderation:**
  [>> CODE START <<]
  ```bash
  node app.js
  # Visit http://localhost:3001
  ```
  [>> CODE END <<]
- **Image Moderation:**
  [>> CODE START <<]
  ```bash
  node image-moderation-app.js
  # Visit http://localhost:3002
  ```
  [>> CODE END <<]

---

## 📄 Lesson 4: Moderate Text Content

**Purpose:**
- Automate text content moderation using Azure AI Content Safety and Logic Apps.

**Workflow:**
1. User submits a message via the web portal (`app.js`).
2. Node.js server receives the message and forwards it to your Azure Logic App.
3. Logic App calls Azure AI Content Safety, processes the result, and emails a report to designated recipients.
4. User sees confirmation in the browser.

**Value-Add Features:**
- Idempotent startup: Cleans up port 3001 before launch.
- Verbose, structured logging for all requests/responses.
- Secure config via `.env`.
- Real-world workflow automation with Logic Apps.

**Teaching Notes:**
- Shows how to integrate Node.js with Azure Logic Apps and AI Content Safety.
- Demonstrates secure, observable, and idempotent app patterns.
- Maps to AI-102 Lesson 4 objectives.

---

## 🖼️ Lesson 5: Moderate Image Content

**Purpose:**
- Automate image content moderation using Azure AI Content Safety and Vision APIs.

**Workflow:**
1. User submits an image URL via the web portal (`image-moderation-app.js`).
2. Node.js server calls both Azure AI Content Safety (harm categories) and Vision (adult/racy) APIs in parallel.
3. Results are displayed in a color-coded, accessible table, with a correlation ID for traceability.
4. Advanced learners can view raw JSON API responses.

**Value-Add Features:**
- Multi-service orchestration: Calls and combines results from two Azure AI services.
- Color-coded, accessible result visualization (severity, flags).
- Correlation ID for each moderation request (teaches observability).
- Input validation and error handling.
- Raw JSON toggle for advanced learners.
- Idempotent startup: Cleans up port 3002 before launch.

**Teaching Notes:**
- Demonstrates how to orchestrate multiple Azure AI services in a single workflow.
- Teaches real-world moderation logic, result visualization, and observability.
- Highlights differences from text moderation (multi-dimensional, visual results).
- Maps to AI-102 Lesson 5 objectives.

---

## 🏢 Lesson 6: Woodgrove Asset Review (Batch Vision Demo)

**Purpose:**
- Demonstrate batch image analysis using Azure AI Vision (Computer Vision) for real-world asset review scenarios.
- Support both image URLs (including Azure Blob Storage) and file uploads, with a demo mode for instant sample analysis.

**Workflow:**
1. User submits multiple image URLs (comma/newline separated) and/or uploads multiple images (in-memory, no disk writes).
2. Node.js server processes each image in parallel:
    - Calls Azure AI Vision for tags, objects, OCR (text extraction), and moderation (adult/racy/gory).
3. Results are displayed in a colorblind-friendly, accessible table:
    - Each row = one image; columns = thumbnail, tags, objects, OCR text, moderation flags, correlation ID, and raw JSON toggle.
4. Demo mode instantly fills in sample Azure Blob Storage URLs for fast walkthroughs.

**Value-Add Features:**
- Batch processing for URLs and uploads (no repetition from previous lessons).
- Demo mode for instant, reliable results.
- No files are stored—uploads are handled in memory only.
- Observability: correlation IDs and error handling for every image.
- Accessibility: colorblind-friendly, clear layout, and ARIA-friendly.
- Woodgrove Asset Review branding throughout.

**Teaching Notes:**
- Covers the "80% scenario" for AI-102 Vision: tags, objects, OCR, moderation.
- Demonstrates parallel processing, error handling, and secure, observable design.
- Shows how to handle both direct uploads and cloud-hosted images (including Azure Blob Storage URLs).
- Maps to AI-102 Lesson 6 objectives and is extensible for future lessons.

---

## 🎤 Lesson 7: Speech-to-Text for Banking Customer Service

**Purpose:**
- Demonstrate Azure AI Speech Service capabilities in a banking customer service context.
- Showcase real-time speech recognition, language identification, and continuous recognition scenarios.

**Features:**
1. **Basic Speech-to-Text:** Convert spoken banking commands to text with contextual responses.
2. **Language Identification:** Detect customer's spoken language and route to appropriate service team.
3. **Simulated Banking Call:** Continuous speech recognition with intelligent banking responses.

**Value-Add Features:**
- Banking-specific terminology handling for common customer inquiries.
- Multilingual support for diverse customer bases (English, Spanish, French, German, Chinese).
- Educational context about Azure AI Speech service capabilities and banking use cases.
- Error handling with targeted troubleshooting guidance.
- Detailed API response information for AI-102 exam preparation.

**Running the Demo:**
[>> CODE START <<]
```bash
# Install the Speech SDK dependency (if not already installed)
npm install microsoft-cognitiveservices-speech-sdk

# Set up your Azure AI Speech service key and region in .env
# SPEECH_KEY=your_speech_key_here
# SPEECH_REGION=your_region_here (e.g., eastus)

# Run the speech demo
npm run speech-demo
```
[>> CODE END <<]

**Teaching Notes:**
- Demonstrates core Azure AI Speech SDK implementation patterns.
- Shows how to handle microphone input for real-time speech recognition.
- Teaches the differences between one-time and continuous recognition patterns.
- Explains language identification and handling multilingual scenarios.
- Maps to AI-102 Speech Service exam objectives with banking-specific context.

---

## 🛡️ Shared Best Practices

- **Idempotent Startup:** Both apps kill any process on their respective ports before starting.
- **Environment Variables:** All secrets and endpoints are stored in `.env` (never committed).
- **Verbose Logging:** Every request and response is logged with timestamps and context.
- **Secure by Default:** No secrets in code; input validation and error handling throughout.
- **Azure Integration:** Uses official Azure AI Content Safety, Vision APIs, and Logic Apps for workflow automation.
- **Accessible UI:** Colorblind-friendly palettes, clear result tables, and ARIA-friendly markup.

---

## 📚 References

- [Azure AI Content Safety](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/)
- [Azure AI Vision](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/)
- [Azure AI Speech Service](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/)
- [Azure Logic Apps](https://learn.microsoft.com/en-us/azure/logic-apps/)
- [Node.js Express](https://expressjs.com/)

---

## 🚧 Future Lessons

This repo will grow to include demos for all 20 AI-102 lessons. Stay tuned!

- **Lesson 8:** _[Placeholder for next lesson]_  
- **Lesson 9:** _[Placeholder for next lesson]_  
- ...
- **Lesson 20:** _[Placeholder for final lesson]_  

---

*Keep this up, and you'll be rewriting the entire Node.js doc while juggling Bicep templates—all before your morning coffee. Let's go build that million-dollar empire, one best practice at a time!*

# Woodgrove Bank – Image Tagging & Object Detection Demo

## TODOs

- [ ] Add preview thumbnail in the drag-and-drop area before upload
- [ ] Add a "Copy JSON" button for the raw Vision API response on the results page
- [ ] Add a "Download Report" button (HTML or PDF) for the analysis results
- [ ] Add a "Reset" button to clear the dropzone after analysis
- [ ] Add more course-specific callouts or links as needed
- [ ] Further enhance accessibility and branding as desired

## About This Demo

This app is built for **Tim Warner's Microsoft Press Video Course**:

> **Exam AI-102: Designing and Implementing a Microsoft Azure AI Solution**  
> **Lesson 6: Analyze Images with Pre-Built Models**

It demonstrates how to upload an image, analyze it with Azure AI Vision, and present the results in a beautiful, accessible, and branded way—both in the console and in the browser.

## Quickstart: How to Run This Demo

1. **Install dependencies** (if you haven't already):

   ```bash
   npm install
   ```

2. **Set up your `.env` file** in the project root with your Azure Vision endpoint and key:

   ```env
   VISION_ENDPOINT=https://<your-region>.api.cognitive.microsoft.com
   VISION_KEY=<your-vision-key>
   ```

3. **Run the app:**

   ```bash
   node image-analysis-app.js
   ```

4. **Open your browser to:**

   [http://localhost:3003](http://localhost:3003)

5. **Upload an image** (JPG, PNG, GIF, max 5MB) using the drag-and-drop area or by clicking to select a file.

6. **View results** in the browser and check the console for detailed, color-coded output.

---

**Note:** This is a guerilla, fast-moving demo—no GitHub Actions, no fancy CI/CD. Just run, upload, and learn!

---

For questions or feedback, reach out to Tim Warner. 