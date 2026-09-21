#!/usr/bin/env bash
set -euo pipefail

root=/home/wangjieren/code/1x5_Heisenberg_Pentamer
run_dir="$root/results/autoresearch_v5_20260730/round1_cv_oracle/cell-0001-cv-fix4"
launcher_dir="$root/results/autoresearch_v5_20260730/round1_cv_oracle"

mkdir -p "$launcher_dir"
if [[ -e "$run_dir" ]]; then
  echo "拒绝覆盖已有 cell: $run_dir" >&2
  exit 1
fi

cd "$root"
nohup python3 scripts/autoresearch_v5/run_cv_dsf_cell.py \
  --cell-id cell-0001-fix4 \
  --outdir "$run_dir" \
  --alpha 0.23 \
  --beta 0.5 \
  --n-units 2 \
  --q-over-pi 1.0 \
  --eta 0.1 \
  --omega-min 0.0 \
  --omega-max 3.0 \
  --omega-step 0.05 \
  --dmrg-maxdim 64 \
  --cv-maxdim 100 \
  --nsweeps 12 \
  --cutoff 1e-14 \
  --threads 8 \
  > "$launcher_dir/launcher_attempt5.log" 2>&1 < /dev/null &

pid=$!
echo "$pid" > "$launcher_dir/launcher_attempt5.pid"
echo "PID=$pid"
