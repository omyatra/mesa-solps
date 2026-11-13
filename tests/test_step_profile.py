"""
Tests for the transport profile shapes (Solps profile_shape): the step profile
("step") and the default barrier profile ("barrier"), written through
write_solps_transport_inputfile into a temporary folder. Run with pytest;
nothing here calls Slurm or SOLPS.

The step profile reproduces the transport files of an earlier fit made with a
version of mesa-solps whose profile_radius_axis was hard-coded to the knots
[left, -0.001, +0.001, right] (runs 0, 1 and 9 below). Set
MESA_STEP_REFERENCE_DATA to a folder holding that fit's evaluations_data.h5 and
b2.transport.inputfile_N files to check against those files as well.
"""

import ast
import inspect
import json
import os
import re
from pathlib import Path

import numpy as np
import pytest

from mesa_solps.models import (
    linear_transport_profile,
    profile_radius_axis,
    step_half_width,
    step_profile_knots,
)
from mesa_solps.parameters import conductivity_profile, diffusivity_profile
from mesa_solps.simulation import Solps, check_profile_shape, transport_profiles
from mesa_solps.transport import _fitted_kind, write_solps_transport_inputfile

repo = Path(__file__).resolve().parent.parent
bounds = (-0.250, 0.240)

# the last lines of the earlier fit's files; written out so that the trailing
# space after ".true." can't be lost
namelist_end = " no_pflux=.true. \n /\n"

# A template laid out like the earlier fit's files: the kind 1, 3 and 4 blocks
# are replaced, the other lines kept
template_text = """\
 &TRANSPORT
 ndata(1, 1 , 1 )= 2 ,
 tdata(1, 1 , 1 , 1 )= -0.250000 , tdata(2, 1 , 1 , 1 )= 1.000000 ,
 tdata(1, 2 , 1 , 1 )= 0.240000 , tdata(2, 2 , 1 , 1 )= 1.000000 ,
 ndata(1, 3 , 1 )= 2 ,
 tdata(1, 1 , 3 , 1 )= -0.250000 , tdata(2, 1 , 3 , 1 )= 1.000000 ,
 tdata(1, 2 , 3 , 1 )= 0.240000 , tdata(2, 2 , 3 , 1 )= 1.000000 ,
 ndata(1, 4 , 1 )= 2 ,
 tdata(1, 1 , 4 , 1 )= -0.250000 , tdata(2, 1 , 4 , 1 )= 1.000000 ,
 tdata(1, 2 , 4 , 1 )= 0.240000 , tdata(2, 2 , 4 , 1 )= 1.000000 ,
""" + namelist_end

# A template with other settings around the fitted blocks, as a reference
# case's file may have
template_with_extras = """\
 &TRANSPORT
 ndata(1, 1 , 1 )= 2 ,
 tdata(1, 1 , 1 , 1 )= -0.250000 , tdata(2, 1 , 1 , 1 )= 1.000000 ,
 tdata(1, 2 , 1 , 1 )= 0.240000 , tdata(2, 2 , 1 , 1 )= 1.000000 ,
 ndata(1, 3 , 1 )= 2 ,
 tdata(1, 1 , 3 , 1 )= -0.250000 , tdata(2, 1 , 3 , 1 )= 1.000000 ,
 tdata(1, 2 , 3 , 1 )= 0.240000 , tdata(2, 2 , 3 , 1 )= 1.000000 ,
 ndata(1, 4 , 1 )= 2 ,
 tdata(1, 1 , 4 , 1 )= -0.250000 , tdata(2, 1 , 4 , 1 )= 1.000000 ,
 tdata(1, 2 , 4 , 1 )= 0.240000 , tdata(2, 2 , 4 , 1 )= 1.000000 ,
 ndata(1, 7 , 1 )= 2 ,
 tdata(1, 1 , 7 , 1 )= -0.250000 , tdata(2, 1 , 7 , 1 )= 0.500000 ,
 tdata(1, 2 , 7 , 1 )= 0.240000 , tdata(2, 2 , 7 , 1 )= 0.500000 ,
 ! a comment line
 no_pflux=.true.
 /
"""

