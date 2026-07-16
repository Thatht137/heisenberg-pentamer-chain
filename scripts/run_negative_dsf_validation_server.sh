#!/bin/bash
# 负侧临界性 DSF 服务器验证。
# 用法：bash scripts/run_negative_dsf_validation_server.sh [并行度]

set -e

PARALLEL=${1:-4}
ALPHAS=(-0.5 -0.1 -0.05 0.23)
BETA=0.5
N_UNITS=16
L=80
TAG=L80_t30

mkdir -p logs/negative_dsf_validation

export OPENBLAS_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OMP_NUM_THREADS=4

printf "%s\n" "${ALPHAS[@]}" | xargs -P "$PARALLEL" -I {} bash -c '
    alpha=$1
    beta=$2
    n_units=$3
    length=$4
    tag=$5
    log="logs/negative_dsf_validation/a${alpha}_b${beta}_${tag}.log"
    ndsf="data/NDSF_pentamer_alpha=${alpha}_beta=${beta}_L=${length}_${tag}.jld2"
    sqw="data/Sqw_tebd_pentamer_alpha=${alpha}_beta=${beta}_${tag}.jld2"

    export PENTAMER_ALPHA="$alpha"
    export PENTAMER_BETA="$beta"
    export PENTAMER_N_UNITS="$n_units"
    export PENTAMER_TSTEP=0.05
    export PENTAMER_N_STEPS=600
    export PENTAMER_DMRG_MAXDIM=1200
    export PENTAMER_TEBD_MAXDIM=500
    export PENTAMER_DMRG_CUTOFF=1e-10
    export PENTAMER_TEBD_CUTOFF=1e-9
    export PENTAMER_NSWEEPS=30
    export PENTAMER_Q_POINTS=121
    export PENTAMER_OMEGA_POINTS=241
    export PENTAMER_OMEGA_MAX=2.0
    export PENTAMER_SPACE_WINDOW=38
    export PENTAMER_OUTPUT_TAG="$tag"

    echo "[$(date)] alpha=$alpha 开始" > "$log"
    if [ ! -f "$ndsf" ]; then
        julia --project=. scripts/05_tebd_pentamer_server.jl >> "$log" 2>&1
    fi
    if [ ! -f "$sqw" ]; then
        julia --project=. scripts/06_ft_tebd_pentamer_mapped_server.jl >> "$log" 2>&1
    fi
    echo "[$(date)] alpha=$alpha 完成" >> "$log"
' _ {} "$BETA" "$N_UNITS" "$L" "$TAG"

echo "负侧临界性 DSF 验证完成。"
