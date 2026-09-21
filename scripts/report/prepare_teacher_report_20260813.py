"""将项目报告整理为教师阅读版。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/meeting_report_20260812/report.json"


def find_section(document: dict, title: str) -> dict:
    return next(section for section in document["sections"] if section["title"] == title)


def replace_text(value: str) -> str:
    replacements = {
        "（论文风格重绘）": "",
        "（论文布局与 jet 配色）": "",
        "（参考 Fig.4 的黑色短线/圆点语言）": "",
        "（参考 Fig.5 的时序示意语言）": "",
        "1×5 当前最强动力学验收": "1×5 代表点动力学对照",
        "11 个 accepted CV 点": "11 个已收敛的 CV 频率点",
        "已有 pilot/限定结果": "已有探索性结果",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


def clean_strings(value):
    if isinstance(value, dict):
        return {key: clean_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_strings(item) for item in value]
    if isinstance(value, str):
        return replace_text(value)
    return value


def main() -> None:
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    document["eyebrow"] = "研究进展报告 · 2026-08-13"
    document["lede"] = (
        "本报告总结 1×5 Heisenberg 五聚体链的模型、数值方法和主要结果，并将参考四聚体论文 Fig. 1–8 "
        "与 1×5 计算结果逐项比较。核心结论是：论文的研究框架已经迁移到五聚体模型；由于奇数单胞保留半整数低能自由度，"
        "正耦合区表现为有效 S=1/2 反铁磁链。负耦合区的二维相图以及全 q 动力学谱仍需进一步收敛。"
    )
    document["sections"] = [section for section in document["sections"] if section["title"] != "可直接使用的汇报讲稿"]

    overview = find_section(document, "一页结论")
    overview["title"] = "研究概览"
    overview["note"] = "主要结论、证据强度与尚未完成的部分。"
    overview["blocks"][2]["label"] = "1×5 与 1×4 的物理结论不同"
    overview["blocks"][3]["label"] = "负耦合区：初步结果"

    relation = find_section(document, "研究目标与参考关系")
    relation["blocks"] = [block for block in relation["blocks"] if block.get("label") != "汇报口径"]

    positive = find_section(document, "结果二：正耦合区的有效 S=1/2 链")
    positive["note"] = "单胞投影、有限系统计算和纠缠标度给出相互一致的证据。"

    negative = find_section(document, "结果三：负耦合区的候选动量重构")
    negative["note"] = "当前观察到动量重构迹象，但尚不足以确认新的热力学相。"

    comparison = find_section(document, "论文原图与 1×5 结果逐图对照")
    comparison["note"] = (
        "左侧为参考论文四聚体结果，右侧为本项目的 1×5 计算结果。图形采用相近的字体、布局和配色；"
        "当物理量或参数路径不同时，在图注和结论中明确说明。"
    )
    summary = comparison["blocks"][0]
    summary["rows"] = [
        ["Fig. 1", "同类诊断", "已完成", "正 α 区的五聚体基态为 S=1/2 双重态。"],
        ["Fig. 2", "同类诊断", "已完成", "α=0 两侧的单胞基态由 S=3/2 切换为 S=1/2。"],
        ["Fig. 3", "同类诊断", "有限尺寸结果", "正 α 区未观察到可稳定验收的额外相界。"],
        ["Fig. 4", "同类诊断", "正区代表点", "五种切口具有规则纠缠谱结构，纠缠标度与 c=1 接近。"],
        ["Fig. 5", "机制对应", "已完成", "低能自由度是有效 S=1/2，自旋通道受动量选择定则过滤。"],
        ["Fig. 6", "参数直接对应", "探索性", "谱权随 β 重排，但全参数收敛尚未完成。"],
        ["Fig. 7", "诊断角色对应", "探索性", "正 α 代表点保留低能连续谱，参数路径与论文不同。"],
        ["Fig. 8", "方法验证", "代表点已验收", "q=π 代表点的 CV 与 TEBD 结果一致。"],
    ]

    cards = {block.get("title", ""): block for block in comparison["blocks"] if block.get("kind") == "card"}
    cards["Fig. 1｜模型与局域多重态"]["blocks"][-1] = {
        "kind": "verdict",
        "status": "good",
        "label": "模型与单胞谱已确认",
        "why": "键序、哈密顿量和孤立五聚体 ED 结果相互一致。",
    }
    cards["Fig. 2｜单胞能级流与可见通道"]["blocks"][-1] = {
        "kind": "verdict",
        "status": "good",
        "label": "完整 α 区间已覆盖",
        "why": "单胞能级覆盖 α∈[-1,1]；动量通道分类目前限定在正 α 区。",
    }
    cards["Fig. 3｜二维静态诊断"]["blocks"][-1]["label"] = "高密度纹理与有限尺寸诊断并列展示"
    cards["Fig. 6｜跨 β 的动力学结构因子"]["blocks"][-1]["label"] = "探索性动力学结果"
    fig7 = cards["Fig. 7｜参数路径谱与 q=π 切片"]
    fig7["title"] = "Fig. 7｜参数路径动力学谱"
    fig7["blocks"][0]["items"][1]["caption"] = (
        "1×5 结果：固定 β=0.5，沿正 α=0.14/0.23/0.33 扫描得到的全 q 动力学结构因子。"
    )
    fig7["blocks"][-1]["why"] = "论文固定负 α 扫描 β；本图固定 β=0.5 扫描正 α，且系统为 L=40、tmax=15。"
    fig8 = cards["Fig. 8｜理论分支叠加与跨方法验收"]
    fig8["title"] = "Fig. 8｜动力学结果的跨方法验证"
    fig8["blocks"][0]["items"][1]["caption"] = (
        "1×5 代表点动力学对照：α=0.23、β=0.5、L=40、q=π；11 个已收敛的 CV 频率点与 TEBD 曲线比较，"
        "并给出相对差异和四项验收结果。"
    )
    fig8["blocks"][-1]["why"] = "该结果验证了代表点的数值一致性，但尚不能外推为完整全 q、全参数动力学谱。"

    progress = find_section(document, "当前完成度与下一步")
    progress["title"] = "研究进展与下一步"
    progress["note"] = "已完成的结果、证据强度以及后续需要补充的计算。"
    progress["blocks"] = [block for block in progress["blocks"] if block.get("kind") not in {"code"} and block.get("label") != "环境说明"]
    table = progress["blocks"][0]
    table["columns"] = ["工作项", "状态", "当前结论"]
    table["rows"] = [
        ["模型与计算框架", "完成", "1×5 Hamiltonian、ED、DMRG 和两条动力学路线已建立。"],
        ["单胞 ED 与低能多重态", "完成", "正区 S=1/2、负区 S=3/2，α=0 为特殊简并点。"],
        ["正区有效理论", "较强证据", "单胞投影、两胞 ED、多尺寸 DMRG 和纠缠标度相互支持。"],
        ["正区静态相图", "有限尺寸结果", "当前没有证据支持正区内部存在额外相界。"],
        ["负区相图", "进行中", "β=0.5 出现候选动量重构，其他 β 切片仍需验证。"],
        ["q=π 代表点动力学", "完成交叉验证", "CV 与 TEBD 在峰位和积分权重上相互一致。"],
        ["全 q、全参数动力学谱", "进行中", "仍需系统尺寸、时间步、最大演化时间和跨方法收敛。"],
    ]

    document = clean_strings(document)
    REPORT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
