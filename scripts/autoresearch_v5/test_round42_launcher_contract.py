"""测试 round42 启动器的静态保护契约。"""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/autoresearch_v5/launch_round42_qpi_cv_low000_20260805.sh"


class Round42LauncherContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_scope_and_single_point(self) -> None:
        for token in ("--alpha 0.23", "--beta 0.5", "--omega-min 0.0", "--omega-max 0.0"):
            self.assertIn(token, self.text)
        self.assertNotIn("--alpha -", self.text)

    def test_residual_gate_and_low005_trigger(self) -> None:
        self.assertIn("residual <= 1e-5", self.text)
        self.assertIn("--max-cv-residual 1e-5", self.text)
        self.assertIn("status[\"accepted\"] is True", self.text)

    def test_resource_and_offline_guards(self) -> None:
        for token in ("pgrep -x julia", "JULIA_PKG_OFFLINE=true", "--threads 4", "nice -n 15"):
            self.assertIn(token, self.text)

    def test_non_clobber_guard(self) -> None:
        self.assertIn("拒绝覆盖已有 cell", self.text)
        self.assertIn("拒绝覆盖 launcher 文件", self.text)


if __name__ == "__main__":
    unittest.main()
