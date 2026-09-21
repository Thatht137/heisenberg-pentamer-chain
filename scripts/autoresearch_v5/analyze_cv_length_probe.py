#!/usr/bin/env python3
"""比较两个 CV 长度探针并生成保守成本投影。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def resource_values(path: Path) -> tuple[float, float]:
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
    parser.add_argument("--small", required=True)
    parser.add_argument("--large", required=True)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()
    small_dir = Path(args.small).resolve()
    large_dir = Path(args.large).resolve()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    small = load_json(small_dir / "manifest.json")
    large = load_json(large_dir / "manifest.json")
    small_wall, small_rss = resource_values(small_dir / "resource.log")
    large_wall, large_rss = resource_values(large_dir / "resource.log")

    keys = ("alpha", "beta", "q_over_pi", "omega_min", "omega_max")
    same_point = all(small["params"][key] == large["params"][key] for key in keys)
    same_method = all(
        small["settings"][key] == large["settings"][key]
        for key in ("method", "eta", "dmrg_cutoff", "cv_cutoff")
    )
    length_ratio = float(large["params"]["L"]) / float(small["params"]["L"])
    cv_time_ratio = (
        float(large["diagnostics"]["cv_seconds"])
        / float(small["diagnostics"]["cv_seconds"])
    )
    dimension_ratio = (
        float(large["diagnostics"]["max_solution_dim"])
        / float(small["diagnostics"]["max_solution_dim"])
    )
    rss_ratio = large_rss / small_rss
    time_exponent = math.log(cv_time_ratio) / math.log(length_ratio)
    dimension_exponent = math.log(dimension_ratio) / math.log(length_ratio)
    rss_exponent = math.log(rss_ratio) / math.log(length_ratio)
    projected_l = float(large["params"]["L"]) * length_ratio
    projected_cv_seconds = float(large["diagnostics"]["cv_seconds"]) * cv_time_ratio
    projected_rss_gib = large_rss * rss_ratio

    checks = {
        "same_physical_point": same_point,
        "same_accuracy_settings": same_method,
        "small_accepted": small.get("acceptance", {}).get("status") == "pass",
        "large_accepted": large.get("acceptance", {}).get("status") == "pass",
        "large_dimension_below_cap": (
            float(large["diagnostics"]["max_solution_dim"])
            < float(large["settings"]["cv_maxdim"])
        ),
        "projected_memory_below_soft_limit": projected_rss_gib < 64.0,
        "projected_cold_point_below_24h": projected_cv_seconds < 24 * 3600,
    }
    summary = {
        "tag": "Length probe passed" if all(checks.values()) else "Needs refinement",
        "checks": checks,
        "small_L": small["params"]["L"],
        "large_L": large["params"]["L"],
        "cv_time_ratio": cv_time_ratio,
        "solution_dimension_ratio": dimension_ratio,
        "peak_rss_ratio": rss_ratio,
        "empirical_exponents": {
            "cv_time_vs_L": time_exponent,
            "solution_dimension_vs_L": dimension_exponent,
            "peak_rss_vs_L": rss_exponent,
        },
        "cold_start_projection": {
            "L": projected_l,
            "cv_seconds": projected_cv_seconds,
            "cv_hours": projected_cv_seconds / 3600,
            "peak_rss_gib": projected_rss_gib,
            "scope": "single difficult frequency; one-step extrapolation only",
        },
        "decision": (
            "Do not launch an L=80 grid before measuring adjacent-frequency warm starts "
            "and validating resumable checkpoints."
        ),
    }
    output = outdir / "length_projection.json"
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    checksum = outdir / "analysis_checksums.sha256"
    checksum.write_text(f"{sha256(output)}  {output.name}\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["tag"] != "Length probe passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
