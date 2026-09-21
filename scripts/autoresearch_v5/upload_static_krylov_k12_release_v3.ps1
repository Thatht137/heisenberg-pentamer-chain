param(
  [string]$Confirmation,
  [switch]$DryRun,
  [string]$ManifestPath,
  [string]$PrivateKey
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Get-Item $PSScriptRoot).Parent.Parent.FullName
if (-not $ManifestPath) {
  $ManifestPath = Join-Path $root "results/autoresearch_v5_20260920/static_krylov_controls_release_v3/server_upload_manifest.json"
}
$helper = Join-Path $root "scripts/autoresearch_v5/static_krylov_k12_preflight.py"
$python = "D:\Python3.12.4\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }
if (-not $PrivateKey) { $PrivateKey = Join-Path $env:USERPROFILE ".ssh\id_ed25519" }

$preview = & $python -B -X utf8 $helper --mode upload --manifest $ManifestPath --root $root --json 2>&1
if ($LASTEXITCODE -ne 0) { throw (($preview | Out-String).Trim()) }
$previewText = ($preview | Out-String)
$previewObject = $previewText | ConvertFrom-Json
$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (($previewObject.PSObject.Properties.Name -notcontains "network_used") -or $previewObject.network_used -ne $false) {
  throw "local preflight did not preserve network=false"
}
if (($previewObject.PSObject.Properties.Name -contains "status") -and $previewObject.status -ne "prepared_only") {
  throw "local preflight status is not prepared_only"
}
if ($null -eq $manifest.files -or @($manifest.files).Count -lt 1) { throw "manifest files is empty" }
if ($DryRun) {
  $fileCount = @($manifest.files).Count + 1
  Write-Output ("DRY_RUN_OK files=" + $fileCount + " control=" + $previewObject.control_path + " network_used=false confirmation_required=CONFIRM_STATIC_KRYLOV_K12_RELEASE_V3")
  exit 0
}
if ($Confirmation -ne "CONFIRM_STATIC_KRYLOV_K12_RELEASE_V3") { throw "Upload blocked" }

$remote = "wangjieren@39.96.207.180"
$port = "6000"
$key = $PrivateKey
$remoteRoot = [string]$manifest.target
if ($remoteRoot -ne "/home/wangjieren/releases/1x5_Heisenberg_Pentamer/static_krylov_controls_release_v3") { throw "remote root is not an isolated release bundle" }
if (-not (Test-Path -LiteralPath $key)) { throw "private key not found: $key" }

function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function SafeRelative([string]$Path) {
  if (-not $Path -or $Path.StartsWith("/") -or $Path.Contains("..") -or $Path.Contains([char]39) -or $Path -match "\s") { throw "unsafe relative path: $Path" }
  return $Path
}
function QuoteNative([string]$Value) {
  if ($Value -notmatch '[\s"]') { return $Value }
  return '"' + $Value.Replace('\', '\\').Replace('"', '\"') + '"'
}
function InvokeRemoteScript([string]$Script) {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = "ssh"
  $args = @("-p", $port, "-i", $key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new", $remote, "bash", "-s")
  $psi.Arguments = (($args | ForEach-Object { QuoteNative ([string]$_) }) -join " ")
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $psi.RedirectStandardInput = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = $psi
  if (-not $process.Start()) { throw "ssh process failed to start" }
  $outBytes = New-Object System.IO.MemoryStream
  $errBytes = New-Object System.IO.MemoryStream
  $outTask = $process.StandardOutput.BaseStream.CopyToAsync($outBytes)
  $errTask = $process.StandardError.BaseStream.CopyToAsync($errBytes)
  $inputBytes = [System.Text.Encoding]::UTF8.GetBytes($Script)
  $process.StandardInput.BaseStream.Write($inputBytes, 0, $inputBytes.Length)
  $process.StandardInput.Close()
  [void]$process.WaitForExit()
  [void]$outTask.GetAwaiter().GetResult()
  [void]$errTask.GetAwaiter().GetResult()
  $stdout = [System.Text.Encoding]::UTF8.GetString($outBytes.ToArray())
  $stderr = [System.Text.Encoding]::UTF8.GetString($errBytes.ToArray())
  $code = $process.ExitCode
  [void]$process.Dispose()
  if ($code -ne 0) { throw ("remote bash-s failed rc=" + $code + "; " + $stderr.Trim()) }
  return [pscustomobject]@{ stdout = $stdout; stderr = $stderr }
}

$records = @()
$controlRelative = SafeRelative ([string]$manifest.control_path)
$records += [pscustomobject]@{ Relative = $controlRelative; Local = (Resolve-Path -LiteralPath $ManifestPath).Path; Digest = (Hash $ManifestPath) }
foreach ($entry in @($manifest.files)) {
  $relative = SafeRelative ([string]$entry.path)
  $local = Join-Path $root $relative
  if ((Hash $local) -ne ([string]$entry.sha256).ToLowerInvariant()) { throw "local hash mismatch: $relative" }
  $records += [pscustomobject]@{ Relative = $relative; Local = $local; Digest = ([string]$entry.sha256).ToLowerInvariant() }
}

$checkLines = @("set -euf", ("root=" + $remoteRoot), ("mkdir -p " + $remoteRoot))
foreach ($record in $records) {
  $checkLines += ("if [ -e " + $remoteRoot + "/" + $record.Relative + " ]; then printf '%s\n' EXISTING_FILE >&2; exit 3; fi")
}
$checkLines += "printf '%s\n' REMOTE_PRECHECK_OK"
$check = InvokeRemoteScript ($checkLines -join "`n")
if ($check.stdout.Trim() -notmatch "REMOTE_PRECHECK_OK") { throw "remote preflight marker missing" }

$dirs = New-Object 'System.Collections.Generic.HashSet[string]'
foreach ($record in $records) {
  $slash = $record.Relative.LastIndexOf("/")
  if ($slash -gt 0) { [void]$dirs.Add($record.Relative.Substring(0, $slash)) }
}
$mkdirLines = @("set -euf", ("root=" + $remoteRoot))
foreach ($dir in $dirs) { $mkdirLines += ("mkdir -p " + $remoteRoot + "/" + $dir) }
[void](InvokeRemoteScript ($mkdirLines -join "`n"))

$scp = @("-P", $port, "-i", $key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new")
foreach ($record in $records) {
  & scp @scp $record.Local ($remote + ":" + $remoteRoot + "/" + $record.Relative)
  if ($LASTEXITCODE -ne 0) { throw "upload failed: $($record.Relative)" }
}

$verifyLines = @("set -euf", ("root=" + $remoteRoot))
foreach ($record in $records) {
  $verifyLines += ("actual=`$(sha256sum " + $remoteRoot + "/" + $record.Relative + " | cut -d' ' -f1); test `$actual = " + $record.Digest)
}
$verifyLines += "printf '%s\n' REMOTE_HASH_OK"
$verified = InvokeRemoteScript ($verifyLines -join "`n")
if ($verified.stdout.Trim() -notmatch "REMOTE_HASH_OK") { throw "remote hash marker missing" }
$count = $records.Count
Write-Output ("UPLOAD_AND_HASH_OK files=" + $count + " cells=1 concurrency=1 isolated=true krylovdim=12")
