# Results draft for the `beta=0.5` cut

> **Revision hold (2026-07-15):** A pilot `L=40`, `tmax=15` DSF scan
> finds low-frequency spectral weight near `q=3pi/5` at
> `alpha=-0.50`. The negative-`alpha` bulk gap has not yet been
> extrapolated. Do not finalize the separation into an SPT-like
> negative side and a uniquely gapless positive side until negative-side
> spin-gap, correlation and DSF size scaling are completed.

## Scope

This draft describes only the one-dimensional parameter cut
`beta=J3/J1=0.5`. It does not establish the complete two-dimensional
phase diagram.

## One-sentence argument

At `beta=0.5`, distance-resolved string correlations, edge
magnetization, entanglement spectra, spin-gap scaling and real-space
correlations consistently separate an SPT-like negative-`alpha`
regime from a gapless positive-`alpha` regime at the decoupled point
`alpha=0`, while the two response maxima inside the positive-`alpha`
region are finite-size crossover scales rather than boundaries of an
additional phase.

## Terminology ledger

| Canonical term | Symbol or definition | Usage boundary |
|---|---|---|
| pentamer chain | five-site unit-cell Heisenberg chain | Use throughout |
| coupling ratios | `alpha=J2/J1`, `beta=J3/J1` | Define on first use |
| string correlator | `O_str(d)` | Do not call long-range order before distance and size scaling |
| staggered string envelope | `(-1)^((d-1)/2) O_str(d)` for odd unit-cell distance | Even distances vanish by spin-inversion parity |
| SPT-like regime | negative-`alpha` region with string order and edge response | Avoid definitive SPT classification until a full projective-symmetry invariant is calculated |
| gapless regime | positive-`alpha` region with vanishing spin gap and algebraic correlations | Supported on the sampled `beta=0.5` cut |
| edge weight | magnetization in the first and last ten sites in the total-`Sz=1` sector | Fixed-width finite-size diagnostic |
| response scale | maximum in an observable derivative or curvature | Do not automatically call a phase boundary |

## Section outline

1. Establish the `alpha=0` separation using distance-resolved string order.
2. Identify edge and entanglement signatures on the negative-`alpha` side.
3. Establish gapless algebraic correlations on the positive-`alpha` side.
4. Test and reject the candidate intermediate fourth phase.
5. Verify the near-zero boundary using multistart and parameter-continuation DMRG.

## Draft

### String correlations separate the two sides of `alpha=0`

We first examined the string correlator as a function of both
unit-cell separation and system size at fixed `beta=0.5`. Spin
inversion forces the correlator to vanish at even unit-cell
separations, whereas the odd-distance values form a staggered
envelope. For `alpha=-0.50`, the longest-distance central values
decreased from `0.137` at `L=60` to `0.122` at `L=100`, and a linear
extrapolation in inverse distance gave a finite intercept of
approximately `0.113`. A finite envelope was also obtained close to
the decoupled point at `alpha=-0.05`, where the corresponding
intercept was approximately `0.079`. By contrast, the envelope at
`alpha=0.05` and `0.50` decreased rapidly with increasing distance
and system size and extrapolated to zero. These results place the
loss of long-range string correlations at `alpha=0` on the
`beta=0.5` cut.

### The negative-`alpha` regime supports localized edge degrees of freedom

We next tested whether the finite string envelope was accompanied by
boundary degrees of freedom. In the total-`Sz=1` sector, the
magnetization profile at `alpha=-0.50` was concentrated at the two
open ends, and the cumulative magnetization approached approximately
`1/2` from each boundary. The combined magnetization within the first
and last ten sites was `0.879`, `0.858` and `0.849` for
`L=40`, `60` and `80`, respectively. A power-law fit of this
fixed-width edge weight gave a size exponent of only `0.05`, showing
that the boundary contribution remained finite over the accessible
sizes. In comparison, the same edge weight decreased with exponents
of approximately `0.73` and `0.86` at `alpha=0.14` and `0.33`.

Cut-resolved entanglement spectra provided a complementary
diagnostic. At `alpha=-0.50`, the unit-cell boundary cut contained a
low-lying singlet--triplet cluster with Schmidt
`Sz=0,+1,0,-1`, consistent with the boundary-state manifold observed
in the real-space magnetization. The exact degeneracies on the
positive-`alpha` side instead followed conventional SU(2)
multiplets, demonstrating that degeneracy alone is not a sufficient
topological criterion. Taken together with the finite string
envelope, the localized boundary magnetization and the low-lying
entanglement cluster support an SPT-like interpretation of the
negative-`alpha` regime. A definitive symmetry-protected
classification will require an explicit projective-symmetry
invariant.

### The positive-`alpha` regime is gapless and algebraically correlated

The positive-`alpha` side showed a qualitatively different finite-size
response. Spin gaps calculated for `L=40`, `60` and `80` at
`alpha=0.10`, `0.20`, `0.25`, `0.30`, `0.40` and `0.50`
all extrapolated to values close to zero. The real-space spin
correlator also followed an algebraic envelope. Fits to
$(-1)^r C(r)\propto r^{-\eta}$ at `L=80` gave
`eta=0.978(64)`, `0.962(37)` and `0.948(20)` for
`alpha=0.14`, `0.23` and `0.33`, respectively. The exponent varied
smoothly across the candidate intermediate region, and the power-law
fit became increasingly favorable over an exponential fit as the
system size increased.

