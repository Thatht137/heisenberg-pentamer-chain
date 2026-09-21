#!/usr/bin/env python3
"""修复 R18 source hash 列表的 CRLF 并重锁包哈希。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STAGE_REL = "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/stage-a-beta050-calibration-r18-a0025-L040"
STAGE = ROOT / STAGE_REL
HASHES = STAGE / "r18_source_hashes.sha256"
CONTRACT = STAGE / "launch-contract.json"
UPLOAD = STAGE / "server_upload_manifest.json"
AUDIT = STAGE / "package-repair-crlf.json"
LINE = re.compile(r"([0-9a-f]{64})  ([^\r\n]+)")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def main() -> int:
    if AUDIT.exists():
        raise FileExistsError("R18 CRLF 修复已执行")
    for path in (HASHES, CONTRACT, UPLOAD):
        if not path.is_file():
            raise FileNotFoundError(path)
    raw = HASHES.read_bytes()
    if b"\r\n" not in raw or b"\n" not in raw:
        raise ValueError("R18 source hash 列表不是预期 CRLF")
    lines = raw.decode("utf-8").splitlines()
    parsed = [LINE.fullmatch(line) for line in lines]
    if not lines or any(item is None for item in parsed):
        raise ValueError("R18 source hash 列表格式非法")
    for item in parsed:
        assert item is not None
        path = ROOT / item.group(2)
        if not path.is_file() or sha256(path) != item.group(1):
            raise ValueError(f"R18 source 哈希内容失配: {item.group(2)}")
    old_hash = sha256(HASHES)
    HASHES.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    new_hash = sha256(HASHES)
    if b"\r" in HASHES.read_bytes() or old_hash == new_hash:
        raise ValueError("R18 LF 修复失败")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("source_hashes_sha256") != old_hash:
        raise ValueError("R18 contract 旧哈希不匹配")
    contract["source_hashes_sha256"] = new_hash
    contract["package_repair"] = "CRLF->LF before first launch; physics unchanged"
    write_json(CONTRACT, contract)
    upload = json.loads(UPLOAD.read_text(encoding="utf-8"))
    entries = {item["path"]: item for item in upload.get("files", [])}
    for relative, path in ((f"{STAGE_REL}/r18_source_hashes.sha256", HASHES),
                           (f"{STAGE_REL}/launch-contract.json", CONTRACT)):
        if relative not in entries:
            raise ValueError(f"R18 upload manifest 缺少 {relative}")
        entries[relative].update({"sha256": sha256(path), "bytes": path.stat().st_size})
    upload["package_repair"] = "CRLF->LF before first launch; physics unchanged"
    write_json(UPLOAD, upload)
    audit = {
        "schema_version": 1, "status": "pass", "reason": "Windows CRLF blocked remote sha256sum -c",
        "launch_attempt_started_julia": False, "physics_or_acceptance_changed": False,
        "source_hashes_old_sha256": old_hash, "source_hashes_new_sha256": new_hash,
        "contract_sha256": sha256(CONTRACT), "upload_manifest_sha256": sha256(UPLOAD),
    }
    write_json(AUDIT, audit)
    print(json.dumps(audit, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
