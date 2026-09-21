param(
    [Parameter(Mandatory = $true)]
    [string]$Confirmation,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$token = (([char]0x786E, [char]0x8BA4, [char]0x9996, [char]0x6BB5) -join "")
if ($Confirmation -ne $token) {
    throw "Upload blocked: pass -Confirmation with the exact first-stage token."
}

$root = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$run = Join-Path $root "results/autoresearch_v5_20260731/round17_phase_diagram_positive"
$manifestPath = Join-Path $run "server_upload_manifest.json"
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$remote = "wangjieren@39.96.207.180"
$port = "6000"
$key = Join-Path $env:USERPROFILE ".ssh\id_ed25519"
$remoteRoot = "/home/wangjieren/code/1x5_Heisenberg_Pentamer"

if (-not $DryRun -and -not (Test-Path -LiteralPath $key -PathType Leaf)) {
    throw "Private key not found: $key"
}

$sshOptions = @("-p", $port, "-i", $key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new")
$scpOptions = @("-P", $port, "-i", $key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new")
$directories = @(
    "$remoteRoot/src",
    "$remoteRoot/docs",
    "$remoteRoot/scripts/autoresearch_v5",
    "$remoteRoot/results/autoresearch_v5_20260731/round17_phase_diagram_positive"
)

if ($DryRun) {
    Write-Output "DRY_RUN_CONFIRMATION_OK"
    foreach ($entry in $manifest.files) {
        Write-Output ("scp " + $entry.path + " -> " + $remote + ":" + $remoteRoot + "/" + $entry.path)
    }
    exit 0
}

& ssh @sshOptions $remote ("mkdir -p " + ($directories -join " "))
if ($LASTEXITCODE -ne 0) {
    throw "Remote directory creation failed; no files were uploaded."
}

foreach ($entry in $manifest.files) {
    $local = Join-Path $root $entry.path
    if (-not (Test-Path -LiteralPath $local -PathType Leaf)) {
        throw "Local upload file missing: $local"
    }
    $remotePath = $remoteRoot + "/" + $entry.path
    $existing = & ssh @sshOptions $remote ("sha256sum " + $remotePath + " 2>/dev/null")
    if ($LASTEXITCODE -eq 0 -and $existing -match $entry.sha256) {
        Write-Output ("SKIP_HASH_MATCH " + $entry.path)
        continue
    }
    $destination = $remote + ":" + $remotePath
    & scp @scpOptions $local $destination
    if ($LASTEXITCODE -ne 0) {
        throw "Upload failed: $($entry.path)"
    }
}

foreach ($entry in $manifest.files) {
    $remotePath = "$remoteRoot/$($entry.path)"
    $check = & ssh @sshOptions $remote ("sha256sum " + $remotePath)
    if ($LASTEXITCODE -ne 0 -or $check -notmatch $entry.sha256) {
        throw "Remote SHA-256 mismatch: $($entry.path)"
    }
}
Write-Output ("UPLOAD_AND_HASH_OK files=" + $manifest.files.Count)

