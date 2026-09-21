#!/usr/bin/env python3
"""独立校验 static Krylov-12 release v3，不执行网络或任务。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RESULTS_REL = Path("results/autoresearch_v5_20260920")
RELEASE_NAME = "static_krylov_controls_release_v3"
RUN_NAME = "static_krylov_k12_r1"
SMOKE_REL = Path("static_krylov_k12_smoke_r1/a-0100-k12")
RELEASE_ID = "static-krylov-controls-release-v3"
RUN_ID = "pentamer-negative-alpha-static-krylov-k12-single-r1-20260920"
CELL_ID = "negdiag-a01000-b02500-L080-k12"
KRYLOV = 12
REMOTE_TARGET = "/home/wangjieren/releases/1x5_Heisenberg_Pentamer/static_krylov_controls_release_v3"
REMOTE_RUN = "results/autoresearch_v5_20260920/static_krylov_k12_r1"
REMOTE_JULIA = "1.12.3"
SMOKE_JULIA = "1.11.5"
SMOKE_ARTIFACTS = (
    "bond_bond_connected.csv",
    "bond_correlations.csv",
    "entropy_profile_full.csv",
    "metrics.csv",
    "schmidt_spectrum.csv",
    "state_sz0.jld2",
    "string_profile.csv",
    "structure_factor_fullq.csv",
    "sweep_history_sz0.csv",
    "sweep_history_sz1.csv",
)


class PreflightError(ValueError):
    """输入不满足固定 v3 合同时抛出。"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PreflightError(f"缺少 JSON: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PreflightError(f"JSON 不可读: {path}") from error
    if not isinstance(value, dict):
        raise PreflightError(f"JSON 须为 object: {path}")
    return value


