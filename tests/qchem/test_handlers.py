import os
import shutil
import unittest
from unittest import TestCase

from pymatgen.io.qchem.inputs import QCInput

from custodian.qchem.handlers import QChemErrorHandler
from tests.conftest import TEST_FILES

try:
    from openbabel import openbabel as ob
except ImportError:
    ob = None

__author__ = "Samuel Blau, Brandon Woods, Shyam Dwaraknath, Ryan Kingsbury"
__copyright__ = "Copyright 2018, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Samuel Blau"
__email__ = "samblau1@gmail.com"
__status__ = "Alpha"
__date__ = "3/26/18"
__credits__ = "Xiaohui Qu"


TEST_DIR = f"{TEST_FILES}/qchem/new_test_files"
SCR_DIR = f"{TEST_DIR}/scratch"
CWD = os.getcwd()
skip_if_no_openbabel = unittest.skipIf(ob is None, "openbabel not installed")


@skip_if_no_openbabel
class QChemErrorHandlerTest(TestCase):
    def setUp(self):
        os.makedirs(SCR_DIR)
        os.chdir(SCR_DIR)

    def _check_equivalent_inputs(self, input1, input2):
        QCinput1 = QCInput.from_file(input1)
        QCinput2 = QCInput.from_file(input2)
        sections1 = QCInput.find_sections(QCinput1.get_str())
        sections2 = QCInput.find_sections(QCinput2.get_str())
        assert sections1 == sections2
        for key in sections1:
            assert QCinput1.as_dict().get(key) == QCinput2.as_dict().get(key)

    def test_unable_to_determine_lamda(self):
        for ii in range(2):
            shutil.copyfile(
                f"{TEST_DIR}/unable_to_determine_lamda.qin.{ii}",
                f"{SCR_DIR}/unable_to_determine_lamda.qin.{ii}",
            )
            shutil.copyfile(
                f"{TEST_DIR}/unable_to_determine_lamda.qout.{ii}",
                f"{SCR_DIR}/unable_to_determine_lamda.qout.{ii}",
            )

        handler = QChemErrorHandler(
            input_file="unable_to_determine_lamda.qin.0",
            output_file="unable_to_determine_lamda.qout.0",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["unable_to_determine_lamda"]
        assert dct["actions"] == [
            {"s2thresh": "16"},
            {"molecule": "molecule_from_last_geometry"},
            {"scf_algorithm": "gdm"},
            {"max_scf_cycles": "500"},
        ]
        self._check_equivalent_inputs("unable_to_determine_lamda.qin.0", "unable_to_determine_lamda.qin.1")

    def test_linear_dependent_basis_and_FileMan(self):
        for ii in range(1, 3):
            shutil.copyfile(
                f"{TEST_DIR}/unable_to_determine_lamda.qin.{ii}",
                f"{SCR_DIR}/unable_to_determine_lamda.qin.{ii}",
            )
            shutil.copyfile(
                f"{TEST_DIR}/unable_to_determine_lamda.qout.{ii}",
                f"{SCR_DIR}/unable_to_determine_lamda.qout.{ii}",
            )

        handler = QChemErrorHandler(
            input_file="unable_to_determine_lamda.qin.1",
            output_file="unable_to_determine_lamda.qout.1",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["premature_end_FileMan_error"]
        assert dct["warnings"]["linear_dependence"] is True
        assert dct["actions"] == [{"scf_guess_always": "true"}]

    def test_failed_to_transform(self):
        for ii in range(2):
            shutil.copyfile(f"{TEST_DIR}/qunino_vinyl.qin.{ii}", f"{SCR_DIR}/qunino_vinyl.qin.{ii}")
            shutil.copyfile(f"{TEST_DIR}/qunino_vinyl.qout.{ii}", f"{SCR_DIR}/qunino_vinyl.qout.{ii}")

        handler = QChemErrorHandler(input_file="qunino_vinyl.qin.0", output_file="qunino_vinyl.qout.0")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["failed_to_transform_coords"]
        assert dct["actions"] == [{"thresh": "14"}, {"s2thresh": "16"}, {"sym_ignore": "true"}, {"symmetry": "false"}]
        self._check_equivalent_inputs("qunino_vinyl.qin.0", "qunino_vinyl.qin.1")

        handler = QChemErrorHandler(input_file="qunino_vinyl.qin.1", output_file="qunino_vinyl.qout.1")
        assert handler.check() is False

    def test_scf_failed_to_converge(self):
        for ii in range(3):
            shutil.copyfile(f"{TEST_DIR}/crowd_gradient.qin.{ii}", f"{SCR_DIR}/crowd_gradient.qin.{ii}")
            shutil.copyfile(f"{TEST_DIR}/crowd_gradient.qout.{ii}", f"{SCR_DIR}/crowd_gradient.qout.{ii}")

        handler = QChemErrorHandler(input_file="crowd_gradient.qin.0", output_file="crowd_gradient.qout.0")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["SCF_failed_to_converge"]
        assert dct["actions"] == [{"s2thresh": "16"}, {"max_scf_cycles": 100}, {"thresh": "14"}]
        self._check_equivalent_inputs("crowd_gradient.qin.0", "crowd_gradient.qin.1")

    def test_scf_failed_to_converge_gdm_add_cycles(self):
        shutil.copyfile(f"{TEST_DIR}/gdm_add_cycles/mol.qin", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/gdm_add_cycles/mol.qin.1", f"{SCR_DIR}/mol.qin.1")
        shutil.copyfile(f"{TEST_DIR}/gdm_add_cycles/mol.qout", f"{SCR_DIR}/mol.qout")

        handler = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["SCF_failed_to_converge"]
        assert dct["actions"] == [{"max_scf_cycles": "500"}]
        self._check_equivalent_inputs("mol.qin", "mol.qin.1")

    def test_advanced_scf_failed_to_converge_1(self):
        shutil.copyfile(f"{TEST_DIR}/diis_guess_always/mol.qin.0", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/diis_guess_always/mol.qout.0", f"{SCR_DIR}/mol.qout")
        shutil.copyfile(f"{TEST_DIR}/diis_guess_always/mol.qin.1", f"{SCR_DIR}/mol.qin.1")

        handler = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["SCF_failed_to_converge"]
        assert dct["actions"] == [{"scf_algorithm": "gdm"}, {"max_scf_cycles": "500"}]
        self._check_equivalent_inputs("mol.qin", "mol.qin.1")

    def test_scf_into_opt(self):
        shutil.copyfile(f"{TEST_DIR}/scf_into_opt/mol.qin.0", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/scf_into_opt/mol.qout.0", f"{SCR_DIR}/mol.qout")
        shutil.copyfile(f"{TEST_DIR}/scf_into_opt/mol.qin.1", f"{SCR_DIR}/mol.qin.1")

        handler = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["SCF_failed_to_converge"]
        assert dct["actions"] == [{"scf_algorithm": "gdm"}, {"max_scf_cycles": "500"}]
        self._check_equivalent_inputs("mol.qin", "mol.qin.1")

        shutil.copyfile(f"{TEST_DIR}/scf_into_opt/mol.qout.1", f"{SCR_DIR}/mol.qout")

        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["out_of_opt_cycles"]
        assert dct["actions"] == [{"molecule": "molecule_from_last_geometry"}]

    def test_custom_smd(self):
        shutil.copyfile(f"{TEST_DIR}/custom_smd/mol.qin.0", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/custom_smd/mol.qout.0", f"{SCR_DIR}/mol.qout")
        shutil.copyfile(f"{TEST_DIR}/custom_smd/mol.qin.1", f"{SCR_DIR}/mol.qin.1")

        handler = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["SCF_failed_to_converge"]
        assert dct["actions"] == [{"scf_algorithm": "gdm"}, {"max_scf_cycles": "500"}]
        self._check_equivalent_inputs("mol.qin", "mol.qin.1")

        shutil.copyfile(f"{TEST_DIR}/custom_smd/mol.qout.1", f"{SCR_DIR}/mol.qout")

        handler.check()
        dct = handler.correct()
        assert dct["errors"] == []
        assert dct["actions"] is None

    def test_out_of_opt_cycles(self):
        shutil.copyfile(f"{TEST_DIR}/crowd_gradient.qin.2", f"{SCR_DIR}/crowd_gradient.qin.2")
        shutil.copyfile(f"{TEST_DIR}/crowd_gradient.qout.2", f"{SCR_DIR}/crowd_gradient.qout.2")
        shutil.copyfile(f"{TEST_DIR}/crowd_gradient.qin.3", f"{SCR_DIR}/crowd_gradient.qin.3")

        handler = QChemErrorHandler(input_file="crowd_gradient.qin.2", output_file="crowd_gradient.qout.2")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["out_of_opt_cycles"]
        assert dct["actions"] == [{"geom_max_cycles:": 200}, {"molecule": "molecule_from_last_geometry"}]
        self._check_equivalent_inputs("crowd_gradient.qin.2", "crowd_gradient.qin.3")

    def test_advanced_out_of_opt_cycles(self):
        shutil.copyfile(f"{TEST_DIR}/2564_complete/error1/mol.qin", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/2564_complete/error1/mol.qout", f"{SCR_DIR}/mol.qout")
        shutil.copyfile(f"{TEST_DIR}/2564_complete/mol.qin.opt_0", f"{SCR_DIR}/mol.qin.opt_0")
        handler = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["out_of_opt_cycles"]
        assert dct["actions"] == [{"s2thresh": "16"}, {"molecule": "molecule_from_last_geometry"}]
        self._check_equivalent_inputs("mol.qin.opt_0", "mol.qin")
        assert handler.opt_error_history[0] == "more_bonds"
        shutil.copyfile(f"{TEST_DIR}/2564_complete/mol.qin.opt_0", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/2564_complete/mol.qout.opt_0", f"{SCR_DIR}/mol.qout")
        handler.check()
        assert handler.opt_error_history == []

    def test_advanced_out_of_opt_cycles1(self):
        shutil.copyfile(f"{TEST_DIR}/2620_complete/mol.qin.opt_0", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/2620_complete/mol.qout.opt_0", f"{SCR_DIR}/mol.qout")
        handler = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        assert handler.check() is False

    def test_failed_to_read_input(self):
        shutil.copyfile(f"{TEST_DIR}/unable_lamda_weird.qin", f"{SCR_DIR}/unable_lamda_weird.qin")
        shutil.copyfile(f"{TEST_DIR}/unable_lamda_weird.qout", f"{SCR_DIR}/unable_lamda_weird.qout")
        handler = QChemErrorHandler(input_file="unable_lamda_weird.qin", output_file="unable_lamda_weird.qout")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["failed_to_read_input"]
        assert dct["actions"] == [{"rerun_job_no_changes": True}]
        self._check_equivalent_inputs("unable_lamda_weird.qin.last", "unable_lamda_weird.qin")

    def test_input_file_error(self):
        shutil.copyfile(f"{TEST_DIR}/bad_input.qin", f"{SCR_DIR}/bad_input.qin")
        shutil.copyfile(f"{TEST_DIR}/bad_input.qout", f"{SCR_DIR}/bad_input.qout")
        handler = QChemErrorHandler(input_file="bad_input.qin", output_file="bad_input.qout")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["input_file_error"]
        assert dct["actions"] is None

    def test_basis_not_supported(self):
        shutil.copyfile(f"{TEST_DIR}/basis_not_supported.qin", f"{SCR_DIR}/basis_not_supported.qin")
        shutil.copyfile(f"{TEST_DIR}/basis_not_supported.qout", f"{SCR_DIR}/basis_not_supported.qout")
        handler = QChemErrorHandler(input_file="basis_not_supported.qin", output_file="basis_not_supported.qout")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["basis_not_supported"]
        assert dct["actions"] is None

    def test_NLebdevPts(self):
        shutil.copyfile(f"{TEST_DIR}/lebdevpts.qin", f"{SCR_DIR}/lebdevpts.qin")
        shutil.copyfile(f"{TEST_DIR}/lebdevpts.qout", f"{SCR_DIR}/lebdevpts.qout")
        handler = QChemErrorHandler(input_file="lebdevpts.qin", output_file="lebdevpts.qout")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["NLebdevPts"]
        assert dct["actions"] == [{"esp_surface_density": "250"}]

    def test_read_error(self):
        shutil.copyfile(f"{TEST_DIR}/molecule_read_error/mol.qin", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/molecule_read_error/mol.qout", f"{SCR_DIR}/mol.qout")
        handler = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["read_molecule_error"]
        assert dct["actions"] == [{"rerun_job_no_changes": True}]
        self._check_equivalent_inputs("mol.qin.last", "mol.qin")

    def test_never_called_qchem_error(self):
        shutil.copyfile(f"{TEST_DIR}/mpi_error/mol.qin", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/mpi_error/mol.qout", f"{SCR_DIR}/mol.qout")
        handler = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["never_called_qchem"]
        assert dct["actions"] == [{"rerun_job_no_changes": True}]
        self._check_equivalent_inputs("mol.qin.last", "mol.qin")

    def test_OOS_read_hess(self):
        shutil.copyfile(f"{TEST_DIR}/OOS_read_hess.qin", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/OOS_read_hess.qout", f"{SCR_DIR}/mol.qout")
        handler = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["out_of_opt_cycles"]
        assert dct["actions"] == [
            {"s2thresh": "16"},
            {"molecule": "molecule_from_last_geometry"},
            {"geom_opt_hessian": "deleted"},
        ]
        self._check_equivalent_inputs(f"{TEST_DIR}/OOS_read_hess_next.qin", "mol.qin")

    def test_gdm_neg_precon_error(self):
        shutil.copyfile(f"{TEST_DIR}/gdm_neg_precon_error.qin", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/gdm_neg_precon_error.qout", f"{SCR_DIR}/mol.qout")
        handler = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["gdm_neg_precon_error"]
        assert dct["actions"] == [{"molecule": "molecule_from_last_geometry"}]

    def test_fileman_cpscf_nseg_error(self):
        shutil.copyfile(f"{TEST_DIR}/fileman_cpscf.qin", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/fileman_cpscf.qout", f"{SCR_DIR}/mol.qout")
        handler = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["premature_end_FileMan_error"]
        assert dct["actions"] == [{"cpscf_nseg": "3"}]

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)
