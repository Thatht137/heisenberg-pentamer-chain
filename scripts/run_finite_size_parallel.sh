#!/bin/bash
# 有限尺寸标度扫描并行启动脚本（07_finite_size_scan.jl）。
# 用法：bash scripts/run_finite_size_parallel.sh [beta] [并行度]

set -e

BETA=${1:-0.5}
PARALLEL=${2:-8}

# 74 alpha points × 4 L values = 296 tasks
TOTAL=296

mkdir -p logs/finite_size

export OPENBLAS_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OMP_NUM_THREADS=4

echo "启动 $TOTAL 个 finite-size 任务，β=$BETA，并行度 $PARALLEL"
echo "日志写到 logs/finite_size/"

seq 1 $TOTAL | xargs -P $PARALLEL -I {} bash -c '
    task_id=$1
    beta=$2
    log="logs/finite_size/task_$(printf %03d $task_id)_b${beta}.log"
    echo "[$(date +%H:%M:%S)] 启动 task $task_id (β=$beta)"
    julia --project=. scripts/07_finite_size_scan.jl $task_id $beta > $log 2>&1
    echo "[$(date +%H:%M:%S)] 完成 task $task_id"
' _ {} $BETA

echo ""
echo "完成。运行 julia --project=. scripts/merge_finite_size.jl 合并数据。"
