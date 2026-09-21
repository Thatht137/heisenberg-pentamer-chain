"""非覆盖式回传 CV 扩展结果并做本地独立 checksum。"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


REMOTE = "wangjieren@39.96.207.180"
PORT = "6000"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_cell(cell: Path) -> None:
    for line in (cell / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = (cell / relative.strip()).resolve()
        target.relative_to(cell)
        if not target.is_file() or sha256(target) != expected:
            raise RuntimeError(f"checksum 失败: {cell.name}/{relative}")


def tree_stats(root: Path) -> tuple[int, int]:
    files = [path for path in root.rglob("*") if path.is_file()]
    return len(files), sum(path.stat().st_size for path in files)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--key", default=str(Path.home() / ".ssh/id_ed25519"))
    parser.add_argument("--confirmed", action="store_true")
    args = parser.parse_args()
    preview_path = Path(args.preview).resolve()
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    destination = Path(args.destination).resolve()
    if destination != Path(preview["local_destination"]).resolve():
        raise SystemExit("目标目录与预览不一致")
    if destination.exists() or preview.get("remote_checksum_status") != "pass":
        raise SystemExit("目标已存在或远端 checksum 未通过")
    if not args.confirmed:
        raise SystemExit("需要 --confirmed")
    root = preview["run_root"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.fetching-", dir=destination.parent))
    downloaded = staging / destination.name
    try:
        command = ["scp", "-P", PORT, "-i", args.key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-r", f"{REMOTE}:{root}", str(staging)]
        result = subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
        if result.returncode or not downloaded.is_dir():
            raise RuntimeError(f"scp 失败: {result.stderr.strip()}")
        count, total = tree_stats(downloaded)
        if count != int(preview["file_count"]) or total != int(preview["total_bytes"]):
            raise RuntimeError(f"文件统计不一致: {count}/{total}")
        for cell in preview["cells"]:
            verify_cell(downloaded / cell)
        downloaded.replace(destination)
        receipt = {
            "schema_version": 1,
            "status": "pass",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source": f"{REMOTE}:{root}",
            "destination": str(destination),
            "file_count": count,
            "total_bytes": total,
            "cells": {cell: {"status": "pass", "checksums_sha256": sha256(destination / cell / "checksums.sha256")} for cell in preview["cells"]},
            "preview_sha256": sha256(preview_path),
            "non_clobbering": True,
            "user_confirmed": True,
        }
        Path(args.receipt).resolve().write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt, ensure_ascii=False))
    finally:
        if staging.is_dir():
            shutil.rmtree(staging)


if __name__ == "__main__":
    main()
