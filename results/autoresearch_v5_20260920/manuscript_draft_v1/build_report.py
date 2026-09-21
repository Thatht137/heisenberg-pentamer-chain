from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


RUN_DIR = Path(__file__).resolve().parent
SOURCE = RUN_DIR / "manuscript.md"
OUTPUT = RUN_DIR / "report.json"


def flush_text(buffer: list[str], blocks: list[dict]) -> None:
    if buffer:
        blocks.append({"kind": "text", "text": " ".join(x.strip() for x in buffer)})
        buffer.clear()


def flush_list(buffer: list[str], blocks: list[dict]) -> None:
    if buffer:
        blocks.append({"kind": "list", "items": buffer.copy()})
        buffer.clear()


def parse_markdown(text: str) -> tuple[str, list[dict]]:
    lines = text.splitlines()
    title = lines[0].removeprefix("# ").strip()
    sections: list[dict] = []
    current = {"title": "Manuscript", "blocks": []}
    sections.append(current)
    text_buffer: list[str] = []
    list_buffer: list[str] = []
    equation_buffer: list[str] = []
    in_equation = False

    for raw in lines[1:]:
        line = raw.rstrip()
        if line == "$$":
            flush_text(text_buffer, current["blocks"])
            flush_list(list_buffer, current["blocks"])
            if in_equation:
                current["blocks"].append(
                    {"kind": "equation", "tex": "\n".join(equation_buffer)}
                )
                equation_buffer.clear()
            in_equation = not in_equation
            continue
        if in_equation:
            equation_buffer.append(line)
            continue

        if line.startswith("## "):
            flush_text(text_buffer, current["blocks"])
            flush_list(list_buffer, current["blocks"])
            current = {"title": line[3:].strip(), "blocks": []}
            sections.append(current)
            continue
        if line.startswith("### "):
            flush_text(text_buffer, current["blocks"])
            flush_list(list_buffer, current["blocks"])
            current["blocks"].append(
                {"kind": "heading", "text": line[4:].strip(), "level": 3}
            )
            continue

        image_match = re.fullmatch(r"!\[(.+)]\((.+)\)", line)
        if image_match:
            flush_text(text_buffer, current["blocks"])
            flush_list(list_buffer, current["blocks"])
            current["blocks"].append(
                {
                    "kind": "figures",
                    "items": [
                        {"src": image_match.group(2), "caption": image_match.group(1)}
                    ],
                }
            )
            continue

        item_match = re.match(r"^(?:[-*]|\d+\.)\s+(.+)$", line)
        if item_match:
            flush_text(text_buffer, current["blocks"])
            list_buffer.append(item_match.group(1))
            continue

        if not line.strip():
            flush_text(text_buffer, current["blocks"])
            flush_list(list_buffer, current["blocks"])
            continue

        flush_list(list_buffer, current["blocks"])
        text_buffer.append(line)

    flush_text(text_buffer, current["blocks"])
    flush_list(list_buffer, current["blocks"])
    return title, sections


def main() -> None:
    source_text = SOURCE.read_text(encoding="utf-8")
    # 适配离线 MathML 子集。
    source_text = source_text.replace(r"\rm ", "").replace(r"\ll", "≪")
    source_text = re.sub(r"(?<!\*)\*(?!\*)", "", source_text)
    title, sections = parse_markdown(source_text)
    sections[0]["blocks"].insert(
        0,
        {
            "kind": "verdict",
            "status": "good",
            "label": "MANUSCRIPT DRAFT · CALCULATION PACKAGE CLOSED",
            "why": "正文已纳入 k=8→12 终态验收；负 alpha 只主张有限尺寸动量重构。",
        },
    )
    report = {
        "schema_version": 1,
        "title": title,
        "eyebrow": "RESEARCH ARTICLE · AUTHOR REVIEW DRAFT",
        "url": "",
        "lede": (
            "完整英文论文草稿，整合局域多重态、有效链、静态/动态 MPS、"
            "负 alpha 动量重构与终态 Krylov 稳定性证据。"
        ),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "scope": "alpha in [-1,1], beta in [0,1]",
            "claim_boundary": "finite-size momentum reconstruction; no new phase label",
            "paper_directory_modified": False,
        },
        "sections": sections,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
