#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/wangjieren/code/1x5_Heisenberg_Pentamer
RUN_DIR="$ROOT/results/autoresearch_v5_20260914/negative_entropy_sizes_r1"
SPEC="$RUN_DIR/parameter-scan.run_spec.json"
CONTRACT="$RUN_DIR/launch-contract.json"
get(){ python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$CONTRACT" "$1"; }
[[ "$(get cell_count)" == 10 && "$(get concurrency)" == 1 && "$(get launch_ready)" == True ]] || exit 2
[[ "$(sha256sum "$SPEC" | cut -d' ' -f1)" == "$(get run_spec_sha256)" ]] || exit 2
(cd "$ROOT" && sha256sum -c "$RUN_DIR/source_hashes.sha256") >/dev/null
[[ ! -e "$RUN_DIR/run_status.json" && ! -e "$RUN_DIR/batch.pid" ]] || exit 3
pgrep -u "$(id -u)" -x julia >/dev/null && exit 3
exec 9>"$ROOT/results/autoresearch_v5_20260913/negative-phase-independent-pilot.lock"
flock -n 9 || exit 3
nohup nice -n 10 env JULIA_NUM_THREADS=8 JULIA_PKG_OFFLINE=true JULIA_PKG_SERVER= HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 \
 python3 "$ROOT/scripts/autoresearch_v5/run_negative_phase_structure_batch.py" --run-spec "$SPEC" --outdir "$RUN_DIR" \
 --standard-sha256 "$(get standard_sha256)" --expected-manifest-sha256 "$(get manifest_sha256)" --expected-julia-version 1.12.3 \
 --source-commit uploaded-negative-entropy-sizes-r1 --julia /home/wangjieren/.juliaup/bin/julia \
 >"$RUN_DIR/batch.stdout.log" 2>"$RUN_DIR/batch.stderr.log" < /dev/null &
echo $! >"$RUN_DIR/batch.pid"
echo "STARTED pid=$(cat "$RUN_DIR/batch.pid") cells=10 concurrency=1 eta_hours=3-5"
