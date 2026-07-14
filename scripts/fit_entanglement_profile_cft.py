"""用五种切键共享斜率拟合开边界 CFT 中心荷。"""

import csv
import glob
import os
import re

import matplotlib.pyplot as plt
import numpy as np


BETA_TARGET = 0.5
L_TARGET = 100
FIT_FRACTION = (0.2, 0.8)
PATTERN = re.compile(
    r"profile_a(?P<alpha>[-+0-9.]+)_b(?P<beta>[-+0-9.]+)_L(?P<L>[0-9]+)"
)


def load_profiles():
    profiles = {}
    for path in glob.glob("data/entanglement_profiles/profile_*.csv"):
        match = PATTERN.search(os.path.basename(path))
        if match is None:
            continue

        alpha = float(match.group("alpha"))
        beta = float(match.group("beta"))
        L = int(match.group("L"))
        if not np.isclose(beta, BETA_TARGET) or L != L_TARGET:
            continue

        rows = []
        with open(path, newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                rows.append((int(row["bond"]), float(row["S"])))
        profiles[alpha] = rows
    return profiles


def joint_cft_fit(rows, L):
    selected = [
        (bond, entropy)
        for bond, entropy in rows
        if FIT_FRACTION[0] * L <= bond <= FIT_FRACTION[1] * L
    ]
    bonds = np.asarray([row[0] for row in selected])
    entropy = np.asarray([row[1] for row in selected])
    chord = np.log(
        (2.0 * L / np.pi) * np.sin(np.pi * bonds / L)
    )
    residue = bonds % 5

    design = np.zeros((len(bonds), 6))
    design[:, 0] = chord
    for index in range(5):
        design[:, index + 1] = residue == index

    coefficients, _, _, _ = np.linalg.lstsq(design, entropy, rcond=None)
    prediction = design @ coefficients
    residual = entropy - prediction
    degrees = len(entropy) - design.shape[1]
    variance = np.sum(residual**2) / degrees
    covariance = variance * np.linalg.inv(design.T @ design)

    slope = coefficients[0]
    slope_error = np.sqrt(covariance[0, 0])
    total = np.sum((entropy - np.mean(entropy)) ** 2)
    r_squared = 1.0 - np.sum(residual**2) / total
    return 6.0 * slope, 6.0 * slope_error, r_squared


def write_results(results):
    output = (
        f"data/entanglement_profiles/cft_profile_fit_"
        f"b{BETA_TARGET:.1f}_L{L_TARGET}.csv"
    )
    with open(output, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["alpha", "beta", "L", "c_eff", "c_error", "r_squared"])
        for alpha, c_eff, c_error, r_squared in results:
            writer.writerow(
                [
                    f"{alpha:.6f}",
                    f"{BETA_TARGET:.6f}",
                    L_TARGET,
                    f"{c_eff:.10f}",
                    f"{c_error:.10f}",
                    f"{r_squared:.10f}",
                ]
            )
    print(f"已输出：{output}")


def plot_results(results):
    alpha = np.asarray([row[0] for row in results])
    charge = np.asarray([row[1] for row in results])
    error = np.asarray([row[2] for row in results])

    fig, axis = plt.subplots(figsize=(7, 4.8))
    axis.errorbar(
        alpha,
        charge,
        yerr=error,
        marker="o",
        linewidth=1.4,
        capsize=3,
        color="tab:blue",
    )
    axis.axhline(0.5, color="tab:orange", linestyle="--", label="c=1/2")
    axis.axhline(1.0, color="tab:red", linestyle="--", label="c=1")
    axis.axvline(0.17, color="tab:purple", linestyle=":")
    axis.axvline(0.30, color="tab:green", linestyle=":")
    axis.set_xlabel(r"$\alpha=J_2/J_1$")
    axis.set_ylabel(r"$c_{\mathrm{profile}}$")
    axis.set_title(
        rf"CFT profile fit ($\beta={BETA_TARGET}, L={L_TARGET}$)"
    )
    axis.grid(alpha=0.25)
    axis.legend()
    fig.tight_layout()

    basename = (
        f"entanglement_profile_cft_b{BETA_TARGET:.1f}_L{L_TARGET}"
    )
    fig.savefig(f"figures/{basename}.pdf")
    fig.savefig(f"figures/{basename}.png")
    plt.close(fig)
    print(f"已输出：figures/{basename}.pdf")


def main():
    profiles = load_profiles()
    if not profiles:
        raise RuntimeError("没有找到目标纠缠剖面")

    results = []
    for alpha, rows in sorted(profiles.items()):
        c_eff, c_error, r_squared = joint_cft_fit(rows, L_TARGET)
        results.append((alpha, c_eff, c_error, r_squared))
        print(
            f"alpha={alpha:+.3f}: c={c_eff:.4f} ± {c_error:.4f}, "
            f"R2={r_squared:.4f}"
        )

    write_results(results)
    plot_results(results)


if __name__ == "__main__":
    main()
