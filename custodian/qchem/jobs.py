# coding: utf-8

from __future__ import unicode_literals, division
import glob
import logging
import shlex
import socket
import re
import time

from pkg_resources import parse_version

"""
This module implements basic kinds of jobs for QChem runs.
"""

import os
import shutil
import copy
import subprocess
from pymatgen.io.qchem import QcInput, QcOutput
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
        self.qchem_cmd = self._modify_qchem_according_to_version(copy.deepcopy(qchem_cmd))
        self.input_file = input_file
        self.output_file = output_file
        self.chk_file = chk_file
        self.qclog_file = qclog_file
        self.gzipped = gzipped
        self.backup = backup
        self.current_command = self.qchem_cmd
        self.current_command_name = "general"
        self.large_static_mem = large_static_mem
        self.alt_cmd = {k: self._modify_qchem_according_to_version(c)
                        for k, c in copy.deepcopy(alt_cmd).items()}
        available_commands = ["general"]
        if self.alt_cmd:
            available_commands.extend(self.alt_cmd.keys())
        self._set_qchem_memory()


    @classmethod
    def _modify_qchem_according_to_version(cls, qchem_cmd):
        cmd2 = copy.deepcopy(qchem_cmd)
        try:
            from rubicon.utils.qchem_info import get_qchem_version
            cur_version = get_qchem_version()
        except:
            cur_version = parse_version("4.3.0")
        if cmd2 is not None:
            if cur_version >= parse_version("4.3.0"):
                if cmd2[0] == "qchem":
                    if "-seq" in cmd2:
                        cmd2.remove("-seq")
                    if "NERSC_HOST" in os.environ and \
                            os.environ["NERSC_HOST"] in ["cori", "edison"]:
                        if "-dbg" not in cmd2:
                            cmd2.insert(1, "-dbg")
                        if "-seq" in cmd2:
                            cmd2.remove("-seq")
                    elif "NERSC_HOST" in os.environ and \
                            os.environ["NERSC_HOST"] == "matgen":
                        if "-dbg" not in cmd2:
                            cmd2.insert(1, "-dbg")
                        if "-seq" in cmd2:
                            cmd2.remove("-seq")
            else:
                if "-dbg" in cmd2:
                    cmd2.remove("-dbg")
                if "-pbs" in cmd2:
                    cmd2.remove("-pbs")
        return cmd2

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
        elif "NERSC_HOST" in os.environ and os.environ["NERSC_HOST"] == "cori":
            if "QCSCRATCH" in os.environ and "eg_qchem" in os.environ["QCSCRATCH"]:
                # in memory scratch
                for j in qcinp.jobs:
                    if self.current_command_name == "general":
                        if self.large_static_mem:
                            j.set_memory(total=1400, static=200)
                        else:
                            j.set_memory(total=1500, static=100)
                    elif self.current_command_name == "half_cpus":
                        if self.large_static_mem:
                            j.set_memory(total=3000, static=500)
                        else:
                            j.set_memory(total=3200, static=300)
                    elif self.current_command_name == "openmp":
                        if self.large_static_mem:
                            j.set_memory(total=50000, static=12000)
                        else:
                            j.set_memory(total=60000, static=2000)
            else:
                # disk scratch
                for j in qcinp.jobs:
                    if self.current_command_name == "general":
                        if self.large_static_mem:
                            j.set_memory(total=2700, static=500)
                        else:
                            j.set_memory(total=3000, static=200)
                    elif self.current_command_name == "half_cpus":
                        if self.large_static_mem:
                            j.set_memory(total=6000, static=1000)
                        else:
                            j.set_memory(total=6500, static=500)
                    elif self.current_command_name == "openmp":
                        if self.large_static_mem:
                            j.set_memory(total=100000, static=25000)
                        else:
                            j.set_memory(total=120000, static=8000)
        elif "NERSC_HOST" in os.environ and os.environ["NERSC_HOST"] == "edison":
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
        elif "NERSC_HOST" in os.environ and os.environ["NERSC_HOST"] == "matgen":
            if "QCSCRATCH" in os.environ and "eg_qchem" in os.environ["QCSCRATCH"]:
                # in memory scratch
                for j in qcinp.jobs:
                    if self.current_command_name == "general":
                        if self.large_static_mem:
                            j.set_memory(total=1500, static=200)
                        else:
                            j.set_memory(total=1600, static=100)
                    elif self.current_command_name == "half_cpus":
                        if self.large_static_mem:
                            j.set_memory(total=3000, static=600)
                        else:
                            j.set_memory(total=3200, static=400)
                    elif self.current_command_name == "openmp":
                        if self.large_static_mem:
                            j.set_memory(total=15000, static=5500)
                        else:
                            j.set_memory(total=29000, static=2000)
            else:
                # disk scratch
                for j in qcinp.jobs:
                    if self.current_command_name == "general":
                        if self.large_static_mem:
                            j.set_memory(total=2800, static=500)
                        else:
                            j.set_memory(total=3100, static=200)
                    elif self.current_command_name == "half_cpus":
                        if self.large_static_mem:
                            j.set_memory(total=6000, static=1100)
                        else:
                            j.set_memory(total=6500, static=600)
                    elif self.current_command_name == "openmp":
                        if self.large_static_mem:
                            j.set_memory(total=50000, static=10000)
                        else:
                            j.set_memory(total=59000, static=3000)
        elif 'vesta' in socket.gethostname():
            for j in qcinp.jobs:
                j.set_memory(total=14500, static=800)
        qcinp.write_file(self.input_file)

    @staticmethod
    def is_openmp_compatible(qcinp):
        for j in qcinp.jobs:
            if j.params["rem"]["jobtype"] == "freq":
                return False
            try:
                from rubicon.utils.qchem_info import get_qchem_version
                cur_version = get_qchem_version()
            except:
                cur_version = parse_version("4.3.0")
            if cur_version < parse_version("4.3.0"):
                if j.params["rem"]["exchange"] in ["pbe", "b"] \
                    and "correlation" in j.params['rem'] \
                        and j.params["rem"]["correlation"] in ["pbe", "lyp"]:
                    return False
        return True

    def command_available(self, cmd_name):
        available_commands = ["general"]
        if self.alt_cmd:
            available_commands.extend(self.alt_cmd.keys())
        return cmd_name in available_commands

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
        if not self.command_available(cmd_name):
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
        if 'vesta' in socket.gethostname():
            # on ALCF
            returncode = self._run_qchem_on_alcf(log_file_object=log_file_object)
        else:

            qc_cmd = copy.deepcopy(self.current_command)
            qc_cmd += [self.input_file, self.output_file]
            qc_cmd = [str(t) for t in qc_cmd]
            if self.chk_file:
                qc_cmd.append(self.chk_file)
            if log_file_object:
                returncode = subprocess.call(qc_cmd, stdout=log_file_object)
            else:
                returncode = subprocess.call(qc_cmd)
        return returncode

    def _run_qchem_on_alcf(self, log_file_object=None):
        parent_qcinp = QcInput.from_file(self.input_file)
        njobs = len(parent_qcinp.jobs)
        return_codes = []
        alcf_cmds = []
        qc_jobids = []
        for i, j in enumerate(parent_qcinp.jobs):
            qsub_cmd = copy.deepcopy(self.current_command)
            sub_input_filename = "alcf_{}_{}".format(i+1, self.input_file)
            sub_output_filename = "alcf_{}_{}".format(i+1, self.output_file)
            sub_log_filename = "alcf_{}_{}".format(i+1, self.qclog_file)
            qsub_cmd[-2] = sub_input_filename
            sub_qcinp = QcInput([copy.deepcopy(j)])
            if "scf_guess" in sub_qcinp.jobs[0].params["rem"] and \
                    sub_qcinp.jobs[0].params["rem"]["scf_guess"] == "read":
                sub_qcinp.jobs[0].params["rem"].pop("scf_guess")
            if i > 0:
                if isinstance(j.mol, str) and j.mol == "read":
                    prev_qcout_filename = "alcf_{}_{}".format(i+1-1, self.output_file)
                    prev_qcout = QcOutput(prev_qcout_filename)
                    prev_final_mol = prev_qcout.data[0]["molecules"][-1]
                    j.mol = prev_final_mol
            sub_qcinp.write_file(sub_input_filename)
            logging.info("The command to run QChem is {}".format(' '.join(qsub_cmd)))
            alcf_cmds.append(qsub_cmd)
            p = subprocess.Popen(qsub_cmd,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            out, err = p.communicate()
            qc_jobid = int(out.strip())
            qc_jobids.append(qc_jobid)
            cqwait_cmd = shlex.split("cqwait {}".format(qc_jobid))
            subprocess.call(cqwait_cmd)
            output_file_name = "{}.output".format(qc_jobid)
            cobaltlog_file_name = "{}.cobaltlog".format(qc_jobid)
            with open(cobaltlog_file_name) as f:
                cobaltlog_last_line = f.readlines()[-1]
                exit_code_pattern = re.compile("an exit code of (?P<code>\d+);")
                m = exit_code_pattern.search(cobaltlog_last_line)
                if m:
                    rc = float(m.group("code"))
                else:
                    rc = -99999
                return_codes.append(rc)
            for name_change_trial in range(10):
                if not os.path.exists(output_file_name):
                    message = "{} is not found in {}, {}th wait " \
                              "for 5 mins\n".format(
                                    output_file_name,
                                    os.getcwd(), name_change_trial)
                    logging.info(message)
                    if log_file_object:
                        log_file_object.writelines([message])
                    time.sleep(60 * 5)
                    pass
                else:
                    message = "Found qchem output file {} in {}, change file " \
                              "name\n".format(output_file_name,
                                              os.getcwd(),
                                              name_change_trial)
                    logging.info(message)
                    if log_file_object:
                        log_file_object.writelines([message])
                    break
            log_file_object.flush()
            os.fsync(log_file_object.fileno())
            shutil.move(output_file_name, sub_output_filename)
            shutil.move(cobaltlog_file_name, sub_log_filename)
        overall_return_code = min(return_codes)
        with open(self.output_file, "w") as out_file_object:
            for i, job_cmd, rc, qc_jobid in zip(range(njobs), alcf_cmds, return_codes, qc_jobids):
                sub_output_filename = "alcf_{}_{}".format(i+1, self.output_file)
                sub_log_filename = "alcf_{}_{}".format(i+1, self.qclog_file)
                with open(sub_output_filename) as sub_out_file_object:
                    header_lines = ["Running Job {} of {} {}\n".format(i + 1, njobs, self.input_file),
                                    " ".join(job_cmd) + "\n"]
                    if i > 0:
                        header_lines = ['', ''] + header_lines
                    sub_out = sub_out_file_object.readlines()
                    out_file_object.writelines(header_lines)
                    out_file_object.writelines(sub_out)
                    if rc < 0 and rc != -99999:
                        out_file_object.writelines(["Application {} exit codes: {}\n".format(qc_jobid, rc), '\n', '\n'])
                if log_file_object:
                    with open(sub_log_filename) as sub_log_file_object:
                        sub_log = sub_log_file_object.readlines()
                        log_file_object.writelines(sub_log)
        return overall_return_code

    def run(self):
        if "NERSC_HOST" in os.environ and (os.environ["NERSC_HOST"] in ["cori", "edison"]):
            nodelist = os.environ["QCNODE"]
            num_nodes = len(nodelist.split(","))
            tmp_creation_cmd = shlex.split("srun -N {} --ntasks-per-node 1 --nodelist {}  mkdir /dev/shm/eg_qchem".format(num_nodes, nodelist))
            tmp_clean_cmd = shlex.split("srun -N {} --ntasks-per-node 1 --nodelist {} rm -rf /dev/shm/eg_qchem".format(num_nodes, nodelist))
        elif "NERSC_HOST" in os.environ and os.environ["NERSC_HOST"] == "matgen":
            nodelist = os.environ["QCNODE"]
            num_nodes = len(nodelist.split(","))
            tmp_creation_cmd = shlex.split("mpirun -np {} --npernode 1 --host {}  mkdir /dev/shm/eg_qchem".format(num_nodes, nodelist))
            tmp_clean_cmd = shlex.split("mpirun -np {} --npernode 1 --host {} rm -rf /dev/shm/eg_qchem".format(num_nodes, nodelist))
        else:
            tmp_clean_cmd = None
            tmp_creation_cmd = None
        logging.info("Scratch dir creation command is {}".format(tmp_creation_cmd))
        logging.info("Scratch dir deleting command is {}".format(tmp_clean_cmd))
        if self.qclog_file:
            with open(self.qclog_file, "a") as filelog:
                if tmp_clean_cmd:
                    filelog.write("delete scratch before running qchem using command {}\n".format(tmp_clean_cmd))
                    subprocess.call(tmp_clean_cmd, stdout=filelog)
                if tmp_creation_cmd:
                    filelog.write("Create scratch dir before running qchem using command {}\n".format(tmp_creation_cmd))
                    subprocess.call(tmp_creation_cmd, stdout=filelog)
                returncode = self._run_qchem(log_file_object=filelog)
                if tmp_clean_cmd:
                    filelog.write("clean scratch after running qchem using command {}\n".format(tmp_clean_cmd))
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

    def as_dict(self):
        d = {"@module": self.__class__.__module__,
             "@class": self.__class__.__name__,
             "qchem_cmd": self.qchem_cmd,
             "input_file": self.input_file,
             "output_file": self.output_file,
             "chk_file": self.chk_file,
             "qclog_file": self.qclog_file,
             "gzipped": self.gzipped,
             "backup": self.backup,
             "large_static_mem": self.large_static_mem,
             "alt_cmd": self.alt_cmd}
        return d

    @classmethod
    def from_dict(cls, d):
        return QchemJob(qchem_cmd=d["qchem_cmd"],
                        input_file=d["input_file"],
                        output_file=d["output_file"],
                        chk_file=d["chk_file"],
                        qclog_file=d["qclog_file"],
                        gzipped=d["gzipped"],
                        backup=d["backup"],
                        alt_cmd=d["alt_cmd"],
                        large_static_mem=d["large_static_mem"])

    def postprocess(self):
        if self.gzipped:
            if "NERSC_HOST" in os.environ and os.environ["NERSC_HOST"] == "edison":
                cur_dir = os.getcwd()
                file_list = [os.path.join(cur_dir, name) for name in glob.glob("*")]
                nodelist = os.environ["QCNODE"]
                gzip_cmd = shlex.split("srun -N 1 --ntasks-per-node 1 --nodelist  "
                                       "{} gzip".format(nodelist)) + file_list
                subprocess.call(gzip_cmd)
            else:
                gzip_dir(".")
