param(
  [string]$Confirmation,
  [switch]$DryRun,
  [string]$ManifestPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Get-Item $PSScriptRoot).Parent.Parent.FullName
if (-not $ManifestPath) {
  $ManifestPath = Join-Path $root "results/autoresearch_v5_20260919/static_krylov_controls_release_v1/server_upload_manifest.json"
}
$helper = Join-Path $root "scripts/autoresearch_v5/static_krylov_launch_preflight.py"
$python = "D:\Python3.12.4\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }

$preview = & $python $helper --mode upload --manifest $ManifestPath --json 2>&1
if ($LASTEXITCODE -ne 0) { throw (($preview | Out-String).Trim()) }
$previewText = ($preview | Out-String)
$previewObject = $previewText | ConvertFrom-Json
if ($previewObject.network_used -ne $false -or $previewObject.base_input_count -ne 18) {
  throw "local preflight did not preserve network=false and 18 inputs"
}

if ($DryRun) {
  $fileCount = [int]$previewObject.base_input_count + [int]$previewObject.additional_file_count
  Write-Output ("DRY_RUN_OK files=" + $fileCount + " control=" + $previewObject.control_path + " network_used=false")
  exit 0
}
if ($Confirmation -ne "CONFIRM_STATIC_KRYLOV_CONTROLS_RELEASE_V1") { throw "Upload blocked" }

$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$remote = "wangjieren@39.96.207.180"
$port = "6000"
$key = Join-Path $env:USERPROFILE ".ssh\id_ed25519"
$remoteRoot = [string]$manifest.target
if ($remoteRoot -ne "/home/wangjieren/code/1x5_Heisenberg_Pentamer") { throw "remote root does not match profile" }
$ssh = @("-p", $port, "-i", $key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new")
$scp = @("-P", $port, "-i", $key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new")

function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function SafeRelative([string]$Path) {
  if (-not $Path -or $Path.StartsWith("/") -or $Path.Contains("..") -or $Path.Contains([char]39)) { throw "unsafe relative path: $Path" }
  return $Path
}
function ShellQuote([string]$Path) { return $Path }

$records = @()
$controlRelative = SafeRelative ([string]$manifest.control_path)
$records += [pscustomobject]@{
  Relative = $controlRelative
  Local = (Resolve-Path -LiteralPath $ManifestPath).Path
  Digest = (Hash $ManifestPath)
}
foreach ($entry in @($manifest.files)) {
  $relative = SafeRelative ([string]$entry.path)
  $local = Join-Path $root $relative
  if ((Hash $local) -ne ([string]$entry.sha256).ToLowerInvariant()) { throw "local hash mismatch: $relative" }
  $records += [pscustomobject]@{ Relative = $relative; Local = $local; Digest = ([string]$entry.sha256).ToLowerInvariant() }
}

& ssh @ssh $remote ("mkdir -p " + (ShellQuote $remoteRoot))
if ($LASTEXITCODE -ne 0) { throw "remote root unavailable" }

foreach ($record in $records) {
  $remotePath = "$remoteRoot/$($record.Relative)"
  & ssh @ssh $remote ("test ! -e " + (ShellQuote $remotePath))
  if ($LASTEXITCODE -ne 0) { throw "remote file exists; refusing overwrite: $($record.Relative)" }
}

foreach ($record in $records) {
  $remotePath = "$remoteRoot/$($record.Relative)"
  $parent = $remotePath.Substring(0, $remotePath.LastIndexOf("/"))
  & ssh @ssh $remote ("mkdir -p " + (ShellQuote $parent))
  if ($LASTEXITCODE -ne 0) { throw "remote mkdir failed: $($record.Relative)" }
  & scp @scp $record.Local ($remote + ":" + $remotePath)
  if ($LASTEXITCODE -ne 0) { throw "upload failed: $($record.Relative)" }
}

foreach ($record in $records) {
  $remotePath = "$remoteRoot/$($record.Relative)"
  $check = "sha256sum " + $remotePath + " | grep -q " + $record.Digest
  & ssh @ssh $remote $check
  if ($LASTEXITCODE -ne 0) { throw "remote hash check failed: $($record.Relative)" }
}
$count = $records.Count
Write-Output ("UPLOAD_AND_HASH_OK files=" + $count + " cells=2 concurrency=1")
