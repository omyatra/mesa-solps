# Handoff: packaging mesa-solps

## What was done

- Added `pyproject.toml` (setuptools backend). It defines the package `mesa_solps` at version
  `0.1.0.dev0` with `requires-python = ">=3.10"`, and depends on `numpy`, `scipy`, `mesa`
  and `sim-solps`. These are the third-party imports in `mesa_solps/`.
- Added a `.gitignore` for build artefacts (`build/`, `dist/`, `*.egg-info/`, `__pycache__/`).
- No code changes were needed: every module imports as-is.

## Repositories

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

## Pins and why

```
mesa      @ git+https://github.com/omyatra/mesa.git@468c754eeb1b4718c3336bd5b436c11f332a8a72
sim-solps @ git+https://github.com/omyatra/sim-solps.git@7a8d1ac47a8d6bd82af8e89fa6390ed8baad179c
```

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

## Test result

Ran in a fresh venv under `/tmp` with Python 3.14.6 on Linux, using the real pins (no
patched copies):

- `pip install --no-cache-dir .` succeeded, and so did `pip check` ("No broken requirements
  found"). Resolved versions included mesa 0.1.0, sim-solps 0.1.dev37+g7a8d1ac47,
  numpy 2.5.4, scipy 1.18.1, pandas 3.1.0, tables 3.11.1 and inference-tools 0.15.1.
- `python -c "import mesa_solps"` worked from outside the repo, as did importing each of
  `models`, `objective`, `parameters`, `simulation` and `transport`.
- The venv was deleted afterwards.

Nothing was run beyond imports and constructors. The repo has no tests.

## Open issues

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
- **Possible bugs spotted while reading, left alone (out of scope):**
  - `SolpsRun.status()` calls `check_convergence()`, which opens `./b2time.nc` relative to
    the current working directory, not `self.directory`.
  - In `build_solps_case`, the result of `line.replace(...)` is discarded, the parameter
    value isn't converted to a string, the output keeps the `.mesa` file name, and every
    line written gets an extra newline.
