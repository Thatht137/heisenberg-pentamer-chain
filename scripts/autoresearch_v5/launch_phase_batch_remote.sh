#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/wangjieren/code/1x5_Heisenberg_Pentamer"
RUN_DIR="$ROOT/results/autoresearch_v5_20260731/round17_phase_diagram_positive"
RUN_SPEC="$RUN_DIR/parameter-scan.run_spec.json"
RUNNER="$ROOT/scripts/autoresearch_v5/run_phase_structure_batch.py"
PID_FILE="$RUN_DIR/batch.pid"
LOCK_FILE="$RUN_DIR/batch.lock"
STDOUT="$RUN_DIR/batch.stdout.log"
STDERR="$RUN_DIR/batch.stderr.log"

EXPECTED_STANDARD="9fb6b1a1f07242be9ada456acc1f8064e3350e93aa410e89a7745e5acded2011"
EXPECTED_MANIFEST="37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c"
EXPECTED_JULIA="1.12.3"

if [[ ! -f "$RUN_SPEC" || ! -f "$RUNNER" ]]; then
    echo "缺少 run spec 或 batch runner" >&2
    exit 2
fi
if [[ -s "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "已有运行中的 batch: $(cat "$PID_FILE")" >&2
    exit 3
fi

MAX_ARGS=()
if [[ "${1:-}" != "" ]]; then
    [[ "$1" =~ ^[0-9]+$ && "$1" -gt 0 ]] || { echo "max-cells 必须为正整数" >&2; exit 2; }
    MAX_ARGS=(--max-cells "$1")
fi

mkdir -p "$RUN_DIR"
nohup flock -n "$LOCK_FILE" env JULIA_NUM_THREADS=8 python3 "$RUNNER" \
    --run-spec "$RUN_SPEC" \
    --outdir "$RUN_DIR" \
    --standard-sha256 "$EXPECTED_STANDARD" \
    --expected-manifest-sha256 "$EXPECTED_MANIFEST" \
    --expected-julia-version "$EXPECTED_JULIA" \
    --source-commit uploaded-bundle-20260731 \
    --julia auto \
    "${MAX_ARGS[@]}" >"$STDOUT" 2>"$STDERR" < /dev/null &
echo $! > "$PID_FILE"
echo "STARTED pid=$(cat "$PID_FILE") stdout=$STDOUT stderr=$STDERR"
