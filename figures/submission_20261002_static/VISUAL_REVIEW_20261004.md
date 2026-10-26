# Figure acceptance review

Review date: 2026-10-04. Backend: the existing Python/matplotlib workflow.

## Result

The three figures below were opened and visually inspected, then regenerated
from the retained source records. All three regenerated PNG files were
byte-identical to the inspected previews. The two plotting scripts completed
successfully; no eigensolver, time evolution, or new parameter scan was run.

| Figure | Evidence role | Visual result |
|---|---|---|
| `fig_projection_ed_benchmark` | Absolute low-band weights and gap errors in the controlled two-cell weak-coupling regime | All four panels are legible, with no clipped labels, overlapping legends, or hidden data points. The two signs share the same weight and error scales. |
| `fig8_finite_size_reconstruction` | Existing finite-size momentum observations and operational candidate tests | All 22 sample points and eight candidate rows are visible. No interpolated phase region is drawn. |
| `fig9_entropy_solver_control` | Historical entropy estimates and a separate fixed-size solver comparison | The three historical sizes and the independent L=80 controls are separated. No mixed-solver size curve is drawn. |

All three figures have white backgrounds and no bottom-left parameter footer.
The selected full-momentum heatmaps are outside this review's edit scope and
were not modified.

## Reproducibility checks

- Every recorded plotting-input hash matched its current source file.
- The two plotter hashes and the projection plotter's export-helper hash matched
  the generated QA records.
- Every exported CSV and PDF/SVG/PNG hash matched its QA record before rerunning.
- Both plotters rechecked source hashes before and after rendering and the
  displayed quantitative values against the independently retained summaries.
- The three regenerated PNG hashes were identical to the previous previews.
  PDF/SVG export hashes are refreshed by the scripts; export metadata can change
  even when the plotted values and appearance do not.
- Each PDF has one page, with width 518.4 points (7.2 inches). The PDF text is
  extractable. The corresponding SVGs contain 44, 98, and 44 editable text
  elements for the projection, reconstruction, and entropy figures.
- The upstream static provenance inventory contains 52 present files. The 51
  recorded measurement/other matching files retain their hashes. The changed
  item is the historical analysis adapter, already identified in `qa.json`;
  historical code identity has not been asserted.

The generated `qa.json` and `projection_qa.json` deliberately retain the status
`rendered_for_visual_review`: rendering alone cannot certify human/model visual
inspection. This separate record documents the completed visual review of the
byte-identical PNGs. It is not a scientific-convergence certificate.

## Scientific limits for integration

1. The projection benchmark is L=10 with open boundaries. The upper panels use
   the predefined g=0.01 point; the lower panels contain five computed g values,
   not an interpolated numerical scan. At g=0.01, positive/negative gap errors
   are 0.3040%/0.5574% and weight-vector errors are 0.2643%/0.08842%.
   The beta=0.5 diagnostics fail the predefined low-band separation test for
   both signs. Do not use the benchmark to assign the production heatmap bands.
2. The reconstruction figure records finite-size diagnostics. Failure of the
   joint criterion neither establishes nor excludes a thermodynamic transition.
   Its error bars are retained numerical tolerances, not statistical confidence
   intervals.
3. The entropy figure shows entropy coefficients only. It no longer displays
   gaps, bond observables, or correlation functions. The k=8 L=80 controls must
   not be combined with k=3 L=40,60 as a uniformly controlled size sequence.
   The coefficient-one line is a reference, not a central-charge determination.

## Suggested manuscript hierarchy

The existing model/topology figure can remain as the entry point. The positive
isolated-cell level scan duplicates parts of the model spectrum and selection
rule figure, while the ten entanglement-cut panels are secondary diagnostics;
they can move to supplementary material. The new absolute-weight benchmark
should appear immediately after the projected-response derivation and before
the finite-resolution production spectra.

If the older selection-rule composite remains, its repeated model sketch is
redundant with the model entry figure. Its five sampled momenta joined by line
segments must not be presented as a fully resolved momentum response. Its
isolated-cell selection rules are not exact full-chain branch assignments.
