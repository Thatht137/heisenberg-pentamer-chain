#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/wangjieren/code/1x5_Heisenberg_Pentamer"
RUN_DIR="$ROOT/results/autoresearch_v5_20260913/negative_phase_independent_pilot_r1"
SPEC="$RUN_DIR/parameter-scan.run_spec.json"
HASHES="$RUN_DIR/source_hashes.sha256"
CONTRACT="$RUN_DIR/launch-contract.json"
RUNNER="$ROOT/scripts/autoresearch_v5/run_negative_phase_structure_batch.py"
LOCK="$ROOT/results/autoresearch_v5_20260913/negative-phase-independent-pilot.lock"
JULIA="/home/wangjieren/.juliaup/bin/julia"

get(){ python3 -c 'import json,sys;print(json.load(open(sys.argv[1],encoding="utf-8"))[sys.argv[2]])' "$CONTRACT" "$1"; }
[[ -f "$SPEC" && -f "$HASHES" && -f "$CONTRACT" && -x "$JULIA" ]] || exit 2
[[ "$(get launch_ready)" == True && "$(get concurrency)" == 1 ]] || exit 2
[[ "$(get save_state)" == True && "$(get enriched_diagnostics)" == True ]] || exit 2
[[ "$(sha256sum "$SPEC" | awk '{print $1}')" == "$(get run_spec_sha256)" ]] || exit 2
(cd "$ROOT" && sha256sum -c "$HASHES") >/dev/null
[[ ! -e "$RUN_DIR/run_status.json" ]] || exit 3
pgrep -u "$(id -u)" -x julia >/dev/null && exit 3
exec 9>"$LOCK"
flock -n 9 || exit 3
nohup nice -n 10 env JULIA_NUM_THREADS=8 JULIA_PKG_OFFLINE=true JULIA_PKG_SERVER= HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 \
  python3 "$RUNNER" --run-spec "$SPEC" --outdir "$RUN_DIR" --standard-sha256 "$(get standard_sha256)" \
  --expected-manifest-sha256 "$(get manifest_sha256)" --expected-julia-version 1.12.3 \
  --source-commit uploaded-negative-independent-pilot-r1-20260913 --julia "$JULIA" \
  >"$RUN_DIR/batch.stdout.log" 2>"$RUN_DIR/batch.stderr.log" < /dev/null &
echo $! >"$RUN_DIR/batch.pid"
echo "STARTED pid=$(cat "$RUN_DIR/batch.pid") cells=$(get cell_count) concurrency=1 eta_hours=4-10"
