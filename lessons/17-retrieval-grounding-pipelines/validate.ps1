<#
.SYNOPSIS
    AI-103 Lesson 17 -- prove the demo works against LIVE Azure before recording.

.DESCRIPTION
    Runs every on-camera command COLD (real Azure calls, cache cleared) and then
    WARM (cache replay), writing everything to validation-output.txt.

    This is the only thing in this folder that proves anything.

    There is no offline harness in this lesson, on purpose. Lesson 16 shipped
    with one that passed 9 of 9 assertions while three beats were broken,
    because it tested the shape of requests this repo composed rather than what
    Azure did with them. An assertion about your own request proves nothing
    about the service. So the checks here are all downstream of a real call:

      * did the indexer report success, and how many items did it process
      * how many chunks are actually in the index
      * did a phrase that exists ONLY as pixels come back from a text query
      * did the reranker score appear when, and only when, it should have
      * did the query planner emit more than one subquery
      * did the grounded model decline the question it cannot answer

    When it finishes green the cache is primed, so the first take is a warm one
    and every retake shows byte-identical scores.

.EXAMPLE
    pwsh -File validate.ps1
    pwsh -File validate.ps1 -SkipCold      # cache replay only, ~30 seconds
#>
[CmdletBinding()]
param(
    [switch]$SkipCold
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'
# Without this, a redirected run buffers stdout and the log stays empty until
# the process exits -- which looks exactly like a hang.
$env:PYTHONUNBUFFERED = '1'

$log = Join-Path $PSScriptRoot 'validation-output.txt'
if (Test-Path $log) { Remove-Item $log -Force }

function Write-Both {
    param([string]$Text)
    Write-Host $Text
    Add-Content -Path $script:log -Value $Text -Encoding utf8
}

function Invoke-Step {
    param([string]$Label, [string[]]$CliArgs)
    Write-Both ''
    Write-Both ('=' * 78)
    Write-Both "  $Label"
    Write-Both ("  uv run python " + ($CliArgs -join ' '))
    Write-Both ('=' * 78)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $out = & uv run python @CliArgs 2>&1 | Out-String
    $sw.Stop()
    Write-Both $out.TrimEnd()
    Write-Both ("  [elapsed {0:N1}s]" -f $sw.Elapsed.TotalSeconds)
    if ($LASTEXITCODE -ne 0) {
        Write-Both "  *** FAILED with exit code $LASTEXITCODE ***"
        $script:failed += $Label
    }
}

# ---------------------------------------------------------------------------
# Environment guard. Every one of these has cost this course a take before.
# ---------------------------------------------------------------------------
Write-Both 'AI-103 Lesson 17 validation -- retrieval and grounding pipelines'
Write-Both ("started {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    if (Test-Path (Join-Path $PSScriptRoot '.venv\bin\python')) {
        Write-Both ''
        Write-Both 'ERROR: .venv is a LINUX virtual environment. Windows uv cannot use it.'
        Write-Both '         Move-Item .venv _to_delete-venv-linux'
        Write-Both '         uv sync'
        exit 1
    }
    Write-Both ''
    Write-Both 'No virtual environment found. Building it with: uv sync'
    & uv sync
    if ($LASTEXITCODE -ne 0) { Write-Both 'uv sync FAILED.'; exit 1 }
}

if (-not (Test-Path (Join-Path $PSScriptRoot '.env'))) {
    Write-Both ''
    Write-Both 'ERROR: no .env found. Copy .env.example to .env and fill every value.'
    exit 1
}

$required = @('SEARCH_ENDPOINT', 'SEARCH_API_VERSION', 'SEARCH_PREVIEW_API_VERSION',
              'AZURE_SUBSCRIPTION_ID', 'AZURE_RESOURCE_GROUP', 'STORAGE_ACCOUNT',
              'FOUNDRY_RESOURCE_URI', 'FOUNDRY_OPENAI_ENDPOINT',
              'EMBEDDING_DEPLOYMENT', 'CHAT_DEPLOYMENT', 'PROJECT_ENDPOINT')
$envText = Get-Content (Join-Path $PSScriptRoot '.env') -Raw
foreach ($key in $required) {
    if ($envText -notmatch "(?m)^\s*$key\s*=\s*\S") {
        Write-Both "ERROR: $key is missing or empty in .env"
        exit 1
    }
}

# az login is the credential every script uses (AzureCliCredential, deliberately).
$account = & az account show --query "user.name" -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $account) {
    Write-Both 'ERROR: not logged in. Run: az login'
    exit 1
}
Write-Both "azure identity  : $account"

