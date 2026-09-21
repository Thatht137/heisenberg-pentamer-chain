"""测试 round43 Fig.8 的分支和 checksum 合同。"""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.autoresearch_v5 import plot_fig8_round43_branch as target


class Fig8Round43BranchTests(unittest.TestCase):
    def test_production_requires_agreement(self) -> None:
        self.assertEqual(
            target.select_mode({"status": "production_ready", "production_ready": True, "tag": "Agreement"}),
            "production",
        )
        with self.assertRaises(ValueError):
            target.select_mode({"status": "production_ready", "production_ready": True, "tag": "NotEvaluable"})

    def test_bounded_accepts_only_nonproduction_tags(self) -> None:
        self.assertEqual(
            target.select_mode({"status": "bounded", "production_ready": False, "tag": "NotEvaluable"}),
            "bounded",
        )
        with self.assertRaises(ValueError):
            target.select_mode({"status": "bounded", "production_ready": False, "tag": "Agreement"})

    def test_checksum_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence.json"
            evidence.write_text("{}\n", encoding="utf-8")
            digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
            (root / "checksums.sha256").write_text(f"{digest}  evidence.json\n", encoding="utf-8")
            target.verify_checksums(root)
            evidence.write_text('{"changed": true}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                target.verify_checksums(root)


if __name__ == "__main__":
    unittest.main()
