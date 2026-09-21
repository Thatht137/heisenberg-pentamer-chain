#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/wangjieren/code/1x5_Heisenberg_Pentamer"
RUN_DIR="$ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/stage-a-beta050-calibration-r9-remaining7"
RUN_SPEC="$RUN_DIR/parameter-scan.run_spec.json"
SOURCE_HASHES="$RUN_DIR/r9_source_hashes.sha256"
CONTRACT="$RUN_DIR/launch-contract.json"
RUNNER="$ROOT/scripts/autoresearch_v5/run_negative_phase_structure_batch.py"
PID_FILE="$RUN_DIR/batch.pid"
GLOBAL_LOCK="$ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/negative-phase-global.lock"
JULIA="/home/wangjieren/.juliaup/bin/julia"

get() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8"))[sys.argv[2]])' "$CONTRACT" "$1"; }
[[ -f "$RUN_SPEC" && -f "$SOURCE_HASHES" && -f "$CONTRACT" && -x "$JULIA" ]] || { echo "R9 输入不完整" >&2; exit 2; }
[[ "$(get launch_ready)" == "True" && "$(get cell_count)" == "7" && "$(get concurrency)" == "1" && "$(get offline)" == "True" && "$(get r7_r8_evidence_preserved)" == "True" && "$(get thresholds_relaxed)" == "False" ]] || { echo "R9 contract 未放行" >&2; exit 2; }
[[ "$(sha256sum "$RUN_SPEC" | awk '{print $1}')" == "$(get run_spec_sha256)" ]] || { echo "R9 run spec 哈希失败" >&2; exit 2; }
[[ "$(sha256sum "$SOURCE_HASHES" | awk '{print $1}')" == "$(get source_hashes_sha256)" ]] || { echo "R9 source list 哈希失败" >&2; exit 2; }
(cd "$ROOT" && sha256sum -c "$SOURCE_HASHES") >/dev/null || { echo "R9 source 哈希失败" >&2; exit 2; }
[[ ! -e "$RUN_DIR/run_status.json" ]] || { echo "R9 已有运行证据" >&2; exit 3; }
if pgrep -u "$(id -u)" -x julia >/dev/null; then echo "检测到 Julia" >&2; exit 3; fi
mkdir -p "$RUN_DIR"
exec 9>"$GLOBAL_LOCK"
flock -n 9 || { echo "R9 全局锁占用" >&2; exit 3; }
nohup nice -n 10 env JULIA_NUM_THREADS=8 JULIA_PKG_OFFLINE=true JULIA_PKG_SERVER= HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 \
    python3 "$RUNNER" --run-spec "$RUN_SPEC" --outdir "$RUN_DIR" --standard-sha256 "$(get standard_sha256)" \
    --expected-manifest-sha256 "$(get manifest_sha256)" --expected-julia-version 1.12.3 \
    --source-commit uploaded-negative-stage-a-r9-remaining7-20260811 --julia "$JULIA" \
    >"$RUN_DIR/batch.stdout.log" 2>"$RUN_DIR/batch.stderr.log" < /dev/null &
echo $! > "$PID_FILE"
echo "STARTED pid=$(cat "$PID_FILE") cells=7 concurrency=1 eta_hours=3-5"
