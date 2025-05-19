# Woodgrove Bank AI-102 API Server (Express)

## Overview
This is the backend REST API for the Woodgrove Bank Knowledge Mining demo, built for Azure AI-102 exam prep and real-world teaching. It powers the React frontend with endpoints that model Azure AI Search and Document Intelligence scenarios.

---

## Features
- **Faceted hotel search** (mocked Azure AI Search)
- **Receipt analysis** (mocked Document Intelligence)
- **Hotel detail lookup**
- **Morgan logging, CORS, dotenv config**
- **Idempotent port cleanup (no port conflicts!)**
- **Nodemon for hot reload in dev**

---

## Setup & Run
```bash
cd ai-search-document-intelligence/server
npm install
npm run dev
```
- Default port: **3010** (set `PORT` in `.env` to change)
- Health check: [http://localhost:3010](http://localhost:3010)

---

## API Endpoints
- `POST /api/search` — Search hotels with facets (body: `{ search, city, category, rating }`)
- `POST /api/analyze-receipt` — Mocked receipt analysis (returns hotel name, date, amount)
- `GET /api/hotel/:id` — Get full hotel details by ID

---

## Architecture
```
[ React Frontend ] <--> [ Express API Server ]
         |                    |
         |----/api/search-----|
         |----/api/analyze----|
         |----/api/hotel/:id--|
```

---

## Teaching Notes
- **Exam-aligned:** Endpoints match AI-102 skills (search, analyze, retrieve)
- **Observability:** Morgan logs every request for easy debugging
- **Port cleanup:** No more "address in use" errors in class or demos
- **Separation of concerns:** Clean, modular, and ready for real Azure integration

---

## Extending
- Connect to real Azure AI Search or Document Intelligence APIs
- Add file upload to `/api/analyze-receipt` (see `multer`)
- Add authentication, error handling, or CI/CD
- Serve the React build as static files for production

---

## Troubleshooting
- **Port in use?** The server auto-kills old processes on startup
- **CORS errors?** CORS is enabled for local dev; adjust as needed for prod
- **API not found?** Check the port and endpoint path

---

Happy building, teaching, and demoing! — Cursor 