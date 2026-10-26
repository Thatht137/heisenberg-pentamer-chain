"""按冻结计划审计十二项同基态、单变量动力学对照。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

try:
    import tomllib
except ModuleNotFoundError:
    from pip._vendor import toml as tomllib


ROOT = Path(__file__).resolve().parents[2]
SAME_SOURCE_TOL = 1e-7
ROUND_TOL = 1e-12
FIXED_KEYS = (
    "alpha", "beta", "L", "n_units", "tmax", "cutoff", "nsweeps",
    "dmrg_maxdim", "itensors_version", "itensormps_version", "julia_version",
    "operator", "time_window", "window_fwhm", "clipping", "inversion_averaging",
    "energy", "variance_per_site", "static_reflection_relative_rms",
    "ground_maxdim_used", "ground_additional_sweeps", "norm_monitor",
)


class PendingRun(Exception):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [{k: float(v) for k, v in row.items()} for row in csv.DictReader(handle)]


def close(a, b) -> bool:
    return bool(np.allclose(a, b, atol=ROUND_TOL, rtol=0))


def check_hash(path: Path, expected: str) -> str:
    require(path.is_file(), f"Missing provenance input: {path}")
    actual = digest(path)
    require(actual == expected, f"Source SHA256 mismatch: {path}")
    return actual


def validate_plan(plan: dict) -> dict:
    require(plan["schema_version"] == 1, "Unsupported plan schema")
    keys = ("spectrum_relative_l2", "low_spectrum_relative_l2", "band_weight_relative",
            "band_absolute_floor_C0", "main_peak_shift_J1", "norm_drift")
    require(all(np.isfinite(plan["thresholds"][k]) and plan["thresholds"][k] > 0 for k in keys),
            "Invalid frozen thresholds")
    bands = plan["bands_J1"]
    require(len(bands) == 3 and bands[0][0] == 0 and bands[-1][1] == 4,
            "Expected three contiguous bands over [0,4]")
    require(all(a < b for a, b in bands) and all(bands[i][1] == bands[i + 1][0] for i in range(2)),
            "Invalid band endpoints")
    jobs = {row["name"]: row for row in plan["jobs"]}
    require(len(jobs) == len(plan["jobs"]) == 4, "Four unique jobs are required")
    for sign, alpha in (("positive", 0.5), ("negative", -0.5)):
        for knob, dt, q in (("chi", 0.05, [0.2, 0.6, 1.0]), ("dt", 0.025, [0.2, 0.6])):
            job = jobs[f"{sign}_{knob}"]
            require(float(job["alpha"]) == alpha and float(job["dt"]) == dt and job["chi"] == 256,
                    f"Unexpected planned controls: {sign}_{knob}")
            actual_q = [float(x) for x in job["q_over_pi"].split(",")]
            require(actual_q == q, f"Unexpected planned q grid: {sign}_{knob}")
        require(jobs[f"{sign}_chi"]["seed"] == jobs[f"{sign}_dt"]["seed"] and
                jobs[f"{sign}_chi"]["seed_sha256"] == jobs[f"{sign}_dt"]["seed_sha256"],
                f"Different planned ground seeds: {sign}")
    return jobs


def load_run(directory: Path, expected_q: list[float], selected_q: list[float],
             expected_meta: dict, seed: Path, baseline_generated: bool = False) -> dict:
    marker = directory / "result.jld2"
    if not marker.is_file():
        process = directory / "process.json"
        if process.is_file():
            status = json.loads(process.read_text(encoding="utf-8"))["status"]
            require(status not in ("complete", "failed", "timeout", "interrupted"),
                    f"Run is terminal without result: {directory.name} ({status})")
        raise PendingRun(f"No completed result: {directory.name}")
    paths = [directory / name for name in
             ("result.jld2", "run_metadata.toml", "q.csv", "omega.csv", "spectrum.csv", "metrics.csv")]
    require(all(p.is_file() for p in paths), f"Incomplete completed artifact: {directory.name}")
    hashes = {p.name: digest(p) for p in paths}
    meta = tomllib.loads((directory / "run_metadata.toml").read_text(encoding="utf-8"))
    require(all(k in meta for k in FIXED_KEYS), f"Missing fixed metadata: {directory.name}")
    for key, value in expected_meta.items():
        require(meta.get(key) == value, f"Expected metadata mismatch: {directory.name}: {key}")
    require(meta["operator"] == "connected full momentum Sz / sqrt(L)" and
            meta["time_window"] == "triangular" and not meta["clipping"] and not meta["inversion_averaging"],
            f"Unsupported observable or postprocessing: {directory.name}")
    if baseline_generated:
        require(not meta.get("ground_seed_path"), "Generated baseline unexpectedly has a ground seed")
        require((directory / "ground.jld2").resolve() == seed.resolve(), "Baseline seed path mismatch")
    else:
        require(Path(meta.get("ground_seed_path", "")).resolve() == seed.resolve(),
                f"Ground seed metadata mismatch: {directory.name}")
    q = np.atleast_1d(np.loadtxt(directory / "q.csv", delimiter=","))
    omega = np.atleast_1d(np.loadtxt(directory / "omega.csv", delimiter=","))
    spectrum = np.loadtxt(directory / "spectrum.csv", delimiter=",", ndmin=2)
    require(q.shape == (len(expected_q),) and close(q / np.pi, expected_q),
            f"Actual q grid mismatch: {directory.name}")
    require(np.isfinite(q).all() and np.all(np.diff(q) > 0), "Nonfinite or duplicate q values")
    require(omega.shape == (801,) and close(omega, np.linspace(0, 4, 801)), "Frequency grid mismatch")
    require(spectrum.shape == (len(q), len(omega)) and np.isfinite(spectrum).all(), "Invalid spectrum")
    metrics = csv_rows(directory / "metrics.csv")
    require(len(metrics) == len(q), "Metrics row count mismatch")
    require(close([r["q_over_pi"] for r in metrics], q / np.pi), "Metrics q order mismatch")
    require(all(np.isfinite(list(r.values())).all() for r in metrics), "Nonfinite metrics")
    correlations = {}
    for momentum in selected_q:
        matches = np.flatnonzero(np.isclose(q / np.pi, momentum, atol=ROUND_TOL, rtol=0))
        require(len(matches) == 1, "Missing or duplicate selected q")
        index = int(matches[0])
        path = directory / f"q{index + 1:03}_correlation.csv"
        require(path.is_file(), f"Missing completed correlation: {path}")
        hashes[path.name] = digest(path)
        paths.append(path)
        data = np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2)
        nsteps = int(round(meta["tmax"] / meta["dt"]))
        require(data.shape == (nsteps + 1, 4) and np.isfinite(data).all(), "Correlation shape or finiteness failure")
        require(close(data[:, 0], np.arange(nsteps + 1) * meta["dt"]), "Correlation time grid mismatch")
        row = metrics[index]
        c0 = row["source_norm"]
        require(c0 > 0 and close(data[0, 1:], [c0, 0, c0]), "Initial correlation/source mismatch")
        require(np.all(data[:, 3] >= 0), "Negative norm squared")
        norm_drift = float(np.max(np.abs(data[:, 3] - c0)) / c0)
        require(close(norm_drift, row["relative_norm_drift"]), "Reported norm drift mismatch")
        require(close(abs(c0 - row["expected_static_norm"]), row["source_norm_error"]),
                "Reported source error mismatch")
        require(close(float(spectrum[index].min()), row["min_spectrum"]), "Reported spectrum minimum mismatch")
        correlations[index] = {"norm_drift": norm_drift, "source_relative_error": row["source_norm_error"] / c0,
                               "norm_api_relative_error": row["norm_api_max_relative_error"]}
    require(all(digest(p) == hashes[p.name] for p in paths), f"Inputs changed during read: {directory.name}")
    return {"directory": str(directory), "metadata": meta, "q": q, "omega": omega,
            "spectrum": spectrum, "metrics": metrics, "correlations": correlations,
            "sha256": hashes, "actual_q_points": len(q), "nominal_q_points": meta["q_points"]}


def relative_l2(a: np.ndarray, reference: np.ndarray) -> float:
    denominator = float(np.linalg.norm(reference))
    require(denominator > 0, "Relative L2 undefined for zero reference")
    return float(np.linalg.norm(a - reference) / denominator)


def compare(base: dict, refined: dict, knob: str, q_over_pi: float, plan: dict) -> dict:
    for key in FIXED_KEYS:
        require(base["metadata"][key] == refined["metadata"][key], f"Fixed metadata mismatch: {key}")
    a_meta, b_meta = base["metadata"], refined["metadata"]
    if knob == "chi":
        require(a_meta["dt"] == b_meta["dt"] and a_meta["tebd_maxdim"] < b_meta["tebd_maxdim"],
                "Chi comparison changed dt or did not increase chi")
    elif knob == "dt":
        require(a_meta["tebd_maxdim"] == b_meta["tebd_maxdim"] and a_meta["dt"] == 2 * b_meta["dt"],
                "Dt comparison changed chi or did not halve dt")
    else:
        raise ValueError("Unknown control knob")
    require(np.array_equal(base["omega"], refined["omega"]), "Pair frequency grid mismatch")
    indices = []
    for run in (base, refined):
        match = np.flatnonzero(np.isclose(run["q"] / np.pi, q_over_pi, atol=ROUND_TOL, rtol=0))
        require(len(match) == 1, "Pair q matching is not unique")
        indices.append(int(match[0]))
    i, j = indices
    a, b = base["spectrum"][i], refined["spectrum"][j]
    c0_a, c0_b = base["metrics"][i]["source_norm"], refined["metrics"][j]["source_norm"]
    source_difference = abs(c0_a - c0_b) / c0_b
    require(source_difference < SAME_SOURCE_TOL, "Same-ground source weight mismatch")
    omega, limits = base["omega"], plan["thresholds"]
    low = (omega >= plan["bands_J1"][0][0]) & (omega <= plan["bands_J1"][0][1])
    full_error, low_error = relative_l2(a, b), relative_l2(a[low], b[low])
    peak_a, peak_b = float(omega[np.argmax(a)]), float(omega[np.argmax(b)])
    peak_shift = abs(peak_a - peak_b)
    bands = []
    for lower, upper in plan["bands_J1"]:
        require(any(abs(omega - lower) <= ROUND_TOL) and any(abs(omega - upper) <= ROUND_TOL),
                "Band endpoint absent from grid")
        mask = (omega >= lower) & (omega <= upper)
        wa, wb = float(np.trapezoid(a[mask], omega[mask])), float(np.trapezoid(b[mask], omega[mask]))
        absolute = abs(wa - wb)
        allowed = max(limits["band_weight_relative"] * abs(wb), limits["band_absolute_floor_C0"] * c0_b)
        bands.append({"interval_J1": [lower, upper], "base_weight": wa, "reference_weight": wb,
                      "absolute_error": absolute, "relative_error": absolute / abs(wb) if wb else None,
                      "absolute_error_over_C0": absolute / c0_b, "allowed_absolute_error": allowed,
                      "passed": absolute <= allowed})
    diagnostics = {"base": base["correlations"][i], "reference": refined["correlations"][j]}
    maximum_drift = max(diagnostics["base"]["norm_drift"], diagnostics["reference"]["norm_drift"])
    gates = {"full_l2": full_error < limits["spectrum_relative_l2"],
             "low_l2": low_error < limits["low_spectrum_relative_l2"],
             "band_weights": all(band["passed"] for band in bands),
             "peak_shift": peak_shift <= limits["main_peak_shift_J1"] + ROUND_TOL,
             "norm_drift": maximum_drift < limits["norm_drift"]}
    return {"status": "pass" if all(gates.values()) else "fail", "q_over_pi": q_over_pi,
            "knob": knob, "base_directory": base["directory"], "reference_directory": refined["directory"],
            "full_relative_l2": full_error, "low_relative_l2": low_error,
            "bands": bands, "base_peak_J1": peak_a, "reference_peak_J1": peak_b,
            "main_peak_shift_J1": peak_shift, "maximum_norm_drift": maximum_drift,
            "relative_source_weight_difference": source_difference, "diagnostics": diagnostics,
            "gates": gates, "integrity_passed": True,
            "parameter_change": {"base_dt": a_meta["dt"], "reference_dt": b_meta["dt"],
                                 "base_chi": a_meta["tebd_maxdim"], "reference_chi": b_meta["tebd_maxdim"]}}


def audit(root: Path, plan_path: Path) -> dict:
    plan_hash = digest(plan_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    jobs = validate_plan(plan)
    check_hash(root / "scripts/compute_fullq_dsf.jl", plan["driver_sha256"])
    for job in jobs.values():
        check_hash(Path(job["seed"]), job["seed_sha256"])
    old = root / "results/fullq_dsf_20261001"
    controls = plan_path.parent
    runs, unavailable = {}, {}
    for sign, alpha in (("positive", 0.5), ("negative", -0.5)):
        suffix = "" if sign == "positive" else "_local"
        seed = Path(jobs[f"{sign}_chi"]["seed"])
        specifications = [
            ("baseline", old / f"L40_{sign}{suffix}", np.linspace(0, 2, 41).tolist(), [0.2, 0.6, 1.0], 0.05, 192, 41),
            ("old_check", old / f"L40_{sign}_check{suffix}", [0.4, 0.7, 1, 1.3, 1.6], [1.0], 0.025, 256, 5),
            ("chi", controls / f"{sign}_chi", [0.2, 0.6, 1], [0.2, 0.6, 1], 0.05, 256, 3),
            ("dt", controls / f"{sign}_dt", [0.2, 0.6], [0.2, 0.6], 0.025, 256, 3),
        ]
        for role, directory, grid, selected, dt, chi, nominal_q in specifications:
            name = f"{sign}_{role}"
            expected = {"alpha": alpha, "beta": 0.5, "L": 40, "n_units": 8, "tmax": 60,
                        "dt": dt, "tebd_maxdim": chi, "q_points": nominal_q}
            try:
                runs[name] = load_run(directory, grid, selected, expected, seed,
                                      baseline_generated=(sign == "positive" and role == "baseline"))
            except PendingRun as error:
                unavailable[name] = {"status": "pending", "reason": str(error)}
            except (ValueError, KeyError, OSError) as error:
                unavailable[name] = {"status": "fail", "reason": str(error)}
    comparisons = []
    for sign in ("positive", "negative"):
        for knob in ("chi", "dt"):
            for q in (0.2, 0.6, 1.0):
                a = f"{sign}_baseline" if knob == "chi" else f"{sign}_chi"
                b = f"{sign}_chi" if knob == "chi" else f"{sign}_{'old_check' if q == 1 else 'dt'}"
                identity = {"id": f"{sign}_{knob}_q{q:g}", "sign": sign, "knob": knob, "q_over_pi": q}
                missing = {n: unavailable[n] for n in (a, b) if n in unavailable}
                if missing:
                    status = "fail" if any(v["status"] == "fail" for v in missing.values()) else "pending"
                    comparisons.append({**identity, "status": status, "unavailable": missing})
                    continue
                try:
                    comparisons.append({**identity, **compare(runs[a], runs[b], knob, q, plan)})
                except (ValueError, KeyError) as error:
                    comparisons.append({**identity, "status": "fail", "integrity_passed": False, "reason": str(error)})
    counts = {status: sum(row["status"] == status for row in comparisons) for status in ("pass", "fail", "pending")}
    status = "fail" if counts["fail"] else "partial" if counts["pending"] else "pass"
    check_hash(plan_path, plan_hash)
    check_hash(root / "scripts/compute_fullq_dsf.jl", plan["driver_sha256"])
    for job in jobs.values():
        check_hash(Path(job["seed"]), job["seed_sha256"])
    return {"schema_version": 1, "status": status, "counts": counts, "expected_comparisons": 12,
            "scope": plan["scope"], "plan_path": str(plan_path), "plan_sha256": plan_hash,
            "thresholds": plan["thresholds"], "bands_J1": plan["bands_J1"],
            "band_gate_formula": "abs(Wbase-Wref) <= max(band_weight_relative*abs(Wref), band_absolute_floor_C0*C0ref)",
            "integrity_tolerances": {"same_source_relative": SAME_SOURCE_TOL,
                                     "origin": "Inherited from scripts/audit_fullq_dsf.py; not a new convergence threshold",
                                     "grid_roundoff_absolute": ROUND_TOL},
            "norm_api_error_role": "Reported diagnostic only; no new physical acceptance threshold",
            "runtime_matching_required": True, "thermodynamic_convergence_claim": False,
            "long_time_convergence_claim": False, "driver_and_seed_hashes_verified": True,
            "raw_input_hash_role": "Read-time snapshots with before/after stability checks, not historical content-hash anchors",
            "run_inputs": {name: {k: run[k] for k in ("directory", "sha256", "actual_q_points", "nominal_q_points")}
                           for name, run in runs.items()}, "unavailable_runs": unavailable,
            "comparisons": comparisons, "script_sha256": digest(Path(__file__))}


def exit_code(result: dict, require_complete: bool) -> int:
    if result["status"] == "fail":
        return 1
    return 2 if require_complete and result["status"] != "pass" else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=ROOT / "results/submission_20261002/dsf_controls/plan.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/submission_20261002/dsf_audit")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    try:
        result = audit(ROOT, args.plan)
    except (ValueError, KeyError, OSError) as error:
        result = {"status": "fail", "counts": {"pass": 0, "fail": 12, "pending": 0},
                  "expected_comparisons": 12, "integrity_passed": False, "reason": str(error)}
    args.output.mkdir(parents=True, exist_ok=True)
    temporary = args.output / "audit.json.tmp"
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(args.output / "audit.json")
    summary = {key: result[key] for key in ("status", "counts", "expected_comparisons")}
    if "reason" in result:
        summary["reason"] = result["reason"]
    summary["output"] = str(args.output / "audit.json")
    print(json.dumps(summary, ensure_ascii=False))
    raise SystemExit(exit_code(result, args.require_complete))


if __name__ == "__main__":
    main()
