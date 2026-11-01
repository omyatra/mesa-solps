from pathlib import Path
from datetime import datetime
import json
import os
import re
from os.path import isfile
from time import time
import logging
import subprocess
import shutil as sh
from scipy.io import netcdf
from numpy import log, polyfit, searchsorted

from sims.interface import SolpsInterface
from mesa.simulations import RunStatus, Simulation, SimulationRun
from .transport import check_transport_template, write_solps_transport_inputfile
from .models import linear_transport_profile, profile_radius_axis
from .parameters import conductivity_profile, diffusivity_profile, required_parameters


# Slurm job states (sacct) after which the job will not run again
ended_job_states = {
    "COMPLETED", "CANCELLED", "FAILED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"
}

# How long a run can stay in one state before the log says it needs attention
# (starting values, to tune in testing). The run is never cancelled for it.
pending_attention_hours = 24.0  # PENDING
no_time_file_attention_hours = 1.0  # RUNNING without a b2time.nc
completing_attention_hours = 0.5  # COMPLETING
unknown_attention_polls = 3  # polls in a row unknown to both squeue and sacct

# Outside tools the driver calls, checked at start-up (in Solps.__init__)
required_tools = (
    "setup_baserun_eirene_links", "itmsubmit", "squeue", "sacct", "b2fstate_OK_bool"
)


