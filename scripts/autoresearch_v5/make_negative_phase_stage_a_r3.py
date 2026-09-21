#!/usr/bin/env python3
"""在 R2 严格通过后生成阶段 A 剩余 13 个单元。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260809" / "round44_phase_diagram_full_alpha"
STAGE = RUN / "stage-a-beta050-calibration-r3-remaining13"
R1_SPEC = RUN / "stage-a-beta050-calibration-r1" / "parameter-scan.run_spec.json"
R1_VALIDATION = (
    RUN / "fetches" / "stage-a-beta050-calibration-r1-20260810-1113" / "validation" / "summary.json"
)
R1_INGEST = RUN / "phase-diagram-v2" / "r1_ingestion_summary.json"
R2_INGEST = RUN / "phase-diagram-v2" / "r2_ingestion_summary.json"
STANDARD = ROOT / "docs" / "full_phase_diagram_negative_standard_20260809.md"
R2_CELL = "nega-r2-a0350-b0500-L060"
R1_FAILED_CELL = "nega-r1-a0350-b0500-L060"
EXPECTED_REMAINING = {
    (-0.35, 0.5, 80),
    *{(alpha, 0.5, length) for alpha in (-0.25, -0.1, -0.05, -0.025) for length in (40, 60, 80)},
}
SOURCE_FILES = [
    "Project.toml",
    "Manifest.toml",
    "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl",
    "src/hamiltonian.jl",
    "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py",
    "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py",
    "scripts/autoresearch_v5/validate_negative_phase_run.py",
]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def key(cell: dict[str, Any]) -> tuple[float, float, int]:
    params = cell["params"]
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def label(value: float) -> str:
    return f"{abs(value):.3f}".replace(".", "")


def discover_r2_validation() -> Path:
    pattern = "stage-a-beta050-calibration-r2-a0350-L060-*/validation/summary.json"
    matches = sorted((RUN / "fetches").glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"R2 validator summary 必须唯一，当前 {len(matches)} 个")
    return matches[0]


def validate_r1(spec: dict[str, Any], validation: dict[str, Any], ingest: dict[str, Any]) -> set[str]:
    cells = {str(cell["cell_id"]): cell for cell in spec.get("cells", [])}
    if len(cells) != 24 or len({key(cell) for cell in cells.values()}) != 24:
        raise ValueError("R1 run spec 必须恰有 24 个唯一单元")
    rows = validation.get("rows")
    if not isinstance(rows, list) or validation.get("cell_count") != 11 or len(rows) != 11:
        raise ValueError("R1 validator summary 必须为 11 个已回传单元")
    passed = {str(row.get("cell_id")) for row in rows if row.get("validator_status") == "pass" and row.get("exit_code") == 0}
    failed = {str(row.get("cell_id")) for row in rows if row.get("validator_status") == "fail" and row.get("exit_code") == 1}
    if len(passed) != 10 or failed != {R1_FAILED_CELL} or passed & failed or not (passed | failed) <= cells.keys():
        raise ValueError("R1 validator 必须为 10 pass 与唯一声明失败")
    counts = ingest.get("counts", {})
    expected_counts = {
        "validator_pass": 10,
        "controller_accepted": 7,
        "calibration_accepted": 3,
        "controller_failed": 1,
        "controller_pending": 8,
    }
    if any(counts.get(name) != value for name, value in expected_counts.items()):
        raise ValueError("R1 ingest 计数与 accepted-only 状态不一致")
    if ingest.get("source", {}).get("validation_summary_sha256") != sha256(R1_VALIDATION):
        raise ValueError("R1 ingest 未绑定当前 validator summary")
    if ingest.get("failed_keys") != [{"alpha": -0.35, "beta": 0.5, "L": 60}]:
        raise ValueError("R1 ingest 失败键不匹配")
    return passed


def validate_r2(validation_path: Path, ingest_path: Path) -> None:
    validation = load(validation_path)
    rows = validation.get("rows")
    if validation.get("cell_count") != 1 or not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("R2 validator summary 必须恰有一个单元")
    if validation.get("status") != "pass" or validation.get("counts") != {"pass": 1, "fail": 0}:
        raise ValueError("R2 validator summary 总状态未通过")
    row = rows[0]
    if row.get("cell_id") != R2_CELL or row.get("validator_status") != "pass" or row.get("exit_code") != 0:
        raise ValueError("R2 单元尚未严格通过 validator")
    output = Path(str(row.get("output", "")))
    if not output.is_file():
        raise ValueError("R2 validator 输出文件缺失")
    detail = load(output)
    if detail.get("cell_id") != R2_CELL or detail.get("status") != "pass":
        raise ValueError("R2 validator 明细未通过")
    checks = detail.get("checks")
    if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
        raise ValueError("R2 validator 明细含未通过检查")
    ingest = load(ingest_path)
    counts = ingest.get("counts", {})
    expected_counts = {
        "validator_pass": 1,
        "controller_accepted": 1,
        "controller_failed": 0,
        "controller_success_total": 8,
        "controller_pending_total": 8,
    }
    if any(counts.get(name) != value for name, value in expected_counts.items()):
        raise ValueError("R2 ingest 未记录唯一 accepted controller 单元")
    source = ingest.get("validation_summary", {})
    if source.get("sha256") != sha256(validation_path):
        raise ValueError("R2 ingest 未绑定当前 validator summary")
    if ingest.get("status") != "accepted" or ingest.get("cell_id") != R2_CELL:
        raise ValueError("R2 ingest 状态或 cell 身份不匹配")
    expected = {"alpha": -0.35, "beta": 0.5, "L": 60}
    if ingest.get("accepted_key") != expected:
        raise ValueError("R2 ingest accepted key 不匹配")


def ensure_refresh_safe(refresh: bool) -> None:
    generated = [
        STAGE / "parameter-scan.run_spec.json",
        STAGE / "r3_source_hashes.sha256",
        STAGE / "launch-contract.json",
    ]
    if any(path.exists() for path in generated) and not refresh:
        raise ValueError("R3 launch-ready 文件已存在，拒绝覆盖")
    forbidden = [STAGE / "run_status.json", STAGE / "run.json", STAGE / "batch.pid", STAGE / "submission-receipt.json"]
    cells_dir = STAGE / "cells"
    if any(path.exists() for path in forbidden) or (cells_dir.exists() and any(cells_dir.iterdir())):
        raise ValueError("R3 已有提交或 cell 证据，拒绝刷新")


def planned_cells(spec: dict[str, Any], passed: set[str]) -> list[dict[str, Any]]:
    remaining = [cell for cell in spec["cells"] if cell["cell_id"] not in passed and cell["cell_id"] != R1_FAILED_CELL]
    if len(remaining) != 13 or {key(cell) for cell in remaining} != EXPECTED_REMAINING:
        raise ValueError("R1 减去 10 pass 与 R2 目标后不是声明的 13 个单元")
    result = []
    for source in remaining:
        alpha, beta, length = key(source)
        budget = 64 if length == 80 else 32
        result.append({
            "cell_id": f"nega-r3-a{label(alpha)}-b0500-L{length:03d}",
            "params": {"alpha": alpha, "beta": beta, "L": length, "n_units": length // 5},
            "budget": budget,
            "stage": "A-R3-remaining13",
            "retry_policy": "首次续跑；L40/L60=32、L80=64；失败时仅按 32->64->128 或 64->128",
            "continued_from": source["cell_id"],
            "controller_action_id": source.get("controller_action_id"),
            "calibration_only": bool(source.get("calibration_only")),
        })
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r2-validation-summary", type=Path)
    parser.add_argument("--r2-ingest-summary", type=Path, default=R2_INGEST)
    parser.add_argument("--preview-only", action="store_true")
    parser.add_argument("--refresh-generated", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = load(R1_SPEC)
    passed = validate_r1(spec, load(R1_VALIDATION), load(R1_INGEST))
    cells = planned_cells(spec, passed)
    preview = {
        "schema_version": 1,
        "status": "blocked",
        "launch_ready": False,
        "reason": "等待 R2 validator pass 与 accepted-only ingest 双证据",
        "cell_count": len(cells),
        "eta_hours": {"low": 6, "high": 10},
        "cells": cells,
    }
    validation_path = args.r2_validation_summary.resolve() if args.r2_validation_summary else None
    try:
        validation_path = validation_path or discover_r2_validation()
        validate_r2(validation_path, args.r2_ingest_summary.resolve())
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        preview["gate_error"] = str(error)
        write_json(STAGE / "blocked-preview.json", preview)
        print(json.dumps(preview, ensure_ascii=False))
        return 0 if args.preview_only else 2
    if args.preview_only:
        preview |= {"status": "ready_preview", "launch_ready": True, "reason": "R2 双证据已通过；未写 launch-ready 文件"}
        write_json(STAGE / "blocked-preview.json", preview)
        print(json.dumps(preview, ensure_ascii=False))
        return 0

    ensure_refresh_safe(args.refresh_generated)
    code_hashes = {relative: sha256(ROOT / relative) for relative in SOURCE_FILES}
    run_spec = {
        "schema_version": 1,
        "run_id": "pentamer-negative-phase-stage-a-r3-remaining13-20260810",
        "scope": "beta=0.5 Stage A remaining 13 cells; -1<=alpha<0; Fig.9 excluded",
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
            "budget_definition": "每个独立初态的 sweeps；L40/L60=32，L80=64",
            "acceptance": {
                "variance_per_site_max": 1e-8,
                "final_truncation_error_max": 1e-9,
                "sector_tolerance": 1e-8,
                "q_count_min": 401,
            },
            "offline": True,
            "execution": "direct SSH; concurrency=1; stop on first failed cell",
        },
        "provenance": {
            "negative_alpha_included": True,
            "continuation_reason": "R1 严格接纳 10 项且 R2 严格接纳失败重试后，续跑 Stage A 剩余 13 项",
            "r1_run_spec_sha256": sha256(R1_SPEC),
            "r1_validation_summary_sha256": sha256(R1_VALIDATION),
            "r1_ingestion_summary_sha256": sha256(R1_INGEST),
            "r2_validation_summary_sha256": sha256(validation_path),
            "r2_ingestion_summary_sha256": sha256(args.r2_ingest_summary.resolve()),
            "standard_sha256": sha256(STANDARD),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
            ).stdout.strip(),
            "code_sha256": code_hashes,
            "r1_r2_evidence_preserved": True,
            "exploratory_data_not_accepted": True,
        },
    }
    run_spec_path = STAGE / "parameter-scan.run_spec.json"
    source_hashes_path = STAGE / "r3_source_hashes.sha256"
    write_json(run_spec_path, run_spec)
    with source_hashes_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(f"{digest}  {relative}\n" for relative, digest in code_hashes.items()))
    contract = {
        "schema_version": 1,
        "launch_ready": True,
        "cell_count": 13,
        "concurrency": 1,
        "eta_hours": {"low": 6, "high": 10},
        "run_spec_sha256": sha256(run_spec_path),
        "source_hashes_sha256": sha256(source_hashes_path),
        "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r2_validation_summary_sha256": sha256(validation_path),
        "r2_ingestion_summary_sha256": sha256(args.r2_ingest_summary.resolve()),
    }
    write_json(STAGE / "launch-contract.json", contract)
    write_json(STAGE / "blocked-preview.json", preview | {"status": "released", "launch_ready": True, "reason": "R2 双证据已通过"})
    print(json.dumps({"run_spec": str(run_spec_path), "source_hashes": str(source_hashes_path), "cells": 13}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
