param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$runName = "round24_tebd_eta01_crosscheck"
$cellId = "cell-alpha023-dt025-t30"
$destination = Join-Path $root "results/autoresearch_v5_20260803/$runName"
$staging = Join-Path $root "results/autoresearch_v5_20260803/.downloads-round24-failure"
$remote = "wangjieren@39.96.207.180"
$remoteRoot = "/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/autoresearch_v5_20260803/$runName"
$key = Join-Path $env:USERPROFILE ".ssh\id_ed25519"

if (-not (Test-Path -LiteralPath $key -PathType Leaf)) {
    throw "Private key not found: $key"
}
if (Test-Path -LiteralPath $destination) {
    throw "Refuse to overwrite local run: $destination"
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

function Test-ExpectedFailure($Manifest) {
    if ($Manifest.status -ne "success" -or $Manifest.accepted -ne $false) {
        return $false
    }
    $failed = @(
        $Manifest.acceptance.psobject.Properties |
            Where-Object { $_.Value -ne $true } |
            ForEach-Object { $_.Name }
    )
    return $failed.Count -eq 1 -and $failed[0] -eq "raw_spectrum_nonnegative"
}

$remoteCell = "$remoteRoot/$cellId"
$manifestText = (& ssh @sshOptions $remote ("cat " + $remoteCell + "/manifest.json")) -join "`n"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read remote manifest.json"
}
$manifest = $manifestText | ConvertFrom-Json
if (-not (Test-ExpectedFailure $manifest)) {
    throw "Remote manifest does not match the expected isolated raw-spectrum failure"
}
$remoteCheck = (& ssh @sshOptions $remote ("cd " + $remoteCell + " && sha256sum -c checksums.sha256")) -join "`n"
if ($LASTEXITCODE -ne 0) {
    throw "Remote checksum failed:`n$remoteCheck"
}
$overallHashText = (& ssh @sshOptions $remote ("sha256sum " + $remoteRoot + "/overall_status.json")) -join "`n"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to hash remote overall_status.json"
}
$overallHash = ($overallHashText -split "\s+")[0].ToLowerInvariant()

if ($DryRun) {
    Write-Output ("FETCH_PLAN=" + $remote + ":" + $remoteRoot + " -> " + $destination)
    Write-Output "REMOTE_CHECKSUM=PASS"
    Write-Output "EXPECTED_FAILURE=raw_spectrum_nonnegative"
    exit 0
}

New-Item -ItemType Directory -Force -Path $staging | Out-Null
$tempParent = Join-Path $staging ([guid]::NewGuid().ToString("N"))
$tempRun = Join-Path $tempParent $runName
New-Item -ItemType Directory -Force -Path $tempRun | Out-Null
try {
    & scp @scpOptions -r ($remote + ":" + $remoteCell) $tempRun
    if ($LASTEXITCODE -ne 0) {
        throw "scp failed for $cellId"
    }
    $stagedCell = Join-Path $tempRun $cellId
    if (-not (Test-Checksums $stagedCell)) {
        throw "Downloaded checksum failed"
    }
    $stagedManifest = Get-Content -LiteralPath (Join-Path $stagedCell "manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not (Test-ExpectedFailure $stagedManifest)) {
        throw "Downloaded manifest does not match the expected failure"
    }
    & scp @scpOptions ($remote + ":" + $remoteRoot + "/overall_status.json") $tempRun
    if ($LASTEXITCODE -ne 0) {
        throw "scp failed for overall_status.json"
    }
    if ((Get-Sha256 (Join-Path $tempRun "overall_status.json")) -ne $overallHash) {
        throw "Downloaded overall_status.json checksum failed"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) | Out-Null
    Move-Item -LiteralPath $tempRun -Destination $destination
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
