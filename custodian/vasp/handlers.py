# coding: utf-8

from __future__ import unicode_literals, division

from monty.os.path import zpath

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

import os
import time
import datetime
import operator
import shutil
from functools import reduce
from collections import Counter
import re

from six.moves import map

import numpy as np

from monty.dev import deprecated
from monty.serialization import loadfn

from math import ceil

from custodian.custodian import ErrorHandler
from custodian.utils import backup
from pymatgen.io.vasp import Poscar, VaspInput, Incar, Kpoints, Vasprun, Oszicar, Outcar
from pymatgen.transformations.standard_transformations import \
    SupercellTransformation

from custodian.ansible.interpreter import Modder
from custodian.ansible.actions import FileActions
from custodian.vasp.interpreter import VaspModder

VASP_BACKUP_FILES = {"INCAR", "KPOINTS", "POSCAR", "OUTCAR", "OSZICAR",
                     "vasprun.xml", "vasp.out", "std_err.txt"}


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
                "Routine TETIRR needs special values"],
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
        "grad_not_orth": ["EDWAV: internal error, the gradient is not orthogonal"]
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
        self.error_count = Counter()

    def check(self):
        incar = Incar.from_file("INCAR")
        self.errors = set()
        with open(self.output_filename, "r") as f:
            for line in f:
                l = line.strip()
                for err, msgs in VaspErrorHandler.error_msgs.items():
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

        if self.errors.intersection(["tet", "dentet"]):
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ISMEAR": 0}}})

        if "inv_rot_mat" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"SYMPREC": 1e-8}}})

        if "brmix" in self.errors:
            # If there is not a valid OUTCAR already, increment
            # error count to 1 to skip first fix
            if self.error_count['brmix'] == 0:
                try:
                    assert(Outcar(zpath(os.path.join(
                        os.getcwd(), "OUTCAR"))).is_stopped is False)
                except:
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
                                "action": {"_set": {"generation_style":
                                                        "Monkhorst"}}})
                actions.append({"dict": "INCAR",
                                "action": {"_unset": {"IMIX": 1}}})
                self.error_count['brmix'] += 1

            elif self.error_count['brmix'] in [2, 3] and vi["KPOINTS"].style \
                    == Kpoints.supported_modes.Monkhorst:
                actions.append({"dict": "KPOINTS",
                                "action": {"_set": {"generation_style":
                                                        "Gamma"}}})
                actions.append({"dict": "INCAR",
                                "action": {"_unset": {"IMIX": 1}}})
                self.error_count['brmix'] += 1

                if vi["KPOINTS"].num_kpts < 1:
                    all_kpts_even = all([
                        bool(n % 2 == 0) for n in vi["KPOINTS"].kpts[0]
                    ])
                    print("all_kpts_even = {}".format(all_kpts_even))
                    if all_kpts_even:
                        new_kpts = (tuple(n+1 for n in vi["KPOINTS"].kpts[0]),)
                        print("new_kpts = {}".format(new_kpts))
                        actions.append({"dict": "KPOINTS", "action": {"_set": {
                            "kpoints": new_kpts
                        }}})

            else:
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"ISYM": 0}}})

                if vi["KPOINTS"].style == Kpoints.supported_modes.Monkhorst:
                   actions.append({"dict": "KPOINTS",
                                   "action": {"_set": {"generation_style": "Gamma"}}})

                # Based on VASP forum's recommendation, you should delete the
                # CHGCAR and WAVECAR when dealing with this error.
                if vi["INCAR"].get("ICHARG", 0) < 10:
                    actions.append({"file": "CHGCAR",
                                    "action": {"_file_delete": {'mode': "actual"}}})
                    actions.append({"file": "WAVECAR",
                                    "action": {"_file_delete": {'mode': "actual"}}})

        if "zpotrf" in self.errors:
            # Usually caused by short bond distances. If on the first step,
            # volume needs to be increased. Otherwise, it was due to a step
            # being too big and POTIM should be decreased.
            try:
                oszicar = Oszicar("OSZICAR")
                nsteps = len(oszicar.ionic_steps)
            except:
                nsteps = 0

            if nsteps >= 1:
                potim = float(vi["INCAR"].get("POTIM", 0.5)) / 2.0
                actions.append(
                    {"dict": "INCAR",
                     "action": {"_set": {"ISYM": 0, "POTIM": potim}}})
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

        if self.errors.intersection(["subspacematrix", "rspher",
                                     "real_optlay"]):
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"LREAL": False}}})

        if self.errors.intersection(["tetirr", "incorrect_shift"]):

            if vi["KPOINTS"].style == Kpoints.supported_modes.Monkhorst:
                actions.append({"dict": "KPOINTS",
                                "action": {"_set": {"generation_style": "Gamma"}}})

        if "rot_matrix" in self.errors:
            if vi["KPOINTS"].style == Kpoints.supported_modes.Monkhorst:
                actions.append({"dict": "KPOINTS",
                                "action": {"_set": {"generation_style": "Gamma"}}})
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
            actions.append({"dict": "INCAR", "action":
                                    {"_set": {"ALGO": "Normal"}}})
        if "eddrmm" in self.errors:
            #RMM algorithm is not stable for this calculation
            if vi["INCAR"].get("ALGO", "Normal") in ["Fast", "VeryFast"]:
                actions.append({"dict": "INCAR", "action":
                                        {"_set": {"ALGO": "Normal"}}})
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
            actions.append({"dict": "INCAR", "action":
                            {"_set": {"ALGO": "All"}}})

        if "grad_not_orth" in self.errors:
            if vi["INCAR"].get("ISMEAR", 1) < 0:
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"ISMEAR": "0"}}})

        VaspModder(vi=vi).apply_actions(actions)
        return {"errors": list(self.errors), "actions": actions}


