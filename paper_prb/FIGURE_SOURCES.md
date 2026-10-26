# Figure Source Index, 2026-10-04

Paths are relative to the project root. Figure numbers refer to the rewritten
manuscript, not historical asset filenames. Original numerical data are retained.

| Figure | Manuscript asset | Primary source |
|---|---|---|
| 1 | paper_prb/figures/fig1_model_projection.png | figures/paper_fig1_model_local_multiplets_20260804.sources.json |
| 2 | paper_prb/figures/fig_projection_ed_benchmark.pdf | results/submission_20261002/local_projection/ and figures/submission_20261002_static/projection_qa.json |
| 3 left/right | paper_prb/figures/fig6_fullq_positive.pdf, fig6_fullq_negative.pdf | figures/fullq_visibility_clean_20261002/visibility_qa.json; production arrays below |
| 4 | paper_prb/figures/fig8_finite_size_reconstruction.pdf | figures/submission_20261002_static/qa.json and source/plotted CSVs |
| 5 (Appendix A) | paper_prb/figures/fig5_selection_rules.png | figures/paper_fig5_effective_chain_selection_rules_20260804.sources.json |
| 6 (Appendix B) | paper_prb/figures/fig4_entanglement.png | figures/paper_fig4_entanglement_spectrum_20260804.sources.json |
| 7 (Appendix C) | paper_prb/figures/fig9_entropy_solver_control.pdf | figures/submission_20261002_static/qa.json and entropy fit tables |

## Unchanged selected spectral images

| Item | SHA-256 |
|---|---|
| Positive PDF | b9afa7d66d49472adcc4ef175e576c3f0cff0c020b1237335869f9c10bc90b07 |
| Negative PDF | 8357daca9cffc7aad9b768d08128234b25dfd22d035f8db4b2276fbcfaa9266d |
| Positive spectrum CSV | 6a642e74b05b76694f2b22e1518fd4da025024d9537d69bb4e44c569b1b41c6d |
| Negative spectrum CSV | 66a2ea9e4a17e5bf86b3e489e456129f257a165fc6171a27d57adef59894e210 |

The arrays are in results/fullq_dsf_20261001/L40_positive/ and
L40_negative_local/. The no-footer/no-colorbar layout is preserved.
Shared mapping: asinh(s/0.02)/asinh(6/0.02), s=J1*Szz, range 0..6.
No per-energy or per-momentum normalization was introduced.

## Validation records

- Local projection: results/submission_20261002/local_projection/protocol.json,
  coupling_checks.csv, q_resolved_weights.csv, folded_prediction.csv, sha256.json.
- New figure QA: figures/submission_20261002_static/VISUAL_REVIEW_20261004.md.
- Single-variable dynamical controls:
  results/submission_20261002/dsf_controls/plan.json and dsf_audit/audit.json.
  The audit status, rather than file existence, determines completion.
- Frequency-window accounting:
  results/submission_20261002/window_audit/summary.json and selected_q.csv.
  A complete-period FFT identity is not independent physical validation.
- Historical k=12 recovery and two-point CV residual check:
  results/submission_20261002/provenance/audit.json and
  docs/submission_provenance_audit_20261004.md.
- Near-zero bulk-exchange ED source:
  see source-data inventory and the original near_zero_alpha_oracle records.

## Interpretation boundaries

Fig. 2 uses a full-vector relative error; dark momenta can have larger relative
pointwise errors. Fig. 3 does not validate weak-coupling formulas at beta=0.5.
Fig. 4 uses deterministic numerical tolerances, not statistical confidence
intervals, and no interpolated phase surface. Fig. 6 matches N pentamers to an
N-spin uniform reference, not equal physical-site lengths. Fig. 7 separates
historical k=3 sizes from the k=8 L80 endpoint; k=12 is described, not plotted.

Historical assets no longer cited: old positive phase map, repeated level-flow
plot, legacy CV/center-source comparison, and old Fig. 8/9 exports.
They remain in the project and baselines.
