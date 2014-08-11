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
import shutil
import glob

import numpy as np

from monty.dev import deprecated
from monty.serialization import loadfn

from math import ceil

from custodian.custodian import ErrorHandler
from custodian.utils import backup
from pymatgen.io.vaspio.vasp_input import Poscar, VaspInput, Incar
from pymatgen.transformations.standard_transformations import \
    PerturbStructureTransformation, SupercellTransformation

from pymatgen.io.vaspio.vasp_output import Vasprun, Oszicar
from custodian.ansible.interpreter import Modder
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
        incar = Incar.from_file("INCAR")
        self.errors = set()
        with open(self.output_filename, "r") as f:
            for line in f:
                l = line.strip()
                for err, msgs in VaspErrorHandler.error_msgs.items():
                    for msg in msgs:
                        if l.find(msg) != -1:
                            #this checks if we want to run a charged computation
                            #(e.g., defects) if yes we don't want to kill it
                            #because there is a change in e- density (brmix error)
                            if err == "brmix" and 'NELECT' in incar:
                                continue
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

        if "brmix" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ISYM": 0}}})
            # Based on VASP forum's recommendation, you should delete the
            # CHGCAR and WAVECAR when dealing with this error.
            actions.append({"file": "CHGCAR",
                            "action": {"_file_delete": {'mode': "actual"}}})
            actions.append({"file": "WAVECAR",
                            "action": {"_file_delete": {'mode': "actual"}}})

        if "zpotrf" in self.errors:
            #Based on VASP forum's recommendation, you should
            #decrease POTIM with this error
            potim = float(vi["INCAR"].get("POTIM", 0.5)) / 2.0

            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ISYM": 0, "POTIM": potim}}})
            # Based on VASP forum's recommendation, you should delete the
            # CHGCAR and WAVECAR when dealing with this error.

            actions.append({"file": "CHGCAR",
                            "action": {"_file_delete": {'mode': "actual"}}})
            actions.append({"file": "WAVECAR",
                            "action": {"_file_delete": {'mode': "actual"}}})

        if "subspacematrix" in self.errors or "rspher" in self.errors or \
                        "real_optlay" in self.errors:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"LREAL": False}}})

        if "tetirr" in self.errors or "incorrect_shift" in self.errors or \
                    "rot_matrix" in self.errors:
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
            # According to VASP admins, you can disregard this error
            # if symmetry is off
            if v.converged or (not v.incar.get('ISYM', True)):
                return False
            # do not apply if job was terminated (vasprun.xml cannot be read)
            with open(self.output_filename, "r") as f:
                for line in f:
                    l = line.strip()
                    if l.find(msg) != -1:
                        return True
        except:
            pass
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
            if not v.converged:
                return True
        except:
            pass
        return False

    def correct(self):
        backup(["INCAR", "KPOINTS", "POSCAR", "OUTCAR", "vasprun.xml"])
        actions = [{"file": "CONTCAR",
                    "action": {"_file_copy": {"dest": "POSCAR"}}},
                   {"dict": "INCAR",
                    "action": {"_set": {"ISTART": 1,
                                        "ALGO": "Normal",
                                        "NELMDL": -6,
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


class MaxForceErrorHandler(ErrorHandler):
    """
    Checks that the desired force convergence has been achieved. Otherwise
    restarts the run with smaller EDIFF. (This is necessary since energy
    and force convergence criteria cannot be set simultaneously)
    """
    is_monitor = False

    def __init__(self, output_filename="vasprun.xml",
                 max_force_threshold=0.5):
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
            if max_force > self.max_force_threshold:
                return True
        except:
            pass
        return False

    def correct(self):
        backup(["INCAR", "KPOINTS", "POSCAR", "OUTCAR",
                self.output_filename])
        vi = VaspInput.from_directory(".")
        ediff = float(vi["INCAR"].get("EDIFF", 1e-4))
        actions = [{"file": "CONTCAR",
                    "action": {"_file_copy": {"dest": "POSCAR"}}},
                   {"dict": "INCAR",
                    "action": {"_set": {"EDIFF": ediff*0.75}}}]
        m = Modder(actions=[DictActions, FileActions])
        for a in actions:
            if "dict" in a:
                vi[a["dict"]] = m.modify_object(a["action"], vi[a["dict"]])
            elif "file" in a:
                m.modify(a["action"], a["file"])
        vi["INCAR"].write_file("INCAR")

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
        else:
            self.wall_time = None
        self.buffer_time = buffer_time
        self.start_time = datetime.datetime.now()
        self.electronic_step_stop = electronic_step_stop
        self.electronic_steps_timings = [0]
        self.prev_check_time = self.start_time
        self.prev_check_nscf_steps = 0

    def check(self):
        if self.wall_time:
            run_time = datetime.datetime.now() - self.start_time
            total_secs = run_time.seconds + run_time.days * 3600 * 24
            if not self.electronic_step_stop:
                try:
                    # Intelligently determine time per ionic step.
                    o = Oszicar("OSZICAR")
                    nsteps = len(o.ionic_steps)
                    time_per_step = total_secs / nsteps
                except Exception as ex:
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
                        steps_secs = steps_time.seconds + \
                            steps_time.days * 3600 * 24
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
        m = Modder(actions=[FileActions])
        for a in actions:
            m.modify(a["action"], a["file"])
        # Actions is being returned as None so that custodian will stop after
        # STOPCAR is written. We do not want subsequent jobs to proceed.
        return {"errors": ["Walltime reached"], "actions": None}

    def __str__(self):
        return "WalltimeHandler"


@deprecated(replacement=WalltimeHandler)
class PBSWalltimeHandler(WalltimeHandler):

    def __init__(self, buffer_time=300):
        WalltimeHandler.__init__(self, None, buffer_time=buffer_time)


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
    stored in subdirs chk_#. This should be used in combiantion with the
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

    def __str__(self):
        return "StoppedRunHandler"


class BadVasprunXMLHandler(ErrorHandler):
    """
    Handler to properly terminate a run when a bad vasprun.xml is found.
    """

    is_monitor = False

    is_terminating = True

    def __init__(self):
        self.vasprunxml = None
        pass

    def check(self):
        try:
            self.vasprunxml = _get_vasprun()
            v = Vasprun(self.vasprunxml)
        except:
            return True
        return False

    def correct(self):
        return {"errors": ["Bad vasprun.xml in %s." % self.vasprunxml],
                "actions": None}

    def __str__(self):
        return "BadVasprunXMLHandler"


def _get_vasprun(path="."):
    vaspruns = glob.glob(os.path.join(path, "vasprun.xml*"))
    return sorted(vaspruns, reverse=True)[0] if vaspruns else None