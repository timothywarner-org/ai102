# Azure Application Insights KQL Cheat Sheet (AI-102)

> Use these queries in the Azure Portal (Logs blade) to quickly surface key insights during your demo.

---

## 🚦 Smoke Test: Is Data Flowing?

### See all recent requests (last 10 minutes)
```kusto
// Shows all API calls received in the last 10 minutes, newest first.
requests
| where timestamp > ago(10m)
| order by timestamp desc
```

### See all recent dependencies (last 10 minutes)
```kusto
// Shows all dependency calls (e.g., outgoing HTTP requests) in the last 10 minutes.
dependencies
| where timestamp > ago(10m)
| order by timestamp desc
```

### See all recent exceptions (last 10 minutes)
```kusto
// Shows all exceptions tracked by the Application Insights SDK in the last 10 minutes.
exceptions
| where timestamp > ago(10m)
| order by timestamp desc
```

---

## 🔴 Find All Failed Requests
```kusto
// Lists all failed API requests (e.g., 500, 502 errors), newest first.
requests
| where success == false
| project timestamp, name, resultCode, url, operation_Id
| order by timestamp desc
```

---

## ⏱️ Find Slowest Requests
```kusto
// Shows requests that took longer than 1 second, sorted by duration.
requests
| where duration > 1s
| project timestamp, name, duration, url, operation_Id
| order by duration desc
```

---

## 🔗 Dependency Failures (e.g., Downstream APIs)
```kusto
// Lists all failed dependency calls (e.g., failed HTTP requests to other services).
dependencies
| where success == false
| project timestamp, name, target, resultCode, duration, operation_Id
| order by timestamp desc
```

---

## 📊 Count Requests by Endpoint
```kusto
// Shows how many times each endpoint was called, most popular first.
requests
| summarize count() by name
| order by count_ desc
```

---

## 🧩 Custom Events (e.g., Database Connectivity Failures)
```kusto
// Finds custom events you track in your code, such as DB connectivity failures.
events
| where name == "Database_Connectivity_Failure"
| project timestamp, name, operation_Id
```

---

## 🔍 Trace a Single Request (Correlation)
```kusto
// Replace <operation_Id> with a real value from a request to see all related telemetry (requests, dependencies, exceptions, traces).
union requests, dependencies, exceptions, traces
| where operation_Id == '<operation_Id>'
| order by timestamp asc
```

---

## 🟢 Live Metrics (Last 5 Minutes)
```kusto
// Shows request volume and average duration, binned by minute, for the last 5 minutes.
requests
| where timestamp > ago(5m)
| summarize count(), avg(duration), sum(itemCount) by bin(timestamp, 1m)
```

---

## 📝 Top 5 Most Common Errors
```kusto
// Lists the most frequent error result codes (e.g., 500, 502) in your API.
requests
| where success == false
| summarize count() by resultCode
| top 5 by count_
```

---

*Copy, paste, and adapt these queries live for maximum demo impact!* 