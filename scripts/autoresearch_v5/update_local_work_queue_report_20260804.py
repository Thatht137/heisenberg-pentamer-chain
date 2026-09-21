"""登记服务器计算期间可并行推进的本地工作。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-04 服务器计算期间的本地并行工作队列"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    integrity_path = ROOT / "results/research_progress/local_integrity_audit_20260803.json"
    integrity = json.loads(integrity_path.read_text(encoding="utf-8")) if integrity_path.is_file() else {}
    asset_path = ROOT / "results/research_progress/figure_asset_pixel_qa_20260804.json"
    asset = json.loads(asset_path.read_text(encoding="utf-8")) if asset_path.is_file() else {}
    asset_count = asset.get("asset_count", "待审计")
    asset_failures = len(asset.get("failures", []))
    reference_count = integrity.get("report_references", {}).get("total", "待审计")
    checksum_manifests = integrity.get("checksums", {}).get("manifests", "待审计")
    checksum_entries = integrity.get("checksums", {}).get("entries_checked", "待审计")
    section = {
        "title": TITLE,
        "note": "不轮询服务器、不启动第二个 Julia；只安排本地可复核、可回退的工作。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "本地工作不停摆",
                "why": "图表资产、回归测试、报告引用和 checksum 审计均已完成；远端动态门仍保持原验收标准。",
            },
            {
                "kind": "table",
                "columns": ["任务", "当前状态", "下一动作"],
                "rows": [
                    ["图表资产 QA", f"已完成；{asset_count}/{asset_count} 通过（失败 {asset_failures}）", "保留 Fig.6--8 的 exploratory/pilot/constrained 标签"],
                    ["人工视觉抽查", "已完成；Fig.1--8 无空白或明显裁切", "Fig.1--5 可作静态证据；Fig.6--8 等动态门关闭后再升级"],
                    ["本地 Python 回归", "已完成；46/46 通过", "后续继续用项目 .venv 做离线 smoke 和绘图"],
                    ["报告与证据完整性", f"已完成；{reference_count} 引用、{checksum_manifests} 个 checksum 清单、{checksum_entries} 项通过", "每次回传后再做增量审计"],
                    ["静态数据分析与图注", "可立即进行", "整理 Fig.1--5 的可写结论、图注和数据来源"],
                    ["动态交叉验收", "等待服务器", "仅在 TEBD 和 CV 覆盖主峰/积分窗后升级图 6--8"],
                ],
                "widths": ["25%", "30%", "45%"],
            },
            {
                "kind": "list",
                "title": "当前安全的本地任务",
                "items": [
                    "继续做正区静态结果的误差摘要、有限尺寸趋势和图注一致性检查。",
                    "维护参考图一一对应的 panel/claim/provenance 矩阵，不改 paper/。",
                    "准备远端 cell 回传后的 checksum、validator 和 HTML 增量更新脚本。",
                    "对已有 raw TEBD/CV 数据做不改变结论等级的诊断图和表格。",
                ],
            },
            {
                "kind": "note",
                "label": "等待条件",
                "style": "pending",
                "text": "L=40 dt/dt2 与时间窗交叉门、CV/TEBD 主峰及低频权重交叉门尚未通过；因此 Fig.6--8 暂不标为 production。",
            },
        ],
    }
    report["sections"] = [entry for entry in report["sections"] if entry.get("title") != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · LOCAL PARALLEL WORK QUEUE"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": "recorded"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
