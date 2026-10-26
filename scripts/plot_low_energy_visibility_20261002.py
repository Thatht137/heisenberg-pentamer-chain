"""低能弱谱权显示与原始谱线核查，不改变数值分辨率。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import AsinhNorm, LinearSegmentedColormap

from audit_fullq_dsf import load_run, quality
from plot_dsf_screenshot_style import draw

ROOT = Path(__file__).resolve().parents[1]


def low_energy_summary(run, ymax=0.6):
    omega, spectrum = run["omega"], run["spectrum"]
    selected = omega <= ymax
    if np.count_nonzero(selected) < 2:
        raise ValueError("低能区至少需要两个实际频率点")
    low = spectrum[:, selected]
    low_weight = np.trapezoid(low, omega[selected], axis=1).sum()
    sampled_weight = np.trapezoid(spectrum, omega, axis=1).sum()
    return selected, {
        "omega_range": [float(omega[selected][0]), float(omega[selected][-1])],
        "sampled_full_omega_range": [float(omega[0]), float(omega[-1])],
        "maximum": float(low.max()),
        "median_excluding_conserved_endpoints": float(np.median(low[1:-1])),
        "low_weight_fraction_of_sampled_range": float(low_weight / sampled_weight),
        "window_fwhm": run["metadata"]["window_fwhm"],
        "spectral_resolution_improved": False,
    }


def export(fig, destination):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for label in fig.findobj(match=matplotlib.text.Text):
        if not label.get_visible() or not label.get_text():
            continue
        bounds = label.get_window_extent(renderer)
        if (bounds.x0 < -1 or bounds.y0 < -1 or bounds.x1 > fig.bbox.width + 1
                or bounds.y1 > fig.bbox.height + 1):
            raise ValueError(f"文字越界：{label.get_text()}")
    for extension in ("png", "pdf", "svg"):
        fig.savefig(destination.parent / f"{destination.name}.{extension}", dpi=300,
                    facecolor="white")
    plt.close(fig)


def draw_low(run, selected, norm, destination):
    cmap = LinearSegmentedColormap.from_list("reference_jet", [
        (0, "#1700b4"), (0.125, "#0000ff"), (0.375, "#00ffff"),
        (0.625, "#ffff00"), (0.875, "#ff0000"), (1, "#ff0000"),
    ], N=256)
    meta = run["metadata"]
    fig, ax = plt.subplots(figsize=(10.3, 8.86))
    fig.subplots_adjust(left=0.16, right=0.82, bottom=0.20, top=0.875)
    mesh = ax.pcolormesh(run["q"], run["omega"][selected], run["spectrum"][:, selected].T,
                         shading="nearest", cmap=cmap, norm=norm, rasterized=True,
                         antialiased=False)
    ax.set(xlim=(0, 2 * np.pi), ylim=(0, 0.6))
    ax.set_xticks([0, np.pi, 2 * np.pi], [r"$\mathbf{0}$", r"$\boldsymbol{\pi}$",
                                       r"$\mathbf{2}\boldsymbol{\pi}$"])
    ax.set_yticks([0, 0.2, 0.4, 0.6], ["0", "0.2", "0.4", "0.6"])
    ax.tick_params(direction="in", length=6, labelsize=32, pad=12)
    for tick in ax.get_yticklabels():
        tick.set_fontweight("bold")
    ax.set_xlabel("q", fontsize=42, fontweight="bold", labelpad=24)
    ax.set_ylabel(r"$\boldsymbol{\omega}/J_1$", fontsize=36, labelpad=18)
    ax.text(0.5, 1.095, rf"$J_2={meta['alpha']:g},\ J_3={meta['beta']:g}$",
            transform=ax.transAxes, fontsize=26, ha="center", va="bottom")
    ax.text(0.5, 1.027, "L=40; asinh color scale", transform=ax.transAxes,
            fontsize=15, ha="center", va="bottom")
    cax = fig.add_axes([0.855, 0.20, 0.026, 0.675])
    colorbar = fig.colorbar(mesh, cax=cax)
    colorbar.set_ticks([0, 0.02, 0.1, 0.5, 1, 3, 6])
    colorbar.set_ticklabels(["0", "0.02", "0.1", "0.5", "1", "3", "6"])
    colorbar.ax.tick_params(labelsize=16)
    colorbar.set_label(r"$J_1S^{zz}(q,\omega)$", fontsize=20, labelpad=10)
    export(fig, destination)


def draw_cuts(runs, output):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.16, top=0.87, wspace=0.13)
    colors = ["#0072B2", "#009E73", "#D55E00"]
    rows = []
    for ax, run in zip(axes, runs):
        selected, summary = low_energy_summary(run)
        meta = run["metadata"]
        for momentum, color in zip([0.2, 0.6, 1.0], colors):
            indices = np.flatnonzero(np.isclose(run["q"], momentum * np.pi, atol=1e-12, rtol=0))
            if len(indices) != 1:
                raise ValueError("谱线切片需要原始网格中存在该动量")
            values = run["spectrum"][indices[0], selected]
            ax.plot(run["omega"][selected], values, color=color, linewidth=1.6,
                    label=rf"$q={momentum:g}\pi$")
            rows.extend((meta["alpha"], momentum, omega, value)
                        for omega, value in zip(run["omega"][selected], values))
        ax.set(xlim=(0, 0.6), ylim=(0, 6), xlabel=r"$\omega/J_1$")
        ax.set_title(rf"$J_2={meta['alpha']:g},\ J_3={meta['beta']:g};\ L=40$", fontsize=14)
        ax.legend(frameon=False, fontsize=11, loc="upper right")
        ax.text(0.97, 0.63, f"Window FWHM = {summary['window_fwhm']:.3f} J1",
                transform=ax.transAxes, ha="right", fontsize=10)
        ax.tick_params(direction="in", labelsize=12)
    axes[0].set_ylabel(r"$J_1S^{zz}(q,\omega)$", fontsize=14)
    export(fig, output / "low_energy_raw_cuts")
    with (output / "low_energy_raw_cuts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["J2", "q_over_pi", "omega_over_J1", "J1_Szz"])
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--full", action="store_true", help="保持完整 0 至 4J1 谱图")
    args = parser.parse_args()
    if args.output is None:
        args.output = ROOT / "figures" / ("fullq_visibility_20261002" if args.full else "low_energy_visibility_20261002")
    args.output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "Arial", "mathtext.fontset": "stixsans",
                         "pdf.fonttype": 42, "svg.fonttype": "none"})
    directories = [ROOT / "results/fullq_dsf_20261001" / name
                   for name in ("L40_positive", "L40_negative_local")]
    accepted = json.loads((ROOT / "figures/fullq_dsf_20261001/qa.json").read_text(encoding="utf-8"))
    runs, records = [], []
    # 两组使用同一单调色标，不按动量或参数分别归一化。
    norm = AsinhNorm(linear_width=0.02, vmin=0, vmax=6)
    for directory in directories:
        source = directory / "spectrum.csv"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        run = load_run(directory)
        meta = run["metadata"]
        record = next(item for item in accepted["results"] if item["metadata"]["alpha"] == meta["alpha"])
        if record["status"] != "accepted" or digest != record["spectrum_sha256"]:
            raise ValueError("源数据不是此前验收的原始谱")
        if meta["L"] != 40 or meta["n_units"] != 8 or not quality(run)["baseline_pass"]:
            raise ValueError("模型尺寸或原始谱验收未通过")
        selected, summary = low_energy_summary(run)
        if summary["maximum"] > norm.vmax:
            raise ValueError("共同色标不足以容纳实际峰值")
        label = "full" if args.full else "low"
        stem = f"Sqw_L40_J2={meta['alpha']:g}_J3={meta['beta']:g}_{label}_asinh"
        if args.full:
            draw(run["spectrum"], run["q"], run["omega"], meta["alpha"], meta["beta"],
                 4.0, 6.0, args.output / stem, norm=norm)
            draw(run["spectrum"], run["q"], run["omega"], meta["alpha"], meta["beta"],
                 4.0, 6.0, args.output / (stem + "_colorbar"), norm=norm, colorbar=True)
        else:
            draw_low(run, selected, norm, args.output / stem)
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError("绘图期间原始谱发生变化")
        runs.append(run)
        records.append({"J2": meta["alpha"], "source": source.as_posix(),
                        "source_sha256": digest, "output_stem": stem,
                        "low_energy_diagnostic": summary})
    if not args.full:
        draw_cuts(runs, args.output)
    manifest = {"display_only": True, "normalization": "asinh", "vmin": 0, "vmax": 6,
                "linear_width": 0.02, "shared_color_scale": True, "display_saturation": False,
                "display_omega_range": [0, 4 if args.full else 0.6], "energy_axis": "linear",
                "full_spectrum": args.full, "inset": False, "broken_axis": False,
                "parameter_footer": False, "processing_details_in_readme": True,
                "smoothing": False, "interpolation": False, "inversion_averaging": False,
                "spectral_resolution_improved": False, "source_data_changed": False,
                "plot_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "style_script_sha256": hashlib.sha256((ROOT / "scripts/plot_dsf_screenshot_style.py").read_bytes()).hexdigest(),
                "records": records}
    (args.output / "visibility_qa.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                                 encoding="utf-8")
    lines = ["# 完整谱图弱信号可见性" if args.full else "# 低能谱可见性", "",
             "保留 q=0 至 2pi、omega=0 至 4J1 的完整单幅谱图和线性坐标；无插图、断轴或低能区单独放大。" if args.full else
             "单独显示原始低能频率窗口。",
             "弱谱权图使用两组共用的 asinh 非线性色标，范围 0 至 6，linear_width=0.02。",
             "颜色归一化为 asinh(S/0.02)/asinh(6/0.02)，应用于全部频率和动量，不针对低能区局部修图。",
             "色条刻度仍是原始 J1*Szz。零值仍为零，真实峰值未饱和；不按 q 分别归一化。",
             "无高斯平滑、空间/频率插值或镜像平均，之前的线性色标全谱保留不动。",
             "这是显示动态范围的改进，不是新增能量分辨率，也不能把增强可见的时间窗旁瓣当作新的激发支。", ""]
    lines.extend(["图内不放链长、色标映射或处理参数说明；这些信息保留在本文件中。",
                  "无色条版本用于版式展示；用于科研交流时须附上此色标说明，定量比较请使用附色条版本。", ""])
    for record in records:
        lines.extend([f"## J2={record['J2']:g}",
                      f"0 至 0.6J1 占已采样 0 至 4J1 谱积分的 {100 * record['low_energy_diagnostic']['low_weight_fraction_of_sampled_range']:.2f}%。",
                      "该比例为等权动量网格加总后的有限频率区间积分，不是完整频率求和规则。",
                      f"[{'完整谱图' if args.full else '低能弱谱权图'}]({(args.output / (record['output_stem'] + '.png')).resolve().as_posix()})", ""])
        if args.full:
            lines.extend([f"[完整谱图附色条]({(args.output / (record['output_stem'] + '_colorbar.png')).resolve().as_posix()})", ""])
    if not args.full:
        lines.extend([f"[原始谱线切片]({(args.output / 'low_energy_raw_cuts.png').resolve().as_posix()})",
                      "切片采用线性强度轴，实际频率点相连，不做拟合或平滑。", ""])
    lines.extend([
                  "当前 T=60 的三角时间窗 FWHM=0.09277J1。若需分辨更近的激发，应延长真实演化时间并检查截断与步长收敛。",
                  "T=120 的理论窗口 FWHM 约为 0.04639J1，但本目录没有新增该计算，也不宣称已有该分辨率。", ""])
    (args.output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
