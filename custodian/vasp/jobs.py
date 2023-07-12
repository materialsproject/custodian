"""
This module implements basic kinds of jobs for VASP runs.
"""

import logging
import math
import os
import shutil
import subprocess
from shutil import which

import numpy as np
import psutil
from monty.serialization import dumpfn, loadfn
from monty.shutil import decompress_dir
from pymatgen.core.structure import Structure
from pymatgen.io.vasp.inputs import Incar, Kpoints, Poscar, VaspInput
from pymatgen.io.vasp.outputs import Outcar, Vasprun

from custodian.custodian import SENTRY_DSN, Job
from custodian.utils import backup
from custodian.vasp.handlers import VASP_BACKUP_FILES
from custodian.vasp.interpreter import VaspModder

logger = logging.getLogger(__name__)


VASP_INPUT_FILES = {"INCAR", "POSCAR", "POTCAR", "KPOINTS"}

VASP_OUTPUT_FILES = [
    "DOSCAR",
    "INCAR",
    "KPOINTS",
    "POSCAR",
    "PROCAR",
    "vasprun.xml",
    "CHGCAR",
    "CHG",
    "EIGENVAL",
    "OSZICAR",
    "WAVECAR",
    "CONTCAR",
    "IBZKPT",
    "OUTCAR",
]

VASP_NEB_INPUT_FILES = {"INCAR", "POTCAR", "KPOINTS"}

VASP_NEB_OUTPUT_FILES = ["INCAR", "KPOINTS", "POTCAR", "vasprun.xml"]

VASP_NEB_OUTPUT_SUB_FILES = [
    "CHG",
    "CHGCAR",
    "CONTCAR",
    "DOSCAR",
    "EIGENVAL",
    "IBZKPT",
    "PCDAT",
    "POSCAR",
    "REPORT",
    "PROCAR",
    "OSZICAR",
    "OUTCAR",
    "WAVECAR",
    "XDATCAR",
]


