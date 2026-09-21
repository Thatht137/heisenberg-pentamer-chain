#!/usr/bin/env python3
"""用固定 Sz 精确对角化交叉检查静态 DMRG cell。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from itertools import combinations
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sector_basis(length: int, target_sz: int) -> tuple[list[int], dict[int, int]]:
    n_up = length // 2 + target_sz
    states = [sum(1 << site for site in sites) for sites in combinations(range(length), n_up)]
    return states, {state: index for index, state in enumerate(states)}


def bonds(n_units: int, alpha: float, beta: float) -> list[tuple[int, int, float]]:
    result: list[tuple[int, int, float]] = []
    for unit in range(n_units):
        first = 5 * unit
        result.extend([
            (first, first + 1, alpha),
            (first + 1, first + 2, 1.0),
            (first + 2, first + 3, 1.0),
            (first + 3, first + 4, alpha),
        ])
        if unit + 1 < n_units:
            result.append((first + 4, first + 5, beta))
    return result


def hamiltonian(
    states: list[int],
    state_index: dict[int, int],
    bond_list: list[tuple[int, int, float]],
) -> np.ndarray:
    matrix = np.zeros((len(states), len(states)), dtype=np.float64)
    for column, state in enumerate(states):
        for left, right, coupling in bond_list:
            left_up = (state >> left) & 1
            right_up = (state >> right) & 1
            matrix[column, column] += coupling * (0.25 if left_up == right_up else -0.25)
            if left_up != right_up:
                flipped = state ^ (1 << left) ^ (1 << right)
                matrix[state_index[flipped], column] += 0.5 * coupling
    return matrix


def ed_sector(length: int, n_units: int, target_sz: int, alpha: float, beta: float) -> dict[str, float]:
    states, state_index = sector_basis(length, target_sz)
    matrix = hamiltonian(states, state_index, bonds(n_units, alpha, beta))
    hermiticity = float(np.linalg.norm(matrix - matrix.T))
    energy = float(np.linalg.eigvalsh(matrix)[0])
    roundoff = float(100 * np.finfo(float).eps * max(1.0, abs(energy)) * len(states))
    return {
        "target_sz": target_sz,
        "dimension": len(states),
        "energy": energy,
        "hermiticity_norm": hermiticity,
        "uncertainty": max(hermiticity, roundoff),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dmrg-cell", required=True)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()
    cell_dir = Path(args.dmrg_cell).resolve()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    manifest_path = cell_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    length = int(manifest["params"]["L"])
    n_units = int(manifest["params"]["n_units"])
    alpha = float(manifest["params"]["alpha"])
    beta = float(manifest["params"]["beta"])
    if length > 14:
        raise SystemExit("精确 oracle 仅用于 L<=14")
    if alpha < 0 or beta < 0:
        raise SystemExit("禁止负耦合 oracle")

    ed0 = ed_sector(length, n_units, 0, alpha, beta)
    ed1 = ed_sector(length, n_units, 1, alpha, beta)
    dmrg0 = float(manifest["observables"]["energy_sz0"])
    dmrg1 = float(manifest["observables"]["energy_sz1"])
    variance0 = float(manifest["diagnostics"]["variance_per_site_sz0"]) * length
    variance1 = float(manifest["diagnostics"]["variance_per_site_sz1"]) * length
    budget0 = math.sqrt(max(variance0, 0.0))
    budget1 = math.sqrt(max(variance1, 0.0))
    delta0 = abs(dmrg0 - ed0["energy"])
    delta1 = abs(dmrg1 - ed1["energy"])
    gap_dmrg = dmrg1 - dmrg0
    gap_ed = ed1["energy"] - ed0["energy"]
    gap_delta = abs(gap_dmrg - gap_ed)
    gap_dmrg_budget = budget0 + budget1
    gap_ed_budget = ed0["uncertainty"] + ed1["uncertainty"]
    checks = {
        "same_length": length == 5 * n_units,
        "same_boundary": manifest["settings"]["boundary"] == "OBC",
        "same_sectors": manifest["settings"]["sectors"] == ["Sz=0", "Sz=1"],
        "ed_hermiticity_sz0": ed0["hermiticity_norm"] <= 1e-12,
        "ed_hermiticity_sz1": ed1["hermiticity_norm"] <= 1e-12,
        "energy_sz0_intervals_overlap": delta0 <= budget0 + ed0["uncertainty"],
        "energy_sz1_intervals_overlap": delta1 <= budget1 + ed1["uncertainty"],
        "spin_gap_intervals_overlap": gap_delta <= gap_dmrg_budget + gap_ed_budget,
    }
    tag = "Agreement" if all(checks.values()) else "Disagreement"
    rows = [
        ["DMRG", "energy_sz0", dmrg0, budget0, f"L={length};alpha={alpha};beta={beta};OBC;Sz=0", tag],
        ["ED", "energy_sz0", ed0["energy"], ed0["uncertainty"], f"L={length};alpha={alpha};beta={beta};OBC;Sz=0", tag],
        ["DMRG", "energy_sz1", dmrg1, budget1, f"L={length};alpha={alpha};beta={beta};OBC;Sz=1", tag],
        ["ED", "energy_sz1", ed1["energy"], ed1["uncertainty"], f"L={length};alpha={alpha};beta={beta};OBC;Sz=1", tag],
        ["DMRG", "spin_gap", gap_dmrg, gap_dmrg_budget, f"L={length};alpha={alpha};beta={beta};OBC", tag],
        ["ED", "spin_gap", gap_ed, gap_ed_budget, f"L={length};alpha={alpha};beta={beta};OBC", tag],
    ]
    csv_path = outdir / "cross-method-check.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["method", "observable", "value", "uncertainty", "instance", "tag"])
        writer.writerows(rows)
    summary = {
        "tag": tag,
        "configuration": {
            "L": length,
            "n_units": n_units,
            "alpha": alpha,
            "beta": beta,
            "boundary": "OBC",
            "hamiltonian": "sum J_ij S_i dot S_j",
        },
        "dmrg": {
            "energy_sz0": dmrg0,
            "energy_sz1": dmrg1,
            "spin_gap": gap_dmrg,
            "uncertainty_source": "sqrt(total energy variance)",
            "energy_budget_sz0": budget0,
            "energy_budget_sz1": budget1,
        },
        "ed": {"sz0": ed0, "sz1": ed1, "spin_gap": gap_ed},
        "absolute_differences": {
            "energy_sz0": delta0,
            "energy_sz1": delta1,
            "spin_gap": gap_delta,
        },
        "checks": checks,
        "source_sha256": {str(manifest_path): sha256(manifest_path)},
    }
    summary_path = outdir / "cross-method-check.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in (csv_path, summary_path)), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    if tag != "Agreement":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
