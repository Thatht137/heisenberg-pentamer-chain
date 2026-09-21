#!/usr/bin/env python3
"""只读验证远端严格 q=pi 结果并生成非覆盖式回传预览。"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
from pathlib import Path


REMOTE = "wangjieren@39.96.207.180"
PORT = "6000"
DEFAULT_RUN_ROOT = (
    "/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/"
    "autoresearch_v5_20260803/round26_qpi_tebd_production"
)
DEFAULT_CELLS = [
    "cell-alpha023-qpi-dt0025-t30",
    "cell-alpha023-qpi-dt00125-t30",
]


REMOTE_SCRIPT = r'''
import hashlib
import json
import pathlib

root = pathlib.Path("/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/autoresearch_v5_20260803/round26_qpi_tebd_production")
cells = [
    root / "cell-alpha023-qpi-dt0025-t30",
    root / "cell-alpha023-qpi-dt00125-t30",
]

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def verify(cell):
    failures = []
    checksum_path = cell / "checksums.sha256"
    if not checksum_path.is_file():
        return {"status": "fail", "failures": ["缺少 checksums.sha256"]}
    checked = 0
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = (cell / relative.strip()).resolve()
        try:
            target.relative_to(cell)
        except ValueError:
            failures.append("路径越界: " + relative)
            continue
        if not target.is_file():
            failures.append("文件缺失: " + relative)
        elif sha256(target) != expected:
            failures.append("哈希不匹配: " + relative)
        checked += 1
    return {
        "status": "pass" if not failures else "fail",
        "checked_files": checked,
        "failures": failures,
        "checksums_sha256": sha256(checksum_path),
        "manifest_sha256": sha256(cell / "manifest.json"),
    }

files = [path for path in root.rglob("*") if path.is_file()]
payload = {
    "schema_version": 1,
    "run_root": str(root),
    "exists": root.is_dir(),
    "file_count": len(files),
    "total_bytes": sum(path.stat().st_size for path in files),
    "overall_status_sha256": sha256(root / "overall_status.json"),
    "cells": {cell.name: verify(cell) for cell in cells},
}
payload["remote_checksum_status"] = "pass" if all(
    value["status"] == "pass" for value in payload["cells"].values()
) else "fail"
print(json.dumps(payload, ensure_ascii=False))
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--run-root", default=DEFAULT_RUN_ROOT)
    parser.add_argument("--cell-id", action="append", dest="cell_ids")
    parser.add_argument("--key", default=str(Path.home() / ".ssh/id_ed25519"))
    args = parser.parse_args()

    destination = Path(args.destination).resolve()
    run_root = args.run_root.rstrip("/")
    cell_ids = args.cell_ids or DEFAULT_CELLS
    remote_script = REMOTE_SCRIPT.replace(
        "/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/autoresearch_v5_20260803/round26_qpi_tebd_production",
        run_root,
    ).replace(
        "    root / \"cell-alpha023-qpi-dt0025-t30\",\n    root / \"cell-alpha023-qpi-dt00125-t30\",",
        "\n".join(f'    root / "{cell}",' for cell in cell_ids),
    )
    encoded = base64.b64encode(remote_script.encode("utf-8")).decode("ascii")
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
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"远端 checksum 预览失败: {result.stderr.strip()}")
    payload = json.loads(result.stdout)
    payload.update(
        {
            "target": f"{REMOTE}:{PORT}",
            "local_destination": str(destination),
            "local_destination_exists": destination.exists(),
            "non_clobber_required": True,
            "remote_write": False,
            "fetch_authorized": False,
            "fetch_command_preview": (
                f"scp -P {PORT} -i {args.key} -r "
                f"{REMOTE}:{run_root} {destination.parent}"
            ),
        }
    )
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    print(json.dumps(payload, ensure_ascii=False))
    if payload["remote_checksum_status"] != "pass" or destination.exists():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
