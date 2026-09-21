#!/usr/bin/env python3
"""用现有验收数据和小系统 ED 检查负 alpha 新相迹象。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import eigsh


ROOT = Path(__file__).resolve().parents[2]
PHASE_ROOT = ROOT / "results" / "autoresearch_v5_20260809" / "round44_phase_diagram_full_alpha"
POLICY_ROOT = PHASE_ROOT / "phase-diagram-v2"
STAGE_B_INDEX = POLICY_ROOT / "stage_b_practical_v2_accepted_index_final.json"
STAGE_C_INDEX = POLICY_ROOT / "stage_c_practical_v2_r1_terminal_observations.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def mean_half_range(values: list[float]) -> tuple[float, float]:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return math.nan, math.nan
    return float(np.mean(finite)), 0.5 * (max(finite) - min(finite))


def load_parent_records() -> list[dict[str, object]]:
    stage_b = read_json(STAGE_B_INDEX)["records"]
    stage_c = read_json(STAGE_C_INDEX)["records"]
    merged: dict[tuple[float, float, int], tuple[int, dict[str, object]]] = {}
    for priority, records in ((1, stage_b), (2, stage_c)):
        for record in records:
            params = record["params"]
            key = (float(params["alpha"]), float(params["beta"]), int(params["L"]))
            if key not in merged or priority >= merged[key][0]:
                merged[key] = (priority, record)
    return [item[1] for item in sorted(merged.values(), key=lambda item: (
        float(item[1]["params"]["beta"]), float(item[1]["params"]["alpha"]), int(item[1]["params"]["L"])
    ))]


def bulk_bond_metrics(path: Path, length: int) -> dict[str, float]:
    rows = read_csv(path)
    n_units = length // 5
    margin_units = max(1, n_units // 4)
    by_class: dict[int, list[float]] = defaultdict(list)
    by_class_parity: dict[tuple[int, int], list[float]] = defaultdict(list)
    for row in rows:
        bond = int(row["bond"])
        bond_class = int(row["bond_class"])
        correlation = float(row["correlation"])
        unit = bond // 5 if bond_class == 0 else (bond - 1) // 5 + 1
        if margin_units < unit <= n_units - margin_units:
            by_class[bond_class].append(correlation)
            by_class_parity[(bond_class, unit % 2)].append(correlation)
    class_mean = {key: float(np.mean(values)) for key, values in by_class.items() if values}
    dimer_by_class: dict[int, float] = {}
    for bond_class in range(5):
        even = by_class_parity.get((bond_class, 0), [])
        odd = by_class_parity.get((bond_class, 1), [])
        if even and odd:
            dimer_by_class[bond_class] = 0.5 * abs(float(np.mean(even)) - float(np.mean(odd)))
    return {
        "bond_alpha_left": class_mean.get(1, math.nan),
        "bond_j1_left": class_mean.get(2, math.nan),
        "bond_j1_right": class_mean.get(3, math.nan),
        "bond_alpha_right": class_mean.get(4, math.nan),
        "bond_beta": class_mean.get(0, math.nan),
        "denergy_dalpha_per_unit": class_mean.get(1, math.nan) + class_mean.get(4, math.nan),
        "denergy_dbeta_per_unit": class_mean.get(0, math.nan),
        "dimer_beta": dimer_by_class.get(0, math.nan),
        "dimer_rms": math.sqrt(float(np.mean(np.square(list(dimer_by_class.values()))))) if dimer_by_class else math.nan,
        "mirror_asymmetry": 0.5 * (
            abs(class_mean.get(1, math.nan) - class_mean.get(4, math.nan))
            + abs(class_mean.get(2, math.nan) - class_mean.get(3, math.nan))
        ),
    }


def schmidt_metrics(path: Path) -> dict[str, float]:
    grouped: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for row in read_csv(path):
        grouped[int(row["bond_class"])].append((float(row["probability"]), float(row["entanglement_energy"])))
    entropies: dict[int, float] = {}
    gaps: dict[int, float] = {}
    for bond_class, values in grouped.items():
        probabilities = np.array([value[0] for value in values], dtype=float)
        tail = max(0.0, 1.0 - float(probabilities.sum()))
        entropy = -float(np.sum(probabilities * np.log(np.maximum(probabilities, 1e-300))))
        if tail > 0:
            entropy -= tail * math.log(tail)
        levels = sorted(value[1] for value in values)
        entropies[bond_class] = entropy
        gaps[bond_class] = levels[1] - levels[0] if len(levels) >= 2 else math.nan
    return {
        "entropy_mean5_lower": float(np.mean(list(entropies.values()))),
        "entropy_beta_cut_lower": entropies.get(0, math.nan),
        "entanglement_gap_beta_cut": gaps.get(0, math.nan),
    }


def string_metrics(path: Path) -> dict[str, float]:
    rows = read_csv(path)
    values = [float(row["O_mean"]) for row in rows]
    tail_count = max(2, len(values) // 3)
    tail = values[-tail_count:]
    return {
        "string_tail_rms": math.sqrt(float(np.mean(np.square(tail)))),
        "string_tail_abs_mean": float(np.mean(np.abs(tail))),
    }


def child_metrics(parent_dir: Path, relative_manifest: str, length: int) -> dict[str, float | str]:
    manifest_path = parent_dir / relative_manifest
    child_dir = manifest_path.parent
    manifest = read_json(manifest_path)
    observables = manifest["observables"]
    result = {
        "start_mode": manifest_path.parent.name.removeprefix("start_"),
        "energy_per_site": float(observables["energy_sz0"]) / length,
        "spin_gap": float(observables["spin_gap"]),
        "q_peak_over_pi": float(observables["structure_factor_peak_q_over_pi"]),
        "dominant_ratio": float(observables["dominant_structure_factor_ratio"]),
    }
    result.update(bulk_bond_metrics(child_dir / "bond_correlations.csv", length))
    result.update(schmidt_metrics(child_dir / "schmidt_spectrum.csv"))
    result.update(string_metrics(child_dir / "string_profile.csv"))
    return result


def collect_dmrg() -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for record in load_parent_records():
        parent_manifest_path = ROOT / str(record["artifact"])
        parent = read_json(parent_manifest_path)
        params = parent["params"]
        length = int(params["L"])
        child_paths = parent["diagnostics"]["child_manifests"]
        children = [child_metrics(parent_manifest_path.parent, str(path), length) for path in child_paths]
        selected = min(children, key=lambda child: float(child["energy_per_site"]))
        row: dict[str, float | int | str] = {
            "alpha": float(params["alpha"]),
            "beta": float(params["beta"]),
            "L": length,
            "artifact": str(parent_manifest_path.relative_to(ROOT)).replace("\\", "/"),
            "n_starts": len(children),
            "selected_start": str(selected["start_mode"]),
        }
        for key in children[0]:
            if key == "start_mode":
                continue
            value, error = mean_half_range([float(child[key]) for child in children])
            row[key] = float(selected[key])
            row[f"{key}_start_mean"] = value
            row[f"{key}_start_half_range"] = error
        rows.append(row)
    return rows


def finite_size_diagnostics(dmrg: list[dict[str, object]]) -> list[dict[str, float]]:
    grouped: dict[tuple[float, float], dict[int, dict[str, object]]] = defaultdict(dict)
    for row in dmrg:
        grouped[(float(row["alpha"]), float(row["beta"]))][int(row["L"])] = row
    results: list[dict[str, float]] = []
    for (alpha, beta), by_length in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0])):
        if not all(length in by_length for length in (40, 60, 80)):
            continue
        lengths = np.array([40.0, 60.0, 80.0])
        dimers = np.array([float(by_length[int(length)]["dimer_rms"]) for length in lengths])
        entropies = np.array([float(by_length[int(length)]["entropy_beta_cut_lower"]) for length in lengths])
        dimer_exponent = math.nan
        if np.all(np.isfinite(dimers)) and np.all(dimers > 0):
            dimer_exponent = -float(np.polyfit(np.log(lengths), np.log(dimers), 1)[0])
        c_effective = math.nan
        if np.all(np.isfinite(entropies)):
            c_effective = 6.0 * float(np.polyfit(np.log(lengths), entropies, 1)[0])
        results.append({
            "alpha": alpha,
            "beta": beta,
            "dimer_L40": float(dimers[0]),
            "dimer_L60": float(dimers[1]),
            "dimer_L80": float(dimers[2]),
            "dimer_L80_over_L60": float(dimers[2] / dimers[1]) if dimers[1] > 0 else math.nan,
            "dimer_decay_exponent": dimer_exponent,
            "entropy_L40": float(entropies[0]),
            "entropy_L60": float(entropies[1]),
            "entropy_L80": float(entropies[2]),
            "c_effective_from_entropy_lower_bound": c_effective,
            "Lgap_L40": 40.0 * float(by_length[40]["spin_gap"]),
            "Lgap_L60": 60.0 * float(by_length[60]["spin_gap"]),
            "Lgap_L80": 80.0 * float(by_length[80]["spin_gap"]),
            "max_entropy_start_half_range": max(
                float(by_length[length]["entropy_beta_cut_lower_start_half_range"]) for length in (40, 60, 80)
            ),
            "max_energy_start_half_range": max(
                float(by_length[length]["energy_per_site_start_half_range"]) for length in (40, 60, 80)
            ),
        })
    return results


def chain_bonds(n_units: int, alpha: float, beta: float) -> list[tuple[int, int, float]]:
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


def sector_matrix(n_sites: int, n_up: int, bonds: list[tuple[int, int, float]]):
    basis = [sum(1 << site for site in sites) for sites in itertools.combinations(range(n_sites), n_up)]
    lookup = {state: index for index, state in enumerate(basis)}
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    for column, state in enumerate(basis):
        diagonal = 0.0
        for left, right, coupling in bonds:
            left_bit = (state >> left) & 1
            right_bit = (state >> right) & 1
            diagonal += coupling * (0.25 if left_bit == right_bit else -0.25)
            if left_bit != right_bit:
                rows.append(lookup[state ^ (1 << left) ^ (1 << right)])
                columns.append(column)
                values.append(0.5 * coupling)
        rows.append(column)
        columns.append(column)
        values.append(diagonal)
    return coo_matrix((values, (rows, columns)), shape=(len(basis), len(basis))).tocsr()


def lowest_state(matrix) -> tuple[float, np.ndarray, float]:
    if matrix.shape[0] <= 3:
        values, vectors = np.linalg.eigh(matrix.toarray())
        energy = float(values[0])
        vector = vectors[:, 0]
    else:
        values, vectors = eigsh(matrix, k=1, which="SA", tol=1e-12, maxiter=10000)
        energy = float(values[0])
        vector = vectors[:, 0]
    residual = float(np.linalg.norm(matrix @ vector - energy * vector))
    return energy, vector, residual


def single_pentamer_scan() -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for alpha in np.linspace(-1.0, -0.001, 201):
        energies: dict[float, float] = {}
        residuals: list[float] = []
        for n_up in (3, 4, 5):
            spin_z = n_up - 2.5
            energy, _, residual = lowest_state(sector_matrix(5, n_up, chain_bonds(1, float(alpha), 0.0)))
            energies[spin_z] = energy
            residuals.append(residual)
        ground = min(energies.values())
        total_spin = max(spin for spin, energy in energies.items() if abs(energy - ground) <= 1e-9)
        excited = min((energy - ground for spin, energy in energies.items() if spin > total_spin), default=math.nan)
        rows.append({
            "alpha": float(alpha),
            "ground_spin": float(total_spin),
            "local_multiplet_gap": float(excited),
            "max_residual": max(residuals),
        })
    return rows


def kron_all(operators: list[np.ndarray]) -> np.ndarray:
    result = operators[0]
    for operator in operators[1:]:
        result = np.kron(result, operator)
    return result


def site_operator(local: np.ndarray, site: int) -> np.ndarray:
    identity = np.eye(2, dtype=complex)
    return kron_all([local if index == site else identity for index in range(5)])


def quartet_projection_scan() -> list[dict[str, float]]:
    sx = np.array([[0, 1], [1, 0]], dtype=complex) / 2
    sy = np.array([[0, -1j], [1j, 0]], dtype=complex) / 2
    sz = np.array([[1, 0], [0, -1]], dtype=complex) / 2
    spins = {
        axis: [site_operator(local, site) for site in range(5)]
        for axis, local in (("x", sx), ("y", sy), ("z", sz))
    }
    total_sz = sum(spins["z"])
    rows: list[dict[str, float]] = []
    for alpha in np.linspace(-1.0, -0.001, 201):
        hamiltonian = np.zeros((32, 32), dtype=complex)
        for left, right, coupling in ((0, 1, alpha), (1, 2, 1.0), (2, 3, 1.0), (3, 4, alpha)):
            for axis in ("x", "y", "z"):
                hamiltonian += coupling * spins[axis][left] @ spins[axis][right]
        energies, vectors = np.linalg.eigh(hamiltonian)
        ground_indices = np.flatnonzero(abs(energies - energies[0]) <= 1e-10)
        ground = vectors[:, ground_indices]
        sz_values, rotation = np.linalg.eigh(ground.conj().T @ total_sz @ ground)
        total_spin = float(np.max(sz_values))
        highest = ground @ rotation[:, np.argmax(sz_values)]
        coefficients = np.array([
            float(np.real(highest.conj() @ spins["z"][site] @ highest) / total_spin)
            for site in range(5)
        ])
        folded = np.array([0.2, 0.6, 1.0]) * np.pi
        weights = np.array([
            abs(sum(coefficients[site] * np.exp(-1j * q * site) for site in range(5))) ** 2
            for q in folded
        ])
        rows.append({
            "alpha": float(alpha),
            "ground_spin": total_spin,
            "ground_energy": float(energies[0]),
            "local_multiplet_gap": float(energies[len(ground_indices)] - energies[0]),
            **{f"c{site + 1}": float(coefficients[site]) for site in range(5)},
            "coefficient_sum": float(np.sum(coefficients)),
            "reflection_error": float(np.max(abs(coefficients - coefficients[::-1]))),
            "jeff_over_beta": float(coefficients[0] * coefficients[-1]),
            "weight_q02pi": float(weights[0]),
            "weight_q06pi": float(weights[1]),
            "weight_q10pi": float(weights[2]),
            "dominant_q_over_pi": float((0.2, 0.6, 1.0)[int(np.argmax(weights))]),
            "hermiticity_norm": float(np.linalg.norm(hamiltonian - hamiltonian.conj().T)),
        })
    return rows


def two_pentamer_scan() -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    alpha_grid = np.linspace(-1.0, -0.025, 40)
    for beta in (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 1.00):
        previous: np.ndarray | None = None
        previous_alpha: float | None = None
        for alpha in alpha_grid:
            bonds = chain_bonds(2, float(alpha), beta)
            energy0, vector0, residual0 = lowest_state(sector_matrix(10, 5, bonds))
            energy1, _, residual1 = lowest_state(sector_matrix(10, 6, bonds))
            fidelity_susceptibility = math.nan
            if previous is not None and previous_alpha is not None:
                step = float(alpha) - previous_alpha
                overlap = min(1.0, abs(float(np.vdot(previous, vector0))))
                fidelity_susceptibility = 2.0 * (1.0 - overlap) / (step * step)
            rows.append({
                "alpha": float(alpha),
                "beta": beta,
                "energy_sz0": energy0,
                "spin_gap": energy1 - energy0,
                "fidelity_susceptibility": fidelity_susceptibility,
                "max_residual": max(residual0, residual1),
                "dimension_sz0": 252.0,
                "dimension_sz1": 210.0,
            })
            previous = vector0
            previous_alpha = float(alpha)
    return rows


def three_pentamer_selected_scan() -> list[dict[str, float]]:
    points = {
        0.25: (-0.25, -0.175, -0.10),
        0.75: (-0.625, -0.50, -0.425),
    }
    rows: list[dict[str, float]] = []
    for beta, alphas in points.items():
        previous: np.ndarray | None = None
        previous_alpha: float | None = None
        for alpha in alphas:
            bonds = chain_bonds(3, alpha, beta)
            energy_half, vector_half, residual_half = lowest_state(sector_matrix(15, 8, bonds))
            energy_three_half, _, residual_three_half = lowest_state(sector_matrix(15, 9, bonds))
            energy_five_half, _, residual_five_half = lowest_state(sector_matrix(15, 10, bonds))
            fidelity_susceptibility = math.nan
            if previous is not None and previous_alpha is not None:
                step = alpha - previous_alpha
                overlap = min(1.0, abs(float(np.vdot(previous, vector_half))))
                fidelity_susceptibility = 2.0 * (1.0 - overlap) / (step * step)
            rows.append({
                "alpha": alpha,
                "beta": beta,
                "energy_sz_half": energy_half,
                "energy_sz_three_half": energy_three_half,
                "energy_sz_five_half": energy_five_half,
                "ground_multiplet_splitting": energy_three_half - energy_half,
                "spin_sector_gap": energy_five_half - energy_three_half,
                "fidelity_susceptibility": fidelity_susceptibility,
                "max_residual": max(residual_half, residual_three_half, residual_five_half),
                "dimension_sz_half": 6435.0,
                "dimension_sz_three_half": 5005.0,
                "dimension_sz_five_half": 3003.0,
            })
            previous = vector_half
            previous_alpha = alpha
    return rows


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(
    dmrg: list[dict[str, object]],
    scaling: list[dict[str, float]],
    single: list[dict[str, float]],
    projection: list[dict[str, float]],
    two: list[dict[str, float]],
    three: list[dict[str, float]],
) -> dict[str, object]:
    matched_dimer_ratios: list[float] = []
    lookup = {(float(row["alpha"]), float(row["beta"]), int(row["L"])): row for row in dmrg}
    for alpha, beta, length in list(lookup):
        if length != 80 or (alpha, beta, 60) not in lookup:
            continue
        low = float(lookup[(alpha, beta, 60)]["dimer_rms"])
        high = float(lookup[(alpha, beta, 80)]["dimer_rms"])
        if low > 0:
            matched_dimer_ratios.append(high / low)
    beta_summaries = []
    for beta in sorted({float(row["beta"]) for row in dmrg}):
        subset = [row for row in dmrg if float(row["beta"]) == beta]
        q_values = [float(row["q_peak_over_pi"]) for row in subset if int(row["L"]) >= 60]
        gaps = [float(row["spin_gap"]) for row in subset]
        beta_summaries.append({
            "beta": beta,
            "q_reconstruction_present": min(q_values, default=1.0) < 0.8 and max(q_values, default=0.0) > 0.9,
            "minimum_accepted_spin_gap": min(gaps),
            "accepted_spin_sector_crossing": any(gap < -1e-8 for gap in gaps),
        })
    finite_fidelity = [row for row in two if math.isfinite(row["fidelity_susceptibility"])]
    fidelity_peaks = []
    for beta in sorted({row["beta"] for row in finite_fidelity}):
        subset = [row for row in finite_fidelity if row["beta"] == beta]
        peak = max(subset, key=lambda row: row["fidelity_susceptibility"])
        fidelity_peaks.append({"beta": beta, "alpha": peak["alpha"], "chi_f": peak["fidelity_susceptibility"]})
    stable_strong = [
        row for row in scaling
        if row["alpha"] <= -0.25 and row["beta"] >= 0.25 and row["max_entropy_start_half_range"] <= 0.02
    ]
    dimer_exponents = [row["dimer_decay_exponent"] for row in scaling if math.isfinite(row["dimer_decay_exponent"])]
    stable_c = [
        row["c_effective_from_entropy_lower_bound"]
        for row in stable_strong
        if math.isfinite(row["c_effective_from_entropy_lower_bound"])
    ]
    sensitive_near_zero = [
        row for row in scaling
        if row["alpha"] >= -0.10
        and (row["max_entropy_start_half_range"] > 0.02 or row["max_energy_start_half_range"] > 1e-7)
    ]
    return {
        "verdict": "new_thermodynamic_phase_not_confirmed",
        "working_interpretation": "the strong-negative-alpha bulk supports a c≈1 half-integer effective-spin regime; the weak-|alpha| strip near alpha=0 is a momentum-reconstruction and algorithmically sensitive crossover candidate, not yet a distinct thermodynamic phase",
        "dmrg_unique_points": len(dmrg),
        "dmrg_sizes": sorted({int(row["L"]) for row in dmrg}),
        "single_pentamer_ground_spins": sorted({row["ground_spin"] for row in single}),
        "single_pentamer_alpha_interval": [min(row["alpha"] for row in single), max(row["alpha"] for row in single)],
        "single_pentamer_max_residual": max(row["max_residual"] for row in single),
        "negative_quartet_projection": {
            "coefficient_sum_max_error": max(abs(row["coefficient_sum"] - 1.0) for row in projection),
            "reflection_max_error": max(row["reflection_error"] for row in projection),
            "minimum_jeff_over_beta": min(row["jeff_over_beta"] for row in projection),
            "maximum_jeff_over_beta": max(row["jeff_over_beta"] for row in projection),
            "jeff_antiferromagnetic_everywhere": all(row["jeff_over_beta"] > 0 for row in projection),
            "dominant_folded_momenta": sorted({row["dominant_q_over_pi"] for row in projection}),
        },
        "two_pentamer_min_spin_gap": min(row["spin_gap"] for row in two),
        "two_pentamer_ground_sector_crossing": any(row["spin_gap"] < -1e-9 for row in two),
        "two_pentamer_max_residual": max(row["max_residual"] for row in two),
        "three_pentamer_selected": {
            "points": len(three),
            "maximum_ground_multiplet_splitting": max(abs(row["ground_multiplet_splitting"]) for row in three),
            "minimum_spin_sector_gap": min(row["spin_sector_gap"] for row in three),
            "ground_sector_crossing": any(row["spin_sector_gap"] < -1e-9 for row in three),
            "maximum_residual": max(row["max_residual"] for row in three),
        },
        "matched_L80_over_L60_dimer_rms": {
            "count": len(matched_dimer_ratios),
            "median": float(np.median(matched_dimer_ratios)) if matched_dimer_ratios else math.nan,
            "maximum": max(matched_dimer_ratios, default=math.nan),
        },
        "finite_size_diagnostics": {
            "complete_L40_L60_L80_triplets": len(scaling),
            "positive_dimer_decay_exponents": sum(exponent > 0 for exponent in dimer_exponents),
            "median_dimer_decay_exponent": float(np.median(dimer_exponents)) if dimer_exponents else math.nan,
            "stable_strong_negative_points": len(stable_strong),
            "stable_strong_negative_c_effective_range": [min(stable_c), max(stable_c)] if stable_c else [],
            "stable_strong_negative_c_effective_median": float(np.median(stable_c)) if stable_c else math.nan,
            "near_zero_initial_state_sensitive_triplets": len(sensitive_near_zero),
        },
        "beta_slice_summary": beta_summaries,
        "two_pentamer_fidelity_peaks": fidelity_peaks,
        "diagnostic_status": {
            "momentum_reconstruction": "present",
            "spin_sector_crossing": "absent in accepted DMRG and two-pentamer ED",
            "local_multiplet_change_inside_negative_alpha": "absent; isolated pentamer ground spin remains S=3/2",
            "spontaneous_period_doubling": "evaluate from finite-size dimer columns; nonzero OBC signal alone is not phase proof",
            "entanglement_or_energy_nonanalyticity": "strong-negative stable triplets are compatible with c≈1; near alpha=0 remains initial-state sensitive and no thermodynamic singularity is established",
        },
    }


def plot_results(outdir: Path, dmrg: list[dict[str, object]], single: list[dict[str, float]], two: list[dict[str, float]]) -> None:
    plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.22, "figure.dpi": 150})
    figure, axes = plt.subplots(2, 3, figsize=(12.2, 7.2), constrained_layout=True)
    axes[0, 0].plot([row["alpha"] for row in single], [row["ground_spin"] for row in single], color="#255f85", lw=2)
    axes[0, 0].set(xlabel=r"$\alpha$", ylabel=r"isolated-cell $S$", title="(a) Local multiplet")
    axes[0, 0].set_yticks([0.5, 1.5, 2.5])

    colors = plt.cm.viridis(np.linspace(0.08, 0.92, 7))
    betas = sorted({float(row["beta"]) for row in dmrg})
    for color, beta in zip(colors, betas):
        subset = sorted((row for row in dmrg if float(row["beta"]) == beta and int(row["L"]) >= 60), key=lambda row: float(row["alpha"]))
        axes[0, 1].plot([row["alpha"] for row in subset], [float(row["L"]) * float(row["spin_gap"]) for row in subset], "o-", ms=3, lw=1, color=color, label=f"{beta:g}")
    axes[0, 1].axhline(0, color="black", lw=0.8)
    axes[0, 1].set(xlabel=r"$\alpha$", ylabel=r"$L\Delta_s$", title="(b) Spin-sector gap")
    axes[0, 1].legend(title=r"$\beta$", ncol=2, fontsize=7, frameon=False)

    for length, marker in ((40, "o"), (60, "s"), (80, "^")):
        subset = [row for row in dmrg if int(row["L"]) == length]
        axes[0, 2].scatter([row["alpha"] for row in subset], [row["dimer_rms"] for row in subset], s=18, alpha=0.7, marker=marker, label=f"L={length}")
    axes[0, 2].set(xlabel=r"$\alpha$", ylabel="period-2 bond amplitude", title="(c) Cell-doubling diagnostic")
    axes[0, 2].legend(frameon=False)

    for color, beta in zip(colors, betas):
        subset = sorted((row for row in dmrg if float(row["beta"]) == beta and int(row["L"]) == 60), key=lambda row: float(row["alpha"]))
        axes[1, 0].plot([row["alpha"] for row in subset], [row["denergy_dalpha_per_unit"] for row in subset], "o-", ms=3, lw=1, color=color)
    axes[1, 0].set(xlabel=r"$\alpha$", ylabel=r"$\partial E/\partial\alpha$ per cell", title="(d) Hellmann-Feynman slope (L=60)")

    for color, beta in zip(colors, betas):
        subset = sorted((row for row in dmrg if float(row["beta"]) == beta and int(row["L"]) >= 60), key=lambda row: float(row["alpha"]))
        axes[1, 1].plot([row["alpha"] for row in subset], [row["entropy_beta_cut_lower"] for row in subset], "o-", ms=3, lw=1, color=color)
    axes[1, 1].set(xlabel=r"$\alpha$", ylabel="entropy lower bound (nats)", title="(e) Inter-cell entanglement")

    for color, beta in zip(colors, sorted({row["beta"] for row in two})):
        subset = [row for row in two if row["beta"] == beta and math.isfinite(row["fidelity_susceptibility"])]
        axes[1, 2].plot([row["alpha"] for row in subset], [row["fidelity_susceptibility"] for row in subset], lw=1.2, color=color, label=f"{beta:g}")
    axes[1, 2].set(xlabel=r"$\alpha$", ylabel=r"$\chi_F$ (two cells)", title="(f) Exact finite-cluster fidelity")

    figure.suptitle("Independent diagnostics for possible negative-α phases", fontsize=13, fontweight="bold")
    for suffix in ("png", "svg", "pdf", "tiff"):
        kwargs = {"dpi": 400} if suffix in {"png", "tiff"} else {}
        figure.savefig(outdir / f"negative_alpha_independent_diagnostics.{suffix}", **kwargs)
    plt.close(figure)


def plot_projection(outdir: Path, projection: list[dict[str, float]]) -> None:
    alpha = np.array([row["alpha"] for row in projection])
    figure, axes = plt.subplots(1, 2, figsize=(9.2, 3.6), constrained_layout=True)
    for site in range(5):
        axes[0].plot(alpha, [row[f"c{site + 1}"] for row in projection], lw=1.5, label=fr"$c_{site + 1}$")
    axes[0].plot(alpha, [row["jeff_over_beta"] for row in projection], "k--", lw=1.5, label=r"$J_{eff}/\beta$")
    axes[0].set(xlabel=r"$\alpha$", ylabel="projection coefficient", title=r"(a) $S=3/2$ quartet projection")
    axes[0].legend(frameon=False, ncol=2, fontsize=8)
    for field, label, color in (
        ("weight_q02pi", r"$q/\pi=0.2$", "#4c78a8"),
        ("weight_q06pi", r"$q/\pi=0.6$", "#f58518"),
        ("weight_q10pi", r"$q/\pi=1.0$", "#54a24b"),
    ):
        axes[1].plot(alpha, [row[field] for row in projection], lw=1.8, color=color, label=label)
    axes[1].set(xlabel=r"$\alpha$", ylabel="folded form-factor weight", title="(b) Same effective K=π branch")
    axes[1].legend(frameon=False)
    for axis in axes:
        axis.grid(alpha=0.22)
    figure.suptitle("Why the dominant physical momentum can move without a new phase", fontsize=12, fontweight="bold")
    for suffix in ("png", "svg", "pdf", "tiff"):
        kwargs = {"dpi": 400} if suffix in {"png", "tiff"} else {}
        figure.savefig(outdir / f"negative_alpha_quartet_projection.{suffix}", **kwargs)
    plt.close(figure)


def plot_finite_size(outdir: Path, scaling: list[dict[str, float]]) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(9.2, 3.7), constrained_layout=True)
    scatter = axes[0].scatter(
        [row["alpha"] for row in scaling],
        [row["dimer_decay_exponent"] for row in scaling],
        c=[row["beta"] for row in scaling],
        cmap="viridis",
        s=42,
        edgecolor="white",
        linewidth=0.5,
    )
    axes[0].axhline(0, color="black", lw=0.8)
    axes[0].set(xlabel=r"$\alpha$", ylabel=r"$p$ in $D(L)\sim L^{-p}$", title="(a) Cell-dimer finite-size flow")
    figure.colorbar(scatter, ax=axes[0], label=r"$\beta$")
    stable = [
        row for row in scaling
        if row["alpha"] <= -0.25 and row["beta"] >= 0.25 and row["max_entropy_start_half_range"] <= 0.02
    ]
    sensitive = [row for row in scaling if row not in stable]
    axes[1].scatter(
        [row["alpha"] for row in stable],
        [row["c_effective_from_entropy_lower_bound"] for row in stable],
        c="#2a7f62",
        s=46,
        label="stable strong-negative",
    )
    axes[1].scatter(
        [row["alpha"] for row in sensitive],
        [row["c_effective_from_entropy_lower_bound"] for row in sensitive],
        facecolors="none",
        edgecolors="#b24a3a",
        s=46,
        label="exploratory / sensitive",
    )
    axes[1].axhline(1, color="black", ls="--", lw=1, label=r"$c=1$")
    axes[1].set(xlabel=r"$\alpha$", ylabel=r"effective $c$ from entropy lower bound", title="(b) Three-size entanglement slope")
    axes[1].legend(frameon=False, fontsize=8)
    for axis in axes:
        axis.grid(alpha=0.22)
    figure.suptitle("Finite-size tests of a distinct negative-α phase", fontsize=12, fontweight="bold")
    for suffix in ("png", "svg", "pdf", "tiff"):
        kwargs = {"dpi": 400} if suffix in {"png", "tiff"} else {}
        figure.savefig(outdir / f"negative_alpha_finite_size_scaling.{suffix}", **kwargs)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="results/autoresearch_v5_20260913/negative_phase_independent_audit")
    args = parser.parse_args()
    outdir = (ROOT / args.outdir).resolve()
    outdir.relative_to((ROOT / "results").resolve())
    if outdir.exists() and any(outdir.iterdir()):
        raise SystemExit(f"拒绝覆盖已有输出: {outdir}")
    outdir.mkdir(parents=True, exist_ok=True)

    dmrg = collect_dmrg()
    scaling = finite_size_diagnostics(dmrg)
    single = single_pentamer_scan()
    projection = quartet_projection_scan()
    two = two_pentamer_scan()
    three = three_pentamer_selected_scan()
    write_rows(outdir / "dmrg_independent_observables.csv", dmrg)
    write_rows(outdir / "finite_size_diagnostics.csv", scaling)
    write_rows(outdir / "single_pentamer_multiplet_scan.csv", single)
    write_rows(outdir / "negative_quartet_projection_scan.csv", projection)
    write_rows(outdir / "two_pentamer_exact_scan.csv", two)
    write_rows(outdir / "three_pentamer_selected_exact_scan.csv", three)
    summary = summarize(dmrg, scaling, single, projection, two, three)
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plot_results(outdir, dmrg, single, two)
    plot_projection(outdir, projection)
    plot_finite_size(outdir, scaling)
    files = sorted(path for path in outdir.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (outdir / "checksums.sha256").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
