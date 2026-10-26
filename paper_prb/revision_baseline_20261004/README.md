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
| `figures/` | manuscript figures; Fig. 6 uses two PDF panels with PNG companions |

Class options: `aps, prb, reprint, superscriptaddress, longbibliography,
nofootinbib, floatfix`. For a single-column author-review copy, replace
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

## 2026-10-02 figure and evidence revision

Figure 6 now places the two selected full-spectrum panels side by side:
`figures/fig6_fullq_positive.pdf` and `figures/fig6_fullq_negative.pdf`.
They correspond to $J_2/J_1=0.5$ and $-0.5$ at $J_3/J_1=0.5$ and $L=40$.
The PDF and PNG files were copied byte for byte from the selected clean exports;
the axes, in-panel coupling labels, colors, and full energy range are preserved.
There is no parameter footer or added in-panel text. Processing information is
in the manuscript caption and methods.

The figure's role is a comparison of two finite-chain connected spectra at the
same numerical and display settings. Its two-panel quantitative-grid layout
supports a comparison of spectral-weight distributions, not a phase boundary,
resolved sub-linewidth gaps, or a proven local-multiplet assignment.
The existing Python/matplotlib workflow supplies the figure assets; this revision
does not redraw or retouch them. The PDF containers retain vector axes and text
with a rasterized heatmap. The selected no-colorbar layout is retained; the
caption explicitly discloses the common nonlinear mapping, and the source figure
directory also retains calibrated-colorbar versions for quantitative comparison.

The current estimator uses the full connected momentum operator, 41 independently
evolved momenta, $TJ_1=60$, $\Delta tJ_1=0.05$, $\chi=192$, and a triangular
time window. It differs from the previous Fig. 6 center-source approximation.
Five momentum sources are checked jointly at $\Delta tJ_1=0.025$, $\chi=256$;
this is not a full-grid or independent error extrapolation.
The window FWHM is $0.09277J_1$.
For $s=J_1S_T^{zz}$ the common display map is
$u=\operatorname{asinh}(s/0.02)/\operatorname{asinh}(6/0.02)$, with $0\le s\le6$.
No smoothing, interpolation, reflection averaging, or spectral-data modification
was performed. Fig. 7 is retained only as the earlier $\alpha=0.23$,
$q=\pi$ benchmark using a center-source spatial-window approximation; it does not
validate the new complete-momentum maps.

Internal data and provenance records remain in the project:

- `../figures/fullq_visibility_clean_20261002/README.md` and
  `visibility_qa.json`: selected figure settings and source checksums.
- `../figures/fullq_dsf_20261001/qa.json` and `report.md`: numerical checks.
- `../results/fullq_dsf_20261001/L40_positive/spectrum.csv`: positive panel.
- `../results/fullq_dsf_20261001/L40_negative_local/spectrum.csv`: negative panel.
- `revision_baseline_20261002/`: the pre-revision text and previous Figs. 6 and 7.

The positive and negative spectrum SHA-256 values are, respectively,
`6a642e74b05b76694f2b22e1518fd4da025024d9537d69bb4e44c569b1b41c6d` and
`66a2ea9e4a17e5bf86b3e489e456129f257a165fc6171a27d57adef59894e210`.
This revision adds no numerical runs. It also corrects the endpoint-parity sign
argument, distinguishes physical $q$ from cell momentum $Q=5q\bmod2\pi$, limits
the quartet shape-factor statement to the folded antiferromagnetic replicas,
excludes decoupled axes from the positive-region boundary claim, and limits the
single-point Krylov control to the endpoint actually tested.

### Audit findings requiring follow-up

- Fig. 7 used the obsolete seven-point bounded comparison despite an eleven-point
  caption. It now uses the existing `../figures/round43_fig8_final_20260806_v2.png`,
  whose source CSV and provenance sidecar are present and checksum-verified.
- Fig. 5 contains projection coefficients and local selection rules, not plotted
  continuum bounds; its caption and citation in the text now describe its actual panels.
- Fig. 9 still shows the historical `k=3` size series. Its caption states this;
  the next scientific figure revision should display the saved `k=8` endpoint
  separately rather than treat mixed solver settings as a converged size sequence.
- Six terminal `k=12` fetch/finalize records listed by the 2026-09-20 closeout audit
  are missing locally. The historical summary remains, but those files must be
  restored and verified before submission. The methods now disclose this limitation.
- Author, affiliation, funding, public archive/release, and license information
  remain unfinished. Bibliographic metadata were not all re-audited in this revision.

The prioritized evidence and computation plan is in
`../docs/manuscript_completion_assessment_20261002.md`. No new large calculation
was launched as part of this manuscript assessment.

### Build and visual checks

The revised manuscript compiled successfully to `build/manuscript.pdf` (15 pages).
Fig. 6 appears on page 9. Poppler page renders were inspected; the final changed
captions were checked again. No clipping, overlapping text, blank figures,
undefined references/citations, or overfull boxes were found.
Non-blocking REVTeX/nameref, BibTeX `jnrlst`, and underfull-spacing warnings remain.
The final PDF SHA-256 is
`65fe2568df63a503f09fbd101a2abe02bb6b6ebbea180d292b72a362b44b58d5`.
See `FIGURE_SOURCES.md` for the current figure-source index.
This build verification does not close the scientific and source-archive gaps above.
