#!/usr/bin/env python3
"""把正区静态生产管线与本地 oracle 追加到长期报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
RUN = ROOT / "results" / "autoresearch_v5_20260730" / "round8_positive_static_production"
SECTION_TITLE = "正区静态生产计算准备"


def build_section() -> dict[str, object]:
    comparison = json.loads((RUN / "local_oracle_crosscheck" / "cross-method-check.json").read_text(encoding="utf-8"))
    difference = comparison["absolute_differences"]
    dmrg = comparison["dmrg"]
    ed = comparison["ed"]
    return {
        "title": SECTION_TITLE,
        "note": "2026-07-30 · 27-cell 规格完成；尚未上传或启动服务器任务",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "双扇区静态管线通过本地 ED oracle",
                "why": "L=10 的 Sz=0/1 能量与精确对角化一致，能隙绝对差 1.69e-9；宽松设置被拒绝、紧设置被接受。",
            },
            {
                "kind": "text",
                "text": "候选静态验证已展开为 9 条左/脊/右参数路径和 L=40/60/80 三个尺寸，共 27 个独立 cell。每个 cell 在相同 OBC Hamiltonian 下分别优化 Sz=0 与 Sz=1，保存两扇区方差和截断误差，并从 Sz=0 状态提取弦关联距离剖面、全部最近邻键关联和中心五类 Schmidt 谱。",
            },
            {
                "kind": "table",
                "columns": ["方法要素", "本项目设置", "验收作用"],
                "rows": [
                    ["Hamiltonian", "1×5 Heisenberg，alpha>=0、beta>=0", "固定符号与 S·S 归一化"],
                    ["几何", "OBC，L=40/60/80", "三尺寸趋势，不以单点判相"],
                    ["键维 D", "800/1000/1200", "记录实际 D；触顶则追加一档"],
                    ["算法", "有限链 DMRG，Sz=0 与 Sz=1", "同一 cell 给出能隙与两扇区残差"],
                    ["目标", "gap、O_str(r)、bond correlation、Schmidt spectrum", "多证据区分 crossover 与候选边界"],
                    ["近似", "有限 L 与有限 D", "variance、discarded weight、尺寸和初态复核"],
                ],
                "widths": ["18%", "41%", "41%"],
            },
            {
                "kind": "table",
                "columns": ["量", "DMRG", "精确 ED", "绝对差", "标签"],
                "rows": [
                    ["E(Sz=0)", f"{dmrg['energy_sz0']:.12f}", f"{ed['sz0']['energy']:.12f}", f"{difference['energy_sz0']:.3e}", "Agreement"],
                    ["E(Sz=1)", f"{dmrg['energy_sz1']:.12f}", f"{ed['sz1']['energy']:.12f}", f"{difference['energy_sz1']:.3e}", "Agreement"],
                    ["spin gap", f"{dmrg['spin_gap']:.12f}", f"{ed['spin_gap']:.12f}", f"{difference['spin_gap']:.3e}", "Agreement"],
                ],
                "numeric": [False, True, True, True, False],
                "widths": ["18%", "23%", "23%", "18%", "18%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["生产规模", "9 路径 × 3 尺寸 = 27 cells，顺序运行"],
                    ["最大资源", "8 Julia threads；nice=10；仅 3 个 ridge,L=80 cell 保存 MPS"],
                    ["基线设置", "maxdim=800/1000/1200；32 sweeps；cutoff=1e-11"],
                    ["单 cell 门槛", "两扇区 variance/L<=1e-8；discarded weight<=1e-9；Sz 扇区正确；gap>=-1e-8"],
                    ["本地宽松 oracle", "执行成功但 accepted=false，证明验收器会拒绝低精度结果"],
                    ["本地紧 oracle", "accepted=true；所有 10 项 cell gate 通过"],
                    ["分阶段执行", "pilot=三个 L=40 ridge 点；full=全部 27 cells 并复用已完成 pilot"],
                    ["自动测试", "13 / 13 通过"],
                    ["服务器状态", "未上传、未启动，等待用户确认"],
                ],
            },
            {
                "kind": "list",
                "title": "执行安全边界",
                "items": [
                    "run spec 中所有 alpha 和 beta 均非负。",
                    "服务器强制离线环境，不包含 curl、wget 或 Pkg.add/update/instantiate。",
                    "输出仅允许位于项目 results/，非空 cell 拒绝覆盖。",
                    "已完成 cell 通过 status 与 SHA-256 恢复识别；失败 cell 保留证据。",
                    "一次只运行一个 cell，线程数不超过 8。",
                ],
            },
            {
                "kind": "code",
                "title": "生产与复核入口",
                "text": "results/autoresearch_v5_20260730/round8_positive_static_production/run_spec.json\nresults/autoresearch_v5_20260730/round8_positive_static_production/paths.json\nresults/autoresearch_v5_20260730/round8_positive_static_production/local_oracle_crosscheck/cross-method-check.csv\nscripts/autoresearch_v5/positive_static_cell.jl\nscripts/autoresearch_v5/run_positive_static_cell.py\nscripts/autoresearch_v5/run_positive_static_scan.py\nscripts/autoresearch_v5/launch_positive_static_server.sh\nscripts/autoresearch_v5/exact_static_sector_oracle.py",
            },
            {
                "kind": "note",
                "label": "结论边界",
                "style": "pending",
                "text": "本轮证明实现、规格和验收逻辑可用，不增加相图物理完成度。L=10 oracle 只验证方法；只有服务器返回的 27-cell 数据通过尺寸、方差、键维和多观测量闭环后，才能更新正区静态结论。",
            },
        ],
    }


def append_log(report: dict[str, object]) -> None:
    new_rows = {
        "静态生产管线": ["2026-07-30", "静态生产管线", "9 路径×3 尺寸双扇区 DMRG 与完整静态测量", "pilot/full 分层；27-cell run spec；13/13 测试通过；未提交", "准备完成"],
        "静态方法 oracle": ["2026-07-30", "静态方法 oracle", "L=10 DMRG 与固定 Sz 精确对角化比较", "两能量与能隙均 Agreement；gap 差 1.69e-9", "完成"],
    }
    for section in report["sections"]:
        if section["title"] != "进展日志":
            continue
        for block in section["blocks"]:
            if block.get("kind") != "table":
                continue
            existing = {row[1]: index for index, row in enumerate(block["rows"]) if row}
            for name, row in new_rows.items():
                if name in existing:
                    block["rows"][existing[name]] = row
                else:
                    block["rows"].append(row)
            return
    raise ValueError("未找到进展日志表")


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["sections"] = [section for section in report["sections"] if section["title"] != SECTION_TITLE]
    insert_at = next(
        (index for index, section in enumerate(report["sections"]) if section["title"] == "数值验收"),
        len(report["sections"]),
    )
    report["sections"].insert(insert_at, build_section())
    append_log(report)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {REPORT}")


if __name__ == "__main__":
    main()
