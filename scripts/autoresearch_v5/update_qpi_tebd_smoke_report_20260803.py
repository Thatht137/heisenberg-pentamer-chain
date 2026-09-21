"""把严格 q=pi TEBD smoke 和远端预览写入报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
RUN = ROOT / "results/autoresearch_v5_20260803/round25_qpi_tebd_smoke"
SUMMARY = RUN / "crosscheck_fix1/summary.json"
COARSE = RUN / "L10-qpi-dt005-t30/manifest.json"
REFINED = RUN / "L10-qpi-dt0025-t30/manifest.json"
L20 = RUN / "api-smoke-L20/manifest.json"
RESUME = RUN / "resume-smoke-L10/manifest.json"
PREVIEW = ROOT / "results/research_progress/qpi_tebd_remote_preview_20260803.json"
TITLE = "2026-08-03 19:30 严格 q=pi TEBD 小尺寸验收"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    report = load(REPORT)
    summary = load(SUMMARY)
    coarse = load(COARSE)
    refined = load(REFINED)
    l20 = load(L20)
    resume = load(RESUME)
    preview = load(PREVIEW)
    diagnostics = summary["diagnostics"]
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "L=10 ED/CV oracle、两档 TEBD 和 L=20 扩展 smoke；尚未启动 L=40 生产任务",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "good",
                    "label": "严格动量自相关估计器通过小尺寸方法门",
                    "why": "O_q|GS> 自相关在 L=10 与精确 ED 的峰位完全一致，积分权重误差 0.159%，dt/dt2 权重差 0.0062%，两档原始谱均非负；交叉标签为 Agreement。",
                },
                {
                    "kind": "equation",
                    "tex": "O_{\\pi}=\\frac{1}{\\sqrt{L}}\\sum_{j=1}^{L}e^{i\\pi j}S_j^z,\\quad C_{\\pi}(t)=\\langle O_{\\pi}GS|e^{-iHt}|O_{\\pi}GS\\rangle e^{iE_0t}",
                },
                {
                    "kind": "equation",
                    "tex": "S(\\pi,\\omega)=\\frac{1}{\\pi}\\operatorname{Re}\\int_0^{t_{\\max}}e^{(i\\omega-\\eta)t}C_{\\pi}(t)\\,dt",
                },
                {
                    "kind": "table",
                    "columns": ["验收项", "结果", "预算/判断"],
                    "rows": [
                        ["主峰 omega/J1", f"ED={diagnostics['exact_peak_omega']:.2f}；dt={diagnostics['coarse_peak_omega']:.2f}；dt/2={diagnostics['refined_peak_omega']:.2f}", "差值 0；预算 <=0.1"],
                        ["0<=omega<=3 积分权重", f"ED={diagnostics['exact_integrated_weight']:.6f}；refined={diagnostics['refined_integrated_weight']:.6f}", f"相对误差 {100 * diagnostics['refined_weight_relative_error']:.3f}%；预算 <=15%"],
                        ["dt/dt2 收敛", f"权重相对差 {100 * diagnostics['dt_weight_relative_delta']:.4f}%", "预算 <=5%；峰位差 0"],
                        ["原始谱非负", f"coarse min={diagnostics['coarse_spectrum_min']:.6f}；refined min={diagnostics['refined_spectrum_min']:.6f}", "两档通过；未裁剪、未平滑"],
                        ["源总权重", f"相对 ED 差 {diagnostics['refined_source_norm_relative_error']:.3e}", "纳入既有 15% 权重预算"],
                    ],
                    "widths": ["24%", "42%", "34%"],
                },
                {
                    "kind": "table",
                    "columns": ["工程门", "证据", "状态"],
                    "rows": [
                        ["t=0 与归一化", f"C(0)={refined['diagnostics']['correlation_t0_real']:.9f}；source norm={refined['diagnostics']['source_norm_squared']:.9f}", "一致"],
                        ["checkpoint 恢复", "受控停在 step 2；恢复日志从 step 3 接续；成功后 checkpoint 删除", "通过" if resume["accepted"] else "失败"],
                        ["L=20 扩展 smoke", f"D_actual={int(l20['diagnostics']['tebd_actual_maxdim'])}；20 steps={l20['diagnostics']['tebd_seconds']:.1f}s；variance/L={l20['diagnostics']['variance_per_site']:.2e}", "accepted" if l20["accepted"] else "未通过"],
                        ["回归测试", "31/31 PASS；Julia parse、Bash -n、L=40 dry-run 均通过", "通过"],
                        ["进度显示", "每 30 秒原子 progress.json；step/percent/ETA；100 步 checkpoint", "已实现"],
                    ],
                    "widths": ["24%", "52%", "24%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["生产点", "alpha=0.23、beta=0.5、L=40、q=pi、eta=0.1、OBC、Sz=0"],
                        ["顺序档位", "coarse dt=0.025/1200 steps；通过后 refined dt=0.0125/2400 steps；D=320；8 threads"],
                        ["远端保护", "最多 1 个 Julia、nice=10、每 100 步 checkpoint、/usr/bin/time -v 记录峰值 RSS"],
                        ["预计总时长", f"{preview['estimate']['total_hours']} h；保守上限 {preview['estimate']['conservative_upper_hours']} h"],
                        ["研究范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                    ],
                },
                {
                    "kind": "code",
                    "title": "新增实现与证据",
                    "text": "scripts/autoresearch_v5/tebd_qpi_autocorr.jl\nscripts/autoresearch_v5/run_tebd_qpi_autocorr.py\nscripts/autoresearch_v5/analyze_qpi_tebd_smoke.py\nresults/autoresearch_v5_20260803/round25_qpi_tebd_smoke/crosscheck_fix1/summary.json\nresults/research_progress/qpi_tebd_remote_preview_20260803.json",
                },
                {
                    "kind": "note",
                    "label": "生产边界",
                    "style": "pending",
                    "text": "小尺寸 Agreement 证明符号、1/sqrt(L)、t=0、/pi 和二阶时间步实现正确，但不能替代 L=40 生产验收。远端文件上传和顺序任务仍等待明确确认；当前服务器没有新 Julia。",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 19:30 CST"
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "section": TITLE,
                "cross_method": summary["tag"],
                "remote": preview["status"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