# The earlier fit's fixed parameters (the barrier parameters set so that the
# barrier profile collapses to a step), and its free ones for runs 0, 1 and 9,
# from its evaluations_data.h5
reference_fixed = {
    "chi_frac_left": 1.0, "chi_frac_right": 1.0, "chi_barrier_centre": 0.0,
    "chi_barrier_height": 0.1, "chi_barrier_width": 0.0,
    "chi_gap_left": 1e-6, "chi_gap_right": 1e-6,
    "D_frac_left": 1.0, "D_frac_right": 1.0, "D_barrier_centre": 0.0,
    "D_barrier_height": 0.1, "D_barrier_width": 0.0,
    "D_gap_left": 1e-6, "D_gap_right": 1e-6,
}
reference_runs = {
    0: {
        "chi_boundary_left": 95.41912659085118,
        "chi_boundary_right": 11.378335331016224,
        "D_boundary_left": 32.805427174835366,
        "D_boundary_right": 24.498044771201783,
    },
    1: {
        "chi_boundary_left": 40.06653507179105,
        "chi_boundary_right": 23.19400485684967,
        "D_boundary_left": 36.43718791753149,
        "D_boundary_right": 62.703528437291716,
    },
    9: {
        "chi_boundary_left": 52.635464942493826,
        "chi_boundary_right": 18.910287614367544,
        "D_boundary_left": 15.610284202277608,
        "D_boundary_right": 88.20377528563273,
    },
}

# The transport files those runs were given, as written
reference_files = {
    0: """\
 &TRANSPORT
 ndata(1, 1 , 1 )= 4 ,
 tdata(1, 1 , 1 , 1 )= -0.250000 , tdata(2, 1 , 1 , 1 )= 32.905427 ,
 tdata(1, 2 , 1 , 1 )= -0.001000 , tdata(2, 2 , 1 , 1 )= 32.905427 ,
 tdata(1, 3 , 1 , 1 )= 0.001000 , tdata(2, 3 , 1 , 1 )= 24.598045 ,
 tdata(1, 4 , 1 , 1 )= 0.240000 , tdata(2, 4 , 1 , 1 )= 24.598045 ,
 ndata(1, 3 , 1 )= 4 ,
 tdata(1, 1 , 3 , 1 )= -0.250000 , tdata(2, 1 , 3 , 1 )= 95.519127 ,
 tdata(1, 2 , 3 , 1 )= -0.001000 , tdata(2, 2 , 3 , 1 )= 95.519127 ,
 tdata(1, 3 , 3 , 1 )= 0.001000 , tdata(2, 3 , 3 , 1 )= 11.478335 ,
 tdata(1, 4 , 3 , 1 )= 0.240000 , tdata(2, 4 , 3 , 1 )= 11.478335 ,
 ndata(1, 4 , 1 )= 4 ,
 tdata(1, 1 , 4 , 1 )= -0.250000 , tdata(2, 1 , 4 , 1 )= 95.519127 ,
 tdata(1, 2 , 4 , 1 )= -0.001000 , tdata(2, 2 , 4 , 1 )= 95.519127 ,
 tdata(1, 3 , 4 , 1 )= 0.001000 , tdata(2, 3 , 4 , 1 )= 11.478335 ,
 tdata(1, 4 , 4 , 1 )= 0.240000 , tdata(2, 4 , 4 , 1 )= 11.478335 ,
""" + namelist_end,
    1: """\
 &TRANSPORT
 ndata(1, 1 , 1 )= 4 ,
 tdata(1, 1 , 1 , 1 )= -0.250000 , tdata(2, 1 , 1 , 1 )= 36.537188 ,
 tdata(1, 2 , 1 , 1 )= -0.001000 , tdata(2, 2 , 1 , 1 )= 36.537188 ,
 tdata(1, 3 , 1 , 1 )= 0.001000 , tdata(2, 3 , 1 , 1 )= 62.803528 ,
 tdata(1, 4 , 1 , 1 )= 0.240000 , tdata(2, 4 , 1 , 1 )= 62.803528 ,
 ndata(1, 3 , 1 )= 4 ,
 tdata(1, 1 , 3 , 1 )= -0.250000 , tdata(2, 1 , 3 , 1 )= 40.166535 ,
 tdata(1, 2 , 3 , 1 )= -0.001000 , tdata(2, 2 , 3 , 1 )= 40.166535 ,
 tdata(1, 3 , 3 , 1 )= 0.001000 , tdata(2, 3 , 3 , 1 )= 23.294005 ,
 tdata(1, 4 , 3 , 1 )= 0.240000 , tdata(2, 4 , 3 , 1 )= 23.294005 ,
 ndata(1, 4 , 1 )= 4 ,
 tdata(1, 1 , 4 , 1 )= -0.250000 , tdata(2, 1 , 4 , 1 )= 40.166535 ,
 tdata(1, 2 , 4 , 1 )= -0.001000 , tdata(2, 2 , 4 , 1 )= 40.166535 ,
 tdata(1, 3 , 4 , 1 )= 0.001000 , tdata(2, 3 , 4 , 1 )= 23.294005 ,
 tdata(1, 4 , 4 , 1 )= 0.240000 , tdata(2, 4 , 4 , 1 )= 23.294005 ,
""" + namelist_end,
    9: """\
 &TRANSPORT
 ndata(1, 1 , 1 )= 4 ,
 tdata(1, 1 , 1 , 1 )= -0.250000 , tdata(2, 1 , 1 , 1 )= 15.710284 ,
 tdata(1, 2 , 1 , 1 )= -0.001000 , tdata(2, 2 , 1 , 1 )= 15.710284 ,
 tdata(1, 3 , 1 , 1 )= 0.001000 , tdata(2, 3 , 1 , 1 )= 88.303775 ,
 tdata(1, 4 , 1 , 1 )= 0.240000 , tdata(2, 4 , 1 , 1 )= 88.303775 ,
 ndata(1, 3 , 1 )= 4 ,
 tdata(1, 1 , 3 , 1 )= -0.250000 , tdata(2, 1 , 3 , 1 )= 52.735465 ,
 tdata(1, 2 , 3 , 1 )= -0.001000 , tdata(2, 2 , 3 , 1 )= 52.735465 ,
 tdata(1, 3 , 3 , 1 )= 0.001000 , tdata(2, 3 , 3 , 1 )= 19.010288 ,
 tdata(1, 4 , 3 , 1 )= 0.240000 , tdata(2, 4 , 3 , 1 )= 19.010288 ,
 ndata(1, 4 , 1 )= 4 ,
 tdata(1, 1 , 4 , 1 )= -0.250000 , tdata(2, 1 , 4 , 1 )= 52.735465 ,
 tdata(1, 2 , 4 , 1 )= -0.001000 , tdata(2, 2 , 4 , 1 )= 52.735465 ,
 tdata(1, 3 , 4 , 1 )= 0.001000 , tdata(2, 3 , 4 , 1 )= 19.010288 ,
 tdata(1, 4 , 4 , 1 )= 0.240000 , tdata(2, 4 , 4 , 1 )= 19.010288 ,
""" + namelist_end,
}


