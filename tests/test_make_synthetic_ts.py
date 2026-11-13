"""Tests for the noise, error and file-writing logic of tools/make_synthetic_ts.py (no balance.nc needed)."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

_path = Path(__file__).resolve().parents[1] / "tools" / "make_synthetic_ts.py"
_spec = importlib.util.spec_from_file_location("make_synthetic_ts", _path)
mst = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mst)

NE = np.array([1.4e19, 1.0e19, 5.0e18, np.nan, 2.0e18])
TE = np.array([150.0, 80.0, 20.0, np.nan, 5.0])


def test_errors_are_flat_fraction_of_truth():
    truth, noisy = mst.make_datasets(NE, TE, error_fraction=0.05, seed=0)
    ok = ~np.isnan(NE)
    np.testing.assert_allclose(truth["ne_err"][ok], 0.05 * NE[ok])
    np.testing.assert_allclose(truth["te_err"][ok], 0.05 * TE[ok])
    # the noisy file carries the same errors, not errors from the noisy values
    for k in ("ne_err", "te_err"):
        np.testing.assert_array_equal(noisy[k], truth[k])
    # truth data is the input, untouched
    np.testing.assert_array_equal(truth["ne_data"], NE)
    np.testing.assert_array_equal(truth["te_data"], TE)


def test_noise_is_seeded_and_follows_documented_order():
    _, a = mst.make_datasets(NE, TE, 0.05, seed=3)
    _, b = mst.make_datasets(NE, TE, 0.05, seed=3)
    _, c = mst.make_datasets(NE, TE, 0.05, seed=4)
    for k in mst.KEYS:
        np.testing.assert_array_equal(a[k], b[k])
    assert not np.allclose(a["ne_data"], c["ne_data"], equal_nan=True)

    rng = np.random.default_rng(3)
    te_noise = rng.standard_normal(TE.size)
    ne_noise = rng.standard_normal(NE.size)
    np.testing.assert_allclose(a["te_data"], TE + 0.05 * TE * te_noise)
    np.testing.assert_allclose(a["ne_data"], NE + 0.05 * NE * ne_noise)


def test_noise_is_standard_normal_in_units_of_error():
    n = 20000
    ne = np.full(n, 1e19)
    te = np.full(n, 100.0)
    _, noisy = mst.make_datasets(ne, te, 0.05, seed=0)
    for key in ("ne", "te"):
        z = (noisy[f"{key}_data"] - (ne if key == "ne" else te)) / noisy[f"{key}_err"]
        assert abs(z.mean()) < 0.05
        assert abs(z.std() - 1) < 0.05


def test_nan_channels_found_and_kept():
    assert mst.nan_channels(NE, TE) == [3]
    truth, noisy = mst.make_datasets(NE, TE, 0.05, seed=0)
    for d in (truth, noisy):
        assert all(np.isnan(d[k][3]) for k in mst.KEYS)


@pytest.mark.parametrize("fraction", [0.0, -0.05])
def test_bad_error_fraction_rejected(fraction):
    with pytest.raises(ValueError):
        mst.make_datasets(NE, TE, fraction, seed=0)


def test_write_outputs_round_trip(tmp_path):
    truth, noisy = mst.make_datasets(NE, TE, 0.05, seed=0)
    meta = {"source": "balance.nc", "error_fraction": 0.05, "seed": 0}
    out = tmp_path / "out"
    paths = mst.write_outputs(out, "syn", truth, noisy, meta)

    assert paths["noisy"] == out / "syn.npz"
    assert paths["truth"] == out / "syn_truth.npz"
    assert paths["json"] == out / "syn.json"
    for key, expected in (("noisy", noisy), ("truth", truth)):
        with np.load(paths[key]) as f:
            assert sorted(f.files) == sorted(mst.KEYS)
            for k in mst.KEYS:
                np.testing.assert_array_equal(f[k], expected[k])
    assert json.loads(paths["json"].read_text()) == meta

    # refuses to overwrite unless asked
    with pytest.raises(FileExistsError):
        mst.write_outputs(out, "syn", truth, noisy, meta)
    mst.write_outputs(out, "syn", truth, noisy, {"seed": 1}, overwrite=True)
    assert json.loads(paths["json"].read_text()) == {"seed": 1}


def test_written_files_load_into_thomson_scattering(tmp_path):
    ThomsonScattering = pytest.importorskip("sims.instruments").ThomsonScattering
    truth, noisy = mst.make_datasets(NE, TE, 0.05, seed=0)
    paths = mst.write_outputs(tmp_path, "syn", truth, noisy, {})
    shape = (NE.size, 3)
    R, z, w = np.ones(shape), np.zeros(shape), np.ones(shape)
    with np.load(paths["noisy"]) as f:
        ts = ThomsonScattering(R=R, z=z, weights=w, measurements=dict(f))
    np.testing.assert_array_equal(ts.ne_err, noisy["ne_err"])