class VaspJob(Job):
    """
    A basic vasp job. Just runs whatever is in the directory. But conceivably
    can be a complex processing of inputs etc. with initialization.
    """

    def __init__(
        self,
        vasp_cmd,
        output_file="vasp.out",
        stderr_file="std_err.txt",
        suffix="",
        final=True,
        backup=True,
        auto_npar=False,
        auto_gamma=True,
        settings_override=None,
        gamma_vasp_cmd=None,
        copy_magmom=False,
        auto_continue=False,
    ):
        """
        This constructor is necessarily complex due to the need for
        flexibility. For standard kinds of runs, it's often better to use one
        of the static constructors. The defaults are usually fine too.

        Args:
            vasp_cmd (str): Command to run vasp as a list of args. For example,
                if you are using mpirun, it can be something like
                ["mpirun", "pvasp.5.2.11"]
            output_file (str): Name of file to direct standard out to.
                Defaults to "vasp.out".
            stderr_file (str): Name of file to direct standard error to.
                Defaults to "std_err.txt".
            suffix (str): A suffix to be appended to the final output. E.g.,
                to rename all VASP output from say vasp.out to
                vasp.out.relax1, provide ".relax1" as the suffix.
            final (bool): Indicating whether this is the final vasp job in a
                series. Defaults to True.
            backup (bool): Whether to backup the initial input files. If True,
                the INCAR, KPOINTS, POSCAR and POTCAR will be copied with a
                ".orig" appended. Defaults to True.
            auto_npar (bool): Whether to automatically tune NPAR to be sqrt(
                number of cores) as recommended by VASP for DFT calculations.
                Generally, this results in significant speedups. Defaults to
                False. Set to False for HF, GW and RPA calculations.
            auto_gamma (bool): Whether to automatically check if run is a
                Gamma 1x1x1 run, and whether a Gamma optimized version of
                VASP exists with ".gamma" appended to the name of the VASP
                executable (typical setup in many systems). If so, run the
                gamma optimized version of VASP instead of regular VASP. You
                can also specify the gamma vasp command using the
                gamma_vasp_cmd argument if the command is named differently.
            settings_override ([dict]): An ansible style list of dict to
                override changes. For example, to set ISTART=1 for subsequent
                runs and to copy the CONTCAR to the POSCAR, you will provide::

                    [{"dict": "INCAR", "action": {"_set": {"ISTART": 1}}},
                     {"file": "CONTCAR",
                      "action": {"_file_copy": {"dest": "POSCAR"}}}]
            gamma_vasp_cmd (str): Command for gamma vasp version when
                auto_gamma is True. Should follow the list style of
                subprocess. Defaults to None, which means ".gamma" is added
                to the last argument of the standard vasp_cmd.
            copy_magmom (bool): Whether to copy the final magmom from the
                OUTCAR to the next INCAR. Useful for multi-relaxation runs
                where the CHGCAR and WAVECAR are sometimes deleted (due to
                changes in fft grid, etc.). Only applies to non-final runs.
            auto_continue (bool): Whether to automatically continue a run
                if a STOPCAR is present. This is very useful if using the
                wall-time handler which will write a read-only STOPCAR to
                prevent VASP from deleting it once it finishes
        """
        self.vasp_cmd = tuple(vasp_cmd)
        self.output_file = output_file
        self.stderr_file = stderr_file
        self.final = final
        self.backup = backup
        self.suffix = suffix
        self.settings_override = settings_override
        self.auto_npar = auto_npar
        self.auto_gamma = auto_gamma
        self.gamma_vasp_cmd = tuple(gamma_vasp_cmd) if gamma_vasp_cmd else None
        self.copy_magmom = copy_magmom
        self.auto_continue = auto_continue

        if SENTRY_DSN:
            # if using Sentry logging, add specific VASP executable to scope
            from sentry_sdk import configure_scope

            with configure_scope() as scope:
                try:
                    if isinstance(vasp_cmd, str):
                        vasp_path = which(vasp_cmd.split(" ")[-1])
                    elif isinstance(vasp_cmd, list):
                        vasp_path = which(vasp_cmd[-1])
                    scope.set_tag("vasp_path", vasp_path)
                    scope.set_tag("vasp_cmd", vasp_cmd)
                except Exception:
                    logger.error(f"Failed to detect VASP path: {vasp_cmd}", exc_info=True)
                    scope.set_tag("vasp_cmd", vasp_cmd)

    def setup(self):
        """
        Performs initial setup for VaspJob, including overriding any settings
        and backing up.
        """
        decompress_dir(".")

        if self.backup:
            for f in VASP_INPUT_FILES:
                try:
                    shutil.copy(f, f"{f}.orig")
                except FileNotFoundError:  # handle the situation when there is no KPOINTS file
                    if f == "KPOINTS":
                        pass

        if self.auto_npar:
            try:
                incar = Incar.from_file("INCAR")
                # Only optimized NPAR for non-HF and non-RPA calculations.
                if not (incar.get("LHFCALC") or incar.get("LRPA") or incar.get("LEPSILON")):
                    if incar.get("IBRION") in [5, 6, 7, 8]:
                        # NPAR should not be set for Hessian matrix
                        # calculations, whether in DFPT or otherwise.
                        del incar["NPAR"]
                    else:
                        import multiprocessing

                        # try sge environment variable first
                        # (since multiprocessing counts cores on the current
                        # machine only)
                        ncores = os.environ.get("NSLOTS") or multiprocessing.cpu_count()
                        ncores = int(ncores)
                        for npar in range(int(math.sqrt(ncores)), ncores):
                            if ncores % npar == 0:
                                incar["NPAR"] = npar
                                break
                    incar.write_file("INCAR")
            except Exception:
                pass

        if self.auto_continue:
            if os.path.exists("continue.json"):
                actions = loadfn("continue.json").get("actions")
                logger.info(f"Continuing previous VaspJob. Actions: {actions}")
                backup(VASP_BACKUP_FILES, prefix="prev_run")
                VaspModder().apply_actions(actions)

            else:
                # Default functionality is to copy CONTCAR to POSCAR and set
                # ISTART to 1 in the INCAR, but other actions can be specified
                if self.auto_continue is True:
                    actions = [
                        {
                            "file": "CONTCAR",
                            "action": {"_file_copy": {"dest": "POSCAR"}},
                        },
                        {"dict": "INCAR", "action": {"_set": {"ISTART": 1}}},
                    ]
                else:
                    actions = self.auto_continue
                dumpfn({"actions": actions}, "continue.json")

        if self.settings_override is not None:
            VaspModder().apply_actions(self.settings_override)

    def run(self):
        """
        Perform the actual VASP run.

        Returns:
            (subprocess.Popen) Used for monitoring.
        """
        cmd = list(self.vasp_cmd)
        if self.auto_gamma:
            vi = VaspInput.from_directory(".")
            kpts = vi["KPOINTS"]
            if kpts is not None:
                if kpts.style == Kpoints.supported_modes.Gamma and tuple(kpts.kpts[0]) == (1, 1, 1):
                    if self.gamma_vasp_cmd is not None and which(self.gamma_vasp_cmd[-1]):  # pylint: disable=E1136
                        cmd = self.gamma_vasp_cmd
                    elif which(cmd[-1] + ".gamma"):
                        cmd[-1] += ".gamma"
        logger.info(f"Running {' '.join(cmd)}")
        with open(self.output_file, "w") as f_std, open(self.stderr_file, "w", buffering=1) as f_err:
            # use line buffering for stderr
            return subprocess.Popen(cmd, stdout=f_std, stderr=f_err, start_new_session=True)  # pylint: disable=R1732

    def postprocess(self):
        """
        Postprocessing includes renaming and gzipping where necessary.
        Also copies the magmom to the incar if necessary
        """
        for f in VASP_OUTPUT_FILES + [self.output_file]:
            if os.path.exists(f):
                if self.final and self.suffix != "":
                    shutil.move(f, f"{f}{self.suffix}")
                elif self.suffix != "":
                    shutil.copy(f, f"{f}{self.suffix}")

        if self.copy_magmom and not self.final:
            try:
                outcar = Outcar("OUTCAR")
                magmom = [m["tot"] for m in outcar.magnetization]
                incar = Incar.from_file("INCAR")
                incar["MAGMOM"] = magmom
                incar.write_file("INCAR")
            except Exception:
                logger.error("MAGMOM copy from OUTCAR to INCAR failed")

        # Remove continuation so if a subsequent job is run in
        # the same directory, will not restart this job.
        if os.path.exists("continue.json"):
            os.remove("continue.json")

    @classmethod
    def double_relaxation_run(
        cls,
        vasp_cmd,
        auto_npar=True,
        ediffg=-0.05,
        half_kpts_first_relax=False,
        auto_continue=False,
    ):
        """
        Returns a list of two jobs corresponding to an AFLOW style double
        relaxation run.

        Args:
            vasp_cmd (str): Command to run vasp as a list of args. For example,
                if you are using mpirun, it can be something like
                ["mpirun", "pvasp.5.2.11"]
            auto_npar (bool): Whether to automatically tune NPAR to be sqrt(
                number of cores) as recommended by VASP for DFT calculations.
                Generally, this results in significant speedups. Defaults to
                True. Set to False for HF, GW and RPA calculations.
            ediffg (float): Force convergence criteria for subsequent runs (
                ignored for the initial run.)
            half_kpts_first_relax (bool): Whether to halve the kpoint grid
                for the first relaxation. Speeds up difficult convergence
                considerably. Defaults to False.
            auto_continue (bool): Whether to automatically continue a run
                if a STOPCAR is present. This is very useful if using the
                wall-time handler which will write a read-only STOPCAR to
                prevent VASP from deleting it once it finishes. Defaults to
                False.

        Returns:
            List of two jobs corresponding to an AFLOW style run.
        """
        incar_update = {"ISTART": 1}
        if ediffg:
            incar_update["EDIFFG"] = ediffg
        settings_overide_1 = None
        settings_overide_2 = [
            {"dict": "INCAR", "action": {"_set": incar_update}},
            {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}},
        ]
        if half_kpts_first_relax and os.path.exists("KPOINTS") and os.path.exists("POSCAR"):
            kpts = Kpoints.from_file("KPOINTS")
            orig_kpts_dict = kpts.as_dict()
            # lattice vectors with length < 8 will get >1 KPOINT
            kpts.kpts = np.round(np.maximum(np.array(kpts.kpts) / 2, 1)).astype(int).tolist()
            low_kpts_dict = kpts.as_dict()
            settings_overide_1 = [{"dict": "KPOINTS", "action": {"_set": low_kpts_dict}}]
            settings_overide_2.append({"dict": "KPOINTS", "action": {"_set": orig_kpts_dict}})

        return [
            VaspJob(
                vasp_cmd,
                final=False,
                suffix=".relax1",
                auto_npar=auto_npar,
                auto_continue=auto_continue,
                settings_override=settings_overide_1,
            ),
            VaspJob(
                vasp_cmd,
                final=True,
                backup=False,
                suffix=".relax2",
                auto_npar=auto_npar,
                auto_continue=auto_continue,
                settings_override=settings_overide_2,
            ),
        ]

    @classmethod
    def metagga_opt_run(
        cls,
        vasp_cmd,
        auto_npar=True,
        ediffg=-0.05,
        half_kpts_first_relax=False,
        auto_continue=False,
    ):
        """
        Returns a list of thres jobs to perform an optimization for any
        metaGGA functional. There is an initial calculation of the
        GGA wavefunction which is fed into the initial metaGGA optimization
        to precondition the electronic structure optimizer. The metaGGA
        optimization is performed using the double relaxation scheme
        """

        incar = Incar.from_file("INCAR")
        # Defaults to using the SCAN metaGGA
        metaGGA = incar.get("METAGGA", "SCAN")

        # Pre optimize WAVECAR and structure using regular GGA
        pre_opt_setings = [
            {
                "dict": "INCAR",
                "action": {"_set": {"METAGGA": None, "LWAVE": True, "NSW": 0}},
            }
        ]
        jobs = [
            VaspJob(
                vasp_cmd,
                auto_npar=auto_npar,
                final=False,
                suffix=".precondition",
                settings_override=pre_opt_setings,
            )
        ]

        # Finish with regular double relaxation style run using SCAN
        jobs.extend(
            VaspJob.double_relaxation_run(
                vasp_cmd,
                auto_npar=auto_npar,
                ediffg=ediffg,
                half_kpts_first_relax=half_kpts_first_relax,
            )
        )

        # Ensure the first relaxation doesn't overwrite the original inputs
        jobs[1].backup = False

        # Update double_relaxation job to start from pre-optimized run
        post_opt_settings = [
            {
                "dict": "INCAR",
                "action": {
                    "_set": {
                        "METAGGA": metaGGA,
                        "ISTART": 1,
                        "NSW": incar.get("NSW", 99),
                        "LWAVE": incar.get("LWAVE", False),
                    }
                },
            },
            {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}},
        ]
        if jobs[1].settings_override:
            post_opt_settings = jobs[1].settings_override + post_opt_settings
        jobs[1].settings_override = post_opt_settings

        return jobs

    @classmethod
    def full_opt_run(
        cls, vasp_cmd, vol_change_tol=0.02, max_steps=10, ediffg=-0.05, half_kpts_first_relax=False, **vasp_job_kwargs
    ):
        r"""
        Returns a generator of jobs for a full optimization run. Basically,
        this runs an infinite series of geometry optimization jobs until the
        % vol change in a particular optimization is less than vol_change_tol.

        Args:
            vasp_cmd (str): Command to run vasp as a list of args. For example,
                if you are using mpirun, it can be something like
                ["mpirun", "pvasp.5.2.11"]
            vol_change_tol (float): The tolerance at which to stop a run.
                Defaults to 0.05, i.e., 5%.
            max_steps (int): The maximum number of runs. Defaults to 10 (
                highly unlikely that this limit is ever reached).
            ediffg (float): Force convergence criteria for subsequent runs (
                ignored for the initial run.)
            half_kpts_first_relax (bool): Whether to halve the kpoint grid
                for the first relaxation. Speeds up difficult convergence
                considerably. Defaults to False.
            \*\*vasp_job_kwargs: Passthrough kwargs to VaspJob. See
                :class:`custodian.vasp.jobs.VaspJob`.

        Returns:
            Generator of jobs.
        """
        for i in range(max_steps):
            if i == 0:
                settings = None
                backup = True
                if half_kpts_first_relax and os.path.exists("KPOINTS") and os.path.exists("POSCAR"):
                    kpts = Kpoints.from_file("KPOINTS")
                    orig_kpts_dict = kpts.as_dict()
                    kpts.kpts = np.maximum(np.array(kpts.kpts) / 2, 1).tolist()
                    low_kpts_dict = kpts.as_dict()
                    settings = [{"dict": "KPOINTS", "action": {"_set": low_kpts_dict}}]
            else:
                backup = False
                initial = Poscar.from_file("POSCAR").structure
                final = Poscar.from_file("CONTCAR").structure
                vol_change = (final.volume - initial.volume) / initial.volume

                logger.info(f"Vol change = {vol_change:.1%}!")
                if abs(vol_change) < vol_change_tol:
                    logger.info("Stopping optimization!")
                    break
                incar_update = {"ISTART": 1}
                if ediffg:
                    incar_update["EDIFFG"] = ediffg
                settings = [
                    {"dict": "INCAR", "action": {"_set": incar_update}},
                    {
                        "file": "CONTCAR",
                        "action": {"_file_copy": {"dest": "POSCAR"}},
                    },
                ]
                if i == 1 and half_kpts_first_relax:
                    settings.append({"dict": "KPOINTS", "action": {"_set": orig_kpts_dict}})
            logger.info(f"Generating job = {i + 1}!")
            yield VaspJob(
                vasp_cmd,
                final=False,
                backup=backup,
                suffix=f".relax{i + 1}",
                settings_override=settings,
                **vasp_job_kwargs,
            )

    @classmethod
    def constrained_opt_run(
        cls, vasp_cmd, lattice_direction, initial_strain, atom_relax=True, max_steps=20, algo="bfgs", **vasp_job_kwargs
    ):
        r"""
        Returns a generator of jobs for a constrained optimization run. Typical
        use case is when you want to approximate a biaxial strain situation,
        e.g., you apply a defined strain to a and b directions of the lattice,
        but allows the c-direction to relax.

        Some guidelines on the use of this method:
        i.  It is recommended you do not use the Auto kpoint generation. The
            grid generated via Auto may fluctuate with changes in lattice
            param, resulting in numerical noise.
        ii. Make sure your EDIFF/EDIFFG is properly set in your INCAR. The
            optimization relies on these values to determine convergence.

        Args:
            vasp_cmd (str): Command to run vasp as a list of args. For example,
                if you are using mpirun, it can be something like
                ["mpirun", "pvasp.5.2.11"]
            lattice_direction (str): Which direction to relax. Valid values are
                "a", "b" or "c".
            initial_strain (float): An initial strain to be applied to the
                lattice_direction. This can usually be estimated as the
                negative of the strain applied in the other two directions.
                E.g., if you apply a tensile strain of 0.05 to the a and b
                directions, you can use -0.05 as a reasonable first guess for
                initial strain.
            atom_relax (bool): Whether to relax atomic positions.
            max_steps (int): The maximum number of runs. Defaults to 20 (
                highly unlikely that this limit is ever reached).
            algo (str): Algorithm to use to find minimum. Default is "bfgs",
                which is fast, but can be sensitive to numerical noise
                in energy calculations. The alternative is "bisection",
                which is more robust but can be a bit slow. The code does fall
                back on the bisection when bfgs gives a non-sensical result,
                e.g., negative lattice params.
            \*\*vasp_job_kwargs: Passthrough kwargs to VaspJob. See
                :class:`custodian.vasp.jobs.VaspJob`.

        Returns:
            Generator of jobs. At the end of the run, an "EOS.txt" is written
            which provides a quick look at the E vs lattice parameter.
        """
        nsw = 99 if atom_relax else 0

        incar = Incar.from_file("INCAR")

        # Set the energy convergence criteria as the EDIFFG (if present) or
        # 10 x EDIFF (which itself defaults to 1e-4 if not present).
        if incar.get("EDIFFG") and incar.get("EDIFFG") > 0:
            etol = incar["EDIFFG"]
        else:
            etol = incar.get("EDIFF", 1e-4) * 10

        if lattice_direction == "a":
            lattice_index = 0
        elif lattice_direction == "b":
            lattice_index = 1
        else:
            lattice_index = 2

        energies = {}

        for i in range(max_steps):
            if i == 0:
                settings = [{"dict": "INCAR", "action": {"_set": {"ISIF": 2, "NSW": nsw}}}]
                structure = Poscar.from_file("POSCAR").structure
                x = structure.lattice.abc[lattice_index]
                backup = True
            else:
                backup = False
                v = Vasprun("vasprun.xml")
                structure = v.final_structure
                energy = v.final_energy
                lattice = structure.lattice

                x = lattice.abc[lattice_index]

                energies[x] = energy

                if i == 1:
                    x *= 1 + initial_strain
                else:
                    # Sort the lattice parameter by energies.
                    min_x = min(energies.keys(), key=lambda e: energies[e])
                    sorted_x = sorted(energies.keys())
                    ind = sorted_x.index(min_x)
                    if ind == 0:
                        other = ind + 1
                    elif ind == len(sorted_x) - 1:
                        other = ind - 1
                    else:
                        other = ind + 1 if energies[sorted_x[ind + 1]] < energies[sorted_x[ind - 1]] else ind - 1
                    if abs(energies[min_x] - energies[sorted_x[other]]) < etol:
                        logger.info(f"Stopping optimization! Final {lattice_direction} = {min_x}")
                        break

                    if ind == 0 and len(sorted_x) > 2:
                        # Lowest energy lies outside of range of lowest value.
                        # we decrease the lattice parameter in the next
                        # iteration to find a minimum. This applies only when
                        # there are at least 3 values.
                        x = sorted_x[0] - abs(sorted_x[1] - sorted_x[0])
                        logger.info(f"Lowest energy lies below bounds. Setting {lattice_direction} = {x}.")
                    elif ind == len(sorted_x) - 1 and len(sorted_x) > 2:
                        # Lowest energy lies outside of range of highest value.
                        # we increase the lattice parameter in the next
                        # iteration to find a minimum. This applies only when
                        # there are at least 3 values.
                        x = sorted_x[-1] + abs(sorted_x[-1] - sorted_x[-2])
                        logger.info(f"Lowest energy lies above bounds. Setting {lattice_direction} = {x}.")
                    else:
                        if algo.lower() == "bfgs" and len(sorted_x) >= 4:
                            try:
                                # If there are more than 4 data points, we will
                                # do a quadratic fit to accelerate convergence.
                                x1 = list(energies.keys())
                                y1 = [energies[j] for j in x1]
                                z1 = np.polyfit(x1, y1, 2)
                                pp = np.poly1d(z1)
                                from scipy.optimize import minimize

                                result = minimize(pp, min_x, bounds=[(sorted_x[0], sorted_x[-1])])
                                if (not result.success) or result.x[0] < 0:
                                    raise ValueError("Negative lattice constant!")
                                x = result.x[0]
                                logger.info(f"BFGS minimized {lattice_direction} = {x}.")
                            except ValueError as ex:
                                # Fall back on bisection algo if the bfgs fails.
                                logger.info(str(ex))
                                x = (min_x + sorted_x[other]) / 2
                                logger.info(f"Falling back on bisection {lattice_direction} = {x}.")
                        else:
                            x = (min_x + sorted_x[other]) / 2
                            logger.info(f"Bisection {lattice_direction} = {x}.")

                lattice = lattice.matrix
                lattice[lattice_index] = lattice[lattice_index] / np.linalg.norm(lattice[lattice_index]) * x

                s = Structure(lattice, structure.species, structure.frac_coords)
                fname = f"POSCAR.{x}"
                s.to(filename=fname)

                incar_update = {"ISTART": 1, "NSW": nsw, "ISIF": 2}

                settings = [
                    {"dict": "INCAR", "action": {"_set": incar_update}},
                    {"file": fname, "action": {"_file_copy": {"dest": "POSCAR"}}},
                ]

            logger.info(f"Generating job = {i + 1} with parameter {x}!")
            yield VaspJob(
                vasp_cmd,
                final=False,
                backup=backup,
                suffix=f".static.{x}",
                settings_override=settings,
                **vasp_job_kwargs,
            )

        with open("EOS.txt", "w") as f:
            f.write(f"# {lattice_direction} energy\n")
            for k in sorted(energies.keys()):
                f.write(f"{k} {energies[k]}\n")

    def terminate(self):
        """
        Kill all VASP processes associated with the current job.
        This is done by looping over all processes and selecting the ones
        that contain "vasp" as well as access files (vasprun.xml in particular)
        in the custodian working directory.
        There is also a safety that kills all VASP processes if none of the
        processes can be killed (This is bad if more than one VASP runs are
        simultaneously executed on the same node). However, this should never
        happen.
        """
        workdir = os.getcwd()
        logger.info(f"Killing VASP processes in workdir {workdir}.")
        for proc in psutil.process_iter():
            try:
                if "vasp" in proc.name().lower():
                    open_paths = [file.path for file in proc.open_files()]
                    vasprun_path = os.path.join(workdir, "vasprun.xml")
                    if (vasprun_path in open_paths) and psutil.pid_exists(proc.pid):
                        proc.kill()
                        return
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.warning(f"Exception {e} encountered while killing VASP.")
                continue

        logger.warning(
            f"Killing VASP processes in workdir {workdir} failed with subprocess.Popen.terminate(). "
            "Resorting to 'killall'."
        )
        cmds = self.vasp_cmd
        if self.gamma_vasp_cmd:
            cmds += self.gamma_vasp_cmd
        for k in cmds:
            if "vasp" in k:
                subprocess.run(["killall", f"{k}"])


