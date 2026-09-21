#!/usr/bin/env python3
"""为最终报告与汇总文件生成 SHA-256。"""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v2_20260729"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def write_checksums(directory: Path, files: list[Path]) -> None:
    (directory / "checksums.sha256").write_text(
        "".join(f"{digest(path)}  {path.relative_to(directory).as_posix()}\n" for path in sorted(files)),
        encoding="utf-8",
    )


def main() -> None:
    write_checksums(
        RUN,
        [RUN / "report.json", RUN / "report.html", RUN / "evidence_matrix.md"]
        + sorted((RUN / "analysis").glob("*.png")),
    )
    round2 = RUN / "round2_alpha014_refinement"
    write_checksums(
        round2,
        [path for path in round2.iterdir() if path.is_file() and path.name != "checksums.sha256"],
    )


if __name__ == "__main__":
    main()
