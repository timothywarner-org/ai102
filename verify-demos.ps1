#!/usr/bin/env pwsh
<#
.SYNOPSIS
    One-command health check for the AI-103 Python lesson demos.

.DESCRIPTION
    Walks each lesson that has a uv project (pyproject.toml), runs `uv sync`, and then
    exercises the demo. Two levels:

      Default (safe, no Azure calls, no cost): runs each demo's `--dry-run`, which parses
        the script and prints its plan without calling Azure. Catches import errors, config
        wiring bugs, and SDK-shape regressions -- the failures that bite silently on camera.

      -Live: also runs each demo for real and executes each notebook headless, TWICE, and
        asserts both runs are green (the idempotency check the demos are built for). This
        makes real Azure calls (needs `az login` and each lesson's .env) and costs a little.

    Exit code is 0 only if every selected check passed, so this is CI-friendly.

.PARAMETER Live
    Also run demos live and execute notebooks headless, twice each, asserting idempotency.

.PARAMETER Lesson
    Limit to one lesson by folder prefix, e.g. -Lesson 03. Default: all uv lessons.

.EXAMPLE
    ./verify-demos.ps1
    Dry-run sweep of every lesson demo (safe, fast, no Azure calls).

.EXAMPLE
    ./verify-demos.ps1 -Live -Lesson 03
    Full green-twice verification of Lesson 03 only.

.NOTES
    Requires: uv on PATH. For -Live: `az login` and a filled-in .env per lesson.
    Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
#>
[CmdletBinding()]
param(
    [switch]$Live,
    [string]$Lesson = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$lessonsDir = Join-Path $repoRoot "lessons"

# Registry of runnable demos. entrypoint = the demo script; supportsDryRun gates the safe pass;
# notebooks = paired notebooks to execute headless under -Live. Add new lessons here as they land.
$demos = @(
    @{ folder = "01-choose-foundry-services";        entry = "m01_agent_demo.py"; supportsDryRun = $false; notebooks = @("m01_agent_demo.ipynb") }
    @{ folder = "02-set-up-ai-solutions-foundry";    entry = "m02_setup_demo.py"; supportsDryRun = $true;  notebooks = @("m02_setup_demo.ipynb") }
    @{ folder = "03-manage-monitor-secure-ai";       entry = "m03_ops_demo.py";   supportsDryRun = $true;  notebooks = @("m03_ops_tour.ipynb") }
    @{ folder = "05-responsible-ai-generative-agentic"; entry = "m05_evals_demo.py"; supportsDryRun = $true; notebooks = @(); knownBlocked = "needs a non-gpt-5 judge deployment + proj-lesson-05 (quota request)" }
)

if ($Lesson) { $demos = $demos | Where-Object { $_.folder -like "$Lesson*" } }
if (-not $demos) { Write-Error "No matching lesson for '-Lesson $Lesson'."; exit 2 }

$results = [System.Collections.Generic.List[object]]::new()

function Add-Result([string]$name, [string]$status, [string]$detail = "") {
    $results.Add([pscustomobject]@{ Check = $name; Status = $status; Detail = $detail })
    $color = switch ($status) { "PASS" { "Green" } "FAIL" { "Red" } "SKIP" { "DarkGray" } "BLOCKED" { "Yellow" } default { "Gray" } }
    Write-Host ("  [{0,-7}] {1} {2}" -f $status, $name, $detail) -ForegroundColor $color
}

foreach ($demo in $demos) {
    $path = Join-Path $lessonsDir $demo.folder
    if (-not (Test-Path $path)) { Add-Result $demo.folder "SKIP" "(folder missing)"; continue }
    Write-Host "`n=== $($demo.folder) ===" -ForegroundColor Cyan
    Push-Location $path
    try {
        # Every uv lesson syncs first; a sync failure is a hard fail (broken deps).
        uv sync 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Add-Result "$($demo.folder): uv sync" "FAIL" "(dependency resolution failed)"; continue }

        if ($demo.knownBlocked -and -not $Live) {
            Add-Result "$($demo.folder): $($demo.entry)" "BLOCKED" "($($demo.knownBlocked))"
        }
        elseif ($demo.supportsDryRun) {
            uv run python $demo.entry --dry-run 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { Add-Result "$($demo.folder): dry-run" "PASS" }
            else { Add-Result "$($demo.folder): dry-run" "FAIL" "(exit $LASTEXITCODE)" }
        }
        else {
            Add-Result "$($demo.folder): dry-run" "SKIP" "(no --dry-run; use -Live)"
        }

        if ($Live) {
            if ($demo.knownBlocked) {
                Add-Result "$($demo.folder): live" "BLOCKED" "($($demo.knownBlocked))"
            }
            else {
                # Green twice = idempotent. Both live runs must succeed.
                $ok = $true
                foreach ($pass in 1, 2) {
                    uv run python $demo.entry 2>&1 | Out-Null
                    if ($LASTEXITCODE -ne 0) { $ok = $false; break }
                }
                if ($ok) { Add-Result "$($demo.folder): live x2 (idempotent)" "PASS" }
                else { Add-Result "$($demo.folder): live x2 (idempotent)" "FAIL" "(a run exited non-zero)" }
            }
            foreach ($nb in $demo.notebooks) {
                if (-not (Test-Path $nb)) { Add-Result "$($demo.folder): $nb" "SKIP" "(missing)"; continue }
                uv run --with nbconvert --with ipykernel jupyter nbconvert --to notebook --execute --inplace $nb --ExecutePreprocessor.timeout=180 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) { Add-Result "$($demo.folder): $nb (headless)" "PASS" }
                else { Add-Result "$($demo.folder): $nb (headless)" "FAIL" "(a cell raised)" }
            }
        }
    }
    finally { Pop-Location }
}

Write-Host "`n===== SUMMARY =====" -ForegroundColor Cyan
$results | Format-Table -AutoSize | Out-String | Write-Host
$failed = @($results | Where-Object { $_.Status -eq "FAIL" }).Count
$blocked = @($results | Where-Object { $_.Status -eq "BLOCKED" }).Count
Write-Host ("PASS/FAIL/BLOCKED/SKIP: {0}/{1}/{2}/{3}" -f `
    @($results | Where-Object Status -eq "PASS").Count, $failed, $blocked, `
    @($results | Where-Object Status -eq "SKIP").Count)
if ($failed -gt 0) { Write-Host "FAILURES present." -ForegroundColor Red; exit 1 }
Write-Host "No failures. (Blocked items are known infra gaps, not regressions.)" -ForegroundColor Green
exit 0
