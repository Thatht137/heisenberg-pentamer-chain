param(
    [Parameter(Mandatory = $true)]
    [string]$Confirmation,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$token = (([char]0x786E, [char]0x8BA4, [char]0x9996, [char]0x6BB5) -join "")
if ($Confirmation -ne $token) {
    throw "Upload blocked: confirmation required."
}

$root = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$run = Join-Path $root "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh"
$manifestPath = Join-Path $run "server_upload_manifest.json"
$remote = "wangjieren@39.96.207.180"
$port = "6000"
$key = Join-Path $env:USERPROFILE ".ssh\id_ed25519"

if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Upload manifest missing: $manifestPath"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$remoteRoot = [string]$manifest.target
if ($remoteRoot -notmatch '^/home/[A-Za-z0-9._-]+/code/[A-Za-z0-9._/-]+$') {
    throw "Unsafe remote root: $remoteRoot"
}

function Get-Sha256([string]$Path) {
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
}

$sshOptions = @(
    "-p", $port, "-i", $key, "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new"
)
$scpOptions = @(
    "-P", $port, "-i", $key, "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new"
)

foreach ($entry in $manifest.files) {
    $relative = [string]$entry.path
    $local = Join-Path $root ($relative -replace '/', '\\')
    if (-not (Test-Path -LiteralPath $local -PathType Leaf)) {
        throw "Local upload file missing: $relative"
    }
    if ((Get-Sha256 $local) -ne ([string]$entry.sha256).ToLowerInvariant()) {
        throw "Local manifest hash mismatch: $relative"
    }
}

if ($DryRun) {
    Write-Output "DRY_RUN_CONFIRMATION_OK"
    foreach ($entry in $manifest.files) {
        Write-Output ("scp " + $entry.path + " -> " + $remote + ":" + $remoteRoot + "/" + $entry.path)
    }
    exit 0
}

if (-not (Test-Path -LiteralPath $key -PathType Leaf)) {
    throw "Private key missing: $key"
}
& ssh @sshOptions $remote ("mkdir -p " + $remoteRoot)
if ($LASTEXITCODE -ne 0) {
    throw "Remote root creation failed"
}

foreach ($entry in $manifest.files) {
    $relative = [string]$entry.path
    $remotePath = $remoteRoot + "/" + $relative
    $slash = $remotePath.LastIndexOf('/')
    if ($slash -gt 0) {
        & ssh @sshOptions $remote ("mkdir -p " + $remotePath.Substring(0, $slash))
        if ($LASTEXITCODE -ne 0) {
            throw "Remote directory creation failed: $relative"
        }
    }
    $remoteHash = (& ssh @sshOptions $remote ("sha256sum " + $remotePath + " 2>/dev/null")) -join "`n"
    if ($LASTEXITCODE -eq 0 -and $remoteHash -match "^$([string]$entry.sha256)\s") {
        Write-Output ("SKIP_HASH_MATCH " + $relative)
        continue
    }
    $local = Join-Path $root ($relative -replace '/', '\\')
    & scp @scpOptions $local ($remote + ":" + $remotePath)
    if ($LASTEXITCODE -ne 0) {
        throw "Upload failed: $relative"
    }
}

foreach ($entry in $manifest.files) {
    $remotePath = $remoteRoot + "/" + [string]$entry.path
    $check = (& ssh @sshOptions $remote ("sha256sum " + $remotePath)) -join "`n"
    if ($LASTEXITCODE -ne 0 -or $check -notmatch "^$([string]$entry.sha256)\s") {
        throw "Remote SHA-256 mismatch: $($entry.path)"
    }
}
Write-Output ("UPLOAD_AND_HASH_OK files=" + $manifest.files.Count)