def read_profiles(path):
    """Returns {kind: (positions, values)} for every profile block in a file."""
    pattern = re.compile(
        r"tdata\(1,\s*(\d+)\s*,\s*(\d+)\s*,\s*1\s*\)=\s*(\S+)\s*,\s*"
        r"tdata\(2,\s*(\d+)\s*,\s*(\d+)\s*,\s*1\s*\)=\s*(\S+)\s*,"
    )
    profiles, counts = {}, {}
    for line in Path(path).read_text().splitlines():
        if m := re.match(r"\s*ndata\(1,\s*(\d+)\s*,\s*1\s*\)=\s*(\d+)", line):
            counts[int(m.group(1))] = int(m.group(2))
        elif m := pattern.search(line):
            i, kind, x, j, kind2, y = m.groups()
            assert (i, kind) == (j, kind2), line
            positions, values = profiles.setdefault(int(kind), ([], []))
            assert int(i) == len(positions) + 1, line
            positions.append(float(x))
            values.append(float(y))
    for kind, (positions, _) in profiles.items():
        assert counts[kind] == len(positions), f"kind {kind}: ndata != points"
    return {k: (np.array(x), np.array(y)) for k, (x, y) in profiles.items()}


def write_file(directory, parameters, shape, template=template_text, name="out"):
    """Writes one run's transport file as Solps.launch does; returns its path."""
    directory = Path(directory)
    template_path = directory / f"{name}.template"
    template_path.write_text(template)
    D_radius, D, chi_radius, chi = transport_profiles(parameters, shape, bounds)
    out = directory / f"{name}.b2.transport.inputfile"
    write_solps_transport_inputfile(
        template=template_path,
        filename=out,
        grid_dperp=D_radius,
        values_dperp=D,
        grid_chieperp=chi_radius,
        values_chieperp=chi,
        grid_chiiperp=chi_radius,
        values_chiiperp=chi,
    )
    return out


