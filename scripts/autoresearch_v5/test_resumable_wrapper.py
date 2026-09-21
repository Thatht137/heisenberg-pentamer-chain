#!/usr/bin/env python3
"""验证可恢复任务的哈希与原子写入规则。"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_cv_dsf_resumable as target


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class ChecksumTests(unittest.TestCase):
    def make_case(self, status: str) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        outdir = Path(temporary.name).resolve()
        fixed = b"fixed\n"
        mutable = b"mutable\n"
        (outdir / "run_config.json").write_bytes(fixed)
        (outdir / "status.json").write_text(
            json.dumps({"status": status}), encoding="utf-8"
        )
        (outdir / "stdout.log").write_bytes(mutable)
        (outdir / "checksums.sha256").write_text(
            f"{digest(fixed)}  run_config.json\n"
            f"{digest(mutable)}  stdout.log\n",
            encoding="utf-8",
        )
        return temporary, outdir

    def test_partial_requires_all_files_to_match(self) -> None:
        temporary, outdir = self.make_case("partial")
        self.addCleanup(temporary.cleanup)
        (outdir / "stdout.log").write_text("changed\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            target.verify_checksums(outdir)

    def test_running_allows_mutable_file_to_change(self) -> None:
        temporary, outdir = self.make_case("running")
        self.addCleanup(temporary.cleanup)
        (outdir / "stdout.log").write_text("changed\n", encoding="utf-8")
        target.verify_checksums(outdir)

    def test_running_rejects_fixed_file_change(self) -> None:
        temporary, outdir = self.make_case("running")
        self.addCleanup(temporary.cleanup)
        (outdir / "run_config.json").write_text("changed\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            target.verify_checksums(outdir)

    def test_finished_state_requires_checksum_ledger(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        outdir = Path(temporary.name).resolve()
        (outdir / "status.json").write_text(
            json.dumps({"status": "partial"}), encoding="utf-8"
        )
        with self.assertRaises(SystemExit):
            target.verify_checksums(outdir)

    def test_atomic_write_leaves_no_temporary_file(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "result.json"
        target.atomic_write_text(path, "one")
        target.atomic_write_text(path, "two")
        self.assertEqual(path.read_text(encoding="utf-8"), "two")
        self.assertFalse(path.with_name(path.name + ".tmp").exists())


class FrequencyOrderTests(unittest.TestCase):
    def test_descending_grid_keeps_canonical_bounds(self) -> None:
        self.assertEqual(
            target.ordered_omegas(0.0, 0.2, 0.05, "descending"),
            [0.2, 0.15, 0.1, 0.05, 0.0],
        )

    def test_rejects_non_divisible_grid(self) -> None:
        with self.assertRaises(ValueError):
            target.ordered_omegas(0.0, 0.2, 0.03, "ascending")


if __name__ == "__main__":
    unittest.main()
