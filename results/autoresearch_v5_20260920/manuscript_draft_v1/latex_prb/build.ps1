$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $root "build"
New-Item -ItemType Directory -Force -Path $build | Out-Null
Copy-Item -LiteralPath (Join-Path $root "references.bib") -Destination $build -Force

Push-Location $root
try {
    pdflatex -interaction=nonstopmode -halt-on-error -jobname=manuscript -output-directory=build main.tex
    if ($LASTEXITCODE -ne 0) { throw "首次 LaTeX 编译失败" }

    Push-Location $build
    try {
        bibtex manuscript
        if ($LASTEXITCODE -ne 0) { throw "BibTeX 编译失败" }
    }
    finally {
        Pop-Location
    }

    pdflatex -interaction=nonstopmode -halt-on-error -jobname=manuscript -output-directory=build main.tex
    if ($LASTEXITCODE -ne 0) { throw "第二次 LaTeX 编译失败" }
    pdflatex -interaction=nonstopmode -halt-on-error -jobname=manuscript -output-directory=build main.tex
    if ($LASTEXITCODE -ne 0) { throw "最终 LaTeX 编译失败" }
}
finally {
    Pop-Location
}

Write-Host "已生成 build/manuscript.pdf"
