# Portable Submission Packages, 2026-10-04

## Status and purpose

`scripts/submission_20261002/package_submission.py` prepares two distinct local
packages. Its default is a read-only inventory and portability check, not ZIP
creation, upload, or publication. All 12 independent spectral comparisons have
now passed; the completed negative-coupling time-step exports are available.
Rerun the inventory whenever manuscript or data inputs change; a dry-run count
is not a permanent release manifest.

The package supports inspection of the selected figures and numerical tables.
It is **not a complete historical wavefunction archive**, nor a claim that every
simulation, historical audit, or plotting entry point has been independently
rerun from the portable package. Public repository, DOI, license, authorship,
funding, and submission attestations remain decisions for the authors.

## Two packages

`manuscript.zip` retains the project-relative `paper_prb/` layout and contains:

- `main.tex`, recursively referenced section files, and `references.bib`;
- only the figure files actually referenced by those active TeX inputs;
- `build.ps1`, the current compiled PDF, and `README.md`;
- `cover_letter.txt`, `FIGURE_SOURCES.md`, and `VALIDATION_20261004.md`;
- generated package scope, inventory, and checksum records.

Neither old manuscript baselines nor unused figure exports enter this package.
The tool warns if the PDF predates an active TeX, bibliography, or figure input.
It does not compile the manuscript itself. Identity and funding placeholders
are retained as explicitly requested and must be completed by the authors.

`source_data.zip` retains the project-relative layout and has an explicit
scientific allowlist:

- Main figures: historical model/local-multiplet figure, new two-cell projection
  benchmark, the unchanged user-selected full-q pair, and discrete finite-size
  momentum reconstruction.
- Appendix figures: historical selection rules and positive-coupling
  entanglement, plus the new negative-coupling entropy solver control.
- Selected figures' provenance JSON, plotted/source CSVs, PDF/PNG/SVG exports,
  captions, and visual-QA records. No footer is added to numerical images.
- Positive and negative L40 spectra: 41-q grids, frequency grids, spectral
  arrays, time-correlation CSVs, metrics, and run metadata; old same-ground
  control and small-system ED validation tables are also included.
- The frozen independent-control plan, completed new control CSV/metadata
  exports, and the current DSF audit. A run is not treated as exported until
  its completion artifact exists locally; that large artifact is not copied.
  A non-passing or partial audit remains a final-packaging warning.
- Signed frequency-window accounting: summary, all-q and selected-q tables,
  appendix table, README, and its analysis script.
- Eight-spin near-zero-exchange oracle: all 47 actual computed points,
  specification, summary, checksums, calculation/validation/report scripts,
  and focused tests. These records support the finite-coupling deviations
  discussed in the manuscript; they are not an infinite-chain result.
- Recovered k=12 terminal records and numerical CSV/JSON/checksum records,
  the provenance audit, and the two pointwise CV verification tables. Saved
  states and execution logs remain excluded even when recovery verified them.
- Relevant explicitly selected analysis and computation scripts, their
  unambiguous local Python imports, `src/*.jl`, and Julia Project/Manifest.
  The packaging environment's Python and selected library versions are
  recorded separately; they are not asserted to be every historical runtime.

## Dependency boundaries

Traversal is restricted to known JSON/CSV path fields and source-hash maps,
child-manifest lists, finite-DMRG measurement filenames, and literal Python
imports. Historical checksum records with `root`, `path`, and `sha256` are
resolved against their declared project-local root. Arbitrary string values,
shell commands, machine environment fields, or directory names are not executed
or recursively treated as instructions.

The large historical phase index is retained as provenance, but only the
parameter points used in the new reconstruction figure, at L60 and L80, trigger
raw-run dependency collection. This is not a whole-repository export. Unknown
schemas, dynamic imports, local runtime configuration, and data used only by
unused historical figures may not be covered. The report lists all missing
dependencies found by these supported traversal rules, not an impossible claim
that no undeclared dependency exists anywhere in the historical code.

## Recovery and historical hashes

