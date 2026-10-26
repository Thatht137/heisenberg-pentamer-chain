# Retuned-weight comparison and validation limits

Panels a and b show **absolute**, unsmoothed microscopic integrated low-band weights for the same three-cell, 15-spin periodic geometry. Dashed curves keep alpha at the local root; solid curves use its predicted linear retuning. Panel a retains a local quartet at alpha = -0.3810345402 and q = 14pi/15; panel b retains a doublet at alpha = 1.4535291668 and q = 8pi/15. Both map to cell momentum 2pi/3. Each horizontal coordinate is g = beta/Delta_loc at its own root. The vertical scales differ and are logarithmic; the weights have NOT been normalized independently. Segments only join calculated points. The two Sz = 1/2 ground states are equally averaged and their entire subspace is excluded from the inelastic sum. The odd ring is frustrated.

Panel c shows the leading coefficient C_min at the exact quartet q = pi root for even effective chains, with microscopic probe normalization 1/sqrt(5N). ED points are effective-model results, not full 5N-site microscopic ED. N = 20 DMRG passed the fixed numerical gates; N = 40 failed the energy-per-cell gate and is marked as not converged. The zero at N = 4 PBC is retained. No bulk extrapolation or interpolation between ED and DMRG is supplied.

Panel d shows the leading-theory error against microscopic L = 20 OBC data: Euclidean line-weight-vector error and integrated-weight error. Larger-g points are deliberate failure checks. These axes are logarithmic. The repeated weakest calculation is recorded separately rather than duplicated as another visible point.

## Source mapping

- a,b: `same_ring_microscopic/comparisons.csv` and its summary.
- c ED: `effective_size_extension/size_checks.csv`.
- c DMRG: `effective_dmrg_refined/results.toml`, final chi = 256 entries.
- d: `microscopic_validity_v3/summary.json`, primary seed only.
- Plot: `scripts/submission_20261002/plot_rank_evidence.py`.

Paths above are relative to `results/novelty_20261004` except the plotting script, which is project-relative. Source and export hashes are in `sha256.json`. The plotting environment is the existing Python scientific environment; installed Python 3.12 is used only for standard-library TOML parsing. No smoothing, reflection averaging, intensity clipping, or fitted intensity normalization is used. 

Visual inspection: PNG checked for labels, bounds, and overlap. PDF and SVG are vector exports; parameters are in this caption rather than added as lower-left figure text.
