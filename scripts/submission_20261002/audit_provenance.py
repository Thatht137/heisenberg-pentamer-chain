"""恢复已验证凭证，并登记可复核的 CV 保存态。"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    from pip._vendor import toml as tomllib

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/submission_20261002/provenance"
ARCHIVE = ROOT / "_archive/submission_cleanup_20260923"
K12_AUDIT = ROOT / "results/research_progress/closeout_mechanism_source_data_audit_20260920.json"
CV_TABLE = ROOT / "results/autoresearch_v5_20260806/round43_handoff_final_v2/accepted11/spectrum.csv"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def restore_k12() -> list[dict]:
    result = []
    for item in read_json(K12_AUDIT)["selected_files"]:
        if not any(name in item["path"] for name in (
            "static_krylov_k12_fetch_2052/", "static_krylov_k12_finalize_2057/"
        )):
            continue
        source = ARCHIVE / item["path"]
        destination = OUT / "recovered" / item["path"]
        if source.stat().st_size != item["bytes"] or digest(source) != item["sha256"]:
            raise ValueError(f"归档校验失败: {relative(source)}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if digest(destination) != item["sha256"]:
                raise ValueError(f"拒绝覆盖不同内容: {relative(destination)}")
        else:
            shutil.copy2(source, destination)
        if digest(destination) != item["sha256"]:
            raise ValueError(f"恢复后校验失败: {relative(destination)}")
        result.append({
            "original_path": item["path"], "archived_path": relative(source),
            "restored_path": relative(destination), "bytes": item["bytes"],
            "sha256": item["sha256"], "verified": True,
        })
    if len(result) != 6:
        raise ValueError("应恢复六份终态凭证")
    return result


def cv_inventory() -> list[dict]:
    groups: dict[Path, list[dict]] = {}
    for row in read_csv(CV_TABLE):
        source = Path(row["source_run"]).resolve()
        source.relative_to(ROOT)
        groups.setdefault(source, []).append(row)
    result = []
    for source, rows in groups.items():
        ledger = {}
        checksum_file = source / "checksums.sha256"
        if checksum_file.is_file():
            for line in checksum_file.read_text(encoding="utf-8-sig").splitlines():
                if line.strip():
                    expected, filename = line.split(maxsplit=1)
                    ledger[filename.replace("\\", "/").lstrip("*")] = expected
        files = []
        for path in sorted(source.rglob("*.jld2")):
            name = path.relative_to(source).as_posix()
            actual = digest(path)
            files.append({
                "path": relative(path), "bytes": path.stat().st_size,
                "sha256": actual, "ledger_sha256": ledger.get(name),
                "ledger_matches": actual == ledger.get(name) if name in ledger else None,
            })
        config_path = source / "run_config.json"
        config = read_json(config_path) if config_path.exists() else {}
        point_rows = []
        for path in sorted((source / "points").glob("omega-*.csv")):
            point_rows.extend(read_csv(path))
        inferred_omega = float(point_rows[-1]["omega"]) if point_rows else None
        result.append({
            "run": relative(source),
            "accepted_omegas": [float(row["omega"]) for row in rows],
            "reported_residuals": [float(row["relative_residual"]) for row in rows],
            "parameters": {key: config.get(key) for key in (
                "alpha", "beta", "n_units", "q_over_pi", "eta", "omega_order"
            )},
            "jld2_files": files,
            "latest_solution_omega_inferred_from_ordered_point_csv": inferred_omega,
            "checkpoint_scalar_read_performed": False,
            "independent_stable_residual_performed": False,
        })
    return result


def restore_k12_payload() -> dict:
    original = "results/autoresearch_v5_20260920/static_krylov_k12_fetch_2052/negdiag-a01000-b02500-L080-k12"
    source = ARCHIVE / original
    destination = OUT / "recovered" / original
    parent_expected = "3f6fca0054e80bc7219dbc5193d217d5073caa90847709a73154ec79a54e0bd3"
    final_summary = read_json(OUT / "recovered/results/autoresearch_v5_20260920/static_krylov_k12_finalize_2057/summary.json")
    historical = {
        item["path"].replace("\\", "/"): item
        for item in final_summary["input_sha256"] if item["role"] == "k12_cell_dir"
    }
    if digest(source / "checksums.sha256") != parent_expected:
        raise ValueError("k12 父目录校验表与历史终态登记不符")
    verified = {}
    for ledger in sorted(source.rglob("checksums.sha256")):
        for line in ledger.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            expected, filename = line.split(maxsplit=1)
            path = (ledger.parent / filename.lstrip("*")).resolve()
            path.relative_to(source.resolve())
            if digest(path) != expected:
                raise ValueError(f"k12 原始归档哈希失败: {relative(path)}")
            verified[path] = expected
    entries = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        target = destination / path.relative_to(source)
        actual = digest(path)
        name = path.relative_to(source).as_posix()
        record = historical.get(name)
        if record is None or actual != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise ValueError(f"k12 文件与历史终态登记不符: {relative(path)}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if digest(target) != actual:
                raise ValueError(f"拒绝覆盖不同内容: {relative(target)}")
        else:
            shutil.copy2(path, target)
        if digest(target) != actual:
            raise ValueError(f"k12 恢复文件校验失败: {relative(target)}")
        entries.append({"original_path": f"{original}/{path.relative_to(source).as_posix()}",
                        "archived_path": relative(path), "restored_path": relative(target),
                        "bytes": path.stat().st_size, "sha256": actual,
                        "checksum_ledger_verified": path.resolve() in verified,
                        "historical_terminal_record_verified": True})
    if len(entries) != len(historical):
        raise ValueError("k12 原始目录与历史终态文件集合不一致")
    manifest = read_json(destination / "manifest.json")
    support = []
    for name, expected in manifest["provenance"]["code_sha256"].items():
        path = ROOT / name
        if digest(path) != expected:
            raise ValueError(f"k12 当前脚本与历史版本不同: {name}")
        support.append({"path": name, "sha256": expected, "historical_hash_verified": True})
    for item in final_summary["input_sha256"]:
        if item["role"] != "k12_run_spec":
            continue
        path = Path(item["root"]) / item["path"]
        if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise ValueError("k12 当前运行配置与历史版本不同")
        support.append({"path": relative(path), "sha256": item["sha256"], "historical_hash_verified": True})
    return {"status": "restored_and_verified", "parent_checksum_matches_terminal_record": True,
            "checksum_verified_file_count": len(verified), "historical_verified_file_count": len(entries), "files": entries,
            "existing_run_spec_and_code": support,
            "total_bytes": sum(item["bytes"] for item in entries)}


def stable_cv_checks(inventory: list[dict]) -> dict:
    records = []
    for path in sorted(OUT.glob("cv_*/verification.toml")):
        result = tomllib.loads(path.read_text(encoding="utf-8"))
        if "run_dir" not in result:
            records.append({"path": relative(path), "sha256": digest(path), "result": result})
            continue
        source = Path(result["run_dir"]).resolve()
        source.relative_to(ROOT)
        for name, expected in result["input_sha256"].items():
            if digest(source / name) != expected:
                raise ValueError(f"CV 复验输入已变化: {relative(source / name)}")
        config_path = source / "run_config.json"
        config = read_json(config_path)
        for key in ("alpha", "beta", "eta", "q_over_pi"):
            if result[key] != config[key]:
                raise ValueError(f"CV 复验参数与历史配置不符: {key}")
        if result["L"] != 5 * config["n_units"]:
            raise ValueError("CV 复验链长与历史配置不符")
        if result["hamiltonian_sha256"] != config["code_sha256"]["src/hamiltonian.jl"]:
            raise ValueError("CV 复验哈密顿量与历史版本不符")
        result["run_dir"] = relative(source)
        result["input_hashes_rechecked"] = True
        result["parameters_and_hamiltonian_match_historical_run"] = True
        result["historical_run_config_sha256"] = digest(config_path)
        records.append({"path": relative(path), "sha256": digest(path), "result": result})
    for item in inventory:
        matching = [row for row in records if row["result"].get("run_dir") == item["run"]]
        item["stable_residual_checks"] = matching
        item["checkpoint_scalar_read_performed"] = bool(matching)
        item["independent_stable_residual_performed"] = bool(matching)
        verified_omegas = [row["result"]["omega"] for row in matching]
        item["verified_checkpoint_omegas"] = verified_omegas
        item["accepted_omegas_without_stable_residual"] = [
            omega for omega in item["accepted_omegas"] if omega not in verified_omegas
        ]
    return {"results": records,
            "coverage_rule": "Only the explicitly loaded checkpoint frequency is reverified; no inference to overwritten or absent solutions.",
            "unverified_omegas": sorted(omega for item in inventory
                                       for omega in item["accepted_omegas_without_stable_residual"])}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    recovered = restore_k12()
    payload = restore_k12_payload()
    inventory = cv_inventory()
    stable_checks = stable_cv_checks(inventory)
    report = {
        "schema": "submission_provenance_audit/v2", "date": date.today().isoformat(),
        "scope": "local archive recovery, historical hash verification, and pointwise explicit CV residual checks",
        "k12_recovered": recovered,
        "k12_recovered_total_bytes": sum(item["bytes"] for item in recovered),
        "k12_original_raw_run": payload,
        "cv_source_table": {"path": relative(CV_TABLE), "sha256": digest(CV_TABLE)},
        "cv_saved_solutions": inventory,
        "stable_cv_residual_checks": stable_checks,
        "cv_residual_implementation": {
            "path": "scripts/autoresearch_v5/cv_dsf_resumable.jl",
            "sha256": digest(ROOT / "scripts/autoresearch_v5/cv_dsf_resumable.jl"),
            "formula": "sqrt(max(expanded_norm_squared,0))/norm(b)",
            "stable_alternative": "form r=(omega+E0+i*eta)*x-H*x-b explicitly and evaluate norm(r)/norm(b)",
            "additional_requirement": "bound MPO-application and MPS-sum truncation error",
            "reported_zero_is_not_stable_verification": True,
        },
        "remote_operations": False, "new_physics_calculation": False,
        "original_files_modified": False,
    }
    (OUT / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"recovered": len(recovered), "bytes": report["k12_recovered_total_bytes"],
                      "cv_source_runs": len(inventory), "report": relative(OUT / "audit.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
