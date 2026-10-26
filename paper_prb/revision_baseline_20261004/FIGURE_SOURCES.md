# Figure Source Index, 2026-10-02

Paths below are relative to the project root. This is an index of the assets in
the current manuscript, not a claim that every historical calculation has been
independently reproduced. Full computational settings remain in each source record.

| Manuscript figure | Source asset or provenance record | Scope |
|---|---|---|
| 1 | `figures/paper_fig1_model_local_multiplets_20260804.sources.json` | Model and isolated-cell levels |
| 2 | `figures/paper_fig2_level_flow_qpi_filter_20260804.sources.json` | Local level flow and spectral weights |
| 3 | `figures/paper_fig3_positive_groundstate_diagnostics_refined_20260808.sources.json` | Refined positive-region version, not the earlier 20260804 asset |
| 4 | `figures/paper_fig4_entanglement_spectrum_20260804.sources.json` | Entanglement and finite-size diagnostics |
| 5 | `figures/paper_fig5_effective_chain_selection_rules_20260804.sources.json` | Projection and isolated-cell selection rules |
| 6, left | `figures/fullq_visibility_clean_20261002/Sqw_L40_J2=0.5_J3=0.5_full_asinh.pdf` | Complete connected L40 positive spectrum |
| 6, right | `figures/fullq_visibility_clean_20261002/Sqw_L40_J2=-0.5_J3=0.5_full_asinh.pdf` | Complete connected L40 negative spectrum |
| 7 | `figures/round43_fig8_final_20260806_v2.sources.json` | Historical eleven-frequency CV/center-source TEBD comparison |
| 8 | `figures/negative_practical_v2_crossover_20260913/negative_alpha_crossover_summary.qa.json` | Finite-size negative-region reconstruction |
| 9 | `results/autoresearch_v5_20260919/closeout_stage1_joint_v2/summary.json` and `joint_size_evidence.csv` | Historical k=3 size series, not a controlled mixed-setting extrapolation |

## New Fig. 6

The two PDF panels and their PNG companions were copied without modification.
The selected layout has no parameter footer or colorbar; the shared asinh
mapping is disclosed in the caption. No spectrum was recomputed for insertion.

| Item | SHA-256 |
|---|---|
| Positive PDF | `b9afa7d66d49472adcc4ef175e576c3f0cff0c020b1237335869f9c10bc90b07` |
| Negative PDF | `8357daca9cffc7aad9b768d08128234b25dfd22d035f8db4b2276fbcfaa9266d` |
| Positive spectrum CSV | `6a642e74b05b76694f2b22e1518fd4da025024d9537d69bb4e44c569b1b41c6d` |
| Negative spectrum CSV | `66a2ea9e4a17e5bf86b3e489e456129f257a165fc6171a27d57adef59894e210` |

Spectra: `results/fullq_dsf_20261001/L40_positive/spectrum.csv` and
`results/fullq_dsf_20261001/L40_negative_local/spectrum.csv`.
Display metadata: `figures/fullq_visibility_clean_20261002/visibility_qa.json`.
Numerical checks: `figures/fullq_dsf_20261001/qa.json`.
Protocol: `docs/fullq_dsf_protocol_20261001.md`.

## Corrections and Open Issues

- Fig. 7 now matches the eleven-point caption. The copied PNG hash is
  `f73385a635e37ceebc54c575dfbaef72534f663c8d67cb2af55af0ffed1f7fc4`.
  Its local source table is `figures/round43_fig8_final_20260806_v2.source.csv`.
  This old comparison does not validate the new Fig. 6 protocol.
- Fig. 8 retains a historical in-panel crossover annotation. The manuscript
  limits the interpretation to finite-size reconstruction; a later source-based
  figure revision should use equally neutral wording.
- Fig. 9 needs a separately identified controlled endpoint from
  `results/autoresearch_v5_20260920/static_krylov_impact_v2/` before submission.
  Do not connect mixed k settings as a newly converged finite-size series.
- The six missing terminal k=12 records are listed in
  `results/research_progress/closeout_mechanism_source_data_audit_20260920.json`.
  The surviving historical closeout summary is not a replacement for those files.
- This is a local source index, not a public data release or license declaration.
