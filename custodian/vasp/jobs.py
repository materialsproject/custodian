# coding: utf-8

from __future__ import unicode_literals, division

"""
This module implements basic kinds of jobs for VASP runs.
"""

import subprocess
import os
import shutil
import math
import logging
import numpy as np

from pymatgen.io.vasp import VaspInput, Incar, Poscar, Outcar, Kpoints
from monty.os.path import which

from custodian.custodian import Job
from custodian.vasp.interpreter import VaspModder


__author__ = "Shyue Ping Ong"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__status__ = "Beta"
__date__ = "2/4/13"


VASP_INPUT_FILES = {"INCAR", "POSCAR", "POTCAR", "KPOINTS"}

VASP_OUTPUT_FILES = ['DOSCAR', 'INCAR', 'KPOINTS', 'POSCAR', 'PROCAR',
                     'vasprun.xml', 'CHGCAR', 'CHG', 'EIGENVAL', 'OSZICAR',
                     'WAVECAR', 'CONTCAR', 'IBZKPT', 'OUTCAR']


class VaspJob(Job):
    """
    A basic vasp job. Just runs whatever is in the directory. But conceivably
    can be a complex processing of inputs etc. with initialization.
    """

    def __init__(self, vasp_cmd, output_file="vasp.out", stderr_file="std_err.txt",
                 suffix="", final=True, backup=True, auto_npar=True,
                 auto_gamma=True, settings_override=None,
                 gamma_vasp_cmd=None, copy_magmom=False,auto_continue=False):
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
            output_file (str): Name of file to direct standard error to.
                Defaults to "std_err.txt".
            suffix (str): A suffix to be appended to the final output. E.g.,
                to rename all VASP output from say vasp.out to
                vasp.out.relax1, provide ".relax1" as the suffix.
            final (bool): Indicating whether this is the final vasp job in a
                series. Defaults to True.
            backup (bool): Whether to backup the initial input files. If True,
                the INCAR, KPOINTS, POSCAR and POTCAR will be copied with a
                ".orig" appended. Defaults to True.
            default_vasp_input_set (VaspInputSet): Species the default input
                set (see pymatgen's documentation in pymatgen.io.vasp.sets to
                use for directories that do not contain full set of VASP
                input files. For example, if a directory contains only a
                POSCAR or a cif, the vasp input set will be used to generate
                the necessary input files for the run. If the directory already
                contain a full set of VASP input files,
                this input is ignored. Defaults to the MITVaspInputSet.
            auto_npar (bool): Whether to automatically tune NPAR to be sqrt(
                number of cores) as recommended by VASP for DFT calculations.
                Generally, this results in significant speedups. Defaults to
                True. Set to False for HF, GW and RPA calculations.
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
                if a STOPCAR is present. This is very usefull if using the
                wall-time handler which will write a read-only STOPCAR to
                prevent VASP from deleting it once it finishes
        """
        self.vasp_cmd = vasp_cmd
        self.output_file = output_file
        self.stderr_file = stderr_file
        self.final = final
        self.backup = backup
        self.suffix = suffix
        self.settings_override = settings_override
        self.auto_npar = auto_npar
        self.auto_gamma = auto_gamma
        self.gamma_vasp_cmd = gamma_vasp_cmd
        self.copy_magmom = copy_magmom
        self.auto_continue = auto_continue

    def setup(self):
        """
        Performs initial setup for VaspJob, including overriding any settings
        and backing up.
        """

        if self.backup:
            for f in VASP_INPUT_FILES:
                shutil.copy(f, "{}.orig".format(f))

        if self.auto_npar:
            try:
                incar = Incar.from_file("INCAR")
                # Only optimized NPAR for non-HF and non-RPA calculations.
                if not (incar.get("LHFCALC") or incar.get("LRPA") or
                        incar.get("LEPSILON")):
                    if incar.get("IBRION") in [5, 6, 7, 8]:
                        # NPAR should not be set for Hessian matrix
                        # calculations, whether in DFPT or otherwise.
                        del incar["NPAR"]
                    else:
                        import multiprocessing
                        # try sge environment variable first
                        # (since multiprocessing counts cores on the current
                        # machine only)
                        ncores = os.environ.get('NSLOTS') or multiprocessing.cpu_count()
                        ncores = int(ncores)
                        for npar in range(int(math.sqrt(ncores)),
                                          ncores):
                            if ncores % npar == 0:
                                incar["NPAR"] = npar
                                break
                    incar.write_file("INCAR")
            except:
                pass

        # Auto continue if a read-only STOPCAR is present
        if self.auto_continue and \
           os.path.exists("STOPCAR") and \
           not os.access("STOPCAR",os.W_OK):
            # Remove STOPCAR
            os.chmod("STOPCAR",0o644)
            os.remove("STOPCAR")

            # Setup INCAR to continue
            incar = Incar.from_file("INCAR")
            incar['ISTART'] = 1
            incar.write_file("INCAR")

            shutil.copy('CONTCAR','POSCAR')

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
            if kpts.style == Kpoints.supported_modes.Gamma \
                    and tuple(kpts.kpts[0]) == (1, 1, 1):
                if self.gamma_vasp_cmd is not None and which(
                        self.gamma_vasp_cmd[-1]):
                    cmd = self.gamma_vasp_cmd
                elif which(cmd[-1] + ".gamma"):
                    cmd[-1] += ".gamma"
        logging.info("Running {}".format(" ".join(cmd)))
        with open(self.output_file, 'w') as f_std, \
                open(self.stderr_file, "w", buffering=1) as f_err:
            # use line bufferring for stderr
            p = subprocess.Popen(cmd, stdout=f_std, stderr=f_err)
        return p

    def postprocess(self):
        """
        Postprocessing includes renaming and gzipping where necessary.
        Also copies the magmom to the incar if necessary
        """
        for f in VASP_OUTPUT_FILES + [self.output_file]:
            if os.path.exists(f):
                if self.final and self.suffix != "":
                    shutil.move(f, "{}{}".format(f, self.suffix))
                elif self.suffix != "":
                    shutil.copy(f, "{}{}".format(f, self.suffix))

        if self.copy_magmom and not self.final:
            try:
                outcar = Outcar("OUTCAR")
                magmom = [m['tot'] for m in outcar.magnetization]
                incar = Incar.from_file("INCAR")
                incar['MAGMOM'] = magmom
                incar.write_file("INCAR")
            except:
                logging.error('MAGMOM copy from OUTCAR to INCAR failed')

    @classmethod
    def double_relaxation_run(cls, vasp_cmd, auto_npar=True, ediffg=-0.05,
                              half_kpts_first_relax=False):
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
            half_kpt_first_relax (bool): Whether to halve the kpoint grid
                for the first relaxation. Speeds up difficult convergence
                considerably. Defaults to False.

        Returns:
            List of two jobs corresponding to an AFLOW style run.
        """
        incar_update = {"ISTART": 1}
        if ediffg:
            incar_update["EDIFFG"] = ediffg
        settings_overide_1 = None
        settings_overide_2  = [
            {"dict": "INCAR",
             "action": {"_set": incar_update}},
            {"file": "CONTCAR",
             "action": {"_file_copy": {"dest": "POSCAR"}}}]
        if half_kpts_first_relax and os.path.exists("KPOINTS") and \
                os.path.exists("POSCAR"):
            kpts = Kpoints.from_file("KPOINTS")
            orig_kpts_dict = kpts.as_dict()
            # lattice vectors with length < 8 will get >1 KPOINT
            kpts.kpts = np.round(np.maximum(np.array(kpts.kpts) / 2,
                                            1)).astype(int).tolist()
            low_kpts_dict = kpts.as_dict()
            settings_overide_1 = [
                {"dict": "KPOINTS",
                 "action": {"_set": low_kpts_dict}}
            ]
            settings_overide_2.append(
                {"dict": "KPOINTS",
                 "action": {"_set": orig_kpts_dict}}
            )

        return [VaspJob(vasp_cmd, final=False, suffix=".relax1",
                        auto_npar=auto_npar,
                        settings_override=settings_overide_1),
                VaspJob(vasp_cmd, final=True, backup=False, suffix=".relax2",
                        auto_npar=auto_npar,
                        settings_override=settings_overide_2)]

    @classmethod
    def full_opt_run(cls, vasp_cmd, auto_npar=True, vol_change_tol=0.02,
                     max_steps=10, ediffg=-0.05, half_kpts_first_relax=False):
        """
        Returns a generator of jobs for a full optimization run. Basically,
        this runs an infinite series of geometry optimization jobs until the
        % vol change in a particular optimization is less than vol_change_tol.

        Args:
            vasp_cmd (str): Command to run vasp as a list of args. For example,
                if you are using mpirun, it can be something like
                ["mpirun", "pvasp.5.2.11"]
            auto_npar (bool): Whether to automatically tune NPAR to be sqrt(
                number of cores) as recommended by VASP for DFT calculations.
                Generally, this results in significant speedups. Defaults to
                True. Set to False for HF, GW and RPA calculations.
            vol_change_tol (float): The tolerance at which to stop a run.
                Defaults to 0.05, i.e., 5%.
            max_steps (int): The maximum number of runs. Defaults to 10 (
                highly unlikely that this limit is ever reached).
            ediffg (float): Force convergence criteria for subsequent runs (
                ignored for the initial run.)
            half_kpts_first_relax (bool): Whether to halve the kpoint grid
                for the first relaxation. Speeds up difficult convergence
                considerably. Defaults to False.

        Returns:
            Generator of jobs.
        """
        for i in range(max_steps):
            if i == 0:
                settings = None
                backup = True
                if half_kpts_first_relax and os.path.exists("KPOINTS") and \
                        os.path.exists("POSCAR"):
                    kpts = Kpoints.from_file("KPOINTS")
                    orig_kpts_dict = kpts.as_dict()
                    kpts.kpts = np.maximum(np.array(kpts.kpts) / 2, 1).tolist()
                    low_kpts_dict = kpts.as_dict()
                    settings = [
                        {"dict": "KPOINTS",
                         "action": {"_set": low_kpts_dict}}
                    ]
            else:
                backup = False
                initial = Poscar.from_file("POSCAR").structure
                final = Poscar.from_file("CONTCAR").structure
                vol_change = (final.volume - initial.volume) / initial.volume

                logging.info("Vol change = %.1f %%!" % (vol_change * 100))
                if abs(vol_change) < vol_change_tol:
                    logging.info("Stopping optimization!")
                    break
                else:
                    incar_update = {"ISTART": 1}
                    if ediffg:
                        incar_update["EDIFFG"] = ediffg
                    settings = [
                        {"dict": "INCAR",
                         "action": {"_set": incar_update}},
                        {"file": "CONTCAR",
                         "action": {"_file_copy": {"dest": "POSCAR"}}}]
                    if i == 1 and half_kpts_first_relax:
                        settings.append({"dict": "KPOINTS",
                                         "action": {"_set": orig_kpts_dict}})
            logging.info("Generating job = %d!" % (i+1))
            yield VaspJob(vasp_cmd, final=False, backup=backup,
                          suffix=".relax%d" % (i+1), auto_npar=auto_npar,
                          settings_override=settings)

    def as_dict(self):
        d = dict(vasp_cmd=self.vasp_cmd,
                 output_file=self.output_file, suffix=self.suffix,
                 final=self.final, backup=self.backup,
                 auto_npar=self.auto_npar, auto_gamma=self.auto_gamma,
                 settings_override=self.settings_override,
                 gamma_vasp_cmd=self.gamma_vasp_cmd
                 )
        d["@module"] = self.__class__.__module__
        d["@class"] = self.__class__.__name__
        return d

    @classmethod
    def from_dict(cls, d):
        return VaspJob(
            vasp_cmd=d["vasp_cmd"], output_file=d["output_file"],
            suffix=d["suffix"], final=d["final"],
            backup=d["backup"],
            auto_npar=d['auto_npar'], auto_gamma=d['auto_gamma'],
            settings_override=d["settings_override"],
            gamma_vasp_cmd=d["gamma_vasp_cmd"])
