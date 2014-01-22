#!/usr/bin/env python

"""
This module implements specific error handlers for VASP runs. These handlers
tries to detect common errors in vasp runs and attempt to fix them on the fly
by modifying the input files.
"""

from __future__ import division

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

from custodian.custodian import ErrorHandler
from custodian.utils import backup
from pymatgen.io.vaspio.vasp_input import Poscar, VaspInput
from pymatgen.transformations.standard_transformations import \
    PerturbStructureTransformation, SupercellTransformation

from pymatgen.io.vaspio.vasp_output import Vasprun, Oszicar
from custodian.ansible.intepreter import Modder
from custodian.ansible.actions import FileActions, DictActions


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
        "real_optlay": ["REAL_OPTLAY: internal error"],
        "rspher": ["ERROR RSPHER"],
        "dentet": ["DENTET"],
        "too_few_bands": ["TOO FEW BANDS"],
        "triple_product": ["ERROR: the triple product of the basis vectors"],
        "rot_matrix": ["Found some non-integer element in rotation matrix"],
        "brions": ["BRIONS problems: POTIM should be increased"],
        "pricel": ["internal error in subroutine PRICEL"],
        "zpotrf": ["LAPACK: Routine ZPOTRF failed"],
        "amin": ["One of the lattice vectors is very long (>50 A), but AMIN"],
        "zbrent": ["ZBRENT: fatal internal in brackting"],
        "aliasing": ["WARNING: small aliasing (wrap around) errors must be expected"]
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
        self.errors = set()
        with open(self.output_filename, "r") as f:
            for line in f:
                l = line.strip()
                for err, msgs in VaspErrorHandler.error_msgs.items():
                    for msg in msgs:
                        if l.find(msg) != -1:
                            self.errors.add(err)
        return len(self.errors) > 0

    def correct(self):
        backup([self.output_filename, "INCAR", "KPOINTS", "POSCAR", "OUTCAR",
                "vasprun.xml"])
        actions = []
        vi = VaspInput.from_directory(".")

        if "tet" in self.errors or "dentet" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ISMEAR": 0}}})

        if "inv_rot_mat" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"SYMPREC": 1e-8}}})

        if "brmix" in self.errors or "zpotrf" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ISYM": 0}}})
            # Based on VASP forum's recommendation, you should delete the
            # CHGCAR and WAVECAR when dealing with these errors.
            actions.append({"file": "CHGCAR",
                            "action": {"_file_delete": {'mode': "actual"}}})
            actions.append({"file": "WAVECAR",
                            "action": {"_file_delete": {'mode': "actual"}}})

        if "subspacematrix" in self.errors or "rspher" in self.errors or \
                        "real_optlay" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"LREAL": False}}})

        if "tetirr" in self.errors or "incorrect_shift" in self.errors:
            actions.append({"dict": "KPOINTS",
                            "action": {"_set": {"generation_style": "Gamma"}}})

        if "amin" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"AMIN": "0.01"}}})

        if "triple_product" in self.errors:
            s = vi["POSCAR"].structure
            trans = SupercellTransformation(((1, 0, 0), (0, 0, 1), (0, 1, 0)))
            new_s = trans.apply_transformation(s)
            actions.append({"dict": "POSCAR",
                            "action": {"_set": {"structure": new_s.to_dict}},
                            "transformation": trans.to_dict})

        if "rot_matrix" in self.errors or "pricel" in self.errors:
            s = vi["POSCAR"].structure
            trans = PerturbStructureTransformation(0.05)
            new_s = trans.apply_transformation(s)
            actions.append({"dict": "POSCAR",
                            "action": {"_set": {"structure": new_s.to_dict}},
                            "transformation": trans.to_dict})
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"SYMPREC": 1e-8}}})

        if "brions" in self.errors:
            potim = float(vi["INCAR"].get("POTIM", 0.5)) + 0.1
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"POTIM": potim}}})

        if "zbrent" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"IBRION": 1}}})

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

        if "aliasing" in self.errors:
            with open("OUTCAR") as f:
                grid_adjusted = False
                changes_dict = {}
                for line in f:
                    if "aliasing errors" in line:
                        try:
                            grid_vector = line.split(" NG", 1)[1]
                            value = [int(s) for s in grid_vector.split(" ")
                                     if s.isdigit()][0]

                            changes_dict["NG" + grid_vector[0]] = value
                            grid_adjusted = True
                        except (IndexError, ValueError):
                            pass
                    #Ensure that all NGX, NGY, NGZ have been checked
                    if grid_adjusted and 'NGZ' in line:
                        actions.append({"dict": "INCAR",
                                        "action": {"_set": changes_dict}})
                        break

        m = Modder(actions=[DictActions, FileActions])
        modified = []
        for a in actions:
            if "dict" in a:
                modified.append(a["dict"])
                vi[a["dict"]] = m.modify_object(a["action"], vi[a["dict"]])
            elif "file" in a:
                m.modify(a["action"], a["file"])
        for f in modified:
            vi[f].write_file(f)
        return {"errors": list(self.errors), "actions": actions}

    def __str__(self):
        return "VaspErrorHandler"


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
        backup([self.output_filename, "INCAR", "KPOINTS", "POSCAR", "OUTCAR",
                "vasprun.xml"])
        vi = VaspInput.from_directory(".")
        m = reduce(operator.mul, vi["KPOINTS"].kpts[0])
        m = max(int(round(m ** (1 / 3))), 1)
        if vi["KPOINTS"].style.lower().startswith("m"):
            m += m % 2
        actions = [{"dict": "KPOINTS",
                    "action": {"_set": {"kpoints": [[m] * 3]}}}]
        m = Modder()
        modified = []
        for a in actions:
            modified.append(a["dict"])
            vi[a["dict"]] = m.modify_object(a["action"], vi[a["dict"]])
        for f in modified:
            vi[f].write_file(f)
        return {"errors": ["mesh_symmetry"], "actions": actions}

    def __str__(self):
        return "MeshSymmetryErrorHandler"


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
        except:
            return False
        if not v.converged:
            return True
        return False

    def correct(self):
        backup(["INCAR", "KPOINTS", "POSCAR", "OUTCAR", "vasprun.xml"])
        actions = [{"file": "CONTCAR",
                    "action": {"_file_copy": {"dest": "POSCAR"}}},
                   {"dict": "INCAR",
                    "action": {"_set": {"ISTART": 1,
                                        "ALGO": "Normal",
                                        "NELMDL": 6,
                                        "BMIX": 0.001,
                                        "AMIX_MAG": 0.8,
                                        "BMIX_MAG": 0.001}}}]
        vi = VaspInput.from_directory(".")
        m = Modder(actions=[DictActions, FileActions])
        for a in actions:
            if "dict" in a:
                vi[a["dict"]] = m.modify_object(a["action"], vi[a["dict"]])
            elif "file" in a:
                m.modify(a["action"], a["file"])
        vi["INCAR"].write_file("INCAR")

        return {"errors": ["Unconverged"], "actions": actions}

    def __str__(self):
        return self.__name__


