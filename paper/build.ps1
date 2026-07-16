$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
    New-Item -ItemType Directory -Force build | Out-Null
    latexmk -xelatex -interaction=nonstopmode -halt-on-error main.tex
    Write-Output "完成：paper/build/main.pdf"
}
finally {
    Pop-Location
}
