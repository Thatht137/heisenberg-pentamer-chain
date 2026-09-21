param(
    [int]$MaxCells = 0,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$run = Join-Path $root "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh"
$remote = "wangjieren@39.96.207.180"
$port = "6000"
$key = Join-Path $env:USERPROFILE ".ssh\id_ed25519"
$remoteRun = "/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh"
$cells = Join-Path $run "cells"
$staging = Join-Path $run ".downloads"

if (-not (Test-Path -LiteralPath $key -PathType Leaf)) {
    throw "Private key not found: $key"
}
if (-not (Test-Path -LiteralPath $run -PathType Container)) {
    throw "Run directory not found: $run"
}

$sshOptions = @(
    "-p", $port, "-i", $key, "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new"
)
$scpOptions = @(
    "-P", $port, "-i", $key, "-o", "BatchMode=yes",
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
        $actual = Get-Sha256 $target
        if ($actual -ne $parts[0].ToLowerInvariant()) {
            return $false
        }
    }
    return $true
}

function Remove-Staging([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    for ($attempt = 1; $attempt -le 6; $attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return
        }
        catch {
            if ($attempt -eq 6) {
                Write-Warning ("temporary cleanup deferred: " + $Path)
                return
            }
            Start-Sleep -Seconds 2
        }
    }
}

$statusText = (& ssh @sshOptions $remote ("cat " + $remoteRun + "/run_status.json")) -join "`n"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read remote run_status.json"
}
$status = $statusText | ConvertFrom-Json
$completed = @($status.completed | ForEach-Object { [string]$_ })
if ($MaxCells -gt 0) {
    $completed = @($completed | Select-Object -First $MaxCells)
}

if (-not $DryRun) {
    Set-Content -LiteralPath (Join-Path $run "run_status.json") -Value ($statusText + "`n") -Encoding UTF8
    New-Item -ItemType Directory -Force -Path $cells | Out-Null
    New-Item -ItemType Directory -Force -Path $staging | Out-Null
}

Write-Output ("REMOTE_STATUS=" + [string]$status.status + " COMPLETED=" + $completed.Count)
foreach ($cellId in $completed) {
    if ($cellId -notmatch '^mesh-cell-[0-9]{4}$') {
        throw "Unexpected cell id: $cellId"
    }
    $remoteCell = $remoteRun + "/cells/" + $cellId
    $destination = Join-Path $cells $cellId
    if (Test-Path -LiteralPath $destination) {
        if (Test-Checksums $destination) {
            Write-Output ("SKIP_LOCAL_VALID=" + $cellId)
            continue
        }
        throw "Local destination exists but failed checksum validation: $destination"
    }
    if ($DryRun) {
        Write-Output ("FETCH_PLAN=" + $cellId)
        continue
    }

    $remoteCheck = (& ssh @sshOptions $remote ("cd " + $remoteCell + " && sha256sum -c checksums.sha256")) -join "`n"
    if ($LASTEXITCODE -ne 0) {
        throw "Remote checksum failed: $cellId`n$remoteCheck"
    }

    $tempParent = Join-Path $staging ([guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $tempParent | Out-Null
    try {
        & scp @scpOptions -r ($remote + ":" + $remoteCell) $tempParent
        if ($LASTEXITCODE -ne 0) {
            throw "scp failed: $cellId"
        }
        $staged = Join-Path $tempParent $cellId
        if (-not (Test-Checksums $staged)) {
            throw "Downloaded checksum failed: $cellId"
        }
        $manifest = Get-Content -LiteralPath (Join-Path $staged "manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($manifest.status -ne "success" -or -not [bool]$manifest.accepted) {
            throw "Downloaded cell is not accepted: $cellId"
        }
        Move-Item -LiteralPath $staged -Destination $destination
        Write-Output ("FETCHED=" + $cellId)
    }
    finally {
        if (Test-Path -LiteralPath $tempParent) {
            Remove-Item -LiteralPath $tempParent -Recurse -Force
        }
    }
}

if (-not $DryRun -and (Test-Path -LiteralPath $staging)) {
    Remove-Staging $staging
}
Write-Output "DOWNLOAD_AND_HASH_OK"
