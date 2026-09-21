#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ORIGINAL_LAUNCHER="$SCRIPT_DIR/launch_static_krylov_controls_release_v2.sh"
ORIGINAL_LAUNCHER_SHA256="e4fd4fe02be8581b1f02478513bf0d793a4a7168043790e3912358a9946e7bab"
ORIGINAL_ROOT="/home/wangjieren/code/1x5_Heisenberg_Pentamer"
RELEASE_MANIFEST="$BUNDLE_ROOT/results/autoresearch_v5_20260919/static_krylov_controls_release_v2/server_upload_manifest.json"
PREFLIGHT="$BUNDLE_ROOT/scripts/autoresearch_v5/static_krylov_launch_preflight_v2.py"
SUPERVISOR="$BUNDLE_ROOT/scripts/autoresearch_v5/static_krylov_supervisor.py"
SUPERVISOR_TEST="$BUNDLE_ROOT/scripts/autoresearch_v5/test_static_krylov_supervisor.py"
JULIA="/home/wangjieren/.julia/juliaup/julia-1.12.3+0.x64.linux.gnu/bin/julia"
GLOBAL_LOCK="$ORIGINAL_ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/negative-phase-global.lock"

[[ -f "$ORIGINAL_LAUNCHER" ]] || exit 2
[[ "$(sha256sum "$ORIGINAL_LAUNCHER" | awk '{print $1}')" == "$ORIGINAL_LAUNCHER_SHA256" ]] || exit 2
[[ -f "$RELEASE_MANIFEST" && -f "$PREFLIGHT" && -f "$SUPERVISOR" && -f "$SUPERVISOR_TEST" ]] || exit 2
[[ -x "$(command -v flock)" && -x "$(command -v readlink)" && -x "$(command -v awk)" && -x "$(command -v ps)" && -x "$(command -v python3)" ]] || exit 2
[[ -d /proc ]] || exit 2

RUN_REL="$(python3 -B -X utf8 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["remote_run_dir"])' "$RELEASE_MANIFEST")"
HASH_REL="$(python3 -B -X utf8 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["bundle_source_hashes_path"])' "$RELEASE_MANIFEST")"
RELEASE_ID="$(python3 -B -X utf8 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["release_id"])' "$RELEASE_MANIFEST")"
RUN_DIR="$BUNDLE_ROOT/$RUN_REL"
HASHES="$BUNDLE_ROOT/$HASH_REL"
SPEC="$RUN_DIR/parameter-scan.run_spec.json"
CONTRACT="$RUN_DIR/launch-contract.json"
RUNNER="$BUNDLE_ROOT/scripts/autoresearch_v5/run_negative_phase_structure_batch.py"
RUN_LOCK="$RUN_DIR/static-krylov-controls.lock"
PID_FILE="$RUN_DIR/batch.pid"
PREFLIGHT_LOG="$RUN_DIR/launch-preflight.json"
SESSION_RECEIPT="$RUN_DIR/session.receipt"
TIMEOUT_FILE="$RUN_DIR/batch.timeout"
SELF_TEST_LOG="$RUN_DIR/supervisor-self-test.log"
NUMPY_WHEEL_REL="results/autoresearch_v5_20260919/offline_numpy1264_cp310/numpy-1.26.4-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
NUMPY_EVIDENCE_REL="results/autoresearch_v5_20260919/offline_numpy1264_cp310/dependency_evidence.json"
NUMPY_WHEEL_SHA256="ffa75af20b44f8dba823498024771d5ac50620e6915abac414251bd971b4529f"
NUMPY_WHEEL_BYTES="18240889"
NUMPY_EVIDENCE_SHA256="588c3c2792fa4a0c6310bb680270eeb319b6d5459bbb96aaba49fe4448177d34"
NUMPY_RUNTIME="$BUNDLE_ROOT/.runtime/numpy1264"

[[ -f "$SPEC" && -f "$CONTRACT" && -f "$HASHES" && -f "$RUNNER" ]] || exit 2
[[ ! -e "$PID_FILE" && ! -e "$PREFLIGHT_LOG" && ! -e "$SESSION_RECEIPT" && ! -e "$TIMEOUT_FILE" && ! -e "$SELF_TEST_LOG" && ! -e "$RUN_DIR/run_status.json" ]] || exit 3
[[ ! -d "$RUN_DIR/cells" || -z "$(find "$RUN_DIR/cells" -mindepth 1 -maxdepth 1 -print -quit)" ]] || exit 3
[[ ! -e "$NUMPY_RUNTIME" ]] || exit 3
(cd "$BUNDLE_ROOT" && sha256sum -c <(tr -d '\r' < "$HASHES")) >/dev/null
[[ -d "$(dirname "$GLOBAL_LOCK")" ]] || exit 2
NUMPY_WHEEL="$BUNDLE_ROOT/$NUMPY_WHEEL_REL"
NUMPY_EVIDENCE="$BUNDLE_ROOT/$NUMPY_EVIDENCE_REL"
[[ -f "$NUMPY_WHEEL" && -f "$NUMPY_EVIDENCE" ]] || exit 2
[[ "$(stat -c '%s' "$NUMPY_WHEEL")" == "$NUMPY_WHEEL_BYTES" ]] || exit 2
[[ "$(sha256sum "$NUMPY_WHEEL" | awk '{print $1}')" == "$NUMPY_WHEEL_SHA256" ]] || exit 2
[[ "$(sha256sum "$NUMPY_EVIDENCE" | awk '{print $1}')" == "$NUMPY_EVIDENCE_SHA256" ]] || exit 2

