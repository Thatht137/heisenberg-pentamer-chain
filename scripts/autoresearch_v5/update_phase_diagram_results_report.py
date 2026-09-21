#!/usr/bin/env python3
"""把首段相图扫描结果追加到长期 HTML 报告源。"""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260731" / "round17_phase_diagram_positive"
REPORT = ROOT / "results" / "research_progress" / "report.json"
TITLE = "正区首段相图扫描结果"


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_block(section: dict[str, object], kind: str) -> dict[str, object]:
    return next(block for block in section["blocks"] if block.get("kind") == kind)


def cell_index() -> dict[tuple[float, int], dict[str, object]]:
    result: dict[tuple[float, int], dict[str, object]] = {}
    for path in sorted((RUN / "cells").glob("cell-*/manifest.json")):
        manifest = read_json(path)
        params = manifest["params"]
        result[(float(params["alpha"]), int(params["L"]))] = manifest
    return result


def format_value(value: float) -> str:
    return f"{value:.6f}"


def build_rows(beta: float, cells: dict[tuple[float, int], dict[str, object]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for alpha in (0.0, 0.125, 0.25, 0.5, 1.0):
        low = next(read_json(path) for path in (RUN / "cells").glob("cell-*/manifest.json")
                   if float(read_json(path)["params"]["alpha"]) == alpha
                   and float(read_json(path)["params"]["beta"]) == beta
                   and int(read_json(path)["params"]["L"]) == 40)
        high = next(read_json(path) for path in (RUN / "cells").glob("cell-*/manifest.json")
                    if float(read_json(path)["params"]["alpha"]) == alpha
                    and float(read_json(path)["params"]["beta"]) == beta
                    and int(read_json(path)["params"]["L"]) == 60)
        low_value = float(low["observables"]["structure_factor_ratio"]["value"])
        high_value = float(high["observables"]["structure_factor_ratio"]["value"])
        low_error = float(low["observables"]["structure_factor_ratio"]["error"])
        high_error = float(high["observables"]["structure_factor_ratio"]["error"])
        delta = high_value - low_value
        combined = math.hypot(low_error, high_error)
        significant = abs(delta) > 2.0 * combined
        label = "显著负差" if significant and delta < 0 else "显著正差" if significant else "不确定"
        budgets = f"{int(low['settings']['budget'])}/{int(high['settings']['budget'])}"
        rows.append([
            f"{beta:.1f}", f"{alpha:g}", format_value(low_value), format_value(high_value),
            format_value(delta), format_value(2.0 * combined), label, budgets,
        ])
    return rows


def build_section() -> dict[str, object]:
    cells = cell_index()
    all_manifests = [read_json(path) for path in sorted((RUN / "cells").glob("cell-*/manifest.json"))]
    accepted = sum(bool(item.get("accepted")) for item in all_manifests)
    exception = [item for item in all_manifests if int(item["settings"]["nsweeps"]) != 32]
    guard = read_json(RUN / "phase-diagram" / "positive_phase_guard.json")
    controller = read_json(RUN / "phase-diagram" / "report.json")
    rows: list[list[str]] = []
    for beta in (0.1, 0.5, 0.9):
        rows.extend(build_rows(beta, cells))
    return {
        "title": TITLE,
        "note": "2026-08-01 · 服务器完成 30-cell 正区粗扫；只报告有限尺寸证据，不命名相界",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "粗扫完成，当前不能报告相界",
                "why": f"{accepted}/30 个 cell accepted；controller={controller['status']}，positive guard={guard['status']}。",
            },
            {
                "kind": "text",
                "text": "扫描固定 alpha=[0,0.125,0.25,0.5,1]、beta=[0.1,0.5,0.9] 和 L=[40,60]，使用中心窗口结构因子比 R(L)。beta=0.1 的五个控制点均有显著负的 ΔR=R(60)-R(40)，固定区间内未见 crossing；beta=0.5 与 0.9 的 alpha=0 点落在双初态误差门槛内，因此 guard 要求增加统计或尺寸后再判断。该结果支持‘首段粗扫完成’，不支持给出论文相界数值。",
            },
            {
                "kind": "table",
                "columns": ["beta", "alpha", "R(40)", "R(60)", "ΔR", "2σ误差", "判定", "预算(40/60)"],
                "rows": rows,
                "numeric": [True, True, True, True, True, True, False, True],
                "widths": ["8%", "10%", "13%", "13%", "13%", "13%", "15%", "15%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["服务器验收", "30/30 accepted；每个 cell 的 manifest、CSV、checksums 均通过"],
                    ["统一预算", "29 个 cell 为 32 sweeps；cell-0024 因 Sz=0 方差超阈值，64 sweeps 重试通过"],
                    ["失败审计", "cell-0017 截断边缘；cell-0024 两次 32-sweep 未收敛；原始目录均保留在 cells_failed/"],
                    ["物理判定", "beta=0.1 无显著 crossing；beta=0.5/0.9 的 alpha=0 仍 inconclusive；不命名相界"],
                    ["controller", str(controller["status"]) + "：固定边界内没有可验收 bracket，等待用户决定是否扩大统计/尺寸"],
                ],
            },
            {
                "kind": "list",
                "title": "本轮发现的 Skill 改进点",
                "items": [
                    "长批次下载使用通配符 scp 可能在部分文件完成后超时，应提供按 manifest 清单的断点传输。",
                    "相图 controller 在第一个无 bracket slice 处提前 HUMAN_REQUIRED，未继续汇总后续 slice 的 inconclusive 证据。",
                    "alpha=0 简并点的双初态半差可能是物理简并；应支持 degeneracy 标记，而不是只把它当作统计误差。",
                    "phase-diagram Skill 声明使用 uv，但本机没有 uv 且离线镜像不可下载；应随 Skill 提供可移植无依赖入口。",
                ],
            },
            {
                "kind": "code",
                "title": "证据文件",
                "text": "results/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/observations.json\nresults/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/report.json\nresults/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/positive_phase_guard.json\nresults/autoresearch_v5_20260731/round17_phase_diagram_positive/run.json\nresults/autoresearch_v5_20260731/round17_phase_diagram_positive/cells/\nresults/autoresearch_v5_20260731/round17_phase_diagram_positive/cells_failed/",
            },
            {
                "kind": "note",
                "label": "下一步需用户选择",
                "style": "pending",
                "text": "可保持当前结论为‘固定正区粗扫未发现可验收相界’，或批准把 alpha=0、beta=0.5/0.9 的不确定点升级到更高预算/尺寸。没有这项选择，不应把 guard 的 INCONCLUSIVE 改写成相界。",
            },
        ],
    }


