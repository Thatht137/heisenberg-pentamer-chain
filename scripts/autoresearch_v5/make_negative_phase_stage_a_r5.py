#!/usr/bin/env python3
"""在 R4 严格通过后生成 Stage A 剩余 10 单元。"""

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
STAGE = RUN / "stage-a-beta050-calibration-r5-remaining10"
R3_SPEC = RUN / "stage-a-beta050-calibration-r3-remaining13" / "parameter-scan.run_spec.json"
R3_INGEST = RUN / "phase-diagram-v2" / "r3_partial_ingestion_summary.json"
R4_SPEC = RUN / "stage-a-beta050-calibration-r4-a0250-L060" / "parameter-scan.run_spec.json"
R4_INGEST = RUN / "phase-diagram-v2" / "r4_ingestion_summary.json"
STANDARD = ROOT / "docs" / "full_phase_diagram_negative_standard_20260809.md"
R4_CELL = "nega-r4-a0250-b0500-L060"
R4_ACTION = "act-bd120db6bdbc305ddf42"
EXCLUDED_R3 = {
    "nega-r3-a0350-b0500-L080",
    "nega-r3-a0250-b0500-L040",
    "nega-r3-a0250-b0500-L060",
}
EXPECTED_REMAINING = {
    (-0.25, 0.5, 80),
    *{(alpha, 0.5, length) for alpha in (-0.1, -0.05, -0.025) for length in (40, 60, 80)},
}
EXPECTED_ACTIONS = {
    (-0.1, 0.5, 40): "act-cd2b4353726834318d6b",
    (-0.1, 0.5, 60): "act-6a4963c3064243f17ed8",
    (-0.05, 0.5, 40): "act-fffdf93a9cae183cb1c1",
    (-0.05, 0.5, 60): "act-7016420e7cbf8fc354b7",
    (-0.025, 0.5, 40): "act-4503b7acb169c6a5092f",
    (-0.025, 0.5, 60): "act-3d1ab066156655e22ec8",
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


def discover_r4_validation() -> Path:
    pattern = "stage-a-beta050-calibration-r4-a0250-L060-*/validation/summary.json"
    matches = sorted((RUN / "fetches").glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"R4 validator summary 必须唯一，当前 {len(matches)} 个")
    return matches[0]


def validate_current_state() -> None:
    r3 = load(R3_INGEST)
    counts = r3.get("counts", {})
    expected = {
        "validator_pass": 2,
        "validator_fail": 1,
        "controller_success_total": 9,
        "controller_failed_total": 1,
        "controller_pending_total": 6,
        "calibration_accepted_r3": 1,
    }
    if r3.get("status") != "blocked_by_validation_failure" or any(counts.get(name) != value for name, value in expected.items()):
        raise ValueError("R3 accepted-only 基线不匹配")
    if r3.get("failed_controller_keys") != [{"alpha": -0.25, "beta": 0.5, "L": 60}]:
        raise ValueError("R3 失败键不匹配")
    r4 = load(R4_SPEC)
    cells = r4.get("cells", [])
    if len(cells) != 1:
        raise ValueError("R4 run spec 必须只有一个 cell")
    cell = cells[0]
    if (
        cell.get("cell_id") != R4_CELL
        or key(cell) != (-0.25, 0.5, 60)
        or int(cell.get("budget", -1)) != 64
        or cell.get("controller_action_id") != R4_ACTION
        or cell.get("retry_of") != "nega-r3-a0250-b0500-L060"
    ):
        raise ValueError("R4 run spec 身份不匹配")


def planned_cells() -> list[dict[str, Any]]:
    spec = load(R3_SPEC)
    source = [cell for cell in spec.get("cells", []) if cell.get("cell_id") not in EXCLUDED_R3]
    if len(source) != 10 or {key(cell) for cell in source} != EXPECTED_REMAINING:
        raise ValueError("R3 未运行集合不是声明的 10 个单元")
    result = []
    for item in source:
        alpha, beta, length = key(item)
        calibration = length == 80
        expected_action = None if calibration else EXPECTED_ACTIONS[(alpha, beta, length)]
        if item.get("controller_action_id") != expected_action or bool(item.get("calibration_only")) is not calibration:
            raise ValueError(f"R3 未运行单元 action 身份不匹配: {item['cell_id']}")
        result.append({
            "cell_id": f"nega-r5-a{label(alpha)}-b0500-L{length:03d}",
            "params": {"alpha": alpha, "beta": beta, "L": length, "n_units": length // 5},
            "budget": 64 if length == 80 else 32,
            "stage": "A-R5-remaining10",
            "retry_policy": "首次续跑；L40/L60=32、L80=64；失败时仅按 32->64->128 或 64->128",
            "continued_from": item["cell_id"],
            "controller_action_id": expected_action,
            "calibration_only": calibration,
        })
    return result


def validate_r4(validation_path: Path, ingest_path: Path) -> None:
    validation = load(validation_path)
    rows = validation.get("rows")
    if (
        validation.get("status") != "pass"
        or validation.get("cell_count") != 1
        or validation.get("counts") != {"pass": 1, "fail": 0}
        or not isinstance(rows, list)
        or len(rows) != 1
    ):
        raise ValueError("R4 validator summary 必须严格为 1 pass / 0 fail")
    row = rows[0]
    if row.get("cell_id") != R4_CELL or row.get("validator_status") != "pass" or row.get("exit_code") != 0:
        raise ValueError("R4 validator row 未通过")
    detail_path = Path(str(row.get("output", "")))
    if not detail_path.is_file() or sha256(detail_path) != row.get("sha256"):
        raise ValueError("R4 validator 明细或哈希无效")
    detail = load(detail_path)
    checks = detail.get("checks")
    if detail.get("cell_id") != R4_CELL or detail.get("status") != "pass" or not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
        raise ValueError("R4 validator 明细含未通过检查")

    ingest = load(ingest_path)
    counts = ingest.get("counts", {})
    expected_counts = {
        "validator_pass": 1,
        "controller_accepted": 1,
        "controller_failed": 0,
        "controller_success_total": 10,
        "controller_failed_total": 0,
        "controller_pending_total": 6,
    }
    if ingest.get("status") != "accepted" or ingest.get("cell_id") != R4_CELL or any(
        counts.get(name) != value for name, value in expected_counts.items()
    ):
        raise ValueError("R4 accepted-only ingest 状态或计数不匹配")
    if ingest.get("accepted_key") != {"alpha": -0.25, "beta": 0.5, "L": 60}:
        raise ValueError("R4 ingest accepted key 不匹配")
    source = ingest.get("validation_summary", {})
    if source.get("sha256") != sha256(validation_path):
        raise ValueError("R4 ingest 未绑定当前 validator summary")
    artifact = ROOT / str(source.get("artifact", ""))
    if artifact.resolve() != validation_path.resolve():
        raise ValueError("R4 ingest validator artifact 不匹配")


def settings() -> dict[str, Any]:
    return {
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
    }


def ensure_safe(refresh: bool) -> None:
    generated = [STAGE / name for name in ("parameter-scan.run_spec.json", "r5_source_hashes.sha256", "launch-contract.json")]
    if any(path.exists() for path in generated) and not refresh:
        raise ValueError("R5 launch-ready 文件已存在，拒绝覆盖")
    forbidden = [STAGE / name for name in ("run_status.json", "run.json", "batch.pid", "submission-receipt.json")]
    cells_dir = STAGE / "cells"
    if any(path.exists() for path in forbidden) or (cells_dir.exists() and any(cells_dir.iterdir())):
        raise ValueError("R5 已有提交或 cell 证据，拒绝刷新")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r4-validation-summary", type=Path)
    parser.add_argument("--r4-ingest-summary", type=Path, default=R4_INGEST)
    parser.add_argument("--preview-only", action="store_true")
    parser.add_argument("--refresh-generated", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_current_state()
    cells = planned_cells()
    preview = {
        "schema_version": 1,
        "run_id": "pentamer-negative-phase-stage-a-r5-remaining10-20260810-preview",
        "status": "blocked",
        "launch_ready": False,
        "reason": "等待 R4 validator pass 与 accepted-only ingest 双证据",
        "scope": "beta=0.5 Stage A remaining 10 cells; -1<=alpha<0; Fig.9 excluded",
        "controller": "local_only",
        "cell_count": 10,
        "concurrency": 1,
        "eta_hours": {"low": 5, "high": 8, "basis": "R3 声明窗口按剩余单元比例缩放"},
        "cells": cells,
        "settings": settings(),
        "provenance": {"negative_alpha_included": True, "thresholds_relaxed": False, "preview_only": True},
        "required_ingest_contract": {
            "path": R4_INGEST.relative_to(ROOT).as_posix(),
            "status": "accepted",
            "cell_id": R4_CELL,
            "controller_success_total": 10,
            "controller_failed_total": 0,
            "controller_pending_total": 6,
        },
    }
    validation_path = args.r4_validation_summary.resolve() if args.r4_validation_summary else None
    try:
        validation_path = validation_path or discover_r4_validation()
        validate_r4(validation_path, args.r4_ingest_summary.resolve())
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError) as error:
        preview["gate_error"] = str(error)
        write_json(STAGE / "blocked-preview.json", preview)
        print(json.dumps(preview, ensure_ascii=False))
        return 0 if args.preview_only else 2
    if args.preview_only:
        preview |= {"status": "ready_preview", "launch_ready": True, "reason": "R4 双证据已通过；未写 launch-ready 文件"}
        write_json(STAGE / "blocked-preview.json", preview)
        print(json.dumps(preview, ensure_ascii=False))
        return 0

    ensure_safe(args.refresh_generated)
    code_hashes = {relative: sha256(ROOT / relative) for relative in SOURCE_FILES}
    run_spec = {
        "schema_version": 1,
        "run_id": "pentamer-negative-phase-stage-a-r5-remaining10-20260810",
        "scope": preview["scope"],
        "controller": "local_only",
        "cells": cells,
        "settings": settings(),
        "provenance": {
            "negative_alpha_included": True,
            "continuation_reason": "R3 部分接入且 R4 严格接纳后续跑 Stage A 剩余 10 项",
            "r3_run_spec_sha256": sha256(R3_SPEC),
            "r3_ingestion_summary_sha256": sha256(R3_INGEST),
            "r4_run_spec_sha256": sha256(R4_SPEC),
            "r4_validation_summary_sha256": sha256(validation_path),
            "r4_ingestion_summary_sha256": sha256(args.r4_ingest_summary.resolve()),
            "standard_sha256": sha256(STANDARD),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes,
            "r1_r2_r3_r4_evidence_preserved": True,
            "thresholds_relaxed": False,
            "exploratory_data_not_accepted": True,
        },
    }
    run_spec_path = STAGE / "parameter-scan.run_spec.json"
    hashes_path = STAGE / "r5_source_hashes.sha256"
    write_json(run_spec_path, run_spec)
    with hashes_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(f"{digest}  {relative}\n" for relative, digest in code_hashes.items()))
    contract = {
        "schema_version": 1,
        "launch_ready": True,
        "cell_count": 10,
        "concurrency": 1,
        "offline": True,
        "eta_hours": {"low": 5, "high": 8},
        "run_spec_sha256": sha256(run_spec_path),
        "source_hashes_sha256": sha256(hashes_path),
        "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r4_validation_summary_sha256": sha256(validation_path),
        "r4_ingestion_summary_sha256": sha256(args.r4_ingest_summary.resolve()),
        "thresholds_relaxed": False,
    }
    write_json(STAGE / "launch-contract.json", contract)
    write_json(STAGE / "blocked-preview.json", preview | {"status": "released", "launch_ready": True, "reason": "R4 双证据已通过"})
    print(json.dumps({"run_spec": str(run_spec_path), "source_hashes": str(hashes_path), "cells": 10}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
