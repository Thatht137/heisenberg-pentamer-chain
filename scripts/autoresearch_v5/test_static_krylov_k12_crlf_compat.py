import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "scripts/autoresearch_v5/launch_static_krylov_k12_release_v3.sh"
COMPAT = ROOT / "scripts/autoresearch_v5/launch_static_krylov_k12_release_v3_crlf_compat.sh"


class CompatLauncherTests(unittest.TestCase):
    def test_original_hash_is_pinned(self):
        digest = hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()
        text = COMPAT.read_text(encoding="utf-8")
        self.assertIn(digest, text)

    def test_crlf_hash_list_is_normalized(self):
        text = COMPAT.read_text(encoding="utf-8")
        self.assertIn("sha256sum -c <(tr -d '\\r'", text)
        self.assertIn("sub(/\\r$/", text)

    def test_physics_contract_is_unchanged(self):
        text = COMPAT.read_text(encoding="utf-8")
        self.assertIn("--timeout 7200", text)
        self.assertIn("JULIA_NUM_THREADS=8", text)
        self.assertIn("--expected-julia-version 1.12.3", text)


if __name__ == "__main__":
    unittest.main()
