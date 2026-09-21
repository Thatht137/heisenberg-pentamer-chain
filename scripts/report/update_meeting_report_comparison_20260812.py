"""扩展汇报页，加入论文与五聚体逐图对照。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/meeting_report_20260812/report.json"


def comparison_section() -> dict:
    return {
        "title": "论文原图与 1×5 结果逐图对照",
        "note": "左侧为参考论文四聚体结果，右侧为本项目真实数据图。右图统一采用参考论文的 Times/STIX 字体、黑蓝细线、灰色单胞示意和 jet 动力学色标；物理量或参数路径不相同时仍明确标注。",
        "blocks": [
            {
                "kind": "table",
                "columns": ["论文图", "对应级别", "1×5 状态", "可以下的结论"],
                "rows": [
                    ["Fig. 1", "同类诊断", "已修正", "五聚体末端键已恢复为 $J_2=α$；正区留下 $S=1/2$ 双重态。"],
                    ["Fig. 2", "同类诊断", "已重绘", "完整 $α∈[-1,1]$ 显示基态在 $α=0$ 两侧由 $S=3/2$ 切换为 $S=1/2$。"],
                    ["Fig. 3", "同类诊断", "高密度 + 严格网格", "正 α 区弦序纹理连续，严格 R 诊断目前无额外相界证据。"],
                    ["Fig. 4", "同类诊断", "正区完成", "五切口纠缠谱结构清晰，matched-size 校准与 $c=1$ 的偏差不超过 3.31%。"],
                    ["Fig. 5", "机制替代", "有效链完成", "五聚体低能对象是未淬灭的有效 $S=1/2$，并受动量选择定则过滤。"],
                    ["Fig. 6", "参数直接对齐", "探索性", "参数布局与论文一致；可看谱权重重排，不能据此给最终线宽或谱支命名。"],
                    ["Fig. 7", "角色对应", "pilot", "使用不同参数路径，只能说明正 α 代表点对 α 的响应。"],
                    ["Fig. 8", "方法替代", "代表点验收", "证明 $q=π$ 代表点 CV 与 TEBD 一致，不等于完成论文式全 q 色散叠加。"],
                ],
                "widths": ["10%", "23%", "17%", "50%"],
            },
            {
                "kind": "card",
                "title": "Fig. 1｜模型与局域多重态",
                "blocks": [
                    {
                        "kind": "figures",
                        "items": [
                            {"src": "assets/paper_fig1.png", "caption": "参考论文 Fig. 1：四聚体键序与单胞 singlet/triplet/quintet 多重态。"},
                            {"src": "assets/ours_fig1.png", "caption": "1×5 同类诊断（论文风格重绘）：每个五聚体的键序为 $α,1,1,α$，胞间键为 $β$；下图按参考 Fig.1 的能级线与灰色局域态语言排列 α=0.23 多重态。"},
                        ],
                    },
                    {
                        "kind": "text",
                        "text": "共同点是先用单胞 ED 确定局域自由度；决定性差别是偶数四聚体可以形成整数总自旋，而奇数五聚体必留半整数总自旋。正区五聚体基态为 $S=1/2$，这直接预示长链低能行为不会复制四聚体。",
                    },
                    {"kind": "verdict", "status": "good", "label": "图形错误已修正", "why": "旧图把五聚体第 4–5 位之间的 $J_2$ 键误画为 $J_1$；当前图与哈密顿量一致。"},
                ],
            },
            {
                "kind": "card",
                "title": "Fig. 2｜单胞能级流与可见通道",
                "blocks": [
                    {
                        "kind": "figures",
                        "items": [
                            {"src": "assets/paper_fig2.png", "caption": "参考论文 Fig. 2：四聚体能级随 α 变化，并给出 α=0 的二聚体极限。"},
                            {"src": "assets/ours_fig2.png", "caption": "1×5 同类诊断（论文风格重绘）：上图用论文蓝色细线展示 101 个 α 点的完整单胞能级；下图给出正 α 的 $q=π$ 通道权重。"},
                        ],
                    },
                    {
                        "kind": "text",
                        "text": "完整 α 范围显示一个不能省略的局域交叉：α<0 时最低多重态为 $S=3/2$，α>0 时为 $S=1/2$，α=0 两者简并。$q=π$ 权重目前只在正 α 做了反射宇称分类，因此右图不向负 α 外推。",
                    },
                    {"kind": "verdict", "status": "good", "label": "参数覆盖已补全", "why": "能级图已从原来的正 α 局部扫描扩展为 $[-1,1]$；动量选择定则仍明确限定在正 α。"},
                ],
            },
            {
                "kind": "card",
                "title": "Fig. 3｜二维静态诊断",
                "blocks": [
                    {
                        "kind": "figures",
                        "items": [
                            {"src": "assets/paper_fig3.png", "caption": "参考论文 Fig. 3：弦序热图、参数切片与三类基态示意，据此划分四聚体相区。"},
                            {"src": "assets/ours_fig3_paper_palette.png", "caption": "1×5 同类诊断（论文布局与 jet 配色）：左侧为 40×60 的 $O_{str}$ 热图，右侧依次为 β/α 切片与 $R_{60}-R_{40}$ 有限尺寸流。"},
                        ],
                    },
                    {
                        "kind": "text",
                        "text": "左上图使用 40 个正 α 点 × 60 个 β 点的真实弦序数据，负责展示二维纹理；另外 5×7×3=105 条严格记录负责有限尺寸判断。两类证据分工不同：高密度 $O_{str}$ 图可显示连续色带，但等高线不是相界；R 的尺寸差没有稳定显著交叉，因此当前不支持在正区命名额外相界。",
                    },
                    {"kind": "verdict", "status": "warn", "label": "完成度：高密度展示已恢复", "why": "40×60 弦序图与 L=40/60/80 严格诊断同时保留；前者是探索性纹理，后者承担相界验收。"},
                ],
            },
            {
                "kind": "card",
                "title": "Fig. 4｜纠缠谱",
                "blocks": [
                    {
                        "kind": "figures",
                        "items": [
                            {"src": "assets/paper_fig4.png", "caption": "参考论文 Fig. 4：Schmidt 权重随 α、β 的变化，偶重简并用于辅助识别 Haldane 区。"},
                            {"src": "assets/ours_fig4.png", "caption": "1×5 同类诊断（参考 Fig.4 的黑色短线/圆点语言）：两行分别为 α=0.14/0.33、β=0.5、L=80 的五种切口 Schmidt 谱。"},
                        ],
                    },
                    {
                        "kind": "text",
                        "text": "论文沿两种键切分；1×5 一个单胞内部有五种不等价切口，因此必须逐切口查看。结果显示清晰的多重简并簇，但奇数单胞本身改变了边缘自由度与平移结构，不能仅凭“偶重简并”把正区称为四聚体式 Haldane 相。",
                    },
                    {"kind": "verdict", "status": "warn", "label": "同类诊断，不是同一扫描", "why": "论文画 Schmidt 权重随 α/β 变化；本图画两个代表点的五切口谱，并用 matched-size 方法校准 $c≈1$。"},
                ],
            },
            {
                "kind": "card",
                "title": "Fig. 5｜激发机制与有效自由度",
                "blocks": [
                    {
                        "kind": "figures",
                        "items": [
                            {"src": "assets/paper_fig5.png", "caption": "参考论文 Fig. 5：局域高能激发与缺陷沿四聚体链传播的示意。"},
                            {"src": "assets/ours_fig5.png", "caption": "1×5 机制替代图（参考 Fig.5 的时序示意语言）：灰色五聚体与红/蓝箭头表示有效自由度、亮暗通道及 $q=π$ 选择规则。"},
                        ],
                    },
                    {
                        "kind": "text",
                        "text": "四聚体论文以局域 triplon/quarton/quinton 传播组织高能谱；五聚体最低能过程首先是每胞未淬灭 $S=1/2$ 的集体传播。项目进一步算得 α=0.23 时 $(c_1,c_2,c_3,c_4,c_5)≈(0.657,-0.248,0.182,-0.248,0.657)$，因此 $c_1c_5>0$ 且胞间有效耦合为反铁磁。",
                    },
                    {"kind": "verdict", "status": "good", "label": "机制已建立，但不是原图复刻", "why": "这里回答五聚体中什么自由度传播；没有把四聚体 triplon/quarton/quinton 示意机械替换。"},
                ],
            },
            {
                "kind": "card",
                "title": "Fig. 6｜跨 β 的动力学结构因子",
                "blocks": [
                    {
                        "kind": "figures",
                        "items": [
                            {"src": "assets/paper_fig6.png", "caption": "参考论文 Fig. 6：α=±1、β=1.0/0.7/0.4/0.1 的 $S^{zz}(q,ω)$，展示连续谱向分离能带的演化。"},
                            {"src": "assets/ours_fig6_paper_palette.png", "caption": "1×5 对应图：相同 α=±1 与 β 路径的原始 TEBD 网格；蓝—青—黄—红色标与论文一致，未平滑、未裁剪。"},
                        ],
                    },
                    {
                        "kind": "text",
                        "text": "这是整组中参数路径最接近论文的一张：α=±1，β=1.0/0.7/0.4/0.1 一一对应。正 α、β=1 时可见从 q=π 闭合的低能连续体；减小 β 后谱权重排为更平坦的能带。负 α 行则呈现不同的低能动量结构。",
                    },
                    {"kind": "verdict", "status": "warn", "label": "完成度：探索性", "why": "原始 TEBD 数据可用于看趋势，但尚未逐参数完成时间步、最大时间和 CV 的生产级交叉验收。"},
                ],
            },
            {
                "kind": "card",
                "title": "Fig. 7｜参数路径谱与 q=π 切片",
                "blocks": [
                    {
                        "kind": "figures",
                        "items": [
                            {"src": "assets/paper_fig7.png", "caption": "参考论文 Fig. 7：固定负 α，扫描 β 穿越相界附近的低能与高能谱权变化。"},
                            {"src": "assets/ours_fig7_paper_palette.png", "caption": "1×5 对应图：固定 β=0.5，沿正 α=0.14/0.23/0.33 扫描；上排为全 q 谱，下排为 $q=π$ 频率切片。"},
                        ],
                    },
                    {
                        "kind": "text",
                        "text": "五聚体路径选择围绕代表性正区点，用来检验有效链连续谱对 α 的响应。三点都保留约 ω/J₁≈0.5–0.7 的主带；α 增大时 q=π 附近的低频峰权增强，并伴随较弱高能通道。该趋势可以讲，但谱峰命名仍需结合局域多重态和收敛 CV。",
                    },
                    {"kind": "verdict", "status": "warn", "label": "仅角色对应，不是同一路径", "why": "论文固定负 α 扫 β；本图固定 β=0.5 扫正 α，且为 L=40、tmax=15 pilot。"},
                ],
            },
            {
                "kind": "card",
                "title": "Fig. 8｜理论分支叠加与跨方法验收",
                "blocks": [
                    {
                        "kind": "figures",
                        "items": [
                            {"src": "assets/paper_fig8.png", "caption": "参考论文 Fig. 8：在 DSF 上叠加 spinon、triplon 与 quinton 的解析或微扰色散。"},
                            {"src": "assets/ours_fig8.png", "caption": "1×5 当前最强动力学验收：α=0.23、β=0.5、L=40、q=π，11 个 accepted CV 点与 TEBD 曲线比较；下图为相对差异。"},
                        ],
                    },
                    {
                        "kind": "text",
                        "text": "当前没有把五聚体高能谱支全部命名后再叠加，而是先完成更严格的局部数值验收：11 个 CV 点覆盖低频窗口，CV 与 TEBD 的最大相对差异为 6.40%，峰位 bracket、积分权重窗口、峰值预算和权重预算四项均通过。",
                    },
                    {"kind": "verdict", "status": "good", "label": "代表点方法验收通过", "why": "该点已有 source hash、QA 清单和跨方法检查；图的用途是验证数值可信度，不是替代论文式全 q 理论分支叠加。"},
                ],
            },
            {
                "kind": "note",
                "label": "Fig. 9 范围说明",
                "text": "参考论文 Fig. 9 讨论 CuInVO₅ 的直接/间接 RIXS 与双自旋过程。当前 1×5 项目实现的是单自旋 DSF、CV 和 TEBD，没有材料专属参数与 K-edge 双自旋 RIXS 算符，因此不制作伪对应图。",
                "style": "pending",
            },
        ],
    }


def main() -> None:
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    document["title"] = "1×5 Heisenberg 五聚体链：项目总结与论文逐图对照"
    document["lede"] = "本页总结 1×5 Heisenberg 五聚体链的模型、数值方法和主要结果，并将参考四聚体论文 Fig. 1–8 与真实 1×5 数据生成的对应图逐项比较。核心结论是：研究框架已完整迁移，但奇数单胞保留半整数低能自由度，使正耦合区由有效 S=1/2 反铁磁链控制；完整负区相图和全 q 生产级动力学谱仍在收敛。"
    for section in document["sections"]:
        if section["title"] == "一页结论":
            for block in section["blocks"]:
                if block.get("kind") == "table" and block.get("columns") == ["问题", "当前答案"]:
                    block["rows"] = [row for row in block["rows"] if "老师" not in row[0]]
                    for row in block["rows"]:
                        if row[0] == "还缺什么？":
                            row[1] = "负区多 beta 相图、全 q 生产级 DSF，以及更加严格的有限尺寸和跨方法验收；代表点 q=π 已完成 CV–TEBD 验收。"
        if section["title"] == "研究目标与参考关系":
            section["note"] = "核心不是机械改写 4 为 5，而是检验单胞奇偶性改变后，论文方法和物理结论分别哪些可以继承。"
        if section["title"] == "明天可直接使用的讲稿":
            section["title"] = "可直接使用的汇报讲稿"
            section["note"] = "建议用 3–5 分钟讲完主线，追问时再展开逐图对照和参数。"
        if section["title"] == "当前完成度与下一步":
            for block in section["blocks"]:
                if block.get("kind") == "table" and block.get("columns") == ["工作项", "状态", "汇报时怎么说"]:
                    block["rows"] = [row for row in block["rows"] if row[0] != "生产级长链 DSF"]
                    block["rows"].extend(
                        [
                            ["代表点 q=π 动力学", "已闭环", "α=0.23、β=0.5、L=40 上 11 个 CV 点与 TEBD 通过四项验收。"],
                            ["全 q、全参数生产级 DSF", "未完全闭环", "仍需尺寸、时间步、频率和跨方法收敛。"],
                        ]
                    )
        if section["title"] == "可直接使用的汇报讲稿":
            for block in section["blocks"]:
                if block.get("kind") == "text" and "生产级长链 DSF" in block.get("text", ""):
                    block["text"] = "因此目前项目已经完成了方法迁移、正耦合区的物理闭环和一个代表点的 CV–TEBD 动力学验收；下一步是完成负区多 β 相图以及全 q、全参数的生产级 DSF，最终再判断五聚体是否存在真正独立的临界相边界。"
    document["sections"] = [section for section in document["sections"] if section["title"] != "论文原图与 1×5 结果逐图对照"]
    insert_index = next(index for index, section in enumerate(document["sections"]) if section["title"] == "当前完成度与下一步")
    document["sections"].insert(insert_index, comparison_section())
    REPORT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
