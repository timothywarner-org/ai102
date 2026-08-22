// =============================================================================
// AI-103 -- REUSABLE PER-LESSON ENVIRONMENT.
//
// One template any lesson can target. This exists because the recurring failure
// mode on this course is "the resource group got deleted and now the demo is
// unrecordable." Rebuilding should be one command and about five minutes, not an
// afternoon of clicking through the portal trying to remember what was connected
// to what.
//
// This is the GENERALIZED version of infra/ai103-l11-agents.bicep, which was
// written first and proved the shape against a live L10 + L11 recording setup.
// Prefer this file for new lessons; ai103-l11-agents.bicep is kept as-is because
// its deployment name is referenced in the L10 and L11 runbooks.
//
// USAGE -- agent lessons that need tracing (L10, L11):
//   az group create -n rg-ai103-mvp -l eastus2
//   az deployment group create -g rg-ai103-mvp -n lesson-11 \
//     -f infra/ai103-lesson-env.bicep \
//     -p userObjectId=$(az ad signed-in-user show --query id -o tsv) \
//        projectName=proj-agents baseName=ai103-l11
//
// USAGE -- a lesson that only needs a project and a model (no telemetry):
//   az deployment group create -g rg-ai103-mvp -n lesson-06 \
//     -f infra/ai103-lesson-env.bicep \
//     -p userObjectId=$(az ad signed-in-user show --query id -o tsv) \
//        projectName=proj-lesson-06 baseName=ai103-l06 deployObservability=false
//
// USAGE -- Lesson 12, image + video generation on the shared account:
//   az deployment group create -g rg-ai103-mvp -n lesson-12 \
//     -f infra/ai103-lesson-env.bicep \
//     -p userObjectId=$(az ad signed-in-user show --query id -o tsv) \
//        accountName=YOUR-FOUNDRY-RESOURCE projectName=proj-lesson-12 \
//        baseName=ai103-l12 deployObservability=false \
//        deployImageModel=true deployVideoModel=true
//
// SHARING ONE ACCOUNT ACROSS LESSONS: pass the SAME accountName on each
// deployment and vary only projectName. Foundry accounts carry the model quota,
// so one account with several projects keeps you inside a single TPM grant.
//
// Cost posture: GlobalStandard is pay-per-token and Log Analytics bills on
// ingestion, so an idle environment costs approximately nothing.
//
// Idempotent: re-running is a no-op. Role assignment names are deterministic
// GUIDs, so a second deployment updates in place instead of failing on conflict.
// =============================================================================

@description('Azure region. eastus2 is where this subscription holds gpt-5-mini GlobalStandard quota.')
param location string = 'eastus2'

@description('Foundry account name. Pass the SAME value across lessons to share one account and one quota grant.')
param accountName string = 'aif-ai103-${uniqueString(resourceGroup().id)}'

@description('Foundry project for this lesson, e.g. proj-lesson-06 or proj-agents.')
param projectName string

@description('Short base name for this lesson\'s observability resources, e.g. ai103-l11.')
param baseName string

@description('Object ID of the user who gets keyless data-plane access. Required.')
param userObjectId string

@description('Set false for lessons that do not need tracing. Skips Log Analytics and Application Insights.')
param deployObservability bool = true

@description('Model deployment name. gpt-5-mini is the only family with granted quota on this subscription.')
param modelName string = 'gpt-5-mini'

@description('Model version. The gpt-5 family REQUIRES an explicit version; deployment validation fails without one.')
param modelVersion string = '2025-08-07'

@description('Rate limit in thousands of tokens per minute. 50 leaves headroom so a retry never interrupts a take.')
param modelCapacity int = 50

// -----------------------------------------------------------------------------
// Lesson 12 -- image and video generation. Both flags default to FALSE, so every
// lesson that shipped before L12 deploys exactly what it deployed yesterday.
// -----------------------------------------------------------------------------

