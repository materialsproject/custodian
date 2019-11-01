# coding: utf-8

from __future__ import unicode_literals, division

from monty.os.path import zpath
import os
import time
import datetime
import operator
import shutil
import logging
from functools import reduce
from collections import Counter
import re

import numpy as np

from monty.dev import deprecated
from monty.serialization import loadfn

from custodian.custodian import ErrorHandler
from custodian.utils import backup
from pymatgen.io.vasp.inputs import Poscar, VaspInput, Incar, Kpoints
from pymatgen.io.vasp.outputs import Vasprun, Oszicar, Outcar
from pymatgen.transformations.standard_transformations import \
    SupercellTransformation

from custodian.ansible.interpreter import Modder
from custodian.ansible.actions import FileActions
from custodian.vasp.interpreter import VaspModder

"""
This module implements specific error handlers for VASP runs. These handlers
tries to detect common errors in vasp runs and attempt to fix them on the fly
by modifying the input files.
"""

__author__ = "Shyue Ping Ong, William Davidson Richards, Anubhav Jain, " \
             "Wei Chen, Stephen Dacek"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "ongsp@ucsd.edu"
__status__ = "Beta"
__date__ = "2/4/13"

VASP_BACKUP_FILES = {"INCAR", "KPOINTS", "POSCAR", "OUTCAR", "CONTCAR",
                     "OSZICAR", "vasprun.xml", "vasp.out", "std_err.txt"}


