"""核对参考图导出资产、哈希和位图分辨率。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "results/research_progress/reference_aligned_figures_manifest_20260804.json"
REPORT = ROOT / "results/research_progress/report.json"
OUTPUT = ROOT / "results/research_progress/figure_asset_pixel_qa_20260804.json"
TITLE = "2026-08-04 Fig.1--8 导出资产与位图分辨率 QA"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_asset(relative: str, expected_hash: str, expected_bytes: int) -> dict:
    path = ROOT / relative
    item = {
        "path": relative,
        "exists": path.is_file(),
        "nonempty": path.is_file() and path.stat().st_size > 0,
        "bytes_manifest": expected_bytes,
        "bytes_actual": path.stat().st_size if path.is_file() else 0,
        "sha256_match": False,
    }
    if path.is_file():
        item["sha256_match"] = sha256(path) == expected_hash
    if path.suffix.lower() in {".png", ".tiff", ".tif"} and path.is_file():
        with Image.open(path) as image:
            item["width"] = image.width
            item["height"] = image.height
            item["mode"] = image.mode
            item["resolution_ok"] = image.width >= 1200 and image.height >= 800
    else:
        item["resolution_ok"] = True
    item["ok"] = all(
        [item["exists"], item["nonempty"], item["sha256_match"], item["resolution_ok"]]
    )
    return item


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assets = []
    for figure, payload in manifest["figures"].items():
        for asset in payload["assets"]:
            for export in asset["exports"]:
                result = inspect_asset(
                    export["path"], export["sha256"], export["bytes"]
                )
                result.update({"figure": figure, "stem": asset["stem"]})
                assets.append(result)
    failures = [item for item in assets if not item["ok"]]
    result = {
        "schema_version": 1,
        "checked_at": "2026-08-04T08:30:00+08:00",
        "status": "pass" if not failures else "fail",
        "asset_count": len(assets),
        "assets": assets,
        "failures": failures,
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    by_figure = {}
    for item in assets:
        by_figure.setdefault(item["figure"], []).append(item)
    rows = []
    for figure, items in by_figure.items():
        pngs = [item for item in items if item["path"].lower().endswith(".png")]
        dimensions = "; ".join(
            f"{item.get('width', '?')}×{item.get('height', '?')}" for item in pngs
        )
        rows.append([figure, str(len(items)), dimensions or "矢量资产", "通过" if all(item["ok"] for item in items) else "失败"])
    section = {
        "title": TITLE,
        "note": "本地独立核对 Fig.1--8 的导出文件；不连接服务器，不修改 paper/。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good" if result["status"] == "pass" else "bad",
                "label": "全部图表资产通过本地 QA" if result["status"] == "pass" else "存在图表资产问题",
                "why": f"检查 {len(assets)} 个 SVG/PDF/PNG/TIFF 导出；哈希、非空和 PNG/TIFF 分辨率均符合门槛。",
            },
            {
                "kind": "table",
                "columns": ["图号", "导出数", "PNG 分辨率", "结果"],
                "rows": rows,
                "widths": ["15%", "15%", "45%", "25%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["QA 文件", "results/research_progress/figure_asset_pixel_qa_20260804.json"],
                    ["生产状态", "Fig.1--5 可用于静态结论；Fig.6--8 仍受 CV/TEBD 动力学门约束"],
                    ["范围", "0 <= alpha,beta <= 1；排除负 alpha 和 Fig.9"],
                ],
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(3, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · LOCAL FIGURE ASSET QA"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "asset_count": len(assets), "failures": len(failures)}, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
