#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/wangjieren/code/1x5_Heisenberg_Pentamer"
RUN_DIR="$ROOT/results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/stage-a-beta050-calibration-r1"
RUN_SPEC="$RUN_DIR/parameter-scan.run_spec.json"
SOURCE_HASHES="$RUN_DIR/r1_source_hashes.sha256"
RUNNER="$ROOT/scripts/autoresearch_v5/run_negative_phase_structure_batch.py"
PID_FILE="$RUN_DIR/batch.pid"
LOCK_FILE="$RUN_DIR/batch.lock"
STDOUT="$RUN_DIR/batch.stdout.log"
STDERR="$RUN_DIR/batch.stderr.log"
CONCURRENCY=1

EXPECTED_STANDARD="e0b83c639a8e0a8f992c51ccade05b83944c9c34e39a87c191383bad3c967a4b"
EXPECTED_MANIFEST="37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c"
EXPECTED_RUN_SPEC="3e722a53607cae2a5729530d4ec26fef96067ea3dd0a034d88e53d342c5816a0"
EXPECTED_SOURCE_HASHES="1c30107400a827450638994b45e5b340ff9c57517bc48a9507f6ae9208fe4542"
EXPECTED_JULIA="1.12.3"
JULIA="/home/wangjieren/.juliaup/bin/julia"

[[ "$CONCURRENCY" == "1" && -f "$RUN_SPEC" && -f "$SOURCE_HASHES" && -f "$RUNNER" && -x "$JULIA" ]] || {
    echo "R1 输入不完整或并发设置错误" >&2
    exit 2
}
[[ "$(sha256sum "$RUN_SPEC" | awk '{print $1}')" == "$EXPECTED_RUN_SPEC" ]] || { echo "run spec SHA-256 不匹配" >&2; exit 2; }
[[ "$(sha256sum "$SOURCE_HASHES" | awk '{print $1}')" == "$EXPECTED_SOURCE_HASHES" ]] || { echo "源码清单 SHA-256 不匹配" >&2; exit 2; }
(cd "$ROOT" && sha256sum -c "$SOURCE_HASHES") >/dev/null || { echo "源码 SHA-256 不匹配" >&2; exit 2; }
if [[ -s "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "已有运行中的 R1 batch: $(cat "$PID_FILE")" >&2
    exit 3
fi

mkdir -p "$RUN_DIR"
nohup flock -n "$LOCK_FILE" nice -n 10 env \
    JULIA_NUM_THREADS=8 JULIA_PKG_OFFLINE=true JULIA_PKG_SERVER= \
    HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 \
    python3 "$RUNNER" \
    --run-spec "$RUN_SPEC" \
    --outdir "$RUN_DIR" \
    --standard-sha256 "$EXPECTED_STANDARD" \
    --expected-manifest-sha256 "$EXPECTED_MANIFEST" \
    --expected-julia-version "$EXPECTED_JULIA" \
    --source-commit uploaded-negative-stage-a-r1-20260809 \
    --julia "$JULIA" \
    >"$STDOUT" 2>"$STDERR" < /dev/null &
echo $! > "$PID_FILE"
echo "STARTED pid=$(cat "$PID_FILE") cells=24 concurrency=1 eta_hours=8-14"
