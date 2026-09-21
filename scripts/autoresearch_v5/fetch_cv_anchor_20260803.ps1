param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$run = Join-Path $root "results/autoresearch_v5_20260802/round22_cv_l80_anchor"
$cellId = "cell-0003-L80-qpi-w025"
$destination = Join-Path $run $cellId
$staging = Join-Path $run ".downloads-anchor"
$remote = "wangjieren@39.96.207.180"
$remoteRoot = "/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/autoresearch_v5_20260802/round22_cv_l80_anchor"
$key = Join-Path $env:USERPROFILE ".ssh\id_ed25519"

if (-not (Test-Path -LiteralPath $key -PathType Leaf)) {
    throw "Private key not found: $key"
}
if (-not (Test-Path -LiteralPath $run -PathType Container)) {
    throw "Run directory not found: $run"
}

$sshOptions = @(
    "-p", "6000", "-i", $key, "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new"
)
$scpOptions = @(
    "-P", "6000", "-i", $key, "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new"
)

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

function Test-Checksums([string]$CellPath) {
    $checksumPath = Join-Path $CellPath "checksums.sha256"
    if (-not (Test-Path -LiteralPath $checksumPath -PathType Leaf)) {
        return $false
    }
    foreach ($line in Get-Content -LiteralPath $checksumPath -Encoding UTF8) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        $parts = $line -split "  ", 2
        if ($parts.Count -ne 2) {
            return $false
        }
        $target = Join-Path $CellPath $parts[1]
        if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
            return $false
        }
        if ((Get-Sha256 $target) -ne $parts[0].ToLowerInvariant()) {
            return $false
        }
    }
    return $true
}

$remoteCell = "$remoteRoot/$cellId"
$statusText = (& ssh @sshOptions $remote ("cat " + $remoteCell + "/status.json")) -join "`n"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read remote anchor status.json"
}
$status = $statusText | ConvertFrom-Json
Write-Output ("REMOTE_STATUS=" + [string]$status.status)
if ($status.status -ne "success") {
    Write-Output "ANCHOR_NOT_TERMINAL=TRUE"
    exit 3
}

if (Test-Path -LiteralPath $destination) {
    if (Test-Checksums $destination) {
        Write-Output "LOCAL_ANCHOR_ALREADY_VALID=TRUE"
        exit 0
    }
    throw "Local anchor destination exists but checksum validation failed: $destination"
}

$remoteCheck = (& ssh @sshOptions $remote ("cd " + $remoteCell + " && sha256sum -c checksums.sha256")) -join "`n"
if ($LASTEXITCODE -ne 0) {
    throw "Remote anchor checksum failed:`n$remoteCheck"
}
if ($DryRun) {
    Write-Output ("FETCH_PLAN=" + $remote + ":" + $remoteCell + " -> " + $destination)
    Write-Output "REMOTE_CHECKSUM=PASS"
    exit 0
}

New-Item -ItemType Directory -Force -Path $staging | Out-Null
$tempParent = Join-Path $staging ([guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tempParent | Out-Null
try {
    & scp @scpOptions -r ($remote + ":" + $remoteCell) $tempParent
    if ($LASTEXITCODE -ne 0) {
        throw "scp failed for $cellId"
    }
    $staged = Join-Path $tempParent $cellId
    if (-not (Test-Checksums $staged)) {
        throw "Downloaded anchor checksum failed"
    }
    $manifest = Get-Content -LiteralPath (Join-Path $staged "manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.status -ne "success" -or $manifest.acceptance.status -ne "pass") {
        throw "Downloaded anchor manifest is not accepted"
    }
    Move-Item -LiteralPath $staged -Destination $destination
    Write-Output "FETCH_AND_HASH_OK=TRUE"
}
finally {
    if (Test-Path -LiteralPath $tempParent) {
        Remove-Item -LiteralPath $tempParent -Recurse -Force
    }
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
}
