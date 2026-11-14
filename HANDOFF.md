# Handoff: mesa-solps

## Current state: driver fixes, series A, B, C and D done, plus fixes from the cluster checks and a dry run, and convergence check 1

Fixes to the SOLPS driver are being made from a commit plan kept outside this repo, as series of
commits labelled A1, A2, ... (A: launching runs, B: polling, C: failures and results, D: logging,
heartbeat and resume). **All four series are done: A (A1–A5), B (B1–B7), C (C1–C5) and D
(D1–D4).** Each commit message's "Tested:" section is still empty: it is filled in after the tests
on the cluster.

After series D, three more mesa-solps commits fix problems found in the first cluster checks (not
in the plan; see the last three rows of "Commits"): the run's starting state when the reference has
no `b2fstate`, a convergence window counted in `b2time.nc` points, and `b2mndr_stim` in each
run's `b2mn.dat`. The convergence settings changed names:

| Setting | Default | Floor | Meaning |
|---------|---------|-------|---------|
| `convergence_window_points` | 100 (was 25) | 5 | each fit uses this many points of `b2time.nc`; the test must hold for one whole window more (see "Convergence check 1"); must be an `int` |
| `convergence_min_run_factor` | 3 | 2 | no convergence before ceil(factor × window) points |
| `convergence_timescale` | 1.0 s | – | unchanged |

`convergence_window` and `convergence_min_run_time` are gone (passing them is a `TypeError`).

Then five more mesa commits fix problems found in a dry run of the driver with fake Slurm tools
(every driver path ran; nothing was submitted). They are the last five rows of "Commits":

- After a restart, the interrupted iteration carries on under its own number (`iteration.json`
  in the case folder).
- Stalled runs are left out of the GP fit.
- All-equal scores stop the driver with a clear error.
- `max_iterations` is documented.
- Short Ctrl-C message, clearer refusal message, plain numbers in the logs.

What the review of that dry run found about proposals per iteration and what `max_iterations`
counts is in "Open questions".

One more mesa commit (`6d6c8cd`, last row of "Commits") fixes the initial-sample count in
`GPOptimizer`: it counted the highest run number, which starts at 0, so after N initial runs one
more random run was drawn and iteration 1 was a 1-run random top-up. It now counts the rows of the
evaluations data, so iteration 1 is the first GP proposal.

Then convergence "check 1" (agreed on 2026-11-11) replaced the test in `check_convergence`, in three
mesa-solps commits plus a test file (rows `7641b59` to `317d9ab` of "Commits"):

- the window is 100 points by default (was 25);
- the two guard cells of `ne3da` / `te3da` are left out (38 real cells for the MAST-U grid);
- the test must have held for one whole window.

The threshold (1 s), the floors, `convergence_min_run_factor` and check 2 (Δscore) are unchanged.
The sanity check on real runs, timings and the solps-babysitter follow-up are in
"Convergence check 1" below.

Synthetic Thomson-scattering data for step 7a (a known-answer test) was made from the converged
D-only reference state with two new scripts in `tools/` and a test file; see "Synthetic TS data
for step 7a".

A step transport profile (`Solps(profile_shape="step")`) was added for step 7, so the fit can use
the earlier step fit's 4-parameter setup, with tests and a draft input file
`example_input_step7.py`; see "Step transport profile for step 7". It is on its own branch,
`worktree-step-profile`, based on `worktree-mesa-ab`.

New runs now continue in time from the reference state (`b2mndr_stim` `'-1'` in new runs too,
decided 2026-11-14; was `'0'`, time from 0), on branch `fresh-run-stim-continue`; see "Time" in
"Step 7 launch on Gateway". Before the launch, `baserun/` must hold no `b2time.nc` or other
appended B2 output (check in "Launch").

**Next:** push the mesa branch, then the cluster tests with mesa installed from the `mesa-ab`
branch (see below and "What the cluster tests must check"), then fill in the "Tested:" sections.
The mesa pin in `pyproject.toml` stays where it is until full testing is done; only then does it
move to the last mesa commit (this pin move is the last commit of the plan). Before the main mesa
test, decide when logging starts (see "Open questions": start-up warnings and errors don't reach
`mesa.log`).

Branches (local, not pushed):

- mesa-solps: `worktree-mesa-ab`
- mesa-solps: `worktree-step-profile` (`worktree-mesa-ab` plus the step profile, its tests, the
  draft step-7 input file and this HANDOFF update)
- mesa-solps: `fresh-run-stim-continue` (from `worktree-mesa-ab` at `edc996d`: new runs continue
  in time from the reference state, and this HANDOFF update)
- mesa: `mesa-ab` (14 commits: one needed by A4, then B6, B7, C1, C2, D1, D2 and D3, then five
  from the dry run, then the initial-sample count fix)

**mesa-solps needs mesa from the `mesa-ab` branch.** From A4 on, `Solps.launch()` takes
`iteration`, which only mesa `d484c39` and later pass. B6 (poll interval), B7 (error handling),
C1 (safe evaluations file) and C2 (status column, `"stalled"`) are engine changes the driver needs
too. From C4 on, the plug-in returns `"stalled"`, which an older engine doesn't know: the run
would never leave its slot and the iteration would never end. D4's adoption hooks and
`SolpsRun.job_id` are only used by an engine with D2 and D3. The `pyproject.toml` pin still
points at `468c754`, so
`pip install .` alone installs a mesa that doesn't pass `iteration`, and the first launch fails
with a TypeError (before anything is created or submitted). Until the pin moves (the last commit
of the plan, after full testing is done), install mesa from the `mesa-ab` branch as an
editable install after installing mesa-solps:

```
pip install -e .                  # mesa-solps
pip install -e <mesa checkout>    # mesa on branch mesa-ab, replaces the pinned mesa
```

### Convergence check 1

What the test is now (`check_convergence`, `mesa_solps/simulation.py`):

- **Window:** `convergence_window_points` defaults to 100 points (was 25). The name, the `int`
  check, the floor (5), `convergence_min_run_factor` (3, floor 2) and the 1 s timescale are
  unchanged, so the default minimum run is 300 points.
- **Guard cells:** `ne3da` and `te3da` are `(time, nya)`, with `nya` = ny + 2 = 40 here: the
  outer-midplane column from iy = −1 to iy = ny. Checked on a real file before coding: `dsa` (the
  outer-midplane radial coordinate) steps by half a cell from column 0 to 1 (5.2 mm against 9.8 mm
  next) and from 38 to 39 (2.2 mm against 4.4 mm), so columns 0 and 39 sit on the boundary faces;
  `dsa` changes sign between columns 20 and 21, matching `jsep` with the guard cell first. Only
  columns 1 to 38 are fitted.
- **Hold:** the run is converged only if the test passes for the window of `window_points` points
  ending at each of the last `window_points + 1` points, i.e. over the last 2 × `window_points`
  points. Any failing window means not converged, and the hold starts again after it. Nothing is
  stored: the verdict is worked out from `b2time.nc` on every call, so it doesn't depend on when or
  how often the driver polls, or on a restart. A file shorter than 2 × `window_points` is not
  converged whatever `minimum_points` is (with the floors the minimum run already covers it). The
  "`timesa` not strictly increasing" warning is now checked over those 2 × `window_points` points.
- **Fits:** the windows are fitted together by a new module-level `windows_pass(time, ne, te,
  window_points, timescale)`, one bool per window; its slopes are the same least-squares slopes as
  `numpy.polyfit` (checked window by window on real files and in the tests).

**Sanity check on real runs** (read-only copies of the run folders; the old check is 25 points, all
40 columns, a single fit, minimum 75 points; the new one is 100 points, 38 columns, the hold,
minimum 300 points; 1 s threshold for both; the saved-time step is 2e-4 s in all four, so 100
points are 0.02 s of simulated time). "First" means the shortest prefix of the file on which the
check passes, i.e. when a driver polling every point would have stopped the run:

| Run | Points (simulated time) | Old verdict | New verdict | Old check first passes | New check first holds |
|-----|-------------------------|-------------|-------------|------------------------|-----------------------|
| `version_step` (D + C) | 609 (2.386–2.507 s, continued from an earlier state) | converged | converged | point 75 (0.015 s in) | point 300 (t = 2.445 s, 0.059 s in) |
| `Donly_5b/run_0` | 2259 (0–0.450 s) | not converged | not converged | never | never |
| `Donly_5b/run_1` | 2115 (0–0.421 s) | not converged | converged | point 1696 (t = 0.338 s) | point 1645 (t = 0.328 s) |
| `Donly_5b/run_2` | 2259 (0–0.450 s) | not converged | converged | never | point 1633 (t = 0.325 s) |

- The old 25-point fits are dominated by point-to-point noise: on the 5b runs no 25-point window
  passes (0 %) except one in `run_1` (point 1696, and it fails again at the end of the file); on
  `version_step` 76 % pass, so the old verdict flips from poll to poll. With 100 points, 19 %
  (`run_0`), 28 % (`run_1`), 32 % (`run_2`) and 100 % (`version_step`) of windows pass.
- Leaving out the guard cells changed no verdict on these four files (the pass fractions with and
  without them agree to 0.01); it guards against boundary values the fit shouldn't see.
- `run_0`: 46 of the last 101 windows pass; the slowest real cell in the last window has
  τ(ne) = 1.29 s and τ(Te) = 2.39 s, so it is close but keeps failing.
- `run_1`: once it holds (point 1645) it stays converged to the end of the file; at that point
  the slowest τ is 1.12 s (Te) and it grows to 1.8 s by the end.
- `run_2`: it holds at point 1633 (slowest τ(Te) 1.11 s) for only 9 points, fails again over
  points 1642–1768 and 1797–1905, holds briefly over 1769–1796 and holds from point 1906
  (t = 0.380 s) to the end. A driver stops the run at the first hold (`.quit`), so it would stop
  `run_2` at 0.325 s, where it was only just under the threshold (see "Open questions").
- `timesa` is strictly increasing in all four files.

**Timing:** one `check_convergence` call on a full-length file (57–102 MB, 609–2259 points) takes
11–16 ms for the first call in a process and 6–9 ms for later ones, with the file in the page cache.
Reading a file that isn't cached (e.g. over a network file system) was not measured; it is
dominated by reading `ne3da` / `te3da`, which are record variables spread through the whole file.

**solps-babysitter follow-up** (not changed from here). It calls `check_convergence` through
`solps_babysitter/mesa_link.py` with the same keyword arguments (`window_points`,
`minimum_points`, `timescale`), so it gets the guard cells and the hold with no change. What it
will need:

- Its input files (`example_input.py`, `example_power_ramp.py`) set
  `convergence_window_points = 25` explicitly; set 100 to match the driver's new default (with 25
  the hold spans only 50 points and the noisy 25-point fits rarely pass).
- `diagnostics.py` (`timescales`) has its own copy of the fit: all 40 columns and only the last
  window. Its reported timescales will now disagree with the verdict. It should leave out
  columns 0 and −1, and report the hold (e.g. how many of the last `window_points + 1` windows
  pass, or since which point the test has held), e.g. by calling `windows_pass` through
  `mesa_link.py`.
- A run needs 2 × `window_points` points before it can pass at all; its "minimum" display, if
  any, should use max(`minimum_points`, 2 × `window_points`).

### Synthetic TS data for step 7a

Thomson-scattering data made from a known SOLPS state, so step 7a can test whether MESA finds
it. New files only (no existing code changed):

- `tools/make_synthetic_ts.py`: builds sim-solps's `ThomsonScattering` (the model MESA scores
  with) on a `balance.nc` with the R, z and weights of the TS instrument file, takes the true ne
  and Te per channel from `predictions()`, warns about NaN channels (outside the mesh), sets the
  errors to a flat fraction of the true value (default 5 %, as in the old test data) and adds
  Gaussian noise with a fixed seed (default 0; `default_rng(seed)`, Te noise then ne noise).
  It writes `<name>.npz` (noisy), `<name>_truth.npz` (noise-free, same errors), both with
  `te_data`, `te_err`, `ne_data`, `ne_err`, and `<name>.json` (source path, its mtime,
  instrument file, error fraction, seed, NaN channels, git commit). It refuses to overwrite
  without `--overwrite`. Options: `--balance`, `--instrument`, `--out-dir`, `--name` (default
  `synthetic_ts_refconv`), `--error-fraction`, `--seed`.