class VaspErrorHandler(ErrorHandler):
    """
    Master VaspErrorHandler class that handles a number of common errors
    that occur during VASP runs.
    """

    is_monitor = True

    error_msgs = {
        "tet": ["Tetrahedron method fails for NKPT<4",
                "Fatal error detecting k-mesh",
                "Fatal error: unable to match k-point",
                "Routine TETIRR needs special values",
                "Tetrahedron method fails (number of k-points < 4)"],
        "inv_rot_mat": ["inverse of rotation matrix was not found (increase "
                        "SYMPREC)"],
        "brmix": ["BRMIX: very serious problems"],
        "subspacematrix": ["WARNING: Sub-Space-Matrix is not hermitian in "
                           "DAV"],
        "tetirr": ["Routine TETIRR needs special values"],
        "incorrect_shift": ["Could not get correct shifts"],
        "real_optlay": ["REAL_OPTLAY: internal error",
                        "REAL_OPT: internal ERROR"],
        "rspher": ["ERROR RSPHER"],
        "dentet": ["DENTET"],
        "too_few_bands": ["TOO FEW BANDS"],
        "triple_product": ["ERROR: the triple product of the basis vectors"],
        "rot_matrix": ["Found some non-integer element in rotation matrix"],
        "brions": ["BRIONS problems: POTIM should be increased"],
        "pricel": ["internal error in subroutine PRICEL"],
        "zpotrf": ["LAPACK: Routine ZPOTRF failed"],
        "amin": ["One of the lattice vectors is very long (>50 A), but AMIN"],
        "zbrent": ["ZBRENT: fatal internal in",
                   "ZBRENT: fatal error in bracketing"],
        "pssyevx": ["ERROR in subspace rotation PSSYEVX"],
        "eddrmm": ["WARNING in EDDRMM: call to ZHEGV failed"],
        "edddav": ["Error EDDDAV: Call to ZHEGV failed"],
        "grad_not_orth": [
            "EDWAV: internal error, the gradient is not orthogonal"],
        "nicht_konv": ["ERROR: SBESSELITER : nicht konvergent"],
        "zheev": ["ERROR EDDIAG: Call to routine ZHEEV failed!"],
        "elf_kpar": ["ELF: KPAR>1 not implemented"],
        "elf_ncl": ["WARNING: ELF not implemented for non collinear case"],
        "rhosyg": ["RHOSYG internal error"],
        "posmap": ["POSMAP internal error: symmetry equivalent atom not found"],
        "point_group": ["Error: point group operation missing"]
    }

    def __init__(self, output_filename="vasp.out", natoms_large_cell=100,
                 errors_subset_to_catch=None):
        """
        Initializes the handler with the output file to check.

        Args:
            output_filename (str): This is the file where the stdout for vasp
                is being redirected. The error messages that are checked are
                present in the stdout. Defaults to "vasp.out", which is the
                default redirect used by :class:`custodian.vasp.jobs.VaspJob`.
            natoms_large_cell (int): Number of atoms threshold to treat cell
                as large. Affects the correction of certain errors. Defaults to
                100.
            errors_subset_to_detect (list): A subset of errors to catch. The
                default is None, which means all supported errors are detected.
                Use this to only catch only a subset of supported errors.
                E.g., ["eddrrm", "zheev"] will only catch the eddrmm and zheev
                errors, and not others. If you wish to only excluded one or
                two of the errors, you can create this list by the following
                lines:

                ```
                subset = list(VaspErrorHandler.error_msgs.keys())
                subset.pop("eddrrm")

                handler = VaspErrorHandler(errors_subset_to_catch=subset)
                ```
        """
        self.output_filename = output_filename
        self.errors = set()
        self.error_count = Counter()
        # threshold of number of atoms to treat the cell as large.
        self.natoms_large_cell = natoms_large_cell
        self.errors_subset_to_catch = errors_subset_to_catch or list(VaspErrorHandler.error_msgs.keys())
        self.logger = logging.getLogger(self.__class__.__name__)

    def check(self):
        incar = Incar.from_file("INCAR")
        self.errors = set()
        error_msgs = set()
        with open(self.output_filename, "r") as f:
            for line in f:
                l = line.strip()
                for err, msgs in VaspErrorHandler.error_msgs.items():
                    if err in self.errors_subset_to_catch:
                        for msg in msgs:
                            if l.find(msg) != -1:
                                # this checks if we want to run a charged
                                # computation (e.g., defects) if yes we don't
                                # want to kill it because there is a change in
                                # e-density (brmix error)
                                if err == "brmix" and 'NELECT' in incar:
                                    continue
                                self.errors.add(err)
                                error_msgs.add(msg)
        for msg in error_msgs:
            self.logger.error(msg, extra={"incar": incar.as_dict()})
        return len(self.errors) > 0

    def correct(self):
        backup(VASP_BACKUP_FILES | {self.output_filename})
        actions = []
        vi = VaspInput.from_directory(".")

        if self.errors.intersection(["tet", "dentet"]):
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ISMEAR": 0, "SIGMA": 0.05}}})

        if "inv_rot_mat" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"SYMPREC": 1e-8}}})

        if "brmix" in self.errors:
            # If there is not a valid OUTCAR already, increment
            # error count to 1 to skip first fix
            if self.error_count['brmix'] == 0:
                try:
                    assert (Outcar(zpath(os.path.join(
                        os.getcwd(), "OUTCAR"))).is_stopped is False)
                except Exception:
                    self.error_count['brmix'] += 1

            if self.error_count['brmix'] == 0:
                # Valid OUTCAR - simply rerun the job and increment
                # error count for next time
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"ISTART": 1}}})
                self.error_count['brmix'] += 1

            elif self.error_count['brmix'] == 1:
                # Use Kerker mixing w/default values for other parameters
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"IMIX": 1}}})
                self.error_count['brmix'] += 1

            elif self.error_count['brmix'] == 2 and vi["KPOINTS"].style \
                    == Kpoints.supported_modes.Gamma:
                actions.append({"dict": "KPOINTS",
                                "action": {"_set": {"generation_style": "Monkhorst"}}})
                actions.append({"dict": "INCAR",
                                "action": {"_unset": {"IMIX": 1}}})
                self.error_count['brmix'] += 1

            elif self.error_count['brmix'] in [2, 3] and vi["KPOINTS"].style == Kpoints.supported_modes.Monkhorst:
                actions.append({"dict": "KPOINTS",
                                "action": {"_set": {"generation_style": "Gamma"}}})
                actions.append({"dict": "INCAR",
                                "action": {"_unset": {"IMIX": 1}}})
                self.error_count['brmix'] += 1

                if vi["KPOINTS"].num_kpts < 1:
                    all_kpts_even = all([
                        bool(n % 2 == 0) for n in vi["KPOINTS"].kpts[0]
                    ])
                    if all_kpts_even:
                        new_kpts = (
                            tuple(n + 1 for n in vi["KPOINTS"].kpts[0]),)
                        actions.append({"dict": "KPOINTS", "action": {"_set": {
                            "kpoints": new_kpts
                        }}})

            else:
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"ISYM": 0}}})

                if vi["KPOINTS"].style == Kpoints.supported_modes.Monkhorst:
                    actions.append({"dict": "KPOINTS",
                                    "action": {
                                        "_set": {"generation_style": "Gamma"}}})

                # Based on VASP forum's recommendation, you should delete the
                # CHGCAR and WAVECAR when dealing with this error.
                if vi["INCAR"].get("ICHARG", 0) < 10:
                    actions.append({"file": "CHGCAR",
                                    "action": {
                                        "_file_delete": {'mode': "actual"}}})
                    actions.append({"file": "WAVECAR",
                                    "action": {
                                        "_file_delete": {'mode': "actual"}}})

        if "zpotrf" in self.errors:
            # Usually caused by short bond distances. If on the first step,
            # volume needs to be increased. Otherwise, it was due to a step
            # being too big and POTIM should be decreased.  If a static run
            # try turning off symmetry.
            try:
                oszicar = Oszicar("OSZICAR")
                nsteps = len(oszicar.ionic_steps)
            except Exception:
                nsteps = 0

            if nsteps >= 1:
                potim = float(vi["INCAR"].get("POTIM", 0.5)) / 2.0
                actions.append(
                    {"dict": "INCAR",
                     "action": {"_set": {"ISYM": 0, "POTIM": potim}}})
            elif vi["INCAR"].get("NSW", 0) == 0 \
                    or vi["INCAR"].get("ISIF", 0) in range(3):
                actions.append(
                    {"dict": "INCAR", "action": {"_set": {"ISYM": 0}}})
            else:
                s = vi["POSCAR"].structure
                s.apply_strain(0.2)
                actions.append({"dict": "POSCAR",
                                "action": {"_set": {"structure": s.as_dict()}}})

            # Based on VASP forum's recommendation, you should delete the
            # CHGCAR and WAVECAR when dealing with this error.
            if vi["INCAR"].get("ICHARG", 0) < 10:
                actions.append({"file": "CHGCAR",
                                "action": {"_file_delete": {'mode': "actual"}}})
                actions.append({"file": "WAVECAR",
                                "action": {"_file_delete": {'mode': "actual"}}})

        if self.errors.intersection(["subspacematrix"]):
            if self.error_count["subspacematrix"] == 0:
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"LREAL": False}}})
            else:
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"PREC": "Accurate"}}})
            self.error_count["subspacematrix"] += 1

        if self.errors.intersection(["rspher", "real_optlay", "nicht_konv"]):
            s = vi["POSCAR"].structure
            if len(s) < self.natoms_large_cell:
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"LREAL": False}}})
            else:
                # for large supercell, try an in-between option LREAL = True
                # prior to LREAL = False
                if self.error_count['real_optlay'] == 0:
                    # use real space projectors generated by pot
                    actions.append({"dict": "INCAR",
                                    "action": {"_set": {"LREAL": True}}})
                elif self.error_count['real_optlay'] == 1:
                    actions.append({"dict": "INCAR",
                                    "action": {"_set": {"LREAL": False}}})
                self.error_count['real_optlay'] += 1

        if self.errors.intersection(["tetirr", "incorrect_shift"]):

            if vi["KPOINTS"].style == Kpoints.supported_modes.Monkhorst:
                actions.append({"dict": "KPOINTS",
                                "action": {
                                    "_set": {"generation_style": "Gamma"}}})

        if "rot_matrix" in self.errors:
            if vi["KPOINTS"].style == Kpoints.supported_modes.Monkhorst:
                actions.append({"dict": "KPOINTS",
                                "action": {
                                    "_set": {"generation_style": "Gamma"}}})
            else:
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"ISYM": 0}}})

        if "amin" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"AMIN": "0.01"}}})

        if "triple_product" in self.errors:
            s = vi["POSCAR"].structure
            trans = SupercellTransformation(((1, 0, 0), (0, 0, 1), (0, 1, 0)))
            new_s = trans.apply_transformation(s)
            actions.append({"dict": "POSCAR",
                            "action": {"_set": {"structure": new_s.as_dict()}},
                            "transformation": trans.as_dict()})

        if "pricel" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"SYMPREC": 1e-8, "ISYM": 0}}})

        if "brions" in self.errors:
            potim = float(vi["INCAR"].get("POTIM", 0.5)) + 0.1
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"POTIM": potim}}})

        if "zbrent" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"IBRION": 1}}})
            actions.append({"file": "CONTCAR",
                            "action": {"_file_copy": {"dest": "POSCAR"}}})

        if "too_few_bands" in self.errors:
            if "NBANDS" in vi["INCAR"]:
                nbands = int(vi["INCAR"]["NBANDS"])
            else:
                with open("OUTCAR") as f:
                    for line in f:
                        if "NBANDS" in line:
                            try:
                                d = line.split("=")
                                nbands = int(d[-1].strip())
                                break
                            except (IndexError, ValueError):
                                pass
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"NBANDS": int(1.1 * nbands)}}})

        if "pssyevx" in self.errors:
            actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Normal"}}})
        if "eddrmm" in self.errors:
            # RMM algorithm is not stable for this calculation
            if vi["INCAR"].get("ALGO", "Normal") in ["Fast", "VeryFast"]:
                actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Normal"}}})
            else:
                potim = float(vi["INCAR"].get("POTIM", 0.5)) / 2.0
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"POTIM": potim}}})
            if vi["INCAR"].get("ICHARG", 0) < 10:
                actions.append({"file": "CHGCAR",
                                "action": {"_file_delete": {'mode': "actual"}}})
                actions.append({"file": "WAVECAR",
                                "action": {"_file_delete": {'mode': "actual"}}})

        if "edddav" in self.errors:
            if vi["INCAR"].get("ICHARG", 0) < 10:
                actions.append({"file": "CHGCAR",
                                "action": {"_file_delete": {'mode': "actual"}}})
            actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "All"}}})

        if "grad_not_orth" in self.errors:
            if vi["INCAR"].get("ISMEAR", 1) < 0:
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"ISMEAR": 0, "SIGMA": 0.05}}})

        if "zheev" in self.errors:
            if vi["INCAR"].get("ALGO", "Fast").lower() != "exact":
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"ALGO": "Exact"}}})
        if "elf_kpar" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"KPAR": 1}}})

        if "rhosyg" in self.errors:
            if vi["INCAR"].get("SYMPREC", 1e-4) == 1e-4:
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"ISYM": 0}}})
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"SYMPREC": 1e-4}}})

        if "posmap" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"SYMPREC": 1e-6}}})

        if "point_group" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ISYM": 0}}})

        VaspModder(vi=vi).apply_actions(actions)
        return {"errors": list(self.errors), "actions": actions}


