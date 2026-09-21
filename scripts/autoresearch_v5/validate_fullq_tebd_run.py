#!/usr/bin/env python3
"""独立验收已回传的全动量 TEBD run。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = (ROOT / "results").resolve()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def under_results(path: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(RESULTS)
    return resolved


def verify_checksums(run: Path) -> tuple[bool, list[str]]:
    checksum_file = run / "checksums.sha256"
    if not checksum_file.is_file():
        return False, ["缺少 checksums.sha256"]
    failures: list[str] = []
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = (run / relative.strip()).resolve()
        try:
            target.relative_to(run)
        except ValueError:
            failures.append(f"路径越界: {relative}")
            continue
        if not target.is_file():
            failures.append(f"文件缺失: {relative}")
        elif sha256(target) != expected:
            failures.append(f"哈希不匹配: {relative}")
    return not failures, failures


def read_matrix(path: Path) -> list[list[float]]:
    with path.open(encoding="utf-8", newline="") as handle:
        matrix = [[float(value) for value in row] for row in csv.reader(handle) if row]
    if not matrix or any(len(row) != len(matrix[0]) for row in matrix):
        raise ValueError(f"矩阵形状不规则: {path.name}")
    if not all(math.isfinite(value) for row in matrix for value in row):
        raise ValueError(f"矩阵含非有限值: {path.name}")
    return matrix


def negative_weight_fraction(matrix: list[list[float]]) -> float:
    negative = sum(abs(value) for row in matrix for value in row if value < 0.0)
    positive = sum(value for row in matrix for value in row if value > 0.0)
    return negative / max(negative + positive, 1e-30)


def validate(run: Path) -> dict[str, object]:
    run = under_results(run)
    failures: list[str] = []
    manifest_path = run / "manifest.json"
    status_path = run / "status.json"
    if not manifest_path.is_file() or not status_path.is_file():
        manifest: dict[str, object] = {}
        status: dict[str, object] = {}
        failures.append("缺少终态 manifest.json 或 status.json")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        status = json.loads(status_path.read_text(encoding="utf-8"))

    if manifest.get("status") != "success" or manifest.get("accepted") is not True:
        failures.append("manifest 未通过终态验收")
    if status.get("status") != "success" or status.get("accepted") is not True:
        failures.append("status 未通过终态验收")
    params = manifest.get("params", {})
    for name in ("alpha", "beta"):
        try:
            if not 0.0 <= float(params[name]) <= 1.0:
                failures.append(f"{name} 超出 [0,1]")
        except (KeyError, TypeError, ValueError):
            failures.append(f"缺少参数 {name}")

    settings = manifest.get("settings", {})
    diagnostics = manifest.get("diagnostics", {})
    acceptance = manifest.get("acceptance", {})
    required_acceptance = {
        "tebd_execution",
        "fourier_execution",
        "t0_included",
        "ground_variance",
        "sector_sz0",
        "raw_negative_weight_fraction",
    }
    if not isinstance(acceptance, dict) or not all(acceptance.get(key) is True for key in required_acceptance):
        failures.append("单 run acceptance 未全部通过")
    if settings.get("t0_included") is not True:
        failures.append("未包含 t=0")

    variance = float(diagnostics.get("variance_per_site", math.inf))
    total_sz = float(diagnostics.get("total_sz", math.inf))
    threshold = float(settings.get("max_negative_weight_fraction", 0.15))
    if variance > 1e-8:
        failures.append(f"variance_per_site 超门: {variance}")
    if abs(total_sz) > 1e-8:
        failures.append(f"总 Sz 超门: {total_sz}")

    checksum_ok, checksum_failures = verify_checksums(run)
    failures.extend(checksum_failures)
    raw_path = run / "spectrum_raw.csv"
    spectrum_path = run / "spectrum.csv"
    try:
        raw = read_matrix(raw_path)
        spectrum = read_matrix(spectrum_path)
        expected_shape = (int(settings["q_points"]), int(settings["omega_points"]))
        if (len(raw), len(raw[0])) != expected_shape or (len(spectrum), len(spectrum[0])) != expected_shape:
            failures.append(f"频谱形状不符: expected={expected_shape}")
        negative_fraction = negative_weight_fraction(raw)
        if negative_fraction > threshold:
            failures.append(f"raw 负谱权占比超门: {negative_fraction}")
        if min(value for row in spectrum for value in row) < -1e-10:
            failures.append("交付频谱存在负值")
    except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
        raw = []
        negative_fraction = math.inf
        failures.append(str(error))

    required_files = ("correlation.jld2", "spectrum.jld2", "run_config.json")
    missing = [name for name in required_files if not (run / name).is_file()]
    if missing:
        failures.append("缺少产物: " + ", ".join(missing))
    result = {
        "schema_version": 1,
        "status": "pass" if not failures else "fail",
        "run_dir": str(run),
        "cell_id": manifest.get("cell_id"),
        "checks": {
            "terminal_acceptance": manifest.get("accepted") is True and status.get("accepted") is True,
            "checksums": checksum_ok,
            "positive_region": not any("超出 [0,1]" in item for item in failures),
            "t0_included": settings.get("t0_included") is True,
            "variance_per_site": variance <= 1e-8,
            "sector_sz0": abs(total_sz) <= 1e-8,
            "raw_negative_weight_fraction": negative_fraction <= threshold,
            "artifacts": not missing,
        },
        "diagnostics": {
            "variance_per_site": variance,
            "total_sz": total_sz,
            "raw_negative_weight_fraction": negative_fraction,
            "max_negative_weight_fraction": threshold,
            "tstep": diagnostics.get("tstep"),
            "tmax": diagnostics.get("tmax"),
        },
        "failures": failures,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = under_results(Path(args.output))
    result = validate(Path(args.run_dir))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
