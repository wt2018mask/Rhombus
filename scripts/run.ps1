param(
    [Parameter(Position = 0)]
    [string]$Command,

    [Parameter(Position = 1)]
    [string]$PytestTarget,

    [Parameter(Position = 2, ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArguments
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repoRoot

function Write-Result {
    param([bool]$Passed)

    Write-Host 'RESULT'
    if ($Passed) {
        Write-Host 'PASS'
        exit 0
    }

    Write-Host 'FAIL'
    exit 1
}

if ($Command -ne 'test' -or [string]::IsNullOrWhiteSpace($PytestTarget) -or $ExtraArguments.Count -gt 0) {
    Write-Host 'Usage: .\scripts\run.ps1 test <pytest-target>'
    Write-Result $false
}

Write-Host 'PYTHON'
$python = $null
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'

function Test-PythonCandidate {
    param([string]$Candidate)

    try {
        & $Candidate -c 'import sys; print(sys.executable)' *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Select-PythonCandidate {
    param([string]$Candidate)

    if (-not (Test-PythonCandidate $Candidate)) {
        Write-Host "Skipped unusable Python candidate: $Candidate"
        return $false
    }

    $script:python = $Candidate
    return $true
}

if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    [void](Select-PythonCandidate $venvPython)
}

if ($null -eq $python -and -not [string]::IsNullOrWhiteSpace($env:RHOMBUS_PYTHON)) {
    if (-not (Test-Path -LiteralPath $env:RHOMBUS_PYTHON -PathType Leaf)) {
        Write-Host "RHOMBUS_PYTHON does not exist: $($env:RHOMBUS_PYTHON)"
        Write-Result $false
    }
    [void](Select-PythonCandidate $env:RHOMBUS_PYTHON)
}

if ($null -eq $python) {
    foreach ($candidate in @('python', 'py')) {
        $commandInfo = Get-Command $candidate -CommandType Application -ErrorAction SilentlyContinue
        if ($null -ne $commandInfo) {
            if (Select-PythonCandidate $commandInfo.Source) {
                break
            }
        }
    }
}

if ($null -eq $python) {
    Write-Host 'No usable Python interpreter found; create .venv or set RHOMBUS_PYTHON to a valid Python executable.'
    Write-Result $false
}
Write-Host $python

Write-Host 'PYTEST'
& $python -m pytest $PytestTarget -v
$pytestExit = $LASTEXITCODE

Write-Host 'DIFF CHECK'
git diff --check
$diffExit = $LASTEXITCODE

Write-Host 'STATUS'
git status --short

Write-Result ($pytestExit -eq 0 -and $diffExit -eq 0)
