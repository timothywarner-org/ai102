# AI-102 Azure Video Indexer Demo

## Overview

This demo showcases how to use **Azure Video Indexer** to analyze a public YouTube video using Node.js. It is designed for the AI-102 course and demonstrates best practices for polling, progress metering, and legal compliance.

---

## Legal Attribution

- **Video Analyzed:**
  - Title: *Azure AI Video Indexer: Overview and Demo* by Microsoft Azure
  - URL: [https://www.youtube.com/watch?v=4thFay3dg3I](https://www.youtube.com/watch?v=4thFay3dg3I)
- **Usage:**
  - This video is publicly available on YouTube and is used strictly for educational, non-commercial demonstration purposes in accordance with YouTube's Terms of Service and Microsoft's AI-102 course requirements.

---

## How to Run the Demo

### 1. Prerequisites
- Node.js (v16+ recommended)
- Azure Video Indexer account and access token
- The following environment variables set in your `.env` file:
  ```env
  VIDEO_INDEXER_REGION=eastus
  VIDEO_INDEXER_ACCOUNT_ID=161dadcb-4336-4356-b816-278b3591c2e4
  VIDEO_INDEXER_ACCESS_TOKEN=YOUR_ACCESS_TOKEN
  ```

### 2. Install Dependencies
```bash
npm install
```

### 3. Run the Demo Script

#### One-time run:
```bash
node video-indexer-ai102-demo.js
```

#### Live development (auto-reloads on changes):
```bash
npm run dev:video
```

- This uses [nodemon](https://www.npmjs.com/package/nodemon) to watch for file changes and restart the script automatically.

---

## What the Script Does
- Uploads a public YouTube video to Azure Video Indexer for analysis
- Polls for indexing status with a real-time progress bar
- Fetches and prints summarized insights (faces, brands, locations, people, topics, and transcript excerpt)
- Provides clear legal annotation and references

---

## References
- [Azure Video Indexer API Quickstart](https://learn.microsoft.com/en-us/azure/azure-video-indexer/video-indexer-use-apis)
- [Azure Video Indexer Samples (GitHub)](https://github.com/Azure-Samples/azure-video-indexer-samples)

---

## Support & Attribution
- Script author: Tim Warner (for AI-102 demos)
- For issues or questions, please open an issue in this repository or contact the course author. 