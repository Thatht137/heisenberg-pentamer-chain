#!/bin/bash
# 并行批量跑 06_ft_tebd_pentamer_mapped_server.jl，4 并行（共享服务器约束）。
# 06 主循环是 pure Julia scalar loop（不调 BLAS），多进程并行各占一核不互抢。
# 用法：nohup bash scripts/run_ft_batch.sh > logs/ft_batch_main.log 2>&1 &

set -e
export JULIA_DEPOT_PATH=~/julia_depot
mkdir -p logs

PARAMS_FILE=$(mktemp)
cat > $PARAMS_FILE <<EOF
1.0 0.4
1.0 0.7
-1.0 0.1
-1.0 0.4
-1.0 0.7
-1.0 1.0
EOF

cat $PARAMS_FILE | xargs -P 4 -L 1 bash -c '
    alpha=$1
    beta=$2
    log="logs/ft_a${alpha}_b${beta}.log"
    echo "[$(date +%H:%M:%S)] 启动 alpha=$alpha beta=$beta → $log"
    PENTAMER_ALPHA=$alpha PENTAMER_BETA=$beta julia --project=. scripts/06_ft_tebd_pentamer_mapped_server.jl > $log 2>&1
    echo "[$(date +%H:%M:%S)] 完成 alpha=$alpha beta=$beta"
' _

rm -f $PARAMS_FILE
echo "[$(date +%H:%M:%S)] 全部 6 组完成"
