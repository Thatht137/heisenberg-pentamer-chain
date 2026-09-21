#!/usr/bin/env bash
set -u -o pipefail

ROOT=/home/wangjieren/code/1x5_Heisenberg_Pentamer
RUN_ROOT=$ROOT/results/autoresearch_v5_20260803/round28_qpi_maxdim96
CELL=$RUN_ROOT/cell-alpha023-maxdim096-dt00125-t30
RUNNER=$ROOT/scripts/autoresearch_v5/run_tebd_qpi_autocorr.py
MANIFEST_HASH=37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c
STANDARD_HASH=4f00f333eaf810b2853a46e4e258e192db7ef554c7800d35df2ebe27adee4b46

write_status() {
    python3 -c 'import json,os,sys; p=sys.argv[1]; t=p+".tmp"; open(t,"w",encoding="utf-8").write(json.dumps({"status":sys.argv[2],"phase":sys.argv[3],"message":sys.argv[4]},ensure_ascii=False)+"\n"); os.replace(t,p)' "$RUN_ROOT/overall_status.json" "$1" "$2" "$3"
}

if [[ -e "$RUN_ROOT" ]]; then
    mkdir -p "$RUN_ROOT"
    write_status blocked preflight "目标目录已存在，拒绝覆盖"
    exit 3
fi
if pgrep -af '[j]ulia' >/dev/null; then
    mkdir -p "$RUN_ROOT"
    write_status blocked preflight "检测到已有 Julia，未启动新任务"
    exit 4
fi

mkdir -p "$RUN_ROOT"
write_status running tebd "严格 q=pi maxdim=96 运行中"
nice -n 10 /usr/bin/time -v python3 "$RUNNER" \
    --cell-id qpi-alpha023-maxdim096-dt00125-t30 \
    --outdir "$CELL" \
    --alpha 0.23 --beta 0.5 --n-units 8 \
    --eta 0.1 --omega-min 0 --omega-max 3 --omega-step 0.05 \
    --tstep 0.0125 --n-steps 2400 \
    --dmrg-maxdim 96 --tebd-maxdim 96 --nsweeps 24 \
    --dmrg-cutoff 1e-10 --tebd-cutoff 1e-10 \
    --checkpoint-interval 100 --threads 8 \
    --expected-julia-version 1.12.3 \
    --expected-manifest-sha256 "$MANIFEST_HASH" \
    --standard-sha256 "$STANDARD_HASH" \
    --source-commit working-tree-20260803-qpi-autocorr
rc=$?
if [[ $rc -ne 0 ]]; then
    write_status failed tebd "maxdim=96 未通过单-run 验收"
    exit "$rc"
fi

if ! python3 - "$CELL/manifest.json" <<'PY'
import json
import sys

manifest = json.loads(open(sys.argv[1], encoding="utf-8").read())
if manifest.get("status") != "success" or manifest.get("accepted") is not True:
    raise SystemExit(1)
PY
then
    write_status failed validate "manifest 未通过终态复核"
    exit 1
fi

write_status success finished "maxdim=96 单-run 验收通过"
exit 0
