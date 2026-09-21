# PRB-style LaTeX manuscript

This directory is an independent submission-style LaTeX package. It does not modify the existing project-level `paper/` directory.

## Build

```powershell
PowerShell -ExecutionPolicy Bypass -File .\build.ps1
```

Output: `build/manuscript.pdf`.

## Format

- Class: `revtex4-2`
- Journal option: `aps,prb`
- Layout: `reprint` two-column
- Bibliography: BibTeX with the REVTeX APS style
- Figures: local copies under `figures/`

For a single-column author-review copy, replace `reprint` with `preprint` in `main.tex`.

## Required author edits

Replace the author name, email, affiliation, acknowledgments, CRediT statement, and internal data-availability wording before submission.
