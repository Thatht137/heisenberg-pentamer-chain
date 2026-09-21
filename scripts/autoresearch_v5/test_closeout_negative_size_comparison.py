"""检查联合尺寸分析的定义和拒绝条件。"""
import copy
import shutil
import tempfile
import unittest
from pathlib import Path

import closeout_negative_size_comparison as closeout
from closeout_negative_size_comparison import (DERIVED_NAMES, dimer_rms,
                                               connected_quarter, read_csv,
                                               summarize, verify_derived_provenance)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'results/autoresearch_v5_20260914/negative_entropy_sizes_analysis_20260915'


class JointComparisonTests(unittest.TestCase):
    def test_same_class_constant_has_zero_difference(self):
        rows = [{'bond': str(b), 'correlation': str(b % 5)} for b in range(1, 40)]
        value, count = dimer_rms(rows, 40)
        self.assertEqual(value, 0)
        self.assertEqual(count, 16)
        rows.append(rows[0])
        with self.assertRaises(ValueError):
            dimer_rms(rows, 40)

    def test_connected_preserves_staggered_sign(self):
        rows = [{'bond_class': '0', 'reference_bond': '30', 'target_bond': str(b),
                 'distance_units': '3', 'distance_over_units': '.25', 'connected': '-.01'} for b in (15, 45)]
        self.assertEqual(connected_quarter(rows, 60), [.01, .01])
        rows[1]['target_bond'] = '15'
        with self.assertRaises(ValueError):
            connected_quarter(rows, 60)

    def test_complete_real_grid_and_duplicate_rejection(self):
        arrays = [read_csv(SOURCE / name) for name in ('entropy_fits.csv', 'observables.csv',
                  'bond_expectations.csv', 'connected_bonds.csv')]
        result = summarize(*arrays)
        self.assertEqual(len(result), 12)
        self.assertTrue(all(r['connected_samples'] == 4 for r in result))
        duplicate = copy.deepcopy(arrays)
        duplicate[1][-1] = duplicate[1][0]
        with self.assertRaises(ValueError):
            summarize(*duplicate)
        missing = copy.deepcopy(arrays)
        missing[0].pop()
        with self.assertRaises(ValueError):
            summarize(*missing)

    def test_derived_hash_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            analysis = Path(directory)
            records = []
            for name in DERIVED_NAMES:
                source = SOURCE / name
                target = analysis / name
                shutil.copyfile(source, target)
                records.append({'name': name, 'path': str(target.resolve()),
                                'sha256': closeout.sha256(target)})
            script = Path(closeout.__file__).resolve()
            summary = {
                'derived_outputs': records,
                'analysis_script': {'path': str(script), 'sha256': closeout.sha256(script)},
                'coverage': {'path': str((SOURCE / 'summary.json').resolve()),
                             'sha256': closeout.sha256(SOURCE / 'summary.json'),
                             'run_spec_sha256': 'test'},
                'run_spec_sha256': 'test',
            }
            verify_derived_provenance(analysis, summary)
            with (analysis / DERIVED_NAMES[0]).open('a', encoding='utf-8') as handle:
                handle.write('\n')
            with self.assertRaises(ValueError):
                verify_derived_provenance(analysis, summary)


if __name__ == '__main__':
    unittest.main()
