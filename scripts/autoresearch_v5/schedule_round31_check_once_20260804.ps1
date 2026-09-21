# 只等待到指定时间并执行一次只读检查
# 02:09 北京时间等于 2026-08-03 18:09 UTC
$targetUtc = [datetime]::Parse('2026-08-03T18:09:00Z').ToUniversalTime()
$nowUtc = (Get-Date).ToUniversalTime()
$delay = [math]::Max(0, [int]($targetUtc - $nowUtc).TotalSeconds)
Start-Sleep -Seconds $delay
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$output = Join-Path $root 'results\research_progress\qpi_cv_extension_remote_status_20260804.json'
$log = Join-Path $root 'results\research_progress\qpi_cv_extension_remote_check_20260804.log'
$python = 'python'
& $python (Join-Path $PSScriptRoot 'check_qpi_cv_extension_remote_20260804.py') --output $output *> $log
exit $LASTEXITCODE
