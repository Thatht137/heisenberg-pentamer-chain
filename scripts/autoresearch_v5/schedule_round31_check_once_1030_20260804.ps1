# 只等待到 10:30 北京时间并执行一次只读检查
$targetUtc = [datetime]::Parse('2026-08-04T02:30:00Z').ToUniversalTime()
$nowUtc = (Get-Date).ToUniversalTime()
$delay = [math]::Max(0, [int]($targetUtc - $nowUtc).TotalSeconds)
Start-Sleep -Seconds $delay
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$output = Join-Path $root 'results\research_progress\qpi_cv_extension_remote_status_20260804_1030.json'
$log = Join-Path $root 'results\research_progress\qpi_cv_extension_remote_check_1030_20260804.log'
$python = 'C:\Users\hh250\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python (Join-Path $PSScriptRoot 'check_qpi_cv_extension_remote_20260804.py') --output $output *> $log
exit $LASTEXITCODE