def check_positions(profiles):
    """Every profile's positions are unique and strictly increasing."""
    for kind, (positions, _) in profiles.items():
        assert len(set(positions)) == len(positions), f"kind {kind}: duplicates"
        assert (np.diff(positions) > 0).all(), f"kind {kind}: not increasing"


# --- step profile ---------------------------------------------------------


def test_step_knots():
    x, y = step_profile_knots((3.9, 2.9, 0.1), bounds)
    assert x.tolist() == [-0.25, -step_half_width, step_half_width, 0.24]
    assert np.allclose(y, [4.0, 4.0, 3.0, 3.0], rtol=0, atol=1e-12)


@pytest.mark.parametrize("run", sorted(reference_runs))
def test_step_reproduces_reference_file(tmp_path, run):
    """The same file, byte for byte, as the earlier fit wrote for this run."""
    parameters = reference_runs[run] | reference_fixed
    out = write_file(tmp_path, parameters, "step")
    assert out.read_text() == reference_files[run]


@pytest.mark.parametrize("run", sorted(reference_runs))
def test_step_matches_barrier_with_reference_settings(run):
    """
    With the earlier fit's fixed parameters, the barrier profile evaluated at
    the step knots gives the step values, i.e. the step option computes what
    that fit's hard-coded knots gave.
    """
    parameters = reference_runs[run] | reference_fixed
    D_radius, D, chi_radius, chi = transport_profiles(parameters, "step", bounds)
    D_params = [parameters[k] for k in diffusivity_profile]
    chi_params = [parameters[k] for k in conductivity_profile]
    assert np.allclose(D, linear_transport_profile(D_radius, D_params, bounds), rtol=0, atol=1e-12)
    assert np.allclose(chi, linear_transport_profile(chi_radius, chi_params, bounds), rtol=0, atol=1e-12)


def test_step_only_needs_its_parameters(tmp_path):
    parameters = reference_runs[0] | {"chi_barrier_height": 0.1, "D_barrier_height": 0.1}
    out = write_file(tmp_path, parameters, "step")
    assert out.read_text() == reference_files[0]


def test_step_missing_parameter():
    parameters = dict(reference_runs[0])  # no barrier heights
    with pytest.raises(KeyError, match="barrier_height"):
        transport_profiles(parameters, "step", bounds)


def test_step_truth_gives_valid_file(tmp_path):
    """
    The converged reference state (D = 4 everywhere, chi = 10 inside the
    separatrix and 4 outside) as a step profile, with the barrier heights at 0.1.
    """
    parameters = {
        "D_boundary_left": 3.9, "D_boundary_right": 3.9, "D_barrier_height": 0.1,
        "chi_boundary_left": 9.9, "chi_boundary_right": 3.9, "chi_barrier_height": 0.1,
    }
    out = write_file(tmp_path, parameters, "step", template=template_with_extras)
    profiles = read_profiles(out)
    assert sorted(profiles) == [1, 3, 4, 7]
    check_positions(profiles)
    knots = [-0.25, -0.001, 0.001, 0.24]
    assert profiles[1][0].tolist() == knots
    assert profiles[1][1].tolist() == [4.0, 4.0, 4.0, 4.0]
    for kind in (3, 4):
        assert profiles[kind][0].tolist() == knots
        assert profiles[kind][1].tolist() == [10.0, 10.0, 4.0, 4.0]
    # the other settings are kept
    text = out.read_text()
    assert " tdata(1, 2 , 7 , 1 )= 0.240000 , tdata(2, 2 , 7 , 1 )= 0.500000 ," in text
    assert " ! a comment line\n" in text
    assert text.endswith(" no_pflux=.true.\n /\n")


