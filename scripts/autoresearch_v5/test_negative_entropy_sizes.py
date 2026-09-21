"""检验多尺寸纠缠分析的数值与输入保护。"""
import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np

from analyze_negative_entropy_sizes import analyze_profile, check_coverage_grid


class EntropySizesTests(unittest.TestCase):
    def test_coverage_grid_rejects_duplicate_or_missing_point(self):
        rows = [{'params': {'alpha': a, 'beta': .25, 'L': length}}
                for a in (-.175, -.150, -.125, -.100) for length in (40, 60, 80)]
        check_coverage_grid({'results': rows})
        with self.assertRaises(ValueError):
            check_coverage_grid({'results': rows[:-1]})
        with self.assertRaises(ValueError):
            check_coverage_grid({'results': rows[:-1] + [rows[0]]})

    def test_n_units_is_filled_and_exact(self):
        rows = [{'params': {'alpha': a, 'beta': .25, 'L': length}}
                for a in (-.175, -.150, -.125, -.100) for length in (40, 60, 80)]
        check_coverage_grid({'results': rows})
        self.assertEqual({row['params']['n_units'] for row in rows}, {8, 12, 16})

        for bad_l, bad_units in ((40.9, 8), (40, 8.9), (40, True)):
            bad = [{'params': {'alpha': a, 'beta': .25, 'L': length}}
                   for a in (-.175, -.150, -.125, -.100) for length in (40, 60, 80)]
            bad[0]['params']['L'] = bad_l
            bad[0]['params']['n_units'] = bad_units
            with self.assertRaises(ValueError):
                check_coverage_grid({'results': bad})

    def test_validation_params_must_match_normalized_params(self):
        rows = [{'params': {'alpha': a, 'beta': .25, 'L': length}}
                for a in (-.175, -.150, -.125, -.100) for length in (40, 60, 80)]
        rows[0]['validation'] = {'params': {'alpha': -.175, 'beta': .25, 'L': 40, 'n_units': 7}}
        with self.assertRaises(ValueError):
            check_coverage_grid({'results': rows})

    def profile(self, path, length, omit=False, bad_chord=False):
        with path.open('w', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['bond', 'log_chord', 'entropy'])
            for bond in range(1, length - int(omit)):
                x = np.log(2 * length / np.pi * np.sin(np.pi * bond / length))
                writer.writerow([bond, x + int(bad_chord), x / 6 + .1 * (bond % 10)])

    def test_all_sizes_recover_known_slope(self):
        with tempfile.TemporaryDirectory() as directory:
            for length in (40, 60, 80):
                path = Path(directory) / 'profile.csv'
                self.profile(path, length)
                rows = analyze_profile(path, length)
                self.assertEqual(len(rows), 8)
                for row in rows:
                    if row['period'] == 10:
                        self.assertAlmostEqual(row['c_eff'], 1.0, places=10)

    def test_missing_cut_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.csv'
            self.profile(path, 40, omit=True)
            with self.assertRaises(ValueError):
                analyze_profile(path, 40)

    def test_wrong_chord_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.csv'
            self.profile(path, 40, bad_chord=True)
            with self.assertRaises(ValueError):
                analyze_profile(path, 40)


if __name__ == '__main__':
    unittest.main()
