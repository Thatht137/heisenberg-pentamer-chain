"""完整谱图的温和增强与线性对照，保留可核查色标。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import AsinhNorm, Normalize

from audit_fullq_dsf import load_run, quality
from plot_dsf_screenshot_style import draw

ROOT = Path(__file__).resolve().parents[1]
VMAX = 6.0


def make_norm(mode, linear_width):
    if not np.isfinite(linear_width) or linear_width <= 0:
        raise ValueError("linear_width 必须为有限正数")
    if mode == "linear":
        return Normalize(vmin=0, vmax=VMAX)
    if mode == "asinh":
        return AsinhNorm(linear_width=linear_width, vmin=0, vmax=VMAX)
    raise ValueError("未知色标类型")


def render_run(run, output, linear_width):
    meta, spectrum = run["metadata"], run["spectrum"]
    if not np.isfinite(spectrum).all() or spectrum.min() < 0 or spectrum.max() > VMAX:
        raise ValueError("原始谱超出共同色标范围，不能隐藏或截断")
    original = spectrum.copy()
    figures = []
    # 只改变统一的强度到颜色映射，完整坐标和谱值不变。
    for mode in ("linear", "asinh"):
        norm = make_norm(mode, linear_width)
        stem = f"Sqw_L40_J2={meta['alpha']:g}_J3={meta['beta']:g}_full_{mode}"
        ticks = list(range(7)) if mode == "linear" else [0, 0.02, 0.1, 0.5, 1, 3, 6]
        draw(spectrum, run["q"], run["omega"], meta["alpha"], meta["beta"],
             4.0, VMAX, output / stem, norm=norm, colorbar=True,
             colorbar_ticks=ticks)
        if not np.array_equal(spectrum, original):
            raise ValueError("绘图改变了原始谱数组")
        figures.append({"mode": mode, "stem": stem, "colorbar_ticks": ticks,
                        "linear_width": linear_width if mode == "asinh" else None,
                        "mapping": ("u=S/6" if mode == "linear" else
                                    f"u=asinh(S/{linear_width:g})/asinh(6/{linear_width:g})")})
    return figures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=ROOT / "figures/fullq_documented_20261002")
    parser.add_argument("--linear-width", type=float, default=0.1)
    args = parser.parse_args()
    make_norm("asinh", args.linear_width)
    args.output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "Arial", "mathtext.fontset": "stixsans",
                         "pdf.fonttype": 42, "svg.fonttype": "none"})
    accepted = json.loads((ROOT / "figures/fullq_dsf_20261001/qa.json").read_text(encoding="utf-8"))
    records = []
    for name in ("L40_positive", "L40_negative_local"):
        directory = ROOT / "results/fullq_dsf_20261001" / name
        sources = [directory / filename for filename in
                   ("spectrum.csv", "q.csv", "omega.csv", "run_metadata.toml")]
        hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
        run = load_run(directory)
        meta, checks = run["metadata"], quality(run)
        previous = next(record for record in accepted["results"]
                        if record["metadata"]["alpha"] == meta["alpha"])
        if previous["status"] != "accepted" or hashes["spectrum.csv"] != previous["spectrum_sha256"]:
            raise ValueError("源数据与已验收谱不一致")
        if (meta["L"] != 40 or meta["n_units"] != 8 or meta["beta"] != 0.5
                or not checks["baseline_pass"]):
            raise ValueError("模型参数或原始谱核验未通过")
        if not np.allclose(run["omega"][[0, -1]], [0, 4], atol=1e-12, rtol=0):
            raise ValueError("频率范围不是完整 0 至 4J1")
        figures = render_run(run, args.output, args.linear_width)
        if any(hashlib.sha256(path.read_bytes()).hexdigest() != hashes[path.name] for path in sources):
            raise ValueError("绘图期间源文件发生变化")
        records.append({"J2": meta["alpha"], "J3": meta["beta"], "L": meta["L"],
                        "source_sha256": hashes, "source_grid_shape": list(run["spectrum"].shape),
                        "inversion_relative_rms": checks["inversion_relative_rms"],
                        "window_fwhm": meta["window_fwhm"], "figures": figures})
    manifest = {"display_only": True, "source_data_changed": False,
                "source_files_unchanged": True, "smoothing": False, "interpolation": False,
                "inversion_averaging": False, "out_of_range_clipping": False,
                "shared_color_scale_within_each_mode": True, "vmin": 0, "vmax": VMAX,
                "full_spectrum": True, "display_q_range": [0, float(2 * np.pi)],
                "display_omega_range": [0, 4], "energy_axis": "linear",
                "colorbar": True, "inset": False, "broken_axis": False,
                "parameter_footer": False, "processing_details_in_readme": True,
                "spectral_resolution_improved": False,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "style_script_sha256": hashlib.sha256((ROOT / "scripts/plot_dsf_screenshot_style.py").read_bytes()).hexdigest(),
                "records": records}
    (args.output / "display_qa.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 完整谱图：有标定色条的增强版与线性对照", "",
             "本组图只比较显示方式，不主张新增激发支、改进真实能量分辨率或改变模型。",
             "L=40，即 8 个完整五聚体；J1=1，J2=±0.5，J3=0.5，开放边界。",
             "两种版本均保留 q=0 至 2pi、omega/J1=0 至 4 的完整单幅谱图和线性坐标。",
             "无低能局部放大、插图、断轴、高斯平滑、插值、镜像平均或分区加权。", "",
             "## 色标与图注", "",
             "线性对照采用 u=S/6；S 表示 J1*Szz(q,omega)。",
             f"增强版采用 u=asinh(S/{args.linear_width:g})/asinh(6/{args.linear_width:g})。",
             "两组参数在各自显示模式下共用同一映射和 0 至 6 的色标；色条刻度为实际谱强度而非变换后的数值。",
             "原始峰值和零值保留，数据没有超出色标范围；未针对高能区单独压暗。",
             "非线性色标会改变视觉突出程度和表观带宽。谱权重比、峰宽、能隙等定量分析须使用原始数值。", "",
             "可直接使用的增强版图注：", "",
             f"> L=40 五聚体 Heisenberg 链的连通动态结构因子 Szz(q,omega)。整图采用统一 asinh 强度色标（s0={args.linear_width:g}，范围 0 至 6），色条显示实际 J1*Szz 数值，两组参数共用同一映射。坐标轴保持线性，原始谱未作高斯平滑、插值或镜像平均。谱来自 T=60 的演化及三角时间窗，窗口 FWHM 约 0.09277J1。增强仅用于显示弱谱权，不代表能量分辨率提高；弱条纹可能包含有限时间窗旁瓣。", "",
             "线性对照图注可将上述色标说明替换为“整图采用共同的线性强度色标，范围 0 至 6”。", ""]
    for record in records:
        lines.extend([f"## J2={record['J2']:g}", ""])
        for figure in record["figures"]:
            label = "线性整图" if figure["mode"] == "linear" else "增强整图"
            links = " | ".join(f"[{extension.upper()}]({figure['stem']}.{extension})"
                               for extension in ("png", "pdf", "svg"))
            lines.append(f"{label}：{links}")
        lines.extend([f"原始谱反演对称相对 RMS 误差：{record['inversion_relative_rms']:.6g}；未进行人为对称化。", ""])
    lines.extend(["## 核查", "",
                  "display_qa.json 记录原始谱、动量、频率及计算元数据的 SHA256。绘图前后均核验文件未变。",
                  "既有线性及较强增强版均保留，新图不覆盖它们。所有弱结构仍需结合原始数据与收敛检查解释。", ""])
    (args.output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