The missing logical source
`results/autoresearch_v5_20260914/negative_entropy_sizes_fetch_20260915_1445/coverage.json`
was found under the same relative path inside
`_archive/submission_cleanup_20260923/`. Its SHA-256 is
`f4196d4e1ba7644454c301bdc66a891fccdba05e1b3b6828c5a05e2fd55a5a0b`, exactly
matching the historical reference. The tool only accepts this explicit recovery
after that match, records the physical-to-logical source mapping, and never
restores over an original file.

The k=12 recovery map comes from the verified records in
`results/submission_20261002/provenance/audit.json`. Each portable input is
rehashed before accepting its restored copy. Logical original paths are retained
inside the package; the recovery source is recorded in the manifest. Files with
excluded extensions are not included merely because their hashes are known.

Historical source-hash references can differ from the current analysis code or
other revised files. The inventory reports both hashes and the referring record;
it does not silently replace historical hashes or label revised files as the
original historical version. Review every such entry before release. The
archived historical checksum files describe historical pre-portability bytes;
use the generated `MANIFEST.json` to verify this portable package's bytes.

## Privacy and preservation

The basename and path policy excludes `.env` variants, credentials/secrets,
passwords, SSH/private-key names, private tool/configuration directories, logs,
JLD2 states/checkpoints, process/status files, and unsupported formats. Selected
text files are additionally checked for private-key or token-like content;
finding such content blocks package creation. Files above 30 MiB are explicitly
reported as excluded, not silently added.

Portable copies remove absolute project-root prefixes and omit external local
paths, SSH endpoints, and private/runtime metadata. Original project files are
never edited or deleted. Each manifest entry records the original SHA-256,
portable-copy SHA-256, sizes, inclusion reason, and transformations. Numerical
arrays and scientific values are not adjusted. Source PDF/PNG files are copied
byte-for-byte; no image generation, smoothing, reflection averaging, or retouching
occurs. Textual SVG metadata can receive path-only portability changes.

The explicit scientific allowlist is the primary privacy boundary; token-pattern
checks are not a universal secret detector. Authors must review the inventory
and the staged files before any public release. A local ZIP does not grant a
license or imply permission to publish all included third-party material.

## Validation and use

Run from the project root with the existing Python environment:

```powershell
.venv/Scripts/python.exe scripts/submission_20261002/package_submission.py --summary-only
.venv/Scripts/python.exe scripts/submission_20261002/package_submission.py --self-test
```

Without `--summary-only`, the full JSON inventory includes every selected file,
exclusion, missing supported dependency, historical hash mismatch, and verified
recovery. No actual project package is created in either check. The self-test
uses only disposable synthetic files and verifies escape rejection, private-name
exclusion, path/metadata sanitization, unchanged originals, ZIP CRC/SHA checks,
and refusal to overwrite an existing output directory.

Every selected portable Python source is compiled in memory for syntax, without
execution. If an existing Julia executable is available, every portable Julia
source is parsed with `Meta.parse`, without loading packages or running its
code. Missing Julia or parsing failures are reported. These checks do not prove
runtime portability or scientific correctness, and not all legacy plotting
entry points have been execution-tested from this archive.

After the calculations, audit, and manuscript/PDF are finalized, create a new
local output directory with an explicit execution request:

```powershell
.venv/Scripts/python.exe scripts/submission_20261002/package_submission.py --execute --output results/submission_20261002/submission_package_release
```

The output directory must be new and inside the project. Existing output is
never deleted or overwritten. Missing supported dependencies or warnings block
execution by default. `--allow-incomplete` is only an explicit acknowledgment
for a reviewed incomplete local package, never a way to claim full reproducibility
or scientific validation. Content/privacy failures always block execution.

Creation rereads and rehashes inputs to reject concurrent changes. It writes
`manuscript/` and `source_data/` staging directories, their ZIP files, and the
outer `package_report.json`. Each ZIP receives CRC and payload-SHA verification.
The manifest excludes its own recursive hash; the outer report records each
completed ZIP's SHA-256. No network transfer or public deposition is performed.

Before final release, verify that the 12-comparison DSF audit passes, the final
negative time-step exports are included, the current PDF is rebuilt, the
manuscript validation note exists, every historical hash difference has been
reviewed, and the authors have completed their own publication decisions.
