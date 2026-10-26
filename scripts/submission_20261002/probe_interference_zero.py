"""探索干涉零点及两胞低能谱权，不改现有结果。"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

import numpy as np
from scipy.optimize import brentq

import local_projection_checks as reference

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/novelty_20261004/interference_zero_probe"
G = [0.00125, 0.0025, 0.005, 0.01, 0.02, 0.04]


def main():
    start = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=False)
    q = np.linspace(0, 2 * np.pi, 41)
    contract = ROOT / "docs/novelty_contract_20261004.md"
    reference.write_json(OUT / "protocol.json", {
        "contract_sha256": hashlib.sha256(contract.read_bytes()).hexdigest(),
        "alpha_bracket": [-4.0, -0.02], "alpha_points": 121,
        "g_values": G, "root_offsets": [-0.02, 0.0, 0.02],
        "fit_g_count": 4, "L": 10, "boundary": "OBC",
        "low_band": "0 < omega < Delta_local/2", "threads": 1,
        "wall_limit_seconds": 300, "exploratory": True,
    })

    def cell(alpha):
        if time.perf_counter() - start > 280:
            raise TimeoutError("达到首轮探索时间边界")
        result, shape, weight = reference.local_projection(alpha, q)
        amplitude = float(np.dot(result["c"], [1, -1, 1, -1, 1]))
        return result, shape, weight, amplitude

    scan = []
    for alpha in np.linspace(-4, -0.02, 121):
        result, shape, _, amplitude = cell(float(alpha))
        scan.append({"alpha": float(alpha), "spin": result["s"],
                     "local_gap": result["local_gap"], "A_pi": amplitude,
                     "F_pi": float(shape[20]), "F_06pi": float(shape[12])})
    reference.write_csv(OUT / "cell_scan.csv", scan)
    roots = [brentq(lambda a: cell(a)[3], left["alpha"], right["alpha"], xtol=1e-13)
             for left, right in zip(scan, scan[1:]) if left["A_pi"] * right["A_pi"] < 0]
    rows, qrows, root_records, fits = [], [], [], []
    for root in roots:
        root_records.append(cell(root)[0])
        for offset in (-0.02, 0.0, 0.02):
            alpha = root + offset
            result, _, prediction, amplitude = cell(alpha)
            assert abs(result["s"] - 1.5) < 1e-10
            assert max(result["checks"].values()) <= 1e-10
            dark = []
            for g in G:
                row, data = reference.full_chain(alpha, g * result["local_gap"], result, prediction, q)
                row.update(root=root, offset=offset, A_pi=amplitude)
                assert row["numerical_pass"] and row["band_separated"]
                rows.append(row)
                qrows.extend(dict(item, root=root, offset=offset) for item in data)
                dark.append(data[20]["low_weight_ed"])
                print(json.dumps({"offset": offset, "g": g, "W_pi": dark[-1],
                                  "W_06pi": data[12]["low_weight_ed"]}), flush=True)
            coefficients = np.polyfit(np.log(G[:4]), np.log(dark[:4]), 1)
            fits.append({"alpha": alpha, "offset": offset,
                         "log_slope_first_four_g": float(coefficients[0]),
                         "weights_pi": dark})
    if rows:
        reference.write_csv(OUT / "coupling_checks.csv", rows)
        reference.write_csv(OUT / "q_resolved_weights.csv", qrows)
    summary = {"roots": roots, "root_cells": root_records, "fits": fits,
               "ed_cases": len(rows), "elapsed_seconds": time.perf_counter() - start,
               "all_numerical_checks_pass": all(r["numerical_pass"] for r in rows),
               "new_theory_claim": False, "long_chain_validation": False}
    reference.write_json(OUT / "summary.json", summary)
    inputs = [Path(__file__), Path(reference.__file__).resolve(), contract,
              ROOT / "scripts/autoresearch_v5/static_krylov_ed_reference.py",
              ROOT / "scripts/autoresearch_v3/project_doublet.py"]
    reference.write_json(OUT / "sha256.json", {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in inputs + sorted(OUT.iterdir()) if p.is_file()})
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
