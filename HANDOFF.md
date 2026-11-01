# Handoff: mesa-solps

## Current state: driver fixes, series A and B done

Fixes to the SOLPS driver are being made from a commit plan kept outside this repo, as series of
commits labelled A1, A2, ... (A: launching runs, B: polling, C: failures and results, D: logging,
heartbeat and resume). **Series A (A1–A5) and B (B1–B7) are done. Series C (C1–C4) is next.**
Each commit message's "Tested:" section is still empty: it is filled in after the tests on the
cluster.

Branches (local, not pushed):

- mesa-solps: `worktree-mesa-ab`
- mesa: `mesa-ab` (three commits: one needed by A4, then B6 and B7)

**mesa-solps needs mesa from the `mesa-ab` branch.** From A4 on, `Solps.launch()` takes
`iteration`, which only mesa `d484c39` and later pass. B6 (poll interval) and B7 (error handling)
are engine changes the driver needs too. The `pyproject.toml` pin still points at `468c754`, so
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
| B1    | mesa-solps | `96ce9b8` | `status()` matches the job ID exactly: `squeue -h -u <user> -o %i`, parsed into a set (was a substring search of the whole table). |
| B2    | mesa-solps | `5d8390f` | The 24 h run timeout is removed: no `"timed-out"` from `status()`, no `timeout_hours` in `Solps`, `SolpsRun` or `example_input.py`. Run length is left to SOLPS's own clean stop in `b2mn.dat`. |
| B3    | mesa-solps | `55508cc` | `Solps` settings `convergence_min_run_time` (1e-3 s), `convergence_window` (2e-4 s), `convergence_timescale` (1.0 s), passed via each `SolpsRun` to `check_convergence`. Window ≥ minimum run time is a `ValueError` at start-up (in `Solps.__init__`), replacing the assert. |
| B4    | mesa-solps | `ee6a4d4` | Per-run Slurm states. One `squeue -h -u <user> -o "%i %T %r"` call per status check; a failing call keeps the run "running". PENDING: no checks, needs-attention log after 24 h. RUNNING: convergence test (`.quit`), needs-attention log after 1 h with no `b2time.nc`. COMPLETING: wait, log after 30 min. Other states: wait. Not listed: `sacct -j <id> -n -X -o State%30`; a finished state means ended, anything else or a failing `sacct` means still running, unknown to both for 3 polls is logged. Ended: no `balance.nc`, or `b2fstate_OK_bool` (run in `run_N/`) non-zero, means crashed; else complete. State changes are logged, and `started` / `ended` are added to the job's entry in `run_info.json`. Needs-attention lines are logged once per state. |
| B5    | mesa-solps | `27d4b18` | At the end of a healthy job: converged → complete; `b2time.nc` missing or unreadable → crashed (`check_convergence` returns `None` for "can't judge"); not converged → continued in `run_N/` (`b2fstati` → `b2fstati<k>`, `b2fstate` → `b2fstati`, `balance.nc` → `balance<k>.nc`, `b2mn.prt` removed, resubmitted, job appended to `run_info.json`). After `max_continuations` (new `Solps` setting, default 10, counted from `run_info.json`) the run is logged as stalled and returned as complete. `submit_job()` is shared by `launch()` and continuations. `SolpsRun`'s hash no longer includes the job ID. |
| B6    | mesa | `2c5d1ba` | `launch_iteration`: each pass checks statuses, then fills free slots, then sleeps `poll_interval` (new setting, default 1800 s; no sleep after the iteration's last run). `poll_interval` is a `Mesa` argument and an optional input-file variable (`parse_input_module` only requires fields without a default). |
| B7    | mesa | `df8d08b` | Error handling. `status()` raising: warning, run treated as running; after 3 in a row, "status check failing, needs attention". Scoring raising (`get_results` / objective): run counted as crashed, folder kept, other runs carry on. Anything else: `Mesa.run()` logs the traceback and the runs in flight (run number, folder), then re-raises; no job is cancelled. |

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
- **A4 / B5, no submit-success check.** `itmsubmit`'s output is parsed for the job ID without
  checking it worked; a failed launch or continuation gets a junk ID, which B4 then reports as
  "unknown to squeue and sacct, needs attention" (deferred, as planned).
- **A5:** `cleanup()`'s keep list doesn't include `b2.user.parameters`, so it is deleted from
  scored runs until C3 makes `cleanup()` keep everything.
- **B4, check on the cluster:** the real `squeue -o "%i %T %r"` and `sacct -o State%30` output
  (padding, other states such as `PREEMPTED` or `REQUEUED`); how long a job takes to appear in
  `sacct` after leaving `squeue`; that `b2fstate_OK_bool` checks `b2fstate` in the current
  directory when called with no arguments; the time limits (24 h, 1 h, 30 min).
- **B4 / B7, missing `b2fstate_OK_bool` is retried, not a stop.** `status()` raises if
  `run_info.json` is missing or broken at a state change, or if `b2fstate_OK_bool` is not on
  `PATH`. B7 catches every `status()` error, so both are retried each poll (warning, then
  needs-attention after 3) rather than stopping the driver, and the run holds its slot until the
  cause is fixed. Proposed fix (not in the plan yet): check at start-up (in `Solps.__init__`) that
  every outside tool the driver calls is on `PATH` (`setup_baserun_eirene_links`, `itmsubmit`,
  `b2fstate_OK_bool`, `squeue`, `sacct`), as a small commit with series C.
- **B5:** a continued run's intermediate files (`b2fstati<k>`, `balance<k>.nc`) are kept while it
  runs, but `cleanup()` deletes them once the run is scored, until C3. A stalled run shows as
  "complete" to the engine until C adds a "stalled" status. Check on the cluster that a
  continuation restarts and appends to `run_N/b2time.nc` as in the hand-made restart.
- **B6:** the 1800 s default is SOLPS-scale; upstream may want a smaller default (it is a
  setting). The Himmelblau example (see above).
- **B7:** catching every `status()` error could hide a real bug; the needs-attention line is the
  guard, so watch for it in testing. A scoring failure gives no row in the evaluations file until
  C2.
- **Logging until D1:** `import mesa` calls `logging.basicConfig(level=INFO)`, so all log lines go
  to stderr, without timestamps; the second `basicConfig` call in `mesa/__init__.py` (to
  `runlog.log`) does nothing, and `core.logger_setup()` is never called. D1 (log to a file)
  should deal with both.
- **Naming:** `SolpsRun.run_id` holds the Slurm job ID of the run's current job, not an ID of the
  run (that is `run_number`). Renaming it `job_id` would be clearer; left out as an unrelated
  refactor.
- **mesa commit:** the required `iteration` argument breaks existing plug-ins once (see above);
  to raise in the mesa PR.

### What was tested

Only imports, pure functions and temp dirs; nothing that calls Slurm, and `Solps.launch()` was
not run. For B1, B2, B4 and B5, `SolpsRun.status()` was run on runs in temp dirs, with fake
`squeue`, `sacct`, `b2fstate_OK_bool` and `itmsubmit` scripts first on a restricted `PATH`
(checked to resolve to the fakes or to nothing; there was no `scancel`, real or fake). B6 and B7
used an in-memory fake simulation with `sleep` replaced. Throwaway test scripts were kept
outside the repo.

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
3. **mesa: poll interval and error handling** (`2c5d1ba`, `df8d08b`, branch `mesa-ab`, not
   pushed yet). See "Current state" above.

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
