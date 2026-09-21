#!/usr/bin/env bash
set -u -o pipefail

ROOT=/home/wangjieren/code/1x5_Heisenberg_Pentamer
RUN_ROOT=$ROOT/results/autoresearch_v5_20260803/round26_qpi_tebd_production
COARSE=$RUN_ROOT/cell-alpha023-qpi-dt0025-t30
REFINED=$RUN_ROOT/cell-alpha023-qpi-dt00125-t30
OVERALL=$RUN_ROOT/overall_status.json
RUNNER=$ROOT/scripts/autoresearch_v5/run_tebd_qpi_autocorr.py
MANIFEST_HASH=37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c
STANDARD_HASH=4f00f333eaf810b2853a46e4e258e192db7ef554c7800d35df2ebe27adee4b46

write_status() {
    python3 -c 'import json,os,sys; p=sys.argv[1]; t=p+".tmp"; open(t,"w",encoding="utf-8").write(json.dumps({"status":sys.argv[2],"phase":sys.argv[3],"message":sys.argv[4]},ensure_ascii=False)+"\n"); os.replace(t,p)' "$OVERALL" "$1" "$2" "$3"
}

run_cell() {
    local cell_id=$1
    local outdir=$2
    local tstep=$3
    local steps=$4
    local resume_args=()
    if [[ -f "$outdir/checkpoint_latest.jld2" ]]; then
        resume_args=(--resume)
    fi
    nice -n 10 /usr/bin/time -v python3 "$RUNNER" \
        --cell-id "$cell_id" \
        --outdir "$outdir" \
        --alpha 0.23 --beta 0.5 --n-units 8 \
        --eta 0.1 --omega-min 0 --omega-max 3 --omega-step 0.05 \
        --tstep "$tstep" --n-steps "$steps" \
        --dmrg-maxdim 320 --tebd-maxdim 320 --nsweeps 24 \
        --dmrg-cutoff 1e-10 --tebd-cutoff 1e-10 \
        --checkpoint-interval 100 --threads 8 \
        --expected-julia-version 1.12.3 \
        --expected-manifest-sha256 "$MANIFEST_HASH" \
        --standard-sha256 "$STANDARD_HASH" \
        --source-commit working-tree-20260803-qpi-autocorr \
        "${resume_args[@]}"
}

mkdir -p "$RUN_ROOT"
if pgrep -af '[j]ulia' >/dev/null; then
    write_status blocked preflight "检测到已有 Julia，未启动新任务"
    exit 4
fi

write_status running coarse "严格 q=pi coarse 运行中"
run_cell qpi-alpha023-dt0025-t30 "$COARSE" 0.025 1200
coarse_rc=$?
if [[ $coarse_rc -ne 0 ]]; then
    write_status failed coarse "coarse 未通过，refined 未启动"
    exit "$coarse_rc"
fi

write_status running refined "coarse 通过，严格 q=pi refined 运行中"
run_cell qpi-alpha023-dt00125-t30 "$REFINED" 0.0125 2400
refined_rc=$?
if [[ $refined_rc -ne 0 ]]; then
    write_status failed refined "refined 未通过"
    exit "$refined_rc"
fi

write_status success finished "coarse 与 refined 均通过单-run 验收"
exit 0