@description('Set true for lessons that generate images (L12). Adds a gpt-image-2 deployment to the same account.')
param deployImageModel bool = false

@description('Set true for lessons that generate video (L12). Adds a sora-2 deployment. Requires location eastus2 or swedencentral.')
param deployVideoModel bool = false

@description('Image model deployment name. Do NOT use gpt-image-1 (retires 2026-10-23) or dall-e-3 (already retired 2026-03-04).')
param imageModelName string = 'gpt-image-2'

@description('Image model version. Safe to pin, unlike sora-2: the catalog entry for gpt-image-2 is current.')
param imageModelVersion string = '2026-04-21'

@description('Image rate limit in REQUESTS per minute -- not thousands of tokens. 2 RPM is the granted quota and is ample for a demo.')
param imageModelCapacity int = 2

@description('Video model deployment name.')
param videoModelName string = 'sora-2'

@description('Video model version. LEAVE THIS EMPTY. Empty means "let the service choose its current default"; pinning a version here is exactly how the L12 environment broke. Read the comment above videoModelDefinition before you change it.')
param videoModelVersion string = ''

@description('Video rate limit in REQUESTS per minute -- not thousands of tokens. 9 RPM is the granted quota.')
param videoModelCapacity int = 9

@description('Friendly name shown in the Foundry portal project list.')
param projectDisplayName string = projectName

// Keyless data-plane roles, matching the L4 convention.
// Deliberately NOT Azure AI Developer: that role targets Azure ML / hub-based
// workspaces rather than hub-less Foundry projects. It is the exam trap the deck
// calls out, and granting it here would quietly contradict the lesson.
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
    // plain Cognitive Services account. Without it there is no project endpoint
    // for FoundryChatClient to connect to.
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
    // behavior, and a deck that already claims a specific on-screen outcome then
    // stops matching what the demo prints.
    versionUpgradeOption: 'NoAutoUpgrade'
    // L5 responsible-AI-as-code: the content filter ships WITH the deployment.
    // Name a custom RAI policy here to set tighter thresholds in the template
    // instead of clicking them into the portal after the fact.
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

// -----------------------------------------------------------------------------
// Lesson 12 -- image and video model deployments, optional per lesson.
//
// SEQUENCING IS LOAD-BEARING, NOT STYLE. Model deployments on ONE Cognitive
// Services account have to be created ONE AT A TIME. Left alone, ARM fans the
// deployment PUTs out in parallel, the concurrent writes against the same
// account conflict, and the template fails INTERMITTENTLY -- sometimes on the
// second deployment, sometimes on the third, sometimes not at all, which is the
// worst kind of failure to debug the morning of a recording. The dependsOn
// chain below forces chat -> image -> video -> project.
//
// Every link in that chain is listed EXPLICITLY rather than leaning on
// transitivity, because ARM DROPS a dependsOn entry whose target resource has a
// false condition. With deployImageModel=false, a video deployment that only
// depended on the image deployment would silently lose its ordering and race the
// chat deployment -- the precise bug this comment exists to prevent.
//
// REGIONS: on this subscription sora-2 deploys to eastus2 and swedencentral
// ONLY; gpt-image-2 additionally allows westus3 and polandcentral. location is
// deliberately NOT narrowed with @allowed, because it governs the whole template
// and lessons 1-11 must stay free to target any region. Set deployVideoModel to
// true anywhere but those two regions and the model deployment fails.
// -----------------------------------------------------------------------------

