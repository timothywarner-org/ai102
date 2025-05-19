# Azure App Insights Node.js Sample App

## Overview

This is a simple Node.js Express web app instrumented with Azure Application Insights. It is designed for demos, workshops, and hands-on labs for AI-102 and observability best practices.

**Features:**
- Tracks requests, dependencies, exceptions, and traces in Azure Application Insights
- Exposes endpoints for success, error, and dependency scenarios
- Includes a load test script to generate telemetry

---

## Prerequisites
- Node.js 14+ (LTS recommended)
- Azure Subscription with Application Insights resource

---

## Setup

1. **Clone the repo:**
   ```bash
   git clone <your-repo-url>
   cd azure-appinsights-node-sample-app
   ```
2. **Install dependencies:**
   ```bash
   npm install
   ```
3. **Configure environment variables:**
   Create a `.env` file with your Application Insights Instrumentation Key:
   ```env
   InstrumentationKey=YOUR_APP_INSIGHTS_KEY
   # Optional: LOG_ANALYTICS_WORKSPACE_ID=...
   ```

---

## Running the App

```bash
npm start
```

The app will listen on `http://localhost:3000` by default.

---

## Endpoints

- `/api/names` — Returns a list of names (success)
- `/api/error` — Returns a 500 error (intentional failure)
- `/api/dependency` — Calls itself to simulate a dependency
- `/status` — Health check

---

## Generating Load (Populating App Insights)

A load test script is included to generate traffic and telemetry:

1. **Install axios (if not already):**
   ```bash
   npm install axios
   ```
2. **Run the load test:**
   ```bash
   node loadtest.js
   ```
   - Customize with environment variables:
     ```bash
     BASE_URL=http://localhost:3000 TOTAL_REQUESTS=200 CONCURRENCY=20 node loadtest.js
     ```

---

## Observability Best Practices

- All requests, dependencies, and exceptions are tracked in Azure Application Insights.
- Use the Azure Portal to view live metrics, failures, and distributed traces.
- For production, rotate your Instrumentation Key and use managed identities where possible.
- Keep dependencies up to date and monitor for security alerts (Dependabot, GHAS).

---

## CI/CD & Security

- Add a GitHub Actions workflow for linting, testing, and security scanning.
- Use secret scanning and branch protection rules.
- Reference: [OWASP Node.js Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Nodejs_Security_Cheat_Sheet.html)

---

## Next Steps
- Explore Application Insights dashboards and analytics.
- Extend the app with custom telemetry or additional endpoints.
- Integrate with Azure Monitor and Log Analytics for end-to-end observability.

---

*Keep building, keep observing, and may your traces always be correlated!*
