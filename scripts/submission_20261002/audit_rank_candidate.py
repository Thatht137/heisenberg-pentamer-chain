"""核对新稿数据哈希并渲染逐页检查图。"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "results/novelty_20261004"
PAPER = ROOT / "paper_prb/rank_candidate"
OUT = PAPER / "qa"


def main():
    OUT.mkdir(exist_ok=True)
    paths = list(BASE.glob("*/sha256.json")) + list(BASE.glob("*/sha256.toml"))
    checked, failures = 0, []
    for manifest in paths:
        if manifest.suffix == ".json":
            items = json.loads(manifest.read_text())
        else:
            parsed = subprocess.run(["py", "-3.12", "-c",
                "import json,sys,tomllib; print(json.dumps(tomllib.loads(sys.stdin.read())))"],
                input=manifest.read_text(), text=True, capture_output=True, check=True)
            items = json.loads(parsed.stdout)
        for relative, expected in items.items():
            path = ROOT / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                failures.append({"manifest":str(manifest.relative_to(ROOT)),"source":relative})
            checked += 1
    old = ROOT / "paper_prb/build/manuscript.pdf"
    old_hash = hashlib.sha256(old.read_bytes()).hexdigest()
    old_unchanged = old_hash == "e6d68fc15391e990d9b1d73289e5378f8224e312cfd4a50de1bb419fcf412766"
    pdf = fitz.open(PAPER / "build/rank_manuscript.pdf")
    thumbs, pages = [], []
    for i, page in enumerate(pdf):
        target = OUT / f"page_{i+1:02d}.png"
        page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(target)
        thumb = Image.open(target).convert("RGB")
        thumb.thumbnail((306,396))
        thumbs.append(thumb)
        pages.append({"page":i+1,"text_chars":len(page.get_text()),
                      "width":page.rect.width,"height":page.rect.height})
    sheet = Image.new("RGB",(4*326,((len(thumbs)+3)//4)*430),"#dddddd")
    draw = ImageDraw.Draw(sheet)
    for i, thumb in enumerate(thumbs):
        x,y=(i%4)*326,(i//4)*430
        draw.text((x+10,y+5),f"Page {i+1}",fill="black")
        sheet.paste(thumb,(x+10,y+25))
    sheet.save(OUT / "contact_sheet.png")
    log=(PAPER / "build/rank_manuscript.log").read_text(errors="replace")
    bad=re.findall(r"[^\n]*(?:Overfull|undefined|multiply defined)[^\n]*",log)
    vector = BASE / "rank_figures/rank_compensation"
    svg = ET.parse(vector.with_suffix(".svg"))
    text_nodes = len(svg.findall(".//{http://www.w3.org/2000/svg}text"))
    with fitz.open(vector.with_suffix(".pdf")) as figure:
        figure_text_chars = sum(len(p.get_text()) for p in figure)
    controls = BASE / "rank_controls_figure/rank_controls"
    control_svg = ET.parse(controls.with_suffix(".svg"))
    control_nodes = len(control_svg.findall(".//{http://www.w3.org/2000/svg}text"))
    with fitz.open(controls.with_suffix(".pdf")) as figure:
        control_chars = sum(len(p.get_text()) for p in figure)
    report={"hash_entries_checked":checked,"hash_failures":failures,
            "original_manuscript_unchanged":old_unchanged,"original_pdf_sha256":old_hash,
            "pages":pages,"layout_or_reference_warnings":bad,
            "figure_svg_text_nodes":text_nodes,"figure_pdf_text_chars":figure_text_chars,
            "control_svg_text_nodes":control_nodes,"control_pdf_text_chars":control_chars,
            "visual_review":"pending; rendered pages require inspection"}
    (OUT / "audit.json").write_text(json.dumps(report,indent=2)+"\n")
    sources = [*PAPER.glob("*.tex"),*PAPER.glob("*.bib"),PAPER/"build.ps1",PAPER/"README.md",
        PAPER/"build/rank_manuscript.pdf",ROOT/"paper_prb/references.bib",
        ROOT/"paper_prb/figures/fig6_fullq_positive.pdf",ROOT/"paper_prb/figures/fig6_fullq_negative.pdf",
        ROOT/"docs/rank_mechanism_argument_20261004.md",ROOT/"docs/dark_probe_review_20261004.md",
        ROOT/"docs/bond_channel_interpretation_20261004.md",ROOT/"docs/publication_case_20261004.md",
        BASE/"rank_controls_figure/CAPTION.md",controls.with_suffix(".pdf"),
        BASE/"rank_figures/CAPTION.md",vector.with_suffix(".pdf"),Path(__file__),*paths]
    (PAPER/"sha256.json").write_text(json.dumps({str(p.relative_to(ROOT)):
        hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},indent=2)+"\n")
    print(json.dumps(report,indent=2))
    if failures or bad or not old_unchanged or text_nodes<10 or figure_text_chars<100 or control_nodes<10 or control_chars<100:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