# --- the guard that matters most on this service ---------------------------
# A search service ships with data-plane Entra auth OFF. In that state a valid
# bearer token from an Owner comes back 403 and every script in this folder
# dies on its first call. Prove the DATA PLANE answers before spending time.
$searchEndpoint = ([regex]::Match($envText, '(?m)^\s*SEARCH_ENDPOINT\s*=\s*(\S+)')).Groups[1].Value.TrimEnd('/')
$apiVersion = ([regex]::Match($envText, '(?m)^\s*SEARCH_API_VERSION\s*=\s*(\S+)')).Groups[1].Value
$token = & az account get-access-token --resource https://search.azure.com --query accessToken -o tsv 2>$null
try {
    Invoke-RestMethod -Uri "$searchEndpoint/indexes?api-version=$apiVersion&`$select=name" `
        -Headers @{ Authorization = "Bearer $token" } -Method Get | Out-Null
    Write-Both "search data plane: reachable with a bearer token"
}
catch {
    $code = $_.Exception.Response.StatusCode.value__
    Write-Both ''
    Write-Both "ERROR: the search data plane returned HTTP $code."
    if ($code -eq 403) {
        Write-Both '       403 here almost always means Entra data-plane auth is off,'
        Write-Both '       or the roles are missing. Owner does NOT grant data actions.'
        Write-Both '         az search service update -n <svc> -g <rg> \'
        Write-Both '             --auth-options aadOrApiKey --aad-auth-failure-mode http403'
        Write-Both '       Then assign, on the SERVICE scope:'
        Write-Both '         Search Service Contributor, Search Index Data Contributor,'
        Write-Both '         Search Index Data Reader'
        Write-Both '       Role assignments take several minutes to take effect.'
    }
    exit 1
}

# --- the search service needs an identity of its own -----------------------
# Everything in this lesson is keyless: the blob connection, the Foundry
# billing attach, the embedding skill, the vectorizer, and the knowledge base's
# model. All of them ride the SERVICE's managed identity, which is a different
# security principal from the human above.
$rg = ([regex]::Match($envText, '(?m)^\s*AZURE_RESOURCE_GROUP\s*=\s*(\S+)')).Groups[1].Value
$serviceName = ([regex]::Match($searchEndpoint, 'https://([^.]+)\.')).Groups[1].Value
$identity = & az search service show -n $serviceName -g $rg --query "identity.principalId" -o tsv 2>$null
if (-not $identity) {
    Write-Both ''
    Write-Both 'ERROR: the search service has NO managed identity.'
    Write-Both '       Every keyless connection in this lesson depends on it.'
    Write-Both "         az search service update -n $serviceName -g $rg --identity-type SystemAssigned"
    Write-Both '       Then grant that identity:'
    Write-Both '         Cognitive Services User        on the Foundry resource'
    Write-Both '         Cognitive Services OpenAI User on the Foundry resource'
    Write-Both '         Storage Blob Data Reader       on the storage account'
    exit 1
}
Write-Both "search identity : $identity"

& uv run python -c "import azure.identity, azure.storage.blob, dotenv" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Both 'ERROR: dependencies missing. Run: uv sync'
    exit 1
}
Write-Both 'dependencies    : ok (identity, storage-blob, dotenv)'

$script:failed = @()

# ---------------------------------------------------------------------------
# COLD -- real Azure calls, cache cleared, indexer high-water mark cleared.
# ---------------------------------------------------------------------------
if (-not $SkipCold) {
    Invoke-Step 'COLD 1/3  Beat 2  ingest, enrich, project' @('m17_ingest.py', '--reset')
    Invoke-Step 'COLD 2/3  Beat 3a keyword, vector, hybrid, semantic' @('m17_retrieve.py', '--clean')
    Invoke-Step 'COLD 3/3  Beat 3b knowledge base, agent tool' @('m17_agent.py')
}

# ---------------------------------------------------------------------------
# WARM -- this is what recording feels like. The indexer processes nothing
# because nothing changed; the queries replay from cache byte-identically.
# ---------------------------------------------------------------------------
Invoke-Step 'WARM 1/3  Beat 2  ingest is idempotent' @('m17_ingest.py')
Invoke-Step 'WARM 2/3  Beat 3a cached retrieval' @('m17_retrieve.py')
Invoke-Step 'WARM 3/3  Beat 3b cached knowledge base' @('m17_agent.py')

# ---------------------------------------------------------------------------
# Assertions against the LOG, not against a mock. Every one of these strings
# only exists if Azure actually did the work.
# ---------------------------------------------------------------------------
Write-Both ''
Write-Both ('=' * 78)
Write-Both '  PROOF CHECKS -- each one is downstream of a real Azure response'
Write-Both ('=' * 78)
$logText = Get-Content $log -Raw
$checks = @(
    @{ N = 'indexer reported success';                P = 'status\s+success' },
    @{ N = 'chunks landed in the index';              P = 'search documents \(chunks\)\s+\d+' },
    @{ N = 'OCR text is a citable search document';   P = 'only ever existed as pixels' },
    @{ N = 'the scanned image won the grounding query'; P = 'grounding chunk came out of the scanned image' },
    @{ N = 'semantic reranking was a silent no-op without semanticQuery'; P = 'A was never reranked. B was' },
    @{ N = 'query planning decomposed the question';  P = 'subquery 2' },
    @{ N = 'the grounded answer carries citations';   P = 'citations back to reference ids' },
    # The agent has to CALL the retrieval tool, not answer from what the model
    # already knows. A cited, correct answer that never retrieved is the exact
    # failure this lesson exists to expose, and it looks identical on screen.
    @{ N = 'the agent invoked the retrieval tool';    P = 'invoked the retrieval pipeline \d+ time' },
    @{ N = 'the agent declined the unanswerable question'; P = 'declined instead of inventing' },
    @{ N = 'the knowledge base exposes an MCP tool';  P = 'knowledge_base_retrieve' }
)
foreach ($check in $checks) {
    if ($logText -match $check.P) {
        Write-Both ("  [OK]   " + $check.N)
    }
    else {
        Write-Both ("  [MISS] " + $check.N)
        $script:failed += $check.N
    }
}

Write-Both ''
Write-Both ('=' * 78)
if ($script:failed.Count -eq 0) {
    Write-Both '  ALL GREEN. Cache is primed -- your first take is a warm one.'
    Write-Both "  Full transcript: $log"
    Write-Both ('=' * 78)
    exit 0
}
Write-Both '  FAILED:'
foreach ($f in $script:failed) { Write-Both "    - $f" }
Write-Both ('=' * 78)
exit 1
