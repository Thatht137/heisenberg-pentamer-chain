"""审计 TEBD 交叉检查的启动配置，不执行 TEBD。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts/autoresearch_v5/wait_then_run_tebd_remote.sh"
FOURIER = ROOT / "scripts/06_ft_tebd_pentamer_mapped_server.jl"
MANIFEST = ROOT / "Manifest.toml"
STANDARD = ROOT / "docs/pentamer_reproduction_standard.md"
OUT = ROOT / "results/research_progress/tebd_readiness_audit_20260803.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def capture(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1) if match else None


def main() -> None:
    wrapper = WRAPPER.read_text(encoding="utf-8")
    fourier = FOURIER.read_text(encoding="utf-8")
    expected_manifest = capture(wrapper, r"--expected-manifest-sha256\s+([0-9a-f]+)")
    expected_standard = capture(wrapper, r"--standard-sha256\s+([0-9a-f]+)")
    actual_manifest = sha256(MANIFEST)
    actual_standard = sha256(STANDARD)
    checks = {
        "manifest_hash_matches_wrapper": actual_manifest == expected_manifest,
        "standard_hash_matches_wrapper": actual_standard == expected_standard,
        "positive_alpha_beta": "--alpha 0.23" in wrapper and "--beta 0.5" in wrapper,
        "target_L40": "--n-units 8" in wrapper,
        "dt_0.025_tmax_15": "--tstep 0.025" in wrapper and "--n-steps 600" in wrapper,
        "dt_half_ready": "raw_spectrum = copy(spectrum)" in fourier and "writedlm(raw_csv_file, raw_spectrum" in fourier,
        "raw_display_separation": "spectrum .= max.(raw_spectrum, 0.0)" in fourier,
        "negative_alpha_excluded": "--alpha -" not in wrapper,
    }
    result = {
        "schema_version": 1,
        "status": "READY_TO_START_AFTER_ANCHOR" if all(checks.values()) else "CONFIG_REVIEW_REQUIRED",
        "execution": "remote-only; no local TEBD was started",
        "target": {
            "alpha": 0.23,
            "beta": 0.5,
            "L": 40,
            "dt": 0.025,
            "tmax": 15.0,
            "q_points": 81,
            "omega_points": 181,
            "threads": 8,
        },
        "checks": checks,
        "hashes": {
            "expected_manifest": expected_manifest,
            "actual_manifest": actual_manifest,
            "expected_standard": expected_standard,
            "actual_standard": actual_standard,
            "fourier_live": sha256(FOURIER),
        },
        "boundary": "L=80 CV anchor remains the only active heavy task; supervisor must release it before TEBD starts.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "checks_passed": sum(checks.values()), "checks_total": len(checks)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
