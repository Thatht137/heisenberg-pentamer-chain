# Two-cell projection benchmark

Use `fig_projection_ed_benchmark.pdf` for the manuscript. The SVG retains
editable text and the PNG is a 400 dpi preview. The plotting script is
`../../scripts/submission_20261002/plot_projection_validation.py`.
It only reads the existing exact-diagonalization records and performs display
and consistency checks; it does not run a new eigensolver calculation.

Suggested caption:

> Quantitative weak-coupling projection benchmark for two complete pentamers
> ($L=10$, open boundaries, $J_1=1$). (a,b) Low-band connected spectral weight
> at $\alpha=0.5$ and $-0.5$ for $g=\beta/\Delta_{\mathrm{loc}}=0.01$.
> Here $\Delta_{\mathrm{loc}}$ is the isolated-cell gap above the ground
> multiplet, and the low band is defined before diagonalization by
> $0<\omega<\Delta_{\mathrm{loc}}/2$.
> Circles are exact-diagonalization values at 41 independently evaluated
> momenta; lines join the first-order predictions at the same momenta,
> $W_{\mathrm{low}}(q)=F(q)s(s+1)[1-\cos(5q)]/15$, with
> $s=1/2$ and $3/2$, respectively.
> There is no fitted amplitude or per-momentum normalization.
> (c,d) Relative errors of the singlet--triplet gap and the full momentum vector
> of low-band weights at the five computed values of $g$.
> The gap error is $|\Delta_{\mathrm{ED}}/\Delta_{\mathrm{pred}}-1|$;
> the weight error is $\|\mathbf W_{\mathrm{ED}}-\mathbf W_{\mathrm{pred}}\|_2/
> \|\mathbf W_{\mathrm{pred}}\|_2$.
> Shading marks the predefined weak domain $g\le0.01$; connecting segments
> guide the eye and are not an additional coupling scan.
> This is a small-system benchmark. At the production value $\beta=0.5$,
> neither sign satisfies the predefined low-band separation test, so this
> figure does not assign the bands of the $L=40$ production spectra.

At $g=0.01$, the positive-coupling gap and weight errors are 0.3040% and
0.2643%; the negative-coupling errors are 0.5574% and 0.08842%.
The production $\beta=0.5$ corresponds to $g=1.4604$ and 3.9558, far outside
the predefined weak domain; those diagnostic points are not displayed on the
weak-coupling error axes. Their records remain in the source CSV.

The five source records are copied as `projection_source_*` and checksummed
in `projection_qa.json`. The exact plotted rows are also exported as
`projection_plotted_q_weights.csv` and `projection_plotted_coupling_errors.csv`.
The plotter recalculates the plotted full-$q$ weight error from the source
vectors and checks agreement with the independent summary within $10^{-12}$.
No smoothing, parameter footer, fitted amplitudes, or numerical interpolation
is used.

Suggested text integration: place this figure immediately after the weak-coupling
projection and folded response, before the finite-resolution production spectra.
It substantiates the leading projection in a controlled two-cell limit; it
cannot replace chain-length, long-time, or high-energy multiplet-assignment tests.
