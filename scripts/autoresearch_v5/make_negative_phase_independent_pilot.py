#!/usr/bin/env python3
"""生成负 alpha 新相保存态诊断包。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN_REL = "results/autoresearch_v5_20260913/negative_phase_independent_pilot_r1"
RUN = ROOT / RUN_REL
STANDARD = ROOT / "docs/negative_alpha_practical_convergence_standard_20260829.md"
AUDIT = ROOT / "results/autoresearch_v5_20260913/negative_phase_independent_audit_v6/summary.json"
LAUNCHER = "scripts/autoresearch_v5/launch_negative_phase_independent_pilot.sh"
SOURCES = [
    "Project.toml",
    "Manifest.toml",
    "docs/negative_alpha_practical_convergence_standard_20260829.md",
    "docs/negative_alpha_new_phase_audit_20260913.md",
    "src/PentamerChain.jl",
    "src/hamiltonian.jl",
    "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py",
    "scripts/autoresearch_v5/negative_dmrg_options.py",
    "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py",
    LAUNCHER,
]
POINTS = {
    0.25: (-0.25, -0.175, -0.10),
    0.75: (-0.625, -0.50, -0.425),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"拒绝覆盖: {path}")
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def token(value: float) -> str:
    return f"{round(abs(value) * 10000):05d}"


def main() -> None:
    for path in (STANDARD, AUDIT, *(ROOT / name for name in SOURCES)):
        if not path.is_file():
            raise FileNotFoundError(path)
    if RUN.exists():
        raise FileExistsError(RUN)
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if audit.get("verdict") != "new_thermodynamic_phase_not_confirmed":
        raise ValueError("独立审计状态不匹配")
    cells = []
    for beta, alphas in POINTS.items():
        for position, alpha in zip(("before", "middle", "after"), alphas):
            cells.append({
                "cell_id": f"negdiag-a{token(alpha)}-b{token(beta)}-L080",
                "params": {"alpha": alpha, "beta": beta, "L": 80, "n_units": 16},
                "budget": 64,
                "stage": "negative-alpha-independent-pilot-r1",
                "role": position,
            })
    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    spec = {
        "schema_version": 1,
        "run_id": "pentamer-negative-alpha-independent-pilot-r1-20260913",
        "scope": "six saved-state points testing a distinct phase; Fig.9 excluded",
        "cells": cells,
        "settings": {
            "method": "finite_dmrg_multistart_saved_state_enriched",
            "boundary": "OBC",
            "sectors": ["Sz=0", "Sz=1"],
            "maxdim_by_L": {"80": 1200},
            "nsweeps": 64,
            "cutoff": 1e-11,
            "threads": 8,
            "q_count": 401,
            "init_modes": ["center", "ferro_j2"],
            "variance_per_site_max": 5e-8,
            "save_state": True,
            "enriched_diagnostics": True,
            "offline": True,
            "execution": "direct SSH; concurrency=1; stop on first failed cell",
        },
        "acceptance": {
            "numerical": "both starts pass variance, truncation, Sz, gap and checksum gates",
            "required_files": ["state_sz0.jld2", "entropy_profile_full.csv", "bond_bond_connected.csv"],
            "phase_claim": "no new phase from q_peak alone; promote only after independent large-size signal",
        },
        "provenance": {
            "negative_alpha_included": True,
            "audit_sha256": sha256(AUDIT),
            "standard_sha256": sha256(STANDARD),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "source_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
            ).stdout.strip(),
            "code_sha256": code_hashes,
            "user_authorized_upload_and_launch": "2026-09-13",
            "phase_label_assigned": False,
        },
    }
    RUN.mkdir(parents=True)
    spec_path = RUN / "parameter-scan.run_spec.json"
    hashes_path = RUN / "source_hashes.sha256"
    write_json(spec_path, spec)
    hashes_path.write_text("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()), encoding="utf-8")
    contract = {
        "schema_version": 1,
        "launch_ready": True,
        "cell_count": len(cells),
        "concurrency": 1,
        "stop_on_first_failure": True,
        "save_state": True,
        "enriched_diagnostics": True,
        "eta_hours": {"low": 4, "high": 10},
        "run_spec_sha256": sha256(spec_path),
        "source_hashes_sha256": sha256(hashes_path),
        "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"),
    }
    contract_path = RUN / "launch-contract.json"
    write_json(contract_path, contract)
    files = SOURCES + [
        f"{RUN_REL}/parameter-scan.run_spec.json",
        f"{RUN_REL}/source_hashes.sha256",
        f"{RUN_REL}/launch-contract.json",
    ]
    write_json(RUN / "server_upload_manifest.json", {
        "schema_version": 1,
        "target": "/home/wangjieren/code/1x5_Heisenberg_Pentamer",
        "mode": "offline_upload_and_launch",
        "stage": "negative-alpha-independent-pilot-r1",
        "cell_count": len(cells),
        "concurrency": 1,
        "eta_hours": {"low": 4, "high": 10},
        "files": [
            {"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
            for name in files
        ],
    })
    print(json.dumps({"status": "pass", "cells": len(cells), "eta_hours": [4, 10], "files": len(files)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
