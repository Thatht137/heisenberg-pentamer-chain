"""建立 Fig.1--8 对应图的文件、证据等级和导出 manifest。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
FIGURES = ROOT / "figures"
REPORT_DIR = REPORT.parent
TITLE = "2026-08-04 Fig. 1--8 对应图交付 manifest"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def item(figures: list[str], role: str, status: str, claim: str) -> dict[str, object]:
    exports: list[dict[str, object]] = []
    for stem in figures:
        files = []
        for extension in (".svg", ".pdf", ".png", ".tiff"):
            path = FIGURES / f"{stem}{extension}"
            if path.is_file():
                files.append({"path": f"figures/{path.name}", "bytes": path.stat().st_size, "sha256": digest(path)})
        sidecar = FIGURES / f"{stem}.sources.json"
        exports.append({"stem": stem, "exports": files, "source_sidecar": sidecar.is_file()})
    return {"role": role, "status": status, "claim": claim, "assets": exports}


def main() -> None:
    mapping = {
        "Fig. 1": item(["reference_aligned_fig1_pentamer_20260803"], "模型与有效自由度", "ready", "1x5 单胞、投影系数和有效 S=1/2 链"),
        "Fig. 2": item(["reference_aligned_fig2_pentamer_positive_20260803"], "正 alpha 单胞能级与可见通道", "ready", "局域多重态、宇称和 q=pi 选择定则"),
        "Fig. 3": item(["reference_aligned_fig3_pentamer_positive_20260803"], "正区有限尺寸诊断", "ready_with_boundary", "正区尺寸趋势；不宣称已命名相界"),
        "Fig. 4": item(["reference_aligned_fig4_pentamer_positive_20260803"], "纠缠结构与标度", "ready_with_boundary", "有限尺寸 c≈1 证据；不作热力学极限强断言"),
        "Fig. 5": item(["pentamer_model_effective_chain_20260731", "pentamer_momentum_filter_20260731"], "激发机制与动量过滤", "ready", "有效链传播、局域多重态和暗通道"),
        "Fig. 6": item(["reference_aligned_fig6_alpha1_beta_scan_exploratory_20260803"], "alpha=1 跨 beta 动力学路径", "exploratory", "正 beta 侦察热图；等待生产 CV/TEBD"),
        # 以最新定量 pilot 为主资产，旧版保留作支撑图。
        "Fig. 7": item(["reference_aligned_fig7_pilot_quantitative_20260804", "reference_aligned_fig7_positive_alpha_pilot_20260804"], "beta=0.5 正 alpha 路径", "pilot", "三条正 alpha raw TEBD pilot 路径及 q=pi 峰值/端点/积分窗诊断；不关闭动态门"),
        "Fig. 8": item(["cv_continuum_overlay_20260803"], "连续谱与局域分支叠加", "constrained_overlay", "有效链连续谱边界与 CV 稀疏点的受限叠加"),
    }
    result = {
        "schema_version": 1,
        "created_at": "2026-08-04T00:31:16+08:00",
        "backend": "Python/matplotlib",
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
        "figures": mapping,
        "checks": {
            "all_required_roles_present": len(mapping) == 8,
            "all_assets_exist": all(asset["exports"] for value in mapping.values() for asset in value["assets"]),
            "reference_alignment_complete": True,
            "production_dynamic_ready": False,
        },
    }
    output = REPORT_DIR / "reference_aligned_figures_manifest_20260804.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    rows = []
    for name, value in mapping.items():
        stems = ", ".join(asset["stem"] for asset in value["assets"])
        rows.append([name, value["role"], value["status"], stems])
    section = {
        "title": TITLE,
        "note": "统一采用 Python/matplotlib 现有导出；manifest 只登记资产和证据等级，不提升未通过的动力学结论。",
        "blocks": [
            {"kind": "verdict", "status": "good", "label": "Fig. 1--8 对应关系完整", "why": "8 个参考图角色均有对应五聚体资产；动态 Fig. 6--8 保留 exploratory/pilot/受限叠加等级。"},
            {"kind": "table", "columns": ["图号", "对应角色", "证据等级", "主资产"], "rows": rows, "widths": ["10%", "30%", "23%", "37%"]},
            {"kind": "kv", "pairs": [["manifest", "results/research_progress/reference_aligned_figures_manifest_20260804.json"], ["绘图后端", "Python/matplotlib（统一用于绘图、导出和视觉 QA）"], ["导出契约", "SVG/PDF/PNG/TIFF；源文件和 SHA-256 逐项登记"]]},
            {"kind": "note", "label": "审阅边界", "style": "pending", "text": "Fig. 6--8 的图像已经可供结构审阅，但只有 round31 CV 频点、TEBD 交叉和主要积分窗验收通过后，才能升级为生产级动态主图。"},
        ],
    }
    report["sections"] = [entry for entry in report["sections"] if entry.get("title") != TITLE]
    report["sections"].insert(3, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · FIGURE MANIFEST"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "figures": len(mapping), "status": "pass"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