class PotimErrorHandler(ErrorHandler):
    """
    Check if a run has excessively large positive energy changes.
    This is typically caused by too large a POTIM. Runs typically
    end up crashing with some other error (e.g. BRMIX) as the geometry
    gets progressively worse.
    """
    is_monitor = True

    def __init__(self, input_filename="POSCAR",
                 output_filename="OSZICAR", dE_threshold=1):
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
        backup(["INCAR", "KPOINTS", "POSCAR", "OUTCAR",
                "vasprun.xml"])
        vi = VaspInput.from_directory(".")
        potim = float(vi["INCAR"].get("POTIM", 0.5)) * 0.5
        actions = [{"dict": "INCAR",
                    "action": {"_set": {"POTIM": potim}}}]
        m = Modder()
        modified = []
        for a in actions:
            modified.append(a["dict"])
            vi[a["dict"]] = m.modify_object(a["action"], vi[a["dict"]])
        for f in modified:
            vi[f].write_file(f)
        return {"errors": ["POTIM"], "actions": actions}

    def __str__(self):
        return "Large positive energy change (POTIM)"


class FrozenJobErrorHandler(ErrorHandler):
    """
    Detects an error when the output file has not been updated
    in timeout seconds. Perturbs structure and restarts.
    """

    is_monitor = True

    def __init__(self, output_filename="vasp.out", timeout=3600):
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
        backup([self.output_filename, "INCAR", "KPOINTS", "POSCAR", "OUTCAR",
                "vasprun.xml"])
        p = Poscar.from_file("POSCAR")
        s = p.structure
        trans = PerturbStructureTransformation(0.05)
        new_s = trans.apply_transformation(s)
        actions = [{"dict": "POSCAR",
                    "action": {"_set": {"structure": new_s.to_dict}},
                    "transformation": trans.to_dict}]
        m = Modder()
        vi = VaspInput.from_directory(".")
        for a in actions:
            vi[a["dict"]] = m.modify_object(a["action"], vi[a["dict"]])
        vi["POSCAR"].write_file("POSCAR")

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
        # Fast, else kill the job
        vi = VaspInput.from_directory(".")
        algo = vi["INCAR"].get("ALGO", "Normal")
        if self.change_algo and algo == "Fast":
            backup(["INCAR", "KPOINTS", "POSCAR", "OUTCAR", "vasprun.xml"])
            actions = [{"dict": "INCAR",
                        "action": {"_set": {"ALGO": "Normal"}}}]
            m = Modder()
            modified = []
            for a in actions:
                modified.append(a["dict"])
                vi[a["dict"]] = m.modify_object(a["action"], vi[a["dict"]])
            for f in modified:
                vi[f].write_file(f)
            return {"errors": ["Non-converging job"], "actions": actions}
        #Unfixable error. Just return None for actions.
        else:
            return {"errors": ["Non-converging job"], "actions": None}

    def __str__(self):
        return "NonConvergingErrorHandler"