class SolpsRun(SimulationRun):
    def __init__(
        self,
        parameters: dict[str, float],
        run_number: int,
        iteration: int,
        directory: Path,
        launch_time: float,
        run_id: str,
        convergence_settings: dict[str, float],
        submit_command: str,
        max_continuations: int,
    ):
        self.parameters = parameters
        self.run_number = run_number
        self.iteration = iteration
        self.directory = directory
        self.launch_time = launch_time
        self.run_id = run_id
        # keyword arguments for check_convergence, from Solps
        self.convergence_settings = convergence_settings
        # for continuing the run in the same folder, from Solps
        self.submit_command = submit_command
        self.max_continuations = max_continuations

        # Slurm state of the job as last seen, and since when (driver's clock)
        self.job_state = "PENDING"
        self.job_state_since = launch_time
        self.attention_logged = False
        self.unknown_polls = 0
        # set once the job has ended: "complete", "stalled" or "crashed"
        self.final_status = None

    @property
    def job_id(self) -> str:
        # the Slurm job ID of the run's current job, for the engine's
        # heartbeat file; follows run_id, which changes on a continuation
        return self.run_id

    def status(self) -> RunStatus:
        """
        Checks the run once per poll, only for what makes sense in the job's
        Slurm state. Nothing is decided about the run's result until Slurm
        confirms that the job has ended.
        """
        if self.final_status is not None:
            return self.final_status

        whoami = subprocess.run("whoami", capture_output=True, encoding="utf-8")
        username = whoami.stdout.rstrip()

        # job ID, state and reason, one job per line, no header
        squeue = subprocess.run(
            ["squeue", "-h", "-u", username, "-o", "%i %T %r"],
            capture_output=True,
            encoding="utf-8",
        )
        if squeue.returncode != 0:
            self.log(
                f"squeue failed (exit code {squeue.returncode}), status "
                f"decided next poll: {squeue.stderr.strip()}"
            )
            return "running"

        jobs = {}
        for line in squeue.stdout.splitlines():
            fields = line.split(maxsplit=2)
            if len(fields) >= 2:
                jobs[fields[0]] = (fields[1], fields[2] if len(fields) > 2 else "")

        if self.run_id in jobs:
            self.unknown_polls = 0
            state, reason = jobs[self.run_id]
            self.change_state(state)
            if state == "PENDING":
                self.attention_after(
                    pending_attention_hours,
                    f"pending since {timestamp(self.job_state_since)} ({reason})",
                )
            elif state == "RUNNING":
                self.check_running()
            elif state == "COMPLETING":
                self.attention_after(
                    completing_attention_hours,
                    f"completing since {timestamp(self.job_state_since)}",
                )
            # any other state (e.g. CONFIGURING, SUSPENDED): wait, no checks
            return "running"

        # not listed: ask sacct whether the job has ended
        sacct = subprocess.run(
            ["sacct", "-j", self.run_id, "-n", "-X", "-o", "State%30"],
            capture_output=True,
            encoding="utf-8",
        )
        if sacct.returncode != 0:
            self.log(
                f"job {self.run_id} not in squeue and sacct failed (exit code "
                f"{sacct.returncode}), status decided next poll: {sacct.stderr.strip()}"
            )
            return "running"

        words = sacct.stdout.split()  # e.g. "CANCELLED by 12345"
        sacct_state = words[0] if words else None
        if sacct_state is None:
            self.unknown_polls += 1
            if self.unknown_polls == unknown_attention_polls:
                self.log(
                    f"job {self.run_id} unknown to squeue and sacct, needs attention"
                )
            return "running"
        self.unknown_polls = 0
        if sacct_state not in ended_job_states:
            # e.g. sacct still says RUNNING just after the job left squeue
            return "running"

        self.change_state(sacct_state)
        result = self.check_ended()
        if result == "continue":
            self.continue_run()
            return "running"
        self.final_status = result
        return self.final_status

    def check_running(self):
        time_file = find_time_file(self.directory)
        if time_file is None:
            # normal at first: SOLPS writes the first record a few minutes in
            self.attention_after(
                no_time_file_attention_hours,
                f"running since {timestamp(self.job_state_since)} with no b2time.nc",
            )
        elif check_convergence(self.directory, **self.convergence_settings):
            quit_file = self.directory / "b2mn.exe.dir/.quit"
            if not isfile(quit_file):
                subprocess.run(["touch", quit_file], encoding="utf-8")

    def check_ended(self) -> str:
        """
        The job has ended, so its output should all be there now. Returns
        "crashed", "complete", "stalled" if it hasn't converged after
        max_continuations, or "continue" if the run ended cleanly but hasn't
        converged.
        """
        # the job's final Slurm state (from sacct), for the crash messages
        ended_as = f"job {self.run_id} ended as {self.job_state}"
        if not isfile(self.directory / "balance.nc"):
            self.log(f"crashed: the job ended without writing balance.nc ({ended_as})")
            return "crashed"
        try:
            ok_bool = subprocess.run(
                ["b2fstate_OK_bool"],
                cwd=self.directory,
                capture_output=True,
                encoding="utf-8",
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"b2fstate_OK_bool not found on PATH, so {self.directory} "
                f"can't be checked; run the driver in a shell with SOLPS-ITER's "
                f"setup.csh sourced"
            )
        if ok_bool.returncode != 0:
            self.log(
                f"crashed: b2fstate_OK_bool says b2fstate is bad "
                f"(exit code {ok_bool.returncode}; {ended_as})"
            )
            return "crashed"

        converged = check_convergence(self.directory, **self.convergence_settings)
        if converged is None:
            self.log(
                f"crashed: the job ended cleanly but its b2time.nc is missing "
                f"or unreadable, so convergence can't be judged ({ended_as})"
            )
            return "crashed"
        if converged:
            return "complete"

        # the count is taken from run_info.json, so it survives a driver restart
        continuations = len(read_run_info(self.directory)["jobs"]) - 1
        if continuations >= self.max_continuations:
            self.log(
                f"stalled: not converged after {continuations} continuations; "
                f"scored from its last balance.nc"
            )
            return "stalled"
        return "continue"

    def continue_run(self):
        """
        Continues the run in its own folder from the state it ended in, keeping
        the previous b2fstati and balance.nc as b2fstati<k> and balance<k>.nc.
        """
        d = self.directory
        k = 1
        while (d / f"b2fstati{k}").exists() or (d / f"balance{k}.nc").exists():
            k += 1
        os.rename(d / "b2fstati", d / f"b2fstati{k}")
        os.rename(d / "b2fstate", d / "b2fstati")
        # any balance.nc after a job is then that job's own
        os.rename(d / "balance.nc", d / f"balance{k}.nc")
        if isfile(d / "b2mn.prt"):
            os.remove(d / "b2mn.prt")

        job_id, submit_time = submit_job(d, self.submit_command)
        info = read_run_info(d)
        info["jobs"].append({"job_id": job_id, "submit_time": timestamp(submit_time)})
        write_run_info(d, info)
        self.log(
            f"not converged; continued as job {job_id} "
            f"(continuation {len(info['jobs']) - 1} of at most {self.max_continuations})"
        )

        self.run_id = job_id
        self.job_state = "PENDING"
        self.job_state_since = submit_time
        self.attention_logged = False
        self.unknown_polls = 0

    def change_state(self, state: str):
        """Logs a change of the job's Slurm state and records it in run_info.json."""
        if state == self.job_state:
            return
        now = time()
        self.log(
            f"{self.job_state} -> {state} after "
            f"{duration(now - self.job_state_since)}"
        )
        if state == "RUNNING" or state in ended_job_states:
            key = "started" if state == "RUNNING" else "ended"
            info = read_run_info(self.directory)
            for job in info["jobs"]:
                if job["job_id"] == self.run_id and key not in job:
                    job[key] = timestamp(now)
            write_run_info(self.directory, info)
        self.job_state = state
        self.job_state_since = now
        self.attention_logged = False

    def attention_after(self, hours: float, message: str):
        """Logs message once if the job has been in its state for over hours."""
        if not self.attention_logged and time() - self.job_state_since > hours * 3600.:
            self.log(f"{message}, needs attention")
            self.attention_logged = True

    def log(self, message: str):
        logging.info(f"[solps_interface] run {self.run_number}: {message}")

    def cleanup(self):
        # Keeps every file. The state files (b2fstate, b2fstati*) are needed to
        # restart a fitted run later or re-check it, and the logs to explain an
        # odd score. Which files can go, and how much disk a fit needs, is not
        # known yet; a keep-list can be added once it is.
        pass

    def get_results(self) -> SolpsInterface:
        results_path = self.directory / "balance.nc"
        return SolpsInterface(balance_filepath=results_path)

    def cancel(self):
        subprocess.run(["scancel", self.run_id])

    def __key(self):
        # not run_id: it changes when the run is continued, and the engine
        # keeps runs in a set
        return self.directory, self.run_number, self.launch_time

    def __hash__(self):
        return hash(self.__key())


