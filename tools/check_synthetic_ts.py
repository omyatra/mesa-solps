"""
Check synthetic TS data made by ``make_synthetic_ts.py`` against the SOLPS state it came from.

1. Loads the noisy and the truth file through ``ThomsonScattering(measurements=...)``, as MESA
   does, and checks the truth file against fresh ``predictions()``.
2. Scores the SOLPS state against each file with mesa-solps's ``SolpsLikelihood`` (Cauchy
   log-likelihood), and compares the noisy score with its expected distribution for the same
   number of points (Monte Carlo, Gaussian noise).
3. Optionally scores the old test data too, and plots ne and Te against R: truth, noisy points
   with error bars and (optionally) the old test data.

Example::

    python tools/check_synthetic_ts.py \\
        --balance path/to/balance.nc \\
        --instrument path/to/testing_ts_instrument_data.npz \\
        --data-dir path/to/output \\
        --old-data path/to/testing_ts_data.npz
"""

import argparse
from pathlib import Path

import numpy as np


def load_measurements(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as f:
        return {k: f[k] for k in ("te_data", "te_err", "ne_data", "ne_err")}


def cauchy_score_distribution(n_points: int, n_draws: int = 200_000, seed: int = 12345):
    """Cauchy log-likelihood of n_points standard-normal residuals, sampled n_draws times."""
    rng = np.random.default_rng(seed)
    total = np.zeros(n_draws)
    for _ in range(n_points):  # one point at a time keeps memory small
        total -= np.log1p(rng.standard_normal(n_draws) ** 2)
    return total


def score(interface, geometry, measurements) -> tuple[float, float, int]:
    """(SolpsLikelihood score, Gaussian chi-squared, points used) for one data set."""
    from mesa_solps.objective import SolpsLikelihood
    from sims.instruments import ThomsonScattering
    from sims.likelihoods import gaussian_likelihood

    ts = ThomsonScattering(
        R=geometry["R"], z=geometry["z"], weights=geometry["weights"], measurements=measurements
    )
    objective = SolpsLikelihood(diagnostics=[ts])
    result = objective.evaluate(interface)[objective.name]
    chi2 = -2 * ts.log_likelihood(likelihood=gaussian_likelihood)
    n_points = 2 * np.size(ts.predicted_channels)
    return float(result), float(chi2), int(n_points)


def plot(path: Path, R: np.ndarray, truth, noisy, old=None):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    blue, orange, aqua = "#2a78d6", "#eb6834", "#1baf7a"
    ink, muted, grid = "#0b0b0b", "#52514e", "#e4e3df"
    fig, axes = plt.subplots(2, 1, figsize=(7, 7.5), sharex=True)
    panels = [
        ("ne_data", "ne_err", 1e-19, r"$n_e$ ($10^{19}$ m$^{-3}$)"),
        ("te_data", "te_err", 1.0, r"$T_e$ (eV)"),
    ]
    for ax, (key, err, scale, label) in zip(axes, panels):
        ax.plot(R, truth[key] * scale, color=blue, lw=2, label="truth (SOLPS refconv)", zorder=2)
        ax.errorbar(
            R, noisy[key] * scale, yerr=noisy[err] * scale, fmt="o", ms=5, color=orange,
            ecolor=orange, elinewidth=1, capsize=0, mec="white", mew=0.8,
            label="synthetic (noisy, 5 % errors)", zorder=3,
        )
        if old is not None:
            ax.errorbar(
                R, old[key] * scale, yerr=old[err] * scale, fmt="s", ms=5, mfc="none",
                color=aqua, ecolor=aqua, elinewidth=1, capsize=0,
                label="old test data", zorder=1,
            )
        ax.set_ylabel(label, color=ink)
        ax.grid(True, color=grid, lw=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(muted)
        ax.tick_params(colors=muted)
    axes[0].legend(frameon=False, fontsize=9)
    axes[-1].set_xlabel("R (m), channel-weighted mean of the sample points", color=ink)
    axes[0].set_title("Synthetic Thomson-scattering data vs R", color=ink, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--balance", required=True, type=Path)
    p.add_argument("--instrument", required=True, type=Path)
    p.add_argument("--data-dir", required=True, type=Path)
    p.add_argument("--name", default="synthetic_ts_refconv")
    p.add_argument("--old-data", type=Path, help="old test data npz, for the score and the plot")
    p.add_argument("--plot", type=Path, help="plot path (default: <data-dir>/comparison.png)")
    args = p.parse_args(argv)

    from sims.interface import SolpsInterface
    from sims.instruments import ThomsonScattering

    with np.load(args.instrument.expanduser()) as f:
        geometry = {k: f[k] for k in ("R", "z", "weights")}
    data_dir = args.data_dir.expanduser()
    noisy = load_measurements(data_dir / f"{args.name}.npz")
    truth = load_measurements(data_dir / f"{args.name}_truth.npz")
    old = load_measurements(args.old_data.expanduser()) if args.old_data else None

    interface = SolpsInterface(str(args.balance.expanduser()))

    # 1. load back through ThomsonScattering(measurements=...) and compare with predictions()
    for label, data in (("noisy", noisy), ("truth", truth)):
        ts = ThomsonScattering(
            R=geometry["R"], z=geometry["z"], weights=geometry["weights"],
            interface=interface, measurements=data,
        )
        print(f"{label}: loaded through ThomsonScattering(measurements=...), "
              f"{np.size(ts.predicted_channels)} of {ts.n_channels} channels predicted")
    ne, te = ts.predictions()
    print("truth file equals predictions():",
          np.allclose(truth["ne_data"], ne, rtol=1e-12, equal_nan=True)
          and np.allclose(truth["te_data"], te, rtol=1e-12, equal_nan=True))
    print("NaN channels:", [int(i) for i in np.nonzero(np.isnan(ne) | np.isnan(te))[0]])

    # 2. scores
    results = {}
    sets = [("truth", truth), ("noisy", noisy)] + ([("old test data", old)] if old else [])
    for label, data in sets:
        results[label] = score(interface, geometry, data)
        s, chi2, n = results[label]
        print(f"score {label:>14}: cauchy_logprob = {s:10.3f}   chi2 = {chi2:10.2f}   ({n} points)")

    n = results["noisy"][2]
    dist = cauchy_score_distribution(n)
    s = results["noisy"][0]
    lo, hi = np.percentile(dist, [2.5, 97.5])
    print(f"expected noisy score for {n} points: mean {dist.mean():.2f}, sd {dist.std():.2f}, "
          f"95 % range [{lo:.2f}, {hi:.2f}]; observed {s:.3f} "
          f"(percentile {100 * (dist < s).mean():.1f})")
    chi2 = results["noisy"][1]
    print(f"noisy chi2 = {chi2:.2f} for {n} points (chi2_{n}: mean {n}, sd {np.sqrt(2 * n):.2f})")

    # 3. plot
    R = (geometry["R"] * geometry["weights"]).sum(axis=1) / geometry["weights"].sum(axis=1)
    out = args.plot.expanduser() if args.plot else data_dir / "comparison.png"
    plot(out, R, truth, noisy, old)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
