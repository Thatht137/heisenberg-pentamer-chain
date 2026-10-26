"""沿用双五聚体 ED 基准，验证完整动量谱及时间窗。"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/autoresearch_v5"))
from static_krylov_ed_reference import build_sector_hamiltonian


def main():
    out = ROOT / "results/fullq_dsf_20261001/ed_L10"
    out.mkdir(parents=True, exist_ok=True)
    q = np.linspace(0, 2 * np.pi, 41)
    omega = np.linspace(0, 4, 801)
    rows = []
    for alpha in (-0.5, 0.5):
        basis, h = build_sector_hamiltonian(alpha, 0.5, 5)
        energy, vectors = np.linalg.eigh(h)
        ground = vectors[:, 0]
        sz = np.array([[(state >> site & 1) - 0.5 for site in range(10)] for state in basis])
        source = (sz @ np.exp(1j * np.outer(np.arange(1, 11), q)) / np.sqrt(10)) * ground[:, None]
        source -= ground[:, None] * (ground @ source)[None, :]
        weights = np.abs(vectors.T @ source) ** 2
        gaps = energy - energy[0]
        # 三角时间窗的精确展宽核，未裁剪、未平均动量。
        tmax = 60.0
        kernel = tmax / (2 * np.pi) * np.sinc((omega[:, None] - gaps[None, :]) * tmax / (2 * np.pi)) ** 2
        spectrum = (kernel @ weights).T
        np.savetxt(out / f"a{alpha}_spectrum.csv", spectrum, delimiter=",")
        np.savetxt(out / f"a{alpha}_weights.csv", weights, delimiter=",")
        np.savetxt(out / f"a{alpha}_gaps.csv", gaps, delimiter=",")
        mirror = np.linalg.norm(spectrum - spectrum[::-1]) / np.linalg.norm(spectrum)
        rows.append({"alpha": alpha, "L": 10, "dimension": len(basis), "energy": energy[0],
                     "residual": np.linalg.norm(h @ ground - energy[0] * ground),
                     "inversion_relative_rms": mirror, "q0_max": float(spectrum[0].max()),
                     "min_spectrum": float(spectrum.min()), "tmax": tmax})
        assert len(basis) == 252 and mirror < 1e-12 and spectrum[0].max() < 1e-20
    np.savetxt(out / "q.csv", q, delimiter=",")
    np.savetxt(out / "omega.csv", omega, delimiter=",")
    (out / "checks.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
