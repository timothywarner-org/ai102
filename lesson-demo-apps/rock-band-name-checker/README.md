# Rock Band Name Checker

## What is this?

This is a Python console app that checks if a user-provided rock band name is appropriate using **Azure AI Content Safety**. It demonstrates real-world AI-102 development practices, including:

- **Integration with Azure AI Content Safety** to detect hate and violence in user input.
- **Retry logic** for resilient API calls (shows how to handle transient cloud errors).
- **Structured logging** and **batch telemetry** to Azure Log Analytics for observability and monitoring.
- **Environment variable management** for secrets (API keys, Log Analytics keys)—never hardcoded!
- **Explicit error handling** and user feedback for a robust, demo-friendly experience.
- **Teachable code**: clear, DRY, and ready for learners to adapt.

## Why is this useful for AI-102 learners?

- **Shows how to wire up Azure AI services in Python, end-to-end.**
- **Demonstrates best practices**: retry logic, error handling, logging, and secure config.
- **Highlights real-world pain points**: SDK property names (e.g., `categories_analysis` vs. `categories`) can change—always check the docs and be ready to debug!
- **Batch processing and telemetry**: see how to analyze multiple variants and send results to Log Analytics for KQL analysis.

## Required SDKs

- `azure-ai-contentsafety` (for Content Safety API)
- `requests` (for Log Analytics HTTP Data Collector API)
- `python-dotenv` (optional, for local .env file support)

Install with:
```bash
pip install azure-ai-contentsafety requests
```

## How to run

1. Set your environment variables:
   - `CONTENT_SAFETY_API_KEY` (Azure Content Safety key)
   - `LOG_ANALYTICS_SHARED_KEY` (Log Analytics workspace key)
2. Run the app:
   ```bash
   python rock_band_name_checker.py
   ```
3. Enter a band name when prompted. The app will analyze the name and variants, print verdicts, and send a batch log to Log Analytics.

## Key AI-102 Dev Practices Demonstrated

- **Retry logic**: Handles transient API errors with exponential backoff.
- **Structured logging**: Sends batch results to Log Analytics for monitoring and KQL analysis.
- **Environment variable management**: Keeps secrets out of code.
- **Explicit error handling**: User-friendly and robust.
- **SDK property gotchas**: Always check the docs—property names can change between SDK versions!

---

See the rest of this README for more details, KQL queries, and educational notes.

## Overview

This project serves as an educational example for AI-102 training on Azure AI Service monitoring. It showcases:

1. Integration with Azure AI Content Safety service
2. Comprehensive logging to Azure Log Analytics
3. Advanced Kusto Query Language (KQL) queries for monitoring and analysis

The application allows users to input potential rock band names, which are then analyzed for inappropriate content using Azure AI Content Safety. Results are displayed to the user and logged for analysis.

## Project Structure

```
rock-band-name-checker/
├── rock_band_name_checker.py  # Main application
├── kusto_queries.kql          # KQL queries for Log Analytics
├── more-queries.kql           # Additional KQL queries
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Prerequisites

- Python 3.7 or later
- Azure AI Content Safety resource
- Azure Log Analytics workspace
- Diagnostic settings configured to send Content Safety logs to Log Analytics

## Configuration

Set the following environment variables:

```
CONTENT_SAFETY_API_KEY=your_content_safety_api_key
CONTENT_SAFETY_ENDPOINT=https://twai102contentsafety1.cognitiveservices.azure.com/
APPINSIGHTS_INSTRUMENTATIONKEY=your_app_insights_key (optional)
ENVIRONMENT=development|test|production (optional, defaults to development)
```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python rock_band_name_checker.py
```

Enter rock band names when prompted. The application will analyze each name and display whether it's approved or rejected based on content safety guidelines.

## Monitoring with Azure Log Analytics

This application sends logs to Azure Log Analytics and leverages the diagnostic logs from Azure AI Content Safety. The included KQL queries demonstrate how to:

1. **Monitor service-side metrics** using the AzureDiagnostics table
   - Request volume and patterns
   - Response times and performance
   - Error rates and status codes
   - Throttling events

2. **Analyze application-side data** using the traces table
   - User input patterns
   - Content safety results and categories
   - Rejection rates and reasons
   - Application performance

3. **Correlate service and application logs** for end-to-end visibility
   - Join application and service logs
   - Track complete request flow
   - Identify performance bottlenecks

## Azure Resource Information

- **Log Analytics Workspace:**
  - Name: techtrainertim-web-logs
  - ID: 7f28cf83-d621-4c01-8ab6-06f9cda63c83
  - Resource Group: permanent-rg
  - Location: East US

- **Content Safety Service:**
  - Endpoint: https://twai102contentsafety1.cognitiveservices.azure.com/
  - Resource Group: ai102-rg
  - Location: East US
  - Tier: Standard

## Sample Kusto Queries

The `kusto_queries.kql` file contains comprehensive queries for analyzing both application logs and Azure diagnostic logs.

### Key Diagnostics Queries

```kql
// Basic Azure Diagnostics query for Content Safety TextAnalyze operations
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.COGNITIVESERVICES"
| where OperationName == "TextAnalyze"
| sort by TimeGenerated desc
| take 10
```

```kql
// Content Safety operations with response times and status codes
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.COGNITIVESERVICES"
| where Category == "RequestResponse" or Category == "Audit"
| where OperationName == "TextAnalyze"
| extend responseTime = DurationMs
| extend statusCode = tostring(StatusCode)
| extend userAgent = UserAgent_s
| project TimeGenerated, OperationName, responseTime, statusCode, userAgent, CorrelationId
| sort by TimeGenerated desc
```

### Key Application Queries

```kql
// View all requests and their results
traces
| where customDimensions.service_name == "RockBandNameChecker"
| where message == "Content safety analysis completed successfully"
| extend requestId = tostring(customDimensions.request_id)
| extend results = parse_json(tostring(customDimensions.results))
| extend bandName = tostring(results.text)
| extend isBlocked = results.categories.hate.is_blocked or 
                     results.categories.sexual.is_blocked or 
                     results.categories.violence.is_blocked or 
                     results.categories.self_harm.is_blocked
| project timestamp, bandName, isBlocked, results
```

See the full `kusto_queries.kql` file for more comprehensive queries.

## Educational Notes

This project demonstrates several key Azure AI monitoring concepts:

1. **Structured Logging**: Using custom dimensions for better filtering and analysis
2. **Correlation IDs**: Tracking requests across application and service boundaries
3. **Performance Monitoring**: Tracking response times and throughput
4. **Error Handling**: Proper error logging and analysis
5. **KQL Queries**: Advanced query techniques for monitoring and troubleshooting

## License

This project is licensed under the MIT License.
