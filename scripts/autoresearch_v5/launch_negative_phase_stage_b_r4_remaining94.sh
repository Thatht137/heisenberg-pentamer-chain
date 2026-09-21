#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/wangjieren/code/1x5_Heisenberg_Pentamer"; RUN_DIR="$ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/stage-b-negative-coarse-r4-remaining94"
SPEC="$RUN_DIR/parameter-scan.run_spec.json"; HASHES="$RUN_DIR/stage_b_r4_source_hashes.sha256"; CONTRACT="$RUN_DIR/launch-contract.json"; JULIA="/home/wangjieren/.juliaup/bin/julia"; RUNNER="$ROOT/scripts/autoresearch_v5/run_negative_phase_structure_batch.py"; LOCK="$ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/negative-phase-global.lock"
get(){ python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$CONTRACT" "$1"; }
[[ "$(get launch_ready)" == True && "$(get r3_failure_validated)" == True && "$(get cell_count)" == 94 && "$(get boundary_thresholds_relaxed)" == False ]] || exit 2
[[ "$(sha256sum "$SPEC"|awk '{print $1}')" == "$(get run_spec_sha256)" ]] || exit 2; (cd "$ROOT" && sha256sum -c "$HASHES") >/dev/null
[[ ! -e "$RUN_DIR/run_status.json" ]] || exit 3; pgrep -u "$(id -u)" -x julia >/dev/null && exit 3; exec 9>"$LOCK"; flock -n 9 || exit 3
nohup nice -n 10 env JULIA_NUM_THREADS=8 JULIA_PKG_OFFLINE=true JULIA_PKG_SERVER= HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 python3 "$RUNNER" --run-spec "$SPEC" --outdir "$RUN_DIR" --standard-sha256 e0b83c639a8e0a8f992c51ccade05b83944c9c34e39a87c191383bad3c967a4b --expected-manifest-sha256 37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c --expected-julia-version 1.12.3 --source-commit uploaded-negative-stage-b-r4-remaining94-20260812 --julia "$JULIA" >"$RUN_DIR/batch.stdout.log" 2>"$RUN_DIR/batch.stderr.log" < /dev/null &
echo $! >"$RUN_DIR/batch.pid"; echo "STARTED pid=$(cat "$RUN_DIR/batch.pid") cells=94 concurrency=1 eta_hours=18-32"
