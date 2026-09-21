#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/wangjieren/code/1x5_Heisenberg_Pentamer"
RUN_DIR="$ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/stage-a-beta050-calibration"
RUN_SPEC="$RUN_DIR/parameter-scan.run_spec.json"
RUNNER="$ROOT/scripts/autoresearch_v5/run_negative_phase_structure_batch.py"
PID_FILE="$RUN_DIR/batch.pid"
LOCK_FILE="$RUN_DIR/batch.lock"
STDOUT="$RUN_DIR/batch.stdout.log"
STDERR="$RUN_DIR/batch.stderr.log"

EXPECTED_STANDARD="e0b83c639a8e0a8f992c51ccade05b83944c9c34e39a87c191383bad3c967a4b"
EXPECTED_MANIFEST="37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c"
EXPECTED_RUN_SPEC="391c17806397679cc2a8809274ccabab094a873e1a0e650054424d98964caeeb"
EXPECTED_JULIA="1.12.3"
JULIA="/home/wangjieren/.juliaup/bin/julia"

[[ -f "$RUN_SPEC" && -f "$RUNNER" && -x "$JULIA" ]] || {
    echo "缺少 run spec、batch runner 或 Julia" >&2
    exit 2
}
[[ "$(sha256sum "$RUN_SPEC" | awk '{print $1}')" == "$EXPECTED_RUN_SPEC" ]] || {
    echo "run spec SHA-256 不匹配" >&2
    exit 2
}
if [[ -s "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "已有运行中的 batch: $(cat "$PID_FILE")" >&2
    exit 3
fi

mkdir -p "$RUN_DIR"
nohup flock -n "$LOCK_FILE" nice -n 10 env JULIA_NUM_THREADS=8 python3 "$RUNNER" \
    --run-spec "$RUN_SPEC" \
    --outdir "$RUN_DIR" \
    --standard-sha256 "$EXPECTED_STANDARD" \
    --expected-manifest-sha256 "$EXPECTED_MANIFEST" \
    --expected-julia-version "$EXPECTED_JULIA" \
    --source-commit uploaded-negative-stage-a-20260809 \
    --julia "$JULIA" \
    >"$STDOUT" 2>"$STDERR" < /dev/null &
echo $! > "$PID_FILE"
echo "STARTED pid=$(cat "$PID_FILE") cells=24 eta_hours=5-8"
