#!/usr/bin/env python3
"""把 8 月 10 日交付计划写入长期 HTML 报告源。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
TITLE = "8 月 10 日交付计划"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_section() -> dict[str, object]:
    return {
        "title": TITLE,
        "note": "2026-08-02 · 计算、写作和验收同一排期；只含正 alpha、正 beta",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "目标：8 月 10 日交付可审阅的完整初稿与可复算证据包",
                "why": "Fig. 1--5 可由已验收资产完成；唯一高成本风险是 L=80 动力学谱，因此采用 warm-start 决策门和明确的降级规则。",
            },
            {
                "kind": "text",
                "text": "当前最强主线是正 alpha 五聚体的有效 S=1/2 反铁磁链：单胞 ED、二阶有效理论、有限链静态证据、纠缠校准和局域选择定则均已形成闭环。105 条正区二维记录没有出现 alpha>0 的可验收尺寸 crossing，因此不继续扩大相图，转向补齐动力学谱证据。",
            },
            {
                "kind": "kv",
                "pairs": [
                    ["推荐首个生产点", "alpha=0.23, beta=0.5, L=80, q=pi, eta=0.1 的可恢复 correction-vector DMRG"],
                    ["选择原因", "已有 L=10 精确 oracle、L=20 收敛序列和 L=40 TEBD pilot；它是正侧动力学路径中心点"],
                    ["相图现状", "105 条正区记录完整，无 alpha>0 内部显著 crossing；不命名相界"],
                    ["当前完成度", "核心科学内容约 50%；投稿级完整度约 35%；Fig. 6--8 的生产动力学是主要缺口"],
                    ["服务器纪律", "直连服务器一次一个重任务，离线环境，不下载新包；逐点 checkpoint、回传与 SHA-256 校验"],
                ],
            },
            {
                "kind": "table",
                "columns": ["日期", "计算", "写作/作图", "门槛"],
                "rows": [
                    ["8/02", "审计 checkpoint、Manifest、磁盘与负载", "锁定论文骨架、证据矩阵和图表输入", "只建新 run，不触碰已有结果"],
                    ["8/03", "L=10 恢复 oracle；L=40 三个相邻频率 warm-start", "Fig. 1、2、5 正式排版", "恢复一致，CV 残差 <=1e-5"],
                    ["8/04", "L=80 单点冷启动和恢复；TEBD dt/2", "写模型与方法", "方差/L <=1e-8，内存 <64 GiB"],
                    ["8/05--8/06", "通过成本门槛后做 L=80 小窗口；TEBD tmax=20", "Fig. 3、4 定稿", "TEBD dt 与时间窗均收敛"],
                    ["8/07", "CV/TEBD 同点交叉检查；必要时一枚第二 alpha 锚点", "动力学图和理论叠加候选版", "峰位差 <=0.1，权重差 <=15%"],
                    ["8/08", "复核高误差 mesh-cell-0051", "补 Results、Discussion、图注", "复核不影响主结论"],
                    ["8/09", "只恢复失败最小单元", "全文、参考文献、补充材料审阅版", "主图可回溯到原始数据"],
                    ["8/10", "不启动新扫描", "编译、图像 QA、归档与交付", "未通过谱降为补充材料"],
                ],
                "widths": ["12%", "34%", "30%", "24%"],
            },
            {
                "kind": "list",
                "title": "两道不可跳过的计算决策门",
                "items": [
                    "8/03：仅当 L=40 checkpoint 恢复正确，且相邻频率的中位求解时间不高于冷启动 60%，才进入 L=80 小窗口。",
                    "8/04：仅当 L=80 单点可恢复、残差和方差通过，且恢复后频点预计不超过 4 小时、内存低于 64 GiB，才扩展频率块。",
                    "8/07：正文动态结论必须同时通过 CV 残差、非负性、镜像动量、TEBD dt/tmax 和 CV/TEBD 交叉检查。",
                ],
            },
            {
                "kind": "note",
                "label": "降级原则",
                "style": "pending",
                "text": "若 L=80 CV 的实际成本不满足门槛，8 月 10 日仍交付完整初稿，但动态主图限定为通过收敛验收的 L=40 TEBD/CV 与少量 L=80 锚点。不会为了日期生成未收敛的完整谱面，或把缺原始数据的旧热图写成生产证据。",
            },
            {
                "kind": "code",
                "title": "完整可编辑计划",
                "text": "docs/delivery_plan_to_20260810.md\ndocs/pentamer_reproduction_standard.md\ndocs/claim_evidence_matrix.md\ndocs/figure_plan.md",
            },
        ],
    }


def main() -> None:
    report = load(REPORT)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-02"
    sections = [item for item in report["sections"] if item["title"] != TITLE]
    index = next((i for i, item in enumerate(sections) if item["title"] == "模型与激发机制正式图"), 1)
    sections.insert(index, build_section())
    report["sections"] = sections
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
