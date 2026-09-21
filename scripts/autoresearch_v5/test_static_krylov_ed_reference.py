import unittest

import numpy as np

try:
    from . import static_krylov_ed_reference as oracle
except ImportError:
    import static_krylov_ed_reference as oracle


class StaticKrylovEdReferenceTests(unittest.TestCase):
    def test_two_spin_known_spectrum(self):
        np.testing.assert_allclose(
            oracle.two_spin_spectrum(),
            [-0.75, 0.25, 0.25, 0.25],
            atol=1e-12,
        )

    def test_sector_dimensions_and_bit_kron_roundtrip(self):
        basis0, _ = oracle.sector_basis(10, 5)
        basis1, _ = oracle.sector_basis(10, 6)
        self.assertEqual(len(basis0), 252)
        self.assertEqual(len(basis1), 210)
        for state in range(1 << oracle.N_SITES):
            index = oracle.bit_to_kron_index(state)
            self.assertEqual(oracle.kron_index_to_bit(index), state)

    def test_full_and_sector_hermiticity(self):
        full = oracle.build_full_hamiltonian(-0.1, 0.25)
        self.assertEqual(full.shape, (1024, 1024))
        self.assertEqual(full.dtype, np.dtype(np.float64))
        self.assertLess(full.nbytes, 10_000_000)
        np.testing.assert_allclose(full, full.T, atol=1e-12)
        for alpha in oracle.DEFAULT_ALPHAS:
            for target_sz in oracle.TARGET_SZS:
                matrix = oracle.sector_hamiltonian(alpha, 0.25, target_sz)
                np.testing.assert_allclose(matrix, matrix.T, atol=1e-12)

    def test_bit_sector_matches_independent_kron_projection(self):
        for alpha in oracle.DEFAULT_ALPHAS:
            full = oracle.build_full_hamiltonian(alpha, oracle.DEFAULT_BETA)
            for target_sz in oracle.TARGET_SZS:
                n_up = 5 + target_sz
                basis, direct = oracle.build_sector_hamiltonian(
                    alpha,
                    oracle.DEFAULT_BETA,
                    n_up,
                )
                projected = oracle.project_full_hamiltonian(full, basis)
                np.testing.assert_allclose(projected, direct, atol=2e-12)

    def test_lowest_state_residual_norm_and_total_sz(self):
        for row in oracle.reference_rows():
            result = oracle.solve_sector(row["alpha"], row["beta"], row["target_sz"])
            self.assertEqual(result["dimension"], row["dimension"])
            self.assertLessEqual(result["residual_norm"], 1e-10)
            self.assertAlmostEqual(result["norm"], 1.0, places=12)
            self.assertAlmostEqual(result["total_sz"], row["target_sz"], places=12)

    def test_reference_energy_rows(self):
        rows = oracle.reference_rows()
        self.assertEqual(len(rows), 4)
        self.assertEqual(
            {(row["alpha"], row["target_sz"]) for row in rows},
            {(-0.1, 0), (-0.1, 1), (-0.175, 0), (-0.175, 1)},
        )

    def test_invalid_inputs_rejected(self):
        bad_values = (True, np.bool_(False), np.nan, np.inf, -np.inf, "0.1")
        for bad in bad_values:
            with self.subTest(parameter="alpha", value=bad):
                with self.assertRaises(ValueError):
                    oracle.pentamer_bonds(bad, 0.25)
            with self.subTest(parameter="beta", value=bad):
                with self.assertRaises(ValueError):
                    oracle.pentamer_bonds(-0.1, bad)
        with self.assertRaises(ValueError):
            oracle.build_sector_hamiltonian(-0.1, 0.25, True)
        with self.assertRaises(ValueError):
            oracle.build_sector_hamiltonian(-0.1, 0.25, 5.0)
        with self.assertRaises(ValueError):
            oracle.sector_hamiltonian(-0.1, 0.25, True)
        with self.assertRaises(ValueError):
            oracle.sector_hamiltonian(-0.1, 0.25, 2)
        with self.assertRaises(ValueError):
            oracle.build_full_hamiltonian(-0.1, 0.25, n_sites=9)
        with self.assertRaises(ValueError):
            oracle.bit_to_kron_index(True)
        with self.assertRaises(ValueError):
            oracle.bit_to_kron_index(1 << 10)

    def test_lowest_state_rejects_bad_matrices(self):
        with self.assertRaises(ValueError):
            oracle.lowest_state(np.ones((2, 3)))
        with self.assertRaises(ValueError):
            oracle.lowest_state(np.array([[0.0, 1.0], [0.0, 0.0]]))
        with self.assertRaises(ValueError):
            oracle.lowest_state(np.array([[np.nan]]))


if __name__ == "__main__":
    unittest.main()
