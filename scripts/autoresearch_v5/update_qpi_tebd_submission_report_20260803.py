"""把严格 q=pi L=40 提交状态写入报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SNAPSHOT = ROOT / "results/research_progress/qpi_tebd_submission_20260803_1938.json"
TITLE = "2026-08-03 19:38 严格 q=pi L=40 生产任务已启动"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    process = snapshot["processes"]
    current = snapshot["current"]
    resources = snapshot["resource_preflight"]
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "用户明确确认后执行；上传、哈希、资源和单 Julia 保护均通过",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "warn",
                    "label": "L=40 coarse 正在 DMRG，尚无物理终态",
                    "why": "严格 O_q|GS> 自相关生产任务已启动，supervisor 与唯一 Julia 均存活，progress.json 正常更新；当前只能确认执行健康，不能提前判断谱验收。",
                },
                {
                    "kind": "table",
                    "columns": ["对象", "启动状态", "保护条件"],
                    "rows": [
                        ["远端身份", "wangjieren@39.96.207.180:6000；c104-ysu", "账号与主机复核"],
                        ["coarse", "alpha=0.23、beta=0.5、L=40、dt=0.025、1200 steps", "当前 phase=dmrg"],
                        ["refined", "dt=0.0125、2400 steps", "仅 coarse accepted=true 后启动"],
                        ["进程", f"supervisor PID {process['supervisor_pid']}；Julia PID {process['julia_pid']}", "ps 明确显示 1 个 Julia；8 threads；nice=10"],
                        ["进度", f"{current['subphase']}；elapsed={current['elapsed_seconds']:.0f}s；progress 每 30 秒更新", "每 100 步 checkpoint"],
                    ],
                    "widths": ["24%", "44%", "32%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["上传完整性", "3 个新文件经独立 staging 上传；远端 SHA-256 与本地逐项一致；目标此前不存在"],
                        ["环境完整性", "Manifest、研究标准、progress.py、PentamerChain.jl、hamiltonian.jl 哈希匹配"],
                        ["资源快照", f"可用内存 {resources['memory_available_gib']} GiB；/home 可用 {resources['home_available_gib']} GiB；启动时无 Julia"],
                        ["运行根目录", "results/autoresearch_v5_20260803/round26_qpi_tebd_production"],
                        ["预计时长", "1.0-1.7 h；保守上限 2.5 h"],
                        ["范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                    ],
                },
                {
                    "kind": "code",
                    "title": "状态证据",
                    "text": "results/research_progress/qpi_tebd_submission_20260803_1938.json\n远端：round26_qpi_tebd_production/overall_status.json\n远端：cell-alpha023-qpi-dt0025-t30/progress.json\n远端：round26_qpi_tebd_production/supervisor.log",
                },
                {
                    "kind": "note",
                    "label": "下一检查",
                    "style": "pending",
                    "text": "不做短间隔轮询。等待 coarse 终态或至少一个有意义 checkpoint 事件；若 coarse 失败，refined 必须保持未启动。终态结果仍需远端 checksum、独立回传、本地 checksum 和 CV/TEBD 验收。",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 19:38 CST"
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "section": TITLE,
                "phase": current["phase"],
                "julia_pid": process["julia_pid"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
