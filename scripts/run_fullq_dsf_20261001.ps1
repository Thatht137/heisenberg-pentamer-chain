param([int]$Threads = 16, [ValidateSet('all', 'positive', 'negative', 'positive_check', 'negative_check')][string]$Case = 'all')

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$julia = (Get-Command julia.exe).Source
$python = Join-Path $root '.venv/Scripts/python.exe'
$runRoot = Join-Path $root 'results/fullq_dsf_20261001'
$env:JULIA_NUM_THREADS = [string]$Threads
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'

function Invoke-Case($Name, $Alpha, $Units, $Dt, $Time, $Chi, $QPoints, $GroundChi, $QValues) {
    $directory = Join-Path $runRoot $Name
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    if ($QValues) {
        $env:PENTAMER_FULLQ_VALUES = $QValues
    } else {
        Remove-Item Env:PENTAMER_FULLQ_VALUES -ErrorAction SilentlyContinue
    }
    $arguments = @('--startup-file=no', "--project=$root", (Join-Path $PSScriptRoot 'compute_fullq_dsf.jl'),
        $directory, $Alpha, $Units, $Dt, $Time, $Chi, $QPoints, $GroundChi)
    $process = Start-Process -FilePath $julia -ArgumentList $arguments -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $directory 'run.log') `
        -RedirectStandardError (Join-Path $directory 'error.log')
    $process.PriorityClass = 'BelowNormal'
    @{pid=$process.Id; start=$process.StartTime.ToString('o'); threads=$Threads; arguments=$arguments} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $directory 'process.json') -Encoding utf8
    Write-Output "START $Name pid=$($process.Id)"
    # 每个子任务有独立超时，已完成动量和断点可恢复。
    if (-not $process.WaitForExit(21600000)) {
        $process.Kill()
        throw "计算超时：$Name"
    }
    $process.Refresh()
    if ($process.ExitCode -ne 0) {
        throw "计算失败：$Name，查看 error.log"
    }
    Write-Output "DONE $Name"
}

if ($Case -eq 'positive') {
    Invoke-Case 'L40_positive' '0.5' 8 '0.05' 60 192 41 256 ''
    return
}
if ($Case -eq 'positive_check') {
    $env:PENTAMER_GROUND_SEED = Join-Path $runRoot 'L40_positive/ground.jld2'
    Invoke-Case 'L40_positive_check' '0.5' 8 '0.025' 60 256 5 256 '0.4,0.7,1.0,1.3,1.6'
    return
}
if ($Case -eq 'negative_check') {
    $env:PENTAMER_GROUND_SEED = Join-Path $runRoot 'spin_gap_L40/negative_seed.jld2'
    Invoke-Case 'L40_negative_check_local' '-0.5' 8 '0.025' 60 256 5 256 '0.4,0.7,1.0,1.3,1.6'
    return
}
if ($Case -eq 'negative') {
    $env:PENTAMER_GROUND_SEED = Join-Path $runRoot 'spin_gap_L40/negative_seed.jld2'
    Invoke-Case 'L40_negative_local' '-0.5' 8 '0.05' 60 192 41 256 ''
    return
}

Invoke-Case 'L40_positive' '0.5' 8 '0.05' 60 192 41 256 ''
Invoke-Case 'L40_negative' '-0.5' 8 '0.05' 60 192 41 256 ''
& $python (Join-Path $PSScriptRoot 'audit_fullq_dsf.py') --inputs `
    (Join-Path $runRoot 'L40_positive') (Join-Path $runRoot 'L40_negative')
if ($LASTEXITCODE -ne 0) { throw '初始谱验收未通过' }

Invoke-Case 'L40_positive_check' '0.5' 8 '0.025' 60 256 5 256 '0.4,0.7,1.0,1.3,1.6'
Invoke-Case 'L40_negative_check' '-0.5' 8 '0.025' 60 256 5 256 '0.4,0.7,1.0,1.3,1.6'
Invoke-Case 'tebd_check_L10_negative' '-0.5' 2 '0.05' 2 96 9 96 ''
& $python (Join-Path $PSScriptRoot 'audit_fullq_dsf.py') --ed-check `
    (Join-Path $runRoot 'tebd_check_L10_negative') --alpha '-0.5'
if ($LASTEXITCODE -ne 0) { throw '负参数 ED 对照未通过' }

& $python (Join-Path $PSScriptRoot 'audit_fullq_dsf.py') --inputs `
    (Join-Path $runRoot 'L40_positive') (Join-Path $runRoot 'L40_negative') --checks `
    (Join-Path $runRoot 'L40_positive_check') (Join-Path $runRoot 'L40_negative_check')
if ($LASTEXITCODE -ne 0) { throw '最终谱验收未通过' }
Write-Output 'ALL_FULLQ_CHECKS_PASSED'
