# Woodgrove Bank AI-102 Knowledge Mining Demo

## Overview
This solution demonstrates a full-stack Azure AI-102 scenario: Knowledge Mining with Azure AI Search and Document Intelligence, using a modern Express + React architecture. It is designed for exam prep, teaching, and real-world demos.

---

## Features
- **Faceted hotel search** (Azure AI Search sample schema, mock data)
- **Receipt upload & analysis** (Document Intelligence, mocked)
- **REST API backend** (Express, Morgan, CORS, dotenv, nodemon, idempotent port cleanup)
- **Modern React frontend** (Vite, live reload, clean UI, Woodgrove Bank branding)
- **Exam-aligned endpoints and UI**

---

## Architecture
```
[ React Frontend (Vite) ] <--> [ Express REST API (Node.js) ]
         |                                 |
         |--/api/search--------------------|
         |--/api/analyze-receipt-----------|
         |--/api/hotel/:id-----------------|
```
- **Frontend:** `ai-search-document-intelligence/client` (port 5173)
- **Backend:**  `ai-search-document-intelligence/server` (port 3010)

---

## Setup & Run

### 1. Start the API Server
```bash
cd ai-search-document-intelligence/server
npm install
npm run dev
```
- Visit [http://localhost:3010](http://localhost:3010) for health check

### 2. Start the React Frontend
```bash
cd ai-search-document-intelligence/client
npm install
npm run dev
```
- Visit [http://localhost:5173](http://localhost:5173) for the UI

---

## API Endpoints
- `POST /api/search` — Search hotels with facets (body: `{ search, city, category, rating }`)
- `POST /api/analyze-receipt` — Mocked receipt analysis (returns hotel name, date, amount)
- `GET /api/hotel/:id` — Get full hotel details by ID

---

## Teaching Notes
- **Faceted search**: Mirrors Azure AI Search exam scenarios
- **Document analysis**: Models real-world Doc Intelligence use
- **Separation of concerns**: Modern, scalable, and easy to extend
- **Idempotent port cleanup**: No more port conflicts in class or demos

---

## Extending
- Swap mock data for real Azure AI Search/Doc Intelligence calls
- Add file upload to `/api/analyze-receipt`
- Add authentication, logging, or CI/CD workflows
- Deploy as a single app (build React, serve static from Express)

---

Happy teaching, learning, and demoing! — Cursor 