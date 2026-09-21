#!/usr/bin/env python3
"""生成精简研究主页与完整历史页。"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "research_progress"
SOURCE = RUN / "report.json"
ASSETS = RUN / "assets"
RENDERER = Path.home() / ".codex" / "skills" / "report" / "render_report.py"
MANIFEST = RUN / "paper_static_figures_manifest_20260804.json"
DASHBOARD = RUN / "research_completion_dashboard_20260804.json"
FIGURE_MANIFEST = RUN / "reference_aligned_figures_manifest_20260804.json"
VIEW_CONFIG = RUN / "report_view_config.json"
REMOTE_SNAPSHOT = RUN / "qpi_cv_extension_remote_snapshot_20260804_now.json"
FORECAST = RUN / "paper_completion_forecast_20260804.json"
ROUND41 = RUN / "round41_qpi_cv_low005_submission_20260804.json"
SCHEDULE = RUN / "automation_schedule_20260804.json"
ROUND41_TERMINAL = RUN / "round41_qpi_cv_low005_terminal_assessment_20260805.json"
HIGH150_CURRENT = RUN / "round31_high150_status_20260805_0742.json"
RETRY_CURRENT = RUN / "round41_qpi_cv_low005_retry_submission_20260805.json"
RETRY_HEALTH = RUN / "round41_qpi_cv_low005_retry_health_20260805_2110.json"
LOW000_PLAN = RUN / "round42_qpi_cv_low000_conditional_plan_20260805.json"
BOUNDED_AUDIT = RUN / "bounded_delivery_audit_20260805.json"
REPRO_AUDIT = RUN / "reproducibility_command_audit_20260805.json"
STAGE3_STATUS = RUN / "project_closeout_status_20260919.json"
STAGE3_REPORT = RUN / "project_closeout_status_20260919_report" / "report.json"
STAGE3_REPORT_LINK = "__STAGE3_STATUS_REPORT_LINK__"
MANUSCRIPT_REPORT_LINK = "__MANUSCRIPT_CLOSEOUT_REPORT_LINK__"
LOCAL_IMPACT_REPORT_LINK = "__LOCAL_IMPACT_REPORT_LINK__"
K12_GATE_REPORT_LINK = "__K12_GATE_REPORT_LINK__"
ROUND43_CURRENT = RUN / "round43_phase1_submission_20260806.json"
ROUND43_ACCESS = RUN / "round43_phase_b_access_snapshot_20260806.json"
ROUND43_HANDOFF = ROOT / "results/autoresearch_v5_20260806/round43_handoff_final_v2/handoff_summary.json"
FULLQ_STATUS = RUN / "minimal_fullq_campaign_status_20260807.json"
FULLQ_READINESS = RUN / "minimal_fullq_local_readiness_20260807.json"
FULLQ_PLAN = RUN / "minimal_fullq_campaign_20260807/campaign_plan.json"
NEGATIVE_PHASE_STATUS = RUN / "negative_full_phase_campaign_status_20260809.json"
NEGATIVE_PRACTICAL_STATUS = RUN / "negative_practical_v2_status_20260829.json"
NEGATIVE_INDEPENDENT_AUDIT = ROOT / "results" / "autoresearch_v5_20260913" / "negative_phase_independent_audit_v6" / "summary.json"
NEGATIVE_INDEPENDENT_PILOT_STATUS = RUN / "negative_phase_independent_pilot_status_20260913.json"
NEGATIVE_INDEPENDENT_PILOT_ANALYSIS = ROOT / "results" / "autoresearch_v5_20260913" / "negative_phase_independent_pilot_analysis_20260914_v3" / "summary.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_renderer():
    spec = importlib.util.spec_from_file_location("harness_report_renderer", RENDERER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 renderer: {RENDERER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_figure(src: str) -> Path | None:
    path = Path(src)
    # 兼容历史重复渲染留下的 hash 前缀。
    normalized_name = path.name
    while re.match(r"^[0-9a-f]{12}_", normalized_name):
        normalized_name = normalized_name[13:]
    if path.is_absolute():
        candidates = [path]
    elif path.parts and path.parts[0] == "assets":
        candidates = [
            ROOT / "figures" / normalized_name,
            RUN / path,
            ROOT / path,
        ]
    else:
        candidates = [RUN / path, ROOT / path, ROOT / "figures" / normalized_name]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_file():
            return resolved
    return None


def stage(path: Path, records: dict[str, dict[str, object]]) -> str:
    try:
        relative_asset = path.resolve().relative_to(ASSETS.resolve())
    except ValueError:
        relative_asset = None
    if relative_asset is not None:
        return f"assets/{relative_asset.as_posix()}"
    digest = sha256(path)
    name = f"{digest[:12]}_{path.name}"
    target = ASSETS / name
    if not target.exists() or sha256(target) != digest:
        shutil.copy2(path, target)
    records[name] = {
        "source": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "staged": str(target.relative_to(ROOT)),
        "sha256": digest,
        "bytes": target.stat().st_size,
    }
    return f"assets/{name}"


def stage_document_figures(doc: dict[str, object], records: dict[str, dict[str, object]]) -> list[str]:
    missing = []
    for section in doc.get("sections", []):
        for block in section.get("blocks", []):
            stack = [block]
            while stack:
                item = stack.pop()
                if item.get("kind") == "card":
                    stack.extend(item.get("blocks", []))
                if item.get("kind") != "figures":
                    continue
                for figure in item.get("items", []):
                    source = resolve_figure(str(figure.get("src", "")))
                    if source is None:
                        missing.append(str(figure.get("src", "")))
                        continue
                    figure["src"] = stage(source, records)
    return sorted(set(missing))


def manuscript_section(staged: dict[str, str]) -> dict[str, object]:
    return {
        "title": "2026-08-04 Fig.1–5 manuscript master 完成",
        "note": "完全使用本机既有数据；Python/matplotlib；不覆盖旧 reference-aligned 资产。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "Fig.1–5 静态最终稿已完成",
                "why": "五张图均提供 SVG/PDF/PNG/TIFF 与独立来源 sidecar；Fig.3/4 保留有限尺寸结论边界。",
            },
            {
                "kind": "figures",
                "items": [
                    {"src": staged["Fig. 1"], "caption": "Fig.1. 五聚体链、低能投影与局域多重态。圆面积表示 q=π 谱权；只陈述局域 ED 与一阶有效链。"},
                    {"src": staged["Fig. 2"], "caption": "Fig.2. 正 alpha 能级流与 q=π 通道权重。反射宇称压低最低激发双重态，四重态主导局域非弹性权重。"},
                ],
            },
            {
                "kind": "figures",
                "items": [
                    {"src": staged["Fig. 3"], "caption": "Fig.3. 正耦合区 L=40/60/80 有限尺寸诊断。热图、切片与尺寸差未给出可验收 crossing，因此不命名相界。"},
                    {"src": staged["Fig. 4"], "caption": "Fig.4. 两个正 alpha 代表点的五类切口纠缠谱，以及同尺寸 c=1 oracle 校准。三个估计量偏离不超过 3.31%；裸 log-L 拟合不用于热力学结论。"},
                ],
            },
            {
                "kind": "figures",
                "items": [
                    {"src": staged["Fig. 5"], "caption": "Fig.5. 单一六面板机制图：有效链投影、投影系数、J_eff、局域能级、动量过滤与通道权重。未引入未经生产 DSF 验证的准粒子名称。"},
                ],
            },
            {
                "kind": "figures",
                "items": [
                    {"src": staged["Fig. 8 bounded"], "caption": "Fig.8（bounded）。七个 accepted CV 点与 TEBD 在共享频率上最大差 6.40%；omega=0.05 residual 超门点仅作失败标记。主峰未被包围，因此不升级 production。"},
                ],
            },
            {
                "kind": "note",
                "label": "动态边界",
                "style": "pending",
                "text": "Fig.6 exploratory、Fig.7 pilot、Fig.8 bounded 已冻结；low-005 residual 再次失败，停止追加计算且不升级 production。",
            },
        ],
    }


def progress_summary_section() -> dict[str, object]:
    return {
        "title": "2026-08-04 研究进展、预计交付与人工介入",
        "note": "基于 18:37 只读服务器快照和本地证据仪表盘；不把证据覆盖率等同于论文完成率。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "主线已收敛到一个动态门",
                "why": "静态 Fig.1–5、方法 oracle 和正区有限尺寸证据已闭合；剩余决定性工作是 high-150 与低频 omega≈0.05 的 accepted CV 覆盖。",
            },
            {
                "kind": "table",
                "columns": ["交付节点", "目标时间", "成立条件"],
                "rows": [
                    ["动态计算终态决策", "8 月 5–6 日", "high-150 验收并完成低频最小重试"],
                    ["图件与结论冻结", "8 月 7 日", "Fig.6–8 升级或明确降级边界"],
                    ["HTML 完整审阅稿", "8 月 9 日晚", "Results/Discussion/图注与限制完整"],
                    ["最终研究包", "8 月 10 日晚", "HTML、图表、原始数据、checksum 和复算入口齐全"],
                ],
                "widths": ["30%", "22%", "48%"],
            },
            {
                "kind": "note",
                "label": "需要人工决定",
                "style": "pending",
                "text": "8 月 6 日动态门仍未关闭时，需要选择按有边界的 L=40 动力学版本准时交付，还是延长计算；同时需要确认是否授权把已审阅 HTML 内容迁入 paper/。",
            },
        ],
    }


def fullq_section() -> dict[str, object]:
    status = json.loads(FULLQ_STATUS.read_text(encoding="utf-8")) if FULLQ_STATUS.is_file() else {}
    readiness = json.loads(FULLQ_READINESS.read_text(encoding="utf-8")) if FULLQ_READINESS.is_file() else {}
    production = status.get("production", {})
    production_ready = status.get("replan", {}).get("status") == "production_ready" and bool(production.get("final_handoff"))
    production_label = f"生产 {production.get('schedule', production.get('cell_id', 'current cell'))}"
    return {
        "title": "2026-08-07 精简 full-q 复刻与本机收尾",
        "note": "三个代表点、两档时间步；范围仅 0<=alpha,beta<=1，排除负 alpha 与 Fig.9。",
        "blocks": [
            {"kind": "verdict", "status": "good" if production_ready else ("good" if readiness.get("local_work_complete") else "warn"), "label": "六个 full-q cell 已严格验收；handoff production_ready" if production_ready else ("本机准备 complete；真实 full-q 数据等待服务器" if readiness else "full-q 准备状态待审计"), "why": ("六个单 run、三组 dt/dt2、handoff 和图件均通过；" + production.get("final_handoff", "")) if production_ready else "回传、checksum、独立 validator、dt/dt2 handoff、论文图和合成端到端测试均已完成；不把合成数据当物理结果。"},
            {"kind": "table", "columns": ["阶段", "参数", "状态", "证据/下一步"], "rows": [
                ["本机工具链", "fetch + validator + handoff + 2x3 plot", "通过", "80/80 全项目测试；真实六-cell 已完成" if production_ready else "80/80 全项目测试；inventory 111 条"],
                ["L=10 smoke", status.get("smoke", {}).get("params", ""), status.get("smoke", {}).get("status", ""), status.get("smoke", {}).get("summary", "")],
                [production_label, production.get("params", ""), production.get("status", ""), production.get("schedule", "")],
            ], "widths": ["18%", "28%", "14%", "40%"]},
            {"kind": "kv", "pairs": [
                ["当前 cell", production.get("cell_id", "尚未启动")],
                ["最近只读检查", production.get("latest_readonly_check", "尚未检查")],
                ["进度", production.get("progress", "尚无进度")],
                ["资源与 stderr", production.get("resources", "尚无资源快照")],
                ["条件 ETA", production.get("remaining_estimate", production.get("eta", "待估计"))],
                ["下一次检查", production.get("next_check", "按计划")],
            ]},
            {"kind": "list", "title": "真实数据终态门", "items": [
                "每点 t=0、variance/site<=1e-8、Sz=0、raw 负谱权占比<=0.15。",
                "每个物理点的 dt=0.025 与 dt=0.0125 必须有相同 tmax=30，并通过峰漂移<=0.05 J1、低频权重漂移<=5%。",
                "六个 cell 全部通过后才生成最终 Fig.6/7；任一失败保持 blocked，不裁零或降低门槛。",
            ]},
        ],
    }


def negative_practical_v2_section() -> dict[str, object]:
    status = json.loads(NEGATIVE_PRACTICAL_STATUS.read_text(encoding="utf-8"))
    audit = status["threshold_audit"]
    remote = status["remote_r10"]
    r11 = status.get("remote_r11", {})
    r12 = status.get("remote_r12", {})
    r13 = status.get("remote_r13", {})
    r14 = status.get("local_r14", {})
    r15 = status.get("local_r15", {})
    r16 = status.get("local_r16", {})
    r17 = status.get("local_r17", {})
    r18 = status.get("local_r18", {})
    r19 = status.get("local_r19", {})
    r20 = status.get("local_r20", {})
    stage_c = status.get("stage_c_r1", {})
    operations = status.get("operations_notice", {})
    state = status.get("state")
    running = state == "stage_b_r11_running"
    retry_running = state == "stage_b_r12_retry_running"
    continuation_running = state == "stage_b_r13_running"
    awaiting_upload = state == "stage_b_r14_awaiting_upload_authorization"
    r14_running = state == "stage_b_r14_running"
    r15_awaiting_upload = state == "stage_b_r15_awaiting_upload_authorization"
    r15_running = state == "stage_b_r15_running"
    r16_awaiting_upload = state == "stage_b_r16_awaiting_upload_authorization"
    r16_running = state == "stage_b_r16_running"
    r16_remote_unknown = state == "stage_b_r16_remote_unknown"
    r17_awaiting_upload = state == "stage_b_r17_awaiting_upload_authorization"
    r17_running = state == "stage_b_r17_running"
    r18_awaiting_upload = state == "stage_b_r18_awaiting_upload_authorization"
    r18_running = state == "stage_b_r18_running"
    r19_running = state == "stage_b_r19_running"
    r20_running = state == "stage_b_r20_running"
    stage_c_running = state == "stage_c_r1_running"
    stage_c_bounded = state == "stage_c_r1_bounded_not_evaluable"
    if stage_c_running:
        verdict_label = "Stage B 已闭合 · Stage C 边界精修运行中"
        verdict_why = "Stage B 的96个网格点已全部解析：89 accepted、7 bounded；accepted-only分析给出8个候选区间，Stage C正用L60/L80、64 sweeps精修。"
    elif stage_c_bounded:
        verdict_label = "Stage C 数值闭合 · 正式相界尚未通过双诊断"
        verdict_why = "29/29个L60/L80精修点均通过checksum、回传与独立validator；8个候选目标中可见动量重构或2σ ratio信号，但没有同一相邻区间同时满足两者，因此固定门下为bounded/NotEvaluable。"
    elif r20_running:
        verdict_label = "R20 最后4点正在单并发运行"
        verdict_why = "R19已有14点通过、1点按Practical V2标记NotEvaluable；accepted index=85、bounded=7，R20继续最后4点。"
    elif r19_running:
        verdict_label = "R19 剩余19点正在单并发运行"
        verdict_why = "R18首点已按Practical V2标记NotEvaluable；accepted index=71、bounded=6，R19继续其余19点，不降低任何物理门。"
    elif r18_running:
        verdict_label = "R18 剩余20点正在单并发运行"
        verdict_why = "R17已有14点通过、1点按约定标记NotEvaluable；accepted index=71，R18继续其余20点，不降低任何物理门。"
    elif r18_awaiting_upload:
        verdict_label = "R18 本地预检完成 · 等待显式上传授权"
        verdict_why = "R17证据链为14 pass/1 bounded；R18的20点离线包、哈希门和2-cell dry-run均通过。"
    elif r17_running:
        verdict_label = "R17 剩余35点正在单并发运行"
        verdict_why = "R16首点已按约定标记NotEvaluable；accepted index=57，R17继续其余35点，不降低任何物理门。"
    elif r17_awaiting_upload:
        verdict_label = "R17 本地预检完成 · 等待显式上传授权"
        verdict_why = "R16首点是64-sweep方差门轻微失败，已完成checksum、非覆盖回传和独立validator并标记bounded；R17的35点包与2-cell dry-run均通过。"
    elif r16_remote_unknown:
        verdict_label = "R16 远端状态暂不可读取"
        verdict_why = "本轮唯一一次SSH检查得到connection refused；最后确认时R16健康运行。连接失败不能证明Julia停止，02:00再做一次只读检查。"
    elif r16_running:
        verdict_label = "R16 剩余36点正在单并发运行"
        verdict_why = "R15已有13点严格通过、1点按约定标记NotEvaluable；accepted index=57，R16继续其余36点，不降低任何物理门。"
    elif r16_awaiting_upload:
        verdict_label = "R16 本地预检完成 · 等待显式上传授权"
        verdict_why = "R15证据链为13 pass/1 bounded；R16的36点离线包、哈希门和2-cell dry-run均通过，外部安全审核要求授权文字明确写出R16。"
    elif r15_running:
        verdict_label = "R15 剩余50点正在单并发运行"
        verdict_why = "R14已有14点严格通过、1点按约定标记NotEvaluable；accepted index=44，R15继续其余50点，不降低任何物理门。"
    elif r15_awaiting_upload:
        verdict_label = "R15 已完成本地预检 · 等待新载荷上传授权"
        verdict_why = "R14证据链为14 pass/1 bounded；R15的50点离线包、哈希门和2-cell dry-run均通过，安全审核要求单独授权上传R15源码、运行配置和研究证据。"
    elif r14_running:
        verdict_label = "R14 剩余65点正在单并发运行"
        verdict_why = "R13已有10点严格通过、1点按约定标记NotEvaluable；accepted index=30，R14继续其余65点，不降低任何物理门。"
    elif awaiting_upload:
        verdict_label = "R14 已完成本地预检 · 等待一次上传授权"
        verdict_why = "R13证据链为10 pass/1 bounded；R14的65点离线包、哈希门和2-cell dry-run均通过，安全审核要求明确授权上传源码、运行配置和研究数据。"
    elif continuation_running:
        verdict_label = "R13 剩余76点正在单并发运行"
        verdict_why = "R12已通过远端/本地checksum与独立V2 validator，accepted index增至20；R13只计算剩余76点，最大64 sweeps。"
    elif retry_running:
        verdict_label = "R12 单点64-sweep补算正在运行"
        verdict_why = "R11首点仅ferro_j2方差5.0376×10⁻⁸略高于5×10⁻⁸；其他门全部通过。R12按既定32→64路径补算，禁止128 sweeps。"
    elif running:
        verdict_label = "Practical V2 R11 已单并发启动"
        verdict_why = "已复用19个物理点，剩余77点按27个32-sweep与50个64-sweep顺序执行；variance/site=5×10⁻⁸，禁止新增128-sweep。"
    else:
        verdict_label = "方法阻塞已解除 · 本地方案已就绪"
        verdict_why = "variance/site=5×10⁻⁸ 已覆盖 18/18 个历史物理点；10⁻⁷ 不增加可用点，因此不再追求无物理增益的 128-sweep 超严方差。"
    return {
        "title": "2026-08-29 负 α Practical V2 收敛方案",
        "note": "参考作者确认方法无误；本节用历史阈值审计确定最小有效放宽，不改写旧 strict_v1 证据。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn" if awaiting_upload or r15_awaiting_upload or r16_awaiting_upload or r16_remote_unknown or r17_awaiting_upload or r18_awaiting_upload or stage_c_bounded else "good",
                "label": verdict_label,
                "why": verdict_why,
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "figures/negative_practical_v2_crossover_20260913/negative_alpha_crossover_summary.png",
                        "caption": "负 α accepted-only 终态。上图给出实际采样的大尺寸主波矢，红叉表示 L60/L80 不一致；下图比较 dominant-ratio 尺寸流与8个预设边界门。29/29个 Stage C 点通过数值验收，但没有目标同时满足双诊断，因此只支持有限尺寸 crossover。",
                    }
                ],
            },
            {
                "kind": "table",
                "columns": ["项目", "Practical V2", "保留的物理门"],
                "widths": ["24%", "34%", "42%"],
                "rows": [
                    ["Stage B 粗扫", "32 sweeps；困难点最多 64", "双初态、Sz、非负 gap、截断、checksum"],
                    ["Stage C 边界", "L60/L80，64 sweeps", "双诊断、2σ、边界宽度≤0.025"],
                    ["负区响应", "每个新 bulk regime 1 点；最难点 dt/dt2", "峰漂移≤0.05 J₁；低频权漂移≤10%"],
                ],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["阈值审计", f"{audit['input_parent_manifests']} manifests，{audit['physical_points']} 个独立点；strict={audit['strict_1e-8_accepted']}/18，V2={audit['practical_5e-8_accepted']}/18"],
                    ["32/64 对照", f"{audit['paired_32_64_count']} 组；q_peak/π 最大漂移={audit['max_q_peak_over_pi_drift']:.3g}，dominant ratio 最大漂移={audit['max_dominant_ratio_drift']:.3f}"],
                    ["R10 证据链", f"{remote['fetch']}；Practical V2={remote.get('practical_v2_validation', 'pending')}"],
                    ["R11 终态", f"{r11.get('status', 'unknown')}；首点方差超门 {r11.get('failure', {}).get('relative_excess_percent', 0):.2f}%；checksum、回传与独立validator证据链完成"],
                    ["R12 终态", f"{r12.get('status', 'unknown')}；checksum、非覆盖回传与独立validator={r12.get('independent_validator', 'pending')}；accepted index=20"],
                    ["R13 终态", f"{r13.get('completed_cells', 0)} pass；1 bounded；checksum/回传/validator={r13.get('independent_validator', 'pending')}；accepted index={r13.get('accepted_practical_v2_physical_points_after_ingest', 20)}"],
                    ["R13 不可评估点", f"α=-0.025, β=0.10, L=40；center gap={r13.get('failure', {}).get('center_spin_gap', 0):.3e}；ferro gap={r13.get('failure', {}).get('ferro_j2_spin_gap', 0):.3e}；不进入相界"],
                    ["R14 终态", f"{r14.get('completed_cells', 0)} pass；1 bounded；checksum/回传/validator={r14.get('independent_validator', 'pending')}；accepted index={r14.get('accepted_practical_v2_physical_points', 30)}"],
                    ["R14 不可评估点", f"α=-0.05, β=0.25, L=60；center gap={r14.get('failure', {}).get('center_spin_gap', 0):.3e}；ferro gap={r14.get('failure', {}).get('ferro_j2_spin_gap', 0):.3e}；不进入相界"],
                    ["R15 终态", f"{r15.get('completed_cells', 0)} pass；1 bounded；checksum/回传/validator={r15.get('independent_validator', 'pending')}；accepted index={r15.get('accepted_practical_v2_physical_points', 44)}"],
                    ["R15 不可评估点", f"α=-0.10, β=0.75, L=60；center gap={r15.get('failure', {}).get('center_spin_gap', 0):.3e}；ferro gap={r15.get('failure', {}).get('ferro_j2_spin_gap', 0):.3e}；不进入相界"],
                    ["R16 终态", f"{r16.get('completed_cells', 0)} pass；1 bounded；checksum/回传/validator={r16.get('independent_validator', 'pending')}；accepted index={r16.get('accepted_practical_v2_physical_points', 57)}"],
                    ["R16 不可评估点", f"α=-0.05, β=0.75, L=40；双初态Sz1方差={r16.get('failure', {}).get('variance_per_site_sz1', 0):.3e}，门={r16.get('failure', {}).get('threshold', 0):.1e}；gap与其他门通过，不进入相界"],
                    ["R17 终态", f"{r17.get('completed_cells', 0)} pass；1 bounded；checksum/回传/validator={r17.get('independent_validator', 'pending')}；accepted index={r17.get('accepted_practical_v2_physical_points', 57)}"],
                    ["R17 不可评估点", f"α=-0.10, β=0.90, L=60；center gap={r17.get('failure', {}).get('center_spin_gap', 0):.3e}；ferro gap={r17.get('failure', {}).get('ferro_j2_spin_gap', 0):.3e}；不进入相界"],
                    ["R18 终态", f"{r18.get('completed_cells', 0)} pass；1 bounded；checksum/回传/validator={r18.get('independent_validator', 'pending')}；accepted index={r18.get('accepted_practical_v2_physical_points', 71)}"],
                    ["R18 不可评估点", f"α=-0.05, β=0.90, L=40；双初态Sz1方差={r18.get('failure', {}).get('variance_per_site_sz1', 0):.3e}，门={r18.get('failure', {}).get('threshold', 0):.1e}；gap与其他门通过，不进入相界"],
                    ["R19 终态", f"{r19.get('completed_cells', 0)} pass；1 bounded；checksum/回传/validator={r19.get('independent_validator', 'pending')}；accepted index={r19.get('accepted_practical_v2_physical_points', 71)}"],
                    ["R19 不可评估点", f"α=-0.10, β=1.00, L=60；center gap={r19.get('failure', {}).get('center_spin_gap', 0):.3e}；ferro gap={r19.get('failure', {}).get('ferro_j2_spin_gap', 0):.3e}；不进入相界"],
                    ["R20 续跑", f"{r20.get('planned_cells', 4)} cells；预算64={r20.get('budget_counts', {}).get('64', 4)}；PID={r20.get('batch_pid', 'pending')}；dry-run={r20.get('batch_dry_run', 'pending')}"],
                    ["Stage B 终态", f"accepted={status.get('stage_b_practical_v2', {}).get('accepted', 89)}；bounded={status.get('stage_b_practical_v2', {}).get('bounded', 7)}；pending={status.get('stage_b_practical_v2', {}).get('pending', 0)}；96/96物理点已解析"],
                    ["Stage C 精修", f"{stage_c.get('completed_cells', 0)}/{stage_c.get('planned_cells', 0)} cells；L60/L80、64 sweeps；validator={stage_c.get('independent_validator', 'pending')}；正式边界={stage_c.get('boundary_result', {}).get('confirmed_dual_diagnostic_boundaries', 'pending')}/8"],
                    ["服务器维护", f"{operations.get('server_maintenance_date', '未登记')}；9月13日恢复核验={operations.get('ssh', 'unknown')}；无在途任务，全部Stage C证据已在本机"],
                    ["SSH 核验", r19.get("last_monitor", {}).get("status", r17.get("last_monitor", {}).get("status", r16.get("last_monitor", {}).get("status", r14.get("ssh_check", "待检查"))))],
                    ["进度安排", f"Stage C 条件 ETA {stage_c.get('conditional_eta_hours', [14, 28])[0]}–{stage_c.get('conditional_eta_hours', [14,28])[1]} h；下次一次性读取 {stage_c.get('next_read_window', '待安排')}" if stage_c_running else ("远端计算已结束；固定双诊断门下没有自动补算动作，等待选择保守写法或另行定义相界判据" if stage_c_bounded else ("等待明确写出R18的上传与启动授权" if r18_awaiting_upload else ("等待明确写出R17的上传与启动授权" if r17_awaiting_upload else ("等待明确写出R16的上传与启动授权" if r16_awaiting_upload else ("等待用户明确授权向 39.96.207.180 上传R15源码、运行配置和研究证据" if r15_awaiting_upload else ("等待用户明确授权向 39.96.207.180 上传源码、运行配置和研究数据" if awaiting_upload else f"条件 ETA {r20.get('conditional_eta_hours', r19.get('conditional_eta_hours', r18.get('conditional_eta_hours', r17.get('conditional_eta_hours', r16.get('conditional_eta_hours', r15.get('conditional_eta_hours', [7, 13]))))))[0]}–{r20.get('conditional_eta_hours', r19.get('conditional_eta_hours', r18.get('conditional_eta_hours', r17.get('conditional_eta_hours', r16.get('conditional_eta_hours', r15.get('conditional_eta_hours', [7, 13]))))))[1]} h；下次一次性读取 {r20.get('next_read_window', r19.get('next_read_window', r18.get('next_read_window', r17.get('next_read_window', r16.get('next_read_window', r15.get('next_read_window', '待安排'))))))}"))))))],
                ],
            },
            {
                "kind": "note",
                "label": "结论边界",
                "style": "info",
                "text": "放宽的是数值停止线，不是相判据。Stage C 已出现动量重构和显著有限尺寸流，但两种诊断没有在同一相邻区间重合；因此可以写成强 crossover/候选重构，不能在当前证据契约下命名新的热力学相。",
            },
        ],
    }


def negative_independent_audit_section() -> dict[str, object]:
    summary = json.loads(NEGATIVE_INDEPENDENT_AUDIT.read_text(encoding="utf-8"))
    projection = summary["negative_quartet_projection"]
    scaling = summary["finite_size_diagnostics"]
    dimer = summary["matched_L80_over_L60_dimer_rms"]
    pilot = json.loads(NEGATIVE_INDEPENDENT_PILOT_STATUS.read_text(encoding="utf-8")) if NEGATIVE_INDEPENDENT_PILOT_STATUS.is_file() else {}
    pilot_analysis = json.loads(NEGATIVE_INDEPENDENT_PILOT_ANALYSIS.read_text(encoding="utf-8")) if NEGATIVE_INDEPENDENT_PILOT_ANALYSIS.is_file() else {}
    pilot_complete = pilot.get("state") == "completed_with_localized_candidate" and bool(pilot_analysis)
    figure_items = [
        {
            "src": "results/autoresearch_v5_20260913/negative_phase_independent_audit_v6/negative_alpha_independent_diagnostics.png",
            "caption": "独立诊断汇总。孤立五聚体的基态自旋始终为3/2，DMRG自旋隙未出现可接受的扇区交叉，Hellmann–Feynman能量斜率保持平滑；周期二键序随尺寸下降。两五聚体ED保真度峰只在最接近α=0的端点增强，没有给出负区内部临界点。",
        },
        {
            "src": "results/autoresearch_v5_20260913/negative_phase_independent_audit_v6/negative_alpha_finite_size_scaling.png",
            "caption": "L=40/60/80有限尺寸检验。13/13组三尺寸数据的周期二键序衰减指数为正；5个初态稳定的强负α点给出有效中心荷中位数1.002、范围0.945–1.071。空心点代表近α=0或弱耦合处的初态敏感结果，只能作为待补算线索。",
        },
        {
            "src": "results/autoresearch_v5_20260913/negative_phase_independent_audit_v6/negative_alpha_quartet_projection.png",
            "caption": "强负α的机制图。五聚体S=3/2四重态投影在整个负区给出反铁磁有效耦合Jeff/β=0.1075–0.1111，同一有效K=π支经五站点形状因子折叠后主要落在物理q≈0.6π，因此峰位移动本身不要求出现新相。",
        },
    ]
    if pilot_complete:
        figure_items.insert(0, {
            "src": "results/autoresearch_v5_20260913/negative_phase_independent_pilot_analysis_20260914_v3/negative_alpha_saved_state_independent_diagnostics.png",
            "caption": "保存态独立诊断，6个L=80参数点、每点center与ferro_j2双初态。误差棒为双初态半极差。β=0.75的q≈0.6π→π重构没有伴随纠缠或长程键关联突变；β=0.25、α=-0.10出现有限尺寸纠缠斜率降低与最大的双初态能量密度差，但远端连接键关联仍约10⁻⁵且自旋隙未反号，因此只列为候选异常，不命名新相。",
        })
    return {
        "title": "2026-09-13 负 α 新相独立诊断",
        "note": "本节不再用 S(q) 峰位单独定义相，而是检查局域多重态、总自旋扇区、能量导数、键序、纠缠与精确对角化保真度。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "六点保存态验收完成；发现一个局域候选异常，仍未确认第二个热力学相" if pilot_complete else "发现两个关联区，但尚未确认第二个热力学相",
                "why": "β=0.25、α=-0.10的单尺寸纠缠剖面与初态差异值得有限尺寸复核；其余独立诊断、尤其β=0.75切片，支持同一无隙相内的动量重构。" if pilot_complete else "强负 α 区与有效自旋3/2、c≈1的无隙链一致；靠近 α=0 的主波矢和纠缠发生重组，但目前没有扇区交叉、持续键序或内部非解析点共同支持新相。",
            },
            {
                "kind": "figures",
                "items": figure_items,
            },
            {
                "kind": "kv",
                "pairs": [
                    ["复用数据", f"{summary['dmrg_unique_points']} 个独立DMRG点；尺寸 L={','.join(str(item) for item in summary['dmrg_sizes'])}"],
                    ["小系统精确检验", f"孤立五聚体全负α区 S=3/2；两五聚体最小自旋隙={summary['two_pentamer_min_spin_gap']:.3e}；扇区交叉=无"],
                    ["三五聚体候选点", f"6点精确对角化；S=3/2基态多重态劈裂≤{summary['three_pentamer_selected']['maximum_ground_multiplet_splitting']:.2e}；到S=5/2最小隙={summary['three_pentamer_selected']['minimum_spin_sector_gap']:.3e}"],
                    ["周期二键序", f"L60→L80 匹配点 {dimer['count']} 个，比例中位数={dimer['median']:.3f}、最大值={dimer['maximum']:.3f}；三尺寸衰减指数为正 {scaling['positive_dimer_decay_exponents']}/{scaling['complete_L40_L60_L80_triplets']}"],
                    ["强负α纠缠标度", f"稳定点 {scaling['stable_strong_negative_points']} 个；c_eff 中位数={scaling['stable_strong_negative_c_effective_median']:.3f}，范围={scaling['stable_strong_negative_c_effective_range'][0]:.3f}–{scaling['stable_strong_negative_c_effective_range'][1]:.3f}"],
                    ["近α=0未决", f"初态敏感的三尺寸组={scaling['near_zero_initial_state_sensitive_triplets']}；必须用保存态的完整纠缠剖面与长程键-键关联复核"],
                    ["6点保存态补算", "6/6父cell、12/12双初态、18份远端checksum、252文件本地checksum与Practical V2独立验收全部通过" if pilot_complete else f"{pilot.get('state', 'not_prepared')}；本机Julia smoke、6/6 batch dry-run、16文件上传预检与哈希均通过；启动后ETA={pilot.get('conditional_eta_hours_after_launch', ['?', '?'])[0]}–{pilot.get('conditional_eta_hours_after_launch', ['?', '?'])[1]}小时"],
                    ["保存态候选异常", "β=0.25、α=-0.10：profile c_eff≈0.53，双初态能量密度差7.87×10⁻⁸；连接键关联远尾≤1.24×10⁻⁵，故保持候选而非相" if pilot_complete else "待计算"],
                    ["远端连接", pilot.get("remote_access", {}).get("ssh_result", "待检查")],
                ],
            },
            {
                "kind": "note",
                "label": "当前物理图像",
                "style": "info",
                "text": "最稳妥的解释是一个无隙半整数自旋相内部，从强负α的五聚体块自旋关联逐渐重组为靠近α=0的三聚体/跨单元二聚体关联。新相仍有可能，但只值得在近α=0窄带做保存波函数的定向补算，不需要重扫整个二维区域。",
            },
        ],
    }


def negative_phase_section() -> dict[str, object]:
    status = json.loads(NEGATIVE_PHASE_STATUS.read_text(encoding="utf-8"))
    stage = status["stage_a"]
    server = status["server_snapshot"]
    monitor = status["monitor"]
    state = status.get("status", "unknown")
    failure = status.get("failure_audit", {})
    retry = status.get("retry_plan", {})
    r2_retry = status.get("r2_retry", {})
    r3_continuation = status.get("r3_continuation", {})
    r4_retry = status.get("r4_retry", {})
    r5_preparation = status.get("r5_preparation", {})
    r6_retry = status.get("r6_retry", {})
    r7_continuation = status.get("r7_continuation", {})
    r8_retry = status.get("r8_retry", {})
    r9_continuation = status.get("r9_continuation", {})
    r10_retry = status.get("r10_retry", {})
    r11_retry = status.get("r11_retry", {})
    r12_continuation = status.get("r12_continuation", {})
    r13_retry = status.get("r13_retry", {})
    r14_continuation = status.get("r14_continuation", {})
    r15_retry = status.get("r15_retry", {})
    r16_repair = status.get("r16_repair", {})
    r17_continuation = status.get("r17_continuation", {})
    r18_retry = status.get("r18_retry", {})
    r19_continuation = status.get("r19_continuation", {})
    stage_b = status.get("stage_b_preparation", {})
    if state == "stage_a_retry_preparing":
        verdict_label = "阶段 A 首批已严格拒绝 · R1 修复重跑准备中"
        verdict_why = (
            "远端与本地 checksum 均通过；独立 validator 发现 full-q CSV 换行程序错误，"
            "同时 L80 ferro_j2 的 Sz=0 方差/site 超门。当前负区 accepted=0，旧结果只保留为失败证据。"
        )
        eta = f"R1 条件 ETA {retry['conditional_eta_hours'][0]}–{retry['conditional_eta_hours'][1]} h"
        batch_name = retry.get("run", stage["remote_batch"])
        batch_pid = "待启动"
        next_window = "完成本地修复与上传门后"
        progress_text = "首批 0 accepted；R1 待启动"
    elif state == "stage_a_r1_running":
        verdict_label = "阶段 A R1 正在运行 · 负区严格结果尚未回传"
        verdict_why = "CSV 写出已修复，L80 按 32→64 sweeps 重试；只有 checksum、validator 和有限尺寸 guard 全部通过才接纳。"
        snapshot = retry.get("health_snapshot", {})
        remaining = snapshot.get("remaining_eta_hours", retry["conditional_eta_hours"])
        eta = f"剩余约 {remaining[0]}–{remaining[1]} h；{snapshot.get('conditional_completion_window', '待下一次实测校正')}"
        batch_name = retry["run"]
        batch_pid = retry["pid_receipt"]
        next_window = retry["next_read_window"]
        progress_text = f"{snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', stage['cells'])}；当前 {snapshot.get('current_cell', '待读取')}"
    elif state == "stage_a_r1_status_unknown":
        snapshot = retry.get("health_snapshot", {})
        monitor_snapshot = retry.get("monitor_snapshot", {})
        verdict_label = "阶段 A R1 远端状态暂不可读 · 不等同于计算失败"
        verdict_why = f"本轮单次 SSH 在握手阶段被拒绝；最后可证状态为 {monitor_snapshot.get('last_verified_remote_state', '未知')} 的正常运行快照，按规则不立即重连。"
        remaining = snapshot.get("remaining_eta_hours", retry["conditional_eta_hours"])
        eta = f"沿用最后条件估计 {remaining[0]}–{remaining[1]} h；待下次连接后校正"
        batch_name = retry["run"]
        batch_pid = retry["pid_receipt"]
        next_window = retry["next_read_window"]
        progress_text = f"最后验证 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', stage['cells'])}；当前状态未知"
    elif state == "stage_a_r1_failed_validation_pending":
        terminal = retry.get("terminal", {})
        verdict_label = "阶段 A R1 已严格停止 · 正在执行独立回传验收"
        verdict_why = f"完成 {terminal.get('completed_cells', 0)}/{terminal.get('planned_cells', stage['cells'])} 后，{terminal.get('failed_cell', '未知 cell')} 被数值验收门拒绝；两个初态程序均正常退出，尚不降低门槛。"
        eta = "R1 已终态；待 checksum、validator 与失败字段审计后给出 R2 ETA"
        batch_name = retry["run"]
        batch_pid = retry["pid_receipt"]
        next_window = retry["next_read_window"]
        progress_text = f"完成 {terminal.get('completed_cells', 0)}/{terminal.get('planned_cells', stage['cells'])}；失败点 {terminal.get('failed_cell', '未知')}"
    elif state == "stage_a_r2_retry_preparing":
        terminal = retry.get("terminal", {})
        failed_values = terminal.get("failed_values", {})
        verdict_label = "R1 独立验收 10 pass / 1 fail · R2 单点重试准备中"
        verdict_why = f"唯一失败点 {r2_retry.get('cell', '未知')} 的两个初态仅 Sz=0 方差超门（{failed_values.get('center', float('nan')):.3e}、{failed_values.get('ferro_j2', float('nan')):.3e} > 1e-8）；其余门全部通过。"
        eta_window = r2_retry.get("conditional_eta_minutes", [30, 60])
        eta = f"R2 单 cell 条件 ETA {eta_window[0]}–{eta_window[1]} min"
        batch_name = "stage-a-beta050-calibration-r2-a0350-L060"
        batch_pid = "待启动"
        next_window = "本地门、上传和启动完成后安排"
        progress_text = f"R1 validator pass={terminal.get('validator_pass', 0)}；accepted-only 写入处理中"
    elif state == "stage_a_r2_running":
        r2_snapshot = r2_retry.get("health_snapshot", {})
        verdict_label = "R2 单点 64-sweep 重试正在运行"
        verdict_why = "R1 已有 7 个控制器 accepted 与 3 个 L80 校准 accepted；R2 只重算唯一方差超门点，不覆盖 R1 失败证据。"
        eta_window = r2_retry.get("conditional_eta_minutes", [30, 60])
        eta = f"{eta_window[0]}–{eta_window[1]} min；预计 {r2_snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r2_retry["run_id"]
        batch_pid = r2_retry["pid_receipt"]
        next_window = r2_retry["next_read_window"]
        progress_text = f"R2 0/1；当前 {r2_snapshot.get('current_cell', '待读取')}，{r2_snapshot.get('requested_sweeps', 64)} sweeps"
    elif state == "stage_a_r2_success_validation_pending":
        r2_terminal = r2_retry.get("terminal", {})
        verdict_label = "R2 远端成功 · 独立 checksum 与 validator 进行中"
        verdict_why = "两个初态均完成64 sweeps，Sz=0方差约4.3e-11且远端内部门全通过；只有独立validator通过后才更新controller并启动剩余13 cells。"
        eta = "R2 已终态；本地续跑包并行准备，尚未上传"
        batch_name = r2_retry["run_id"]
        batch_pid = r2_retry["pid_receipt"]
        next_window = r2_retry["next_read_window"]
        progress_text = f"R2 1/1远端成功；validator={r2_terminal.get('independent_validator', 'pending')}"
    elif state == "stage_a_r3_preparing":
        verdict_label = "R2 独立验收通过 · R3 剩余 13 cells 准备中"
        verdict_why = "失败 action 已由64-sweep结果幂等替换为accepted并保留R1失败证据；控制器仍为WAITING且不赋相名。"
        eta_window = r3_continuation.get("conditional_eta_hours", [6, 10])
        eta = f"R3 条件 ETA {eta_window[0]}–{eta_window[1]} h"
        batch_name = "stage-a-beta050-calibration-r3-remaining13"
        batch_pid = "待启动"
        next_window = "本地门、上传和启动完成后安排"
        progress_text = "controller accepted=8、pending=8；L80 calibration accepted=3"
    elif state == "stage_a_r3_running":
        r3_snapshot = r3_continuation.get("health_snapshot", {})
        verdict_label = "R3 剩余 13 cells 正在严格顺序运行"
        verdict_why = "R2 已独立验收并接入controller；R3带全局锁、PID和唯一Julia门，继续补齐Stage A，失败即停。"
        eta_window = r3_continuation.get("conditional_eta_hours", [6, 10])
        eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {r3_snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r3_continuation["run_id"]
        batch_pid = r3_continuation["pid_receipt"]
        next_window = r3_continuation["next_read_window"]
        progress_text = f"R3 {r3_snapshot.get('completed_cells', 0)}/{r3_snapshot.get('planned_cells', 13)}；当前 {r3_snapshot.get('current_cell', '待读取')}"
    elif state == "stage_a_r3_failed_validation_pending":
        r3_terminal = r3_continuation.get("terminal", {})
        verdict_label = "R3 已由严格门停止 · 独立回传验收进行中"
        verdict_why = f"完成 {r3_terminal.get('completed_cells', 0)}/{r3_terminal.get('planned_cells', 13)} 后，{r3_terminal.get('failed_cell', '未知 cell')} 返回1；stderr为空且Julia已退出，具体失败门待validator。"
        eta = "R3 已终态；查明失败门后按32→64策略决定续跑"
        batch_name = r3_continuation["run_id"]
        batch_pid = r3_continuation["pid_receipt"]
        next_window = r3_continuation["next_read_window"]
        progress_text = f"R3完成 {r3_terminal.get('completed_cells', 0)}/{r3_terminal.get('planned_cells', 13)}；失败点 {r3_terminal.get('failed_cell', '未知')}"
    elif state == "stage_a_r4_preparing":
        r3_terminal = r3_continuation.get("terminal", {})
        failed_values = r3_terminal.get("failed_values", {})
        verdict_label = "R3 独立验收 2 pass / 1 fail · R4 单点重试准备中"
        verdict_why = f"唯一失败点 {r4_retry.get('cell', '未知')} 的两个初态仅Sz=0方差略超门（{failed_values.get('center', float('nan')):.3e}、{failed_values.get('ferro_j2', float('nan')):.3e} > 1e-8）。"
        eta_window = r4_retry.get("conditional_eta_minutes", [20, 40])
        eta = f"R4 单 cell 条件 ETA {eta_window[0]}–{eta_window[1]} min"
        batch_name = "stage-a-beta050-calibration-r4-a0250-L060"
        batch_pid = "待启动"
        next_window = "本地门、上传和启动完成后安排"
        progress_text = "R3通过项accepted-only写入中；失败项无value/error"
    elif state == "stage_a_r4_running":
        r4_snapshot = r4_retry.get("health_snapshot", {})
        verdict_label = "R4 单点 64-sweep 重试正在运行"
        verdict_why = (
            "R3通过项已accepted-only接入；R4仅重算alpha=-0.25、L60的Sz=0方差超门点，不覆盖R3失败证据。"
            f"Stage A剩余{r5_preparation.get('cell_count', 10)} cells的R5本地包已预检，只有R4严格通过后才释放。"
        )
        eta_window = r4_retry.get("conditional_eta_minutes", [20, 40])
        eta = f"{eta_window[0]}–{eta_window[1]} min；预计 {r4_snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r4_retry["run_id"]
        batch_pid = r4_retry["pid_receipt"]
        next_window = r4_retry["next_read_window"]
        progress_text = f"R4 0/1；当前 {r4_snapshot.get('current_cell', '待读取')}，{r4_snapshot.get('requested_sweeps', 64)} sweeps"
    elif state == "stage_a_r5_running":
        r5_snapshot = r5_preparation.get("health_snapshot", {})
        verdict_label = "R4 严格通过 · R5 剩余 10 cells 正在运行"
        verdict_why = (
            "R4 已完成远端/本地 checksum、独立 validator 与 accepted-only 接入；"
            "controller 为 success=10、failed=0、pending=6。R5 以单并发补齐 Stage A，不覆盖历史失败证据。"
        )
        eta_window = r5_preparation.get("conditional_eta_hours", [5, 8])
        eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {r5_snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r5_preparation["run_id"]
        batch_pid = r5_preparation["pid_receipt"]
        next_window = r5_preparation["next_read_window"]
        progress_text = (
            f"R5 {r5_snapshot.get('completed_cells', 0)}/{r5_snapshot.get('planned_cells', 10)}；"
            f"当前 {r5_snapshot.get('current_cell', '待读取')}，{r5_snapshot.get('requested_sweeps', 64)} sweeps"
        )
    elif state == "stage_a_r6_running":
        r6_snapshot = r6_retry.get("health_snapshot", {})
        r5_terminal = r5_preparation.get("terminal", {})
        failed_values = r5_terminal.get("failed_variance", {})
        variance_values = [value for key, value in failed_values.items() if key != "threshold"]
        verdict_label = "R5 验收 1 pass / 1 fail · R6 单点重试运行中"
        verdict_why = (
            "R5 的 alpha=-0.25、L80 校准已接纳；alpha=-0.10、L40 仅方差门失败。"
            f"R6 按32→64 sweeps重试，原方差范围约 {min(variance_values or [float('nan')]):.3e}–"
            f"{max(variance_values or [float('nan')]):.3e}，门槛仍为1e-8。"
        )
        eta_window = r6_retry.get("conditional_eta_minutes", [15, 30])
        eta = f"{eta_window[0]}–{eta_window[1]} min；预计 {r6_snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r6_retry["run_id"]
        batch_pid = r6_retry["pid_receipt"]
        next_window = r6_retry["next_read_window"]
        progress_text = f"R6 0/1；当前 {r6_snapshot.get('current_cell', '待读取')}，{r6_snapshot.get('requested_sweeps', 64)} sweeps"
    elif state == "stage_a_r7_running":
        r7_snapshot = r7_continuation.get("health_snapshot", {})
        r6_terminal = r6_retry.get("terminal", {})
        sensitivity = r6_terminal.get("initial_state_sensitivity", {})
        verdict_label = "R6 技术验收通过 · R7 剩余 8 cells 正在运行"
        verdict_why = (
            "R6 已将alpha=-0.10、L40接入controller，但双初态Rpi半差"
            f"{sensitivity.get('half_difference', float('nan')):.3e}作为系统误差保留；"
            "R7继续补齐Stage A，未将该点当作高精度相界证据。"
        )
        eta_window = r7_continuation.get("conditional_eta_hours", [3, 6])
        eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {r7_snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r7_continuation["run_id"]
        batch_pid = r7_continuation["pid_receipt"]
        next_window = r7_continuation["next_read_window"]
        progress_text = (
            f"R7 {r7_snapshot.get('completed_cells', 0)}/{r7_snapshot.get('planned_cells', 8)}；"
            f"当前 {r7_snapshot.get('current_cell', '待读取')}"
        )
    elif state == "stage_a_r8_running":
        r8_snapshot = r8_retry.get("health_snapshot", {})
        verdict_label = "R7 首点严格失败 · R8 32→64 sweeps 重试运行中"
        verdict_why = (
            "R7的alpha=-0.10、L60双初态方差超1e-8，center还出现负gap；"
            "R8保持方差、非负gap、截断与Sz门不变，只增加sweeps。"
        )
        eta_window = r8_retry.get("conditional_eta_minutes", [15, 30])
        eta = f"{eta_window[0]}–{eta_window[1]} min；预计 {r8_snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r8_retry["run_id"]
        batch_pid = r8_retry["pid_receipt"]
        next_window = r8_retry["next_read_window"]
        progress_text = f"R8 0/1；当前 {r8_snapshot.get('current_cell', '待读取')}，{r8_snapshot.get('requested_sweeps', 64)} sweeps"
    elif state == "stage_a_r9_running":
        r9_snapshot = r9_continuation.get("health_snapshot", {})
        r8_terminal = r8_retry.get("terminal", {})
        verdict_label = "R8 严格验收通过 · R9 剩余 7 cells 正在运行"
        verdict_why = (
            "R8 的远端/本地 checksum、非覆盖回传和独立 validator 全部通过，"
            f"controller 为 success={r8_terminal.get('controller_counts', {}).get('success', 12)}、failed=0；"
            "R9 单并发补齐 Stage A，历史失败证据和 R6 双初态系统误差均保留。"
        )
        eta_window = r9_continuation.get("conditional_eta_hours", [3, 5])
        eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {r9_snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r9_continuation["run_id"]
        batch_pid = r9_continuation["pid_receipt"]
        next_window = r9_continuation["next_read_window"]
        progress_text = (
            f"R9 {r9_snapshot.get('completed_cells', 0)}/{r9_snapshot.get('planned_cells', 7)}；"
            f"当前 {r9_snapshot.get('current_cell', '待读取')}"
        )
    elif state == "stage_a_r9_failed_validation_complete":
        terminal = r9_continuation.get("terminal", {})
        failed = terminal.get("failed_variance", {})
        verdict_label = "R9 独立验收 1 pass / 1 fail · R10 单点重试准备中"
        verdict_why = (
            "alpha=-0.10、L80 已通过全部严格门；alpha=-0.05、L40 的两个初态仅 Sz=0/Sz=1 方差超 1e-8，"
            f"范围 {min(v for k, v in failed.items() if k != 'threshold'):.3e}–"
            f"{max(v for k, v in failed.items() if k != 'threshold'):.3e}。程序正常、stderr为空，其余门全部通过。"
        )
        eta = "R10 单 cell 64-sweep 条件 ETA 15–30 min；通过后续跑剩余5 cells"
        batch_name = "stage-a-beta050-calibration-r10-a0050-L040"
        batch_pid = "待本地证据接入与上传门通过"
        next_window = r9_continuation.get("next_read_window", "R10 启动后安排")
        progress_text = "R9 物化2/7；validator=1 pass / 1 fail；其余5 cells未启动"
    elif state == "stage_a_r10_running":
        snapshot = r10_retry.get("health_snapshot", {})
        ingestion = r9_continuation.get("ingestion", {})
        verdict_label = "R9 严格接入完成 · R10 64-sweep 单点重试运行中"
        verdict_why = (
            f"R9 已接入 controller={ingestion.get('controller_counts', {})}、L80 calibration={ingestion.get('calibration_accepted_total', 6)}；"
            "R10 只重算 alpha=-0.05、L40 的方差超门点，所有物理与数值门保持不变。"
        )
        eta_window = r10_retry.get("conditional_eta_minutes", [10, 25])
        eta = f"{eta_window[0]}–{eta_window[1]} min；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r10_retry["run_id"]
        batch_pid = r10_retry["pid_receipt"]
        next_window = r10_retry["next_read_window"]
        progress_text = f"R10 0/1；当前 {snapshot.get('current_cell', '待读取')}，{snapshot.get('requested_sweeps', 64)} sweeps"
    elif state == "stage_a_r10_failed_validation_complete":
        terminal = r10_retry.get("terminal", {})
        center = terminal.get("center", {})
        verdict_label = "R10 独立验收失败 · R11 64→128 sweeps 重试准备中"
        verdict_why = (
            "ferro_j2 初态已通过全部门；center 的 Sz=0 方差为 "
            f"{center.get('variance_per_site_sz0', float('nan')):.3e}，且 gap={center.get('spin_gap', float('nan')):.3e}，"
            "分别未过 1e-8 与 -1e-8 门。程序、checksum、回传和其余门正常。"
        )
        eta = "R11 单 cell 128-sweep 条件 ETA 15–35 min；通过后续跑剩余5 cells"
        batch_name = "stage-a-beta050-calibration-r11-a0050-L040"
        batch_pid = "待本地证据接入与上传门通过"
        next_window = r10_retry.get("next_read_window", "R11 启动后安排")
        progress_text = "R10 validator fail；controller保持12 success / 1 failed / 3 pending"
    elif state == "stage_a_r11_running":
        snapshot = r11_retry.get("health_snapshot", {})
        verdict_label = "R10 失败 provenance 已锁定 · R11 128-sweep 重试运行中"
        verdict_why = (
            "R10 的 ferro_j2 初态通过，center 仅方差与 gap 门失败；R11 使用既定 32→64→128 的最后一级预算，"
            "不改变方差、gap、截断、Sz 或 full-q 门。若仍失败，该点保持 NotEvaluable。"
        )
        eta_window = r11_retry.get("conditional_eta_minutes", [20, 45])
        eta = f"{eta_window[0]}–{eta_window[1]} min；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r11_retry["run_id"]
        batch_pid = r11_retry["pid_receipt"]
        next_window = r11_retry["next_read_window"]
        progress_text = f"R11 0/1；当前 {snapshot.get('current_cell', '待读取')}，{snapshot.get('requested_sweeps', 128)} sweeps"
    elif state == "stage_a_r12_preparing":
        terminal = r11_retry.get("terminal", {})
        verdict_label = "R11 最终预算严格通过 · R12 剩余 5 cells 准备中"
        verdict_why = (
            f"R11 双初态全部通过，最大方差 {terminal.get('maximum_variance_per_site', float('nan')):.3e}，"
            f"最小 gap {terminal.get('minimum_gap', float('nan')):.3e}；远端/本地 checksum、非覆盖回传与独立 validator 均通过。"
        )
        eta = "R12 参数预算与失败 provenance 接入完成后给出；仍保持单并发"
        batch_name = "stage-a-beta050-calibration-r12-remaining5"
        batch_pid = "待本地门与上传"
        next_window = r11_retry.get("next_read_window", "R12 启动后安排")
        progress_text = "R11 validator pass；accepted-only 接入与 R12 本地包生成中"
    elif state == "stage_a_r12_running":
        snapshot = r12_continuation.get("health_snapshot", {})
        ingestion = r11_retry.get("ingestion", {})
        verdict_label = "R11 已严格接入 · R12 剩余 5 cells 正在运行"
        verdict_why = (
            f"controller={ingestion.get('controller_counts', {})}、calibration={ingestion.get('calibration_accepted_total', 6)}；"
            "R12 对 alpha=-0.05、L60 保守采用64 sweeps，其余按32/64预算，单并发且首失败即停。"
        )
        eta_window = r12_continuation.get("conditional_eta_hours", [1.0, 2.5])
        eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r12_continuation["run_id"]
        batch_pid = r12_continuation["pid_receipt"]
        next_window = r12_continuation["next_read_window"]
        progress_text = (
            f"R12 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 5)}；"
            f"当前 {snapshot.get('current_cell', '待读取')}，{snapshot.get('requested_sweeps', 64)} sweeps"
        )
    elif state == "stage_a_r13_preparing":
        terminal = r12_continuation.get("terminal", {})
        verdict_label = "R12 首点严格失败 · R13 L60 64→128 sweeps 准备中"
        verdict_why = (
            "alpha=-0.05、L60 的两个初态仅 Sz=1 方差超门："
            f"{terminal.get('variance_per_site_sz1', float('nan')):.3e} > 1e-8；"
            "Sz=0 方差、gap、截断、Sz 与 full-q 文件均通过。其余4点未启动。"
        )
        eta = "R13 单 cell 128-sweep 条件 ETA 25–50 min；通过后续跑剩余4 cells"
        batch_name = "stage-a-beta050-calibration-r13-a0050-L060"
        batch_pid = "待本地证据接入与上传门通过"
        next_window = r12_continuation.get("next_read_window", "R13 启动后安排")
        progress_text = "R12物化1/5且validator fail；剩余4 cells未启动"
    elif state == "stage_a_r13_running":
        snapshot = r13_retry.get("health_snapshot", {})
        verdict_label = "R12 失败 provenance 已锁定 · R13 L60 128-sweep 重试运行中"
        verdict_why = (
            "R12 的两个初态仅 Sz=1 方差未过门，R13 使用该点最后一级 128-sweep 预算；"
            "所有门槛不变，失败则保持 NotEvaluable，成功后才续跑其余4点。"
        )
        eta_window = r13_retry.get("conditional_eta_minutes", [20, 45])
        eta = f"{eta_window[0]}–{eta_window[1]} min；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r13_retry["run_id"]
        batch_pid = r13_retry["pid_receipt"]
        next_window = r13_retry["next_read_window"]
        progress_text = f"R13 0/1；当前 {snapshot.get('current_cell', '待读取')}，128 sweeps"
    elif state == "stage_a_r14_preparing":
        terminal = r13_retry.get("terminal", {})
        verdict_label = "R13 最终预算严格通过 · R14 剩余 4 cells 准备中"
        verdict_why = (
            f"R13 双初态全部通过，最大方差 {terminal.get('maximum_variance_per_site', float('nan')):.3e}，"
            f"最小 gap {terminal.get('minimum_gap', float('nan')):.3e}；checksum、非覆盖回传和独立 validator 均通过。"
        )
        eta = "R14 保守预算与 provenance 接入完成后给出；仍为单并发"
        batch_name = "stage-a-beta050-calibration-r14-remaining4"
        batch_pid = "待本地门与上传"
        next_window = r13_retry.get("next_read_window", "R14 启动后安排")
        progress_text = "R13 validator pass；accepted-only 接入与剩余4点本地包生成中"
    elif state == "stage_a_r14_running":
        snapshot = r14_continuation.get("health_snapshot", {})
        ingestion = r13_retry.get("ingestion", {})
        verdict_label = "R13 已严格接入 · R14 剩余 4 cells 正在运行"
        verdict_why = (
            f"controller={ingestion.get('controller_counts', {})}、calibration={ingestion.get('calibration_accepted_total', 6)}；"
            "R14 四点均采用64 sweeps、双初态、单并发且首失败即停，所有验收门保持不变。"
        )
        eta_window = r14_continuation.get("conditional_eta_hours", [1.0, 2.0])
        eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r14_continuation["run_id"]
        batch_pid = r14_continuation["pid_receipt"]
        next_window = r14_continuation["next_read_window"]
        progress_text = (
            f"R14 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 4)}；"
            f"当前 {snapshot.get('current_cell', '待读取')}"
        )
    elif state == "stage_a_r15_preparing":
        terminal = r14_continuation.get("terminal", {})
        failed = terminal.get("failed_variance", {})
        verdict_label = "R14 首个 L80 校准点严格失败 · R15 64→128 sweeps 准备中"
        verdict_why = (
            "alpha=-0.05、L80 的方差仅略超门："
            f"center Sz1={failed.get('center_sz1', float('nan')):.3e}，"
            f"ferro_j2 Sz0/Sz1={failed.get('ferro_j2_sz0', float('nan')):.3e}/"
            f"{failed.get('ferro_j2_sz1', float('nan')):.3e} > 1e-8；"
            "gap、截断、Sz、q_count、checksum 和文件门均正常。"
        )
        eta_window = r15_retry.get("conditional_eta_minutes", [20, 50])
        eta = f"R15 单 cell 最终预算条件 ETA {eta_window[0]}–{eta_window[1]} min；通过后续跑剩余3 cells"
        batch_name = r15_retry.get("run_id", "stage-a-beta050-calibration-r15-a0050-L080")
        batch_pid = "待本地门与上传"
        next_window = r15_retry.get("next_read_window", "R15 启动后安排")
        progress_text = "R14物化1/4且validator fail；alpha=-0.025三个 cells 未启动"
    elif state == "stage_a_r15_running":
        snapshot = r15_retry.get("health_snapshot", {})
        verdict_label = "R14 失败 provenance 已锁定 · R15 L80 128-sweep 重试运行中"
        verdict_why = (
            "R14 仅方差门未过；R15 使用该校准点最后一级128-sweep预算。"
            "若仍失败则保持 NotEvaluable，不增加预算或降低任何门槛。"
        )
        eta_window = r15_retry.get("conditional_eta_minutes", [20, 50])
        eta = f"{eta_window[0]}–{eta_window[1]} min；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r15_retry["run_id"]
        batch_pid = r15_retry["pid_receipt"]
        next_window = r15_retry["next_read_window"]
        progress_text = f"R15 0/1；当前 {snapshot.get('current_cell', '待读取')}，128 sweeps"
    elif state == "stage_a_blocked_final_tier":
        terminal = r15_retry.get("terminal", {})
        center = terminal.get("center", {})
        bounded = status.get("stage_a_bounded_outcome", {})
        verdict_label = "R15 最终预算严格失败 · Stage A 保持 NotEvaluable"
        verdict_why = (
            "R15 的两种初态均通过方差、截断、Sz 与 full-q 门，但 center 初态的 gap="
            f"{center.get('spin_gap', float('nan')):.3e} < -1e-8；ferro_j2 初态通过。"
            "64→128预算已用尽，不再加预算或降低门槛，因此不能赋相名或相界。"
        )
        eta = "无自动续算；若扩大预算或改变判据，需作者作出新的方法学决定"
        batch_name = r15_retry.get("run_id", "stage-a-beta050-calibration-r15-a0050-L080")
        batch_pid = r15_retry.get("pid_receipt", "已终态")
        next_window = "自动服务器监控停止；等待作者决定"
        counts = bounded.get("controller_counts", {})
        progress_text = (
            f"controller={counts}；accepted calibration={bounded.get('accepted_calibration', 6)}；"
            f"未物化={len(bounded.get('unmaterialized_cells', []))} cells"
        )
    elif state == "stage_a_r16_preparing":
        terminal = r15_retry.get("terminal", {})
        center = terminal.get("center", {})
        verdict_label = "R15 诊断为初态亚稳 · R16 收敛协议修复准备中"
        verdict_why = (
            f"R15 center 的 gap={center.get('spin_gap', float('nan')):.3e}，但方差已过门且末段能量仍明显下降；"
            "作者已批准三初态、256 sweeps 与新增能量平台门。原方差、gap、截断和Sz门全部保留。"
        )
        eta_window = r16_repair.get("conditional_eta_minutes", [50, 75])
        eta = f"单 cell 条件 ETA {eta_window[0]}–{eta_window[1]} min"
        batch_name = r16_repair.get("run_id", "stage-a-beta050-calibration-r16-a0050-L080")
        batch_pid = "待本地测试与上传"
        next_window = "R16 启动后按实测 ETA 安排"
        progress_text = "R16代码、三初态run spec、能量平台validator和非覆盖上传包生成中"
    elif state == "stage_a_r16_running":
        snapshot = r16_repair.get("health_snapshot", {})
        verdict_label = "R16 三初态收敛修复正在运行"
        verdict_why = (
            "center_random、ferro_j2、domain 三初态均需通过原数值门和 |ΔE_last|≤1e-8 能量平台门；"
            "三初态的 Sz=0/Sz=1 能量极差还须≤1e-6；任何一条失败都不会接入accepted-only结果。"
        )
        eta_window = r16_repair.get("conditional_eta_minutes", [50, 75])
        eta = f"{eta_window[0]}–{eta_window[1]} min；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r16_repair["run_id"]
        batch_pid = r16_repair["pid_receipt"]
        next_window = r16_repair["next_read_window"]
        progress_text = (
            f"R16 0/1；当前 {snapshot.get('current_cell', '待读取')} / "
            f"{snapshot.get('current_start', '待读取')}，{snapshot.get('current_sweep', 0)}/256 sweeps"
        )
    elif state in {"stage_a_r16_practical_adjudication", "stage_a_r16_practical_accepted"}:
        practical = r16_repair.get("practical_adjudication", {})
        verdict_label = "R16 严格平台门失败 · 实用校准判定通过" if practical.get("accepted") else "R16 严格平台门失败 · 实用校准审理中"
        verdict_why = (
            "三个初态均完成256 sweeps，程序、checksum、方差、截断、Sz、full-q与非负gap门通过；"
            "唯一数值失败是末步能量变化约4.60e-8–5.26e-8，高于预先声明的1e-8。"
            "三初态基态能量极差9.87e-7，因此按作者批准仅把平台门放宽到1e-7，"
            "结果只作实用L80校准，不用于高精度相界。"
        )
        eta = "R16 已终态；alpha=-0.025 三尺寸补点后完成 Stage A 物理诊断"
        batch_name = r16_repair.get("run_id", "stage-a-beta050-calibration-r16-a0050-L080")
        batch_pid = r16_repair.get("pid_receipt", "已终态")
        next_window = r16_repair.get("next_read_window", "待释放剩余3 cells")
        progress_text = (
            f"严格验收=fail；实用校准={'accepted' if practical.get('accepted') else 'pending'}；"
            f"boundary_eligible={practical.get('boundary_eligible', False)}"
        )
    elif state == "stage_a_r17_running":
        practical = r16_repair.get("practical_adjudication", {})
        snapshot = r17_continuation.get("health_snapshot", {})
        verdict_label = "R16 实用校准已接入 · R17 最后三尺寸正在运行"
        verdict_why = (
            "R16三初态仅放宽末步能量平台门到1e-7，并标记boundary_eligible=false；"
            "R17补齐alpha=-0.025的L40/L60/L80，仍使用原方差、gap、截断、Sz和full-q门，"
            "任何失败即停。"
        )
        eta_window = r17_continuation.get("conditional_eta_hours", [0.8, 1.8])
        eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r17_continuation["run_id"]
        batch_pid = r17_continuation["pid_receipt"]
        next_window = r17_continuation["next_read_window"]
        progress_text = (
            f"R17 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 3)}；"
            f"当前 {snapshot.get('current_cell', '待读取')}；R16 calibration={practical.get('accepted_calibration_total', 7)}"
        )
    elif state == "stage_a_r18_running":
        snapshot = r18_retry.get("health_snapshot", {})
        failed = r17_continuation.get("terminal", {}).get("failed_values", {})
        verdict_label = "R17 仅方差轻微超门 · R18 最终128-sweep重试运行中"
        verdict_why = (
            "R17的两个初态程序、checksum、gap、截断、Sz与full-q门均通过；"
            f"唯一失败是Sz=1方差/site={failed.get('center', float('nan')):.3e}>1e-8。"
            "R18使用64→128的最后一级预算，不降低数值门；该失败不构成不存在新相的证据。"
        )
        eta_window = r18_retry.get("conditional_eta_minutes", [15, 35])
        eta = f"{eta_window[0]}–{eta_window[1]} min；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r18_retry.get("run_id", "stage-a-beta050-calibration-r18-a0025-L040")
        batch_pid = r18_retry.get("pid_receipt", "待读取")
        next_window = r18_retry.get("next_read_window", "按条件ETA读取")
        progress_text = (
            f"R18 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 1)}；"
            f"当前 {snapshot.get('current_cell', '待读取')}，128 sweeps"
        )
    elif state == "stage_a_r19_running":
        snapshot = r19_continuation.get("health_snapshot", {})
        r18_terminal = r18_retry.get("terminal", {})
        verdict_label = "R18 已严格补救通过 · R19 正在补齐最后两个尺寸"
        verdict_why = (
            "R17唯一失败是Sz=1方差轻微超门；R18以128 sweeps通过checksum、非覆盖回传和独立validator，"
            "证明失败来自收敛预算而非程序或相缺失。R19补齐alpha=-0.025的L60/L80，所有原门槛不变。"
        )
        eta_window = r19_continuation.get("conditional_eta_hours", [0.5, 1.2])
        eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r19_continuation.get("run_id", "stage-a-beta050-calibration-r19-remaining2")
        batch_pid = r19_continuation.get("pid_receipt", "待读取")
        next_window = r19_continuation.get("next_read_window", "按 recurring automation")
        counts = r18_terminal.get("controller_counts", {})
        progress_text = (
            f"R19 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 2)}；"
            f"当前 {snapshot.get('current_cell', '待读取')}；controller="
            f"{counts.get('success', 15)}/{counts.get('failed', 0)}/{counts.get('pending', 1)}"
        )
    elif state == "stage_b_r1_running":
        snapshot = stage_b.get("health_snapshot", {})
        r19_terminal = r19_continuation.get("terminal", {})
        verdict_label = "Stage A 24/24 严格闭合 · Stage B 正在映射二维负区"
        verdict_why = (
            "R19两点通过远端checksum、非覆盖回传、本地checksum和独立validator；"
            "Stage A控制器达到16/0/0、L80校准8点。beta=0.5显示alpha=-0.35到-0.25的"
            "候选动量重构，但是否为二维新相边界仍需Stage B六条beta切片检验。"
        )
        eta_window = stage_b.get("eta_hours", [18, 32])
        eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = stage_b.get("run_id", "stage-b-negative-coarse-r1-96")
        batch_pid = stage_b.get("pid_receipt", "待读取")
        next_window = stage_b.get("next_read_window", "按 recurring automation")
        progress_text = (
            f"Stage B {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 96)}；"
            f"当前 {snapshot.get('current_cell', '待读取')}；Stage A controller="
            f"{r19_terminal.get('controller_counts', {}).get('success', 16)}/0/0"
        )
    elif state == "stage_b_r2_running":
        r2 = stage_b.get("r2", {})
        snapshot = r2.get("health_snapshot", {})
        failed = stage_b.get("r1_terminal", {}).get("failed_values", {})
        verdict_label = "Stage B 首点仅方差超门 · R2 32→64 重试运行中"
        verdict_why = (
            "R1首点两个初态均正常完成，checksum、gap、截断、Sz和full-q文件通过；"
            f"Sz0方差/site为{failed.get('center', float('nan')):.2e}与"
            f"{failed.get('ferro_j2', float('nan')):.2e}。R2只提升该点到64 sweeps，"
            "其余95点保持原预算，不降低任何门槛。"
        )
        eta_window = r2.get("conditional_eta_hours", [18, 32])
        eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r2.get("run_id", "stage-b-negative-coarse-r2-96")
        batch_pid = r2.get("pid_receipt", "待读取")
        next_window = r2.get("next_read_window", "按 recurring automation")
        progress_text = (
            f"Stage B R2 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 96)}；"
            f"当前 {snapshot.get('current_cell', '待读取')}；唯一Julia={snapshot.get('julia_process_count', 1)}"
        )
    elif state == "stage_b_r3_running":
        r3 = stage_b.get("r3", {})
        snapshot = r3.get("health_snapshot", {})
        verdict_label = "Stage B R2 接纳首点 · R3 正在重试L60并续跑95点"
        verdict_why = (
            "alpha=-1、beta=0.05、L40在64 sweeps下严格通过；L60的32-sweep结果仅方差超门。"
            "R3将L60提升至64 sweeps，并在通过后顺序续跑其余94点；R2的通过结果单独保留，所有门槛不变。"
        )
        eta_window = r3.get("conditional_eta_hours", [18, 32])
        eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r3.get("run_id", "stage-b-negative-coarse-r3-remaining95")
        batch_pid = r3.get("pid_receipt", "待读取")
        next_window = r3.get("next_read_window", "按 recurring automation")
        progress_text = f"R3 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 95)}；当前 {snapshot.get('current_cell', '待读取')}；R2 accepted=1"
    elif state == "stage_b_r4_running":
        r4 = stage_b.get("r4", {}); snapshot = r4.get("health_snapshot", {})
        verdict_label = "Stage B 已严格接纳2点 · R4重试第三点并续跑94点"
        verdict_why = "alpha=-1、beta=.05的L40/L60均已在64 sweeps通过；alpha=-.75的L40仅Sz0方差超门。R4将该点升至64 sweeps并续跑其余93点，门槛不变。"
        eta_window = r4.get("conditional_eta_hours", [18, 32]); eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r4.get("run_id", "stage-b-negative-coarse-r4-remaining94"); batch_pid = r4.get("pid_receipt", "待读取"); next_window = r4.get("next_read_window", "按 recurring automation")
        progress_text = f"R4 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 94)}；当前 {snapshot.get('current_cell', '待读取')}；累计accepted=2"
    elif state == "stage_b_r5_running":
        r5 = stage_b.get("r5", {}); snapshot = r5.get("health_snapshot", {})
        verdict_label = "Stage B 已严格接纳3点 · R5重试L60并续跑93点"
        verdict_why = "alpha=-1、beta=.05的L40/L60和alpha=-.75的L40已严格通过；alpha=-.75的L60仅方差略超门。R5将该点升至64 sweeps并续跑其余92点，门槛不变。"
        eta_window = r5.get("conditional_eta_hours", [18, 32]); eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r5.get("run_id", "stage-b-negative-coarse-r5-remaining93"); batch_pid = r5.get("pid_receipt", "待读取"); next_window = r5.get("next_read_window", "按 recurring automation")
        progress_text = f"R5 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 93)}；当前 {snapshot.get('current_cell', '待读取')}；累计accepted=3"
    elif state == "stage_b_r6_running":
        r6 = stage_b.get("r6", {}); snapshot = r6.get("health_snapshot", {})
        verdict_label = "Stage B 已严格接纳4点 · R6重试新L40并续跑92点"
        verdict_why = "R5的alpha=-.75、beta=.05、L60在64 sweeps严格通过；alpha=-.5的L40仅Sz0方差超门。R6只将该点升至64 sweeps并续跑其余91点，门槛不变。"
        eta_window = r6.get("conditional_eta_hours", [18, 32]); eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r6.get("run_id", "stage-b-negative-coarse-r6-remaining92"); batch_pid = r6.get("pid_receipt", "待读取"); next_window = r6.get("next_read_window", "按 recurring automation")
        progress_text = f"R6 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 92)}；当前 {snapshot.get('current_cell', '待读取')}；累计accepted=4"
    elif state == "stage_b_r7_running":
        r7 = stage_b.get("r7", {}); snapshot = r7.get("health_snapshot", {})
        verdict_label = "Stage B 已严格接纳5点 · R7重试L60并续跑91点"
        verdict_why = "R6的alpha=-.5、beta=.05、L40在64 sweeps严格通过；同参数L60的32-sweep结果仅Sz0方差略超门。R7只将该点升至64 sweeps并续跑其余90点。"
        eta_window = r7.get("conditional_eta_hours", [18, 32]); eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r7.get("run_id", "stage-b-negative-coarse-r7-remaining91"); batch_pid = r7.get("pid_receipt", "待读取"); next_window = r7.get("next_read_window", "按 recurring automation")
        progress_text = f"R7 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 91)}；当前 {snapshot.get('current_cell', '待读取')}；累计accepted=5"
    elif state == "stage_b_blocked_remote_connection":
        r7 = stage_b.get("r7", {}); snapshot = r7.get("health_snapshot", {}); monitor_state = r7.get("monitor_snapshot", {})
        verdict_label = "Stage B 暂停监控 · 服务器端口连续三次拒绝连接"
        verdict_why = "00:12、01:11、02:12三个预定窗口均为SSH端口6000拒绝连接。最后可信证据是22:11时R7健康运行8/91；连接失败不能证明Julia停止，因此不改写任何计算结论。"
        eta = "远端状态未知；连接恢复后按实际完成数重算"
        batch_name = r7.get("run_id", "stage-b-negative-coarse-r7-remaining91"); batch_pid = r7.get("pid_receipt", "待读取"); next_window = r7.get("next_read_window", "等待服务器恢复")
        progress_text = f"最后确认 {snapshot.get('completed_cells', 8)}/{snapshot.get('planned_cells', 91)}；连续连接失败={monitor_state.get('consecutive_failures', 3)}；累计accepted=5"
    elif state == "stage_b_r8_running":
        r8 = stage_b.get("r8", {}); snapshot = r8.get("health_snapshot", {})
        verdict_label = "服务器已恢复 · Stage B累计严格接纳15点"
        verdict_why = "R7在断联期间正常运行并产生10个严格通过点；失败的alpha=-.025、beta=.05、L60出现微小负gap且一个初态方差超门。R8按64→128最后一级预算重试，不降低任何门槛。"
        eta_window = r8.get("conditional_eta_hours", [16, 28]); eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r8.get("run_id", "stage-b-negative-coarse-r8-remaining81"); batch_pid = r8.get("pid_receipt", "待读取"); next_window = r8.get("next_read_window", "按 recurring automation")
        progress_text = f"R8 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 81)}；当前 {snapshot.get('current_cell', '待读取')}；累计accepted=15"
    elif state == "stage_b_r9_running":
        r9 = stage_b.get("r9", {}); snapshot = r9.get("health_snapshot", {})
        verdict_label = "Stage B累计严格接纳16点 · R9进入beta=0.10切片"
        verdict_why = "R8的128-sweep补救同时消除了负gap和方差问题；beta=.10首个L40点仅ferro初态Sz0方差超门。R9将该点32→64并继续其余79点。"
        eta_window = r9.get("conditional_eta_hours", [16, 28]); eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r9.get("run_id", "stage-b-negative-coarse-r9-remaining80"); batch_pid = r9.get("pid_receipt", "待读取"); next_window = r9.get("next_read_window", "按 recurring automation")
        progress_text = f"R9 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 80)}；当前 {snapshot.get('current_cell', '待读取')}；累计accepted=16"
    elif state == "stage_b_r10_running":
        r10 = stage_b.get("r10", {}); snapshot = r10.get("health_snapshot", {})
        verdict_label = "Stage B累计严格接纳17点 · R10重试beta=0.10的L60"
        verdict_why = "R9的L40补救严格通过；同参数L60仅双初态Sz0方差超门。R10只将该点32→64并继续其余78点，上传断线经幂等hash重试后完整通过。"
        eta_window = r10.get("conditional_eta_hours", [16, 28]); eta = f"{eta_window[0]}–{eta_window[1]} h；预计 {snapshot.get('conditional_completion_window', '待校正')}"
        batch_name = r10.get("run_id", "stage-b-negative-coarse-r10-remaining79"); batch_pid = r10.get("pid_receipt", "待读取"); next_window = r10.get("next_read_window", "按 recurring automation")
        progress_text = f"R10 {snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', 79)}；当前 {snapshot.get('current_cell', '待读取')}；累计accepted=17"
    elif state == "stage_b_r10_terminal_fetch_pending":
        r10 = stage_b.get("r10", {}); terminal = r10.get("terminal", {})
        verdict_label = "R10已终态且远端checksum通过 · 非覆盖回传待恢复"
        verdict_why = "R10的L60补救已完成，下一L40点触发数值门；无Julia残留且stderr为空。两个cell的父/双子checksum均通过，但回传预览因本地权限审批服务两次超时尚未执行，因此不提前接纳任何新结果。"
        eta = "回传、validator与R11生成通常需10–20分钟"
        batch_name = r10.get("run_id", "stage-b-negative-coarse-r10-remaining79"); batch_pid = r10.get("pid_receipt", "待读取"); next_window = r10.get("next_read_window", "等待回传")
        progress_text = f"R10终态：completed={terminal.get('completed_cells', 1)}，failed={terminal.get('failed_cell', '待读取')}；累计accepted仍为17"
    else:
        verdict_label = "阶段 A 已启动 · 负区严格结果尚未回传"
        verdict_why = "正区 105 个 accepted 记录直接复用；旧负区 40×60 数据仅作探索背景。新批次必须通过 checksum、独立 validator 和有限尺寸 guard。"
        eta = f"{stage['estimated_hours'][0]}–{stage['estimated_hours'][1]} h"
        batch_name = stage["remote_batch"]
        batch_pid = stage["pid_receipt"]
        next_window = stage["next_read_window"]
        progress_text = "尚无可接纳负区记录"
    return {
        "title": "2026-08-09 负 alpha 完整相图 campaign",
        "note": "范围扩展为 -1<=alpha<=1、0<=beta<=1；参考 Fig.3 对齐，Fig.9 仍排除。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": verdict_label,
                "why": verdict_why,
            },
            {
                "kind": "kv",
                "pairs": [
                    ["服务器批次", f"{batch_name} · PID {batch_pid}"],
                    ["阶段 A", f"{stage['cells']} cells；beta=0.5；L=40/60/80；并发 {stage['concurrency']}"],
                    ["当前进度", progress_text],
                    ["alpha 网格", ", ".join(str(value) for value in stage["alpha"])],
                    ["条件 ETA", eta],
                    ["下次读取窗口", next_window],
                    ["持续检查", f"recurring heartbeat 每 {monitor['interval_hours']} h；不是一次性检查"],
                    ["服务器启动前负载", f"load={server['load_average'][0]:.2f}；available RAM={server['memory_available_gib']} GiB；因此单 cell 顺序"],
                ],
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "figures/full_alpha_phase_evidence_20260811.png",
                        "caption": (
                            "完整 alpha 范围的当前证据相图。a，二维证据分区：正 alpha 为已严格覆盖的常规 q=pi 临界区，"
                            "负 alpha 仍以斜线表示待分类区，alpha=0 为解耦奇异线；b，beta=0.5 的 q_peak/pi 显示"
                            "alpha=-0.35 到 -0.25 的动量重分配；c，R(L=60)-R(L=40) 在同一区间反号，"
                            "但尚不满足0.025边界门；d，R16只未通过1e-8能量平台门，1e-7实用门可接纳。"
                            "橙色空心点为boundary-ineligible实用校准，不能单独据此命名新相。"
                        ),
                    },
                    {
                        "src": "figures/full_alpha_tentative_phase_diagram_20260811.png",
                        "caption": (
                            "较宽松的物理假说相图。正区为有限尺寸数据支持的有效S=1/2、q=pi无隙反铁磁区；"
                            "深负区按强耦合图像暂标为有效S≈3/2、q≈0.6pi、弦/边缘活跃的候选非公度临界区；"
                            "靠近alpha=0的负区暂标为低置信的公度临界区。alpha=0是解耦三聚体+跨胞二聚体奇异线。"
                            "只有beta=0.5的橙色区间由数值校准，负区二维着色是待Stage B/C检验的假说，不是最终相界。"
                        ),
                    },
                    {
                        "src": "figures/full_alpha_working_phase_diagram_20260812.png",
                        "caption": (
                            "宽松判定下的工作相图与有限尺寸证据。当前最合理的工作计数是三个体相区："
                            "深负alpha的q≈0.60pi非公度临界区、靠近零点负侧的q=pi公度临界区、"
                            "以及正alpha的q=pi无隙反铁磁区；alpha=0另作解耦高简并奇异线。"
                            "只有beta=0.5上alpha∈[-0.35,-0.25]的动量重构带已有L40/60/80校准，"
                            "其二维延伸仍是Stage B/C要检验的工作假说。"
                        ),
                    },
                ],
            },
            {
                "kind": "note",
                "label": "首批失败证据",
                "style": "warn",
                "text": (
                    f"程序门：{failure.get('program_failure', '无')}；数值门：{failure.get('numerical_failure', '无')}。"
                    f"远端/本地 checksum={failure.get('remote_checksum', '待定')}/{failure.get('local_checksum', '待定')}；"
                    f"科学接纳记录={failure.get('accepted_for_science', 0)}，没有降低阈值。"
                ),
            },
            {
                "kind": "table",
                "columns": ["阶段", "新增计算", "停止/推进门"],
                "rows": [
                    ["A", "beta=0.5；8 alpha×L40/60/80=24", "全 cell 严格验收，校准 q_peak 和负区初态"],
                    ["B", "其余 6 beta；8 alpha×L40/60=96", "失败即停；不铺满无必要的 L80"],
                    ["C", "显著 bracket 或诊断冲突点", "2 sigma、Delta alpha<=0.025、最终 L60/80"],
                    ["D", "合并正区 105 records 与 accepted 负区", "相名至少双诊断；生成图、source manifest 与 HTML"],
                ],
                "widths": ["12%", "42%", "46%"],
            },
            {
                "kind": "note",
                "label": "当前科学边界",
                "style": "pending",
                "text": "宽松口径下可暂按三个体相区组织文章：深负alpha非公度临界区、近零负侧公度临界区和正alpha无隙反铁磁区，alpha=0为奇异线。严格口径仍把q≈3pi/5到pi的变化记作候选Lifshitz动量重构；Stage B/C需验证其随beta的连续边界和双诊断一致性。",
            },
            {
                "kind": "code",
                "title": "验收入口",
                "text": "docs/full_phase_diagram_negative_standard_20260809.md\nresults/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/campaign-plan.json\nscripts/autoresearch_v5/fetch_negative_phase_run.py\nscripts/autoresearch_v5/validate_negative_phase_run.py\nscripts/autoresearch_v5/ingest_negative_phase_r17_success.py\nscripts/autoresearch_v5/analyze_negative_phase_stage_a.py\nscripts/autoresearch_v5/make_negative_phase_stage_b_r1.py\nscripts/autoresearch_v5/stage_negative_phase_stage_b_terminal.py\nscripts/autoresearch_v5/test_negative_phase_stage_b_terminal.py\nscripts/autoresearch_v5/analyze_negative_phase_stage_b.py\nscripts/autoresearch_v5/test_analyze_negative_phase_stage_b.py\nscripts/autoresearch_v5/make_negative_phase_stage_c_r1.py\nscripts/autoresearch_v5/launch_negative_phase_stage_c_r1.sh\nscripts/autoresearch_v5/upload_negative_phase_stage_c_r1.ps1\nresults/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/phase-diagram-v2/stage_a_finite_size_diagnostic_latest.json",
            },
        ],
    }


def update_canonical(doc: dict[str, object], staged: dict[str, str]) -> None:
    managed = {
        "2026-08-04 Fig.1–5 manuscript master 完成",
        "2026-08-04 研究进展、预计交付与人工介入",
        "2026-08-06 round43 production 终态交接",
        "2026-08-07 精简 full-q 复刻与本机收尾",
        "2026-08-09 负 alpha 完整相图 campaign",
        "2026-09-13 负 α 新相独立诊断",
    }
    sections = [section for section in doc.get("sections", []) if section.get("title") not in managed]
    sections.insert(0, manuscript_section(staged))
    sections.insert(0, progress_summary_section())
    if ROUND43_HANDOFF.is_file():
        handoff = json.loads(ROUND43_HANDOFF.read_text(encoding="utf-8"))
        if handoff.get("production_ready") is True and handoff.get("tag") == "Agreement":
            sections.insert(0, {
                "title": "2026-08-06 round43 production 终态交接",
                "note": "严格按远端 checksum、非覆盖回传、本地 checksum、validator 和 handoff 分流顺序完成；范围仅 0≤alpha,beta≤1。",
                "blocks": [
                    {"kind": "verdict", "status": "good", "label": "production_ready=true · Agreement", "why": "round43 q=π CV 五点全部通过，accepted11 与独立 TEBD 的 peak/weight 门均通过。"},
                    {"kind": "table", "columns": ["验收项", "结果", "证据"], "rows": [
                        ["远端终态", "success · 5/5 · returncode=0", "round43 status.json / progress.json"],
                        ["远端 checksum", "22/22 成功", "远端 checksums.sha256"],
                        ["本地回传与 validator", "22/22 checksum；validator=pass", "round43_qpi_cv_lowfreq_desc_validator_20260806.json"],
                        ["CV–TEBD 交叉分析", "Agreement；accepted11", "round43_handoff_final/handoff_summary.json"],
                    ], "widths": ["28%", "28%", "44%"]},
                    {"kind": "figures", "items": [{"src": "figures/round43_fig8_final_20260806_v2.png", "caption": "最终 Fig.8 production。accepted11 个 q=π CV 点与独立 TEBD 频谱叠加；round43 omega=0.00–0.20 补齐主峰左侧覆盖，peak/weight 门通过。结论限定于 alpha=0.23、beta=0.5、L=40、q=π，不外推到负 alpha、Fig.9、其他 q 或完整二维相图。"}]},
                    {"kind": "note", "label": "bounded 并行版本", "style": "info", "text": "独立 bounded HTML 和七点 Fig.8 保留原有 NotEvaluable/保守口径，用于审阅失败路径和证据边界；production 结果不会覆盖 bounded 文件。"},
                ],
            })
    if FULLQ_STATUS.is_file():
        sections.insert(0, fullq_section())
    if NEGATIVE_PHASE_STATUS.is_file():
        sections.insert(0, negative_phase_section())
    if NEGATIVE_PRACTICAL_STATUS.is_file():
        sections.insert(0, negative_practical_v2_section())
    if NEGATIVE_INDEPENDENT_AUDIT.is_file():
        sections.insert(0, negative_independent_audit_section())
    doc["sections"] = sections
    doc["eyebrow"] = "RESEARCH STATUS · UPDATED 2026-08-09 · FULL ALPHA PHASE CAMPAIGN"
    doc["lede"] = "1×5 Heisenberg 五聚体链复现与扩展进度。相图范围为 -1≤alpha≤1、0≤beta≤1，参考 Fig.3 对齐并排除 Fig.9；严格相界仍在计算，宽松工作图采用三个体相区加 alpha=0 奇异线，并保留数值失败 provenance。"


def build_current(doc: dict[str, object], staged: dict[str, str], history_count: int) -> dict[str, object]:
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    figures = json.loads(FIGURE_MANIFEST.read_text(encoding="utf-8"))
    remote = json.loads(REMOTE_SNAPSHOT.read_text(encoding="utf-8"))
    high150 = remote["cells"]["cell-l40-qpi-high-150"]["progress"]
    round41 = json.loads(ROUND41.read_text(encoding="utf-8")) if ROUND41.is_file() else {}
    schedule = json.loads(SCHEDULE.read_text(encoding="utf-8")) if SCHEDULE.is_file() else {}
    round41_terminal = json.loads(ROUND41_TERMINAL.read_text(encoding="utf-8")) if ROUND41_TERMINAL.is_file() else {}
    high150_current = json.loads(HIGH150_CURRENT.read_text(encoding="utf-8")) if HIGH150_CURRENT.is_file() else {}
    retry_current = json.loads(RETRY_CURRENT.read_text(encoding="utf-8")) if RETRY_CURRENT.is_file() else {}
    retry_health = json.loads(RETRY_HEALTH.read_text(encoding="utf-8")) if RETRY_HEALTH.is_file() else {}
    low000_plan = json.loads(LOW000_PLAN.read_text(encoding="utf-8")) if LOW000_PLAN.is_file() else {}
    bounded_audit = json.loads(BOUNDED_AUDIT.read_text(encoding="utf-8")) if BOUNDED_AUDIT.is_file() else {}
    repro_audit = json.loads(REPRO_AUDIT.read_text(encoding="utf-8")) if REPRO_AUDIT.is_file() else {}
    stage3_status = json.loads(STAGE3_STATUS.read_text(encoding="utf-8")) if STAGE3_STATUS.is_file() else {}
    round43_current = json.loads(ROUND43_CURRENT.read_text(encoding="utf-8")) if ROUND43_CURRENT.is_file() else {}
    round43_access = json.loads(ROUND43_ACCESS.read_text(encoding="utf-8")) if ROUND43_ACCESS.is_file() else {}
    round43_handoff = json.loads(ROUND43_HANDOFF.read_text(encoding="utf-8")) if ROUND43_HANDOFF.is_file() else {}
    fullq_status = json.loads(FULLQ_STATUS.read_text(encoding="utf-8")) if FULLQ_STATUS.is_file() else {}
    fullq_readiness = json.loads(FULLQ_READINESS.read_text(encoding="utf-8")) if FULLQ_READINESS.is_file() else {}
    negative_live = json.loads(NEGATIVE_PHASE_STATUS.read_text(encoding="utf-8")) if NEGATIVE_PHASE_STATUS.is_file() else {}
    independent_ready = NEGATIVE_INDEPENDENT_AUDIT.is_file()
    pilot_status = json.loads(NEGATIVE_INDEPENDENT_PILOT_STATUS.read_text(encoding="utf-8")) if NEGATIVE_INDEPENDENT_PILOT_STATUS.is_file() else {}
    pilot_complete = pilot_status.get("state") == "completed_with_localized_candidate" and NEGATIVE_INDEPENDENT_PILOT_ANALYSIS.is_file()
    size_path = RUN / "negative_entropy_sizes_status_20260914.json"
    size_status = json.loads(size_path.read_text(encoding="utf-8")) if size_path.is_file() else {}
    size_running = size_status.get("state") == "running"
    size_note = (f"10点尺寸核验已启动；批次PID {size_status.get('launch', {}).get('batch_pid')}；最近健康检查完成 {size_status.get('health', {}).get('completed_cells', 0)}/10，stderr为空。下次检查 {size_status.get('monitor', {}).get('next_check')}；3–5小时为条件预算。"
                 if size_running else "10点尺寸补算尚未进入运行状态；详见当前状态JSON。")
    if size_status.get("state") == "completed_validated":
        size_note = size_status["result_note"]
    fullq_production = fullq_status.get("production", {})
    production = round43_handoff.get("production_ready") is True and round43_handoff.get("tag") == "Agreement"
    low005 = round41.get("post_launch_verification", {}).get("low005", {})
    retry_status = retry_current.get("status")
    if production:
        server_current = "round43 阶段 B 已成功终态；5/5 点、远端/本地 checksum、validator 全部通过，accepted11 已组装"
        run_note = "CV 网格已覆盖 omega=0.00–0.20，主峰与 major-weight 窗门通过；本结果只适用于 alpha=0.23、beta=0.5、L=40、q=π。"
        current_eyebrow = ("CURRENT VIEW · UPDATED 2026-08-08 CST · FULL-Q PRODUCTION READY" if fullq_status.get("replan", {}).get("status") == "production_ready" else "CURRENT VIEW · UPDATED 2026-08-07 CST · ROUND43 AGREEMENT · FULL-Q RUNNING") if fullq_production.get("status") == "running" or fullq_status.get("replan", {}).get("status") == "production_ready" else "CURRENT VIEW · UPDATED 2026-08-06 CST · ROUND43 PRODUCTION AGREEMENT"
    elif round43_access.get("status") == "gateway_blocked":
        last = round43_access.get("last_authoritative_local_record", {})
        server_current = (
            "服务器未被本次 SSH 命令触达；最后可信本地记录为阶段 B 运行中，"
            f"{last.get('completed_points', '?')} 点、Julia PID {last.get('julia_pid', '?')}，"
            f"CPU {last.get('cpu_percent', '?')}%，RSS {last.get('rss_gib', '?')} GiB，stderr 为空"
        )
        run_note = "当前阻塞来自 Codex SSH 审批网关 503，不是 Julia 终态证据；不重启、不启动第二个 Julia、不下载。"
        current_eyebrow = "CURRENT VIEW · UPDATED 2026-08-06 18:09 CST · ROUND43 PHASE B ACCESS PENDING"
    elif round43_current.get("status") == "running":
        runtime = round43_current.get("runtime", {})
        if round43_current.get("phase") == "phase_b":
            server_current = (
                f"15:37 启动后核验：round43 阶段 B 运行中；Julia PID {runtime.get('julia_pid', '?')}，"
                f"{runtime.get('completed_points', 4)}/5 点，CPU {runtime.get('cpu_percent', '?')}%，"
                f"RSS {runtime.get('rss_gib', '?')} GiB，stderr 为空"
            )
            run_note = "阶段 A checksum 与四点 residual 已通过；单个 4 线程 Julia 只计算 omega=0.00。"
            current_eyebrow = "CURRENT VIEW · UPDATED 2026-08-06 15:37 CST · ROUND43 PHASE B RUNNING"
        else:
            server_current = (
                f"09:30 启动后核验：round43 阶段 A 运行中；Julia PID {runtime.get('julia_pid', '?')}，"
                f"{runtime.get('completed_points', 0)}/4 点，CPU {runtime.get('cpu_percent', '?')}%，"
                f"RSS {runtime.get('rss_gib', '?')} GiB，stderr 为空"
            )
            run_note = "单个 4 线程 Julia；按 omega=0.20→0.15→0.10→0.05 降频 warm-start，不启动第二个 Julia。"
            current_eyebrow = "CURRENT VIEW · UPDATED 2026-08-06 09:30 CST · ROUND43 PHASE A RUNNING"
    elif retry_status == "running":
        retry_remote = retry_current.get("remote", {})
        retry_progress = retry_current.get("post_launch_verification", {})
        elapsed = retry_health.get("elapsed", "1:01:09")
        cpu = retry_health.get("cpu_percent", 139)
        rss = retry_health.get("rss_kib", 1549684) / 1024**2
        server_current = (
            "high-150 已终态通过（omega=1.50；residual=5.540316e-6）；"
            f"retry omega=0.05 运行中，Julia {retry_remote.get('julia_pid', '?')}，"
            f"--threads={retry_remote.get('julia_threads', '?')}，{elapsed}，CPU {cpu}%，RSS {rss:.2f} GiB，"
            f"{retry_health.get('completed_points', retry_progress.get('completed_points', 0))}/"
            f"{retry_health.get('total_points', retry_progress.get('total_points', 1))} 点"
        )
        run_note = "只保留一个 4 线程 retry Julia；21:10 检查无错误，下一次 22:10 只读检查，不反复轮询。"
        current_eyebrow = "CURRENT VIEW · UPDATED 2026-08-05 21:10 CST · HIGH150 PASS · LOW005 RETRY HEALTHY"
    elif retry_status in {"success", "failed", "partial", "failed_acceptance"}:
        retry_remote = retry_current.get("remote", {})
        server_current = (
            "服务器目前不可连接，远端实时状态未知；最后一次已验证状态为 high-150 通过、"
            "retry omega=0.05 residual=1.17670e-5 且 accepted=false"
        )
        run_note = "round43 降频 warm-start 两阶段任务已在本地完成代码、合同测试和启动计划；尚未上传或启动。"
        current_eyebrow = "CURRENT VIEW · UPDATED 2026-08-06 CST · LOCAL WORK COMPLETE · ROUND43 STAGED"
    elif round41_terminal:
        elapsed = float(high150_current.get("elapsed_seconds", high150["elapsed_seconds"])) / 3600
        server_current = f"round31 3/4；high-150 仍为 julia_linsolve，07:42 时累计 {elapsed:.2f} h；round41 已终态但 residual 失败"
        run_note = "round41 已按止损规则排除，不再重试；服务器只保留 high-150 一个 Julia。"
        current_eyebrow = "CURRENT VIEW · 2026-08-05 07:42 CST · ROUND41 REJECTED · HIGH150 RUNNING"
    elif low005:
        server_current = (
            f"round31 3/4；high-150 仍为 {high150['phase']}；"
            f"round41 omega=0.05 已提交，Julia {low005['julia_pid']}，"
            f"--threads={low005['julia_command_threads']}，{low005['progress']['completed_points']}/{low005['progress']['total_points']} 点"
        )
        run_note = "high-150 与经预检批准的 4 线程 omega=0.05 smoke 并行；不再启动第三个 Julia。"
        current_eyebrow = "CURRENT VIEW · 2026-08-04 22:36 CST · CLAIMS 10/12 · DELIVERY 8/9"
    else:
        server_current = f"round31 3/4；high-150 处于 {high150['phase']}，18:37 时累计 {high150['elapsed_seconds']/3600:.2f} h"
        run_note = "high-150 运行中；尚未提交低频 smoke。"
        current_eyebrow = "CURRENT VIEW · 2026-08-04 18:37 CST · CLAIMS 10/12 · DELIVERY 8/9"
    if production and fullq_production.get("status") == "running":
        schedule_summary = (
            f"round43 已完成；{fullq_production.get('schedule', fullq_production.get('cell_id', 'full-q'))} 正在运行，"
            f"下一次 {fullq_production.get('next_check', '按计划')} 一次性只读检查，不启动第二个 Julia"
        )
    elif production:
        schedule_summary = "round43 已完成终态交接；后续只需作者审阅 HTML，不再自动启动新的 Julia"
    elif round43_access.get("status") == "gateway_blocked":
        schedule_summary = "17:40 只读检查未完成：SSH 审批网关返回 503；恢复后只做一次终态快照"
    elif round43_current.get("status") == "running":
        automation_id = round43_current.get("schedule", {}).get("automation_id", "未登记")
        if round43_current.get("phase") == "phase_b":
            schedule_summary = f"阶段 B 于 15:36:03 CST 启动；17:40 CST 一次性只读检查，automation={automation_id}"
        else:
            schedule_summary = f"阶段 A 于 09:28:35 CST 启动；15:30 CST 一次性只读检查，automation={automation_id}"
    elif retry_status == "running":
        schedule_summary = "21:10 已检查：仍健康求解；下一次一次性只读检查为 22:10 CST"
    elif retry_status == "failed_acceptance":
        schedule_summary = "服务器恢复后启动阶段 A；启动后 6 h 一次性检查，阶段 B 启动后 2 h 一次性检查"
    elif schedule.get("latest_update", {}).get("automation_effective"):
        schedule_summary = "high-150 24 h 边界检查已更新：8 月 5 日 15:07 CST，automation id=round31-high-150"
    elif schedule:
        schedule_summary = "已登记检查时间，但 Codex automation_update 未创建有效定时器"
    else:
        schedule_summary = "未登记一次性检查安排"
    if str(negative_live.get("status", "")).endswith("_running"):
        running_key = {
            "stage_a_r19_running": "r19_continuation",
            "stage_a_r18_running": "r18_retry",
            "stage_a_r17_running": "r17_continuation",
            "stage_a_r16_running": "r16_repair",
            "stage_a_r15_running": "r15_retry",
            "stage_a_r14_running": "r14_continuation",
            "stage_a_r13_running": "r13_retry",
            "stage_a_r12_running": "r12_continuation",
            "stage_a_r11_running": "r11_retry",
            "stage_a_r10_running": "r10_retry",
            "stage_a_r9_running": "r9_continuation",
            "stage_a_r8_running": "r8_retry",
        }.get(negative_live.get("status"), "r8_retry")
        retry = negative_live.get(running_key, {})
        schedule_summary = (
            f"负区 {retry.get('run_id', negative_live.get('status'))} 运行中；"
            f"{retry.get('next_read_window', '按 recurring automation')} 只读检查，不提前轮询"
        )
        current_eyebrow = "CURRENT VIEW · UPDATED 2026-08-11 CST · MANUSCRIPT DRAFT · NEGATIVE PHASE CAMPAIGN RUNNING"
    if independent_ready:
        server_current = "6点保存态扫描已成功终态；6/6父cell、12/12双初态和18份远端checksum通过，当前无残留Julia" if pilot_complete else "负区 Stage B 96/96 已解析，Stage C 29/29 已验收；当前没有登记中的远端 Julia，9月13日最近一次SSH连接被服务器关闭"
        schedule_summary = size_note if pilot_complete else "服务器恢复后只考虑6个保存态独立诊断点；不再重扫完整二维网格"
        current_eyebrow = "CURRENT VIEW · UPDATED 2026-09-14 CST · SAVED-STATE PILOT COMPLETE" if pilot_complete else "CURRENT VIEW · UPDATED 2026-09-13 CST · NEGATIVE-ALPHA INDEPENDENT AUDIT"
    if size_running or size_status.get("state") == "completed_validated":
        server_current = size_note
        current_eyebrow = "CURRENT VIEW · 2026-09-15 · " + ("SIZE DATA VALIDATED" if not size_running else "LOCALIZED SIZE SCAN RUNNING")
    latest_titles = [section.get("title", "") for section in doc.get("sections", [])[:8]]
    current_sections = [
            {
                "title": "Overview · 完成度与预计交付",
                "note": "以下均为有明确分母的工程与证据指标，不是主观论文百分比。",
                "blocks": [
                    {"kind": "verdict", "status": "warn" if negative_live else ("good" if production else "warn"), "label": ("六点保存态诊断完成；第二热力学相仍未确认" if pilot_complete else "负 α 静态扫描已闭合；新相独立诊断完成") if independent_ready else ("论文完整草稿已建立；负 alpha 相图仍在严格计算" if negative_live else "round43 production Agreement 已完成"), "why": ("β=0.75的波矢重构在独立观测量中保持平滑；β=0.25、α=-0.10出现单尺寸纠缠与初态敏感候选，但没有长程键序平台或扇区交叉。" if pilot_complete else "118个DMRG点、小系统ED、块自旋投影和L=40/60/80标度共同支持两个关联区，但尚不支持第二个热力学相；只剩近α=0的6点保存态定向检验。") if independent_ready else ("正区机制、q=pi Agreement 和 full-q 三组 dt/dt2 已验收并写入草稿；负区 Stage A–D 未完成前，相数、相名和边界保持空缺。" if negative_live else "round43 五点终态、双端 checksum、validator、accepted11 和 CV–TEBD peak/weight 门均通过。")},
                    {"kind": "kv", "pairs": [
                        ["论断证据覆盖", "12/12 supported or bounded；C10 production 与 C11 thermodynamic 强表述仍禁止"],
                        ["生产动态门", "已通过；production_ready=true、tag=Agreement、accepted11=11" if production else f"{dashboard['delivery_gates']['passed']}/{dashboard['delivery_gates']['total']} = 88.9%；final_dynamic_claim_gate 未通过"],
                        ["bounded 交付门", f"{bounded_audit.get('bounded_delivery_gates', {}).get('passed', 10)}/{bounded_audit.get('bounded_delivery_gates', {}).get('total', 10)}；HTML、图、数据、失败审计和复算入口齐全"],
                        ["图件", "Fig.1–5 已完成；Fig.6 exploratory、Fig.7 pilot；Fig.8 已生成 production 与独立 bounded 两个版本" if production else "Fig.1–5 已完成；Fig.6 exploratory、Fig.7 pilot、Fig.8 bounded 七点叠加"],
                        ["本地回归", "项目 .venv 完整发现集 74/74；round43 启动合同与终态交接定向测试 22/22；Python、Julia、bash 语法检查通过"],
                        ["复算命令链", f"{sum(repro_audit.get('checks', {}).values())}/{len(repro_audit.get('checks', {}))} 通过；" + ("round43 handoff exit=0 / Agreement" if production else "analyzer 退出码 2 对应 NotEvaluable/incomplete")],
                        ["服务器最近核验", server_current],
                        ["本机 full-q 准备", "complete；80/80 测试、inventory=111、合成端到端图 QA 通过" if fullq_readiness.get("local_work_complete") else "incomplete"],
                        ["full-q 当前 cell", f"{fullq_production.get('cell_id', '?')}；{fullq_production.get('status', 'unknown')}；PID {fullq_production.get('pid', '?')}"],
                        ["并行边界", run_note],
                        ["一次性检查", schedule_summary],
                    ]},
                    {"kind": "table", "columns": ["里程碑", "日期", "输出"], "rows": [
                        ["动态补救准备", "已完成", "round43 阶段 A/B launcher、降频 warm-start、严格门控与终态交接"],
                        ["图件冻结", "已完成", "Fig.6 exploratory、Fig.7 pilot、Fig.8 production + bounded 双版本"],
                        ["完整审阅稿", "已建立", "Title 至 Conclusion 全结构；负区结果段为受控占位符"],
                        ["最终相图与收束", "预计 8 月 13–15 日", "取决于 Stage A–C 是否触发 64/128 sweeps 重试"],
                    ], "widths": ["28%", "20%", "52%"]},
                ],
            },
            {
                "title": "Implemented · 已实现的工作",
                "note": "不仅有结果图，也已经形成可恢复、可验收、可复算的计算链。",
                "blocks": [
                    {"kind": "table", "columns": ["模块", "已实现内容", "当前状态"], "rows": [
                        ["模型与局域 ED", "五聚体完整多重态、总自旋/宇称、投影系数、q=π 谱权", "100 点正 alpha 扫描通过"],
                        ["有效理论", "一阶 J_eff 与二阶虚激发 J2；两/三单胞完整谱验证", "误差阶从 O(beta²) 推迟到 O(beta³)"],
                        ["静态长链", "双初态 DMRG、40/60/80 尺寸晋级、crossing guard、纠缠谱", "有边界完成"],
                        ["动力学", "CV oracle、checkpoint/warm-start、严格 q=π TEBD、dt/tmax/键维检查", "生产 Agreement 已通过；bounded 版本仍保留" if production else "方法通过；生产覆盖门冻结为 8/9"],
                        ["服务器运行", "离线 Julia 环境、进度 JSON、checksum、独立回传与 validator", server_current],
                        ["full-q 生产", "三个代表点、六个 run、三组 dt/dt2 handoff 与 2x3 绘图", "production_ready；最大峰漂移 0.01 J1"],
                        ["图表与报告", "Fig.1–5 manuscript master、Fig.6–8 边界图、双视图离线 HTML", "主页与完整历史分离"],
                    ], "widths": ["18%", "57%", "25%"]},
                ],
            },
            {
                "title": "Findings · 目前发现了什么",
                "note": "只列已经有数值证据或明确边界的发现。",
                "blocks": [
                    {"kind": "table", "columns": ["发现", "定量证据", "物理含义"], "rows": [
                        ["奇数单胞留下有效 S=1/2", "J_eff/beta = 0.4189–0.4396 > 0", "正 beta 投影为反铁磁有效链"],
                        ["q=π 存在严格动量过滤", "最低激发双重态变暗；四重态占 84.1%–97.6%", "局域高能通道主要由 S=3/2 多重态承载"],
                        ["弱的二阶有效挫折", "受控边缘 J2/J1 = 3.95%–5.19%", "五聚体内部虚激发产生反铁磁次近邻项"],
                        ["低能标度接近 c=1", "matched-size oracle 比值 1.024–1.033", "有限尺寸上支持反铁磁自旋链低能结构"],
                        ["正区未见可验收内部 crossing", "105 个成功记录；40/60/80 数据无稳定符号 bracket", "当前不能支持额外命名相界；这是有价值的否定结果"],
                        ["高预算控制点仍有初始化敏感性", "alpha=0.125, beta=1, L=80 双初态半差 1.79096e-3 > 1e-3", "可约束有限尺寸趋势，但不能独自支持二维相结构"],
                        ["动力学方法被独立验证", "L=10 CV 对精确谱相对 L2 误差 8.52e-12", "CV 实现本身不是当前瓶颈"],
                        ["严格 q=π TEBD 已收敛", "主峰 omega≈0.05；dt、tmax、maxdim 与 Fourier 复算通过", "TEBD 独立 Agreement；round43 已关闭 CV 低频覆盖" if production else "TEBD 本身可标 Agreement，当前缺口是 CV 频率覆盖"],
                        ["CV 与 TEBD 在共享窗一致", "round43 五点 omega=0.00–0.20 与既有七点共同形成 accepted11；peak/weight 门通过", "production CV–TEBD Agreement（仅限 alpha=0.23,beta=0.5,L=40,q=π）" if production else "high-150 已纳入；低频覆盖不足时仍标 NotEvaluable"],
                    ], "widths": ["30%", "30%", "40%"]},
                    {"kind": "note", "label": "最重要的新认识", "text": "五聚体不是四聚体结果的简单平移：奇数单胞强制保留半整数低能自由度，而局域多重态与动量选择定则共同决定高能谱权；二阶虚过程还生成弱有效挫折。"},
                ],
            },
            {
                "title": "Methods draft · 可复现方法草稿",
                "note": "这是供作者审阅的中文证据稿，不写入 paper/；参数、门槛和失败处理均来自已执行流程。",
                "blocks": [
                    {"kind": "list", "title": "模型与局域基底", "items": [
                        "研究对象为正耦合 1×5 自旋-1/2 Heisenberg 五聚体链，能量单位取 J1；参数范围限定为 0≤alpha,beta≤1。先对孤立五聚体完整对角化，按总自旋和反射宇称标记多重态，再计算 q=π 局域自旋算符的跃迁权重。",
                        "将最低偶宇称 S=1/2 双重态投影为每个五聚体的有效自旋。胞间交换在一阶产生 J_eff；二阶 Schrieffer–Wolff 虚激发给出次近邻有效耦合，并用两、三单胞完整谱检验误差阶。",
                    ]},
                    {"kind": "list", "title": "静态长链与有限尺寸判据", "items": [
                        "有限 OBC 链采用双初态 DMRG。每个候选点记录能量、方差、截断误差、实际键维和目标观测量；尺寸按 L=40、60、80 晋级。内部 crossing 只在尺寸差形成稳定符号 bracket 且通过 2σ 后成立。",
                        "纠缠谱按五类切口保存。中心荷解释不直接使用裸 log-L 拟合，而与相同有效单胞数的 c=1 Heisenberg oracle 比较，以隔离强奇偶振荡和边界效应。",
                    ]},
                    {"kind": "list", "title": "动力学与交叉验收", "items": [
                        "correction-vector DMRG 在 q=π、eta=0.1 下逐频点求解；每个频点要求 relative residual≤1e-5，并保存 checkpoint、manifest 和 SHA-256。失败频点不进入 accepted-only 组装。",
                        "TEBD 独立检查 dt、tmax、maxdim 和 Fourier 实现，并保留截断前原始谱。只有 CV 网格包围 TEBD 主峰、覆盖 [0,1.5] 窗，且 peak/weight 门同时通过，动态结论才可升级为 Agreement。",
                    ]},
                    {"kind": "note", "label": "复现入口", "text": "完整命令见 docs/reproducibility_commands_20260804.md；源数据和哈希见 source_data_inventory_20260804.json。"},
                ],
            },
            {
                "title": "Results draft · 结果与图注骨架",
                "note": "观察与解释分开；所有数字都可回到本地 manifest、CSV 或验收 JSON。",
                "blocks": [
                    {"kind": "verdict", "status": "good", "label": "局域低能自由度与有效交换已闭合", "why": "正 alpha 五聚体保留偶宇称 S=1/2 基态双重态；J_eff/beta=0.4189–0.4396>0。最低激发双重态在 q=π 变暗，四重态承载 84.1%–97.6% 的局域非弹性权重。"},
                    {"kind": "verdict", "status": "good", "label": "二阶机制提供了可检验的新内容", "why": "虚激发产生反铁磁 J2，受控边缘 J2/J1=3.95%–5.19%；纳入该项后，两/三单胞谱误差由 O(beta²) 推迟到 O(beta³)。"},
                    {"kind": "verdict", "status": "warn", "label": "正区静态结果支持有限尺寸有效链图景", "why": "105 条成功记录未给出可验收内部 crossing；matched-size c=1 比值为 1.024–1.033。两者都不构成热力学单相或无偏中心荷证明。"},
                    {"kind": "verdict", "status": "good" if production else "warn", "label": "CV–TEBD 动力学 Agreement 已通过" if production else "动力学局部一致但总体仍不可评价", "why": "round43 将 CV 网格扩展至 omega=0.00，主峰被包围且 major-weight 窗覆盖；peak/weight 两门和 validator 均通过。结论限定于 alpha=0.23、beta=0.5、L=40、q=π。" if production else "七个 accepted CV 点与 TEBD 的最大差为 6.40%，共享窗积分差为 1.53%；omega=1.50 点差仅 2.07%。主峰 omega≈0.05 与左端覆盖尚未关闭，因此保持 NotEvaluable。"},
                    {"kind": "table", "columns": ["图", "建议图注主句", "边界"], "rows": [
                        ["Fig.1", "五聚体链、局域多重态与低能 S=1/2 投影。", "局域 ED 与一阶有效链"],
                        ["Fig.2", "正 alpha 能级流揭示 q=π 的宇称过滤与四重态主导权重。", "不将局域跃迁直接命名为长链谱支"],
                        ["Fig.3", "40/60/80 有限尺寸诊断未给出可验收内部 crossing。", "不是热力学相图证明"],
                        ["Fig.4", "五类切口纠缠谱与 matched-size c=1 oracle 相符。", "保留有限尺寸限定"],
                        ["Fig.5", "有效链、二阶挫折与局域选择定则形成统一机制图。", "不创造未经 DSF 验证的准粒子"],
                        ["Fig.6–8", "Fig.6 exploratory、Fig.7 pilot；Fig.8 同时提供 production Agreement 和 bounded 保守版本。" if production else "正区动力学按证据等级冻结：Fig.6 exploratory、Fig.7 pilot、Fig.8 bounded。", "Agreement 仅限 round43 覆盖的 L=40、q=π 点；不外推为完整二维相图" if production else "生产门 8/9；不得升级为完整谱 Agreement"],
                    ], "widths": ["12%", "55%", "33%"]},
                ],
            },
            {
                "title": "Discussion draft · 物理解释与结论边界",
                "note": "该部分解释结果，不重复逐图叙述。",
                "blocks": [
                    {"kind": "note", "label": "中心解释", "text": "与偶数自旋单胞不同，五聚体的奇数自旋数强制留下半整数低能自由度。正 beta 将这些有效 S=1/2 自旋反铁磁耦合，因此低能标度自然接近 c=1 链；与此同时，五聚体内部多重态和反射宇称决定 q=π 的高能可见通道。"},
                    {"kind": "note", "label": "新增机制", "text": "二阶反铁磁 J2 表明 1×5 并非参考 1×4 结论的尺寸替换。它给出弱而可量化的有效挫折，但当前受控比值不足以单独支持新相或新准粒子。"},
                    {"kind": "note", "label": "竞争解释", "text": "正区未见 crossing 可能反映同一低能相，也可能来自有限尺寸、观测量灵敏度或当前网格分辨率。由于最弱高预算点仍有初始化敏感性，本文只报告“当前有限尺寸数据未见可验收 crossing”。"},
                    {"kind": "note", "label": "动力学边界", "style": "info" if production else "pending", "text": "round43 五点 omega=0.00–0.20 全部通过 residual、双端 checksum 和 validator；主峰与 major-weight 窗门通过，因此 alpha=0.23、beta=0.5、L=40、q=π 的 CV–TEBD 可标 Agreement。该结论不外推到负 alpha、Fig.9、其他 q、其他尺寸或完整二维相图。" if production else "CV 实现已由 exact oracle 验证，TEBD 也通过内部收敛，high-150 已通过。low-005 retry 因 residual=1.17670e-5 超过 1e-5 被隔离，round42 未启动；低频主峰未被 CV 包围，因此总体保持 NotEvaluable，Fig.6–8 按 exploratory、pilot、bounded 交付。"},
                    {"kind": "verdict", "status": "good" if production else "warn", "label": "建议结论", "why": "当前证据支持正耦合五聚体链的低能有效 S=1/2 反铁磁链图景、局域 q=π 选择定则、弱二阶挫折，以及限定于 alpha=0.23、beta=0.5、L=40、q=π 的 CV–TEBD Agreement；热力学相结构和完整二维相图仍保留边界。"},
                ],
            },
            {
                "title": "Human decisions · 需要人工介入的地方",
                "note": "round43 已完成终态交接；当前只需作者审阅主报告与独立 bounded 版本。",
                "blocks": [
                    {"kind": "table", "columns": ["时间", "需要决定", "默认方案", "不决定的影响"], "rows": [
                        ["现在", "是否接受 C11 的有限尺寸表述", "推荐接受：不强行命名二维相界", "若坚持强主张，需要新增序参量/临界标度计算"],
                        ["已决策", "low-005 是否满足 residual 与 validator", "未通过；失败结果隔离，门槛不降低", "round43 使用新降频 warm-start 策略补救"],
                        ["计算后", "是否接受 L=40 production Agreement", "已通过固定门控；作者审阅限定范围", "不应外推到其他 q、尺寸或完整二维相图"],
                        ["审阅后", "是否授权把 HTML 结论迁入 paper/", "继续先在 HTML 审阅和修改", "未授权时只能完成研究包，不能宣称 TeX 论文定稿"],
                        ["投稿前", "目标期刊、作者顺序、数据仓库与署名信息", "由作者人工确认", "这些不能由计算结果自动决定"],
                    ], "widths": ["14%", "34%", "30%", "22%"]},
                    {"kind": "verdict", "status": "good", "label": "计算交接已完成", "why": "round43 production_ready=true、tag=Agreement；主报告已更新，bounded 版本独立保留。" if production else "阶段 A 已通过门控，阶段 B 正在运行；17:40 只读检查后按终态自动分流。"},
                ],
            },
            {
                "title": "Paper figures · 当前图件",
                "note": "Fig.1–5 为双栏 183 mm 静态最终稿；SVG/PDF 保留可编辑文本。",
                "blocks": manuscript_section(staged)["blocks"][1:5],
            },
            {
                "title": "Remaining work · 剩余路径与风险",
                "note": "只保留会影响最终结论或交付的任务。",
                "blocks": [
                    {"kind": "table", "columns": ["图", "当前等级", "参考角色", "生产缺口"], "rows": [
                        ["Fig.6", figures["figures"]["Fig. 6"]["status"], "alpha=1 的正 beta DSF 路径", "生产 CV/TEBD 与镜像动量"],
                        ["Fig.7", figures["figures"]["Fig. 7"]["status"], "正 alpha 代表路径", "L=40 pilot 尚未关闭动态门"],
                        ["Fig.8", "production_agreement + bounded_seven_point_overlay" if production else "bounded_seven_point_overlay", "连续谱与局域分支叠加", "production 版本已通过 peak/weight 门；bounded 版本保留失败路径与保守边界" if production else "分支绘图器已就绪；等待 round43 低频五点关闭主峰左侧覆盖"],
                    ], "widths": ["12%", "18%", "30%", "40%"]},
                    {"kind": "verdict", "status": "good" if production else "warn", "label": "Fig.8 production 与 bounded 双版本已交付" if production else "Fig.8 已按 bounded 等级交付", "why": "最终 production Fig.8 使用 accepted11 与 round43 交叉分析；独立 bounded Fig.8 仍保留七点和失败路径，二者均不外推为完整二维相图。" if production else "七个 accepted q=π CV 点、TEBD 曲线与失败 low-005 标记已同图呈现；它不等同于参考论文的完整 DSF+解析色散。"},
                    {"kind": "list", "title": "严格顺序", "items": [
                        "round43 脚本已通过本地/远端 SHA-256 核对；确认无 Julia 后，阶段 A 已于 09:28:35 CST 启动。",
                        "阶段 A 已按 omega=0.20→0.15→0.10→0.05 完成；远端 checksum 与四点 residual 全部通过。",
                        "阶段 B 从 omega=0.05 checkpoint 继续计算 omega=0.00，已于 16:04 CST 成功终态，5/5 点。",
                        "已依次完成远端 checksum、非覆盖回传、本地 22/22 checksum、validate_cv_run.py、accepted11 组装与 CV–TEBD 分析。",
                        "finalize_round43_handoff.py 已把 validator、五点网格、11 点组装和 bounded/production 分流固化为单一非覆盖入口。",
                        "round43 五点全部通过，因此本参数点升级为 production Agreement；bounded 版本仍保持 NotEvaluable 以作为保守交付对照。",
                    ]},
                    {"kind": "note", "label": "计算状态", "style": "info", "text": "round43 阶段 A 的四点与远端 checksum 通过；阶段 B 于 15:36:03 CST 启动并于 16:04:56 CST 成功终态。五点 residual 均为 0.0，远端/本地 checksum 和 validator 全部通过，handoff_summary.json 给出 production_ready=true、tag=Agreement。" if production else "round43 阶段 A 已于 12:35:55 CST 结束，远端 checksum 和四点 residual 均通过。阶段 B 已于 15:36:03 CST 启动，只计算 omega=0.00；17:40 CST 做一次只读检查."},
                ],
            },
            {
                "title": "Evidence map · 文件与完整历史",
                "note": f"完整历史共 {history_count} 节；主页只保留当前判断。",
                "blocks": [
                    {"kind": "kv", "pairs": [
                        ["交付预测", "paper_completion_forecast_20260804.json"],
                        ["静态图 manifest", "paper_static_figures_manifest_20260804.json"],
                        ["完成度仪表盘", "research_completion_dashboard_20260804.json"],
                        ["完整事件源", "report.json"],
                        ["完整历史 HTML", "report_history.html"],
                        ["图件资产清单", "report_assets_manifest_20260804.json"],
                        ["源数据清单", "source_data_inventory_20260804.json / .md / .sha256"],
                        ["复算命令", "docs/reproducibility_commands_20260804.md"],
                        ["补充材料计划", "docs/supplementary_materials_plan_20260804.md"],
                        ["代理执行规范", "docs/agent_execution_standard.md"],
                        ["round41 提交记录", "round41_qpi_cv_low005_submission_20260804.json"],
                        ["round41 retry 记录", "round41_qpi_cv_low005_retry_submission_20260805.json"],
                        ["high-150 本地 validator", "round31_high150_validator_20260805.json"],
                        ["high-150 回传 receipt", "round31_high150_fetch_receipt_20260805.json"],
                        ["七点 CV–TEBD", "results/autoresearch_v5_20260805/round40_cv_tebd_accepted7_analysis/cross-method-check.json"],
                        ["round42 条件计划", LOW000_PLAN.name if low000_plan else "尚未生成"],
                        ["bounded 交付审计", BOUNDED_AUDIT.name if bounded_audit else "尚未生成"],
                        ["复算命令审计", REPRO_AUDIT.name if repro_audit else "尚未生成"],
                        ["独立 bounded manuscript", "bounded_manuscript_20260805.html"],
                        ["当前 bounded manuscript", "bounded_manuscript_20260806.html"],
                        ["round43 计算计划", "docs/round43_compute_plan_20260805.md"],
                        ["round43 launcher 合同测试", "scripts/autoresearch_v5/test_round43_launchers.py"],
                        ["round43 阶段 A 提交记录", ROUND43_CURRENT.name if round43_current else "尚未生成"],
                        ["round43 终态交接器", "scripts/autoresearch_v5/finalize_round43_handoff.py"],
                        ["round43 handoff 结果", "results/autoresearch_v5_20260806/round43_handoff_final_v2/handoff_summary.json" if production else "尚未生成"],
                        ["round43 accepted11", "results/autoresearch_v5_20260806/round43_handoff_final_v2/accepted11/manifest.json" if production else "尚未生成"],
                        ["Fig.8 production", "figures/round43_fig8_final_20260806_v2.png/.svg/.pdf/.tiff" if production else "尚未生成"],
                        ["round43 本地 validator", "results/research_progress/round43_qpi_cv_lowfreq_desc_validator_20260806.json" if production else "尚未生成"],
                        ["round43 Fig.8 分支绘图器", "scripts/autoresearch_v5/plot_fig8_round43_branch.py"],
                        ["Fig.8 bounded 分支 QA", "figures/round43_fig8_branch_dryrun_bounded_20260806_v2.qa.json"],
                        ["round43 live status", "docs/round43_live_status_20260806.md"],
                        ["失败路径 dry-run", "results/autoresearch_v5_20260806/round43_handoff_dryrun_failed005/handoff_summary.json"],
                        ["retry launcher", "scripts/autoresearch_v5/launch_round41_qpi_cv_low005_retry_20260805.sh"],
                        ["automation 记录", "automation_schedule_20260804.json"],
                        ["full-q 计划", "minimal_fullq_campaign_20260807/campaign_plan.json"],
                        ["full-q 本机审计", "minimal_fullq_local_readiness_20260807.json"],
                        ["full-q validator", "scripts/autoresearch_v5/validate_fullq_tebd_run.py"],
                        ["full-q handoff", "scripts/autoresearch_v5/finalize_minimal_fullq_handoff.py"],
                        ["full-q 绘图", "scripts/autoresearch_v5/plot_minimal_fullq_campaign.py"],
                    ]},
                    {"kind": "list", "title": "最近记录", "items": latest_titles},
                ],
            },
        ]
    if FULLQ_STATUS.is_file():
        current_sections.insert(1, fullq_section())
    draft = next(
        (
            section
            for section in doc.get("sections", [])
            if section.get("title") == "2026-08-11 论文完整草稿 · evidence-locked"
        ),
        None,
    )
    if draft is None:
        draft = next((section for section in doc.get("sections", []) if section.get("title") == "2026-08-07 论文草稿与结论判断"), None)
    else:
        # 新稿已覆盖三段旧摘要，主页避免重复。
        duplicate_titles = {
            "Methods draft · 可复现方法草稿",
            "Results draft · 结果与图注骨架",
            "Discussion draft · 物理解释与结论边界",
        }
        current_sections = [section for section in current_sections if section.get("title") not in duplicate_titles]
    if draft is not None:
        current_sections.insert(1, draft)
    if NEGATIVE_PHASE_STATUS.is_file():
        current_sections.insert(1, negative_phase_section())
    if NEGATIVE_PRACTICAL_STATUS.is_file():
        current_sections.insert(1, negative_practical_v2_section())
    if NEGATIVE_INDEPENDENT_AUDIT.is_file():
        current_sections.insert(1, negative_independent_audit_section())
    robustness = ROOT / "results/autoresearch_v5_20260913/pilot_entropy_robustness_20260914/report.json"
    if robustness.is_file():
        audit_doc = json.loads(robustness.read_text(encoding="utf-8"))
        current_sections.insert(0, {
            "title": "收尾状态：尺寸数据已验收，物理判定待完成" if size_status.get("state") == "completed_validated" else "收尾状态：局部异常仍待尺寸核验",
            "blocks": [
                {"kind": "verdict", "status": "warn", "label": "未确认第二个相，也未证明全域只有一个相", "why": "六点计算已通过验收；取消高 R² 筛选并考虑单元奇偶后，α=-0.10、β=0.25的有效纠缠斜率仍偏低。"},
                {"kind": "text", "text": size_note},
                *size_status.get("report_blocks", []),
                *audit_doc["sections"][1]["blocks"],
                {"kind": "note", "text": "下方历史分析图中的中心荷采用旧的高 R² 类别筛选，只保留为探索证据。小的有限距离连接关联、通过非负 gap 验收，都不能单独排除其他相。后续用统一分析规则比较尺寸，不凭 q 峰切换命名相。"},
            ],
        })
    joint_path = ROOT / "results/autoresearch_v5_20260919/closeout_stage1_joint_v2/report.json"
    stage1_inserted = False
    if joint_path.is_file():
        joint_doc = json.loads(joint_path.read_text(encoding="utf-8"))
        joint_blocks = copy.deepcopy(joint_doc["sections"][1]["blocks"])
        for block in joint_blocks:
            if block.get("kind") == "figures":
                for item in block["items"]:
                    item["src"] = str(joint_path.parent / item["src"])
        current_sections.insert(0, {
            "title": "9月19日收尾阶段1：联合尺寸证据",
            "blocks": [
                {"kind": "text", "text": "十二点重新验收并核对84个原始来源，生成纠缠、扇区gap和键关联联合图。历史 Stage1 记录中的 α=-0.10、L=80 两初态 gap 全差/均值 12.65% 属于旧 k=3 快照，不能当作当前 k=8 结果；本轮 L=80 k=8 两点已终态成功并通过独立验收，α=-0.10 新 gap≈7.2772×10⁻⁵、α=-0.175 新 gap≈1.5871×10⁻⁴。当前 648 条对照仍为 audit_only，物理稳定性未宣称。"},
                *joint_blocks,
                {"kind": "note", "text": "下一阶段优先统一局域投影、晶胞动量和胞内谱权重机制，再决定最多两个困难点的收敛对照。不是继续加密全域相图，也尚未完成整个研究项目。"},
            ],
        })
        stage1_inserted = True
        current_eyebrow = "CURRENT VIEW · 2026-09-19 · JOINT SIZE EVIDENCE"
    stage2_path = ROOT / "results/autoresearch_v5_20260919/near_zero_alpha_mechanism_report_v2/report.json"
    stage2_inserted = False
    if stage2_path.is_file():
        try:
            stage2_doc = json.loads(stage2_path.read_text(encoding="utf-8"))
            stage2_blocks = [{"kind": "text", "text": stage2_doc.get("lede", "")}]
            for section in stage2_doc.get("sections", []):
                stage2_blocks.append({
                    "kind": "card",
                    "title": section.get("title", ""),
                    "blocks": copy.deepcopy(section.get("blocks", [])),
                })
            current_sections.insert(1 if stage1_inserted else 0, {
                "title": "收尾阶段2：近零点交换的独立检验",
                "note": "由独立 8-spin oracle 报告整合；若输入报告缺失，主页保持原有内容。",
                "blocks": stage2_blocks,
            })
            stage2_inserted = True
        except (OSError, json.JSONDecodeError, TypeError, AttributeError):
            pass
    if STAGE3_STATUS.is_file() and STAGE3_REPORT.is_file():
        try:
            stage3_status = json.loads(STAGE3_STATUS.read_text(encoding="utf-8"))
            stage3 = stage3_status.get("stage3", {})
            latest_preflight = stage3_status.get("scope_guards", {}).get("remote_preflight", {}).get("latest_read_only_check", {})
            dependency = stage3_status.get("dependency_preparation", {})
            wheel = dependency.get("wheel", {})
            historical_upload_rejection = stage3_status.get("execution_upload_rejected", {})
            compatibility_script = stage3.get("compatibility_script", {})
            compatibility_upload_current = stage3.get("compatibility_upload_current", {}) or compatibility_script
            first_launcher = stage3.get("first_launcher", {})
            current_release_status = stage3_status.get("overall_status", stage3.get("status", "unknown"))
            payload_bytes = historical_upload_rejection.get("payload_bytes", "unknown")
            try:
                payload_bytes_display = f"{int(payload_bytes):,}"
            except (TypeError, ValueError):
                payload_bytes_display = str(payload_bytes)
            def _as_dict(value):
                return value if isinstance(value, dict) else {}

            def _as_bool(value):
                if isinstance(value, bool):
                    return value
                if isinstance(value, (int, float)) and value in (0, 1):
                    return bool(value)
                text = str(value).strip().lower()
                if text in {"true", "yes", "started", "running", "pass", "passed", "healthy"}:
                    return True
                if text in {"false", "no", "stopped", "not_started", "failed", "error"}:
                    return False
                return None

            launch_receipt = (
                _as_dict(stage3.get("launch_receipt"))
                or _as_dict(stage3.get("startup_receipt"))
                or _as_dict(stage3.get("execution_receipt"))
            )
            health_receipt = (
                _as_dict(stage3.get("health_receipt"))
                or _as_dict(stage3.get("runtime_health_receipt"))
                or _as_dict(stage3_status.get("health_receipt"))
            )
            terminal_receipt = (
                _as_dict(stage3.get("terminal_receipt_current"))
                or _as_dict(stage3.get("terminal_receipt"))
                or _as_dict(stage3_status.get("terminal_receipt"))
            )
            remote_started_raw = launch_receipt.get(
                "remote_julia_started",
                launch_receipt.get("julia_started", stage3.get("remote_julia_started", "unknown")),
            )
            remote_started_bool = _as_bool(remote_started_raw)
            remote_julia_started = "unknown" if remote_started_bool is None else str(remote_started_bool).lower()
            candidate_validated_bool = _as_bool(stage3.get("candidate_validated", "unknown"))
            health_raw = health_receipt.get("status", health_receipt.get("health", stage3.get("runtime_health_status", "not_recorded")))
            health_status = str(health_raw)
            terminal_raw = terminal_receipt.get("status", stage3.get("terminal_status", stage3.get("terminal_state", "pending")))
            terminal_status = str(terminal_raw).strip().lower()
            terminal_failure = any(token in terminal_status for token in ("failed", "failure", "timed_out", "timeout", "error", "cancelled", "killed"))
            terminal_success = any(token in terminal_status for token in ("success", "completed", "passed", "pass"))
            current_status_lower = str(current_release_status).lower()
            if terminal_failure:
                stage3_verdict_status = "bad"
                stage3_verdict_label = f"L=80 对照终态：{terminal_raw}"
            elif terminal_success and candidate_validated_bool is True:
                stage3_verdict_status = "good"
                stage3_verdict_label = "L=80 对照已验收（按当前状态字段）"
            elif terminal_success:
                stage3_verdict_status = "warn"
                stage3_verdict_label = f"L=80 运行终态：{terminal_raw}；candidate 尚待验收"
            elif candidate_validated_bool is True:
                stage3_verdict_status = "good"
                stage3_verdict_label = "L=80 对照已验收（按当前状态字段）"
            elif remote_started_bool is True:
                stage3_verdict_status = "warn"
                stage3_verdict_label = "L=80 对照已启动；候选结果尚待验收"
            elif any(token in current_status_lower for token in ("failed", "rejected", "blocked", "error")):
                stage3_verdict_status = "bad"
                stage3_verdict_label = "L=80 对照尚未启动；当前上传/启动状态需处理"
            else:
                stage3_verdict_status = "warn"
                stage3_verdict_label = "L=80 对照尚未启动"
            stage3_note = (
                f"状态字段驱动：overall_status={current_release_status}；"
                f"remote_julia_started={remote_julia_started}；"
                f"launch_receipt={launch_receipt.get('status', 'not_recorded')}；"
                f"health_receipt={health_status}；terminal_receipt={terminal_raw}。"
            )
            stage3_index = (1 if stage1_inserted else 0) + (1 if stage2_inserted else 0)
            current_sections.insert(stage3_index, {
                "title": "收尾阶段3：静态对照准备",
                "note": stage3_note,
                "blocks": [
                    {"kind": "verdict", "status": stage3_verdict_status, "label": stage3_verdict_label, "why": f"状态 {stage3.get('status', 'unknown')}；local_k8_calibration_verified={stage3.get('local_k8_calibration_verified', False)}，local_k8_save_enriched_verified={stage3.get('local_k8_save_enriched_verified', False)}，launch_ready={stage3.get('launch_ready', False)}，candidate_present={stage3.get('candidate_present', False)}，candidate_validated={stage3.get('candidate_validated', 'unknown')}。"},
                    {"kind": "text", "text": "baseline_v2 已核对 2 个 L=80 点、4 个初态、checksums 与 Practical V2 validator；本地 L=10 v4 两个 k=8 保存态/增强诊断点通过本次总能量门，历史四点 all_cases_gate 仍保留 v1 k=3 Sz=0 失败。"},
                    {"kind": "text", "text": f"最新只读预检 {latest_preflight.get('asof', 'unknown')}：{latest_preflight.get('target', 'unknown')}；项目相关 Python={latest_preflight.get('project_python_count', 'unknown')}，本用户 Julia={latest_preflight.get('user_julia_count', 'unknown')}；固定 Julia={latest_preflight.get('fixed_julia', {}).get('version', 'unknown')}；运行健康回执 status={health_status}，remote_julia_started={remote_julia_started}，progress={health_receipt.get('progress', health_receipt.get('progress_status', 'not_recorded'))}；terminal_receipt={terminal_raw}。"},
                    {"kind": "text", "text": f"NumPy 独立 ED 预检依赖状态={dependency.get('status', 'unknown')}；uploaded={dependency.get('uploaded', 'unknown')}；uploaded_sha256_verified={dependency.get('uploaded_sha256_verified', 'unknown')}；local_wheel_present={dependency.get('local_wheel_present', 'unknown')}；cleanup_receipt_observed={dependency.get('cleanup_receipt_observed', 'unknown')}；wheel={wheel.get('path', 'unknown')}；SHA256={wheel.get('sha256', 'unknown')}；不等同 Julia 计算成功。"},
                    {"kind": "text", "text": f"当前发布状态={current_release_status}；73 文件上传哈希={stage3.get('upload_hash_verification', 'unknown')}；首个 launcher={first_launcher.get('status', 'unknown')}（Julia started={str(first_launcher.get('julia_started', 'unknown')).lower()}）；兼容脚本本地测试={compatibility_upload_current.get('local_test', compatibility_script.get('local_test', 'unknown'))}，当前上传={compatibility_upload_current.get('status', compatibility_upload_current.get('upload_status', compatibility_script.get('upload_status', 'unknown')))}，重启={compatibility_upload_current.get('restart_performed', compatibility_script.get('restart_performed', 'unknown'))}，SHA256={compatibility_upload_current.get('remote_sha256', compatibility_upload_current.get('sha256', compatibility_script.get('sha256', 'unknown')))}；remote_julia_started={remote_julia_started}。"},
                    {"kind": "text", "text": f"历史外传审核记录（不代表当前状态）：status={historical_upload_rejection.get('status', 'unknown')}；files={historical_upload_rejection.get('payload_file_count', 'unknown')} payload + {historical_upload_rejection.get('control_manifest_file_count', 'unknown')} control manifest = {historical_upload_rejection.get('total_file_count', 'unknown')}；payload_bytes={payload_bytes_display}；{historical_upload_rejection.get('intercept_reason', '详细拦截原因待补')}；control manifest SHA256={historical_upload_rejection.get('manifest_sha256', 'unknown')}；partial_side_effects={historical_upload_rejection.get('partial_side_effects', 'unknown')}。"},
                    {"kind": "text", "text": f"离线状态详情：{STAGE3_REPORT_LINK}；独立写作报告：{MANUSCRIPT_REPORT_LINK}"},
                ],
            })
        except (OSError, json.JSONDecodeError, TypeError, AttributeError):
            pass
    # 展示 k12 单点门控的当前状态。
    k12_gate = stage3_status.get("k12_gate", {}) if isinstance(stage3_status, dict) else {}
    if isinstance(k12_gate, dict) and k12_gate.get("status") in {"local_prepared_only", "remote_running", "terminal_accepted"}:
        upload_state = k12_gate.get("upload_rejected_external_review", {})
        params = k12_gate.get("parameters", {})
        eta = k12_gate.get("eta", {})
        launch = k12_gate.get("launch", {})
        running = k12_gate.get("status") == "remote_running"
        accepted = k12_gate.get("status") == "terminal_accepted"
        validator = k12_gate.get("validator", {})
        comparison = k12_gate.get("comparison", {})
        current_sections.insert(0, {
            "title": "已验收：L80 Krylov-12 单点" if accepted else ("运行中：L80 Krylov-12 单点" if running else "下一门控：L80 Krylov-12 单点"),
            "note": (
                "远端与本地 checksum、独立 validator 及 k8→k12 audit-only 比较均已通过。"
                if accepted else f"远端唯一 Julia 正在运行；PID={launch.get('julia_pid', 'unknown')}，计划 {launch.get('scheduled_check', '按 ETA')} 一次性检查。"
                if running else "本地包与验收链已准备；尚未上传或启动，目标仍未完成。"
            ),
            "blocks": [
                {"kind": "verdict", "status": "good" if accepted else "warn", "label": "release_v3 已验收 · k8→k12 稳定" if accepted else ("release_v3 远端运行中 · 尚未验收" if running else "release_v3 本地 ready · 远端未启动"), "why": (f"validator={validator.get('status', 'unknown')}；comparison gate={comparison.get('gate_status', 'unknown')}；仍限定为 audit_only。" if accepted else (f"current={launch.get('current_cell', 'unknown')}；stderr={launch.get('launcher_stderr_bytes', 'unknown')}/{launch.get('batch_stderr_bytes', 'unknown')} bytes；窗口={launch.get('expected_completion_window', 'unknown')}。" if running else f"上传状态={upload_state.get('status', 'unknown')}；no_remote_side_effects={k12_gate.get('no_remote_side_effects', 'unknown')}。"))},
                {"kind": "text", "text": f"单点 alpha={params.get('alpha')}、beta={params.get('beta')}、L={params.get('L')}、k={params.get('eigsolve_krylovdim')}；64 sweeps、maxdim=1200、双初态、单并发、无 retry/128。"},
                {"kind": "text", "text": f"本地 L10 smoke={k12_gate.get('local_smoke_pass', {}).get('status', 'unknown')}；42 文件发布合同，manifest SHA256={k12_gate.get('manifest_sha256', 'unknown')}；预计 {eta.get('expected_wall_minutes', 'unknown')} 分钟，硬超时 {eta.get('timeout_seconds', 'unknown')} 秒。"},
                {"kind": "text", "text": f"k8→k12 最大漂移：gap={comparison.get('max_abs_delta', {}).get('spin_gap', 'pending')}，dominant ratio={comparison.get('max_abs_delta', {}).get('dominant_ratio', 'pending')}，entropy={comparison.get('max_abs_delta', {}).get('entropy', 'pending')}；q_peak/pi={comparison.get('q_peak_over_pi', {}).get('k12', 'pending')}。"} if accepted else {"kind": "text", "text": "终态后才生成 validator 与 k8→k12 比较；运行中不提前解释。"},
                {"kind": "text", "text": f"run spec：{k12_gate.get('run_spec', 'unknown')}；独立准备报告：{K12_GATE_REPORT_LINK}；该计算只判断 k8→k12 稳定性，固定为 audit_only，不作新相或热力学标度结论。"},
            ],
        })
    # 仅在 status 明确登记且 summary 哈希匹配时展示本地 impact 审计。
    local_impact = stage3_status.get("local_impact_audit", {}) if isinstance(stage3_status, dict) else {}
    if isinstance(local_impact, dict) and local_impact.get("status") == "generated" and local_impact.get("goal_complete") is False and k12_gate.get("status") != "terminal_accepted":
        try:
            impact_summary_path = (ROOT / str(local_impact["summary"])).resolve()
            impact_report_path = (ROOT / str(local_impact["report_html"])).resolve()
            impact_summary_path.relative_to(ROOT.resolve())
            impact_report_path.relative_to(ROOT.resolve())
            if impact_summary_path.is_file() and impact_report_path.is_file() and sha256(impact_summary_path) == local_impact.get("summary_sha256"):
                impact_summary = json.loads(impact_summary_path.read_text(encoding="utf-8"))
                slope_rows = impact_summary.get("key_facts", {}).get("entropy_period10_window020", [])
                grouped = {}
                for row in slope_rows:
                    if int(row.get("period", -1)) == 10 and abs(float(row.get("window", -1.0)) - 0.20) <= 1e-12:
                        grouped.setdefault((float(row["alpha"]), str(row["start"])), {})[str(row["solver"])] = float(row["c_eff"])
                slope_text = "；".join(
                    f"alpha={alpha:g}/{start}: k3={pair['k3']:.10f}→k8={pair['k8']:.10f}"
                    for (alpha, start), pair in sorted(grouped.items())
                    if set(pair) == {"k3", "k8"}
                )
                href = os.path.relpath(impact_report_path, RUN.resolve()).replace(os.sep, "/")
                current_sections.insert(0, {
                    "title": "收尾审计：L80 Krylov impact",
                    "note": "由 project_closeout_status_20260919.json 的 local_impact_audit 状态字段驱动；目标仍未完成。",
                    "blocks": [
                        {"kind": "verdict", "status": "warn", "label": "impact audit 已生成 · audit_only / claim=none", "why": f"648 条 k=3→k=8 对照记录已核验；不把 solver-control audit 升格为物理稳定性结论。"},
                        {"kind": "text", "text": f"period=10、window=.20 的 c_eff 修正配对：{slope_text}。"},
                        {"kind": "text", "text": f"独立 impact 报告：{LOCAL_IMPACT_REPORT_LINK}；summary={impact_summary_path.relative_to(ROOT).as_posix()}。"},
                    ],
                })
        except (KeyError, OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    closeout_complete = isinstance(k12_gate, dict) and k12_gate.get("goal_complete") is True
    closeout_note = (
        "最后一项 L80 k8→k12 稳定性门已通过，计算、回传和独立验收已收尾；论文解释仍受 audit-only 与有限尺寸边界约束。"
        if closeout_complete else
        ("局部十二点尺寸数据已验收，待完成统一物理判读，研究尚未收尾。" if size_status.get("state") == "completed_validated" else "局部纠缠异常仍待尺寸核验，研究尚未收尾。")
    )
    return {
        "title": "1×5 Heisenberg Pentamer 研究进展",
        "eyebrow": current_eyebrow,
        "lede": "正区静态与代表性动力学已有结果；负区粗扫、边界精修和保存态计算已完成。目前没有确认第二个热力学相，也没有证明整个区域只有一个相。" + closeout_note,
        "sections": current_sections,
    }


def add_page_links(html: str, history: bool) -> str:
    target = "report.html" if history else "report_history.html"
    label = "返回当前主页" if history else "打开完整历史"
    css = """
    <style>
    .view-switch{position:fixed;right:22px;bottom:20px;z-index:50;background:#1a1a1a;color:#fff!important;padding:9px 13px;border-radius:4px;text-decoration:none!important;box-shadow:0 4px 16px #0002;font-size:13px}
    .view-switch:hover{background:#1f5cd6;border-bottom-color:transparent}
    @media(max-width:900px){.view-switch{right:12px;bottom:12px}.toc-bar{max-height:92px;overflow:auto}}
    </style>
    """
    link = f'<a class="view-switch" href="{target}">{label}</a>'
    return html.replace("</head>", css + "</head>").replace("</body>", link + "</body>")


def add_stage3_report_link(html: str) -> str:
    """把受控 marker 替换为同目录下的离线状态报告链接。"""
    target = "project_closeout_status_20260919_report/report.html"
    link = f'<a href="{target}">打开 Stage3 离线状态报告</a>'
    return html.replace(STAGE3_REPORT_LINK, link)


def add_manuscript_report_link(html: str) -> str:
    target = "../autoresearch_v5_20260919/manuscript_closeout_20260919_report/report.html"
    link = f'<a href="{target}">打开独立写作收尾报告</a>'
    return html.replace(MANUSCRIPT_REPORT_LINK, link)


def add_local_impact_report_link(html: str, target: str) -> str:
    """替换状态驱动的本地 impact 报告链接。"""
    link = f'<a href="{target}">打开 L80 Krylov impact audit 报告</a>'
    return html.replace(LOCAL_IMPACT_REPORT_LINK, link)


def add_k12_gate_report_link(html: str) -> str:
    target = "../autoresearch_v5_20260920/static_krylov_k12_gate_report_v3/report.html"
    link = f'<a href="{target}">打开 Krylov-12 门控终态报告</a>'
    return html.replace(K12_GATE_REPORT_LINK, link)


def deduplicate_identical_sections(doc: dict[str, object]) -> int:
    # 只合并完全相同的内容，不删除不同版本的历史。
    seen = set()
    retained = []
    for section in doc.get("sections", []):
        key = json.dumps(section, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            retained.append(section)
    removed = len(doc.get("sections", [])) - len(retained)
    doc["sections"] = retained
    return removed


def main() -> None:
    if not RENDERER.is_file():
        raise FileNotFoundError(RENDERER)
    ASSETS.mkdir(parents=True, exist_ok=True)
    renderer = load_renderer()
    doc = json.loads(SOURCE.read_text(encoding="utf-8"))
    static_manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records: dict[str, dict[str, object]] = {}
    staged_masters = {}
    for figure, item in static_manifest["figures"].items():
        staged_masters[figure] = stage(ROOT / item["outputs"]["png"]["path"], records)
    staged_masters["Fig. 8 bounded"] = stage(ROOT / "figures/paper_fig8_bounded_cv_tebd_20260805.png", records)
    update_canonical(doc, staged_masters)
    missing = stage_document_figures(doc, records)
    if missing:
        raise FileNotFoundError("未找到报告图件: " + ", ".join(missing))
    deduplicate_identical_sections(doc)
    SOURCE.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    history_html = add_page_links(renderer.render(doc, RUN), history=True)
    (RUN / "report_history.html").write_text(history_html, encoding="utf-8")
    current = build_current(doc, staged_masters, len(doc["sections"]))
    current_missing = stage_document_figures(current, records)
    if current_missing:
        raise FileNotFoundError("未找到当前主页图件: " + ", ".join(current_missing))
    local_impact_target = ""
    try:
        local_impact = json.loads(STAGE3_STATUS.read_text(encoding="utf-8")).get("local_impact_audit", {})
        if isinstance(local_impact, dict) and local_impact.get("report_html"):
            local_impact_target = os.path.relpath((ROOT / str(local_impact["report_html"])).resolve(), RUN.resolve()).replace(os.sep, "/")
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    current_html = add_k12_gate_report_link(add_local_impact_report_link(add_manuscript_report_link(add_stage3_report_link(add_page_links(renderer.render(current, RUN), history=False))), local_impact_target))
    (RUN / "report.html").write_text(current_html, encoding="utf-8")
    (RUN / "report_current.json").write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 根据当前状态生成交付门描述，避免沿用旧的启动前文案。
    stage3_status = json.loads(STAGE3_STATUS.read_text(encoding="utf-8")) if STAGE3_STATUS.is_file() else {}
    stage3_state = stage3_status.get("overall_status", "unknown")
    stage3_detail = stage3_status.get("stage3", {})
    terminal_state = stage3_detail.get("terminal_state", "unknown")
    candidate_validated = stage3_detail.get("candidate_validated") is True
    comparison_audit = stage3_detail.get("comparison_audit_current", {})
    terminal_success = any(token in str(terminal_state).lower() for token in ("success", "completed", "passed", "pass"))
    comparison_audit_ready = str(comparison_audit.get("status", "")).lower() == "audit_only"
    if candidate_validated and (stage3_state == "completed_validated_comparison_audit" or terminal_success or comparison_audit_ready):
        dynamic_gate_decision = (
            "Stage3 L80 two-point Practical V2 and independent validation passed; "
            "comparison is audit_only and physics stability is not claimed"
        )
    elif terminal_state == "terminal_success_pending_local_validation":
        dynamic_gate_decision = "Stage3 terminal success recorded; local validation pending"
    elif stage3_state in {"completed_pending_local_validation", "running_pending_validation"}:
        dynamic_gate_decision = "Stage3 candidate running or awaiting validation; no completion claim"
    else:
        dynamic_gate_decision = f"Stage3 status={stage3_state}; see current status JSON"
    forecast = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": {"alpha_beta": "[-1,1]x[0,1]", "negative_alpha_included": True, "fig9_excluded": True},
        "forecast": {
            "dynamic_gate_decision": dynamic_gate_decision,
            "figure_freeze": "pending localized finite-size evidence and claim audit",
            "complete_html_review_draft": "current report available; not a final research package",
            "final_research_package": None,
            "conditional_size_scan_hours_after_launch": None,
            "size_scan_status_source": "results/research_progress/project_closeout_status_20260919.json",
            "tex_manuscript": "requires explicit authorization to migrate reviewed HTML content into paper/",
        },
        "risk": "L80 observable convergence and the negative-region response range remain open; no ETA is verified.",
        "human_decisions": ["authorize any later migration into paper/"],
    }
    FORECAST.write_text(json.dumps(forecast, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    asset_manifest = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "asset_count": len(records),
        "missing": missing,
        "assets": records,
    }
    (RUN / "report_assets_manifest_20260804.json").write_text(json.dumps(asset_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    config = {
        "schema_version": 1,
        "canonical_source": "report.json",
        "current_view": "report.html",
        "history_view": "report_history.html",
        "current_sections": [section["title"] for section in current["sections"]],
        "history_sections": len(doc["sections"]),
        "render_command": ".venv\\Scripts\\python.exe scripts\\autoresearch_v5\\render_research_progress.py",
    }
    VIEW_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "current_sections": len(current["sections"]), "history_sections": len(doc["sections"]), "assets": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
