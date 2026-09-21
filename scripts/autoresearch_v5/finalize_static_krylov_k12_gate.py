#!/usr/bin/env python3
"""本地交接 k12 验收与 k8→k12 审计结果；不覆盖已有输出。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

try:
    from compare_static_krylov_k8_k12 import compare_runs
    from validate_static_krylov_k12_run import validate as validate_k12
except ImportError:  # 允许从仓库外直接调用
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from compare_static_krylov_k8_k12 import compare_runs
    from validate_static_krylov_k12_run import validate as validate_k12


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _input_files(path: Path, role: str) -> list[dict[str, Any]]:
    if path.is_symlink():
        raise ValueError(f"输入包含符号链接：{path}")
    root = path.resolve()
    if path.is_file():
        return [{"role": role, "root": str(root.parent), "path": root.name, "bytes": path.stat().st_size, "sha256": sha256(path)}]
    if not path.is_dir():
        raise ValueError(f"输入路径不存在：{path}")
    records = []
    for item in sorted(root.rglob("*")):
        if item.is_symlink():
            raise ValueError(f"输入包含符号链接：{item}")
        if not item.is_file():
            continue
        resolved = item.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise ValueError(f"输入文件越界：{item}") from error
        records.append({"role": role, "root": str(root), "path": str(item.relative_to(root)), "bytes": item.stat().st_size, "sha256": sha256(item)})
    if not records:
        raise ValueError(f"输入目录为空：{path}")
    return records


def collect_input_hashes(k12_cell_dir: Path, k12_run_spec: Path, k8_cell_dir: Path) -> list[dict[str, Any]]:
    records = []
    records.extend(_input_files(k12_cell_dir, "k12_cell_dir"))
    records.extend(_input_files(k12_run_spec, "k12_run_spec"))
    records.extend(_input_files(k8_cell_dir, "k8_cell_dir"))
    return sorted(records, key=lambda item: (item["role"], item["root"], item["path"]))


def _write_new(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _write_text_new(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(value)


def _check_output_path(output_dir: Path, inputs: list[Path]) -> None:
    if output_dir.exists():
        raise ValueError(f"拒绝覆盖既有输出目录：{output_dir}")
    output_resolved = output_dir.resolve()
    for source in inputs:
        source_resolved = source.resolve()
        if not source.is_dir():
            continue
        try:
            output_resolved.relative_to(source_resolved)
        except ValueError:
            continue
        raise ValueError(f"输出目录不能位于输入路径内：{output_dir}")


def _fixed_result(base: dict[str, Any], input_hashes: list[dict[str, Any]], gate_status: str) -> dict[str, Any]:
    result = dict(base)
    result.update({"status": "audit_only", "audit_only": True, "claim": "none", "gate_status": gate_status, "input_sha256": input_hashes})
    return result


def finalize(
    k12_cell_dir: Path,
    k12_run_spec: Path,
    k8_cell_dir: Path,
    output_dir: Path,
    validator: Callable[[Path, Path], dict[str, Any]] = validate_k12,
    comparator: Callable[[Path, Path], dict[str, Any]] = compare_runs,
) -> dict[str, Any]:
    """执行一次性 gate，并始终保留成功或失败证据。"""
    k12 = Path(k12_cell_dir).resolve()
    spec = Path(k12_run_spec).resolve()
    k8 = Path(k8_cell_dir).resolve()
    out = Path(output_dir).resolve()
    _check_output_path(out, [k12, spec, k8])
    input_hashes = collect_input_hashes(k12, spec, k8)
    out.mkdir(parents=True)

    failures: list[str] = []
    try:
        validation = validator(k12, spec)
    except Exception as error:
        validation = {"status": "fail", "failures": [f"k12 validator 异常：{error}"]}
    validation_failures = list(validation.get("failures") or [])
    validation_pass = validation.get("status") == "pass" and not validation_failures

    comparison: dict[str, Any]
    if validation_pass:
        try:
            comparison = comparator(k8, k12)
            if comparison.get("status") != "audit_only" or comparison.get("claim") not in (None, "none"):
                raise ValueError("比较结果未保持 audit_only/claim=none")
            comparison = _fixed_result(comparison, input_hashes, "pass")
        except Exception as error:
            failures.append(f"比较器失败：{error}")
            comparison = _fixed_result({"comparison_ran": False, "failures": [str(error)]}, input_hashes, "comparison_failed")
    else:
        failures.extend(validation_failures or ["k12 validator 未通过"])
        comparison = _fixed_result({"comparison_ran": False, "failures": ["k12 validator 未通过，比较未运行"]}, input_hashes, "blocked_by_validator")

    summary = _fixed_result(
        {
            "schema_version": 1,
            "gate": "static_krylov_k12_finalize",
            "inputs": {"k12_cell_dir": str(k12), "k12_run_spec": str(spec), "k8_cell_dir": str(k8)},
            "validator": validation,
            "comparison_file": "comparison.json",
            "failures": sorted(set(failures + validation_failures)),
            "physical_stability_conclusion": "not_generated",
        },
        input_hashes,
        "pass" if validation_pass and not failures else ("comparison_failed" if validation_pass else "blocked_by_validator"),
    )
    _write_new(out / "summary.json", summary)
    _write_new(out / "comparison.json", comparison)
    checksum_lines = []
    for name in ("summary.json", "comparison.json"):
        checksum_lines.append(f"{sha256(out / name)}  {name}")
    _write_text_new(out / "checksums.sha256", "\n".join(checksum_lines) + "\n")
    return {"summary": summary, "comparison": comparison, "output_dir": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k12-cell-dir", type=Path, required=True)
    parser.add_argument("--k12-run-spec", type=Path, required=True)
    parser.add_argument("--k8-cell-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = finalize(args.k12_cell_dir, args.k12_run_spec, args.k8_cell_dir, args.output_dir)
    summary = result["summary"]
    print(json.dumps({"status": summary["status"], "gate_status": summary["gate_status"], "output_dir": result["output_dir"]}, ensure_ascii=False))
    raise SystemExit(0 if summary["gate_status"] == "pass" else 2)


if __name__ == "__main__":
    main()
