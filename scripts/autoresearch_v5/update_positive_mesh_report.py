#!/usr/bin/env python3
"""把扩展正区网格验收结果写入长期 HTML 报告源。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
RUN = ROOT / "results" / "autoresearch_v5_20260802" / "round19_phase_diagram_positive_mesh"
OBS = RUN / "phase-diagram" / "observations_merged.json"
GUARD = RUN / "phase-diagram" / "positive_phase_guard.json"
STATUS = RUN / "run_status.json"
TITLE = "正区扩展相图网格验收"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_section() -> dict[str, object]:
    observations = load(OBS)
    guard = load(GUARD)
    status = load(STATUS)
    records = observations["records"]
    max_error_record = max(records, key=lambda record: float(record["error"]))
    max_error_artifact = Path(str(max_error_record["artifact"]))
    max_error_label = f"{max_error_artifact.parent.name}/{max_error_artifact.name}"
    grouped: dict[float, list[dict[str, object]]] = {}
    for record in records:
        grouped.setdefault(float(record["params"]["beta"]), []).append(record)
    guard_by_beta = {float(item["slice"]): item for item in guard["slices"]}
    rows = []
    for beta in sorted(grouped):
        item = guard_by_beta[beta]
        edge = next((entry for entry in item["edge_entries"] if entry["control"] == 0.0), None)
        interior = item["interior_entries"]
        signs = {entry["sign"] for entry in interior}
        interior_status = "无显著 crossing" if item["status"] == "NO_SIGNIFICANT_CROSSING" else item["status"]
        edge_status = "不确定" if edge and edge["sign"] == 0 else "显著同号"
        rows.append([
            f"{beta:g}",
            str(len(grouped[beta])),
            interior_status,
            edge_status,
            "全部负" if signs == {-1} else ",".join(str(value) for value in sorted(signs)),
        ])
    completed = len(status.get("completed", []))
    total = len(records)
    verdict = "good" if completed == 60 and total == 105 and guard["status"] == "NO_SIGNIFICANT_CROSSING" else "warn"
    return {
        "title": TITLE,
        "note": "2026-08-02 · 正 alpha、正 beta；负 alpha 未执行",
        "blocks": [
            {
                "kind": "verdict",
                "status": verdict,
                "label": "正区扩展网格完成；未发现内部可验收相界" if verdict == "good" else "正区扩展网格尚未完全验收",
                "why": f"旧 45 条记录与新 60 条记录合计 {total} 条；edge-aware guard={guard['status']}。",
            },
            {
                "kind": "text",
                "text": "在首段 beta=[0.1,0.5,0.9] 的基础上，新增 beta=[0.05,0.25,0.75,1.0]；每条截面使用 alpha=[0,0.125,0.25,0.5,1] 和 L=[40,60,80]。alpha=0 作为域边界点单独审计，内部 crossing 只在 alpha>0 上判断。",
            },
            {
                "kind": "table",
                "columns": ["beta", "记录数", "alpha>0 尺寸差", "alpha=0 边界", "内部符号"],
                "rows": rows,
                "numeric": [True, True, False, False, False],
                "widths": ["12%", "14%", "26%", "22%", "26%"],
            },
            {
                "kind": "figures",
                "items": [{
                    "src": "positive_phase_mesh_size_differences_20260802.png",
                    "caption": "完成后验收图。各 beta 截面的 Delta R=R(L_large)-R(L_small) 和 2σ 合成误差；零线是有限尺寸 crossing 判据，alpha=0 不参与内部 bracket。",
                }],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["服务器批次", "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh"],
                    ["新批次状态", f"{completed}/60 个新 cell 完成"],
                    ["合并记录", f"{total} 条（旧 45 + 新 60）"],
                    ["上游 controller", "仅作机械 crossing 控制；不覆盖 edge-aware 项目 guard"],
                    ["负 alpha", "未生成、未上传、未进入 observations 或图表"],
                ],
            },
            {
                "kind": "note",
                "label": "统计质量提示",
                "style": "pending",
                "text": (
                    "最大观测误差为 "
                    f"{float(max_error_record['error']):.3e}，来自 "
                    f"{max_error_label}（alpha="
                    f"{max_error_record['params']['alpha']}，beta="
                    f"{max_error_record['params']['beta']}，L="
                    f"{max_error_record['params']['L']}）。该 manifest 通过 artifact acceptance，"
                    "但该点应作为后续统计复核优先对象；本轮不据此命名相界。"
                ),
            },
            {
                "kind": "list",
                "title": "本轮 Skill 改进记录",
                "items": [
                    "支持 edge_controls，避免 alpha=0 简并边界阻塞正区内部结论。",
                    "无 bracket 时先汇总全部 beta slice，再决定是否需要用户升级。",
                    "直连服务器使用 PID、flock、心跳和逐 cell manifest，不依赖 Slurm 状态。",
                    "上传前固定标准文档和 Manifest 哈希，并强制远端 smoke/dry-run。",
                ],
            },
            {
                "kind": "code",
                "title": "证据文件",
                "text": "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/observations_merged.json\nresults/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/positive_phase_guard.json\nresults/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/phase-size-differences.csv\ndocs/phase_scan_skill_issues_20260802.md",
            },
        ],
    }


def main() -> None:
    report = load(REPORT)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-02"
    report["sections"] = [section for section in report["sections"] if section["title"] != TITLE]
    insert_at = next((i for i, section in enumerate(report["sections"]) if section["title"] == "数值验收"), len(report["sections"]))
    report["sections"].insert(insert_at, build_section())
    report_path = REPORT
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