class LrfCommutatorHandler(ErrorHandler):
    """
    Corrects LRF_COMMUTATOR errors by setting LPEAD=True if not already set.
    Note that switching LPEAD=T can slightly change results versus the
    default due to numerical evaluation of derivatives.
    """

    is_monitor = True

    error_msgs = {
        "lrf_comm": ["LRF_COMMUTATOR internal error"],
    }

    def __init__(self, output_filename="std_err.txt"):
        """
        Initializes the handler with the output file to check.

        Args:
            output_filename (str): This is the file where the stderr for vasp
                is being redirected. The error messages that are checked are
                present in the stderr. Defaults to "std_err.txt", which is the
                default redirect used by :class:`custodian.vasp.jobs.VaspJob`.
        """
        self.output_filename = output_filename
        self.errors = set()
        self.error_count = Counter()

    def check(self):
        self.errors = set()
        with open(self.output_filename, "r") as f:
            for line in f:
                l = line.strip()
                for err, msgs in LrfCommutatorHandler.error_msgs.items():
                    for msg in msgs:
                        if l.find(msg) != -1:
                            self.errors.add(err)
        return len(self.errors) > 0

    def correct(self):
        backup(VASP_BACKUP_FILES | {self.output_filename})
        actions = []
        vi = VaspInput.from_directory(".")

        if "lrf_comm" in self.errors:
            if Outcar(zpath(os.path.join(
                    os.getcwd(), "OUTCAR"))).is_stopped is False:
                if not vi["INCAR"].get("LPEAD"):
                    actions.append({"dict": "INCAR",
                                    "action": {"_set": {"LPEAD": True}}})

        VaspModder(vi=vi).apply_actions(actions)
        return {"errors": list(self.errors), "actions": actions}


