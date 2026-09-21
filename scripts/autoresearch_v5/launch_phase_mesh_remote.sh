#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/wangjieren/code/1x5_Heisenberg_Pentamer"
RUN_DIR="$ROOT/results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh"
RUN_SPEC="$RUN_DIR/parameter-scan.run_spec.json"
RUNNER="$ROOT/scripts/autoresearch_v5/run_phase_structure_batch.py"
PID_FILE="$RUN_DIR/batch.pid"
LOCK_FILE="$RUN_DIR/batch.lock"
STDOUT="$RUN_DIR/batch.stdout.log"
STDERR="$RUN_DIR/batch.stderr.log"

EXPECTED_STANDARD="4f00f333eaf810b2853a46e4e258e192db7ef554c7800d35df2ebe27adee4b46"
EXPECTED_MANIFEST="37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c"
EXPECTED_JULIA="1.12.3"
JULIA="/home/wangjieren/.juliaup/bin/julia"

if [[ ! -f "$RUN_SPEC" || ! -f "$RUNNER" || ! -x "$JULIA" ]]; then
    echo "缺少 run spec、batch runner 或 Julia 1.12.3" >&2
    exit 2
fi
if [[ -s "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "已有运行中的 batch: $(cat "$PID_FILE")" >&2
    exit 3
fi

mkdir -p "$RUN_DIR"
nohup flock -n "$LOCK_FILE" env JULIA_NUM_THREADS=8 python3 "$RUNNER" \
    --run-spec "$RUN_SPEC" \
    --outdir "$RUN_DIR" \
    --standard-sha256 "$EXPECTED_STANDARD" \
    --expected-manifest-sha256 "$EXPECTED_MANIFEST" \
    --expected-julia-version "$EXPECTED_JULIA" \
    --source-commit uploaded-mesh-20260802 \
    --julia "$JULIA" \
    >"$STDOUT" 2>"$STDERR" < /dev/null &
echo $! > "$PID_FILE"
echo "STARTED pid=$(cat "$PID_FILE") stdout=$STDOUT stderr=$STDERR"
