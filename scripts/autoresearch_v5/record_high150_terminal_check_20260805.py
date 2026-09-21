#!/usr/bin/env python3
"""记录 high-150 终态只读检查。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results/research_progress"
REPORT = RUN / "report.json"
OUTPUT = RUN / "round31_high150_terminal_check_20260805_2053.json"
TITLE = "2026-08-05 high-150 终态只读检查 20:53"


def main() -> None:
    record = {
        "schema_version": 1,
        "checked_at": "2026-08-05T20:53:33+08:00",
        "mode": "read_only",
        "remote": {
            "host": "c104-ysu",
            "address": "39.96.207.180:6000",
            "cell": "results/autoresearch_v5_20260803/round31_qpi_cv_extension/cell-l40-qpi-high-150",
        },
        "process": {
            "historical_julia_pid": 324653,
            "present_at_check": False,
            "interpretation": "终态后进程已退出，非宕机。",
        },
        "terminal": {
            "status": "success",
            "accepted": True,
            "returncode": 0,
            "phase": "finished",
            "completed_points": 1,
            "total_points": 1,
            "elapsed_seconds": 77962.877,
            "started_at": "2026-08-04T07:07:28.311722+00:00",
            "finished_at": "2026-08-05T04:46:51.187878+00:00",
            "stderr_bytes": 0,
            "stdout_success_marker": "CV_DSF_CELL_SUCCESS",
        },
        "diagnostics": {
            "omega": 1.5,
            "max_cv_relative_residual": 5.540316362540025e-06,
            "variance_per_site": 2.611944438513092e-10,
            "max_dmrg_truncation": 9.99645287244195e-11,
            "max_solution_dim": 600,
            "resource_cpu_percent": 1607,
            "resource_wall_time": "21:39:22",
            "resource_max_rss_kib": 4131312,
            "resource_exit_status": 0,
        },
        "integrity": {
            "remote_sha256sum_c": "pass",
            "verified_files": [
                "manifest.json",
                "metrics.csv",
                "progress.json",
                "resource.log",
                "spectrum.csv",
                "spectrum.jld2",
                "status.json",
                "stderr.log",
                "stdout.log",
                "sweep_history.csv",
            ],
        },
        "server_concurrency": {
            "high150_julia_running": False,
            "observed_retry_julia_pid": 401894,
            "observed_retry_threads": 4,
            "decision": "不启动第二个 Julia；仅保留已存在的 low-005 retry。",
        },
        "scope": {
            "alpha_beta": "[0,1]",
            "negative_alpha_excluded": True,
            "fig9_excluded": True,
        },
        "raw_command_evidence": {
            "process_probe": "pgrep 未返回 high-150/cv_dsf_cell 匹配进程；julia 列表仅见 retry-005 PID 401894。",
            "status_json": "status=success; accepted=true; returncode=0",
            "progress_json": "phase=finished; completed_points=1/1; elapsed_seconds=77962.877",
            "stderr": "0 bytes",
            "checksum": "sha256sum -c 对 10 个文件全部成功",
        },
    }
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "一次性远端只读终态检查；未启动任务、未下载依赖、未覆盖任何结果。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "high-150 已自然终态且远端完整性通过",
                "why": "历史 Julia PID 324653 已退出；status=success、accepted=true、returncode=0，progress=finished 1/1，stderr=0 B。",
            },
            {
                "kind": "table",
                "columns": ["检查项", "原始事实", "判断"],
                "rows": [
                    ["PID / phase", "PID 324653 已不存在；finished", "正常终态，不是宕机"],
                    ["elapsed / 资源", "77,962.877 s；CPU 1607%；max RSS 4,131,312 KiB", "资源日志 exit status=0"],
                    ["频点", "omega=1.50；1/1", "relative residual=5.540316e-6"],
                    ["stderr / 输出", "0 B；CV_DSF_CELL_SUCCESS", "无程序报错"],
                    ["远端 checksum", "10/10 文件 sha256sum -c 成功", "可进入后续非覆盖回传"],
                    ["并发边界", "仅见 retry-005 Julia PID 401894（4 threads）", "未启动第二个 Julia"],
                ],
                "widths": ["21%", "50%", "29%"],
            },
            {
                "kind": "note",
                "label": "后续交接",
                "style": "pending",
                "text": "high-150 的远端终态和 checksum 已闭合。遵循既定顺序：非覆盖回传、本地 checksum、validate_cv_run.py；retry-005 仍运行期间不再启动新的 Julia。",
            },
            {
                "kind": "kv",
                "pairs": [
                    ["终态快照", "results/research_progress/round31_high150_terminal_check_20260805_2053.json"],
                    ["远端 cell", record["remote"]["cell"]],
                    ["范围", "0<=alpha,beta<=1；排除负 alpha 与 Fig.9"],
                ],
            },
        ],
    }
    report["sections"] = [section] + [item for item in report["sections"] if item.get("title") != TITLE]
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-05 · HIGH150 TERMINAL PASS · LOW005 RETRY RUNNING"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "recorded", "output": str(OUTPUT), "title": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