class StdErrHandler(ErrorHandler):
    """
    Master StdErr class that handles a number of common errors
    that occur during VASP runs with error messages only in
    the standard error.
    """

    is_monitor = True

    error_msgs = {
        "kpoints_trans": ["internal error in GENERATE_KPOINTS_TRANS: "
                          "number of G-vector changed in star"],
        "out_of_memory": ["Allocation would exceed memory limit"]
    }

    def __init__(self, output_filename="std_err.txt"):
        """
        Initializes the handler with the output file to check.

        Args:
            output_filename (str): This is the file where the stderr for vasp
                is being redirected. The error messages that are checked are
                present in the stderr. Defaults to "std_err.txt", which is the
                default redirect used by :class:`custodian.vasp.jobs.VaspJob`.
        """
        self.output_filename = output_filename
        self.errors = set()
        self.error_count = Counter()

    def check(self):
        self.errors = set()
        with open(self.output_filename, "r") as f:
            for line in f:
                l = line.strip()
                for err, msgs in StdErrHandler.error_msgs.items():
                    for msg in msgs:
                        if l.find(msg) != -1:
                            self.errors.add(err)
        return len(self.errors) > 0

    def correct(self):
        backup(VASP_BACKUP_FILES | {self.output_filename})
        actions = []
        vi = VaspInput.from_directory(".")

        if "kpoints_trans" in self.errors:
            if self.error_count["kpoints_trans"] == 0:
                m = reduce(operator.mul, vi["KPOINTS"].kpts[0])
                m = max(int(round(m ** (1 / 3))), 1)
                if vi["KPOINTS"].style.name.lower().startswith("m"):
                    m += m % 2
                actions.append({"dict": "KPOINTS",
                                "action": {"_set": {"kpoints": [[m] * 3]}}})
                self.error_count['kpoints_trans'] += 1

        if "out_of_memory" in self.errors:
            if vi["INCAR"].get("KPAR", 1) > 1:
                reduced_kpar = max(vi["INCAR"].get("KPAR", 1) // 2, 1)
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"KPAR": reduced_kpar}}})

        VaspModder(vi=vi).apply_actions(actions)
        return {"errors": list(self.errors), "actions": actions}


class AliasingErrorHandler(ErrorHandler):
    """
    Master VaspErrorHandler class that handles a number of common errors
    that occur during VASP runs.
    """

    is_monitor = True

    error_msgs = {
        "aliasing": [
            "WARNING: small aliasing (wrap around) errors must be expected"],
        "aliasing_incar": ["Your FFT grids (NGX,NGY,NGZ) are not sufficient "
                           "for an accurate"]
    }

    def __init__(self, output_filename="vasp.out"):
        """
        Initializes the handler with the output file to check.

        Args:
            output_filename (str): This is the file where the stdout for vasp
                is being redirected. The error messages that are checked are
                present in the stdout. Defaults to "vasp.out", which is the
                default redirect used by :class:`custodian.vasp.jobs.VaspJob`.
        """
        self.output_filename = output_filename
        self.errors = set()

    def check(self):
        incar = Incar.from_file("INCAR")
        self.errors = set()
        with open(self.output_filename, "r") as f:
            for line in f:
                l = line.strip()
                for err, msgs in AliasingErrorHandler.error_msgs.items():
                    for msg in msgs:
                        if l.find(msg) != -1:
                            # this checks if we want to run a charged
                            # computation (e.g., defects) if yes we don't
                            # want to kill it because there is a change in e-
                            # density (brmix error)
                            if err == "brmix" and 'NELECT' in incar:
                                continue
                            self.errors.add(err)
        return len(self.errors) > 0

    def correct(self):
        backup(VASP_BACKUP_FILES | {self.output_filename})
        actions = []
        vi = VaspInput.from_directory(".")

        if "aliasing" in self.errors:
            with open("OUTCAR") as f:
                grid_adjusted = False
                changes_dict = {}
                r = re.compile(".+aliasing errors.*(NG.)\s*to\s*(\d+)")
                for line in f:
                    m = r.match(line)
                    if m:
                        changes_dict[m.group(1)] = int(m.group(2))
                        grid_adjusted = True
                    # Ensure that all NGX, NGY, NGZ have been checked
                    if grid_adjusted and 'NGZ' in line:
                        actions.append(
                            {"dict": "INCAR", "action": {"_set": changes_dict}})
                        if vi["INCAR"].get("ICHARG", 0) < 10:
                            actions.extend([{"file": "CHGCAR",
                                             "action": {"_file_delete": {
                                                 'mode': "actual"}}},
                                            {"file": "WAVECAR",
                                             "action": {"_file_delete": {
                                                 'mode': "actual"}}}])
                        break

        if "aliasing_incar" in self.errors:
            # vasp seems to give different warnings depending on whether the
            # aliasing error was caused by user supplied inputs
            d = {k: 1 for k in ['NGX', 'NGY', 'NGZ'] if k in vi['INCAR'].keys()}
            actions.append({"dict": "INCAR", "action": {"_unset": d}})

            if vi["INCAR"].get("ICHARG", 0) < 10:
                actions.extend([{"file": "CHGCAR",
                                 "action": {
                                     "_file_delete": {'mode': "actual"}}},
                                {"file": "WAVECAR",
                                 "action": {
                                     "_file_delete": {'mode': "actual"}}}])

        VaspModder(vi=vi).apply_actions(actions)
        return {"errors": list(self.errors), "actions": actions}


