import os
import shutil
import unittest
from unittest import TestCase

from pymatgen.io.qchem.inputs import QCInput

from custodian.qchem.handlers import QChemErrorHandler

__author__ = "Samuel Blau, Brandon Woods, Shyam Dwaraknath, Ryan Kingsbury"
__copyright__ = "Copyright 2018, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Samuel Blau"
__email__ = "samblau1@gmail.com"
__status__ = "Alpha"
__date__ = "3/26/18"
__credits__ = "Xiaohui Qu"

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "test_files", "qchem", "new_test_files")

scr_dir = os.path.join(test_dir, "scr")
cwd = os.getcwd()


class QChemErrorHandlerTest(TestCase):
    def setUp(self):
        os.makedirs(scr_dir)
        os.chdir(scr_dir)

    def _check_equivalent_inputs(self, input1, input2):
        QCinput1 = QCInput.from_file(input1)
        QCinput2 = QCInput.from_file(input2)
        sections1 = QCInput.find_sections(QCinput1.get_string())
        sections2 = QCInput.find_sections(QCinput2.get_string())
        self.assertEqual(sections1, sections2)
        for key in sections1:
            self.assertEqual(QCinput1.as_dict().get(key), QCinput2.as_dict().get(key))

    def test_unable_to_determine_lamda(self):
        for ii in range(2):
            shutil.copyfile(
                os.path.join(test_dir, "unable_to_determine_lamda.qin." + str(ii)),
                os.path.join(scr_dir, "unable_to_determine_lamda.qin." + str(ii)),
            )
            shutil.copyfile(
                os.path.join(test_dir, "unable_to_determine_lamda.qout." + str(ii)),
                os.path.join(scr_dir, "unable_to_determine_lamda.qout." + str(ii)),
            )

        h = QChemErrorHandler(
            input_file="unable_to_determine_lamda.qin.0",
            output_file="unable_to_determine_lamda.qout.0",
        )
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["unable_to_determine_lamda"])
        self.assertEqual(
            d["actions"],
            [
                {"s2thresh": "16"},
                {"molecule": "molecule_from_last_geometry"},
                {"scf_algorithm": "diis_gdm"},
            ],
        )
        self._check_equivalent_inputs("unable_to_determine_lamda.qin.0", "unable_to_determine_lamda.qin.1")

    def test_linear_dependent_basis_and_FileMan(self):
        for ii in range(1, 3):
            shutil.copyfile(
                os.path.join(test_dir, "unable_to_determine_lamda.qin." + str(ii)),
                os.path.join(scr_dir, "unable_to_determine_lamda.qin." + str(ii)),
            )
            shutil.copyfile(
                os.path.join(test_dir, "unable_to_determine_lamda.qout." + str(ii)),
                os.path.join(scr_dir, "unable_to_determine_lamda.qout." + str(ii)),
            )

        h = QChemErrorHandler(
            input_file="unable_to_determine_lamda.qin.1",
            output_file="unable_to_determine_lamda.qout.1",
        )
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["premature_end_FileMan_error"])
        self.assertEqual(d["warnings"]["linear_dependence"], True)
        self.assertEqual(d["actions"], [{"scf_guess_always": "true"}])

    def test_failed_to_transform(self):
        for ii in range(2):
            shutil.copyfile(
                os.path.join(test_dir, "qunino_vinyl.qin." + str(ii)),
                os.path.join(scr_dir, "qunino_vinyl.qin." + str(ii)),
            )
            shutil.copyfile(
                os.path.join(test_dir, "qunino_vinyl.qout." + str(ii)),
                os.path.join(scr_dir, "qunino_vinyl.qout." + str(ii)),
            )

        h = QChemErrorHandler(input_file="qunino_vinyl.qin.0", output_file="qunino_vinyl.qout.0")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["failed_to_transform_coords"])
        self.assertEqual(
            d["actions"], [{"thresh": "14"}, {"s2thresh": "16"}, {"sym_ignore": "true"}, {"symmetry": "false"}]
        )
        self._check_equivalent_inputs("qunino_vinyl.qin.0", "qunino_vinyl.qin.1")

        h = QChemErrorHandler(input_file="qunino_vinyl.qin.1", output_file="qunino_vinyl.qout.1")
        self.assertEqual(h.check(), False)

    def test_scf_failed_to_converge(self):
        for ii in range(3):
            shutil.copyfile(
                os.path.join(test_dir, "crowd_gradient.qin." + str(ii)),
                os.path.join(scr_dir, "crowd_gradient.qin." + str(ii)),
            )
            shutil.copyfile(
                os.path.join(test_dir, "crowd_gradient.qout." + str(ii)),
                os.path.join(scr_dir, "crowd_gradient.qout." + str(ii)),
            )

        h = QChemErrorHandler(input_file="crowd_gradient.qin.0", output_file="crowd_gradient.qout.0")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["SCF_failed_to_converge"])
        self.assertEqual(d["actions"], [{"s2thresh": "16"}, {"max_scf_cycles": 100}, {"thresh": "14"}])
        self._check_equivalent_inputs("crowd_gradient.qin.0", "crowd_gradient.qin.1")

    def test_advanced_scf_failed_to_converge_1(self):
        shutil.copyfile(
            os.path.join(test_dir, "diis_guess_always/mol.qin.0"),
            os.path.join(scr_dir, "mol.qin"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "diis_guess_always/mol.qout.0"),
            os.path.join(scr_dir, "mol.qout"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "diis_guess_always/mol.qin.1"),
            os.path.join(scr_dir, "mol.qin.1"),
        )

        h = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["SCF_failed_to_converge"])
        self.assertEqual(d["actions"], [{"scf_guess_always": "true"}])
        self._check_equivalent_inputs("mol.qin", "mol.qin.1")

    def test_advanced_scf_failed_to_converge_2(self):
        shutil.copyfile(
            os.path.join(test_dir, "custom_gdm_diis/mol.qin.0"),
            os.path.join(scr_dir, "mol.qin.0"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "custom_gdm_diis/mol.qout.0"),
            os.path.join(scr_dir, "mol.qout.0"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "custom_gdm_diis/mol.qin.1"),
            os.path.join(scr_dir, "mol.qin.1"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "custom_gdm_diis/mol.qout.1"),
            os.path.join(scr_dir, "mol.qout.1"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "custom_gdm_diis/mol.qin.2"),
            os.path.join(scr_dir, "mol.qin.2"),
        )

        h = QChemErrorHandler(input_file="mol.qin.0", output_file="mol.qout.0")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["SCF_failed_to_converge"])
        self.assertEqual(d["actions"], [{"s2thresh": "16"}, {"scf_algorithm": "diis_gdm"}])
        self._check_equivalent_inputs("mol.qin.0", "mol.qin.1")

        h = QChemErrorHandler(input_file="mol.qin.1", output_file="mol.qout.1")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["SCF_failed_to_converge"])
        self.assertEqual(d["actions"], [{"scf_algorithm": "custom_gdm_diis"}])
        self._check_equivalent_inputs("mol.qin.1", "mol.qin.2")

    def test_out_of_opt_cycles(self):
        shutil.copyfile(
            os.path.join(test_dir, "crowd_gradient.qin.2"),
            os.path.join(scr_dir, "crowd_gradient.qin.2"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "crowd_gradient.qout.2"),
            os.path.join(scr_dir, "crowd_gradient.qout.2"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "crowd_gradient.qin.3"),
            os.path.join(scr_dir, "crowd_gradient.qin.3"),
        )

        h = QChemErrorHandler(input_file="crowd_gradient.qin.2", output_file="crowd_gradient.qout.2")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["out_of_opt_cycles"])
        self.assertEqual(
            d["actions"],
            [{"geom_max_cycles:": 200}, {"molecule": "molecule_from_last_geometry"}],
        )
        self._check_equivalent_inputs("crowd_gradient.qin.2", "crowd_gradient.qin.3")

    def test_advanced_out_of_opt_cycles(self):
        shutil.copyfile(
            os.path.join(test_dir, "2564_complete/error1/mol.qin"),
            os.path.join(scr_dir, "mol.qin"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "2564_complete/error1/mol.qout"),
            os.path.join(scr_dir, "mol.qout"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "2564_complete/mol.qin.opt_0"),
            os.path.join(scr_dir, "mol.qin.opt_0"),
        )
        h = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["out_of_opt_cycles"])
        self.assertEqual(d["actions"], [{"s2thresh": "16"}, {"molecule": "molecule_from_last_geometry"}])
        self._check_equivalent_inputs("mol.qin.opt_0", "mol.qin")
        self.assertEqual(h.opt_error_history[0], "more_bonds")
        shutil.copyfile(
            os.path.join(test_dir, "2564_complete/mol.qin.opt_0"),
            os.path.join(scr_dir, "mol.qin"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "2564_complete/mol.qout.opt_0"),
            os.path.join(scr_dir, "mol.qout"),
        )
        h.check()
        self.assertEqual(h.opt_error_history, [])

    def test_advanced_out_of_opt_cycles1(self):
        shutil.copyfile(
            os.path.join(test_dir, "2620_complete/mol.qin.opt_0"),
            os.path.join(scr_dir, "mol.qin"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "2620_complete/mol.qout.opt_0"),
            os.path.join(scr_dir, "mol.qout"),
        )
        h = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        self.assertEqual(h.check(), False)

    def test_failed_to_read_input(self):
        shutil.copyfile(
            os.path.join(test_dir, "unable_lamda_weird.qin"),
            os.path.join(scr_dir, "unable_lamda_weird.qin"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "unable_lamda_weird.qout"),
            os.path.join(scr_dir, "unable_lamda_weird.qout"),
        )
        h = QChemErrorHandler(input_file="unable_lamda_weird.qin", output_file="unable_lamda_weird.qout")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["failed_to_read_input"])
        self.assertEqual(d["actions"], [{"rerun_job_no_changes": True}])
        self._check_equivalent_inputs("unable_lamda_weird.qin.last", "unable_lamda_weird.qin")

    def test_input_file_error(self):
        shutil.copyfile(
            os.path.join(test_dir, "bad_input.qin"),
            os.path.join(scr_dir, "bad_input.qin"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "bad_input.qout"),
            os.path.join(scr_dir, "bad_input.qout"),
        )
        h = QChemErrorHandler(input_file="bad_input.qin", output_file="bad_input.qout")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["input_file_error"])
        self.assertEqual(d["actions"], None)

    def test_basis_not_supported(self):
        shutil.copyfile(
            os.path.join(test_dir, "basis_not_supported.qin"),
            os.path.join(scr_dir, "basis_not_supported.qin"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "basis_not_supported.qout"),
            os.path.join(scr_dir, "basis_not_supported.qout"),
        )
        h = QChemErrorHandler(input_file="basis_not_supported.qin", output_file="basis_not_supported.qout")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["basis_not_supported"])
        self.assertEqual(d["actions"], None)

    def test_NLebdevPts(self):
        shutil.copyfile(
            os.path.join(test_dir, "lebdevpts.qin"),
            os.path.join(scr_dir, "lebdevpts.qin"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "lebdevpts.qout"),
            os.path.join(scr_dir, "lebdevpts.qout"),
        )
        h = QChemErrorHandler(input_file="lebdevpts.qin", output_file="lebdevpts.qout")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["NLebdevPts"])
        self.assertEqual(d["actions"], [{"esp_surface_density": "250"}])

    def test_read_error(self):
        shutil.copyfile(
            os.path.join(test_dir, "molecule_read_error/mol.qin"),
            os.path.join(scr_dir, "mol.qin"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "molecule_read_error/mol.qout"),
            os.path.join(scr_dir, "mol.qout"),
        )
        h = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["read_molecule_error"])
        self.assertEqual(d["actions"], [{"rerun_job_no_changes": True}])
        self._check_equivalent_inputs("mol.qin.last", "mol.qin")

    def test_never_called_qchem_error(self):
        shutil.copyfile(
            os.path.join(test_dir, "mpi_error/mol.qin"),
            os.path.join(scr_dir, "mol.qin"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "mpi_error/mol.qout"),
            os.path.join(scr_dir, "mol.qout"),
        )
        h = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["never_called_qchem"])
        self.assertEqual(d["actions"], [{"rerun_job_no_changes": True}])
        self._check_equivalent_inputs("mol.qin.last", "mol.qin")

    def test_OOS_read_hess(self):
        shutil.copyfile(
            os.path.join(test_dir, "OOS_read_hess.qin"),
            os.path.join(scr_dir, "mol.qin"),
        )
        shutil.copyfile(
            os.path.join(test_dir, "OOS_read_hess.qout"),
            os.path.join(scr_dir, "mol.qout"),
        )
        h = QChemErrorHandler(input_file="mol.qin", output_file="mol.qout")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["out_of_opt_cycles"])
        self.assertEqual(
            d["actions"],
            [
                {"s2thresh": "16"},
                {"molecule": "molecule_from_last_geometry"},
                {"geom_opt_hessian": "deleted"},
            ],
        )
        self._check_equivalent_inputs(os.path.join(test_dir, "OOS_read_hess_next.qin"), "mol.qin")

    def tearDown(self):
        os.chdir(cwd)
        shutil.rmtree(scr_dir)


if __name__ == "__main__":
    unittest.main()