- `tools/check_synthetic_ts.py`: the checks below, and the plot.
- `tests/test_make_synthetic_ts.py`: errors, seeded noise (and its documented draw order), the
  noise's distribution, NaN channels, a bad error fraction, writing and reading back, refusing to
  overwrite, loading into `ThomsonScattering(measurements=...)`. No `balance.nc` needed.

**Made from:** the converged D-only MAST-U reference state (`refconv/balance.nc`; D⊥ = 4,
χe = χi = 10 inside the separatrix and 4 outside), with the instrument file
`testing_ts_instrument_data.npz` (23 channels × 11 samples), at commit `3c4f29b`. Output
(kept outside the repo): `synthetic_ts_refconv.npz`, `synthetic_ts_refconv_truth.npz`,
`synthetic_ts_refconv.json`, `comparison.png`. Run time about 4 s.

**Checks** (`tools/check_synthetic_ts.py`):

- **NaN channels: none.** All 23 channels have > 95 % of their weight inside the mesh, so all
  are predicted: 46 points (23 ne + 23 Te).
- Both files load through `ThomsonScattering(measurements=...)` (the check MESA does), and the
  truth file equals a fresh `predictions()` to 1e-12.
- **Scores** with the likelihood `SolpsLikelihood` uses: `cauchy_likelihood` from
  `sims.likelihoods`, −Σ log(1 + z²) with z = (data − prediction) / error, summed over ne and
  Te. Scored by calling `SolpsLikelihood.evaluate` on the state itself:

  | Data | `cauchy_logprob` | Gaussian χ² |
  |------|------------------|-------------|
  | truth | 0.000 | 0.00 |
  | noisy (seed 0) | −19.081 | 31.40 |
  | old test data | −0.041 | 0.04 |

  The truth score is 0, the best possible (each term is ≤ 0). For 46 points with Gaussian noise
  the Cauchy score has mean −24.55, sd 3.51 and a 95 % range of [−31.71, −17.93] (Monte Carlo,
  200 000 draws). −19.08 is inside it, at the 94.5th percentile: seed 0 happens to give
  slightly small residuals (χ² = 31.4 against 46 ± 9.6, 1.5 sd low). It is in the range
  expected.
- **Plot** (`comparison.png`): ne and Te against R (channel-weighted mean of the sample points):
  truth line, noisy points with error bars, old test data. The noisy points scatter about the
  truth within their errors.

**Copying the data to the cluster:** copy the two `.npz` files and the `.json` (the plot is
optional) to wherever the 7a input file reads its TS data, e.g.
`scp <output folder>/synthetic_ts_refconv*.{npz,json} <cluster>:<data folder>/`, and check
them with `sha256sum` at both ends. In the 7a input file, load
`synthetic_ts_refconv.npz` (or `_truth.npz` for a noise-free test) as the `measurements` of
`ThomsonScattering`, with the same instrument file as here.

### Step transport profile for step 7

Step 7 fits the synthetic TS data above with the setup of an earlier step fit (made with a
modified copy of upstream mesa-solps): a step transport profile, one core value and one SOL value
per coefficient with the jump at the separatrix ±1 mm, and 4 free parameters
(`chi_boundary_left/right`, `D_boundary_left/right`, each in (0.05, 100)). The true transport
(D⊥ = 4; χ = 10 inside, 4 outside) is a step, so it can be reached.

**How the earlier fit makes its step.** Its `models.py` differs from ours only in
`profile_radius_axis`, which returns the fixed knots `[left, -0.001, +0.001, right]` and ignores
the parameters (the knot-spacing code is commented out). Its `simulation.py` profile code is
the same as ours: `linear_transport_profile` (the barrier profile, unchanged) is evaluated at
those 4 knots. Its input file fixes the other 14 parameters so that the barrier collapses to a
step: `frac_left/right` 1, `barrier_centre` 0, `barrier_height` 0.1, `barrier_width` 0,
`gap_left/right` 1e-6. Then at −0.25 and −0.001 the profile is the left asymptote
`boundary_left + barrier_height` (with frac 1 the left slope is 0), and at +0.001 and +0.24 it is
`boundary_right + barrier_height`. So each written value is the boundary parameter + 0.1, e.g.
run 0: `D_boundary_left` 32.805427 → 32.905427. The χe (kind 3) and χi (kind 4) profiles are
the same χ profile.

**Why our fork broke with those parameters.** Our `profile_radius_axis` places 6 points around
each of the barrier's 4 inner knots, spaced by the distance to the neighbouring knot. With width
0 and gaps 1e-6 the 4 knots are within 2 µm of each other, so 24 of the 32 points print (6
decimals) as −0.000001, 0.000000 or 0.000001, with different values at the same printed
position, and the value at 0.000000 is the barrier level 0.1. Checked on run 0's parameters.

**What changed** (commit `9424724`):

- `Solps(profile_shape=...)`: `"barrier"` (default, the existing profile) or `"step"`.
- `models.step_profile_knots(params, boundaries)`: knots `[left, -0.001, +0.001, right]`
  (`step_half_width` = 0.001 m) and values `[core, core, sol, sol]` with
  core = `boundary_left + barrier_height` and sol = `boundary_right + barrier_height`, which is
  what the earlier fit's barrier profile gives at those knots with its fixed settings.
  `params` is `(boundary_left, boundary_right, barrier_height)` (`parameters.step_conductivity_profile`
  and `step_diffusivity_profile`). The other 7 parameters per profile are not used and need not be
  in the input file.
- `simulation.transport_profiles(parameters, profile_shape, bounds)`: returns
  `(D_radius, D, chi_radius, chi)`; the barrier branch is the old code from `Solps.launch()`,
  moved unchanged, and `launch()` calls it at the same point as before (after the run folder is
  made). It can be called without `Solps` (whose start-up needs the Slurm tools).
- `check_profile_shape()` at start-up (in `Solps.__init__`, before `check_tools()`): an unknown
  shape, or step bounds that don't satisfy left < −0.001 and right > 0.001, is a `ValueError`.
  For `"barrier"` nothing is checked (as before). A missing step parameter is a `KeyError` naming
  it, raised in `launch()`.
- `write_solps_transport_inputfile` and `build_solps_case` are unchanged. The step parameters are
  all in `required_parameters`, so they are not treated as `.mesa` template parameters.

**Mapping, earlier fit → ours:**

| Earlier fit | Ours (`profile_shape="step"`) |
|-------------|-------------------------------|
| knots `[left, -0.001, 0.001, right]` from the hard-coded `profile_radius_axis` | `step_profile_knots`, same knots |
| values: `linear_transport_profile` at the knots, with frac 1, centre 0, width 0, gap 1e-6 | `boundary_left/right + barrier_height`, directly |
| 18 parameters in the input file (14 fixed) | 6 needed: the 4 boundaries and the 2 barrier heights; the rest ignored |
| `set_div_transport`, `no_pflux=.true.` written by the writer | taken from `ref_clean/b2.transport.inputfile` (our template writer) |

The values agree whenever frac is 1 (the earlier fit's settings). With other frac or gap values the
earlier code would give a value between the asymptote and the barrier level at ±0.001; ours always
gives the asymptote.

**Tests** (`tests/test_step_profile.py`, commit `3b4fbe0`; `pip install pytest`, then
`python -m pytest tests`): 46 passed, 3 skipped (the optional reference-data checks), with the
two older test files included; 0.5 s. With `MESA_STEP_REFERENCE_DATA` set to the folder holding
the earlier fit's `evaluations_data.h5` and `b2.transport.inputfile_{0,1,9}`, those 3 pass too
(needs `tables`).

- **Reproduction of runs 0, 1 and 9: byte-identical** to the earlier fit's files (the same knots,
  values and formatting, down to the trailing space in `no_pflux=.true. `), when the template is
  laid out as those files are (`&TRANSPORT`, the kind 1, 3 and 4 blocks, `no_pflux=.true.`, `/`).
  This is checked twice: against the files embedded in the test (parameters from the
  evaluations file, at full precision), and, with `MESA_STEP_REFERENCE_DATA`, against the files
  and the evaluations file themselves (all 18 parameters as recorded). In a real run our file
  differs from theirs only in what comes from `ref_clean/b2.transport.inputfile` (its other
  lines, e.g. a kind 7 block, `no_pflux`), not in the fitted blocks. With the earlier fit's fixed
  parameters, the barrier profile evaluated at the step knots equals the step values (to 1e-12).
- **Positions:** unique and strictly increasing in every written profile, for 200 random step
  points over (0.05, 100), the truth, the build test and the 6 barrier sets.
- **Truth** (`D_boundary_left/right` 3.9, `chi_boundary_left` 9.9, `chi_boundary_right` 3.9,
  barrier heights 0.1): kind 1 is 4.000000 at all 4 knots; kinds 3 and 4 are 10.000000,
  10.000000, 4.000000, 4.000000. The template's other lines (kind 7 block, a comment,
  `no_pflux`) are kept.
- **Barrier path unchanged:** for the midpoints of `example_input.py`'s bounds and 5 random points
  in them, `transport_profiles(..., "barrier", ...)` writes the same bytes as the profile code
  copied from before the change (32 points per profile). The default of `profile_shape` is
  `"barrier"`.
- Errors: unknown shape (`"Step"`), step bounds not enclosing ±1 mm, a missing barrier height.
- A fresh non-editable `pip install .` imports `mesa_solps.simulation` and `.objective`.

**Build test (nothing submitted):** `test_step7_build` (also run by hand into a temporary folder)
reads `example_input_step7.py` with `ast`, without running it, draws one initial run's free
parameters uniformly within their bounds (as `GPOptimizer` does), adds the fixed ones, and writes
`parameters.json` and `b2.transport.inputfile` from a template with extra lines. Seed 0 gave
`chi_boundary_left` 63.714, `chi_boundary_right` 27.015, `D_boundary_left` 4.145,
`D_boundary_right` 1.702: written as D 4.245304 / 1.801937 and χ 63.814321 / 27.115182 at
−0.25, −0.001 | 0.001, 0.24, with the template's other lines unchanged. `test_step7_input_settings`
checks the input file's settings (step shape, window 100, 12 initial runs, 12 concurrent runs,
`max_iterations` 25, the 4 free parameters and their bounds, floats only as mesa's input check
requires).

**`example_input_step7.py` (draft, commit `8f235d9`).** As `example_input.py`, with:
`profile_shape="step"`; the 4 free parameters in (0.05, 100.0) and `chi/D_barrier_height` fixed
at 0.1; convergence check 1 (`convergence_window_points=100`, factor 3, timescale 1 s), no other
stop rule; TS measurements `synthetic_ts_refconv.npz`; `initial_sample_count=12`,
`max_concurrent_runs=12`, `max_iterations=25` (iteration 0: 12 random runs; iterations 1 to 25:
one GP point each, so 37 runs at most, plus continuations); the GP settings of the earlier fit
(SquaredExponential, QuadraticMean, UCB κ = 1, trust region 0.3).

**Filled in (commit `d67dda0`):** both paths are set; `memory_gb` 2 (was 20); `n_proc` 36,
`max_continuations` 10, `fit_stalled=False`, `poll_interval` default (1800 s) and the barrier
heights 0.1 are settled, so the file has no CHECK or TODO left. The start state is no longer a
separate task: `ref_clean/` holds the converged reference's final `b2fstate` (and no
`b2fstati`), which `build_solps_case` copies to each run's `b2fstati`. `ref_clean/b2mn.dat`
keeps `b2mndr_ntim` 100000 (decided).

### Step 7 launch on Gateway

**How a run starts** (read from the code; nothing run). SOLPS paths are relative to the
SOLPS-ITER `src/` tree (`runs/Makefile`) and `src/modules/`; line numbers are from a local copy of
the source and may be off by a few lines in the version on the cluster:

- **Start state:** `build_solps_case` copies `ref_clean/b2fstate` to `run_N/b2fstati` with
  `shutil.copy` (`mesa_solps/simulation.py:621`, file from `reference_state_file`, `:700-709`).
  `shutil.copy` copies data and mode but not times, so the copy's mtime is the launch time. The
  SOLPS runs `Makefile` rebuilds `b2fstati` with `b2ai` only if it is older than `b2ag.dat`,
  `b2ai.dat` or `b2fgmtry` (`runs/Makefile:177`, found in the run folder or `baserun/` by
  `vpath`, `:131-134`), which were copied into `baserun/` before the launch, so `b2ai` is not
  rerun. A continuation renames `b2fstate` to `b2fstati` (`simulation.py:257`), and that
  `b2fstate` was written by the job, so it is newer too.
