"""This module implements basic kinds of jobs for Cp2k runs."""

import logging
import os
import shutil
import subprocess

from monty.os.path import zpath
from monty.shutil import decompress_dir
from pymatgen.io.cp2k.inputs import Cp2kInput, Keyword

from custodian.cp2k.interpreter import Cp2kModder
from custodian.cp2k.utils import cleanup_input, restart
from custodian.custodian import Job

logger = logging.getLogger(__name__)

__author__ = "Nicholas Winner"
__version__ = "1.0"

CP2K_INPUT_FILES = ["cp2k.inp"]
CP2K_OUTPUT_FILES = ["cp2k.out"]


class Cp2kJob(Job):
    """
    A basic cp2k job. Just runs whatever is in the directory. But conceivably
    can be a complex processing of inputs etc. with initialization.
    """

    def __init__(
        self,
        cp2k_cmd,
        input_file="cp2k.inp",
        output_file="cp2k.out",
        stderr_file="std_err.txt",
        suffix="",
        final=True,
        backup=True,
        settings_override=None,
        restart=False,
    ):
        """
        This constructor is necessarily complex due to the need for
        flexibility. For standard kinds of runs, it's often better to use one
        of the static constructors. The defaults are usually fine too.

        Args:
            cp2k_cmd (list): Command to run cp2k as a list of args. For example,
                if you are using mpirun, it can be something like
                ["mpirun", "cp2k.popt"]
            input_file (str): Name of the file to use as input to CP2K
                executable. Defaults to "cp2k.inp"
            output_file (str): Name of file to direct standard out to.
                Defaults to "cp2k.out".
            stderr_file (str): Name of file to direct standard error to.
                Defaults to "std_err.txt".
            suffix (str): A suffix to be appended to the final output. E.g.,
                to rename all CP2K output from say cp2k.out to
                cp2k.out.relax1, provide ".relax1" as the suffix.
            final (bool): Indicating whether this is the final cp2k job in a
                series. Defaults to True.
            backup (bool): Whether to backup the initial input files. If True,
                the input file will be copied with a
                ".orig" appended. Defaults to True.
            settings_override ([actions]): A list of actions. See the Cp2kModder
                in interpreter.py
            restart (bool): Whether to run in restart mode, i.e. this a continuation of
                a previous calculation. Default is False.

        """
        self.cp2k_cmd = cp2k_cmd
        self.input_file = input_file
        self.ci = None
        self.output_file = output_file
        self.stderr_file = stderr_file
        self.final = final
        self.backup = backup
        self.suffix = suffix
        self.settings_override = settings_override if settings_override else []
        self.restart = restart

    def setup(self, directory="./"):
        """
        Performs initial setup for Cp2k in three stages. First, if custodian is running in restart mode, then
        the restart function will copy the restart file to self.input_file, and remove any previous WFN initialization
        if present. Second, any additional user specified settings will be applied. Lastly, a backup of the input
        file will be made for reference.
        """
        decompress_dir(directory)

        self.ci = Cp2kInput.from_file(zpath(os.path.join(directory, self.input_file)))
        cleanup_input(self.ci)

        if self.restart:
            restart(
                actions=self.settings_override,
                output_file=os.path.join(directory, self.output_file),
                input_file=os.path.join(directory, self.input_file),
                no_actions_needed=True,
            )

        if self.settings_override or self.restart:
            modder = Cp2kModder(filename=os.path.join(directory, self.input_file), actions=[], ci=self.ci)
            modder.apply_actions(self.settings_override)

        if self.backup:
            shutil.copy(os.path.join(directory, self.input_file), os.path.join(directory, f"{self.input_file}.orig"))

    def run(self, directory="./"):
        """
        Perform the actual CP2K run.

        Returns:
            (subprocess.Popen) Used for monitoring.
        """
        # TODO: cp2k has bizarre in/out streams. Some errors that should go to std_err are not sent anywhere...
        cmd = list(self.cp2k_cmd)
        cmd += ["-i", self.input_file]
        cmd_str = " ".join(cmd)
        logger.info(f"Running {cmd_str}")
        with (
            open(os.path.join(directory, self.output_file), "w") as f_std,
            open(os.path.join(directory, self.stderr_file), "w", buffering=1) as f_err,
        ):
            # use line buffering for stderr
            return subprocess.Popen(cmd, cwd=directory, stdout=f_std, stderr=f_err, shell=False)

    # TODO double jobs, file manipulations, etc. should be done in atomate in the future
    # and custodian should only run the job itself
    def postprocess(self, directory="./"):
        """Postprocessing includes renaming and gzipping where necessary."""
        files = os.listdir(directory)
        if os.path.isfile(self.output_file) and self.suffix != "":
            os.mkdir(f"run{self.suffix}")
            for file in files:
                if "json" in file:
                    continue
                if not os.path.isdir(os.path.join(directory, file)):
                    if self.final:
                        shutil.move(os.path.join(directory, file), os.path.join(directory, f"run{self.suffix}/{file}"))
                    else:
                        shutil.copy(os.path.join(directory, file), os.path.join(directory, f"run{self.suffix}/{file}"))

        # Remove continuation so if a subsequent job is run in
        # the same directory, will not restart this job.
        if os.path.isfile(os.path.join(directory, "continue.json")):
            os.remove(os.path.join(directory, "continue.json"))

    def terminate(self, directory="./"):
        """Terminate cp2k."""
        for cmd in self.cp2k_cmd:
            if "cp2k" in cmd:
                try:
                    os.system(f"killall {cmd}")
                except Exception:
                    pass

    @classmethod
    def gga_static_to_hybrid(
        cls,
        cp2k_cmd,
        input_file="cp2k.inp",
        output_file="cp2k.out",
        stderr_file="std_err.txt",
        backup=True,
        settings_override_gga=None,
        settings_override_hybrid=None,
        directory="./",
    ):
        """
        A bare GGA to hybrid calculation. Removes all unnecessary features
        from the GGA run, and making it only a ENERGY/ENERGY_FORCE
        depending on the hybrid run.
        """
        job1_settings_override = [
            {
                "dict": input_file,
                "action": {
                    "_unset": {"FORCE_EVAL": {"DFT": "XC"}},
                    "_set": {"GLOBAL": {"PROJECT_NAME": "GGA", "RUN_TYPE": "ENERGY_FORCE"}},
                },
            },
            {
                "dict": input_file,
                "action": {"_set": {"FORCE_EVAL": {"DFT": {"XC": {"XC_FUNCTIONAL": {"PBE": {}}}}}}},
            },
        ]

        job1 = Cp2kJob(
            cp2k_cmd,
            input_file=input_file,
            output_file=output_file,
            backup=backup,
            stderr_file=stderr_file,
            final=False,
            suffix="1",
            settings_override=job1_settings_override,
        )

        ci = Cp2kInput.from_file(zpath(os.path.join(directory, input_file)))
        run_type = ci["global"].get("run_type", Keyword("RUN_TYPE", "ENERGY_FORCE")).values[0]
        if run_type in {"ENERGY", "WAVEFUNCTION_OPTIMIZATION", "WFN_OPT", "ENERGY_FORCE"}:  # no need for double job
            return [job1]

        job2_settings_override = [
            {
                "dict": input_file,
                "action": {
                    "_set": {
                        "FORCE_EVAL": {
                            "DFT": {
                                "XC": {
                                    "HF": {
                                        "SCREENING": {
                                            "SCREEN_ON_INITIAL_P": True,
                                            "SCREEN_P_FORCES": True,
                                        }
                                    }
                                },
                                "WFN_RESTART_FILE_NAME": "GGA-RESTART.wfn",
                            }
                        },
                        "GLOBAL": {"RUN_TYPE": run_type},
                    },
                },
            }
        ]

        job2 = Cp2kJob(
            cp2k_cmd,
            input_file=input_file,
            output_file=output_file,
            backup=backup,
            stderr_file=stderr_file,
            final=True,
            suffix="2",
            restart=False,
            settings_override=job2_settings_override,
        )
        return [job1, job2]

    @classmethod
    def double_job(
        cls,
        cp2k_cmd,
        input_file="cp2k.inp",
        output_file="cp2k.out",
        stderr_file="std_err.txt",
        backup=True,
        directory="./",
    ):
        """
        This creates a sequence of two jobs. The first of which is an "initialization" of the
        wfn. Using this, the "restart" function can be exploited to determine if a diagonalization
        job can/would benefit from switching to OT scheme. If not, then the second job remains a
        diagonalization job, and there is minimal overhead from restarting.
        """
        job1 = Cp2kJob(
            cp2k_cmd,
            input_file=input_file,
            output_file=output_file,
            backup=backup,
            stderr_file=stderr_file,
            final=False,
            suffix="1",
            settings_override={},
        )
        ci = Cp2kInput.from_file(zpath(os.path.join(directory, input_file)))
        run_type = ci["global"].get("run_type", Keyword("RUN_TYPE", "ENERGY_FORCE")).values[0]
        if run_type not in {"ENERGY", "WAVEFUNCTION_OPTIMIZATION", "WFN_OPT"}:
            job1.settings_override = [
                {"dict": input_file, "action": {"_set": {"GLOBAL": {"RUN_TYPE": "ENERGY_FORCE"}}}}
            ]

        job2 = Cp2kJob(
            cp2k_cmd,
            input_file=input_file,
            output_file=output_file,
            backup=backup,
            stderr_file=stderr_file,
            final=True,
            suffix="2",
            restart=True,
        )
        job2.settings_override = [{"dict": input_file, "action": {"_set": {"GLOBAL": {"RUN_TYPE": run_type}}}}]

        return [job1, job2]

    @classmethod
    def pre_screen_hybrid(
        cls,
        cp2k_cmd,
        input_file="cp2k.inp",
        output_file="cp2k.out",
        stderr_file="std_err.txt",
        backup=True,
        directory="./",
    ):
        """
        Build a job where the first job is an unscreened hybrid static calculation, then the second one
        uses the wfn from the first job as a restart to do a screened calculation.
        """
        job1_settings_override = [
            {
                "dict": input_file,
                "action": {
                    "_set": {
                        "FORCE_EVAL": {
                            "DFT": {
                                "XC": {
                                    "HF": {
                                        "SCREENING": {
                                            "SCREEN_ON_INITIAL_P": False,
                                            "SCREEN_P_FORCES": False,
                                        }
                                    }
                                }
                            }
                        },
                        "GLOBAL": {"RUN_TYPE": "ENERGY_FORCE"},
                    }
                },
            }
        ]

        job1 = Cp2kJob(
            cp2k_cmd,
            input_file=input_file,
            output_file=output_file,
            backup=backup,
            stderr_file=stderr_file,
            final=False,
            suffix="1",
            settings_override=job1_settings_override,
        )

        ci = Cp2kInput.from_file(zpath(os.path.join(directory, input_file)))
        r = ci["global"].get("run_type", Keyword("RUN_TYPE", "ENERGY_FORCE")).values[0]
        if r in {"ENERGY", "WAVEFUNCTION_OPTIMIZATION", "WFN_OPT", "ENERGY_FORCE"}:  # no need for double job
            return [job1]

        job2_settings_override = [
            {
                "dict": input_file,
                "action": {
                    "_set": {
                        "FORCE_EVAL": {
                            "DFT": {
                                "XC": {
                                    "HF": {
                                        "SCREENING": {
                                            "SCREEN_ON_INITIAL_P": True,
                                            "SCREEN_P_FORCES": True,
                                        }
                                    }
                                },
                                "WFN_RESTART_FILE_NAME": "UNSCREENED_HYBRID-RESTART.wfn",
                            }
                        },
                        "GLOBAL": {"RUN_TYPE": r},
                    },
                },
            }
        ]

        job2 = Cp2kJob(
            cp2k_cmd,
            input_file=input_file,
            output_file=output_file,
            backup=backup,
            stderr_file=stderr_file,
            final=True,
            suffix="2",
            restart=False,
            settings_override=job2_settings_override,
        )

        return [job1, job2]
