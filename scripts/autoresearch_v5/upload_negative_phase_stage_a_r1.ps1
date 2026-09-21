param(
    [Parameter(Mandatory = $true)]
    [string]$Confirmation,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if ($Confirmation -ne "CONFIRM_NEGATIVE_STAGE_A_R1") { throw "Upload blocked: confirmation required." }

$root = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$run = Join-Path $root "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/stage-a-beta050-calibration-r1"
$manifestPath = Join-Path $run "server_upload_manifest.json"
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$remote = "wangjieren@39.96.207.180"
$port = "6000"
$key = Join-Path $env:USERPROFILE ".ssh\id_ed25519"
$remoteRoot = [string]$manifest.target
if ($remoteRoot -notmatch '^/home/[A-Za-z0-9._-]+/code/[A-Za-z0-9._/-]+$') { throw "Unsafe remote root: $remoteRoot" }

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

foreach ($entry in $manifest.files) {
    $relative = [string]$entry.path
    $local = Join-Path $root ($relative -replace '/', '\')
    if (-not (Test-Path -LiteralPath $local -PathType Leaf)) { throw "Local upload file missing: $relative" }
    if ((Get-Sha256 $local) -ne ([string]$entry.sha256).ToLowerInvariant()) { throw "Local manifest hash mismatch: $relative" }
}
if ($DryRun) {
    Write-Output ("DRY_RUN_OK files=" + $manifest.files.Count + " target=" + $remoteRoot + " concurrency=" + $manifest.concurrency)
    exit 0
}
if (-not (Test-Path -LiteralPath $key -PathType Leaf)) { throw "Private key missing: $key" }
$ssh = @("-p", $port, "-i", $key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new")
$scp = @("-P", $port, "-i", $key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new")
& ssh @ssh $remote ("mkdir -p " + $remoteRoot)
if ($LASTEXITCODE -ne 0) { throw "Remote root creation failed" }
foreach ($entry in $manifest.files) {
    $relative = [string]$entry.path
    $remotePath = $remoteRoot + "/" + $relative
    $parent = $remotePath.Substring(0, $remotePath.LastIndexOf('/'))
    & ssh @ssh $remote ("mkdir -p " + $parent)
    if ($LASTEXITCODE -ne 0) { throw "Remote directory creation failed: $relative" }
    $remoteHash = ((& ssh @ssh $remote ("sha256sum " + $remotePath + " 2>/dev/null")) -join [Environment]::NewLine)
    if ($LASTEXITCODE -eq 0 -and $remoteHash -match ("^" + [string]$entry.sha256 + "\s")) {
        Write-Output ("SKIP_HASH_MATCH " + $relative)
        continue
    }
    $local = Join-Path $root ($relative -replace '/', '\')
    & scp @scp $local ($remote + ":" + $remotePath)
    if ($LASTEXITCODE -ne 0) { throw "Upload failed: $relative" }
}
foreach ($entry in $manifest.files) {
    $remotePath = $remoteRoot + "/" + [string]$entry.path
    $check = ((& ssh @ssh $remote ("sha256sum " + $remotePath)) -join [Environment]::NewLine)
    if ($LASTEXITCODE -ne 0 -or $check -notmatch ("^" + [string]$entry.sha256 + "\s")) { throw "Remote SHA-256 mismatch: $($entry.path)" }
}
Write-Output ("UPLOAD_AND_HASH_OK files=" + $manifest.files.Count)
