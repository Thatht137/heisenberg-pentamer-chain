#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/wangjieren/code/1x5_Heisenberg_Pentamer"
STAGE="stage-c-negative-refine-practical-v2-r1"
RUN_DIR="$ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/$STAGE"
SPEC="$RUN_DIR/parameter-scan.run_spec.json"
HASHES="$RUN_DIR/stage_c_source_hashes.sha256"
CONTRACT="$RUN_DIR/launch-contract.json"
RUNNER="$ROOT/scripts/autoresearch_v5/run_negative_phase_structure_batch.py"
LOCK="$ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/negative-phase-global.lock"
JULIA="/home/wangjieren/.juliaup/bin/julia"

get(){ python3 -c 'import json,sys;print(json.load(open(sys.argv[1],encoding="utf-8"))[sys.argv[2]])' "$CONTRACT" "$1"; }
[[ -f "$SPEC" && -f "$HASHES" && -f "$CONTRACT" && -x "$JULIA" ]] || exit 2
[[ "$(get launch_ready)" == True && "$(get stage_b_complete)" == True && "$(get practical_v2)" == True ]] || exit 2
[[ "$(get concurrency)" == 1 && "$(get stop_on_first_failure)" == True && "$(get max_sweeps)" == 64 ]] || exit 2
[[ "$(get boundary_thresholds_relaxed)" == False ]] || exit 2
[[ "$(sha256sum "$SPEC"|awk '{print $1}')" == "$(get run_spec_sha256)" ]] || exit 2
(cd "$ROOT" && sha256sum -c "$HASHES") >/dev/null
[[ ! -e "$RUN_DIR/run_status.json" ]] || exit 3
pgrep -u "$(id -u)" -x julia >/dev/null && exit 3
exec 9>"$LOCK"
flock -n 9 || exit 3
nohup nice -n 10 env JULIA_NUM_THREADS=8 JULIA_PKG_OFFLINE=true JULIA_PKG_SERVER= HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 \
  python3 "$RUNNER" --run-spec "$SPEC" --outdir "$RUN_DIR" --standard-sha256 "$(get standard_sha256)" \
  --expected-manifest-sha256 "$(get manifest_sha256)" --expected-julia-version 1.12.3 \
  --source-commit uploaded-stage-c-practical-v2-r1-20260908 --julia "$JULIA" \
  >"$RUN_DIR/batch.stdout.log" 2>"$RUN_DIR/batch.stderr.log" < /dev/null &
echo $! >"$RUN_DIR/batch.pid"
echo "STARTED pid=$(cat "$RUN_DIR/batch.pid") cells=$(get cell_count) concurrency=1 eta_hours=14-28"
