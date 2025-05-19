# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.

# Woodgrove Bank AI-Powered Hotel Search (MVP)

## Overview
This is a React (Vite) MVP for the AI-102 exam scenario: a Woodgrove Bank-branded portal for hotel search and receipt analysis, using Azure AI Search and Document Intelligence (mocked for MVP).

## Why this structure?
- **ai-search-document-intelligence/client/**: Frontend React app (Vite, JS)
- **ai-search-document-intelligence/server/**: (To be added) Express backend for API proxying and document analysis
- **.env**: Backend config only (never expose secrets to frontend)

## How to run
```bash
cd ai-search-document-intelligence/client
npm install
npm run dev
```

## Teaching Notes
- **Faceted search**: Demonstrates enterprise search patterns (exam topic)
- **Mock data**: Fast feedback, easy to swap for real APIs
- **Branding**: Woodgrove Bank, plausible for exam/demo

## Extending
- Replace mock data with real API calls to Azure AI Search and Document Intelligence
- Add authentication, observability, and error handling for production

---

Happy teaching! — Cursor
