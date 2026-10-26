"""按显式图源和已知索引试算投稿材料包，默认不写归档。"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATIC = "figures/submission_20261002_static"
SPECTRA = "results/fullq_dsf_20261001"
CONTROL = "results/submission_20261002/dsf_controls"
OLD_STEMS = (
    "paper_fig1_model_local_multiplets_20260804",
    "paper_fig4_entanglement_spectrum_20260804",
    "paper_fig5_effective_chain_selection_rules_20260804",
)
CODE = (
    "scripts/submission_20261002/local_projection_checks.py",
    "scripts/submission_20261002/plot_controlled_static.py",
    "scripts/submission_20261002/plot_projection_validation.py",
    "scripts/submission_20261002/audit_dsf_controls.py",
    "scripts/submission_20261002/audit_spectral_window.py",
    "scripts/submission_20261002/audit_provenance.py",
    "scripts/submission_20261002/test_audit_dsf_controls.py",
    "scripts/submission_20261002/run_dsf_controls.py",
    "scripts/submission_20261002/check_cv_residual.jl",
    "scripts/submission_20261002/package_submission.py",
    "scripts/compute_fullq_dsf.jl", "scripts/compute_spin_gap_20261001.jl",
    "scripts/check_fullq_dsf_ed.py", "scripts/audit_fullq_dsf.py",
    "scripts/plot_low_energy_visibility_20261002.py", "scripts/plot_dsf_screenshot_style.py",
    "scripts/autoresearch_v5/plot_paper_static_figures_20260804.py",
    "scripts/autoresearch_v3/project_doublet.py",
    "scripts/autoresearch_v3/analyze_entanglement_scaling.py",
    "scripts/autoresearch_v4/analyze_positive_local_spectral_channels.py",
    "scripts/autoresearch_v5/analyze_negative_phase_independent_observables.py",
    "scripts/autoresearch_v5/validate_near_zero_alpha_oracle.py",
    "scripts/autoresearch_v5/test_near_zero_alpha_oracle.py",
    "scripts/autoresearch_v5/report_near_zero_alpha_oracle.py",
)
ALLOWED_SUFFIXES = {".csv", ".json", ".toml", ".md", ".py", ".jl", ".ps1", ".tex", ".bib",
                    ".pdf", ".png", ".svg", ".sha256", ".txt", ".yaml", ".yml"}
PRIVATE_PARTS = {".git", ".ssh", ".aws", ".codex", ".agents", ".venv", "__pycache__"}
PRIVATE_NAMES = re.compile(r"(?:^\.env(?:\.|$)|secret|credential|password|id_rsa|id_ed25519|known_hosts|authorized_keys|\.pem$|\.key$|\.pfx$)", re.I)
PRIVATE_FIELDS = {"password", "token", "access_token", "api_key", "secret", "ssh_host", "ssh_user",
                  "username", "hostname", "remote_root", "host_id", "connection_id", "host", "user",
                  "ssh_alias", "ssh_key", "env", "environment", "command", "argv", "remote_path", "remote_dir"}
ABS_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|/(?:home|Users|root|tmp|mnt)/)[^\s\"'<>\)\],;]*")
SECRET_CONTENT = re.compile(r"(?m)^-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{30,}\b")
PATH_FIELDS = {"artifact", "path", "source", "source_path", "source_file", "source_csv", "source_json",
               "manifest_path", "run_spec_path", "validation_basis"}
HASH_MAPS = {"source_sha256", "code_sha256", "source_data", "input_sha256"}
RECOVERY = {
    "results/autoresearch_v5_20260914/negative_entropy_sizes_fetch_20260915_1445/coverage.json":
        "f4196d4e1ba7644454c301bdc66a891fccdba05e1b3b6828c5a05e2fd55a5a0b",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exclusion(path: Path) -> str | None:
    if any(part.lower() in PRIVATE_PARTS for part in path.parts) or PRIVATE_NAMES.search(path.name):
        return "private-name policy"
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        return "unsupported or excluded extension (including wavefunctions/logs)"
    if path.name.lower() in {"process.json", "status.json"}:
        return "operational process/status record"
    return None


class Inventory:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.files = {"manuscript": {}, "source_data": {}}
        self.missing, self.excluded, self.warnings, self.hash_mismatches = [], [], [], []
        self.recovered = []
        self.recovery_map = {}
        audit = self.root / "results/submission_20261002/provenance/audit.json"
        if audit.is_file():
            recovery = json.loads(audit.read_text(encoding="utf-8-sig"))
            rows = recovery.get("k12_recovered", []) + recovery.get("k12_original_raw_run", {}).get("files", [])
            for row in rows:
                if row.get("verified") or row.get("historical_terminal_record_verified"):
                    self.recovery_map[row["original_path"]] = (row["restored_path"], row["sha256"])
        self.queue = deque()
        self.python_index = {}
        for path in (self.root / "scripts").rglob("*.py"):
            self.python_index.setdefault(path.stem, []).append(path)
        self.selected_parameters = set()
        table = self.root / STATIC / "fig8_points.csv"
        if table.is_file():
            with table.open(encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    for length in (60, 80):
                        self.selected_parameters.add((float(row["alpha"]), float(row["beta"]), length))

    def relative(self, value: str, parent: Path | None = None) -> Path | None:
        normal = value.replace("\\", "/")
        if re.search(r"[\w.-]+@[^/]+:|^ssh://|\x00", normal):
            return None
        root_string = self.root.as_posix()
        if normal.lower().startswith(root_string.lower() + "/"):
            normal = normal[len(root_string) + 1:]
        elif re.match(r"^[A-Za-z]:/|^/|^https?://", normal):
            return None
        parts = Path(normal)
        if parts.parts and parts.parts[0] not in {"paper_prb", "figures", "results", "scripts", "src", "data", "docs", "Project.toml", "Manifest.toml"}:
            if parent is not None:
                parts = parent / parts
        try:
            resolved = (self.root / parts).resolve()
            return resolved.relative_to(self.root)
        except (ValueError, OSError):
            return None

    def add(self, value: str | Path, package: str, reason: str, expected: str | None = None,
            parent: Path | None = None, optional: bool = False):
        relative = self.relative(str(value), parent)
        if relative is None:
            self.excluded.append({"referenced_by": reason, "reason": "external or escaping path omitted"})
            return
        name = relative.as_posix()
        block = exclusion(relative)
        if block:
            self.excluded.append({"path": name, "reason": block, "referenced_by": reason})
            return
        path = self.root / relative
        if not path.is_file() and name in self.recovery_map:
            restored, digest = self.recovery_map[name]
            restored_relative = self.relative(restored)
            if restored_relative is not None:
                candidate = self.root / restored_relative
                if candidate.is_file() and sha(candidate.read_bytes()) == digest and expected in (None, digest):
                    path = candidate
                    self.recovered.append({"recovered_path": restored_relative.as_posix(),
                                           "package_path": name, "historical_sha256": digest,
                                           "original_path_overwritten": False})
        if not path.is_file() and name in RECOVERY:
            archived = self.root / "_archive/submission_cleanup_20260923" / relative
            if archived.is_file() and sha(archived.read_bytes()) == RECOVERY[name] and expected == RECOVERY[name]:
                path = archived
                self.recovered.append({"archive_path": archived.relative_to(self.root).as_posix(),
                                       "package_path": name, "historical_sha256": expected,
                                       "original_path_overwritten": False})
        if not path.is_file():
            if not optional:
                self.missing.append({"path": name, "referenced_by": reason, "kind": "file"})
            return
        if path.stat().st_size > 30 * 1024 * 1024:
            self.excluded.append({"path": name, "reason": "file exceeds 30 MiB scoped-package limit"})
            return
        raw = path.read_bytes()
        current = sha(raw)
        if expected and re.fullmatch(r"[0-9a-f]{64}", str(expected)) and current != expected:
            self.hash_mismatches.append({"path": name, "referenced_by": reason,
                                         "historical_sha256": expected, "current_sha256": current})
        if name in self.files[package]:
            return
        self.files[package][name] = {"source_path": path.relative_to(self.root).as_posix(),
                                    "source_sha256": current, "source_bytes": len(raw), "reason": reason}
        if package == "source_data":
            self.queue.append(relative)

    def glob(self, directory: str, patterns: tuple[str, ...], reason: str):
        for pattern in patterns:
            for path in sorted((self.root / directory).glob(pattern)):
                if path.is_file():
                    self.add(path, "source_data", reason)

    def manuscript(self):
        for name in ("README.md", "build.ps1", "references.bib", "build/manuscript.pdf",
                     "cover_letter.txt", "FIGURE_SOURCES.md", "VALIDATION_20261004.md"):
            self.add(f"paper_prb/{name}", "manuscript", "manuscript delivery")
        pending, seen = [Path("paper_prb/main.tex")], set()
        while pending:
            relative = pending.pop()
            if relative in seen:
                continue
            seen.add(relative)
            self.add(relative, "manuscript", "active TeX input")
            path = self.physical_path(relative.as_posix())
            if not path.is_file():
                continue
            text = re.sub(r"(?m)(?<!\\)%.*$", "", path.read_text(encoding="utf-8-sig"))
            for token in re.findall(r"\\(?:input|include)\{([^{}]+)\}", text):
                target = self.relative("paper_prb/" + token + ("" if Path(token).suffix else ".tex"))
                if target and target.parts[0] == "paper_prb":
                    pending.append(target)
                else:
                    self.warnings.append({"path": relative.as_posix(), "reason": "unsupported TeX input"})
            for token in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}", text):
                candidate = Path("paper_prb/figures") / token
                if not candidate.suffix:
                    candidate = next((candidate.with_suffix(ext) for ext in (".pdf", ".png")
                                      if (self.root / candidate.with_suffix(ext)).is_file()), candidate.with_suffix(".pdf"))
                self.add(candidate, "manuscript", f"graphics in {relative.as_posix()}")
        pdf = self.root / "paper_prb/build/manuscript.pdf"
        if pdf.is_file() and any((self.root / n).stat().st_mtime > pdf.stat().st_mtime
                                for n in self.files["manuscript"] if n != "paper_prb/build/manuscript.pdf"
                                and Path(n).suffix in {".tex", ".bib", ".png", ".pdf"}):
            self.warnings.append({"path": "paper_prb/build/manuscript.pdf", "reason": "PDF predates an active input; rebuild required"})

    def source_roots(self):
        for name in ("Project.toml", "Manifest.toml") + CODE:
            self.add(name, "source_data", "explicit environment/code allowlist")
        self.glob("src", ("*.jl",), "model source module")
        for stem in OLD_STEMS:
            self.add(f"figures/{stem}.sources.json", "source_data", "used historical figure provenance")
            for suffix in ("pdf", "png", "svg"):
                self.add(f"figures/{stem}.{suffix}", "source_data", "used historical figure export")
        self.glob(STATIC, ("fig8_*", "fig9_*", "projection_*", "fig_projection_*", "source_*", "*.md", "qa.json"),
                  "controlled static/projection figure bundle")
        clean = "figures/fullq_visibility_clean_20261002"
        self.glob(clean, ("Sqw_*_full_asinh.pdf", "Sqw_*_full_asinh.png", "Sqw_*_full_asinh.svg",
                          "README.md", "visibility_qa.json"), "selected full-spectrum figures")
        for run in ("L40_positive", "L40_negative_local", "L40_positive_check", "L40_negative_check_local",
                    "tebd_check_L10_positive", "tebd_check_L10_negative", "ed_L10"):
            self.glob(f"{SPECTRA}/{run}", ("*.csv", "run_metadata.toml", "ed_crosscheck.json"), "spectral data and same-ground checks")
        self.add(f"{SPECTRA}/spin_gap_L40/gap_results.toml", "source_data", "finite-chain sector-gap table")
        self.add(f"{SPECTRA}/source_final_sha256.json", "source_data", "historical full-q code hashes")
        for name in ("qa.json", "report.md"):
            self.add(f"figures/fullq_dsf_20261001/{name}", "source_data", "full-q numerical audit")
        self.glob("results/submission_20261002/local_projection", ("*.csv", "*.json"), "two-cell ED benchmark")
        self.add(f"{CONTROL}/plan.json", "source_data", "frozen independent-controls plan")
        for run in ("positive_chi", "positive_dt", "negative_chi", "negative_dt"):
            directory = self.root / CONTROL / run
            if (directory / "result.jld2").is_file():
                self.glob(f"{CONTROL}/{run}", ("*.csv", "run_metadata.toml"), "completed independent control")
            else:
                self.missing.append({"path": f"{CONTROL}/{run}", "kind": "pending-completed-CSV-export", "referenced_by": "independent controls"})
        self.glob("results/submission_20261002/dsf_audit", ("audit.json", "README.md"), "independent-controls audit")
        audit = self.root / "results/submission_20261002/dsf_audit/audit.json"
        if audit.is_file() and json.loads(audit.read_text(encoding="utf-8-sig")).get("status") != "pass":
            self.warnings.append({"path": audit.relative_to(self.root).as_posix(), "reason": "Control audit is not complete and passing; refresh before final packaging"})
        self.glob("results/submission_20261002/window_audit",
                  ("summary.json", "all_q.csv", "selected_q.csv", "appendix_table.tex", "README.md"),
                  "signed frequency-window accounting")
        self.glob("results/autoresearch_v5_20260919/near_zero_alpha_oracle_v2",
                  ("oracle_points.csv", "summary.json", "spec.json", "checksums.sha256"),
                  "eight-spin near-zero exchange oracle")
        for name in ("docs/fullq_dsf_protocol_20261001.md", "docs/package_source_plan_20261004.md",
                     "docs/submission_provenance_audit_20261004.md"):
            self.add(name, "source_data", "protocol and package scope")
        self.glob("results/autoresearch_v5_20260913/negative_phase_independent_audit_v6",
                  ("negative_quartet_projection_scan.csv",), "negative local-spin projection scan")
        self.add("results/autoresearch_v5_20260919/closeout_stage1_joint_v2/summary.json", "source_data", "historical entropy size provenance")
        self.glob("results/submission_20261002/provenance", ("cv_*/verification.toml",), "explicit checkpoint-residual checks without saved states")
        self.add("results/submission_20261002/provenance/audit.json", "source_data", "verified archive recovery ledger")
        for original, (_, digest) in self.recovery_map.items():
            self.add(original, "source_data", "selected recovered k12 terminal and numerical records", digest)

    def records(self, value, parent: Path, reason: str):
        if isinstance(value, list):
            for item in value:
                self.records(item, parent, reason)
        elif isinstance(value, dict):
            if all(isinstance(value.get(k), str) for k in ("root", "path", "sha256")):
                source_root = self.relative(value["root"])
                if source_root is not None:
                    self.add(value["path"], "source_data", reason, value["sha256"], source_root)
                else:
                    self.excluded.append({"referenced_by": reason, "reason": "external checksum root omitted"})
                return
            params = value.get("params", {})
            if all(k in params for k in ("alpha", "beta", "L")) and "artifact" in value:
                point = (float(params["alpha"]), float(params["beta"]), int(params["L"]))
                if "round44_phase_diagram" in reason and point not in self.selected_parameters:
                    return
            for key, item in value.items():
                if key in PATH_FIELDS and isinstance(item, str):
                    if "/" in item or "\\" in item or Path(item).suffix in ALLOWED_SUFFIXES:
                        self.add(item, "source_data", reason, value.get("sha256"), parent)
                elif key in HASH_MAPS and isinstance(item, dict):
                    for path, expected in item.items():
                        if isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected):
                            source_parent = Path("results/submission_20261002/local_projection") if reason.endswith("/projection_qa.json") else parent
                            self.add(path, "source_data", reason, expected, source_parent)
                        else:
                            self.records(expected, parent, reason)
                elif key == "child_manifests" and isinstance(item, list):
                    for path in item:
                        if isinstance(path, str):
                            self.add(path, "source_data", reason, parent=parent)
                elif key not in {"outputs", "exports", "environment", "command", "env"}:
                    self.records(item, parent, reason)

    def dependencies(self):
        seen = set()
        while self.queue:
            relative = self.queue.popleft()
            if relative in seen:
                continue
            seen.add(relative)
            if len(seen) > 3000:
                raise ValueError("Scoped dependency limit exceeded")
            path = self.physical_path(relative.as_posix())
            if path.suffix == ".json":
                try:
                    payload = json.loads(path.read_text(encoding="utf-8-sig"))
                    self.records(payload, relative.parent, relative.as_posix())
                    if path.name == "manifest.json" and payload.get("settings", {}).get("method") == "finite_dmrg":
                        self.glob(relative.parent.as_posix(), ("metrics.csv", "structure_factor_fullq.csv", "entropy_profile_full.csv",
                                                              "sweep_history_sz0.csv", "sweep_history_sz1.csv", "checksums.sha256"),
                                  f"known finite-DMRG measurement schema in {relative.as_posix()}")
                except (ValueError, TypeError) as error:
                    self.warnings.append({"path": relative.as_posix(), "reason": f"Unparsed JSON schema: {type(error).__name__}"})
            elif path.suffix == ".csv":
                with path.open(encoding="utf-8-sig", newline="") as stream:
                    for row in csv.DictReader(stream):
                        self.records({k: v for k, v in row.items() if k in PATH_FIELDS}, relative.parent, relative.as_posix())
            elif path.suffix == ".py":
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
                except SyntaxError:
                    self.warnings.append({"path": relative.as_posix(), "reason": "Python dependency parse failed"})
                    continue
                for node in ast.walk(tree):
                    modules = [node.module] if isinstance(node, ast.ImportFrom) else [n.name for n in node.names] if isinstance(node, ast.Import) else []
                    for module in filter(None, modules):
                        name = module.split(".")[0]
                        candidates = self.python_index.get(name, [])
                        local = [p for p in candidates if p.parent == path.parent]
                        if len(local or candidates) == 1:
                            self.add((local or candidates)[0], "source_data", f"Python import in {relative.as_posix()}")
                        elif candidates:
                            self.warnings.append({"path": relative.as_posix(), "reason": f"Ambiguous local import: {name}"})

    def portable_text(self, text: str) -> tuple[str, bool]:
        root = str(self.root)
        for prefix in sorted({root + "\\", root.replace("\\", "\\\\") + "\\\\", self.root.as_posix() + "/"}, key=len, reverse=True):
            text = text.replace(prefix, "")
        changed = False
        if ABS_PATH.search(text):
            text = ABS_PATH.sub("[EXTERNAL_PATH_OMITTED]", text)
            changed = True
        text = re.sub(r"[\w.-]+@(?:\d{1,3}\.){3}\d{1,3}", "[SSH_ENDPOINT_OMITTED]", text)
        return text, changed

    def physical_path(self, relative: str) -> Path:
        record = self.files["source_data"].get(relative) or self.files["manuscript"].get(relative)
        return self.root / (record["source_path"] if record else relative)

    def portable(self, relative: str) -> tuple[bytes, list[str]]:
        path = self.physical_path(relative)
        raw = path.read_bytes()
        if path.suffix.lower() in {".pdf", ".png"}:
            return raw, []
        text = raw.decode("utf-8-sig")
        if SECRET_CONTENT.search(text):
            raise ValueError(f"Credential-like content rejected: {relative}")
        def clean(value):
            if isinstance(value, str):
                return self.portable_text(value)[0]
            if isinstance(value, list):
                return [clean(v) for v in value]
            if isinstance(value, dict):
                return {self.portable_text(str(k))[0]: clean(v) for k, v in value.items() if k.lower() not in PRIVATE_FIELDS}
            return value
        actions = []
        if path.suffix == ".json":
            original = json.loads(text)
            sanitized = clean(original)
            if sanitized != original:
                actions.append("project-relative paths and private/external metadata removed")
                text = json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n"
        else:
            text, external = self.portable_text(text)
            if external:
                actions.append("external path literals removed; local runtime configuration may be needed")
        if text.encode("utf-8") != raw and not actions:
            actions.append("project-root prefix removed or UTF-8 BOM normalized")
        if ABS_PATH.search(text):
            raise ValueError(f"Absolute local path remained: {relative}")
        return text.encode("utf-8"), actions

    def report(self):
        errors = []
        for package, files in self.files.items():
            for name, metadata in files.items():
                try:
                    data, actions = self.portable(name)
                    metadata.update(archive_sha256=sha(data), archive_bytes=len(data), transformations=actions)
                except (ValueError, UnicodeError) as error:
                    errors.append({"path": name, "reason": str(error)})
        syntax = self.syntax_checks(errors)
        def unique(rows):
            return list({json.dumps(row, sort_keys=True): row for row in rows}.values())
        return {"schema_version": 1, "mode": "dry-run", "files": self.files,
                "counts": {k: len(v) for k, v in self.files.items()},
                "source_bytes": {k: sum(m["source_bytes"] for m in v.values()) for k, v in self.files.items()},
                "missing_dependencies": unique(self.missing), "excluded_dependencies": unique(self.excluded),
                "historical_hash_mismatches": unique(self.hash_mismatches), "warnings": unique(self.warnings),
                "verified_archive_recovery": unique(self.recovered),
                "content_errors": errors, "full_reproducibility_claim": False,
                "portable_code_syntax": syntax,
                "wavefunctions_included": False, "public_deposit": False, "license_selected": False,
                "source_archive_contract": "Selected figure-source tables, correlations, provenance snapshots, code and environments; not a complete state archive"}

    def syntax_checks(self, errors):
        counts = {"python": 0, "julia": 0}
        julia_records = []
        for name in self.files["source_data"]:
            if Path(name).suffix not in {".py", ".jl"}:
                continue
            try:
                data, _ = self.portable(name)
                if Path(name).suffix == ".py":
                    compile(data, name, "exec")
                    counts["python"] += 1
                else:
                    julia_records.extend((name, data.decode("utf-8")))
            except (ValueError, UnicodeError, SyntaxError) as error:
                errors.append({"path": name, "reason": f"Portable code syntax: {type(error).__name__}: {error}"})
        if not julia_records:
            return {"status": "pass" if not errors else "fail", "checked_files": counts, "execution_tested": False}
        julia = shutil.which("julia")
        if julia is None:
            self.warnings.append({"reason": "Julia unavailable: portable Julia syntax unverified"})
            return {"status": "partial", "checked_files": counts, "execution_tested": False}
        # 只解析归档副本，不载入模块或执行计算。
        parser = """function checkall()
