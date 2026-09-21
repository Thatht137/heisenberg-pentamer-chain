"""兼容 launcher 的本地回归测试。"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "scripts/autoresearch_v5/launch_static_krylov_controls_release_v2.sh"
COMPAT = ROOT / "scripts/autoresearch_v5/launch_static_krylov_controls_release_v2_crlf_compat.sh"
RELEASE = ROOT / "results/autoresearch_v5_20260919/static_krylov_controls_release_v2"
MANIFEST = RELEASE / "server_upload_manifest.json"
EVIDENCE = ROOT / "results/autoresearch_v5_20260919/offline_numpy1264_cp310/dependency_evidence.json"
WHEEL = ROOT / "results/autoresearch_v5_20260919/offline_numpy1264_cp310/numpy-1.26.4-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
EXPECTED_ORIGINAL_SHA = "e4fd4fe02be8581b1f02478513bf0d793a4a7168043790e3912358a9946e7bab"
EXPECTED_MANIFEST_SHA = "e0dedb571cb265817f537de63e2bd107369c23fcb12326099c008ef55392efb4"
EXPECTED_EVIDENCE_SHA = "588c3c2792fa4a0c6310bb680270eeb319b6d5459bbb96aaba49fe4448177d34"


class StaticKrylovCrlfCompatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sha256sum = shutil.which("sha256sum") or shutil.which("sha256sum.exe")
        cls.bash = None
        cls.bash_backend = None
        candidates = []
        for name in ("bash", "bash.exe"):
            candidate = shutil.which(name)
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        for candidate in candidates:
            path_text = str(candidate).lower()
            try:
                version = subprocess.run(
                    [candidate, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            version_text = (version.stdout + version.stderr).lower()
            if "gnu bash" in version_text and "cygwin" in version_text:
                cls.bash = candidate
                cls.bash_backend = "local_gnu_bash_cygwin"
                break
            if "gnu bash" in version_text and ("mingw" in version_text or "msys" in version_text):
                cls.bash = candidate
                cls.bash_backend = "local_gnu_bash_msys"
                break

    def test_crlf_normalization_passes_and_tamper_is_rejected(self):
        if not self.sha256sum:
            self.skipTest("缺少 sha256sum")
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp)
            files = {"alpha.txt": b"alpha\n", "nested/beta.txt": b"beta\r\n"}
            for relative, content in files.items():
                target = fixture / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            lines = "".join(
                f"{hashlib.sha256(content).hexdigest()}  {relative}\n"
                for relative, content in files.items()
            ).encode()
            crlf = lines.replace(b"\n", b"\r\n")
            self.assertEqual(crlf.count(b"\r"), 2)
            normalized = crlf.replace(b"\r\n", b"\n")
            with tempfile.NamedTemporaryFile(dir=fixture, suffix=".sha256", delete=False) as handle:
                good = Path(handle.name)
            good.write_bytes(normalized)
            passed = subprocess.run(
                [self.sha256sum, "-c", str(good)],
                cwd=fixture,
                capture_output=True,
                text=True,
            )
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            tampered = bytearray(normalized)
            tampered[0] = ord("0") if tampered[0] != ord("0") else ord("1")
            bad = fixture / "tampered.sha256"
            bad.write_bytes(bytes(tampered))
            rejected = subprocess.run(
                [self.sha256sum, "-c", str(bad)],
                cwd=fixture,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(rejected.returncode, 0)

    def test_compat_delta_is_format_only_and_guards_original_hash(self):
        original_text = ORIGINAL.read_text(encoding="utf-8")
        compat_text = COMPAT.read_text(encoding="utf-8")
        original_sha = hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()
        self.assertEqual(original_sha, EXPECTED_ORIGINAL_SHA)
        self.assertIn(f'ORIGINAL_LAUNCHER_SHA256="{EXPECTED_ORIGINAL_SHA}"', compat_text)
        self.assertIn("sha256sum -c <(tr -d '\\r' < \"$HASHES\")", compat_text)
        self.assertEqual(compat_text.count("sub(/\\r$/, \"\", $2)"), 2)

        normalized_lines = []
        for line in compat_text.splitlines():
            if line.startswith("ORIGINAL_LAUNCHER="):
                continue
            if line.startswith("ORIGINAL_LAUNCHER_SHA256="):
                continue
            if line in {
                '[[ -f "$ORIGINAL_LAUNCHER" ]] || exit 2',
                '[[ "$(sha256sum "$ORIGINAL_LAUNCHER" | awk \'{print $1}\')" == "$ORIGINAL_LAUNCHER_SHA256" ]] || exit 2',
            }:
                continue
            line = line.replace(
                '(cd "$BUNDLE_ROOT" && sha256sum -c <(tr -d \'\\r\' < "$HASHES")) >/dev/null',
                '(cd "$BUNDLE_ROOT" && sha256sum -c "$HASHES") >/dev/null',
            )
            line = line.replace(
                'STANDARD_SHA="$(awk \'{ sub(/\\r$/, "", $2); if ($2 == "docs/negative_alpha_practical_convergence_standard_20260829.md") print $1 }\' "$HASHES")"',
                'STANDARD_SHA="$(awk \'$2 == "docs/negative_alpha_practical_convergence_standard_20260829.md" {print $1}\' "$HASHES")"',
            )
            line = line.replace(
                'MANIFEST_SHA="$(awk \'{ sub(/\\r$/, "", $2); if ($2 == "Manifest.toml") print $1 }\' "$HASHES")"',
                'MANIFEST_SHA="$(awk \'$2 == "Manifest.toml" {print $1}\' "$HASHES")"',
            )
            normalized_lines.append(line)
        self.assertEqual("\n".join(normalized_lines), original_text.rstrip("\n"))

    def test_manifest_and_cleanup_evidence_are_unchanged(self):
        manifest_bytes = MANIFEST.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        self.assertEqual(hashlib.sha256(manifest_bytes).hexdigest(), EXPECTED_MANIFEST_SHA)
        self.assertEqual(len(manifest["files"]), 72)
        self.assertEqual(manifest["offline_numpy_wheel_sha256"], "ffa75af20b44f8dba823498024771d5ac50620e6915abac414251bd971b4529f")
        self.assertFalse(WHEEL.exists(), "清理后的 wheel 不应被重新下载")
        self.assertTrue(EVIDENCE.is_file())
        self.assertEqual(hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(), EXPECTED_EVIDENCE_SHA)

    def test_local_gnu_bash_cygwin_process_substitution_and_awk_reject_tamper(self):
        if not self.sha256sum:
            self.skipTest("缺少 sha256sum")
        if not self.bash:
            self.skipTest("缺少本地 GNU Bash/Cygwin")
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp)
            standard = fixture / "docs/negative_alpha_practical_convergence_standard_20260829.md"
            manifest = fixture / "Manifest.toml"
            standard.parent.mkdir(parents=True, exist_ok=True)
            standard.write_bytes(b"standard-fixture\n")
            manifest.write_bytes(b"manifest-fixture\n")
            standard_sha = hashlib.sha256(standard.read_bytes()).hexdigest()
            manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
            lines = (
                f"{standard_sha}  docs/negative_alpha_practical_convergence_standard_20260829.md\n"
                f"{manifest_sha}  Manifest.toml\n"
            ).encode()
            script = f'''set -eu
HASHES=source_hashes.sha256
(cd "$PWD" && sha256sum -c <(tr -d '\\r' < "$HASHES")) >/dev/null
STANDARD_SHA="$(awk '{{ sub(/\\r$/, "", $2); if ($2 == "docs/negative_alpha_practical_convergence_standard_20260829.md") print $1 }}' "$HASHES")"
MANIFEST_SHA="$(awk '{{ sub(/\\r$/, "", $2); if ($2 == "Manifest.toml") print $1 }}' "$HASHES")"
test "$STANDARD_SHA" = "{standard_sha}"
test "$MANIFEST_SHA" = "{manifest_sha}"
printf 'STANDARD_SHA=%s\\nMANIFEST_SHA=%s\\n' "$STANDARD_SHA" "$MANIFEST_SHA"
'''

            def run_fixture(hash_bytes: bytes) -> subprocess.CompletedProcess[bytes]:
                (fixture / "source_hashes.sha256").write_bytes(hash_bytes)
                return subprocess.run(
                    [self.bash, "-s"],
                    cwd=fixture,
                    input=script.encode("utf-8"),
                    capture_output=True,
                    timeout=15,
                )

            for hash_bytes in (lines, lines.replace(b"\n", b"\r\n")):
                passed = run_fixture(hash_bytes)
                output = (passed.stdout + passed.stderr).decode("utf-8", errors="replace")
                self.assertEqual(passed.returncode, 0, output)
                self.assertIn(f"STANDARD_SHA={standard_sha}", output)
                self.assertIn(f"MANIFEST_SHA={manifest_sha}", output)

            tampered_digest = bytearray(lines.replace(b"\n", b"\r\n"))
            tampered_digest[0] = ord("0") if tampered_digest[0] != ord("0") else ord("1")
            rejected_digest = run_fixture(bytes(tampered_digest))
            self.assertNotEqual(rejected_digest.returncode, 0)

            run_fixture(lines.replace(b"\n", b"\r\n"))
            manifest.write_bytes(b"manifest-tampered\n")
            rejected_content = run_fixture(lines.replace(b"\n", b"\r\n"))
            self.assertNotEqual(rejected_content.returncode, 0)

    def test_local_gnu_bash_cygwin_n_accepts_compat_launcher(self):
        if not self.bash:
            self.skipTest("缺少本地 GNU Bash/Cygwin")
        checked = subprocess.run(
            [self.bash, "-n"],
            cwd=ROOT,
            input=COMPAT.read_bytes(),
            capture_output=True,
            timeout=15,
        )
        output = (checked.stdout + checked.stderr).decode("utf-8", errors="replace")
        self.assertEqual(checked.returncode, 0, output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
