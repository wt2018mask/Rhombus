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

function Write-CommandResult {
    param([int]$ExitCode)

    Write-Host 'RESULT'
    if ($ExitCode -eq 0) {
        Write-Host 'PASS'
    } else {
        Write-Host 'FAIL'
    }
    exit $ExitCode
}

$extraCount = @($ExtraArguments).Count
$validCommand = $Command -in @('test', 'kaggle-list', 'kaggle-quota', 'kaggle-status', 'kaggle-logs', 'kaggle-inspect')
$validArguments = switch ($Command) {
    'test' { -not [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-list' { [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-quota' { [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-status' { -not [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-logs' { -not [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-inspect' { -not [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    default { $false }
}

if (-not $validCommand -or -not $validArguments) {
    Write-Host 'Usage: .\scripts\run.ps1 test <pytest-target>'
    Write-Host '       .\scripts\run.ps1 kaggle-list'
    Write-Host '       .\scripts\run.ps1 kaggle-quota'
    Write-Host '       .\scripts\run.ps1 kaggle-status <kernel-ref>'
    Write-Host '       .\scripts\run.ps1 kaggle-logs <kernel-ref>'
    Write-Host '       .\scripts\run.ps1 kaggle-inspect <kernel-ref>'
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

if ($Command -eq 'kaggle-inspect') {
    $statusOutput = @(& $python -m kaggle kernels status $PytestTarget 2>&1 | Tee-Object -Variable capturedStatusOutput)
    $statusExit = $LASTEXITCODE

    if ($statusExit -ne 0) {
        Write-Host 'QUERY_OK=false'
        Write-Host 'REMOTE_STATE=UNKNOWN'
        Write-Host 'REMOTE_OK=false'
        Write-Host 'RESULT'
        Write-Host 'FAIL'
        exit $statusExit
    }

    $statusText = ($statusOutput | ForEach-Object { $_.ToString() }) -join "`n"
    $stateMatch = [regex]::Match($statusText, 'KernelWorkerStatus\.([A-Za-z0-9_]+)')

    if (-not $stateMatch.Success) {
        Write-Host 'QUERY_OK=true'
        Write-Host 'REMOTE_STATE=UNKNOWN'
        Write-Host 'REMOTE_TERMINAL=false'
        Write-Host 'REMOTE_OK=false'
        Write-Host 'RESULT'
        Write-Host 'UNKNOWN'
        exit 11
    }

    $remoteState = $stateMatch.Groups[1].Value
    Write-Host 'QUERY_OK=true'
    Write-Host "REMOTE_STATE=$remoteState"

    switch ($remoteState) {
        'COMPLETE' {
            Write-Host 'REMOTE_TERMINAL=true'
            Write-Host 'REMOTE_OK=true'
            Write-Host 'RESULT'
            Write-Host 'PASS'
            exit 0
        }
        'ERROR' {
            Write-Host 'REMOTE_TERMINAL=true'
            Write-Host 'REMOTE_OK=false'
            & $python -m kaggle kernels logs $PytestTarget 2>&1
            Write-Host 'RESULT'
            Write-Host 'REMOTE_ERROR'
            exit 20
        }
        default {
            Write-Host 'REMOTE_TERMINAL=false'
            Write-Host 'REMOTE_OK=false'
            Write-Host 'RESULT'
            Write-Host 'REMOTE_PENDING'
            exit 10
        }
    }
}

if ($Command -eq 'kaggle-list' -or $Command -eq 'kaggle-quota' -or $Command -eq 'kaggle-status' -or $Command -eq 'kaggle-logs') {
    switch ($Command) {
        'kaggle-list' {
            Write-Host 'KAGGLE LIST'
            & $python -m kaggle kernels list --mine
        }
        'kaggle-quota' {
            Write-Host 'KAGGLE QUOTA'
            & $python -m kaggle quota
        }
        'kaggle-status' {
            Write-Host 'KAGGLE STATUS'
            & $python -m kaggle kernels status $PytestTarget
        }
        'kaggle-logs' {
            Write-Host 'KAGGLE LOGS'
            & $python -m kaggle kernels logs $PytestTarget
        }
    }
    $kaggleExit = $LASTEXITCODE
    Write-CommandResult $kaggleExit
}

Write-Host 'PYTEST'
& $python -m pytest $PytestTarget -v
$pytestExit = $LASTEXITCODE

Write-Host 'DIFF CHECK'
git diff --check
$diffExit = $LASTEXITCODE

Write-Host 'STATUS'
git status --short

Write-Result ($pytestExit -eq 0 -and $diffExit -eq 0)