def refresh_legacy_sections(report: dict[str, object]) -> None:
    latest = next((section for section in report["sections"] if section["title"] == "最新成果"), None)
    if latest:
        latest_table = find_block(latest, "table")
        for row in latest_table["rows"]:
            if row and row[0] == "PR #244 相图扫描 Skill":
                row[1] = "已安装并用于 30-cell 首段；全部结果已回传"
                row[2] = "controller/guard 已运行"
            elif row and row[0] == "论文级正区相图扫描协议":
                row[1] = "30/30 cell 完成；cell-0024 使用 64 sweeps 例外"
                row[2] = "粗扫完成，未命名相界"

    protocol = next((section for section in report["sections"] if section["title"] == "论文级正区相图扫描协议"), None)
    if protocol:
        protocol["note"] = "2026-08-01 · 首段 30-cell 已完成；controller/guard 结果已回写"
        verdict = next((block for block in protocol["blocks"] if block.get("kind") == "verdict"), None)
        if verdict:
            verdict.update({"status": "warn", "label": "首段粗扫完成但未形成可验收相界", "why": "30 个 cell 均通过文件和物理验收；beta=0.1 无显著 crossing，beta=0.5/0.9 的 alpha=0 点仍不确定。"})
        for block in protocol["blocks"]:
            if block.get("kind") != "table":
                continue
            for row in block["rows"]:
                if row and row[0] == "已回传 cell":
                    row[1] = "cell-0001–0030 均 accepted=true；本地 checksums 全部通过"
                    row[2] = "30 个 cell 的结果可进入 observations"
                elif row and row[0] == "beta=0.1 切片":
                    row[1] = "5 个 alpha × 2 个尺寸 = 10/10 cell 通过；无显著 crossing"
                    row[2] = "固定正区边界内未见 crossing"
                elif row and row[0] == "beta=0.5 切片":
                    row[1] = "10/10 cell 通过；alpha=0 差值不确定；alpha>0 均为显著负差"
                    row[2] = "guard 保留为 inconclusive，不命名相界"
                elif row and row[0] == "首段运行状态":
                    row[1] = "30/30 完成；cell-0024 使用 64 sweeps 例外重试"
                    row[2] = "服务器 run_status=success"
            if not any(row and row[0] == "beta=0.9 切片" for row in block["rows"]):
                block["rows"].append(["beta=0.9 切片", "10/10 cell 通过；alpha=0 差值不确定；其余点显著负差", "guard 保留为 inconclusive"])
        for block in protocol["blocks"]:
            if block.get("kind") == "note" and block.get("label") == "首段计算进行中":
                block.update({"label": "首段已完成", "style": "info", "text": "服务器 30-cell batch 已完成；结果已下载并经本地 observations、controller 和 positive_phase_guard 处理。当前不报告相界。"})

    skill = next((section for section in report["sections"] if section["title"] == "PR #244 相图扫描 Skill"), None)
    if skill:
        skill["note"] = "2026-08-01 · Skill 已用于首段 30-cell 扫描；结果已回传"
        for block in skill["blocks"]:
            if block.get("kind") != "table":
                continue
            for row in block["rows"]:
                if row and row[0] == "物理计算":
                    row[1] = "cell-0001–0030 均通过；cell-0024 64-sweep 例外；controller HUMAN_REQUIRED"
                    row[2] = "粗扫完成，等待相界决策"
        for block in skill["blocks"]:
            if block.get("kind") == "note" and block.get("label") == "首段服务器计算进行中":
                block.update({"label": "首段服务器计算已完成", "style": "info", "text": "30 个 cell 已回传并校验；controller=HUMAN_REQUIRED、guard=INCONCLUSIVE，当前不命名相界。"})


