"""沿 beta=0.5 切线估计有效中心荷。"""

import csv
import os
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


SOURCE = "data/finite_size/finite_size_all.csv"
BETA_TARGET = 0.5
FIT_SIZES = (60, 80, 100)


def load_entropy():
    grouped = defaultdict(list)
    with open(SOURCE, newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            beta = float(row["beta"])
            if not np.isclose(beta, BETA_TARGET):
                continue
            alpha = float(row["alpha"])
            grouped[alpha].append((int(row["L"]), float(row["S_L2"])))

    for values in grouped.values():
        values.sort()
    return grouped


def fit_central_charge(values):
    selected = [(L, entropy) for L, entropy in values if L in FIT_SIZES]
    if len(selected) < 3:
        return None

    sizes = np.asarray([item[0] for item in selected], dtype=float)
    entropy = np.asarray([item[1] for item in selected])
    log_sizes = np.log(sizes)

    slope, intercept = np.polyfit(log_sizes, entropy, 1)
    prediction = slope * log_sizes + intercept
    residual = entropy - prediction
    rss = np.sum(residual**2)
    centered = log_sizes - np.mean(log_sizes)
    slope_error = np.sqrt((rss / (len(sizes) - 2)) / np.sum(centered**2))

    total = np.sum((entropy - np.mean(entropy)) ** 2)
    r_squared = 1.0 - rss / total if total > 0 else 1.0
    return 6.0 * slope, 6.0 * slope_error, r_squared


def write_results(results):
    output = f"data/finite_size/effective_central_charge_b{BETA_TARGET:.1f}.csv"
    with open(output, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["alpha", "beta", "c_eff", "c_error", "r_squared"])
        for alpha, c_eff, c_error, r_squared in results:
            writer.writerow(
                [
                    f"{alpha:.6f}",
                    f"{BETA_TARGET:.6f}",
                    f"{c_eff:.10f}",
                    f"{c_error:.10f}",
                    f"{r_squared:.10f}",
                ]
            )
    print(f"已输出：{output}")


def configure_style():
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 11,
            "axes.labelsize": 12,
            "axes.titlesize": 13,
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
        }
    )


def plot_results(grouped, results):
    fig, (axis_c, axis_s) = plt.subplots(1, 2, figsize=(12, 4.8))

    alphas = np.asarray([row[0] for row in results])
    central_charge = np.asarray([row[1] for row in results])
    errors = np.asarray([row[2] for row in results])

    axis_c.errorbar(
        alphas,
        central_charge,
        yerr=errors,
        marker="o",
        markersize=3,
        linewidth=1,
        capsize=2,
        color="tab:blue",
    )
    axis_c.axhline(0, color="0.5", linewidth=0.8)
    axis_c.axhline(1, color="tab:red", linestyle="--", linewidth=1)
    axis_c.axvline(0, color="0.5", linestyle=":", linewidth=1)
    axis_c.set_xlabel(r"$\alpha=J_2/J_1$")
    axis_c.set_ylabel(r"$c_{\mathrm{eff}}$")
    axis_c.set_title(rf"Effective central charge ($\beta={BETA_TARGET}$)")
    axis_c.set_ylim(-0.5, 1.8)
    axis_c.grid(alpha=0.25)

    representative = [-0.05, 0.05, 0.25, 0.50, 1.00]
    colors = plt.cm.viridis(np.linspace(0.1, 0.9, len(representative)))
    for target, color in zip(representative, colors):
        alpha = min(grouped, key=lambda value: abs(value - target))
        selected = [
            (L, entropy)
            for L, entropy in grouped[alpha]
            if L in FIT_SIZES
        ]
        sizes = np.asarray([item[0] for item in selected])
        entropy = np.asarray([item[1] for item in selected])
        axis_s.plot(
            np.log(sizes),
            entropy,
            marker="o",
            linewidth=1.4,
            color=color,
            label=rf"$\alpha={alpha:+.2f}$",
        )

    axis_s.set_xlabel(r"$\ln L$")
    axis_s.set_ylabel(r"$S(L/2)$")
    axis_s.set_title("Half-chain entropy scaling")
    axis_s.grid(alpha=0.25)
    axis_s.legend(fontsize=9)

    fig.tight_layout()
    os.makedirs("figures", exist_ok=True)
    basename = f"effective_central_charge_b{BETA_TARGET:.1f}"
    fig.savefig(f"figures/{basename}.pdf")
    fig.savefig(f"figures/{basename}.png")
    plt.close(fig)
    print(f"已输出：figures/{basename}.pdf")


def main():
    grouped = load_entropy()
    results = []
    for alpha, values in sorted(grouped.items()):
        fit = fit_central_charge(values)
        if fit is not None:
            results.append((alpha, *fit))

    write_results(results)
    configure_style()
    plot_results(grouped, results)


if __name__ == "__main__":
    main()
