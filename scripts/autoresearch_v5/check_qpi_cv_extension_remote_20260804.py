"""只读检查 round31 q=pi CV 顺序任务。"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
from pathlib import Path


REMOTE = "wangjieren@39.96.207.180"
PORT = "6000"
RUN = "/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/autoresearch_v5_20260803/round31_qpi_cv_extension"


REMOTE_SCRIPT = r'''
import datetime, json, pathlib, subprocess
root = pathlib.Path("/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/autoresearch_v5_20260803/round31_qpi_cv_extension")
def load(path):
    if not path.is_file(): return None
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc: return {"read_error": str(exc)}
def stat(path):
    if not path.is_file(): return None
    info = path.stat()
    return {"bytes": info.st_size, "mtime": datetime.datetime.fromtimestamp(info.st_mtime, datetime.timezone.utc).isoformat()}
try:
    processes = subprocess.check_output(["pgrep", "-af", "julia"], text=True).splitlines()
except subprocess.CalledProcessError:
    processes = []
cells = {}
for name in ("cell-l40-qpi-low-000-020", "cell-l40-qpi-high-055", "cell-l40-qpi-high-100", "cell-l40-qpi-high-150"):
    cell = root / name
    cells[name] = {"progress": load(cell / "progress.json"), "status": load(cell / "status.json"), "manifest": load(cell / "manifest.json"), "checkpoint": stat(cell / "checkpoint_latest.jld2")}
print(json.dumps({"checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "run_root": str(root), "overall_progress": load(root / "overall_progress.json"), "overall_status": load(root / "overall_status.json"), "cells": cells, "julia_processes": processes, "julia_process_count": len(processes), "supervisor_log": stat(root / "supervisor.log")}, ensure_ascii=False))
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--key", default=str(Path.home() / ".ssh" / "id_ed25519"))
    args = parser.parse_args()
    encoded = base64.b64encode(REMOTE_SCRIPT.encode("utf-8")).decode("ascii")
    command = [
        "ssh", "-p", PORT, "-i", args.key, "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=15", REMOTE,
        f'''python3 -c "import base64;exec(base64.b64decode('{encoded}'))"''',
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0:
        raise SystemExit(f"SSH 只读检查失败: {result.stderr.strip()}")
    payload = json.loads(result.stdout)
    payload["target"] = f"{REMOTE}:{PORT}"
    payload["remote_write"] = False
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"target": payload["target"], "julia_process_count": payload["julia_process_count"], "cells": list(payload["cells"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
