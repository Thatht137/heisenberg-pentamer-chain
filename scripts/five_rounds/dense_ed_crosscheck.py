#!/usr/bin/env python3
"""用独立 Python 实现计算十格点链的全空间 ED 基态。"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
from scipy.linalg import eigh


ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def bonds(n_units: int, alpha: float, beta: float) -> list[tuple[int, int, float]]:
    result: list[tuple[int, int, float]] = []
    for unit in range(n_units):
        first = 5 * unit
        result.extend(
            [
                (first, first + 1, alpha),
                (first + 1, first + 2, 1.0),
                (first + 2, first + 3, 1.0),
                (first + 3, first + 4, alpha),
            ]
        )
        if unit + 1 < n_units:
            result.append((first + 4, first + 5, beta))
    return result


def build_hamiltonian(n_sites: int, chain_bonds: list[tuple[int, int, float]]) -> np.ndarray:
    dim = 1 << n_sites
    hamiltonian = np.zeros((dim, dim), dtype=np.float64)
    for state in range(dim):
        for left, right, coupling in chain_bonds:
            left_bit = (state >> left) & 1
            right_bit = (state >> right) & 1
            left_sz = 0.5 if left_bit else -0.5
            right_sz = 0.5 if right_bit else -0.5
            hamiltonian[state, state] += coupling * left_sz * right_sz
            if left_bit != right_bit:
                flipped = state ^ (1 << left) ^ (1 << right)
                hamiltonian[flipped, state] += 0.5 * coupling
    return hamiltonian


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--alpha", type=float, required=True)
    parser.add_argument("--beta", type=float, required=True)
    parser.add_argument("--n-units", type=int, default=2)
    args = parser.parse_args()

    if not 0.0 <= args.alpha <= 1.0:
        raise SystemExit("禁止 alpha<0 或 alpha>1")
    if not 0.0 <= args.beta <= 1.0:
        raise SystemExit("beta 必须位于 [0,1]")
    if args.n_units != 2:
        raise SystemExit("交叉验证固定为两个五聚体，即 L=10")

    outdir = Path(args.outdir).resolve()
    outdir.relative_to((ROOT / "results").resolve())
    if outdir.exists() and any(outdir.iterdir()):
        raise SystemExit(f"拒绝覆盖已有 ED 目录: {outdir}")
    outdir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    write_json(outdir / "status.json", {"status": "running", "started_at": started.isoformat()})

    n_sites = 5 * args.n_units
    chain_bonds = bonds(args.n_units, args.alpha, args.beta)
    hamiltonian = build_hamiltonian(n_sites, chain_bonds)
    hermiticity_norm = float(np.linalg.norm(hamiltonian - hamiltonian.T))
    trace_abs = float(abs(np.trace(hamiltonian)))
    eigenvalues, eigenvectors = eigh(
        hamiltonian,
        subset_by_index=[0, 0],
        check_finite=True,
        driver="evr",
    )
    energy = float(eigenvalues[0])
    ground_state = eigenvectors[:, 0]
    residual = hamiltonian @ ground_state - energy * ground_state
    residual_norm = float(np.linalg.norm(residual))
    variance = float(np.vdot(residual, residual).real)
    sz_diagonal = np.array(
        [sum(0.5 if (state >> site) & 1 else -0.5 for site in range(n_sites)) for state in range(1 << n_sites)]
    )
    total_sz = float(np.vdot(ground_state, sz_diagonal * ground_state).real)
    finished = datetime.now(timezone.utc)

    metrics = {
        "method": "dense_ed_python",
        "alpha": args.alpha,
        "beta": args.beta,
        "n_units": args.n_units,
        "L": n_sites,
        "dimension": 1 << n_sites,
        "boundary": "OBC",
        "energy": energy,
        "energy_density": energy / n_sites,
        "residual_norm": residual_norm,
        "variance": variance,
        "hermiticity_norm": hermiticity_norm,
        "trace_abs": trace_abs,
        "total_sz": total_sz,
        "bonds": chain_bonds,
        "negative_alpha_excluded": True,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "source_sha256": sha256(Path(__file__)),
    }
    write_json(outdir / "metrics.json", metrics)
    np.savez_compressed(outdir / "ground_state.npz", energy=energy, psi=ground_state)
    write_json(outdir / "status.json", {"status": "success", "finished_at": finished.isoformat()})
    outputs = [path for path in outdir.iterdir() if path.is_file() and path.name != "checksums.sha256"]
    (outdir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in sorted(outputs)),
        encoding="utf-8",
    )
    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()
