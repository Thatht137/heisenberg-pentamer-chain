"""只读诊断 round31 当前活动 cell。"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
from pathlib import Path


REMOTE = "wangjieren@39.96.207.180"
PORT = "6000"

REMOTE_SCRIPT = r'''
import datetime, json, pathlib, subprocess
cell = pathlib.Path("/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/autoresearch_v5_20260803/round31_qpi_cv_extension/cell-l40-qpi-high-100")
def load(name):
    p = cell / name
    if not p.is_file(): return None
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc: return {"read_error": str(exc)}
def tail(name, n=4000):
    p = cell / name
    if not p.is_file(): return None
    return p.read_text(encoding="utf-8", errors="replace")[-n:]
def stat(name):
    p = cell / name
    if not p.is_file(): return None
    s = p.stat()
    return {"bytes": s.st_size, "mtime_utc": datetime.datetime.fromtimestamp(s.st_mtime, datetime.timezone.utc).isoformat()}
try:
    lines = subprocess.check_output(["pgrep", "-af", "cv_dsf_cell.jl"], text=True).splitlines()
except subprocess.CalledProcessError:
    lines = []
procs = []
for line in lines:
    pid = line.split(None, 1)[0]
    if "cell-l40-qpi-high-100" not in line: continue
    try:
        ps = subprocess.check_output(["ps", "-o", "pid=,ppid=,stat=,etime=,%cpu=,%mem=,wchan:32=,args=", "-p", pid], text=True).strip()
    except subprocess.CalledProcessError:
        ps = None
    procs.append({"pgrep": line, "ps": ps})
print(json.dumps({
    "checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "cell": str(cell),
    "progress": load("progress.json"),
    "status": load("status.json"),
    "file_stats": {name: stat(name) for name in ("progress.json", "stdout.log", "stderr.log", "resource.log", "checkpoint_latest.jld2", "manifest.json")},
    "stdout_tail": tail("stdout.log"),
    "stderr_tail": tail("stderr.log"),
    "resource_tail": tail("resource.log"),
    "processes": procs,
}, ensure_ascii=False))
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--key", default=str(Path.home() / ".ssh" / "id_ed25519"))
    args = parser.parse_args()
    encoded = base64.b64encode(REMOTE_SCRIPT.encode("utf-8")).decode("ascii")
    command = [
        "ssh", "-p", PORT, "-i", args.key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
        REMOTE, f'''python3 -c "import base64;exec(base64.b64decode('{encoded}'))"''',
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode:
        raise SystemExit(f"SSH 只读诊断失败: {result.stderr.strip()}")
    payload = json.loads(result.stdout)
    payload["target"] = f"{REMOTE}:{PORT}"
    payload["remote_write"] = False
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"target": payload["target"], "processes": len(payload["processes"]), "progress": payload["progress"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