- **Files needed:** only `b2fstati` (plus `baserun/` and the `fort.1` link made by
  `setup_baserun_eirene_links`). `b2mn` depends on `b2mn.dat b2fgmtry b2fpardf b2fstati
  b2frates fort.30 AMJUEL` (`runs/Makefile:192`), no `fort.*` restart file and no `b2time.nc`.
  `b2time.nc` is only read back to append to it when `b2mndr_stim` < 0 and an existing file is
  found (`B2.5/src/modules/b2mod_mwti.F90:347-371`); if none is found, B2 creates one ("b2time.nc
  will be created", `:350-357`), whatever stim is. A new run has `'-1'` (`simulation.py:629-637`)
  but no `b2time.nc` in its folder, so it starts a new file. Where B2 looks: it runs in
  `run_N/b2mn.exe.dir/`, which the Makefile deletes and makes again at the start of each job
  (`runs/Makefile:196`, `:242`), and `find_file` (`B2.5/src/utility/open_file.F:193-230`) tries
  `./`, then `../` (= `run_N/`), `../baserun/` (= `run_N/baserun/`, normally absent) and
  `../../baserun/` (= the case folder's shared `baserun/`). The path found is the one B2 then
  writes to (`filename` is saved, `b2mod_mwti.F90:186`, and reopened for each write, `:1448`). So a
  continuation appends to `run_N/b2time.nc` in place, and a new run's file is made in
  `b2mn.exe.dir/` and moved to `run_N/` at the end of the job (`runs/Makefile:278`). **If the
  shared `baserun/` holds a `b2time.nc`, every new run appends to that one file instead** (and
  no `run_N/b2time.nc` appears, so the driver logs "needs attention" after 1 h and calls the run
  crashed when the job ends). The other files B2 appends to when stim < 0 follow the same
  pattern (create if not found, append to the one found): `b2tallies.nc`
  (`B2.5/src/output/tallies.F:586-614`), `b2wall.nc` (`B2.5/src/sources/b2stbr.F:1155-1163`),
  `b2batch.nc` (`b2mod_mwti.F90:398-410`), `b2movies.nc` and `eirenemovies.nc`
  (`B2.5/src/user/cdfmovie.F:75-80`, `:261-266`), and the `tracing/*.trc` files
  (`B2.5/src/user/b2mod_file.F:94-98`, `b2mod_usrtrc.F:1798-1806`, `b2mod_wrsrt.F:232-241` and the
  other `b2mod_bln*.F`, `b2mod_wrint.F`, `b2mod_wrsep.F`, `b2mod_usrspb.F`); see the check before
  the launch below. `balance.nc` is always written new (`nf_create` with `NF_CLOBBER`,
  `B2.5/src/modules/b2mod_balance.F:2844`); `read_balance` is only called from the IMAS output
  code (`B2.5/src/ids/b2mod_ual_io.F90:1052`). EIRENE doesn't read `b2mndr_stim`. EIRENE reads `fort.15` only for a census start (`NFILEJ` 2 or 3,
  `Eirene/src/startup-routines/setup_time_surface.f:118-122`), skips Monte Carlo and reads
  saved tallies only for `NFILEN` 2 or 7 (`main-routines/eirmod_mcarlo.F:337`), and writes
  `fort.13` if it is missing (`startup-routines/input.F:857-863`). Not checked here: that
  `ref_clean/input.dat` uses none of these (block 1, `NFILEJ` and `NFILEN` below 2).
- **Time:** a new run continues in time from the reference state (decided 2026-11-14; until
  then a new run had `b2mndr_stim` `'0'`, which reset the time to 0). With `'-1'`, B2 keeps the
  time stored in `b2fstati` (`B2.5/src/driver/b2mod_driver.F:991-996`, `:2319-2329`), so the
  time printed and saved in `b2time.nc` carries on from refconv's end time, in new runs and
  continuations alike. Each run's `b2time.nc` history still starts with the run (a new file, see
  above), and the convergence test fits against `timesa`, so the start time doesn't matter to it
  (`version_step` in "Convergence check 1" started at 2.386 s). What else sees the absolute time
  (none of it checked in `ref_clean/` here):
  - `b2mndr_etim` must be 0 (or absent): B2 stops with "faulty input etim" unless etim is 0 or
    later than the start time (`b2mod_driver.F:2330-2331`), and a nonzero etim is an absolute
    end time (`:2788`). The local copies of the 5b runs and `version_step` don't set it.
  - Time-dependent inputs are read against the absolute time, e.g. the density feedback
    `b2mndr_ne_wanted_time` (`b2mod_driver.F:1775`, `:2481`) and `b2news_l_timbound`
    (`B2.5/src/modules/b2mod_boundary_namelist.F:414`); if `ref_clean/` uses any, they now see
    refconv's end time, not 0.
- **Stopping:** at each poll, a job that Slurm lists as RUNNING gets the convergence test, and if
  it holds the driver touches `run_N/b2mn.exe.dir/.quit` (`simulation.py:137-138`,
  `:182-193`). `b2mn` checks for `.quit` after every time step (`b2mod_driver.F:2747`, `:2784`)
  and stops cleanly, so a converged run is stopped mid-job, at most one `poll_interval` after it
  converged. The test is run again when the job ends (`simulation.py:227`).

**Launch.** In the mesa-solps checkout on Gateway (installed as before, with mesa installed
editable from `mesa-ab`). The step 7 commits must be pushed first: they are local only.

```
git fetch origin
git checkout worktree-mesa-ab
git pull --ff-only origin worktree-mesa-ab
echo $status
```

`$status` should print 0. Before the launch, check the shared `baserun/` (in the case folder,
next to where the `run_N/` folders go) and `ref_clean/b2mn.dat` (see "Files needed" and "Time"
above):

```
cd <case folder>
ls -d baserun/b2time.nc baserun/b2tallies.nc baserun/b2wall.nc baserun/b2batch.nc \
      baserun/b2movies.nc baserun/eirenemovies.nc baserun/tracing
grep etim <ref_clean>/b2mn.dat
```

`ls` must report "No such file or directory" for every one: any of them in `baserun/` would be
appended to by every run (move it out of `baserun/`, don't copy it into `ref_clean/` either).
`grep` must print nothing, or `b2mndr_etim` with a value of 0.

Then, in a tcsh with SOLPS-ITER's `setup.csh` sourced (the driver needs
`itmsubmit`, `squeue`, `sacct`, `setup_baserun_eirene_links` and `b2fstate_OK_bool` on `PATH`):

```
python -c "import mesa_solps.simulation, mesa_solps.objective"
echo $status
nohup python example_input_step7.py >& step7_driver.out &
```

`mesa.log` and `heartbeat.json` are written in the case folder; `step7_driver.out` gets the
start-up errors that come before logging starts.

**First job: what to check** (`run_0`, while it runs):

- `mesa.log` has "run_0: b2fstati copied from the reference's b2fstate".
- `grep -c b2ai run_0/run.log` prints 0: no `b2ai` line, so no flat start.
- `run_0/run.log` says "b2time.nc will be created" (not "appended"): a new file, not one found in
  `baserun/`.
- The first time printed is one time step after refconv's end time, not one step from 0 (see
  "Time" above). In `run_0`'s `b2time.nc` (in `run_0/b2mn.exe.dir/` while the job runs, in
  `run_0/` after it), the first `timesa` is refconv's last `timesa` plus about one time step. To
  check that the run really starts from refconv's state, compare the first point of the run's
  `b2time.nc` with the last point of refconv's: the outer-midplane `ne3da` and `te3da` should
  agree to within a few per cent (a flat start differs by far more).

### Commits