class DriftErrorHandler(ErrorHandler):
    """
    Corrects for total drift exceeding the force convergence criteria.
    """

    def __init__(self, max_drift=None, to_average=3, enaug_multiply=2):
        """
        Initializes the handler with max drift
        Args:
            max_drift (float): This defines the max drift. Leaving this at the default of None gets the max_drift from
                EDFIFFG
        """

        self.max_drift = max_drift
        self.to_average = int(to_average)
        self.enaug_multiply = enaug_multiply

    def check(self):

        incar = Incar.from_file("INCAR")
        if incar.get("EDIFFG", 0.1) >= 0 or incar.get("NSW", 0) == 0:
            # Only activate when force relaxing and ionic steps
            # NSW check prevents accidental effects when running DFPT
            return False

        if not self.max_drift:
            self.max_drift = incar["EDIFFG"] * -1

        try:
            outcar = Outcar("OUTCAR")
        except Exception:
            # Can't perform check if Outcar not valid
            return False

        if len(outcar.data.get('drift', [])) < self.to_average:
            # Ensure enough steps to get average drift
            return False
        else:
            curr_drift = outcar.data.get("drift", [])[::-1][:self.to_average]
            curr_drift = np.average([np.linalg.norm(d) for d in curr_drift])
            return curr_drift > self.max_drift

    def correct(self):
        backup(VASP_BACKUP_FILES)
        actions = []
        vi = VaspInput.from_directory(".")

        incar = vi["INCAR"]
        outcar = Outcar("OUTCAR")

        # Move CONTCAR to POSCAR
        actions.append({"file": "CONTCAR",
                        "action": {"_file_copy": {"dest": "POSCAR"}}})

        # First try adding ADDGRID
        if not incar.get("ADDGRID", False):
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ADDGRID": True}}})
        # Otherwise set PREC to High so ENAUG can be used to control Augmentation Grid Size
        elif incar.get("PREC", "Accurate").lower() != "high":
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"PREC": "High"}}})
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ENAUG": incar.get("ENCUT", 520) * 2}}})
        # PREC is already high and ENAUG set so just increase it
        else:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ENAUG": int(incar.get("ENAUG", 1040) * self.enaug_multiply)}}})

        curr_drift = outcar.data.get("drift", [])[::-1][:self.to_average]
        curr_drift = np.average([np.linalg.norm(d) for d in curr_drift])
        VaspModder(vi=vi).apply_actions(actions)
        return {"errors": "Excessive drift {} > {}".format(curr_drift, self.max_drift), "actions": actions}


class MeshSymmetryErrorHandler(ErrorHandler):
    """
    Corrects the mesh symmetry error in VASP. This error is sometimes
    non-fatal. So this error handler only checks at the end of the run,
    and if the run has converged, no error is recorded.
    """
    is_monitor = False

    def __init__(self, output_filename="vasp.out",
                 output_vasprun="vasprun.xml"):
        """
        Initializes the handler with the output files to check.

        Args:
            output_filename (str): This is the file where the stdout for vasp
                is being redirected. The error messages that are checked are
                present in the stdout. Defaults to "vasp.out", which is the
                default redirect used by :class:`custodian.vasp.jobs.VaspJob`.
            output_vasprun (str): Filename for the vasprun.xml file. Change
                this only if it is different from the default (unlikely).
        """
        self.output_filename = output_filename
        self.output_vasprun = output_vasprun

    def check(self):
        msg = "Reciprocal lattice and k-lattice belong to different class of" \
              " lattices."

        vi = VaspInput.from_directory('.')
        # According to VASP admins, you can disregard this error
        # if symmetry is off
        # Also disregard if automatic KPOINT generation is used
        if (not vi["INCAR"].get('ISYM', True)) or \
                vi[
                    "KPOINTS"].style == Kpoints.supported_modes.Automatic:
            return False

        try:
            v = Vasprun(self.output_vasprun)
            if v.converged:
                return False
        except Exception:
            pass
        with open(self.output_filename, "r") as f:
            for line in f:
                l = line.strip()
                if l.find(msg) != -1:
                    return True
        return False

    def correct(self):
        backup(VASP_BACKUP_FILES | {self.output_filename})
        vi = VaspInput.from_directory(".")
        m = reduce(operator.mul, vi["KPOINTS"].kpts[0])
        m = max(int(round(m ** (1 / 3))), 1)
        if vi["KPOINTS"].style.name.lower().startswith("m"):
            m += m % 2
        actions = [{"dict": "KPOINTS",
                    "action": {"_set": {"kpoints": [[m] * 3]}}}]
        VaspModder(vi=vi).apply_actions(actions)
        return {"errors": ["mesh_symmetry"], "actions": actions}


class UnconvergedErrorHandler(ErrorHandler):
    """
    Check if a run is converged.
    """
    is_monitor = False

    def __init__(self, output_filename="vasprun.xml"):
        """
        Initializes the handler with the output file to check.

        Args:
            output_vasprun (str): Filename for the vasprun.xml file. Change
                this only if it is different from the default (unlikely).
        """
        self.output_filename = output_filename

    def check(self):
        try:
            v = Vasprun(self.output_filename)
            if not v.converged:
                return True
        except Exception:
            pass
        return False

    def correct(self):
        v = Vasprun(self.output_filename)
        actions = []
        if not v.converged_electronic:
            # Ladder from VeryFast to Fast to Fast to All
            # These progressively switches to more stable but more
            # expensive algorithms
            algo = v.incar.get("ALGO", "Normal")
            if algo == "VeryFast":
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"ALGO": "Fast"}}})
            elif algo == "Fast":
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"ALGO": "Normal"}}})
            elif algo == "Normal":
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"ALGO": "All"}}})
            else:
                # Try mixing as last resort
                new_settings = {"ISTART": 1,
                                "ALGO": "Normal",
                                "NELMDL": -6,
                                "BMIX": 0.001,
                                "AMIX_MAG": 0.8,
                                "BMIX_MAG": 0.001}

                if not all([v.incar.get(k, "") == val for k, val in new_settings.items()]):
                    actions.append({"dict": "INCAR",
                                    "action": {"_set": new_settings}})

        elif not v.converged_ionic:
            # Just continue optimizing and let other handles fix ionic
            # optimizer parameters
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"IBRION": 1}}})
            actions.append({"file": "CONTCAR",
                            "action": {"_file_copy": {"dest": "POSCAR"}}})

        if actions:
            vi = VaspInput.from_directory(".")
            backup(VASP_BACKUP_FILES)
            VaspModder(vi=vi).apply_actions(actions)
            return {"errors": ["Unconverged"], "actions": actions}
        else:
            # Unfixable error. Just return None for actions.
            return {"errors": ["Unconverged"], "actions": None}


@deprecated(message="This handler is no longer supported and its use is no "
                    "longer recommended. It will be removed in v2020.x.")
