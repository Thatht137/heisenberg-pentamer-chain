#!/usr/bin/env bash
set -euo pipefail

mode=${1:-}
root=/home/wangjieren/code/1x5_Heisenberg_Pentamer
round_dir="$root/results/autoresearch_v5_20260730/round4_cv_resume_oracle"
run_dir="$round_dir/cell-0001-L10-qpi-w000-w010"

case "$mode" in
  first)
    [[ ! -e "$run_dir" ]] || { echo "拒绝覆盖已有 cell: $run_dir" >&2; exit 1; }
    resume_args=()
    max_new_points=1
    attempt=1
    ;;
  resume)
    [[ -f "$run_dir/run_config.json" ]] || { echo "缺少可恢复配置" >&2; exit 1; }
    [[ -f "$run_dir/checksums.sha256" ]] || { echo "缺少可恢复哈希" >&2; exit 1; }
    resume_args=(--resume)
    max_new_points=0
    attempt=2
    ;;
  *)
    echo "用法: $0 first|resume" >&2
    exit 2
    ;;
esac

mkdir -p "$round_dir"
cd "$root"
nohup python3 scripts/autoresearch_v5/run_cv_dsf_resumable.py \
  --cell-id cell-0001-L10-qpi-w000-w010 \
  --outdir "$run_dir" \
  --alpha 0.23 \
  --beta 0.5 \
  --n-units 2 \
  --q-over-pi 1.0 \
  --eta 0.1 \
  --omega-min 0.0 \
  --omega-max 0.1 \
  --omega-step 0.05 \
  --dmrg-maxdim 64 \
  --cv-maxdim 100 \
  --nsweeps 12 \
  --cutoff 1e-14 \
  --cv-cutoff 1e-14 \
  --max-cv-residual 1e-5 \
  --max-new-points "$max_new_points" \
  --threads 8 \
  "${resume_args[@]}" \
  > "$round_dir/launcher-attempt-${attempt}.log" 2>&1 < /dev/null &

pid=$!
echo "$pid" > "$round_dir/launcher-attempt-${attempt}.pid"
echo "PID=$pid"
