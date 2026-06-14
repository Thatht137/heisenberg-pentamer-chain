#!/bin/bash
# 在服务器上并行跑 80 个 task 的加密相图。
# 用法：bash scripts/run_phase_80x60_parallel.sh [并行度]
# 默认并行度 8，根据服务器空闲核数调整。

set -e

PARALLEL=${1:-8}
TOTAL=80

mkdir -p logs/phase80x60

# 限制每个 Julia 的 BLAS 线程数为 1，避免单进程吃多核
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OMP_NUM_THREADS=1

echo "启动 $TOTAL 个 task，并行度 $PARALLEL"
echo "日志写到 logs/phase80x60/"

# xargs -P 控制并行度
seq 1 $TOTAL | xargs -P $PARALLEL -I {} bash -c '
    task_id=$1
    log="logs/phase80x60/task_$(printf %03d $task_id).log"
    echo "[$(date +%H:%M:%S)] 启动 task $task_id"
    julia --project=. scripts/03c_phase_diagram_80x60.jl $task_id > $log 2>&1
    echo "[$(date +%H:%M:%S)] 完成 task $task_id"
' _ {}

echo ""
echo "全部完成。运行 julia --project=. scripts/merge_phase_80x60.jl 合并数据。"