exec 9>"$GLOBAL_LOCK"
flock -n 9 || exit 3
exec 8>"$RUN_LOCK"
flock -n 8 || exit 3

python3 -B -X utf8 - "$NUMPY_WHEEL" "$NUMPY_RUNTIME" <<'PY'
from pathlib import Path
import shutil
import stat
import sys
import zipfile

wheel = Path(sys.argv[1])
dest = Path(sys.argv[2])
if dest.exists():
    raise SystemExit("NumPy runtime already exists")
root = dest.resolve()
seen = set()
try:
    dest.mkdir(parents=True)
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            name = info.filename
            if not name or name in seen or name.startswith("/") or "\x00" in name:
                raise SystemExit("unsafe wheel member")
            seen.add(name)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise SystemExit("symlink in wheel")
            target = (dest / name).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise SystemExit("wheel path escapes runtime") from exc
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
except BaseException:
    shutil.rmtree(dest, ignore_errors=True)
    raise
PY
export PYTHONNOUSERSITE=1
export PYTHONPATH="$NUMPY_RUNTIME"
python3 -B -X utf8 -c 'import numpy,sys; assert numpy.__version__ == "1.26.4"; sys.stdout.write(numpy.__version__)' >/dev/null 2>&1 || exit 2
python3 -B -X utf8 "$SUPERVISOR_TEST" -q >"$SELF_TEST_LOG" 2>&1 || exit 2
[[ -x "$JULIA" ]] || exit 2
[[ "$($JULIA --startup-file=no --version 2>/dev/null)" == "julia version 1.12.3" ]] || exit 2

julia_real="$(readlink -f "$JULIA")"
uid_self="$(id -u)"
julia_owned() {
  local proc uid exe
  for proc in /proc/[0-9]*; do
    [[ -r "$proc/status" && -r "$proc/exe" ]] || continue
    uid="$(awk '/^Uid:/{print $2; exit}' "$proc/status" 2>/dev/null)"
    [[ "$uid" == "$uid_self" ]] || continue
    exe="$(readlink -f "$proc/exe" 2>/dev/null)" || continue
    [[ "${exe##*/}" == "julia" ]] && return 0
  done
  return 1
}
julia_owned && exit 3

python3 -B -X utf8 "$PREFLIGHT" --mode launch --manifest "$RELEASE_MANIFEST" --root "$BUNDLE_ROOT" --json >"$PREFLIGHT_LOG"
[[ -s "$PREFLIGHT_LOG" ]] || exit 2

STANDARD_SHA="$(awk '{ sub(/\r$/, "", $2); if ($2 == "docs/negative_alpha_practical_convergence_standard_20260829.md") print $1 }' "$HASHES")"
MANIFEST_SHA="$(awk '{ sub(/\r$/, "", $2); if ($2 == "Manifest.toml") print $1 }' "$HASHES")"
[[ "$STANDARD_SHA" =~ ^[0-9a-f]{64}$ && "$MANIFEST_SHA" =~ ^[0-9a-f]{64}$ ]] || exit 2

export JULIA_NUM_THREADS=8 JULIA_PKG_OFFLINE=true JULIA_PKG_SERVER=
export HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 PYTHONUNBUFFERED=1
exec nice -n 10 python3 -B -X utf8 "$SUPERVISOR" \
  --cwd "$BUNDLE_ROOT" \
  --receipt "$SESSION_RECEIPT" \
  --pid-file "$PID_FILE" \
  --status-file "$RUN_DIR/supervisor_status.json" \
  --timeout-file "$TIMEOUT_FILE" \
  --stdout "$RUN_DIR/batch.stdout.log" \
  --stderr "$RUN_DIR/batch.stderr.log" \
  --timeout 7200 --term-grace 60 -- \
  python3 -B -X utf8 "$RUNNER" \
  --run-spec "$SPEC" \
  --outdir "$RUN_DIR" \
  --standard-sha256 "$STANDARD_SHA" \
  --expected-manifest-sha256 "$MANIFEST_SHA" \
  --expected-julia-version 1.12.3 \
  --source-commit "$RELEASE_ID" \
  --julia "$JULIA"
