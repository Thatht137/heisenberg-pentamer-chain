"""生成论文逐图对照所需的裁图与五聚体图。"""

from __future__ import annotations

import json
import shutil
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

import plot_literature_style_comparisons_20260813 as literature_style


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/meeting_report_20260812"
ASSETS = REPORT / "assets"
PAGES = ASSETS / "paper_pages_highres"


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
            "font.size": 8,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )


def crop_paper_figures() -> None:
    # 坐标基于 120 dpi 页面预览。
    boxes = {
        1: (3, (75, 65, 930, 660)),
        2: (4, (65, 75, 490, 430)),
        3: (5, (60, 65, 940, 415)),
        4: (6, (65, 455, 490, 690)),
        5: (6, (65, 790, 940, 1110)),
        6: (7, (115, 75, 890, 380)),
        7: (7, (110, 505, 505, 835)),
        8: (8, (95, 85, 500, 430)),
    }
    for figure_id, (page_id, box) in boxes.items():
        source = PAGES / f"page-{page_id:02d}.png"
        with Image.open(source) as image:
            sx = image.width / 1001.0
            sy = image.height / 1295.0
            scaled = tuple(round(value * (sx if index % 2 == 0 else sy)) for index, value in enumerate(box))
            crop = image.crop(scaled)
            crop.save(ASSETS / f"paper_fig{figure_id}.png", optimize=True)


def load_phase_rows() -> list[dict[str, float]]:
    source = ROOT / "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/observations_merged.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    return [
        {
            "alpha": float(row["params"]["alpha"]),
            "beta": float(row["params"]["beta"]),
            "L": float(row["params"]["L"]),
            "R": float(row["value"]),
        }
        for row in data["records"]
        if row.get("status") == "success" and float(row["params"]["alpha"]) >= 0
    ]


def plot_fig3() -> None:
    rows = load_phase_rows()
    alphas = np.array(sorted({row["alpha"] for row in rows}))
    betas = np.array(sorted({row["beta"] for row in rows}))

    def values(size: float) -> np.ndarray:
        return np.array(
            [
                [next(row["R"] for row in rows if row["L"] == size and row["alpha"] == alpha and row["beta"] == beta) for alpha in alphas]
                for beta in betas
            ]
        )

    r40, r60, r80 = values(40), values(60), values(80)
    figure, axes = plt.subplots(2, 2, figsize=(7.2, 5.2), gridspec_kw={"hspace": 0.38, "wspace": 0.32})
    image = axes[0, 0].imshow(
        r80,
        origin="lower",
        aspect="auto",
        extent=[alphas.min() - 0.0625, alphas.max() + 0.0625, betas.min() - 0.05, betas.max() + 0.05],
        cmap="jet",
        vmin=0,
        vmax=max(r80.max(), 0.4),
    )
    axes[0, 0].set(xlabel=r"$\alpha=J_2/J_1$", ylabel=r"$\beta=J_3/J_1$", title=r"$R(L=80)$")
    axes[0, 0].set_xticks(alphas)
    axes[0, 0].set_yticks(betas)
    figure.colorbar(image, ax=axes[0, 0], fraction=0.046, pad=0.04, label="R")
    colors = ["#0072B2", "#009E73", "#E69F00", "#7A3E9D"]
    for alpha, color in zip((0.0, 0.25, 0.5, 1.0), colors):
        index = np.where(alphas == alpha)[0][0]
        axes[0, 1].plot(betas, r80[:, index], marker="o", ms=3, lw=1.3, color=color, label=fr"$\alpha={alpha:g}$")
    axes[0, 1].set(xlabel=r"$\beta$", ylabel=r"$R(L=80)$")
    axes[0, 1].legend(fontsize=6.5, ncol=2)
    for beta, color in zip((0.1, 0.5, 1.0), colors):
        index = np.where(betas == beta)[0][0]
        axes[1, 0].plot(alphas, r80[index], marker="o", ms=3, lw=1.3, color=color, label=fr"$\beta={beta:g}$")
        axes[1, 1].plot(alphas, r60[index] - r40[index], marker="o", ms=3, lw=1.3, color=color, label=fr"$\beta={beta:g}$")
    axes[1, 0].set(xlabel=r"$\alpha$", ylabel=r"$R(L=80)$")
    axes[1, 0].legend(fontsize=6.5)
    axes[1, 1].axhline(0, color="#777777", lw=0.8, ls="--")
    axes[1, 1].set(xlabel=r"$\alpha$", ylabel=r"$R_{60}-R_{40}$")
    axes[1, 1].legend(fontsize=6.5)
    axes[1, 1].text(0.03, 0.06, "finite-size diagnostic", transform=axes[1, 1].transAxes, fontsize=6.5, color="#555555")
    for index, axis in enumerate(axes.flat):
        axis.text(-0.11, 1.04, f"({chr(97 + index)})", transform=axis.transAxes, fontweight="bold")
    figure.suptitle("1×5 positive-region diagnostics", fontsize=10, fontweight="bold")
    figure.savefig(ASSETS / "ours_fig3_paper_palette.png", dpi=260, bbox_inches="tight")
    plt.close(figure)


