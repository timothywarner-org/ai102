<#
.SYNOPSIS
    Deploys the secure Foundry account from Bicep with the Azure CLI.

.DESCRIPTION
    Teaching sample for AI-103 Lesson 4. Shows the shape of a real
    infrastructure-as-code deployment: authenticate, preview, then deploy the
    same Bicep we read on screen (identity = SystemAssigned, disableLocalAuth,
    networkAcls). It runs a what-if PREVIEW first, because you never push a
    security change to a resource group without seeing the diff it will make.

    This is a demo artifact. Read it to learners; you do not need to run it.

.PARAMETER ResourceGroup
    Target resource group. Defaults to the course's rg-ai103-core.

.PARAMETER Location
    Azure region. Defaults to eastus2, which holds the gpt-5-mini quota.

.PARAMETER WhatIfOnly
    Stop after the preview. Defaults to $true so the script is safe to run as-is.

.EXAMPLE
    ./deploy-secure-foundry.ps1
    Logs in if needed, then prints the what-if diff and stops. No changes made.

.EXAMPLE
    ./deploy-secure-foundry.ps1 -WhatIfOnly:$false
    Runs the preview, then performs the actual deployment.

.NOTES
    Keyless by design: the deployer's own Entra object ID is resolved at run
    time, so no secret or GUID is ever hardcoded in the script.
#>

[CmdletBinding()]
param(
    [string]$ResourceGroup = 'rg-ai103-core',
    [string]$Location      = 'eastus2',
    [bool]$WhatIfOnly      = $true
)

$ErrorActionPreference = 'Stop'

# The Bicep we read on screen lives at the repo's infra/ folder, two levels up
# from this lesson folder. Resolve it relative to the script so the path holds
# no matter where the terminal's working directory happens to be.
$template = Join-Path $PSScriptRoot '..\..\infra\ai103-core.mvp.bicep' | Resolve-Path

# Fail early with a clear message instead of a cryptic az error later.
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw 'Azure CLI (az) not found. Install it, then run az login.'
}

# Keyless auth: the identity that runs this script is the identity that deploys.
# Resolve the signed-in user's object ID rather than pasting a GUID into source.
Write-Host 'Resolving signed-in Entra identity...' -ForegroundColor Cyan
$userObjectId = az ad signed-in-user show --query id -o tsv
if (-not $userObjectId) {
    throw 'No signed-in Entra user. Run az login first.'
}

# Ensure the resource group exists before we target it. Idempotent: creating a
# group that already exists is a no-op, so re-runs never break.
az group create --name $ResourceGroup --location $Location --output none

# PREVIEW: what-if renders the exact diff the deployment would apply. Read this
# out loud to learners before anything is changed.
Write-Host "Previewing deployment to $ResourceGroup (no changes yet)..." -ForegroundColor Cyan
az deployment group what-if `
    --resource-group $ResourceGroup `
    --template-file $template `
    --parameters location=$Location userObjectId=$userObjectId

if ($WhatIfOnly) {
    Write-Host 'Preview only. No resources were changed.' -ForegroundColor Yellow
    return
}

# DEPLOY: same template, same parameters, now applied for real. The named
# deployment shows up in the resource group's Deployments history for audit.
Write-Host "Deploying to $ResourceGroup..." -ForegroundColor Green
az deployment group create `
    --name 'ai103-secure-foundry' `
    --resource-group $ResourceGroup `
    --template-file $template `
    --parameters location=$Location userObjectId=$userObjectId `
    --output table
