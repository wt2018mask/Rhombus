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
$validCommand = $Command -in @('test', 'kaggle-list', 'kaggle-quota', 'kaggle-status', 'kaggle-logs', 'kaggle-inspect', 'kaggle-gpu-smoke-submit', 'kaggle-gpu-smoke-verify')
$validArguments = switch ($Command) {
    'test' { -not [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-list' { [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-quota' { [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-status' { -not [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-logs' { -not [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-inspect' { -not [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-gpu-smoke-submit' { [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-gpu-smoke-verify' { [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    default { $false }
}

if (-not $validCommand -or -not $validArguments) {
    Write-Host 'Usage: .\scripts\run.ps1 test <pytest-target>'
    Write-Host '       .\scripts\run.ps1 kaggle-list'
    Write-Host '       .\scripts\run.ps1 kaggle-quota'
    Write-Host '       .\scripts\run.ps1 kaggle-status <kernel-ref>'
    Write-Host '       .\scripts\run.ps1 kaggle-logs <kernel-ref>'
    Write-Host '       .\scripts\run.ps1 kaggle-inspect <kernel-ref>'
    Write-Host '       .\scripts\run.ps1 kaggle-gpu-smoke-submit'
    Write-Host '       .\scripts\run.ps1 kaggle-gpu-smoke-verify'
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

if ($Command -eq 'kaggle-gpu-smoke-verify') {
    $kernelRef = 'wt2018mask/rhombus-gpu-smoke'
    $statusOutput = @(& $python -m kaggle kernels status $kernelRef 2>&1 | Tee-Object -Variable capturedStatusOutput)
    $statusExit = $LASTEXITCODE

    if ($statusExit -ne 0) {
        Write-Host 'QUERY_OK=false'
        Write-Host 'REMOTE_STATE=UNKNOWN'
        Write-Host 'VERIFY_OK=false'
        Write-Host 'RESULT'
        Write-Host 'FAIL'
        exit $statusExit
    }

    $statusText = ($statusOutput | ForEach-Object { $_.ToString() }) -join "`n"
    $stateMatch = [regex]::Match($statusText, '(?im)^[^\r\n]*KernelWorkerStatus\.([A-Za-z0-9_]+)[^\r\n]*$')

    if (-not $stateMatch.Success) {
        Write-Host 'QUERY_OK=true'
        Write-Host 'REMOTE_STATE=UNKNOWN'
        Write-Host 'VERIFY_OK=false'
        Write-Host 'RESULT'
        Write-Host 'UNKNOWN'
        exit 11
    }

    $remoteState = $stateMatch.Groups[1].Value
    if ($remoteState -cne 'COMPLETE') {
        Write-Host 'QUERY_OK=true'
        Write-Host "REMOTE_STATE=$remoteState"
        Write-Host 'VERIFY_OK=false'
        Write-Host 'RESULT'
        Write-Host 'REMOTE_PENDING'
        exit 10
    }

    Write-Host 'QUERY_OK=true'
    Write-Host 'REMOTE_STATE=COMPLETE'

    $logOutput = @(& $python -m kaggle kernels logs $kernelRef 2>&1 | Tee-Object -Variable capturedLogOutput)
    $logsExit = $LASTEXITCODE

    if ($logsExit -ne 0) {
        Write-Host 'LOGS_OK=false'
        Write-Host 'VERIFY_OK=false'
        Write-Host 'RESULT'
        Write-Host 'FAIL'
        exit $logsExit
    }

    Write-Host 'LOGS_OK=true'
    $logText = ($logOutput | ForEach-Object { $_.ToString() }) -join "`n"
    $gpuAvailable = [regex]::IsMatch($logText, '(?im)^[^\r\n]*\bCUDA_AVAILABLE\s*=\s*true\b[^\r\n]*$')
    $smokePass = [regex]::IsMatch($logText, '(?im)^[^\r\n]*\bRHOMBUS_GPU_SMOKE\s*=\s*PASS\b[^\r\n]*$')
    $gpuCountMatch = [regex]::Match($logText, '(?im)^[^\r\n]*\bGPU_COUNT\s*=\s*(\d+)\b[^\r\n]*$')
    $gpuCountOk = $false
    if ($gpuCountMatch.Success) {
        try {
            $gpuCountOk = [int64]::Parse($gpuCountMatch.Groups[1].Value) -ge 1
        } catch {
            $gpuCountOk = $false
        }
    }

    if ($gpuAvailable -and $gpuCountOk -and $smokePass) {
        Write-Host 'GPU_AVAILABLE=true'
        Write-Host 'GPU_COUNT_OK=true'
        Write-Host 'SMOKE_PASS=true'
        Write-Host 'VERIFY_OK=true'
        Write-Host 'SCIENTIFIC_EVIDENCE=false'
        Write-Host 'RESULT'
        Write-Host 'PASS'
        exit 0
    }

    Write-Host "GPU_AVAILABLE=$($gpuAvailable.ToString().ToLowerInvariant())"
    Write-Host "GPU_COUNT_OK=$($gpuCountOk.ToString().ToLowerInvariant())"
    Write-Host "SMOKE_PASS=$($smokePass.ToString().ToLowerInvariant())"
    Write-Host 'VERIFY_OK=false'
    Write-Host 'SCIENTIFIC_EVIDENCE=false'
    Write-Host 'RESULT'
    Write-Host 'VERIFY_FAIL'
    exit 21
}

if ($Command -eq 'kaggle-gpu-smoke-submit') {
    $stagingDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("rhombus-gpu-smoke-" + [guid]::NewGuid().ToString('N'))

    try {
        New-Item -ItemType Directory -Path $stagingDirectory -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $repoRoot 'scripts\kaggle\gpu_smoke.py') -Destination (Join-Path $stagingDirectory 'gpu_smoke.py') -Force

        $metadata = [ordered]@{
            id = 'wt2018mask/rhombus-gpu-smoke'
            title = 'rhombus-gpu-smoke'
            code_file = 'gpu_smoke.py'
            language = 'python'
            kernel_type = 'script'
            is_private = $true
            enable_gpu = $true
            enable_internet = $false
            machine_shape = 'NvidiaTeslaT4'
            dataset_sources = @()
            competition_sources = @()
            kernel_sources = @()
            model_sources = @()
        }
        $metadataPath = Join-Path $stagingDirectory 'kernel-metadata.json'
        $metadataJson = $metadata | ConvertTo-Json -Depth 3
        $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($metadataPath, $metadataJson, $utf8WithoutBom)

        $metadataBytes = [System.IO.File]::ReadAllBytes($metadataPath)
        if ($metadataBytes.Length -ge 3 -and
            $metadataBytes[0] -eq 0xEF -and
            $metadataBytes[1] -eq 0xBB -and
            $metadataBytes[2] -eq 0xBF) {
            throw 'Generated Kaggle metadata contains an unexpected UTF-8 BOM.'
        }

        $validatedMetadata = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json
        if ($validatedMetadata.id -cne 'wt2018mask/rhombus-gpu-smoke' -or
            $validatedMetadata.code_file -cne 'gpu_smoke.py' -or
            $validatedMetadata.enable_gpu -ne $true -or
            $validatedMetadata.enable_internet -ne $false -or
            $validatedMetadata.machine_shape -cne 'NvidiaTeslaT4' -or
            -not (Test-Path -LiteralPath (Join-Path $stagingDirectory $validatedMetadata.code_file) -PathType Leaf)) {
            throw 'Generated Kaggle metadata validation failed.'
        }

        & $python -m kaggle quota
        $quotaExit = $LASTEXITCODE
        if ($quotaExit -ne 0) {
            throw "Kaggle quota command failed with exit code $quotaExit."
        }

        Write-Host 'KERNEL_REF=wt2018mask/rhombus-gpu-smoke'
        Write-Host 'STAGING_LOCATION=TEMP'
        Write-Host 'ACCELERATOR=NvidiaTeslaT4'
        Write-Host 'SCIENTIFIC_EVIDENCE=false'

        & $python -m kaggle kernels push -p $stagingDirectory --accelerator NvidiaTeslaT4
        $pushExit = $LASTEXITCODE

        if ($pushExit -eq 0) {
            Write-Host 'SUBMIT_OK=true'
            Write-Host 'KERNEL_REF=wt2018mask/rhombus-gpu-smoke'
            Write-Host 'RESULT'
            Write-Host 'PASS'
        } else {
            Write-Host 'SUBMIT_OK=false'
            Write-Host 'KERNEL_REF=wt2018mask/rhombus-gpu-smoke'
            Write-Host 'RESULT'
            Write-Host 'FAIL'
        }
        exit $pushExit
    } finally {
        if (Test-Path -LiteralPath $stagingDirectory) {
            Remove-Item -LiteralPath $stagingDirectory -Recurse -Force
        }
    }
}

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
