#!/usr/bin/env python3
"""预览并非覆盖回传负 alpha 相图 cell。"""

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
DEFAULT_REMOTE = "wangjieren@39.96.207.180"
DEFAULT_PORT = "6000"
CELL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def under_results(path: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(RESULTS)
    return resolved


def cell_id(value: str) -> str:
    if CELL_RE.fullmatch(value) is None or ".." in value:
        raise ValueError(f"非法 cell-id: {value}")
    return value


def checksum_lines(checksum_file: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or re.fullmatch(r"[0-9a-f]{64}", parts[0]) is None:
            raise ValueError(f"非法 checksum 行: {line}")
        pairs.append((parts[0], parts[1].strip().lstrip("*")))
    if not pairs:
        raise ValueError("空 checksums.sha256")
    return pairs


def verify_checksums(run: Path) -> tuple[bool, list[str]]:
    checksum_file = run / "checksums.sha256"
    if not checksum_file.is_file():
        return False, ["缺少 checksums.sha256"]
    failures: list[str] = []
    try:
        pairs = checksum_lines(checksum_file)
    except ValueError as error:
        return False, [str(error)]
    for expected, relative in pairs:
        target = (run / relative).resolve()
        try:
            target.relative_to(run)
        except ValueError:
            failures.append(f"checksum 路径越界: {relative}")
            continue
        if not target.is_file():
            failures.append(f"checksum 文件缺失: {relative}")
        elif sha256(target) != expected:
            failures.append(f"checksum 不匹配: {relative}")
    return not failures, failures


def command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)


def ssh_base(args: argparse.Namespace) -> list[str]:
    return ["ssh", "-p", str(args.port), "-i", args.key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", args.remote]


def checked_remote_dir(args: argparse.Namespace, identifier: str) -> str:
    campaign = str(args.remote_campaign).rstrip("/")
    parts = Path(campaign).parts
    if not campaign.startswith("/home/") or any(part in {".", ".."} for part in parts):
        raise SystemExit("远端 campaign 必须是 /home/ 下的规范路径")
    return f"{campaign}/{identifier}"


def preview(args: argparse.Namespace) -> None:
    identifier = cell_id(args.cell_id)
    destination = under_results(Path(args.destination))
    output = under_results(Path(args.output))
    if destination.exists():
        raise SystemExit(f"拒绝覆盖已有目录: {destination}")
    remote_dir = checked_remote_dir(args, identifier)
    script = (
        f"cd {remote_dir} && test -f manifest.json -a -f status.json -a -f checksums.sha256 && "
        "sha256sum -c checksums.sha256 >/dev/null && "
        "sha256sum checksums.sha256 manifest.json status.json && "
        "find . -type f -printf '%s\\n' | awk '{s+=$1;n+=1} END {print n, s}'"
    )
    result = command(ssh_base(args) + [script])
    if result.returncode:
        raise SystemExit(f"远端预览失败: {result.stderr.strip()}")
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) < 4:
        raise SystemExit("远端预览输出不完整")
    try:
        hashes = {name: digest for digest, name in (line.split(maxsplit=1) for line in lines[-4:-1])}
        file_count, total_bytes = (int(item) for item in lines[-1].split())
    except (TypeError, ValueError) as error:
        raise SystemExit(f"无法解析远端预览: {error}") from error
    payload = {
        "schema_version": 1, "status": "pass", "created_at": datetime.now(timezone.utc).isoformat(),
        "cell_id": identifier, "remote": args.remote, "port": str(args.port), "remote_dir": remote_dir,
        "local_destination": str(destination), "destination_exists": False, "file_count": file_count,
        "total_bytes": total_bytes, "remote_checksum_status": "pass", "hashes": hashes,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


def fetch(args: argparse.Namespace) -> None:
    plan_path = under_results(Path(args.preview))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    identifier = cell_id(str(plan.get("cell_id", "")))
    destination = under_results(Path(args.destination))
    output = under_results(Path(args.output))
    if destination != Path(str(plan.get("local_destination", ""))).resolve():
        raise SystemExit("目标目录与预览不一致")
    if plan.get("remote_checksum_status") != "pass" or plan.get("destination_exists") is not False:
        raise SystemExit("预览未通过 checksum 或非覆盖门")
    if destination.exists():
        raise SystemExit(f"拒绝覆盖已有目录: {destination}")
    if not args.confirmed:
        raise SystemExit("缺少 --confirmed")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{identifier}.fetching-", dir=destination.parent)).resolve()
    downloaded = temporary / identifier
    try:
        result = command(["scp", "-P", str(plan["port"]), "-i", args.key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-r", f"{plan['remote']}:{plan['remote_dir']}", str(temporary)])
        if result.returncode:
            raise RuntimeError(f"scp 失败: {result.stderr.strip()}")
        if not downloaded.is_dir():
            raise RuntimeError("未生成预期下载目录")
        files = [path for path in downloaded.rglob("*") if path.is_file()]
        total_bytes = sum(path.stat().st_size for path in files)
        if len(files) != int(plan["file_count"]) or total_bytes != int(plan["total_bytes"]):
            raise RuntimeError("下载统计与预览不一致")
        ok, failures = verify_checksums(downloaded)
        for name, expected in dict(plan["hashes"]).items():
            target = downloaded / name
            if not target.is_file() or sha256(target) != expected:
                failures.append(f"远端预览哈希不一致: {name}")
        if not ok or failures:
            raise RuntimeError("本地 checksum 失败: " + "; ".join(failures))
        downloaded.replace(destination)
        receipt = {
            "schema_version": 1, "status": "pass", "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cell_id": identifier, "source": f"{plan['remote']}:{plan['remote_dir']}", "destination": str(destination),
            "file_count": len(files), "total_bytes": total_bytes, "preview_sha256": sha256(plan_path),
            "checksums_sha256": sha256(destination / "checksums.sha256"), "manifest_sha256": sha256(destination / "manifest.json"),
            "non_clobbering": True,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt, ensure_ascii=False))
    finally:
        if temporary.is_dir():
            shutil.rmtree(temporary)


def main() -> None:
    parser = argparse.ArgumentParser()
    parsers = parser.add_subparsers(dest="action", required=True)
    preview_parser = parsers.add_parser("preview")
    preview_parser.add_argument("--cell-id", required=True)
    preview_parser.add_argument("--destination", required=True)
    preview_parser.add_argument("--output", required=True)
    preview_parser.add_argument("--remote-campaign", required=True)
    preview_parser.add_argument("--remote", default=DEFAULT_REMOTE)
    preview_parser.add_argument("--port", default=DEFAULT_PORT)
    preview_parser.add_argument("--key", default=str(Path.home() / ".ssh/id_ed25519"))
    preview_parser.set_defaults(handler=preview)
    fetch_parser = parsers.add_parser("fetch")
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