| Label | Repo | Commit | What it does |
|-------|------|--------|--------------|
| –     | mesa-solps | `d7ed833` | CLAUDE.md: fixes to mesa / sim-solps are committed in their own repo, never patched here or in site-packages. |
| A1    | mesa-solps | `9b237bf` | Absolute paths and no `os.chdir`: `ref_clean` is resolved in `Solps.__init__`, `simulations_directory` at the start of `launch()`; `itmsubmit` runs with `cwd=run_N`. `check_convergence(run_directory, ...)` reads `run_N/b2mn.exe.dir/b2time.nc`, else `run_N/b2time.nc`; a missing file or failed read means not converged (a failed read is logged). |
| A2    | mesa-solps | `8478d69` | `b2.transport.inputfile` is built from `ref_clean/b2.transport.inputfile`: only the fitted profile blocks (kinds 1, 3, 4, species 1) are replaced, every other line is kept. Checked at start-up (in `Solps.__init__`): a missing block for a fitted kind, or a line mixing fitted profile data with other settings, is an error. Removed: the hard-coded `addspec` list, `no_pflux` / `no_div`, `set_div_transport` (also from `example_input.py`), the kind 7 option. |
| A3    | mesa-solps | `f4970f3` | `setup_eirene_links()`: runs `setup_baserun_eirene_links` in `run_N/` before `itmsubmit`, then requires a non-empty `run_N/fort.1`; otherwise the driver stops with an error naming the folder (with the script's exit code and output), or saying the script is not on `PATH`. |
| –     | mesa | `d484c39` | `Simulation.launch()` gets `iteration` (the engine passes it) and `**kwargs`, with a docstring rule: the engine passes every argument by keyword, and plug-ins should accept `**kwargs`. Himmelblau example updated. |
| A4    | mesa-solps | `0b992b4` | `run_N/run_info.json`, written after `itmsubmit` via a tmp file + `os.replace`: `run_number`, `iteration`, `parameters`, and `jobs` (one entry per submit: `job_id`, `submit_time` as local ISO time with UTC offset). `Solps.launch()` takes `iteration` and `**kwargs`. |
| A5    | mesa-solps | `be2b995` | `build_solps_case` copy list: adds `b2.user.parameters`, drops `fort.1` and `fort.13` (no `fort.*` files are copied from the reference). |
| B1    | mesa-solps | `96ce9b8` | `status()` matches the job ID exactly: `squeue -h -u <user> -o %i`, parsed into a set (was a substring search of the whole table). |
| B2    | mesa-solps | `5d8390f` | The 24 h run timeout is removed: no `"timed-out"` from `status()`, no `timeout_hours` in `Solps`, `SolpsRun` or `example_input.py`. Run length is left to SOLPS's own clean stop in `b2mn.dat`. |
| B3    | mesa-solps | `55508cc` | `Solps` settings `convergence_min_run_time` (1e-3 s), `convergence_window` (2e-4 s), `convergence_timescale` (1.0 s), passed via each `SolpsRun` to `check_convergence`. Window ≥ minimum run time is a `ValueError` at start-up (in `Solps.__init__`), replacing the assert. The two times were later replaced by point counts (`2b70784`). |
| B4    | mesa-solps | `ee6a4d4` | Per-run Slurm states. One `squeue -h -u <user> -o "%i %T %r"` call per status check; a failing call keeps the run "running". PENDING: no checks, needs-attention log after 24 h. RUNNING: convergence test (`.quit`), needs-attention log after 1 h with no `b2time.nc`. COMPLETING: wait, log after 30 min. Other states: wait. Not listed: `sacct -j <id> -n -X -o State%30`; a finished state means ended, anything else or a failing `sacct` means still running, unknown to both for 3 polls is logged. Ended: no `balance.nc`, or `b2fstate_OK_bool` (run in `run_N/`) non-zero, means crashed; else complete. State changes are logged, and `started` / `ended` are added to the job's entry in `run_info.json`. Needs-attention lines are logged once per state. |
| B5    | mesa-solps | `27d4b18` | At the end of a healthy job: converged → complete; `b2time.nc` missing or unreadable → crashed (`check_convergence` returns `None` for "can't judge"); not converged → continued in `run_N/` (`b2fstati` → `b2fstati<k>`, `b2fstate` → `b2fstati`, `balance.nc` → `balance<k>.nc`, `b2mn.prt` removed, resubmitted, job appended to `run_info.json`). After `max_continuations` (new `Solps` setting, default 10, counted from `run_info.json`) the run is logged as stalled and returned as complete. `submit_job()` is shared by `launch()` and continuations. `SolpsRun`'s hash no longer includes the job ID. |
| B6    | mesa | `2c5d1ba` | `launch_iteration`: each pass checks statuses, then fills free slots, then sleeps `poll_interval` (new setting, default 1800 s; no sleep after the iteration's last run). `poll_interval` is a `Mesa` argument and an optional input-file variable (`parse_input_module` only requires fields without a default). |
| B7    | mesa | `df8d08b` | Error handling. `status()` raising: warning, run treated as running; after 3 in a row, "status check failing, needs attention". Scoring raising (`get_results` / objective): run counted as crashed, folder kept, other runs carry on. Anything else: `Mesa.run()` logs the traceback and the runs in flight (run number, folder), then re-raises; no job is cancelled. |
| C1    | mesa | `5f2dd57` | The evaluations file is written to `<name>.tmp` in the same folder, then `os.replace`d onto it (helper `__write_evaluations_data`, used by the initialiser and after each run). The `astype` results are now kept, so the column types are applied. |
| C2    | mesa | `2014bc3` | New `status` column; every finished run gets a row (helper `__add_evaluation`): `complete` / `stalled` scored, `crashed` / `timed-out` and scoring failures with a NaN objective. New run status `"stalled"`, handled like `"complete"`. No `rm -r`: crashed and timed-out folders are kept (timed-out still cancels first). `GPOptimizer.propose_evaluations` fits only rows with a score, and raises a clear error if fewer than 2 are left; the initial-sample count still counts every run. |
| C3    | mesa-solps | `d74d919` | `cleanup()` keeps every file (no-op with a comment); the engine still calls it. |
| C4    | mesa-solps | `dc560c8` | At the continuation cap, `status()` returns `"stalled"` (was `"complete"`). Each crash line in `check_ended()` ends with the job ID and its sacct State, e.g. "(job 1234 ended as NODE_FAIL)". |
| C5    | mesa-solps | `6c54195` | At start-up (in `Solps.__init__`), `check_tools()` checks that `setup_baserun_eirene_links`, `itmsubmit`, `squeue`, `sacct` and `b2fstate_OK_bool` (`required_tools`) are on `PATH`, and raises an error listing the missing ones. |
| D1    | mesa | `dad79c4` | No `basicConfig` at import. `Mesa.run()` calls `logger_setup(simulations_directory)` first: `mesa.log` in the simulations directory (appended to) and the screen, both with timestamps, every logger at INFO and above. Handlers are added directly (works if logging was configured earlier; a second call for the same folder adds nothing). |
| D2    | mesa | `4277d15` | `heartbeat.json` in the simulations directory (tmp file + rename), written at start-up and after each pass: `state` `"running"`, time, host, PID, iteration, runs in flight (run number, `job_id`, last status). On a stop in `run()` (finished, error, Ctrl-C) it is rewritten as `"stopped"` with `stopped_by`, unless it now holds another host/PID. At start-up a `"running"` heartbeat younger than 2 × `poll_interval`, or an unreadable one, is an error ("another driver may be running ..."); `"stopped"` never blocks; an older `"running"` one is taken over with a warning. Optional `SimulationRun.job_id` (default `None`). |
| –     | mesa-solps | `1465b36` | `SolpsRun.job_id`: read-only property returning `run_id`, so the heartbeat shows the current Slurm job. |
| D3    | mesa | `a1a81f8` | Optional hooks `Simulation.existing_run_numbers()` and `Simulation.adopt()` (defaults: empty set / `None`), optional `SimulationRun.iteration`. At start-up every folder number with no evaluation row is adopted and polled with the normal handling until recorded, each with its own iteration, before new points are proposed; one that can't be adopted (`None`, an error, no iteration) is logged as needing attention and skipped. Per-run handling moved unchanged into `__check_run`, used by both loops. Next run number = max(rows, folders) + 1. |
| D4    | mesa-solps | `76cedec` | `Solps.existing_run_numbers()`: the N of every `run_N/` folder. `Solps.adopt()`: no `run_info.json` → `None`; else a `SolpsRun` with run number, iteration, parameters and the last job, its Slurm state starting as last recorded (RUNNING since `started` if started and not ended, else PENDING since its submit time). `SolpsRun` takes `iteration`; the submit command is worked out once in `Solps.__init__`. |
| –     | mesa-solps | `5d89426` | `build_solps_case` copies the reference's `b2fstate` to `run_N/b2fstati`, else its `b2fstati` (new helper `reference_state_file()`), and logs which one. Neither: an error naming the folder at start-up (in `Solps.__init__`, after `check_tools()`). |
| –     | mesa-solps | `2b70784` | Convergence window counted in `b2time.nc` points (one saved time each, written every `b2mndr_b2time` iterations), replacing B3's times: `convergence_window_points` (25, floor 5, `int` only, else `TypeError`) and `convergence_min_run_factor` (3, floor 2; minimum run = ceil(factor × window) points); `convergence_timescale` unchanged. A value below its floor is raised to it with one warning at start-up (replaces B3's `ValueError`). `check_convergence`: fewer points than the minimum → not converged; else fit the last `window_points` points against `timesa`; `timesa` not strictly increasing in the window → warning, test still applied. Points counted over the whole file. `example_input.py` passes the three settings at their defaults. |
| –     | mesa-solps | `1ef403c` | `b2mndr_stim` in `b2mn.dat`: `build_solps_case` sets it to `'0'` (new `b2time.nc`, time from 0), `continue_run` to `'-1'` before resubmitting (appends). New helper `set_b2mn_value()`: sets one key, keeps the rest of the file byte for byte, adds the key at the end if it is missing. |
| –     | mesa | `4ac188c` | Resume the interrupted iteration: `launch_iteration` keeps the iteration's points not launched yet in `iteration.json` in the simulations directory (tmp file + rename, rewritten after each launch). At start-up, after the adopted runs have finished, `__resume_iteration` launches them under the same iteration number (new run numbers), then the driver carries on with the next iteration, so a driver stop no longer uses up one of `max_iterations`. An unreadable file, one for another iteration than the last recorded one (or the one after), or one with other parameter names is logged and ignored. Run-number calculation moved unchanged into `__next_run_number`. |
| –     | mesa | `9dae4d3` | Stalled runs are left out of the GP fit (`GPOptimizer.propose_evaluations`, next to the crashed-run filter); they keep their score and `stalled` row in the evaluations file and still count towards the initial sample count. The "fewer than 2" error says "usable score (stalled runs excluded)". `RunStatus` comment in `simulations.py` updated. |
| –     | mesa | `6931ecd` | All scores equal (zero spread) among the runs the GP fits: `ValueError` before the fit, giving the number of runs, the shared value and the likely cause (the runs gave the same output), instead of the NaN error from inside `inference.gp`. |
| –     | mesa | `1c1da0f` | Docstring on `Mesa.__init__`: `max_iterations` is the last iteration number to run; iterations count from 0 (iteration 0 is the initial random batch with `GPOptimizer`), so up to `max_iterations + 1` are run. No code change. |
| –     | mesa | `c8b5799` | Ctrl-C: `run()` catches `KeyboardInterrupt`, marks the heartbeat stopped as before, logs "interrupted (Ctrl-C), heartbeat marked stopped; runs in flight not cancelled" (or "not marked stopped (see above)") and exits with `SystemExit(130)`, no traceback. The "another driver may be running" refusal adds "or wait 2 x poll_interval (N s) after the last-seen time and restart". New-parameter log lines in `core.py` and `gpo.py` print plain numbers, not `np.float64(...)`. |
| –     | mesa | `6d6c8cd` | `GPOptimizer.propose_evaluations` counts the runs so far as the number of rows in the evaluations data (was the highest run number, one less than the count since run numbers start at 0). Every run still counts towards the initial sample (complete, stalled, crashed, timed-out, adopted). With `initial_sample_count=N`, iteration 0 has N random runs and iteration 1 is a GP proposal (was a 1-run random top-up). A run folder that can't be adopted has no row and is no longer counted. |
| –     | mesa-solps | `7641b59` | Convergence check 1, window: `convergence_window_points` defaults to 100 (was 25); floors and `convergence_min_run_factor` unchanged, so the default minimum run is 300 points. `example_input.py` passes 100. |
| –     | mesa-solps | `d9c467a` | Convergence check 1, guard cells: `check_convergence` fits only columns 1 to `nya` − 2 of `ne3da` / `te3da` (38 real outer-midplane cells here), not the two guard cells. |
| –     | mesa-solps | `82e81be` | Convergence check 1, hold: converged only if the test passes for the window ending at each of the last `window_points + 1` points (over the last 2 × `window_points` points), worked out from the file on each call with no stored state; a shorter file is not converged. New `windows_pass()` fits every window at once (same slopes as `polyfit`). |
| –     | mesa-solps | `317d9ab` | `tests/test_convergence.py`: pytest tests on small synthetic `b2time.nc` files (steady, drifting, too short, passes then fails, passes only in the last window, hold restarting, wild guard cells, `windows_pass` against `polyfit`). |
| –     | mesa-solps | `3c4f29b` | `tools/make_synthetic_ts.py`: synthetic TS data from a `balance.nc` (see "Synthetic TS data for step 7a"). |
| –     | mesa-solps | `be41e15` | `tools/check_synthetic_ts.py`: reload, truth check, scores and plot for the synthetic data. |
| –     | mesa-solps | `3c94574` | `tests/test_make_synthetic_ts.py`: tests for the noise, errors and file writing. |
| –     | mesa-solps | `9424724` | Step transport profile: `Solps(profile_shape="step")`, `models.step_profile_knots`, `simulation.transport_profiles` and `check_profile_shape` (see "Step transport profile for step 7"). Default `"barrier"` unchanged. Branch `worktree-step-profile`. |
| –     | mesa-solps | `8f235d9` | `example_input_step7.py`: draft input file for step 7 (step profile, 4 free parameters). |
| –     | mesa-solps | `3b4fbe0` | `tests/test_step_profile.py`: reproduction of the earlier step fit's files, positions, truth, unchanged barrier path, build test for `example_input_step7.py`. |
| –     | mesa-solps | `d67dda0` | `example_input_step7.py`: paths filled in, `memory_gb` 2, settled settings, start from the converged `b2fstate` (see "Step transport profile for step 7"). |
| –     | mesa-solps | `1ed9690` | `build_solps_case` sets `b2mndr_stim` to `'-1'` in a new run's `b2mn.dat` (was `'0'`), as `continue_run` does: the simulated time carries on from the reference's end time. The new folder has no `b2time.nc`, so B2 still starts a new one. Branch `fresh-run-stim-continue`. |

### Changes from the plan

- **Added mesa commit** (not in the plan): passing `iteration` to `launch()`. A4 records the
  iteration, which `launch()` didn't receive. The `**kwargs` rule was chosen so that later
  additions to `launch()` don't break plug-ins. It is still a one-time break for any existing
  plug-in, which must add `iteration` (or `**kwargs`); this should be raised in the mesa PR.
  Alternatives considered: a `LaunchRequest` object (cleaner, but a bigger API change), and the
  engine checking the plug-in's signature at start-up (not needed while SOLPS is the only
  plug-in).
- **A1:** `simulations_directory` is resolved in `launch()`, not "once at start-up", because the
  plug-in only receives it there; with no chdir every call gives the same path. Read failures are
  caught broadly (`except Exception`, around the netCDF read only), since a half-written file can
  raise several error types.
- **A2:** the template check runs in `Solps.__init__` rather than in `launch()`, so a bad
  reference stops the driver before any `run_N/` is created. The mixed-line error is new. The
  error text says "add one to the reference case" rather than "to ref_clean". A kind 7
  (viscosity) block in the reference is now kept, whereas before it was never written.
- **A3:** the step is its own function so it can be tested without `launch()`; the
  not-on-`PATH` error and the script output in the error message are additions.
- **A4:** written after every submit, not only "a successful submit": there is no submit-success
  check yet. Run number and iteration are cast to `int` (the engine gives numpy ints, which
  `json` rejects). `read_run_info()` was added in B4.
- **A5:** message as planned.
- **B1, B2:** as planned.
- **B3:** the settings reach `check_convergence` through each `SolpsRun` (it is called from
  `status()`), as one dict of keyword arguments; `check_convergence` takes a new `timescale`
  argument. Not added to `example_input.py` (defaults unchanged).
- **B4:** one `squeue` call per status check, not one shared call per poll (decided: simpler,
  negligible load at a 30 min poll even with 20 slots; a shared call can be added inside `Solps`
  later). Decided while implementing: other `squeue` states (e.g. CONFIGURING, SUSPENDED) wait
  with no checks; `b2fstate_OK_bool` runs in `run_N/` with no arguments, any non-zero exit means
  crashed, and not on `PATH` stops the driver with an error; needs-attention lines are logged
  once per state. Also: the result of an ended run is kept, so later calls don't check again;
  "unknown to both" counts polls where `sacct` succeeds but prints nothing (a failing `sacct` is
  logged separately); `started` is set only when RUNNING is seen, so a job that runs entirely
  between two polls gets `ended` only; times are the driver's, accurate to one poll. The
  time limits are module constants, not settings. The `b2time.nc` lookup moved into
  `find_time_file()`.
