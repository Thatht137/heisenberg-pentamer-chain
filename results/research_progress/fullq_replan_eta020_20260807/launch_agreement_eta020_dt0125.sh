#!/usr/bin/env bash
set -euo pipefail

# agreement 点只启动一个细步长 cell
python3 scripts/autoresearch_v5/run_tebd_production.py \
  --cell-id fullq-agreement-eta020-dt0125 \
  --outdir results/autoresearch_v5_20260807/minimal_fullq_replan_eta020/fullq-agreement-eta020-dt0125 \
  --alpha 0.23 --beta 0.5 --n-units 8 --tstep 0.0125 --n-steps 2400 \
  --dmrg-maxdim 800 --tebd-maxdim 320 --dmrg-cutoff 1e-10 --tebd-cutoff 1e-10 \
  --nsweeps 32 --q-points 121 --omega-points 301 --omega-max 3.0 \
  --space-window 18 --time-window exponential --window-eta 0.20 \
  --max-negative-weight-fraction 0.15 --threads 16 \
  --standard-sha256 aa06eaf6d816b40161e1d493a4c8a800aeac33d8a190eb8312e1ddba90fd7ce8 \
  --expected-manifest-sha256 37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c \
  --expected-julia-version 1.12.3 --source-commit minimal-fullq-eta020-20260807
