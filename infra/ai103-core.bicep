// =============================================================================
// AI-103 course CORE infrastructure -- one standardized, always-up Foundry account.
//
// Design: the ACCOUNT is the expensive, RBAC-bearing, quota-bearing resource, so we
// keep exactly ONE and leave it up. It is pay-per-call, so an idle account costs
// almost nothing. Model deployments live at the account level and are SHARED by
// every project. Each of the 18 lessons gets its OWN project (the isolation
// boundary for agents, threads, files, and vector stores) so lessons never collide.
//
// This template is IDEMPOTENT: re-running `az deployment group create` converges the
// resource group to this shape -- it adds what is missing and no-ops what already
// matches. You never tear down and rebuild; you re-apply.
//
// Deliberately NOT in the always-up core: Azure AI Search. Search carries a fixed
// monthly SKU cost even when idle, which would break the "cheap to leave running"
// property. Add it (and tear it down) around the retrieval lesson (L17) instead.
//
// Deploy:  az deployment group create -g rg-ai103-core -f infra/ai103-core.bicep
// GA API version 2025-06-01 (matches the official AVM ai-foundry module).
// =============================================================================

@description('Azure region. eastus2 has confirmed gpt-5 family + embeddings + gpt-4o quota.')
param location string = resourceGroup().location

@description('Globally unique Foundry account name; also the *.services.ai.azure.com subdomain.')
param accountName string = 'aif-ai103-core-${uniqueString(resourceGroup().id)}'

@description('Object ID of the user who gets keyless data-plane access to the account.')
param userObjectId string

@description('Number of lesson projects to create (the AI-103 course is 18 lessons).')
param lessonCount int = 18

// Shared model deployments. Superset the 18 lessons draw from: a flagship + an SLM
// for the agent/bake-off lessons, embeddings for retrieval, and gpt-4o for
// multimodal. Versions were resolved from the live Foundry catalog, not guessed.
var models = [
  { name: 'gpt-5.1', model: 'gpt-5.1', version: '2025-11-13', capacity: 50 }
  { name: 'gpt-5-nano', model: 'gpt-5-nano', version: '2025-08-07', capacity: 50 }
  { name: 'text-embedding-3-large', model: 'text-embedding-3-large', version: '1', capacity: 50 }
  { name: 'gpt-4o', model: 'gpt-4o', version: '2024-11-20', capacity: 50 }
]

// Built-in role GUIDs (resolved via `az role definition list`, not hardcoded blind).
var roleAzureAIDeveloper = '64702f94-c441-49e6-a78b-ef80e0188fee'
var roleCognitiveServicesOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var dataPlaneRoles = [
  roleAzureAIDeveloper           // agents, threads, files, vector stores (project data plane)
  roleCognitiveServicesOpenAIUser // chat/completions + embeddings inference
]

// The one shared Foundry account. allowProjectManagement=true is what makes it
// agent-capable; the custom subdomain is required for keyless token auth.
resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

// Cognitive Services deployments on one account must be created SERIALLY; batchSize(1)
// enforces that so a parallel-create race does not fail the deployment.
@batchSize(1)
resource deployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [for m in models: {
  parent: account
  name: m.name
  sku: {
    name: 'GlobalStandard'
    capacity: m.capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: m.model
      version: m.version
    }
  }
}]

// One project per lesson: proj-lesson-01 .. proj-lesson-18. range(1, lessonCount)
// yields lessonCount values starting at 1.
// Azure serializes control-plane operations PER ACCOUNT, so batchSize(1) creates the
// projects one at a time, and dependsOn:[deployments] keeps the project phase from
// overlapping the model-deployment phase -- both would otherwise 'RequestConflict'.
@batchSize(1)
resource projects 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = [for i in range(1, lessonCount): {
  parent: account
  name: 'proj-lesson-${padLeft(string(i), 2, '0')}'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'AI-103 Lesson ${padLeft(string(i), 2, '0')}'
    description: 'Isolated Foundry project for AI-103 lesson ${padLeft(string(i), 2, '0')} demos.'
  }
  dependsOn: [
    deployments
  ]
}]

// Grant the user keyless data-plane access at the account scope; child projects
// inherit it. Deterministic GUID names make the assignments idempotent on re-run.
@batchSize(1)
resource roleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for r in dataPlaneRoles: {
  name: guid(account.id, userObjectId, r)
  scope: account
  properties: {
    principalId: userObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', r)
  }
  dependsOn: [
    projects
  ]
}]

output accountName string = account.name
output accountResourceId string = account.id
// The endpoint each lesson's .env uses, shown for lesson 01. Swap the project name
// for other lessons: https://<account>.services.ai.azure.com/api/projects/proj-lesson-NN
output lesson01ProjectEndpoint string = 'https://${account.name}.services.ai.azure.com/api/projects/proj-lesson-01'
output projectEndpointPattern string = 'https://${account.name}.services.ai.azure.com/api/projects/proj-lesson-{NN}'