- **B5:** `SolpsRun`'s hash no longer includes `run_id` (approved; in the same commit): the
  engine keeps runs in a set, and the job ID changes on a continuation. `itmsubmit` and the
  job-ID parsing moved unchanged into `submit_job()`. `check_convergence` returns a plain
  `bool`. One `k` for both renames: the first number free for both `b2fstati<k>` and
  `balance<k>.nc`.
- **B6:** `poll_interval` is optional in input files (decided), which needed
  `parse_input_module` to skip fields with a default. The Himmelblau example was left alone
  (decided): with the 1800 s default it now takes about 30 h unless it passes `poll_interval`;
  raise this in the mesa PR.
- **B7:** decided while implementing: a run whose scoring fails keeps its folder (the crashed
  branch's `rm -r` is skipped for it); the in-flight list gives run number and folder, not the
  job ID (the engine doesn't know job IDs; for SOLPS the current one is the last entry in
  `run_info.json`); the error is re-raised after logging; Ctrl-C (`KeyboardInterrupt`) is not
  caught. Also: the traceback for a failing status check is logged once per streak; the stop
  message is logged at error level and per-run problems at warning level; the loop moved
  unchanged into a private `__run()`, so `run()` has a single `try`.
- **C1:** the message's "Why" was corrected: the missing `astype` was not harmless, since a new
  file's columns were untyped (`object`) and an int fixed parameter was stored as `int64`. The
  tmp file is named after the evaluations file (`<name>.tmp`), whatever its name. A failed write
  leaves the tmp file behind; the next write overwrites it.
- **C2:** decided while implementing: a run whose scoring fails (B7) also gets a `crashed` row,
  which also keeps a later iteration from reusing a failed run's number (its folder is now kept,
  so `run_N/` would already exist). The GP raises a clear error when fewer than 2 runs have a
  score (it can't fit 0 or 1 points), rather than drawing more random points. The row-building
  code moved unchanged into `__add_evaluation`, used by all four cases. `import subprocess` was
  removed (only used by `rm -r`); the crash log line now says "folder kept". The `status` column
  is written as `object` (pandas 3 reads it back as `str`).
- **C3:** as planned. The message also names the files the old keep-list deleted that series A
  and B added (`run_info.json`, `b2.user.parameters`, `b2fstati<k>`, `balance<k>.nc`).
- **C4:** B4/B5 already logged a reason for every crash (including a third one, `b2time.nc`
  missing or unreadable), and `change_state()` already logged the sacct state on the line
  before. So the crash half only adds the job ID and sacct State to each crash line (decided:
  kept, so each crash is explained in one line). Title changed to "give the Slurm state when a
  run crashes". Only the first word of the sacct output is logged ("CANCELLED", not
  "CANCELLED by <uid>").
- **C5:** checked against the code: the driver also calls `whoami`, `touch` and `scancel`. Not
  checked: the first two are standard system tools, and `scancel` is only reached through
  `cancel()`, which the engine calls only for `"timed-out"` (no SOLPS run returns it since B2).
  The check runs first in `Solps.__init__`, before the template check. Building a `Solps` now
  needs the five tools on `PATH` (tests need placeholders).
- No commits were added in series C.
- **D1:** nothing calls `build_from_input_module`; input files build `Mesa(...)` and call `run()`,
  so `Mesa.run()` calls `logger_setup()`. Handlers are added directly rather than with
  `basicConfig` (which does nothing if logging was already configured), and a second call for the
  same folder adds nothing. The screen now has timestamps too. Errors raised before `run()` (e.g.
  `Solps.__init__`'s checks) only reach the screen. Code that calls `launch_iteration` directly no
  longer gets INFO on the screen.
- **D2 (decided):** the heartbeat is marked `"stopped"` (with the reason) on every stop that
  reaches `run()`'s `finally`, instead of being left as is, so a restart after a clean stop or an
  error stop needs no override; a killed driver still leaves a `"running"` heartbeat for the age
  check. The stop write is skipped if the file holds another host/PID, and its failure is logged
  without hiding the original error. A heartbeat is also written at start-up (claims the case at
  once). The job ID comes from a new optional `SimulationRun.job_id`. Decided while
  implementing: the age is taken from the `time` field (local ISO time with UTC offset); a missing
  or bad time, or an unreadable file, blocks start-up; the start-up check runs before the
  `try`, so a refusal never touches the other driver's file. Runs show `launched`, the last
  `status()` result, or `status check failed`.
- **Added mesa-solps commit** (`1465b36`, decided with D2): `SolpsRun.job_id` returns `run_id`, so
  the engine reads the job ID generically. Its own commit, so D4 stays about adoption. `run_id`
  was not renamed.
- **D3:** adopted runs must be recorded with their own iteration, which the plan's
  `adopt() -> SimulationRun` can't return, so `SimulationRun` gets an optional `iteration`. The
  per-run handling is shared (`__check_run`), not copied; the one ordering change is that
  `cleanup()` now runs before the run leaves the in-flight set. Decided while implementing:
  `adopt()` raising counts as "can't be adopted" (warning with traceback); during adoption the
  heartbeat's `iteration` is `null`; an unadoptable folder is warned about again on every restart.
- **D4:** `adopt()` also sets the job's starting Slurm state from `run_info.json` (not in the
  plan): without it a still-running job logs a false "PENDING -> RUNNING after <time since first
  submit>" and the "no `b2time.nc` for 1 h" timer restarts at adoption. `SolpsRun` takes a
  required `iteration`. The submit command moved unchanged into `Solps.__init__` so continuations
  of adopted runs use the same one.
- **Added mesa-solps commits after series D** (not in the plan), from the first cluster checks:
  - `5d89426` (b2fstati fallback): the start-up error is a `FileNotFoundError` (`check_tools` raises
    `RuntimeError`).
  - `2b70784` (window in points): the minimum is `ceil(round(factor × window, 6))`, so that e.g.
    2.2 × 5 gives 11 and not 12 (floating point). Decided in review: `convergence_window_points`
    must be an `int` (numpy ints are accepted; floats, even 25.0, strings and `bool` are a
    `TypeError` at start-up); the three settings were added to `example_input.py`, which had none
    since B3. The floors are module constants (`min_window_points`, `min_run_factor`).
  - `1ef403c` (`b2mndr_stim`): a reference with no `b2mn.dat` still gives a run with none (as
    before); `continue_run` raises if `run_N/b2mn.dat` is missing. Lines that don't start with the
    quoted key (e.g. comments) are left alone.
  - `1ed9690` (new runs continue in time, decided 2026-11-14): replaces `1ef403c`'s rule "new run
    `'0'`, continuation `'-1'`"; now both are `'-1'`, so a run's times follow on from the
    reference state's instead of restarting at 0. The SOLPS source was read first to check that a
    `'-1'` run with no `b2time.nc` creates one rather than failing (see "Files needed"). Found
    while reading: B2 would append to a `b2time.nc` (and its other appended outputs) in the shared
    `baserun/`, so a check was added to the launch steps. The earlier "Files needed" citation for
    the `b2time.nc` append (`b2mod_wrsrt.F:241`) was the trace file `tracing/intshrt.trc`; it now
    cites `b2mod_mwti.F90`, where `b2time.nc` is opened.
