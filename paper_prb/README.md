# Pentamer-chain manuscript: technical closeout, 2026-10-04

This is the active English manuscript in APS/PRB REVTeX 4-2 format.
The author, affiliation, contact, and funding placeholders are intentionally
retained at the user's request. No submission or public data release has occurred.

## Scientific scope

The main question is how the internal spin distribution of a pentamer changes
the relative visibility of physical momenta with the same cell momentum.
The paper does not claim a newly established thermodynamic phase.

- Local spin-1/2 and spin-3/2 projections fix the exchange and the probe's
  absolute normalization, including the factor F(q)/5.
- A two-cell ED test verifies the low-band weight vector and singlet-triplet
  gap at six predefined weak-domain points. The 0.27% weight bound is a
  relative L2 vector error, not a uniform pointwise relative error.
- The two user-selected L40 maps remain unchanged. They are finite-time,
  finite-coupling comparisons, outside that weak-domain test.
- Negative-coupling static data resolve a finite-size momentum reconstruction,
  not a common boundary interval or a complete thermodynamic phase diagram.
- Solver-controlled entropy and finite-window weight checks are in appendices.

## Build

From this directory:

    powershell -ExecutionPolicy Bypass -File .\build.ps1

Output: build/manuscript.pdf.
The existing build runs pdflatex, bibtex, and two further pdflatex passes.
A TeX installation with REVTeX 4-2 is required; the manuscript is a multi-file
project, not a standalone editor document.

## Layout

| File | Role |
|---|---|
| main.tex | title, abstract, front matter, data statement |
| sections/introduction.tex | question and literature context |
| sections/model_methods.tex | actual static/dynamical observables and methods |
| sections/results.tex | projection, ED test, spectra, finite-size reconstruction |
| sections/discussion.tex | physical interpretation and near-zero bulk/boundary limits |
| sections/conclusion.tex | bounded conclusions |
| sections/appendices.tex | selection rules, entropy controls, spectral/window checks |
| references.bib | citation library; only cited entries enter the PDF |
| FIGURE_SOURCES.md | current figure numbering and source index |
| cover_letter.txt | unsent draft; author attestations remain to be confirmed |

Main figures: model; two-cell quantitative projection; unchanged full-q pair;
discrete finite-size reconstruction. Appendix figures: local selection rules;
positive-coupling entanglement; negative-coupling entropy solver control.

## Integrity and baseline

The pre-rewrite main text and documentation are in revision_baseline_20261004.
The earlier 2026-10-02 baseline remains intact.
Historical data, unused figures, and the legacy CV comparison were not deleted.

The old CV plot is no longer used to validate the main spectra. Only two saved
CV solutions could be directly rechecked; both pass their residual threshold,
but a historical printed residual of zero was numerical cancellation.
The six previously missing k=12 terminal records and 42 raw run files were
recovered byte-for-byte from the local archive. These findings are documented
in ../docs/submission_provenance_audit_20261004.md.

No Gaussian image smoothing, image synthesis, momentum reflection averaging,
or manual retouching was applied to numerical figures.
The selected spectra have linear frequency axes and one shared asinh color
normalization. Display metadata belongs in captions, never a bottom-left footer.

## Source data and author-only release steps

A bounded source-data archive is prepared by
../scripts/submission_20261002/package_submission.py.
It contains figure data, relevant analysis/calculation code, environment records,
and checksums, not every historical checkpoint or wavefunction.
Its inventory and exclusions must be read before claiming full recomputation.
The local source-data archive is not a public repository or DOI.

Before actual submission the authors must review the scientific interpretation,
complete their retained identity/funding fields, choose the data-release route
and license, and verify journal attestations.
No authorship approval, exclusivity declaration, public release, or license
choice has been fabricated.

Relevant current policies (checked 2026-10-04):
- https://journals.aps.org/prb/authors
- https://journals.aps.org/authors/data-availability-statements

The scientific assessment and unresolved originality risk are summarized in
../docs/paper_closure_assessment_20261004.md.
