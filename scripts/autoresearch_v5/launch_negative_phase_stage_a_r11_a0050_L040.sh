#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/wangjieren/code/1x5_Heisenberg_Pentamer"
RUN_DIR="$ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/stage-a-beta050-calibration-r11-a0050-L040"
RUN_SPEC="$RUN_DIR/parameter-scan.run_spec.json"
SOURCE_HASHES="$RUN_DIR/r11_source_hashes.sha256"
CONTRACT="$RUN_DIR/launch-contract.json"
RUNNER="$ROOT/scripts/autoresearch_v5/run_negative_phase_structure_batch.py"
PID_FILE="$RUN_DIR/batch.pid"
LOCK_FILE="$RUN_DIR/batch.lock"
GLOBAL_LOCK="$ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/negative-phase-global.lock"
JULIA="/home/wangjieren/.juliaup/bin/julia"

get() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8"))[sys.argv[2]])' "$CONTRACT" "$1"; }
[[ -f "$RUN_SPEC" && -f "$SOURCE_HASHES" && -f "$CONTRACT" && -x "$JULIA" ]] || { echo "R11 输入不完整" >&2; exit 2; }
[[ "$(get launch_ready)" == "True" && "$(get cell_count)" == "1" && "$(get concurrency)" == "1" && "$(get offline)" == "True" && "$(get r6_r7_r9_evidence_preserved)" == "True" && "$(get gap_gate_enforced)" == "True" && "$(get thresholds_relaxed)" == "False" ]] || { echo "R11 contract 未放行" >&2; exit 2; }
[[ "$(sha256sum "$RUN_SPEC" | awk '{print $1}')" == "$(get run_spec_sha256)" ]] || { echo "R11 run spec 哈希失败" >&2; exit 2; }
[[ "$(sha256sum "$SOURCE_HASHES" | awk '{print $1}')" == "$(get source_hashes_sha256)" ]] || { echo "R11 source list 哈希失败" >&2; exit 2; }
(cd "$ROOT" && sha256sum -c "$SOURCE_HASHES") >/dev/null || { echo "R11 source 哈希失败" >&2; exit 2; }
if [[ -e "$RUN_DIR/run_status.json" ]]; then echo "R11 已有运行证据，拒绝重复启动" >&2; exit 3; fi
if [[ -s "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then echo "R11 已运行" >&2; exit 3; fi
if pgrep -u "$(id -u)" -x julia >/dev/null; then echo "检测到 Julia" >&2; exit 3; fi
mkdir -p "$RUN_DIR"
exec 9>"$GLOBAL_LOCK"
flock -n 9 || { echo "R11 全局锁占用" >&2; exit 3; }
exec 8>"$LOCK_FILE"
flock -n 8 || { echo "R11 计算锁占用" >&2; exit 3; }
nohup nice -n 10 env JULIA_NUM_THREADS=8 JULIA_PKG_OFFLINE=true JULIA_PKG_SERVER= HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 \
    python3 "$RUNNER" --run-spec "$RUN_SPEC" --outdir "$RUN_DIR" --standard-sha256 "$(get standard_sha256)" \
    --expected-manifest-sha256 "$(get manifest_sha256)" --expected-julia-version 1.12.3 \
    --source-commit uploaded-negative-stage-a-r11-a0050-L040-20260811 --julia "$JULIA" \
    >"$RUN_DIR/batch.stdout.log" 2>"$RUN_DIR/batch.stderr.log" < /dev/null &
echo $! > "$PID_FILE"
echo "STARTED pid=$(cat "$PID_FILE") cells=1 concurrency=1 eta_minutes=20-45"
