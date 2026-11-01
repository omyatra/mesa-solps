from pathlib import Path
import re
from numpy import ndarray


# transport coefficient kinds (the k in ndata(1,k,1) / tdata(.,.,k,1)) set by MESA
fitted_kinds = (1, 3, 4)

# one ndata / tdata assignment for species 1, e.g. "ndata(1, 3 , 1 )= 12 ," or
# "tdata(2, 5 , 3 , 1 )= 0.25 ,", with the kind as group 1
_profile_assignment = re.compile(
    r"(?:ndata\(\s*1\s*,|tdata\(\s*[12]\s*,\s*\d+\s*,)\s*(\d+)\s*,\s*1\s*\)\s*=\s*[^,\s]+\s*,?",
    re.IGNORECASE,
)


def _fitted_kind(line: str) -> int | None:
    """
    Returns the fitted kind if the line holds profile data for one, else None.
    Raises a ValueError if the line also holds anything else, since that
    would be lost when the profile is replaced.
    """
    code = line.split("!", 1)[0]  # ignore Fortran comments
    kinds = {int(k) for k in _profile_assignment.findall(code)} & set(fitted_kinds)
    if not kinds:
        return None
    rest = _profile_assignment.sub("", code).strip()
    if len(kinds) > 1 or rest:
        raise ValueError(
            f"b2.transport.inputfile line mixes fitted profile data with other "
            f"settings, which MESA can't replace safely:\n{line.rstrip()}"
        )
    return kinds.pop()


def check_transport_template(template: Path):
    """
    Checks that the reference b2.transport.inputfile has a profile block for
    every kind MESA fits, and raises an error if not.
    """
    if not template.is_file():
        raise FileNotFoundError(
            f"reference inputfile {template} not found; MESA takes every "
            f"setting except the fitted profiles from it"
        )
    with open(template) as f:
        found = {_fitted_kind(line) for line in f} - {None}
    for kind in fitted_kinds:
        if kind not in found:
            raise ValueError(
                f"reference inputfile {template} has no profile for kind "
                f"{kind}; add one to the reference case"
            )


def write_solps_transport_inputfile(
        template: Path,
        filename: Path,
        grid_dperp: ndarray,
        values_dperp: ndarray,
        grid_chieperp: ndarray,
        values_chieperp: ndarray,
        grid_chiiperp: ndarray,
        values_chiiperp: ndarray,
):
    """
    Writes a b2.transport.inputfile to prepare a SOLPS-ITER run, using the
    reference case's b2.transport.inputfile as a template: the profile blocks
    MESA fits (kinds 1, 3 and 4) are replaced, every other line is kept as is.
    Inputs:
        - template: the reference case's b2.transport.inputfile
        - filename: name of file to output
        - grid_dperp: grid where profile of anomalous radial particle diffusion is specified.
        - values_dperp: profile of anomalous radial particle diffusion
        - grid_chieperp: grid where profile of anomalous radial electron heat diffusion is specified.
        - values_chieperp: profile of anomalous radial electron heat diffusion.
        - grid_chiiperp: grid where profile of anomalous radial ion heat diffusion is specified.
        - values_chiiperp: profile of anomalous raidal ion heat diffusion
    """
    check_transport_template(template)

    def build_profile(grid, values, code):
        strings = [f' ndata(1, {code} , 1 )= {len(grid)} ,']
        for i, (x, y) in enumerate(zip(grid, values)):
            line = f' tdata(1,{i + 1:2.0f} , {code} , 1 )= {x:6.6f} , tdata(2,{i + 1:2.0f} , {code} , 1 )= {y:6.6f} ,'
            strings.append(line)
        return strings

    profiles = {
        1: build_profile(grid_dperp, values_dperp, code=1),  # anomalous radial particle diffusivity
        3: build_profile(grid_chieperp, values_chieperp, code=3),  # anomalous radial electron heat diffusivity
        4: build_profile(grid_chiiperp, values_chiiperp, code=4),  # anomalous radial ion heat diffusivity
    }

    # the new profile goes where the reference's block for that kind starts;
    # the reference's own lines for it are dropped
    sout = []
    written = set()
    with open(template) as f:
        for line in f:
            kind = _fitted_kind(line)
            if kind is None:
                sout.append(line.rstrip("\n"))
            elif kind not in written:
                sout.extend(profiles[kind])
                written.add(kind)

    # Write the list to a file
    with open(filename, 'w') as f:
        for item in sout:
            f.write("%s\n" % item)