def test_step_random_files_valid(tmp_path):
    """Boundary values drawn over the step-7 bounds (0.05 to 100)."""
    rng = np.random.default_rng(1)
    for i in range(200):
        parameters = {
            k: rng.uniform(0.05, 100.0)
            for k in ("chi_boundary_left", "chi_boundary_right",
                      "D_boundary_left", "D_boundary_right")
        } | {"chi_barrier_height": 0.1, "D_barrier_height": 0.1}
        profiles = read_profiles(write_file(tmp_path, parameters, "step", name=str(i)))
        assert sorted(profiles) == [1, 3, 4]
        check_positions(profiles)
        assert all(len(x) == 4 for x, _ in profiles.values())


@pytest.mark.parametrize("bad", [(-0.0005, 0.24), (-0.25, 0.001), (0.1, -0.1)])
def test_step_bounds_must_enclose_step(bad):
    with pytest.raises(ValueError, match="enclose the step"):
        check_profile_shape("step", bad)


def test_unknown_shape():
    with pytest.raises(ValueError, match="profile_shape"):
        check_profile_shape("Step", bounds)
    check_profile_shape("barrier", (0.1, -0.1))  # the barrier shape checks nothing


# --- the default (barrier) profile is unchanged ---------------------------


def write_barrier_as_before(directory, parameters):
    """
    The transport file as Solps.launch wrote it before profile_shape existed
    (its profile code, copied).
    """
    directory = Path(directory)
    template_path = directory / "before.template"
    template_path.write_text(template_with_extras)
    chi_params = [parameters[k] for k in conductivity_profile]
    chi_radius = profile_radius_axis(chi_params, bounds)
    chi = linear_transport_profile(chi_radius, chi_params, bounds)
    D_params = [parameters[k] for k in diffusivity_profile]
    D_radius = profile_radius_axis(D_params, bounds)
    D = linear_transport_profile(D_radius, D_params, bounds)
    out = directory / "before.b2.transport.inputfile"
    write_solps_transport_inputfile(
        template=template_path,
        filename=out,
        grid_dperp=D_radius,
        values_dperp=D,
        grid_chieperp=chi_radius,
        values_chieperp=chi,
        grid_chiiperp=chi_radius,
        values_chiiperp=chi,
    )
    return out


def input_file_parameters(name):
    """The parameters dict of an input file in the repo, read without running it."""
    tree = ast.parse((repo / name).read_text())
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "parameters"
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"no parameters in {name}")


def barrier_parameter_sets():
    """The midpoints of example_input.py's bounds, and 5 random points in them."""
    rng = np.random.default_rng(2)
    limits = input_file_parameters("example_input.py")
    sets = [{k: 0.5 * (lo + hi) for k, (lo, hi) in limits.items()}]
    for _ in range(5):
        sets.append({k: rng.uniform(lo, hi) for k, (lo, hi) in limits.items()})
    return sets


@pytest.mark.parametrize("index", range(6))
def test_barrier_unchanged(tmp_path, index):
    parameters = barrier_parameter_sets()[index]
    before = write_barrier_as_before(tmp_path, parameters).read_bytes()
    out = write_file(tmp_path, parameters, "barrier", template=template_with_extras)
    assert out.read_bytes() == before
    profiles = read_profiles(out)
    # 6 points around each of the 4 inner knots, 3 inside each edge, the edges
    assert all(len(x) == 32 for kind, (x, _) in profiles.items() if kind != 7)
    check_positions(profiles)


def test_barrier_is_default():
    default = inspect.signature(Solps).parameters["profile_shape"].default
    assert default == "barrier"


# --- check against the earlier fit's own files, if they are available ------

reference_data = os.environ.get("MESA_STEP_REFERENCE_DATA")


@pytest.mark.skipif(not reference_data, reason="MESA_STEP_REFERENCE_DATA not set")
@pytest.mark.parametrize("run", [0, 1, 9])
def test_step_reproduces_reference_data(tmp_path, run):
    pandas = pytest.importorskip("pandas")
    pytest.importorskip("tables")
    folder = Path(reference_data)
    df = pandas.read_hdf(folder / "evaluations_data.h5")
    row = df[df["run_number"] == run].iloc[0]
    skip = {"run_number", "iteration", "cauchy_logprob"}
    parameters = {c: float(row[c]) for c in df.columns if c not in skip}
    out = write_file(tmp_path, parameters, "step")
    expected = folder / f"b2.transport.inputfile_{run}"
    assert out.read_bytes() == expected.read_bytes()
    ours, theirs = read_profiles(out), read_profiles(expected)
    for kind in (1, 3, 4):
        assert np.array_equal(ours[kind][0], theirs[kind][0])
        assert np.array_equal(ours[kind][1], theirs[kind][1])


