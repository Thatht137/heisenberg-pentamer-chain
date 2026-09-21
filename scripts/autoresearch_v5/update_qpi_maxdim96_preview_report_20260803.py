"""记录 maxdim=96 服务器任务的只读预览。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
PREVIEW = ROOT / "results/research_progress/qpi_tebd_maxdim96_submission_preview_20260803.json"
TITLE = "2026-08-03 21:17 maxdim=96 严格 q=pi 服务器预览"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    preview = json.loads(PREVIEW.read_text(encoding="utf-8"))
    params = preview["parameters"]
    resources = preview["resources"]
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "只读冲突检查与本地 dry-run 已完成；不上传、不启动",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "warn",
                    "label": "D=96 预览就绪，等待独立提交确认",
                    "why": "它是唯一能实际触及基准 tebd_actual_maxdim=117 的候选第二档；远端目标目录和上传脚本路径均不存在。",
                },
                {
                    "kind": "table",
                    "columns": ["锁定项", "值", "保护"],
                    "rows": [
                        ["实例", "alpha=0.23，beta=0.5，L=40，q=pi，OBC，Sz=0", "仅正区；排除负 alpha 与 Fig. 9"],
                        ["演化", f"dt={params['tstep']}，tmax={params['tmax']}，eta={params['eta']}，二阶 Trotter", "与 refined 完全相同，仅 maxdim 改为 96"],
                        ["截断", f"dmrg_maxdim=tebd_maxdim={params['tebd_maxdim']}", "实际上限必须触及；结果需峰位 <=0.05、权重 <=5%"],
                        ["资源", f"threads={params['threads']}，nice={resources['nice']}，checkpoint={resources['checkpoint_interval_steps']} steps", "Julia 包离线；禁止已有 Julia 并拒绝覆盖"],
                        ["ETA", "约 8–18 min；保守上限 30 min", "依据 L=40 refined 实测 664.6 s 和活跃 cap 缩减"],
                    ],
                    "widths": ["18%", "48%", "34%"],
                },
                {
                    "kind": "code",
                    "title": "待确认的两步远端动作",
                    "text": preview["commands"]["upload"] + "\n" + preview["commands"]["execute"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["预览证据", "results/research_progress/qpi_tebd_maxdim96_submission_preview_20260803.json"],
                        ["本地脚本哈希", preview["script"]["sha256"]],
                        ["目标冲突", "run_root_exists=false；remote_script_exists=false"],
                        ["提交授权", "需要用户明确确认；当前仍 remote_write=false"],
                    ],
                },
                {
                    "kind": "note",
                    "label": "确认后顺序",
                    "style": "pending",
                    "text": "收到明确确认后才上传 1 个 supervisor 脚本并启动单个 Julia；完成后做远端只读状态、独立回传 checksum、--maxdim-dir 分析和 HTML 更新。",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 21:17 CST"
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"section": TITLE, "action": "preview_only"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
