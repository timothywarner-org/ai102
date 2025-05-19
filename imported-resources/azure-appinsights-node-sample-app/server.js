/*
 * Azure App Insights Node.js Sample App (AI-102 Demo)
 * ---------------------------------------------------
 * - Simple Express web API instrumented with Azure Application Insights.
 * - Tracks requests, dependencies, exceptions, and traces for observability demos.
 * - Endpoints:
 *     GET  /                  - API info
 *     GET  /api/names         - Returns a list of names (success)
 *     GET  /api/error         - Randomly returns 500 error or 200 OK (for error telemetry)
 *     GET  /api/dependency    - Simulates a dependency call (self-call)
 *     GET  /api/slow          - Delayed response for slow request demo
 *     GET  /api/dependencyfail- Simulates a failed dependency call
 *     GET  /status            - Health check (can be extended for DB checks)
 * - Designed for hands-on labs, workshops, and AI-102 monitoring/telemetry education.
 */
// Requires
require('dotenv').config();
const express = require("express");
const axios = require('axios');
let appInsights = require('applicationinsights');

// Configuration
const port = process.env.PORT || 3000;
const ikey = process.env.InstrumentationKey;

// Instances and configuration
const app = express();
appInsights.setup(ikey)
    .setAutoDependencyCorrelation(true)
    .setAutoCollectRequests(true)
    .setAutoCollectPerformance(true, true)
    .setAutoCollectExceptions(true)
    .setAutoCollectDependencies(true)
    .setAutoCollectConsole(true)
    .setUseDiskRetryCaching(true)
    .setSendLiveMetrics(true)
    .setDistributedTracingMode(appInsights.DistributedTracingModes.AI_AND_W3C)
    .start();
let client = appInsights.defaultClient;

// Middleware
app.use((req, res, next) => {
    let msg = req.method + " " + req.url;
    console.info(msg);
    client.trackTrace({message: msg});
    next();
});

// Routes
app.get("/", (req, res, next) => {
    res.send("API running at: /api/names, /api/error, /api/dependency, /api/slow, /api/dependencyfail, /status")
});

app.get("/api/names", (req, res, next) => {
    res.json(["Tony", "Lisa", "Michael", "Ginger", "Food"]);
});

app.get("/api/error", (req, res, next) => {
    if (Math.random() < 0.5) {
        res.status(500).json({ error: "Random error" });
    } else {
        res.status(200).json({ message: "All good" });
    }
});

app.get("/status", (req, res, next) => {
    try {
        /// Test DB connection
    } catch(error) {
        ///
        client.trackEvent({name: "Database_Connectivity_Failure"})
        res.status(500).json(error);
        return;
    }
    res.send("");
});

app.get("/api/dependency", async (req, res, next) => {
    try {
        let startTime = Date.now();
        let url = `http://localhost:${port}/api/names`;
        let result = await axios.get(url);
        let duration = Date.now() - startTime;
        console.info(result.data);
        client.trackDependency({ target: url, name: "self call", data: "", duration: duration, resultCode: 0, success: true, dependencyTypeName: "SELF_CALL" });
        res.json(result.data);
    } catch (error) {
        console.error(error);
        client.trackException({ exception: error });
    }
});

// Slow endpoint for response time demo
app.get("/api/slow", async (req, res, next) => {
    setTimeout(() => {
        res.json({ message: "This was slow!" });
    }, 1500); // 1.5 seconds
});

// Dependency failure endpoint
app.get("/api/dependencyfail", async (req, res, next) => {
    try {
        // Call a non-existent service to trigger dependency failure
        await axios.get("http://localhost:9999/doesnotexist", { timeout: 1000 });
        res.json({ message: "Should not get here" });
    } catch (error) {
        client.trackDependency({
            target: "localhost:9999",
            name: "bad call",
            data: "/doesnotexist",
            duration: 1000,
            resultCode: error.code || 500,
            success: false,
            dependencyTypeName: "HTTP"
        });
        res.status(502).json({ error: "Dependency failure" });
    }
});

// Listen and wait
app.listen(port, () => {
    console.log("Server running on port " + port);
});
