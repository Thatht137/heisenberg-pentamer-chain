# Figure Caption

**Local cancellation and residual low-energy response in a pentamer chain.**
(a) Signed amplitude Aπ of the isolated-cell ground-quartet projection. The analytic expression crosses zero at α*=−(2+√7)/6 while the effective exchange remains finite.
(b) Relative error of the integrated low-energy weight predicted by the leading effective observable against microscopic exact diagonalization of four pentamers (20 spin-1/2 sites, open boundaries). β=J3/J1, J1=1, g=β/Δlocal, and Δlocal=0.1662215475 is held at α*. Blue: fixed α*. Red: α=α*+κ*β, with κ*=1.052179596 computed from the effective-chain ground state. The fixed energy window is 0<ω<Δlocal/2. Both initial points above the prespecified 5% gate are retained. Lines between sampled points are guides, not fitted curves.
(c) Unbroadened spectral lines after retuning, comparing the leading effective observable with the microscopic g=0.0025 calculation. Weights are divided by β², not independently normalized. All 44 low-band states, including zero-weight levels, are displayed. Integrated-weight error is 0.653%; the relative Euclidean difference of the sorted line-weight vectors is 4.973%. No smoothing or interpolation of spectral lines is used.
(d) Leading residual coefficient after optimizing the single detuning parameter at q=π, calculated in effective spin-3/2 chains. OBC and PBC denote open and periodic boundaries. The four-cell periodic zero is retained. These are effective-chain results through ten cells, not microscopic 50-spin ED; no thermodynamic extrapolation is asserted.

All results are deterministic zero-temperature calculations. No sampling error bars, experimental replicates, statistical significance tests, or p-values apply. Numerical eigen-residuals and perturbative discrepancies are recorded separately. The operator normalization is Oq=Σj exp(iqj) Szj/√L, with its ground-state expectation removed.

# Figure QA

- Existing Python/matplotlib workflow; quantitative four-panel grid.
- Dimensions: 181.61 × 138.43 mm; vector PDF and editable-text SVG; 300 dpi PNG preview.
- Arial text, 8 pt base size; circle/square/plus encodings supplement colors.
- PNG visually inspected: no overlapping axes, legends or clipped labels.
- No image generation, spatial filtering, Gaussian smoothing, symmetry averaging, gamma enhancement, or local contrast adjustment.
- No bottom-left parameter footer. Original full-spectrum images are unchanged.
- This is a research-evidence figure, not a claim of final journal compliance or acceptance.

# Data Mapping

Paths below are relative to the current research-results directory.

- Panel a: `evidence_figures/local_amplitude.csv`; analytic one-flip expression checked against seven independent local diagonalizations.
- Panel b: `microscopic_four_cells/comparisons.csv` and `microscopic_retuning_v2/comparisons.csv`.
- Panel c: `dark_operator/effective_spectra.csv` and `microscopic_retuning_v2/spectral_lines.csv`.
- Panel d: `effective_size_extension/size_checks.csv`.
- Diagnostics: `evidence_figures/spectral_comparison.json`.
- Provenance: each calculation directory contains its protocol, outputs, and SHA-256 records. No failed run was replaced with a successful one.
