$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $root "build"
New-Item -ItemType Directory -Force -Path $build | Out-Null
Copy-Item -LiteralPath (Join-Path (Split-Path -Parent $root) "references.bib") -Destination $build -Force
Copy-Item -LiteralPath (Join-Path $root "rank_references.bib") -Destination $build -Force
Push-Location $root
try {
    pdflatex -interaction=nonstopmode -halt-on-error -jobname=rank_manuscript -output-directory=build main.tex
    if ($LASTEXITCODE -ne 0) { throw "LaTeX first pass failed" }
    Push-Location $build
    try {
        bibtex rank_manuscript
        if ($LASTEXITCODE -ne 0) { throw "BibTeX failed" }
    }
    finally {
        Pop-Location
    }
    pdflatex -interaction=nonstopmode -halt-on-error -jobname=rank_manuscript -output-directory=build main.tex
    if ($LASTEXITCODE -ne 0) { throw "LaTeX second pass failed" }
    pdflatex -interaction=nonstopmode -halt-on-error -jobname=rank_manuscript -output-directory=build main.tex
    if ($LASTEXITCODE -ne 0) { throw "LaTeX final pass failed" }
}
finally {
    Pop-Location
}
