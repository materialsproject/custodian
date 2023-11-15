import os
import shutil
import unittest
from unittest import TestCase

from pymatgen.io.qchem.inputs import QCInput

from custodian import TEST_FILES
from custodian.qchem.handlers import QChemErrorHandler
from custodian.qchem.jobs import QCJob

try:
    from openbabel import openbabel as ob
except ImportError:
    ob = None

__author__ = "Samuel Blau"
__copyright__ = "Copyright 2022, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Samuel Blau"
__email__ = "samblau1@gmail.com"
__status__ = "Alpha"
__date__ = "6/3/22"

test_dir = f"{TEST_FILES}/qchem/new_test_files"

scr_dir = os.path.join(test_dir, "scr")
cwd = os.getcwd()


@unittest.skipIf(ob is None, "openbabel not installed")
class FFOptJobHandlerInteraction(TestCase):
    def _check_equivalent_inputs(self, input1, input2):
        QCinput1 = QCInput.from_file(input1)
        QCinput2 = QCInput.from_file(input2)
        sections1 = QCInput.find_sections(QCinput1.get_string())
        sections2 = QCInput.find_sections(QCinput2.get_string())
        assert sections1 == sections2
        for key in sections1:
            assert QCinput1.as_dict().get(key) == QCinput2.as_dict().get(key)

    def setUp(self):
        os.makedirs(scr_dir)
        os.makedirs(os.path.join(scr_dir, "scratch"))
        shutil.copyfile(
            os.path.join(test_dir, "job_handler_interaction/mol.qin.orig"),
            os.path.join(scr_dir, "mol.qin"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "job_handler_interaction/error.1/mol.qout"),
            os.path.join(scr_dir, "mol.qout.error1"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "job_handler_interaction/error.2/mol.qin"),
            os.path.join(scr_dir, "mol.qin.error2"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "job_handler_interaction/error.2/mol.qout"),
            os.path.join(scr_dir, "mol.qout.error2"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "job_handler_interaction/error.3/mol.qin"),
            os.path.join(scr_dir, "mol.qin.error3"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "job_handler_interaction/error.3/mol.qout"),
            os.path.join(scr_dir, "mol.qout.error3"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "job_handler_interaction/mol.qin.opt_0"),
            os.path.join(scr_dir, "mol.qin.opt_0"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "job_handler_interaction/mol.qout.opt_0"),
            os.path.join(scr_dir, "mol.qout.opt_0"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "job_handler_interaction/error.5/mol.qin"),
            os.path.join(scr_dir, "mol.qin.error5"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "job_handler_interaction/error.5/mol.qout"),
            os.path.join(scr_dir, "mol.qout.error5"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "job_handler_interaction/mol.qin.freq_0"),
            os.path.join(scr_dir, "mol.qin.freq_0"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "job_handler_interaction/mol.qout.freq_0"),
            os.path.join(scr_dir, "mol.qout.freq_0"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "job_handler_interaction/mol.qin.opt_1"),
            os.path.join(scr_dir, "mol.qin.opt_1"),
        )
        os.chdir(scr_dir)

    def tearDown(self):
        os.chdir(cwd)
        shutil.rmtree(scr_dir)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem",
            max_cores=40,
            input_file="mol.qin",
            output_file="mol.qout",
            linked=True,
        )
        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=40,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_0",
            save_scratch=True,
            backup=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next

        h = QChemErrorHandler(
            input_file="mol.qin",
            output_file="mol.qout.error1",
        )
        h.check()
        d = h.correct()
        assert d["errors"] == ["back_transform_error"]
        assert d["actions"] == [{"molecule": "molecule_from_last_geometry"}]
        self._check_equivalent_inputs("mol.qin", "mol.qin.error2")

        h = QChemErrorHandler(
            input_file="mol.qin",
            output_file="mol.qout.error2",
        )
        h.check()
        d = h.correct()
        assert d["errors"] == ["SCF_failed_to_converge"]
        assert d["actions"] == [{"scf_algorithm": "gdm"}, {"max_scf_cycles": "500"}]
        self._check_equivalent_inputs("mol.qin", "mol.qin.error3")

        h = QChemErrorHandler(
            input_file="mol.qin",
            output_file="mol.qout.error3",
        )
        h.check()
        d = h.correct()
        assert d["errors"] == ["back_transform_error"]
        assert d["actions"] == [{"molecule": "molecule_from_last_geometry"}]
        self._check_equivalent_inputs("mol.qin", "mol.qin.opt_0")

        h = QChemErrorHandler(
            input_file="mol.qin",
            output_file="mol.qout.opt_0",
        )
        h.check()
        assert not h.check()

        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=40,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_0",
            save_scratch=True,
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        self._check_equivalent_inputs("mol.qin", "mol.qin.error5")

        h = QChemErrorHandler(
            input_file="mol.qin",
            output_file="mol.qout.error5",
        )
        h.check()
        d = h.correct()
        assert d["errors"] == ["failed_cpscf"]
        assert d["actions"] == [{"cpscf_nseg": "3"}]
        self._check_equivalent_inputs("mol.qin", "mol.qin.freq_0")

        h = QChemErrorHandler(
            input_file="mol.qin",
            output_file="mol.qout.freq_0",
        )
        h.check()
        assert not h.check()

        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=40,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_1",
            save_scratch=True,
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next

        self._check_equivalent_inputs("mol.qin", "mol.qin.opt_1")
