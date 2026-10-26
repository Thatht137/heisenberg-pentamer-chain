"""分离端点与复合探针，检查整带最优和单线抵消的区别。"""

from __future__ import annotations

import csv
import hashlib
import time
from pathlib import Path

import extend_dark_effective as sparse
import numpy as np
from scipy.sparse.linalg import LinearOperator, eigsh

dark, reference, ROOT = sparse.dark, sparse.reference, sparse.ROOT
OUT = ROOT / "results/novelty_20261004/probe_components"


def main():
    start = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=False)
    reference.write_json(OUT / "protocol.json", {
        "effective_cells": [4, 6, 8, 10], "boundaries": ["OBC", "PBC"],
        "purpose": "separate boundary one-spin term from quadrupole-spin term; compare modewise cancellation",
        "decomposition": "K=K_linear+K_composite, each projected orthogonal to D|0>",
        "tests": ["sum of components", "PBC scalar source has zero perpendicular part", "prior Wmin agreement"],
        "threads": 1, "wall_limit_seconds": 600, "bulk_claim": False,
    })
    with (ROOT / "results/novelty_20261004/effective_size_extension/size_checks.csv").open(newline="") as f:
        baseline = {(int(r["cells"]), r["boundary"]): r for r in csv.DictReader(f)}
    t, quad, c1, coeff, kl, kr, _ = dark.effective_probe()
    linear_left = coeff[0]*np.kron(np.eye(4), t["z"])
    linear_right = coeff[0]*np.kron(t["z"], np.eye(4))
    linear_bond = linear_left-linear_right
    composite_bond = kl-kr-linear_bond
    link = c1**2 * sum(np.kron(op, op) for op in t.values())
    rows = []
    for count in (4, 6, 8, 10):
        for periodic in (False, True):
            data = sparse.sector(count)
            pairs = [(i, i+1) for i in range(count-1)] + ([(count-1, 0)] if periodic else [])
            h = sum(sparse.bond_matrix(link, i, j, data) for i, j in pairs)
            operators = [sum((-1)**i*sparse.bond_matrix(op, i, j, data) for i,j in pairs)/np.sqrt(5*count)
                         for op in (linear_bond, composite_bond)]
            def matvec(x):
                if time.perf_counter()-start > 600:
                    raise TimeoutError("达到探针分解时间边界")
                return h@x
            e, v = eigsh(LinearOperator(h.shape, matvec=matvec, dtype=np.float64),
                         k=2, which="SA", tol=1e-12, ncv=30,
                         v0=np.random.default_rng(20261005).normal(size=h.shape[0]))
            order = np.argsort(e)
            e, v = e[order], v[:,order]
            ground, excited = v.T
            d = np.sum((1.5-data[2])*((-1.)**np.arange(count))[None,:], axis=1)*ground/np.sqrt(5*count)
            d -= ground*np.dot(ground,d)
            parts = [op@ground for op in operators]
            parts = [p-ground*np.dot(ground,p) for p in parts]
            linear, composite = parts
            k = linear+composite
            norm_d = np.dot(d,d)
            perpendicular = [p-d*np.dot(d,p)/norm_d for p in parts]
            lp, cp = perpendicular
            remainder = lp+cp
            best = np.dot(d,k)/norm_d
            gap_amplitude = np.dot(excited,k)/np.dot(excited,d)
            gap_cancelled = k-gap_amplitude*d
            def mean_energy(p):
                norm = np.dot(p,p)
                return float(np.dot(p,h@p-e[0]*p)/norm) if norm > 1e-20 else None
            bc = "PBC" if periodic else "OBC"
            row = {"cells": count, "boundary": bc,
                   "W_linear_perpendicular": float(lp@lp), "W_composite_perpendicular": float(cp@cp),
                   "interference_perpendicular": float(2*lp@cp), "W_min": float(remainder@remainder),
                   "lambda_integrated": float(best), "lambda_lowest_line": float(gap_amplitude),
                   "W_after_lowest_line_cancellation": float(gap_cancelled@gap_cancelled),
                   "mean_energy_ordinary_over_beta": mean_energy(d),
                   "mean_energy_fixed_over_beta": mean_energy(k),
                   "mean_energy_retuned_over_beta": mean_energy(remainder),
                   "lowest_line_share_fixed": float(np.dot(excited,k)**2/(k@k)),
                   "lowest_line_share_retuned": float(np.dot(excited,remainder)**2/(remainder@remainder))
                                                 if remainder@remainder > 1e-20 else None,
                   "residual_norm": float(np.max(np.linalg.norm(h@v-v*e,axis=0)))}
            assert abs(row["W_min"]-float(baseline[count,bc]["retuned_W_over_beta2"])) < 1e-10
            assert row["residual_norm"] < 1e-10
            if periodic:
                assert row["W_linear_perpendicular"] < 1e-20
            rows.append(row)
            reference.write_csv(OUT / "decomposition.csv", rows)
            print(row, flush=True)
    reference.write_json(OUT / "summary.json", {"all_checks_pass": True, "rows": rows,
                         "elapsed_seconds": time.perf_counter()-start, "microscopic_validation": False})
    reference.write_json(OUT / "sha256.json", {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), Path(sparse.__file__), Path(dark.__file__), Path(reference.__file__)]
        + sorted(OUT.iterdir()) if p.is_file()})


if __name__ == "__main__":
    main()
