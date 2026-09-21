param([Parameter(Mandatory=$true)][string]$Confirmation,[switch]$DryRun)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$stage="negative_phase_independent_pilot_r1"
if($Confirmation-ne("CONFIRM_"+$stage)){throw "Upload blocked"}
$root=(Get-Item $PSScriptRoot).Parent.Parent.FullName
$manifestPath=Join-Path $root "results/autoresearch_v5_20260913/negative_phase_independent_pilot_r1/server_upload_manifest.json"
$manifest=Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8|ConvertFrom-Json
if($manifest.cell_count-ne6-or$manifest.concurrency-ne1){throw "Manifest blocked"}
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
foreach($entry in $manifest.files){
  $path=Join-Path $root(([string]$entry.path)-replace'/','\')
  if((Hash $path)-ne([string]$entry.sha256)){throw "Hash mismatch: $($entry.path)"}
}
if($DryRun){"DRY_RUN_OK files=$($manifest.files.Count) cells=$($manifest.cell_count)";exit 0}
$remote="wangjieren@39.96.207.180"
$port="6000"
$key=Join-Path $env:USERPROFILE ".ssh\id_ed25519"
$remoteRoot=[string]$manifest.target
$ssh=@("-p",$port,"-i",$key,"-o","BatchMode=yes","-o","ConnectTimeout=15","-o","StrictHostKeyChecking=accept-new")
$scp=@("-P",$port,"-i",$key,"-o","BatchMode=yes","-o","ConnectTimeout=15","-o","StrictHostKeyChecking=accept-new")
& ssh @ssh $remote ("mkdir -p "+$remoteRoot)
if($LASTEXITCODE-ne0){throw "Remote root failed"}
foreach($entry in $manifest.files){
  $relative=[string]$entry.path
  $remotePath=$remoteRoot+"/"+$relative
  $parent=$remotePath.Substring(0,$remotePath.LastIndexOf('/'))
  & ssh @ssh $remote ("mkdir -p "+$parent)
  if($LASTEXITCODE-ne0){throw "Remote mkdir failed"}
  $got=((& ssh @ssh $remote ("sha256sum "+$remotePath+" 2>/dev/null"))-join"`n")
  if($LASTEXITCODE-eq0-and$got-match("^"+[string]$entry.sha256+"\s")){continue}
  $localPath=Join-Path $root($relative-replace'/','\')
  & scp @scp $localPath ($remote+":"+$remotePath)
  if($LASTEXITCODE-ne0){throw "Upload failed: $relative"}
}
foreach($entry in $manifest.files){
  $remotePath=$remoteRoot+"/"+[string]$entry.path
  $got=((& ssh @ssh $remote ("sha256sum "+$remotePath))-join"`n")
  if($LASTEXITCODE-ne0-or$got-notmatch("^"+[string]$entry.sha256+"\s")){throw "Remote hash failed: $($entry.path)"}
}
"UPLOAD_AND_HASH_OK files=$($manifest.files.Count) cells=$($manifest.cell_count)"
