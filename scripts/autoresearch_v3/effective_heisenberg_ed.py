#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精确计算有限 OBC 有效 Heisenberg 链的基态能量与自旋隙。"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import eigsh


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "autoresearch_v3_20260729" / "round2_effective_oracle"


def sector_hamiltonian(length: int, target_sz: int):
    n_up = length // 2 + target_sz
    basis = [sum(1 << site for site in sites) for sites in itertools.combinations(range(length), n_up)]
    lookup = {state: index for index, state in enumerate(basis)}
    rows, columns, values = [], [], []
    for column, state in enumerate(basis):
        diagonal = 0.0
        for site in range(length - 1):
            left = (state >> site) & 1
            right = (state >> (site + 1)) & 1
            diagonal += 0.25 if left == right else -0.25
            if left != right:
                flipped = state ^ (1 << site) ^ (1 << (site + 1))
                rows.append(lookup[flipped])
                columns.append(column)
                values.append(0.5)
        rows.append(column)
        columns.append(column)
        values.append(diagonal)
    return coo_matrix((values, (rows, columns)), shape=(len(basis), len(basis))).tocsr()


def ground_energy(length: int, target_sz: int) -> tuple[float, float, int]:
    hamiltonian = sector_hamiltonian(length, target_sz)
    value, vector = eigsh(hamiltonian, k=1, which="SA", tol=1e-13)
    residual = np.linalg.norm(hamiltonian @ vector[:, 0] - value[0] * vector[:, 0])
    return float(value[0]), float(residual), hamiltonian.shape[0]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=False)
    rows = []
    for length in (8, 12, 16):
        energy0, residual0, dimension0 = ground_energy(length, 0)
        energy1, residual1, dimension1 = ground_energy(length, 1)
        rows.append({"N_units": length, "E_sz0": energy0, "E_sz1": energy1, "spin_gap": energy1 - energy0, "residual_sz0": residual0, "residual_sz1": residual1, "dimension_sz0": dimension0, "dimension_sz1": dimension1})
    with (OUT / "heisenberg_obc_oracle.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    acceptance = {"max_residual": max(max(row["residual_sz0"], row["residual_sz1"]) for row in rows), "all_residuals_pass": all(max(row["residual_sz0"], row["residual_sz1"]) <= 1e-10 for row in rows), "boundary": "OBC", "sectors": [0, 1]}
    (OUT / "acceptance.json").write_text(json.dumps(acceptance, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in sorted(OUT.iterdir()) if path.name != "checksums.sha256"), encoding="utf-8"
    )
    print(json.dumps(acceptance, ensure_ascii=False))


if __name__ == "__main__":
    main()
