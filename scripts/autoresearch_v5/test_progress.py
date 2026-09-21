#!/usr/bin/env python3
"""验证 heartbeat 的原子写入和终态信息。"""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from progress import ProgressWriter


class ProgressWriterTests(unittest.TestCase):
    def test_writes_running_and_terminal_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outdir = Path(temporary)
            progress = ProgressWriter(outdir, {"job_type": "test", "phase": "work"}, interval_seconds=0.01)
            progress.start()
            time.sleep(0.03)
            running = json.loads((outdir / "progress.json").read_text(encoding="utf-8"))
            self.assertEqual(running["status"], "running")
            progress.finish(status="success", returncode=0, phase="finished")
            terminal = json.loads((outdir / "progress.json").read_text(encoding="utf-8"))
            self.assertEqual(terminal["status"], "success")
            self.assertEqual(terminal["returncode"], 0)
            self.assertFalse((outdir / "progress.json.tmp").exists())

    def test_probe_failure_is_reported_without_interrupting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            progress = ProgressWriter(Path(temporary), {"job_type": "test"}, probe=lambda: 1 / 0)
            progress.start()
            progress.finish(status="failed", returncode=1)
            payload = json.loads((Path(temporary) / "progress.json").read_text(encoding="utf-8"))
            self.assertIn("probe_error", payload)


if __name__ == "__main__":
    unittest.main()
