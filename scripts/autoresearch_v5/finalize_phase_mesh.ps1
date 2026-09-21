param(
    [int]$PollSeconds = 300,
    [int]$MaxPolls = 288
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$run = Join-Path $root "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh"
$download = Join-Path $root "scripts/autoresearch_v5/download_phase_mesh_results.ps1"
$python = Join-Path $root ".venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $python = "python"
}
$env:PYTHONUTF8 = "1"
$log = Join-Path $run "finalize_phase_mesh.log"
$done = Join-Path $run "finalize_phase_mesh.done"

function Log([string]$Message) {
    $line = "[$(Get-Date -Format s)] $Message"
    Add-Content -LiteralPath $log -Value $line -Encoding UTF8
    Write-Output $line
}

if ($PollSeconds -lt 30 -or $MaxPolls -lt 1) {
    throw "PollSeconds must be >=30 and MaxPolls must be positive"
}

for ($poll = 1; $poll -le $MaxPolls; $poll++) {
    $fetchOutput = & $download 2>&1
    $fetchExit = $LASTEXITCODE
    $fetchOutput | ForEach-Object { Add-Content -LiteralPath $log -Value ([string]$_) -Encoding UTF8 }
    if ($fetchExit -ne 0) {
        Log "download failed; keep remote batch and retry (poll=$poll)"
        Start-Sleep -Seconds $PollSeconds
        continue
    }

    $status = Get-Content -LiteralPath (Join-Path $run "run_status.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    Log ("remote_status=" + [string]$status.status + " completed=" + @($status.completed).Count)
    if ($status.status -eq "failed") {
        Log "remote batch failed; inspect run_status.json and batch.stderr.log"
        exit 2
    }
    if ($status.status -ne "success") {
        Start-Sleep -Seconds $PollSeconds
        continue
    }

    $phase = Join-Path $run "phase-diagram"
    & $python scripts/autoresearch_v5/phase_diagram_windows_controller.py collect `
        --policy (Join-Path $phase "phase-policy.json") `
        --cells-dir (Join-Path $run "cells") `
        --output (Join-Path $phase "observations.json") | Add-Content -LiteralPath $log -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "collect failed" }
    & $python scripts/autoresearch_v5/merge_positive_mesh_observations.py | Add-Content -LiteralPath $log -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "merge failed" }
    & $python scripts/autoresearch_v5/phase_diagram_windows_controller.py check `
        --policy (Join-Path $phase "phase-policy.json") `
        --observations (Join-Path $phase "observations_merged.json") `
        --report (Join-Path $phase "report.json") | Add-Content -LiteralPath $log -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "controller check failed" }
    & $python scripts/autoresearch_v5/phase_diagram_windows_controller.py ingest `
        --policy (Join-Path $phase "phase-policy.json") `
        --state (Join-Path $phase "state.json") `
        --report (Join-Path $phase "report.json") | Add-Content -LiteralPath $log -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "controller ingest failed" }
    & $python scripts/autoresearch_v5/positive_phase_guard.py `
        --policy (Join-Path $phase "phase-policy.json") `
        --observations (Join-Path $phase "observations_merged.json") `
        --output (Join-Path $phase "positive_phase_guard.json") | Add-Content -LiteralPath $log -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "guard failed" }
    & $python scripts/autoresearch_v5/make_positive_mesh_summary.py | Add-Content -LiteralPath $log -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "summary failed" }
    & $python scripts/autoresearch_v5/update_positive_mesh_report.py | Add-Content -LiteralPath $log -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "report update failed" }
    & $python C:\Users\hh250\.codex\skills\report\render_report.py results/research_progress | Add-Content -LiteralPath $log -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "HTML render failed" }
    Set-Content -LiteralPath $done -Value (Get-Date -Format o) -Encoding UTF8
    Log "complete batch finalized: collect/merge/guard/summary/report succeeded"
    exit 0
}

Log "MaxPolls reached; remote batch is incomplete and no final report was generated"
exit 3