class Solps(Simulation):
    def __init__(
        self,
        reference_directory: Path,
        transport_profile_bounds: tuple[float, float],
        n_proc: int = 1,
        memory_gb: int = 20,
        convergence_min_run_time: float = 1e-3,
        convergence_window: float = 2e-4,
        convergence_timescale: float = 1.0,
        max_continuations: int = 10,
    ):
        # stop now, before any run folder is created, if a tool is missing
        check_tools()
        # absolute, so it doesn't depend on the current directory
        self.reference_directory = Path(reference_directory).resolve()
        self.transport_bounds = transport_profile_bounds
        # stop now, before anything is submitted, if the reference
        # b2.transport.inputfile can't be used as a template
        check_transport_template(self.reference_directory / "b2.transport.inputfile")
        self.n_proc = n_proc
        self.memory = memory_gb
        self.submit_command = (
            "itmsubmit" if n_proc == 1 else f'itmsubmit -m "-np {n_proc}" -M {memory_gb}GB'
        )

        # convergence test (check_convergence), all in seconds of simulated time
        if not convergence_window < convergence_min_run_time:
            raise ValueError(
                f"convergence_window ({convergence_window} s) must be shorter "
                f"than convergence_min_run_time ({convergence_min_run_time} s)"
            )
        self.convergence_settings = {
            "minimum_run_time": convergence_min_run_time,
            "window": convergence_window,
            "timescale": convergence_timescale,
        }
        # how many times a run that ends unconverged is continued
        self.max_continuations = max_continuations

    def launch(
        self,
        run_number: int,
        iteration: int,
        simulations_directory: Path,
        parameters: dict,
        **kwargs,
    ) -> SolpsRun:
        """
        Evaluates SOLPS for the provided transport profiles and saves the results.

        :param int run_number: \
            The run number corresponding to the requested SOLPS run, used to name
            directory in which the SOLPS output is stored.

        :param int iteration: \
            The iteration the run belongs to, recorded in run_N/run_info.json.

        :param str simulations_directory: \

        """
        case_dir = Path(simulations_directory).resolve() / f"run_{run_number}"

        build_solps_case(
            reference_directory=self.reference_directory,
            case_directory=case_dir,
            parameter_dictionary=parameters
        )

        # produce transport profiles defined by new point
        chi_params = [parameters[k] for k in conductivity_profile]
        chi_radius = profile_radius_axis(chi_params, self.transport_bounds)
        chi = linear_transport_profile(chi_radius, chi_params, self.transport_bounds)

        D_params = [parameters[k] for k in diffusivity_profile]
        D_radius = profile_radius_axis(D_params, self.transport_bounds)
        D = linear_transport_profile(D_radius, D_params, self.transport_bounds)

        write_solps_transport_inputfile(
            template=self.reference_directory / 'b2.transport.inputfile',
            filename=case_dir / 'b2.transport.inputfile',
            grid_dperp=D_radius,
            values_dperp=D,
            grid_chieperp=chi_radius,
            values_chieperp=chi,
            grid_chiiperp=chi_radius,
            values_chiiperp=chi,
        )

        setup_eirene_links(case_dir)

        job_id, submit_time = submit_job(case_dir, self.submit_command)

        write_run_info(
            case_dir,
            {
                # int() as the engine's numbers can be numpy ints, which json rejects
                "run_number": int(run_number),
                "iteration": int(iteration),
                "parameters": {k: float(v) for k, v in parameters.items()},
                "jobs": [{"job_id": job_id, "submit_time": timestamp(submit_time)}],
            },
        )

        logging.info(f'[solps_interface] Submitted job {job_id}')
        return SolpsRun(
            run_id=job_id,
            directory=case_dir,
            run_number=run_number,
            iteration=iteration,
            parameters=parameters,
            launch_time=submit_time,
            convergence_settings=self.convergence_settings,
            submit_command=self.submit_command,
            max_continuations=self.max_continuations,
        )

    def existing_run_numbers(self, simulations_directory: Path, **kwargs) -> set[int]:
        """The N of every run_N/ folder in the simulations directory."""
        return {
            int(match.group(1))
            for path in Path(simulations_directory).resolve().iterdir()
            if path.is_dir() and (match := re.fullmatch(r"run_(\d+)", path.name))
        }

    def adopt(
        self, run_number: int, simulations_directory: Path, **kwargs
    ) -> SolpsRun | None:
        """
        Rebuilds a run left in flight by an earlier driver from its
        run_N/run_info.json: run number, iteration, parameters, and the last
        job in "jobs", whose Slurm state the run then follows with status()
        as usual. Returns None if there is no run_info.json: the run was never
        submitted (e.g. stopped by the EIRENE-links check). A broken
        run_info.json raises.
        """
        case_dir = Path(simulations_directory).resolve() / f"run_{run_number}"
        if not isfile(case_dir / "run_info.json"):
            logging.info(
                f"[solps_interface] run {run_number}: no run_info.json, so it "
                f"was never submitted; not adopted"
            )
            return None
        info = read_run_info(case_dir)
        jobs = info["jobs"]
        last_job = jobs[-1]
        run = SolpsRun(
            run_id=last_job["job_id"],
            directory=case_dir,
            run_number=run_number,
            iteration=info["iteration"],
            parameters=info["parameters"],
            launch_time=datetime.fromisoformat(jobs[0]["submit_time"]).timestamp(),
            convergence_settings=self.convergence_settings,
            submit_command=self.submit_command,
            max_continuations=self.max_continuations,
        )
        # the job's state as last recorded, so the first poll logs only a real
        # change, and the needs-attention times count from the right moment
        if "started" in last_job and "ended" not in last_job:
            run.job_state = "RUNNING"
            run.job_state_since = datetime.fromisoformat(last_job["started"]).timestamp()
        else:
            run.job_state = "PENDING"
            run.job_state_since = datetime.fromisoformat(last_job["submit_time"]).timestamp()
        run.log(
            f"adopted: job {run.run_id} ({len(jobs)} job(s) so far), "
            f"last seen {run.job_state}"
        )
        return run


