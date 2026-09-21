"""重算 TEBD 启动前哈希和配置门槛。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
READINESS = ROOT / "results/research_progress/tebd_readiness_audit_20260803.json"
OUT = ROOT / "results/research_progress/tebd_preflight_recheck_20260803.json"
FILES = {
    "manifest": ROOT / "Manifest.toml",
    "standard": ROOT / "docs/pentamer_reproduction_standard.md",
    "fourier_live": ROOT / "scripts/06_ft_tebd_pentamer_mapped_server.jl",
    "tebd_wrapper": ROOT / "scripts/autoresearch_v5/run_tebd_production.py",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    actual = {name: sha256(path) for name, path in FILES.items()}
    expected = readiness["hashes"]
    checks = {
        "readiness_status": readiness.get("status") == "READY_TO_START_AFTER_ANCHOR",
        "readiness_checks": all(bool(value) for value in readiness.get("checks", {}).values()),
        "manifest_hash": actual["manifest"] == expected["expected_manifest"],
        "standard_hash": actual["standard"] == expected["expected_standard"],
        "fourier_hash": actual["fourier_live"] == expected["fourier_live"],
        "wrapper_present": FILES["tebd_wrapper"].is_file(),
        "wrapper_scope_guard": "只允许 alpha,beta 位于 [0,1]" in FILES["tebd_wrapper"].read_text(encoding="utf-8"),
        "raw_display_separation": "raw_spectrum_csv" in FILES["tebd_wrapper"].read_text(encoding="utf-8"),
    }
    result = {
        "schema_version": 1,
        "status": "pass" if all(checks.values()) else "fail",
        "created_at": "2026-08-03",
        "checks": checks,
        "actual_sha256": actual,
        "expected_sha256": {
            "manifest": expected["expected_manifest"],
            "standard": expected["expected_standard"],
            "fourier_live": expected["fourier_live"],
        },
        "target": readiness["target"],
        "boundary": "L=80 anchor 终态前不启动 TEBD；不包含负 alpha 或 Fig. 9",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
