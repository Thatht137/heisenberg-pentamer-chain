"""复算最弱信号，检查起始向量和 Krylov 空间敏感性。"""

import hashlib
import json
import time
from pathlib import Path

import validate_thermal_four_cells as calc
import audit_four_cell_thermal_window as audit

np = calc.np
OUT = calc.ROOT/"results/novelty_20261008/four_cell_solver_repeat"


def main():
    OUT.mkdir(exist_ok=False)
    started = time.perf_counter()
    calc.reference.write_json(OUT/"protocol.json", {
        "g": .000625, "seed": 20261009, "ncv": 220, "tol": 5e-14,
        "wall_limit_seconds": 180, "threads": 1,
        "relative_weight_gate": 1e-4, "scope": "solver sensitivity, not an independent numerical method",
        "original_source_unchanged": True})
    original_solver = calc.eigsh
    def alternative(operator, **kwargs):
        kwargs.update(ncv=220, tol=5e-14,
                      v0=np.random.default_rng(20261009).normal(size=operator.shape[0]))
        return original_solver(operator, **kwargs)
    calc.eigsh = alternative
    raw = audit.read_rows(audit.SOURCE/"comparisons.csv")[0]
    alpha, beta, gap = (float(raw[k]) for k in ("alpha_retuned", "beta", "local_gap"))
    jeff = float(raw["T"])/float(raw["tau"])
    blocks, checks = calc.spectrum(20, alpha, beta, gap, started+180)
    calc.save_spectrum(OUT/"low_band_repeat.npz", blocks)
    before = audit.load_blocks(.000625)
    rows = []
    for tau in (.1, .2, .4, 1.6):
        for cut in (1e-10, .05*jeff):
            old = calc.weight(before, tau*jeff, cut)
            new = calc.weight(blocks, tau*jeff, cut)
            for key in ("W_positive_low", "W_ground_initial", "W_excited_initial"):
                rows.append({"tau": tau, "cutoff": cut, "quantity": key,
                             "original": old[key], "repeat": new[key], "relative_change": abs(new[key]/old[key]-1)})
    calc.reference.write_csv(OUT/"comparisons.csv", rows)
    maximum = max(r["relative_change"] for r in rows)
    summary = {"max_relative_weight_change": maximum, "checks": checks,
               "passed": maximum < 1e-4, "elapsed_seconds": time.perf_counter()-started}
    calc.reference.write_json(OUT/"summary.json", summary)
    files = [Path(__file__), Path(calc.__file__), Path(audit.__file__), *sorted(OUT.iterdir())]
    calc.reference.write_json(OUT/"sha256.json", {str(p.relative_to(calc.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                               for p in files if p.is_file()})
    print(json.dumps(summary), flush=True)
    assert summary["passed"]


if __name__ == "__main__":
    main()
