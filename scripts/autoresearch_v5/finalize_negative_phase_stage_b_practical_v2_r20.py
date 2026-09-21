#!/usr/bin/env python3
"""验收 R20，并形成 Practical V2 的 Stage B 终态索引。"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha"
STAGE = RUN / "stage-b-negative-coarse-r20-remaining4"
PHASE = RUN / "phase-diagram-v2"
PROGRESS = ROOT / "results/research_progress"
DATE = "20260908"
VARIANCE_MAX = 5e-8
ALPHAS = (-1.0, -0.75, -0.5, -0.35, -0.25, -0.1, -0.05, -0.025)
BETAS = (0.05, 0.1, 0.25, 0.75, 0.9, 1.0)
LENGTHS = (40, 60)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def key(params: dict[str, Any]) -> tuple[float, float, int]:
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"拒绝覆盖: {path}")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent,
                                     prefix=f".{path.name}.", delete=False) as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        name = Path(stream.name)
    name.replace(path)


def main() -> int:
    index_path = STAGE / "accepted-practical-v2-index.json"
    bounded_path = STAGE / "bounded-practical-v2-records.json"
    spec_path = STAGE / "parameter-scan.run_spec.json"
    for path in (index_path, bounded_path, spec_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    index, bounded, spec = load(index_path), load(bounded_path), load(spec_path)
    if index.get("count") != 85 or bounded.get("count") != 7 or len(spec.get("cells", [])) != 4:
        raise ValueError("R20 基线计数不匹配")

    validations = sorted(PROGRESS.glob(f"stage_b_r20_*_validation_practical_v2_{DATE}.json"))
    receipts = sorted(PROGRESS.glob(f"stage_b_r20_*_fetch_receipt_{DATE}.json"))
    if len(validations) != 4 or len(receipts) != 4:
        raise ValueError("R20 必须提供4组 validator 与回传证据")
    receipt_map = {load(path)["cell_id"]: (path, load(path)) for path in receipts}
    spec_ids = {cell["cell_id"] for cell in spec["cells"]}
    evidence: list[dict[str, Any]] = []
    new_records: list[dict[str, Any]] = []
    for validation_path in validations:
        validation = load(validation_path)
        cell_id = validation.get("cell_id")
        receipt_path, receipt = receipt_map.get(cell_id, (None, None))
        if (
            cell_id not in spec_ids
            or validation.get("status") != "pass"
            or validation.get("failures") != []
            or validation.get("thresholds", {}).get("variance_per_site_max") != VARIANCE_MAX
            or receipt is None
            or receipt.get("status") != "pass"
            or receipt.get("non_clobbering") is not True
        ):
            raise ValueError(f"R20 证据未通过: {cell_id}")
        run_dir = Path(validation["run_dir"])
        manifest = run_dir / "manifest.json"
        if (
            not manifest.is_file()
            or validation.get("provenance", {}).get("original_manifest_sha256") != sha256(manifest)
        ):
            raise ValueError(f"R20 manifest provenance 不匹配: {cell_id}")
        new_records.append(
            {
                "params": {name: validation["params"][name] for name in ("alpha", "beta", "L")},
                "cell_id": cell_id,
                "sweeps": int(validation["settings"]["nsweeps"]),
                "artifact": relative(manifest),
                "validation_basis": relative(validation_path),
                "validation_sha256": sha256(validation_path),
                "legacy_accepted": bool(validation.get("legacy_parent_accepted")),
            }
        )
        evidence.append(
            {
                "cell_id": cell_id,
                "status": "pass",
                "validation": relative(validation_path),
                "validation_sha256": sha256(validation_path),
                "receipt": relative(receipt_path),
                "receipt_sha256": sha256(receipt_path),
                "manifest": relative(manifest),
                "manifest_sha256": sha256(manifest),
            }
        )

    accepted_records = index["records"] + new_records
    accepted_keys = {key(row["params"]) for row in accepted_records}
    bounded_keys = {key(row["params"]) for row in bounded["records"]}
    expected = {(alpha, beta, length) for alpha in ALPHAS for beta in BETAS for length in LENGTHS}
    if len(accepted_keys) != 89 or len(bounded_keys) != 7 or accepted_keys & bounded_keys:
        raise ValueError("accepted/bounded 终态索引重复或计数错误")
    if accepted_keys | bounded_keys != expected:
        raise ValueError("Stage B 网格尚未全部解析")

    accepted_doc = {
        "schema_version": 1,
        "policy": "Practical V2",
        "variance_per_site_max": VARIANCE_MAX,
        "records": sorted(accepted_records, key=lambda row: key(row["params"])),
        "count": 89,
        "boundary_eligible_count": 89,
        "old_manifests_unchanged": True,
    }
    bounded_doc = dict(bounded)
    bounded_doc["all_records_boundary_eligible"] = False
    bounded_doc["old_manifests_unchanged"] = True
    accepted_out = PHASE / "stage_b_practical_v2_accepted_index_final.json"
    bounded_out = PHASE / "stage_b_practical_v2_bounded_records_final.json"
    evidence_out = PHASE / "stage_b_practical_v2_r20_terminal_evidence.json"
    write_json(accepted_out, accepted_doc)
    write_json(bounded_out, bounded_doc)
    write_json(evidence_out, {"schema_version": 1, "summary": "4 pass/0 fail", "records": evidence})
    summary = {
        "schema_version": 1,
        "status": "accepted_stage_b_complete_with_bounded",
        "policy": "Practical V2",
        "counts": {"grid": 96, "accepted": 89, "bounded": 7, "pending": 0},
        "grid_fully_resolved": True,
        "boundary_eligible": 89,
        "bounded_excluded_from_boundary": 7,
        "stage_c_analysis_ready": True,
        "thresholds_relaxed_during_terminal_ingest": False,
        "max_new_sweeps": 64,
        "inputs": {
            "accepted_index": {"artifact": relative(accepted_out), "sha256": sha256(accepted_out)},
            "bounded_records": {"artifact": relative(bounded_out), "sha256": sha256(bounded_out)},
            "r20_evidence": {"artifact": relative(evidence_out), "sha256": sha256(evidence_out)},
        },
    }
    summary_out = PHASE / "stage_b_practical_v2_completion_summary.json"
    write_json(summary_out, summary)
    print(json.dumps({"status": summary["status"], **summary["counts"],
                      "summary": relative(summary_out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
