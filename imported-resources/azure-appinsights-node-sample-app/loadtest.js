/*
 * Load Test Script for Azure App Insights Node.js Demo (AI-102)
 * -------------------------------------------------------------
 * - Generates concurrent HTTP requests to all API endpoints to populate telemetry in App Insights.
 * - Randomizes endpoints: /api/names, /api/error, /api/dependency, /api/slow, /status, /api/dependencyfail
 * - Adds random user/session headers to simulate unique users and sessions.
 * - Logs status codes and errors for each request.
 * - Usage: BASE_URL=http://localhost:3000 TOTAL_REQUESTS=200 CONCURRENCY=40 node loadtest.js
 * - Designed for hands-on demos and workshops to showcase monitoring and observability.
 */
// Simple load generator for Express App Insights demo
const axios = require('axios');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const ENDPOINTS = [
  '/api/names',
  '/api/error',
  '/api/dependency',
  '/api/slow',
  '/status',
  '/api/dependencyfail'
];

const TOTAL_REQUESTS = process.env.TOTAL_REQUESTS ? parseInt(process.env.TOTAL_REQUESTS) : 200;
const CONCURRENCY = process.env.CONCURRENCY ? parseInt(process.env.CONCURRENCY) : 40;

function randomEndpoint() {
  return ENDPOINTS[Math.floor(Math.random() * ENDPOINTS.length)];
}

async function sendRequest(i) {
  const url = BASE_URL + randomEndpoint();
  const userId = Math.floor(Math.random() * 1000);
  try {
    const res = await axios.get(url, {
      headers: {
        'x-user-id': userId,
        'x-session-id': 'sess-' + Math.floor(Math.random() * 10000)
      }
    });
    console.log(`[${i}] ${url} -> ${res.status}`);
  } catch (err) {
    if (err.response) {
      console.log(`[${i}] ${url} -> ${err.response.status} (error)`);
    } else {
      console.log(`[${i}] ${url} -> NETWORK ERROR`);
    }
  }
}

async function runLoadTest() {
  let inFlight = 0;
  let sent = 0;

  return new Promise((resolve) => {
    function next() {
      while (inFlight < CONCURRENCY && sent < TOTAL_REQUESTS) {
        inFlight++;
        sendRequest(sent + 1).finally(() => {
          inFlight--;
          if (sent < TOTAL_REQUESTS) next();
          if (sent === TOTAL_REQUESTS && inFlight === 0) resolve();
        });
        sent++;
      }
    }
    next();
  });
}

runLoadTest().then(() => {
  console.log('Load test complete.');
}); 