def install_refined_fig3() -> None:
    source = ROOT / "figures/paper_fig3_positive_groundstate_diagnostics_refined_20260808.png"
    if not source.is_file():
        raise FileNotFoundError("缺少高密度 Fig. 3")
    shutil.copy2(source, ASSETS / "ours_fig3_paper_palette.png")


def plot_fig2_full_alpha() -> None:
    summary_path = ROOT / "data/single_pentamer_low_energy_summary.csv"
    qpi_path = ROOT / "results/autoresearch_v4_20260730/round2_local_spectral_channels_v4/multiplet_scan.csv"
    with summary_path.open(encoding="utf-8", newline="") as handle:
        summary = list(csv.DictReader(handle))
    with qpi_path.open(encoding="utf-8", newline="") as handle:
        qpi_rows = list(csv.DictReader(handle))

    alphas = np.array([float(row["alpha"]) for row in summary])
    colors = {0.5: "#2166AC", 1.5: "#D55E00", 2.5: "#5B5B5B"}
    labels = {0.5: r"$S=1/2$", 1.5: r"$S=3/2$", 2.5: r"$S=5/2$"}
    figure, axes = plt.subplots(1, 2, figsize=(7.6, 3.0), gridspec_kw={"width_ratios": [1.08, 1.0]})
    for spin in (0.5, 1.5, 2.5):
        gaps = np.array([float(row[f"gap_S{spin:.1f}"]) for row in summary])
        axes[0].plot(alphas, gaps, color=colors[spin], lw=1.7, label=labels[spin])
    axes[0].axvline(0, color="#777777", lw=0.8, ls="--")
    axes[0].set(xlabel=r"intracell coupling $\alpha=J_2/J_1$", ylabel=r"lowest multiplet gap $(E_S-E_0)/J_1$", xlim=(-1, 1), ylim=(-0.03, 3.05))
    axes[0].text(-0.96, 2.88, r"ground state: $S=3/2$ for $\alpha<0$", color=colors[1.5], fontsize=7)
    axes[0].text(0.06, 2.64, r"$S=1/2$ for $\alpha>0$", color=colors[0.5], fontsize=7)
    axes[0].legend(ncol=3, fontsize=6.5, loc="lower center", bbox_to_anchor=(0.5, 1.01))

    positive = sorted({float(row["alpha"]) for row in qpi_rows if float(row["alpha"]) >= 0})
    weights = {spin: [] for spin in (0.5, 1.5, 2.5)}
    for alpha in positive:
        selected = [row for row in qpi_rows if abs(float(row["alpha"]) - alpha) < 1e-10]
        for spin in weights:
            weights[spin].append(100 * sum(float(row["qpi_weight"]) for row in selected if abs(float(row["spin_S"]) - spin) < 1e-10))
    for spin in (0.5, 1.5, 2.5):
        axes[1].plot(positive, weights[spin], color=colors[spin], lw=1.7, label=labels[spin])
    axes[1].axvline(0.23, color="#777777", lw=0.8, ls="--")
    axes[1].set(xlabel=r"intracell coupling $\alpha=J_2/J_1$", ylabel=r"$q=\pi$ local spectral weight (%)", xlim=(0, 1), ylim=(0, None))
    axes[1].text(0.26, 0.90, r"classified positive-$\alpha$ scan", transform=axes[1].transAxes, fontsize=6.7, color="#555555")
    for index, axis in enumerate(axes):
        axis.text(-0.10, 1.04, f"({chr(97 + index)})", transform=axis.transAxes, fontweight="bold")
    figure.suptitle("1×5 isolated-pentamer spectrum and visible channel", fontsize=10, fontweight="bold")
    figure.subplots_adjust(left=0.09, right=0.98, bottom=0.18, top=0.80, wspace=0.30)
    figure.savefig(ASSETS / "ours_fig2.png", dpi=320, bbox_inches="tight")
    plt.close(figure)


