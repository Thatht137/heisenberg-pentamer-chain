#!/usr/bin/env python3
"""检查报告引用和本地 checksum，不连接服务器。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
OUTPUT = ROOT / "results" / "research_progress" / "local_integrity_audit_20260803.json"
REMOTE_PREFIXES = (
    "results/autoresearch_v5_20260802/round22_cv_l80_anchor/",
    "results/autoresearch_v5_20260803/round31_qpi_cv_extension/",
    "results/autoresearch_v5_20260805/code_backup_retry_20260805/",
    "results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_20260805_2003/",
)
FIGURE_EXTENSIONS = (".svg", ".pdf", ".png", ".tiff")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in strings(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in strings(child)]
    return []


def report_paths(report: dict[str, object]) -> tuple[list[str], list[str]]:
    found: set[str] = set()
    pattern = re.compile(r"(?:results|figures|scripts|docs|paper)/[A-Za-z0-9_./\\-]+")
    for text in strings(report):
        for piece in re.split(r"[\s\n]+", text):
            match = pattern.match(piece)
            if match:
                found.add(match.group(0).rstrip("./").replace("\\", "/"))
    missing: list[str] = []
    remote: list[str] = []
    for relative in sorted(found):
        if any(
            relative.startswith(prefix) or relative == prefix.rstrip("/")
            for prefix in REMOTE_PREFIXES
        ):
            remote.append(relative)
        elif (ROOT / relative).is_file() or (ROOT / relative).is_dir():
            continue
        elif relative.startswith("figures/") and Path(relative).suffix == "":
            if any((ROOT / f"{relative}{extension}").is_file() for extension in FIGURE_EXTENSIONS):
                continue
            missing.append(relative)
        else:
            missing.append(relative)
    return missing, remote


def checksum_audit() -> tuple[int, int, list[str]]:
    manifests = sorted((ROOT / "results").glob("**/checksums.sha256"))
    checked = 0
    failures: list[str] = []
    for manifest in manifests:
        run = manifest.parent.resolve()
        for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            expected, relative = line.split(maxsplit=1)
            relative = relative.lstrip("* ")
            target = (run / relative).resolve()
            try:
                target.relative_to(run)
            except ValueError:
                failures.append(f"{manifest}:{line_number}:path_escape")
                continue
            if not target.is_file():
                failures.append(f"{manifest}:{line_number}:missing:{relative}")
                continue
            checked += 1
            if digest(target) != expected.lower():
                failures.append(f"{manifest}:{line_number}:mismatch:{relative}")
    return len(manifests), checked, failures


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    missing, remote = report_paths(report)
    checksum_files, checksum_entries, checksum_failures = checksum_audit()
    result = {
        "schema_version": 1,
        "created_at": "2026-08-03",
        "status": "pass" if not missing and not checksum_failures else "fail",
        "report_references": {
            "total": len(set(path for text in strings(report) for path in re.findall(r"(?:results|figures|scripts|docs|paper)/[A-Za-z0-9_./\\-]+", text))),
            "missing_local": missing,
            "allowed_remote": remote,
        },
        "checksums": {
            "manifests": checksum_files,
            "entries_checked": checksum_entries,
            "failures": checksum_failures,
        },
        "scope": {"negative_alpha_included": False, "server_polled": False},
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
