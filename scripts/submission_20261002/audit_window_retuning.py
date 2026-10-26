"""用完整谱矩阵元复核窗口重调结果。"""

import csv
import hashlib
import json
import time
from pathlib import Path

import check_window_retuning as study
import numpy as np


def main():
    out, root = study.OUT, study.ROOT
    manifest = json.loads((out/"sha256.json").read_text())
    failures = [name for name, digest in manifest.items()
                if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest]
    assert not failures
    with (out/"comparisons.csv").open(newline="") as handle:
        rows = [{k: float(v) if k not in ("optimizer_success",) and v else v
                 for k, v in row.items()} for row in csv.DictReader(handle)]
    summary = json.loads((out/"summary.json").read_text())
    assert len(rows) == 32
    cases = {c["spin"]: c for c in summary["cases"]}
    started = time.perf_counter()
    deadline = started+120
    direct = []
    nodes, weights = np.polynomial.legendre.leggauss(16)
    for row in rows:
        if row["g"] not in (.00125, .01) or row["rho"] != 1:
            continue
        case = cases[row["spin"]]
        q = np.pi if row["spin"] == 1.5 else 3*np.pi/5
        values = []
        residuals, balance, missing = [], [], []
        for node in nodes:
            result = study.validation.microscopic(row["alpha_opt"], row["beta"],
                q+node*np.pi*row["delta_over_pi"],
                1.6*row["beta"]*case["c1_squared"], case["gap"], deadline)
            values.append(result["W_positive_low"])
            residuals.append(result["max_eigen_residual"])
            balance.append(result["detailed_balance_error"])
            missing.append(result["thermal_population_outside_band"])
            assert result["retained_states_all_sectors"] == int(2*row["spin"]+1)**2
        value = float(np.dot(weights, values)/2)
        relative = abs(value/row["W_min"]-1)
        assert relative < 1e-6
        direct.append({"spin": row["spin"], "g": row["g"], "W_direct": value,
                       "relative_error": relative, "max_eigen_residual": max(residuals),
                       "max_detailed_balance_error": max(balance),
                       "max_omitted_population": max(missing)})
    # 中心近零值只作为数值上界，不报有效数字。
    centers = [r for r in rows if r["spin"] == .5 and r["rho"] == 0]
    weak = [r for r in rows if r["g"] == .00125 and r["rho"] > 0]
    checks = {
        "source_hashes_checked": len(manifest), "hash_failures": failures,
        "direct_transition_checks": direct,
        "shared_hamiltonian_and_eigensolver": True,
        "independent_method_claim": False,
        "doublet_optimized_center_weight_upper_bound": 1e-28,
        "doublet_center_passes_upper_bound": all(r["W_min"] < 1e-28 for r in centers),
        "weakest_limit_max_relative_error": {
            str(s): max(abs(r["relative_to_limit"]-1) for r in weak if r["spin"] == s)
            for s in (1.5, .5)},
        "quadrature_max_relative_error": max(r["quadrature_error"] for r in rows),
        "elapsed_seconds": time.perf_counter()-started,
        "no_general_doublet_fourth_order_floor_claim": True,
    }
    study.reference.write_json(out/"audit.json", checks)
    files = [Path(__file__), out/"sha256.json", out/"audit.json"]
    study.reference.write_json(out/"audit_sha256.json", {str(p.relative_to(root)):
        hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
