"""核对热稳定性新证据并渲染当前工作稿。"""

import hashlib
import json
import re
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

import fitz
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "results/novelty_20261008"
PAPER = ROOT / "paper_prb/rank_candidate"
OUT = PAPER / "qa_four_cell_20261008"


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("four_cell", "general_spin", "weight_bound", "local_controls", "novelty_review", "window_retuning", "exact_local", "fulltext_review"), default="four_cell")
    stage = parser.parse_args().stage
    OUT = PAPER / f"qa_{stage}_20261008"
    OUT.mkdir(exist_ok=True)
    folders = ["thermal_compensation", "thermal_activation_audit_v2",
               "thermal_activation_exact", "thermal_operator_obstruction",
               "thermal_microscopic_two_cells", "momentum_acceptance_v2", "figures",
               "thermal_microscopic_four_cells", "four_cell_window_audit", "four_cell_solver_repeat"]
    if stage in ("general_spin", "weight_bound", "local_controls", "novelty_review", "window_retuning", "exact_local", "fulltext_review"):
        folders += ["general_spin_obstruction", "general_spin_moment", "general_spin_chain_check"]
    if stage in ("weight_bound", "local_controls", "novelty_review", "window_retuning", "exact_local", "fulltext_review"):
        folders += ["uniform_trace_weight_bound"]
    if stage in ("local_controls", "novelty_review", "window_retuning", "exact_local", "fulltext_review"):
        folders += ["local_control_obstruction"]
    if stage in ("window_retuning", "exact_local", "fulltext_review"):
        folders += ["momentum_window_retuning"]
    if stage in ("exact_local", "fulltext_review"):
        folders += ["exact_pentamer_coefficients_v3"]
    checked, failures = 0, []
    for folder in folders:
        manifest = DATA/folder/"sha256.json"
        for relative, expected in json.loads(manifest.read_text()).items():
            path = ROOT/relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                failures.append({"manifest": str(manifest.relative_to(ROOT)), "path": relative})
            checked += 1
    original = ROOT/"paper_prb/build/manuscript.pdf"
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    original_unchanged = original_hash == "e6d68fc15391e990d9b1d73289e5378f8224e312cfd4a50de1bb419fcf412766"
    previous_hashes = {Path(p).as_posix(): value for p, value in
                       json.loads((PAPER/"sha256.json").read_text()).items()}
    selected_figures = ["paper_prb/figures/fig6_fullq_positive.pdf", "paper_prb/figures/fig6_fullq_negative.pdf"]
    figures_unchanged = all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == previous_hashes[p]
                            for p in selected_figures)
    pdf_path = PAPER/"build/rank_manuscript.pdf"
    log = (PAPER/"build/rank_manuscript.log").read_text(errors="replace")
    warnings = re.findall(r"[^\n]*(?:Overfull|undefined|multiply defined)[^\n]*", log)
    pages, thumbs, overflow = [], [], []
    with fitz.open(pdf_path) as pdf:
        for i, page in enumerate(pdf):
            target = OUT/f"page_{i+1:02d}.png"
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(target)
            thumbnail = Image.open(target).convert("RGB")
            thumbnail.thumbnail((306, 396))
            thumbs.append(thumbnail)
            pages.append({"page": i+1, "text_chars": len(page.get_text()),
                          "has_thermal_figure_caption": "momentum-acceptance limitation" in page.get_text()})
            for word in page.get_text("words"):
                if not page.rect.contains(fitz.Rect(word[:4])):
                    overflow.append({"page": i+1, "word": word[4]})
        text = "\n".join(p.get_text() for p in pdf)
    sheet = Image.new("RGB", (4*326, ((len(thumbs)+3)//4)*430), "#dddddd")
    draw = ImageDraw.Draw(sheet)
    for i, thumb in enumerate(thumbs):
        x, y = (i % 4)*326, (i//4)*430
        draw.text((x+10, y+5), f"Page {i+1}", fill="black")
        sheet.paste(thumb, (x+10, y+25))
    sheet.save(OUT/"contact_sheet.png")
    vector = DATA/"figures/thermal_evidence"
    svg = ET.parse(vector.with_suffix(".svg"))
    svg_texts = len(svg.findall(".//{http://www.w3.org/2000/svg}text"))
    with fitz.open(vector.with_suffix(".pdf")) as figure:
        figure_text_chars = sum(len(p.get_text()) for p in figure)
    new_vector = DATA/"four_cell_window_audit/four_cell_activation"
    new_svg_texts = len(ET.parse(new_vector.with_suffix(".svg")).findall(".//{http://www.w3.org/2000/svg}text"))
    with fitz.open(new_vector.with_suffix(".pdf")) as figure:
        new_figure_text_chars = sum(len(p.get_text()) for p in figure)
    exact = json.loads((DATA/"thermal_activation_exact/summary.json").read_text())
    obstruction = json.loads((DATA/"thermal_operator_obstruction/summary.json").read_text())
    visual_path = OUT/"visual_review.json"
    visual = json.loads(visual_path.read_text()) if visual_path.exists() else None
    visual_matches = bool(visual and visual["pdf_sha256"] == hashlib.sha256(pdf_path.read_bytes()).hexdigest())
    report = {"hash_entries_checked": checked, "hash_failures": failures,
              "original_manuscript_unchanged": original_unchanged,
              "original_pdf_sha256": original_hash,
              "selected_original_figures_unchanged": figures_unchanged,
              "pages": pages, "text_outside_page": overflow,
              "layout_or_reference_warnings": warnings,
              "thermal_figure_svg_text_nodes": svg_texts,
              "thermal_figure_pdf_text_chars": figure_text_chars,
              "four_cell_figure_svg_text_nodes": new_svg_texts,
              "four_cell_figure_pdf_text_chars": new_figure_text_chars,
              "new_title_present": "Thermal stability of retuned interference zeros" in text,
              "exact_activation_prefactor": exact["total_prefactor_divided_by_b_squared"],
              "commutator_lower_bound": obstruction["all_even_N_ge4_lower_bound_over_b_squared"],
              "visual_review": visual["status"] if visual_matches else "pending; current PDF has no matching visual record",
              "visual_review_matches_pdf": visual_matches,
              "scientific_completion_claim": False}
    (OUT/"audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    files = [*PAPER.glob("*.tex"), *PAPER.glob("*.bib"), PAPER/"build.ps1", PAPER/"README.md", pdf_path,
             ROOT/"paper_prb/references.bib", DATA/"literature_discovery.json", Path(__file__),
             ROOT/"docs/topic_selection_20261008.md", ROOT/"docs/thermal_compensation_argument_20261008.md",
             ROOT/"paper_prb/figures/fig6_fullq_positive.pdf", ROOT/"paper_prb/figures/fig6_fullq_negative.pdf",
             *[DATA/f/"sha256.json" for f in folders], *([visual_path] if visual_matches else [])]
    if stage in ("general_spin", "weight_bound", "local_controls", "novelty_review", "window_retuning", "exact_local", "fulltext_review"):
        files += [DATA/"general_spin_literature_discovery.json", ROOT/"docs/publication_review_general_spin_20261008.md"]
    if stage in ("weight_bound", "local_controls", "novelty_review", "window_retuning", "exact_local", "fulltext_review"):
        files += [ROOT/"docs/uniform_trace_weight_bound_20261008.md"]
    if stage in ("local_controls", "novelty_review", "window_retuning", "exact_local", "fulltext_review"):
        files += [ROOT/"docs/local_control_obstruction_20261008.md"]
    if stage in ("novelty_review", "window_retuning", "exact_local", "fulltext_review"):
        files += [ROOT/"docs/novelty_boundary_review_20261008.md", DATA/"local_control_literature_discovery.json"]
        files += [DATA/"closest_fulltext_retrieval.json", DATA/"Haraldsen_PRL107_037205_2011_accepted.pdf",
                  DATA/"PRB103214422_openaire.json", DATA/"PRB103214422_depositonce_doi.json",
                  DATA/"PRB103214422_depositonce_author.json"]
    if stage in ("window_retuning", "exact_local", "fulltext_review"):
        files += [DATA/"momentum_window_retuning/audit.json", DATA/"momentum_window_retuning/audit_sha256.json",
                  ROOT/"scripts/submission_20261002/audit_window_retuning.py"]
    if stage in ("exact_local", "fulltext_review"):
        local = json.loads((DATA/"exact_pentamer_coefficients_v3/summary.json").read_text())
        assert local["passed"] and local["b_float"] > 0
        assert local["numeric_comparison_max_absolute_error"] < 1e-12
        files += [ROOT/"docs/exact_pentamer_coefficients_20261008.md",
                  ROOT/"docs/extinction_prior_art_review_20261008.md",
                  DATA/"extinction_fulltext_review.json", DATA/"Tabrizi_arxiv2608_13795v1.pdf",
                  DATA/"Tabrizi_arxiv2608_13795v1_supplement.pdf"]
    if stage == "fulltext_review":
        review_path = DATA/"prb103214422_fulltext_review/review.json"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        source = ROOT/review["source"]["project_copy"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == review["source"]["sha256"]
        with fitz.open(source) as source_pdf:
            assert len(source_pdf) == review["source"]["pages"] == 18
            assert review["source"]["doi"] in source_pdf[0].get_text()
        assert review["decision"]["previous_fulltext_blocker_resolved"]
        files += [review_path, source]
    (PAPER/f"sha256_{stage}_20261008.json").write_text(json.dumps({str(p.relative_to(ROOT)):
        hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    assert not failures and original_unchanged and figures_unchanged and not warnings and not overflow
    assert report["new_title_present"] and svg_texts > 15 and figure_text_chars > 100
    assert new_svg_texts > 15 and new_figure_text_chars > 100


if __name__ == "__main__":
    main()
