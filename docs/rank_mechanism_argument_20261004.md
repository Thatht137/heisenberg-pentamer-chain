# Rank-dependent compensation: argument and evidence

## One-sentence argument

In an SU(2)-invariant Heisenberg pentamer chain, a tunable zero of the projected spin probe exposes intercell corrections: a single isolated spin-1/2 cell multiplet permits cancellation of the entire first-order probe on a uniform inversion-symmetric periodic chain, whereas a spin-3/2 multiplet permits a quadrupole-times-spin vector and a state-dependent, nonzero residual, as checked by microscopic finite-ring diagonalization and separate even-chain effective calculations.

This is a candidate research contribution, not a priority claim, an acceptance prediction, or a new universal theorem.

## Terminology

| Symbol / term | Meaning |
|---|---|
| L = 5N | Microscopic spin-1/2 sites; N is the number of pentamers |
| alpha = J2/J1; beta = J3/J1 | Dimensionless intra-cell outer bond and intercell bond; J1 = 1 |
| s | Spin of one isolated, non-repeated ground multiplet |
| Delta_loc | Gap above that entire local multiplet |
| g = beta/Delta_loc | Small parameter at the unshifted compensation point |
| q; Q = 5q mod 2pi | Physical-site and cell momenta |
| A(q,alpha) | Real, center-referenced local projected amplitude |
| D_Q | Sum exp(i Q n) T_n^z / sqrt(5N), not /sqrt(N) |
| K_q | Coefficient of beta in the effective probe at A = 0 |
| W_low | Inelastic low-band weight, excluding the entire ground eigenspace |
| retuning | Physical change alpha = alpha_* + kappa beta; not data rescaling |
| composite vector | Q_n^{z mu} T_{n+1}^mu; total spin rank one |
| O(beta^4) | Upper-order statement for a doublet; not an unavoidable fourth-order floor |

## Proof and assumptions

Write H = H0 + beta V and P as the product of local ground-multiplet projectors. For a local vector B, its first-order observable correction is

O_eff = P O P - beta (P O R V P + P V R O P) + O(beta^2),

where R = (1-P)/(H0-E0). The energy denominator is positive. For a complex Fourier operator the two terms must be computed separately: P O R is NOT the adjoint of R O P unless O is Hermitian.

Only a single excited cell can contribute to this order, because a local probe cannot remove excitations on both endpoints. On a link the local factor is

M^{z mu} = P_cell (B^z R_cell S_end^mu + S_end^mu R_cell B^z) P_cell.

For a Hermitian local B, M is Hermitian and even under time reversal. The product of two vectors contains tensor ranks 0, 1, 2. A Hermitian rank-one operator in a single SU(2) irrep is time-reversal odd, so the rank-one term is absent. Rotational covariance consequently leaves a scalar delta_{z mu} and a rank-two quadrupole. Real and imaginary parts of a Fourier B can be treated separately and then recombined.

Within one spin-1/2 irrep every Hermitian operator is a real linear combination of I and T^mu. Time reversal removes the latter from M. Equivalently its quadrupole is identically zero. The link correction is therefore a scalar multiple of the neighboring T^z. Translation sums on a periodic uniform chain reduce the full first-order probe to gamma(q) D_Q. Reflection around a cell center and real exchange make gamma real in the same phase convention as A. At a simple root A(q,alpha_*) = 0 with A' != 0, choosing kappa = -gamma/A' gives O_eff = O(beta^2), hence W_low = O(beta^4) or smaller. This is an operator cancellation, not just cancellation of a single line.

For s = 3/2 a nonzero quadrupole is allowed:

Q^{z mu} = {T^z,T^mu}/2 - s(s+1) delta_{z mu} I/3.

The correction can contain sum_mu Q_n^{z mu} T_{n+1}^mu. This is a vector under simultaneous rotation, not a direct rank-two neutron transition. Its presence permits, but does not ensure, a source independent of D_Q on the ground state. Four-cell periodic chains at q = pi are a calculated counterexample to any claim that s = 3/2 alone forces a nonzero residual.

For a possibly degenerate ground ensemble, define the inner product by equally averaging over the ground states and projecting out the entire ground subspace. Put d = D_Q |G> and k = K_q |G> in this direct-sum source space. A real retuning minimizes

C(kappa) = ||k + kappa A' d||^2.

