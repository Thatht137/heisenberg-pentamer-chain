#!/usr/bin/env python3
"""包装 Practical V2，并严格验收单点 k=12 产物。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_KRYLOV = 12
STARTS = ("center", "ferro_j2")

try:
    from validate_negative_phase_run_practical_v2 import validate as practical_validate
except ImportError:  # 直接从其他工作目录调用时保持可用
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from validate_negative_phase_run_practical_v2 import validate as practical_validate


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象：{path}")
    return value


def _check_k(value: Any, label: str, failures: list[str]) -> int | None:
    if type(value) is not int or value != EXPECTED_KRYLOV:
        failures.append(f"{label}: eigsolve_krylovdim 必须严格为 {EXPECTED_KRYLOV}")
        return None
    return value


def _check_manifest_k(manifest: dict[str, Any], label: str, failures: list[str]) -> int | None:
    settings = manifest.get("settings")
    if not isinstance(settings, dict):
        failures.append(f"{label}: 缺少 settings")
        return None
    observed = _check_k(settings.get("eigsolve_krylovdim"), f"{label}.settings", failures)
    params = manifest.get("params")
    if isinstance(params, dict) and "eigsolve_krylovdim" in params:
        _check_k(params.get("eigsolve_krylovdim"), f"{label}.params", failures)
    return observed


def _contract_check(run: Path, run_spec: Path) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    observed: dict[str, Any] = {"expected_krylovdim": EXPECTED_KRYLOV, "run_spec": None, "parent": None, "children": {}}

    try:
        spec = load_json(run_spec)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"run spec 不可读：{error}"], observed

    spec_settings = spec.get("settings")
    if not isinstance(spec_settings, dict):
        failures.append("run spec: 缺少 settings")
    else:
        observed["run_spec"] = _check_k(spec_settings.get("eigsolve_krylovdim"), "run spec.settings", failures)

    cells = spec.get("cells")
    if not isinstance(cells, list) or len(cells) != 1:
        failures.append("run spec: k12 release 必须恰有一个 cell")
        cells = cells if isinstance(cells, list) else []
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            failures.append(f"run spec.cells[{index}] 不是对象")
            continue
        params = cell.get("params")
        if not isinstance(params, dict):
            failures.append(f"run spec.cells[{index}]: 缺少 params")
        else:
            _check_k(params.get("eigsolve_krylovdim"), f"run spec.cells[{index}].params", failures)

    parent_path = run / "manifest.json"
    try:
        parent = load_json(parent_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        failures.append(f"父 manifest 不可读：{error}")
        return sorted(set(failures)), observed

    observed["parent"] = _check_manifest_k(parent, "父 manifest", failures)
    cell_id = parent.get("cell_id")
    matches = [cell for cell in cells if isinstance(cell, dict) and cell.get("cell_id") == cell_id]
    if len(matches) != 1:
        failures.append("run spec: 父 manifest cell_id 未唯一匹配")

    for mode in STARTS:
        path = run / f"start_{mode}" / "manifest.json"
        try:
            child = load_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            failures.append(f"子 manifest {mode} 不可读：{error}")
            continue
        observed["children"][mode] = _check_manifest_k(child, f"子 manifest {mode}", failures)

    return sorted(set(failures)), observed


def validate(run_dir: Path, run_spec: Path) -> dict[str, Any]:
    """返回 Practical V2 与 k12 合同的合并验收结果。"""
    run = Path(run_dir).resolve()
    spec = Path(run_spec).resolve()
    try:
        practical = practical_validate(run, spec)
    except Exception as error:  # 让合同检查仍能报告完整失败集合
        practical = {
            "status": "fail",
            "acceptance_label": "practical_v2_error",
            "failures": [f"Practical V2 异常：{error}"],
        }
    contract_failures, observed = _contract_check(run, spec)
    failures = sorted(set((practical.get("failures") or []) + contract_failures))
    accepted = not failures and practical.get("status") == "pass"
    return {
        "schema_version": 1,
        "status": "pass" if accepted else "fail",
        "acceptance_label": "accepted_under_practical_v2_k12" if accepted else "rejected_under_practical_v2_k12",
        "run_dir": str(run),
        "run_spec": str(spec),
        "cell_id": practical.get("cell_id"),
        "krylov_contract": {"expected": EXPECTED_KRYLOV, "observed": observed},
        "practical_v2": practical,
        "failures": failures,
    }


validate_k12 = validate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.run_dir, args.run_spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "cell_id": result["cell_id"], "failures": result["failures"]}, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "pass" else 2)


if __name__ == "__main__":
    main()
