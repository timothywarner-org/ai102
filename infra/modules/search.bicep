// =============================================================================
// L3 module -- SEARCH: Azure AI Search (Basic) connected to the Foundry project,
// so the index-health + relevance demo (LO3) has a real index to read.
// Basic is the cheapest SKU that still supports semantic ranking. Keyless via
// Entra RBAC (aadOrApiKey allows both during the lesson; flip disableLocalAuth
// to true to go keys-off entirely).
// =============================================================================
@description('Azure region.')
param location string
@description('Short base name for L3 add-on resources, e.g. ai103-l03.')
param baseName string
@description('Azure AI Search SKU.')
@allowed([ 'basic', 'standard' ])
param searchSku string = 'basic'
@description('Existing Foundry (Cognitive Services) account name.')
param accountName string
@description('Existing Foundry project name to attach the search connection to.')
param projectName string
@description('Optional. Object ID of the demo user; gets keyless read/query roles. Leave empty to skip RBAC.')
param userObjectId string = ''

// Keyless read roles for the demo user: query the index + read index/indexer stats.
var roleSearchIndexDataReader = '1407120a-92aa-4202-b7e9-c0e197c71c8f'
var roleSearchServiceContributor = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: 'srch-${baseName}-${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: searchSku }
  identity: { type: 'SystemAssigned' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    semanticSearch: 'free'
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
    metadata: {
      ApiType: 'Azure'
      ResourceId: search.id
      Location: location
    }
  }
}

resource searchDataReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(userObjectId)) {
  name: guid(search.id, userObjectId, roleSearchIndexDataReader)
  scope: search
  properties: {
    principalId: userObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchIndexDataReader)
  }
}

resource searchContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(userObjectId)) {
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
