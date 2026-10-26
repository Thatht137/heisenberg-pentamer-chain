"""低能显示不得改变谱值或分辨率。"""

import unittest
from pathlib import Path
from unittest import mock

import matplotlib
import matplotlib.figure
import numpy as np
from matplotlib.colors import AsinhNorm, Normalize

from plot_low_energy_visibility_20261002 import low_energy_summary
from plot_dsf_screenshot_style import draw
from plot_fullq_documented_20261002 import make_norm, render_run


class VisibilityTests(unittest.TestCase):
    def test_shared_color_scale_preserves_zero_and_is_monotone(self):
        norm = AsinhNorm(linear_width=0.02, vmin=0, vmax=6)
        values = np.array([0, 0.001, 0.02, 0.1, 1, 3, 6])
        self.assertEqual(norm(0), 0)
        self.assertEqual(norm(6), 1)
        self.assertTrue(np.all(np.diff(norm(values)) > 0))
        np.testing.assert_allclose(norm.inverse(norm(values)), values, atol=1e-12)

    def test_weight_uses_original_frequency_points_without_mutation(self):
        spectrum = np.full((5, 9), 0.1)
        original = spectrum.copy()
        run = {"omega": np.linspace(0, 4, 9), "spectrum": spectrum,
               "metadata": {"window_fwhm": 0.093}}
        selected, summary = low_energy_summary(run)
        self.assertEqual(np.count_nonzero(selected), 2)
        self.assertAlmostEqual(summary["low_weight_fraction_of_sampled_range"], 0.125)
        self.assertFalse(summary["spectral_resolution_improved"])
        np.testing.assert_array_equal(spectrum, original)

    def test_documented_scales_are_calibrated_and_invertible(self):
        values = np.array([0, 0.001, 0.02, 0.1, 1, 3, 6])
        for mode in ("linear", "asinh"):
            norm = make_norm(mode, 0.1)
            self.assertEqual(norm(0), 0)
            self.assertEqual(norm(6), 1)
            self.assertTrue(np.all(np.diff(norm(values)) > 0))
            np.testing.assert_allclose(norm.inverse(norm(values)), values, atol=1e-12)
        self.assertIsInstance(make_norm("linear", 0.1), Normalize)
        for width in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                make_norm("asinh", width)

    def test_documented_pair_uses_same_unmodified_grid(self):
        spectrum = np.linspace(0, 5, 405).reshape(5, 81)
        original = spectrum.copy()
        run = {"spectrum": spectrum, "q": np.linspace(0, 2 * np.pi, 5),
               "omega": np.linspace(0, 4, 81),
               "metadata": {"alpha": 0.5, "beta": 0.5, "tmax": 60}}
        with mock.patch("plot_fullq_documented_20261002.draw") as draw_mock:
            figures = render_run(run, Path("unused"), 0.1)
        self.assertEqual(draw_mock.call_count, 2)
        self.assertEqual([figure["mode"] for figure in figures], ["linear", "asinh"])
        for call in draw_mock.call_args_list:
            self.assertIs(call.args[0], spectrum)
            self.assertEqual(call.args[5:7], (4, 6))
            self.assertTrue(call.kwargs["colorbar"])
            self.assertNotIn("scale_label", call.kwargs)
            self.assertEqual(call.kwargs["norm"].vmin, 0)
            self.assertEqual(call.kwargs["norm"].vmax, 6)
        np.testing.assert_array_equal(spectrum, original)
        run["spectrum"] = np.full_like(spectrum, 7)
        with self.assertRaises(ValueError):
            render_run(run, Path("unused"), 0.1)

    def test_calibrated_full_plot_has_no_parameter_footer(self):
        spectrum = np.linspace(0, 5, 405).reshape(5, 81)
        with matplotlib.rc_context({"font.family": "Arial", "mathtext.fontset": "stixsans"}):
            with mock.patch.object(matplotlib.figure.Figure, "savefig", autospec=True) as save:
                draw(spectrum, np.linspace(0, 2 * np.pi, 5), np.linspace(0, 4, 81),
                     0.5, 0.5, 4, 6, Path("unused"), colorbar=True,
                     colorbar_ticks=list(range(7)))
        fig = save.call_args.args[0]
        self.assertEqual(len(fig.axes), 2)
        np.testing.assert_array_equal(fig.axes[1].get_yticks(), np.arange(7))
        self.assertEqual(fig.texts, [])
        self.assertEqual(len(fig.axes[0].texts), 1)

    def test_undersampled_window_rejected(self):
        run = {"omega": np.array([0, 1, 2]), "spectrum": np.ones((3, 3)),
               "metadata": {"window_fwhm": 0.093}}
        with self.assertRaises(ValueError):
            low_energy_summary(run)

    def test_full_plot_keeps_full_grid_and_linear_energy_axis(self):
        q = np.linspace(0, 2 * np.pi, 5)
        omega = np.linspace(0, 4, 81)
        spectrum = np.linspace(0, 5, 405).reshape(5, 81)
        original = spectrum.copy()
        norm = AsinhNorm(linear_width=0.02, vmin=0, vmax=6)
        with matplotlib.rc_context({"font.family": "Arial", "mathtext.fontset": "stixsans"}):
            with mock.patch.object(matplotlib.figure.Figure, "savefig", autospec=True) as save:
                draw(spectrum, q, omega, 0.5, 0.5, 4, 6, Path("unused"), norm=norm)
        self.assertEqual(save.call_count, 3)
        fig = save.call_args.args[0]
        self.assertEqual(len(fig.axes), 1)
        self.assertEqual(fig.axes[0].get_ylim(), (0, 4))
        self.assertEqual(fig.axes[0].get_yscale(), "linear")
        self.assertEqual(fig.texts, [])
        mesh = fig.axes[0].collections[0]
        self.assertIs(mesh.norm, norm)
        np.testing.assert_array_equal(np.asarray(mesh.get_array()).reshape(81, 5), spectrum.T)
        np.testing.assert_array_equal(spectrum, original)


if __name__ == "__main__":
    unittest.main()
