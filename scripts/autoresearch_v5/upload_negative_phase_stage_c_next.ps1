param(
    [Parameter(Mandatory=$true)][string]$StageDir,
    [Parameter(Mandatory=$true)][string]$Confirmation,
    [switch]$DryRun
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
if($Confirmation-ne"CONFIRM_NEGATIVE_STAGE_C_NEXT"){throw "Upload blocked: confirmation required."}
if($StageDir-notmatch'^stage-c-negative-refine-r[2-9][0-9]*$'){throw "StageDir 非法"}
$root=(Get-Item $PSScriptRoot).Parent.Parent.FullName
$base="results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/"+$StageDir
$manifestPath=Join-Path $root (($base+"/server_upload_manifest.json")-replace'/','\')
$m=Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8|ConvertFrom-Json
if($m.launch_ready-ne$true-or$m.cell_count-lt1-or$m.concurrency-ne1-or$m.stop_on_first_failure-ne$true-or$m.stage_b_complete-ne$true){throw "Upload blocked"}
if([string]$m.run_rel-ne$base){throw "run_rel 不匹配"}
function Hash([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
foreach($e in $m.files){$p=Join-Path $root(([string]$e.path)-replace'/','\');if((Hash $p)-ne([string]$e.sha256)){throw "Hash mismatch: $($e.path)"}}
if($DryRun){"DRY_RUN_OK files=$($m.files.Count) cells=$($m.cell_count)";exit 0}
$remote="wangjieren@39.96.207.180";$port="6000";$key=Join-Path $env:USERPROFILE ".ssh\id_ed25519";$rr=[string]$m.target
$ssh=@("-p",$port,"-i",$key,"-o","BatchMode=yes","-o","ConnectTimeout=15","-o","StrictHostKeyChecking=accept-new")
$scp=@("-P",$port,"-i",$key,"-o","BatchMode=yes","-o","ConnectTimeout=15","-o","StrictHostKeyChecking=accept-new")
& ssh @ssh $remote ("mkdir -p "+$rr);if($LASTEXITCODE-ne0){throw "Remote root failed"}
foreach($e in $m.files){
    $rel=[string]$e.path;$rp=$rr+"/"+$rel;$parent=$rp.Substring(0,$rp.LastIndexOf('/'))
    & ssh @ssh $remote ("mkdir -p "+$parent);if($LASTEXITCODE-ne0){throw "Remote mkdir failed"}
    $got=((& ssh @ssh $remote ("sha256sum "+$rp+" 2>/dev/null"))-join"`n")
    if($LASTEXITCODE-eq0-and$got-match("^"+[string]$e.sha256+"\s")){continue}
    $lp=Join-Path $root($rel-replace'/','\');& scp @scp $lp ($remote+":"+$rp)
    if($LASTEXITCODE-ne0){throw "Upload failed: $rel"}
}
foreach($e in $m.files){$rp=$rr+"/"+[string]$e.path;$got=((& ssh @ssh $remote ("sha256sum "+$rp))-join"`n");if($LASTEXITCODE-ne0-or$got-notmatch("^"+[string]$e.sha256+"\s")){throw "Remote hash failed: $($e.path)"}}
"UPLOAD_AND_HASH_OK files=$($m.files.Count) cells=$($m.cell_count)"
