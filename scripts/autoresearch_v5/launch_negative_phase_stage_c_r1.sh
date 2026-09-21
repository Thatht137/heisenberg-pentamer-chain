#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/wangjieren/code/1x5_Heisenberg_Pentamer"
RUN_DIR="$ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/stage-c-negative-refine-r1"
RUN_SPEC="$RUN_DIR/parameter-scan.run_spec.json"
SOURCE_HASHES="$RUN_DIR/stage_c_source_hashes.sha256"
CONTRACT="$RUN_DIR/launch-contract.json"
RUNNER="$ROOT/scripts/autoresearch_v5/run_negative_phase_structure_batch.py"
PID_FILE="$RUN_DIR/batch.pid"
GLOBAL_LOCK="$ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/negative-phase-global.lock"
JULIA="/home/wangjieren/.juliaup/bin/julia"

get() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8"))[sys.argv[2]])' "$CONTRACT" "$1"; }
[[ -f "$RUN_SPEC" && -f "$SOURCE_HASHES" && -f "$CONTRACT" && -x "$JULIA" ]] || { echo "Stage C 输入不完整" >&2; exit 2; }
[[ "$(get launch_ready)" == "True" && "$(get concurrency)" == "1" && "$(get stop_on_first_failure)" == "True" && "$(get offline)" == "True" && "$(get stage_b_complete)" == "True" && "$(get boundary_thresholds_relaxed)" == "False" ]] || { echo "Stage C contract 未放行" >&2; exit 2; }
[[ "$(sha256sum "$RUN_SPEC" | awk '{print $1}')" == "$(get run_spec_sha256)" ]] || { echo "Stage C run spec 哈希失败" >&2; exit 2; }
[[ "$(sha256sum "$SOURCE_HASHES" | awk '{print $1}')" == "$(get source_hashes_sha256)" ]] || { echo "Stage C source list 哈希失败" >&2; exit 2; }
(cd "$ROOT" && sha256sum -c "$SOURCE_HASHES") >/dev/null || { echo "Stage C source 哈希失败" >&2; exit 2; }
[[ ! -e "$RUN_DIR/run_status.json" ]] || { echo "Stage C 已有运行证据" >&2; exit 3; }
if pgrep -u "$(id -u)" -x julia >/dev/null; then echo "检测到 Julia" >&2; exit 3; fi
mkdir -p "$RUN_DIR"
exec 9>"$GLOBAL_LOCK"
flock -n 9 || { echo "Stage C 全局锁占用" >&2; exit 3; }
nohup nice -n 10 env JULIA_NUM_THREADS=8 JULIA_PKG_OFFLINE=true JULIA_PKG_SERVER= HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 \
    python3 "$RUNNER" --run-spec "$RUN_SPEC" --outdir "$RUN_DIR" --standard-sha256 "$(get standard_sha256)" \
    --expected-manifest-sha256 "$(get manifest_sha256)" --expected-julia-version 1.12.3 \
    --source-commit uploaded-negative-stage-c-r1-20260812 --julia "$JULIA" \
    >"$RUN_DIR/batch.stdout.log" 2>"$RUN_DIR/batch.stderr.log" < /dev/null &
echo $! > "$PID_FILE"
echo "STARTED pid=$(cat "$PID_FILE") cells=$(get cell_count) concurrency=1 eta_hours=8-24"
