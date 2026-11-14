# Input file for step 7: a known-answer test of the step transport profile.
#
# The TS data is synthetic, made from a converged SOLPS state whose transport is a
# step at the separatrix (D = 4 everywhere; chi = 10 inside, 4 outside), so the
# answer MESA should find is known. Every run starts from that converged state:
# ref_clean/b2fstate is copied to each run's b2fstati.
#
# Needs mesa from the mesa-ab branch (see HANDOFF.md): Solps.launch() takes
# `iteration`, and GPOptimizer counts the initial sample by rows.
from mesa.core import Mesa

# ----------------------------------------------------------------------------
#   path settings
# ----------------------------------------------------------------------------
from pathlib import Path
# directory in which the runs and the evaluations file are made; it holds
# baserun/ and ref_clean/
simulations_directory = Path("/pfs/work/g2om622/SOLPS-ITER/runs/mastu_sxd_46860_450ms_Donly_step7")

# file name in which the training data will be stored
evaluations_filepath = simulations_directory / "evaluations_data.h5"

# folder holding the synthetic TS data (synthetic_ts_refconv.npz, made with
# tools/make_synthetic_ts.py) and the TS instrument file it was made with
ts_data_directory = Path("/pfs/work/g2om622/src/ts_data/")


# ----------------------------------------------------------------------------
#   diagnostics settings
# ----------------------------------------------------------------------------
from numpy import load
from sims.instruments import ThomsonScattering
from mesa_solps.simulation import Solps
from mesa_solps.objective import SolpsLikelihood

# the instrument file the synthetic data was made with
instrument_data = load(ts_data_directory / "testing_ts_instrument_data.npz")
TS = ThomsonScattering(
    R=instrument_data['R'],
    z=instrument_data['z'],
    weights=instrument_data['weights'],
    # noisy synthetic data; synthetic_ts_refconv_truth.npz is the noise-free version
    measurements=load(ts_data_directory / "synthetic_ts_refconv.npz"),
)

objective_function = SolpsLikelihood(diagnostics=[TS])


# ----------------------------------------------------------------------------
#   simulation settings
# ----------------------------------------------------------------------------
simulation = Solps(
    n_proc=36,
    memory_gb=2,
    transport_profile_bounds=(-0.250, 0.240),
    # ref_clean holds the converged reference's b2.* parameter files, b2mn.dat,
    # input.dat and its final b2fstate (no b2fstati, no fort.* files). Each run
    # starts from that b2fstate, copied to the run's b2fstati.
    reference_directory=simulations_directory / "ref_clean",
    # one core value and one SOL value per profile, with the jump at the
    # separatrix +-1 mm (knots [left, -0.001, +0.001, right])
    profile_shape="step",
    # convergence test, check 1, on the saved times (points) in b2time.nc; no
    # other stop rule
    convergence_window_points=100,  # fit over the last 100 points, and the test must have held for 100 points more
    convergence_min_run_factor=3,   # no convergence before 3 x 100 points
    convergence_timescale=1.0,      # ne and Te (real outer-midplane cells, no guard cells) must change slower than this (s)
    max_continuations=10,           # how often an unconverged run is continued
)


# ----------------------------------------------------------------------------
#   strategy settings
# ----------------------------------------------------------------------------
from mesa.strategies import GPOptimizer
from inference.gp import SquaredExponential, QuadraticMean, UpperConfidenceBound

strategy = GPOptimizer(
    covariance_kernel=SquaredExponential(),
    mean_function=QuadraticMean(),
    acquisition_function=UpperConfidenceBound(kappa=1.),
    initial_sample_count=12,  # iteration 0: 12 random runs
    cross_validation=False,
    trust_region_width=0.3,
    n_processes=1,
    fit_stalled=False,  # stalled runs are left out of the GP fit
)


# ----------------------------------------------------------------------------
#   parameter settings
# ----------------------------------------------------------------------------
# parameters to fix or vary. To fix set as a single value. To vary set bounds as a tuple.
# With profile_shape="step" only these six are used: the core value is
# boundary_left + barrier_height and the SOL value boundary_right + barrier_height
# (the boundaries are heights above the barrier level, as for the barrier shape).
# The true state is chi_boundary_left 9.9, chi_boundary_right 3.9,
# D_boundary_left 3.9, D_boundary_right 3.9.
parameters = {
    'chi_boundary_left'  : (0.05, 100.0),  # core chi, above the barrier level
    'chi_boundary_right' : (0.05, 100.0),  # SOL chi, above the barrier level
    'chi_barrier_height' : 0.1,            # as in the earlier step fit

    'D_boundary_left'  : (0.05, 100.0),    # core D, above the barrier level
    'D_boundary_right' : (0.05, 100.0),    # SOL D, above the barrier level
    'D_barrier_height' : 0.1,              # as for chi_barrier_height
}

mesa = Mesa(
    parameters=parameters,
    simulation=simulation,
    objective_function=objective_function,
    strategy=strategy,
    simulations_directory=simulations_directory,
    evaluations_filepath=evaluations_filepath,
    max_concurrent_runs=12,
    # the last iteration number: iteration 0 is the random batch, then
    # iterations 1 to 25 each run one GP-proposed point
    max_iterations=25,
    # poll_interval not set: the default (1800 s) is used
)

mesa.run()
