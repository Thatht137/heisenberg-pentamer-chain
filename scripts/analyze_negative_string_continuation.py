"""拟合负 alpha 低能延拓态的弦关联。"""

import csv
import glob
import os
import re
from collections import defaultdict

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


INPUT_PATTERN = "data/negative_string_continuation/profiles_b0.50_L*.csv"
SUMMARY_PATH = "data/negative_string_continuation/fit_summary_b0.5.csv"
FIGURE_STEM = "figures/negative_string_continuation_b0.5"


def load_profiles():
    profiles = defaultdict(lambda: defaultdict(list))
    metadata = {}
    for path in glob.glob(INPUT_PATTERN):
        match = re.search(r"_L([0-9]+)", path)
        if not match:
            continue
        length = int(match.group(1))
        with open(path, newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                alpha = float(row["alpha"])
                distance = int(row["distance_units"])
                profiles[(length, alpha)][distance].append(
                    float(row["O_envelope"])
                )
                metadata[(length, alpha)] = {
                    "energy": float(row["energy"]),
                    "margin": int(row["margin"]),
                    "maxdim": int(row["maxdim"]),
                }
    if not profiles:
        raise RuntimeError("没有找到负侧延拓弦关联数据")
    return profiles, metadata


def summarize_profile(by_distance):
    rows = []
    for distance, values in sorted(by_distance.items()):
        array = np.asarray(values)
        rows.append(
            (
                distance,
                np.mean(array),
                np.std(array) / np.sqrt(len(array)),
                len(array),
            )
        )
    return rows


def fit_models(summary, length):
    distance = np.asarray([row[0] for row in summary], dtype=float)
    value = np.asarray([row[1] for row in summary], dtype=float)
    max_fit_distance = 2 * (length // 5) / 3
    valid = (
        (distance >= 3)
        & (distance <= max_fit_distance)
        & (value > 0)
    )
    distance = distance[valid]
    value = value[valid]
    if len(distance) < 3:
        return None

    log_value = np.log(value)
    models = {}

    constant = np.full_like(log_value, np.mean(log_value))
    models["constant"] = {
        "prediction": constant,
        "parameters": (np.exp(np.mean(log_value)), np.nan),
        "k": 1,
    }

    power_coeff = np.polyfit(np.log(distance), log_value, 1)
    models["power"] = {
        "prediction": np.polyval(power_coeff, np.log(distance)),
        "parameters": (np.exp(power_coeff[1]), -power_coeff[0]),
        "k": 2,
    }

    exponential_coeff = np.polyfit(distance, log_value, 1)
    inverse_slope = (
        -1.0 / exponential_coeff[0]
        if exponential_coeff[0] < 0
        else np.nan
    )
    models["exponential"] = {
        "prediction": np.polyval(exponential_coeff, distance),
        "parameters": (np.exp(exponential_coeff[1]), inverse_slope),
        "k": 2,
    }

    for model in models.values():
        residual = log_value - model["prediction"]
        rss = max(np.sum(residual**2), 1e-30)
        model["rms_log"] = np.sqrt(np.mean(residual**2))
        model["aic"] = len(distance) * np.log(rss / len(distance)) + 2 * model["k"]

    winner = min(models, key=lambda name: models[name]["aic"])
    return {
        "distance": distance,
        "value": value,
        "models": models,
        "winner": winner,
        "max_fit_distance": max_fit_distance,
    }


def build_summary(profiles, metadata):
    rows = []
    fits = {}
    for key in sorted(profiles):
        length, alpha = key
        profile = summarize_profile(profiles[key])
        fit = fit_models(profile, length)
        fits[key] = (profile, fit)
        base = {
            "L": length,
            "alpha": alpha,
            "energy": metadata[key]["energy"],
            "margin": metadata[key]["margin"],
            "maxdim": metadata[key]["maxdim"],
            "n_fit": 0,
            "max_fit_distance": 2 * (length // 5) / 3,
            "winner": "insufficient",
            "constant": np.nan,
            "eta_power": np.nan,
            "xi_exponential": np.nan,
        }
        if fit is not None:
            models = fit["models"]
            base.update(
                {
                    "n_fit": len(fit["distance"]),
                    "max_fit_distance": fit["max_fit_distance"],
                    "winner": fit["winner"],
                    "constant": models["constant"]["parameters"][0],
                    "eta_power": models["power"]["parameters"][1],
                    "xi_exponential": models["exponential"]["parameters"][1],
                    "constant_rms_log": models["constant"]["rms_log"],
                    "power_rms_log": models["power"]["rms_log"],
                    "exponential_rms_log": models["exponential"]["rms_log"],
                    "constant_aic": models["constant"]["aic"],
                    "power_aic": models["power"]["aic"],
                    "exponential_aic": models["exponential"]["aic"],
                }
            )
        rows.append(base)
    return rows, fits


def export_summary(rows):
    os.makedirs(os.path.dirname(SUMMARY_PATH), exist_ok=True)
    fieldnames = [
        "L",
        "alpha",
        "energy",
        "margin",
        "maxdim",
        "n_fit",
        "max_fit_distance",
        "winner",
        "constant",
        "eta_power",
        "xi_exponential",
        "constant_rms_log",
        "power_rms_log",
        "exponential_rms_log",
        "constant_aic",
        "power_aic",
        "exponential_aic",
    ]
    with open(SUMMARY_PATH, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def model_curve(fit, model_name, distance):
    model = fit["models"][model_name]
    amplitude, scale = model["parameters"]
    if model_name == "constant":
        return np.full_like(distance, amplitude)
    if model_name == "power":
        return amplitude * distance ** (-scale)
    return amplitude * np.exp(-distance / scale)


def plot_results(fits):
    mpl.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 7,
            "axes.labelsize": 8,
            "legend.fontsize": 6,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "pdf.fonttype": 42,
        }
    )
    alphas = sorted({key[1] for key in fits})
    lengths = sorted({key[0] for key in fits})
    colors = dict(zip(lengths, ("#56B4E9", "#0072B2", "#D55E00")))
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(7.2, 5.4),
        layout="constrained",
    )

    for axis, alpha in zip(axes.flat, alphas):
        for length in lengths:
            profile, fit = fits[(length, alpha)]
            distance = np.asarray([row[0] for row in profile])
            value = np.asarray([row[1] for row in profile])
            error = np.asarray([row[2] for row in profile])
            axis.errorbar(
                distance,
                value,
                yerr=error,
                fmt="o",
                ms=3,
                capsize=2,
                color=colors[length],
                label=rf"$L={length}$",
            )
            if fit is not None:
                curve_distance = np.linspace(
                    fit["distance"].min(),
                    fit["distance"].max(),
                    120,
                )
                axis.plot(
                    curve_distance,
                    model_curve(fit, fit["winner"], curve_distance),
                    "-",
                    lw=1,
                    color=colors[length],
                )
        axis.set_yscale("log")
        axis.set_xscale("log")
        axis.set_xlabel("Odd distance (unit cells)")
        axis.set_ylabel(r"$\widetilde{O}_{\mathrm{str}}^z(r)$")
        axis.set_title(rf"$\alpha={alpha:+.2f}$")
        axis.grid(alpha=0.2)
        axis.legend()

    os.makedirs(os.path.dirname(FIGURE_STEM), exist_ok=True)
    fig.savefig(f"{FIGURE_STEM}.pdf")
    fig.savefig(f"{FIGURE_STEM}.png", dpi=300)
    plt.close(fig)


def main():
    profiles, metadata = load_profiles()
    rows, fits = build_summary(profiles, metadata)
    export_summary(rows)
    plot_results(fits)
    print(f"已输出：{SUMMARY_PATH}")
    print(f"已输出：{FIGURE_STEM}.pdf")


if __name__ == "__main__":
    main()
