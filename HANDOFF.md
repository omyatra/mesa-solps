# Handoff: mesa-solps

## Current state: driver fixes, series A, B, C and D done, plus three fixes from the cluster checks

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
| `convergence_window_points` | 25 | 5 | the fit uses the last this many points of `b2time.nc`; must be an `int` |
| `convergence_min_run_factor` | 3 | 2 | no convergence before ceil(factor × window) points |
| `convergence_timescale` | 1.0 s | – | unchanged |

`convergence_window` and `convergence_min_run_time` are gone (passing them is a `TypeError`).

**Next:** push the mesa branch, then move the mesa pin in `pyproject.toml` to its last commit (the
last commit of the plan), then the cluster tests (see "What the cluster tests must check" below),
then fill in the "Tested:" sections. Before the main mesa test, decide when logging starts (see
"Open questions": start-up warnings and errors don't reach `mesa.log`).

Branches (local, not pushed):

- mesa-solps: `worktree-mesa-ab`
- mesa: `mesa-ab` (eight commits: one needed by A4, then B6, B7, C1, C2, D1, D2 and D3)

**mesa-solps needs mesa from the `mesa-ab` branch.** From A4 on, `Solps.launch()` takes
`iteration`, which only mesa `d484c39` and later pass. B6 (poll interval), B7 (error handling),
C1 (safe evaluations file) and C2 (status column, `"stalled"`) are engine changes the driver needs
too. From C4 on, the plug-in returns `"stalled"`, which an older engine doesn't know: the run
would never leave its slot and the iteration would never end. D4's adoption hooks and
`SolpsRun.job_id` are only used by an engine with D2 and D3. The `pyproject.toml` pin still
points at `468c754`, so
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
  initial-sample count `n_evals` is the highest run number, not the number of runs: run numbers
  start at 0, so after 20 initial runs `n_evals` is 19 and one more random run is drawn before
  the GP phase starts. Check with the mesa author. D3 doesn't depend on `n_evals` and doesn't
  change it, but folders that can't be adopted leave gaps in the run numbers, and each gap below
  the highest number counts as an initial sample that never ran.
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
- **Convergence window in points:** with a tiny time step, 25 points cover very little simulated
  time, so a run can look converged over a short stretch. Check the defaults against real
  `b2mndr_b2time` values and time steps.
- **Stale `b2time.nc` in `b2mn.exe.dir/`:** `find_time_file` reads `run_N/b2mn.exe.dir/b2time.nc`
  before `run_N/b2time.nc`. If a continuation leaves an old copy there, the point count and the
  fit use the wrong file (see the cluster checks).
- **`b2mn.dat` comments:** `set_b2mn_value` was only tested on hand-made files; check that real
  `b2mn.dat` files have no other way of writing a key or a comment.

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
- `1ef403c` (`b2mndr_stim`): a copy of a `b2mn.dat` with stim `-1` (tab-indented, trailing comment,
  a commented-out stim line and a `b2mndr_stim_x` key): `'0'` after `build_solps_case`, other
  lines byte-identical, reference unchanged; `'-1'` after `continue_run` (fake `itmsubmit`, run in
  `run_0`), file byte-identical to the reference's, and after a second continuation; key missing
  (with and without a final newline, only commented out, via `build_solps_case`) → added at the
  end; CRLF endings kept; an unquoted value replaced; no `b2mn.dat` in the reference → none made.
  The earlier two fixes' tests rerun and pass.
- Imports of all `mesa_solps` modules, with mesa from the `mesa-ab` branch.

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
- **`b2time.nc` history (`1ef403c`, `2b70784`):** a fresh `run_N`'s `b2time.nc` starts at time 0
  (`b2mndr_stim` `0`), and each continuation appends to it (`-1`). A continuation's `b2time.nc`
  ends up in `run_N/`, and no stale copy stays in `run_N/b2mn.exe.dir/` (`find_time_file` reads
  that one first). Check the point counts the driver works with against the file, and whether the
  window and minimum defaults suit real `b2mndr_b2time` values.
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