items = split(read(stdin, String), '\\0'); failed = false
for i in 1:2:length(items)
    name, text = items[i], items[i+1]
    try
        position = firstindex(text)
        while position <= lastindex(text)
            _, position = Meta.parse(text, position; raise=true)
        end
        println("OK\\t", name)
    catch err
        failed = true
        println("FAIL\\t", name, "\\t", sprint(showerror, err))
    end
end
exit(failed ? 1 : 0)
end
checkall()"""
        try:
            run = subprocess.run([julia, "--startup-file=no", "--history-file=no", "-e", parser],
                                 input="\0".join(julia_records), capture_output=True,
                                 encoding="utf-8", timeout=60, check=False)
            counts["julia"] = sum(line.startswith("OK\t") for line in run.stdout.splitlines())
            if run.returncode or counts["julia"] != len(julia_records) // 2:
                errors.append({"reason": "Portable Julia syntax failed", "details": self.portable_text(run.stdout + run.stderr)[0]})
        except (OSError, subprocess.TimeoutExpired) as error:
            self.warnings.append({"reason": f"Julia syntax check unavailable: {type(error).__name__}"})
        return {"status": "pass" if not errors and counts["julia"] == len(julia_records) // 2 else "fail",
                "checked_files": counts, "execution_tested": False}


def package_readme(package: str) -> str:
    if package == "manuscript":
        return "# Manuscript package\n\nBuild paper_prb/main.tex using paper_prb/build.ps1 or pdflatex/bibtex. Only active TeX inputs and referenced figure assets are included. Author, funding, license and public-deposit decisions remain with the authors.\n"
    return """# Selected source data

