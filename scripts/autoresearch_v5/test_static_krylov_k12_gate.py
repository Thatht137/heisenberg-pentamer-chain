"""k12 gate、manifest 隔离与上传保护的回归测试。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
import make_static_krylov_k12_gate as gate  # noqa: E402
import static_krylov_k12_preflight as preflight  # noqa: E402


class StaticKrylovK12GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = ROOT / gate.RELEASE_REL / "server_upload_manifest.json"
        if not cls.manifest.is_file():
            raise unittest.SkipTest("先运行 make_static_krylov_k12_gate.py")

    def test_generated_release_passes_preflight(self) -> None:
        result = preflight.validate_package(
            ROOT,
            ROOT / gate.RELEASE_REL,
            ROOT / gate.RUN_REL,
            ROOT / gate.SMOKE_REL,
            "prepare",
        )
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["network_used"])
        self.assertEqual(result["settings"]["krylovdim"], 12)
        self.assertEqual(result["settings"]["nsweeps"], 64)

    def test_run_spec_and_smoke_roles_are_separate(self) -> None:
        spec = json.loads((ROOT / gate.RUN_REL / "parameter-scan.run_spec.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["cells"][0]["params"]["eigsolve_krylovdim"], 12)
        self.assertEqual(spec["settings"]["nsweeps"], 64)
        self.assertEqual(spec["settings"]["maxdim_by_L"], {"80": 1200})
        self.assertFalse(spec["settings"]["warmstart"])
        smoke = spec["provenance"]["smoke_evidence"]
        self.assertEqual(smoke["julia_version"], "1.11.5")
        self.assertEqual(smoke["remote_julia_version_required"], "1.12.3")
        self.assertTrue(smoke["not_remote_validation"])

    def test_path_isolation_rejects_absolute_and_legacy_paths(self) -> None:
        for value in (r"C:\bundle\file", "../old/file"):
            with self.subTest(value=value):
                with self.assertRaises(preflight.PreflightError):
                    preflight.safe_relative(ROOT, value, "fixture")

    def test_manifest_layout_isolated_from_v2(self) -> None:
        with self.assertRaises(preflight.PreflightError):
            preflight.validate_package(
                ROOT,
                ROOT / "results/autoresearch_v5_20260919/static_krylov_controls_release_v2",
                ROOT / gate.RUN_REL,
                ROOT / gate.SMOKE_REL,
                "prepare",
            )

    def test_future_contract_is_k12_for_parent_and_children(self) -> None:
        spec = json.loads((ROOT / gate.RUN_REL / "parameter-scan.run_spec.json").read_text(encoding="utf-8"))
        contract = spec["future_output_contract"]
        self.assertEqual(contract["parent"]["required_krylovdim"], 12)
        self.assertEqual(contract["children"]["required_krylovdim"], 12)
        self.assertEqual(contract["children"]["modes"], ["center", "ferro_j2"])
        self.assertEqual(contract["children"]["required_sweeps"], 64)

    def test_upload_script_has_fixed_confirmation_and_non_overwrite_hash_gates(self) -> None:
        text = (SCRIPT_DIR / "upload_static_krylov_k12_release_v3.ps1").read_text(encoding="utf-8")
        self.assertIn("CONFIRM_STATIC_KRYLOV_K12_RELEASE_V3", text)
        self.assertIn(".ssh\\id_ed25519", text)
        self.assertIn("static_krylov_controls_release_v3", text)
        self.assertIn("if [ -e ", text)
        self.assertIn("sha256sum ", text)
        self.assertIn("[switch]$DryRun", text)

    def test_launcher_uses_remote_julia_123_and_k12_preflight(self) -> None:
        text = (SCRIPT_DIR / "launch_static_krylov_k12_release_v3.sh").read_text(encoding="utf-8")
        self.assertIn("static_krylov_k12_preflight.py", text)
        self.assertIn("julia-1.12.3+0.x64.linux.gnu/bin/julia", text)
        self.assertIn("--expected-julia-version 1.12.3", text)
        self.assertIn("static_krylov_controls_release_v3", text)


if __name__ == "__main__":
    unittest.main()