class AliasingErrorHandler(ErrorHandler):
    """
    Master VaspErrorHandler class that handles a number of common errors
    that occur during VASP runs.
    """

    is_monitor = True

    error_msgs = {
        "aliasing": ["WARNING: small aliasing (wrap around) errors must be expected"],
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
                    #Ensure that all NGX, NGY, NGZ have been checked
                    if grid_adjusted and 'NGZ' in line:
                        actions.append({"dict": "INCAR", "action": {"_set": changes_dict}})
                        if vi["INCAR"].get("ICHARG", 0) < 10:
                            actions.extend([{"file": "CHGCAR",
                                             "action": {"_file_delete": {'mode': "actual"}}},
                                            {"file": "WAVECAR",
                                             "action": {"_file_delete": {'mode': "actual"}}}])
                        break

        if "aliasing_incar" in self.errors:
            #vasp seems to give different warnings depending on whether the
            #aliasing error was caused by user supplied inputs
            d = {k: 1 for k in ['NGX', 'NGY', 'NGZ'] if k in vi['INCAR'].keys()}
            actions.append({"dict": "INCAR", "action": {"_unset": d}})

            if vi["INCAR"].get("ICHARG", 0) < 10:
                actions.extend([{"file": "CHGCAR",
                                 "action": {"_file_delete": {'mode': "actual"}}},
                                {"file": "WAVECAR",
                                 "action": {"_file_delete": {'mode': "actual"}}}])

        VaspModder(vi=vi).apply_actions(actions)
        return {"errors": list(self.errors), "actions": actions}


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
        #Also disregard if automatic KPOINT generation is used
        if (not vi["INCAR"].get('ISYM', True)) or \
                    vi["KPOINTS"].style == Kpoints.supported_modes.Automatic:
            return False

        try:
            v = Vasprun(self.output_vasprun)
            if v.converged:
                return False
        except:
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
    Check if a run is converged. Switches to ALGO = Normal.
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
        except:
            pass
        return False

    def correct(self):
        backup(VASP_BACKUP_FILES)
        actions = [{"file": "CONTCAR",
                    "action": {"_file_copy": {"dest": "POSCAR"}}},
                   {"dict": "INCAR",
                    "action": {"_set": {"ISTART": 1,
                                        "ALGO": "Normal",
                                        "NELMDL": -6,
                                        "BMIX": 0.001,
                                        "AMIX_MAG": 0.8,
                                        "BMIX_MAG": 0.001}}}]
        VaspModder().apply_actions(actions)
        return {"errors": ["Unconverged"], "actions": actions}


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
            max_force = max([np.linalg.norm(a) for a
                             in v.ionic_steps[-1]["forces"]])
            if max_force > self.max_force_threshold and v.converged is True:
                return True
        except:
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
                    "action": {"_set": {"EDIFFG": ediffg*0.5}}}]
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
        except:
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

        VaspModder(vi=vi).apply_actions(actions)

        return {"errors": ["Frozen job"], "actions": actions}


