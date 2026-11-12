"""
Tests for the convergence test (check_convergence) on small synthetic
b2time.nc files. Run with pytest; nothing here calls Slurm or SOLPS.
"""

import inspect

import numpy as np
import pytest
from scipy.io import netcdf_file

from mesa_solps.simulation import Solps, check_convergence, windows_pass

window = 100
minimum = 300
timescale = 1.0
dt = 2e-4  # s between saved points, as in real runs
cells = 38  # real outer-midplane cells; the file has 2 guard cells more


def profiles(n, ne_rate=0.0, te_rate=0.0, seed=0):
    """
    n points of flat ne and Te radial profiles (real cells only) with 0.1 %
    noise, growing as exp(rate * t); returns time, ne (m^-3), Te (eV).
    """
    rng = np.random.default_rng(seed)
    time = 1.0 + dt * np.arange(n)
    shape = np.linspace(1.0, 0.1, cells)
    ne = 1e19 * shape * np.exp(ne_rate * time)[:, None]
    te = 100.0 * shape * np.exp(te_rate * time)[:, None]
    ne *= 1 + 1e-3 * rng.standard_normal(ne.shape)
    te *= 1 + 1e-3 * rng.standard_normal(te.shape)
    return time, ne, te


def write_b2time(directory, time, ne, te, guard_ne=None, guard_te=None):
    """
    Writes directory/b2time.nc with timesa (time) and ne3da / te3da
    (time, nya), nya being the real cells plus a guard cell at each end.
    Te is stored in J, as SOLPS does. The guard cells copy their neighbour
    unless guard_ne / guard_te give their values, shape (n, 2).
    """
    n = len(time)
    if guard_ne is None:
        guard_ne = ne[:, [0, -1]]
    if guard_te is None:
        guard_te = te[:, [0, -1]]
    ne_full = np.column_stack([guard_ne[:, 0], ne, guard_ne[:, 1]])
    te_full = np.column_stack([guard_te[:, 0], te, guard_te[:, 1]]) * 1.602e-19
    with netcdf_file(directory / "b2time.nc", "w") as f:
        f.createDimension("time", None)
        f.createDimension("nya", cells + 2)
        f.createVariable("timesa", "d", ("time",))[:n] = time
        f.createVariable("ne3da", "d", ("time", "nya"))[:n] = ne_full
        f.createVariable("te3da", "d", ("time", "nya"))[:n] = te_full
    return directory


def converged(directory):
    return check_convergence(directory, window, minimum, timescale)


def test_default_window_is_100_points():
    default = inspect.signature(Solps).parameters["convergence_window_points"].default
    assert default == 100


def test_missing_file_cant_be_judged(tmp_path):
    assert converged(tmp_path) is None


def test_steady_run_converges(tmp_path):
    write_b2time(tmp_path, *profiles(minimum))
    assert converged(tmp_path) is True


def test_slow_drift_fails(tmp_path):
    # ne grows on a 0.5 s timescale, faster than the 1 s threshold
    write_b2time(tmp_path, *profiles(2 * minimum, ne_rate=2.0))
    assert converged(tmp_path) is False


def test_drift_slower_than_threshold_converges(tmp_path):
    write_b2time(tmp_path, *profiles(minimum, te_rate=0.5))
    assert converged(tmp_path) is True


def test_shorter_than_minimum_run_fails(tmp_path):
    write_b2time(tmp_path, *profiles(minimum - 1))
    assert converged(tmp_path) is False


def test_shorter_than_hold_fails_whatever_the_minimum(tmp_path):
    # 2 x window points are needed for the hold, even with a lower minimum
    write_b2time(tmp_path, *profiles(2 * window - 1))
    assert check_convergence(tmp_path, window, window, timescale) is False
    write_b2time(tmp_path, *profiles(2 * window))
    assert check_convergence(tmp_path, window, window, timescale) is True


def step_run(n, step_at):
    """A steady run with a 5 % step up in ne at point step_at."""
    time, ne, te = profiles(n)
    ne[step_at:] *= 1.05
    return time, ne, te


def test_passes_once_then_fails_is_not_converged(tmp_path):
    # steady for long enough to pass, then the step in the last window
    n = 2 * minimum
    write_b2time(tmp_path, *step_run(n, n - 30))
    assert converged(tmp_path) is False


def test_passing_only_in_the_last_window_is_not_converged(tmp_path):
    # the last window is steady, so the old single-window test would pass,
    # but the step is in an earlier window of the hold
    n = 2 * minimum
    step_at = n - window - 20
    time, ne, te = step_run(n, step_at)
    assert windows_pass(time[-window:], ne[-window:], te[-window:], window, timescale).all()
    write_b2time(tmp_path, time, ne, te)
    assert converged(tmp_path) is False


def test_hold_restarts_after_a_failure(tmp_path):
    # converged once every window of the hold is past the step, not before
    step_at = minimum
    write_b2time(tmp_path, *step_run(step_at + window + 50, step_at))
    assert converged(tmp_path) is False
    write_b2time(tmp_path, *step_run(step_at + 2 * window + 1, step_at))
    assert converged(tmp_path) is True


def test_verdict_independent_of_how_often_it_is_called(tmp_path):
    # the verdict on a file depends only on the file
    write_b2time(tmp_path, *step_run(2 * minimum, 2 * minimum - window - 20))
    assert {converged(tmp_path) for _ in range(3)} == {False}


def wild_guards(n, seed=1):
    """Guard-cell values that jump by orders of magnitude, with zeros and
    negative values, shape (n, 2)."""
    rng = np.random.default_rng(seed)
    wild = 10.0 ** rng.uniform(-3, 3, (n, 2))
    wild[::7] = 0.0
    wild[3::11] *= -1
    return wild


@pytest.mark.parametrize("ne_rate, expected", [(0.0, True), (2.0, False)])
def test_guard_cells_dont_change_the_verdict(tmp_path, ne_rate, expected):
    time, ne, te = profiles(minimum, ne_rate=ne_rate)
    write_b2time(tmp_path, time, ne, te)
    assert converged(tmp_path) is expected
    with np.errstate(all="ignore"):
        write_b2time(
            tmp_path,
            time,
            ne,
            te,
            guard_ne=1e19 * wild_guards(minimum, seed=1),
            guard_te=100 * wild_guards(minimum, seed=2),
        )
    assert converged(tmp_path) is expected


def test_windows_pass_matches_polyfit():
    rng = np.random.default_rng(3)
    n, w = 40, 10
    # uneven spacing, profiles drifting at different rates per column
    time = np.cumsum(rng.uniform(0.5, 1.5, n)) * 1e-3
    rates = rng.uniform(-3, 3, 4)
    ne = np.exp(rates * time[:, None]) * (1 + 1e-3 * rng.standard_normal((n, 4)))
    te = np.exp(-rates * time[:, None] / 2) * (1 + 1e-3 * rng.standard_normal((n, 4)))
    for limit in (0.2, 0.5, 1.0, 2.0):
        expected = []
        for start in range(n - w + 1):
            t = time[start : start + w]
            ne_slopes = np.polyfit(t, np.log(ne[start : start + w]), 1)[0]
            te_slopes = np.polyfit(t, np.log(te[start : start + w]), 1)[0]
            expected.append(
                (1 / abs(ne_slopes) > limit).all() and (1 / abs(te_slopes) > limit).all()
            )
        assert list(windows_pass(time, ne, te, w, limit)) == expected
