# Single-variable DSF controls

The audit reads the frozen `../dsf_controls/plan.json` without changing it.
Run `scripts/submission_20261002/audit_dsf_controls.py` with the project Python
environment. Add `--require-complete` when the complete twelve-comparison result
is required. Any failure exits with code 1; incomplete but otherwise valid data
exit with code 2 in strict mode, or code 0 in partial-report mode. Missing
completed data are reported as pending; the audit does not launch or restart jobs.

## Comparisons

For each sign of alpha, the three momenta q/pi=0.2,0.6,1 are checked twice:

1. Bond dimension: original dt=0.05, chi=192 versus dt=0.05, chi=256.
2. Time step: dt=0.05, chi=256 versus dt=0.025, chi=256. The q/pi=1
   reference is the retained same-ground five-momentum check, while 0.2 and
   0.6 use the new two-momentum run.

These are twelve separate comparisons, not averages over momentum. The full
L2 error covers omega/J1=0..4; the low-energy L2 error covers the first frozen
band, 0..0.6. Each denominator is the corresponding refined spectrum norm.
Three integrated band weights use the original frequency grid and trapezoidal
quadrature; shared boundary nodes are integrated normally without adding any
frequency interval twice. The peak shift compares the grid location of each
spectrum's maximum and is not a pole-resolution estimate.

Every physical acceptance threshold comes directly from the frozen plan.
The band rule is

`abs(Wbase-Wref) <= max(0.05*abs(Wref), 0.001*C0ref)`.

The coefficients shown here are the current frozen values, not hardcoded
threshold overrides. Both absolute and relative errors are retained so the
absolute floor cannot conceal a large relative change in a weak tail.

## Integrity and provenance

The driver and ground-seed SHA256 hashes must match the frozen plan before and
after the audit. Completed runs require their result marker, full metadata,
actual q and omega grids, spectra, metrics, and selected correlation records.
Read-time hashes are recorded for these inputs and checked again after reading;
they are snapshots, not claims of independent historical content hashes.

Model, ground-state energy/variance/reflection diagnostics, source construction,
time window, truncation cutoff, and software versions must be unchanged between
the two runs. Only the intended dt or chi may differ. The same-source relative
difference must remain below 1e-7, inherited from the original full-q audit as
an integrity gate rather than introduced as a new physical convergence threshold.
Grid and tabulation consistency checks use absolute roundoff tolerance 1e-12.
Norm drift is recalculated from the correlation record; source and norm-API
errors are retained per momentum. The norm-API error is diagnostic only here.

The driver records its nominal command-line q_points even when an environment
variable supplies the actual momenta. Consequently the new dt runs have
nominal q_points=3 but two actual momentum rows. Both counts are recorded;
actual q.csv, metric row order, and selected correlation indices must match
the frozen plan. No missing momentum is inferred from the nominal count.

The ground JLD2 containers are not required to have identical file hashes:
each container also stores its run configuration. The frozen common seed hash,
seed-path metadata, unchanged ground diagnostics, and initial source weights
are checked instead. This is an evidence-backed same-ground check, not a
claim that different JLD2 containers are byte-identical.

## Scope

Passing this audit supports three selected momenta at fixed L=40 and T=60.
It does not establish uniform full-q, longer-time, thermodynamic, or
high-energy multiplet-assignment convergence. No smoothing, reflected copying,
source clipping, or spectral renormalization is performed by this audit.

The synthetic test suite checks both-knob changes, every fixed metadata field,
wrong or duplicated q values, frequency and time grids, same-source mismatches,
changed provenance hashes, incomplete/terminal states, numeric failures,
the absolute band floor, plan-derived thresholds, and strict-mode exit codes.
