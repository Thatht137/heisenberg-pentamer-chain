#!/usr/bin/env python3
"""把精简全动量任务状态写入长期研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
RECEIPT = ROOT / "results" / "research_progress" / "minimal_fullq_campaign_status_20260807.json"
READINESS = ROOT / "results" / "research_progress" / "minimal_fullq_local_readiness_20260807.json"
TITLE = "2026-08-07 精简全动量复刻"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    smoke = receipt["smoke"]
    production = receipt["production"]
    production_label = f"生产 {production.get('schedule', production.get('cell_id', 'current cell'))}"
    smoke_passed = smoke["status"] == "pass"
    production_running = production["status"] == "running"
    production_accepted = production["status"] == "accepted"
    production_bounded = str(production.get("status", "")).startswith("bounded")
    replan = receipt.get("replan", {})
    production_ready = replan.get("status") == "production_ready" and bool(production.get("final_handoff"))

    if production_bounded:
        verdict_label = "严格验收失败；重规划提案待启动"
        verdict_why = f"{production.get('failure_gate', production.get('schedule', '保留失败证据；不启动后续 cell。'))}；推荐 {replan.get('recommended_window', '待定')}，{replan.get('eta', 'ETA 待定')}。"
    elif production_ready:
        verdict_label = "六个 full-q cell 已严格验收；handoff production_ready"
        verdict_why = "六个单 run、三组 dt/dt2、最终 handoff 和图件均通过；" + production.get("final_handoff", "")
    elif production_accepted:
        verdict_label = "全动量结果已严格验收"
        verdict_why = production.get("diagnostics", "验收通过")
    elif production_running:
        verdict_label = "全动量生产管线已启动"
        verdict_why = f"L=10 全链路 smoke 通过；当前 {production['cell_id']} 正在运行，{production['params']}。"
    else:
        verdict_label = "全动量管线预检"
        verdict_why = smoke["summary"]

    section = {
        "title": TITLE,
        "note": "只覆盖 0<=alpha,beta<=1；负 alpha 与参考 Fig.9 永久排除；不修改 paper/。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good" if smoke_passed and (production_running or production_accepted or production_ready) else "warn",
                "label": verdict_label,
                "why": verdict_why,
            },
            {
                "kind": "table",
                "columns": ["阶段", "参数", "状态", "验收/安排"],
                "rows": [
                    ["服务器恢复", receipt["server"]["resources"], "通过", receipt["server"]["environment"]],
                    ["L=10 smoke", smoke["params"], smoke["status"], smoke["summary"]],
                    [production_label, production["params"], production["status"], production["schedule"]],
                    ["本机准备", "回传、validator、handoff、绘图、文档和 inventory", readiness["status"], "真实六-cell 已完成；最终 handoff 与图件可直接追溯" if production_ready else "6/6 合成端到端测试；等待真实计算数据"],
                ],
                "widths": ["18%", "28%", "14%", "40%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["远端项目", receipt["server"]["project"]],
                    ["Julia / Manifest", receipt["server"]["julia_manifest"]],
                    ["脚本哈希", receipt["server"]["code_hashes"]],
                    ["当前 PID", production.get("pid", "尚未启动")],
                    ["本地验收", production.get("agreement_refined_validator", production.get("validator", "尚未执行"))],
                    ["数据回传", production.get("agreement_refined_fetch", production.get("checksum", "尚未回传"))],
                    ["失败门", production.get("failure_gate", "无")],
                    ["失败诊断", production.get("negative_weight_diagnostic", "未生成")],
                    ["时间窗诊断", production.get("window_sensitivity_diagnostic", "未生成")],
                    ["时间窗结论", production.get("window_sensitivity_summary", "未生成")],
                    ["终态诊断", production.get("diagnostics", "无")],
                    ["运行健康", production.get("runtime_health", "未记录")],
                    ["重规划", replan.get("plan_file", "未生成")],
                    ["范围核对", replan.get("scope_audit", "未生成")],
                    ["启动回执", production.get("active_launch_receipt", "未生成")],
                    ["重规划状态", replan.get("status", "未生成")],
                    ["重规划 ETA", "已完成" if production_ready else replan.get("eta", "未估计")],
                    ["预计完成", production.get("remaining_estimate", production.get("eta", "待 smoke 结束后估计"))],
                    ["下次检查", production.get("next_check", "不反复轮询")],
                    ["本机工作", "complete" if readiness["local_work_complete"] else "incomplete"],
                ],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["最近只读检查", production.get("latest_readonly_check", "尚未检查")],
                    ["进度", production.get("progress", "尚无进度")],
                    ["资源与 stderr", production.get("resources", "尚无资源快照")],
                    ["条件 ETA", production.get("remaining_estimate", production.get("eta", "待估计"))],
                    ["下一次检查", production.get("next_check", "按计划")],
                ],
            },
            {
                "kind": "list",
                "title": "生产验收门",
                "items": [
                    "每个 run 必须包含 t=0，基态 variance/site <= 1e-8，且总 Sz=0。",
                    "原始负谱权绝对占比必须 <= 0.15；不得用裁零掩盖负振铃。",
                    "同一点 dt 与 dt/2 的主峰漂移 <= 0.05 J1，低频谱权漂移 <= 5%。",
                    "每个结果先远端 checksum，再非覆盖回传、本地 checksum 与 validator；未通过不得进入文章证据。",
                ],
            },
            {
                "kind": "note",
                "label": "本轮科学目标",
                "style": "info",
                "text": "补齐参考论文式全动量 S(q,omega)，检验五站点动量折叠、q=pi 暗双重态谱权迁移，以及低能连续谱与局域四重态高能支是否并存。六-cell 已完成，但这仍不是二维相图，也不把有限尺寸未见 crossing 写成无相变证明。",
            },
            {
                "kind": "table",
                "title": "参考图与五聚体对应（当前可用等级）",
                "columns": ["参考图", "五聚体对应资产", "当前解释边界"],
                "rows": [
                    ["Fig.1", "figures/reference_aligned_fig1_pentamer_20260803.*", "1x5 单胞、局域多重态和有效自由度；可直接作为模型图"],
                    ["Fig.2", "figures/reference_aligned_fig2_pentamer_positive_20260803.*", "正 alpha 能级流与 q=pi 选择定则；四聚体能级不直接移植"],
                    ["Fig.3", "figures/paper_fig3_positive_groundstate_diagnostics_refined_20260808.*；旧版 reference_aligned_fig3_pentamer_positive_20260803.*", "40×60 O_str 探索图 + 105 条严格 R 诊断；未发现可验收内部 crossing，不命名相"],
                    ["Fig.4", "figures/reference_aligned_fig4_pentamer_positive_20260803.*", "纠缠标度与 c=1 一致的有限尺寸证据，不作无偏热力学极限断言"],
                    ["Fig.5", "figures/paper_fig5_effective_chain_selection_rules_20260804.*；figures/pentamer_momentum_filter_20260731.*", "五聚体有效链、局域多重态和动量过滤；替代四聚体激发示意"],
                    ["Fig.6", "figures/reference_aligned_fig6_alpha1_beta_scan_exploratory_20260803.*；figures/fullq_minimal_eta020_20260808.*", "前者是 alpha=1 beta 路径 exploratory，后者是三代表点 full-q production，不等于密集 beta 扫描"],
                    ["Fig.7", "figures/reference_aligned_fig7_positive_alpha_pilot_20260804.*；figures/fullq_minimal_eta020_20260808.*", "前者为 beta=0.5 正 alpha pilot，后者含 alpha=0.23,beta=0.5 生产点，不外推整条路径"],
                    ["Fig.8", "figures/round43_fig8_final_20260806_v2.*；figures/paper_fig8_bounded_cv_tebd_20260805.*", "q=pi Agreement 与 bounded 对照并存；full-q 三点图补充动态谱，不替代完整二维相图"],
                    ["Fig.9", "不纳入", "按项目范围永久排除负 alpha 与材料/RIXS 内容"],
                ],
                "widths": ["12%", "43%", "45%"],
            },
            {
                "kind": "table",
                "title": "五聚体与参考四聚体的物理差异",
                "columns": ["方面", "四聚体参考链", "五聚体当前结论"],
                "rows": [
                    ["单胞奇偶性", "4 个 spin-1/2，可形成 S=0 单胞基态", "5 个 spin-1/2 留下 S=1/2 双重态，弱正胞间耦合投影为有效反铁磁链"],
                    ["相图命名", "文献讨论平庸四聚体、Haldane 和中间临界区域", "正区当前没有验收过的命名相；三个代表点一致支持同一有效链图景，但不证明全区单相"],
                    ["激发命名", "triplon/quarton/quinton 等依赖四聚体多重态", "五聚体用自身多重态和宇称选择定则描述；q=pi 可使最低双重态变暗、四重态承载局域谱权"],
                    ["低能标度", "偶数单胞的整数自旋/弦序框架", "匹配尺寸校准后与 c=1 有限尺寸链一致，并出现可量化的弱二阶 J2，不足以单独定义新相"],
                ],
                "widths": ["18%", "38%", "44%"],
            },
            {
                "kind": "code",
                "title": "任务与状态入口",
                "text": "results/research_progress/minimal_fullq_campaign_20260807/campaign_plan.json\nresults/research_progress/minimal_fullq_campaign_status_20260807.json\nresults/research_progress/minimal_fullq_local_readiness_20260807.json\nresults/autoresearch_v5_20260807/minimal_fullq_campaign/\nscripts/autoresearch_v5/fetch_fullq_tebd_run.py\nscripts/autoresearch_v5/validate_fullq_tebd_run.py\nscripts/autoresearch_v5/finalize_minimal_fullq_handoff.py\nscripts/autoresearch_v5/plot_minimal_fullq_campaign.py",
            },
        ],
    }

    report["eyebrow"] = "RESEARCH STATUS · UPDATED 2026-08-07 · MINIMAL FULL-Q CAMPAIGN"
    report["lede"] = "1x5 Heisenberg 五聚体链复现进度。当前补齐参考论文式全动量动力学谱；范围固定为 0<=alpha,beta<=1，排除负 alpha 与参考 Fig.9。"
    report["sections"] = [section] + [item for item in report["sections"] if item.get("title") != TITLE]
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "updated", "title": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
