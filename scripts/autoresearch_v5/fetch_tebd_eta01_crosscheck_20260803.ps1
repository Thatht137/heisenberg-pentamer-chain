param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$runName = "round24_tebd_eta01_crosscheck"
$destination = Join-Path $root "results/autoresearch_v5_20260803/$runName"
$staging = Join-Path $root "results/autoresearch_v5_20260803/.downloads-round24"
$cells = @("cell-alpha023-dt025-t30", "cell-alpha023-dt0125-t30")
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

$overallText = (& ssh @sshOptions $remote ("cat " + $remoteRoot + "/overall_status.json")) -join "`n"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read remote overall_status.json"
}
$overall = $overallText | ConvertFrom-Json
Write-Output ("REMOTE_STATUS=" + [string]$overall.status)
if ($overall.status -ne "success") {
    Write-Output "ROUND24_NOT_TERMINAL=TRUE"
    exit 3
}

foreach ($cell in $cells) {
    $remoteCell = "$remoteRoot/$cell"
    $remoteCheck = (& ssh @sshOptions $remote ("cd " + $remoteCell + " && sha256sum -c checksums.sha256")) -join "`n"
    if ($LASTEXITCODE -ne 0) {
        throw "Remote checksum failed for ${cell}:`n$remoteCheck"
    }
}
$crossHashText = (& ssh @sshOptions $remote ("sha256sum " + $remoteRoot + "/crosscheck.json")) -join "`n"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to hash remote crosscheck.json"
}
$crossHash = ($crossHashText -split "\s+")[0].ToLowerInvariant()

if ($DryRun) {
    Write-Output ("FETCH_PLAN=" + $remote + ":" + $remoteRoot + " -> " + $destination)
    Write-Output "REMOTE_CHECKSUM=PASS"
    exit 0
}

New-Item -ItemType Directory -Force -Path $staging | Out-Null
$tempParent = Join-Path $staging ([guid]::NewGuid().ToString("N"))
$tempRun = Join-Path $tempParent $runName
New-Item -ItemType Directory -Force -Path $tempRun | Out-Null
try {
    foreach ($cell in $cells) {
        & scp @scpOptions -r ($remote + ":" + $remoteRoot + "/" + $cell) $tempRun
        if ($LASTEXITCODE -ne 0) {
            throw "scp failed for $cell"
        }
        if (-not (Test-Checksums (Join-Path $tempRun $cell))) {
            throw "Downloaded checksum failed for $cell"
        }
        $manifest = Get-Content -LiteralPath (Join-Path $tempRun "$cell/manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($manifest.status -ne "success" -or $manifest.accepted -ne $true) {
            throw "Downloaded manifest is not accepted: $cell"
        }
    }
    foreach ($file in @("overall_status.json", "crosscheck.json")) {
        & scp @scpOptions ($remote + ":" + $remoteRoot + "/" + $file) $tempRun
        if ($LASTEXITCODE -ne 0) {
            throw "scp failed for $file"
        }
    }
    if ((Get-Sha256 (Join-Path $tempRun "crosscheck.json")) -ne $crossHash) {
        throw "Downloaded crosscheck.json checksum failed"
    }
    $crosscheck = Get-Content -LiteralPath (Join-Path $tempRun "crosscheck.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($crosscheck.status -ne "pass") {
        throw "Remote dt/dt2 crosscheck did not pass"
    }
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
