"""绘制 beta=0.5 切线的多观测量相边界诊断。"""

import csv
import os
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


BETA_TARGET = 0.5
ALPHA_WINDOW = (0.15, 0.35)
SOURCE = "data/finite_size/finite_size_all.csv"
CENTRAL_CHARGE_SOURCE = (
    f"data/finite_size/effective_central_charge_b{BETA_TARGET:.1f}.csv"
)


def load_finite_size():
    grouped = defaultdict(list)
    with open(SOURCE, newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if not np.isclose(float(row["beta"]), BETA_TARGET):
                continue
            grouped[int(row["L"])].append(
                (
                    float(row["alpha"]),
                    float(row["energy"]) / int(row["L"]),
                    float(row["O_str"]),
                    float(row["S_L2"]),
                )
            )

    for values in grouped.values():
        values.sort()
    return grouped


def load_central_charge():
    rows = []
    with open(CENTRAL_CHARGE_SOURCE, newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            rows.append(
                (
                    float(row["alpha"]),
                    float(row["c_eff"]),
                    float(row["c_error"]),
                )
            )
    return rows


def dense_window(values):
    array = np.asarray(values)
    mask = (
        (array[:, 0] >= ALPHA_WINDOW[0])
        & (array[:, 0] <= ALPHA_WINDOW[1])
    )
    return array[mask]


def derivative_diagnostics(values):
    array = dense_window(values)
    alpha = array[:, 0]
    energy = array[:, 1]
    string_order = array[:, 2]
    entropy = array[:, 3]

    first_energy = np.gradient(energy, alpha)
    second_energy = np.gradient(first_energy, alpha)
    entropy_derivative = np.gradient(entropy, alpha)
    string_derivative = np.gradient(string_order, alpha)
    return (
        alpha,
        np.abs(second_energy),
        np.abs(entropy_derivative),
        np.abs(string_derivative),
    )


def peak_positions(grouped):
    rows = []
    for L, values in sorted(grouped.items()):
        alpha, energy_d2, entropy_d1, string_d1 = derivative_diagnostics(values)
        rows.append(
            (
                L,
                alpha[np.argmax(energy_d2)],
                alpha[np.argmax(entropy_d1)],
                alpha[np.argmax(string_d1)],
            )
        )
    return rows


def write_peaks(rows):
    output = (
        f"data/finite_size/beta_{BETA_TARGET:.1f}_diagnostic_peaks.csv"
    )
    with open(output, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "L",
                "alpha_peak_energy_d2",
                "alpha_peak_entropy_d1",
                "alpha_peak_string_d1",
            ]
        )
        writer.writerows(rows)
    print(f"已输出：{output}")


def configure_style():
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 10,
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
        }
    )


def plot_diagnostics(grouped, central_charge, peaks):
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    colors = plt.cm.viridis(np.linspace(0.15, 0.85, len(grouped)))

    for color, (L, values) in zip(colors, sorted(grouped.items())):
        alpha, energy_d2, entropy_d1, string_d1 = derivative_diagnostics(
            values
        )
        axes[0, 0].plot(alpha, energy_d2, color=color, label=f"L={L}")
        axes[0, 1].plot(alpha, entropy_d1, color=color, label=f"L={L}")
        axes[1, 0].plot(alpha, string_d1, color=color, label=f"L={L}")

    charge_alpha = np.asarray([row[0] for row in central_charge])
    charge = np.asarray([row[1] for row in central_charge])
    charge_error = np.asarray([row[2] for row in central_charge])
    mask = (
        (charge_alpha >= ALPHA_WINDOW[0])
        & (charge_alpha <= ALPHA_WINDOW[1])
    )
    axes[1, 1].errorbar(
        charge_alpha[mask],
        charge[mask],
        yerr=charge_error[mask],
        marker="o",
        markersize=3,
        linewidth=1,
        capsize=2,
        color="tab:blue",
    )
    axes[1, 1].axhline(0.5, color="tab:orange", linestyle="--")
    axes[1, 1].axhline(1.0, color="tab:red", linestyle="--")

    peak_energy = np.mean([row[1] for row in peaks])
    peak_entropy = np.mean([row[2] for row in peaks])
    for axis in axes.flat:
        axis.axvline(peak_energy, color="tab:purple", linestyle=":")
        axis.axvline(peak_entropy, color="tab:green", linestyle=":")
        axis.set_xlabel(r"$\alpha=J_2/J_1$")
        axis.grid(alpha=0.25)

    axes[0, 0].set_ylabel(r"$|d^2(E/L)/d\alpha^2|$")
    axes[0, 0].set_title("Energy curvature")
    axes[0, 1].set_ylabel(r"$|dS(L/2)/d\alpha|$")
    axes[0, 1].set_title("Entropy response")
    axes[1, 0].set_ylabel(r"$|dO_{\mathrm{str}}/d\alpha|$")
    axes[1, 0].set_title("String-order response")
    axes[1, 1].set_ylabel(r"$c_{\mathrm{eff}}$")
    axes[1, 1].set_title("Effective central charge")
    axes[0, 0].legend(fontsize=8)

    fig.suptitle(
        rf"Phase diagnostics along $\beta={BETA_TARGET}$",
        fontsize=14,
    )
    fig.tight_layout()
    os.makedirs("figures", exist_ok=True)
    basename = f"phase_diagnostics_b{BETA_TARGET:.1f}"
    fig.savefig(f"figures/{basename}.pdf")
    fig.savefig(f"figures/{basename}.png")
    plt.close(fig)
    print(f"已输出：figures/{basename}.pdf")


def main():
    grouped = load_finite_size()
    central_charge = load_central_charge()
    peaks = peak_positions(grouped)
    write_peaks(peaks)
    configure_style()
    plot_diagnostics(grouped, central_charge, peaks)

    for row in peaks:
        print(
            f"L={row[0]}: energy={row[1]:.3f}, "
            f"entropy={row[2]:.3f}, string={row[3]:.3f}"
        )


if __name__ == "__main__":
    main()
