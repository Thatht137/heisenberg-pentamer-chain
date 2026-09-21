#!/usr/bin/env python3
"""从已验收 run 组装 CV 锚点，不接受失败或重复数据。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_run(run_dir: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    manifest_path = run_dir / "manifest.json"
    spectrum_path = run_dir / "spectrum.csv"
    if not manifest_path.is_file() or not spectrum_path.is_file():
        raise SystemExit(f"缺少 run 证据: {run_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "success" or manifest.get("acceptance", {}).get("status") != "pass":
        raise SystemExit(f"run 未通过验收: {run_dir}")
    params = manifest.get("params", {})
    alpha, beta = float(params.get("alpha", -1)), float(params.get("beta", -1))
    if not 0 <= alpha <= 1 or not 0 <= beta <= 1:
        raise SystemExit(f"run 超出正区范围: {run_dir}")
    with spectrum_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"run 频谱为空: {run_dir}")
    parsed = []
    for row in rows:
        residual = float(row["relative_residual"])
        if residual > 1e-5:
            raise SystemExit(f"频点 residual 超门: {run_dir} omega={row['omega']}")
        parsed.append({
            "q_over_pi": float(row.get("q_over_pi", 1.0)),
            "omega": float(row["omega"]),
            "intensity": float(row["intensity"]),
            "relative_residual": residual,
            "source_run": run_dir.as_posix(),
        })
    return parsed, {
        "run_dir": run_dir.as_posix(),
        "manifest_sha256": sha256(manifest_path),
        "spectrum_sha256": sha256(spectrum_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    if output.exists():
        raise SystemExit(f"输出目录已存在，拒绝覆盖: {output}")
    all_rows, sources, parameter_keys = [], [], []
    for value in args.run_dir:
        run_dir = Path(value).resolve()
        rows, source = read_run(run_dir)
        all_rows.extend(rows)
        sources.append(source)
        params = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8")).get("params", {})
        parameter_keys.append(tuple(params.get(key) for key in ("alpha", "beta", "L", "q_over_pi", "eta")))
    if len(set(parameter_keys)) != 1:
        raise SystemExit("accepted run 的 alpha/beta/L/q/eta 不一致")
    keys = [(row["q_over_pi"], row["omega"]) for row in all_rows]
    if len(keys) != len(set(keys)):
        raise SystemExit("accepted run 含重复 q/omega 点")
    all_rows.sort(key=lambda row: (row["q_over_pi"], row["omega"]))
    output.mkdir(parents=True)
    spectrum = output / "spectrum.csv"
    with spectrum.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)
    params = json.loads((Path(args.run_dir[0]).resolve() / "manifest.json").read_text(encoding="utf-8")).get("params", {})
    manifest = {
        "schema_version": 1,
        "status": "success",
        "acceptance": {"status": "pass", "accepted_only": True, "residual_threshold": 1e-5},
        "params": params,
        "points": len(all_rows),
        "omega_range": [min(row["omega"] for row in all_rows), max(row["omega"] for row in all_rows)],
        "sources": sources,
        "spectrum_sha256": sha256(spectrum),
        "scope": {"negative_alpha_excluded": True, "fig9_excluded": True},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "points": len(all_rows), "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
