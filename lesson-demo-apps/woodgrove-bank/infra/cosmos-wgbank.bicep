// Cosmos DB for Woodgrove Bank AI-102 Demo (CAF, partitionKey: /filename)
// SHINE: Explicit, robust, and teaching-focused for MS Press AI-102 learners

@description('Cosmos DB account name (lowercase, max 44 chars)')
param accountName string = toLower('cosmos-wgbank-${uniqueString(resourceGroup().id)}')

@description('Location for Cosmos DB (choose region with quota)')
@allowed([
  'northcentralus'
  'eastus'
  'westus2'
  'southcentralus'
  'westeurope'
])
param location string = 'westus2'

@description('Logical database name')
param databaseName string = 'woodgrovebankdb'

@description('Container name')
param containerName string = 'images'

@description('Partition key path (must start with /, e.g. /filename)')
@minLength(2)
param partitionKeyPath string = '/filename'

@description('Enable free tier (true for training, false for prod)')
param enableFreeTier bool = false

@description('Tags for CAF compliance')
param tags object = {
  environment: 'training'
  owner: 'tim.warner'
  costcenter: 'ai102'
  workload: 'woodgrovebank'
  purpose: 'ai-102-demo'
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: accountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    enableFreeTier: enableFreeTier
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    publicNetworkAccess: 'Enabled'
    enableAnalyticalStorage: false
    enableAutomaticFailover: false
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
    options: {
      throughput: 400 // Minimum for demo, adjust as needed
    }
  }
}

resource container 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: database
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: [
          partitionKeyPath
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          { path: '/*' }
        ]
        excludedPaths: [
          { path: '/_etag/?' }
        ]
      }
    }
  }
}

// Optional: Diagnostic settings for observability (uncomment and configure as needed)
/*
resource cosmosDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'cosmosDiagnostics'
  scope: cosmosAccount
  properties: {
    workspaceId: '<your-log-analytics-workspace-resource-id>'
    logs: [
      {
        category: 'DataPlaneRequests'
        enabled: true
        retentionPolicy: { enabled: false, days: 0 }
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: { enabled: false, days: 0 }
      }
    ]
  }
}
*/

output cosmosAccountUri string = cosmosAccount.properties.documentEndpoint
output databaseName string = database.name
output containerName string = container.name
output partitionKeyPath string = partitionKeyPath
output region string = location
output deploymentTips string = 'If you see a ServiceUnavailable error, try a different region with quota. See https://aka.ms/cosmosdbquota for details.' 