Then kappa_opt = -Re<d,k>/(A' ||d||^2) and C_min = ||k||^2 - (Re<d,k>)^2/||d||^2. In the geometries checked here the overlap is real to numerical precision. This elementary least-squares identity is not claimed as a mathematical innovation.

Assumptions are essential: one isolated SU(2) irrep per cell without extra orbital multiplicity; SU(2) and time-reversal invariant exchange; bilinear intercell coupling; uniform periodic geometry, commensurate q and reflection for the real one-parameter cancellation; a simple zero; fixed finite N as beta tends to zero. Open endpoints produce nonuniform one-spin terms and are outside the periodic operator-cancellation argument. No uniform-in-N perturbation bound or thermodynamic residual is established.

## Decisive tests

1. **Same microscopic geometry.** Three cells, 15 microscopic spins, PBC, total Sz = 1/2. The two degenerate ground states are averaged and all ground-to-ground transitions excluded. Quartet: alpha_* = -0.38103454019107325, q = 14pi/15. Doublet: alpha_* = 1.4535291668426678, q = 8pi/15. Both have Q = 2pi/3. The positive root extends the previous alpha <= 1 survey; the Hamiltonian and ring geometry do not change.
2. **Microscopic powers.** At g = .005, .01, .02, .04, the first three retuned weights give log slopes 1.98687385 and 4.01673143 for quartet and doublet. These deterministic finite-interval slopes are not statistical critical exponents. The smallest quartet W/beta^2 differs from the effective prediction 0.1420278853 by 0.7823%. The doublet weights range from 9.9690e-14 to 4.3111e-10; observability is not established. All microscopic eigen-residual and ground-space-count gates pass.
3. **Even-chain quartet residual.** At q = pi, alpha_* = -(2+sqrt(7))/6, PBC N = 6, 8, 10 gives C_min = .000443300, .000649072, .000751090. N = 4 PBC is zero. The scalar-neighbor component is removed completely under periodic retuning; the residual is composite. This avoids attributing open-end effects to the composite mechanism.
4. **Microscopic q = pi check.** Four open cells, 20 microscopic spins: g = .000625 gives line-vector error 1.2254% and integrated-weight error .1333%, with an independent solver restart agreeing at relative line error 3.56e-9. At g = .02 and .04 the line errors rise to 46% and 109%; those points demonstrate failure of the leading theory, not success.
5. **Longer effective chains.** DMRG N = 20, chi = 256 passes the fixed criteria and gives C_min = .0010093797603 (OBC). N = 40, chi = 256 fails the energy-per-cell change threshold: 1.0814e-8 > 1e-8. It remains explicitly unaccepted despite a stable weight .0009808034781. These are effective spin-3/2 chains, not microscopic L = 100 or 200 simulations. No bulk extrapolation is made.

## Prior work and candidate increment

- Waldmann, arXiv:cond-mat/0304463: geometrical interference and symmetry control of cluster scattering are established. https://arxiv.org/abs/cond-mat/0304463
- Waldmann and Guedel, PRB 72, 094422 (2005), Sec. V A and Eq. (27): perturbative effective scattering operators and higher-rank corrections are established, there for anisotropy-induced multiplet mixing within a cluster. Its existence rules out presenting effective-operator construction itself as new. Full primary-source PDF inspected. https://arxiv.org/abs/cond-mat/0508225
- Mueller, Mikeska and Cavadini, arXiv:cond-mat/0312042: higher-order corrections to dimer structure factors are established. https://arxiv.org/abs/cond-mat/0312042
- Ghassemi Tabrizi, arXiv:2608.13795v1: systematic cluster extinctions and their distinction from parameter-dependent zeros; preprint status must be retained. https://arxiv.org/abs/2608.13795
- Cheng et al. (2022) and Li et al. (2026): effective chains and folded spectra in related trimer/tetramer systems are already known. https://www.nature.com/articles/s41535-021-00416-4 ; https://www.nature.com/articles/s41535-026-00855-x

The proposed increment is the physically retuned residual in an isotropic interacting-cell chain, its doublet/quartet contrast, and explicit boundary and weak-coupling limits. Absence of a matching search result does not establish priority. The three-cell odd ring is frustrated and is not itself a bulk-chain demonstration. The fourth-order coefficient has not been derived from a full second-order probe, nor shown to survive second-order retuning.

## Manuscript architecture

- Introduction: extinction is known; ask what survives after physical retuning.
- Model and observable: normalization, simple root, assumptions and local gaps.
- Mechanism: rank decomposition, cancellation and residual criterion.
- Results: same-ring microscopic comparison, even periodic controls, q = pi microscopic validation and finite effective-chain checks.
- Discussion: compare directly with established effective-operator work; no new phase or universal nonzero floor.
- Appendix: numerical protocols, failure cases, selected original full L = 40 maps as finite-coupling context only.

The former manuscript remains unchanged while this evidence-led research draft is developed. Target-journal suitability and final author approval remain unresolved.
