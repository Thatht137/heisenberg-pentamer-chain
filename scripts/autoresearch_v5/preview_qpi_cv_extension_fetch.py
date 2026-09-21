"""只读检查 CV 扩展远端结果并生成非覆盖式回传预览。"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


REMOTE = "wangjieren@39.96.207.180"
PORT = "6000"


def ssh(key: str, command: str) -> str:
    result = subprocess.run(
        ["ssh", "-p", PORT, "-i", key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", REMOTE, command],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise SystemExit(f"远端预览失败: {result.stderr.strip()}")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--cell-id", action="append", required=True)
    parser.add_argument("--key", default=str(Path.home() / ".ssh/id_ed25519"))
    args = parser.parse_args()
    root = args.run_root.rstrip("/")
    exists = ssh(args.key, f"test -d {root} && echo true || echo false") == "true"
    cells: dict[str, object] = {}
    for cell in args.cell_id:
        path = f"{root}/{cell}"
        checksum = ssh(args.key, f"cd {path} && sha256sum -c checksums.sha256 >/dev/null && echo pass || echo fail")
        cells[cell] = {"status": "pass" if checksum == "pass" else "fail", "remote_path": path}
    stats = ssh(args.key, f"find {root} -type f -printf '%s\\n' | awk 'BEGIN{{n=0;s=0}}{{n++;s+=$1}}END{{print n, s}}'" if exists else "echo 0 0")
    file_count, total_bytes = (int(value) for value in stats.split())
    payload = {
        "schema_version": 1,
        "run_root": root,
        "exists": exists,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "cells": cells,
        "remote_checksum_status": "pass" if exists and all(item["status"] == "pass" for item in cells.values()) else "fail",
        "target": f"{REMOTE}:{PORT}",
        "local_destination": str(Path(args.destination).resolve()),
        "local_destination_exists": Path(args.destination).resolve().exists(),
        "non_clobber_required": True,
        "remote_write": False,
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    if payload["remote_checksum_status"] != "pass" or payload["local_destination_exists"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
