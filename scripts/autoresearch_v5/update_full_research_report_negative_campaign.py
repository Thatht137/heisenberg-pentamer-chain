#!/usr/bin/env python3
"""把负 alpha 完整相图 campaign 写入完整研究报告。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

from render_research_progress import negative_phase_section


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "full_research_report_20260808" / "report.json"
STATUS = ROOT / "results" / "research_progress" / "negative_full_phase_campaign_status_20260809.json"
RENDERER = Path.home() / ".codex" / "skills" / "report" / "render_report.py"
TITLE = "2026-08-09 负 alpha 完整相图 campaign"


def stage_phase_figure(section: dict[str, object]) -> None:
    """把相图复制到完整报告资产目录。"""
    assets = REPORT.parent / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    names = {
        "full_alpha_phase_evidence_20260811.png",
        "full_alpha_tentative_phase_diagram_20260811.png",
        "full_alpha_working_phase_diagram_20260812.png",
    }
    for name in names:
        source = ROOT / "figures" / name
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
        target = assets / f"{digest}_{source.name}"
        if not target.exists():
            shutil.copy2(source, target)
        for block in section.get("blocks", []):
            if block.get("kind") != "figures":
                continue
            for item in block.get("items", []):
                if Path(item.get("src", "")).name == source.name:
                    item["src"] = f"assets/{target.name}"


def load_renderer():
    spec = importlib.util.spec_from_file_location("harness_report_renderer", RENDERER)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载报告渲染器")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    campaign = json.loads(STATUS.read_text(encoding="utf-8"))
    sections = [section for section in document["sections"] if section.get("title") != TITLE]
    index = next((i + 1 for i, section in enumerate(sections) if section.get("title") == "Figure 3：相结构诊断"), 1)
    phase_section = negative_phase_section()
    stage_phase_figure(phase_section)
    sections.insert(index, phase_section)
    for section in sections:
        if section.get("title") == "一页结论":
            for block in section.get("blocks", []):
                if block.get("kind") == "verdict":
                    block["label"] = "严格未确认第二个热力学相；宽松口径采用三个体相区的工作图"
                    block["why"] = "工作计数为：深负alpha的有效S≈3/2、q≈0.60π候选非公度临界区，近零负侧q=π候选公度临界区，以及正alpha有效S=1/2、q=π无隙反铁磁区；alpha=0另作解耦高简并奇异线。alpha=-0.35到-0.25的分隔仍可能只是Lifshitz交叉。"
                    break
            for block in section.get("blocks", []):
                if block.get("kind") != "table" or block.get("columns", [None])[0] != "问题":
                    continue
                for row in block.get("rows", []):
                    if row[0] == "是否找到了新相？":
                        row[1] = "严格口径尚未；宽松物理判断采用三个体相区，其中负α含两个候选临界区。"
                        row[2] = "强耦合图像 + beta=0.5有限尺寸数据"
                    elif row[0] == "是否找到了相变点？":
                        row[1] = "候选动量重构区间[-0.35,-0.25]；未定为热力学相界。"
                        row[2] = "q_peak变化与R60-R40反号"
        if section.get("title") == "研究目标、范围与对象":
            for block in section.get("blocks", []):
                if block.get("kind") != "table":
                    continue
                for row in block.get("rows", []):
                    if row[0] == "参数范围":
                        row[1] = "-1 ≤ α ≤ 1，0 ≤ β ≤ 1；α=0、β=0 作为奇异边界控制"
                    elif row[0] == "参考复现":
                        row[1] = "对应参考文献 Fig.3 的完整 α 范围；五聚体替换四聚体"
                    elif row[0] == "明确排除":
                        row[1] = "参考文献 Fig.9；未经严格验收的相名和热力学外推"
    document["sections"] = sections
    document["eyebrow"] = "FULL RESEARCH REPORT · UPDATED 2026-08-09 · FULL ALPHA CAMPAIGN"
    phase_state = {
        "stage_a_r1_running": "R1 已启动并按原门槛顺序运行",
        "stage_a_r1_status_unknown": "R1 最近一次 SSH 状态不可读，等待下一周期复核",
        "stage_a_r1_failed_validation_pending": "R1 已由严格数值门停止，正在执行独立回传验收",
        "stage_a_r2_retry_preparing": "R1 独立验收为10 pass/1 fail，R2 单点严格重试准备中",
        "stage_a_r2_running": "R1 已接纳10项严格结果，R2 单点64-sweep重试正在运行",
        "stage_a_r2_success_validation_pending": "R2 远端成功，正在执行独立checksum与validator",
        "stage_a_r3_preparing": "R2 独立验收通过，R3剩余13-cell续跑包准备中",
        "stage_a_r3_running": "R2 已接入控制器，R3剩余13-cell续跑正在运行",
        "stage_a_r3_failed_validation_pending": "R3已由严格门停止，正在执行独立回传验收",
        "stage_a_r4_preparing": "R3独立验收为2 pass/1 fail，R4单点严格重试准备中",
        "stage_a_r4_running": "R3通过项已接入控制器，R4单点64-sweep重试正在运行",
        "stage_a_r5_running": "R4严格验收并接入控制器，R5剩余10 cells正在单并发运行",
        "stage_a_r6_running": "R5一项校准通过、一项方差失败，R6按32→64 sweeps单点重试运行中",
        "stage_a_r7_running": "R6通过且保留双初态系统误差，R7剩余8 cells正在单并发运行",
        "stage_a_r8_running": "R7首个L60点方差与gap门失败，R8按32→64 sweeps单点重试运行中",
        "stage_a_r9_running": "R8严格验收并接入控制器，R9剩余7 cells正在单并发运行",
        "stage_a_r9_failed_validation_complete": "R9独立验收1 pass/1 fail，L40方差超门，R10按32→64 sweeps单点重试准备中",
        "stage_a_r10_running": "R9部分终态已严格接入，R10按32→64 sweeps单点重试正在运行",
        "stage_a_r10_failed_validation_complete": "R10的center仍有方差与gap超门，R11按64→128 sweeps单点重试准备中",
        "stage_a_r11_running": "R10失败provenance已锁定，R11按最终128 sweeps预算单点重试运行中",
        "stage_a_r12_preparing": "R11最终128-sweep预算严格通过，R12剩余5 cells本地准备中",
        "stage_a_r12_running": "R11已严格接入，R12剩余5 cells正在保守预算下单并发运行",
        "stage_a_r13_preparing": "R12首个L60点仅Sz1方差超门，R13按64→128 sweeps单点重试准备中",
        "stage_a_r13_running": "R12失败provenance已锁定，R13以最终128 sweeps预算单点重试运行中",
        "stage_a_r14_preparing": "R13最终128-sweep预算严格通过，R14剩余4 cells本地准备中",
        "stage_a_r14_running": "R13已严格接入，R14剩余4 cells正在64-sweep保守预算下单并发运行",
        "stage_a_r15_preparing": "R14首个L80校准点仅方差超门，R15按64→128 sweeps最终预算准备中",
        "stage_a_r15_running": "R14失败provenance已锁定，R15以最终128 sweeps预算单点重试运行中",
        "stage_a_blocked_final_tier": "R15最终预算仅center gap门失败，Stage A严格保持NotEvaluable且不赋相名",
        "stage_a_r16_preparing": "R15诊断为初态亚稳，作者批准R16三初态、256 sweeps与能量平台门修复",
        "stage_a_r16_running": "R16三初态收敛协议修复正在单并发运行，原验收门全部保留",
        "stage_a_r16_practical_adjudication": "R16严格平台门失败，正在按作者批准的1e-7实用门审理，仅作非边界校准",
        "stage_a_r16_practical_accepted": "R16按1e-7实用平台门接纳为非边界L80校准，严格失败证据完整保留",
        "stage_a_r17_running": "R16实用校准已接入，R17正在补齐alpha=-0.025的L40/L60/L80",
        "stage_a_r18_running": "R17仅Sz1方差轻微超门，R18以最终128-sweep预算重试alpha=-0.025、L40",
        "stage_a_r19_running": "R18已严格补救通过，R19正在补齐alpha=-0.025的L60/L80",
        "stage_b_r1_running": "Stage A已24/24闭合，Stage B正在扫描六条beta切片并检验负区二维相界",
        "stage_b_r2_running": "Stage B首点仅Sz0方差超门，R2按32→64 sweeps重试且其余95点预算不变",
        "stage_b_r3_running": "Stage B R2接纳L40，L60方差超门；R3将L60升至64 sweeps并续跑剩余95点",
        "stage_b_r4_running": "Stage B已接纳alpha=-1的L40/L60；R4重试alpha=-.75的L40并续跑94点",
        "stage_b_r5_running": "Stage B已接纳前三点；R5将alpha=-.75的L60升至64 sweeps并续跑93点",
        "stage_b_r6_running": "Stage B已接纳前四点；R6将alpha=-.5的L40升至64 sweeps并续跑92点",
        "stage_b_r7_running": "Stage B已接纳前五点；R7将alpha=-.5的L60升至64 sweeps并续跑91点",
        "stage_b_blocked_remote_connection": "Stage B R7最后确认健康运行8/91；SSH端口连续三次拒绝连接，监控暂停且不推断计算状态",
        "stage_b_r8_running": "服务器已恢复；R7严格接纳10点，R8正以128 sweeps重试负gap与方差失败点并续跑81点",
        "stage_b_r9_running": "R8的128-sweep补救通过；Stage B累计接纳16点，R9正重试beta=.10首个L40点并续跑80点",
        "stage_b_r10_running": "Stage B累计接纳17点；R10正将beta=.10的L60从32提升至64 sweeps并续跑79点",
        "stage_b_r10_terminal_fetch_pending": "R10已自然终态且远端checksum通过；非覆盖回传因本地权限审批超时待恢复，尚未作科学接纳",
    }.get(campaign.get("status"), "R1 修复重跑准备中")
    document["lede"] = f"完整汇总 1×5 Heisenberg 五聚体链的模型、数值链、图件、当前物理判断与证据边界。相图范围为 -1≤alpha≤1、0≤beta≤1；严格口径尚未确认第二个热力学相，宽松口径采用深负alpha非公度区、近零负侧公度区和正alpha无隙反铁磁区三个体相区的工作图，alpha=0另作奇异线；beta=0.5 的 alpha∈[-0.35,-0.25] 暂作动量重构带；{phase_state}。"
    REPORT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html = load_renderer().render(document, REPORT.parent)
    (REPORT.parent / "report.html").write_text(html, encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "sections": len(sections)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
