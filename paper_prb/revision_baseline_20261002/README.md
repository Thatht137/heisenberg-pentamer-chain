# PRB-format manuscript (REVTeX 4-2)

A self-contained APS/PRB manuscript for the spin-$1/2$ Heisenberg pentamer-chain
study. It does not modify the project-level `paper/` directory.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Output: `build/manuscript.pdf`

The build runs `pdflatex` → `bibtex` → `pdflatex` → `pdflatex`, so cross-references
and the numbered reference list resolve in one invocation.

## Layout

| File | Purpose |
|---|---|
| `main.tex` | preamble, title, abstract, front matter, section order |
| `sections/introduction.tex` | background, motivation, the three organizing results |
| `sections/model_methods.tex` | Hamiltonian, projection, acceptance gates, DSF, Krylov control |
| `sections/results.tex` | the six results subsections and Figs. 1–9 |
| `sections/discussion.tex` | tetramer contrast, near-zero mechanism, bounded negative-$\alpha$ reading |
| `sections/conclusion.tex` | conclusions |
| `references.bib` | 60-entry bibliography |
| `figures/` | the nine manuscript figures (PNG) |

Class options: `aps, prb, reprint, superscriptaddress, longbibliography,
nofootinbib, floatfix, showkeys`. For a single-column author-review copy, replace
`reprint` with `preprint`.

## Bibliography provenance

`references.bib` was not hand-typed. Metadata for every entry was harvested
programmatically from DOI content negotiation (Crossref) and cross-checked against
the publisher records; titles carrying inline MathML in the Crossref payload were
replaced with LaTeX-safe equivalents verified against the source PDFs. Citation
keys were then curated and every key is cited in the running text — the build
reports no uncited entries and no unresolved citations.

Bibliography hygiene notes for future edits:

- The APS style applies sentence case to titles. Any token whose capitalization
  matters (chemical formulas, acronyms, math symbols) must stay brace-protected,
  e.g. `{CuInVO}$_5$`, `{XXZ}`, `{O(3)}`, `{1-D}`, `{$J_1$}-{$J_2$}`.
- Do not leave a trailing period in `title` or `author` fields; BibTeX supplies
  the punctuation and a stray period renders as `Fe$_{18}$.,` and `Cardy.,`.

## Required author edits before submission

- Author names, affiliations, and the corresponding e-mail address.
- The `acknowledgments` block in `main.tex`.
- The `Data and code availability` statement: replace the internal archive wording
  with a public repository or archival DOI and an exact release identifier.

## Scope boundary

The manuscript deliberately reports a bounded result on the negative-$\alpha$
side — a finite-size momentum reconstruction, not a thermodynamic phase boundary.
If the claims are revised, update `sections/results.tex` Sec. III E–F,
`sections/discussion.tex` Sec. IV C, and the abstract together so that the
abstract, evidence, and conclusions stay consistent.
