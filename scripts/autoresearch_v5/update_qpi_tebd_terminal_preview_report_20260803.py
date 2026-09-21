"""把严格 q=pi 远端终态与回传预览写入报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
STATUS = ROOT / "results/research_progress/qpi_tebd_remote_status_20260803_2008.json"
PREVIEW = ROOT / "results/research_progress/qpi_tebd_fetch_preview_20260803_2010.json"
TITLE = "2026-08-03 20:11 严格 q=pi L=40 远端终态"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    status = json.loads(STATUS.read_text(encoding="utf-8"))
    preview = json.loads(PREVIEW.read_text(encoding="utf-8"))
    coarse = status["coarse"]["manifest"]
    refined = status["refined"]["manifest"]
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "只读远端终态与 checksum 预览；尚未回传，因此不作独立频谱比较",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "good",
                    "label": "coarse 与 refined 均完成并通过单 run 验收",
                    "why": "overall_status=success/finished；两档 accepted=true、returncode=0，远端已无 Julia 进程，refined 没有越过 coarse 门提前启动。",
                },
                {
                    "kind": "table",
                    "columns": ["远端诊断", "coarse dt=0.025", "refined dt=0.0125", "当前判断"],
                    "rows": [
                        ["wall time", f"{coarse['diagnostics']['wall_seconds']:.2f} s", f"{refined['diagnostics']['wall_seconds']:.2f} s", "顺序总计约 23.1 min"],
                        ["TEBD actual maxdim", f"{coarse['diagnostics']['tebd_actual_maxdim']:.0f}", f"{refined['diagnostics']['tebd_actual_maxdim']:.0f}", "远低于配置上限 320"],
                        ["variance/L", f"{coarse['diagnostics']['variance_per_site']:.3e}", f"{refined['diagnostics']['variance_per_site']:.3e}", "均低于 1e-8"],
                        ["relative norm drift", f"{coarse['diagnostics']['relative_norm_drift']:.3e}", f"{refined['diagnostics']['relative_norm_drift']:.3e}", "保留为时域诊断"],
                        ["min S(pi,omega)", f"{coarse['diagnostics']['spectrum_min']:.6f}", f"{refined['diagnostics']['spectrum_min']:.6f}", "两档原始谱均为正"],
                        ["max S(pi,omega)", f"{coarse['diagnostics']['spectrum_max']:.6f}", f"{refined['diagnostics']['spectrum_max']:.6f}", "需回传后定位峰位"],
                    ],
                    "widths": ["24%", "24%", "24%", "28%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["coarse 完成", "2026-08-03 19:45:39 CST；1200/1200 steps"],
                        ["refined 完成", "2026-08-03 19:59:43 CST；2400/2400 steps"],
                        ["资源终态", f"Julia 进程数={status['julia_process_count']}；checkpoint 成功后均已清理"],
                        ["范围", "alpha=0.23、beta=0.5、L=40、q=pi；负 alpha 与 Fig. 9 排除"],
                    ],
                },
                {
                    "kind": "verdict",
                    "status": "good",
                    "label": "远端 checksum 与非覆盖式回传预览通过",
                    "why": f"两个 cell 共验证 {sum(cell['checked_files'] for cell in preview['cells'].values())} 个文件哈希；run 共 {preview['file_count']} 个文件、{preview['total_bytes']:,} bytes，本地目标不存在。",
                },
                {
                    "kind": "table",
                    "columns": ["对象", "远端验证", "本地状态"],
                    "rows": [
                        ["coarse", f"11/11 checksum；manifest {preview['cells']['cell-alpha023-qpi-dt0025-t30']['manifest_sha256'][:12]}...", "未下载"],
                        ["refined", f"11/11 checksum；manifest {preview['cells']['cell-alpha023-qpi-dt00125-t30']['manifest_sha256'][:12]}...", "未下载"],
                        ["目标目录", preview["run_root"], f"{preview['local_destination']}；不存在"],
                    ],
                    "widths": ["20%", "47%", "33%"],
                },
                {
                    "kind": "code",
                    "title": "确认后执行的非覆盖式命令预览",
                    "text": preview["fetch_command_preview"],
                },
                {
                    "kind": "note",
                    "label": "回传后的固定顺序",
                    "style": "pending",
                    "text": "明确确认下载后：非覆盖式回传 -> 本地逐文件 checksum -> analyze_qpi_tebd_production.py（tmax=25/30）-> 接入四点 CV anchor 集 -> Python 论文图与 HTML。D=320 实际只到 117，第二档 maxdim 的参数在独立分析后再定，不现在启动新 Julia。",
                },
                {
                    "kind": "code",
                    "title": "状态证据",
                    "text": "results/research_progress/qpi_tebd_remote_status_20260803_2008.json\nresults/research_progress/qpi_tebd_fetch_preview_20260803_2010.json\nscripts/autoresearch_v5/check_qpi_tebd_remote_status.py\nscripts/autoresearch_v5/preview_qpi_tebd_fetch.py",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 20:11 CST"
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"section": TITLE, "remote_status": preview["remote_checksum_status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
