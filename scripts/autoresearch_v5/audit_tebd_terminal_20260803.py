"""审计已完成 TEBD run 的原始谱，不把裁剪谱当作通过。"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results/autoresearch_v5_20260802/round23_tebd_crosscheck/cell-alpha023-dt025-t15-auto"
OUT = ROOT / "results/research_progress/tebd_crosscheck_20260803.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def matrix(path: Path) -> list[list[float]]:
    return [[float(item) for item in row] for row in csv.reader(path.open(encoding="utf-8")) if row]


def main() -> None:
    manifest = json.loads((RUN / "manifest.json").read_text(encoding="utf-8"))
    progress = json.loads((RUN / "progress.json").read_text(encoding="utf-8"))
    raw = matrix(RUN / "spectrum_raw.csv")
    clipped = matrix(RUN / "spectrum.csv")
    raw_values = [value for row in raw for value in row]
    clipped_values = [value for row in clipped for value in row]
    minimum = min(raw_values)
    minimum_index = next((index for index, value in enumerate(raw_values) if value == minimum), 0)
    q_points = len(raw)
    omega_points = len(raw[0])
    iq, iw = divmod(minimum_index, omega_points)
    omega_max = float(manifest["settings"]["omega_max"])
    checks = {
        "tebd_finished": progress.get("tebd_step") == progress.get("tebd_total_steps") and progress.get("tebd_returncode") == 0,
        "fourier_finished": progress.get("fourier_q") == progress.get("fourier_total_q") and progress.get("fourier_returncode") == 0,
        "positive_region": 0.0 <= float(manifest["params"]["alpha"]) <= 1.0,
        "raw_shape": [len(raw), len(raw[0])] == [q_points, omega_points],
        "raw_finite": all(math.isfinite(value) for value in raw_values),
        "processed_nonnegative": min(clipped_values) >= -1e-10,
        "raw_nonnegative": minimum >= -1e-10,
    }
    result = {
        "schema_version": 1,
        "status": "pass" if all(checks.values()) else "fail",
        "run_dir": str(RUN),
        "parameters": manifest["params"],
        "settings": manifest["settings"],
        "progress": progress,
        "diagnostics": {
            "raw_shape": [q_points, omega_points],
            "raw_min": minimum,
            "raw_min_q_index": iq,
            "raw_min_omega_index": iw,
            "raw_min_q": 2.0 * math.pi * iq / max(q_points - 1, 1),
            "raw_min_omega": omega_max * iw / max(omega_points - 1, 1),
            "raw_negative_count": sum(value < 0.0 for value in raw_values),
            "raw_total_count": len(raw_values),
            "tmin_from_correlation": 0.025,
            "tmax": manifest["diagnostics"]["tmax"],
        },
        "checks": checks,
        "acceptance": checks,
        "interpretation": "TEBD 和 Fourier 都执行完成，但有限时间窗 raw spectrum 未通过非负性；裁剪后的显示谱不作为物理验收。",
        "provenance": {
            "manifest_sha256": sha256(RUN / "manifest.json"),
            "raw_spectrum_sha256": sha256(RUN / "spectrum_raw.csv"),
            "correlation_sha256": sha256(RUN / "correlation.jld2"),
            "negative_alpha_excluded": True,
        },
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "raw_min": minimum, "negative_count": result["diagnostics"]["raw_negative_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
