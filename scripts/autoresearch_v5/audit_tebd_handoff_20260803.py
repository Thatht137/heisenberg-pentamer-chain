#!/usr/bin/env python3
"""审计 anchor 释放后的 TEBD 顺序交接器。"""

from __future__ import annotations

import hashlib
import json
import py_compile
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
OUTPUT = ROOT / "results/research_progress/tebd_handoff_audit_20260803.json"
SUPERVISOR = ROOT / "scripts/autoresearch_v5/wait_then_run_tebd_remote.sh"
TEBD = ROOT / "scripts/autoresearch_v5/run_tebd_production.py"
ANALYZER = ROOT / "scripts/autoresearch_v5/analyze_tebd_crosscheck.py"
TITLE = "TEBD 顺序交接器本地复核（2026-08-03）"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    shell = subprocess.run(["bash", "-n", str(SUPERVISOR)], capture_output=True, text=True, check=False)
    supervisor = SUPERVISOR.read_text(encoding="utf-8")
    token_checks = {
        "anchor_path": "round22_cv_l80_anchor" in supervisor,
        "tebd_run": "round23_tebd_crosscheck" in supervisor,
        "no_parallel_julia_guard": "another Julia task is active; aborting" in supervisor,
        "tstep_0025": "--tstep 0.025" in supervisor,
        "n_steps_600": "--n-steps 600" in supervisor,
        "threads_8": "--threads 8" in supervisor,
        "manifest_gate": "--expected-manifest-sha256" in supervisor,
    }
    compile_errors: list[str] = []
    for path in (TEBD, ANALYZER):
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as error:
            compile_errors.append(str(error))
    audit = {
        "schema_version": 1,
        "created_at": "2026-08-03",
        "status": "pass" if shell.returncode == 0 and all(token_checks.values()) and not compile_errors else "fail",
        "shell_syntax": {"returncode": shell.returncode, "stderr": shell.stderr.strip()},
        "token_checks": token_checks,
        "python_compile": {"files": [str(TEBD.relative_to(ROOT)), str(ANALYZER.relative_to(ROOT))], "errors": compile_errors},
        "script_sha256": {str(path.relative_to(ROOT)): digest(path) for path in (SUPERVISOR, TEBD, ANALYZER)},
        "execution": "handoff only; no remote computation started",
        "scope": {"negative_alpha_included": False, "fig9_included": False},
    }
    OUTPUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只检查交接配置和本地语法；不启动 TEBD",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good" if audit["status"] == "pass" else "bad",
                "label": "TEBD 交接器可在 anchor 释放后接续" if audit["status"] == "pass" else "TEBD 交接器审计失败",
                "why": "shell 语法、Python 编译和 7 项参数/保护条件均通过；当前仍保持不绕过 supervisor 的规则。",
            },
            {
                "kind": "table",
                "columns": ["检查", "结果", "意义"],
                "rows": [
                    ["shell 语法", "通过" if shell.returncode == 0 else "失败", "避免远端 supervisor 启动即退出"],
                    ["Python 编译", "2/2 通过" if not compile_errors else f"失败 {len(compile_errors)}", "TEBD 入口和交叉验收器可加载"],
                    ["配置/保护条件", f"{sum(token_checks.values())}/{len(token_checks)}", "anchor 路径、dt=0.025、600 steps、8 threads、Manifest 门和并行 Julia 保护一致"],
                ],
                "widths": ["25%", "25%", "50%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["交接脚本", "scripts/autoresearch_v5/wait_then_run_tebd_remote.sh"],
                    ["生产入口", "scripts/autoresearch_v5/run_tebd_production.py"],
                    ["下一步", "anchor 终态后回传并验收 CV；supervisor 再自动启动 TEBD"],
                    ["本轮执行", "只读/本地检查，没有远端启动"],
                ],
            },
            {
                "kind": "code",
                "title": "审计文件",
                "text": "results/research_progress/tebd_handoff_audit_20260803.json\nscripts/autoresearch_v5/audit_tebd_handoff_20260803.py",
            },
            {
                "kind": "note",
                "label": "动态准入边界",
                "style": "pending",
                "text": "交接器通过不等于 TEBD 已产生数据；仍需 raw spectrum、dt/dt2、时间窗、非负性和 CV/TEBD 峰位及权重门槛。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    index = next((i + 1 for i, item in enumerate(report["sections"]) if item["title"] == "TEBD 启动前哈希与配置复核"), len(report["sections"]))
    report["sections"].insert(index, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": audit["status"], "output": str(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
