"""Implements various validators, e.g., check if vasprun.xml is valid, for VASP."""

import logging
import os
from collections import deque

from pymatgen.io.vasp import Chgcar, Incar

from custodian.custodian import Validator
from custodian.vasp.io import load_outcar, load_vasprun


class VasprunXMLValidator(Validator):
    """Checks that a valid vasprun.xml was generated."""

    def __init__(self, output_file: str = "vasp.out", stderr_file: str = "std_err.txt") -> None:
        """
        Args:
            output_file (str): Name of file VASP standard output is directed to.
                Defaults to "vasp.out".
            stderr_file (str): Name of file VASP standard error is direct to.
                Defaults to "std_err.txt".
        """
        self.output_file = output_file
        self.stderr_file = stderr_file
        self.logger = logging.getLogger(type(self).__name__)

    def check(self, directory="./"):
        """Check for errors."""
        try:
            load_vasprun(os.path.join(directory, "vasprun.xml"))
        except Exception:
            exception_context = {}

            if os.path.isfile(os.path.join(directory, self.output_file)):
                with open(os.path.join(directory, self.output_file)) as output_file:
                    output_file_tail = deque(output_file, maxlen=10)
                exception_context["output_file_tail"] = "".join(output_file_tail)

            if os.path.isfile(os.path.join(directory, self.stderr_file)):
                with open(os.path.join(directory, self.stderr_file)) as stderr_file:
                    stderr_file_tail = deque(stderr_file, maxlen=10)
                exception_context["stderr_file_tail"] = "".join(stderr_file_tail)

            if os.path.isfile(os.path.join(directory, "vasprun.xml")):
                stat = os.stat(os.path.join(directory, "vasprun.xml"))
                exception_context["vasprun_st_size"] = stat.st_size
                exception_context["vasprun_st_atime"] = stat.st_atime
                exception_context["vasprun_st_mtime"] = stat.st_mtime
                exception_context["vasprun_st_ctime"] = stat.st_ctime

                with open(os.path.join(directory, "vasprun.xml")) as vasprun:
                    vasprun_tail = deque(vasprun, maxlen=10)
                exception_context["vasprun_tail"] = "".join(vasprun_tail)

            self.logger.exception("Failed to load vasprun.xml", extra=exception_context)

            return True
        return False


class VaspFilesValidator(Validator):
    """
    Check for existence of some of the files that VASP
        normally create upon running.
    """

    def __init__(self):
        """Dummy init."""

    def check(self, directory="./"):
        """Check for error."""
        return any(not os.path.isfile(os.path.join(directory, vfile)) for vfile in ("CONTCAR", "OSZICAR", "OUTCAR"))


class VaspNpTMDValidator(Validator):
    """
    Check NpT-AIMD settings is loaded by VASP compiled with -Dtbdyn.
    Currently, VASP only have Langevin thermostat (MDALGO = 3) for NpT ensemble.
    """

    def __init__(self):
        """Dummy init."""

    def check(self, directory="./"):
        """Check for error."""
        incar = Incar.from_file(os.path.join(directory, "INCAR"))
        is_npt = incar.get("MDALGO") == 3
        if not is_npt:
            return False

        outcar = load_outcar(os.path.join(directory, "OUTCAR"))
        patterns = {"MDALGO": r"MDALGO\s+=\s+([\d]+)"}
        outcar.read_pattern(patterns=patterns)
        if outcar.data["MDALGO"] == [["3"]]:
            return False
        return True


class VaspAECCARValidator(Validator):
    """Check if the data in the AECCAR is corrupted."""

    def __init__(self):
        """Dummy init."""

    def check(self, directory="./"):
        """Check for error."""
        aeccar0 = Chgcar.from_file(os.path.join(directory, "AECCAR0"))
        aeccar2 = Chgcar.from_file(os.path.join(directory, "AECCAR2"))
        aeccar = aeccar0 + aeccar2
        return check_broken_chgcar(aeccar)


def check_broken_chgcar(chgcar, diff_thresh=None):
    """
    Check if the charge density file is corrupt
    Args:
        chgcar (Chgcar): Chgcar-like object.
        diff_thresh (Float): Threshold for diagonal difference.
            None means we won't check for this.
    """
    chgcar_data = chgcar.data["total"]
    if (chgcar_data < 0).sum() > 100:
        # a decent bunch of the values are negative this for sure means a broken charge density
        return True

    if diff_thresh:
        """
        If any one diagonal difference accounts for more than a particular portion of
        the total difference between highest and lowest density.
        When we are looking at AECCAR data, since the charge density is so high near the core
        and we have a course grid, this threshold can be as high as 0.99
        """
        diff = chgcar_data[:-1, :-1, :-1] - chgcar_data[1:, 1:, 1:]
        if diff.max() / (chgcar_data.max() - chgcar_data.min()) > diff_thresh:
            return True

    return False
