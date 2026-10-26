# Manuscript verification, 2026-10-04

This is a technical verification record for the rewritten manuscript, not a
claim of acceptance, complete historical reproduction, or author approval.
Author/contact/funding placeholders are intentionally retained.

## Scientific checks actually performed

- The two-cell ED calculation was rerun in a fresh directory. The three
  numerical CSVs (coupling checks, all-q weights, folded predictions) are
  byte-identical to the original records. All predefined weak-domain checks pass.
- Twenty-three focused tests of the single-variable spectral audit pass,
  including wrong momentum grids, changed fixed parameters, mismatched source
  weights, incomplete outputs, and failed numerical thresholds.
- All 12 single-variable DSF comparisons pass the frozen criteria, with zero
  failures or pending cases. The maximum full/low spectral changes are
  0.8100%/0.8156%; the maximum relative band-weight change is 0.376% and norm
  drift is 0.338%. Sampled main-peak grid indices do not change. These are
  selected-momentum, fixed-L40, fixed-T60 controls, not all-q or long-time limits.
- The 82 saved production correlation records reconstruct the original spectral
  arrays to relative RMS error of order 1e-15. Their initial norms agree with an
  independent static contraction to within 5.60e-11 for nonzero sources.
- Discrete-period window-weight accounting is recorded separately from physical
  sum-rule validation. Negative-frequency leakage is not a negative excitation.
- The recovered k=12 records match historical checksums. Two available complete
  CV solutions pass explicit residual checks; the other nine historical CV
  frequencies were not directly reverified, and that legacy plot is not used.
- The abstract's 0.27% bound is a relative L2 weight-vector error, not a pointwise
  bound at dark momenta. Open-boundary near-zero-coupling terms are stated
  separately from the bulk second-order exchange.

## Figures and source preservation

The selected spectral PDFs remain byte-identical:
positive b9afa7d66d49472adcc4ef175e576c3f0cff0c020b1237335869f9c10bc90b07;
negative 8357daca9cffc7aad9b768d08128234b25dfd22d035f8db4b2276fbcfaa9266d.

No Gaussian smoothing, image synthesis, momentum interpolation, reflection
averaging, per-column normalization, or bottom-left parameter footer was added.
The shared asinh mapping is disclosed in the caption. Original numerical arrays
and pre-rewrite manuscript baselines remain intact.

## Build and reading checks

The multi-file project compiles using its existing REVTeX workflow.
The current text has 12 cited bibliography entries, no unresolved labels,
duplicate labels, missing citation keys, or PDF question-mark references.
A second reader inspected every page of the 12-page b1ee5eaf snapshot and found
no clipping or overlap. Its table/bibliography ordering issue was corrected:
a later rendered snapshot places the appendix table before the references.
The final 12-page PDF has SHA-256
e6d68fc15391e990d9b1d73289e5378f8224e312cfd4a50de1bb419fcf412766.
Its changed pages 10--12 were rendered and inspected after the last control
results were inserted: both control tables fit, references begin after the
appendix, and there is no clipping or overlap. Earlier pages retain the
previously inspected layout. There are seven numbered figures and three tables.
The final log has no overfull boxes, undefined references, duplicate labels,
or missing characters. REVTeX floatfix/nameref and spacing diagnostics remain;
successful placement was checked in the rendered PDF.

## Packaging and publication boundary

The package generator's synthetic safety, ZIP CRC, and payload-hash tests pass.
Portable Python and Julia copies are syntax-checked without running all legacy
drivers. The bounded data archive excludes wavefunctions, checkpoints, logs,
machine credentials, and unneeded historical figures. Historical source-code
hash differences are reported rather than concealed.

Author review of the scientific interpretation, closest literature,
data access/license, and submission attestations remains
necessary. No public deposit, DOI, submission, or author approval is claimed.
