#!/usr/bin/env python3
"""汇总五轮 DMRG 数据并生成验收图表。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = ROOT / "results" / "five_rounds_20260729"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def number(row: dict[str, str], key: str) -> float:
    return float(row[key])


def relative_difference(left: float, right: float) -> float:
    scale = max(abs(left), abs(right), 1e-15)
    return abs(left - right) / scale


def main() -> None:
    round2 = rows(RUN_ROOT / "round2_smoke_fix1" / "parameter-scan.csv")
    round3 = rows(RUN_ROOT / "round3_convergence" / "parameter-scan.csv")
    round4 = rows(RUN_ROOT / "round4_validation" / "parameter-scan.csv")
    output = RUN_ROOT / "analysis"
    output.mkdir(parents=True, exist_ok=True)

    convergence: list[dict[str, object]] = []
    for length in (40, 60, 80):
        group = {int(number(row, "maxdim")): row for row in round3 if int(number(row, "L")) == length}
        medium, high = group[400], group[800]
        energy_diff = abs(number(medium, "energy_density") - number(high, "energy_density"))
        order_abs = abs(number(medium, "string_order") - number(high, "string_order"))
        order_rel = relative_difference(number(medium, "string_order"), number(high, "string_order"))
        convergence.append(
            {
                "L": length,
                "energy_density_difference_400_800": energy_diff,
                "string_order_absolute_difference_400_800": order_abs,
                "string_order_relative_difference_400_800": order_rel,
                "energy_pass": energy_diff <= 1e-6,
                "observable_pass": order_rel <= 0.02 or order_abs <= 1e-10,
                "variance_pass": number(high, "variance_per_site") <= 1e-8,
                "truncation_pass": number(high, "max_truncation_error") <= 1e-8,
                "actual_maxdim": int(number(high, "actual_maxdim")),
            }
        )

    main_rows = [row for row in round4 if row["init_mode"] == "neel"]
    alpha_023 = [row for row in round4 if abs(number(row, "alpha") - 0.23) < 1e-12]
    neel = next(row for row in alpha_023 if row["init_mode"] == "neel")
    shifted = next(row for row in alpha_023 if row["init_mode"] == "shifted")
    init_energy_diff = abs(number(neel, "energy_density") - number(shifted, "energy_density"))
    init_order_abs = abs(number(neel, "string_order") - number(shifted, "string_order"))
    init_order_rel = relative_difference(number(neel, "string_order"), number(shifted, "string_order"))

    round3_reference = next(
        row
        for row in round3
        if int(number(row, "L")) == 80 and int(number(row, "maxdim")) == 800
    )
    extension_energy_diff = abs(
        number(neel, "energy_density") - number(round3_reference, "energy_density")
    )
    extension_order_rel = relative_difference(
        number(neel, "string_order"), number(round3_reference, "string_order")
    )
    round4_cells = []
    for row in round4:
        cell_dir = RUN_ROOT / "round4_validation" / "cells" / row["cell_id"]
        round4_cells.append(
            {
                "cell_id": row["cell_id"],
                "alpha": number(row, "alpha"),
                "init_mode": row["init_mode"],
                "variance_per_site": number(row, "variance_per_site"),
                "max_truncation_error": number(row, "max_truncation_error"),
                "actual_maxdim": int(number(row, "actual_maxdim")),
                "mps_present": (cell_dir / "state.jld2").is_file(),
                "pass": number(row, "variance_per_site") <= 1e-8
                and number(row, "max_truncation_error") <= 1e-8
                and (cell_dir / "state.jld2").is_file(),
            }
        )

    summary = {
        "round2": {
            "cells": len(round2),
            "all_success": all(row["status"] == "success" for row in round2),
            "max_variance_per_site": max(number(row, "variance_per_site") for row in round2),
            "max_peak_rss_kb": max(int(number(row, "peak_rss_kb")) for row in round2),
        },
        "round3": {
            "cells": len(round3),
            "convergence": convergence,
            "all_pass": all(
                item["energy_pass"]
                and item["observable_pass"]
                and item["variance_pass"]
                and item["truncation_pass"]
                for item in convergence
            ),
        },
        "round4": {
            "cells": round4_cells,
            "all_cell_gates_pass": all(item["pass"] for item in round4_cells),
            "initial_state_energy_density_difference": init_energy_diff,
            "initial_state_string_order_absolute_difference": init_order_abs,
            "initial_state_string_order_relative_difference": init_order_rel,
            "initial_state_pass": init_energy_diff <= 1e-7
            and (init_order_rel <= 0.02 or init_order_abs <= 1e-10),
            "maxdim_800_to_1200_energy_density_difference": extension_energy_diff,
            "maxdim_800_to_1200_string_order_relative_difference": extension_order_rel,
            "extension_pass": extension_energy_diff <= 1e-6 and extension_order_rel <= 0.02,
        },
    }
    summary["overall_dmrg_acceptance"] = bool(
        summary["round2"]["all_success"]
        and summary["round3"]["all_pass"]
        and summary["round4"]["all_cell_gates_pass"]
        and summary["round4"]["initial_state_pass"]
        and summary["round4"]["extension_pass"]
    )
    (output / "acceptance_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.9))
    for length in (40, 60, 80):
        group = sorted(
            (row for row in round3 if int(number(row, "L")) == length),
            key=lambda row: number(row, "maxdim"),
        )
        dims = [number(row, "maxdim") for row in group]
        axes[0].plot(dims, [number(row, "energy_density") for row in group], "o-", label=f"L={length}")
        axes[1].plot(dims, [number(row, "string_order") for row in group], "o-", label=f"L={length}")
        axes[2].semilogy(dims, [number(row, "variance_per_site") for row in group], "o-", label=f"L={length}")
    axes[0].set_ylabel("Energy density")
    axes[1].set_ylabel("String order")
    axes[2].set_ylabel("Variance / site")
    for axis in axes:
        axis.set_xlabel("Requested maxdim")
        axis.grid(alpha=0.25)
    axes[0].legend(frameon=False)
    fig.suptitle("DMRG convergence at alpha=0.23, beta=0.5")
    fig.tight_layout()
    fig.savefig(output / "round3_convergence.png", dpi=180)
    plt.close(fig)

    main_rows.sort(key=lambda row: number(row, "alpha"))
    alphas = [number(row, "alpha") for row in main_rows]
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.9))
    axes[0].plot(alphas, [number(row, "energy_density") for row in main_rows], "o-", color="#1f4e79")
    axes[1].plot(alphas, [number(row, "string_order") for row in main_rows], "o-", color="#b54a3a")
    axes[2].plot(alphas, [number(row, "center_entropy") for row in main_rows], "o-", color="#2f7d4a")
    axes[0].set_ylabel("Energy density")
    axes[1].set_ylabel("String order")
    axes[2].set_ylabel("Center entropy")
    for axis in axes:
        axis.set_xlabel("alpha")
        axis.grid(alpha=0.25)
    fig.suptitle("Positive-alpha validation at beta=0.5, L=80")
    fig.tight_layout()
    fig.savefig(output / "round4_validation.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
