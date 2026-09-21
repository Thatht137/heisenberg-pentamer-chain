"""纯合成、非物理数据测试；不生成真实对照报告。"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_static_krylov_controls import compare_records  # noqa: E402


BASE_METADATA = {
    "alpha": -0.1,
    "beta": 0.25,
    "L": 80,
    "nsweeps": 64,
    "maxdim": 1200,
    "cutoff": 1e-11,
    "eigsolve_krylovdim": 3,
}
CANDIDATE_METADATA = {**BASE_METADATA, "eigsolve_krylovdim": 8}


def records(values=(1.0, 2.0)):
    return [
        {"alpha": -0.1, "beta": 0.25, "L": 80, "start": "center",
         "observable": "entropy", "index": i, "value": value}
        for i, value in enumerate(values)
    ]


class CompareStaticKrylovControlsTests(unittest.TestCase):
    def test_pair_and_signed_deltas(self):
        result = compare_records(records((1.0, 2.0)), records((1.5, 1.0)), BASE_METADATA, CANDIDATE_METADATA)
        self.assertEqual(result["status"], "audit_only")
        self.assertEqual(result["comparison_count"], 2)
        self.assertAlmostEqual(result["records"][0]["signed_delta"], 0.5)
        self.assertAlmostEqual(result["records"][1]["abs_delta"], 1.0)
        self.assertNotIn("phase", result)
        self.assertNotIn("converged", result)

    def test_symmetric_relative_delta_and_double_zero(self):
        result = compare_records(records((0.0, 2.0)), records((0.0, 1.0)), BASE_METADATA, CANDIDATE_METADATA)
        self.assertIsNone(result["records"][0]["symmetric_relative_delta"])
        self.assertAlmostEqual(result["records"][1]["symmetric_relative_delta"], -2.0 / 3.0)

    def test_duplicate_key_rejected(self):
        duplicate = records((1.0, 2.0)) + [records((3.0,))[0]]
        with self.assertRaises(ValueError):
            compare_records(duplicate, records((1.0, 2.0)), BASE_METADATA, CANDIDATE_METADATA)

    def test_missing_candidate_rejected(self):
        with self.assertRaises(ValueError):
            compare_records(records((1.0, 2.0)), records((1.0,)), BASE_METADATA, CANDIDATE_METADATA)

    def test_nonfinite_and_bool_rejected(self):
        bad = records((1.0, 2.0))
        bad[0]["value"] = math.nan
        with self.assertRaises(ValueError):
            compare_records(bad, records((1.0, 2.0)), BASE_METADATA, CANDIDATE_METADATA)
        bad = records((True, 2.0))
        with self.assertRaises(ValueError):
            compare_records(bad, records((1.0, 2.0)), BASE_METADATA, CANDIDATE_METADATA)

    def test_metadata_drift_rejected(self):
        candidate = {**CANDIDATE_METADATA, "cutoff": 1e-10}
        with self.assertRaises(ValueError):
            compare_records(records(), records(), BASE_METADATA, candidate)

    def test_only_three_to_eight_is_allowed(self):
        wrong = {**CANDIDATE_METADATA, "eigsolve_krylovdim": 7}
        with self.assertRaises(ValueError):
            compare_records(records(), records(), BASE_METADATA, wrong)

    def test_same_values_have_zero_deltas(self):
        result = compare_records(records((4.0, 4.0)), records((4.0, 4.0)), BASE_METADATA, CANDIDATE_METADATA)
        for row in result["records"]:
            self.assertEqual(row["signed_delta"], 0.0)
            self.assertEqual(row["abs_delta"], 0.0)
            self.assertEqual(row["symmetric_relative_delta"], 0.0)

    def test_empty_records_rejected(self):
        with self.assertRaises(ValueError):
            compare_records([], [], BASE_METADATA, CANDIDATE_METADATA)


if __name__ == "__main__":
    unittest.main()