Static structure factors at the same three representative couplings
all exhibited a single dominant peak at `q/pi=1`. The peak amplitude
increased continuously from `3.390` to `4.065`, without peak
splitting or a shift to an incommensurate wave vector. The vanishing
spin gap, nearly continuous correlation exponent and unchanged
dominant wave vector identify the sampled positive-`alpha` region as
one broadly gapless antiferromagnetic regime.

### Response maxima inside the gapless regime do not define a fourth phase

Several finite-size observables nevertheless developed distinct
response maxima. The ground-state energy curvature peaked near
`alpha=0.17`, whereas the entanglement response peaked near
`alpha=0.30`. We therefore tested the interval between these scales
using local bond correlations, spin gaps, correlation exponents and
static structure factors. The three independent bulk bond classes
changed smoothly throughout the interval, and the differences
between left and right `J1` or `J2` bonds remained at the numerical
level of approximately `10^-9` to `10^-7`. No spontaneous
dimerization, bond reordering, finite spin gap or momentum-space
reconstruction was detected.

The two maxima are therefore not accompanied by independent
thermodynamic or structural signatures. Within the current system
sizes, they are more consistently interpreted as observable-dependent
crossover scales inside a single gapless regime. This conclusion does
not exclude a transition between two gapless phases in principle, but
such a claim would require a change in a universal quantity, symmetry
sector or topological invariant that is absent from the present data.

### Parameter-continuation DMRG fixes the near-zero numerical ambiguity

Independent DMRG calculations close to `alpha=0` initially showed
strong dependence on whether the additional magnetization was placed
at the center, left edge or right edge of the initial state. Because
the left- and right-edge states must be related by inversion, their
energy difference provided a direct convergence diagnostic. In
independent runs, this difference reached $10^{-4}$ to
$5\times10^{-4}$, explaining the asymmetric profile obtained at
`alpha=-0.05`.

We removed this bias by converging left- and right-edge branches at
`alpha=-0.15` and then reusing each MPS while continuously increasing
`alpha` to `-0.00625`. The branch-energy difference was reduced to
$10^{-12}$--$10^{-9}$, and the root-mean-square difference between one
profile and the reflected partner remained below
$7.5\times10^{-4}$. Over the same scan, the ten-site edge weight
increased smoothly from `0.904` to `0.931`, with no hysteresis or
collapse on the negative side. The continuous calculation therefore
locates the separation between the edge-state and gapless regimes at
the special decoupled point `alpha=0` for `beta=0.5`.

## Proposed figure sequence

| Figure | Main conclusion | Existing panels or source |
|---|---|---|
| Figure 1 | Overview of the numerical phase diagnostics | `phase_diagram_dense_signed`, energy/string/entropy response |
| Figure 2 | Negative `alpha` has finite string order and boundary response | string-distance scaling, edge magnetization, Schmidt-sector spectrum |
| Figure 3 | Positive `alpha` is broadly gapless | spin-gap scaling, algebraic correlations, static structure factor |
| Figure 4 | The apparent intermediate region is a crossover | bond correlations, response peaks, continuation diagnostics |

## Claim-evidence map

| Claim | Evidence | Status |
|---|---|---|
| Long-range string correlations survive for negative `alpha` | Distance and size scaling at `alpha=-0.50,-0.05` | supported on sampled points |
| Deep negative `alpha` carries localized edge degrees of freedom | Edge-weight size scaling and cumulative `Sz` | supported |
| Negative `alpha` is SPT-like | String order, edge response and entanglement cluster | supported but not a complete invariant |
| Positive `alpha` is gapless | Spin-gap extrapolation and algebraic correlations | supported on sampled points |
| `0.17<alpha<0.30` is not a conventional fourth phase | No gap, dimerization, bond reconstruction or wave-vector shift | supported |
| The boundary on the `beta=0.5` cut is `alpha=0` | String-order contrast and continuous DMRG to `alpha=-0.00625` | strongly supported at finite size |
| The full two-dimensional diagram contains only three phases | Not established by this cut alone | needs additional `beta` cuts |

## Assumptions or missing inputs

- The target journal and final Results word limit have not been chosen.
- A complete projective-symmetry or topological invariant has not yet
  been calculated.
- The central-charge estimate from single-size entanglement profiles
  is too uncertain for a main claim.
- The full two-dimensional phase structure requires at least two or
  three additional `beta` cuts.
- Figure numbers are provisional and should be updated after the main
  multi-panel layout is fixed.

## 中文写作说明

- 本稿只写 `beta=0.5` 截面，没有把全局“三相”结论提前写死。
- Results 中先写直接观测，再写有限尺寸验证，最后才给出受限制的
  相解释。
- 负 `alpha` 使用 `SPT-like`，而不是直接写成已经严格证明的
  Haldane 相。
- `alpha≈0.17` 和 `0.30` 被称为 response scales，而不是相界。
- 后续新增其他 `beta` 截面后，可以把本稿扩展成完整相图 Results。
