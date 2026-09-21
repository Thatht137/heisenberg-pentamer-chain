#!/usr/bin/env python3
"""汇总 CV 单点收敛序列并生成验收记录。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def first_intensity(path: Path) -> float:
    with path.open(encoding="utf-8", newline="") as handle:
        return float(next(csv.DictReader(handle))["intensity"])


def resources(path: Path) -> tuple[float, float]:
    text = path.read_text(encoding="utf-8")
    wall_match = re.search(r"Elapsed \(wall clock\) time .*: ([0-9:.]+)", text)
    rss_match = re.search(r"Maximum resident set size \(kbytes\): (\d+)", text)
    if not wall_match or not rss_match:
        raise ValueError(f"资源日志字段缺失: {path}")
    fields = [float(value) for value in wall_match.group(1).split(":")]
    wall_seconds = sum(value * 60**index for index, value in enumerate(reversed(fields)))
    return wall_seconds, float(rss_match.group(1)) / 1024**2


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    parser.add_argument("cells", nargs="+")
    args = parser.parse_args()
    cells = [Path(cell).resolve() for cell in args.cells]
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    points: set[tuple[object, ...]] = set()
    for cell in cells:
        manifest = load_json(cell / "manifest.json")
        params = manifest["params"]
        settings = manifest["settings"]
        diagnostics = manifest["diagnostics"]
        wall_seconds, peak_rss_gib = resources(cell / "resource.log")
        point = (
            params["alpha"], params["beta"], params["L"], params["q_over_pi"],
            settings["eta"], params["omega_min"], params["omega_max"],
        )
        points.add(point)
        rows.append({
            "cell": cell.name,
            "cv_cutoff": settings.get("cv_cutoff", settings.get("cutoff")),
            "cv_maxdim": settings["cv_maxdim"],
            "nsweeps": settings["nsweeps"],
            "solution_maxdim": diagnostics["max_solution_dim"],
            "residual": diagnostics["max_cv_relative_residual"],
            "intensity": first_intensity(cell / "spectrum.csv"),
            "cv_seconds": diagnostics["cv_seconds"],
            "wall_seconds": wall_seconds,
            "peak_rss_gib": peak_rss_gib,
            "accepted": manifest.get("acceptance", {}).get("status") == "pass",
        })

    rows.sort(key=lambda row: float(row["cv_cutoff"]), reverse=True)
    tightest_intensity = float(rows[-1]["intensity"])
    for row in rows:
        row["relative_intensity_drift"] = abs(
            float(row["intensity"]) - tightest_intensity
        ) / abs(tightest_intensity)

    residuals = [float(row["residual"]) for row in rows]
    checks = {
        "same_physical_point": len(points) == 1,
        "residual_monotonic": all(
            right < left for left, right in zip(residuals, residuals[1:])
        ),
        "tightest_residual": residuals[-1] <= 1e-5,
        "tightest_pair_intensity": (
            float(rows[-2]["relative_intensity_drift"]) <= 0.02 if len(rows) > 1 else False
        ),
        "nonnegative_alpha": all(float(point[0]) >= 0 for point in points),
    }
    summary = {
        "tag": "Agreement" if all(checks.values()) else "Needs refinement",
        "checks": checks,
        "budgets": {"max_residual": 1e-5, "relative_intensity_drift": 0.02},
        "point": list(next(iter(points))) if len(points) == 1 else None,
        "residual_improvement": residuals[0] / residuals[-1],
        "rows": rows,
    }

    csv_path = outdir / "convergence.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    json_path = outdir / "convergence_summary.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    checksum_path = outdir / "analysis_checksums.sha256"
    checksum_path.write_text(
        f"{sha256(csv_path)}  {csv_path.name}\n{sha256(json_path)}  {json_path.name}\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    if summary["tag"] != "Agreement":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
