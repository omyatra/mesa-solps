"""
Make synthetic Thomson-scattering (TS) data from a SOLPS ``balance.nc``.

The true electron density and temperature per channel are the predictions of
sim-solps's ``ThomsonScattering`` model (the model MESA scores runs with) for
the given SOLPS state. The errors are a flat fraction of the true values, and
Gaussian noise with those errors is added using a fixed seed.

Three files are written to the output folder:

- ``<name>.npz``: the noisy data
- ``<name>_truth.npz``: the noise-free data, with the same errors
- ``<name>.json``: where the data came from (source path, its mtime, error
  fraction, seed, git commit)

Both ``.npz`` files have the keys ``te_data``, ``te_err``, ``ne_data`` and
``ne_err`` (1D arrays, one value per channel), as ``ThomsonScattering``
expects for its ``measurements`` argument. Channels outside the SOLPS mesh are
NaN in both files.

The noise is drawn as ``rng = numpy.random.default_rng(seed)``, then one
standard normal per channel for Te, then one per channel for ne.

Example::

    python tools/make_synthetic_ts.py \\
        --balance path/to/balance.nc \\
        --instrument path/to/testing_ts_instrument_data.npz \\
        --out-dir path/to/output
"""

import argparse
import json
import subprocess
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

KEYS = ("te_data", "te_err", "ne_data", "ne_err")


def flat_errors(values: np.ndarray, error_fraction: float) -> np.ndarray:
    """Errors equal to ``error_fraction`` times the absolute true values."""
    if not error_fraction > 0:
        raise ValueError(f"error_fraction must be > 0, got {error_fraction}")
    return error_fraction * np.abs(values)


def make_datasets(
    ne_true: np.ndarray, te_true: np.ndarray, error_fraction: float, seed: int
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """
    Build the noise-free and the noisy data sets from the true ne and Te.

    :return: ``(truth, noisy)``, two dicts with the keys in ``KEYS``. Both have
        the same errors; NaN channels stay NaN.
    """
    ne_true = np.asarray(ne_true, dtype=float)
    te_true = np.asarray(te_true, dtype=float)
    if ne_true.shape != te_true.shape or ne_true.ndim != 1:
        raise ValueError("ne_true and te_true must be 1D arrays of the same length")

    te_err = flat_errors(te_true, error_fraction)
    ne_err = flat_errors(ne_true, error_fraction)

    rng = np.random.default_rng(seed)
    te_noise = rng.standard_normal(te_true.size)
    ne_noise = rng.standard_normal(ne_true.size)

    truth = {
        "te_data": te_true.copy(),
        "te_err": te_err,
        "ne_data": ne_true.copy(),
        "ne_err": ne_err,
    }
    noisy = {
        "te_data": te_true + te_err * te_noise,
        "te_err": te_err.copy(),
        "ne_data": ne_true + ne_err * ne_noise,
        "ne_err": ne_err.copy(),
    }
    return truth, noisy


def nan_channels(ne: np.ndarray, te: np.ndarray) -> list[int]:
    """Indices of the channels where ne or Te is NaN."""
    return [int(i) for i in np.nonzero(np.isnan(ne) | np.isnan(te))[0]]


def git_commit(path: Path) -> str | None:
    """The git commit of the repository holding ``path`` (``-dirty`` if it has changes)."""
    try:
        out = subprocess.run(
            ["git", "describe", "--always", "--dirty", "--abbrev=40"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


def write_outputs(
    out_dir: Path,
    name: str,
    truth: dict[str, np.ndarray],
    noisy: dict[str, np.ndarray],
    metadata: dict,
    overwrite: bool = False,
) -> dict[str, Path]:
    """
    Write ``<name>.npz`` (noisy), ``<name>_truth.npz`` and ``<name>.json``.

    :return: the paths written, under the keys ``noisy``, ``truth`` and ``json``.
    """
    out_dir = Path(out_dir)
    paths = {
        "noisy": out_dir / f"{name}.npz",
        "truth": out_dir / f"{name}_truth.npz",
        "json": out_dir / f"{name}.json",
    }
    if not overwrite:
        existing = [str(p) for p in paths.values() if p.exists()]
        if existing:
            raise FileExistsError(
                f"refusing to overwrite {', '.join(existing)} (pass --overwrite)"
            )
    for data in (truth, noisy):
        if set(data) != set(KEYS):
            raise ValueError(f"data sets must have exactly the keys {KEYS}")

    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez(paths["noisy"], **{k: noisy[k] for k in KEYS})
    np.savez(paths["truth"], **{k: truth[k] for k in KEYS})
    with open(paths["json"], "w") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")
    return paths


def true_profiles(balance: Path, instrument: Path) -> tuple[np.ndarray, np.ndarray]:
    """True ne and Te per channel from ``ThomsonScattering.predictions()``."""
    from sims.interface import SolpsInterface
    from sims.instruments import ThomsonScattering

    geometry = np.load(instrument)
    interface = SolpsInterface(str(balance))
    ts = ThomsonScattering(
        R=geometry["R"], z=geometry["z"], weights=geometry["weights"], interface=interface
    )
    ne, te = ts.predictions()
    return ne, te


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Make synthetic TS data from a SOLPS balance.nc using sim-solps's ThomsonScattering."
    )
    p.add_argument("--balance", required=True, type=Path, help="SOLPS balance.nc (read only)")
    p.add_argument(
        "--instrument",
        required=True,
        type=Path,
        help="npz with the TS geometry: R, z, weights, each (channels, samples)",
    )
    p.add_argument("--out-dir", required=True, type=Path, help="output folder")
    p.add_argument(
        "--name",
        default="synthetic_ts_refconv",
        help="output file stem (default: %(default)s)",
    )
    p.add_argument(
        "--error-fraction",
        type=float,
        default=0.05,
        help="errors as a fraction of the true value (default: %(default)s)",
    )
    p.add_argument("--seed", type=int, default=0, help="noise seed (default: %(default)s)")
    p.add_argument("--overwrite", action="store_true", help="replace existing output files")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    balance = args.balance.expanduser().resolve()
    instrument = args.instrument.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()

    ne_true, te_true = true_profiles(balance, instrument)
    bad = nan_channels(ne_true, te_true)
    if bad:
        warnings.warn(
            f"{len(bad)} of {ne_true.size} channels are NaN (outside the SOLPS mesh): {bad}",
            stacklevel=1,
        )

    truth, noisy = make_datasets(ne_true, te_true, args.error_fraction, args.seed)

    mtime = balance.stat().st_mtime
    metadata = {
        "source": str(balance),
        "source_mtime": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
        "source_mtime_epoch": mtime,
        "instrument": str(instrument),
        "error_fraction": args.error_fraction,
        "seed": args.seed,
        "noise": "rng = numpy.random.default_rng(seed); Te noise then ne noise, one standard normal per channel",
        "n_channels": int(ne_true.size),
        "nan_channels": bad,
        "git_commit": git_commit(Path(__file__).resolve().parent),
        "created": datetime.now(timezone.utc).isoformat(),
    }
    paths = write_outputs(out_dir, args.name, truth, noisy, metadata, args.overwrite)
    for p in paths.values():
        print(f"wrote {p}")


if __name__ == "__main__":
    main()
