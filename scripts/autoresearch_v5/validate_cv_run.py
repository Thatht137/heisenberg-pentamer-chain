#!/usr/bin/env python3
"""独立验收已回传的 correction-vector CV run。"""

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
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def under_results(path: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(RESULTS)
    return resolved


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_checksums(run: Path) -> tuple[bool, list[str]]:
    checksum_path = run / "checksums.sha256"
    failures: list[str] = []
    if not checksum_path.is_file():
        return False, ["缺少 checksums.sha256"]
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = (run / relative).resolve()
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


def read_metric(path: Path, name: str) -> float | None:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("metric") == name:
                try:
                    return float(row["value"])
                except (KeyError, TypeError, ValueError):
                    return None
    return None


def read_spectrum(path: Path) -> list[dict[str, float]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows: list[dict[str, float]] = []
        for row in csv.DictReader(handle):
            values = {key: float(value) for key, value in row.items() if value is not None}
            if not values or not all(math.isfinite(value) for value in values.values()):
                raise ValueError(f"频谱含非有限值: {path}")
            rows.append(values)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-cv-residual", type=float, default=1e-5)
    args = parser.parse_args()

    run = under_results(Path(args.run_dir))
    output = under_results(Path(args.output))
    failures: list[str] = []
    status_path = run / "status.json"
    manifest_path = run / "manifest.json"
    if not status_path.is_file() or not manifest_path.is_file():
        failures.append("缺少终态 status.json 或 manifest.json")
        status: dict[str, object] = {}
        manifest: dict[str, object] = {}
    else:
        status = read_json(status_path)
        manifest = read_json(manifest_path)
        if status.get("status") != "success" or status.get("accepted") is not True:
            failures.append(f"run 未通过终态验收: {status}")
        if manifest.get("status") != "success":
            failures.append("manifest.status 不是 success")
        acceptance = manifest.get("acceptance", {})
        if not isinstance(acceptance, dict) or acceptance.get("status") != "pass":
            failures.append("manifest.acceptance.status 不是 pass")

    params = manifest.get("params", {})
    if isinstance(params, dict):
        for name in ("alpha", "beta"):
            try:
                if not 0.0 <= float(params[name]) <= 1.0:
                    failures.append(f"{name} 越界或为负")
            except (KeyError, TypeError, ValueError):
                failures.append(f"缺少参数 {name}")
    checksum_ok, checksum_failures = verify_checksums(run)
    failures.extend(checksum_failures)

    metrics_path = run / "metrics.csv"
    variance = read_metric(metrics_path, "variance_per_site")
    truncation = read_metric(metrics_path, "max_dmrg_truncation")
    residual = read_metric(metrics_path, "max_cv_residual")
    complete = read_metric(metrics_path, "complete")
    completed = read_metric(metrics_path, "completed_points")
    total = read_metric(metrics_path, "total_points")
    if variance is None or variance > 1e-8:
        failures.append(f"variance_per_site 未通过: {variance}")
    if truncation is None or truncation > 1e-8:
        failures.append(f"max_dmrg_truncation 未通过: {truncation}")
    if residual is None or residual > args.max_cv_residual:
        failures.append(f"max_cv_residual 未通过: {residual}")

    spectrum_path = run / "spectrum.csv"
    point_paths = sorted((run / "points").glob("omega-*.csv")) if (run / "points").is_dir() else []
    try:
        spectrum = read_spectrum(spectrum_path)
        points = [row for path in point_paths for row in read_spectrum(path)]
        intensities = [row["intensity"] for row in spectrum if "intensity" in row]
        source_rows = points if points else spectrum
        point_residuals = [
            row["relative_residual"] for row in source_rows if "relative_residual" in row
        ]
        schema_version = int(manifest.get("schema_version", 0))
        params = manifest.get("params", {})
        if completed is None or total is None:
            omega_min = float(params["omega_min"])
            omega_max = float(params["omega_max"])
            omega_step = float(params["omega_step"])
            expected = round((omega_max - omega_min) / omega_step) + 1
            total = float(expected)
            completed = float(len(spectrum))
        if complete is None:
            complete = 1.0 if completed == total and len(spectrum) == int(total) else 0.0
        if not intensities or min(intensities) < -1e-10:
            failures.append(f"谱强度非负性未通过: min={min(intensities) if intensities else None}")
        if not point_residuals or max(point_residuals) > args.max_cv_residual:
            failures.append(f"频点 residual 未通过: max={max(point_residuals) if point_residuals else None}")
        if complete != 1.0 or completed != total or len(spectrum) != int(total):
            failures.append(
                f"频点未完整: rows={len(spectrum)}, completed={completed}, total={total}, complete={complete}"
            )
        if schema_version >= 2 and len(point_paths) != int(total):
            failures.append(f"频点文件数量不一致: files={len(point_paths)}, total={int(total)}")
    except (FileNotFoundError, ValueError, KeyError) as error:
        failures.append(str(error))

    result = {
        "schema_version": 1,
        "status": "pass" if not failures else "fail",
        "run_dir": str(run),
        "checks": {
            "terminal_acceptance": not any("终态" in item or "manifest" in item for item in failures),
            "checksums": checksum_ok,
            "positive_region": not any("越界" in item or "为负" in item for item in failures),
            "variance_per_site": variance is not None and variance <= 1e-8,
            "dmrg_truncation": truncation is not None and truncation <= 1e-8,
            "cv_residual": residual is not None and residual <= args.max_cv_residual,
            "complete_spectrum": complete == 1.0 and completed == total,
            "nonnegative_spectrum": bool('intensities' in locals() and intensities) and min(intensities) >= -1e-10,
        },
        "diagnostics": {
            "variance_per_site": variance,
            "max_dmrg_truncation": truncation,
            "max_cv_residual": residual,
            "completed_points": completed,
            "total_points": total,
            "point_files": len(point_paths),
        },
        "failures": failures,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
