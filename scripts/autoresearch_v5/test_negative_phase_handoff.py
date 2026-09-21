#!/usr/bin/env python3
"""负 alpha 回传验收链的最小合成测试。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def checksums(path: Path) -> None:
    files = sorted(item for item in path.iterdir() if item.is_file() and item.name != "checksums.sha256")
    (path / "checksums.sha256").write_text("".join(f"{sha256(item)}  {item.name}\n" for item in files), encoding="utf-8")


def load_validator():
    source = ROOT / "scripts" / "autoresearch_v5" / "validate_negative_phase_run.py"
    spec = importlib.util.spec_from_file_location("negative_validator", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def child(run: Path, parent_id: str, mode: str) -> None:
    out = run / f"start_{mode}"
    out.mkdir()
    h = "a" * 64
    manifest = {
        "cell_id": f"{parent_id}-{mode}", "status": "success", "accepted": True,
        "params": {"alpha": -0.5, "beta": 0.5, "L": 40, "n_units": 8},
        "settings": {"sectors": ["Sz=0", "Sz=1"], "nsweeps": 24, "q_count": 401,
                     "noise_profile": "repair", "energy_change_max": 1e-8},
        "observables": {"spin_gap": 1e-5},
        "diagnostics": {"variance_per_site_sz0": 1e-10, "variance_per_site_sz1": 1e-10,
                        "final_truncation_error_sz0": 1e-11, "final_truncation_error_sz1": 1e-11,
                        "final_energy_change_sz0": 1e-10, "final_energy_change_sz1": 1e-10,
                        "total_sz0": 0.0, "total_sz1": 1.0, "nsweeps_completed_sz0": 24, "nsweeps_completed_sz1": 24},
        "acceptance": {key: True for key in ("execution_success", "variance_sz0_per_site_le_1e-8", "variance_sz1_per_site_le_1e-8", "truncation_sz0_le_1e-9", "truncation_sz1_le_1e-9", "sz0_sector", "sz1_sector", "nonnegative_gap", "energy_plateau_sz0", "energy_plateau_sz1", "all_sweeps_completed", "fullq_file", "fullq_count", "measurement_files")},
        "provenance": {"standard_sha256": h, "manifest_sha256": h, "code_sha256": {"cell.jl": h}},
    }
    dump(out / "manifest.json", manifest)
    dump(out / "status.json", {"status": "success", "accepted": True})
    with (out / "structure_factor_fullq.csv").open("w", encoding="utf-8") as handle:
        handle.write("q,q_over_pi,Sq,window_sites\n")
        for index in range(401):
            handle.write(f"{index / 400:.16e},{index / 400:.16e},1.0,32\n")
    checksums(out)


def main() -> None:
    temporary = Path(tempfile.mkdtemp(prefix=".negative-handoff-test-", dir=RESULTS))
    try:
        run = temporary / "neg-cell-0001"
        run.mkdir()
        child(run, "neg-cell-0001", "center_random")
        child(run, "neg-cell-0001", "ferro_j2")
        child(run, "neg-cell-0001", "domain")
        h = "a" * 64
        parent = {
            "cell_id": "neg-cell-0001", "status": "success", "accepted": True,
            "params": {"alpha": -0.5, "beta": 0.5, "L": 40, "n_units": 8},
            "settings": {"nsweeps": 24, "q_count": 401, "sectors": ["Sz=0", "Sz=1"],
                         "init_modes": ["center_random", "ferro_j2", "domain"],
                         "noise_profile": "repair", "energy_change_max": 1e-8},
            "diagnostics": {"child_manifests": ["start_center_random/manifest.json", "start_ferro_j2/manifest.json", "start_domain/manifest.json"]},
            "observables": {"structure_factor_peak_q_over_pi": {"value": 1.0}, "dominant_structure_factor_ratio": {"value": 0.1}},
            "acceptance": {key: True for key in ("children_completed", "children_accepted", "finite_pi_ratio", "finite_q_peak", "finite_peak", "finite_peak_ratio")},
            "provenance": {"standard_sha256": h, "manifest_sha256": h, "code_sha256": {"runner.py": h}},
        }
        dump(run / "manifest.json", parent)
        dump(run / "status.json", {"status": "success", "accepted": True})
        checksums(run)
        run_spec = temporary / "negative.run_spec.json"
        dump(run_spec, {"cells": [{"cell_id": "neg-cell-0001", "params": parent["params"], "budget": 24}], "standard_sha256": h, "manifest_sha256": h})
        validator = load_validator()
        passed = validator.validate(run, run_spec)
        assert passed["status"] == "pass", passed["failures"]
        (run / "status.json").write_text('{"status":"success","accepted":false}\n', encoding="utf-8")
        rejected = validator.validate(run, run_spec)
        assert rejected["status"] == "fail"
        fullq = run / "start_center_random" / "structure_factor_fullq.csv"
        fullq.write_text("q,q_over_pi,Sq,window_sites\\n0,0,1,32\\n", encoding="utf-8")
        checksums(run / "start_center_random")
        literal_rejected = validator.validate(run, run_spec)
        assert literal_rejected["status"] == "fail"
        assert any("字面 \\n" in item for item in literal_rejected["failures"]), literal_rejected["failures"]
        print("negative phase handoff: PASS")
    finally:
        shutil.rmtree(temporary)


if __name__ == "__main__":
    main()