def install_curated_static_assets() -> None:
    sources = {
        "ours_fig1.png": ROOT / "figures/paper_fig1_model_local_multiplets_20260804.png",
        "ours_fig4.png": ROOT / "figures/paper_fig4_entanglement_spectrum_20260804.png",
        "ours_fig5.png": ROOT / "figures/paper_fig5_effective_chain_selection_rules_20260804.png",
        "ours_fig8.png": ROOT / "figures/round43_fig8_final_20260806_v2.png",
    }
    for name, source in sources.items():
        if not source.is_file():
            raise FileNotFoundError(f"缺少图件：{source}")
        shutil.copy2(source, ASSETS / name)


def write_figure_audit() -> None:
    audit = {
        "date": "2026-08-13",
        "figures": {
            "Fig. 1": {"alignment": "同类诊断", "status": "论文风格重绘", "note": "修正末端 J2=alpha 键，并使用参考图的能级线与灰色局域态语言。"},
            "Fig. 2": {"alignment": "同类诊断", "status": "论文风格重绘", "note": "使用蓝色细线覆盖 alpha=-1..1；q=pi 权重仅限正 alpha 分类数据。"},
            "Fig. 3": {"alignment": "同类诊断", "status": "论文风格重绘", "note": "使用 jet 热图与右侧三联诊断；40x60 纹理和严格有限尺寸证据分开解释。"},
            "Fig. 4": {"alignment": "同类诊断", "status": "论文风格重绘", "note": "采用参考图的黑色短线/圆点语言展示五切口 Schmidt 谱；不是论文的 alpha/beta 权重扫描。"},
            "Fig. 5": {"alignment": "机制替代", "status": "论文风格重绘", "note": "采用灰色单胞、红蓝箭头和时序网格展示有效自由度与选择定则。"},
            "Fig. 6": {"alignment": "参数直接对齐", "status": "探索性", "note": "alpha=+/-1 与 beta=1.0/0.7/0.4/0.1 路径一致，但未完成全参数收敛。"},
            "Fig. 7": {"alignment": "角色对应", "status": "pilot", "note": "本项目固定 beta 扫正 alpha，和论文固定负 alpha 扫 beta 不是同一路径。"},
            "Fig. 8": {"alignment": "方法替代", "status": "代表点通过", "note": "是 q=pi 的 CV-TEBD 验收，不是完整 q 分辨解析色散叠加。"},
        },
    }
    (REPORT / "figure_audit_20260813.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_spectrum(alpha: float, beta: float) -> np.ndarray:
    path = ROOT / "data" / f"Sqw_tebd_pentamer_alpha={alpha:.1f}_beta={beta:.1f}.csv"
    return np.loadtxt(path, delimiter=",")


def plot_fig6() -> None:
    alphas = (1.0, -1.0)
    betas = (1.0, 0.7, 0.4, 0.1)
    arrays = {(alpha, beta): load_spectrum(alpha, beta) for alpha in alphas for beta in betas}
    vmin = min(float(array.min()) for array in arrays.values())
    vmax = max(float(array.max()) for array in arrays.values())
    figure, axes = plt.subplots(2, 4, figsize=(9.4, 4.6), sharex=True, sharey=True)
    image = None
    for row, alpha in enumerate(alphas):
        for column, beta in enumerate(betas):
            array = arrays[(alpha, beta)]
            q = np.linspace(0, 2 * np.pi, array.shape[0])
            omega = np.linspace(0, 3, array.shape[1])
            axis = axes[row, column]
            image = axis.pcolormesh(q, omega, array.T, shading="auto", cmap="jet", vmin=vmin, vmax=vmax, rasterized=True)
            axis.set_xlim(0, 2 * np.pi)
            axis.set_ylim(0, 3)
            axis.set_xticks([0, np.pi, 2 * np.pi], [r"$0$", r"$\pi$", r"$2\pi$"])
            axis.set_title(fr"$\alpha={alpha:g},\ \beta={beta:g}$", fontsize=8)
            axis.text(0.04, 0.93, f"({chr(97 + row * 4 + column)})", transform=axis.transAxes, color="white", fontweight="bold", va="top")
            if column == 0:
                axis.set_ylabel(r"$\omega/J_1$")
            if row == 1:
                axis.set_xlabel(r"$q$")
    figure.subplots_adjust(left=0.07, right=0.91, bottom=0.14, top=0.88, wspace=0.14, hspace=0.24)
    colorbar = figure.colorbar(image, ax=axes, fraction=0.022, pad=0.02)
    colorbar.set_label(r"raw $S^{zz}(q,\omega)$")
    figure.suptitle("1×5 dynamical structure factor across β", fontsize=10, fontweight="bold")
    figure.savefig(ASSETS / "ours_fig6_paper_palette.png", dpi=260, bbox_inches="tight")
    plt.close(figure)


def plot_fig7() -> None:
    alphas = (0.14, 0.23, 0.33)
    paths = [ROOT / "data" / f"Sqw_tebd_pentamer_alpha={alpha:.2f}_beta=0.5_L40_t15.csv" for alpha in alphas]
    arrays = [np.loadtxt(path, delimiter=",") for path in paths]
    vmin = min(float(array.min()) for array in arrays)
    vmax = max(float(array.max()) for array in arrays)
    figure, axes = plt.subplots(2, 3, figsize=(7.4, 4.5), sharex="row", sharey="row")
    colors = ["#0072B2", "#009E73", "#D55E00"]
    image = None
    for index, (alpha, array, color) in enumerate(zip(alphas, arrays, colors)):
        q_over_pi = np.linspace(0, 2, array.shape[0])
        count = min(array.shape[1], int(round(array.shape[1] * 0.5)))
        omega = np.linspace(0, 1.5, count)
        display = array[:, :count]
        image = axes[0, index].pcolormesh(q_over_pi, omega, display.T, shading="auto", cmap="jet", vmin=vmin, vmax=vmax, rasterized=True)
        axes[0, index].set_title(fr"$\alpha={alpha:.2f},\ \beta=0.5$", fontsize=8)
        axes[0, index].set_xticks([0, 1, 2])
        axes[0, index].set_ylim(0, 1.5)
        axes[0, index].set_xlabel(r"$q/\pi$")
        q_index = int(np.argmin(np.abs(q_over_pi - 1)))
        axes[1, index].plot(omega, display[q_index], color=color, lw=1.5)
        axes[1, index].set_title(rf"$q=\pi$ cut, $\alpha={alpha:.2f}$", fontsize=7.5)
        axes[1, index].set_xlim(0, 1.5)
        axes[1, index].set_xlabel(r"$\omega/J_1$")
        for row in range(2):
            axes[row, index].text(0.04, 0.92, f"({chr(97 + row * 3 + index)})", transform=axes[row, index].transAxes, color="white" if row == 0 else "black", fontweight="bold", va="top")
    axes[0, 0].set_ylabel(r"$\omega/J_1$")
    axes[1, 0].set_ylabel(r"raw $S^{zz}(\pi,\omega)$")
    figure.subplots_adjust(left=0.08, right=0.91, bottom=0.15, top=0.86, wspace=0.22, hspace=0.42)
    colorbar = figure.colorbar(image, ax=axes[0, :], fraction=0.035, pad=0.03)
    colorbar.set_label(r"raw $S^{zz}(q,\omega)$")
    figure.suptitle("1×5 positive-α spectrum path", fontsize=10, fontweight="bold")
    figure.savefig(ASSETS / "ours_fig7_paper_palette.png", dpi=260, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    style()
    crop_paper_figures()
    literature_style.main()
    write_figure_audit()


if __name__ == "__main__":
    main()