def submit_job(run_directory: Path, command: str) -> tuple[str, float]:
    """Submits the run in run_directory; returns the job ID and submit time."""
    # SOLPS has to start inside the run directory (it finds ../baserun from
    # there), but the driver itself never changes directory.
    start_run = subprocess.run(command, stdout=subprocess.PIPE, shell=True, cwd=run_directory)

    start_run_output = start_run.stdout
    # Find the batch job number
    findstr = 'Submitted batch job'
    tmp = str(start_run_output).find(findstr)
    job_id = str(start_run_output)[tmp + len(findstr) + 1:-3]
    return job_id, time()


def build_solps_case(
    reference_directory: Path,
    case_directory: Path,
    parameter_dictionary: dict
):
    # No fort.* files: setup_baserun_eirene_links makes fort.1 (a link to
    # input.dat), and EIRENE starts fresh, as in a run folder set up by hand.
    input_files = [
        "input.dat",
        "b2.neutrals.parameters",
        "b2.boundary.parameters",
        "b2.numerics.parameters",
        "b2.transport.parameters",
        "b2.user.parameters",
        "b2mn.dat"
    ]

    # create the case directory and copy all the reference files
    case_directory.mkdir()
    sh.copy(reference_directory / "b2fstate", case_directory / "b2fstati")
    for input in input_files:
        if isfile(reference_directory / input):
            sh.copy(reference_directory / input, case_directory / input)

    optional_params = {k for k in parameter_dictionary.keys()} - required_parameters
    written_params = set()

    mesa_input_files = [f + ".mesa" for f in input_files]
    mesa_input_files = [f for f in mesa_input_files if isfile(reference_directory / f)]

    if len(optional_params) != 0:
        if len(mesa_input_files) == 0:
            raise FileNotFoundError(
                f"""\n
                \r[ MESA ERROR ]
                \r>> The following optional parameters were specified
                \r>> {optional_params}
                \r>> However no input files with a .mesa extension were
                \r>> found in the reference directory.
                """
            )

        for mif in mesa_input_files:
            output = []
            with open(reference_directory / mif) as f:
                for line in f:
                    for p in optional_params:
                        if '{'+p+'}' in line:
                            val_string = parameter_dictionary[p]  # TODO - CONVERT TO STRING WITH FORMATTING
                            line.replace('{'+p+'}', val_string)
                            written_params.add(p)
                    output.append(line)

            with open(case_directory / mif, 'w') as f:  # TODO - does this overwrite?
                for item in output:
                    f.write("%s\n" % item)

        unwritten_params = optional_params - written_params
        if len(unwritten_params) > 0:
            raise ValueError(
                f"""\n
                \r[ MESA ERROR ]
                \r>> The following optional parameters were specified
                \r>> {unwritten_params}
                \r>> but were not found in any input files with a .mesa extension.
                """
            )


