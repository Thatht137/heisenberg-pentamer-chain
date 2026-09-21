#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/wangjieren/code/1x5_Heisenberg_Pentamer"
RUN_DIR="$ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/stage-a-beta050-calibration-r4-a0250-L060"
RUN_SPEC="$RUN_DIR/parameter-scan.run_spec.json"
SOURCE_HASHES="$RUN_DIR/r4_source_hashes.sha256"
CONTRACT="$RUN_DIR/launch-contract.json"
RUNNER="$ROOT/scripts/autoresearch_v5/run_negative_phase_structure_batch.py"
PID_FILE="$RUN_DIR/batch.pid"
LOCK_FILE="$RUN_DIR/batch.lock"
GLOBAL_LOCK="$ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/negative-phase-global.lock"
STDOUT="$RUN_DIR/batch.stdout.log"
STDERR="$RUN_DIR/batch.stderr.log"
JULIA="/home/wangjieren/.juliaup/bin/julia"
CONCURRENCY=1

contract_get() {
    python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]])' "$CONTRACT" "$1"
}

[[ "$CONCURRENCY" == "1" && -f "$RUN_SPEC" && -f "$SOURCE_HASHES" && -f "$CONTRACT" && -f "$RUNNER" && -x "$JULIA" ]] || {
    echo "R4 输入不完整或并发设置错误" >&2
    exit 2
}
[[ "$(contract_get launch_ready)" == "True" && "$(contract_get cell_count)" == "1" && "$(contract_get concurrency)" == "1" && "$(contract_get offline)" == "True" && "$(contract_get thresholds_relaxed)" == "False" ]] || {
    echo "R4 launch contract 未放行" >&2
    exit 2
}
[[ "$(sha256sum "$RUN_SPEC" | awk '{print $1}')" == "$(contract_get run_spec_sha256)" ]] || { echo "run spec SHA-256 不匹配" >&2; exit 2; }
[[ "$(sha256sum "$SOURCE_HASHES" | awk '{print $1}')" == "$(contract_get source_hashes_sha256)" ]] || { echo "源码清单 SHA-256 不匹配" >&2; exit 2; }
(cd "$ROOT" && sha256sum -c "$SOURCE_HASHES") >/dev/null || { echo "源码 SHA-256 不匹配" >&2; exit 2; }
if [[ -s "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "已有运行中的 R4 batch: $(cat "$PID_FILE")" >&2
    exit 3
fi
if pgrep -u "$(id -u)" -f '[j]ulia' >/dev/null; then
    echo "检测到本账户 Julia，拒绝启动第二批" >&2
    exit 3
fi

mkdir -p "$RUN_DIR"
exec 9>"$GLOBAL_LOCK"
flock -n 9 || { echo "负区全局计算锁已被占用" >&2; exit 3; }
exec 8>"$LOCK_FILE"
flock -n 8 || { echo "R4 计算锁已被占用" >&2; exit 3; }
nohup nice -n 10 env \
    JULIA_NUM_THREADS=8 JULIA_PKG_OFFLINE=true JULIA_PKG_SERVER= \
    HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 \
    python3 "$RUNNER" \
    --run-spec "$RUN_SPEC" \
    --outdir "$RUN_DIR" \
    --standard-sha256 "$(contract_get standard_sha256)" \
    --expected-manifest-sha256 "$(contract_get manifest_sha256)" \
    --expected-julia-version 1.12.3 \
    --source-commit uploaded-negative-stage-a-r4-a0250-L060-20260810 \
    --julia "$JULIA" \
    >"$STDOUT" 2>"$STDERR" < /dev/null &
echo $! > "$PID_FILE"
echo "STARTED pid=$(cat "$PID_FILE") cells=1 concurrency=1 eta_minutes=20-40"
