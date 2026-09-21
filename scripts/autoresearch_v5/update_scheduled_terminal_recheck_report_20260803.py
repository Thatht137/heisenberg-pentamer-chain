"""把定时终态复核追加到研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SNAPSHOT = ROOT / "results/research_progress/scheduled_terminal_recheck_20260803_1857.json"
TITLE = "2026-08-03 18:57 服务器终态复核"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    anchor = snapshot["anchor"]
    tebd = snapshot["tebd"]
    resources = snapshot["resources"]
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "按定时任务做只读 SSH 复核；实际服务器时间 18:57，不启动第二个 Julia",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "warn",
                    "label": "anchor 已闭环，TEBD coarse 已结束但未准入",
                    "why": "L=80 anchor 本地复验仍为 8/8 PASS；TEBD coarse 的远端 12/12 checksum 通过，但唯一失败项 raw_spectrum_nonnegative 阻止 refined 启动。",
                },
                {
                    "kind": "table",
                    "columns": ["对象", "只读终态", "判断"],
                    "rows": [
                        ["L=80 CV anchor", f"success / accepted；residual={anchor['max_cv_relative_residual']:.3e}", "独立回传、checksum、validator 已闭环"],
                        ["本地独立复验", anchor["local_validator"], "8 项门槛再次全部通过"],
                        ["TEBD coarse", "1200/1200；Fourier 81/81；accepted=false", "执行完整，物理验收未通过"],
                        ["唯一失败项", f"raw_spectrum_nonnegative；min={tebd['raw_spectrum_min']:.6f}", "refined 未启动，动态准入保持关闭"],
                        ["服务器进程", "Julia=0；supervisor=0", "当前无运行中任务，ETA 不适用"],
                    ],
                    "widths": ["24%", "38%", "38%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["远端完整性", "round24 coarse checksums 12/12 PASS"],
                        ["状态文件辨析", "overall_status.json 的 running/coarse 是旧 set -e 缺陷留下的 stale 状态；manifest 是真实终态"],
                        ["资源快照", f"load={resources['load_average_1m']:.2f}/{resources['load_average_5m']:.2f}/{resources['load_average_15m']:.2f}；可用内存 {resources['memory_available_gib']} GiB；/home 可用 {resources['home_available_gib']} GiB"],
                        ["研究范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                    ],
                },
                {
                    "kind": "code",
                    "title": "本次证据",
                    "text": "results/research_progress/scheduled_terminal_recheck_20260803_1857.json\nresults/research_progress/l80_anchor_validator_recheck_20260803_1857.json\n远端：round24_tebd_eta01_crosscheck/cell-alpha023-dt025-t30/{manifest.json,checksums.sha256}",
                },
                {
                    "kind": "note",
                    "label": "下一计算门",
                    "style": "pending",
                    "text": "先实现 O_q|GS> 的严格 q=pi 自相关并做 L=10/20 smoke；通过符号、归一化和 ED/CV 对照后，才预览新的 L=40 远端任务。任何新 Julia 都需另行确认。",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 18:57 CST"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "anchor": anchor["local_validator"], "tebd": tebd["accepted"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
