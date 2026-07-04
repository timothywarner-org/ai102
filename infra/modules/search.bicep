// =============================================================================
// L3 module -- SEARCH: Azure AI Search connected to the Foundry project, so the
// index-health + relevance signal (LO3) has a real index to read. Defaults to the
// FREE tier ($0) for a cert-prep MVP. Keyless via Entra RBAC.
// =============================================================================
@description('Azure region.')
param location string
@description('Short base name, e.g. ai103-l03.')
param baseName string
@description('Search SKU. free = $0 (one per subscription); basic/standard add semantic ranking.')
@allowed([ 'free', 'basic', 'standard' ])
param searchSku string = 'free'
@description('Existing Foundry account name.')
param accountName string
@description('Existing Foundry project name.')
param projectName string
@description('Optional. Object ID of the demo user; gets keyless read/query roles.')
param userObjectId string = ''

var isFree = searchSku == 'free'
var roleSearchIndexDataContributor = '8ebe5a00-799e-43f5-93ac-243d3dce84a7' // create index + upload docs (student seeds a tiny index)
var roleSearchServiceContributor = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'   // read index/indexer stats

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: 'srch-${baseName}-${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: searchSku }
  identity: isFree ? { type: 'None' } : { type: 'SystemAssigned' } // free tier has no managed identity
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    semanticSearch: isFree ? 'disabled' : 'free' // semantic ranking isn't on the free tier
    publicNetworkAccess: 'enabled'
    authOptions: { aadOrApiKey: { aadAuthFailureMode: 'http403' } } // keyless-first, keys still allowed
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  name: '${accountName}/${projectName}'
}

resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: project
  name: 'aisearch'
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${search.name}.search.windows.net'
    authType: 'AAD'
    isSharedToAll: true
    metadata: { ApiType: 'Azure', ResourceId: search.id, Location: location }
  }
}

resource dataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(userObjectId)) {
  name: guid(search.id, userObjectId, roleSearchIndexDataContributor)
  scope: search
  properties: {
    principalId: userObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchIndexDataContributor)
  }
}

resource svcContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(userObjectId)) {
  name: guid(search.id, userObjectId, roleSearchServiceContributor)
  scope: search
  properties: {
    principalId: userObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchServiceContributor)
  }
}

output searchName string = search.name
output searchEndpoint string = 'https://${search.name}.search.windows.net'
