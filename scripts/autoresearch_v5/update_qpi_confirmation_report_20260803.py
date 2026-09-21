"""记录严格 q=pi 顺序任务的确认与终态复核。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
STATUS = ROOT / "results/research_progress/qpi_tebd_remote_status_20260803_2030.json"
TITLE = "2026-08-03 20:26 严格 q=pi L=40 确认与去重复核"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    status = json.loads(STATUS.read_text(encoding="utf-8"))
    coarse = status["coarse"]["manifest"]
    refined = status["refined"]["manifest"]
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "用户已确认上传与启动；对应顺序任务已先行完成，因此不重复提交第二个 Julia",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "good",
                    "label": "上传、顺序执行与远端单-run 验收均已完成",
                    "why": "20:26 的只读复核保持 success/finished；coarse 与 refined 均 accepted=true，Julia 进程数为 0。",
                },
                {
                    "kind": "table",
                    "columns": ["顺序阶段", "参数", "终态", "耗时与诊断"],
                    "rows": [
                        [
                            "coarse",
                            "dt=0.025，tmax=30，1200 steps",
                            "accepted=true",
                            f"{coarse['diagnostics']['wall_seconds']:.2f} s；actual maxdim={coarse['diagnostics']['tebd_actual_maxdim']:.0f}",
                        ],
                        [
                            "refined",
                            "dt=0.0125，tmax=30，2400 steps",
                            "accepted=true",
                            f"{refined['diagnostics']['wall_seconds']:.2f} s；actual maxdim={refined['diagnostics']['tebd_actual_maxdim']:.0f}",
                        ],
                    ],
                    "widths": ["18%", "34%", "18%", "30%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["模型点", "alpha=0.23，beta=0.5，L=40，q=pi，eta=0.1"],
                        ["数值门槛", f"variance/L={coarse['diagnostics']['variance_per_site']:.3e}；两档 spectrum_min 均为正"],
                        ["资源终态", f"Julia process count={status['julia_process_count']}；supervisor exit status=0"],
                        ["范围约束", "仅 0<=alpha,beta<=1；负 alpha 与 Fig. 9 均排除"],
                        ["远端证据", "results/research_progress/qpi_tebd_remote_status_20260803_2030.json"],
                    ],
                },
                {
                    "kind": "note",
                    "label": "去重决定",
                    "style": "info",
                    "text": "不再次上传或启动同一 L=40 参数任务。重复运行不会增加独立误差轴，只会复制已有数据。",
                },
                {
                    "kind": "note",
                    "label": "下一授权门",
                    "style": "pending",
                    "text": "结果尚未回传到本地。按 cluster-jobs 规则，下载需要与上传/启动分开的明确确认；收到“确认下载”后才执行非覆盖式回传、checksum 和本地验收。",
                },
                {
                    "kind": "code",
                    "title": "本次修复",
                    "text": "scripts/autoresearch_v5/check_qpi_tebd_remote_status.py\n  默认 SSH 密钥改为 id_ed25519\n  Windows 子进程输出固定按 UTF-8 解码",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 20:26 CST"
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"section": TITLE, "status": "success"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