- **Added mesa commits after series D** (not in the plan), from a dry run with fake Slurm tools.
  Each was agreed before it was written, and committed one at a time:
  - `4ac188c` (resume): of three options (save the unlaunched points; reuse the adopted runs'
    iteration number; keep the behaviour and log "budget reduced by 1"), saving the points was
    chosen. Reusing the number would give a finished GP iteration a second point. Decided: the
    leftover points get new run numbers and are launched after the adopted runs have finished, not
    alongside them; the file is rewritten after each launch, so a stop in between launches that
    point twice rather than losing it.
  - `9dae4d3` (stalled runs): filtered in `GPOptimizer` (decided), not in the engine, so that they
    still count towards the initial sample and other strategies still see them.
  - `6931ecd` (equal scores): no fallback; inference-tools untouched.
  - `1c1da0f` (`max_iterations`): docstring only (decided); not a bug, as the same `>` check was in
    the code before the framework refactor.
  - `c8b5799` (cosmetics): decided: `SystemExit(130)` after Ctrl-C (not returning normally, which
    would run the input file's code after `mesa.run()`). Added while implementing: the message says
    whether the heartbeat was really marked stopped (`__mark_heartbeat_stopped` returns a bool) and
    that runs in flight are not cancelled. No `np.float64(...)` log lines were found in mesa-solps.
- **Added mesa commit after the dry run** (not in the plan): `6d6c8cd` (initial-sample count),
  agreed before it was written. Only `gpo.py` used the highest run number as a count; the other
  uses (`core.py`'s next run number and iteration numbers, `genetic.py`'s iteration check, the
  Himmelblau plot) are not counts and were left alone.
- Commit messages: where the plan names the cluster, the name was dropped ("checked on scratch
  runs", C3's disk sizes), and plan labels are not referenced in commit messages.

### Open questions

- **A2, not tested on a real `b2.transport.inputfile`.** Check it on both MAST-U references
  (D-only and D + C) in the cluster tests: the output should differ from the reference only in the
  kind 1, 3 and 4 blocks.
- **A2, kind 7 now from the reference.** If the reference sets a viscosity profile, runs now get
  it. Linked to the open team question of whether viscosity should follow D⊥ in a fit.
- **A2, team list (unchanged):** what `no_div` does; whether `no_pflux=.true.` is right for
  MAST-U fits; χe/χi kind labels possibly swapped in `transport.py` (harmless while χi = χe).
- **A3:** the script's exit code is not checked, only `fort.1`. If the script can fail after
  making `fort.1`, the run would still launch.
- **A3, failed check leaves `run_N/` behind.** The driver stops and nothing is submitted. On a
  restart, D3/D4 log the folder (no `run_info.json`) as needing attention and skip it, on every
  restart until it is removed by hand; new run numbers go past it.
- **A4 / B5, no submit-success check.** `itmsubmit`'s output is parsed for the job ID without
  checking it worked; a failed launch or continuation gets a junk ID, which B4 then reports as
  "unknown to squeue and sacct, needs attention" (deferred, as planned).
- **B4, check on the cluster:** the real `squeue -o "%i %T %r"` and `sacct -o State%30` output
  (padding, other states such as `PREEMPTED` or `REQUEUED`); how long a job takes to appear in
  `sacct` after leaving `squeue`; that `b2fstate_OK_bool` checks `b2fstate` in the current
  directory when called with no arguments; the time limits (24 h, 1 h, 30 min).
- **B4 / B7, broken `run_info.json` is retried, not a stop.** `status()` raises if
  `run_info.json` is missing or broken at a state change; B7 catches every `status()` error, so
  it is retried each poll (warning, then needs-attention after 3) and the run holds its slot
  until it is fixed. Left as a per-run case (decided with C5). A tool missing at start-up now
  stops the driver (C5); one that disappears while it runs is still retried this way.
- **B5:** check on the cluster that a continuation restarts and appends to `run_N/b2time.nc` as
  in the hand-made restart.
- **B6:** the 1800 s default is SOLPS-scale; upstream may want a smaller default (it is a
  setting). The Himmelblau example (see above).
- **B7:** catching every `status()` error could hide a real bug; the needs-attention line is the
  guard, so watch for it in testing.
- **C2, crash loop (watch in testing):** a crashed point leaves the GP's data unchanged, so the GP
  may propose the same point again. A penalty score is parked until after the first tests.
- **C2, too few scored runs stops the driver.** If fewer than 2 runs have a score once the GP
  phase starts (e.g. most of the initial runs crashed), `propose_evaluations` raises and the
  driver stops. Intended (likely a set-up problem); raise in the mesa PR.
- **C2, old evaluations files** without the `status` column don't match the new columns. Fine
  while no real fits exist.
- **C2, `GPOptimizer` bugs seen while testing, left alone (out of scope):** `gpo_search` fails
  with exactly 1 free parameter (`reverse_normalisation`: "'numpy.float64' object is not
  iterable"), before and after C2; SOLPS fits have several, so it doesn't affect them. The
  initial-sample count `n_evals` was the highest run number, not the number of runs (one random
  run too many); fixed in `6d6c8cd`, which counts rows, so folders that can't be adopted (no row)
  no longer count as initial samples either.
- **C3, disk use:** every file of every run is kept. Measure a real fit's disk use in testing,
  then decide a keep-list (tarball vs loose files, `*.last10`, `2d_profiles/`, `fort.15` on
  restart).
- **C5:** `whoami`, `touch` and `scancel` are called but not checked (see "Changes from the
  plan").
- **D1:** if a user's input file adds its own screen handler, lines appear twice on the screen.
- **D2:** a failing per-pass heartbeat write stops the driver (the "anything else" rule); only the
  stop write is guarded. A driver that stalls longer than 2 × `poll_interval` while another one
  takes over only notices when it stops. The age limit uses the new driver's `poll_interval`.
- **D2 / D3, engine API additions:** optional `SimulationRun.job_id` and `SimulationRun.iteration`,
  optional `Simulation.existing_run_numbers()` and `Simulation.adopt()`. No change for existing
  plug-ins; to raise in the mesa PR.
- **Proposals per iteration (left out for now):** with `GPOptimizer`, only the initial random
  batch (iteration 0) fills the `max_concurrent_runs` slots. There is no batch-size setting.
  - Iteration 1 used to be a 1-point random top-up (the `n_evals` off-by-one above); since
    `6d6c8cd` it is the first GP proposal.
  - Each GP iteration proposes one point by design (one fit, one acquisition maximum), and the
    next iteration only starts once all of the current one's runs have finished. So in the GP
    phase one slot is used and the others stay empty.
  - To fill them, the GP would propose a batch per fit ("kriging believer": add each proposed
    point with its predicted score, refit, propose again; `GpOptimiser.add_evaluation` exists),
    about 20–30 lines in `gpo.py` plus a batch-size setting. An iteration would then count
    batches. Proposing asynchronously as slots free up is the bigger alternative.
  - Trade-off: a batch uses the slots (less wall-clock time per fit), but each point is chosen
    with less information, so a fit usually needs more runs in total.
- **What `max_iterations` counts:** the last iteration number run. Iterations count from 0, and
  iteration 0 is the initial random batch with `GPOptimizer`, so up to `max_iterations + 1`
  iterations are run (documented in `1c1da0f`). Since `6d6c8cd` (no random top-up),
  `max_iterations=2` gives two GP iterations (1 and 2). The genetic strategy's check
  (`df.index[-1][0] >= max_iterations`, on the last recorded iteration) means the same, but
  `GeneticOptimizer` is left over from an older API and can't be instantiated (no
  `propose_evaluations`).
- **`4ac188c`, resume windows:** a driver stopped between a `launch()` and the rewrite of
  `iteration.json` launches that point again on restart (one extra run). While the adopted runs
  finish, the free slots stay empty; the leftover points start only afterwards.
- **Engine changes to raise in the mesa PR (dry-run commits):** the new `iteration.json` state
  file; Ctrl-C now ends `run()` with `SystemExit(130)`, not `KeyboardInterrupt`.
- **D4, short windows a restart doesn't handle:** a driver killed inside a continuation, after
  the renames but before the new job is recorded, leaves a run that is judged "crashed" when
  adopted (`balance.nc` already renamed); a driver killed between `itmsubmit` and writing
  `run_info.json` leaves a job running in a folder that can't be adopted (needs attention).
- **Naming:** `SolpsRun.run_id` holds the Slurm job ID of the run's current job, not an ID of the
  run (that is `run_number`). Since `1465b36` a read-only `job_id` property returns it; renaming
  the attribute itself to `job_id` would be clearer, left out as an unrelated refactor.
- **mesa commit:** the required `iteration` argument breaks existing plug-ins once (see above);
  to raise in the mesa PR.
- **Convergence floor warnings only reach the screen.** They are logged in `Solps.__init__`, which
  runs before `Mesa.run()` sets up `mesa.log` (as for D1's start-up errors): with no handler yet,
  Python's last-resort handler prints them to stderr, and the records are not kept for the file
  handler added later. Left as is for now (decided). **Before the main mesa test, decide when
  logging should start**, so that everything from start-up reaches `mesa.log`: e.g. mesa sets up
  logging when `Mesa(...)` is built rather than in `run()`, or input files set it up (or build
  `Mesa`) before the simulation. That would be a mesa change; it would also cover D1's start-up
  errors. A mesa-solps-only alternative (`Solps` logging the warnings again on the first
  `launch()`) was considered and not taken.
- **Convergence window in points:** with a tiny time step, the window covers very little simulated
  time, so a run can look converged over a short stretch. Check 1 widened it to 100 points plus a
  100-point hold; with the 2e-4 s step of the real runs checked that is 0.02 s per window and 0.04 s
  for the hold, against a 1 s threshold. Check the defaults against other `b2mndr_b2time` values
  and time steps.
- **Check 1, the hold looks back only:** a run is stopped at the first point where the test has
  held for one window, which can be right at the threshold. `run_2` of the sanity check holds at
  point 1633 with its slowest τ(Te) at 1.11 s and then fails again for most of the next 270 points.
  Whether that matters depends on how much the score moves in that time (check 2, Δscore, is
  the other guard). Not changed: the threshold and the decision stand as agreed.
- **Check 1, tests need pytest,** which is not a dependency of the package (no test extra in
  `pyproject.toml`; adding one is a packaging change for upstream to decide). Run them with
  `pip install pytest` and `python -m pytest tests`.
- **Stale `b2time.nc` in `b2mn.exe.dir/`:** `find_time_file` reads `run_N/b2mn.exe.dir/b2time.nc`
  before `run_N/b2time.nc`. If a continuation leaves an old copy there, the point count and the
  fit use the wrong file (see the cluster checks).
- **`b2mn.dat` comments:** `set_b2mn_value` was only tested on hand-made files; check that real
  `b2mn.dat` files have no other way of writing a key or a comment.
- **Synthetic TS, the old test data is already near this truth.** `testing_ts_data.npz` scores
  −0.041 against the refconv state: it has no noise and is within 0.5 % (ne) and 0.07 % (Te) of
  the new truth, i.e. it looks like noise-free synthetic data from a state very close to this
  one. Where did it come from? If it came from the same transport, earlier tests with it were
  already known-answer tests.
- **Synthetic TS, which file for 7a:** the noisy file is the realistic test; the truth file is a
  cleaner first test (the score at the right answer is exactly 0). Seed 0 gives a slightly
  low-residual draw (94.5th percentile); fine, or pick another seed.
- **Synthetic TS, the answer MESA should find:** with the noisy data the best-scoring
  transport is not exactly the true one (the noise moves the optimum), so 7a should check that
  the true D⊥ and χ values fall within MESA's spread, not that they are hit exactly. The
  parameters MESA fits must also be able to express the true profiles (a step at the
  separatrix: 10 inside, 4 outside for χ; flat 4 for D⊥).
- **Synthetic TS, flat errors:** 5 % of the true value at every channel, as in the old test
  data. Real TS errors are larger at low density (the far SOL); not modelled.
- **Step profile, barrier heights in step 7:** the draft fixes `chi/D_barrier_height` at 0.1, as
  the earlier fit did, so values run from 0.15 to 100.1 and the truth is at boundaries 3.9 / 9.9.
  Fixing them at 0.0 would make the boundary parameters the coefficients themselves (truth at 4 /
  10, values 0.05 to 100). 0.1 keeps the runs comparable with the earlier fit's; decide before
  step 7.
- **Step profile, linear or log bounds:** (0.05, 100) is drawn and fitted on a linear scale, so
  the initial 12 runs put few points near the truth (D 4 is in the bottom 4 % of the range; the
  chance that all 4 parameters fall below 10 is 10⁻⁴). Same as the earlier fit; a narrower range or
  a log-scale parameter would be a separate change.
- **Step profile, jump width fixed:** ±1 mm (`step_half_width`) is a module constant, as in the
  earlier fit. If it should be a setting, that is a small follow-up.
- **Step profile, missing parameter leaves a run folder:** a step parameter missing from the
  input file raises a `KeyError` in `launch()` after `build_solps_case` has made `run_N/` (the
  barrier path behaves the same for its parameters). Computing the profiles before
  `build_solps_case` would avoid it; left out to keep `launch()`'s order unchanged.
- **Barrier path, no position check:** the barrier shape can still write repeated or
  non-increasing positions when its knots nearly coincide (e.g. the earlier fit's parameters with
  `"barrier"`). The step shape can't. Adding a check (error if positions repeat) to the barrier
  path or the writer would change the default path, so it was left out; worth deciding.
- **Earlier fit, other differences not carried over:** its writer writes the whole file
  (`&TRANSPORT`, `no_pflux=.true.`, optional kind 7 and `no_div`) instead of using
  `ref_clean`'s file as a template, and its `Solps` has `set_div_transport` and `timeout_hours`.
  Ours takes all of that from `ref_clean/b2.transport.inputfile` (A2) and has no timeout (B2).
  Check that `ref_clean`'s file has `no_pflux=.true.` and no viscosity block, as the earlier
  fit's runs had.
- **Synthetic TS tools in the repo:** `tools/` holds analysis scripts for this fit and may not
  belong upstream; keep them in their own commits so they are easy to leave out of a PR.

### What was tested

Only imports, pure functions and temp dirs; nothing that calls Slurm, and neither
`Solps.launch()` nor `Mesa.run()` with the SOLPS plug-in was run. For B1, B2, B4, B5, C4, the
`job_id` commit and D4, `SolpsRun.status()` was run on runs in temp dirs, with fake `squeue`,
`sacct`, `b2fstate_OK_bool` and `itmsubmit` scripts first on a restricted `PATH` (checked to
resolve to the fakes or to nothing; there was no `scancel`, real or fake). C3 called
`SolpsRun.cleanup()` on a run in a temp dir, and C5 and D4 built `Solps` with placeholder tools on
such a `PATH`. B6, B7, C1, C2 and D1–D3 used an in-memory fake simulation with `sleep` replaced.
Throwaway test scripts were kept outside the repo.

- A1: `check_convergence` on synthetic `b2time.nc` files: missing, corrupt (logged), converged
  in `run_N/`, drifting in `b2mn.exe.dir/` (preferred), run shorter than the minimum.
- A2: a reference in the old writer's format (kind 7, 26 `addspec` lines, `no_pflux`, `no_div`):
  non-fitted lines kept in order, fitted blocks replaced in place, rewriting the output is
  stable. A D-only-style reference with mixed case, comments and a species-2 block. Errors for a
  missing file, a missing kind and a mixed line. `Solps(...)` construction with and without a
  reference inputfile.
- A3: fake `setup_baserun_eirene_links` scripts on a temp `PATH`: good link, no `fort.1`, empty
  `fort.1`, dangling link, script missing.
- mesa commit: `Mesa.launch_iteration` with a fake in-memory simulation in a temp dir passes the
  iteration to `launch()`; a plug-in following the rule accepts an extra keyword argument.
- A4: `run_info.json` written from numpy inputs reads back equal, no tmp file left, a failed
  write leaves the old file intact.
- A5: `build_solps_case` in a temp dir copies `b2.user.parameters` (when present) and no
  `fort.*` files.
- B1: job 12345 against a queue with 123456 (no match), with 12345 (match), gone with
  `balance.nc`, an empty job ID, an empty queue; the `squeue` arguments.
- B2: a job still queued 100+ days after submit stays running; `timeout_hours` gone from both
  signatures; `Solps(timeout_hours=24)` is a `TypeError`; `example_input.py` byte-compiles.
- B3: `check_convergence` with default and changed settings on synthetic files (timescale,
  minimum run time); `Solps` defaults, custom values, and the `ValueError` for window ≥ minimum;
  `status()` passes the settings through (`.quit` touched or not).
- B4: `squeue` failing; PENDING under and over 24 h (logged once, with the reason, no checks);
  PENDING → RUNNING logged with its duration and `started` written; RUNNING with no `b2time.nc`
  under and over 1 h, unconverged and converged (`.quit`); COMPLETING over 30 min; CONFIGURING
  (no checks, no limit); a reason with spaces; not listed with `sacct` saying RUNNING, failing,
  or empty for 5 polls (logged once at the 3rd, count reset); ended as COMPLETED, `CANCELLED by
  <uid>`, FAILED, TIMEOUT, OUT_OF_MEMORY, NODE_FAIL with and without `balance.nc` and with
  `b2fstate_OK_bool` 0 / 1; `started` and `ended` in `run_info.json`; a job that ran between two
  polls; the result kept after the end; `b2fstate_OK_bool` not on `PATH`.
- B5: `check_convergence` returning `None` / `False` / `True`; a healthy end converged
  (complete), with `b2time.nc` missing or unreadable (crashed); not converged: the renames
  (contents checked), `b2mn.prt` removed, `itmsubmit` with the same command in `run_N/`, the job
  appended, the new job tracked through `squeue` and `sacct`, a second continuation (`k = 2`),
  then convergence (complete, last `balance.nc`); `k` skipping used numbers; the cap (continued
  below it, stalled at it, `max_continuations=0`, count read back from `run_info.json`); the hash
  unchanged and the run still found in a set; `submit_job` parsing. The B4 cases rerun: all pass
  except healthy ends with no `b2time.nc`, which are now crashed, as intended.
- B6: the order of status checks, launches and sleeps over a whole iteration (3 runs, 2 slots);
  a freed slot refilled in the same pass; every sleep is `poll_interval`; no sleep after the last
  run; the default; input files with no, int, float and string `poll_interval`, and with a
  required field missing; `build_from_input_module` passing it on.
- B7: `status()` failing 2 and 4 times in a row (warnings, traceback once per streak,
  needs-attention at the 3rd, reset after a good check); `get_results` and the objective failing
  (crashed, folder kept, other runs scored); the evaluations file, a launch and the optimiser
  failing (traceback and in-flight list logged, original error re-raised); Ctrl-C passing
  through; a normal run unaffected; B6 rerun.
- C1: a new evaluations file is empty with the right types; after an iteration of 3 runs, 3 rows
  with the right types (an int fixed parameter stored as `float64`); no tmp file left; a write
  that fails mid-way (`to_hdf` writing half a file, then "Disk quota exceeded") leaves the old
  file intact and readable, and the next write succeeds; an existing file is not re-initialised.
- C2: one iteration with runs ending complete, stalled, crashed, timed-out and complete with a
  failing `get_results`: a row each with the right status, scores for complete and stalled
  only, NaN otherwise, parameters recorded for all; every folder kept with its files;
  `cleanup()` for complete and stalled only, `cancel()` for timed-out only; the next run number
  and iteration count every run. GP: only scored rows reach `gpo_search` (caller's table
  unchanged); 0 or 1 scored of 5 raise the clear error; the initial phase still counts crashed
  runs; a real GP fit on 4 scored of 6 rows (gaps in the run numbers, 2 free parameters)
  proposes a point in bounds. B6 rerun passes; B7 rerun: only its "no row for a scoring failure"
  checks fail, as intended.
- C3: `cleanup()` on a run folder with 13 files (state files, continuation files,
  `run_info.json`, `b2.user.parameters`, logs, a subfolder) leaves every file unchanged.
- C4: at the cap (2 of 2) → `"stalled"`, logged, not continued, kept on later polls with no
  tool called; `max_continuations=0` → stalled; below the cap still continued; converged at the
  cap → complete. Crash lines end with "(job 4242 ended as <State>)" for no `balance.nc` with
  FAILED, `CANCELLED by <uid>`, NODE_FAIL, OUT_OF_MEMORY; for `b2fstate_OK_bool` exiting 3; for
  no `b2time.nc`. B4 / B5 reruns: only the expected checks fail (the cap now stalled; healthy
  ends with no `b2time.nc` crashed, as after B5).
- C5: all tools present → `Solps` builds; each tool missing alone → error naming only it; two
  missing → both listed in order; all missing with a bad reference → the tool error comes
  first; a non-executable tool counts as missing; nothing created.
- D1: `import mesa` adds no handler and writes no file. A run with the fake simulation: `mesa.log`
  in the simulations directory (nothing in the current directory), timestamped lines from the
  engine and another logger, the status-check and scoring warnings with their tracebacks, the
  same lines on the screen; a second `run()` in one process doesn't double lines; a restart
  appends; an error stop logs the stop line, traceback and "no runs in flight" to the file.
- D2: the start-up heartbeat (running, no iteration, nothing in flight), per-pass heartbeats
  (`launched`, last status, `status check failed`, `job_id` or `null`, numpy run numbers as
  ints), the stop record for finished, an error and Ctrl-C; refused for a young, a time-less and
  a 199 s old (limit 200 s) `"running"` heartbeat and an unreadable one (file untouched, nothing
  launched, error in `mesa.log`); a stopped one doesn't block; a 201 s old one is taken over; the
  guard leaves another driver's heartbeat alone; a failing stop write is logged and the original
  error still raised.
- `job_id` commit: `job_id` follows `run_id` through a continuation (fake `itmsubmit`), hash
  unchanged, read-only; a `Mesa` heartbeat with a `SolpsRun` in flight shows the job ID.
- D3: a driver killed mid-iteration (runs 1, 2 in flight), plus a never-submitted and a broken
  folder; the next driver adopts only unrecorded folders, skips the two with "needs attention",
  records the adopted runs with their own iteration through the normal handling (status-check
  warning, `cleanup()`), calls the strategy only afterwards, numbers new runs past the folders; a
  third driver retries only the unadoptable folders; an error during adoption lists the adopted
  runs in the error log and the stopped heartbeat; default hooks keep the old numbering; an
  adopted run with no iteration is skipped.
- D4: `existing_run_numbers` ignores files and non-`run_N` names; `adopt` rebuilds number,
  iteration, parameters, last job, folder, settings and the starting Slurm state (PENDING since
  submit, or RUNNING since `started`), returns `None` with no `run_info.json`, raises on a broken
  one, calls no tool. `status()` on adopted runs: still running (no false state change,
  needs-attention timed from `started`), PENDING → RUNNING (`started` written), ended while no
  driver ran (complete, `ended` written), continued with `Solps`' submit command, stalled at the
  cap counted from `run_info.json`, crashed with the job and sacct state. The engine's adoption
  step (called directly, not through `Mesa.run()`) with `Solps`: rows with each run's iteration,
  `cleanup()` for complete runs, the never-submitted folder skipped, nothing submitted.
- Reruns after each D commit: earlier tests fail only where an earlier change was intended (C2's
  status column and scoring-failure rows, C5's tool check, old `SolpsRun` signatures) or where a
  test counted log lines or `read_hdf` calls that D1/D3 changed; checked against the commit before.
- `5d89426` (b2fstati fallback): with placeholder tools on a restricted `PATH`, a reference with
  both files, `b2fstate` only and `b2fstati` only gives `run_0/b2fstati` from the right file, with
  the log line; with neither, `Solps(...)` raises naming the folder and nothing is created.
- `2b70784` (window in points): synthetic `b2time.nc` files (`timesa`, `ne3da`, `te3da`): fewer
  points than the minimum (74 of 75, not converged); exactly the minimum (converged when flat);
  drifting (0.2 s timescale, not converged) and slow (2 s, converged) profiles; drift only before
  the window (converged) and a jump inside it (not converged); uneven (geometric) spacing fitted
  against `timesa`; 1 ns steps (a 5/s drift still caught); `timesa` going backwards or repeating in
  the window (one warning, test still applied) and backwards only before it (no warning); the
  `b2mn.exe.dir` copy still read first; a missing file gives `None`. `Solps`: defaults (25, 75,
  1.0, no warning); floors raised with one warning each (window 3 → 5, factor 1 → 2, both at
  once); values at the floors give no warning; 2.2 × 5 → 11, 2.5 × 7 → 18; 25.0, 25.7, `"25"`,
  `True`, `None` rejected, `numpy.int64(30)` accepted; the old names rejected. `example_input.py`
  compiles and its `Solps(...)` keywords are all valid (not run).
- Convergence check 1 (`7641b59` to `317d9ab`): `tests/test_convergence.py`, 14 tests, all pass. A
  steady run converges; a drift on a 0.5 s timescale doesn't, a 2 s one does; a missing file gives
  `None`; 299 of 300 points and 199 of 200 (the hold, with a lower minimum) are not converged;
  a 5 % step in the last 30 points, or 120 points from the end (the last window alone passes),
  is not converged; after a step at point 300 it is not converged with 150 more points and
  converged with 201 more; the verdict is the same on repeated calls; guard cells jumping by six
  orders of magnitude, with zeros and negative values, change neither a converged nor a drifting
  verdict; `windows_pass` agrees with `numpy.polyfit` window by window (uneven spacing, four
  timescales). Run against the code before the guard-cell and hold commits, the hold, guard-cell
  and `windows_pass` tests fail (6 of 14), as they should. On the real files, `windows_pass`
  matched `polyfit` on every 37th window at three timescales (0 mismatches). The sanity check and
  timings are in "Convergence check 1".
- `1ef403c` (`b2mndr_stim`): a copy of a `b2mn.dat` with stim `-1` (tab-indented, trailing comment,
  a commented-out stim line and a `b2mndr_stim_x` key): `'0'` after `build_solps_case`, other
  lines byte-identical, reference unchanged; `'-1'` after `continue_run` (fake `itmsubmit`, run in
  `run_0`), file byte-identical to the reference's, and after a second continuation; key missing
  (with and without a final newline, only commented out, via `build_solps_case`) → added at the
  end; CRLF endings kept; an unquoted value replaced; no `b2mn.dat` in the reference → none made.
  The earlier two fixes' tests rerun and pass.
- Imports of all `mesa_solps` modules, with mesa from the `mesa-ab` branch.
- `1ed9690` (new runs continue in time): `python -m pytest tests` with
  `MESA_STEP_REFERENCE_DATA` set: 49 passed (no test file checks `b2mndr_stim`; `1ef403c`'s
  checks were throwaway scripts). By hand, `build_solps_case` in a temp folder on a reference
  `b2mn.dat` with stim `'0'` (tab, trailing comment, a commented-out stim line): `'-1'` in the
  run's file, every other byte unchanged. The SOLPS checks are reading only (see "Files needed"
  and "Time").
- Dry-run commits (`4ac188c` to `c8b5799`). The setup:
  - A toy plug-in in Python that keeps each run's state in its folder, so runs survive a killed
    driver. A run is complete after 2 status checks.
  - Strategies: a toy one (5 points in iteration 0, then 1) and the real `GPOptimizer`.
  - Each driver ran in its own process, with 2 slots and `poll_interval` 0 (no sleeping).
    "kill -9" was `os._exit`, so no cleanup ran.
  - `PATH` had no Slurm tools.

  The checks:
  - `4ac188c` (resume):
    - No restart: iterations 0, 1, 2 with 5 + 1 + 1 runs, and `iteration.json` empty at the
      end.
    - Killed in iteration 0 with 2 runs in flight and 3 points not launched: the restart adopts
      the 2 runs, logs the resume, and runs exactly the 3 saved points as iteration 0, numbered
      past every folder. Total 5 + 1 + 1, run numbers with no gaps.
    - Killed before the first launch: all 5 points resumed.
    - Killed inside a launch, before the file is rewritten: that point runs twice (the
      documented window).
    - Killed in a 1-point iteration: nothing to resume, and the driver goes on to the next.
    - Unreadable, stale-iteration or wrong-parameter files: a warning, no extra runs, and a
      normal stop at `max_iterations`.
  - `9dae4d3` (stalled runs), with the real `GPOptimizer` (`initial_sample_count` 4, run 1
    stalled):
    - Run 1 is in the evaluations file with status `stalled` and its score.
    - Neither of the 2 GP fits included it (4 and 5 rows).
    - Iterations 0–3 had 4 + 1 + 1 + 1 runs, so the stalled run still counted towards the
      initial sample.
    - 1 usable of 5 rows (2 stalled, 2 crashed) gives the new "fewer than 2" error.
  - `6931ecd` (equal scores):
    - Every run scoring 1.0: before the change, inference-tools' "array must not contain infs or
      NaNs"; after, the new message in `mesa.log` and the evaluations file intact.
    - Equal usable scores with a different stalled one: still the error.
    - Two different scores: the fit works.
  - `1c1da0f` (`max_iterations`): the docstring reads back.
  - `c8b5799` (cosmetics):
    - Ctrl-C mid-iteration: exit status 130, no traceback, the short message on the screen and
      in `mesa.log`, the heartbeat `stopped` / `interrupted`. A restart finishes the case.
    - Ctrl-C with the heartbeat taken by another driver: "not marked stopped (see above)".
    - The refusal message names 2 x `poll_interval` in seconds (3600 s for 1800).
    - The new-parameter log lines print plain numbers (`np.float64(...)` before).
    - The earlier tests rerun and pass.
- `6d6c8cd` (initial-sample count), `initial_sample_count` 4, 2 free parameters:
  - `propose_evaluations` on toy tables, against the code before the change: empty → 4 random
    (both); 3 rows → 1 random (2 before); 4 rows with a crashed (NaN) and a stalled row → a GP
    fit on the 2 usable rows, point in bounds (1 random before). The caller's table is unchanged.
  - `Mesa.run()` with the toy plug-in (4 slots, `max_iterations` 2, `poll_interval` 0, run 1
    crashed, run 2 stalled): iteration 0 has 4 random runs, iterations 1 and 2 one GP proposal
    each (4 + 1 + 1). Before the change, iteration 1 was a random top-up and only iteration 2 a
    GP proposal.
  - Ctrl-C with runs 0 and 1 recorded and 2 and 3 in flight: the restart adopts 2 and 3,
    finishes iteration 0, and iteration 1 is a GP proposal (4 + 1 + 1).

### What the cluster tests must check

Gathered from all series; none of this could be tested here.

- **Transport file (A2):** on both MAST-U references (D-only and D + C), each run's
  `b2.transport.inputfile` differs from the reference only in the kind 1, 3 and 4 blocks.
- **Run folder set-up (A3, A5):** `setup_baserun_eirene_links` makes `fort.1` and EIRENE starts;
  `b2.user.parameters` is copied; no `fort.*` from the reference.
- **Submit (A4):** the job ID parsed from `itmsubmit` is right; `run_info.json` is written.
- **Slurm output (B1, B4):** the real `squeue -o "%i %T %r"` and `sacct -o State%30` output
  (padding, states such as `PREEMPTED` or `REQUEUED`); how long a job takes to appear in `sacct`
  after leaving `squeue`; `b2fstate_OK_bool` with no arguments checks `b2fstate` in the current
  directory; whether the 24 h / 1 h / 30 min attention limits suit.
- **Convergence and continuation (B3, B5, C4):** `.quit` is touched and SOLPS stops cleanly; a
  continuation restarts from `b2fstati` and appends to `b2time.nc`; the cap gives `"stalled"`.
- **`b2time.nc` history (`1ef403c`, `2b70784`, `1ed9690`):** a fresh `run_N` gets a new
  `b2time.nc` ("will be created" in `run.log`) whose first time is one step after refconv's end
  time (`b2mndr_stim` `-1`), and each continuation appends to it (`-1`); `baserun/` holds no
  `b2time.nc`. A continuation's `b2time.nc`
  ends up in `run_N/`, and no stale copy stays in `run_N/b2mn.exe.dir/` (`find_time_file` reads
  that one first). Check the point counts the driver works with against the file, and whether the
  window and minimum defaults suit real `b2mndr_b2time` values.
- **Convergence check 1:** a run is only stopped (`.quit`) after the test has held for one window
  (by default 300 points minimum, 200 for the hold); check in `mesa.log` / `run_info.json` that
  converged runs stop where the offline check says, and how long a call takes on the cluster's
  file system.
- **Reference state (`5d89426`):** the log says which reference file `b2fstati` came from.
- **Crashes (B4, C2, C4):** a crashed run gets a row with its status and the sacct state in the
  log, keeps its folder, and the other runs carry on; watch whether the GP re-proposes crashed
  points (crash loop).
- **Poll interval (B6):** 1800 s against real job lengths.
- **Error handling (B7):** watch for "status check failing, needs attention" lines.
- **Evaluations file (C1, C2):** rows, types and the `status` column after a real fit; read back
  in pandas.
- **Disk use (C3):** measure a real fit, then decide a keep-list.
- **Logging (D1):** `mesa.log` in the case folder, appended across restarts, with B4's state
  lines and any tracebacks.
- **Heartbeat (D2):** `cat heartbeat.json` from another login node while the driver runs; a
  second driver on the same case is refused; after a clean stop or error stop a restart works at
  once; after killing the driver (close the session) a restart is refused until 2 ×
  `poll_interval` has passed or the file is deleted.
- **Resume (D3, D4):** kill the driver with runs pending, running, and finished but not yet
  recorded; restart: each is adopted, followed to the end and recorded with its iteration, new
  run numbers don't clash, and a never-submitted folder is logged and skipped. Kill it again
  during a continuation's resubmit only if the D4 window above is worth checking.
- **Iteration number after a restart (`4ac188c`):** after a driver restart (Ctrl-C, and kill
  -9 or a closed session), the iteration number and remaining budget are as expected:
  - an interrupted multi-run iteration (e.g. the initial batch) carries on under its own number
    ("Resuming iteration N" in `mesa.log`, its leftover points from `iteration.json`);
  - a finished one is followed by the next number;
  - the run counts per iteration in the evaluations file match a run with no restart.
- **Stalled runs (`9dae4d3`):** a stalled run shows in the evaluations file (status `stalled`,
  with its score) but not in the GP fit. The fit logs no row count, so check this offline: the
  rows the GP fits are those with a score and a status other than `stalled`.
- **Initial sample (`6d6c8cd`):** with `initial_sample_count=N`, iteration 0 has N random runs
  and iteration 1 is a GP proposal ("New parameters:" from the GP in `mesa.log`, one run).
- **Tools at start-up (C5):** the driver starts in a shell with SOLPS-ITER's `setup.csh` sourced
  and stops with the list of missing tools otherwise.

## Packaging (earlier work)

### What was done

- Added `pyproject.toml` (setuptools backend). It defines the package `mesa_solps` at version
  `0.1.0.dev0` with `requires-python = ">=3.10"`, and depends on `numpy`, `scipy`, `mesa`
  and `sim-solps`. These are the third-party imports in `mesa_solps/`.
- Added a `.gitignore` for build artefacts (`build/`, `dist/`, `*.egg-info/`, `__pycache__/`).
- No code changes were needed: every module imports as-is.

### Repositories

All three repositories are used through forks, and fixes for the dependencies are collected
there to go upstream to C-bowman later as PRs:

| Package    | Fork                                    | Upstream                                  |
|------------|-----------------------------------------|-------------------------------------------|
| mesa-solps | https://github.com/omyatra/mesa-solps   | https://github.com/C-bowman/mesa-solps    |
| mesa       | https://github.com/omyatra/mesa         | https://github.com/C-bowman/mesa          |
| sim-solps  | https://github.com/omyatra/sim-solps    | https://github.com/C-bowman/sim-solps     |

Fixes waiting to go upstream:

1. **mesa: add `version` to `pyproject.toml`** (fork commit `468c754`). Upstream mesa has a
   `[project]` table with no `version` and no `dynamic = ["version"]`, so setuptools
   (>= 61) refuses to build it: `project must contain ['version'] properties`. Upstream
   mesa can't be pip-installed until this is merged.
2. **mesa: pass the iteration number to `Simulation.launch()`** (`d484c39`, branch `mesa-ab`,
   not pushed yet). See "Current state" above.
3. **mesa: poll interval and error handling** (`2c5d1ba`, `df8d08b`, branch `mesa-ab`, not
   pushed yet). See "Current state" above.
4. **mesa: safe evaluations file; a row for every run** (`5f2dd57`, `2014bc3`, branch
   `mesa-ab`, not pushed yet). See "Current state" above.
5. **mesa: log file, heartbeat, resume** (`dad79c4`, `4277d15`, `a1a81f8`, branch `mesa-ab`,
   not pushed yet). See "Current state" above.

### Pins and why

```
mesa      @ git+https://github.com/omyatra/mesa.git@468c754eeb1b4718c3336bd5b436c11f332a8a72
sim-solps @ git+https://github.com/omyatra/sim-solps.git@7a8d1ac47a8d6bd82af8e89fa6390ed8baad179c
```

The mesa pin is now behind the code: see "Current state" above.

- **mesa `468c754`** = upstream `1afc9ad` ("Framework refactor (#5)", current upstream
  master) plus the one-line version fix above. mesa has no tags. `1afc9ad` is the first commit
  that has the API mesa-solps uses:
  - `mesa.objectives.ObjectiveFunction`. Before this commit it was `mesa.diagnostics`.
  - `mesa.simulations.{RunStatus, Simulation, SimulationRun}`. Before this commit,
    `mesa.simulations` was a package that still held the SOLPS code that now lives in this
    repo.
  - `mesa.core.Mesa` and `mesa.strategies.GPOptimizer`, used by `example_input.py`.

  `SolpsRun`, `Solps` and `SolpsLikelihood` all implement every abstract method of the
  mesa base classes at this commit, and each instantiates without error.
- **sim-solps `7a8d1ac`** = current upstream main. The latest tag, `0.1.3`, can't be used
  because `mesa_solps/objective.py` imports `sims.instruments.Instrument`, which was added
  after it (`ffbca7b`). `7a8d1ac` is the tip of main. The only change after `ffbca7b` is
  that `ThomsonScattering` measurement checks use `isinstance` instead of exact type
  checks, with no API change, so the tip was chosen over the minimum commit.
  `SolpsInterface(balance_filepath=...)`, `Instrument.update_interface`,
  `log_likelihood(likelihood=...)` and `sims.likelihoods.cauchy_likelihood` all match.
- **Python >= 3.10**: the mesa-solps code alone needs 3.9 (built-in generics such as
  `dict[str, float]` in signatures). mesa requires 3.10, so a lower bound would not resolve.
- `numpy >= 1.20` and `scipy >= 1.6.3` use the same lower bounds as mesa and sim-solps.

### Test result

Ran in a fresh venv under `/tmp` with Python 3.14.6 on Linux, using the real pins (no
patched copies):

- `pip install --no-cache-dir .` succeeded, and so did `pip check` ("No broken requirements
  found"). Resolved versions included mesa 0.1.0, sim-solps 0.1.dev37+g7a8d1ac47,
  numpy 2.5.4, scipy 1.18.1, pandas 3.1.0, tables 3.11.1 and inference-tools 0.15.1.
- `python -c "import mesa_solps"` worked from outside the repo, as did importing each of
  `models`, `objective`, `parameters`, `simulation` and `transport`.
- The venv was deleted afterwards.

Nothing was run beyond imports and constructors. The repo has no tests.

### Open issues

- **No licence.** mesa and sim-solps declare MIT, but mesa-solps has no licence file or
  `license` field. That is upstream's decision. `pyproject.toml` has no licence
  classifier for the same reason.
- **The pins point at forks.** Before this packaging goes upstream as a PR, the mesa fix must
  be merged upstream and both pins switched to C-bowman URLs. Upstream tagging a mesa
  release and a sim-solps release after `0.1.3` would allow pinning tags instead of commits.
- **sim-solps reports a dev version.** The fork has no tags, so setuptools_scm gives
  `0.1.dev37+g7a8d1ac47` rather than `0.1.4.dev5+g7a8d1ac` (what it gives from upstream,
  which has tags). Pushing the upstream tags to the fork fixes this.
- **Not publishable to PyPI.** PyPI rejects direct (`@ git+...`) dependencies. Also, the PyPI
  name `mesa` belongs to an unrelated agent-based-modelling package, so mesa must never be
  installed with a bare `pip install mesa`.
- **Untested:** Python 3.10 to 3.13, macOS and Windows, and all runtime behaviour (the
  driver, `example_input.py`, Slurm submission, convergence checking, file I/O).
  `inference-tools`, which the example imports directly, is only present as a transitive
  dependency of mesa.
- **SciPy 2.0.** `mesa_solps/simulation.py` (and sim-solps's `interface.py`) use the
  deprecated `scipy.io.netcdf` namespace. It works on SciPy 1.18 with a
  `DeprecationWarning`, but SciPy 2.0 will remove it. The fix is
  `from scipy.io import netcdf_file`.
- **Broken module in upstream mesa.** `mesa/plotting.py` imports names that no longer exist in
  `mesa` (`normalise_parameters`, `conductivity_profile`, `diffusivity_profile`).
  mesa-solps doesn't import it.
- **Possible bug spotted while reading, left alone (out of scope):** in `build_solps_case`,
  the result of `line.replace(...)` is discarded, the parameter value isn't converted to a
  string, the output keeps the `.mesa` file name, and every line written gets an extra newline.
  (The other bug noted here, `check_convergence` opening `./b2time.nc` relative to the current
  directory, is fixed by A1.)
