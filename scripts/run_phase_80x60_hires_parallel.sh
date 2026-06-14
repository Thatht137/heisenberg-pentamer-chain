#!/bin/bash
# 高精度版加密相图并行启动脚本（03d）。
# 用法：bash scripts/run_phase_80x60_hires_parallel.sh [并行度]

set -e

PARALLEL=${1:-8}
TOTAL=80

mkdir -p logs/phase80x60_hires

export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OMP_NUM_THREADS=1

echo "启动 $TOTAL 个 hires task，并行度 $PARALLEL"
echo "日志写到 logs/phase80x60_hires/"

seq 1 $TOTAL | xargs -P $PARALLEL -I {} bash -c '
    task_id=$1
    log="logs/phase80x60_hires/task_$(printf %03d $task_id).log"
    echo "[$(date +%H:%M:%S)] 启动 task $task_id"
    julia --project=. scripts/03d_phase_diagram_80x60_hires.jl $task_id > $log 2>&1
    echo "[$(date +%H:%M:%S)] 完成 task $task_id"
' _ {}

echo ""
echo "完成。运行 julia --project=. scripts/merge_phase_80x60_hires.jl 合并数据。"
