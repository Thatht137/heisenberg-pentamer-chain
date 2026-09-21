#!/usr/bin/env python3
"""验收论文静态图与双视图 HTML。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "research_progress"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads((RUN / "paper_static_figures_manifest_20260804.json").read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}
    figures = {}
    for figure, item in manifest["figures"].items():
        figure_checks = {}
        for suffix, record in item["outputs"].items():
            path = ROOT / record["path"]
            figure_checks[f"{suffix}_exists"] = path.is_file() and path.stat().st_size > 0
            figure_checks[f"{suffix}_hash"] = path.is_file() and sha256(path) == record["sha256"]
            if suffix in {"png", "tiff"} and path.is_file():
                with Image.open(path) as image:
                    figure_checks[f"{suffix}_resolution"] = image.width >= 2000 and image.height >= 900
            if suffix == "svg" and path.is_file():
                text = path.read_text(encoding="utf-8")
                figure_checks["svg_editable_text"] = "<text" in text and "Reference-aligned" not in text
        sidecar = ROOT / item["sidecar"]
        figure_checks["sidecar"] = sidecar.is_file() and bool(json.loads(sidecar.read_text(encoding="utf-8")).get("source_sha256"))
        figures[figure] = figure_checks
        checks[f"{figure}_bundle"] = all(figure_checks.values())

    current = (RUN / "report.html").read_text(encoding="utf-8")
    history = (RUN / "report_history.html").read_text(encoding="utf-8")
    current_sections = len(re.findall(r"<section\b", current))
    history_sections = len(re.findall(r"<section\b", history))
    checks.update({
        "current_sections_minimum": current_sections >= 10,
        "current_draft_section": "2026-08-11 论文完整草稿 · evidence-locked" in current,
        "current_nine_images": current.count("data:image/") == 9,
        "current_no_missing_images": "Image not embedded" not in current,
        "current_navigation_compact": current.count('<nav class="toc">') == 1 and current.count('<nav class="toc-bar">') == 1 and current.count('<a href="#') == current_sections * 2,
        "current_history_link": 'href="report_history.html"' in current,
        "history_complete": history_sections >= 149,
        "history_no_missing_images": "Image not embedded" not in history,
        "history_current_link": 'href="report.html"' in history,
        "asset_manifest_clean": not json.loads((RUN / "report_assets_manifest_20260804.json").read_text(encoding="utf-8"))["missing"],
    })
    result = {
        "schema_version": 1,
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "figures": figures,
        "metrics": {
            "current_sections": current_sections,
            "history_sections": history_sections,
            "current_bytes": (RUN / "report.html").stat().st_size,
            "history_bytes": (RUN / "report_history.html").stat().st_size,
            "current_embedded_images": current.count("data:image/"),
            "history_embedded_images": history.count("data:image/"),
        },
    }
    out = RUN / "paper_static_and_report_qa_20260804.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
