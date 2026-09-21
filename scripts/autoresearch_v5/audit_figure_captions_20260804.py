"""审计 Fig.1--8 图注是否与当前证据等级一致。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "results/research_progress/reference_aligned_figures_manifest_20260804.json"
REPORT = ROOT / "results/research_progress/report.json"
OUTPUT = ROOT / "results/research_progress/figure_caption_claim_audit_20260804.json"
FREEZE = ROOT / "results/research_progress/dynamic_gate_freeze_20260805.json"
TITLE = "2026-08-04 Fig.1--8 图注—主张—证据边界审计"


CAPTIONS = {
    "Fig. 1": {
        "claim": "1×5 单胞投影到有效 S=1/2 链。",
        "caption": "通过。示意 1×5 五聚体、胞内投影系数和正 J_eff 的有效链连接；不把单胞投影扩展为完整相图。",
        "boundary": "单胞与一阶有效理论。",
    },
    "Fig. 2": {
        "claim": "正 alpha 单胞能级与 q=pi 选择定则。",
        "caption": "通过。完整单胞 ED 标出总自旋、镜像宇称和可见谱权；最低双重态为 q=pi 暗通道，四重态占主要局域非弹性权重。",
        "boundary": "单胞直接跃迁，不等同于长链色散。",
    },
    "Fig. 3": {
        "claim": "正区有限尺寸结构趋势。",
        "caption": "有边界通过。展示正 alpha、beta 区域的有限尺寸诊断和代表点趋势；图中不命名未经多证据闭环确认的相界。",
        "boundary": "有限尺寸证据，非热力学极限相图。",
    },
    "Fig. 4": {
        "claim": "纠缠结构与 matched-size c≈1 标度证据。",
        "caption": "有边界通过。五类胞内切口与 matched-size Heisenberg oracle 的标度比较支持 c 接近 1；估计包含有限尺寸和拟合窗口边界。",
        "boundary": "校准后的有限链证据，不作无偏热力学外推。",
    },
    "Fig. 5": {
        "claim": "有效链传播、局域多重态和动量过滤。",
        "caption": "通过。示意有效 S=1/2 链低能传播、局域四重态分支和宇称过滤；暗通道标签服从 Fig.2 的单胞谱权。",
        "boundary": "机制示意，不创造未经验证的准粒子命名。",
    },
    "Fig. 6": {
        "claim": "alpha=1 跨正 beta 的动力学路径。",
        "caption": "探索性冻结。给出五个正 beta 的 raw TEBD 侦察热图，用于比较结构变化；不作为 CV/TEBD 交叉验收或生产谱。",
        "boundary": "exploratory_frozen；生产动态门为 8/9。",
    },
    "Fig. 7": {
        "claim": "beta=0.5 的三条正 alpha 动力学路径。",
        "caption": "试验性冻结。展示 alpha=0.14、0.23、0.33 的 raw TEBD pilot、q=pi 峰值、端点敏感性和积分窗权重；保留离散时间窗限制，不宣称生产交叉一致。",
        "boundary": "pilot_frozen；不再等待追加低频计算。",
    },
    "Fig. 8": {
        "claim": "七个 accepted CV 点与 TEBD 的受限交叉比较。",
        "caption": "有边界交付。七个 accepted q=pi CV 点与 TEBD 在共享频率上的最大相对差为 6.40%，共享窗积分差为 1.53%；omega=0.05 失败点以空心叉标记且不进入 accepted 曲线。低频主峰未被包围，总体保持 NotEvaluable。",
        "boundary": "bounded_seven_point_overlay；不是生产动态 Agreement。",
    },
}


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    frozen_status = {key.replace("Fig.", "Fig. "): value for key, value in freeze["figure_status"].items()}
    rows = []
    failures = []
    for figure, text in CAPTIONS.items():
        status = frozen_status.get(figure, manifest["figures"][figure]["status"])
        if figure in {"Fig. 6", "Fig. 7", "Fig. 8"} and status in {"ready", "production"}:
            failures.append(f"{figure}: dynamic status overpromoted")
        if figure == "Fig. 8" and ("NotEvaluable" not in text["caption"] or "空心叉" not in text["caption"]):
            failures.append("Fig. 8: 缺少失败点或 NotEvaluable 边界")
        rows.append({"figure": figure, "manifest_status": status, **text, "boundary_label_present": bool(text["boundary"])})
    result = {
        "schema_version": 1,
        "checked_at": "2026-08-05T22:55:00+08:00",
        "status": "pass" if not failures else "fail",
        "figures": rows,
        "failures": failures,
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "图注只进入 HTML 研究日志，不写入 paper/；检查图注结论不得超过当前数值证据。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good" if result["status"] == "pass" else "bad",
                "label": "8 张图的图注边界通过审计" if result["status"] == "pass" else "图注存在越界",
                "why": "Fig.1–5 保留静态/有限尺寸边界，Fig.6–8 明确 exploratory、pilot 或 bounded，并保留 NotEvaluable。",
            },
            {
                "kind": "table",
                "columns": ["图号", "当前状态", "可写主张", "证据边界"],
                "rows": [[item["figure"], item["manifest_status"], item["claim"], item["boundary"]] for item in rows],
                "widths": ["11%", "22%", "37%", "30%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["审计文件", "results/research_progress/figure_caption_claim_audit_20260804.json"],
                    ["范围", "0 <= alpha,beta <= 1；排除负 alpha 与 Fig.9"],
                    ["生产升级条件", "当前未满足；须重新设计低频求解并独立通过主峰、积分权重和覆盖门"],
                ],
            },
        ],
    }
    report["sections"] = [entry for entry in report["sections"] if entry.get("title") != TITLE]
    report["sections"].insert(2, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · CAPTION CLAIM AUDIT"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "figures": len(rows), "failures": len(failures)}, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