# --- build test for example_input_step7.py (nothing run or submitted) ------


def call_keywords(name, function):
    """The literal keyword arguments of the call to function in an input file."""
    tree = ast.parse((repo / name).read_text())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == function
        ):
            keywords = {}
            for k in node.keywords:
                try:
                    keywords[k.arg] = ast.literal_eval(k.value)
                except ValueError:
                    pass  # not a literal, e.g. a path or an object
            return keywords
    raise AssertionError(f"no call to {function} in {name}")


def test_step7_input_settings():
    solps = call_keywords("example_input_step7.py", "Solps")
    assert solps["profile_shape"] == "step"
    assert solps["convergence_window_points"] == 100
    gpo = call_keywords("example_input_step7.py", "GPOptimizer")
    assert gpo["initial_sample_count"] == 12
    mesa = call_keywords("example_input_step7.py", "Mesa")
    assert mesa["max_concurrent_runs"] == 12
    assert mesa["max_iterations"] == 25
    parameters = input_file_parameters("example_input_step7.py")
    free = {k: v for k, v in parameters.items() if isinstance(v, tuple)}
    assert free == {
        k: (0.05, 100.0)
        for k in ("chi_boundary_left", "chi_boundary_right",
                  "D_boundary_left", "D_boundary_right")
    }
    # as mesa's input-file check requires: floats, or tuples of two floats
    for value in parameters.values():
        values = value if isinstance(value, tuple) else (value,)
        assert all(isinstance(v, float) for v in values)


def build_step7_run(directory, seed=0):
    """
    One run's parameter set and transport file from example_input_step7.py, as
    the driver would make them for an initial (random) run: the free parameters
    drawn uniformly within their bounds, the fixed ones added. Writes
    parameters.json and b2.transport.inputfile into directory.
    """
    directory = Path(directory)
    solps = call_keywords("example_input_step7.py", "Solps")
    parameters = input_file_parameters("example_input_step7.py")
    rng = np.random.default_rng(seed)
    point = {k: rng.uniform(*v) for k, v in parameters.items() if isinstance(v, tuple)}
    point |= {k: v for k, v in parameters.items() if not isinstance(v, tuple)}
    (directory / "parameters.json").write_text(json.dumps(point, indent=2))
    template = directory / "reference.b2.transport.inputfile"
    template.write_text(template_with_extras)
    D_radius, D, chi_radius, chi = transport_profiles(
        point, solps["profile_shape"], solps["transport_profile_bounds"]
    )
    out = directory / "b2.transport.inputfile"
    write_solps_transport_inputfile(
        template=template,
        filename=out,
        grid_dperp=D_radius,
        values_dperp=D,
        grid_chieperp=chi_radius,
        values_chieperp=chi,
        grid_chiiperp=chi_radius,
        values_chiiperp=chi,
    )
    return point, out


def test_step7_build(tmp_path):
    point, out = build_step7_run(tmp_path)
    assert json.loads((tmp_path / "parameters.json").read_text()) == point
    profiles = read_profiles(out)
    assert sorted(profiles) == [1, 3, 4, 7]
    check_positions(profiles)
    knots = [-0.25, -0.001, 0.001, 0.24]
    for kind, prefix in ((1, "D"), (3, "chi"), (4, "chi")):
        positions, values = profiles[kind]
        assert positions.tolist() == knots
        core = point[f"{prefix}_boundary_left"] + point[f"{prefix}_barrier_height"]
        sol = point[f"{prefix}_boundary_right"] + point[f"{prefix}_barrier_height"]
        assert np.allclose(values, [core, core, sol, sol], rtol=0, atol=5e-7)
    # every line but the fitted blocks is the reference's
    kept = [l for l in out.read_text().splitlines() if _fitted_kind(l) is None]
    expected = [l for l in template_with_extras.splitlines() if _fitted_kind(l) is None]
    assert kept == expected
