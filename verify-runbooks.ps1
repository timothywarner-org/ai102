#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Check every lesson demo runbook against the files and CLI flags it tells you to use.

.DESCRIPTION
    Runbooks drift away from code silently. A script gets renamed, a flag gets dropped, a
    folder gets restructured -- and nothing complains until the instructor is on camera
    reading a DO step that cannot be executed. Three real instances of this were found by
    hand in August 2026: the Lesson 7 runbook referenced a `demo\` folder and three scripts
    that never existed in the repo, the Lesson 11 runbook claimed its own lesson had no
    virtual environment, and Lesson 10 pointed at `@tool` on a line holding `load_dotenv()`.

    This catches that class mechanically:

      1. FILE REFERENCES  -- every `*.py` / `*.ps1` / `*.ipynb` named in a runbook must exist,
                             either in that lesson folder or at a path the runbook spells out.
      2. CLI FLAGS        -- every `--flag` shown next to a script must appear in that script's
                             argparse (or param block, for PowerShell).
      3. STALE PATHS      -- absolute local paths and private-folder references that should
                             never ship in a public learner repo.

    Read-only. Makes no Azure calls, costs nothing, and never edits a file.

.PARAMETER Lesson
    Check a single lesson by number, e.g. -Lesson 07. Omit to check all.

.PARAMETER Quiet
    Suppress the per-lesson OK lines; print only problems and the summary.

.EXAMPLE
    pwsh -File verify-runbooks.ps1
    Check every runbook and print a summary.

.EXAMPLE
    pwsh -File verify-runbooks.ps1 -Lesson 11
    Check only Lesson 11, printing every reference it resolves.

.NOTES
    Exit code 0 = clean, 1 = at least one problem found. Suitable for CI.
#>
[CmdletBinding()]
param(
    [string] $Lesson,
    [switch] $Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot   = Split-Path -Parent $MyInvocation.MyCommand.Path
$lessonsDir = Join-Path $repoRoot 'lessons'

if (-not (Test-Path $lessonsDir)) {
    Write-Error "lessons/ not found next to this script. Run it from the repo root."
    exit 1
}

$problems = [System.Collections.Generic.List[string]]::new()
$checked  = 0

function Add-Problem {
    param([string] $LessonName, [string] $Runbook, [int] $Line, [string] $Message)
    $script:problems.Add(("{0}`n    {1}:{2}`n    {3}" -f $LessonName, $Runbook, $Line, $Message))
}

# Scripts a runbook may legitimately reference from a sibling lesson, plus repo-level tools.
# Anything else must live in the lesson folder the runbook belongs to.
$repoLevelFiles = @('verify-demos.ps1', 'verify-runbooks.ps1')

# Index every candidate script ONCE. An earlier cut called Get-ChildItem -Recurse per
# reference, which rescanned the whole tree hundreds of times and took minutes. Build the
# lookup up front: leaf name -> full path. .venv and node_modules are excluded because a
# vendored copy of a common name would otherwise mask a genuinely missing lesson file.
$fileIndex = @{}
Get-ChildItem $lessonsDir -Recurse -File -Include '*.py', '*.ps1', '*.ipynb' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch '\\(\.venv|node_modules|__pycache__|_archive)\\' } |
    ForEach-Object {
        if (-not $fileIndex.ContainsKey($_.Name)) { $fileIndex[$_.Name] = $_.FullName }
    }

$runbooks = Get-ChildItem $lessonsDir -Recurse -File -Filter 'Warner.AI-103.Lesson-*-demo-runbook.md' |
    Sort-Object Name

if ($Lesson) {
    $pad = $Lesson.PadLeft(2, '0')
    $runbooks = $runbooks | Where-Object { $_.Name -match "Lesson-$pad-" }
    if (-not $runbooks) {
        Write-Error "No runbook found for lesson '$Lesson'."
        exit 1
    }
}

foreach ($rb in $runbooks) {
    $lessonFolder = $rb.Directory
    $lessonName   = $lessonFolder.Name
    $rbRelative   = $rb.FullName.Replace("$repoRoot\", '')
    $lines        = Get-Content $rb.FullName
    $checked++
    $found = 0

    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line   = $lines[$i]
        $lineNo = $i + 1

        # --- 1. FILE REFERENCES -------------------------------------------------
        # Match bare script names in backticks or plain prose: m07_prompt_demo.py,
        # demo\reflect.py, validate.ps1. Skip fenced-code noise like pip package names.
        foreach ($m in [regex]::Matches($line, '(?<![\w/\\.-])([A-Za-z0-9_./\\-]+\.(?:py|ps1|ipynb))\b')) {
            $ref  = $m.Groups[1].Value
            $leaf = Split-Path $ref -Leaf

            # Placeholders and generic examples are not claims about the repo.
            if ($leaf -match '^(script|your|name|file|foo|bar)\.') { continue }
            if ($ref  -match '^<.*>$') { continue }

            $found++

            # Resolve: lesson folder first, then the path as written from the repo root,
            # then anywhere under lessons/ (cross-lesson references are legitimate and
            # several runbooks make them on purpose).
            $inLesson = Join-Path $lessonFolder.FullName $ref
            $fromRoot = Join-Path $repoRoot $ref

            $resolved = (Test-Path $inLesson) -or
                        (Test-Path $fromRoot) -or
                        ($leaf -in $repoLevelFiles -and (Test-Path (Join-Path $repoRoot $leaf))) -or
                        $fileIndex.ContainsKey($leaf)

            if (-not $resolved) {
                Add-Problem $lessonName $rbRelative $lineNo "MISSING FILE: '$ref' is referenced but does not exist"
            }
        }

        # --- 2. CLI FLAGS -------------------------------------------------------
        # Only inspect lines that actually invoke a script, so prose using a double
        # hyphen is not mistaken for a flag.
        $invoke = [regex]::Match($line, '([A-Za-z0-9_-]+\.(?:py|ps1))((?:\s+-{1,2}[A-Za-z][\w-]*)+)')
        if ($invoke.Success) {
            $scriptLeaf = $invoke.Groups[1].Value
            $flagBlob   = $invoke.Groups[2].Value

            $scriptPath = Join-Path $lessonFolder.FullName $scriptLeaf
            if ((-not (Test-Path $scriptPath)) -and $fileIndex.ContainsKey($scriptLeaf)) {
                $scriptPath = $fileIndex[$scriptLeaf]
            }

            if (Test-Path $scriptPath) {
                $src = Get-Content $scriptPath -Raw
                foreach ($fm in [regex]::Matches($flagBlob, '--([A-Za-z][\w-]*)')) {
                    $flag = $fm.Groups[1].Value

                    # argparse and PowerShell both supply these for free; a script never
                    # declares them, so checking for a declaration would always fail.
                    if ($flag -in @('help', 'version', 'verbose', 'debug')) { continue }

                    # argparse declares "--flag"; PowerShell declares [switch]$Flag / [string]$Flag.
                    $declared = $src -match [regex]::Escape("--$flag") -or
                                $src -match ('\$' + [regex]::Escape(($flag -replace '-', '')) + '\b')

                    if (-not $declared) {
                        Add-Problem $lessonName $rbRelative $lineNo "MISSING FLAG: '$scriptLeaf --$flag' is not declared in that script"
                    }
                }
            }
        }

        # --- 3. STALE PATHS -----------------------------------------------------
        if ($line -match '[A-Za-z]:\\(?:Users|github)\\') {
            Add-Problem $lessonName $rbRelative $lineNo "ABSOLUTE PATH: leaks a machine-specific path into a public repo"
        }
        if ($line -match '(?i)\bGPD\b|Pearson\\') {
            Add-Problem $lessonName $rbRelative $lineNo "PRIVATE FOLDER: references the private Pearson authoring folder"
        }
    }

    if (-not $Quiet) {
        Write-Output ("  {0,-40} {1,3} references checked" -f $lessonName, $found)
    }
}

Write-Output ''
if ($problems.Count -eq 0) {
    Write-Output "PASS: $checked runbooks checked, no broken references."
    exit 0
}

Write-Output "FAIL: $($problems.Count) problem(s) across $checked runbooks."
Write-Output ''
foreach ($p in $problems) {
    Write-Output "  $p"
    Write-Output ''
}
exit 1
