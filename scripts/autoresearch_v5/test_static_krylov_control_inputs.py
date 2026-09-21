"""提取模块的小型 fixture 测试；fixture 明确不是物理结果。"""

from __future__ import annotations

import csv
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from static_krylov_control_inputs import (  # noqa: E402
    KNOWN_LEGACY_DEFAULT3,
    KRYLOV_SOURCE,
    _select_connected_quarter_rows,
    _krylov_value,
    read_csv_rows,
    sha256,
    validate_entropy_rows,
    verify_recorded_hash,
)
from closeout_negative_size_comparison import connected_quarter  # noqa: E402


class StaticKrylovInputTests(unittest.TestCase):
    def _csv(self, directory: Path, name: str, text: str) -> Path:
        path = directory / name
        path.write_text(text, encoding="utf-8", newline="")
        return path

    def test_missing_measurement_file_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(ValueError):
                read_csv_rows(Path(raw) / "missing.csv", ("bond",))

    def test_duplicate_entropy_bond_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self._csv(raw := Path(raw), "entropy.csv", "bond,bond_class,log_chord,entropy\n1,1,0.1,0.2\n1,1,0.2,0.3\n")
            rows = read_csv_rows(path, ("bond", "bond_class", "log_chord", "entropy"))
            with self.assertRaises(ValueError):
                validate_entropy_rows(rows, 3, "synthetic")

    def test_missing_entropy_field_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self._csv(Path(raw), "entropy.csv", "bond,bond_class,log_chord\n1,1,0.1\n")
            with self.assertRaises(ValueError):
                read_csv_rows(path, ("bond", "bond_class", "log_chord", "entropy"))

    def test_hash_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self._csv(Path(raw), "source.txt", "synthetic\n")
            recorded = sha256(path)
            path.write_text("tampered\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                verify_recorded_hash(path, recorded)

    def test_explicit8_mixed_with_legacy3_rejected(self):
        legacy = {"provenance": {"code_sha256": {KRYLOV_SOURCE: next(iter(KNOWN_LEGACY_DEFAULT3))}}}
        explicit = {"settings": {"eigsolve_krylovdim": 8}}
        with self.assertRaises(ValueError):
            _krylov_value([explicit, legacy], "synthetic")

    def test_unknown_missing_krylov_rejected(self):
        unknown = {"provenance": {"code_sha256": {KRYLOV_SOURCE: "unknown"}}}
        with self.assertRaises(ValueError):
            _krylov_value([unknown], "synthetic")

    def test_bool_explicit_krylov_rejected(self):
        with self.assertRaises(ValueError):
            _krylov_value([{"settings": {"eigsolve_krylovdim": True}}], "synthetic")

    def test_connected_quarter_rows_keep_raw_coordinates_after_prefix(self):
        rows = [
            {"bond_class": 0, "reference_bond": 40, "target_bond": 5, "distance_units": 1, "connected": 0.5},
            {"bond_class": 0, "reference_bond": 40, "target_bond": 10, "distance_units": 2, "connected": 0.6},
            {"bond_class": 0, "reference_bond": 40, "target_bond": 20, "distance_units": 4, "distance_over_units": 0.25, "connected": 2.8991064554562129e-6},
            {"bond_class": 0, "reference_bond": 40, "target_bond": 60, "distance_units": 4, "distance_over_units": 0.25, "connected": 2.8988285881714759e-6},
        ]
        selected = _select_connected_quarter_rows(rows, 80)
        self.assertEqual([(row["reference_bond"], row["target_bond"]) for row in selected], [(40, 20), (40, 60)])
        self.assertEqual([row["connected"] for row in selected], [rows[2]["connected"], rows[3]["connected"]])
        self.assertEqual(connected_quarter(rows, 80), [rows[2]["connected"], rows[3]["connected"]])

    def test_explicit3_and_legacy3_are_consistent(self):
        legacy = {"provenance": {"code_sha256": {KRYLOV_SOURCE: next(iter(KNOWN_LEGACY_DEFAULT3))}}}
        explicit = {"settings": {"eigsolve_krylovdim": 3}}
        result = _krylov_value([explicit, legacy], "synthetic")
        self.assertEqual(result["value"], 3)
        self.assertEqual(result["inference"], "per_manifest_consistent")


if __name__ == "__main__":
    unittest.main()