class MaxForceErrorHandler(ErrorHandler):
    """
    Checks that the desired force convergence has been achieved. Otherwise
    restarts the run with smaller EDIFF. (This is necessary since energy
    and force convergence criteria cannot be set simultaneously)
    """
    is_monitor = False

    def __init__(self, output_filename="vasprun.xml",
                 max_force_threshold=0.25):
        """
        Args:
            input_filename (str): name of the vasp INCAR file
            output_filename (str): name to look for the vasprun
            max_force_threshold (float): Threshold for max force for
                restarting the run. (typically should be set to the value
                that the creator looks for)
        """
        self.output_filename = output_filename
        self.max_force_threshold = max_force_threshold

    def check(self):
        try:
            v = Vasprun(self.output_filename)
            forces = np.array(v.ionic_steps[-1]['forces'])
            sdyn = v.final_structure.site_properties.get('selective_dynamics')
            if sdyn:
                forces[np.logical_not(sdyn)] = 0
            max_force = max(np.linalg.norm(forces, axis=1))
            if max_force > self.max_force_threshold and v.converged is True:
                return True
        except Exception:
            pass
        return False

    def correct(self):
        backup(VASP_BACKUP_FILES | {self.output_filename})
        vi = VaspInput.from_directory(".")
        ediff = float(vi["INCAR"].get("EDIFF", 1e-4))
        ediffg = float(vi["INCAR"].get("EDIFFG", ediff * 10))
        actions = [{"file": "CONTCAR",
                    "action": {"_file_copy": {"dest": "POSCAR"}}},
                   {"dict": "INCAR",
                    "action": {"_set": {"EDIFFG": ediffg * 0.5}}}]
        VaspModder(vi=vi).apply_actions(actions)

        return {"errors": ["MaxForce"], "actions": actions}


class PotimErrorHandler(ErrorHandler):
    """
    Check if a run has excessively large positive energy changes.
    This is typically caused by too large a POTIM. Runs typically
    end up crashing with some other error (e.g. BRMIX) as the geometry
    gets progressively worse.
    """
    is_monitor = True

    def __init__(self, input_filename="POSCAR", output_filename="OSZICAR",
                 dE_threshold=1):
        """
        Initializes the handler with the input and output files to check.

        Args:
            input_filename (str): This is the POSCAR file that the run
                started from. Defaults to "POSCAR". Change
                this only if it is different from the default (unlikely).
            output_filename (str): This is the OSZICAR file. Change
                this only if it is different from the default (unlikely).
            dE_threshold (float): The threshold energy change. Defaults to 1eV.
        """
        self.input_filename = input_filename
        self.output_filename = output_filename
        self.dE_threshold = dE_threshold

    def check(self):
        try:
            oszicar = Oszicar(self.output_filename)
            n = len(Poscar.from_file(self.input_filename).structure)
            max_dE = max([s['dE'] for s in oszicar.ionic_steps[1:]]) / n
            if max_dE > self.dE_threshold:
                return True
        except Exception:
            return False

    def correct(self):
        backup(VASP_BACKUP_FILES)
        vi = VaspInput.from_directory(".")
        potim = float(vi["INCAR"].get("POTIM", 0.5))
        ibrion = int(vi["INCAR"].get("IBRION", 0))
        if potim < 0.2 and ibrion != 3:
            actions = [{"dict": "INCAR",
                        "action": {"_set": {"IBRION": 3,
                                            "SMASS": 0.75}}}]
        elif potim < 0.1:
            actions = [{"dict": "INCAR",
                        "action": {"_set": {"SYMPREC": 1e-8}}}]
        else:
            actions = [{"dict": "INCAR",
                        "action": {"_set": {"POTIM": potim * 0.5}}}]

        VaspModder(vi=vi).apply_actions(actions)
        return {"errors": ["POTIM"], "actions": actions}


class FrozenJobErrorHandler(ErrorHandler):
    """
    Detects an error when the output file has not been updated
    in timeout seconds. Changes ALGO to Normal from Fast
    """

    is_monitor = True

    def __init__(self, output_filename="vasp.out", timeout=21600):
        """
        Initializes the handler with the output file to check.

        Args:
            output_filename (str): This is the file where the stdout for vasp
                is being redirected. The error messages that are checked are
                present in the stdout. Defaults to "vasp.out", which is the
                default redirect used by :class:`custodian.vasp.jobs.VaspJob`.
            timeout (int): The time in seconds between checks where if there
                is no activity on the output file, the run is considered
                frozen. Defaults to 3600 seconds, i.e., 1 hour.
        """
        self.output_filename = output_filename
        self.timeout = timeout

    def check(self):
        st = os.stat(self.output_filename)
        if time.time() - st.st_mtime > self.timeout:
            return True

    def correct(self):
        backup(VASP_BACKUP_FILES | {self.output_filename})

        vi = VaspInput.from_directory('.')
        actions = []
        if vi["INCAR"].get("ALGO", "Normal") == "Fast":
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ALGO": "Normal"}}})
        else:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"SYMPREC": 1e-8}}})

        VaspModder(vi=vi).apply_actions(actions)

        return {"errors": ["Frozen job"], "actions": actions}


