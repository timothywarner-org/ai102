// =============================================================================
// L3 module -- OBSERVABILITY: Log Analytics + Application Insights, connected to
// the lesson's Foundry project so Foundry Observability + continuous evaluation
// have a place to write latency, safety, and groundedness signals (LO2).
// Keyless: the project connection uses authType 'AAD' (no keys in the template).
// =============================================================================
@description('Azure region.')
param location string
@description('Short base name for L3 add-on resources, e.g. ai103-l03.')
param baseName string
@description('Existing Foundry (Cognitive Services) account name.')
param accountName string
@description('Existing Foundry project name to attach Application Insights to.')
param projectName string
@description('Optional. Object ID of the user who runs the read-only demo; gets Log Analytics Reader. Leave empty to skip RBAC.')
param userObjectId string = ''

// Log Analytics Reader (lets the demo user read App Insights / LA queries keyless).
var roleLogAnalyticsReader = '73c42c96-874c-492b-b04d-ab87d138a893'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${baseName}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${baseName}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id   // workspace-based App Insights (classic is retired)
  }
}

// Reference the already-deployed project (created by ai103-core.bicep).
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  name: '${accountName}/${projectName}'
}

// Wire App Insights to the project as a keyless connection. Foundry stores the
// CONNECTION STRING as the connection target (that's what tracing/continuous-eval read).
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: project
  name: 'appinsights'
  properties: {
    category: 'AppInsights'
    target: appInsights.id
    authType: 'ApiKey'
    credentials: {
      key: appInsights.properties.ConnectionString
    }
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: appInsights.id
    }
  }
}

// Grant the demo user read access to the telemetry (keyless). Deterministic GUID = idempotent.
resource laReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(userObjectId)) {
  name: guid(logAnalytics.id, userObjectId, roleLogAnalyticsReader)
  scope: logAnalytics
  properties: {
    principalId: userObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleLogAnalyticsReader)
  }
}

output appInsightsName string = appInsights.name
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output logAnalyticsResourceId string = logAnalytics.id
