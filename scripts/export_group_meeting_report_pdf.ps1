$ErrorActionPreference = "Stop"

$root = Split-Path $PSScriptRoot
$docs = Join-Path $root "docs"
$output = Join-Path $docs "group_meeting_report_20260723.pdf"
$source = "group_meeting_report_20260723.tex"

Push-Location $docs
try {
    lualatex `
        --shell-escape `
        -interaction=nonstopmode `
        -halt-on-error `
        $source
    if ($LASTEXITCODE -ne 0) {
        throw "First LuaLaTeX pass failed"
    }

    lualatex `
        --shell-escape `
        -interaction=nonstopmode `
        -halt-on-error `
        $source
    if ($LASTEXITCODE -ne 0) {
        throw "Second LuaLaTeX pass failed"
    }
}
finally {
    Pop-Location
}

$log = Join-Path $docs "group_meeting_report_20260723.log"
$layoutIssues = Select-String `
    -Path $log `
    -Pattern "Overfull|Float too large|Undefined control sequence"
if ($layoutIssues) {
    $layoutIssues | ForEach-Object { Write-Error $_.Line }
    throw "PDF layout or compilation check failed"
}

$auxiliary = @(
    "group_meeting_report_20260723.aux",
    "group_meeting_report_20260723.log",
    "group_meeting_report_20260723.out"
)
foreach ($name in $auxiliary) {
    $path = Join-Path $docs $name
    if (Test-Path $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

Get-ChildItem -LiteralPath $docs -Directory |
    Where-Object { $_.Name -like "_markdown_*" } |
    ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force
    }

Write-Output "Completed: $output"
