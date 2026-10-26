$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $root "build"
New-Item -ItemType Directory -Force -Path $build | Out-Null
Copy-Item -LiteralPath (Join-Path $root "references.bib") -Destination $build -Force

Push-Location $root
try {
    pdflatex -interaction=nonstopmode -halt-on-error -jobname=manuscript -output-directory=build main.tex
    if ($LASTEXITCODE -ne 0) { throw "First LaTeX pass failed" }

    Push-Location $build
    try {
        bibtex manuscript
        if ($LASTEXITCODE -ne 0) { throw "BibTeX pass failed" }
    }
    finally {
        Pop-Location
    }

    pdflatex -interaction=nonstopmode -halt-on-error -jobname=manuscript -output-directory=build main.tex
    if ($LASTEXITCODE -ne 0) { throw "Second LaTeX pass failed" }
    pdflatex -interaction=nonstopmode -halt-on-error -jobname=manuscript -output-directory=build main.tex
    if ($LASTEXITCODE -ne 0) { throw "Final LaTeX pass failed" }
}
finally {
    Pop-Location
}

Write-Host "Built build/manuscript.pdf"
