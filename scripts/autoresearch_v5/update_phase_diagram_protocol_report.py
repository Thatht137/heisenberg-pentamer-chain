#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把论文级正区相图协议写入长期 HTML 报告数据。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
TITLE = "论文级正区相图扫描协议"


def find_block(section: dict[str, object], kind: str) -> dict[str, object]:
    return next(block for block in section["blocks"] if block.get("kind") == kind)


def upsert_row(table: dict[str, object], row: list[str]) -> None:
    for index, old in enumerate(table["rows"]):
        if old and old[0] == row[0]:
            table["rows"][index] = row
            return
    table["rows"].append(row)


def build_section() -> dict[str, object]:
    return {
        "title": TITLE,
        "note": "2026-07-31 · 首段已授权；cell-0001 通过，30-cell batch 运行中",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "首段已上传，首个 cell 通过验收",
                "why": "服务器 c104-ysu 的 cell-0001 双初态收敛；完整 30-cell 首段仍在运行。",
            },
            {
                "kind": "text",
                "text": "这是复现参考论文判相逻辑的五聚体版本：固定 J1=1，扫描 alpha=J2/J1 与 beta=J3/J1，使用开边界有限链 DMRG。控制量是中心窗口的 R(L)=1-S(q1)/S(pi)，其中 q1=pi-2pi/M、M 为窗口长度；R 只用于检查相邻尺寸是否出现带误差的 crossing，不能单独赋予相名。首 cell 暴露出确定性 domain 产品态会停在高能局域本征态，现已改用固定种子的随机 QN-MPS（link dimension 4，噪声 1e-6/1e-7/1e-8）作为 domain 的 Sz=0 初态；本地和服务器统一重跑的首 cell 均通过。",
            },
            {
                "kind": "table",
                "columns": ["项目", "论文级设置", "用途/门槛"],
                "rows": [
                    ["alpha 控制轴", "0, 0.125, 0.25, 0.50, 1.00；边界 [0,1]", "保留 alpha=0 解耦点；禁止负 alpha"],
                    ["beta 切片", "0.10, 0.50, 0.90", "覆盖弱、中、强胞间耦合"],
                    ["尺寸序列", "L=40, 60, 80（N_units=8,12,16）", "先 40/60 粗扫，再按 crossing 晋级 80"],
                    ["方法", "OBC DMRG；Sz=0 与 Sz=1；maxdim=800/1000/1200；32 sweeps；cutoff=1e-11；domain 使用固定种子随机 QN-MPS", "能隙、方差、截断、结构因子统一验收"],
                    ["观测量", "R(L)=1-S(pi-2pi/M)/S(pi)，中心 80% 窗口的 connected Sz 结构因子", "无量纲；q=pi 主峰处做归一化"],
                    ["误差", "center/domain 双初态半差；与 10 倍最大 discarded weight 比较；下限 1e-4", "保守数值误差，不伪造统计精度"],
                    ["crossing 验收", "sigma=2；目标 bracket 宽度 <=0.025；最终必须由 (L=60,80) 支持", "无显著 bracket 时报告‘未发现可验收相界’"],
                    ["实现 smoke", "L=10, alpha=0.25, beta=0.5：R=0.3555503；center/domain 半差 1.1e-16", "双扇区方差、截断和结构因子输出均通过"],
                    ["首 cell 服务器验收", "alpha=0，beta=0.1，L=40；R=0.007581918893；双初态半差 3.19e-5；cell-0001 accepted=true", "alpha=0 简并性进入保守误差"],
                    ["已回传 cell", "cell-0001–0016 均 accepted=true；最大截断 1e-11 量级；本地 checksums 全部通过", "前十六个 cell 原始结果已核对"],
                    ["beta=0.1 切片", "5 个 alpha × 2 个尺寸 = 10/10 cell 通过；未发现失败或显著初态不一致", "首个 beta 切片完成，等待本地 crossing 分析"],
                    ["beta=0.5 切片", "当前 6/10 cell 通过（alpha=0,0.125,0.25；L=40/60）；无失败", "第二个 beta 切片进行中"],
                    ["首段运行状态", "PID=3436382；cell-0001/30–0016/30 已完成；当前 cell-0017", "服务器 batch 运行中，未提前命名相"],
                    ["研究边界", "alpha>=0、beta>=0；Fig.9/负 alpha 路径不做", "旧负区文件只作档案，不进入新任务"],
                ],
                "numeric": [False, False, False],
                "widths": ["20%", "48%", "32%"],
            },
            {
                "kind": "heading",
                "level": 3,
                "text": "本地控制器和服务器分工",
            },
            {
                "kind": "list",
                "items": [
                    "phase policy、observations、state、report 和 crossing 决策只在 Windows 本地运行；已加入 fcntl 兼容入口并通过 scaffold/init/check/ingest/inspect smoke。",
                    "服务器只接收 parameter-scan compute entrypoint 和 run spec；不上传控制器、state 或认证信息。首段已按用户确认上传，远端 PID=3436382。",
                    "每个 phase cell 内部运行 center/domain 两个独立初态，回传一个带 value/error 的 manifest；回传前不接受调度器状态作为科学成功。",
                    "首段粗扫共 30 个 cell（3 个 beta × 5 个 alpha × 2 个初始尺寸）；30 个 action spec 已逐一落盘并与 controller 授权 ID 对齐。",
                    "positive_phase_guard 会把‘无显著 crossing’与‘数据不足’分开；前者可作为正区无相界证据，后者必须继续计算。",
                    "upload_phase_bundle.ps1 需要显式‘确认首段’，并在断线重试时按远端 SHA-256 跳过已完成文件；首个失败 cell 已移入 cells_failed/cell-0001_initial_failure 作为审计记录。",
                    "domain 初态采用固定种子 randomMPS(sites,state,4)，配合 1e-6/1e-7/1e-8 小噪声，保持 QN 扇区和可复现性；这修复了 alpha=0,beta=0.1 的高能局域态陷阱。",
                ],
            },
            {
                "kind": "heading",
                "level": 3,
                "text": "Skill 改进建议",
            },
            {
                "kind": "list",
                "items": [
                    "上传脚本应区分‘SSH 连接超时’与‘远端 SHA-256 不匹配’，对前者做有限指数重试，不要直接报 hash mismatch。",
                    "phase cell runner 应默认提供固定种子的随机 QN-MPS 或参数延续初态；确定性 domain 产品态可能停在高能局域本征态。",
                    "alpha=0 存在简并基态时，双初态 observable 半差可能是物理简并而非数值误差；应标记 degeneracy 并禁止用该点单独命名相界。",
                    "Windows 报告工具应显式使用 UTF-8，避免系统 GBK 导致中文 JSON/脚本渲染失败。",
                ],
            },
            {
                "kind": "code",
                "title": "已生成的本地输入",
                "text": "results/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/phase-policy.json\nresults/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/observations.json\nresults/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/state.json\nresults/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/report.json\nresults/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/action_index.json\nresults/autoresearch_v5_20260731/round17_phase_diagram_positive/parameter-scan.run_spec.json\nscripts/autoresearch_v5/run_phase_structure_ratio_cell.py",
            },
            {
                "kind": "note",
                "label": "首段计算进行中",
                "style": "info",
                "text": "服务器已完成 cell-0001 并通过双初态验收；完整 30-cell batch 由 PID=3436382 顺序运行，当前为 cell-0002。完成后回传 cells/ manifests，再由本地 controller collect/check/ingest，并运行 positive_phase_guard。",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["sections"] = [section for section in report["sections"] if section["title"] != TITLE]
    insert_at = next(
        (index for index, section in enumerate(report["sections"])
         if section["title"] == "PR #244 相图扫描 Skill"),
        len(report["sections"]),
    ) + 1
    report["sections"].insert(insert_at, build_section())

    latest = next(section for section in report["sections"] if section["title"] == "最新成果")
    latest_table = find_block(latest, "table")
    upsert_row(latest_table, ["论文级正区相图扫描协议", "beta=0.1 的 10/10 完成；beta=0.5 已通过 6/10，当前 cell-0017", "服务器 batch 运行中，结果未用于命名相"])

    log = next(section for section in report["sections"] if section["title"] == "进展日志")
    log_table = find_block(log, "table")
    upsert_row(log_table, ["2026-07-31", "论文级正区相图扫描协议", "最终初态方案统一重跑", "随机 QN-MPS + 小噪声压低 L=60 截断；cell-0001 通过；batch PID=3436382", "运行中"])
    upsert_row(log_table, ["2026-07-31", "首段首 cell 验收", "alpha=0,beta=0.1,L=40 双初态结构因子比值", "R=0.007581918893；半差 3.19e-5；两 child accepted=true", "通过"])

    outputs = next(section for section in report["sections"] if section["title"] == "成果文件")
    code = find_block(outputs, "code")
    additions = [
        "results/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/phase-policy.json",
        "results/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/observations.json",
        "results/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/state.json",
        "results/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/report.json",
                "results/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/action_index.json",
                "results/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/action_specs/",
                "results/autoresearch_v5_20260731/round17_phase_diagram_positive/phase-diagram/positive_phase_guard.json",
                "results/autoresearch_v5_20260731/round17_phase_diagram_positive/server_upload_manifest.json",
        "results/autoresearch_v5_20260731/round17_phase_diagram_positive/parameter-scan.run_spec.json",
        "scripts/autoresearch_v5/phase_diagram_windows_controller.py",
        "scripts/autoresearch_v5/run_phase_structure_ratio_cell.py",
        "scripts/autoresearch_v5/make_phase_diagram_run_spec.py",
        "scripts/autoresearch_v5/update_phase_diagram_protocol_report.py",
        "scripts/autoresearch_v5/materialize_phase_diagram_actions.py",
        "scripts/autoresearch_v5/positive_phase_guard.py",
        "scripts/autoresearch_v5/run_phase_structure_batch.py",
        "scripts/autoresearch_v5/make_phase_server_upload_manifest.py",
        "scripts/autoresearch_v5/upload_phase_bundle.ps1",
    ]
    lines = code["text"].splitlines()
    code["text"] = "\n".join(lines + [item for item in additions if item not in lines])
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {REPORT}")


if __name__ == "__main__":
    main()
