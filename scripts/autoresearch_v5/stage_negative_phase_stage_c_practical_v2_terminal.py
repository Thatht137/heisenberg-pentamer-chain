#!/usr/bin/env python3
"""组装 Practical V2 Stage C 终态证据。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--launch-contract", type=Path, required=True)
    parser.add_argument("--stage-b-summary", type=Path, required=True)
    parser.add_argument("--phase-dir", type=Path, required=True)
    parser.add_argument("--round", type=int, default=1)
    return parser.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def key(params: dict[str, Any]) -> tuple[float, float, int]:
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def write_json(path: Path, value: Any) -> None:
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


def main() -> int:
    args = parse_args()
    fetch = args.fetch_dir.resolve()
    spec_path = args.run_spec.resolve()
    analysis_path = args.analysis.resolve()
    contract_path = args.launch_contract.resolve()
    summary_path = args.stage_b_summary.resolve()
    phase = args.phase_dir.resolve()
    for path in (fetch, spec_path, analysis_path, contract_path, summary_path, phase):
        if not path.exists():
            raise FileNotFoundError(path)
    spec, analysis, contract, stage_b = map(load, (spec_path, analysis_path, contract_path, summary_path))
    cells = spec.get("cells", [])
    actions = {row["action_id"]: row for row in analysis.get("stage_c_actions", [])}
    if (
        stage_b.get("status") != "accepted_stage_b_complete_with_bounded"
        or contract.get("launch_ready") is not True
        or contract.get("practical_v2") is not True
        or contract.get("run_spec_sha256") != sha256(spec_path)
        or contract.get("analysis_sha256") != sha256(analysis_path)
        or spec.get("provenance", {}).get("stage_b_summary_sha256") != sha256(summary_path)
        or spec.get("provenance", {}).get("stage_b_analysis_sha256") != sha256(analysis_path)
        or len(cells) != len(actions)
        or not cells
        or any(int(cell.get("budget", 0)) != 64 for cell in cells)
    ):
        raise ValueError("Practical V2 Stage C 输入证据不匹配")

    records: list[dict[str, Any]] = []
    action_results: list[dict[str, Any]] = []
    for cell in cells:
        cell_id = cell["cell_id"]
        action = dict(actions.get(cell["controller_action_id"], {}))
        run_dir = fetch / cell_id
        validation_path = fetch / "validation" / f"{cell_id}.json"
        receipt_path = fetch / "receipts" / f"{cell_id}.json"
        manifest_path = run_dir / "manifest.json"
        for path in (validation_path, receipt_path, manifest_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        validation, receipt, manifest = map(load, (validation_path, receipt_path, manifest_path))
        if (
            not action
            or key(action["params"]) != key(cell["params"])
            or validation.get("status") != "pass"
            or validation.get("acceptance_label") != "accepted_under_practical_v2"
            or validation.get("failures") != []
            or validation.get("thresholds", {}).get("variance_per_site_max") != 5e-8
            or validation.get("provenance", {}).get("original_manifest_sha256") != sha256(manifest_path)
            or receipt.get("status") != "pass"
            or receipt.get("non_clobbering") is not True
            or receipt.get("cell_id") != cell_id
            or manifest.get("status") != "success"
            or manifest.get("accepted") is not True
            or key(manifest["params"]) != key(cell["params"])
            or int(manifest["settings"]["nsweeps"]) != 64
        ):
            raise ValueError(f"Stage C 证据不一致: {cell_id}")
        ratio = manifest["observables"]["dominant_structure_factor_ratio"]
        records.append({
            "params": cell["params"], "status": "success",
            "value": ratio["value"], "error": ratio["error"], "budget": 64,
            "artifact": relative(manifest_path), "accepted_only": True,
            "boundary_eligible": True, "controller_action_id": cell["controller_action_id"],
            "diagnostics": {"q_peak_over_pi": manifest["observables"]["structure_factor_peak_q_over_pi"]},
            "validation": {"artifact": relative(validation_path), "sha256": sha256(validation_path),
                           "policy": "Practical V2"},
            "checksum_receipt": {"artifact": relative(receipt_path), "sha256": sha256(receipt_path)},
            "provenance": manifest["provenance"],
        })
        action.update({"observation_status": "success", "accepted": True,
                       "terminal_state": "validated", "artifact": relative(manifest_path)})
        action_results.append(action)

    stage_name = f"C-Practical-V2-R{args.round}"
    observations_out = phase / f"stage_c_practical_v2_r{args.round}_terminal_observations.json"
    actions_out = phase / f"stage_c_practical_v2_r{args.round}_terminal_action_results.json"
    summary_out = phase / f"stage_c_practical_v2_r{args.round}_terminal_summary.json"
    write_json(observations_out, {"schema_version": 1, "stage": stage_name, "records": records})
    write_json(actions_out, {"schema_version": 1, "stage": stage_name,
                             "canonical_action_index_mutated": False, "actions": action_results})
    summary = {
        "schema_version": 1, "status": "accepted_stage_c_round_complete",
        "policy": "Practical V2", "round": args.round,
        "counts": {"success": len(records), "failed": 0, "pending": 0},
        "planned_cells": len(cells),
        "observations": {"artifact": relative(observations_out), "sha256": sha256(observations_out)},
        "action_results": {"artifact": relative(actions_out), "sha256": sha256(actions_out)},
        "stage_b_summary": {"artifact": relative(summary_path), "sha256": None},
        "next_analysis_ready": True, "stage_d_ready": False,
        "canonical_controller_mutated": False, "boundary_thresholds_relaxed": False,
        "max_sweeps": 64,
    }
    summary["stage_b_summary"]["sha256"] = sha256(summary_path)
    write_json(summary_out, summary)
    print(json.dumps({"status": summary["status"], "round": args.round,
                      "success": len(records), "summary": relative(summary_out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