class PBSWalltimeHandler(ErrorHandler):
    """
    Check if a run is nearing the walltime of a PBS queuing system. If so,
    write a STOPCAR with LSTOP=.True.. The PBS_WALLTIME variable must be in
    the environment (usually the case for PBS systems like most
    supercomputing centers).
    """
    is_monitor = True

    # The PBS handler should not terminate as we want VASP to terminate
    # itself naturally with the STOPCAR.
    is_terminating = False

    def __init__(self, buffer_time=300):
        """
        Initializes the handler with a buffer time.

        Args:
            buffer_time (int): The min amount of buffer time in secs at the
                end that the STOPCAR will be written. The STOPCAR is written
                when the time remaining is < the higher of 3 x the average
                time for each ionic step and the buffer time. Defaults to
                300 secs, which is the default polling time of Custodian.
                This is typically sufficient for the current ionic step to
                complete. But if other operations are being performed after
                the run has stopped, the buffer time may need to be increased
                accordingly.
        """
        self.buffer_time = buffer_time
        self.start_time = datetime.datetime.now()

    def check(self):
        if "PBS_WALLTIME" in os.environ:
            wall_time = int(os.environ["PBS_WALLTIME"])
            run_time = datetime.datetime.now() - self.start_time
            total_secs = run_time.seconds + run_time.days * 3600 * 24
            try:
                #Intelligently determine time per ionic step.
                o = Oszicar("OSZICAR")
                nsteps = len(o.ionic_steps)
                time_per_step = total_secs / nsteps
            except Exception as ex:
                time_per_step = 0

            # If the remaining time is less than average time for 3 ionic
            # steps or buffer_time.
            time_left = wall_time - total_secs
            if time_left < max(time_per_step * 3, self.buffer_time):
                return True
        return False

    def correct(self):
        #Write STOPCAR
        actions = [{"file": "STOPCAR",
                    "action": {"_file_create": {'content': "LSTOP = .TRUE."}}}]
        m = Modder(actions=[FileActions])
        for a in actions:
            m.modify(a["action"], a["file"])
        # Actions is being returned as None so that custodian will stop after
        # STOPCAR is written. We do not want subsequent jobs to proceed.
        return {"errors": ["Walltime reached"], "actions": None}

    def __str__(self):
        return "PBSWalltimeHandler"
