#!/usr/bin/env bash
set -euo pipefail

mode=${1:-}
root=/home/wangjieren/code/1x5_Heisenberg_Pentamer
run_dir="$root/results/autoresearch_v5_20260731/round10_positive_static_multistart_production"
run_spec="$run_dir/run_spec.json"
paths="$run_dir/paths.json"

case "$mode" in
  pilot|full)
    ;;
  *)
    echo "用法: $0 pilot|full" >&2
    exit 2
    ;;
esac

[[ -f "$run_spec" ]] || { echo "缺少 run_spec: $run_spec" >&2; exit 1; }
[[ -f "$paths" ]] || { echo "缺少 paths: $paths" >&2; exit 1; }
pid_file="$run_dir/controller-${mode}.pid"
log_file="$run_dir/controller-${mode}.log"
if [[ -f "$pid_file" ]]; then
  old_pid=$(cat "$pid_file")
  kill -0 "$old_pid" 2>/dev/null && { echo "已有控制器运行: PID=$old_pid" >&2; exit 1; }
fi
[[ ! -e "$log_file" ]] || { echo "拒绝覆盖控制器日志: $log_file" >&2; exit 1; }

cd "$root"
nohup python3 scripts/autoresearch_v5/run_positive_static_scan.py \
  --run-spec "$run_spec" \
  --paths "$paths" \
  --mode "$mode" \
  > "$log_file" 2>&1 < /dev/null &

pid=$!
echo "$pid" > "$pid_file"
echo "PID=$pid MODE=$mode"
