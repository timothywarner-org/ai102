// =============================================================================
// AI-103 course core -- MVP variant (cert-prep, minimal spend).
// One Foundry account + 3 lesson projects + ONE model (gpt-5-mini, the only model
// with granted quota on this subscription/region). All pay-per-token => ~$0 idle.
// Deploy the full ai103-core.bicep (4 models, 18 projects) once you have quota.
//   az deployment group create -g rg-ai103-core -f infra/ai103-core.mvp.bicep \
//     -p userObjectId=$(az ad signed-in-user show --query id -o tsv)
// =============================================================================
@description('Azure region. eastus2 has gpt-5-mini GlobalStandard quota (limit 500).')
param location string = 'eastus2'
@description('Globally unique Foundry account name (also the *.services.ai.azure.com subdomain).')
param accountName string = 'aif-ai103-mvp-${uniqueString(resourceGroup().id)}'
@description('Object ID of the user who gets keyless data-plane access.')
param userObjectId string
@description('Number of lesson projects (MVP = 3 for L1-L3).')
param lessonCount int = 3

// gpt-5-mini is the only model with quota here; gpt-5 family REQUIRES an explicit version.
var modelName = 'gpt-5-mini'
var modelVersion = '2025-08-07'
var modelCapacity = 20   // 20K TPM rate limit; GlobalStandard is pay-per-token (no idle cost)

var roleAzureAIDeveloper = '64702f94-c441-49e6-a78b-ef80e0188fee'
var roleCognitiveServicesOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var dataPlaneRoles = [ roleAzureAIDeveloper, roleCognitiveServicesOpenAIUser ]

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
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
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

@batchSize(1)
resource projects 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = [for i in range(1, lessonCount): {
  parent: account
  name: 'proj-lesson-${padLeft(string(i), 2, '0')}'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'AI-103 Lesson ${padLeft(string(i), 2, '0')}'
    description: 'Isolated Foundry project for AI-103 lesson ${padLeft(string(i), 2, '0')} (MVP).'
  }
  dependsOn: [ deployment ]
}]

@batchSize(1)
resource roleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for r in dataPlaneRoles: {
  name: guid(account.id, userObjectId, r)
  scope: account
  properties: {
    principalId: userObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', r)
  }
  dependsOn: [ projects ]
}]

output accountName string = account.name
output modelDeploymentName string = deployment.name
output lesson02Endpoint string = 'https://${account.name}.services.ai.azure.com/api/projects/proj-lesson-02'
output lesson03Endpoint string = 'https://${account.name}.services.ai.azure.com/api/projects/proj-lesson-03'