class NonConvergingErrorHandler(ErrorHandler):
    """
    Check if a run is hitting the maximum number of electronic steps at the
    last nionic_steps ionic steps (default=10). If so, change ALGO from Fast to
    Normal or kill the job.
    """
    is_monitor = True

    def __init__(self, output_filename="OSZICAR", nionic_steps=10):
        """
        Initializes the handler with the output file to check.

        Args:
            output_filename (str): This is the OSZICAR file. Change
                this only if it is different from the default (unlikely).
            nionic_steps (int): The threshold number of ionic steps that
                needs to hit the maximum number of electronic steps for the
                run to be considered non-converging.
        """
        self.output_filename = output_filename
        self.nionic_steps = nionic_steps

    def check(self):
        vi = VaspInput.from_directory(".")
        nelm = vi["INCAR"].get("NELM", 60)
        try:
            oszicar = Oszicar(self.output_filename)
            esteps = oszicar.electronic_steps
            if len(esteps) > self.nionic_steps:
                return all([len(e) == nelm
                            for e in esteps[-(self.nionic_steps + 1):-1]])
        except Exception:
            pass
        return False

    def correct(self):
        vi = VaspInput.from_directory(".")
        algo = vi["INCAR"].get("ALGO", "Normal")
        amix = vi["INCAR"].get("AMIX", 0.4)
        bmix = vi["INCAR"].get("BMIX", 1.0)
        amin = vi["INCAR"].get("AMIN", 0.1)
        actions = []
        # Ladder from VeryFast to Fast to Fast to All
        # These progressively switches to more stable but more
        # expensive algorithms
        if algo == "VeryFast":
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ALGO": "Fast"}}})
        elif algo == "Fast":
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ALGO": "Normal"}}})
        elif algo == "Normal":
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ALGO": "All"}}})
        elif amix > 0.1 and bmix > 0.01:
            # Try linear mixing
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"AMIX": 0.1, "BMIX": 0.01,
                                                "ICHARG": 2}}})
        elif bmix < 3.0 and amin > 0.01:
            # Try increasing bmix
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"AMIN": 0.01, "BMIX": 3.0,
                                                "ICHARG": 2}}})

        if actions:
            backup(VASP_BACKUP_FILES)
            VaspModder(vi=vi).apply_actions(actions)
            return {"errors": ["Non-converging job"], "actions": actions}
        # Unfixable error. Just return None for actions.
        else:
            return {"errors": ["Non-converging job"], "actions": None}
        
    @classmethod
    def from_dict(cls, d):
        """
        Custom from_dict method to preserve backwards compatibility with 
        older versions of Custodian.
        """
        if "change_algo" in d:
            del d["change_algo"]
        return cls(output_filename=d.get("output_filename", "OSZICAR"),
                   nionic_steps=d.get("nionic_steps", 10))


class WalltimeHandler(ErrorHandler):
    """
    Check if a run is nearing the walltime. If so, write a STOPCAR with
    LSTOP or LABORT = .True.. You can specify the walltime either in the init (
    which is unfortunately necessary for SGE and SLURM systems. If you happen
    to be running on a PBS system and the PBS_WALLTIME variable is in the run
    environment, the wall time will be automatically determined if not set.
    """
    is_monitor = True

    # The WalltimeHandler should not terminate as we want VASP to terminate
    # itself naturally with the STOPCAR.
    is_terminating = False

    # This handler will be unrecoverable, but custodian shouldn't raise an
    # error
    raises_runtime_error = False

    def __init__(self, wall_time=None, buffer_time=300,
                 electronic_step_stop=False):
        """
        Initializes the handler with a buffer time.

        Args:
            wall_time (int): Total walltime in seconds. If this is None and
                the job is running on a PBS system, the handler will attempt to
                determine the walltime from the PBS_WALLTIME environment
                variable. If the wall time cannot be determined or is not
                set, this handler will have no effect.
            buffer_time (int): The min amount of buffer time in secs at the
                end that the STOPCAR will be written. The STOPCAR is written
                when the time remaining is < the higher of 3 x the average
                time for each ionic step and the buffer time. Defaults to
                300 secs, which is the default polling time of Custodian.
                This is typically sufficient for the current ionic step to
                complete. But if other operations are being performed after
                the run has stopped, the buffer time may need to be increased
                accordingly.
            electronic_step_stop (bool): Whether to check for electronic steps
                instead of ionic steps (e.g. for static runs on large systems or
                static HSE runs, ...). Be careful that results such as density
                or wavefunctions might not be converged at the electronic level.
                Should be used with LWAVE = .True. to be useful. If this is
                True, the STOPCAR is written with LABORT = .TRUE. instead of
                LSTOP = .TRUE.
        """
        if wall_time is not None:
            self.wall_time = wall_time
        elif "PBS_WALLTIME" in os.environ:
            self.wall_time = int(os.environ["PBS_WALLTIME"])
        elif "SBATCH_TIMELIMIT" in os.environ:
            self.wall_time = int(os.environ["SBATCH_TIMELIMIT"])
        else:
            self.wall_time = None
        self.buffer_time = buffer_time
        # Sets CUSTODIAN_WALLTIME_START as the start time to use for
        # future jobs in the same batch environment.  Can also be
        # set manually be the user in the batch environment.
        if "CUSTODIAN_WALLTIME_START" in os.environ:
            self.start_time = datetime.datetime.strptime(
                os.environ["CUSTODIAN_WALLTIME_START"], "%a %b %d %H:%M:%S %Z %Y")
        else:
            self.start_time = datetime.datetime.now()
            os.environ["CUSTODIAN_WALLTIME_START"] = datetime.datetime.strftime(
                self.start_time, "%a %b %d %H:%M:%S UTC %Y")

        self.electronic_step_stop = electronic_step_stop
        self.electronic_steps_timings = [0]
        self.prev_check_time = self.start_time

    def check(self):
        if self.wall_time:
            run_time = datetime.datetime.now() - self.start_time
            total_secs = run_time.total_seconds()
            outcar = Outcar("OUTCAR")
            if not self.electronic_step_stop:
                # Determine max time per ionic step.
                outcar.read_pattern({"timings": "LOOP\+.+real time(.+)"},
                                    postprocess=float)
                time_per_step = np.max(outcar.data.get('timings')) if outcar.data.get("timings", []) else 0
            else:
                # Determine max time per electronic step.
                outcar.read_pattern({"timings": "LOOP:.+real time(.+)"},
                                    postprocess=float)
                time_per_step = np.max(outcar.data.get('timings')) if outcar.data.get("timings", []) else 0

            # If the remaining time is less than average time for 3
            # steps or buffer_time.
            time_left = self.wall_time - total_secs
            if time_left < max(time_per_step * 3, self.buffer_time):
                return True

        return False

    def correct(self):

        content = "LSTOP = .TRUE." if not self.electronic_step_stop else \
            "LABORT = .TRUE."
        # Write STOPCAR
        actions = [{"file": "STOPCAR",
                    "action": {"_file_create": {'content': content}}}]

        m = Modder(actions=[FileActions])
        for a in actions:
            m.modify(a["action"], a["file"])
        return {"errors": ["Walltime reached"], "actions": None}