def finite(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise PreflightError(f"{label} 不是数值") from error
    if not math.isfinite(result):
        raise PreflightError(f"{label} 不是有限数")
    return result


def exact(value: Any, expected: float, label: str) -> None:
    if finite(value, label) != expected:
        raise PreflightError(f"{label} 不匹配: {value!r} != {expected!r}")


def exact_bool(value: Any, expected: bool, label: str) -> None:
    if type(value) is not bool or value is not expected:
        raise PreflightError(f"{label} 不匹配: {value!r} != {expected!r}")


def safe_relative(root: Path, raw: str, label: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        raise PreflightError(f"{label} 不得为绝对路径: {raw}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise PreflightError(f"{label} 越出 workspace: {raw}") from error
    return resolved


def require_exact_layout(root: Path, release: Path, run: Path, smoke: Path) -> None:
    root = root.resolve()
    results = (root / RESULTS_REL).resolve()
    expected_release = results / RELEASE_NAME
    expected_run = results / RUN_NAME
    expected_smoke = results / SMOKE_REL
    for actual, expected, label in (
        (release, expected_release, "release"),
        (run, expected_run, "run"),
        (smoke, expected_smoke, "smoke"),
    ):
        if actual.resolve() != expected:
            raise PreflightError(f"{label} 路径不属于固定 release-v3 布局: {actual}")
    for path in (release, run, smoke):
        if "v2" in str(path).lower():
            raise PreflightError(f"拒绝 v2 路径: {path}")


def validate_manifest_files(root: Path, release: Path, manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise PreflightError("manifest.files 为空")
    seen: set[str] = set()
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not {"path", "bytes", "sha256"} <= set(entry):
            raise PreflightError(f"manifest 文件项字段不完整: {entry!r}")
        raw = str(entry["path"])
        path = safe_relative(root, raw, "manifest.files.path")
        normalized = path.relative_to(root).as_posix()
        if normalized in seen:
            raise PreflightError(f"manifest 文件重复: {normalized}")
        seen.add(normalized)
        if not path.is_file():
            raise PreflightError(f"manifest 文件不存在: {normalized}")
        try:
            expected_bytes = int(entry["bytes"])
        except (TypeError, ValueError) as error:
            raise PreflightError(f"manifest bytes 非整数: {normalized}") from error
        actual_bytes = path.stat().st_size
        actual_sha = sha256(path)
        if actual_bytes != expected_bytes:
            raise PreflightError(f"manifest bytes 不匹配: {normalized}")
        if actual_sha != str(entry["sha256"]):
            raise PreflightError(f"manifest SHA256 不匹配: {normalized}")
        result[normalized] = entry
    manifest_path = (release / "server_upload_manifest.json").resolve()
    if manifest_path.relative_to(root).as_posix() in result:
        raise PreflightError("manifest.files 不得把自身当作 payload")
    return result


def read_source_hashes(root: Path, run: Path, spec: dict[str, Any], manifest_files: dict[str, dict[str, Any]]) -> dict[str, str]:
    path = run / "source_hashes.sha256"
    if not path.is_file():
        raise PreflightError(f"缺少 source_hashes: {path}")
    records: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        fields = line.split()
        if len(fields) != 2 or len(fields[0]) != 64:
            raise PreflightError(f"source_hashes 第 {line_number} 行格式错误")
        digest, raw = fields
        if any(char not in "0123456789abcdef" for char in digest.lower()):
            raise PreflightError(f"source_hashes 第 {line_number} 行 SHA 错误")
        source = safe_relative(root, raw, "source_hashes.path")
        relative_path = source.relative_to(root).as_posix()
        if relative_path in records:
            raise PreflightError(f"source_hashes 重复: {relative_path}")
        if not source.is_file() or sha256(source) != digest:
            raise PreflightError(f"source_hashes 校验失败: {relative_path}")
        if relative_path not in manifest_files:
            raise PreflightError(f"source_hashes 文件未列入 manifest: {relative_path}")
        records[relative_path] = digest
    if not records:
        raise PreflightError("source_hashes 为空")
    provenance = spec.get("provenance")
    if not isinstance(provenance, dict):
        raise PreflightError("run spec 缺少 provenance")
    expected_path = (run.relative_to(root) / "source_hashes.sha256").as_posix()
    if provenance.get("source_hashes_path") != expected_path:
        raise PreflightError("run spec source_hashes_path 不匹配")
    expected_records = provenance.get("source_hashes")
    if expected_records != records:
        raise PreflightError("run spec provenance.source_hashes 不匹配")
    return records


def validate_smoke(root: Path, smoke: Path, spec: dict[str, Any], manifest_files: dict[str, dict[str, Any]]) -> dict[str, Any]:
    evidence = spec.get("provenance", {}).get("smoke_evidence")
    if not isinstance(evidence, dict):
        raise PreflightError("缺少 smoke_evidence")
    if evidence.get("path") != (smoke.relative_to(root)).as_posix():
        raise PreflightError("smoke_evidence.path 不匹配")
    if evidence.get("julia_version") != SMOKE_JULIA or evidence.get("remote_julia_version_required") != REMOTE_JULIA:
        raise PreflightError("smoke/remote Julia 版本证据不匹配")
    exact_bool(evidence.get("not_remote_validation"), True, "smoke.not_remote_validation")
    if evidence.get("artifact_names") != list(SMOKE_ARTIFACTS):
        raise PreflightError("smoke artifact 名称不匹配")
    hashes = evidence.get("artifact_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(SMOKE_ARTIFACTS):
        raise PreflightError("smoke artifact SHA 清单不完整")
    for name in SMOKE_ARTIFACTS:
        path = smoke / name
        if not path.is_file() or path.stat().st_size <= 0:
            raise PreflightError(f"smoke artifact 缺失或为空: {name}")
        digest = sha256(path)
        if digest != hashes[name]:
            raise PreflightError(f"smoke evidence SHA 不匹配: {name}")
        relative_path = path.relative_to(root).as_posix()
        if relative_path not in manifest_files:
            raise PreflightError(f"smoke artifact 未列入 manifest: {relative_path}")
    metrics_path = smoke / "metrics.csv"
    with metrics_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    metrics = {row.get("metric"): row.get("value") for row in rows if set(row) == {"metric", "value"}}
    if len(metrics) != len(rows):
        raise PreflightError("smoke metrics.csv 格式或 metric 重复")
    for key, expected in {
        "alpha": -0.1,
        "beta": 0.25,
        "n_units": 2,
        "L": 10,
        "structure_factor_q_count": 401,
        "eigsolve_krylovdim": KRYLOV,
        "eigsolve_maxiter": 1,
        "random_seed_base": 20260811,
        "nsweeps_requested": 16,
        "nsweeps_completed_sz0": 16,
        "nsweeps_completed_sz1": 16,
    }.items():
        exact(metrics.get(key), expected, f"smoke.{key}")
    if metrics.get("noise_profile") != "legacy":
        raise PreflightError("smoke noise_profile 不匹配")
    if metrics.get("init_mode_sz0") != "center" or metrics.get("init_mode_sz1") != "center":
        raise PreflightError("smoke 初态不匹配")
    if metrics.get("enriched_diagnostics") != "true":
        raise PreflightError("smoke enriched diagnostics 未开启")
    return {"path": evidence["path"], "julia_version": evidence["julia_version"], "metrics": metrics}


def validate_run_spec(root: Path, run: Path, spec: dict[str, Any]) -> None:
    if spec.get("schema_version") != 3 or spec.get("run_id") != RUN_ID:
        raise PreflightError("run spec schema/run_id 不匹配")
    if spec.get("run_dir") != run.relative_to(root).as_posix():
        raise PreflightError("run spec run_dir 不匹配")
    cells = spec.get("cells")
    if not isinstance(cells, list) or len(cells) != 1:
        raise PreflightError("run spec 必须只有一个 cell")
    cell = cells[0]
    if cell.get("cell_id") != CELL_ID or cell.get("budget") != 64:
        raise PreflightError("cell id 或 64 sweeps budget 不匹配")
    params = cell.get("params", {})
    for key, expected in {
        "alpha": -0.1,
        "beta": 0.25,
        "L": 80,
        "n_units": 16,
        "eigsolve_krylovdim": KRYLOV,
    }.items():
        exact(params.get(key), expected, f"cell.params.{key}")
    settings = spec.get("settings")
    if not isinstance(settings, dict):
        raise PreflightError("run spec 缺少 settings")
    for key, expected in {
        "nsweeps": 64,
        "cutoff": 1e-11,
        "threads": 8,
        "q_count": 401,
        "random_seed": 20260811,
        "eigsolve_krylovdim": KRYLOV,
        "eigsolve_maxiter": 1,
        "eigsolve_tol": 1e-14,
    }.items():
        exact(settings.get(key), expected, f"settings.{key}")
    if settings.get("maxdim_by_L") != {"80": 1200}:
        raise PreflightError("settings.maxdim_by_L 不匹配")
    if settings.get("sectors") != ["Sz=0", "Sz=1"] or settings.get("init_modes") != ["center", "ferro_j2"]:
        raise PreflightError("settings 扇区或两初态不匹配")
    if settings.get("noise_profile") != "legacy":
        raise PreflightError("settings noise_profile 不匹配")
    exact_bool(settings.get("save_state"), True, "settings.save_state")
    exact_bool(settings.get("enriched_diagnostics"), True, "settings.enriched_diagnostics")
    exact_bool(settings.get("warmstart"), False, "settings.warmstart")
    exact_bool(settings.get("maxdim_escalation"), False, "settings.maxdim_escalation")
    if settings.get("retry_policy") != "none":
        raise PreflightError("settings.retry_policy 必须为 none")
    execution = str(settings.get("execution", ""))
    for marker in ("concurrency=1", "stop on first failed cell"):
        if marker not in execution:
            raise PreflightError(f"settings.execution 缺少 {marker}")
    contract = spec.get("future_output_contract")
    if not isinstance(contract, dict):
        raise PreflightError("缺少 future_output_contract")
    parent = contract.get("parent", {})
    children = contract.get("children", {})
    if parent.get("cell_id") != CELL_ID or parent.get("required_krylovdim") != KRYLOV:
        raise PreflightError("future parent k12 contract 不匹配")
    if parent.get("required_modes") != ["center", "ferro_j2"] or parent.get("required_sectors") != ["Sz=0", "Sz=1"]:
        raise PreflightError("future parent 初态/扇区 contract 不匹配")
    if children.get("modes") != ["center", "ferro_j2"] or children.get("required_krylovdim") != KRYLOV:
        raise PreflightError("future children contract 不匹配")
    if children.get("required_sweeps") != 64:
        raise PreflightError("future children sweeps contract 不匹配")
    acceptance = spec.get("acceptance")
    if not isinstance(acceptance, dict):
        raise PreflightError("缺少 acceptance")
    for key in ("no_warmstart", "no_128", "no_retry", "parent_child_k12_contract_required"):
        exact_bool(acceptance.get(key), True, f"acceptance.{key}")
    if acceptance.get("success_receipt") not in (False, None):
        raise PreflightError("prepared release 不得伪造 success receipt")


def validate_manifest(root: Path, release: Path, manifest: dict[str, Any], mode: str) -> dict[str, dict[str, Any]]:
    if manifest.get("schema_version") != 3 or manifest.get("release_id") != RELEASE_ID:
        raise PreflightError("manifest 不是 release-v3")
    if manifest.get("release_version") != 3 or manifest.get("target") != REMOTE_TARGET:
        raise PreflightError("manifest release/version/target 不匹配")
    if manifest.get("remote_run_dir") != REMOTE_RUN or manifest.get("cell_count") != 1:
        raise PreflightError("manifest 单 cell/run_dir 不匹配")
    if manifest.get("concurrency") != 1 or manifest.get("stop_on_first_failure") is not True:
        raise PreflightError("manifest 并发/失败策略不匹配")
    if manifest.get("retry_policy") != "none" or manifest.get("krylovdim") != KRYLOV:
        raise PreflightError("manifest retry/krylov 不匹配")
    if manifest.get("expected_remote_julia_version") != REMOTE_JULIA:
        raise PreflightError("manifest remote Julia 版本不匹配")
    if manifest.get("status") != "prepared_only" or manifest.get("launch_ready") is not False:
        raise PreflightError("manifest 必须保持 status=prepared_only、launch_ready=false")
    if manifest.get("network_used") is True:
        raise PreflightError("preflight 拒绝 network_used=true")
    return validate_manifest_files(root, release, manifest)


def validate_package(
    root: Path,
    release: Path,
    run: Path,
    smoke: Path,
    mode: str = "upload",
) -> dict[str, Any]:
    if mode not in {"prepare", "upload", "launch"}:
        raise PreflightError(f"未知模式: {mode}")
    root = root.resolve()
    release, run, smoke = release.resolve(), run.resolve(), smoke.resolve()
    require_exact_layout(root, release, run, smoke)
    manifest = read_json(release / "server_upload_manifest.json")
    manifest_files = validate_manifest(root, release, manifest, mode)
    run_spec = read_json(run / "parameter-scan.run_spec.json")
    validate_run_spec(root, run, run_spec)
    source_records = read_source_hashes(root, run, run_spec, manifest_files)
    smoke_result = validate_smoke(root, smoke, run_spec, manifest_files)
    return {
        "status": "pass",
        "mode": mode,
        "release_id": RELEASE_ID,
        "release_version": 3,
        "cell_id": CELL_ID,
        "network_used": False,
        "launch_ready": mode == "launch",
        "manifest_files": len(manifest_files),
        "source_hashes": len(source_records),
        "smoke": smoke_result,
        "settings": {
            "alpha": -0.1,
            "beta": 0.25,
            "L": 80,
            "krylovdim": KRYLOV,
            "nsweeps": 64,
            "maxdim": 1200,
            "init_modes": ["center", "ferro_j2"],
            "retry_policy": "none",
            "warmstart": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("prepare", "upload", "launch"), required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="保留兼容接口，始终输出 JSON")
    parser.add_argument("--release-dir", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--smoke-dir", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    results = root / RESULTS_REL
    expected_release = (results / RELEASE_NAME).resolve()
    expected_manifest = expected_release / "server_upload_manifest.json"
    manifest_path = (args.manifest or expected_manifest).resolve()
    if manifest_path != expected_manifest:
        result = {"status": "rejected", "mode": args.mode, "network_used": False, "reason": "manifest 必须是固定 release-v3 manifest"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    release = (args.release_dir or expected_release).resolve()
    run = (args.run_dir or results / RUN_NAME).resolve()
    smoke = (args.smoke_dir or results / SMOKE_REL).resolve()
    try:
        result = validate_package(root, release, run, smoke, args.mode)
        result["status"] = "prepared_only"
        result["launch_ready"] = args.mode == "launch"
        result["control_path"] = manifest_path.relative_to(root).as_posix()
        result["mode"] = args.mode
    except (OSError, PreflightError, json.JSONDecodeError) as error:
        result = {"status": "rejected", "mode": args.mode, "network_used": False, "reason": str(error)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
