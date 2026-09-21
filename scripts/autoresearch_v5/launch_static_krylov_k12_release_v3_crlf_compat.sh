#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ORIGINAL_LAUNCHER="$SCRIPT_DIR/launch_static_krylov_k12_release_v3.sh"
ORIGINAL_LAUNCHER_SHA256="6b5ec80766d705368235e29adb89932e338430302865c14288ca737019071b99"
ORIGINAL_ROOT="/home/wangjieren/code/1x5_Heisenberg_Pentamer"
RELEASE_MANIFEST="$BUNDLE_ROOT/results/autoresearch_v5_20260920/static_krylov_controls_release_v3/server_upload_manifest.json"
PREFLIGHT="$BUNDLE_ROOT/scripts/autoresearch_v5/static_krylov_k12_preflight.py"
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
RUN_LOCK="$RUN_DIR/static-krylov-k12.lock"
PID_FILE="$RUN_DIR/batch.pid"
PREFLIGHT_LOG="$RUN_DIR/launch-preflight.json"
SESSION_RECEIPT="$RUN_DIR/session.receipt"
TIMEOUT_FILE="$RUN_DIR/batch.timeout"
SELF_TEST_LOG="$RUN_DIR/supervisor-self-test.log"

[[ -f "$SPEC" && -f "$CONTRACT" && -f "$HASHES" && -f "$RUNNER" ]] || exit 2
[[ ! -e "$PID_FILE" && ! -e "$PREFLIGHT_LOG" && ! -e "$SESSION_RECEIPT" && ! -e "$TIMEOUT_FILE" && ! -e "$SELF_TEST_LOG" && ! -e "$RUN_DIR/run_status.json" ]] || exit 3
[[ ! -d "$RUN_DIR/cells" || -z "$(find "$RUN_DIR/cells" -mindepth 1 -maxdepth 1 -print -quit)" ]] || exit 3
(cd "$BUNDLE_ROOT" && sha256sum -c <(tr -d '\r' < "$HASHES")) >/dev/null
[[ -d "$(dirname "$GLOBAL_LOCK")" ]] || exit 2

exec 9>"$GLOBAL_LOCK"
flock -n 9 || exit 3
exec 8>"$RUN_LOCK"
flock -n 8 || exit 3
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