def main() -> None:
    report = read_json(REPORT)
    refresh_legacy_sections(report)
    report["sections"] = [section for section in report["sections"] if section["title"] != TITLE]
    insert_at = next((i for i, section in enumerate(report["sections"]) if section["title"] == "数值验收"), len(report["sections"]))
    report["sections"].insert(insert_at, build_section())

    latest = next(section for section in report["sections"] if section["title"] == "最新成果")
    latest_table = find_block(latest, "table")
    row = ["正区首段相图扫描", "30/30 cell 完成；beta=0.1 无 crossing，beta=0.5/0.9 的 alpha=0 不确定", "粗扫完成，未命名相界"]
    for index, old in enumerate(latest_table["rows"]):
        if old and old[0] == row[0]:
            latest_table["rows"][index] = row
            break
    else:
        latest_table["rows"].append(row)

    log = next(section for section in report["sections"] if section["title"] == "进展日志")
    log_table = find_block(log, "table")
    log_row = ["2026-08-01", "正区首段相图扫描", "服务器 30-cell 粗扫和本地 controller/guard 验收", "30/30 accepted；1 个 64-sweep 例外；controller HUMAN_REQUIRED，guard INCONCLUSIVE", "完成（待决策）"]
    for index, old in enumerate(log_table["rows"]):
        if old and old[0] == log_row[0] and old[1] == log_row[1]:
            log_table["rows"][index] = log_row
            break
    else:
        log_table["rows"].append(log_row)

    outputs = next(section for section in report["sections"] if section["title"] == "成果文件")
    code = find_block(outputs, "code")
    paths = [
        "scripts/autoresearch_v5/update_phase_diagram_results_report.py",
        "results/autoresearch_v5_20260731/round17_phase_diagram_positive/run.json",
        "results/autoresearch_v5_20260731/round17_phase_diagram_positive/cells_failed/",
    ]
    lines = code["text"].splitlines()
    code["text"] = "\n".join(lines + [path for path in paths if path not in lines])
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {REPORT}")


if __name__ == "__main__":
    main()