class VaspNEBJob(VaspJob):
    """
    A NEB vasp job, especially for CI-NEB running at PBS clusters.
    The class is added for the purpose of handling a different folder
    arrangement in NEB calculation.
    """

    def __init__(
        self,
        vasp_cmd,
        output_file="neb_vasp.out",
        stderr_file="neb_std_err.txt",
        suffix="",
        final=True,
        backup=True,
        auto_npar=True,
        half_kpts=False,
        auto_gamma=True,
        auto_continue=False,
        gamma_vasp_cmd=None,
        settings_override=None,
    ):
        """
        This constructor is a simplified version of VaspJob, which satisfies
        the need for flexibility. For standard kinds of runs, it's often
        better to use one of the static constructors. The defaults are
        usually fine too.

        Args:
            vasp_cmd (str): Command to run vasp as a list of args. For example,
                if you are using mpirun, it can be something like
                ["mpirun", "pvasp.5.2.11"]
            output_file (str): Name of file to direct standard out to.
                Defaults to "vasp.out".
            stderr_file (str): Name of file to direct standard error to.
                Defaults to "std_err.txt".
            suffix (str): A suffix to be appended to the final output. E.g.,
                to rename all VASP output from say vasp.out to
                vasp.out.relax1, provide ".relax1" as the suffix.
            final (bool): Indicating whether this is the final vasp job in a
                series. Defaults to True.
            backup (bool): Whether to backup the initial input files. If True,
                the INCAR, KPOINTS, POSCAR and POTCAR will be copied with a
                ".orig" appended. Defaults to True.
            auto_npar (bool): Whether to automatically tune NPAR to be sqrt(
                number of cores) as recommended by VASP for DFT calculations.
                Generally, this results in significant speedups. Defaults to
                True. Set to False for HF, GW and RPA calculations.
            half_kpts (bool): Whether to halve the kpoint grid for NEB.
                Speeds up convergence considerably. Defaults to False.
            auto_gamma (bool): Whether to automatically check if run is a
                Gamma 1x1x1 run, and whether a Gamma optimized version of
                VASP exists with ".gamma" appended to the name of the VASP
                executable (typical setup in many systems). If so, run the
                gamma optimized version of VASP instead of regular VASP. You
                can also specify the gamma vasp command using the
                gamma_vasp_cmd argument if the command is named differently.
            auto_continue (bool): Whether to automatically continue a run
                if a STOPCAR is present. This is very useful if using the
                wall-time handler which will write a read-only STOPCAR to
                prevent VASP from deleting it once it finishes.
            gamma_vasp_cmd (str): Command for gamma vasp version when
                auto_gamma is True. Should follow the list style of
                subprocess. Defaults to None, which means ".gamma" is added
                to the last argument of the standard vasp_cmd.
            settings_override ([dict]): An ansible style list of dict to
                override changes. For example, to set ISTART=1 for subsequent
                runs and to copy the CONTCAR to the POSCAR, you will provide::

                    [{"dict": "INCAR", "action": {"_set": {"ISTART": 1}}},
                     {"file": "CONTCAR",
                      "action": {"_file_copy": {"dest": "POSCAR"}}}]
        """

        self.vasp_cmd = tuple(vasp_cmd)
        self.output_file = output_file
        self.stderr_file = stderr_file
        self.final = final
        self.backup = backup
        self.suffix = suffix
        self.auto_npar = auto_npar
        self.half_kpts = half_kpts
        self.auto_gamma = auto_gamma
        self.gamma_vasp_cmd = tuple(gamma_vasp_cmd) if gamma_vasp_cmd else None
        self.auto_continue = auto_continue
        self.settings_override = settings_override
        self.neb_dirs = []  # 00, 01, etc.
        self.neb_sub = []  # 01, 02, etc.

        for path in os.listdir("."):
            if os.path.isdir(path) and path.isdigit():
                self.neb_dirs.append(path)
        self.neb_dirs = sorted(self.neb_dirs)
        self.neb_sub = self.neb_dirs[1:-1]

    def setup(self):
        """
        Performs initial setup for VaspNEBJob, including overriding any settings
        and backing up.
        """
        neb_dirs = self.neb_dirs

        if self.backup:
            # Back up KPOINTS, INCAR, POTCAR
            for f in VASP_NEB_INPUT_FILES:
                shutil.copy(f, f"{f}.orig")
            # Back up POSCARs
            for path in neb_dirs:
                poscar = os.path.join(path, "POSCAR")
                shutil.copy(poscar, f"{poscar}.orig")

        if self.half_kpts and os.path.exists("KPOINTS"):
            kpts = Kpoints.from_file("KPOINTS")
            kpts.kpts = np.maximum(np.array(kpts.kpts) / 2, 1)
            kpts.kpts = kpts.kpts.astype(int).tolist()
            if tuple(kpts.kpts[0]) == (1, 1, 1):
                kpt_dic = kpts.as_dict()
                kpt_dic["generation_style"] = "Gamma"
                kpts = Kpoints.from_dict(kpt_dic)
            kpts.write_file("KPOINTS")

        if self.auto_npar:
            try:
                incar = Incar.from_file("INCAR")
                import multiprocessing

                # Try sge environment variable first
                # (since multiprocessing counts cores on the current
                # machine only)
                ncores = os.environ.get("NSLOTS") or multiprocessing.cpu_count()
                ncores = int(ncores)
                for npar in range(int(math.sqrt(ncores)), ncores):
                    if ncores % npar == 0:
                        incar["NPAR"] = npar
                        break
                incar.write_file("INCAR")
            except Exception:
                pass

        if self.auto_continue and os.path.exists("STOPCAR") and not os.access("STOPCAR", os.W_OK):
            # Remove STOPCAR
            os.chmod("STOPCAR", 0o644)
            os.remove("STOPCAR")

            # Copy CONTCAR to POSCAR
            for path in self.neb_sub:
                contcar = os.path.join(path, "CONTCAR")
                poscar = os.path.join(path, "POSCAR")
                shutil.copy(contcar, poscar)

        if self.settings_override is not None:
            VaspModder().apply_actions(self.settings_override)

    def run(self):
        """
        Perform the actual VASP run.

        Returns:
            (subprocess.Popen) Used for monitoring.
        """
        cmd = list(self.vasp_cmd)
        if self.auto_gamma:
            kpts = Kpoints.from_file("KPOINTS")
            if kpts.style == Kpoints.supported_modes.Gamma and tuple(kpts.kpts[0]) == (
                1,
                1,
                1,
            ):
                if self.gamma_vasp_cmd is not None and which(self.gamma_vasp_cmd[-1]):  # pylint: disable=E1136
                    cmd = self.gamma_vasp_cmd
                elif which(cmd[-1] + ".gamma"):
                    cmd[-1] += ".gamma"
        logger.info(f"Running {' '.join(cmd)}")
        with open(self.output_file, "w") as f_std, open(self.stderr_file, "w", buffering=1) as f_err:
            # Use line buffering for stderr
            return subprocess.Popen(cmd, stdout=f_std, stderr=f_err, start_new_session=True)  # pylint: disable=R1732

    def postprocess(self):
        """
        Postprocessing includes renaming and gzipping where necessary.
        """
        # Add suffix to all sub_dir/{items}
        for path in self.neb_dirs:
            for f in VASP_NEB_OUTPUT_SUB_FILES:
                f = os.path.join(path, f)
                if os.path.exists(f):
                    if self.final and self.suffix != "":
                        shutil.move(f, f"{f}{self.suffix}")
                    elif self.suffix != "":
                        shutil.copy(f, f"{f}{self.suffix}")

        # Add suffix to all output files
        for f in VASP_NEB_OUTPUT_FILES + [self.output_file]:
            if os.path.exists(f):
                if self.final and self.suffix != "":
                    shutil.move(f, f"{f}{self.suffix}")
                elif self.suffix != "":
                    shutil.copy(f, f"{f}{self.suffix}")


class GenerateVaspInputJob(Job):
    """
    Generates a VASP input based on an existing directory. This is typically
    used to modify the VASP input files before the next VaspJob.
    """

    def __init__(self, input_set, contcar_only=True, **kwargs):
        """
        Args:
            input_set (str): Full path to the input set. E.g.,
                "pymatgen.io.vasp.sets.MPNonSCFSet".
            contcar_only (bool): If True (default), only CONTCAR structures
                are used as input to the input set.
        """
        self.input_set = input_set
        self.contcar_only = contcar_only
        self.kwargs = kwargs

    def setup(self):
        """
        Dummy setup
        """

    def run(self):
        """
        Run the calculation.
        """
        if os.path.exists("CONTCAR"):
            structure = Structure.from_file("CONTCAR")
        elif (not self.contcar_only) and os.path.exists("POSCAR"):
            structure = Structure.from_file("POSCAR")
        else:
            raise RuntimeError("No CONTCAR/POSCAR detected to generate input!")
        modname, classname = self.input_set.rsplit(".", 1)
        mod = __import__(modname, globals(), locals(), [classname], 0)
        vis = getattr(mod, classname)(structure, **self.kwargs)
        vis.write_input(".")

    def postprocess(self):
        """
        Dummy postprocess.
        """
