#!/usr/bin/env python3
"""从已完成的频点安全创建可恢复的相邻频率扩展 run。"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = (ROOT / "results").resolve()
COPY_FILES = ["ground_state.jld2", "source_state.jld2", "checkpoint_latest.jld2"]


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


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--cell-id", required=True)
    parser.add_argument("--omega-max", type=float, required=True)
    args = parser.parse_args()

    source = under_results(Path(args.source_dir))
    target = under_results(Path(args.outdir))
    config_path = source / "run_config.json"
    point_path = source / "points" / "omega-0001.csv"
    for filename in COPY_FILES:
        if not (source / filename).is_file():
            raise SystemExit(f"源 run 缺少 {filename}")
    if not config_path.is_file() or not point_path.is_file():
        raise SystemExit("源 run 缺少 run_config.json 或首个频点")
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"拒绝覆盖已有扩展 run: {target}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    source_cell_id = config.get("cell_id", "unknown")
    old_max = float(config["omega_max"])
    if args.omega_max <= old_max:
        raise SystemExit("扩展 omega_max 必须大于源 run 的 omega_max")
    target.mkdir(parents=True, exist_ok=True)
    (target / "points").mkdir()
    copied = {}
    for filename in COPY_FILES:
        source_file = source / filename
        target_file = target / filename
        shutil.copy2(source_file, target_file)
        copied[filename] = {"sha256": sha256(source_file), "size": source_file.stat().st_size}
    shutil.copy2(point_path, target / "points" / "omega-0001.csv")
    copied["points/omega-0001.csv"] = {
        "sha256": sha256(point_path),
        "size": point_path.stat().st_size,
    }

    config["cell_id"] = args.cell_id
    config["omega_max"] = args.omega_max
    write_json(target / "run_config.json", config)
    write_json(target / "seed_provenance.json", {
        "schema_version": 1,
        "kind": "cv_frequency_extension_seed",
        "source_dir": str(source),
        "source_cell_id": source_cell_id,
        "seed_frequency": float(config["omega_min"]),
        "old_omega_max": old_max,
        "new_omega_max": args.omega_max,
        "copied_files": copied,
        "negative_alpha_excluded": True,
    })
    print(json.dumps({"outdir": str(target), "seeded_points": 1, "omega_max": args.omega_max}, ensure_ascii=False))


if __name__ == "__main__":
    main()
