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

$extraCount = if ($null -eq $ExtraArguments) { 0 } else { @($ExtraArguments).Count }
$validCommand = $Command -in @('test', 'kaggle-list', 'kaggle-quota', 'kaggle-status', 'kaggle-logs', 'kaggle-inspect', 'kaggle-gpu-smoke-submit', 'kaggle-gpu-smoke-verify', 'kaggle-gpu-smoke-run', 'kaggle-mobile-ion-e2e', 'kaggle-mobile-ion-e2e-integrity-self-test')
$validArguments = switch ($Command) {
    'test' { -not [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-list' { [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-quota' { [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-status' { -not [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-logs' { -not [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-inspect' { -not [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-gpu-smoke-submit' { [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-gpu-smoke-verify' { [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-gpu-smoke-run' { [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-mobile-ion-e2e' { [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
    'kaggle-mobile-ion-e2e-integrity-self-test' { [string]::IsNullOrWhiteSpace($PytestTarget) -and $extraCount -eq 0 }
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
    Write-Host '       .\scripts\run.ps1 kaggle-gpu-smoke-run'
    Write-Host '       .\scripts\run.ps1 kaggle-mobile-ion-e2e'
    Write-Host '       .\scripts\run.ps1 kaggle-mobile-ion-e2e-integrity-self-test'
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

function Get-Sha256Text {
    param([string]$Text)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Get-FileSha256 {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Test-ReportWorkspaceIdentity {
    param(
        [object]$ReportWorkspace,
        [object]$SubmittedIdentity
    )
    if ($null -eq $ReportWorkspace -or $null -eq $SubmittedIdentity) { return $false }
    $scalarFields = @('schema_version', 'run_id', 'git_head', 'branch', 'tracked_dirty',
        'repository_workspace_manifest_sha256', 'tracked_delta_sha256', 'driver_template_sha256',
        'driver_path', 'explicitly_staged_input_manifest_sha256', 'runtime_manifest_sha256',
        'runtime_dataset_manifest_sha256', 'dataset_transport_manifest_sha256')
    foreach ($field in $scalarFields) {
        if ([string]$ReportWorkspace.$field -ne [string]$SubmittedIdentity.$field) { return $false }
    }
    if ((@($ReportWorkspace.repository_tracked_files) -join "`n") -ne (@($SubmittedIdentity.repository_tracked_files) -join "`n")) { return $false }
    if ((@($ReportWorkspace.runtime_files) -join "`n") -ne (@($SubmittedIdentity.runtime_files) -join "`n")) { return $false }
    if ((@($ReportWorkspace.runtime_dataset_files) -join "`n") -ne (@($SubmittedIdentity.runtime_dataset_files) -join "`n")) { return $false }
    if ((@($ReportWorkspace.dataset_transport_files) -join "`n") -ne (@($SubmittedIdentity.dataset_transport_files) -join "`n")) { return $false }
    if ((@($ReportWorkspace.status_porcelain) -join "`n") -ne (@($SubmittedIdentity.status_porcelain) -join "`n")) { return $false }
    if ((@($ReportWorkspace.explicitly_staged_untracked_inputs) -join "`n") -ne (@($SubmittedIdentity.explicitly_staged_untracked_inputs) -join "`n")) { return $false }
    $submittedProtected = @($SubmittedIdentity.protected_artifacts) | ForEach-Object { "$(($_.path))`t$(($_.sha256))" } | Sort-Object
    $reportedProtected = @($ReportWorkspace.protected_artifacts) | ForEach-Object { "$(($_.path))`t$(($_.sha256))" } | Sort-Object
    return (($submittedProtected -join "`n") -eq ($reportedProtected -join "`n"))
}

function Get-RepositoryRelativePath {
    param(
        [string]$RepositoryRoot,
        [string]$SourcePath
    )

    $resolvedRoot = [System.IO.Path]::GetFullPath($RepositoryRoot)
    $resolvedSource = [System.IO.Path]::GetFullPath($SourcePath)
    $rootPrefix = $resolvedRoot
    if (-not $rootPrefix.EndsWith([System.IO.Path]::DirectorySeparatorChar.ToString()) -and
        -not $rootPrefix.EndsWith([System.IO.Path]::AltDirectorySeparatorChar.ToString())) {
        $rootPrefix += [System.IO.Path]::DirectorySeparatorChar
    }

    if (-not $resolvedSource.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Source path is outside the repository root: $SourcePath"
    }

    return $resolvedSource.Substring($rootPrefix.Length).Replace('\', '/')
}

function Get-GitTrackedDeltaSha256 {
    $deltaPath = Join-Path ([System.IO.Path]::GetTempPath()) ("rhombus-tracked-delta-" + [guid]::NewGuid().ToString('N') + '.patch')
    try {
        $gitProcess = Start-Process -FilePath 'git' -ArgumentList @('diff', '--binary', 'HEAD', '--') -RedirectStandardOutput $deltaPath -NoNewWindow -Wait -PassThru
        if ($gitProcess.ExitCode -ne 0) { throw 'Unable to compute tracked Git diff.' }
        return Get-FileSha256 $deltaPath
    } finally {
        if (Test-Path -LiteralPath $deltaPath) { Remove-Item -LiteralPath $deltaPath -Force }
    }
}

function Get-MobileIonRuntimeSourceFiles {
    return @(
        'config.yaml',
        'data/batches/audit/g_ordered_expansion_v1.json',
        'rudeus/__init__.py',
        'rudeus/schema.py',
        'rudeus/empirical/__init__.py',
        'rudeus/empirical/liion.py',
        'rudeus/empirical/obelix.py',
        'rudeus/filters/__init__.py',
        'rudeus/filters/bvse.py',
        'rudeus/filters/f3_diffusive.py',
        'rudeus/filters/p0.py',
        'rudeus/generation/__init__.py',
        'rudeus/generation/audit.py',
        'rudeus/generation/generator.py',
        'rudeus/generation/mobile_ion_diagnostic.py',
        'rudeus/generation/scheduler.py'
    )
}

function Get-MobileIonObelixRuntimeFiles {
    $relative = @(
        'data/obelix/data/processed.csv',
        'data/obelix/data/train_idx.csv',
        'data/obelix/data/test_idx.csv',
        'data/obelix/data/misc/LiIonDatabase.csv'
    )
    $cifRoot = Join-Path $repoRoot 'data\obelix\data\randomized_cifs'
    if (Test-Path -LiteralPath $cifRoot -PathType Container) {
        $relative += @(Get-ChildItem -LiteralPath $cifRoot -File -Filter '*.cif' | ForEach-Object { Get-RepositoryRelativePath $repoRoot $_.FullName })
    }
    return @($relative | Sort-Object -Unique)
}

function Get-MobileIonCanonicalManifest {
    param([string[]]$ManifestLines)
    $ordered = [string[]]@($ManifestLines)
    [Array]::Sort($ordered, [System.StringComparer]::Ordinal)
    return (($ordered -join "`n") + "`n")
}

function Test-MobileIonDatasetStage {
    param(
        [string]$DatasetPath,
        [string[]]$ExpectedFiles,
        [hashtable]$ExpectedHashes,
        [string[]]$ExpectedObelixFiles,
        [object[]]$ExpectedProtectedArtifacts = @()
    )
    if (-not (Test-Path -LiteralPath $DatasetPath -PathType Container)) { return $false }
    $actual = @(Get-ChildItem -LiteralPath $DatasetPath -Recurse -File | Where-Object { $_.Name -ne 'dataset-metadata.json' } | ForEach-Object { Get-RepositoryRelativePath $DatasetPath $_.FullName })
    $expected = [string[]]@($ExpectedFiles)
    [Array]::Sort($actual, [System.StringComparer]::Ordinal)
    [Array]::Sort($expected, [System.StringComparer]::Ordinal)
    if (($actual -join "`n") -cne ($expected -join "`n")) { return $false }
    if ($expected -notcontains 'config.yaml' -or $expected -notcontains 'data/batches/audit/g_ordered_expansion_v1.json') { return $false }
    foreach ($relative in $expected) {
        $file = Join-Path $DatasetPath ($relative.Replace('/', '\'))
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { return $false }
        if ((Get-FileSha256 $file) -cne $ExpectedHashes[$relative]) { return $false }
        $parts = $relative.Split('/')
        if ($parts -contains '.git' -or $parts -contains '.venv' -or $parts -contains '.opencode') { return $false }
    }
    $actualObelix = @($expected | Where-Object { $_.StartsWith('data/obelix/', [System.StringComparison]::Ordinal) })
    $wantedObelix = [string[]]@($ExpectedObelixFiles)
    [Array]::Sort($actualObelix, [System.StringComparer]::Ordinal)
    [Array]::Sort($wantedObelix, [System.StringComparer]::Ordinal)
    if (($actualObelix -join "`n") -cne ($wantedObelix -join "`n")) { return $false }
    foreach ($record in $ExpectedProtectedArtifacts) {
        if ($expected -notcontains [string]$record.path -or $ExpectedHashes[[string]$record.path] -cne [string]$record.sha256) { return $false }
    }
    return $true
}

function New-MobileIonRuntimeDatasetStage {
    param(
        [string]$DatasetPath,
        [object[]]$ProtectedArtifacts = @(),
        [string]$ProtectedSourceRoot = $repoRoot
    )
    New-Item -ItemType Directory -Path $DatasetPath -Force | Out-Null
    $runtimeSourceFiles = @(Get-MobileIonRuntimeSourceFiles)
    $obelixFiles = @(Get-MobileIonObelixRuntimeFiles)
    $runtimeDatasetFiles = @($runtimeSourceFiles + $obelixFiles | Sort-Object -Unique)
    $protectedPaths = @($ProtectedArtifacts | ForEach-Object { [string]$_.path })
    $transportFiles = @($runtimeDatasetFiles + $protectedPaths | Sort-Object -Unique)
    $hashes = @{}
    $runtimeManifestLines = [System.Collections.Generic.List[string]]::new()
    foreach ($relative in $runtimeDatasetFiles) {
        $source = Join-Path $repoRoot ($relative.Replace('/', '\'))
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Required runtime dataset source is missing: $relative" }
        $destination = Join-Path $DatasetPath ($relative.Replace('/', '\'))
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
        $sourceHash = Get-FileSha256 $source
        if ((Get-FileSha256 $destination) -cne $sourceHash) { throw "Runtime dataset copy hash mismatch: $relative" }
        $hashes[$relative] = $sourceHash
        $runtimeManifestLines.Add("$relative`t$sourceHash")
    }
    $transportManifestLines = [System.Collections.Generic.List[string]]::new()
    foreach ($relative in $transportFiles) {
        $sourceRoot = if ($protectedPaths -contains $relative) { $ProtectedSourceRoot } else { $repoRoot }
        $source = Join-Path $sourceRoot ($relative.Replace('/', '\'))
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Required dataset transport source is missing: $relative" }
        $sourceHash = Get-FileSha256 $source
        if ($protectedPaths -contains $relative) {
            $record = $ProtectedArtifacts | Where-Object { [string]$_.path -ceq $relative } | Select-Object -First 1
            if ($sourceHash -cne [string]$record.sha256) { throw "Protected artifact source hash mismatch: $relative" }
        }
        $destination = Join-Path $DatasetPath ($relative.Replace('/', '\'))
        if (-not (Test-Path -LiteralPath $destination -PathType Leaf)) {
            New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
            Copy-Item -LiteralPath $source -Destination $destination -Force
        }
        if ((Get-FileSha256 $destination) -cne $sourceHash) { throw "Dataset transport copy hash mismatch: $relative" }
        $hashes[$relative] = $sourceHash
        $transportManifestLines.Add("$relative`t$sourceHash")
    }
    if (-not (Test-MobileIonDatasetStage $DatasetPath $transportFiles $hashes $obelixFiles $ProtectedArtifacts)) {
        throw 'Runtime dataset staged path set or content validation failed.'
    }
    $runtimeManifest = Get-MobileIonCanonicalManifest @($runtimeManifestLines)
    $transportManifest = Get-MobileIonCanonicalManifest @($transportManifestLines)
    $manifestHash = Get-Sha256Text $runtimeManifest
    $transportManifestHash = Get-Sha256Text $transportManifest
    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    $datasetMetadata = [ordered]@{
        id = 'wt2018mask/rhombus-mobile-ion-runtime'
        title = 'rhombus-mobile-ion-runtime'
        isPrivate = $true
        licenses = @(@{ name = 'other' })
    }
    $metadataPath = Join-Path $DatasetPath 'dataset-metadata.json'
    [System.IO.File]::WriteAllText($metadataPath, ($datasetMetadata | ConvertTo-Json -Depth 5), $utf8WithoutBom)
    $metadataBytes = [System.IO.File]::ReadAllBytes($metadataPath)
    if ($metadataBytes.Length -ge 3 -and $metadataBytes[0] -eq 0xEF -and $metadataBytes[1] -eq 0xBB -and $metadataBytes[2] -eq 0xBF) { throw 'Dataset metadata unexpectedly contains a UTF-8 BOM.' }
    $metadataCheck = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json
    if ($metadataCheck.id -cne 'wt2018mask/rhombus-mobile-ion-runtime' -or $metadataCheck.title -cne 'rhombus-mobile-ion-runtime' -or $metadataCheck.isPrivate -ne $true) { throw 'Runtime dataset metadata identity/privacy validation failed.' }
    return [pscustomobject]@{
        RuntimeSourceFiles = $runtimeSourceFiles
        ObelixFiles = $obelixFiles
        RuntimeDatasetFiles = $runtimeDatasetFiles
        TransportFiles = $transportFiles
        Hashes = $hashes
        ManifestLines = @($runtimeManifestLines)
        ManifestText = $runtimeManifest
        ManifestSha256 = $manifestHash
        TransportManifestLines = @($transportManifestLines)
        TransportManifestText = $transportManifest
        TransportManifestSha256 = $transportManifestHash
    }
}

function Resolve-MobileIonDatasetCreateResult {
    param(
        [int]$ExitCode,
        [string]$Output
    )

    $exactDuplicatePatterns = @(
        '(?i)\bDataset\s+["'']?wt2018mask/rhombus-mobile-ion-runtime["'']?\s+(?:already exists|already been created)\b',
        '(?i)\brequested title\s+["'']rhombus-mobile-ion-runtime["'']\s+is already in use by a dataset\b',
        '(?i)\bduplicate (?:dataset|slug)\b[^\r\n]*\brhombus-mobile-ion-runtime\b',
        '(?i)\bslug\s+["'']?rhombus-mobile-ion-runtime["'']?\s+(?:is )?(?:already in use|already exists)\b',
        '(?i)\b409\b[^\r\n]*\bconflict\b[^\r\n]*(?:wt2018mask/rhombus-mobile-ion-runtime|rhombus-mobile-ion-runtime)'
    )
    if (@($exactDuplicatePatterns | Where-Object { $Output -match $_ }).Count -gt 0) {
        return 'ALREADY_EXISTS'
    }
    if ($Output -match '(?im)^\s*(?:Dataset creation error:|Error creating dataset:|Dataset creation failed\b|Validation error:|Invalid dataset\b)|\b(?:401|403) Client Error\b|\bHTTP \d{3} Client Error\b|\bTraceback \(most recent call last\)') {
        return 'ERROR'
    }
    if ($ExitCode -eq 0 -and $Output -match '(?i)\bYour private Dataset is being created\b') {
        return 'CREATE_OK'
    }
    return 'ERROR'
}

function Resolve-MobileIonDatasetVersionResult {
    param(
        [int]$ExitCode,
        [string]$Output
    )
    if ($Output -match '(?im)^\s*(?:Dataset version error:|Error creating dataset version:|Dataset version failed\b|Validation error:|Invalid dataset\b)|\b(?:401|403) Client Error\b|\bHTTP \d{3} Client Error\b|\bTraceback \(most recent call last\)') {
        return 'ERROR'
    }
    if ($ExitCode -eq 0 -and $Output -match '(?i)\bDataset version (?:is being created|created successfully|creation successful)\b') {
        return 'VERSION_OK'
    }
    return 'ERROR'
}

function Get-MobileIonDatasetAction {
    param([string]$CreateResult)
    switch ($CreateResult) {
        'CREATE_OK' { return 'CREATE' }
        'ALREADY_EXISTS' { return 'VERSION' }
        default { return 'ERROR' }
    }
}

function Test-MobileIonDatasetUploadSuccess {
    param([string]$UploadResult)
    return $UploadResult -in @('CREATE_OK', 'VERSION_OK')
}

function Resolve-MobileIonDatasetReadinessState {
    param(
        [int]$ExitCode,
        [string]$Output
    )
    if ($ExitCode -ne 0) { return 'QUERY_FAILURE' }
    if ([string]::IsNullOrWhiteSpace($Output)) { return 'UNKNOWN' }
    if ($Output -match '(?i)\b(?:error|failed|failure)\b') { return 'ERROR' }
    $stateMatches = [regex]::Matches($Output, '(?im)^\s*(?:(?:dataset\s+)?status\s*[:=]\s*)?(?:DatasetStatus\.)?(ready|pending|running|creating|updating|queued|initializing|processing|uploading|waiting|submitted|in\s+progress)\s*[.!]?\s*$')
    if ($stateMatches.Count -ne 1) { return 'UNKNOWN' }
    $stateMatch = $stateMatches[0]
    if ($stateMatch.Groups[1].Value -match '(?i)^ready$') { return 'READY' }
    return 'PENDING'
}

function Get-MobileIonDatasetReadinessOutcome {
    param(
        [string]$State,
        [int]$Attempt,
        [int]$MaxAttempts
    )
    if ($State -eq 'READY') {
        if ($Attempt -le $MaxAttempts) { return 'READY' }
        return 'TIMEOUT'
    }
    if ($State -eq 'PENDING' -and $Attempt -ge $MaxAttempts) { return 'TIMEOUT' }
    return $State
}

function Test-MobileIonKernelSubmissionAllowed {
    param([string]$ReadinessOutcome)
    return $ReadinessOutcome -eq 'READY'
}

function Wait-MobileIonDatasetReady {
    param(
        [string]$DatasetRef,
        [int]$MaxAttempts = 30,
        [int]$IntervalSeconds = 5
    )
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        Write-Host "DATASET_READY_POLL_ATTEMPT=$attempt"
        $statusOutput = @(& $python -m kaggle datasets status $DatasetRef 2>&1)
        $statusExitCode = [int]$LASTEXITCODE
        $statusText = ($statusOutput | ForEach-Object { $_.ToString() }) -join "`n"
        $statusOutput | ForEach-Object { Write-Host $_ }
        $state = Resolve-MobileIonDatasetReadinessState -ExitCode $statusExitCode -Output $statusText
        Write-Host "DATASET_READY_STATE=$state"
        $outcome = Get-MobileIonDatasetReadinessOutcome -State $state -Attempt $attempt -MaxAttempts $MaxAttempts
        if ($outcome -ne 'PENDING') {
            return [pscustomobject]@{ State = $outcome; Attempts = $attempt }
        }
        if ($attempt -lt $MaxAttempts) { Start-Sleep -Seconds $IntervalSeconds }
    }
    return [pscustomobject]@{ State = 'TIMEOUT'; Attempts = $MaxAttempts }
}

function Invoke-MobileIonDatasetUpload {
    param([string]$DatasetPath)
    $datasetRef = 'wt2018mask/rhombus-mobile-ion-runtime'
    # Omitting Kaggle's public flag preserves its private-by-default behavior.
    $createOutput = @(& $python -m kaggle datasets create -p $DatasetPath -r zip 2>&1)
    $createExitCode = [int]$LASTEXITCODE
    Write-Host "DATASET_CREATE_EXIT_CODE=$createExitCode"
    $createText = ($createOutput | ForEach-Object { $_.ToString() }) -join "`n"
    $createOutput | ForEach-Object { Write-Host $_ }
    $createResult = Resolve-MobileIonDatasetCreateResult -ExitCode $createExitCode -Output $createText
    $action = Get-MobileIonDatasetAction -CreateResult $createResult
    $uploadResult = $createResult
    $versionExitCode = $null

    if ($action -eq 'VERSION') {
        $versionOutput = @(& $python -m kaggle datasets version -p $DatasetPath -m 'Refresh Rhombus CPU runtime snapshot' -r zip 2>&1)
        $versionExitCode = [int]$LASTEXITCODE
        Write-Host "DATASET_VERSION_EXIT_CODE=$versionExitCode"
        $versionText = ($versionOutput | ForEach-Object { $_.ToString() }) -join "`n"
        $versionOutput | ForEach-Object { Write-Host $_ }
        $uploadResult = Resolve-MobileIonDatasetVersionResult -ExitCode $versionExitCode -Output $versionText
    } elseif ($action -eq 'ERROR') {
        throw "Kaggle runtime dataset create failed closed (exit $createExitCode): $createText"
    }
    if (-not (Test-MobileIonDatasetUploadSuccess -UploadResult $uploadResult)) {
        $versionDetail = if ($null -eq $versionExitCode) { 'not attempted' } else { [string]$versionExitCode }
        throw "Kaggle runtime dataset upload was not confirmed successful (create exit $createExitCode, version exit $versionDetail): $versionText"
    }
    $action = if ($uploadResult -eq 'CREATE_OK') { 'CREATE' } else { 'VERSION' }
    Write-Host "RUNTIME_DATASET_REF=$datasetRef"
    Write-Host "DATASET_ACTION=$action"
}

function Invoke-MobileIonE2E {
    $kernelRef = 'wt2018mask/rhombus-mobile-ion-e2e'
    $driverRelative = 'scripts/kaggle/mobile_ion_displace_e2e.py'
    $stagingDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("rhombus-mobile-ion-e2e-" + [guid]::NewGuid().ToString('N'))
    $datasetStagingDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("rhombus-mobile-ion-runtime-" + [guid]::NewGuid().ToString('N'))
    $resultDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("rhombus-mobile-ion-e2e-result-" + [guid]::NewGuid().ToString('N'))
    $script:mobileIonExit = 20
    try {
        $helpOutput = @(& $python -m kaggle kernels push --help 2>&1)
        if ($LASTEXITCODE -ne 0) { throw 'Kaggle CLI kernels push help is unavailable.' }
        $outputHelp = @(& $python -m kaggle kernels output --help 2>&1)
        if ($LASTEXITCODE -ne 0) { throw 'Kaggle CLI kernels output help is unavailable.' }

        New-Item -ItemType Directory -Path $stagingDirectory -Force | Out-Null
        New-Item -ItemType Directory -Path $resultDirectory -Force | Out-Null
        $tracked = @(git ls-files)
        if ($LASTEXITCODE -ne 0) { throw 'Unable to enumerate tracked files.' }
        $repositoryManifestLines = [System.Collections.Generic.List[string]]::new()
        foreach ($relative in $tracked) {
            $normalized = $relative.Replace('\', '/')
            $source = Join-Path $repoRoot ($relative.Replace('/', '\'))
            if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Tracked file is missing: $relative" }
            $workHash = Get-FileSha256 $source
            $repositoryManifestLines.Add("$normalized`t$workHash")
        }
        $protected = @($tracked | Where-Object { $_ -eq 'data/batches/audit/g_ordered_expansion_v1.json' -or $_ -match '^data/batches/audit/(p2|p25|p3)' } | Sort-Object -Unique)
        $protectedRecords = @()
        foreach ($relative in $protected) {
            $path = Join-Path $repoRoot $relative.Replace('/', '\')
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Protected artifact is missing: $relative" }
            $basis = if ($relative -eq 'data/batches/audit/g_ordered_expansion_v1.json') { 'required immutable source input' } else { 'conservative E2E protected audit set; filename is not authoritative frozen evidence' }
            $protectedRecords += [ordered]@{ path = $relative; sha256 = Get-FileSha256 $path; protection_basis = $basis }
        }
        Write-Host "PROTECTED_ARTIFACT_COUNT=$($protectedRecords.Count)"
        $datasetInfo = New-MobileIonRuntimeDatasetStage -DatasetPath $datasetStagingDirectory -ProtectedArtifacts $protectedRecords
        $runtimeSourceFiles = @($datasetInfo.RuntimeSourceFiles)
        $obelixRuntimeRelative = @($datasetInfo.ObelixFiles)
        $additionalInputLines = [System.Collections.Generic.List[string]]::new()
        foreach ($relative in @($obelixRuntimeRelative | Sort-Object -Unique)) {
            $source = Join-Path $repoRoot ($relative.Replace('/', '\'))
            $additionalInputLines.Add("$relative`t$(Get-FileSha256 $source)")
        }
        $driverSource = Join-Path $repoRoot $driverRelative.Replace('/', '\')
        $driverDestination = Join-Path $stagingDirectory 'mobile_ion_displace_e2e.py'
        New-Item -ItemType Directory -Path (Split-Path -Parent $driverDestination) -Force | Out-Null
        $driverSourceBytes = [System.IO.File]::ReadAllBytes($driverSource)
        $driverSourceText = (New-Object System.Text.UTF8Encoding($false, $true)).GetString($driverSourceBytes)
        $placeholder = '__RHOMBUS_WORKSPACE_IDENTITY_B64__'
        if ([regex]::Matches($driverSourceText, [regex]::Escape($placeholder)).Count -ne 1) { throw 'Workspace identity placeholder must occur exactly once in source driver.' }
        $driverTemplateSha256 = Get-FileSha256 $driverSource
        $runtimeManifestLines = [System.Collections.Generic.List[string]]::new()
        foreach ($relative in $runtimeSourceFiles) {
            $source = Join-Path $repoRoot ($relative.Replace('/', '\'))
            if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Required runtime file is missing: $relative" }
            $runtimeManifestLines.Add("$relative`t$(Get-FileSha256 $source)")
        }
        $runtimeManifestAllLines = @(("mobile_ion_displace_e2e.py" + [char]9 + $driverTemplateSha256)) + @($runtimeManifestLines) + @($additionalInputLines)
        $runtimeManifestText = Get-MobileIonCanonicalManifest -ManifestLines $runtimeManifestAllLines
        $explicitInputManifestText = Get-MobileIonCanonicalManifest -ManifestLines @($additionalInputLines)
        $statusLines = @(git status --porcelain)
        & git diff --quiet HEAD --
        $trackedDirty = ($LASTEXITCODE -ne 0)
        $branch = (git branch --show-current).Trim()
        $identity = [ordered]@{
            schema_version = 'rhombus-workspace-identity-v1'
            run_id = [guid]::NewGuid().ToString('D')
            git_head = (git rev-parse HEAD).Trim()
            branch = $branch
            tracked_dirty = $trackedDirty
            status_porcelain = @($statusLines)
            repository_tracked_files = @($repositoryManifestLines | Sort-Object | ForEach-Object { ($_ -split "`t", 2)[0] })
            repository_workspace_manifest_sha256 = Get-Sha256Text ((($repositoryManifestLines | Sort-Object) -join "`n") + "`n")
            tracked_delta_sha256 = Get-GitTrackedDeltaSha256
            driver_template_sha256 = $driverTemplateSha256
            driver_path = 'mobile_ion_displace_e2e.py'
            explicitly_staged_untracked_inputs = @('data/obelix')
            explicitly_staged_input_manifest_sha256 = Get-Sha256Text $explicitInputManifestText
            runtime_files = @('mobile_ion_displace_e2e.py') + @($runtimeSourceFiles) + @($additionalInputLines | Sort-Object | ForEach-Object { ($_ -split "`t", 2)[0] })
            runtime_dataset_files = @($datasetInfo.RuntimeDatasetFiles)
            runtime_dataset_manifest_sha256 = $datasetInfo.ManifestSha256
            dataset_transport_files = @($datasetInfo.TransportFiles)
            dataset_transport_manifest_sha256 = $datasetInfo.TransportManifestSha256
            runtime_manifest_sha256 = Get-Sha256Text $runtimeManifestText
            protected_artifacts = $protectedRecords
        }
        $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
        $identityJson = $identity | ConvertTo-Json -Depth 12 -Compress
        $identityBytes = $utf8WithoutBom.GetBytes($identityJson)
        $identityB64 = [Convert]::ToBase64String($identityBytes)
        $stagedDriverText = $driverSourceText.Replace($placeholder, $identityB64)
        if ($stagedDriverText.Contains($placeholder)) { throw 'Workspace identity placeholder remains in staged executable.' }
        [System.IO.File]::WriteAllText($driverDestination, $stagedDriverText, $utf8WithoutBom)
        $decodedIdentity = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($identityB64))
        if ($decodedIdentity -cne $identityJson) { throw 'Embedded identity round-trip bytes differ from submitted identity.' }
        $decodedObject = $decodedIdentity | ConvertFrom-Json
        if ((($decodedObject | ConvertTo-Json -Depth 12 -Compress)) -cne $identityJson) { throw 'Embedded identity round-trip fields differ from submitted identity.' }
        $metadata = [ordered]@{
            id = $kernelRef; title = 'rhombus-mobile-ion-e2e'; code_file = 'mobile_ion_displace_e2e.py'
            language = 'python'; kernel_type = 'script'; is_private = $true
            enable_gpu = $false; enable_internet = $true; dataset_sources = @('wt2018mask/rhombus-mobile-ion-runtime')
            competition_sources = @(); kernel_sources = @(); model_sources = @()
        }
        $metadataPath = Join-Path $stagingDirectory 'kernel-metadata.json'
        [System.IO.File]::WriteAllText($metadataPath, ($metadata | ConvertTo-Json -Depth 5), $utf8WithoutBom)
        $metadataBytes = [System.IO.File]::ReadAllBytes($metadataPath)
        if ($metadataBytes.Length -ge 3 -and $metadataBytes[0] -eq 0xEF -and $metadataBytes[1] -eq 0xBB -and $metadataBytes[2] -eq 0xBF) { throw 'Generated Kaggle metadata contains an unexpected UTF-8 BOM.' }

        Write-Host "KERNEL_REF=$kernelRef"
        Write-Host 'ACCELERATOR=CPU'
        Write-Host 'SCIENTIFIC_EVIDENCE=OBSERVATIONAL_DIAGNOSTIC'
        Write-Host "PROTECTED_ARTIFACT_COUNT=$($protectedRecords.Count)"
        Invoke-MobileIonDatasetUpload $datasetStagingDirectory
        $datasetReadiness = Wait-MobileIonDatasetReady -DatasetRef 'wt2018mask/rhombus-mobile-ion-runtime' -MaxAttempts 30 -IntervalSeconds 5
        if (-not (Test-MobileIonKernelSubmissionAllowed -ReadinessOutcome $datasetReadiness.State)) {
            $readinessClass = switch ($datasetReadiness.State) {
                'QUERY_FAILURE' { 'ORCHESTRATION_QUERY_FAILURE' }
                'UNKNOWN' { 'ORCHESTRATION_PARSE_FAILURE' }
                'TIMEOUT' { 'ORCHESTRATION_TIMEOUT' }
                default { 'INFRA_FAILURE' }
            }
            Write-Host "E2E_CLASS=$readinessClass"
            Write-Host "DATASET_READY_RESULT=$($datasetReadiness.State)"
            Write-Host 'REPORT_OK=false'
            Write-Host 'ARTIFACT_HASH_OK=false'
            Write-Host 'SCIENTIFIC_EVIDENCE=OBSERVATIONAL_DIAGNOSTIC'
            Write-Host "LOCAL_RESULT_DIR=$resultDirectory"
            Write-Host 'LOCAL_REPORT_PATH='
            Write-Host 'LOCAL_ARTIFACT_PATH='
            Write-Host 'RESULT'
            switch ($datasetReadiness.State) {
                'QUERY_FAILURE' { Write-Host 'QUERY_FAILURE'; $script:mobileIonExit = 11 }
                'UNKNOWN' { Write-Host 'PARSE_FAILURE'; $script:mobileIonExit = 13 }
                'TIMEOUT' { Write-Host 'TIMEOUT'; $script:mobileIonExit = 12 }
                default { Write-Host 'INFRA_FAILURE'; $script:mobileIonExit = 20 }
            }
            exit $script:mobileIonExit
        }
        & $python -m kaggle kernels push -p $stagingDirectory
        if ($LASTEXITCODE -ne 0) { throw "Kaggle kernel submission failed with exit code $LASTEXITCODE." }
        $terminalState = $null
        for ($attempt = 1; $attempt -le 30; $attempt++) {
            Write-Host "POLL_ATTEMPT=$attempt"
            $statusOutput = @(& $python -m kaggle kernels status $kernelRef 2>&1)
            if ($LASTEXITCODE -ne 0) {
                Write-Host 'E2E_CLASS=ORCHESTRATION_QUERY_FAILURE'; Write-Host 'REMOTE_STATE=UNKNOWN'; Write-Host 'REPORT_OK=false'; Write-Host 'ARTIFACT_HASH_OK=false'; Write-Host 'SCIENTIFIC_EVIDENCE=OBSERVATIONAL_DIAGNOSTIC'; Write-Host "LOCAL_RESULT_DIR=$resultDirectory"; Write-Host 'LOCAL_REPORT_PATH='; Write-Host 'LOCAL_ARTIFACT_PATH='; Write-Host 'RESULT'; Write-Host 'QUERY_FAILURE'; $script:mobileIonExit = 11; exit $script:mobileIonExit
            }
            $statusText = ($statusOutput | ForEach-Object { $_.ToString() }) -join "`n"
            $stateMatch = [regex]::Match($statusText, '(?im)^[^\r\n]*KernelWorkerStatus\.([A-Za-z0-9_]+)[^\r\n]*$')
            if (-not $stateMatch.Success) {
                Write-Host 'E2E_CLASS=ORCHESTRATION_PARSE_FAILURE'; Write-Host 'REMOTE_STATE=UNKNOWN'; Write-Host 'REPORT_OK=false'; Write-Host 'ARTIFACT_HASH_OK=false'; Write-Host 'SCIENTIFIC_EVIDENCE=OBSERVATIONAL_DIAGNOSTIC'; Write-Host "LOCAL_RESULT_DIR=$resultDirectory"; Write-Host 'LOCAL_REPORT_PATH='; Write-Host 'LOCAL_ARTIFACT_PATH='; Write-Host 'RESULT'; Write-Host 'PARSE_FAILURE'; $script:mobileIonExit = 13; exit $script:mobileIonExit
            }
            $remoteState = $stateMatch.Groups[1].Value
            Write-Host "REMOTE_STATE=$remoteState"
            if ($remoteState -ceq 'COMPLETE' -or $remoteState -ceq 'ERROR') { $terminalState = $remoteState; break }
            if ($attempt -lt 30) { Start-Sleep -Seconds 10 }
        }
        if ($null -eq $terminalState) {
            Write-Host 'E2E_CLASS=ORCHESTRATION_TIMEOUT'
            Write-Host 'REMOTE_STATE=RUNNING'
            Write-Host 'REPORT_OK=false'
            Write-Host 'ARTIFACT_HASH_OK=false'
            Write-Host 'SCIENTIFIC_EVIDENCE=OBSERVATIONAL_DIAGNOSTIC'
            Write-Host "LOCAL_RESULT_DIR=$resultDirectory"
            Write-Host 'LOCAL_REPORT_PATH='
            Write-Host 'LOCAL_ARTIFACT_PATH='
            Write-Host 'RESULT'
            Write-Host 'TIMEOUT'
            $script:mobileIonExit = 12
            exit $script:mobileIonExit
        }
        $logs = @(& $python -m kaggle kernels logs $kernelRef 2>&1)
        $logsExit = $LASTEXITCODE
        Write-Host "LOGS_OK=$($logsExit -eq 0)"
        $logs | ForEach-Object { Write-Host $_ }
        & $python -m kaggle kernels output $kernelRef -p $resultDirectory
        $outputExit = $LASTEXITCODE
        if ($outputExit -ne 0) { throw 'Kaggle output download failed.' }
        $reportPath = Get-ChildItem -LiteralPath $resultDirectory -Recurse -File -Filter 'mobile_ion_displace_e2e_report.json' | Select-Object -First 1
        $artifactPath = Get-ChildItem -LiteralPath $resultDirectory -Recurse -File -Filter 'g_candidate_supply_v2_mobile_ion_displace_diagnostic_panel.json' | Select-Object -First 1
        if ($null -eq $reportPath) { throw 'Downloaded Kaggle output is missing the report.' }
        $report = Get-Content -LiteralPath $reportPath.FullName -Raw | ConvertFrom-Json
        $classificationOk = [string]$report.final_classification -in @('PASS', 'SCIENTIFIC_VALIDATION_FAIL', 'INFRA_FAILURE')
        $schemaOk = [string]$report.schema_version -eq 'mobile-ion-displace-e2e-report-v1'
        $runIdOk = [string]$report.run_id -eq [string]$identity.run_id
        $workspaceOk = Test-ReportWorkspaceIdentity $report.workspace $identity
        $reportOk = $classificationOk -and $schemaOk -and $runIdOk -and $workspaceOk
        $artifactHashOk = $false
        if ($null -ne $artifactPath -and $report.artifact.sha256) { $artifactHashOk = (Get-FileSha256 $artifactPath.FullName) -eq [string]$report.artifact.sha256 }
        Write-Host "E2E_CLASS=$($report.final_classification)"
        Write-Host "REMOTE_STATE=$terminalState"
        Write-Host "REPORT_OK=$($reportOk.ToString().ToLowerInvariant())"
        Write-Host "ARTIFACT_HASH_OK=$($artifactHashOk.ToString().ToLowerInvariant())"
        Write-Host 'SCIENTIFIC_EVIDENCE=OBSERVATIONAL_DIAGNOSTIC'
        Write-Host "LOCAL_RESULT_DIR=$resultDirectory"
        Write-Host "LOCAL_REPORT_PATH=$($reportPath.FullName)"
        Write-Host "LOCAL_ARTIFACT_PATH=$(if ($null -ne $artifactPath) { $artifactPath.FullName } else { '' })"
        Write-Host 'RESULT'
        if ($report.final_classification -eq 'PASS' -and $reportOk -and $artifactHashOk -and $terminalState -ceq 'COMPLETE') { Write-Host 'PASS'; $script:mobileIonExit = 0 }
        elseif ($report.final_classification -eq 'SCIENTIFIC_VALIDATION_FAIL' -and $reportOk) { Write-Host 'SCIENTIFIC_VALIDATION_FAIL'; $script:mobileIonExit = 30 }
        else { Write-Host 'INFRA_FAILURE'; $script:mobileIonExit = 20 }
    } catch {
        Write-Host "E2E_ERROR=$($_.Exception.Message)"
        Write-Host 'E2E_CLASS=INFRA_FAILURE'
        Write-Host 'REMOTE_STATE=ERROR'
        Write-Host 'REPORT_OK=false'
        Write-Host 'ARTIFACT_HASH_OK=false'
        Write-Host 'SCIENTIFIC_EVIDENCE=OBSERVATIONAL_DIAGNOSTIC'
        Write-Host "LOCAL_RESULT_DIR=$resultDirectory"
        Write-Host 'LOCAL_REPORT_PATH='
        Write-Host 'LOCAL_ARTIFACT_PATH='
        Write-Host 'RESULT'
        Write-Host 'INFRA_FAILURE'
        $script:mobileIonExit = 20
    } finally {
        if (Test-Path -LiteralPath $stagingDirectory) { Remove-Item -LiteralPath $stagingDirectory -Recurse -Force }
        if (Test-Path -LiteralPath $datasetStagingDirectory) { Remove-Item -LiteralPath $datasetStagingDirectory -Recurse -Force }
        Write-Host 'LOCAL_GIT_STATUS'
        git status --short
        Write-Host "LOCAL_RESULT_DIR=$resultDirectory"
    }
    exit $script:mobileIonExit
}

function Invoke-MobileIonIntegritySelfTest {
    & $python scripts/kaggle/mobile_ion_displace_e2e.py --integrity-self-test
    if ($LASTEXITCODE -ne 0) { Write-Result $false }
    Invoke-MobileIonDatasetStagingSelfTest
    $duplicateFixture = 'Dataset creation error: The requested title "rhombus-mobile-ion-runtime" is already in use by a dataset. Please choose another title.'
    $successCreateFixture = 'Your private Dataset is being created.'
    $successVersionFixture = 'Dataset version is being created.'
    $createCases = @(
        @{ Name = 'success'; ExitCode = 0; Output = $successCreateFixture; Expected = 'CREATE_OK' },
        @{ Name = 'exact observed duplicate zero'; ExitCode = 0; Output = $duplicateFixture; Expected = 'ALREADY_EXISTS' },
        @{ Name = 'exact observed duplicate nonzero'; ExitCode = 1; Output = $duplicateFixture; Expected = 'ALREADY_EXISTS' },
        @{ Name = 'generic create error zero'; ExitCode = 0; Output = 'Dataset creation error: validation rejected'; Expected = 'ERROR' },
        @{ Name = '403'; ExitCode = 1; Output = '403 Client Error: Forbidden for wt2018mask/rhombus-mobile-ion-runtime'; Expected = 'ERROR' },
        @{ Name = '401'; ExitCode = 1; Output = '401 Client Error: Unauthorized for wt2018mask/rhombus-mobile-ion-runtime'; Expected = 'ERROR' },
        @{ Name = 'validation'; ExitCode = 1; Output = 'Invalid dataset metadata for wt2018mask/rhombus-mobile-ion-runtime'; Expected = 'ERROR' },
        @{ Name = 'arbitrary failure'; ExitCode = 7; Output = 'unexpected CLI failure'; Expected = 'ERROR' },
        @{ Name = 'unrelated already in use'; ExitCode = 1; Output = 'Credential is already in use for another account'; Expected = 'ERROR' },
        @{ Name = 'ambiguous zero'; ExitCode = 0; Output = 'Upload completed'; Expected = 'ERROR' },
        @{ Name = 'normal output nonzero'; ExitCode = 3; Output = $successCreateFixture; Expected = 'ERROR' }
    )
    foreach ($case in $createCases) {
        $actual = Resolve-MobileIonDatasetCreateResult -ExitCode $case.ExitCode -Output $case.Output
        if ($actual -ne $case.Expected) { Write-Result $false }
    }
    $actionCases = @(
        @{ CreateResult = 'ALREADY_EXISTS'; ExpectedAction = 'VERSION' },
        @{ CreateResult = 'CREATE_OK'; ExpectedAction = 'CREATE' },
        @{ CreateResult = 'ERROR'; ExpectedAction = 'ERROR' }
    )
    foreach ($case in $actionCases) {
        $actualAction = Get-MobileIonDatasetAction -CreateResult $case.CreateResult
        if ($actualAction -ne $case.ExpectedAction) { Write-Result $false }
    }
    foreach ($errorFirstCase in @(
        @{ ExitCode = 0; Output = $duplicateFixture; Expected = 'ALREADY_EXISTS' },
        @{ ExitCode = 0; Output = 'Dataset creation error: generic failure'; Expected = 'ERROR' },
        @{ ExitCode = 9; Output = $successCreateFixture; Expected = 'ERROR' }
    )) {
        if ((Resolve-MobileIonDatasetCreateResult -ExitCode $errorFirstCase.ExitCode -Output $errorFirstCase.Output) -ne $errorFirstCase.Expected) { Write-Result $false }
    }
    if ((Resolve-MobileIonDatasetVersionResult -ExitCode 0 -Output $successVersionFixture) -ne 'VERSION_OK') { Write-Result $false }
    if ((Resolve-MobileIonDatasetVersionResult -ExitCode 0 -Output 'Dataset version error: upload rejected') -ne 'ERROR') { Write-Result $false }
    if ((Resolve-MobileIonDatasetVersionResult -ExitCode 1 -Output $successVersionFixture) -ne 'ERROR') { Write-Result $false }
    if ((Get-MobileIonDatasetAction -CreateResult (Resolve-MobileIonDatasetCreateResult -ExitCode 0 -Output $duplicateFixture)) -ne 'VERSION') { Write-Result $false }
    if ((Get-MobileIonDatasetAction -CreateResult (Resolve-MobileIonDatasetCreateResult -ExitCode 0 -Output 'Dataset creation error: no conflict')) -ne 'ERROR') { Write-Result $false }
    if (-not (Test-MobileIonDatasetUploadSuccess -UploadResult 'CREATE_OK')) { Write-Result $false }
    if (-not (Test-MobileIonDatasetUploadSuccess -UploadResult 'VERSION_OK')) { Write-Result $false }
    foreach ($errorResult in @('ERROR', 'ALREADY_EXISTS', '')) {
        if (Test-MobileIonDatasetUploadSuccess -UploadResult $errorResult) { Write-Result $false }
    }
    Write-Host 'DATASET_CREATE_CONFLICT_MAPPING=PASS'
    Write-Host 'DATASET_CREATE_ACTION_FALLBACK=PASS'
    Write-Host 'DATASET_CREATE_VERSION_SUBMISSION_GATE=PASS'
    $readinessCases = @(
        @{ ExitCode = 0; Output = 'ready'; Expected = 'READY' },
        @{ ExitCode = 0; Output = ' READY '; Expected = 'READY' },
        @{ ExitCode = 0; Output = 'Ready'; Expected = 'READY' },
        @{ ExitCode = 0; Output = 'DatasetStatus.pending'; Expected = 'PENDING' },
        @{ ExitCode = 0; Output = 'running'; Expected = 'PENDING' },
        @{ ExitCode = 0; Output = 'creating'; Expected = 'PENDING' },
        @{ ExitCode = 0; Output = 'updating'; Expected = 'PENDING' },
        @{ ExitCode = 0; Output = 'queued'; Expected = 'PENDING' },
        @{ ExitCode = 0; Output = 'Dataset status: error'; Expected = 'ERROR' },
        @{ ExitCode = 0; Output = 'processing failed'; Expected = 'ERROR' },
        @{ ExitCode = 0; Output = 'unexpected response'; Expected = 'UNKNOWN' },
        @{ ExitCode = 0; Output = "pending`nready"; Expected = 'UNKNOWN' },
        @{ ExitCode = 0; Output = ''; Expected = 'UNKNOWN' },
        @{ ExitCode = 1; Output = 'ready'; Expected = 'QUERY_FAILURE' }
    )
    foreach ($case in $readinessCases) {
        if ((Resolve-MobileIonDatasetReadinessState -ExitCode $case.ExitCode -Output $case.Output) -ne $case.Expected) { Write-Result $false }
    }
    if (-not (Test-MobileIonKernelSubmissionAllowed -ReadinessOutcome 'READY')) { Write-Result $false }
    foreach ($notReady in @('PENDING', 'ERROR', 'UNKNOWN', 'QUERY_FAILURE', 'TIMEOUT')) {
        if (Test-MobileIonKernelSubmissionAllowed -ReadinessOutcome $notReady) { Write-Result $false }
    }
    $timeoutOutcome = Get-MobileIonDatasetReadinessOutcome -State 'PENDING' -Attempt 30 -MaxAttempts 30
    if ($timeoutOutcome -ne 'TIMEOUT' -or (Test-MobileIonKernelSubmissionAllowed -ReadinessOutcome $timeoutOutcome)) { Write-Result $false }
    if ((Get-MobileIonDatasetReadinessOutcome -State 'READY' -Attempt 31 -MaxAttempts 30) -ne 'TIMEOUT') { Write-Result $false }
    Write-Host 'DATASET_READINESS_STATE_MAPPING=PASS'
    Write-Host 'DATASET_READINESS_SUBMISSION_GATE=PASS'
    Write-Host 'DATASET_READINESS_TIMEOUT_GATE=PASS'
    $identity = [pscustomobject]@{
        schema_version = 'self-test'; run_id = 'current-run'; git_head = 'head'; branch = 'branch'; tracked_dirty = $false
        repository_workspace_manifest_sha256 = 'repo'; tracked_delta_sha256 = 'delta'; driver_template_sha256 = 'driver'
        driver_path = 'mobile_ion_displace_e2e.py'; explicitly_staged_input_manifest_sha256 = 'obelix'; runtime_manifest_sha256 = 'runtime'
        runtime_dataset_manifest_sha256 = 'dataset'; runtime_dataset_files = @('config.yaml')
        dataset_transport_manifest_sha256 = 'transport'; dataset_transport_files = @('config.yaml')
        repository_tracked_files = @('.github/workflows/cron.yml', 'runtime.py'); runtime_files = @('runtime.py')
        status_porcelain = @(); explicitly_staged_untracked_inputs = @('data/obelix'); protected_artifacts = @()
    }
    if (-not (Test-ReportWorkspaceIdentity $identity $identity)) { Write-Result $false }
    $stale = $identity | Select-Object *
    $stale.run_id = 'stale-run'
    if (Test-ReportWorkspaceIdentity $stale $identity) { Write-Result $false }
    Write-Host 'REPORT_IDENTITY_ROUND_TRIP=PASS'
    Write-Host 'STALE_REPORT_REJECTED=PASS'
    Write-Result $true
}

function Invoke-MobileIonDatasetStagingSelfTest {
    $testDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("rhombus-mobile-ion-dataset-self-test-" + [guid]::NewGuid().ToString('N'))
    try {
        $datasetPath = Join-Path $testDirectory 'dataset'
        $protectedSourceRoot = Join-Path $testDirectory 'synthetic-source'
        $protectedRelative = 'data/batches/audit/synthetic-protected-self-test.json'
        $protectedSource = Join-Path $protectedSourceRoot ($protectedRelative.Replace('/', '\'))
        New-Item -ItemType Directory -Path (Split-Path -Parent $protectedSource) -Force | Out-Null
        [System.IO.File]::WriteAllText($protectedSource, 'synthetic protected fixture', (New-Object System.Text.UTF8Encoding($false)))
        $protectedRecord = [ordered]@{ path = $protectedRelative; sha256 = Get-FileSha256 $protectedSource; protection_basis = 'synthetic self-test only' }
        $runtimeLines = [System.Collections.Generic.List[string]]::new()
        $runtimePaths = @(Get-MobileIonRuntimeSourceFiles) + @(Get-MobileIonObelixRuntimeFiles)
        foreach ($relative in @($runtimePaths | Sort-Object -Unique)) {
            $runtimeLines.Add("$relative`t$(Get-FileSha256 (Join-Path $repoRoot ($relative.Replace('/', '\'))))")
        }
        $runtimeManifestWithoutProtected = Get-Sha256Text (Get-MobileIonCanonicalManifest @($runtimeLines))
        $dataset = New-MobileIonRuntimeDatasetStage -DatasetPath $datasetPath -ProtectedArtifacts @($protectedRecord) -ProtectedSourceRoot $protectedSourceRoot
        if (-not (Test-MobileIonDatasetStage $datasetPath $dataset.TransportFiles $dataset.Hashes $dataset.ObelixFiles @($protectedRecord))) { throw 'Positive runtime transport staging validation failed.' }
        if ($dataset.ManifestSha256 -cne $runtimeManifestWithoutProtected) { throw 'Runtime dataset manifest changed when a protected-only file was transported.' }
        if ($dataset.TransportFiles -notcontains $protectedRelative) { throw 'Protected test artifact is absent from the transport path set.' }
        if ($dataset.RuntimeDatasetFiles -contains $protectedRelative -or $dataset.RuntimeSourceFiles -contains $protectedRelative) { throw 'Protected-only test artifact entered runtime files.' }
        if (-not $dataset.TransportManifestText.Contains($protectedRelative)) { throw 'Dataset transport manifest omits the protected test artifact.' }
        if ($dataset.RuntimeDatasetFiles -notcontains 'config.yaml') { throw 'config.yaml is absent from runtime dataset.' }
        if ($dataset.RuntimeDatasetFiles -notcontains 'data/batches/audit/g_ordered_expansion_v1.json') { throw 'Ordered expansion input is absent from runtime dataset.' }
        if ((@($dataset.RuntimeDatasetFiles | Where-Object { $_.StartsWith('data/obelix/', [System.StringComparison]::Ordinal) }) -join "`n") -cne (@($dataset.ObelixFiles) -join "`n")) { throw 'OBELiX runtime membership is not exact.' }
        if ($dataset.TransportFiles -contains '.github/workflows/cron.yml') { throw 'Repository-only workflow metadata entered dataset transport.' }
        Write-Host "PROTECTED_ARTIFACT_COUNT=$(@($protectedRecord).Count) (synthetic self-test fixture)"
        Write-Host "DATASET_STAGE_FILE_COUNT=$($dataset.TransportFiles.Count)"
        Write-Host 'DATASET_STAGE_HASHES=PASS'
        Write-Host 'DATASET_STAGE_EXACT_SET=PASS'
        Write-Host 'PROTECTED_TRANSPORT_RUNTIME_SEPARATION=PASS'

        $driver = Join-Path $repoRoot 'scripts\kaggle\mobile_ion_displace_e2e.py'
        $pythonOutput = @(& $python $driver --canonical-manifest-self-test $datasetPath 2>&1)
        if ($LASTEXITCODE -ne 0) { throw "Python canonical manifest self-test failed: $($pythonOutput -join "`n")" }
        $pythonText = ($pythonOutput | ForEach-Object { $_.ToString() }) -join "`n"
        $pythonB64 = [regex]::Match($pythonText, '(?m)^CANONICAL_MANIFEST_B64=([A-Za-z0-9+/=]+)$')
        $pythonHash = [regex]::Match($pythonText, '(?m)^CANONICAL_MANIFEST_SHA256=([0-9a-f]{64})$')
        if (-not $pythonB64.Success -or -not $pythonHash.Success) { throw 'Python canonical self-test omitted manifest bytes/hash.' }
        $pythonBytes = [Convert]::FromBase64String($pythonB64.Groups[1].Value)
        $powershellBytes = [System.Text.Encoding]::UTF8.GetBytes($dataset.TransportManifestText)
        $powershellHash = Get-Sha256Text $dataset.TransportManifestText
        if ([Convert]::ToBase64String($powershellBytes) -cne $pythonB64.Groups[1].Value -or
            $powershellHash -cne $pythonHash.Groups[1].Value -or
            [Convert]::ToBase64String($pythonBytes) -cne [Convert]::ToBase64String($powershellBytes)) {
            throw 'PowerShell and Python canonical manifest bytes/hash differ.'
        }
        Write-Host "CANONICAL_MANIFEST_SHA256=$powershellHash"
        Write-Host 'CROSS_LANGUAGE_MANIFEST_PARITY=PASS'

        foreach ($relative in @('config.yaml', 'data/obelix/data/processed.csv', $protectedRelative)) {
            $target = Join-Path $datasetPath ($relative.Replace('/', '\'))
            $original = [System.IO.File]::ReadAllBytes($target)
            try {
                $mutated = New-Object byte[] ($original.Length + 1)
                [Array]::Copy($original, $mutated, $original.Length)
                $mutated[$mutated.Length - 1] = 1
                [System.IO.File]::WriteAllBytes($target, $mutated)
                if (Test-MobileIonDatasetStage $datasetPath $dataset.TransportFiles $dataset.Hashes $dataset.ObelixFiles @($protectedRecord)) { throw "Mutation was accepted: $relative" }
            } finally { [System.IO.File]::WriteAllBytes($target, $original) }
            [System.IO.File]::Delete($target)
            if (Test-MobileIonDatasetStage $datasetPath $dataset.TransportFiles $dataset.Hashes $dataset.ObelixFiles @($protectedRecord)) { throw "Removal was accepted: $relative" }
            [System.IO.File]::WriteAllBytes($target, $original)
        }
        Write-Host 'RUNTIME_OBELIX_PROTECTED_MUTATION_REMOVAL_REJECTION=PASS'
    } finally {
        if (Test-Path -LiteralPath $testDirectory) { Remove-Item -LiteralPath $testDirectory -Recurse -Force }
    }
}

if ($Command -eq 'kaggle-mobile-ion-e2e') {
Invoke-MobileIonE2E
}

if ($Command -eq 'kaggle-mobile-ion-e2e-integrity-self-test') {
Invoke-MobileIonIntegritySelfTest
}

$kernelRef = 'wt2018mask/rhombus-gpu-smoke'

function Invoke-GpuSmokeSubmission {
    $stagingDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("rhombus-gpu-smoke-" + [guid]::NewGuid().ToString('N'))

    try {
        New-Item -ItemType Directory -Path $stagingDirectory -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $repoRoot 'scripts\kaggle\gpu_smoke.py') -Destination (Join-Path $stagingDirectory 'gpu_smoke.py') -Force

        $metadata = [ordered]@{
            id = $kernelRef
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
        if ($validatedMetadata.id -cne $kernelRef -or
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
            $script:gpuSmokeSubmissionExit = $quotaExit
            throw "Kaggle quota command failed with exit code $quotaExit."
        }

        Write-Host "KERNEL_REF=$kernelRef"
        Write-Host 'STAGING_LOCATION=TEMP'
        Write-Host 'ACCELERATOR=NvidiaTeslaT4'
        Write-Host 'SCIENTIFIC_EVIDENCE=false'

        & $python -m kaggle kernels push -p $stagingDirectory --accelerator NvidiaTeslaT4
        $script:gpuSmokeSubmissionExit = $LASTEXITCODE
    } finally {
        if (Test-Path -LiteralPath $stagingDirectory) {
            Remove-Item -LiteralPath $stagingDirectory -Recurse -Force
        }
    }
}

function Get-GpuSmokeVerification {
    param([string]$LogText)

    $gpuAvailable = [regex]::IsMatch($LogText, '(?im)^[^\r\n]*\bCUDA_AVAILABLE\s*=\s*true\b[^\r\n]*$')
    $smokePass = [regex]::IsMatch($LogText, '(?im)^[^\r\n]*\bRHOMBUS_GPU_SMOKE\s*=\s*PASS\b[^\r\n]*$')
    $gpuCountMatch = [regex]::Match($LogText, '(?im)^[^\r\n]*\bGPU_COUNT\s*=\s*(\d+)\b[^\r\n]*$')
    $gpuCountOk = $false
    if ($gpuCountMatch.Success) {
        try {
            $gpuCountOk = [int64]::Parse($gpuCountMatch.Groups[1].Value) -ge 1
        } catch {
            $gpuCountOk = $false
        }
    }

    return [pscustomobject]@{
        GpuAvailable = $gpuAvailable
        GpuCountOk = $gpuCountOk
        SmokePass = $smokePass
    }
}

if ($Command -eq 'kaggle-gpu-smoke-verify') {
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
    $verification = Get-GpuSmokeVerification $logText
    $gpuAvailable = $verification.GpuAvailable
    $gpuCountOk = $verification.GpuCountOk
    $smokePass = $verification.SmokePass

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
    Invoke-GpuSmokeSubmission
    $pushExit = $script:gpuSmokeSubmissionExit

    if ($pushExit -eq 0) {
        Write-Host 'SUBMIT_OK=true'
        Write-Host "KERNEL_REF=$kernelRef"
        Write-Host 'RESULT'
        Write-Host 'PASS'
    } else {
        Write-Host 'SUBMIT_OK=false'
        Write-Host "KERNEL_REF=$kernelRef"
        Write-Host 'RESULT'
        Write-Host 'FAIL'
    }
    exit $pushExit
}

if ($Command -eq 'kaggle-gpu-smoke-run') {
    $script:gpuSmokeSubmissionExit = $null
    try {
        Invoke-GpuSmokeSubmission
        $submitExit = $script:gpuSmokeSubmissionExit
    } catch {
        $submitExit = $script:gpuSmokeSubmissionExit
        if ($null -eq $submitExit -or $submitExit -eq 0) {
            $submitExit = 1
        }
        Write-Host 'RUN_PHASE=SUBMIT'
        Write-Host 'SUBMIT_OK=false'
        Write-Host 'VERIFY_OK=false'
        Write-Host 'SCIENTIFIC_EVIDENCE=false'
        Write-Host 'RESULT'
        Write-Host 'FAIL'
        exit $submitExit
    }

    if ($submitExit -ne 0) {
        Write-Host 'RUN_PHASE=SUBMIT'
        Write-Host 'SUBMIT_OK=false'
        Write-Host 'VERIFY_OK=false'
        Write-Host 'SCIENTIFIC_EVIDENCE=false'
        Write-Host 'RESULT'
        Write-Host 'FAIL'
        exit $submitExit
    }

    Write-Host 'RUN_PHASE=WAIT'
    Write-Host 'SUBMIT_OK=true'
    Write-Host "KERNEL_REF=$kernelRef"

    $terminalState = $null
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        Write-Host "POLL_ATTEMPT=$attempt"
        $statusOutput = @(& $python -m kaggle kernels status $kernelRef 2>&1 | Tee-Object -Variable capturedStatusOutput)
        $statusExit = $LASTEXITCODE

        if ($statusExit -ne 0) {
            Write-Host 'RUN_PHASE=WAIT'
            Write-Host 'QUERY_OK=false'
            Write-Host 'REMOTE_STATE=UNKNOWN'
            Write-Host 'VERIFY_OK=false'
            Write-Host 'SCIENTIFIC_EVIDENCE=false'
            Write-Host 'RESULT'
            Write-Host 'FAIL'
            exit $statusExit
        }

        $statusText = ($statusOutput | ForEach-Object { $_.ToString() }) -join "`n"
        $stateMatch = [regex]::Match($statusText, '(?im)^[^\r\n]*KernelWorkerStatus\.([A-Za-z0-9_]+)[^\r\n]*$')
        if (-not $stateMatch.Success) {
            Write-Host 'RUN_PHASE=WAIT'
            Write-Host 'QUERY_OK=true'
            Write-Host 'REMOTE_STATE=UNKNOWN'
            Write-Host 'VERIFY_OK=false'
            Write-Host 'SCIENTIFIC_EVIDENCE=false'
            Write-Host 'RESULT'
            Write-Host 'UNKNOWN'
            exit 11
        }

        $remoteState = $stateMatch.Groups[1].Value
        if ($remoteState -cne 'COMPLETE' -and $remoteState -cne 'ERROR') {
            Write-Host 'QUERY_OK=true'
            Write-Host "REMOTE_STATE=$remoteState"
            Write-Host 'REMOTE_TERMINAL=false'
            if ($attempt -lt 30) {
                Start-Sleep -Seconds 10
            }
            continue
        }

        $terminalState = $remoteState
        break
    }

    if ($null -eq $terminalState) {
        Write-Host 'RUN_PHASE=WAIT'
        Write-Host 'REMOTE_TERMINAL=false'
        Write-Host 'VERIFY_OK=false'
        Write-Host 'SCIENTIFIC_EVIDENCE=false'
        Write-Host 'RESULT'
        Write-Host 'TIMEOUT'
        exit 12
    }

    if ($terminalState -ceq 'ERROR') {
        Write-Host 'RUN_PHASE=REMOTE_ERROR'
        Write-Host 'QUERY_OK=true'
        Write-Host 'REMOTE_STATE=ERROR'
        Write-Host 'REMOTE_TERMINAL=true'
        Write-Host 'REMOTE_OK=false'
        $logOutput = @(& $python -m kaggle kernels logs $kernelRef 2>&1 | Tee-Object -Variable capturedLogOutput)
        $logsExit = $LASTEXITCODE
        if ($logsExit -ne 0) {
            Write-Host 'LOGS_OK=false'
        } else {
            Write-Host 'LOGS_OK=true'
        }
        Write-Host 'VERIFY_OK=false'
        Write-Host 'SCIENTIFIC_EVIDENCE=false'
        Write-Host 'RESULT'
        Write-Host 'REMOTE_ERROR'
        exit 20
    }

    Write-Host 'RUN_PHASE=VERIFY'
    Write-Host 'QUERY_OK=true'
    Write-Host 'REMOTE_STATE=COMPLETE'
    Write-Host 'REMOTE_TERMINAL=true'
    Write-Host 'REMOTE_OK=true'
    $logOutput = @(& $python -m kaggle kernels logs $kernelRef 2>&1 | Tee-Object -Variable capturedLogOutput)
    $logsExit = $LASTEXITCODE
    if ($logsExit -ne 0) {
        Write-Host 'LOGS_OK=false'
        Write-Host 'VERIFY_OK=false'
        Write-Host 'SCIENTIFIC_EVIDENCE=false'
        Write-Host 'RESULT'
        Write-Host 'FAIL'
        exit $logsExit
    }

    Write-Host 'LOGS_OK=true'
    $logText = ($logOutput | ForEach-Object { $_.ToString() }) -join "`n"
    $verification = Get-GpuSmokeVerification $logText
    $gpuAvailable = $verification.GpuAvailable
    $gpuCountOk = $verification.GpuCountOk
    $smokePass = $verification.SmokePass
    if ($gpuAvailable -and $gpuCountOk -and $smokePass) {
        Write-Host 'GPU_AVAILABLE=true'
        Write-Host 'GPU_COUNT_OK=true'
        Write-Host 'SMOKE_PASS=true'
        Write-Host 'VERIFY_OK=true'
        Write-Host 'SCIENTIFIC_EVIDENCE=false'
        Write-Host 'RUN_OK=true'
        Write-Host 'RESULT'
        Write-Host 'PASS'
        exit 0
    }

    Write-Host "GPU_AVAILABLE=$($gpuAvailable.ToString().ToLowerInvariant())"
    Write-Host "GPU_COUNT_OK=$($gpuCountOk.ToString().ToLowerInvariant())"
    Write-Host "SMOKE_PASS=$($smokePass.ToString().ToLowerInvariant())"
    Write-Host 'VERIFY_OK=false'
    Write-Host 'SCIENTIFIC_EVIDENCE=false'
    Write-Host 'RUN_OK=false'
    Write-Host 'RESULT'
    Write-Host 'VERIFY_FAIL'
    exit 21
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
