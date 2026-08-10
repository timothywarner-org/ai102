// AI-103 | Lesson 9 | Alert on the Contoso Cloud RAG agent in rg-ai103-mvp.
// Two signals, one action group:
//   1. Groundedness gate FAILED  -> log alert over App Insights (eval_trace.py evaluate)
//   2. Agent is being throttled  -> metric alert on the Foundry account
// Deploy: az deployment group create -g rg-ai103-mvp -f .\Warner.AI-103.Lesson-09-alerts.bicep

param foundryAccountName string = 'aif-ai103-mvp-gcn5uizg'
param appInsightsName string = 'appi-ai103-l09'
param gatekeeperFunctionApp string = 'func-ai103-gatekeeper'
param oncallEmail string = 'oncall@warnerco.com'
param location string = resourceGroup().location

// The 1-5 groundedness bar. Keep this in sync with GROUNDEDNESS_GATE in eval_trace.py.
param groundednessGate int = 3

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

// The "run code" half of the response. This function app is already deployed;
// QuarantineDeployment pins the app back to the last known-good prompt version
// so a hallucinating build stops serving users while a human reads the traces.
resource gatekeeper 'Microsoft.Web/sites@2023-12-01' existing = {
  name: gatekeeperFunctionApp
}

// -----------------------------------------------------------------------------
// Action group: notify a human AND take the automated action. Both, not either.
// -----------------------------------------------------------------------------
resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-rag-agent-oncall'
  location: 'global'
  properties: {
    groupShortName: 'ragagent'
    enabled: true
    emailReceivers: [
      {
        name: 'oncall'
        emailAddress: oncallEmail
        useCommonAlertSchema: true
      }
    ]
    azureFunctionReceivers: [
      {
        name: 'quarantine'
        functionAppResourceId: gatekeeper.id
        functionName: 'QuarantineDeployment'
        httpTriggerUrl: 'https://${gatekeeperFunctionApp}.azurewebsites.net/api/quarantine-deployment'
        useCommonAlertSchema: true
      }
    ]
  }
}

// -----------------------------------------------------------------------------
// Signal 1: the quality gate failed.
// eval_trace.py stamps the rag.gate span with gate.status and gate.groundedness;
// custom span attributes land in customDimensions on the App Insights dependency.
// Bicep multi-line strings don't interpolate, so the threshold is stitched in
// with replace() -- that keeps the KQL readable and the gate value in one place.
// -----------------------------------------------------------------------------
var gateQuery = replace('''
dependencies
| where name == "rag.gate"
| extend status = tostring(customDimensions["gate.status"])
| extend groundedness = todouble(customDimensions["gate.groundedness"])
| where status == "HOLD" or groundedness < {gate}
| project timestamp, operation_Id, groundedness, question = tostring(customDimensions["rag.question"])
''', '{gate}', string(groundednessGate))

resource alertGateFailure 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: 'alert-rag-groundedness-gate'
  location: location
  properties: {
    displayName: 'RAG groundedness gate failed'
    description: 'An answer scored below the groundedness bar. Do not ship this build.'
    severity: 1
    enabled: true
    scopes: [ appInsights.id ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      allOf: [
        {
          query: gateQuery
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          // Fire on the first bad answer. A gate that tolerates one miss isn't a gate.
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    autoMitigate: false // Stays fired until a human clears it. Quality is not self-healing.
    actions: {
      actionGroups: [ actionGroup.id ]
    }
  }
}

// -----------------------------------------------------------------------------
// Signal 2: the agent is being throttled. Different failure, same responders.
// -----------------------------------------------------------------------------
resource alertThrottling 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-rag-agent-throttling'
  location: 'global'
  properties: {
    description: 'The RAG agent is getting HTTP 429s. Quota is undersized.'
    severity: 2
    enabled: true
    scopes: [ foundry.id ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    targetResourceType: 'Microsoft.CognitiveServices/accounts'
    targetResourceRegion: foundry.location
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'Http429Count'
          criterionType: 'StaticThresholdCriterion'
          metricName: 'AzureOpenAIRequests'
          operator: 'GreaterThan'
          threshold: 5
          timeAggregation: 'Total'
          dimensions: [
            {
              name: 'StatusCode'
              operator: 'Include'
              values: [ '429' ]
            }
          ]
        }
      ]
    }
    autoMitigate: true
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

output actionGroupId string = actionGroup.id
output gateAlertId string = alertGateFailure.id
