# mesa-solps

A SOLPS-ITER plug-in for the MESA optimisation framework, which fits SOLPS transport profiles
to experimental data with Gaussian-process optimisation. The package is `mesa_solps/`.
`example_input.py` is an example MESA input file. See `HANDOFF.md` for packaging state,
dependency pins and open issues.

## Rules

- **Never run the driver.** Don't run `example_input.py`, `Mesa.run()`, `Solps.launch()` or
  any `SolpsRun` method, or anything else that submits jobs. They call `itmsubmit`,
  `squeue` and `scancel` (Slurm), `chdir` into run directories, and delete files in them
  (`SolpsRun.cleanup`). Testing is limited to imports and pure functions (`models`,
  `transport` writing to a temp dir).
- Never use ssh or touch clusters.
- Don't edit the dependency repos (mesa, sim-solps) from here. Fixes to them go in their own
  repos as separate commits, so they can go upstream as PRs.
- Keep commits upstreamable: packaging, fixes and docs go in separate commits, with no
  unrelated refactoring.
- This repo is public. Keep committed files about the code: no personal notes, user names,
  cluster names or machine-specific paths.
- No licence has been chosen yet. Don't add one; that is the upstream author's decision.

## Install / test

```
python -m venv /tmp/venv && /tmp/venv/bin/pip install .
/tmp/venv/bin/python -c "import mesa_solps.simulation, mesa_solps.objective"
```

`mesa` and `sim-solps` are git dependencies pinned to commits in `pyproject.toml`. If you
change a pin, check the APIs that `mesa_solps/` imports against that commit. Never
`pip install mesa` from PyPI: that is an unrelated package.
