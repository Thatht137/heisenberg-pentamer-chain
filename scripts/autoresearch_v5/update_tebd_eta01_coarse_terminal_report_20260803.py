"""把 TEBD coarse 终态与影响写入研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SNAPSHOT = ROOT / "results/research_progress/tebd_eta01_coarse_terminal_20260803_1756.json"
TITLE = "2026-08-03 17:56 TEBD eta=0.1 coarse 终态"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    terminal = snapshot["terminal_observation"]
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "TEBD 与 Fourier 正常结束，但单 run 验收未通过；refined 未启动",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "bad",
                    "label": "计算完成，动态准入失败",
                    "why": "coarse 完成 1200/1200 TEBD 步和 81/81 Fourier 动量点，两个程序返回码均为 0；但 accepted=false、wrapper returncode=1，因此不能启动 dt/2 refined。",
                },
                {
                    "kind": "table",
                    "columns": ["对象", "终态", "影响"],
                    "rows": [
                        ["TEBD 演化", "1200/1200；911.5 s；returncode=0", "原始时域计算完整"],
                        ["Fourier", "81/81；422.4 s；returncode=0", "后处理完整"],
                        ["单 run 验收", "accepted=false；returncode=1", "禁止进入 refined"],
                        ["服务器", "Julia 进程 0", "当前无计算占用"],
                        ["交付就绪", "保持 7/9", "L=80 anchor、静态和 CV 证据不受影响"],
                    ],
                    "widths": ["24%", "38%", "38%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["失败影响", "只阻断 TEBD dt/dt2 与最终动态准入，不推翻正区相图、ED、有效理论、L=40 CV 或 L=80 anchor"],
                        ["supervisor 问题", "set -e 在 coarse 返回 1 时提前退出，overall_status.json 因而错误保留 running/coarse；本地脚本已修复终态写入"],
                        ["当前证据边界", "远端 manifest 明细读取被权限审查拒绝，暂不猜测具体失败检查"],
                        ["范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                    ],
                },
                {
                    "kind": "code",
                    "title": "证据与修复",
                    "text": "results/research_progress/tebd_eta01_coarse_terminal_20260803_1756.json\nscripts/autoresearch_v5/run_tebd_eta01_crosscheck_remote.sh\nscripts/autoresearch_v5/analyze_cv_tebd_crosscheck.py",
                },
                {
                    "kind": "note",
                    "label": "下一步需要许可",
                    "style": "pending",
                    "text": "只读获取远端 manifest、目录大小和校验日志，确认失败项；随后预览并回传 coarse 终态目录到独立本地目录。未获许可前不重跑、不启动第二个 Julia。",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 17:56 CST"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "accepted": terminal["accepted"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
