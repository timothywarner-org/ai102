// =============================================================================
// AI-103 Lesson 3 add-on infra -- MAIN (modular entry point).
//
// The always-up CORE (ai103-core.bicep) already gives us the Foundry account,
// the per-lesson projects, quota (LO1), and model deployments. This add-on layers
// the two extra resources L3's monitoring demo needs, then tears down cleanly:
//   * OBSERVABILITY (LO2): Log Analytics + Application Insights, connected to the project.
//   * SEARCH (LO3): Azure AI Search (Basic), connected to the project.
// Pass userObjectId to grant the demo user keyless read roles on both.
//
// Deploy (after the core is deployed):
//   az deployment group create -g rg-ai103-core \
//     -f infra/ai103-l3-observability.main.bicep \
//     -p accountName=<your-foundry-account> projectName=proj-lesson-03 \
//        userObjectId=$(az ad signed-in-user show --query id -o tsv)
//
// Tear down the fixed-cost Search + App Insights when the lesson is recorded.
// =============================================================================
targetScope = 'resourceGroup'

@description('Azure region. eastus2 carries the gpt-5 family + embeddings quota this course uses.')
param location string = resourceGroup().location

@description('Existing Foundry account name (from ai103-core.bicep outputs).')
param accountName string

@description('Existing Foundry project to attach the L3 resources to.')
param projectName string = 'proj-lesson-03'

@description('Short base name for the L3 add-on resources.')
param baseName string = 'ai103-l03'

@description('Optional. Object ID of the demo user; gets keyless read roles on Search + Log Analytics.')
param userObjectId string = ''

module observability 'modules/observability.bicep' = {
  name: 'l3-observability'
  params: {
    location: location
    baseName: baseName
    accountName: accountName
    projectName: projectName
    userObjectId: userObjectId
  }
}

module search 'modules/search.bicep' = {
  name: 'l3-search'
  params: {
    location: location
    baseName: baseName
    accountName: accountName
    projectName: projectName
    userObjectId: userObjectId
  }
}

@description('Paste into the L3 demo .env as the observability signal (LO2).')
output appInsightsConnectionString string = observability.outputs.appInsightsConnectionString
@description('Paste into the L3 demo .env as SEARCH_ENDPOINT (LO3).')
output searchEndpoint string = search.outputs.searchEndpoint
@description('The project endpoint to paste into the L3 demo .env as FOUNDRY_PROJECT_ENDPOINT (LO2).')
output projectEndpoint string = 'https://${accountName}.services.ai.azure.com/api/projects/${projectName}'
