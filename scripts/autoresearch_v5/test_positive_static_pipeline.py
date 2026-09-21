#!/usr/bin/env python3
"""测试正区静态生产管线的规格、安全边界与 oracle。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260730" / "round8_positive_static_production"
RUN_MULTI = ROOT / "results" / "autoresearch_v5_20260731" / "round10_positive_static_multistart_production"
ANALYZER_PATH = ROOT / "scripts" / "autoresearch_v5" / "analyze_positive_static_multistart.py"
ANALYZER_SPEC = importlib.util.spec_from_file_location("positive_multistart_analyzer", ANALYZER_PATH)
assert ANALYZER_SPEC is not None and ANALYZER_SPEC.loader is not None
ANALYZER = importlib.util.module_from_spec(ANALYZER_SPEC)
ANALYZER_SPEC.loader.exec_module(ANALYZER)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_checksums(directory: Path) -> bool:
    for line in (directory / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        if sha256(directory / name) != expected:
            return False
    return True


class PositiveStaticPipelineTests(unittest.TestCase):
    def test_run_spec_has_27_positive_cells(self) -> None:
        run_spec = json.loads((RUN / "run_spec.json").read_text(encoding="utf-8"))
        paths = json.loads((RUN / "paths.json").read_text(encoding="utf-8"))["paths"]
        path_index = {row["path_id"]: row for row in paths}
        self.assertEqual(len(run_spec["cells"]), 27)
        self.assertEqual(len({row["cell_id"] for row in run_spec["cells"]}), 27)
        self.assertEqual({row["params"]["L"] for row in run_spec["cells"]}, {40, 60, 80})
        self.assertTrue(all(path_index[row["params"]["path_id"]]["alpha"] >= 0 for row in run_spec["cells"]))
        self.assertTrue(all(path_index[row["params"]["path_id"]]["beta"] >= 0 for row in run_spec["cells"]))

    def test_negative_alpha_is_hard_blocked(self) -> None:
        command = [
            sys.executable,
            "-X", "utf8",
            str(ROOT / "scripts" / "autoresearch_v5" / "run_positive_static_cell.py"),
            "--cell-id", "blocked", "--outdir", str(RUN / "blocked"),
            "--path-id", "blocked", "--group", "0", "--role", "ridge",
            "--alpha", "-0.1", "--beta", "0.5", "--n-units", "2",
            "--maxdim", "10", "--nsweeps", "2", "--cutoff", "1e-8",
            "--standard-sha256", "x", "--expected-manifest-sha256", "x",
            "--expected-julia-version", "1.11.5", "--dry-run",
        ]
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("alpha<0", result.stderr)

    def test_pilot_selects_three_l40_ridges(self) -> None:
        command = [
            sys.executable,
            "-X", "utf8",
            str(ROOT / "scripts" / "autoresearch_v5" / "run_positive_static_scan.py"),
            "--run-spec", str(RUN / "run_spec.json"),
            "--paths", str(RUN / "paths.json"),
            "--mode", "pilot",
            "--dry-run",
        ]
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True
        )
        lines = result.stdout.splitlines()
        rows = [json.loads(line) for line in lines[:-1]]
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["L"] == 40 and row["path"]["role"] == "ridge" for row in rows))
        self.assertEqual({row["path"]["group"] for row in rows}, {1, 2, 3})
        self.assertEqual(lines[-1], "DRY_RUN_OK mode=pilot cells=3")

    def test_multistart_run_spec_has_36_positive_cells(self) -> None:
        run_spec = json.loads((RUN_MULTI / "run_spec.json").read_text(encoding="utf-8"))
        paths = json.loads((RUN_MULTI / "paths.json").read_text(encoding="utf-8"))
        variants = {row["variant_id"]: row for row in paths["variants"]}
        self.assertEqual(len(variants), 12)
        self.assertEqual(len(run_spec["cells"]), 36)
        self.assertEqual(len({row["cell_id"] for row in run_spec["cells"]}), 36)
        self.assertEqual({row["params"]["L"] for row in run_spec["cells"]}, {40, 60, 80})
        domain = [row for row in variants.values() if row["init_mode"] == "domain"]
        self.assertEqual(len(domain), 3)
        self.assertTrue(all(row["role"] == "ridge" for row in domain))
        self.assertTrue(all(row["alpha"] >= 0 and row["beta"] >= 0 for row in variants.values()))

    def test_multistart_pilot_selects_six_l40_ridges(self) -> None:
        command = [
            sys.executable,
            "-X", "utf8",
            str(ROOT / "scripts" / "autoresearch_v5" / "run_positive_static_scan.py"),
            "--run-spec", str(RUN_MULTI / "run_spec.json"),
            "--paths", str(RUN_MULTI / "paths.json"),
            "--mode", "pilot",
            "--dry-run",
        ]
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True
        )
        lines = result.stdout.splitlines()
        rows = [json.loads(line) for line in lines[:-1]]
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row["L"] == 40 and row["path"]["role"] == "ridge" for row in rows))
        self.assertEqual({row["init_mode"] for row in rows}, {"center", "domain"})
        self.assertEqual(lines[-1], "DRY_RUN_OK mode=pilot cells=6")

    def test_multistart_comparison_checks_all_observables(self) -> None:
        budgets = {
            "energy_density_abs_max": 1e-10,
            "spin_gap_abs_max": 1e-8,
            "string_profile_abs_max": 1e-5,
            "bond_correlation_abs_max": 1e-5,
            "schmidt_probability_l1_max": 1e-4,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            center = root / "center"
            domain = root / "domain"
            center.mkdir()
            domain.mkdir()
            for directory, shift in ((center, 0.0), (domain, 1e-11)):
                (directory / "metrics.csv").write_text(
                    "metric,value\nL,10\nenergy_sz0,-2.5\nspin_gap," + str(0.1 + shift) + "\n",
                    encoding="utf-8",
                )
                (directory / "string_profile.csv").write_text(
                    "distance_units,O_mean\n1," + str(0.2 + shift) + "\n",
                    encoding="utf-8",
                )
                (directory / "bond_correlations.csv").write_text(
                    "bond,correlation\n1," + str(-0.3 + shift) + "\n",
                    encoding="utf-8",
                )
                (directory / "schmidt_spectrum.csv").write_text(
                    "bond,probability\n5," + str(0.7 + shift) + "\n5," + str(0.3 - shift) + "\n",
                    encoding="utf-8",
                )
            accepted = ANALYZER.compare_cell_dirs(center, domain, budgets)
            self.assertTrue(accepted["accepted"])
            (domain / "bond_correlations.csv").write_text(
                "bond,correlation\n1,-0.29\n", encoding="utf-8"
            )
            rejected = ANALYZER.compare_cell_dirs(center, domain, budgets)
            self.assertFalse(rejected["accepted"])
            self.assertFalse(rejected["checks"]["bond_correlation_abs"])

    def test_multistart_oracle_and_hashes(self) -> None:
        domain = json.loads(
            (RUN_MULTI / "local_oracle_L10_domain_tight" / "manifest.json").read_text(encoding="utf-8")
        )
        comparison = json.loads(
            (RUN_MULTI / "local_oracle_multistart_crosscheck" / "multistart-check.json").read_text(encoding="utf-8")
        )
        self.assertEqual(domain["status"], "success")
        self.assertTrue(domain["accepted"])
        self.assertEqual(comparison["tag"], "Agreement")
        self.assertTrue(comparison["accepted"])
        self.assertTrue(all(comparison["checks"].values()))
        self.assertTrue(verify_checksums(RUN_MULTI / "local_oracle_L10_domain_tight"))
        self.assertTrue(verify_checksums(RUN_MULTI / "local_oracle_multistart_crosscheck"))

    def test_output_escape_is_hard_blocked(self) -> None:
        command = [
            sys.executable,
            "-X", "utf8",
            str(ROOT / "scripts" / "autoresearch_v5" / "run_positive_static_cell.py"),
            "--cell-id", "blocked", "--outdir", str(ROOT.parent / "blocked"),
            "--path-id", "blocked", "--group", "0", "--role", "ridge",
            "--alpha", "0.1", "--beta", "0.5", "--n-units", "2",
            "--maxdim", "10", "--nsweeps", "2", "--cutoff", "1e-8",
            "--standard-sha256", "x", "--expected-manifest-sha256", "x",
            "--expected-julia-version", "1.11.5", "--dry-run",
        ]
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不在 results 下", result.stderr)

    def test_acceptance_separates_loose_and_tight_oracles(self) -> None:
        loose = json.loads((RUN / "local_smoke_L10_v3" / "manifest.json").read_text(encoding="utf-8"))
        tight = json.loads((RUN / "local_oracle_L10_tight" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(loose["status"], "success")
        self.assertFalse(loose["accepted"])
        self.assertEqual(tight["status"], "success")
        self.assertTrue(tight["accepted"])
        self.assertTrue(all(tight["acceptance"].values()))

    def test_ed_crosscheck_and_hashes(self) -> None:
        comparison = json.loads((RUN / "local_oracle_crosscheck" / "cross-method-check.json").read_text(encoding="utf-8"))
        self.assertEqual(comparison["tag"], "Agreement")
        self.assertTrue(all(comparison["checks"].values()))
        self.assertLess(comparison["absolute_differences"]["spin_gap"], 2e-9)
        self.assertTrue(verify_checksums(RUN / "local_oracle_L10_tight"))
        self.assertTrue(verify_checksums(RUN / "local_oracle_crosscheck"))


if __name__ == "__main__":
    unittest.main()
