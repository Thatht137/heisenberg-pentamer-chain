#!/usr/bin/env python3
"""验收 round43 并生成 bounded/production 分流结果。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = (ROOT / "results").resolve()
VALIDATOR = ROOT / "scripts/autoresearch_v5/validate_cv_run.py"
ASSEMBLER = ROOT / "scripts/autoresearch_v5/assemble_qpi_cv_anchors.py"
ANALYZER = ROOT / "scripts/autoresearch_v5/analyze_cv_tebd_crosscheck.py"
EXPECTED_ROUND43_OMEGAS = [0.0, 0.05, 0.10, 0.15, 0.20]
DEFAULT_BASE_RUNS = [
    "results/autoresearch_v5_20260802/round21_cv_triplet_warmstart/cell-0002-L40-qpi-w025-w035",
    "results/autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804/cell-l40-qpi-high-055",
    "results/autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804/cell-l40-qpi-high-100",
    "results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150",
]
DEFAULT_TEBD = (
    "results/autoresearch_v5_20260803/round26_qpi_tebd_production/"
    "cell-alpha023-qpi-dt00125-t30"
)


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


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_round43_omegas(run: Path) -> list[float]:
    with (run / "spectrum.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    omegas = sorted(float(row["omega"]) for row in rows)
    if len(omegas) != len(EXPECTED_ROUND43_OMEGAS) or any(
        abs(left - right) > 1e-12
        for left, right in zip(omegas, EXPECTED_ROUND43_OMEGAS)
    ):
        raise ValueError(f"round43 频率网格不完整: {omegas}")
    residuals = [float(row["relative_residual"]) for row in rows]
    if max(residuals) > 1e-5:
        raise ValueError(f"round43 residual 超门: {residuals}")
    return omegas


def classify_crosscheck(result: dict[str, object]) -> tuple[str, bool, int]:
    status, tag = result.get("status"), result.get("tag")
    if status == "pass" and tag == "Agreement":
        return "production_ready", True, 0
    if status == "incomplete" and tag == "NotEvaluable":
        return "bounded", False, 2
    return "bounded_disagreement", False, 1


def run(command: list[str], accepted: set[int] = {0}) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode not in accepted:
        raise RuntimeError(
            f"命令失败 exit={completed.returncode}: {' '.join(command)}\n{completed.stderr}"
        )
    return completed


def write_checksums(output: Path) -> None:
    files = sorted(
        path for path in output.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    )
    (output / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.relative_to(output).as_posix()}\n" for path in files),
        encoding="utf-8",
    )


def write_summary(output: Path, payload: dict[str, object]) -> None:
    payload["next_figure_command"] = (
        ".venv\\Scripts\\python.exe "
        "scripts\\autoresearch_v5\\plot_fig8_round43_branch.py "
        f"--handoff-root {output.relative_to(ROOT)} "
        "--output-base figures\\round43_fig8_final_20260806"
    )
    (output / "handoff_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_checksums(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round43-run", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--tebd-dir", default=DEFAULT_TEBD)
    parser.add_argument("--base-run-dir", action="append")
    parser.add_argument("--peak-budget", type=float, default=0.1)
    parser.add_argument("--weight-budget", type=float, default=0.15)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    round43 = under_results(ROOT / args.round43_run)
    output = under_results(ROOT / args.output_root)
    tebd = under_results(ROOT / args.tebd_dir)
    base_names = args.base_run_dir or DEFAULT_BASE_RUNS
    base_runs = [under_results(ROOT / value) for value in base_names]
    plan = {
        "round43": str(round43),
        "base_runs": [str(path) for path in base_runs],
        "tebd": str(tebd),
        "accepted_output": str(output / "accepted11"),
        "crosscheck_output": str(output / "cross_method/cross-method-check.json"),
        "expected_round43_omegas": EXPECTED_ROUND43_OMEGAS,
        "scope": {"negative_alpha_excluded": True, "figure_9_excluded": True},
    }
    if args.plan_only:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    if output.exists():
        raise SystemExit(f"输出目录已存在，拒绝覆盖: {output}")
    output.mkdir(parents=True)

    validator = output / "round43_validator.json"
    validated = run(
        [
            sys.executable,
            str(VALIDATOR),
            "--run-dir",
            str(round43),
            "--output",
            str(validator),
        ],
        accepted={0, 1},
    )
    validator_result = read_json(validator)
    if validated.returncode != 0 or validator_result.get("status") != "pass":
        summary = {
            "schema_version": 1,
            "status": "bounded",
            "production_ready": False,
            "stage": "round43_validator",
            "tag": "NotEvaluable",
            "plan": plan,
            "validator": validator_result,
            "reason": "round43 未通过独立 validator；禁止 accepted-only 组装",
        }
        write_summary(output, summary)
        print(json.dumps(summary, ensure_ascii=False))
        raise SystemExit(2)

    try:
        read_round43_omegas(round43)
    except ValueError as error:
        summary = {
            "schema_version": 1,
            "status": "bounded",
            "production_ready": False,
            "stage": "round43_grid",
            "tag": "NotEvaluable",
            "plan": plan,
            "reason": str(error),
        }
        write_summary(output, summary)
        print(json.dumps(summary, ensure_ascii=False))
        raise SystemExit(2) from error

    accepted = output / "accepted11"
    assemble_command = [sys.executable, str(ASSEMBLER)]
    for run_dir in [*base_runs, round43]:
        assemble_command.extend(["--run-dir", str(run_dir)])
    assemble_command.extend(["--output-dir", str(accepted)])
    run(assemble_command)

    cross_output = output / "cross_method/cross-method-check.json"
    analyzed = run(
        [
            sys.executable,
            str(ANALYZER),
            "--cv-dir",
            str(accepted),
            "--tebd-dir",
            str(tebd),
            "--output",
            str(cross_output),
            "--peak-budget",
            str(args.peak_budget),
            "--weight-budget",
            str(args.weight_budget),
        ],
        accepted={0, 1, 2},
    )
    cross = read_json(cross_output)
    status, production_ready, exit_code = classify_crosscheck(cross)
    if analyzed.returncode != exit_code:
        raise RuntimeError(
            f"分析器退出码与标签不一致: exit={analyzed.returncode}, expected={exit_code}"
        )
    summary = {
        "schema_version": 1,
        "status": status,
        "production_ready": production_ready,
        "stage": "cross_method",
        "tag": cross.get("tag"),
        "plan": plan,
        "accepted_points": read_json(accepted / "manifest.json").get("params", {}).get("omega_points"),
        "coverage": cross.get("coverage"),
        "checks": cross.get("checks"),
        "reason": (
            "覆盖门与 peak/weight 门全部通过"
            if production_ready
            else "保留 bounded 版本，不提升动态论断"
        ),
    }
    write_summary(output, summary)
    print(json.dumps(summary, ensure_ascii=False))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
