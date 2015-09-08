# coding: utf-8

from __future__ import unicode_literals, division
import glob
import logging
import shlex
import socket
import re

"""
This module implements basic kinds of jobs for QChem runs.
"""

import os
from monty.io import zopen
import shutil
import copy
import subprocess
from pymatgen.io.qchem import QcInput
from custodian.custodian import Job, gzip_dir

__author__ = "Xiaohui Qu"
__version__ = "0.1"
__maintainer__ = "Xiaohui Qu"
__email__ = "xhqu1981@gmail.com"
__status__ = "Alpha"
__date__ = "12/03/13"


class QchemJob(Job):
    """
    A basic QChem Job.
    """

    def __init__(self, qchem_cmd, input_file="mol.qcinp",
                 output_file="mol.qcout", chk_file=None, qclog_file=None,
                 gzipped=False, backup=True, alt_cmd=None,
                 large_static_mem=False):
        """
        This constructor is necessarily complex due to the need for
        flexibility. For standard kinds of runs, it's often better to use one
        of the static constructors.

        Args:
            qchem_cmd ([str]): Command to run QChem as a list args (without
                input/output file name). For example: ["qchem", "-np", "24"]
            input_file (str): Name of the QChem input file.
            output_file (str): Name of the QChem output file.
            chk_file (str): Name of the QChem check point file. None means no
                checkpoint point file. Defaults to None.
            qclog_file (str): Name of the file to redirect the standard output
                to. None means not to record the standard output. Defaults to
                None.
            gzipped (bool): Whether to gzip the final output. Defaults to False.
            backup (bool): Whether to backup the initial input files. If True,
                the input files will be copied with a ".orig" appended.
                Defaults to True.
            alt_cmd (dict of list): Alternate commands.
                For example: {"openmp": ["qchem", "-seq", "-nt", "24"]
                              "half_cpus": ["qchem", "-np", "12"]}
            large_static_mem: use ultra large static memory
        """
        self.qchem_cmd = copy.deepcopy(qchem_cmd)
        self.input_file = input_file
        self.output_file = output_file
        self.chk_file = chk_file
        self.qclog_file = qclog_file
        self.gzipped = gzipped
        self.backup = backup
        self.current_command = self.qchem_cmd
        self.current_command_name = "general"
        self.large_static_mem = large_static_mem
        self.alt_cmd = copy.deepcopy(alt_cmd)
        available_commands = ["general"]
        if self.alt_cmd:
            available_commands.extend(self.alt_cmd.keys())
        qcinp = QcInput.from_file(self.input_file)
        if "openmp" in available_commands and self.is_openmp_compatible(qcinp):
            if "PBS_JOBID" in os.environ and \
                    ("hopque" in os.environ["PBS_JOBID"] or
                     "edique" in os.environ["PBS_JOBID"]):
                self.select_command("openmp")
        self._set_qchem_memory()

    def _set_qchem_memory(self, qcinp=None):
        if not qcinp:
            qcinp = QcInput.from_file(self.input_file)
        if "PBS_JOBID" in os.environ:
            if "hopque" in os.environ["PBS_JOBID"]:
                # on Hopper
                for j in qcinp.jobs:
                    if self.current_command_name == "general":
                        if self.large_static_mem:
                            j.set_memory(total=1100, static=300)
                        else:
                            j.set_memory(total=1100, static=100)
                    elif self.current_command_name == "half_cpus":
                        if self.large_static_mem:
                            j.set_memory(total=2200, static=500)
                        else:
                            j.set_memory(total=2200, static=100)
                    elif self.current_command_name == "openmp":
                        if self.large_static_mem:
                            j.set_memory(total=28000, static=10000)
                        else:
                            j.set_memory(total=28000, static=3000)
            elif "edique" in os.environ["PBS_JOBID"]:
                # on Edison
                if "QCSCRATCH" in os.environ and "/tmp/eg_qchem" in os.environ["QCSCRATCH"]:
                    # in memory scratch
                    for j in qcinp.jobs:
                        if self.current_command_name == "general":
                            if self.large_static_mem:
                                j.set_memory(total=1200, static=300)
                            else:
                                j.set_memory(total=1200, static=100)
                        elif self.current_command_name == "half_cpus":
                            if self.large_static_mem:
                                j.set_memory(total=2400, static=400)
                            else:
                                j.set_memory(total=2400, static=200)
                        elif self.current_command_name == "openmp":
                            if self.large_static_mem:
                                j.set_memory(total=25000, static=1000)
                            else:
                                j.set_memory(total=25000, static=500)
                else:
                    # disk scratch
                    for j in qcinp.jobs:
                        if self.current_command_name == "general":
                            if self.large_static_mem:
                                j.set_memory(total=2500, static=500)
                            else:
                                j.set_memory(total=2500, static=100)
                        elif self.current_command_name == "half_cpus":
                            if self.large_static_mem:
                                j.set_memory(total=5000, static=1000)
                            else:
                                j.set_memory(total=5000, static=200)
                        elif self.current_command_name == "openmp":
                            if self.large_static_mem:
                                j.set_memory(total=60000, static=20000)
                            else:
                                j.set_memory(total=60000, static=5000)
            elif 'vesta' in socket.gethostname():
                for j in qcinp.jobs:
                    j.set_memory(total=7200, static=800)
        qcinp.write_file(self.input_file)

    @staticmethod
    def is_openmp_compatible(qcinp):
        for j in qcinp.jobs:
            if j.params["rem"]["jobtype"] == "freq":
                return False
            if j.params["rem"]["exchange"] in ["pbe", "b"] \
                and "correlation" in j.params['rem'] \
                    and j.params["rem"]["correlation"] in ["pbe", "lyp"]:
                return False
        return True

    def select_command(self, cmd_name, qcinp=None):
        """
        Set the command to run QChem by name. "general" set to the default one.
            Args:
                cmd_name: the command name to change to.
                qcinp: the QcInput object to operate on.

        Returns:
            True: success
            False: failed
        """
        available_commands = ["general"]
        if self.alt_cmd:
            available_commands.extend(self.alt_cmd.keys())
        if cmd_name not in available_commands:
            raise Exception("Command mode \"{cmd_name}\" is not available".format(cmd_name=cmd_name))
        if cmd_name == "general":
            self.current_command = self.qchem_cmd
        else:
            self.current_command = self.alt_cmd[cmd_name]
        self.current_command_name = cmd_name
        self._set_qchem_memory(qcinp)
        return True

    def setup(self):
        if self.backup:
            i = 0
            while os.path.exists("{}.{}.orig".format(self.input_file, i)):
                i += 1
            shutil.copy(self.input_file,
                        "{}.{}.orig".format(self.input_file, i))
            if self.chk_file and os.path.exists(self.chk_file):
                shutil.copy(self.chk_file,
                            "{}.{}.orig".format(self.chk_file, i))
            if os.path.exists(self.output_file):
                shutil.copy(self.output_file,
                            "{}.{}.orig".format(self.output_file, i))
            if self.qclog_file and os.path.exists(self.qclog_file):
                shutil.copy(self.qclog_file,
                            "{}.{}.orig".format(self.qclog_file, i))

    def _run_qchem(self, log_file_object=None):
        if not 'vesta' in socket.gethostname():
            qc_cmd = copy.deepcopy(self.current_command)
            qc_cmd += [self.input_file, self.output_file]
            if self.chk_file:
                qc_cmd.append(self.chk_file)
            if log_file_object:
                returncode = subprocess.call(qc_cmd, stdout=log_file_object)
            else:
                returncode = subprocess.call(qc_cmd)
        else:
            # on ALCF
            qsub_cmd = self.current_command
            logging.info("The command to run QChem is {}".format(' '.join(qsub_cmd)))
            p = subprocess.Popen(qsub_cmd,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            out, err = p.communicate()
            qc_jobid = int(out.strip())
            cqwait_cmd = shlex.split("cqwait {}".format(qc_jobid))
            subprocess.call(cqwait_cmd)
            output_file_name = "{}.output".format(qc_jobid)
            cobaltlog_file_name = "{}.cobaltlog".format(qc_jobid)
            with open(cobaltlog_file_name) as f:
                cobaltlog_last_line = f.readlines()[-1]
                exit_code_pattern = re.compile("an exit code of (?P<code>\d+);")
                m = exit_code_pattern.search(cobaltlog_last_line)
                if m:
                    returncode = float(m.group("code"))
                else:
                    returncode = -99999
            shutil.move(output_file_name, self.output_file)
        return returncode

    def run(self):
        if "PBS_JOBID" in os.environ and "edique" in os.environ["PBS_JOBID"]:
            nodelist = os.environ["QCNODE"]
            tmp_creation_cmd = shlex.split("aprun -n1 -N1 -L {} mkdir /tmp/eg_qchem".format(nodelist))
            tmp_clean_cmd = shlex.split("aprun -n1 -N1 -L {} rm -rf /tmp/eg_qchem".format(nodelist))
        else:
            tmp_clean_cmd = None
            tmp_creation_cmd = None
        if self.qclog_file:
            with open(self.qclog_file, "a") as filelog:
                if tmp_clean_cmd:
                    subprocess.call(tmp_clean_cmd, stdout=filelog)
                if tmp_creation_cmd:
                    subprocess.call(tmp_creation_cmd, stdout=filelog)
                returncode = self._run_qchem(log_file_object=filelog)
                if tmp_clean_cmd:
                    subprocess.call(tmp_clean_cmd, stdout=filelog)
        else:
            if tmp_clean_cmd:
                subprocess.call(tmp_clean_cmd)
            if tmp_creation_cmd:
                subprocess.call(tmp_creation_cmd)
            returncode = self._run_qchem()
            if tmp_clean_cmd:
                subprocess.call(tmp_clean_cmd)
        return returncode

    def postprocess(self):
        if self.gzipped:
            if "PBS_JOBID" in os.environ and "edique" in os.environ["PBS_JOBID"]:
                cur_dir = os.getcwd()
                file_list = [os.path.join(cur_dir, name) for name in glob.glob("*")]
                nodelist = os.environ["QCNODE"]
                gzip_cmd = shlex.split("aprun -n1 -N1 -L {} gzip".format(nodelist)) + file_list
                subprocess.call(gzip_cmd)
            else:
                gzip_dir(".")
