import os
import shutil
import unittest
from unittest import TestCase

from pymatgen.io.qchem.inputs import QCInput

from custodian.qchem.handlers import QChemErrorHandler
from custodian.qchem.jobs import QCJob
from tests.conftest import TEST_FILES

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

TEST_DIR = f"{TEST_FILES}/qchem/new_test_files"
SCR_DIR = f"{TEST_DIR}/scratch"
CWD = os.getcwd()
skip_if_no_openbabel = unittest.skipIf(ob is None, "openbabel not installed")


@skip_if_no_openbabel
class FFOptJobHandlerInteraction(TestCase):
    def _check_equivalent_inputs(self, input1, input2) -> None:
        QCinput1 = QCInput.from_file(input1)
        QCinput2 = QCInput.from_file(input2)
        sections1 = QCInput.find_sections(QCinput1.get_str())
        sections2 = QCInput.find_sections(QCinput2.get_str())
        assert sections1 == sections2
        for key in sections1:
            assert QCinput1.as_dict().get(key) == QCinput2.as_dict().get(key)

    def setUp(self) -> None:
        os.makedirs(f"{SCR_DIR}/scratch", exist_ok=True)
        shutil.copyfile(f"{TEST_DIR}/job_handler_interaction/mol.qin.orig", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/job_handler_interaction/error.1/mol.qout", f"{SCR_DIR}/mol.qout.error1")
        shutil.copyfile(f"{TEST_DIR}/job_handler_interaction/error.2/mol.qin", f"{SCR_DIR}/mol.qin.error2")
        shutil.copyfile(f"{TEST_DIR}/job_handler_interaction/error.2/mol.qout", f"{SCR_DIR}/mol.qout.error2")
        shutil.copyfile(f"{TEST_DIR}/job_handler_interaction/error.3/mol.qin", f"{SCR_DIR}/mol.qin.error3")
        shutil.copyfile(f"{TEST_DIR}/job_handler_interaction/error.3/mol.qout", f"{SCR_DIR}/mol.qout.error3")
        shutil.copyfile(f"{TEST_DIR}/job_handler_interaction/mol.qin.opt_0", f"{SCR_DIR}/mol.qin.opt_0")
        shutil.copyfile(f"{TEST_DIR}/job_handler_interaction/mol.qout.opt_0", f"{SCR_DIR}/mol.qout.opt_0")
        shutil.copyfile(f"{TEST_DIR}/job_handler_interaction/error.5/mol.qin", f"{SCR_DIR}/mol.qin.error5")
        shutil.copyfile(f"{TEST_DIR}/job_handler_interaction/error.5/mol.qout", f"{SCR_DIR}/mol.qout.error5")
        shutil.copyfile(f"{TEST_DIR}/job_handler_interaction/mol.qin.freq_0", f"{SCR_DIR}/mol.qin.freq_0")
        shutil.copyfile(f"{TEST_DIR}/job_handler_interaction/mol.qout.freq_0", f"{SCR_DIR}/mol.qout.freq_0")
        shutil.copyfile(f"{TEST_DIR}/job_handler_interaction/mol.qin.opt_1", f"{SCR_DIR}/mol.qin.opt_1")
        os.chdir(SCR_DIR)

    def tearDown(self) -> None:
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self) -> None:
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

        handler = QChemErrorHandler(
            input_file="mol.qin",
            output_file="mol.qout.error1",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["back_transform_error"]
        assert dct["actions"] == [{"molecule": "molecule_from_last_geometry"}]
        self._check_equivalent_inputs("mol.qin", "mol.qin.error2")

        handler = QChemErrorHandler(
            input_file="mol.qin",
            output_file="mol.qout.error2",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["SCF_failed_to_converge"]
        assert dct["actions"] == [{"scf_algorithm": "gdm"}, {"max_scf_cycles": "500"}]
        self._check_equivalent_inputs("mol.qin", "mol.qin.error3")

        handler = QChemErrorHandler(
            input_file="mol.qin",
            output_file="mol.qout.error3",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["back_transform_error"]
        assert dct["actions"] == [{"molecule": "molecule_from_last_geometry"}]
        self._check_equivalent_inputs("mol.qin", "mol.qin.opt_0")

        handler = QChemErrorHandler(
            input_file="mol.qin",
            output_file="mol.qout.opt_0",
        )
        handler.check()
        assert not handler.check()

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

        handler = QChemErrorHandler(
            input_file="mol.qin",
            output_file="mol.qout.error5",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["failed_cpscf"]
        assert dct["actions"] == [{"cpscf_nseg": "3"}]
        self._check_equivalent_inputs("mol.qin", "mol.qin.freq_0")

        handler = QChemErrorHandler(
            input_file="mol.qin",
            output_file="mol.qout.freq_0",
        )
        handler.check()
        assert not handler.check()

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
