# AI-103 Lesson 15 -- one-shot validation pass.
#
# Runs every demo command cold, captures ALL output to validation-output.txt,
# then re-runs warm so the cache is primed and your first take replays instantly.
#
#   pwsh -File validate.ps1
#
# Send validation-output.txt back and the runbook's [UNVERIFIED] markers get
# replaced with the real strings.

$ErrorActionPreference = 'Continue'

# Every step runs relative to this script, never to wherever the shell happened
# to be. Without this, running `pwsh -File lessons/15-.../validate.ps1` from the
# repo root makes every uv command miss the lesson's pyproject.toml.
Set-Location $PSScriptRoot

# ---------------------------------------------------------------------------
# Environment sanity, BEFORE anything else.
#
# A .venv created on one OS is unusable on another: Linux builds bin/python,
# Windows needs Scripts\python.exe. If this repo folder is ever touched from
# WSL, a container, or a mounted Linux VM, uv on Windows sees a .venv it cannot
# use and refuses every single command with a message that looks like a uv bug.
# It is not. Detect it and rebuild rather than making anyone debug it live.
#
# Do NOT hand-activate anything here. `uv run` resolves the environment on its
# own from any shell, with no activated state, which is the whole point.
# ---------------------------------------------------------------------------
$venv = Join-Path $PSScriptRoot '.venv'
$winPython = Join-Path $venv 'Scripts\python.exe'
if ((Test-Path $venv) -and -not (Test-Path $winPython)) {
    Write-Host "!! .venv exists but has no Windows Python (built on another OS). Rebuilding." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venv
}

# uv sync is idempotent: it creates .venv when missing and is a no-op when the
# lock is already satisfied. Run it unconditionally rather than only when .venv
# is absent, so a half-built or drifted environment self-heals too.
Write-Host ">> uv sync" -ForegroundColor Cyan
uv sync
if ($LASTEXITCODE -ne 0) { Write-Host "uv sync failed. Fix that first." -ForegroundColor Red; exit 1 }

# .env is the other thing that stops everything dead.
$envFile = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path $envFile)) {
    Write-Host "!! No .env found. Copy .env.example to .env and fill in all five values." -ForegroundColor Red
    Write-Host "   The scripts cannot reach Azure without it." -ForegroundColor Red
    exit 1
}

# Prove the interpreter answers before spending a single Azure call.
$probe = & uv run python -c "import openai, azure.identity, dotenv; print('deps ok')" 2>&1 | Out-String
if ($probe -notmatch 'deps ok') {
    Write-Host "!! Dependency probe failed:" -ForegroundColor Red
    Write-Host $probe
    exit 1
}
Write-Host ">> environment OK  ($($probe.Trim()))" -ForegroundColor Green


$log = Join-Path $PSScriptRoot 'validation-output.txt'
Remove-Item $log -ErrorAction SilentlyContinue

function Step($label, $cmd) {
    $banner = ('=' * 74)
    Add-Content $log "`n$banner`n# $label`n# `$ $cmd`n$banner"
    Write-Host "`n>> $label" -ForegroundColor Cyan
    $sw = [Diagnostics.Stopwatch]::StartNew()
    # Pin the working directory per step. A step that changes directory (or dies
    # partway through one) must not silently relocate every step after it.
    Push-Location $PSScriptRoot
    $out = Invoke-Expression "$cmd 2>&1" | Out-String
    Pop-Location
    $sw.Stop()
    Add-Content $log $out
    Add-Content $log ("[elapsed] {0:N1}s" -f $sw.Elapsed.TotalSeconds)
    Write-Host $out
    Write-Host ("   {0:N1}s" -f $sw.Elapsed.TotalSeconds) -ForegroundColor DarkGray
}

Add-Content $log "AI-103 Lesson 15 validation pass"
Add-Content $log ("az account: " + (az account show --query user.name -o tsv 2>&1))
Add-Content $log ("python:     " + (uv run python --version 2>&1))

# make_assets.py writes next to itself, so it does not need the shell to be in
# assets/. Calling it by path keeps this step directory-independent.
Step 'pre-flight: regenerate fixtures' 'uv run python assets/make_assets.py'
Step 'dry-run: extract'   'uv run python m15_extract.py --dry-run'
Step 'dry-run: translate' 'uv run python m15_translate.py --dry-run'
Step 'offline harness (no Azure calls)' 'uv run python offline_harness.py'

Step 'COLD 1/4  extract'                 'uv run python m15_extract.py --clean'
Step 'COLD 2/4  extract --loose'         'uv run python m15_extract.py --loose'
Step 'COLD 3/4  translate --no-dictionary' 'uv run python m15_translate.py --no-dictionary'
Step 'COLD 4/4  translate'               'uv run python m15_translate.py'

Step 'WARM 1/4  extract'                 'uv run python m15_extract.py'
Step 'WARM 2/4  extract --loose'         'uv run python m15_extract.py --loose'
Step 'WARM 3/4  translate --no-dictionary' 'uv run python m15_translate.py --no-dictionary'
Step 'WARM 4/4  translate'               'uv run python m15_translate.py'

Write-Host "`nDone. Cache is primed -- your next run is a warm take." -ForegroundColor Green
Write-Host "Send me: $log" -ForegroundColor Green
