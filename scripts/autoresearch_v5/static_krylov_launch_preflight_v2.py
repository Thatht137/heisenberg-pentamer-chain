#!/usr/bin/env python3
"""校验 controls_r2 与 v4 证据；只读、离线、拒绝旧证据。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
R2_REL = Path("results/autoresearch_v5_20260919/static_krylov_controls_r2")
V4_REL = Path("results/autoresearch_v5_20260919/static_krylov_smoke_v4")
RELEASE_REL = Path("results/autoresearch_v5_20260919/static_krylov_controls_release_v2")
JULIA_SOURCE = "scripts/autoresearch_v5/negative_static_cell.jl"
ED_SOURCE = "scripts/autoresearch_v5/static_krylov_ed_reference.py"
V4_DRIVER = "scripts/autoresearch_v5/smoke_static_krylov_v4.py"
PREFLIGHT_SOURCE = "scripts/autoresearch_v5/static_krylov_launch_preflight_v2.py"
SUPERVISOR_SOURCE = "scripts/autoresearch_v5/static_krylov_supervisor.py"
SUPERVISOR_TEST_SOURCE = "scripts/autoresearch_v5/test_static_krylov_supervisor.py"
EXPECTED_JULIA_SHA = "291eb369d5441b53d4abafd36d8469e107f4c1d91622ed33478912228ed3635f"
OLD_JULIA_SHA = "17cb83c1922b39efe34542ec795632360ff63873eb173c70763ecaa34337694e"
CASES = {"a-0100-k8": -0.1, "a-0175-k8": -0.175}
V4_ARTIFACTS = (
    "metrics.csv",
    "entropy_profile_full.csv",
    "bond_correlations.csv",
    "bond_bond_connected.csv",
    "state_sz0.jld2",
)


class PreflightError(ValueError):
    """可审计的预检拒绝。"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PreflightError(f"缺少 JSON：{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PreflightError(f"JSON 不可读：{path}") from error
    if not isinstance(value, dict):
        raise PreflightError(f"JSON 顶层不是对象：{path}")
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise PreflightError(f"{label} 不得为 bool")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise PreflightError(f"{label} 不是数值") from error
    if not math.isfinite(result):
        raise PreflightError(f"{label} 非有限")
    return result


def _same_float(value: Any, expected: float, label: str, tolerance: float = 1e-14) -> None:
    if abs(_finite(value, label) - expected) > tolerance:
        raise PreflightError(f"{label} 不匹配：{value!r} != {expected!r}")


def _exact_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise PreflightError(f"{label} 不得为 bool")
    if type(value) is int:
        return value
    if type(value) is float and math.isfinite(value) and value.is_integer():
        return int(value)
    raise PreflightError(f"{label} 必须是整数值")


def _relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")):
        raise PreflightError(f"{label} 不是安全相对路径")
    normalized = value.replace("\\", "/")
    posix_path = PurePosixPath(normalized)
    windows_path = PureWindowsPath(value)
    if (
        "\x00" in value
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or ".." in posix_path.parts
        or any(char.isspace() for char in value)
    ):
        raise PreflightError(f"{label} 含非法路径：{value}")
    return normalized


def _entry_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise PreflightError("release manifest 缺少非空 files")
    result: dict[str, dict[str, Any]] = {}
    for raw in entries:
        if not isinstance(raw, dict):
            raise PreflightError("release files 含非对象项")
        path = _relative_path(raw.get("path"), "release path")
        if path in result:
            raise PreflightError(f"release path 重复：{path}")
        digest = raw.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
            raise PreflightError(f"release hash 非 SHA256：{path}")
        if isinstance(raw.get("bytes"), bool) or not isinstance(raw.get("bytes"), int) or raw["bytes"] < 0:
            raise PreflightError(f"release bytes 非法：{path}")
        result[path] = raw
    return result


def _require_entry(entries: dict[str, dict[str, Any]] | None, path: str) -> None:
    if entries is not None and path.replace("\\", "/") not in entries:
        raise PreflightError(f"依赖未被 release manifest 覆盖：{path}")


def _verify_entries(root: Path, entries: dict[str, dict[str, Any]]) -> dict[str, str]:
    actuals: dict[str, str] = {}
    root_resolved = root.resolve()
    for relative, entry in entries.items():
        path = root / relative
        try:
            resolved = path.resolve()
            resolved.relative_to(root_resolved)
        except ValueError as error:
            raise PreflightError(f"release 文件越出 bundle root：{relative}") from error
        if path.is_symlink() or not path.is_file():
            raise PreflightError(f"release 文件不存在：{relative}")
        if path.stat().st_size != entry["bytes"]:
            raise PreflightError(f"release bytes 不匹配：{relative}")
        actual = sha256(path)
        if actual != entry["sha256"].lower():
            raise PreflightError(f"release hash 不匹配：{relative}")
        actuals[relative] = actual
    return actuals


def validate_release_manifest(manifest_path: Path, root: Path = ROOT) -> dict[str, Any]:
    manifest = _json(manifest_path)
    if manifest.get("release_id") != "static-krylov-controls-release-v2":
        raise PreflightError("只接受 static-krylov-controls-release-v2")
    if manifest.get("schema_version") not in (1, 2):
        raise PreflightError("release v2 schema_version 不支持")
    if manifest.get("status") != "prepared_only":
        raise PreflightError("release manifest 不是 prepared_only")
    if manifest.get("launch_ready") not in (None, False):
        raise PreflightError("launch_ready 必须由现场证据动态决定")
    if manifest.get("cell_count") != 2 or manifest.get("concurrency") != 1 or manifest.get("stop_on_first_failure") is not True:
        raise PreflightError("release 并发/停止策略不匹配")
    if manifest.get("remote_run_dir") != str(R2_REL).replace("\\", "/"):
        raise PreflightError("release remote_run_dir 不是 controls_r2")
    entries = _entry_map(manifest)
    control_path = _relative_path(manifest.get("control_path"), "control_path")
    try:
        expected_control = manifest_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise PreflightError("release manifest 必须位于 bundle root 内") from error
    if control_path != expected_control:
        raise PreflightError("control_path 与 manifest 路径不一致")
    if expected_control in entries:
        raise PreflightError("release manifest 不得纳入自身 files 哈希")
    _require_entry(entries, PREFLIGHT_SOURCE)
    _require_entry(entries, SUPERVISOR_SOURCE)
    _require_entry(entries, SUPERVISOR_TEST_SOURCE)
    bundle_hash_path = manifest.get("bundle_source_hashes_path")
    if bundle_hash_path is not None:
        bundle_hash_path = _relative_path(bundle_hash_path, "bundle_source_hashes_path")
        if bundle_hash_path == expected_control:
            raise PreflightError("bundle source hash 文件不得指向 release manifest")
        _require_entry(entries, bundle_hash_path)
    local_hashes = _verify_entries(root, entries)
    return {"manifest": manifest, "entries": entries, "local_hashes": local_hashes, "control_path": control_path}


def _read_hash_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise PreflightError(f"缺少 source hash 文件：{path}")
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2 or len(parts[0]) != 64 or any(char not in "0123456789abcdef" for char in parts[0].lower()):
            raise PreflightError(f"source hash 行格式错误：{line}")
        name = _relative_path(parts[1], "source hash path")
        if name in result:
            raise PreflightError(f"source hash 重复：{name}")
        result[name] = parts[0].lower()
    if not result:
        raise PreflightError("source hash 文件为空")
    return result


def _validate_r2_spec(root: Path, entries: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    run = root / R2_REL
    spec_path = run / "parameter-scan.run_spec.json"
    source_file = run / "source_hashes.sha256"
    contract_path = run / "launch-contract.json"
    for path in (spec_path, source_file, contract_path):
        _require_entry(entries, path.relative_to(root).as_posix())
    spec = _json(spec_path)
    contract = _json(contract_path)
    if spec.get("schema_version") != 2 or spec.get("run_id") != "pentamer-negative-alpha-static-krylov-controls-r2-20260919":
        raise PreflightError("controls_r2 run-spec 标识不匹配")
    if spec.get("run_dir") != R2_REL.as_posix():
        raise PreflightError("controls_r2 run_dir 必须是 bundle 内相对路径")
    if contract.get("status") != "prepared_only" or contract.get("launch_ready") is not False or contract.get("dry_run_only") is not True:
        raise PreflightError("controls_r2 合同不是 prepared_only/dry_run_only")
    for key, expected in (("cell_count", 2), ("concurrency", 1), ("stop_on_first_failure", True), ("retry_policy", "none")):
        if contract.get(key) != expected:
            raise PreflightError(f"controls_r2 合同字段错误：{key}")
    if contract.get("run_spec_sha256") != sha256(spec_path) or contract.get("source_hashes_sha256") != sha256(source_file):
        raise PreflightError("controls_r2 合同文件 hash 不匹配")
    if contract.get("julia_parse_fix_sha256") != EXPECTED_JULIA_SHA:
        raise PreflightError("controls_r2 未锁定解析修复 SHA")

    cells = spec.get("cells")
    if not isinstance(cells, list) or len(cells) != 2:
        raise PreflightError("controls_r2 必须恰好两个 cell")
    observed = set()
    for cell in cells:
        if not isinstance(cell, dict) or not isinstance(cell.get("params"), dict):
            raise PreflightError("controls_r2 cell 缺 params")
        params = cell["params"]
        alpha = _finite(params.get("alpha"), "cell.alpha")
        beta = _finite(params.get("beta"), "cell.beta")
        length = _exact_int(params.get("L"), "cell.L")
        krylov = _exact_int(params.get("eigsolve_krylovdim"), "cell.eigsolve_krylovdim")
        observed.add((alpha, beta, length, krylov))
    if observed != {(-0.1, 0.25, 80, 8), (-0.175, 0.25, 80, 8)}:
        raise PreflightError(f"controls_r2 cell 映射错误：{sorted(observed)}")
    settings = spec.get("settings")
    if not isinstance(settings, dict):
        raise PreflightError("controls_r2 缺 settings")
    required = {
        "nsweeps": 64, "threads": 8, "q_count": 401, "eigsolve_krylovdim": 8,
        "eigsolve_maxiter": 1, "eigsolve_tol": 1e-14, "warmstart": False,
        "retry_policy": "none", "maxdim_escalation": False, "noise_profile": "legacy",
        "random_seed": 20260811, "save_state": True, "enriched_diagnostics": True,
    }
    for key, expected in required.items():
        if settings.get(key) != expected:
            raise PreflightError(f"controls_r2 settings 错误：{key}")
    if settings.get("maxdim_by_L") != {"80": 1200} or settings.get("init_modes") != ["center", "ferro_j2"]:
        raise PreflightError("controls_r2 maxdim/init 错误")
    _same_float(settings.get("cutoff"), 1e-11, "controls_r2.cutoff")
    acceptance = spec.get("acceptance")
    if not isinstance(acceptance, dict) or any(acceptance.get(key) is not True for key in ("no_warmstart", "no_128", "no_retry")):
        raise PreflightError("controls_r2 acceptance 未锁定")

    hashes = _read_hash_file(source_file)
    for name, digest in hashes.items():
        path = root / name
        if not path.is_file() or sha256(path) != digest:
            raise PreflightError(f"controls_r2 source hash 不匹配：{name}")
        _require_entry(entries, name)
        if entries is not None and entries[name]["sha256"].lower() != digest:
            raise PreflightError(f"controls_r2 source 未按 release hash 覆盖：{name}")
    if hashes.get(JULIA_SOURCE) != EXPECTED_JULIA_SHA or hashes.get(JULIA_SOURCE) == OLD_JULIA_SHA:
        raise PreflightError("controls_r2 source 未使用新 Julia 解析修复")
    return {"cells": 2, "krylovdim": 8, "source_hashes": hashes, "run_spec": spec, "contract": contract}


def _metric_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise PreflightError(f"缺少 metrics：{path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or ()) != {"metric", "value"}:
            raise PreflightError(f"metrics 字段错误：{path}")
        result: dict[str, str] = {}
        for row in reader:
            name, value = row.get("metric"), row.get("value")
            if not isinstance(name, str) or not name or name in result or not isinstance(value, str) or not value:
                raise PreflightError(f"metrics 字段重复或缺值：{path}")
            result[name] = value
    if not result:
        raise PreflightError(f"metrics 为空：{path}")
    return result


def _load_ed(root: Path) -> tuple[Any, str]:
    path = root / ED_SOURCE
    if not path.is_file():
        raise PreflightError(f"缺少 ED helper：{path}")
    spec = importlib.util.spec_from_file_location("static_krylov_ed_reference_v2", path)
    if spec is None or spec.loader is None:
        raise PreflightError("无法加载 ED helper")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        raise PreflightError("ED helper 加载失败") from error
    if not callable(getattr(module, "solve_sector", None)):
        raise PreflightError("ED helper 缺少 solve_sector")
    return module, sha256(path)


def _validate_csv(path: Path, required: set[str]) -> int:
    if not path.is_file() or path.stat().st_size <= 0:
        raise PreflightError(f"增强产物缺失或为空：{path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not required.issubset(set(reader.fieldnames or ())):
            raise PreflightError(f"增强产物字段不完整：{path}")
        rows = sum(1 for _ in reader)
    if rows <= 0:
        raise PreflightError(f"增强产物无数据行：{path}")
    return rows


def _validate_command(wrapper: dict[str, Any], alpha: float, case_id: str) -> None:
    command = wrapper.get("command")
    if not isinstance(command, list) or len(command) != 21 or any(not isinstance(item, str) for item in command):
        raise PreflightError(f"v4 command 形状错误：{case_id}")
    if not command[0].replace("\\", "/").split("/")[-1].lower().startswith("julia"):
        raise PreflightError(f"v4 Julia executable 错误：{case_id}")
    if command[1:5] != ["--startup-file=no", "--threads=2", "--project=.", "scripts/autoresearch_v5/negative_static_cell.jl"]:
        raise PreflightError(f"v4 Julia 启动协议漂移：{case_id}")
    if not command[5].replace("\\", "/").endswith(f"/static_krylov_smoke_v4/{case_id}"):
        raise PreflightError(f"v4 输出路径漂移：{case_id}")
    expected = [str(alpha), "0.25", "2", "64", "16", "1e-11", "center", "0", "8", "401", "1", "legacy", "20260811", "1", "8"]
    if command[6:] != expected:
        raise PreflightError(f"v4 参数协议漂移：{case_id}")


def _validate_case(root: Path, case_id: str, alpha: float, ed: Any, entries: dict[str, dict[str, Any]] | None) -> dict[str, Any]:
    directory = root / V4_REL / case_id
    wrapper_path = directory / "wrapper_run.json"
    _require_entry(entries, wrapper_path.relative_to(root).as_posix())
    wrapper = _json(wrapper_path)
    if wrapper.get("cell_id") != case_id or type(wrapper.get("returncode")) is not int or wrapper.get("returncode") != 0 or wrapper.get("timed_out") is not False:
        raise PreflightError(f"v4 wrapper 未正常完成：{case_id}")
    if type(wrapper.get("krylovdim")) is not int or wrapper.get("krylovdim") != 8 or type(wrapper.get("L")) is not int or wrapper.get("L") != 10:
        raise PreflightError(f"v4 wrapper L/Krylov 错误：{case_id}")
    _same_float(wrapper.get("alpha"), alpha, f"{case_id}.wrapper.alpha")
    _same_float(wrapper.get("beta"), 0.25, f"{case_id}.wrapper.beta")
    _validate_command(wrapper, alpha, case_id)

    for artifact in V4_ARTIFACTS:
        _require_entry(entries, (directory / artifact).relative_to(root).as_posix())
    metrics_path = directory / "metrics.csv"
    metrics = _metric_values(metrics_path)
    for key in ("alpha", "beta", "n_units", "L", "energy_sz0", "energy_sz1", "state_norm_sz0", "state_norm_sz1", "total_sz0", "total_sz1", "nsweeps_requested", "nsweeps_completed_sz0", "nsweeps_completed_sz1", "cutoff", "structure_factor_q_count", "eigsolve_krylovdim", "random_seed_base", "enriched_seconds"):
        if key not in metrics:
            raise PreflightError(f"v4 metrics 缺字段 {key}：{case_id}")
        _finite(metrics[key], f"{case_id}.metrics.{key}")
    _same_float(metrics["alpha"], alpha, f"{case_id}.metrics.alpha")
    for key, expected in (("beta", 0.25), ("n_units", 2), ("L", 10), ("nsweeps_requested", 16), ("structure_factor_q_count", 401), ("eigsolve_krylovdim", 8), ("random_seed_base", 20260811)):
        _same_float(metrics[key], expected, f"{case_id}.metrics.{key}")
    _same_float(metrics["cutoff"], 1e-11, f"{case_id}.metrics.cutoff")
    if metrics.get("noise_profile") != "legacy" or metrics.get("init_mode_sz0") != "center" or metrics.get("init_mode_sz1") != "center":
        raise PreflightError(f"v4 初态/noise 漂移：{case_id}")
    if metrics.get("enriched_diagnostics") != "true" or _finite(metrics["enriched_seconds"], "enriched_seconds") <= 0:
        raise PreflightError(f"v4 enriched 未实际开启：{case_id}")
    for key in ("state_norm_sz0", "state_norm_sz1"):
        if abs(_finite(metrics[key], key) - 1.0) > 1e-8:
            raise PreflightError(f"{case_id} {key} 不接近 1")
    for key, expected in (("total_sz0", 0.0), ("total_sz1", 1.0), ("nsweeps_completed_sz0", 16), ("nsweeps_completed_sz1", 16)):
        if abs(_finite(metrics[key], key) - expected) > (1e-8 if "total" in key else 0.0):
            raise PreflightError(f"{case_id} {key} 不匹配")
    if not (directory / "state_sz0.jld2").is_file() or (directory / "state_sz0.jld2").stat().st_size <= 0:
        raise PreflightError(f"{case_id} 保存态缺失")
    _validate_csv(directory / "entropy_profile_full.csv", {"bond", "bond_class", "log_chord", "entropy"})
    _validate_csv(directory / "bond_correlations.csv", {"bond", "left_site", "right_site", "bond_class", "correlation"})
    _validate_csv(directory / "bond_bond_connected.csv", {"bond_class", "reference_bond", "target_bond", "distance_units", "connected"})

    deltas: dict[str, float] = {}
    ed_rows: dict[str, dict[str, Any]] = {}
    for target_sz in (0, 1):
        try:
            row = ed.solve_sector(alpha, 0.25, target_sz)
        except Exception as error:
            raise PreflightError(f"ED 重算失败：{case_id}/Sz{target_sz}") from error
        dimension = _exact_int(row.get("dimension"), f"ED dimension Sz{target_sz}")
        expected_dim = 252 if target_sz == 0 else 210
        if dimension != expected_dim:
            raise PreflightError(f"ED 维数错误：{case_id}/Sz{target_sz}")
        residual = _finite(row.get("residual_norm"), f"ED residual Sz{target_sz}")
        norm = _finite(row.get("norm"), f"ED norm Sz{target_sz}")
        total_sz = _finite(row.get("total_sz"), f"ED total Sz{target_sz}")
        if residual > 1e-10 or abs(norm - 1.0) > 1e-12 or abs(total_sz - target_sz) > 1e-12:
            raise PreflightError(f"ED 自检门失败：{case_id}/Sz{target_sz}")
        energy = _finite(row.get("energy"), f"ED energy Sz{target_sz}")
        delta = abs(_finite(metrics[f"energy_sz{target_sz}"], f"metrics.energy_sz{target_sz}") - energy)
        if delta > 1e-8:
            raise PreflightError(f"energy 超过 1e-8：{case_id}/Sz{target_sz}")
        deltas[f"energy_abs_delta_sz{target_sz}"] = delta
        ed_rows[f"sz{target_sz}"] = {"energy": energy, "dimension": dimension, "residual_ed": residual, "norm_ed": norm, "total_sz_ed": total_sz}
    return {"cell_id": case_id, "alpha": alpha, "energy_abs_deltas": deltas, "ed": ed_rows, "metrics_sha256": sha256(metrics_path), "wrapper_sha256": sha256(wrapper_path)}


def validate_v4_evidence(root: Path = ROOT, entries: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    metadata_path = root / V4_REL / "run_metadata.json"
    manifest_path = root / V4_REL / "manifest.json"
    _require_entry(entries, metadata_path.relative_to(root).as_posix())
    _require_entry(entries, manifest_path.relative_to(root).as_posix())
    metadata = _json(metadata_path)
    manifest = _json(manifest_path)
    if metadata.get("mode") != "execute" or metadata.get("cases") != [{"alpha": -0.1, "krylovdim": 8}, {"alpha": -0.175, "krylovdim": 8}]:
        raise PreflightError("v4 metadata cases/mode 不匹配")
    settings = metadata.get("settings")
    expected_settings = {"beta": 0.25, "L": 10, "maxdim": 64, "nsweeps": 16, "cutoff": 1e-11, "threads": 2, "init_mode_sz0": "center", "init_mode_sz1": "center", "noise_profile": "legacy", "random_seed": 20260811, "save_state": True, "enriched_diagnostics": True, "krylov_dimensions": [8]}
    if settings != expected_settings:
        raise PreflightError("v4 metadata settings 不匹配")
    if metadata.get("source_change_scope", {}).get("new_julia_cell_sha256") != EXPECTED_JULIA_SHA:
        raise PreflightError("v4 metadata 未锁定新 Julia 源码 SHA")
    source_hashes = metadata.get("source_hashes")
    if not isinstance(source_hashes, dict) or not source_hashes:
        raise PreflightError("v4 metadata 缺 source_hashes")
    for name, digest in source_hashes.items():
        safe_name = _relative_path(name, "v4 source path")
        if not isinstance(digest, str) or len(digest) != 64:
            raise PreflightError(f"v4 source hash 非法：{safe_name}")
        path = root / safe_name
        if not path.is_file() or sha256(path) != digest.lower():
            raise PreflightError(f"v4 实际源 hash 不匹配：{safe_name}")
        _require_entry(entries, safe_name)
        if entries is not None and entries[safe_name]["sha256"].lower() != digest.lower():
            raise PreflightError(f"v4 源 hash 未被 payload 覆盖：{safe_name}")
    if source_hashes.get(JULIA_SOURCE) != EXPECTED_JULIA_SHA or source_hashes.get(JULIA_SOURCE) == OLD_JULIA_SHA:
        raise PreflightError("v4 使用旧 Julia 源码 hash")
    output_dir = manifest.get("output_dir")
    if not isinstance(output_dir, str) or not output_dir.replace("\\", "/").rstrip("/").endswith("/" + str(V4_REL).replace("\\", "/")):
        raise PreflightError("v4 manifest output_dir 漂移")
    _require_entry(entries, ED_SOURCE)
    ed, ed_sha = _load_ed(root)
    summaries = [_validate_case(root, case_id, alpha, ed, entries) for case_id, alpha in CASES.items()]
    return {"launch_ready": True, "cases": summaries, "ed_helper_sha256": ed_sha, "source_hashes": source_hashes, "cached_gate_ignored": True}


def build_preflight(mode: str, manifest_path: Path, root: Path = ROOT) -> dict[str, Any]:
    release = validate_release_manifest(manifest_path, root)
    contract = _validate_r2_spec(root, release["entries"])
    result: dict[str, Any] = {"schema_version": 2, "mode": mode, "status": "prepared_only", "launch_ready": False, "network_used": False, "control_path": release["control_path"], "file_count": len(release["entries"]), "contract": {"cells": contract["cells"], "krylovdim": contract["krylovdim"]}}
    if mode == "launch":
        result["evidence"] = validate_v4_evidence(root, release["entries"])
        result["launch_ready"] = True
    else:
        result["evidence"] = {"status": "deferred_until_launch", "launch_ready": False}
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("upload", "launch"), required=True)
    parser.add_argument("--manifest", type=Path, default=ROOT / RELEASE_REL / "server_upload_manifest.json")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = build_preflight(args.mode, args.manifest.resolve(), args.root.resolve())
    except (OSError, PreflightError, json.JSONDecodeError) as error:
        result = {"status": "rejected", "mode": args.mode, "network_used": False, "reason": str(error)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