resource imageDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = if (deployImageModel) {
  parent: account
  name: imageModelName
  sku: { name: 'GlobalStandard', capacity: imageModelCapacity }
  properties: {
    model: { format: 'OpenAI', name: imageModelName, version: imageModelVersion }
    // NOT NoAutoUpgrade, unlike the chat deployment above. Image output is
    // nondeterministic anyway, so pinning buys no on-screen stability, while this
    // model family retires fast -- gpt-image-1 goes away 2026-10-23 and dall-e-3
    // already did (2026-03-04, leaving existing deployments non-functional).
    // Riding the current default is the safer failure mode here, and it matches
    // what the live L12 account is running.
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  // Serialize behind the chat deployment. See the sequencing note above.
  dependsOn: [ deployment ]
}

// DO NOT PIN THE SORA VERSION. Read this before you "fix" videoModelVersion.
//
// The Foundry model catalog STILL ADVERTISES sora-2 version 2025-10-06, and that
// version is dead. Deploying it fails with:
//
//   ServiceModelDeprecated: The model 'Format:OpenAI,Name:sora-2,
//   Version:2025-10-06' has been deprecated since 07/15/2026
//
// The catalog is wrong, so a version copied out of it cannot be trusted. Omit the
// version and the service selects its own current default, which is by definition
// a live one -- it resolved to 2025-12-08 on 2026-08-11. The ARM contract backs
// this up: DeploymentModel.version is documented as "Optional ... If version is
// not specified, a default version will be assigned."
//
// Bicep has no "omit this key" modifier for an object literal, so the model
// object is declared as two complete alternatives and the version key simply does
// not exist in the empty-string branch. Sending version: '' instead would put an
// empty version on the wire and fail validation, which is why this is not a
// one-liner ternary inside the resource body.
var videoModelDefinition = empty(videoModelVersion)
  ? { format: 'OpenAI', name: videoModelName }
  : { format: 'OpenAI', name: videoModelName, version: videoModelVersion }

resource videoDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = if (deployVideoModel) {
  parent: account
  name: videoModelName
  sku: { name: 'GlobalStandard', capacity: videoModelCapacity }
  properties: {
    model: videoModelDefinition
    // Must NOT be NoAutoUpgrade. With no pinned version this deployment rides the
    // service default on purpose, and that is what keeps the next deprecation from
    // stranding it the way 2025-10-06 stranded the last one.
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  // BOTH links are required -- imageDeployment alone is not enough when
  // deployImageModel is false. See the sequencing note above.
  dependsOn: [ deployment, imageDeployment ]
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: projectDisplayName
    description: 'AI-103 lesson project provisioned from infra/ai103-lesson-env.bicep.'
  }
  // Last link in the chat -> image -> video -> project chain. Creating the
  // project while a model deployment is still writing to the same account is the
  // same concurrency conflict, so the project waits for all three.
  dependsOn: [ deployment, imageDeployment, videoDeployment ]
}

// -----------------------------------------------------------------------------
// Observability, optional per lesson.
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
// connection target, which is why this one hop is authType ApiKey even though
// every other hop in these lessons is keyless.
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
// Outputs map 1:1 onto a lesson .env file, so standing an environment back up is
// copy-paste rather than portal archaeology.
// -----------------------------------------------------------------------------

@description('Paste into FOUNDRY_PROJECT_ENDPOINT in the lesson .env')
output foundryProjectEndpoint string = 'https://${account.name}.services.ai.azure.com/api/projects/${projectName}'

@description('Paste into FOUNDRY_MODEL. This is the DEPLOYMENT name, not the model family name.')
output foundryModel string = deployment.name

@description('Paste into FOUNDRY_IMAGE_MODEL. Empty string when deployImageModel is false.')
output foundryImageModel string = deployImageModel ? imageModelName : ''

@description('Paste into FOUNDRY_VIDEO_MODEL. Empty string when deployVideoModel is false.')
output foundryVideoModel string = deployVideoModel ? videoModelName : ''

@description('Paste into APPLICATIONINSIGHTS_CONNECTION_STRING. Secret: never commit it.')
output appInsightsConnectionString string = deployObservability ? appInsights.properties.ConnectionString : ''

@description('Reuse this as the accountName parameter on the next lesson to share one account and quota grant.')
output accountName string = account.name
