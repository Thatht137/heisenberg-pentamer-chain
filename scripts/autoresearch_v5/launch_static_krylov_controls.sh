#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/wangjieren/code/1x5_Heisenberg_Pentamer"
RUN_DIR="$ROOT/results/autoresearch_v5_20260919/static_krylov_controls_r1"
RELEASE_MANIFEST="$ROOT/results/autoresearch_v5_20260919/static_krylov_controls_release_v1/server_upload_manifest.json"
SPEC="$RUN_DIR/parameter-scan.run_spec.json"
HASHES="$RUN_DIR/source_hashes.sha256"
CONTRACT="$RUN_DIR/launch-contract.json"
RUNNER="$ROOT/scripts/autoresearch_v5/run_negative_phase_structure_batch.py"
PREFLIGHT="$ROOT/scripts/autoresearch_v5/static_krylov_launch_preflight.py"
LOCK="$ROOT/results/autoresearch_v5_20260919/static-krylov-controls-global.lock"
RUN_LOCK="$RUN_DIR/static-krylov-controls.lock"
PID_FILE="$RUN_DIR/batch.pid"
PREFLIGHT_LOG="$RUN_DIR/launch-preflight.json"
TIMEOUT_FILE="$RUN_DIR/batch.timeout"
JULIA="/home/wangjieren/.julia/juliaup/julia-1.12.3+0.x64.linux.gnu/bin/julia"
TOTAL_WALL=7200
TERM_GRACE=60

[[ -f "$SPEC" && -f "$HASHES" && -f "$CONTRACT" && -f "$RELEASE_MANIFEST" && -f "$PREFLIGHT" && -x "$JULIA" ]] || exit 2
[[ "$($JULIA --startup-file=no --version 2>/dev/null)" == "julia version 1.12.3" ]] || exit 2
[[ -x "$(command -v flock)" && -x "$(command -v setsid)" && -x "$(command -v readlink)" && -x "$(command -v awk)" && -x "$(command -v ps)" ]] || exit 2
[[ -d /proc ]] || exit 2
[[ ! -e "$PREFLIGHT_LOG" && ! -e "$PID_FILE" && ! -e "$TIMEOUT_FILE" && ! -e "$RUN_DIR/run_status.json" ]] || exit 3
[[ ! -d "$RUN_DIR/cells" || -z "$(find "$RUN_DIR/cells" -mindepth 1 -maxdepth 1 -print -quit)" ]] || exit 3
(cd "$ROOT" && sha256sum -c "$HASHES") >/dev/null

julia_real="$(readlink -f "$JULIA")"
uid_self="$(id -u)"
julia_owned() {
  local proc uid exe
  for proc in /proc/[0-9]*; do
    [[ -r "$proc/status" && -r "$proc/exe" ]] || continue
    uid="$(awk '/^Uid:/{print $2; exit}' "$proc/status" 2>/dev/null)"
    [[ "$uid" == "$uid_self" ]] || continue
    exe="$(readlink -f "$proc/exe" 2>/dev/null)" || continue
    case "$exe" in
      "$julia_real"|/home/wangjieren/.julia/juliaup/*/bin/julia) return 0 ;;
    esac
  done
  return 1
}
julia_owned && exit 3

exec 9>"$LOCK"
flock -n 9 || exit 3
exec 8>"$RUN_LOCK"
flock -n 8 || exit 3

python3 "$PREFLIGHT" --mode launch --manifest "$RELEASE_MANIFEST" --root "$ROOT" --json >"$PREFLIGHT_LOG"
[[ -s "$PREFLIGHT_LOG" ]] || exit 2
mkdir -p "$RUN_DIR"

child_pid=""
child_pgid=""
watchdog_pid=""
group_alive() {
  [[ -n "$child_pgid" ]] && kill -0 -- "-$child_pgid" 2>/dev/null
}
terminate_group() {
  if group_alive; then
    kill -TERM -- "-$child_pgid" 2>/dev/null || true
    for _ in $(seq 1 "$TERM_GRACE"); do
      group_alive || break
      sleep 1
    done
    kill -KILL -- "-$child_pgid" 2>/dev/null || true
  fi
}
on_signal() {
  terminate_group
  exit 143
}
trap on_signal INT TERM

nohup setsid nice -n 10 env \
  JULIA_NUM_THREADS=8 \
  JULIA_PKG_OFFLINE=true \
  JULIA_PKG_SERVER= \
  HTTP_PROXY=http://127.0.0.1:9 \
  HTTPS_PROXY=http://127.0.0.1:9 \
  PYTHONUNBUFFERED=1 \
  python3 "$RUNNER" \
  --run-spec "$SPEC" \
  --outdir "$RUN_DIR" \
  --standard-sha256 "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["standard_sha256"])' "$CONTRACT")" \
  --expected-manifest-sha256 "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["manifest_sha256"])' "$CONTRACT")" \
  --expected-julia-version 1.12.3 \
  --source-commit uploaded-static-krylov-controls-release-v1 \
  --julia "$JULIA" \
  >"$RUN_DIR/batch.stdout.log" 2>"$RUN_DIR/batch.stderr.log" < /dev/null &
child_pid=$!
child_pgid="$(ps -o pgid= -p "$child_pid" | tr -d ' ')"
[[ "$child_pgid" == "$child_pid" && "$child_pgid" != "$(ps -o pgid= -p $$ | tr -d ' ')" ]] || { terminate_group; exit 2; }
echo "$child_pid" >"$PID_FILE"

(
  sleep "$TOTAL_WALL"
  if group_alive; then
    : >"$TIMEOUT_FILE"
    kill -TERM -- "-$child_pgid" 2>/dev/null || true
    sleep "$TERM_GRACE"
    kill -KILL -- "-$child_pgid" 2>/dev/null || true
  fi
) &
watchdog_pid=$!

set +e
wait "$child_pid"
rc=$?
set -e
terminate_group
kill "$watchdog_pid" 2>/dev/null || true
wait "$watchdog_pid" 2>/dev/null || true
exit "$rc"
