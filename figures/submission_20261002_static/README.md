# Static figures for manuscript revision

These figures are rebuilt from existing numerical records, with no new DMRG
runs and no changes to source values. They replace the old manuscript Fig. 8
and Fig. 9. The two selected full-momentum spectra are not modified here.

The Python/matplotlib script is
`../../scripts/submission_20261002/plot_controlled_static.py`.
Run it from the project root with the project's Python environment.
Each figure is exported as PDF, editable-text SVG, and 400 dpi PNG at 7.2 inches
width. Input records are copied here as `source_*`; plotted data are available
as `fig8_*.csv` and `fig9_*.csv`. `qa.json` records hashes and numerical checks.

## Fig. 8

Use `fig8_finite_size_reconstruction.pdf`.
The three panels show the original 22 sampled parameter points, the same
dominant-ratio size differences, and the original eight candidate-interval
decisions. There is no interpolated phase surface or asserted thermodynamic
boundary. The previous categorical crossover title and footer are removed.

Suggested manuscript caption:

> Finite-size momentum reconstruction at negative intra-cell exchange.
> (a) Dominant momentum at $L=80$ for the sampled couplings; crosses mark
> disagreement of the momentum classification between $L=60$ and 80.
> Gray segments connect sampled points on a fixed-$\beta$ slice only.
> (b) Dominant-ratio size flow $\Delta R=R_{80}-R_{60}$.
> Error bars show the retained numerical tolerance $\epsilon$, obtained by
> quadrature of the two size-specific tolerances. Each size-specific tolerance
> is the larger of the initial-state half-range, ten times the maximum final
> truncation error, and $10^{-4}$; these are not statistical confidence intervals.
> Colored segments guide the eye between sampled couplings.
> (c) The eight candidate targets are evaluated for a momentum shift, a sign
> change satisfying $|\Delta R|\ge2\epsilon$ at both interval endpoints,
> interval width at most 0.025, and the joint momentum/size-flow criterion.
> No target satisfies the joint criterion. This operational test does not
> establish or rule out a thermodynamic phase transition.

The source calls the numerical two-error threshold `two_sigma_ratio_sign`.
The figure labels it $2\epsilon$ to avoid implying statistical sampling.
No threshold or decision value has been changed.

| Target | beta | Initial alpha interval |
|---|---:|---|
| 1 | 0.05 | [-0.05, -0.025] |
| 2 | 0.10 | [-0.10, -0.05] |
| 3 | 0.25 | [-0.25, -0.10] |
| 4 | 0.50 | [-0.35, -0.25] |
| 5 | 0.75 | [-0.50, -0.25] |
| 6 | 0.75 | [-0.75, -0.50] |
| 7 | 0.90 | [-0.75, -0.50] |
| 8 | 1.00 | [-0.75, -0.50] |

## Fig. 9

Use `fig9_entropy_solver_control.pdf`.
This figure replaces the previous four-panel historical size plot with direct
evidence for the entropy correction and its remaining finite-size limitation.

Suggested manuscript caption:

> Entropy-coefficient sensitivity to the eigensolver at $\beta=0.25$.
> All fits use period-10 bond-class intercepts.
> (a) Historical $k=3$ calculations at $L=40,60,80$ for $\alpha=-0.175$ and
> $-0.10$. Symbols are the means over two $S^z=0$ initial states at fixed
> fitting-window fraction $f=0.20$; vertical ranges cover both initial states
> and all four windows $f=0.10,0.15,0.20,0.25$.
> (b,c) Separate $L=80$ solver comparisons at the indicated couplings.
> Symbols show the two-initial-state mean at each fitting window and bars show
> the corresponding initial-state range for $k=3$ and $k=8$.
> The two solver symbols are shifted horizontally by $\mp0.002$ for visibility.
> The dotted line marks coefficient one as a reference, not a thermodynamic
> central-charge determination.
> Ranges are deterministic sensitivity intervals, not confidence intervals.
> The new $k=8$ results are not joined to the historical sizes; they do not
> constitute a solver-controlled finite-size sequence.

At $f=0.20$, the two-initial-state mean changes from 0.5331624818 to
0.9324647374 at $\alpha=-0.10$, and from 0.9165658764 to 0.9598967772 at
$\alpha=-0.175$. These numbers are independently consistent with both the
fit-level table and the finite-size-impact table within $10^{-12}$.
The two $k=8$ initial-state values differ by $3.3943\times10^{-8}$ and
$2.7880\times10^{-8}$, respectively. This is stability against those two
initial states at one solver setting, not convergence in system size or bond
dimension. No $k=12$ result is plotted.

Required associated text edits:

- Replace claims that Fig. 9 displays gaps, bond variation, and connected
  correlations: it now displays historical entropy-size sensitivity and the
  explicit solver comparison. Those other records remain in the source tables.
- Do not connect the old $L=40,60$ points to new $k=8$ $L=80$ data as a single
  controlled size trend.
- Use $2\epsilon$ numerical-tolerance language when explaining Fig. 8;
  the original source's `sigma` field is a value/error ratio, not a fitted
  statistical standard deviation.
- Describe the negative-region result as a finite-size reconstruction, with
  a crossover as one possible interpretation, rather than a settled phase.

## Checks

Both PNGs were inspected after rendering: axes, labels, legends, ranges, and
markers are visible without clipping or overlap. Neither figure contains a
bottom-left parameter footer. PDF and SVG preserve vector plot elements.

The selected original source hashes were checked before and after rendering;
they did not change. The historical provenance lists 52 upstream files: all
are present, 51 match their recorded hashes. The only changed hash belongs to
the current `static_krylov_candidate_adapter.py` analysis code, not a
measurement file. Its historical hash and current hash are both retained in
`qa.json`; no claim of historical code identity is made.

The numerical gates and fit comparisons are deterministic checks. They do not
replace renewed solver controls, longer chains, or thermodynamic extrapolation.
