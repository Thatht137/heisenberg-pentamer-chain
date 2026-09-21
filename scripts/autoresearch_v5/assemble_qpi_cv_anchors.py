#!/usr/bin/env python3
"""组装同一物理实例的已验收 q=pi CV 稀疏锚点。"""

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


def verify_checksums(run: Path) -> bool:
    checksum_path = run / "checksums.sha256"
    if not checksum_path.is_file():
        return False
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = (run / relative.strip()).resolve()
        try:
            target.relative_to(run)
        except ValueError:
            return False
        if not target.is_file() or sha256(target) != expected:
            return False
    return True


def instance(manifest: dict[str, object]) -> tuple[float, float, int, float, str, str, str]:
    params = manifest["params"]
    settings = manifest["settings"]
    return (
        float(params["alpha"]),
        float(params["beta"]),
        int(params["L"]),
        float(settings["eta"]),
        str(settings["boundary"]),
        str(settings["sector"]),
        str(settings["momentum_normalization"]),
    )


def read_rows(run: Path) -> list[dict[str, float]]:
    with (run / "spectrum.csv").open(encoding="utf-8", newline="") as handle:
        rows = [{key: float(value) for key, value in row.items()} for row in csv.DictReader(handle)]
    if not rows or not all(math.isfinite(value) for row in rows for value in row.values()):
        raise ValueError(f"频谱无效: {run}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    runs = [Path(value).resolve() for value in args.run_dir]
    output = Path(args.output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"拒绝覆盖已有锚点集: {output}")
    output.mkdir(parents=True, exist_ok=True)

    manifests = [read_json(run / "manifest.json") for run in runs]
    reference = instance(manifests[0])
    if not 0.0 <= reference[0] <= 1.0 or not 0.0 <= reference[1] <= 1.0:
        raise SystemExit("参数超出正区")
    if reference[4:] != ("OBC", "Sz=0", "1/sqrt(L)"):
        raise SystemExit("边界、扇区或归一化不匹配")
    points: dict[float, dict[str, object]] = {}
    sources: list[dict[str, object]] = []
    for run, manifest in zip(runs, manifests):
        if instance(manifest) != reference:
            raise SystemExit(f"物理实例不一致: {run}")
        if manifest.get("status") != "success":
            raise SystemExit(f"manifest 未通过: {run}")
        acceptance = manifest.get("acceptance", {})
        if not isinstance(acceptance, dict) or acceptance.get("status") != "pass":
            raise SystemExit(f"单 run 验收未通过: {run}")
        if not verify_checksums(run):
            raise SystemExit(f"checksum 未通过: {run}")
        for row in read_rows(run):
            if not math.isclose(row["q_over_pi"], 1.0, rel_tol=0.0, abs_tol=1e-12):
                raise SystemExit(f"频谱不是 q=pi: {run}")
            omega = row["omega"]
            record = {
                "q_over_pi": 1.0,
                "omega": omega,
                "intensity": row["intensity"],
                "relative_residual": row["relative_residual"],
                "source_run": run.as_posix(),
            }
            if omega in points and not math.isclose(
                float(points[omega]["intensity"]), row["intensity"], rel_tol=1e-8, abs_tol=1e-12
            ):
                raise SystemExit(f"重复频点强度冲突: omega={omega:g}")
            points[omega] = record
        sources.append(
            {
                "run": run.as_posix(),
                "manifest_sha256": sha256(run / "manifest.json"),
                "spectrum_sha256": sha256(run / "spectrum.csv"),
                "checksums_sha256": sha256(run / "checksums.sha256"),
            }
        )

    ordered = [points[omega] for omega in sorted(points)]
    with (output / "spectrum.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["q_over_pi", "omega", "intensity", "relative_residual", "source_run"],
        )
        writer.writeheader()
        writer.writerows(ordered)
    manifest = {
        "schema_version": 1,
        "status": "success",
        "accepted": True,
        "params": {
            "alpha": reference[0],
            "beta": reference[1],
            "L": reference[2],
            "q_over_pi": 1.0,
            "omega_min": ordered[0]["omega"],
            "omega_max": ordered[-1]["omega"],
            "omega_points": len(ordered),
        },
        "settings": {
            "method": "validated_sparse_correction_vector_anchors",
            "eta": reference[3],
            "boundary": reference[4],
            "sector": reference[5],
            "momentum_normalization": reference[6],
        },
        "acceptance": {
            "status": "pass",
            "checks": {
                "source_runs_accepted": True,
                "source_checksums": True,
                "same_instance": True,
                "unique_omega": len(ordered) == len(points),
                "finite": all(
                    math.isfinite(float(row[key]))
                    for row in ordered
                    for key in ("omega", "intensity", "relative_residual")
                ),
                "nonnegative": min(float(row["intensity"]) for row in ordered) >= -1e-10,
                "residual": max(float(row["relative_residual"]) for row in ordered) <= 1e-5,
            },
        },
        "coverage": {
            "sparse_only": True,
            "main_peak_bracketed": False,
            "major_weight_window_covered": False,
        },
        "provenance": {
            "sources": sources,
            "negative_alpha_excluded": True,
            "figure_9_excluded": True,
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    files = [output / "manifest.json", output / "spectrum.csv"]
    (output / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8"
    )
    print(json.dumps({"status": "pass", "points": len(ordered), "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
