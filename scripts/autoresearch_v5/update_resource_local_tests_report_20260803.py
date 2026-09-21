"""把资源占用与本机回归结果追加到离线研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
SNAPSHOT = ROOT / "results" / "research_progress" / "server_resource_snapshot_20260803_1230.json"
TITLE = "2026-08-03 12:30 资源占用与本机回归复核"


def build_section(snapshot: dict[str, object]) -> dict[str, object]:
    resources = snapshot["resources"]
    anchor = snapshot["anchor"]
    return {
        "title": TITLE,
        "note": "一次性只读服务器检查；未启动新的远端 Julia",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "服务器有空闲核，但暂不并行 Julia",
                "why": "80 核中 anchor 约占 16.2 核、可用内存约 240 GiB；supervisor 会在 anchor 结束时检测其他 Julia 并放弃自动 TEBD，因此保留空闲核给后续接续。",
            },
            {
                "kind": "table",
                "columns": ["指标", "本轮值", "判断"],
                "rows": [
                    ["CPU", f"{anchor['cpu_percent']}%（约 16.2 核）/ 80 核", "约 64 核空闲，但不用于新 Julia"],
                    ["内存", f"{resources['memory_available_gib']} GiB 可用 / {resources['memory_total_gib']} GiB", "不是瓶颈"],
                    ["负载", "16.08 / 14.07 / 15.62", "与 anchor 的 16 核计算一致"],
                    ["anchor", f"PID {anchor['pid']}，运行 {anchor['elapsed']}，points=0，stderr 为空", "继续等待终态"],
                    ["TEBD supervisor", "waiting_for_anchor；生产文件尚不存在", "保留自动接续"],
                    ["磁盘", f"/home 可用 {resources['home_free_gib']} GiB（20% 空间）", "留意空间，不新增大批次"],
                ],
                "widths": ["22%", "43%", "35%"],
            },
            {
                "kind": "verdict",
                "status": "good",
                "label": "本机逻辑回归通过 21/21",
                "why": "progress 2/2、resumable wrapper 5/5、oracle analyzer 2/2、positive static pipeline 10/10、TEBD crosscheck analyzer 2/2；compileall 无错误。",
            },
            {
                "kind": "kv",
                "pairs": [
                    ["本轮执行", "未提交新的服务器计算；完成本机测试和只读资源诊断"],
                    ["可安全并行", "本机 Python 测试、离线分析、报告渲染；不启动额外 Julia"],
                    ["主任务", "anchor 结束后由 supervisor 自动接 TEBD；终态后回传 manifest/checksum/CV residual"],
                    ["范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                ],
            },
            {
                "kind": "code",
                "title": "证据文件",
                "text": "results/research_progress/server_resource_snapshot_20260803_1230.json\nscripts/autoresearch_v5/test_progress.py\nscripts/autoresearch_v5/test_resumable_wrapper.py\nscripts/autoresearch_v5/test_resume_oracle_analyzer.py\nscripts/autoresearch_v5/test_positive_static_pipeline.py",
            },
            {
                "kind": "note",
                "label": "下一检查条件",
                "style": "pending",
                "text": "不按固定短间隔轮询；等 anchor 进程消失、stderr/进度状态变化或 supervisor 日志出现 TEBD 启动，再进行一次状态检查。",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(0, build_section(snapshot))
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
