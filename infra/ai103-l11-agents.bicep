// =============================================================================
// AI-103 Lesson 11 -- multi-agent hand-off + agent observability.
//
// SELF-CONTAINED ON PURPOSE. Every other lesson template assumes the shared core
// account already exists. This one does not, because L11's failure mode is
// "the resource group got deleted and the demo is unrecordable." One command has
// to rebuild the entire lesson environment from nothing:
//
//   az group create -n rg-ai103-mvp -l eastus2
//   az deployment group create -g rg-ai103-mvp -f infra/ai103-l11-agents.bicep \
//     -p userObjectId=$(az ad signed-in-user show --query id -o tsv)
//
// Cost posture: GlobalStandard model deployment is pay-per-token, and both
// Log Analytics and Application Insights bill on ingestion. Idle cost is ~$0,
// so this can sit provisioned between recording sessions.
//
// Idempotent: re-running is a no-op. Role assignment names are deterministic
// GUIDs, so a second deployment updates in place instead of erroring on conflict.
// =============================================================================

@description('Azure region. eastus2 is where this subscription has gpt-5-mini GlobalStandard quota.')
param location string = 'eastus2'

@description('Globally unique Foundry account name (also the *.services.ai.azure.com subdomain).')
param accountName string = 'aif-ai103-l11-${uniqueString(resourceGroup().id)}'

@description('Foundry project that the L11 agents run against.')
param projectName string = 'proj-agents'

@description('Object ID of the user who gets keyless data-plane access. Required.')
param userObjectId string

@description('Set false to skip Log Analytics + Application Insights. The hand-off demo still runs; tracing reports itself as off.')
param deployObservability bool = true

@description('Short base name for the observability resources.')
param baseName string = 'ai103-l11'

// gpt-5-mini is the only model with granted quota on this subscription. The gpt-5
// family REQUIRES an explicit version; omitting it fails deployment validation.
var modelName = 'gpt-5-mini'
var modelVersion = '2025-08-07'

// 50K TPM. The hand-off demo makes 2-3 model calls per scenario across 3 scenarios,
// and a rate-limit retry mid-recording is a ruined take. Headroom is cheap here
// because GlobalStandard bills per token, not per provisioned unit.
var modelCapacity = 50

// Keyless data-plane roles, matching the L4 convention.
// Deliberately NOT Azure AI Developer: that role is scoped to Azure ML / hub-based
// workspaces, not hub-less Foundry projects. It is the exam trap the deck calls out.
var roleFoundryUser = '53ca6127-db72-4b80-b1b0-d745d6d5456d'            // formerly "Azure AI User"
var roleCognitiveServicesOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var roleLogAnalyticsReader = '73c42c96-874c-492b-b04d-ab87d138a893'
var dataPlaneRoles = [ roleFoundryUser, roleCognitiveServicesOpenAIUser ]

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    // allowProjectManagement is what makes this a Foundry account rather than a
    // plain Cognitive Services account. Without it there is no project endpoint,
    // and FoundryChatClient has nothing to connect to.
    allowProjectManagement: true
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: modelName
  sku: { name: 'GlobalStandard', capacity: modelCapacity }
  properties: {
    model: { format: 'OpenAI', name: modelName, version: modelVersion }
    // Pin the version. An auto-upgrade between recording sessions changes model
    // behavior, and in a routing demo that means the hand-off decisions shift
    // under a deck that already claims a specific outcome.
    versionUpgradeOption: 'NoAutoUpgrade'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'AI-103 Lesson 11 -- multi-agent'
    description: 'Foundry project for the L11 hand-off and agent-observability demos.'
  }
  dependsOn: [ deployment ]
}

// -----------------------------------------------------------------------------
// Observability. L11's second half is "follow one request across three agents",
// which is only demonstrable if the spans land somewhere queryable.
// -----------------------------------------------------------------------------

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = if (deployObservability) {
  name: 'log-${baseName}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = if (deployObservability) {
  name: 'appi-${baseName}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    // Workspace-based. Classic Application Insights is retired.
    WorkspaceResourceId: logAnalytics.id
  }
}

// Attach App Insights to the project so Foundry Observability in the portal reads
// the same telemetry the SDK exports. Foundry stores the CONNECTION STRING as the
// connection target, which is why this is authType ApiKey even though every other
// hop in this lesson is keyless.
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = if (deployObservability) {
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

// -----------------------------------------------------------------------------
// RBAC. Deterministic GUIDs keep re-runs idempotent.
// -----------------------------------------------------------------------------

@batchSize(1)
resource roleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for r in dataPlaneRoles: {
  name: guid(account.id, userObjectId, r)
  scope: account
  properties: {
    principalId: userObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', r)
  }
  dependsOn: [ project ]
}]

resource laReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployObservability) {
  name: guid(logAnalytics.id, userObjectId, roleLogAnalyticsReader)
  scope: logAnalytics
  properties: {
    principalId: userObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleLogAnalyticsReader)
  }
}

// -----------------------------------------------------------------------------
// Outputs map 1:1 onto the lesson's .env file, so standing the environment back
// up is copy-paste rather than portal archaeology.
// -----------------------------------------------------------------------------

@description('Paste into FOUNDRY_PROJECT_ENDPOINT in lessons/11-build-agents-foundry/.env')
output foundryProjectEndpoint string = 'https://${account.name}.services.ai.azure.com/api/projects/${projectName}'

@description('Paste into FOUNDRY_MODEL.')
output foundryModel string = deployment.name

@description('Paste into APPLICATIONINSIGHTS_CONNECTION_STRING. Secret: do not commit.')
output appInsightsConnectionString string = deployObservability ? appInsights.properties.ConnectionString : ''

output accountName string = account.name
