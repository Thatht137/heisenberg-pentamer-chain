"""追加 round41 retry 健康快照并重渲染报告。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
RENDERER = Path(r"C:/Users/hh250/.codex/skills/report/render_report.py")
TITLE = "2026-08-05 round41 adaptive retry 20:33 健康检查"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    section = {
        "title": TITLE,
        "note": "一次性只读检查；不启动第二个 Julia，不改变 residual 验收门槛。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "retry 仍在正常 linsolve",
                "why": "PID 401894 状态 RNl，CPU 136%，RSS 1.54 GiB，stderr 为空，progress heartbeat 已更新。",
            },
            {
                "kind": "table",
                "columns": ["项目", "值", "解释"],
                "rows": [
                    ["elapsed", "24:04", "尚未到条件 ETA"],
                    ["频点进度", "0/1", "omega=0.05 仍在求解"],
                    ["资源", "CPU 136%；RSS 1,537,880 KiB", "进程未宕机"],
                    ["stderr", "0 B", "未见程序错误"],
                ],
                "widths": ["25%", "32%", "43%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["下一次检查", "2026-08-05 21:10 CST"],
                    ["验收顺序", "远端 checksum → 非覆盖回传 → 本地 checksum → validate_cv_run.py"],
                    ["范围", "0<=alpha,beta<=1；排除负 alpha 和 Fig.9"],
                ],
            },
        ],
    }
    report["sections"] = [s for s in report["sections"] if s.get("title") != TITLE]
    report["sections"].insert(2, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-05 · LOW005 RETRY HEALTHY"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, "-X", "utf8", str(RENDERER), str(REPORT.parent)], check=True)
    print(json.dumps({"status": "pass", "title": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
