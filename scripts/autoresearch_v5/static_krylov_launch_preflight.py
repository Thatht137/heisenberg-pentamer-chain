#!/usr/bin/env python3
"""校验 static-krylov-controls 发布包；只读，不连接远端。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
R1_REL = Path("results/autoresearch_v5_20260919/static_krylov_controls_r1")
RELEASE_REL = Path("results/autoresearch_v5_20260919/static_krylov_controls_release_v1")
V2_REL = Path("results/autoresearch_v5_20260919/static_krylov_smoke_v2")
V3_REL = Path("results/autoresearch_v5_20260919/static_krylov_smoke_v3")
REQUIRED_SOURCES = (
    "Project.toml",
    "Manifest.toml",
    "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/static_krylov_ed_reference.py",
    "src/PentamerChain.jl",
    "src/hamiltonian.jl",
    "src/order_parameters.jl",
)
K8_CASES = ("a-0100-k8", "a-0175-k8")
CONTROL_FLOATS = {"beta": 0.25, "cutoff": 1e-11}


class PreflightError(ValueError):
    """可审计的预检拒绝。"""


def _json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PreflightError(f"缺少文件：{path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PreflightError(f"JSON 顶层不是对象：{path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def _same_float(value: Any, expected: float, label: str) -> None:
    if abs(_finite(value, label) - expected) > 1e-14:
        raise PreflightError(f"{label} 不匹配：{value!r} != {expected!r}")


def _relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")):
        raise PreflightError(f"{label} 不是安全相对路径")
    path = Path(value)
    if ".." in path.parts:
        raise PreflightError(f"{label} 含父目录：{value}")
    return value.replace("\\", "/")


def _entry_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise PreflightError("发布 manifest 缺少非空 files")
    mapped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise PreflightError("manifest files 含非对象项")
        path = _relative_path(entry.get("path"), "manifest path")
        if path in mapped:
            raise PreflightError(f"manifest path 重复：{path}")
        digest = entry.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
            raise PreflightError(f"manifest hash 非 SHA256：{path}")
        if isinstance(entry.get("bytes"), bool) or not isinstance(entry.get("bytes"), int) or entry["bytes"] < 0:
            raise PreflightError(f"manifest bytes 非法：{path}")
        mapped[path] = entry
    return mapped


def validate_release_manifest(manifest_path: Path, root: Path = ROOT) -> dict[str, Any]:
    manifest = _json(manifest_path)
    if manifest.get("schema_version") != 1 or manifest.get("release_id") != "static-krylov-controls-release-v1":
        raise PreflightError("发布 manifest schema/release_id 不匹配")
    if manifest.get("status") != "prepared_only":
        raise PreflightError("发布 manifest 不是 prepared_only")
    if manifest.get("launch_ready") is not None:
        raise PreflightError("launch_ready 必须由现场证据动态决定")
    if manifest.get("cell_count") != 2 or manifest.get("concurrency") != 1 or manifest.get("stop_on_first_failure") is not True:
        raise PreflightError("并发/停止策略不匹配")
    target = manifest.get("target")
    remote_run_dir = manifest.get("remote_run_dir")
    if not isinstance(target, str) or not target.startswith("/home/"):
        raise PreflightError("远端 target 不匹配 profile")
    if not isinstance(remote_run_dir, str) or not remote_run_dir.startswith("results/"):
        raise PreflightError("remote_run_dir 必须是仓库内相对路径")

    entries = _entry_map(manifest)
    old_path = root / R1_REL / "server_upload_manifest.json"
    old = _json(old_path)
    old_entries = _entry_map(old)
    base_paths = {path for path, entry in entries.items() if entry.get("group") == "control_input"}
    if base_paths != set(old_entries):
        raise PreflightError(f"18 项输入未原样保留：{len(base_paths)}")
    for path, old_entry in old_entries.items():
        entry = entries[path]
        if entry.get("sha256") != old_entry.get("sha256") or entry.get("bytes") != old_entry.get("bytes"):
            raise PreflightError(f"原18项 hash/bytes 改变：{path}")
    if len(base_paths) != 18:
        raise PreflightError(f"原18项数量错误：{len(base_paths)}")

    local_hashes: dict[str, str] = {}
    for path, entry in entries.items():
        local = root / path
        if not local.is_file():
            raise PreflightError(f"发布文件不存在：{path}")
        actual = sha256(local)
        if actual != entry["sha256"].lower():
            raise PreflightError(f"发布 hash 不匹配：{path}")
        local_hashes[path] = actual
    control_rel = manifest.get("control_path")
    if control_rel != str(manifest_path.resolve().relative_to(root).as_posix()):
        raise PreflightError("control_path 与 manifest 路径不一致")
    return {"manifest": manifest, "entries": entries, "local_hashes": local_hashes, "control_path": control_rel}


def validate_contract(root: Path = ROOT) -> dict[str, Any]:
    run = root / R1_REL
    spec = _json(run / "parameter-scan.run_spec.json")
    contract = _json(run / "launch-contract.json")
    server = _json(run / "server_upload_manifest.json")
    if contract.get("status") != "prepared_only" or contract.get("dry_run_only") is not True:
        raise PreflightError("旧合同不是 prepared_only/dry_run_only")
    if contract.get("launch_ready") is not False:
        raise PreflightError("旧合同必须保持 launch_ready=false")
    for key, expected in (("cell_count", 2), ("concurrency", 1), ("stop_on_first_failure", True), ("retry_policy", "none"), ("input_file_count", 18)):
        if contract.get(key) != expected:
            raise PreflightError(f"旧合同字段不匹配：{key}")
    hash_checks = {
        "run_spec_sha256": run / "parameter-scan.run_spec.json",
        "source_hashes_sha256": run / "source_hashes.sha256",
        "manifest_sha256": root / "Manifest.toml",
        "standard_sha256": root / "docs/negative_alpha_practical_convergence_standard_20260829.md",
    }
    for key, path in hash_checks.items():
        if contract.get(key) != sha256(path):
            raise PreflightError(f"旧合同 hash 不匹配：{key}")
    if server.get("status") != "prepared_only" or server.get("launch_allowed") is not False:
        raise PreflightError("旧上传 manifest 不得已授权")
    cells = spec.get("cells")
    if not isinstance(cells, list) or len(cells) != 2:
        raise PreflightError("L80 控制必须恰好两点")
    observed: set[tuple[float, float, int, int]] = set()
    for cell in cells:
        if not isinstance(cell, dict) or not isinstance(cell.get("params"), dict):
            raise PreflightError("cell 缺少 params")
        params = cell["params"]
        if isinstance(params.get("L"), bool) or isinstance(params.get("eigsolve_krylovdim"), bool):
            raise PreflightError("L/Krylov 不得为 bool")
        observed.add((float(params.get("alpha")), float(params.get("beta")), int(params.get("L")), int(params.get("eigsolve_krylovdim"))))
    if observed != {(-0.1, 0.25, 80, 8), (-0.175, 0.25, 80, 8)}:
        raise PreflightError(f"控制点不匹配：{sorted(observed)}")
    settings = spec.get("settings")
    if not isinstance(settings, dict):
        raise PreflightError("run spec 缺 settings")
    required = {
        "nsweeps": 64,
        "threads": 8,
        "q_count": 401,
        "eigsolve_krylovdim": 8,
        "eigsolve_maxiter": 1,
        "eigsolve_tol": 1e-14,
        "warmstart": False,
        "retry_policy": "none",
        "maxdim_escalation": False,
        "noise_profile": "legacy",
        "random_seed": 20260811,
        "save_state": True,
        "enriched_diagnostics": True,
    }
    for key, expected in required.items():
        if settings.get(key) != expected:
            raise PreflightError(f"run spec settings 不匹配：{key}")
    if settings.get("maxdim_by_L") != {"80": 1200} or settings.get("init_modes") != ["center", "ferro_j2"]:
        raise PreflightError("L80 maxdim/init 不匹配")
    _same_float(settings.get("cutoff"), CONTROL_FLOATS["cutoff"], "cutoff")
    acceptance = spec.get("acceptance")
    if not isinstance(acceptance, dict) or any(acceptance.get(key) is not True for key in ("no_warmstart", "no_128", "no_retry")):
        raise PreflightError("acceptance 未锁定单因素控制")
    return {"cells": 2, "krylovdim": 8, "threads": 8, "nsweeps": 64, "concurrency": 1, "stop_on_first_failure": True}


def _metric_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise PreflightError(f"缺少 k8 metrics：{path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or ()) != {"metric", "value"}:
            raise PreflightError(f"k8 metrics 字段错误：{path}")
        rows = list(reader)
    if not rows:
        raise PreflightError(f"k8 metrics 为空：{path}")
    return rows


def _metric_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for row in _metric_rows(path):
        name = row.get("metric")
        if not isinstance(name, str) or not name:
            raise PreflightError(f"metrics 含空字段：{path}")
        if name in values:
            raise PreflightError(f"metrics 字段重复：{name}")
        value = row.get("value")
        if not isinstance(value, str) or not value:
            raise PreflightError(f"metrics.{name} 缺值：{path}")
        values[name] = value
    return values


def _load_ed_helper(root: Path) -> tuple[Any, str]:
    path = root / "scripts/autoresearch_v5/static_krylov_ed_reference.py"
    if not path.is_file():
        raise PreflightError(f"缺少本地 ED helper：{path}")
    spec = importlib.util.spec_from_file_location("static_krylov_ed_reference_release", path)
    if spec is None or spec.loader is None:
        raise PreflightError(f"无法加载 ED helper：{path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        raise PreflightError(f"ED helper 加载失败：{path}") from error
    if not callable(getattr(module, "solve_sector", None)):
        raise PreflightError("ED helper 缺少 solve_sector")
    return module, sha256(path)


def _validate_command(wrapper: dict[str, Any], alpha: float, case_id: str) -> None:
    command = wrapper.get("command")
    if not isinstance(command, list) or len(command) != 21 or any(not isinstance(item, str) for item in command):
        raise PreflightError(f"k8 wrapper command 形状错误：{case_id}")
    executable = command[0].replace("\\", "/").rstrip("/").split("/")[-1].lower()
    if not executable.startswith("julia"):
        raise PreflightError(f"k8 wrapper Julia executable 不匹配：{case_id}")
    if command[1:5] != ["--startup-file=no", "--threads=2", "--project=.", "scripts/autoresearch_v5/negative_static_cell.jl"]:
        raise PreflightError(f"k8 wrapper Julia 启动协议漂移：{case_id}")
    output_path = command[5].replace("\\", "/")
    version = "v2" if alpha == -0.1 else "v3"
    if not output_path.endswith(f"/static_krylov_smoke_{version}/{case_id}"):
        raise PreflightError(f"k8 wrapper 输出路径漂移：{case_id}")
    expected = [str(alpha), "0.25", "2", "64", "16", "1e-11", "center", "0", "8", "401", "0", "legacy", "20260811", "0", "8"]
    if command[6:] != expected:
        raise PreflightError(f"k8 wrapper 参数协议漂移：{case_id}")


def _validate_wrapper(path: Path, alpha: float, ed_helper: Any) -> dict[str, Any]:
    wrapper = _json(path)
    case_id = "a-0100-k8" if alpha == -0.1 else "a-0175-k8"
    if wrapper.get("cell_id") != case_id:
        raise PreflightError(f"k8 wrapper cell_id 不匹配：{path}")
    if type(wrapper.get("returncode")) is not int or wrapper.get("returncode") != 0 or type(wrapper.get("timed_out")) is not bool or wrapper.get("timed_out") is not False:
        raise PreflightError(f"k8 wrapper 未正常返回：{path}")
    if type(wrapper.get("krylovdim")) is not int or wrapper.get("krylovdim") != 8 or type(wrapper.get("L")) is not int or wrapper.get("L") != 10:
        raise PreflightError(f"k8 wrapper 不是 L10/Krylov8：{path}")
    _same_float(wrapper.get("beta"), 0.25, "k8 beta")
    _same_float(wrapper.get("alpha"), alpha, "k8 alpha")
    _validate_command(wrapper, alpha, case_id)

    metrics_path = path.parent / "metrics.csv"
    metrics = _metric_values(metrics_path)
    required_numeric = (
        "alpha", "beta", "n_units", "L", "energy_sz0", "energy_sz1",
        "state_norm_sz0", "state_norm_sz1", "total_sz0", "total_sz1",
        "nsweeps_completed_sz0", "nsweeps_completed_sz1", "eigsolve_krylovdim",
        "nsweeps_requested", "cutoff", "structure_factor_q_count",
    )
    for key in required_numeric:
        if key not in metrics:
            raise PreflightError(f"metrics 缺字段：{key}：{path}")
        _finite(metrics[key], f"metrics.{key}")
    _same_float(metrics["alpha"], alpha, "metrics.alpha")
    _same_float(metrics["beta"], 0.25, "metrics.beta")
    for key, expected in (("n_units", 2.0), ("L", 10.0), ("eigsolve_krylovdim", 8.0), ("nsweeps_requested", 16.0), ("structure_factor_q_count", 401.0)):
        _same_float(metrics[key], expected, f"metrics.{key}")
    _same_float(metrics["cutoff"], 1e-11, "metrics.cutoff")
    if metrics.get("noise_profile") != "legacy" or metrics.get("init_mode_sz0") != "center" or metrics.get("init_mode_sz1") != "center":
        raise PreflightError(f"metrics 初态/noise 协议漂移：{path}")
    _same_float(metrics.get("random_seed_base"), 20260811, "metrics.random_seed_base")
    for key in ("state_norm_sz0", "state_norm_sz1"):
        if abs(_finite(metrics[key], key) - 1.0) > 1e-8:
            raise PreflightError(f"{key} 不接近 1：{path}")
    for key, expected in (("total_sz0", 0.0), ("total_sz1", 1.0)):
        if abs(_finite(metrics[key], key) - expected) > 1e-8:
            raise PreflightError(f"{key} 不匹配：{path}")
    if any(_finite(metrics[key], key) != 16.0 for key in ("nsweeps_completed_sz0", "nsweeps_completed_sz1")):
        raise PreflightError(f"sweeps 未完成16：{path}")

    deltas: dict[str, float] = {}
    ed_rows: dict[str, dict[str, float | int]] = {}
    for target_sz in (0, 1):
        try:
            row = ed_helper.solve_sector(alpha, 0.25, target_sz)
        except Exception as error:
            raise PreflightError(f"ED 重算失败：alpha={alpha}, Sz={target_sz}") from error
        dimension = int(row.get("dimension", -1))
        if dimension != (252 if target_sz == 0 else 210):
            raise PreflightError(f"ED 维数错误：alpha={alpha}, Sz={target_sz}")
        residual = _finite(row.get("residual_norm"), f"ED residual Sz{target_sz}")
        norm = _finite(row.get("norm"), f"ED norm Sz{target_sz}")
        total_sz = _finite(row.get("total_sz"), f"ED total Sz{target_sz}")
        if residual > 1e-10 or abs(norm - 1.0) > 1e-12 or abs(total_sz - target_sz) > 1e-12:
            raise PreflightError(f"ED 自检门失败：alpha={alpha}, Sz={target_sz}")
        energy = _finite(row.get("energy"), f"ED energy Sz{target_sz}")
        delta = abs(_finite(metrics[f"energy_sz{target_sz}"], f"metrics.energy_sz{target_sz}") - energy)
        if delta > 1e-8:
            raise PreflightError(f"energy Sz{target_sz} 超过 1e-8：{path}")
        deltas[f"energy_abs_delta_sz{target_sz}"] = delta
        ed_rows[f"sz{target_sz}"] = {"energy": energy, "residual_ed": residual, "norm_ed": norm, "total_sz_ed": total_sz, "dimension": dimension}
    return {
        "cell_id": case_id,
        "alpha": alpha,
        "energy_abs_deltas": deltas,
        "norms": {key: _finite(metrics[key], key) for key in ("state_norm_sz0", "state_norm_sz1")},
        "total_sz": {key: _finite(metrics[key], key) for key in ("total_sz0", "total_sz1")},
        "sweeps": 16,
        "ed": ed_rows,
        "command_sha256": hashlib.sha256(json.dumps(wrapper["command"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest(),
        "wrapper_sha256": sha256(path),
        "metrics_sha256": sha256(metrics_path),
    }


def _source_hashes(metadata: dict[str, Any], label: str, root: Path) -> dict[str, str]:
    sources = metadata.get("source_hashes_before")
    if not isinstance(sources, dict):
        raise PreflightError(f"{label} 缺 source_hashes_before")
    result: dict[str, str] = {}
    for name in REQUIRED_SOURCES:
        digest = sources.get(name)
        if not isinstance(digest, str) or len(digest) != 64:
            raise PreflightError(f"{label} 缺源 hash：{name}")
        actual_path = root / name
        if not actual_path.is_file() or sha256(actual_path) != digest.lower():
            raise PreflightError(f"{label} 实际源 hash 不匹配：{name}")
        result[name] = digest.lower()
    return result


def validate_k8_evidence(root: Path = ROOT, entries: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    v3 = _json(root / V3_REL / "manifest.json")
    gate = v3.get("k8_gate")
    if not isinstance(gate, dict) or gate.get("required_cases") != 2:
        raise PreflightError("v3 k8_gate 两个 cell 声明不完整")
    rows = gate.get("rows")
    if not isinstance(rows, list) or {row.get("cell_id") for row in rows if isinstance(row, dict)} != set(K8_CASES):
        raise PreflightError("v3 k8_gate 两个 cell 不完整")

    wrappers = {
        "a-0100-k8": root / V2_REL / "a-0100-k8" / "wrapper_run.json",
        "a-0175-k8": root / V3_REL / "a-0175-k8" / "wrapper_run.json",
    }
    v2_metadata = _json(root / V2_REL / "run_metadata.json")
    v3_metadata = _json(root / V3_REL / "run_metadata.json")
    hashes = [_source_hashes(v2_metadata, "v2", root), _source_hashes(v3_metadata, "v3", root)]
    if hashes[0] != hashes[1]:
        raise PreflightError("v2/v3 shared source hash 不一致")
    ed_helper, ed_helper_sha256 = _load_ed_helper(root)
    summaries = [_validate_wrapper(wrappers[case], -0.1 if case == "a-0100-k8" else -0.175, ed_helper) for case in K8_CASES]
    if entries is not None:
        for name, digest in hashes[0].items():
            entry = entries.get(name)
            if entry is None or entry.get("sha256", "").lower() != digest:
                raise PreflightError(f"k8 证据源 hash 不属于当前发布包：{name}")
    all_gate = v3.get("all_cases_gate")
    historical_nonblocking = isinstance(all_gate, dict) and all_gate.get("passed") is False
    return {
        "launch_ready": True,
        "evidence": summaries,
        "source_hashes": hashes[0],
        "ed_helper_sha256": ed_helper_sha256,
        "k8_cases": list(K8_CASES),
        "historical_all_cases_gate": all_gate.get("passed") if isinstance(all_gate, dict) else None,
        "historical_k3_gate_nonblocking": historical_nonblocking,
    }


def build_preflight(mode: str, manifest_path: Path, root: Path = ROOT) -> dict[str, Any]:
    release = validate_release_manifest(manifest_path, root)
    contract = validate_contract(root)
    result: dict[str, Any] = {
        "schema_version": 1,
        "mode": mode,
        "status": "prepared_only",
        "launch_ready": False,
        "network_used": False,
        "base_input_count": 18,
        "additional_file_count": len(release["entries"]) - 18,
        "control_path": release["control_path"],
        "contract": contract,
    }
    if mode == "launch":
        result["evidence"] = validate_k8_evidence(root, release["entries"])
        result["launch_ready"] = True
    else:
        result["evidence"] = {"status": "deferred_until_launch", "launch_ready": False}
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("upload", "launch"), required=True)
    parser.add_argument("--manifest", type=Path, default=ROOT / RELEASE_REL / "server_upload_manifest.json")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
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
