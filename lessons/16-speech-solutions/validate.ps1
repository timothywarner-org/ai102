<#
.SYNOPSIS
    AI-103 Lesson 16 -- prove the demo works against LIVE Azure before recording.

.DESCRIPTION
    Runs every on-camera command COLD (real Azure calls) and then WARM (cache
    replay), writing everything to validation-output.txt.

    This is the only thing in this folder that proves anything. The offline
    harness tests local string logic; it cannot tell you whether Azure honours
    a request. That distinction cost this lesson a full rebuild.

    When it finishes green, the cache is primed, so the first take is a warm one
    and every retake is byte-identical.

.EXAMPLE
    pwsh -File validate.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipCold
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# Force UTF-8 end to end. Without this, French and German come back through the
# console codepage as mojibake -- in the log, and on camera if the terminal is
# not already UTF-8. The scripts also call sys.stdout.reconfigure themselves.
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

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
    Write-Both ('=' * 74)
    Write-Both "  $Label"
    Write-Both ("  uv run python " + ($CliArgs -join ' '))
    Write-Both ('=' * 74)
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
# Environment guard. Every one of these has bitten this course before.
# ---------------------------------------------------------------------------
Write-Both "AI-103 Lesson 16 validation"
Write-Both ("started {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    if (Test-Path (Join-Path $PSScriptRoot '.venv\bin\python')) {
        Write-Both ''
        Write-Both 'ERROR: .venv is a LINUX virtual environment. Windows uv cannot use it.'
        Write-Both '       Move it aside and rebuild:'
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

# Fail on config BEFORE spending an Azure call or a minute of your time.
$required = @('FOUNDRY_ACCOUNT_ENDPOINT', 'CHAT_MODEL', 'SPEECH_REGION', 'SPEECH_RESOURCE_ID')
$envText = Get-Content (Join-Path $PSScriptRoot '.env') -Raw
foreach ($key in $required) {
    if ($envText -notmatch "(?m)^\s*$key\s*=\s*\S") {
        Write-Both "ERROR: $key is missing or empty in .env"
        exit 1
    }
}
if ($envText -notmatch "(?m)^\s*AUDIO_MODEL\s*=\s*\S") {
    Write-Both ''
    Write-Both 'WARNING: AUDIO_MODEL is empty. Beat 3 will run Path A alone.'
    Write-Both '         Deploy an audio-capable model first. NOTE: the'
    Write-Both '         gpt-4o-*-audio-preview family is gone from the catalog.'
    Write-Both '         Current options: gpt-audio, gpt-audio-mini, gpt-audio-1.5.'
}

# az login is the credential the scripts use (AzureCliCredential, deliberately).
$account = & az account show --query "user.name" -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $account) {
    Write-Both 'ERROR: not logged in. Run: az login'
    exit 1
}
Write-Both "azure identity : $account"

# Import probe. Cheaper to fail here than three Azure calls deep.
& uv run python -c "import azure.cognitiveservices.speech, azure.identity, openai, dotenv" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Both 'ERROR: dependencies missing. Run: uv sync'
    exit 1
}
Write-Both 'dependencies  : ok (speech sdk, identity, openai, dotenv)'

$script:failed = @()

# ---------------------------------------------------------------------------
# Local logic first. Fast, free, and it fails loudly.
# ---------------------------------------------------------------------------
Invoke-Step 'OFFLINE  pure-function checks' @('offline_harness.py')

# ---------------------------------------------------------------------------
# COLD -- real Azure calls, cache cleared.
# ---------------------------------------------------------------------------
if (-not $SkipCold) {
    Invoke-Step 'COLD 1/4  Beat 2  round trip, no phrase list' @('m16_speech.py', '--clean', '--no-phrase-list')
    Invoke-Step 'COLD 2/4  Beat 2  phrase list repairs the term' @('m16_speech.py')
    Invoke-Step 'COLD 3/4  Beat 3  transcript vs audio' @('m16_audio_reason.py')
    Invoke-Step 'COLD 4/4  Beat 4  two routes out' @('m16_translate_speech.py')
}

# ---------------------------------------------------------------------------
# WARM -- everything should replay from cache. This is what recording feels like.
# ---------------------------------------------------------------------------
Invoke-Step 'WARM 1/4  Beat 2  round trip, no phrase list' @('m16_speech.py', '--no-phrase-list')
Invoke-Step 'WARM 2/4  Beat 2  phrase list repairs the term' @('m16_speech.py')
Invoke-Step 'WARM 3/4  Beat 3  transcript vs audio' @('m16_audio_reason.py')
Invoke-Step 'WARM 4/4  Beat 4  two routes out' @('m16_translate_speech.py')

Write-Both ''
Write-Both ('=' * 74)
if ($script:failed.Count -eq 0) {
    Write-Both '  ALL STEPS GREEN. Cache is primed -- your first take is a warm one.'
    Write-Both "  Full transcript: $log"
    Write-Both ('=' * 74)
    exit 0
}
Write-Both '  FAILED STEPS:'
foreach ($f in $script:failed) { Write-Both "    - $f" }
Write-Both ('=' * 74)
exit 1
