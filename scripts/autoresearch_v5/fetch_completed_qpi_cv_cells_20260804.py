"""非覆盖式回传已结束的 round31 cell。"""

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
    ledger = cell / "checksums.sha256"
    if not ledger.is_file():
        raise RuntimeError(f"缺少 checksum 清单: {cell.name}")
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = (cell / relative.lstrip("* ")).resolve()
        target.relative_to(cell.resolve())
        if not target.is_file() or sha256(target) != expected.lower():
            raise RuntimeError(f"checksum 失败: {cell.name}/{relative}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--cell-id", action="append", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--key", default=str(Path.home() / ".ssh/id_ed25519"))
    parser.add_argument("--confirmed", action="store_true")
    args = parser.parse_args()

    preview_path = Path(args.preview).resolve()
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    destination = Path(args.destination).resolve()
    if not args.confirmed:
        raise SystemExit("需要 --confirmed")
    if destination.exists():
        raise SystemExit("拒绝覆盖已有目标目录")
    if preview.get("remote_checksum_status") != "pass":
        raise SystemExit("远端 checksum 预检未通过")
    preview_cells = preview.get("cells", {})
    if any(cell not in preview_cells or preview_cells[cell].get("status") != "pass" for cell in args.cell_id):
        raise SystemExit("所选 cell 未在通过 checksum 的预览中")

    root = preview["run_root"].rstrip("/")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.fetching-", dir=destination.parent))
    downloaded = staging / destination.name
    downloaded.mkdir()
    try:
        for cell in args.cell_id:
            command = [
                "scp", "-P", PORT, "-i", args.key, "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=15", "-r", f"{REMOTE}:{root}/{cell}", str(downloaded),
            ]
            result = subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
            if result.returncode or not (downloaded / cell).is_dir():
                raise RuntimeError(f"scp 失败 ({cell}): {result.stderr.strip()}")
            verify_cell(downloaded / cell)

        files = [path for path in downloaded.rglob("*") if path.is_file()]
        receipt = {
            "schema_version": 1,
            "status": "pass",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source": f"{REMOTE}:{root}",
            "destination": str(destination),
            "cells": {cell: {"status": "pass", "checksums_sha256": sha256(downloaded / cell / "checksums.sha256")} for cell in args.cell_id},
            "file_count": len(files),
            "total_bytes": sum(path.stat().st_size for path in files),
            "preview_sha256": sha256(preview_path),
            "non_clobbering": True,
            "remote_write": False,
            "user_confirmed": True,
        }
        downloaded.replace(destination)
        Path(args.receipt).resolve().write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt, ensure_ascii=False))
    finally:
        if staging.is_dir():
            shutil.rmtree(staging)


if __name__ == "__main__":
    main()