class NonConvergingErrorHandler(ErrorHandler):
    """
    Check if a run is hitting the maximum number of electronic steps at the
    last nionic_steps ionic steps (default=10). If so, change ALGO from Fast to
    Normal or kill the job.
    """
    is_monitor = True

    def __init__(self, output_filename="OSZICAR", nionic_steps=10,
                 change_algo=False):
        """
        Initializes the handler with the output file to check.

        Args:
            output_filename (str): This is the OSZICAR file. Change
                this only if it is different from the default (unlikely).
            nionic_steps (int): The threshold number of ionic steps that
                needs to hit the maximum number of electronic steps for the
                run to be considered non-converging.
            change_algo (bool): Whether to attempt to correct the job by
                changing the ALGO from Fast to Normal.
        """
        self.output_filename = output_filename
        self.nionic_steps = nionic_steps
        self.change_algo = change_algo

    def check(self):
        vi = VaspInput.from_directory(".")
        nelm = vi["INCAR"].get("NELM", 60)
        try:
            oszicar = Oszicar(self.output_filename)
            esteps = oszicar.electronic_steps
            if len(esteps) > self.nionic_steps:
                return all([len(e) == nelm
                            for e in esteps[-(self.nionic_steps + 1):-1]])
        except:
            pass
        return False

    def correct(self):
        # if change_algo is True, change ALGO = Fast to Normal if ALGO is
        # Fast. If still not converging, following Kresse's
        # recommendation, we will try two iterations of different mixing
        # parameters. If this error is caught again, then kil the job
        vi = VaspInput.from_directory(".")
        algo = vi["INCAR"].get("ALGO", "Normal")
        amix = vi["INCAR"].get("AMIX", 0.4)
        bmix = vi["INCAR"].get("BMIX", 1.0)
        amin = vi["INCAR"].get("AMIN", 0.1)
        actions = []
        if self.change_algo:
            if algo == "Fast":
                backup(VASP_BACKUP_FILES)
                actions.append({"dict": "INCAR",
                            "action": {"_set": {"ALGO": "Normal"}}})

            elif amix > 0.1 and bmix > 0.01:
                #try linear mixing
                backup(VASP_BACKUP_FILES)
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"AMIX": 0.1, "BMIX": 0.01,
                                                    "ICHARG": 2}}})

            elif bmix < 3.0 and amin > 0.01:
                #Try increasing bmix
                backup(VASP_BACKUP_FILES)
                actions.append({"dict": "INCAR",
                                "action": {"_set": {"AMIN": 0.01, "BMIX": 3.0,
                                                    "ICHARG": 2}}})

        if actions:
            VaspModder(vi=vi).apply_actions(actions)
            return {"errors": ["Non-converging job"], "actions": actions}

        #Unfixable error. Just return None for actions.
        else:
            return {"errors": ["Non-converging job"], "actions": None}


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
                 electronic_step_stop=False,
                 auto_continue = False):
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
            auto_continue (bool): Use the auto-continue functionality within the
                VaspJob by ensuring Vasp doesn't delete the STOPCAR
        """
        if wall_time is not None:
            self.wall_time = wall_time
        elif "PBS_WALLTIME" in os.environ:
            self.wall_time = int(os.environ["PBS_WALLTIME"])
        else:
            self.wall_time = None
        self.buffer_time = buffer_time
        self.start_time = datetime.datetime.now()
        self.electronic_step_stop = electronic_step_stop
        self.electronic_steps_timings = [0]
        self.prev_check_time = self.start_time
        self.prev_check_nscf_steps = 0
        self.auto_continue = auto_continue

    def check(self):
        if self.wall_time:
            run_time = datetime.datetime.now() - self.start_time
            total_secs = run_time.total_seconds()
            if not self.electronic_step_stop:
                try:
                    # Intelligently determine time per ionic step.
                    o = Oszicar("OSZICAR")
                    nsteps = len(o.ionic_steps)
                    time_per_step = total_secs / nsteps
                except Exception:
                    time_per_step = 0
            else:
                try:
                    # Intelligently determine approximate time per electronic
                    # step.
                    o = Oszicar("OSZICAR")
                    if len(o.ionic_steps) == 0:
                        nsteps = 0
                    else:
                        nsteps = sum(map(len, o.electronic_steps))
                    if nsteps > self.prev_check_nscf_steps:
                        steps_time = datetime.datetime.now() - \
                            self.prev_check_time
                        steps_secs = steps_time.total_seconds()
                        step_timing = self.buffer_time * ceil(
                            (steps_secs /
                             (nsteps - self.prev_check_nscf_steps)) /
                            self.buffer_time)
                        self.electronic_steps_timings.append(step_timing)
                        self.prev_check_nscf_steps = nsteps
                        self.prev_check_time = datetime.datetime.now()
                    time_per_step = max(self.electronic_steps_timings)
                except Exception as ex:
                    time_per_step = 0

            # If the remaining time is less than average time for 3 ionic
            # steps or buffer_time.
            time_left = self.wall_time - total_secs
            if time_left < max(time_per_step * 3, self.buffer_time):
                return True

        return False

    def correct(self):

        content = "LSTOP = .TRUE." if not self.electronic_step_stop else \
            "LABORT = .TRUE."
        #Write STOPCAR
        actions = [{"file": "STOPCAR",
                    "action": {"_file_create": {'content': content}}}]

        if self.auto_continue:
            actions.append({"file": "STOPCAR",
                            "action": {"_file_modify": {'mode': 0o444}}})

        m = Modder(actions=[FileActions])
        for a in actions:
            m.modify(a["action"], a["file"])
        # Actions is being returned as None so that custodian will stop after
        # STOPCAR is written. We do not want subsequent jobs to proceed.
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

        #Write STOPCAR
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
        except:
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
        #Unfixable error. Just return None for actions.
        else:
            return {"errors": ["Positive energy"], "actions": None}
