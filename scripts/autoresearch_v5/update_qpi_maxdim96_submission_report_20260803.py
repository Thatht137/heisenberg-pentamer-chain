"""把 maxdim=96 提交与启动证据写入研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
EVIDENCE = ROOT / "results/research_progress/qpi_tebd_maxdim96_submission_20260803.json"
TITLE = "2026-08-03 21:37 maxdim=96 严格 q=pi 已启动"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    launch = evidence["launch"]
    params = evidence["parameters"]
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "已按用户确认上传并启动；当前只保留一个 Julia 生产进程。",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "warn",
                    "label": "作业运行中，尚无终态验收",
                    "why": "supervisor、Python 驱动和唯一 Julia 均存活；当前只能确认启动健康，不能提前宣称谱结果通过。",
                },
                {
                    "kind": "table",
                    "columns": ["项目", "当前证据", "验收约束"],
                    "rows": [
                        ["实例", "alpha=0.23，beta=0.5，L=40，q=pi，OBC，Sz=0", "仅 0<=alpha,beta<=1；排除负 alpha 与 Fig. 9"],
                        ["演化", f"dt={params['tstep']}，tmax={params['tmax']}，eta={params['eta']}", "与 refined 基准一致"],
                        ["截断", f"DMRG/TEBD maxdim={params['tebd_maxdim']}，threads={params['threads']}", "与 maxdim=320 基准比较峰位和积分权重"],
                        ["远端进程", f"supervisor={launch['supervisor_pid']}；driver={launch['driver_pid']}；Julia={launch['julia_pid']}", "Julia 数量保持 1，禁止并行冲突"],
                        ["ETA", "典型 8–18 分钟；保守上限 30 分钟", "终态后才下载和分析"],
                    ],
                    "widths": ["18%", "48%", "34%"],
                },
                {
                    "kind": "code",
                    "title": "启动命令与运行目录",
                    "text": "nohup bash /home/wangjieren/code/1x5_Heisenberg_Pentamer/scripts/run_qpi_tebd_maxdim96_remote_20260803.sh ...\n" + evidence["run_root"] + "\n" + evidence["cell_id"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["提交证据", "results/research_progress/qpi_tebd_maxdim96_submission_20260803.json"],
                        ["脚本哈希", evidence["local_script_sha256"]],
                        ["上传", "1 个脚本；成功；非覆盖式"],
                        ["启动状态", f"{launch['remote_status']['status']} / {launch['remote_status']['phase']}"],
                        ["检查时间", launch["checked_at"]],
                    ],
                },
                {
                    "kind": "note",
                    "label": "下一步",
                    "style": "pending",
                    "text": "不做短间隔轮询。等待 overall_status.json 进入 success/failed；成功后回传到独立目录，做 checksum、manifest、maxdim 门槛分析，并把真实曲线追加到 HTML。",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 21:37 CST"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "status": launch["remote_status"]["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
