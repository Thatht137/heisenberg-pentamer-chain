#!/usr/bin/env python3
"""测试 R16 验证器的通过、篡改和能量分支失败路径。"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import tempfile
from pathlib import Path
from typing import Any

from validate_negative_phase_r16_run import CELL, MODES, RESULTS, validate


PARAMS = {"alpha": -0.05, "beta": 0.5, "L": 80, "n_units": 16}
HASH = "a" * 64


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_checksums(directory: Path) -> None:
    files = sorted(path for path in directory.iterdir() if path.is_file() and path.name != "checksums.sha256")
    with (directory / "checksums.sha256").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(f"{sha256(path)}  {path.name}\n" for path in files))


def child_manifest(mode: str, energy0: float, energy1: float, ratios: dict[str, float]) -> dict[str, Any]:
    acceptance = {
        "execution_success": True, "variance_sz0_per_site_le_1e-8": True,
        "variance_sz1_per_site_le_1e-8": True, "truncation_sz0_le_1e-9": True,
        "truncation_sz1_le_1e-9": True, "sz0_sector": True, "sz1_sector": True,
        "nonnegative_gap": True, "all_sweeps_completed": True, "fullq_file": True,
        "fullq_count": True, "measurement_files": True,
        "energy_plateau_sz0": True, "energy_plateau_sz1": True,
    }
    return {
        "schema_version": 1, "cell_id": f"{CELL}-{mode}", "status": "success", "accepted": True,
        "params": {"path_id": CELL, "group": 0, "role": "ridge"} | PARAMS,
        "settings": {"method": "finite_dmrg", "boundary": "OBC", "sectors": ["Sz=0", "Sz=1"],
                     "maxdim": 1200, "nsweeps": 256, "cutoff": 1e-11, "threads": 8,
                     "init_mode_sz0": mode, "init_mode_sz1": "center", "q_count": 401,
                     "noise_profile": "repair", "random_seed": 20260811, "energy_change_max": 1e-8},
        "observables": {"energy_sz0": energy0, "energy_sz1": energy1, "spin_gap": energy1 - energy0,
                        "structure_factor_ratio": ratios["pi"],
                        "structure_factor_peak_q_over_pi": ratios["q"],
                        "structure_factor_peak": ratios["peak"],
                        "dominant_structure_factor_ratio": ratios["ratio"]},
        "diagnostics": {"variance_per_site_sz0": 1e-10, "variance_per_site_sz1": 2e-10,
                        "final_truncation_error_sz0": 1e-11, "final_truncation_error_sz1": 1e-11,
                        "final_energy_change_sz0": 2e-9, "final_energy_change_sz1": 3e-9,
                        "total_sz0": 0.0, "total_sz1": 1.0,
                        "nsweeps_completed_sz0": 256, "nsweeps_completed_sz1": 256,
                        "initial_seed_sz0": 20260811 + 17 * 80 + {"center_random": 101, "ferro_j2": 307, "domain": 211}[mode],
                        "initial_seed_sz1": -1},
        "acceptance": acceptance,
        "provenance": {"standard_sha256": HASH, "manifest_sha256": HASH,
                       "noise_protocol": "repair", "code_sha256": {"synthetic": HASH}},
    }


def write_fullq(path: Path) -> None:
    lines = ["q,q_over_pi,Sq\n"]
    for index in range(401):
        q_over_pi = index / 400
        lines.append(f"{math.pi * q_over_pi:.17g},{q_over_pi:.17g},{1 + q_over_pi:.17g}\n")
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(lines))


def make_fixture(root: Path) -> tuple[Path, Path]:
    spec_path = root / "parameter-scan.run_spec.json"
    spec = {
        "schema_version": 1, "cells": [{"cell_id": CELL, "params": PARAMS, "budget": 256,
            "retry_of": "nega-r15-a0050-b0500-L080", "calibration_only": True,
            "controller_action_id": None}],
        "settings": {"nsweeps": 256, "cutoff": 1e-11, "threads": 8, "q_count": 401,
            "maxdim_by_L": {"80": 1200}, "init_modes": list(MODES), "noise_profile": "repair",
            "random_seed": 20260811, "energy_change_max": 1e-8, "energy_spread_max": 1e-6,
            "acceptance": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
                "sector_tolerance": 1e-8, "spin_gap_min": -1e-8,
                "energy_change_max": 1e-8, "energy_spread_max": 1e-6, "q_count_min": 401}},
        "provenance": {"standard_sha256": HASH, "manifest_sha256": HASH,
            "code_sha256": {"synthetic": HASH}, "thresholds_relaxed": False,
            "posthoc_branch_selection_forbidden": True},
    }
    write_json(spec_path, spec)
    run = root / CELL
    ratios_by_mode = {
        "center_random": {"pi": 0.10, "q": 0.9000, "peak": 2.0, "ratio": 0.20},
        "ferro_j2": {"pi": 0.12, "q": 0.9025, "peak": 2.2, "ratio": 0.22},
        "domain": {"pi": 0.11, "q": 0.9000, "peak": 2.1, "ratio": 0.21},
    }
    energies = {
        "center_random": (-10.0, -9.9999),
        "ferro_j2": (-9.9999998, -9.9998998),
        "domain": (-9.9999996, -9.9998996),
    }
    children: dict[str, dict[str, Any]] = {}
    for mode in MODES:
        directory = run / f"start_{mode}"
        manifest = child_manifest(mode, *energies[mode], ratios_by_mode[mode])
        children[mode] = manifest
        write_json(directory / "manifest.json", manifest)
        write_json(directory / "status.json", {"status": "success", "accepted": True, "returncode": 0})
        write_fullq(directory / "structure_factor_fullq.csv")
        for name in ("string_profile.csv", "bond_correlations.csv", "schmidt_spectrum.csv"):
            with (directory / name).open("w", encoding="utf-8", newline="\n") as handle:
                handle.write("x,y\n0,0\n")
        write_checksums(directory)
    truncation_floor = 1e-4

    def aggregate(key: str, floor: float) -> dict[str, float]:
        values = [float(children[mode]["observables"][key]) for mode in MODES]
        return {"value": sum(values) / 3, "error": max((max(values) - min(values)) / 2, floor)}

    parent = {
        "schema_version": 1, "cell_id": CELL, "status": "success", "accepted": True,
        "params": PARAMS,
        "settings": {"method": "finite_dmrg_multistart", "boundary": "OBC", "sectors": ["Sz=0", "Sz=1"],
            "maxdim": 1200, "nsweeps": 256, "budget": 256, "cutoff": 1e-11, "threads": 8,
            "init_modes": list(MODES), "q_count": 401, "noise_profile": "repair",
            "random_seed": 20260811, "energy_change_max": 1e-8, "energy_spread_max": 1e-6},
        "observables": {
            "structure_factor_ratio": aggregate("structure_factor_ratio", truncation_floor),
            "structure_factor_peak_q_over_pi": aggregate("structure_factor_peak_q_over_pi", 1 / 400),
            "structure_factor_peak": aggregate("structure_factor_peak", truncation_floor),
            "dominant_structure_factor_ratio": aggregate("dominant_structure_factor_ratio", truncation_floor),
            "structure_factor_peak_ratio": aggregate("dominant_structure_factor_ratio", truncation_floor),
        },
        "diagnostics": {"child_manifests": [f"start_{mode}/manifest.json" for mode in MODES],
            "independent_start_half_range": {"pi_ratio": 0.01, "q_peak_over_pi": 0.00125,
                                             "peak": 0.1, "peak_ratio": 0.01},
            "independent_start_energy_spread": {"sz0": 4e-7, "sz1": 4e-7}},
        "acceptance": {"children_completed": True, "children_accepted": True,
            "finite_pi_ratio": True, "finite_q_peak": True, "finite_peak": True,
            "finite_peak_ratio": True, "energy_consistency": True},
        "provenance": {"standard_sha256": HASH, "manifest_sha256": HASH,
            "code_sha256": {"synthetic": HASH}},
    }
    write_json(run / "manifest.json", parent)
    write_json(run / "status.json", {"status": "success", "accepted": True, "returncode": 0})
    write_checksums(run)
    return run, spec_path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="r16-validator-", dir=RESULTS) as temporary:
        base = Path(temporary)
        pass_run, spec = make_fixture(base / "pass")
        passed = validate(pass_run, spec)
        if passed["status"] != "pass" or not all(passed["checks"].values()):
            raise AssertionError(f"合成 PASS 未通过: {passed['failures']}")

        tamper_root = base / "tamper"
        shutil.copytree(base / "pass", tamper_root)
        tamper_run = tamper_root / CELL
        target = tamper_run / "start_domain" / "manifest.json"
        tampered = json.loads(target.read_text(encoding="utf-8"))
        tampered["synthetic_tamper"] = True
        write_json(target, tampered)
        tamper = validate(tamper_run, tamper_root / spec.name)
        if tamper["status"] != "fail" or tamper["checks"]["child_checksums"] is not False:
            raise AssertionError("内容篡改未被 child checksum 拒绝")

        spread_root = base / "spread"
        shutil.copytree(base / "pass", spread_root)
        spread_run = spread_root / CELL
        child_path = spread_run / "start_domain" / "manifest.json"
        child = json.loads(child_path.read_text(encoding="utf-8"))
        child["observables"]["energy_sz0"] += 2e-6
        child["observables"]["energy_sz1"] += 2e-6
        write_json(child_path, child)
        write_checksums(child_path.parent)
        parent_path = spread_run / "manifest.json"
        parent = json.loads(parent_path.read_text(encoding="utf-8"))
        parent["status"] = "failed"
        parent["accepted"] = False
        parent["acceptance"]["energy_consistency"] = False
        parent["diagnostics"]["independent_start_energy_spread"] = {"sz0": 2.4e-6, "sz1": 2.4e-6}
        write_json(parent_path, parent)
        write_json(spread_run / "status.json", {"status": "failed", "accepted": False, "returncode": 1})
        write_checksums(spread_run)
        spread = validate(spread_run, spread_root / spec.name)
        if (
            spread["status"] != "fail" or spread["checks"]["energy_consistency"] is not False
            or spread["checks"]["parent_checksums"] is not True
            or spread["checks"]["child_checksums"] is not True
        ):
            raise AssertionError(f"能量 spread 失败路径错误: {spread}")
        print(json.dumps({"status": "pass", "cases": {
            "strict_pass": passed["status"], "tamper": tamper["status"],
            "energy_spread": spread["status"]}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
