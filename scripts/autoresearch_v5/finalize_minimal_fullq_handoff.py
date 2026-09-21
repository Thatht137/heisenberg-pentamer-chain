#!/usr/bin/env python3
"""验收六个全动量 run 并组装三组 dt/dt2 交接。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = (ROOT / "results").resolve()
sys.path.insert(0, str(HERE))

from validate_fullq_tebd_run import validate  # noqa: E402


PAIR_CANDIDATES = {
    "uniform": [("fullq-uniform-dt025", "fullq-uniform-dt0125")],
    "weak": [
        ("fullq-weak-eta020-dt025", "fullq-weak-eta020-dt0125"),
        ("fullq-weak-dt025", "fullq-weak-dt0125"),
    ],
    "agreement": [
        ("fullq-agreement-eta020-dt025", "fullq-agreement-eta020-dt0125"),
        ("fullq-agreement-dt025", "fullq-agreement-dt0125"),
    ],
}


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


def resolve_pair(campaign: Path, point: str) -> tuple[str, str]:
    """优先使用 eta=0.20 重规划 cell，兼容旧批次。"""
    for coarse_name, refined_name in PAIR_CANDIDATES[point]:
        if (campaign / coarse_name).is_dir() and (campaign / refined_name).is_dir():
            return coarse_name, refined_name
    choices = ", ".join(f"{a}+{b}" for a, b in PAIR_CANDIDATES[point])
    raise SystemExit(f"缺少 {point} dt/dt2 pair；候选：{choices}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    campaign = under_results(Path(args.campaign_dir))
    output = under_results(Path(args.output_dir))
    if output.exists():
        raise SystemExit(f"拒绝覆盖已有交接目录: {output}")
    output.mkdir(parents=True)
    validator_dir = output / "validators"
    validator_dir.mkdir()
    pair_results: dict[str, object] = {}
    failures: list[str] = []

    for point in PAIR_CANDIDATES:
        coarse_name, refined_name = resolve_pair(campaign, point)
        coarse = campaign / coarse_name
        refined = campaign / refined_name
        validators: dict[str, object] = {}
        for label, run in (("coarse", coarse), ("refined", refined)):
            result = validate(run)
            validators[label] = result
            (validator_dir / f"{point}_{label}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            if result["status"] != "pass":
                failures.append(f"{point}/{label} 单 run 验收失败")
        cross_path = output / f"{point}_dt_crosscheck.json"
        if all(item["status"] == "pass" for item in validators.values()):
            command = [
                sys.executable,
                str(HERE / "analyze_tebd_crosscheck.py"),
                "--coarse-dir", str(coarse),
                "--refined-dir", str(refined),
                "--output", str(cross_path),
            ]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            cross = json.loads(cross_path.read_text(encoding="utf-8")) if cross_path.is_file() else {
                "status": "fail", "stderr": completed.stderr.strip()
            }
        else:
            cross = {"status": "blocked", "reason": "单 run 验收未全部通过"}
            cross_path.write_text(json.dumps(cross, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if cross.get("status") != "pass":
            failures.append(f"{point} dt/dt2 交叉验收失败")
        pair_results[point] = {
            "status": "pass" if cross.get("status") == "pass" and all(item["status"] == "pass" for item in validators.values()) else "fail",
            "coarse": coarse_name,
            "refined": refined_name,
            "crosscheck": cross_path.name,
            "parameters": cross.get("parameters"),
            "diagnostics": cross.get("diagnostics"),
        }

    summary = {
        "schema_version": 1,
        "status": "production_ready" if not failures else "blocked",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
        "campaign_dir": str(campaign),
        "pairs": pair_results,
        "acceptance": {
            "six_single_runs_pass": not any("单 run" in item for item in failures),
            "three_dt_pairs_pass": not any("dt/dt2" in item for item in failures),
        },
        "failures": failures,
        "next": "仅 production_ready 时允许生成全动量论文图",
    }
    summary_path = output / "handoff_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "checksums.sha256")
    (output / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.relative_to(output).as_posix()}\n" for path in files), encoding="ascii"
    )
    print(json.dumps(summary, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
