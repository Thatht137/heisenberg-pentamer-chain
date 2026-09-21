#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成可独立审阅的 bounded manuscript HTML。"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
from datetime import datetime
from pathlib import Path


FIGURES = [
    ("fig1", "paper_fig1_model_local_multiplets_20260804.png"),
    ("fig2", "paper_fig2_level_flow_qpi_filter_20260804.png"),
    ("fig3", "paper_fig3_positive_groundstate_diagnostics_20260804.png"),
    ("fig4", "paper_fig4_entanglement_spectrum_20260804.png"),
    ("fig5", "paper_fig5_effective_chain_selection_rules_20260804.png"),
    ("fig8", "paper_fig8_bounded_cv_tebd_20260805.png"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.source_root.resolve()
    output = args.output.resolve()
    paths = {key: root / "figures" / name for key, name in FIGURES}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("缺少图件: " + ", ".join(missing))
    images = {key: image_uri(path) for key, path in paths.items()}
    updated = datetime.now().astimezone().isoformat(timespec="minutes")

    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>正耦合自旋 1/2 五聚体 Heisenberg 链 · bounded manuscript</title>
<style>
:root{{--ink:#1c232b;--muted:#5d6772;--line:#d8dde3;--paper:#fff;--back:#f3f5f7;--blue:#175d8f;--green:#17715a;--amber:#9a5b09;--red:#a33838}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--back);color:var(--ink);font:16px/1.72 "Segoe UI","Microsoft YaHei",Arial,sans-serif;letter-spacing:0}}
.layout{{display:grid;grid-template-columns:240px minmax(0,900px);gap:36px;max-width:1220px;margin:0 auto;padding:26px 28px 80px}}
aside{{position:sticky;top:20px;align-self:start;max-height:calc(100vh - 40px);overflow:auto;border-right:1px solid var(--line);padding-right:22px}}
aside .label{{font-size:12px;text-transform:uppercase;color:var(--muted);font-weight:700;margin-bottom:10px}}aside a{{display:block;color:#35414d;text-decoration:none;padding:6px 0;font-size:13px}}aside a:hover{{color:var(--blue)}}
main{{background:var(--paper);border:1px solid var(--line);padding:56px 70px;box-shadow:0 8px 24px #1f29370b}}
.eyebrow{{font-size:12px;color:var(--blue);font-weight:700;text-transform:uppercase}}h1{{font-size:34px;line-height:1.25;margin:12px 0 10px;font-weight:700}}.subtitle{{font-size:18px;color:var(--muted);margin:0 0 28px}}
.status{{display:grid;grid-template-columns:repeat(3,1fr);border-top:3px solid var(--green);border-bottom:1px solid var(--line);margin:24px 0 38px}}.status div{{padding:14px 12px;border-right:1px solid var(--line)}}.status div:last-child{{border-right:0}}.status b{{display:block;font-size:18px}}.status span{{font-size:12px;color:var(--muted)}}
h2{{font-size:24px;margin:52px 0 16px;padding-top:8px;border-top:1px solid var(--line)}}h3{{font-size:19px;margin:34px 0 10px;color:#263b4d}}p{{margin:0 0 16px}}.lead{{font-size:18px;line-height:1.78}}.equation{{font-family:Cambria Math,"Times New Roman",serif;text-align:center;padding:13px;background:#f8fafb;border-left:3px solid var(--blue);margin:20px 0}}
.boundary{{border-left:4px solid var(--amber);background:#fff8ec;padding:14px 18px;margin:22px 0}}.supported{{border-left:4px solid var(--green);background:#f1faf7;padding:14px 18px;margin:22px 0}}.boundary b,.supported b{{display:block;margin-bottom:4px}}
figure{{margin:30px 0 38px}}figure img{{display:block;width:100%;height:auto;border:1px solid var(--line)}}figcaption{{font-size:13px;color:#4d5965;line-height:1.55;margin-top:10px}}
table{{width:100%;border-collapse:collapse;margin:20px 0 30px;font-size:13px}}th,td{{border-bottom:1px solid var(--line);padding:10px 9px;vertical-align:top;text-align:left}}th{{background:#f4f7f9;color:#31404d}}.pass{{color:var(--green);font-weight:700}}.bounded{{color:var(--amber);font-weight:700}}.pending{{color:var(--red);font-weight:700}}
ul,ol{{padding-left:22px}}li{{margin:7px 0}}code{{font:13px Consolas,monospace;background:#f1f3f5;padding:2px 4px}}.meta{{font-size:12px;color:var(--muted)}}
.references p{{padding-left:24px;text-indent:-24px;font-size:14px}}footer{{border-top:1px solid var(--line);margin-top:54px;padding-top:18px;color:var(--muted);font-size:12px}}
@media(max-width:900px){{.layout{{display:block;padding:0}}aside{{position:relative;top:0;max-height:none;border:0;border-bottom:1px solid var(--line);padding:16px 22px;background:#fff}}aside a{{display:inline-block;margin-right:14px}}main{{border:0;padding:34px 22px;box-shadow:none}}h1{{font-size:28px}}.status{{grid-template-columns:1fr}}.status div{{border-right:0;border-bottom:1px solid var(--line)}}}}
@media print{{body{{background:#fff}}.layout{{display:block;max-width:none;padding:0}}aside{{display:none}}main{{border:0;box-shadow:none;padding:0}}figure{{break-inside:avoid}}h2,h3{{break-after:avoid}}}}
</style>
</head>
<body>
<div class="layout">
<aside>
  <div class="label">Bounded manuscript</div>
  <a href="#abstract">摘要</a><a href="#intro">1 引言</a><a href="#methods">2 模型与方法</a>
  <a href="#results">3 结果</a><a href="#discussion">4 讨论</a><a href="#conclusion">5 结论</a>
  <a href="#compute-status">计算状态</a><a href="#claims">论断—证据表</a><a href="#missing">待作者确认</a><a href="#references">参考文献</a>
</aside>
<main>
<header>
  <div class="eyebrow">Author review draft · bounded evidence · updated {html.escape(updated)}</div>
  <h1>正耦合自旋 1/2 五聚体 Heisenberg 链中的有效自旋链与动量选择激发</h1>
  <p class="subtitle">不含负 alpha，不复现参考 Fig.9；本文档不修改 paper/</p>
  <div class="status">
    <div><b>12/12</b><span>论断 supported 或 bounded</span></div>
    <div><b>10/10</b><span>bounded 交付门</span></div>
    <div><b>8/9</b><span>production 动态门</span></div>
  </div>
</header>

<section id="abstract">
<h2>摘要</h2>
<p class="lead">本文研究正耦合区间 <i>0 ≤ alpha,beta ≤ 1</i> 内具有五站点单胞的一维自旋 1/2 Heisenberg 链。孤立五聚体的奇数自旋数使基态保留有效 <i>S=1/2</i> 双重态，正胞间耦合在一阶投影中产生反铁磁有效 Heisenberg 链。局域精确对角化、两与三单胞有效哈密顿量、有限链密度矩阵重整化群和纠缠谱共同支持这一低能图景：<i>J</i><sub>eff</sub>/beta 位于 0.4189–0.4396，二阶虚过程产生弱反铁磁 <i>J</i><sub>2</sub>/<i>J</i><sub>1</sub>=3.95%–5.19%，同尺寸 Heisenberg oracle 校准后的三个纠缠估计量为 1.024–1.033。反射宇称还使最低激发双重态在 <i>q=pi</i> 通道变暗，而 <i>S=3/2</i> 四重态承载 84.1%–97.6% 的局域非弹性谱权。七个已验收 correction-vector 点与独立 TEBD 在共享窗内的最大逐点差为 6.40%，积分权重差为 1.53%；然而 CV 网格尚未包围位于 omega≈0.05 的 TEBD 主峰，因此完整动态比较保持 NotEvaluable。本文据此建立五聚体链的有效低能机制和局域选择定则，但不把有限尺寸结果表述为完整二维相图或热力学极限单相证明。</p>
</section>

<section id="intro">
<h2>1 引言</h2>
<p>团簇化自旋链把局域多重态、胞间交换、量子临界性和动力学结构因子联系在同一可控模型中。Li 等对四聚体链的研究展示了以单胞能级、弦关联、纠缠结构和自旋激发谱组织证据的路线。然而，五聚体单胞包含奇数个自旋 1/2，其低能总自旋不能按偶数单胞的单重态图景直接类推；四聚体中的相名、弦算符端点和准粒子命名也不能机械移植。</p>
<p>本文考虑胞内耦合 <i>J</i><sub>1</sub>、<i>J</i><sub>2</sub> 与胞间耦合 <i>J</i><sub>3</sub>，定义 alpha=<i>J</i><sub>2</sub>/<i>J</i><sub>1</sub>、beta=<i>J</i><sub>3</sub>/<i>J</i><sub>1</sub>，并把范围严格限制为 <i>0 ≤ alpha,beta ≤ 1</i>。研究问题不是将 1×4 图像平移到 1×5，而是确定奇数单胞留下的有效自由度、这些自由度之间的交换，以及局域对称性如何限制长链动力学的可见通道。</p>
<p>为回答这些问题，我们先完整对角化孤立五聚体并建立低能投影，再用两、三单胞精确谱验证一阶与二阶有效哈密顿量；随后以多尺寸 DMRG、双初态和同尺寸 <i>c=1</i> Heisenberg oracle 约束有限链解释；最后用 correction-vector DMRG 与 TEBD 对 <i>S</i><sup>zz</sup>(<i>q</i>,omega) 做独立交叉检查。每一层结论均由固定的 residual、方差、截断误差、checksum 和覆盖门控制。</p>
<div class="boundary"><b>本文边界</b>负 alpha 与参考论文 Fig.9 永久排除；未通过验收的低频 CV 点不进入 accepted-only 结果；有限尺寸无 crossing 不等同于热力学极限无相变。</div>
</section>

<section id="methods">
<h2>2 模型与数值方法</h2>
<h3>2.1 五聚体链与低能投影</h3>
<p>每个单胞含五个自旋 1/2。<i>J</i><sub>1</sub> 设定能量单位，alpha 控制胞内交替键，beta 控制相邻五聚体之间的交换。孤立单胞按总自旋和反射宇称标记多重态，并计算 <i>q=pi</i> 局域自旋算符在各多重态之间的矩阵元。</p>
<div class="equation"><i>P S</i><sub>n,r</sub><i> P = c</i><sub>r</sub><i> T</i><sub>n</sub>，&nbsp;&nbsp;<i>J</i><sub>eff</sub>=beta <i>J</i><sub>1</sub><i> c</i><sub>5</sub><i>c</i><sub>1</sub></div>
<p>其中 <i>P</i> 投影到五聚体最低 <i>S=1/2</i> 双重态，<i>T</i><sub>n</sub> 是单胞有效自旋。二阶 Schrieffer–Wolff 虚过程进一步生成最近邻修正与次近邻 <i>J</i><sub>2</sub>，其系数由两、三单胞低能谱和算符拟合共同确定。</p>

<h3>2.2 有限链 DMRG 与静态验收</h3>
<p>开放边界链使用双初态 DMRG，并按 <i>L=40,60,80</i> 晋级。每个点保存能量、方差、最大截断误差、实际键维和目标观测量。内部 crossing 只有在尺寸差形成稳定符号 bracket 并通过 2sigma 预算后才成立。纠缠标度不直接采用受五站点振荡影响的裸 log-<i>L</i> 拟合，而与相同边界和有效单胞数的已知 <i>c=1</i> Heisenberg 链比较。</p>

<h3>2.3 动力学与交叉验收</h3>
<p>correction-vector DMRG 在 <i>q=pi</i>、eta=0.1 下逐频点求解线性系统，每个频点要求 relative residual ≤1e-5；方差、截断误差、谱非负性和 checksum 同时通过后，run 才能进入 accepted-only 组装。TEBD 独立检查时间步长、总演化时间、最大键维和 Fourier 变换。只有 CV 网格包围 TEBD 主峰并覆盖 [0,1.5] 主要积分窗，峰位与积分权重门才具有可评价性。</p>
</section>

<section id="results">
<h2>3 结果</h2>
<h3>3.1 奇数单胞留下有效 S=1/2</h3>
<p>在整个正 alpha 扫描中，孤立五聚体基态保持偶反射宇称的 <i>S=1/2</i> 双重态。投影系数给出 <i>J</i><sub>eff</sub>/beta=0.4189–0.4396，符号始终为正。因此正 beta 不是在单重态单胞之间传播局域三重态，而是直接反铁磁耦合未淬灭的有效自旋 1/2。</p>
<figure><img src="{images['fig1']}" alt="五聚体模型、低能投影与局域多重态"><figcaption><b>图 1 | 五聚体模型、低能投影与局域多重态。</b> 单胞基态双重态投影为有效自旋，圆面积表示 <i>q=pi</i> 局域谱权。本图只支持局域 ED 与一阶有效链，不命名热力学相。</figcaption></figure>

<h3>3.2 动量选择定则与二阶弱挫折</h3>
<p>最低激发双重态虽然在能量上接近基态，却因反射宇称在 <i>q=pi</i> 通道严格变暗。相反，<i>S=3/2</i> 四重态贡献 84.1%–97.6% 的局域非弹性权重。二阶虚激发同时产生反铁磁次近邻项；在受控参数边缘，<i>J</i><sub>2</sub>/<i>J</i><sub>1</sub>=3.95%–5.19%。加入该项后，两与三单胞低能谱的首个系统误差由 <i>O</i>(beta<sup>2</sup>) 推迟到 <i>O</i>(beta<sup>3</sup>)。</p>
<figure><img src="{images['fig2']}" alt="能级流与 q=pi 动量过滤"><figcaption><b>图 2 | 正 alpha 能级流和 q=pi 通道权重。</b> 最低激发双重态被宇称过滤，四重态主导可见局域谱权。</figcaption></figure>
<figure><img src="{images['fig5']}" alt="有效链、二阶交换与选择定则"><figcaption><b>图 5 | 有效链、二阶交换与局域选择定则的统一机制。</b> 图中不引入未经 production DSF 验证的准粒子名称。</figcaption></figure>

<h3>3.3 正耦合有限尺寸数据未见可验收 crossing</h3>
<p>正区扫描共有 105 条成功记录。<i>L=40,60,80</i> 的尺寸差没有形成满足验收规则的稳定符号 bracket，因此当前数据不支持额外命名内部相界。该否定结果与有效反铁磁链图景一致，但也可能受到有限尺寸、观测量灵敏度和网格分辨率限制。最弱高预算控制点 alpha=0.125、beta=1、<i>L=80</i> 仍表现出 1.79096e-3 的双初态半差，高于 1e-3 预算。</p>
<figure><img src="{images['fig3']}" alt="正区有限尺寸基态诊断"><figcaption><b>图 3 | 正耦合区的有限尺寸诊断。</b> 热图、代表切片和尺寸差均未给出可验收内部 crossing；本图不是热力学相图证明。</figcaption></figure>
<p>同尺寸 Heisenberg oracle 校准后的三个纠缠估计量为 1.024–1.033，与 <i>c=1</i> 相差不超过 3.31%。在最大有效单胞数上，扣除非普适常数偏移后的熵剖面 RMS 差为 0.002048；键维从 80 增至 400 时中心熵最大相对变化为 0.0240%。这些结果支持有限尺寸上的 <i>c=1</i> 有效链结构，但裸 log-<i>L</i> 拟合的较大 chi<sup>2</sup>/dof 阻止无偏热力学外推。</p>
<figure><img src="{images['fig4']}" alt="纠缠谱与 c=1 oracle"><figcaption><b>图 4 | 五类切口纠缠谱和 matched-size c=1 oracle。</b> 校准比值接近 1，但结论严格限定于当前有限尺寸。</figcaption></figure>

<h3>3.4 动力学局部一致，但总体仍不可评价</h3>
<p>correction-vector 实现在 <i>L=10</i> 精确 oracle 上达到 8.52e-12 的相对 L2 误差，说明实现本身不是当前瓶颈。严格 <i>q=pi</i> TEBD 的主峰位于 omega≈0.05，并通过时间步长、总时长、最大键维与 Fourier 复算。七个 accepted CV 点 omega=0.20、0.25、0.30、0.35、0.55、1.00、1.50 与 TEBD 的最大逐点差为 6.40%，共享窗积分权重差为 1.53%。</p>
<p>但是，accepted CV 网格左端仍为 0.20，未包围低频主峰，也未从 0 覆盖完整 [0,1.5] 窗。两次独立 omega=0.05 计算都正常退出，residual 分别为 1.17068e-5 和 1.17670e-5，超过固定门槛 1e-5。因此这些结果只能支持“共享频点和共享窗内数值接近”，不能升级为完整谱 Agreement。</p>
<figure><img src="{images['fig8']}" alt="七点 CV 与 TEBD bounded 比较"><figcaption><b>图 8 | bounded CV–TEBD 比较。</b> 七个通过验收的 CV 点与 TEBD 曲线在共享区域接近；失败的 omega=0.05 点只作诊断标记，不进入定量组装。低频主峰未被包围，因此总体标签保持 NotEvaluable。</figcaption></figure>
<div class="boundary"><b>Production 动态门：8/9</b>缺失项不是绘图，而是通过 residual 的低频网格覆盖。新 round43 只改变 warm-start 顺序和数值截断精度，不降低门槛。</div>
</section>

<section id="discussion">
<h2>4 讨论</h2>
<p>五聚体与四聚体之间的核心差异来自单胞自旋数的奇偶性。偶数单胞可形成整数总自旋或局域单重态，而五个自旋 1/2 必然留下半整数低能自由度。正 beta 因而自然产生反铁磁有效自旋链，这解释了有限尺寸纠缠结果为何接近 <i>c=1</i> Heisenberg oracle，也解释了为什么不能直接沿用四聚体相图的命名。</p>
<p>高能谱权则由另一层结构控制。局域多重态的总自旋和反射宇称决定某个激发是否能被 <i>q=pi</i> 自旋算符看到。最低激发并不必然是最强谱支；本模型中最低双重态被过滤，四重态反而主导局域权重。二阶反铁磁 <i>J</i><sub>2</sub> 进一步表明五聚体内部虚过程会在有效链中留下弱挫折，但当前 3.95%–5.19% 的受控比值不足以单独建立新相或新准粒子。</p>
<p>正区未见 crossing 有两种竞争解释：其一，整个已扫描区域属于同一低能有效链机制；其二，有限尺寸、观测量或网格尚不足以分辨较弱边界。双初态控制点的残余敏感性使第二种解释不能被排除。因此本文采用“当前有限尺寸数据未见可验收 crossing”，而不采用“热力学极限只有一个相”。</p>
<p>动力学方面，CV 精确 oracle 和 TEBD 内部收敛均已通过，七点共享窗也显示数值接近；唯一实质缺口是低频 CV 条件数增大后 residual 尚未过门。新的降频 warm-start 计算可以关闭该门，但在终态回传、checksum 和 validator 之前，不改变本文的 bounded 表述。</p>
</section>

<section id="conclusion">
<h2>5 结论</h2>
<p>本研究建立了正耦合自旋 1/2 五聚体链的有边界数值图景。孤立五聚体保留有效 <i>S=1/2</i> 双重态，正胞间交换产生反铁磁有效链；局域宇称在 <i>q=pi</i> 通道过滤最低双重态，并使四重态承担主要非弹性谱权；二阶虚过程生成弱反铁磁次近邻交换。多尺寸 DMRG 和 matched-size oracle 在有限尺寸上支持 <i>c=1</i> 低能结构，且当前正区扫描未发现可验收内部 crossing。七点 CV 与 TEBD 在共享窗内一致，但低频主峰覆盖尚未闭合。因此本文的可靠结论是有效链机制、局域选择定则和弱二阶挫折，而不是完整二维相图、热力学单相证明或 production 动态谱归属。</p>
</section>

<section id="compute-status">
<h2>计算状态与预注册分流</h2>
<div class="boundary"><b>当前状态</b>round43 阶段 A 已完成，远端 checksum 与 omega=0.20、0.15、0.10、0.05 四点 residual 均通过。阶段 B 已于 2026-08-06 15:36 CST 从 checkpoint 启动，只计算 omega=0.00；终态交接前不进入本文任何定量论断。</div>
<table>
<thead><tr><th>终态证据</th><th>自动处理</th><th>允许的结论等级</th></tr></thead>
<tbody>
<tr><td>validator、checksum 或任一 residual 失败</td><td>停止；禁止 accepted-only 组装</td><td class="bounded">bounded / NotEvaluable</td></tr>
<tr><td>五点不完整或频率不是 0.00–0.20</td><td>停止；保留失败审计</td><td class="bounded">bounded / NotEvaluable</td></tr>
<tr><td>11 点组装后覆盖门不足</td><td>生成交叉分析但不升级</td><td class="bounded">bounded / NotEvaluable</td></tr>
<tr><td>覆盖、峰位和积分权重门全部通过</td><td>production_ready=true</td><td class="pass">允许审阅 production 动态结论</td></tr>
</tbody>
</table>
<p class="meta">分流入口：<code>scripts/autoresearch_v5/finalize_round43_handoff.py</code>。已用失败的 low-005 retry 做 dry-run，确认不会产生 accepted11 或误升级结论。</p>
<p class="meta">Fig.8 分支入口：<code>scripts/autoresearch_v5/plot_fig8_round43_branch.py</code>。它读取终态交接摘要后自动选择 bounded 或 production 分支，并固定输出 SVG、PDF、PNG、TIFF、source CSV、来源 sidecar 与 QA JSON。当前 bounded dry-run 已通过 89 mm 单栏尺寸、可编辑 SVG 文本、最小 5.2 pt 字号和无重叠检查；该图件准备不改变运行中的证据等级。</p>
</section>

<section id="claims">
<h2>论断—证据映射</h2>
<table><thead><tr><th>论断</th><th>核心证据</th><th>状态</th><th>允许表述</th></tr></thead><tbody>
<tr><td>五聚体基态为有效 S=1/2</td><td>正 alpha 的局域 ED 与多重态分类</td><td class="pass">Supported</td><td>可直接陈述</td></tr>
<tr><td>正 beta 产生反铁磁 J_eff</td><td>投影系数与两单胞谱</td><td class="pass">Supported</td><td>J_eff/beta=0.4189–0.4396</td></tr>
<tr><td>二阶虚过程产生弱 J2</td><td>两、三单胞 Schrieffer–Wolff 拟合</td><td class="pass">Supported</td><td>受控边缘 3.95%–5.19%</td></tr>
<tr><td>q=pi 过滤最低双重态</td><td>反射宇称与局域矩阵元</td><td class="pass">Supported</td><td>局域选择定则</td></tr>
<tr><td>有限尺寸低能结构接近 c=1</td><td>三种 matched-size oracle 比值</td><td class="bounded">Bounded</td><td>限定当前尺寸，不作无偏外推</td></tr>
<tr><td>正区未见内部 crossing</td><td>105 条成功记录，L=40/60/80</td><td class="bounded">Bounded</td><td>不得改写为热力学无相变</td></tr>
<tr><td>CV 与 TEBD 完整 Agreement</td><td>七点共享窗通过，低频覆盖失败</td><td class="pending">NotEvaluable</td><td>只能陈述共享区域接近</td></tr>
</tbody></table>
</section>

<section id="missing">
<h2>待作者确认与缺失输入</h2>
<ol>
<li>确认目标期刊、摘要字数和中英文稿件要求；当前按 generic research article 组织。</li>
<li>确认作者姓名、单位、作者顺序、通讯作者和贡献声明。</li>
<li>从文献管理软件补全 Li 等 2026 四聚体论文的完整作者列表；DOI 已核对为 10.1038/s41535-026-00855-x。</li>
<li>决定是否接受“有限尺寸未见 crossing”的 C11 表述；若坚持热力学相图，需要额外序参量和临界标度。</li>
<li>round43 低频计算通过前，动态结论维持 NotEvaluable；通过后需重新生成图 8 和本节数字。</li>
</ol>
</section>

<section id="references" class="references">
<h2>参考文献</h2>
<p>1. Li et al. Spin order and spin excitation spectra of spin-1/2 tetramer chains. <i>npj Quantum Materials</i> <b>11</b>, 37 (2026). https://doi.org/10.1038/s41535-026-00855-x.</p>
<p>2. des Cloizeaux, J. & Pearson, J. J. Spin-wave spectrum of the antiferromagnetic linear chain. <i>Physical Review</i> <b>128</b>, 2131–2135 (1962).</p>
</section>

<footer>
<p>证据入口：<code>docs/claim_evidence_matrix.md</code>、<code>docs/pentamer_reproduction_standard.md</code>、<code>results/research_progress/source_data_inventory_20260804.json</code>、<code>results/research_progress/bounded_delivery_audit_20260805.json</code>。</p>
<p>本文档为作者审阅用 bounded HTML，不代表 paper/ 已定稿。</p>
</footer>
</main>
</div>
</body>
</html>"""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    forbidden = [
        "本文证明热力学极限只有一个相",
        "本文完成了完整 CV–TEBD Agreement",
        "本文已完成完整二维相图",
    ]
    required_sections = [
        'id="abstract"',
        'id="intro"',
        'id="methods"',
        'id="results"',
        'id="discussion"',
        'id="conclusion"',
        'id="claims"',
        'id="missing"',
    ]
    qa = {
        "schema_version": 1,
        "status": "pass",
        "output": str(output),
        "sha256": sha256(output),
        "bytes": output.stat().st_size,
        "checks": {
            "all_sections": all(marker in document for marker in required_sections),
            "six_figures_embedded": document.count("data:image/png;base64,") == 6,
            "positive_scope": "0 ≤ alpha,beta ≤ 1" in document,
            "negative_alpha_excluded": "负 alpha" in document,
            "fig9_excluded": "Fig.9" in document,
            "dynamic_not_evaluable": "NotEvaluable" in document,
            "round43_branch_guard": "production_ready=true" in document and "禁止 accepted-only 组装" in document,
            "forbidden_claims_absent": not any(term in document for term in forbidden),
        },
        "figure_sha256": {key: sha256(path) for key, path in paths.items()},
    }
    qa["status"] = "pass" if all(qa["checks"].values()) else "fail"
    qa_path = output.with_suffix(".qa.json")
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(qa, ensure_ascii=False))
    if qa["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
