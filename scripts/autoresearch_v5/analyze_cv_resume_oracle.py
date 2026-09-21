#!/usr/bin/env python3
"""验收两段 CV 恢复任务并与精确谱逐点比较。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_metrics(path: Path) -> dict[str, object]:
    values: dict[str, object] = {}
    for row in read_csv(path):
        value = row["value"]
        if value.lower() in {"true", "false"}:
            values[row["metric"]] = value.lower() == "true"
            continue
        try:
            values[row["metric"]] = float(value)
        except ValueError:
            values[row["metric"]] = value
    return values


def verify_checksums(run_dir: Path) -> int:
    count = 0
    for line in (run_dir / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(maxsplit=1)
        path = (run_dir / relative).resolve()
        path.relative_to(run_dir)
        if not path.is_file() or sha256(path) != expected:
            raise SystemExit(f"cell 哈希失败: {relative}")
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--exact", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    exact_path = args.exact.resolve()
    outdir = args.outdir.resolve()
    if outdir.exists() and any(outdir.iterdir()):
        raise SystemExit(f"拒绝覆盖已有分析: {outdir}")
    outdir.mkdir(parents=True, exist_ok=True)

    checksum_files = verify_checksums(run_dir)
    spectrum = read_csv(run_dir / "spectrum.csv")
    exact = read_csv(exact_path)
    exact_by_omega = {round(float(row["omega"]), 12): float(row["intensity"]) for row in exact}
    attempts = [read_json(path) for path in sorted(run_dir.glob("attempt-*.json"))]
    metrics = read_metrics(run_dir / "metrics.csv")
    status = read_json(run_dir / "status.json")
    manifest = read_json(run_dir / "manifest.json")
    point_files = sorted((run_dir / "points").glob("omega-*.csv"))

    comparison: list[dict[str, float]] = []
    for row in spectrum:
        omega = float(row["omega"])
        cv = float(row["intensity"])
        oracle = exact_by_omega[round(omega, 12)]
        comparison.append({
            "omega": omega,
            "exact": oracle,
            "cv": cv,
            "absolute_error": abs(cv - oracle),
        })

    numerator = math.sqrt(sum((row["cv"] - row["exact"]) ** 2 for row in comparison))
    denominator = math.sqrt(sum(row["exact"] ** 2 for row in comparison))
    relative_l2 = numerator / denominator
    max_absolute = max(row["absolute_error"] for row in comparison)
    checks = {
        "cell_checksums": checksum_files > 0,
        "three_spectrum_points": len(spectrum) == 3,
        "three_unique_point_files": len(point_files) == 3 and len({path.name for path in point_files}) == 3,
        "two_attempts": len(attempts) == 2,
        "first_attempt_partial": len(attempts) == 2
        and attempts[0].get("status") == "partial"
        and attempts[0].get("completed_points") == 1.0,
        "second_attempt_resumed": len(attempts) == 2
        and attempts[1].get("resume") is True
        and attempts[1].get("status") == "success"
        and attempts[1].get("completed_points") == 3.0,
        "ground_reused": metrics.get("ground_reused") is True,
        "source_reused": metrics.get("source_reused") is True,
        "accepted": status.get("accepted") is True
        and manifest.get("acceptance", {}).get("status") == "pass",
        "residual": isinstance(metrics.get("max_cv_residual"), float)
        and metrics["max_cv_residual"] <= 1e-5,
        "exact_agreement": relative_l2 <= 1e-8 and max_absolute <= 1e-8,
        "no_temporary_files": not list(run_dir.rglob("*.tmp")),
    }
    passed = all(checks.values())
    summary = {
        "tag": "Agreement" if passed else "Disagreement",
        "checks": checks,
        "checksum_files": checksum_files,
        "relative_l2": relative_l2,
        "max_absolute_error": max_absolute,
        "max_cv_relative_residual": metrics.get("max_cv_residual"),
        "attempt_1_cv_seconds": attempts[0].get("cv_seconds_this_attempt") if attempts else None,
        "attempt_2_cv_seconds": attempts[1].get("cv_seconds_this_attempt") if len(attempts) > 1 else None,
    }
    (outdir / "resume_oracle_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (outdir / "resume_oracle_comparison.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)
    outputs = sorted(path for path in outdir.iterdir() if path.is_file())
    (outdir / "analysis_checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in outputs), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
