#!/usr/bin/env python3
"""同步并审计 HTML 报告中的论文级图表资产。"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "results" / "research_progress"
REPORT = REPORT_DIR / "report.json"
OUTPUT = REPORT_DIR / "figure_provenance_audit_20260803.json"
FIGURE_DIR = ROOT / "figures"
TITLE = "图表 provenance 与导出审计（2026-08-03）"
SYNC_NAMES = (
    "positive_region_evidence_20260803.png",
    "cv_triplet_cost_quality_20260803.png",
    "positive_tebd_pilot_audit_20260803.png",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def resolve_path(raw: str) -> Path:
    normalized = raw.replace("\\", "/")
    path = Path(normalized)
    return path if path.is_absolute() else ROOT / path


def sync_current_previews() -> list[str]:
    synced: list[str] = []
    for name in SYNC_NAMES:
        source = FIGURE_DIR / name
        target = REPORT_DIR / name
        if not source.is_file():
            raise FileNotFoundError(source)
        if not target.is_file() or digest(source) != digest(target):
            shutil.copy2(source, target)
            synced.append(name)
    return synced


def report_figures() -> tuple[list[dict[str, object]], list[str], list[str]]:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    rows: list[dict[str, object]] = []
    missing: list[str] = []
    caption_missing: list[str] = []
    for section in report["sections"]:
        for block in section.get("blocks", []):
            if block.get("kind") != "figures":
                continue
            for item in block.get("items", []):
                source = str(item.get("src", ""))
                path = (REPORT_DIR / source).resolve()
                exists = path.is_file()
                if not exists:
                    missing.append(source)
                caption = str(item.get("caption", "")).strip()
                if not caption:
                    caption_missing.append(source)
                row: dict[str, object] = {
                    "section": section["title"],
                    "src": source,
                    "exists": exists,
                    "caption_present": bool(caption),
                }
                try:
                    from PIL import Image

                    with Image.open(path) as image:
                        row["pixels"] = [image.width, image.height]
                        row["mode"] = image.mode
                except Exception as error:
                    row["raster_error"] = str(error)
                rows.append(row)
    return rows, missing, caption_missing


def sidecar_audit() -> tuple[list[dict[str, object]], list[str], list[str], list[str]]:
    records: list[dict[str, object]] = []
    missing: list[str] = []
    mismatches: list[str] = []
    warnings: list[str] = []
    for sidecar in sorted(FIGURE_DIR.glob("*.sources.json")):
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        entries = payload.get("source_files", payload.get("sources", []))
        checked_sources = 0
        for entry in entries:
            raw = str(entry.get("path", ""))
            path = resolve_path(raw)
            checked_sources += 1
            if not path.is_file():
                missing.append(f"{sidecar.name}:{raw}")
            elif str(entry.get("sha256", "")).lower() != digest(path):
                mismatches.append(f"{sidecar.name}:{raw}")
        # 兼容 source_sha256 和绘图脚本生成的 inputs 字典。
        source_maps = []
        if isinstance(payload.get("source_sha256"), dict):
            source_maps.append(payload["source_sha256"])
        if isinstance(payload.get("inputs"), dict):
            source_maps.append(payload["inputs"])
        for source_map in source_maps:
            for raw, expected in source_map.items():
                path = resolve_path(str(raw))
                checked_sources += 1
                if not path.is_file():
                    missing.append(f"{sidecar.name}:{raw}")
                elif str(expected).lower() != digest(path):
                    mismatches.append(f"{sidecar.name}:{raw}")
        checked_exports = 0
        for raw in payload.get("exports", []):
            path = resolve_path(str(raw))
            checked_exports += 1
            if not path.is_file():
                missing.append(f"{sidecar.name}:{raw}")
        outputs = payload.get("outputs")
        if isinstance(outputs, dict):
            stem = sidecar.name.removesuffix(".sources.json")
            for extension, expected in outputs.items():
                path = FIGURE_DIR / f"{stem}.{extension.lstrip('.') }"
                checked_exports += 1
                if not path.is_file():
                    missing.append(f"{sidecar.name}:{path.name}")
                elif str(expected).lower() != digest(path):
                    mismatches.append(f"{sidecar.name}:{path.name}")
        figure_contract = payload.get("figure_contract", {})
        backend = payload.get("backend")
        if not backend and isinstance(figure_contract, dict):
            backend = figure_contract.get("backend")
        if not backend:
            warnings.append(f"{sidecar.name}:诊断图 sidecar 未声明绘图后端")
        records.append(
            {
                "sidecar": sidecar.name,
                "figure": payload.get("figure", sidecar.stem.replace(".sources", "")),
                "backend": backend or "diagnostic/unspecified",
                "sources_checked": checked_sources,
                "exports_checked": checked_exports,
            }
        )
    return records, missing, mismatches, warnings


def vector_audit() -> dict[str, object]:
    svg = sorted(FIGURE_DIR.glob("*.svg"))
    pdf = sorted(FIGURE_DIR.glob("*.pdf"))
    svg_text = {path.name: len(re.findall(r"<text(?:\s|>)", path.read_text(encoding="utf-8", errors="ignore"))) for path in svg}
    pdf_fonts = {path.name: bool(re.search(rb"/Font", path.read_bytes())) for path in pdf}
    return {
        "svg_files": len(svg),
        "svg_with_editable_text": sum(value > 0 for value in svg_text.values()),
        "svg_text_nodes": svg_text,
        "pdf_files": len(pdf),
        "pdf_with_font_resources": sum(pdf_fonts.values()),
        "pdf_font_resources": pdf_fonts,
    }


def build_section(audit: dict[str, object]) -> dict[str, object]:
    report_rows = audit["report_figures"]
    sidecars = audit["sidecars"]
    return {
        "title": TITLE,
        "note": "只审计图表资产和来源；不增加服务器计算，不修改 paper/",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good" if audit["status"] == "pass" else "warn",
                "label": "HTML 图表资产可追溯且已同步" if audit["status"] == "pass" else "图表审计存在待处理项",
                "why": f"报告包含 {len(report_rows)} 个图块，缺失 {len(audit['report_missing'])} 个；{len(sidecars)} 个 source sidecar 的 {audit['source_entries']} 条来源和 {audit['export_entries']} 个导出均已检查。",
            },
            {
                "kind": "table",
                "columns": ["审计层", "结果", "解释"],
                "rows": [
                    ["HTML 图块", f"{len(report_rows)}/ {len(report_rows)} 存在" if not audit["report_missing"] else f"缺失 {len(audit['report_missing'])}", "渲染目录中的 PNG 预览可读取"],
                    ["图注", f"{len(report_rows) - len(audit['caption_missing'])}/{len(report_rows)} 有图注", "图注是结果解释和证据边界，不是文件名"],
                    ["来源 SHA-256", f"{audit['source_entries']} 条，{len(audit['source_mismatches'])} 不匹配", "sidecar 中的源数据逐条核验"],
                    ["导出文件", f"{audit['export_entries']} 个，{len(audit['source_missing'])} 缺失", "SVG/PDF/TIFF/PNG 路径逐条核验"],
                    ["矢量文字", f"SVG {audit['vector']['svg_with_editable_text']}/{audit['vector']['svg_files']}；PDF 字体 {audit['vector']['pdf_with_font_resources']}/{audit['vector']['pdf_files']}", "检查可编辑文字和字体资源"],
                ],
                "widths": ["23%", "28%", "49%"],
            },
            {
                "kind": "list",
                "title": "本轮修复",
                "items": [
                    f"同步 {', '.join(audit['synced_previews']) if audit['synced_previews'] else '0 张'} 报告预览，使其与 figures/ 当前导出一致。",
                    "当前三张主审计图使用 Python/matplotlib；其源数据、manifest 和导出路径均保留。",
                    "旧版图仍通过结果目录和运行清单追溯，不把缺少 sidecar 当成新的物理证据。",
                ],
            },
            {
                "kind": "code",
                "title": "审计入口",
                "text": "scripts/autoresearch_v5/audit_figure_provenance_20260803.py\nresults/research_progress/figure_provenance_audit_20260803.json\nfigures/*.sources.json",
            },
            {
                "kind": "note",
                "label": "边界",
                "style": "pending",
                "text": "图表资产审计只证明文件、来源和导出可追溯，不提升 L=80 CV、TEBD 或最终动态结论的准入等级；负 alpha 和 Fig. 9 仍排除。",
            },
        ],
    }


def update_report(audit: dict[str, object]) -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [section for section in report["sections"] if section["title"] != TITLE]
    report["sections"].insert(1, build_section(audit))
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    synced = sync_current_previews()
    rows, report_missing, caption_missing = report_figures()
    sidecars, source_missing, source_mismatches, warnings = sidecar_audit()
    vector = vector_audit()
    source_entries = sum(int(item["sources_checked"]) for item in sidecars)
    export_entries = sum(int(item["exports_checked"]) for item in sidecars)
    audit: dict[str, object] = {
        "schema_version": 1,
        "created_at": "2026-08-03",
        "status": "pass" if not report_missing and not caption_missing and not source_missing and not source_mismatches else "warn",
        "synced_previews": synced,
        "report_figures": rows,
        "report_missing": report_missing,
        "caption_missing": caption_missing,
        "sidecars": sidecars,
        "source_entries": source_entries,
        "export_entries": export_entries,
        "source_missing": source_missing,
        "source_mismatches": source_mismatches,
        "warnings": warnings,
        "vector": vector,
        "scope": {"negative_alpha_included": False, "fig9_included": False, "server_polled": False},
    }
    OUTPUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_report(audit)
    print(json.dumps({"status": audit["status"], "synced": synced, "report_figures": len(rows), "source_entries": source_entries, "export_entries": export_entries}, ensure_ascii=False))


if __name__ == "__main__":
    main()
