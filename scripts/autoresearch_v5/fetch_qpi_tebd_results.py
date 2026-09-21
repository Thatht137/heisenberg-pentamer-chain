#!/usr/bin/env python3
"""经明确确认后非覆盖式回传并验证严格 q=pi 结果。"""

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


def verify_checksums(cell: Path) -> tuple[bool, list[str]]:
    failures: list[str] = []
    checksum_path = cell / "checksums.sha256"
    if not checksum_path.is_file():
        return False, ["缺少 checksums.sha256"]
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = (cell / relative.strip()).resolve()
        try:
            target.relative_to(cell)
        except ValueError:
            failures.append(f"路径越界: {relative}")
            continue
        if not target.is_file():
            failures.append(f"文件缺失: {relative}")
        elif sha256(target) != expected:
            failures.append(f"哈希不匹配: {relative}")
    return not failures, failures


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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    preview_path = Path(args.preview).resolve()
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    destination = Path(args.destination).resolve()
    expected_destination = Path(preview["local_destination"]).resolve()
    if destination != expected_destination:
        raise SystemExit("目标目录与已审阅预览不一致")
    if preview.get("remote_checksum_status") != "pass":
        raise SystemExit("远端 checksum 预览未通过")
    if destination.exists():
        raise SystemExit(f"拒绝覆盖已有目录: {destination}")
    remote_root = str(preview["run_root"])
    command = [
        "scp",
        "-P",
        PORT,
        "-i",
        args.key,
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        "-r",
        f"{REMOTE}:{remote_root}",
        "<validated-temporary-parent>",
    ]
    plan = {
        "action": "non_clobbering_fetch",
        "source": f"{REMOTE}:{remote_root}",
        "destination": str(destination),
        "destination_exists": False,
        "expected_file_count": int(preview["file_count"]),
        "expected_total_bytes": int(preview["total_bytes"]),
        "remote_checksum_status": preview["remote_checksum_status"],
        "confirmed": args.confirmed,
        "dry_run": args.dry_run,
        "command": command,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False))
        return
    if not args.confirmed:
        raise SystemExit("缺少 --confirmed；必须在用户明确确认后执行")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_parent = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.fetching-", dir=destination.parent)
    ).resolve()
    downloaded = temporary_parent / destination.name
    try:
        real_command = command[:-1] + [str(temporary_parent)]
        result = subprocess.run(
            real_command,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"scp 失败: {result.stderr.strip()}")
        if not downloaded.is_dir():
            raise RuntimeError("scp 未生成预期 run 目录")
        file_count, total_bytes = tree_stats(downloaded)
        if file_count != int(preview["file_count"]) or total_bytes != int(preview["total_bytes"]):
            raise RuntimeError(
                f"文件统计不一致: files={file_count}, bytes={total_bytes}"
            )
        cell_results: dict[str, object] = {}
        for cell_name, remote_cell in preview["cells"].items():
            cell = downloaded / cell_name
            checksum_ok, failures = verify_checksums(cell)
            local_checksums_hash = sha256(cell / "checksums.sha256")
            local_manifest_hash = sha256(cell / "manifest.json")
            if local_checksums_hash != remote_cell["checksums_sha256"]:
                failures.append("checksums.sha256 与远端预览不一致")
            if local_manifest_hash != remote_cell["manifest_sha256"]:
                failures.append("manifest.json 与远端预览不一致")
            if failures or not checksum_ok:
                raise RuntimeError(f"{cell_name} 本地验证失败: {failures}")
            cell_results[cell_name] = {
                "status": "pass",
                "checksums_sha256": local_checksums_hash,
                "manifest_sha256": local_manifest_hash,
            }
        overall_hash = sha256(downloaded / "overall_status.json")
        if overall_hash != preview["overall_status_sha256"]:
            raise RuntimeError("overall_status.json 与远端预览不一致")
        downloaded.replace(destination)
        receipt = {
            "schema_version": 1,
            "status": "pass",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source": f"{REMOTE}:{remote_root}",
            "destination": str(destination),
            "file_count": file_count,
            "total_bytes": total_bytes,
            "overall_status_sha256": overall_hash,
            "cells": cell_results,
            "preview_sha256": sha256(preview_path),
            "non_clobbering": True,
            "user_confirmed": True,
        }
        receipt_path = Path(args.receipt).resolve()
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(receipt, ensure_ascii=False))
    finally:
        if temporary_parent.is_dir():
            temporary_parent.relative_to(destination.parent)
            shutil.rmtree(temporary_parent)


if __name__ == "__main__":
    main()
