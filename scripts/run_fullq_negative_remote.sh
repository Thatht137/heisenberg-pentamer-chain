#!/usr/bin/env bash
set -euo pipefail

project=/home/wangjieren/code/1x5_Heisenberg_Pentamer
runroot="$project/results/fullq_dsf_20261001"
workspace="$runroot/workspace"
julia=/home/wangjieren/.juliaup/bin/julia
export JULIA_NUM_THREADS=16 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

if [[ "${1:-}" == --start ]]; then
    if [[ -f "$runroot/launcher.pid" ]] && kill -0 "$(cat "$runroot/launcher.pid")" 2>/dev/null; then
        printf '已有运行中的任务\n' >&2
        exit 1
    fi
    nohup timeout --signal=TERM --kill-after=30s 8h bash "$0" \
        > "$runroot/launcher.log" 2>&1 < /dev/null &
    printf '%s\n' "$!" | tee "$runroot/launcher.pid"
    exit 0
fi

run_case() {
    local name=$1 dt=$2 chi=$3 qpoints=$4
    local directory="$runroot/$name"
    mkdir -p "$directory"
    printf 'START %s %s\n' "$name" "$(date -Is)"
    # 复用服务器已有依赖；单任务、低优先级、独立超时。
    timeout --signal=TERM --kill-after=30s 6h nice -n 10 "$julia" +release \
        --startup-file=no --project="$project" "$workspace/scripts/compute_fullq_dsf.jl" \
        "$directory" -0.5 8 "$dt" 60 "$chi" "$qpoints" 256 \
        > "$directory/run.log" 2> "$directory/error.log"
    printf 'DONE %s %s\n' "$name" "$(date -Is)"
}

unset PENTAMER_FULLQ_VALUES
export PENTAMER_GROUND_SEED="$runroot/L40_negative/ground.jld2"
run_case L40_negative_converged 0.05 192 41
export PENTAMER_FULLQ_VALUES=0.4,0.7,1.0,1.3,1.6
export PENTAMER_GROUND_SEED="$runroot/L40_negative_converged/ground.jld2"
run_case L40_negative_check_converged 0.025 256 5
printf 'REMOTE_FULLQ_SUCCESS %s\n' "$(date -Is)"