def timestamp(t: float) -> str:
    """Local time with its UTC offset, e.g. 2026-11-01T16:30:00+00:00."""
    return datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


def duration(seconds: float) -> str:
    """e.g. "1 h 40 min", "25 min"."""
    minutes = int(seconds // 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if hours else f"{minutes} min"


def write_run_info(run_directory: Path, info: dict):
    """
    Writes run_directory/run_info.json: the run number, iteration, parameters
    and "jobs", one entry per submitted job (job ID, submit time). It is
    written to a tmp file first and renamed, so it is never left half-written.
    """
    tmp_file = run_directory / "run_info.json.tmp"
    with open(tmp_file, "w") as f:
        json.dump(info, f, indent=2)
        f.write("\n")
    os.replace(tmp_file, run_directory / "run_info.json")


def read_run_info(run_directory: Path) -> dict:
    with open(run_directory / "run_info.json") as f:
        return json.load(f)


def setup_eirene_links(run_directory: Path):
    """
    Runs setup_baserun_eirene_links in the run directory, which makes fort.1
    (a link to input.dat) and the EIRENE data links a fresh run folder needs,
    then checks that fort.1 is there. Without it EIRENE fails at start-up, so
    an error is raised instead of launching the run.
    """
    try:
        result = subprocess.run(
            ["setup_baserun_eirene_links"],
            cwd=run_directory,
            capture_output=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        raise RuntimeError(
            f"setup_baserun_eirene_links not found on PATH, so {run_directory} "
            f"can't be set up; run the driver in a shell with SOLPS-ITER's "
            f"setup.csh sourced"
        )

    fort1 = run_directory / "fort.1"
    if not isfile(fort1) or fort1.stat().st_size == 0:
        raise RuntimeError(
            f"setup_baserun_eirene_links did not make a non-empty fort.1 in "
            f"{run_directory}, so the run was not launched "
            f"(exit code {result.returncode}):\n{result.stdout}{result.stderr}"
        )


def check_tools():
    """Raises an error listing the outside tools that are not on PATH."""
    missing = [tool for tool in required_tools if sh.which(tool) is None]
    if missing:
        raise RuntimeError(
            f"not found on PATH: {', '.join(missing)}; run the driver in a shell "
            f"with SOLPS-ITER's setup.csh sourced, on a machine with Slurm"
        )


def find_time_file(run_directory: Path) -> Path | None:
    """The run's b2time.nc, or None if there is none yet."""
    # A fresh run writes b2time.nc in b2mn.exe.dir while it runs; a restarted
    # run appends to the one in the run directory.
    for time_file in (run_directory / "b2mn.exe.dir" / "b2time.nc", run_directory / "b2time.nc"):
        if isfile(time_file):
            return time_file
    return None


def check_convergence(
    run_directory: Path, minimum_run_time: float, window: float, timescale: float
) -> bool | None:
    """
    The run is converged if it has run for at least minimum_run_time (s of
    simulated time) and, over the last window (s), every monitored ne and Te
    changes on a timescale longer than timescale (s).

    Returns None if it can't be judged: b2time.nc is missing or can't be
    read. While the job runs that is normal (not converged yet); once the
    job has ended it means the run failed.
    """
    time_file = find_time_file(run_directory)
    if time_file is None:
        return None

    try:
        with netcdf.netcdf_file(time_file, "r") as solps:
            ne = solps.variables["ne3da"].data.copy()
            te = solps.variables["te3da"].data.copy() / 1.602e-19
            time = solps.variables["timesa"].data.copy()
    except Exception as error:
        # e.g. the file is read while SOLPS is writing it; try again next poll
        logging.info(f"[solps_interface] could not read {time_file}: {error!r}")
        return None

    run_time = time.max() - time.min()
    if run_time < minimum_run_time:
        return False

    index = searchsorted(time, time.max() - window)
    log_te = log(te)[index:]
    log_ne = log(ne)[index:]
    fit_time = time[index:]

    te_gradients = polyfit(x=fit_time, y=log_te, deg=1)[0, :]
    te_timescales = 1 / abs(te_gradients)

    ne_gradients = polyfit(x=fit_time, y=log_ne, deg=1)[0, :]
    ne_timescales = 1 / abs(ne_gradients)


    converged = (te_timescales > timescale).all() and (ne_timescales > timescale).all()
    return bool(converged)