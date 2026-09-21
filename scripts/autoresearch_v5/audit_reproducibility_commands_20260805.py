#!/usr/bin/env python3
"""验证 bounded 七点结果的本地复算命令链。"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
OUTPUT = RESULTS / "research_progress/reproducibility_command_audit_20260805.json"
PYTHON = Path(sys.executable)
SCRIPTS = ROOT / "scripts/autoresearch_v5"
HIGH150 = RESULTS / "autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150"
TEBD = RESULTS / "autoresearch_v5_20260803/round26_qpi_tebd_production/cell-alpha023-qpi-dt00125-t30"
CANONICAL_ANCHOR = RESULTS / "autoresearch_v5_20260805/round40_qpi_cv_anchor_assembly_accepted"
CANONICAL_CROSS = RESULTS / "autoresearch_v5_20260805/round40_cv_tebd_accepted7_analysis/cross-method-check.json"
RUNS = [
    RESULTS / "autoresearch_v5_20260730/round3_cv_L40_probe/cell-0001-L40-qpi-w020",
    RESULTS / "autoresearch_v5_20260802/round21_cv_triplet_warmstart/cell-0002-L40-qpi-w025-w035",
    RESULTS / "autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804/cell-l40-qpi-high-055",
    RESULTS / "autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804/cell-l40-qpi-high-100",
    HIGH150,
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, encoding="utf-8")


def main() -> None:
    work = RESULTS / f"_reproduction_check_{uuid.uuid4().hex}"
    work.resolve().relative_to(RESULTS.resolve())
    work.mkdir()
    try:
        validator_output = work / "high150-validator.json"
        validator = run([
            str(PYTHON), "-X", "utf8", str(SCRIPTS / "validate_cv_run.py"),
            "--run-dir", str(HIGH150), "--output", str(validator_output),
        ])
        anchor = work / "accepted7"
        assemble_command = [
            str(PYTHON), "-X", "utf8", str(SCRIPTS / "assemble_qpi_cv_anchors.py"),
        ]
        for source in RUNS:
            assemble_command.extend(["--run-dir", str(source)])
        assemble_command.extend(["--output-dir", str(anchor)])
        assembler = run(assemble_command)
        cross_output = work / "cross/cross-method-check.json"
        analyzer = run([
            str(PYTHON), "-X", "utf8", str(SCRIPTS / "analyze_cv_tebd_crosscheck.py"),
            "--cv-dir", str(anchor), "--tebd-dir", str(TEBD), "--output", str(cross_output),
        ])

        validator_json = json.loads(validator_output.read_text(encoding="utf-8")) if validator_output.is_file() else {}
        anchor_json = json.loads((anchor / "manifest.json").read_text(encoding="utf-8")) if (anchor / "manifest.json").is_file() else {}
        cross_json = json.loads(cross_output.read_text(encoding="utf-8")) if cross_output.is_file() else {}
        checks = {
            "validator_exit_zero": validator.returncode == 0,
            "validator_pass": validator_json.get("status") == "pass",
            "assembler_exit_zero": assembler.returncode == 0,
            "accepted_anchor_seven_points": anchor_json.get("accepted") is True and anchor_json.get("params", {}).get("omega_points") == 7,
            "anchor_manifest_matches_canonical": (anchor / "manifest.json").is_file() and sha256(anchor / "manifest.json") == sha256(CANONICAL_ANCHOR / "manifest.json"),
            "anchor_spectrum_matches_canonical": (anchor / "spectrum.csv").is_file() and sha256(anchor / "spectrum.csv") == sha256(CANONICAL_ANCHOR / "spectrum.csv"),
            "analyzer_expected_incomplete_exit": analyzer.returncode == 2,
            "cross_tag_not_evaluable": cross_json.get("tag") == "NotEvaluable",
            "main_peak_not_bracketed": cross_json.get("coverage", {}).get("main_peak_bracketed_by_cv_grid") is False,
            "major_window_not_covered": cross_json.get("coverage", {}).get("major_weight_window_covered_by_cv_grid") is False,
            "cross_output_matches_canonical": cross_output.is_file() and sha256(cross_output) == sha256(CANONICAL_CROSS),
        }
        payload = {
            "schema_version": 1,
            "status": "pass" if all(checks.values()) else "fail",
            "checks": checks,
            "returncodes": {"validator": validator.returncode, "assembler": assembler.returncode, "analyzer": analyzer.returncode},
            "interpretation": "analyzer 返回 2 表示 incomplete；JSON 必须为 NotEvaluable，不能视为程序崩溃。",
            "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True, "server_used": False},
        }
        OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": payload["status"], "passed": sum(checks.values()), "total": len(checks)}, ensure_ascii=False))
        if payload["status"] != "pass":
            raise SystemExit(1)
    finally:
        if work.is_dir():
            shutil.rmtree(work)


if __name__ == "__main__":
    main()
