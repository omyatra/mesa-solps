# Handoff: mesa-solps

## Current state: driver fixes, series A done

Fixes to the SOLPS driver are being made from a commit plan kept outside this repo, as series of
commits labelled A1, A2, ... (A: launching runs, B: polling, C: failures and results, D: logging,
heartbeat and resume). **Series A (A1–A5) is done. Series B (B1–B7) is next.** Each commit
message's "Tested:" section is still empty: it is filled in after the tests on the cluster.

Branches (local, not pushed):

- mesa-solps: `worktree-mesa-ab`
- mesa: `mesa-ab` (one commit, needed by A4)

**mesa-solps now needs the mesa commit below.** From A4 on, `Solps.launch()` takes `iteration`,
which only mesa `d484c39` passes. The `pyproject.toml` pin still points at `468c754`, so
`pip install .` alone installs a mesa that doesn't pass `iteration`, and the first launch fails
with a TypeError (before anything is created or submitted). Until the pin moves (the last commit
of the plan, after the mesa commits are pushed), install mesa from the `mesa-ab` branch as an
editable install after installing mesa-solps:

```
pip install -e .                  # mesa-solps
pip install -e <mesa checkout>    # mesa on branch mesa-ab, replaces the pinned mesa
```

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
  check yet (deferred to B4). Run number and iteration are cast to `int` (the engine gives numpy
  ints, which `json` rejects). No reader function yet; B5 / D4 add one.
- **A5:** message as planned.
- Commit messages: where the plan names the cluster, the name was dropped ("checked on scratch
  runs"), and plan labels are not referenced in commit messages.

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
- **A3, failed check leaves `run_N/` behind.** The driver stops and nothing is submitted. D4
  treats a folder without `run_info.json` as never submitted.
- **A5:** `cleanup()`'s keep list doesn't include `b2.user.parameters`, so it is deleted from
  scored runs until C3 makes `cleanup()` keep everything.
- **mesa commit:** the required `iteration` argument breaks existing plug-ins once (see above);
  to raise in the mesa PR.

### Decided for series B (not implemented yet)

- **B4, per-run states.** One `squeue -h -u <user> -o "%i %T %r"` call per poll (this replaces
  B1's `-o %i` call). Each run is checked only for what makes sense in its state: pending (no file
  checks; needs-attention log after 24 h), running (convergence test on the live `b2time.nc`;
  needs-attention log if there is still no `b2time.nc` after 1 h), completing (wait;
  needs-attention log after 30 min), not listed (ask `sacct`), ended (`balance.nc` and
  `b2fstate_OK_bool` decide crashed vs complete). State changes are logged, and `started` /
  `ended` times are added to the job's entry in `run_info.json` (A4's format allows extra keys).
  The time limits are starting values to tune in testing.
- **B5, can't judge = crashed.** At the end of a job, a missing or unreadable `b2time.nc` means
  the run can't be judged: crashed (logged), not continued. `check_convergence` will report this
  separately (e.g. return `None`). This narrows A1's "missing = not converged", which stays right
  while the job is running.

### What was tested

Only imports, pure functions and temp dirs; nothing that calls Slurm, and no `SolpsRun` method or
`Solps.launch()` was run. Throwaway test scripts were kept outside the repo.

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
- Imports of all `mesa_solps` modules, with mesa from the `mesa-ab` branch.

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
