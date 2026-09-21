#!/usr/bin/env python3
"""汇总 R5 部分终态，不写 controller observations。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "nega-r5-a0250-b0500-L080": ("pass", (-0.25, 0.5, 80), 64, True),
    "nega-r5-a0100-b0500-L040": ("fail", (-0.1, 0.5, 40), 32, False),
}
AUDIT = "audit/remote_checksum_20260810_2048.txt"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def key(params: dict[str, Any]) -> tuple[float, float, int]:
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fetch_dir, run_spec_path = args.fetch_dir.resolve(), args.run_spec.resolve()
    audit_path = fetch_dir / AUDIT
    if not audit_path.is_file():
        raise FileNotFoundError(audit_path)
    spec = load(run_spec_path)
    cells = {cell["cell_id"]: cell for cell in spec.get("cells", [])}
    if len(cells) != 10 or not set(EXPECTED).issubset(cells):
        raise ValueError("R5 run spec 或物化 cell 集合不匹配")

    rows, records = [], []
    for cell_id, (expected_status, expected_key, expected_budget, calibration_only) in EXPECTED.items():
        cell = cells[cell_id]
        if key(cell["params"]) != expected_key or int(cell["budget"]) != expected_budget or bool(cell["calibration_only"]) is not calibration_only:
            raise ValueError(f"R5 cell spec 身份不匹配: {cell_id}")
        run_dir = fetch_dir / "cells" / cell_id
        validation_path = fetch_dir / "validation" / f"{cell_id}.json"
        receipt_path = fetch_dir / "receipts" / f"{cell_id}.json"
        manifest_path = run_dir / "manifest.json"
        for path in (validation_path, receipt_path, manifest_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        validation, receipt, manifest = load(validation_path), load(receipt_path), load(manifest_path)
        if (
            validation.get("cell_id") != cell_id or validation.get("status") != expected_status
            or Path(validation.get("run_dir", "")).resolve() != run_dir.resolve()
            or Path(validation.get("run_spec", "")).resolve() != run_spec_path
        ):
            raise ValueError(f"validator 身份或状态不匹配: {cell_id}")
        checks = validation.get("checks", {})
        if expected_status == "pass":
            if not checks or not all(value is True for value in checks.values()) or validation.get("failures"):
                raise ValueError(f"pass validator 含失败门: {cell_id}")
        elif (
            checks.get("terminal_acceptance") is not False
            or any(value is not True for name, value in checks.items() if name != "terminal_acceptance")
            or not validation.get("failures")
        ):
            raise ValueError(f"fail validator 含非声明异常: {cell_id}")
        if (
            receipt.get("status") != "pass" or receipt.get("cell_id") != cell_id
            or receipt.get("non_clobbering") is not True
            or Path(receipt.get("destination", "")).resolve() != run_dir.resolve()
            or receipt.get("manifest_sha256") != sha256(manifest_path)
        ):
            raise ValueError(f"回传 receipt 无效: {cell_id}")
        if manifest.get("cell_id") != cell_id or key(manifest["params"]) != expected_key:
            raise ValueError(f"manifest 身份不匹配: {cell_id}")

        rows.append({
            "cell_id": cell_id,
            "validator_status": expected_status,
            "exit_code": 0 if expected_status == "pass" else 1,
            "output": str(validation_path),
            "sha256": sha256(validation_path),
        })
        base = {
            "params": {"alpha": expected_key[0], "beta": expected_key[1], "L": expected_key[2]},
            "status": "success" if expected_status == "pass" else "failed",
            "budget": expected_budget,
            "artifact": relative(manifest_path if expected_status == "pass" else validation_path),
            "validation": {"status": expected_status, "artifact": relative(validation_path), "sha256": sha256(validation_path)},
            "checksum_receipt": {"artifact": relative(receipt_path), "sha256": sha256(receipt_path)},
            "calibration_only": calibration_only,
        }
        if expected_status == "pass":
            observable = manifest["observables"]["dominant_structure_factor_ratio"]
            record = base | {
                "value": observable["value"], "error": observable["error"],
                "accepted_only_candidate": True,
                "diagnostics": {"q_peak_over_pi": manifest["observables"]["structure_factor_peak_q_over_pi"]},
            }
        else:
            diagnostics = {}
            for mode in ("center", "ferro_j2"):
                child = load(run_dir / f"start_{mode}" / "manifest.json")
                diagnostics[mode] = {
                    "variance_per_site_sz0": child["diagnostics"]["variance_per_site_sz0"],
                    "variance_per_site_sz1": child["diagnostics"]["variance_per_site_sz1"],
                    "final_truncation_error_sz0": child["diagnostics"]["final_truncation_error_sz0"],
                    "final_truncation_error_sz1": child["diagnostics"]["final_truncation_error_sz1"],
                    "total_sz0": child["diagnostics"]["total_sz0"],
                    "total_sz1": child["diagnostics"]["total_sz1"],
                }
            record = base | {
                "failure_evidence": {
                    "checks": checks, "failures": validation["failures"],
                    "thresholds": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9, "sector_tolerance": 1e-8},
                    "diagnostics": diagnostics,
                },
                "accepted_only_candidate": False,
            }
            if "value" in record or "error" in record:
                raise ValueError("failed record 不得含 value/error")
        records.append(record)

    validation_summary = {
        "schema_version": 1, "status": "partial_fail", "cell_count": 2,
        "counts": {"pass": 1, "fail": 1}, "rows": sorted(rows, key=lambda item: item["cell_id"]),
    }
    summary_path = fetch_dir / "validation" / "summary.json"
    write_json(summary_path, validation_summary)
    handoff = {
        "schema_version": 1, "status": "partial_terminal",
        "run_spec": {"artifact": relative(run_spec_path), "sha256": sha256(run_spec_path)},
        "remote_checksum_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "validation_summary": {"artifact": relative(summary_path), "sha256": sha256(summary_path)},
        "counts": {"materialized": 2, "validator_pass": 1, "validator_fail": 1, "unmaterialized": 8},
        "records": sorted(records, key=lambda item: (item["params"]["alpha"], item["params"]["L"])),
        "controller_written": False,
        "retry_started": False,
        "interpretation": "仅 validator pass 点可作为 accepted-only candidate；失败点不含 value/error。",
    }
    output = fetch_dir / "partial_handoff_summary.json"
    write_json(output, handoff)
    print(json.dumps(handoff, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
