#!/usr/bin/env python3
"""完成 low-005 回传后的本地严格交接。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = (ROOT / "results").resolve()
VALIDATOR = ROOT / "scripts/autoresearch_v5/validate_cv_run.py"
ASSEMBLER = ROOT / "scripts/autoresearch_v5/assemble_qpi_cv_anchors.py"
ANALYZER = ROOT / "scripts/autoresearch_v5/analyze_cv_tebd_crosscheck.py"
BASE_RUNS = [
    ROOT / "results/autoresearch_v5_20260730/round3_cv_L40_probe/cell-0001-L40-qpi-w020",
    ROOT / "results/autoresearch_v5_20260802/round21_cv_triplet_warmstart/cell-0002-L40-qpi-w025-w035",
    ROOT / "results/autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804/cell-l40-qpi-high-055",
    ROOT / "results/autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804/cell-l40-qpi-high-100",
    ROOT / "results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150",
]
TEBD = ROOT / "results/autoresearch_v5_20260803/round26_qpi_tebd_production/cell-alpha023-qpi-dt00125-t30"


def confined(path: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(RESULTS)
    return resolved


def run(command: list[str], allowed: set[int] = {0}) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode not in allowed:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"命令失败: {result.returncode}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retry-dir", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--validator-output", required=True)
    parser.add_argument("--anchor-dir", required=True)
    parser.add_argument("--analysis-dir", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    retry = confined(Path(args.retry_dir))
    receipt_path = confined(Path(args.receipt))
    validator_output = confined(Path(args.validator_output))
    anchor = confined(Path(args.anchor_dir))
    analysis = confined(Path(args.analysis_dir))
    summary_path = confined(Path(args.summary))
    for output in (validator_output, anchor, analysis, summary_path):
        if output.exists():
            raise SystemExit(f"拒绝覆盖已有输出: {output}")

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "pass" or receipt.get("non_clobbering") is not True:
        raise SystemExit("回传 receipt 未通过")
    if Path(str(receipt.get("destination", ""))).resolve() != retry:
        raise SystemExit("receipt 目标与 retry 目录不一致")

    run([sys.executable, str(VALIDATOR), "--run-dir", str(retry), "--output", str(validator_output)])
    validator = json.loads(validator_output.read_text(encoding="utf-8"))
    if validator.get("status") != "pass" or not all(validator.get("checks", {}).values()):
        raise SystemExit("low-005 validator 未全部通过")

    command = [sys.executable, str(ASSEMBLER)]
    for source in [*BASE_RUNS, retry]:
        command.extend(["--run-dir", str(source)])
    command.extend(["--output-dir", str(anchor)])
    run(command)

    analysis.mkdir(parents=True)
    crosscheck_path = analysis / "cross-method-check.json"
    result = run(
        [
            sys.executable,
            str(ANALYZER),
            "--cv-dir",
            str(anchor),
            "--tebd-dir",
            str(TEBD),
            "--output",
            str(crosscheck_path),
        ],
        {0, 2},
    )
    crosscheck = json.loads(crosscheck_path.read_text(encoding="utf-8"))
    if result.returncode == 0 and crosscheck.get("tag") != "Agreement":
        raise SystemExit("analyzer 返回码与标签矛盾")
    if result.returncode == 2 and crosscheck.get("tag") != "NotEvaluable":
        raise SystemExit("analyzer 不完整返回码与标签矛盾")

    summary = {
        "schema_version": 1,
        "status": "pass",
        "retry_validator": str(validator_output),
        "accepted_anchor": str(anchor),
        "accepted_points": len(crosscheck["diagnostics"]["cv_omegas"]),
        "crosscheck": str(crosscheck_path),
        "cross_method_tag": crosscheck["tag"],
        "coverage": crosscheck["coverage"],
        "next_action": (
            "关闭动态交叉门并进入图件审计"
            if crosscheck["tag"] == "Agreement"
            else "按条件计划补 omega=0.00；不降低 residual 门槛"
        ),
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