Paths retain the project-relative layout. MANIFEST.json records original and
archive SHA256 values and every portable-copy transformation. Numerical source
values are not adjusted. Absolute project prefixes are removed; external local
paths and private metadata are omitted. Original files are never modified.

This is not a complete wavefunction archive or a claim that all historical
calculations are independently reproducible. JLD2 states/checkpoints, execution
logs, credentials, machine profiles and unused manuscript figures are excluded.
PACKAGING_REPORT.json lists missing dependencies and historical hash changes.
Historical checksum fields refer to pre-sanitization files; use MANIFEST.json
for this archive's bytes. Some runners need local Julia executable configuration.
No license, public repository, DOI or author information is fabricated here.

Python package versions are recorded in PYTHON_ENVIRONMENT.json; Julia uses
Project.toml and Manifest.toml. Relevant plotting entry points are
scripts/submission_20261002/plot_controlled_static.py and
scripts/submission_20261002/plot_projection_validation.py. Selected full spectra
use scripts/plot_low_energy_visibility_20261002.py --full. Do not run the legacy
all-five-figures entry point: only its draw_fig1, draw_fig4 and draw_fig5 functions
are relevant, called after style() and loading reference12.load_rows(). Portable
Python and Julia sources receive syntax-only checks, recorded in the report.
All historical plot and simulation entry points have NOT been execution-tested
from the portable archive; local path/runtime adjustments may still be required.

