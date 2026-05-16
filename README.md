# 1x5 Heisenberg Pentamer Chain

Julia code for studying a spin-1/2 Heisenberg pentamer chain with exact
diagonalization, DMRG, string order parameters, and dynamical structure factors.

## Model

Each pentamer unit has five spin-1/2 sites:

```text
o--J2--o--J1--o--J1--o--J2--o
1      2      3      4      5
```

Neighboring units are coupled by `J3` between site 5 of one unit and site 1 of
the next unit.

Parameters:

- `J1 = 1`: energy unit.
- `alpha = J2 / J1`: edge-bond strength inside a pentamer.
- `beta = J3 / J1`: inter-pentamer coupling.

## Repository Layout

```text
src/
  PentamerChain.jl       Main module
  utils.jl               Spin-basis utilities
  hamiltonian.jl         ED Hamiltonian and ITensors MPO construction
  exact_diag.jl          Exact diagonalization and total-spin classification
  dmrg_solver.jl         DMRG ground-state and excited-state helpers
  order_parameters.jl    String order parameter and spin gap
  spectral.jl            Correction-vector DSF calculation

scripts/
  01_single_pentamer.jl  Single-pentamer ED scan
  02_dmrg_chain.jl       DMRG chain benchmark
  03_phase_diagram.jl    String-order phase diagram scan
  04_dsf.jl              Dynamical structure factor scan

test/
  runtests.jl            Basic unit tests
```

## Usage

Instantiate the Julia environment first:

```powershell
julia --project=. -e "using Pkg; Pkg.instantiate()"
```

Run tests:

```powershell
julia --project=. test\runtests.jl
```

Run example scripts:

```powershell
julia --project=. scripts\01_single_pentamer.jl
julia --project=. scripts\02_dmrg_chain.jl
julia --project=. scripts\03_phase_diagram.jl
julia -t 8 --project=. scripts\04_dsf.jl
```

The phase diagram and DSF scripts are computationally heavier. For production
runs, use larger `N_units`, denser parameter grids, and enough DMRG bond
dimension on a server.

## Validation Status

The code has been checked on small systems:

- Basis encoding/decoding tests pass.
- Single-pentamer Hamiltonian agrees with exact diagonalization benchmarks.
- DMRG energies match expected limiting cases.
- Small-grid DSF output satisfies non-negativity, `q=0` / `2pi` zero weight, and
  `q -> 2pi-q` symmetry within numerical tolerance.

Current small result files in `data/` are intended as workflow checks, not final
publication-scale data.
