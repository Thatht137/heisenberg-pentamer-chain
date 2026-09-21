"""生成严格 q=pi maxdim=96 的提交预览，不执行远端动作。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/autoresearch_v5/run_qpi_tebd_maxdim96_remote.sh"
OUTPUT = ROOT / "results/research_progress/qpi_tebd_maxdim96_submission_preview_20260803.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    run_root = "/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/autoresearch_v5_20260803/round28_qpi_maxdim96"
    remote_script = "/home/wangjieren/code/1x5_Heisenberg_Pentamer/scripts/run_qpi_tebd_maxdim96_remote_20260803.sh"
    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target": "wangjieren@39.96.207.180:6000",
        "action": "preview_only",
        "scope": {
            "alpha": 0.23,
            "beta": 0.5,
            "L": 40,
            "q_over_pi": 1.0,
            "negative_alpha_excluded": True,
            "figure_9_excluded": True,
        },
        "run_root": run_root,
        "cell_id": "qpi-alpha023-maxdim096-dt00125-t30",
        "parameters": {
            "method": "finite_dmrg_tebd_qpi_autocorrelation",
            "boundary": "OBC",
            "sector": "Sz=0",
            "eta": 0.1,
            "tstep": 0.0125,
            "n_steps": 2400,
            "tmax": 30.0,
            "dmrg_maxdim": 96,
            "tebd_maxdim": 96,
            "nsweeps": 24,
            "cutoff": 1e-10,
            "threads": 8,
            "omega_grid": [0.0, 3.0, 0.05],
        },
        "resources": {
            "nice": 10,
            "julia_processes": 1,
            "network_downloads": False,
            "checkpoint_interval_steps": 100,
            "estimated_wall_hours": [0.13, 0.30],
            "conservative_upper_hours": 0.50,
            "basis": "L=40 refined actual maxdim=117, TEBD wall=664.6 s; D=96 lowers the active cap",
        },
        "safety": {
            "preflight_reject_existing_run": True,
            "preflight_reject_existing_julia": True,
            "non_clobbering": True,
            "offline_julia_packages": True,
            "remote_write": False,
            "requires_explicit_confirmation": True,
        },
        "remote_conflict_checks": {
            "run_root_exists": False,
            "remote_script_exists": False,
            "checked_read_only": True,
        },
        "commands": {
            "upload": "scp -P 6000 -i C:\\Users\\hh250\\.ssh\\id_ed25519 scripts/autoresearch_v5/run_qpi_tebd_maxdim96_remote.sh wangjieren@39.96.207.180:/home/wangjieren/code/1x5_Heisenberg_Pentamer/scripts/run_qpi_tebd_maxdim96_remote_20260803.sh",
            "execute": f"ssh -p 6000 -i C:\\Users\\hh250\\.ssh\\id_ed25519 wangjieren@39.96.207.180 bash {remote_script}",
            "post_run_read_only": "python scripts/autoresearch_v5/check_qpi_tebd_remote_status.py --output results/research_progress/qpi_tebd_remote_status_after_maxdim96.json --key C:/Users/hh250/.ssh/id_ed25519",
        },
        "script": {
            "path": "scripts/autoresearch_v5/run_qpi_tebd_maxdim96_remote.sh",
            "sha256": sha256(SCRIPT),
            "upload_files": 1,
        },
        "post_run": [
            "terminal manifest/status/checksums",
            "local independent checksum",
            "analyze_qpi_tebd_production.py --maxdim-dir",
            "maxdim peak <=0.05 and integrated weight <=5%",
            "update report.html",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
