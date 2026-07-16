$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
    latexmk -C main.tex
    if (Test-Path build) {
        Remove-Item -LiteralPath build -Recurse -Force
    }
}
finally {
    Pop-Location
}
