#!/usr/bin/env python3
"""生成负 alpha 相图阶段 A 的离线 run spec。"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260809" / "round44_phase_diagram_full_alpha"
STAGE = RUN / "stage-a-beta050-calibration"
PLAN = RUN / "campaign-plan.json"
POLICY = RUN / "phase-diagram-v2" / "phase-policy.json"
REPORT = RUN / "phase-diagram-v2" / "report.json"
STANDARD = ROOT / "docs" / "full_phase_diagram_negative_standard_20260809.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def action_id(spec: dict[str, object]) -> str:
    payload = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "act-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def label(value: float) -> str:
    return f"{abs(value):.3f}".replace(".", "")


def main() -> None:
    plan = read_json(PLAN)
    stage = next(item for item in plan["stages"] if item["id"] == "A")
    report = read_json(REPORT)
    authorized = {
        (
            float(item["spec"]["params"]["alpha"]),
            float(item["spec"]["params"]["beta"]),
            int(item["spec"]["params"]["L"]),
        ): item["spec"]
        for item in report["actions"]
    }
    cells: list[dict[str, object]] = []
    actions_dir = STAGE / "actions"
    for alpha in stage["alpha"]:
        for length in stage["L"]:
            params = {"alpha": float(alpha), "beta": 0.5, "L": int(length), "n_units": int(length) // 5}
            key = (params["alpha"], params["beta"], params["L"])
            spec = authorized.get(key)
            cell = {
                "cell_id": f"nega-a{label(float(alpha))}-b0500-L{int(length):03d}",
                "params": params,
                "budget": 32,
                "stage": "A",
                "controller_action_id": action_id(spec) if spec else None,
                "calibration_only": spec is None,
            }
            cells.append(cell)
            if spec:
                write_json(actions_dir / f"{cell['controller_action_id']}.json", spec)
    run_spec = {
        "schema_version": 1,
        "run_id": "pentamer-negative-phase-stage-a-20260809",
        "scope": "-1<=alpha<0, beta=0.5, L=40/60/80; static phase diagnostics; Fig.9 excluded",
        "policy": "../phase-diagram-v2/phase-policy.json",
        "controller": "local_only",
        "cells": cells,
        "settings": {
            "method": "finite_dmrg_multistart_fullq",
            "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"],
            "maxdim_by_L": {"40": 800, "60": 1000, "80": 1200},
            "nsweeps": 32,
            "cutoff": 1e-11,
            "threads": 8,
            "q_count": 401,
            "init_modes": ["center", "ferro_j2"],
            "budget_definition": "nsweeps per independent start",
            "observable_definition": "dominant peak-locked structure-factor ratio from connected central-window S(q)",
            "acceptance": {
                "variance_per_site_max": 1e-8,
                "final_truncation_error_max": 1e-9,
                "sector_tolerance": 1e-8,
                "q_count_min": 401,
            },
            "offline": True,
            "execution": "direct SSH; one heavy cell at a time; stop on first failed cell",
        },
        "provenance": {
            "negative_alpha_included": True,
            "policy_sha256": sha256(POLICY),
            "standard_sha256": sha256(STANDARD),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
            ).stdout.strip(),
            "exploratory_data_not_accepted": True,
        },
    }
    write_json(STAGE / "parameter-scan.run_spec.json", run_spec)
    print(json.dumps({"run_spec": str(STAGE / "parameter-scan.run_spec.json"), "cells": len(cells), "controller_actions": sum(cell["controller_action_id"] is not None for cell in cells)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
