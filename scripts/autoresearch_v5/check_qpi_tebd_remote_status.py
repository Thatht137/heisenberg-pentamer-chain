#!/usr/bin/env python3
"""只读采集严格 q=pi 远端生产任务状态。"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
from pathlib import Path


REMOTE = "wangjieren@39.96.207.180"
PORT = "6000"
RUN_ROOT = (
    "/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/"
    "autoresearch_v5_20260803/round26_qpi_tebd_production"
)


REMOTE_SCRIPT = r'''
import datetime
import json
import pathlib
import subprocess

root = pathlib.Path("/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/autoresearch_v5_20260803/round26_qpi_tebd_production")

def load_json(path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return {"read_error": str(error)}

def tail(path, lines=20):
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]

def stat(path):
    if not path.is_file():
        return None
    info = path.stat()
    return {"size_bytes": info.st_size, "mtime": datetime.datetime.fromtimestamp(info.st_mtime, datetime.timezone.utc).isoformat()}

try:
    julia_processes = subprocess.check_output(["pgrep", "-af", "julia"], text=True).splitlines()
except subprocess.CalledProcessError:
    julia_processes = []

try:
    matched = subprocess.check_output(
        ["pgrep", "-f", "round26_qpi_tebd_production|run_qpi_tebd_production_remote|tebd_qpi_autocorr"],
        text=True,
    ).split()
except subprocess.CalledProcessError:
    matched = []

process_table = []
if matched:
    process_table = subprocess.check_output(
        ["ps", "-o", "pid=,ppid=,stat=,etime=,%cpu=,%mem=,rss=,nlwp=,ni=,args=", "-p", ",".join(matched)],
        text=True,
    ).splitlines()

coarse = root / "cell-alpha023-qpi-dt0025-t30"
refined = root / "cell-alpha023-qpi-dt00125-t30"
payload = {
    "schema_version": 1,
    "checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "hostname": pathlib.Path("/etc/hostname").read_text().strip(),
    "run_root": str(root),
    "overall_status": load_json(root / "overall_status.json"),
    "coarse": {
        "progress": load_json(coarse / "progress.json"),
        "status": load_json(coarse / "status.json"),
        "manifest": load_json(coarse / "manifest.json"),
        "checkpoint": stat(coarse / "checkpoint_latest.jld2"),
        "stdout_tail": tail(coarse / "julia.stdout.log"),
        "stderr_tail": tail(coarse / "julia.stderr.log"),
    },
    "refined": {
        "progress": load_json(refined / "progress.json"),
        "status": load_json(refined / "status.json"),
        "manifest": load_json(refined / "manifest.json"),
        "checkpoint": stat(refined / "checkpoint_latest.jld2"),
        "stdout_tail": tail(refined / "julia.stdout.log"),
        "stderr_tail": tail(refined / "julia.stderr.log"),
    },
    "supervisor_tail": tail(root / "supervisor.log"),
    "julia_process_count": len(julia_processes),
    "julia_processes": julia_processes,
    "matched_process_table": process_table,
}
print(json.dumps(payload, ensure_ascii=False))
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--key", default=str(Path.home() / ".ssh/id_ed25519"))
    args = parser.parse_args()

    encoded = base64.b64encode(REMOTE_SCRIPT.encode("utf-8")).decode("ascii")
    remote_command = f'''python3 -c "import base64;exec(base64.b64decode('{encoded}'))"'''
    command = [
        "ssh",
        "-p",
        PORT,
        "-i",
        args.key,
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        REMOTE,
        remote_command,
    ]
    result = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"SSH 只读检查失败: {result.stderr.strip()}")
    payload = json.loads(result.stdout)
    payload["target"] = f"{REMOTE}:{PORT}"
    payload["remote_write"] = False
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
