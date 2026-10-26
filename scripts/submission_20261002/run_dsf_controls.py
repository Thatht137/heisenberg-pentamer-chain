"""限额运行同基态、单变量动力学对照。"""

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/submission_20261002/dsf_controls"
OLD = ROOT / "results/fullq_dsf_20261001"
JULIA = Path("D:/program/Julia-1.11.5/bin/julia.exe")
DRIVER = ROOT / "scripts/compute_fullq_dsf.jl"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def free_memory():
    if os.name != "nt":
        return float("inf")
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                    *[(name, ctypes.c_ulonglong) for name in
                      ("total", "available", "total_page", "available_page",
                       "total_virtual", "available_virtual", "extended")]]
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("无法读取可用内存")
    return status.available


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    jobs = []
    for sign, alpha, seed in [
        ("positive", "0.5", OLD / "L40_positive/ground.jld2"),
        ("negative", "-0.5", OLD / "spin_gap_L40/negative_seed.jld2"),
    ]:
        for label, dt, q in [("chi", "0.05", "0.2,0.6,1.0"),
                             ("dt", "0.025", "0.2,0.6")]:
            jobs.append({"name": f"{sign}_{label}", "alpha": alpha, "dt": dt,
                         "q_over_pi": q, "chi": 256, "seed": str(seed),
                         "seed_sha256": digest(seed)})
    plan = {"schema_version": 1, "scope": "fixed L40 and T60, not thermodynamic convergence",
            "max_concurrent_jobs": 2, "threads_per_job": 3, "blas_threads": 1,
            "job_timeout_seconds": 7200, "total_timeout_seconds": 21600,
            "minimum_available_memory_bytes": 1610612736,
            "driver_sha256": digest(DRIVER), "jobs": jobs,
            "qpi_dt_reference": "Existing same-ground dt0.025 chi256 check at q/pi=1",
            "thresholds": {"spectrum_relative_l2": 0.03, "low_spectrum_relative_l2": 0.05,
                           "band_weight_relative": 0.05, "band_absolute_floor_C0": 0.001,
                           "main_peak_shift_J1": 0.015, "norm_drift": 0.01},
            "bands_J1": [[0, 0.6], [0.6, 2.5], [2.5, 4.0]],
            "threshold_note": "Frozen before new results; failures are retained and reported."}
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    planpath = OUT / "plan.json"
    if planpath.exists():
        assert json.loads(planpath.read_text(encoding="utf-8")) == plan, "已有计划不同"
    else:
        save(planpath, plan)
    assert JULIA.is_file()
    pending = list(jobs)
    running = []
    records = []
    start = time.monotonic()
    last_report = 0.0
    failure = False
    try:
        while pending or running:
            if time.monotonic() - start > plan["total_timeout_seconds"]:
                raise TimeoutError("总时限已到")
            if free_memory() < plan["minimum_available_memory_bytes"]:
                raise MemoryError("可用内存低于1.5 GiB，停止本轮计算并保留断点")
            while pending and len(running) < plan["max_concurrent_jobs"] and not failure:
                job = pending.pop(0)
                dest = OUT / job["name"]
                dest.mkdir(exist_ok=True)
                if (dest / "result.jld2").exists():
                    records.append({"name": job["name"], "status": "existing_complete"})
                    continue
                env = os.environ.copy()
                env.update(JULIA_NUM_THREADS="3", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
                           PENTAMER_FULLQ_VALUES=job["q_over_pi"], PENTAMER_GROUND_SEED=job["seed"])
                log = (dest / "run.log").open("ab")
                err = (dest / "error.log").open("ab")
                command = [str(JULIA), "--startup-file=no", f"--project={ROOT}", str(DRIVER),
                           str(dest), job["alpha"], "8", job["dt"], "60", "256", "3", "256"]
                flags = subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 0
                proc = subprocess.Popen(command, env=env, cwd=ROOT, stdout=log, stderr=err,
                                        creationflags=flags)
                record = {"name": job["name"], "pid": proc.pid, "command": command,
                          "started_epoch": time.time(), "status": "running"}
                save(dest / "process.json", record)
                running.append((proc, time.monotonic(), record, dest, log, err))
                print(f"START {job['name']} pid={proc.pid}", flush=True)
            for item in running[:]:
                proc, began, record, dest, log, err = item
                elapsed = time.monotonic() - began
                if proc.poll() is None and elapsed > plan["job_timeout_seconds"]:
                    proc.kill()
                    proc.wait()
                    record["status"] = "timeout"
                if proc.poll() is not None:
                    record.update(elapsed_seconds=elapsed, exit_code=proc.returncode)
                    if record["status"] != "timeout":
                        record["status"] = "complete" if proc.returncode == 0 and (dest / "result.jld2").is_file() else "failed"
                    failure |= record["status"] != "complete"
                    save(dest / "process.json", record)
                    records.append(record)
                    running.remove(item)
                    log.close()
                    err.close()
                    print(f"DONE {record['name']} {record['status']} elapsed={elapsed:.1f}s", flush=True)
            if failure and not running:
                break
            if time.monotonic() - last_report > 300:
                print("ACTIVE " + ", ".join(item[2]["name"] for item in running), flush=True)
                last_report = time.monotonic()
            save(OUT / "status.json", {"completed": records, "running": [x[2] for x in running],
                                      "pending": [x["name"] for x in pending], "failure": failure})
            if pending or running:
                time.sleep(10)
    finally:
        # 只终止本轮注册的进程，保留原始数据和断点。
        for proc, _, record, dest, log, err in running:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            record["status"] = "interrupted"
            save(dest / "process.json", record)
            log.close()
            err.close()
    if failure or pending:
        raise RuntimeError("至少一项未完成；检查状态和错误日志")
    print("ALL_CONTROLS_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
