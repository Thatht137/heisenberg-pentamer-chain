#!/usr/bin/env bash
set -euo pipefail

root=/home/wangjieren/code/1x5_Heisenberg_Pentamer
run_dir="$root/results/autoresearch_v5_20260730/round2_cv_cost_probe/cell-0001-L20"
launcher_dir="$root/results/autoresearch_v5_20260730/round2_cv_cost_probe"

mkdir -p "$launcher_dir"
if [[ -e "$run_dir" ]]; then
  echo "拒绝覆盖已有 cell: $run_dir" >&2
  exit 1
fi

cd "$root"
nohup python3 scripts/autoresearch_v5/run_cv_dsf_cell.py \
  --cell-id cell-0001-L20 \
  --outdir "$run_dir" \
  --alpha 0.23 \
  --beta 0.5 \
  --n-units 4 \
  --q-over-pi 1.0 \
  --eta 0.1 \
  --omega-min 0.2 \
  --omega-max 0.2 \
  --omega-step 0.05 \
  --dmrg-maxdim 128 \
  --cv-maxdim 200 \
  --nsweeps 12 \
  --cutoff 1e-10 \
  --threads 8 \
  > "$launcher_dir/launcher.log" 2>&1 < /dev/null &

pid=$!
echo "$pid" > "$launcher_dir/launcher.pid"
echo "PID=$pid"