The same-ground numerical audit needs deliberately omitted seed states to
repeat exact seed-hash gates. Its archived report and raw CSVs remain inspectable;
this source package does not claim that seed-state audit is self-contained.
"""


def execute(inventory: Inventory, report: dict, output: Path, allow_incomplete: bool):
    output = output.resolve()
    output.relative_to(inventory.root)
    if output.exists():
        raise ValueError("Output directory already exists; choose a new path, no files are deleted")
    if report["content_errors"]:
        raise ValueError("Content privacy/encoding gate failed")
    if not allow_incomplete and (report["missing_dependencies"] or report["warnings"]):
        raise ValueError("Unresolved dependencies or portability warnings; review before using --allow-incomplete")
    output.mkdir(parents=True)
    report["mode"] = "executed"
    for package, files in inventory.files.items():
        stage = output / package
        stage.mkdir()
        for name, metadata in files.items():
            raw = inventory.physical_path(name).read_bytes()
            if sha(raw) != metadata["source_sha256"]:
                raise ValueError(f"Input changed after planning: {name}")
            data, _ = inventory.portable(name)
            if sha(data) != metadata["archive_sha256"]:
                raise ValueError(f"Portable payload changed: {name}")
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        generated = {"README_PACKAGE.md": package_readme(package),
                     "PACKAGING_REPORT.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n"}
        if package == "source_data":
            versions = {}
            for name in ("numpy", "scipy", "matplotlib", "Pillow", "pypdf"):
                try:
                    versions[name] = importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError:
                    versions[name] = "not installed in packaging environment"
            generated["PYTHON_ENVIRONMENT.json"] = json.dumps({"python": sys.version.split()[0], "packages": versions}, indent=2) + "\n"
        generated_hashes = {name: {"archive_sha256": sha(text.encode("utf-8")), "archive_bytes": len(text.encode("utf-8"))}
                            for name, text in generated.items()}
        generated["MANIFEST.json"] = json.dumps({"files": files, "generated_files": generated_hashes,
                                                 "self_hash": "Manifest is excluded from its own recursive hash index"},
                                                ensure_ascii=False, indent=2) + "\n"
        for name, text in generated.items():
            (stage / name).write_bytes(text.encode("utf-8"))
        with zipfile.ZipFile(output / f"{package}.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(stage).as_posix())
        with zipfile.ZipFile(output / f"{package}.zip") as archive:
            if archive.testzip() is not None:
                raise ValueError("ZIP CRC check failed")
            for name, metadata in {**files, **generated_hashes}.items():
                if sha(archive.read(name)) != metadata["archive_sha256"]:
                    raise ValueError(f"Archived payload SHA256 mismatch: {name}")
        zip_path = output / f"{package}.zip"
        report.setdefault("archives", {})[zip_path.name] = {"sha256": sha(zip_path.read_bytes()), "bytes": zip_path.stat().st_size}
    (output / "package_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "results/submission_20261002/submission_package")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    inventory = Inventory(ROOT)
    inventory.manuscript()
    inventory.source_roots()
    inventory.dependencies()
    report = inventory.report()
    if args.execute:
        execute(inventory, report, args.output, args.allow_incomplete)
    if args.summary_only:
        report = {k: v for k, v in report.items() if k not in {"files", "excluded_dependencies", "historical_hash_mismatches", "verified_archive_recovery"}}
        report["excluded_count"] = len(inventory.excluded)
        report["verified_recovery_count"] = len({x["package_path"] for x in inventory.recovered})
        report["historical_hash_mismatch_count"] = len({(x["path"], x["historical_sha256"]) for x in inventory.hash_mismatches})
    print(json.dumps(report, ensure_ascii=False, indent=2))


def self_test():
    for name in (".env", ".env.local", "credentials.json", "secret.txt", "id_rsa", "id_ed25519", "known_hosts", "state.jld2", "stdout.log", ".ssh/config"):
        assert exclusion(Path(name)), name
    for name in ("Project.toml", "Manifest.toml", "src/hamiltonian.jl", "data/metrics.csv"):
        assert exclusion(Path(name)) is None, name
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        inventory = Inventory(root)
        assert inventory.relative("../../outside.txt") is None
        assert inventory.relative("user@192.0.2.1:/home/user/result.json") is None
        assert inventory.relative("Project.toml", Path("results/run")) == Path("Project.toml")
        (root / "data").mkdir()
        source = root / "data/example.json"
        source.write_text(json.dumps({"path": str(root / "data/value.csv"), "password": "synthetic",
                                      "value": 0.125, "other": "C:/Users/test/private.csv"}), encoding="utf-8")
        inventory.add(source, "source_data", "synthetic privacy test")
        data, actions = inventory.portable("data/example.json")
        value = json.loads(data)
        assert value["value"] == 0.125 and "password" not in value
        assert value["path"].replace("\\", "/") == "data/value.csv"
        assert value["other"] == "[EXTERNAL_PATH_OMITTED]" and actions
        assert not ABS_PATH.search(data.decode())
        (root / "data/value.csv").write_text("value\n0.125\n", encoding="utf-8")
        digest = sha((root / "data/value.csv").read_bytes())
        inventory.records({"root": str(root / "data"), "path": "value.csv", "sha256": digest},
                          Path("unrelated"), "synthetic root/path schema")
        assert "data/value.csv" in inventory.files["source_data"] and not inventory.missing
        program = root / "data/example.py"
        program.write_text("SOURCE = " + repr(str(root / "data/value.csv")) + "\nVALUE = 0.125\n", encoding="utf-8")
        inventory.add(program, "source_data", "synthetic Python portability")
        report = inventory.report()
        assert not report["content_errors"]
        assert report["portable_code_syntax"]["checked_files"]["python"] == 1
        execute(inventory, report, root / "smoke_package", allow_incomplete=False)
        with zipfile.ZipFile(root / "smoke_package/source_data.zip") as archive:
            assert archive.read("data/example.json") == data
            assert archive.testzip() is None
        assert json.loads(source.read_text())["password"] == "synthetic"
        assert program.read_text() == "SOURCE = " + repr(str(root / "data/value.csv")) + "\nVALUE = 0.125\n"
        try:
            execute(inventory, report, root / "smoke_package", allow_incomplete=False)
        except ValueError:
            pass
        else:
            raise AssertionError("Existing output must not be overwritten")
    print(json.dumps({"safety_self_test": "pass", "actual_project_archive_created": False}))


if __name__ == "__main__":
    main()
