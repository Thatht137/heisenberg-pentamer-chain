#!/usr/bin/env python3
"""预览并非覆盖回传单个全动量 TEBD run。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = (ROOT / "results").resolve()
REMOTE = "wangjieren@39.96.207.180"
PORT = "6000"
REMOTE_CAMPAIGN = "/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/autoresearch_v5_20260807/minimal_fullq_campaign"
CELL_PATTERN = re.compile(r"fullq-(uniform|weak|agreement)(?:-eta020)?-dt(025|0125)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_cell_id(value: str) -> str:
    if CELL_PATTERN.fullmatch(value) is None:
        raise ValueError(f"非法 cell-id: {value}")
    return value


def under_results(path: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(RESULTS)
    return resolved


def verify_checksums(run: Path) -> tuple[bool, list[str]]:
    checksum_file = run / "checksums.sha256"
    if not checksum_file.is_file():
        return False, ["缺少 checksums.sha256"]
    failures: list[str] = []
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = (run / relative.strip()).resolve()
        try:
            target.relative_to(run)
        except ValueError:
            failures.append(f"路径越界: {relative}")
            continue
        if not target.is_file():
            failures.append(f"文件缺失: {relative}")
        elif sha256(target) != expected:
            failures.append(f"哈希不匹配: {relative}")
    return not failures, failures


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)


def ssh_base(key: str) -> list[str]:
    return ["ssh", "-p", PORT, "-i", key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", REMOTE]


def preview(args: argparse.Namespace) -> None:
    cell_id = validate_cell_id(args.cell_id)
    destination = under_results(Path(args.destination))
    if destination.exists():
        raise SystemExit(f"拒绝覆盖已有目录: {destination}")
    remote_campaign = str(args.remote_campaign).rstrip("/")
    if not remote_campaign.startswith("/home/"):
        raise SystemExit("远端 campaign 路径必须位于 /home/ 下")
    remote_dir = f"{remote_campaign}/{cell_id}"
    remote_script = (
        f"cd {remote_dir} && "
        "test -f status.json -a -f manifest.json -a -f checksums.sha256 && "
        "sha256sum -c checksums.sha256 >/dev/null && "
        "sha256sum checksums.sha256 manifest.json status.json && "
        "find . -type f -printf '%s\\n' | awk '{s+=$1;n+=1} END {print n, s}'"
    )
    result = run_command(ssh_base(args.key) + [remote_script])
    if result.returncode != 0:
        raise SystemExit(f"远端预览失败: {result.stderr.strip()}")
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) < 4:
        raise SystemExit("远端预览输出不完整")
    hashes: dict[str, str] = {}
    for line in lines[-4:-1]:
        digest, name = line.split(maxsplit=1)
        hashes[name] = digest
    file_count, total_bytes = (int(value) for value in lines[-1].split())
    payload = {
        "schema_version": 1,
        "status": "pass",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cell_id": cell_id,
        "remote": REMOTE,
        "remote_dir": remote_dir,
        "local_destination": str(destination),
        "destination_exists": False,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "remote_checksum_status": "pass",
        "hashes": hashes,
    }
    output = under_results(Path(args.output))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


def fetch(args: argparse.Namespace) -> None:
    plan_path = under_results(Path(args.preview))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    cell_id = validate_cell_id(str(plan["cell_id"]))
    destination = under_results(Path(args.destination))
    if destination != Path(str(plan["local_destination"])).resolve():
        raise SystemExit("目标目录与预览不一致")
    if plan.get("remote_checksum_status") != "pass" or plan.get("destination_exists") is not False:
        raise SystemExit("预览未通过远端 checksum 或非覆盖门")
    if destination.exists():
        raise SystemExit(f"拒绝覆盖已有目录: {destination}")
    if not args.confirmed:
        raise SystemExit("缺少 --confirmed")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_parent = Path(tempfile.mkdtemp(prefix=f".{cell_id}.fetching-", dir=destination.parent)).resolve()
    downloaded = temporary_parent / cell_id
    try:
        command = [
            "scp", "-P", PORT, "-i", args.key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
            "-r", f"{REMOTE}:{plan['remote_dir']}", str(temporary_parent),
        ]
        result = run_command(command)
        if result.returncode != 0:
            raise RuntimeError(f"scp 失败: {result.stderr.strip()}")
        if not downloaded.is_dir():
            raise RuntimeError("未生成预期下载目录")
        files = [path for path in downloaded.rglob("*") if path.is_file()]
        total_bytes = sum(path.stat().st_size for path in files)
        if len(files) != int(plan["file_count"]) or total_bytes != int(plan["total_bytes"]):
            raise RuntimeError("下载文件统计与预览不一致")
        checksum_ok, failures = verify_checksums(downloaded)
        for name, expected in plan["hashes"].items():
            target = downloaded / name
            if not target.is_file() or sha256(target) != expected:
                failures.append(f"远端预览哈希不一致: {name}")
        if not checksum_ok or failures:
            raise RuntimeError("本地 checksum 失败: " + "; ".join(failures))
        downloaded.replace(destination)
        receipt = {
            "schema_version": 1,
            "status": "pass",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cell_id": cell_id,
            "source": f"{REMOTE}:{plan['remote_dir']}",
            "destination": str(destination),
            "file_count": len(files),
            "total_bytes": total_bytes,
            "preview_sha256": sha256(plan_path),
            "checksums_sha256": sha256(destination / "checksums.sha256"),
            "manifest_sha256": sha256(destination / "manifest.json"),
            "non_clobbering": True,
        }
        output = under_results(Path(args.output))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt, ensure_ascii=False))
    finally:
        if temporary_parent.is_dir():
            temporary_parent.relative_to(destination.parent)
            shutil.rmtree(temporary_parent)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("--cell-id", required=True)
    preview_parser.add_argument("--destination", required=True)
    preview_parser.add_argument("--output", required=True)
    preview_parser.add_argument("--remote-campaign", default=REMOTE_CAMPAIGN)
    preview_parser.add_argument("--key", default=str(Path.home() / ".ssh/id_ed25519"))
    preview_parser.set_defaults(handler=preview)
    fetch_parser = subparsers.add_parser("fetch")
    fetch_parser.add_argument("--preview", required=True)
    fetch_parser.add_argument("--destination", required=True)
    fetch_parser.add_argument("--output", required=True)
    fetch_parser.add_argument("--key", default=str(Path.home() / ".ssh/id_ed25519"))
    fetch_parser.add_argument("--confirmed", action="store_true")
    fetch_parser.set_defaults(handler=fetch)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
