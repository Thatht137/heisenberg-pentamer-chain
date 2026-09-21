import tempfile
import unittest
from pathlib import Path

import numpy as np

import validate_near_zero_alpha_oracle as oracle


class NearZeroAlphaOracleTests(unittest.TestCase):
    def test_sector_dimensions(self):
        self.assertEqual(len(oracle.sector_basis(4)), 70)
        self.assertEqual(len(oracle.sector_basis(5)), 56)
        self.assertEqual(len(oracle.sector_basis(3)), 56)

    def test_bit_sector_matches_full_kron(self):
        full = oracle.build_full_hamiltonian(-0.01, 0.25)
        for nup in (3, 4, 5):
            basis, sector = oracle.build_sector_hamiltonian(-0.01, 0.25, nup)
            self.assertLess(
                oracle._compare_point_constructions(full, basis, sector),
                1e-12,
            )

    def test_hermiticity(self):
        full = oracle.build_full_hamiltonian(0.02, 0.5)
        self.assertLess(oracle._matrix_error(full - full.conj().T), 1e-12)
        for nup in (3, 4, 5):
            _, sector = oracle.build_sector_hamiltonian(0.02, 0.5, nup)
            self.assertLess(oracle._matrix_error(sector - sector.T), 1e-12)

    def test_two_spin_benchmark(self):
        result = oracle.two_spin_benchmark()
        self.assertLess(result["max_abs_error"], 1e-12)
        np.testing.assert_allclose(
            result["eigenvalues"],
            [-0.75, 0.25, 0.25, 0.25],
            atol=1e-12,
        )

    def test_three_spin_projection(self):
        result = oracle.three_spin_projection_validation()
        self.assertEqual(result["ground_degeneracy"], 2)
        self.assertLess(result["max_coefficient_error"], 1e-10)
        self.assertLess(result["max_projection_matrix_residual"], 1e-10)

    def test_alpha_zero_limit_and_multiplicity(self):
        row = oracle.evaluate_point(0.0, 0.25)
        checks = row["alpha0_checks"]
        self.assertLess(checks["energy_error"], 1e-10)
        self.assertEqual(checks["full_ground_degeneracy"], 4)
        self.assertEqual(checks["sector_ground_degeneracies"], {"3": 1, "4": 2, "5": 1})
        self.assertLess(checks["s2_multiplet_error"], 1e-8)

    def test_nonzero_su2_low_energy_multiplets(self):
        row = oracle.evaluate_point(-0.01, 0.25)
        self.assertGreater(row["gap_sz1_minus_sz0"], 0.0)
        self.assertAlmostEqual(row["total_sz_sz0_ground"], 0.0, places=8)
        self.assertAlmostEqual(row["total_sz_sz1_ground"], 1.0, places=8)
        self.assertAlmostEqual(row["total_sz_sz_minus1_ground"], -1.0, places=8)
        self.assertAlmostEqual(row["s2_sz0_ground"], 0.0, places=8)
        self.assertAlmostEqual(row["s2_sz1_ground"], 2.0, places=8)
        self.assertAlmostEqual(row["s2_sz0_triplet_match"], 2.0, places=8)
        self.assertLess(row["sz0_triplet_energy_match_error"], 1e-10)

    def test_positive_and_negative_alpha_rows(self):
        negative = oracle.evaluate_point(-0.005, 0.1)
        positive = oracle.evaluate_point(0.005, 0.1)
        self.assertGreater(negative["gap_over_alpha2"], 0.0)
        self.assertGreater(positive["gap_over_alpha2"], 0.0)
        self.assertTrue(negative["asymptotic_gate_applicable"])
        self.assertTrue(positive["asymptotic_gate_applicable"])

    def test_invalid_parameters_rejected(self):
        with self.assertRaises(ValueError):
            oracle.build_sector_hamiltonian(0.0, 0.0, 4)
        with self.assertRaises(ValueError):
            oracle.build_sector_hamiltonian(0.0, 0.25, True)
        with self.assertRaises(ValueError):
            oracle.build_sector_hamiltonian(0.0, 0.25, 4.0)
        with self.assertRaises(ValueError):
            oracle.build_sector_hamiltonian(float("nan"), 0.25, 4)
        with self.assertRaises(ValueError):
            oracle.build_sector_hamiltonian(False, 0.25, 4)
        with self.assertRaises(ValueError):
            oracle.build_sector_hamiltonian(0.0, True, 4)

    def test_failed_validation_gate_never_reports_pass(self):
        self.assertNotEqual(oracle._status_from_gates(False, True), "pass")
        self.assertNotEqual(oracle._status_from_gates(True, False), "pass")
        self.assertEqual(oracle._status_from_gates(True, True), "pass")

    def test_nonempty_output_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "oracle"
            output.mkdir()
            (output / "keep.txt").write_text("保留", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                oracle._prepare_output_dir(output)


if __name__ == "__main__":
    unittest.main()
