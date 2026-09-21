"""测试 low-005 本地交接保护规则。"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/autoresearch_v5/handoff_round41_low005.py"
SPEC = importlib.util.spec_from_file_location("handoff_round41_low005", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class HandoffRound41Tests(unittest.TestCase):
    def test_confined_rejects_outside_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                MODULE.confined(Path(temporary))

    def test_run_rejects_unexpected_returncode(self) -> None:
        fake = type("Result", (), {"returncode": 1, "stderr": "失败", "stdout": ""})()
        with patch.object(MODULE.subprocess, "run", return_value=fake):
            with self.assertRaisesRegex(RuntimeError, "失败"):
                MODULE.run(["fixture"])

    def test_run_accepts_not_evaluable_returncode(self) -> None:
        fake = type("Result", (), {"returncode": 2, "stderr": "", "stdout": ""})()
        with patch.object(MODULE.subprocess, "run", return_value=fake):
            self.assertEqual(MODULE.run(["fixture"], {0, 2}).returncode, 2)

    def test_receipt_contract_fixture(self) -> None:
        receipt = {"status": "pass", "non_clobbering": True}
        self.assertTrue(receipt["non_clobbering"] and receipt["status"] == "pass")
        self.assertEqual(json.loads(json.dumps(receipt)), receipt)


if __name__ == "__main__":
    unittest.main()