@deprecated(replacement=WalltimeHandler)
class PBSWalltimeHandler(WalltimeHandler):

    def __init__(self, buffer_time=300):
        super(PBSWalltimeHandler, self).__init__(None, buffer_time=buffer_time)


class CheckpointHandler(ErrorHandler):
    """
    This is not an error handler per se, but rather a checkpointer. What this
    does is that every X seconds, a STOPCAR and CHKPT will be written. This
    forces VASP to stop at the end of the next ionic step. The files are then
    copied into a subdir, and then the job is restarted. To use this proper,
    max_errors in Custodian must be set to a very high value, and you
    probably wouldn't want to use any standard VASP error handlers. The
    checkpoint will be stored in subdirs chk_#. This should be used in
    combiantion with the StoppedRunHandler.
    """
    is_monitor = True

    # The CheckpointHandler should not terminate as we want VASP to terminate
    # itself naturally with the STOPCAR.
    is_terminating = False

    def __init__(self, interval=3600):
        """
        Initializes the handler with an interval.

        Args:
            interval (int): Interval at which to checkpoint in seconds.
            Defaults to 3600 (1 hr).
        """
        self.interval = interval
        self.start_time = datetime.datetime.now()
        self.chk_counter = 0

    def check(self):
        run_time = datetime.datetime.now() - self.start_time
        total_secs = run_time.seconds + run_time.days * 3600 * 24
        if total_secs > self.interval:
            return True
        return False

    def correct(self):
        content = "LSTOP = .TRUE."
        chkpt_content = "Index: %d\nTime: \"%s\"" % (self.chk_counter,
                                                     datetime.datetime.now())
        self.chk_counter += 1

        # Write STOPCAR
        actions = [{"file": "STOPCAR",
                    "action": {"_file_create": {'content': content}}},
                   {"file": "chkpt.yaml",
                    "action": {"_file_create": {'content': chkpt_content}}}]

        m = Modder(actions=[FileActions])
        for a in actions:
            m.modify(a["action"], a["file"])

        # Reset the clock.
        self.start_time = datetime.datetime.now()

        return {"errors": ["Checkpoint reached"], "actions": actions}

    def __str__(self):
        return "CheckpointHandler with interval %d" % self.interval


class StoppedRunHandler(ErrorHandler):
    """
    This is not an error handler per se, but rather a checkpointer. What this
    does is that every X seconds, a STOPCAR will be written. This forces VASP to
    stop at the end of the next ionic step. The files are then copied into a
    subdir, and then the job is restarted. To use this proper, max_errors in
    Custodian must be set to a very high value, and you probably wouldn't
    want to use any standard VASP error handlers. The checkpoint will be
    stored in subdirs chk_#. This should be used in combination with the
    StoppedRunHandler.
    """
    is_monitor = False

    # The CheckpointHandler should not terminate as we want VASP to terminate
    # itself naturally with the STOPCAR.
    is_terminating = False

    def __init__(self):
        pass

    def check(self):
        return os.path.exists("chkpt.yaml")

    def correct(self):
        d = loadfn("chkpt.yaml")
        i = d["Index"]
        name = shutil.make_archive(
            os.path.join(os.getcwd(), "vasp.chk.%d" % i), "gztar")

        actions = [{"file": "CONTCAR",
                    "action": {"_file_copy": {"dest": "POSCAR"}}}]

        m = Modder(actions=[FileActions])
        for a in actions:
            m.modify(a["action"], a["file"])

        actions.append({"Checkpoint": name})

        return {"errors": ["Stopped run."],
                "actions": actions}


class PositiveEnergyErrorHandler(ErrorHandler):
    """
    Check if a run has positive absolute energy.
    If so, change ALGO from Fast to Normal or kill the job.
    """
    is_monitor = True

    def __init__(self, output_filename="OSZICAR"):
        """
        Initializes the handler with the output file to check.

        Args:
            output_filename (str): This is the OSZICAR file. Change
                this only if it is different from the default (unlikely).
        """
        self.output_filename = output_filename

    def check(self):
        try:
            oszicar = Oszicar(self.output_filename)
            if oszicar.final_energy > 0:
                return True
        except Exception:
            pass
        return False

    def correct(self):
        # change ALGO = Fast to Normal if ALGO is !Normal
        vi = VaspInput.from_directory(".")
        algo = vi["INCAR"].get("ALGO", "Normal")
        if algo.lower() not in ['normal', 'n']:
            backup(VASP_BACKUP_FILES)
            actions = [{"dict": "INCAR",
                        "action": {"_set": {"ALGO": "Normal"}}}]
            VaspModder(vi=vi).apply_actions(actions)
            return {"errors": ["Positive energy"], "actions": actions}
        elif algo == "Normal":
            potim = float(vi["INCAR"].get("POTIM", 0.5)) / 2.0
            actions = [{"dict": "INCAR",
                        "action": {"_set": {"POTIM": potim}}}]
            VaspModder(vi=vi).apply_actions(actions)
            return {"errors": ["Positive energy"], "actions": actions}
        # Unfixable error. Just return None for actions.
        else:
            return {"errors": ["Positive energy"], "actions": None}
