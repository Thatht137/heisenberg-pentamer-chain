"""
分析负 alpha 区域的双向参数连续关联扫描。
"""

import csv
import glob
import os
import re
from collections import defaultdict

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


INPUT_PATTERN = (
    "data/negative_correlation_continuation/"
    "profiles_b0.50_L*.csv"
)
SUMMARY_PATH = (
    "data/negative_correlation_continuation/"
    "summary_b0.5.csv"
)
FIGURE_STEM = (
    "figures/negative_correlation_continuation_b0.5"
)


def load_profiles():
    profiles = {}
    for path in glob.glob(INPUT_PATTERN):
        match = re.search(r"_L([0-9]+)", path)
        if not match:
            continue
        length = int(match.group(1))
        grouped = defaultdict(list)
        with open(path, newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                grouped[(float(row["alpha"]), row["branch"])].append(row)

        for (alpha, branch), rows in grouped.items():
            distance = np.asarray(
                [int(row["distance"]) for row in rows]
            )
            correlation = np.asarray(
                [float(row["C_mean"]) for row in rows]
            )
            profiles[(length, alpha, branch)] = {
                "distance": distance,
                "correlation": correlation,
                "energy": float(rows[0]["energy"]),
            }
    return profiles


def cell_envelope(distance, correlation, length):
    envelope_distance = []
    envelope_value = []
    for start in range(5, length // 3 + 1, 5):
        mask = (
            (distance >= start)
            & (distance < start + 5)
            & (distance <= length // 3)
        )
        if not np.any(mask):
            continue
        local_distance = distance[mask]
        local_value = np.abs(correlation[mask])
        index = np.argmax(local_value)
        envelope_distance.append(local_distance[index])
        envelope_value.append(local_value[index])
    return np.asarray(envelope_distance), np.asarray(envelope_value)


def profile_metrics(distance, correlation, length):
    qvals = np.linspace(0.0, np.pi, 2001)
    structure = np.asarray([
        np.sum(correlation * np.cos(qval * distance))
        for qval in qvals
    ])
    q_peak = qvals[np.argmax(structure)] / np.pi

    envelope_distance, envelope_value = cell_envelope(
        distance,
        correlation,
        length,
    )
    exponent = np.nan
    power_rms = np.nan
    exponential_rms = np.nan
    correlation_length = np.nan
    if len(envelope_distance) >= 3:
        log_distance = np.log(envelope_distance)
        log_value = np.log(envelope_value)
        power_fit = np.polyfit(log_distance, log_value, 1)
        exponential_fit = np.polyfit(
            envelope_distance,
            log_value,
            1,
        )
        exponent = -power_fit[0]
        power_rms = np.sqrt(np.mean(
            (log_value - np.polyval(power_fit, log_distance)) ** 2
        ))
        exponential_rms = np.sqrt(np.mean(
            (
                log_value
                - np.polyval(exponential_fit, envelope_distance)
            ) ** 2
        ))
        if exponential_fit[0] < 0:
            correlation_length = -1.0 / exponential_fit[0]

    return {
        "q_peak_over_pi": q_peak,
        "eta": exponent,
        "power_rms_log": power_rms,
        "exponential_rms_log": exponential_rms,
        "rms_ratio_exp_over_power": exponential_rms / power_rms,
        "xi_exponential": correlation_length,
        "envelope_distance": envelope_distance,
        "envelope_value": envelope_value,
    }


def build_summary(profiles):
    rows = []
    keys = sorted(profiles)
    for length, alpha, branch in keys:
        profile = profiles[(length, alpha, branch)]
        metrics = profile_metrics(
            profile["distance"],
            profile["correlation"],
            length,
        )
        opposite = (
            "backward" if branch == "forward" else "forward"
        )
        opposite_profile = profiles.get((length, alpha, opposite))
        energy_difference = np.nan
        if opposite_profile:
            energy_difference = (
                profile["energy"] - opposite_profile["energy"]
            )
        rows.append({
            "L": length,
            "alpha": alpha,
            "branch": branch,
            "energy": profile["energy"],
            "energy_minus_opposite": energy_difference,
            "q_peak_over_pi": metrics["q_peak_over_pi"],
            "eta": metrics["eta"],
            "power_rms_log": metrics["power_rms_log"],
            "exponential_rms_log": metrics["exponential_rms_log"],
            "rms_ratio_exp_over_power": (
                metrics["rms_ratio_exp_over_power"]
            ),
            "xi_exponential": metrics["xi_exponential"],
        })
    return rows


def export_summary(rows):
    os.makedirs(os.path.dirname(SUMMARY_PATH), exist_ok=True)
    with open(SUMMARY_PATH, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def plot_summary(profiles, rows):
    mpl.rcParams.update({
        "font.family": "Arial",
        "font.size": 7,
        "axes.labelsize": 8,
        "legend.fontsize": 6.5,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    })

    lengths = sorted({row["L"] for row in rows})
    colors = {
        length: color
        for length, color in zip(
            lengths,
            ("#56B4E9", "#0072B2", "#D55E00"),
        )
    }
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(7.2, 5.4),
        layout="constrained",
    )

    for length in lengths:
        forward = sorted(
            (
                row for row in rows
                if row["L"] == length
                and row["branch"] == "forward"
            ),
            key=lambda row: row["alpha"],
        )
        alphas = np.asarray([row["alpha"] for row in forward])
        lower_energy = np.asarray([
            -row["energy_minus_opposite"] for row in forward
        ])
        axes[0, 0].plot(
            alphas,
            np.maximum(lower_energy, 1e-10),
            "o-",
            color=colors[length],
            label=rf"$L={length}$",
        )
        axes[0, 1].plot(
            alphas,
            [row["q_peak_over_pi"] for row in forward],
            "o-",
            color=colors[length],
        )

        valid = [
            row for row in forward
            if np.isfinite(row["eta"])
        ]
        if valid:
            axes[1, 0].plot(
                [row["alpha"] for row in valid],
                [row["eta"] for row in valid],
                "o-",
                color=colors[length],
            )

    axes[0, 0].set_yscale("log")
    axes[0, 0].set_ylabel(r"$E_{\rm backward}-E_{\rm forward}$")
    axes[0, 0].legend(frameon=False)
    axes[0, 1].set_ylabel(r"$q_{\rm peak}/\pi$")
    axes[0, 1].set_ylim(0.5, 1.05)
    axes[1, 0].set_ylabel(r"envelope exponent $\eta$")
    axes[1, 0].set_ylim(0.7, 1.15)

    selected = (-0.50, -0.25, -0.10, -0.05, -0.025)
    palette = plt.cm.viridis(np.linspace(0.08, 0.92, len(selected)))
    for alpha, color in zip(selected, palette):
        key = (80, alpha, "forward")
        if key not in profiles:
            continue
        profile = profiles[key]
        distance, envelope = cell_envelope(
            profile["distance"],
            profile["correlation"],
            80,
        )
        axes[1, 1].loglog(
            distance,
            envelope,
            "o-",
            color=color,
            label=rf"$\alpha={alpha:g}$",
        )

    axes[1, 1].set_ylabel(r"$|C(r)|$ envelope")
    axes[1, 1].legend(frameon=False, ncol=2)
    for label, axis in zip(("a", "b", "c", "d"), axes.flat):
        axis.text(
            0.03,
            0.95,
            f"({label})",
            transform=axis.transAxes,
            fontweight="bold",
            va="top",
        )
        axis.set_xlabel(r"$\alpha$" if label != "d" else r"$r$")
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)

    os.makedirs("figures", exist_ok=True)
    fig.savefig(f"{FIGURE_STEM}.pdf", bbox_inches="tight")
    fig.savefig(f"{FIGURE_STEM}.svg", bbox_inches="tight")
    fig.savefig(f"{FIGURE_STEM}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    profiles = load_profiles()
    if not profiles:
        raise RuntimeError("没有找到参数连续关联数据")
    rows = build_summary(profiles)
    export_summary(rows)
    plot_summary(profiles, rows)
    print(f"已保存: {SUMMARY_PATH}")
    print(f"已保存: {FIGURE_STEM}.pdf/.svg/.png")


if __name__ == "__main__":
    main()
