import os
import shutil
import unittest
from unittest import TestCase
from unittest.mock import patch

import pytest
from pymatgen.io.qchem.inputs import QCInput

from custodian import TEST_FILES
from custodian.qchem.jobs import QCJob

try:
    from openbabel import openbabel as ob
except ImportError:
    ob = None

__author__ = "Samuel Blau"
__copyright__ = "Copyright 2018, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Samuel Blau"
__email__ = "samblau1@gmail.com"
__status__ = "Alpha"
__date__ = "6/6/18"
__credits__ = "Shyam Dwaraknath"

TEST_DIR = f"{TEST_FILES}/qchem/new_test_files"
SCR_DIR = f"{TEST_DIR}/scratch"
CWD = os.getcwd()


@unittest.skipIf(ob is None, "openbabel not installed")
class QCJobTest(TestCase):
    def setUp(self):
        os.makedirs(SCR_DIR)
        shutil.copyfile(f"{TEST_DIR}/no_nbo.qin", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/nbo7.qin", f"{SCR_DIR}/different.qin")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_defaults(self):
        with patch("custodian.qchem.jobs.shutil.copy") as copy_patch:
            job = QCJob(qchem_command="qchem", max_cores=32)
            assert job.current_command == "qchem -nt 32 mol.qin mol.qout scratch"
            job.setup()
            assert copy_patch.call_args_list[0][0][0] == "mol.qin"
            assert copy_patch.call_args_list[0][0][1] == "mol.qin.orig"
            assert os.environ["QCSCRATCH"] == os.getcwd()
            assert os.environ["QCTHREADS"] == "32"
            assert os.environ["OMP_NUM_THREADS"] == "32"

    def test_not_defaults(self):
        job = QCJob(
            qchem_command="qchem -slurm",
            multimode="mpi",
            input_file="different.qin",
            output_file="not_default.qout",
            max_cores=12,
            calc_loc="/not/default/",
            nboexe="/path/to/nbo7.i4.exe",
            backup=False,
        )
        assert job.current_command == "qchem -slurm -np 12 different.qin not_default.qout scratch"
        job.setup()
        assert os.environ["QCSCRATCH"] == os.getcwd()
        assert os.environ["QCLOCALSCR"] == "/not/default/"
        assert os.environ["NBOEXE"] == "/path/to/nbo7.i4.exe"
        assert os.environ["KMP_INIT_AT_FORK"] == "FALSE"

    def test_save_scratch(self):
        with patch("custodian.qchem.jobs.shutil.copy") as copy_patch:
            job = QCJob(
                qchem_command="qchem -slurm",
                max_cores=32,
                calc_loc="/tmp/scratch",
                save_scratch=True,
            )
            assert job.current_command == "qchem -slurm -nt 32 mol.qin mol.qout scratch"
            job.setup()
            assert copy_patch.call_args_list[0][0][0] == "mol.qin"
            assert copy_patch.call_args_list[0][0][1] == "mol.qin.orig"
            assert os.environ["QCSCRATCH"] == os.getcwd()
            assert os.environ["QCTHREADS"] == "32"
            assert os.environ["OMP_NUM_THREADS"] == "32"
            assert os.environ["QCLOCALSCR"] == "/tmp/scratch"


@unittest.skipIf(ob is None, "openbabel not installed")
class OptFFComplexUnlinkedTest(TestCase):
    def setUp(self):
        os.makedirs(SCR_DIR)
        shutil.copyfile(f"{TEST_DIR}/FF_complex/mol.qin.opt_0", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/FF_complex/mol.qout.opt_0", f"{SCR_DIR}/mol.qout.opt_0")
        shutil.copyfile(f"{TEST_DIR}/FF_complex/mol.qout.freq_0", f"{SCR_DIR}/mol.qout.freq_0")
        shutil.copyfile(f"{TEST_DIR}/FF_complex/mol.qin.freq_0", f"{SCR_DIR}/mol.qin.freq_0")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem",
            max_cores=32,
            input_file="mol.qin",
            output_file="mol.qout",
            max_molecule_perturb_scale=0.5,
            linked=False,
        )
        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_0",
            backup=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_0",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/FF_complex/mol.qin.freq_0_ref").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_1",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/FF_complex/mol.qin.opt_1_unlinked").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )


@unittest.skipIf(ob is None, "openbabel not installed")
class OptFFTestComplexLinkedChangeNsegTest(TestCase):
    def setUp(self):
        os.makedirs(SCR_DIR)
        shutil.copyfile(f"{TEST_DIR}/FF_complex/mol.qin.opt_0", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/FF_complex/mol.qin.opt_0", f"{SCR_DIR}/mol.qin.opt_0")
        shutil.copyfile(f"{TEST_DIR}/FF_complex/mol.qin.freq_0", f"{SCR_DIR}/mol.qin.freq_0")
        shutil.copyfile(f"{TEST_DIR}/FF_complex/mol.qin.opt_1", f"{SCR_DIR}/mol.qin.opt_1")
        shutil.copyfile(f"{TEST_DIR}/FF_complex/mol.qin.freq_1", f"{SCR_DIR}/mol.qin.freq_1")
        shutil.copyfile(f"{TEST_DIR}/FF_complex/mol.qout.opt_0", f"{SCR_DIR}/mol.qout.opt_0")
        shutil.copyfile(f"{TEST_DIR}/FF_complex/mol.qout.freq_0", f"{SCR_DIR}/mol.qout.freq_0")
        shutil.copyfile(f"{TEST_DIR}/FF_complex/mol.qout.opt_1", f"{SCR_DIR}/mol.qout.opt_1")
        shutil.copyfile(f"{TEST_DIR}/FF_complex/mol.qout.freq_1", f"{SCR_DIR}/mol.qout.freq_1")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem",
            max_cores=32,
            input_file="mol.qin",
            output_file="mol.qout",
            linked=True,
        )
        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_0",
            backup=True,
            save_scratch=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_0",
            backup=False,
            save_scratch=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/FF_complex/mol.qin.freq_0_ref").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_1",
            backup=False,
            save_scratch=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/FF_complex/mol.qin.opt_1").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_1",
            backup=False,
            save_scratch=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/FF_complex/mol.qin.freq_1").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )


@unittest.skipIf(ob is None, "openbabel not installed")
class OptFFTest(TestCase):
    def setUp(self):
        os.makedirs(SCR_DIR)
        shutil.copyfile(f"{TEST_DIR}/FF_working/test.qin", f"{SCR_DIR}/test.qin")
        shutil.copyfile(f"{TEST_DIR}/FF_working/test.qout.opt_0", f"{SCR_DIR}/test.qout.opt_0")
        shutil.copyfile(f"{TEST_DIR}/FF_working/test.qout.freq_0", f"{SCR_DIR}/test.qout.freq_0")
        shutil.copyfile(f"{TEST_DIR}/FF_working/test.qin.freq_0", f"{SCR_DIR}/test.qin.freq_0")
        shutil.copyfile(f"{TEST_DIR}/FF_working/test.qin.freq_1", f"{SCR_DIR}/test.qin.freq_1")
        shutil.copyfile(f"{TEST_DIR}/FF_working/test.qout.opt_1", f"{SCR_DIR}/test.qout.opt_1")
        shutil.copyfile(f"{TEST_DIR}/FF_working/test.qout.freq_1", f"{SCR_DIR}/test.qout.freq_1")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem",
            max_cores=32,
            input_file="test.qin",
            output_file="test.qout",
            linked=False,
        )
        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=32,
            multimode="openmp",
            input_file="test.qin",
            output_file="test.qout",
            suffix=".opt_0",
            backup=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=32,
            multimode="openmp",
            input_file="test.qin",
            output_file="test.qout",
            suffix=".freq_0",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/FF_working/test.qin.freq_0").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "test.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=32,
            multimode="openmp",
            input_file="test.qin",
            output_file="test.qout",
            suffix=".opt_1",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/FF_working/test.qin.opt_1").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "test.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=32,
            multimode="openmp",
            input_file="test.qin",
            output_file="test.qout",
            suffix=".freq_1",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/FF_working/test.qin.freq_1").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "test.qin")).as_dict()
        )
        with pytest.raises(StopIteration):
            job.__next__()


@unittest.skipIf(ob is None, "openbabel not installed")
class OptFFTest1(TestCase):
    def setUp(self):
        os.makedirs(SCR_DIR)
        shutil.copyfile(f"{TEST_DIR}/2620_complete/mol.qin.orig", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/2620_complete/mol.qout.opt_0", f"{SCR_DIR}/mol.qout.opt_0")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem -slurm", max_cores=32, input_file="mol.qin", output_file="mol.qout", linked=False
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_0",
            backup=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        with pytest.raises(StopIteration):
            job.__next__()


@unittest.skipIf(ob is None, "openbabel not installed")
class OptFFTest2(TestCase):
    def setUp(self):
        os.makedirs(SCR_DIR)
        shutil.copyfile(f"{TEST_DIR}/disconnected_but_converged/mol.qin.orig", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/disconnected_but_converged/mol.qout.opt_0", f"{SCR_DIR}/mol.qout.opt_0")
        shutil.copyfile(f"{TEST_DIR}/disconnected_but_converged/mol.qout.freq_0", f"{SCR_DIR}/mol.qout.freq_0")
        shutil.copyfile(f"{TEST_DIR}/disconnected_but_converged/mol.qin.freq_0", f"{SCR_DIR}/mol.qin.freq_0")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem -slurm",
            max_cores=32,
            input_file="mol.qin",
            output_file="mol.qout",
            linked=False,
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_0",
            backup=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_0",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/disconnected_but_converged/mol.qin.freq_0").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        with pytest.raises(StopIteration):
            job.__next__()


@unittest.skipIf(ob is None, "openbabel not installed")
class OptFFTestSwitching(TestCase):
    def setUp(self):
        os.makedirs(SCR_DIR)
        shutil.copyfile(f"{TEST_DIR}/FF_switching/mol.qin.orig", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/FF_switching/mol.qout.opt_0", f"{SCR_DIR}/mol.qout.opt_0")
        shutil.copyfile(f"{TEST_DIR}/FF_switching/mol.qout.freq_0", f"{SCR_DIR}/mol.qout.freq_0")
        shutil.copyfile(f"{TEST_DIR}/FF_switching/mol.qin.freq_0", f"{SCR_DIR}/mol.qin.freq_0")
        shutil.copyfile(f"{TEST_DIR}/FF_switching/mol.qin.freq_1", f"{SCR_DIR}/mol.qin.freq_1")
        shutil.copyfile(f"{TEST_DIR}/FF_switching/mol.qin.freq_2", f"{SCR_DIR}/mol.qin.freq_2")
        shutil.copyfile(f"{TEST_DIR}/FF_switching/mol.qout.opt_1", f"{SCR_DIR}/mol.qout.opt_1")
        shutil.copyfile(f"{TEST_DIR}/FF_switching/mol.qout.freq_1", f"{SCR_DIR}/mol.qout.freq_1")
        shutil.copyfile(f"{TEST_DIR}/FF_switching/mol.qout.opt_2", f"{SCR_DIR}/mol.qout.opt_2")
        shutil.copyfile(f"{TEST_DIR}/FF_switching/mol.qout.freq_2", f"{SCR_DIR}/mol.qout.freq_2")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem -slurm",
            max_cores=32,
            input_file="mol.qin",
            output_file="mol.qout",
            linked=False,
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_0",
            backup=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_0",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/FF_switching/mol.qin.freq_0").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_1",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/FF_switching/mol.qin.opt_1").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_1",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/FF_switching/mol.qin.freq_1").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_2",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/FF_switching/mol.qin.opt_2").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_2",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/FF_switching/mol.qin.freq_2").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        with pytest.raises(StopIteration):
            job.__next__()


@unittest.skipIf(ob is None, "openbabel not installed")
class OptFFTest6004(TestCase):
    def setUp(self):
        os.makedirs(SCR_DIR)
        shutil.copyfile(f"{TEST_DIR}/6004_frag12/mol.qin.orig", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/6004_frag12/mol.qout.opt_0", f"{SCR_DIR}/mol.qout.opt_0")
        shutil.copyfile(f"{TEST_DIR}/6004_frag12/mol.qout.freq_0", f"{SCR_DIR}/mol.qout.freq_0")
        shutil.copyfile(f"{TEST_DIR}/6004_frag12/mol.qin.freq_0", f"{SCR_DIR}/mol.qin.freq_0")
        shutil.copyfile(f"{TEST_DIR}/6004_frag12/mol.qin.freq_1", f"{SCR_DIR}/mol.qin.freq_1")
        shutil.copyfile(f"{TEST_DIR}/6004_frag12/mol.qin.freq_2", f"{SCR_DIR}/mol.qin.freq_2")
        shutil.copyfile(f"{TEST_DIR}/6004_frag12/mol.qout.opt_1", f"{SCR_DIR}/mol.qout.opt_1")
        shutil.copyfile(f"{TEST_DIR}/6004_frag12/mol.qout.freq_1", f"{SCR_DIR}/mol.qout.freq_1")
        shutil.copyfile(f"{TEST_DIR}/6004_frag12/mol.qout.opt_2", f"{SCR_DIR}/mol.qout.opt_2")
        shutil.copyfile(f"{TEST_DIR}/6004_frag12/mol.qout.freq_2", f"{SCR_DIR}/mol.qout.freq_2")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem -slurm",
            max_cores=32,
            input_file="mol.qin",
            output_file="mol.qout",
            linked=False,
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_0",
            backup=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_0",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/6004_frag12/mol.qin.freq_0").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_1",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/6004_frag12/mol.qin.opt_1").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_1",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/6004_frag12/mol.qin.freq_1").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_2",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/6004_frag12/mol.qin.opt_2").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_2",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/6004_frag12/mol.qin.freq_2").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )


@unittest.skipIf(ob is None, "openbabel not installed")
class OptFFTest5952(TestCase):
    def setUp(self):
        os.makedirs(SCR_DIR)
        shutil.copyfile(f"{TEST_DIR}/5952_frag16/mol.qin.orig", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/5952_frag16/mol.qout.opt_0", f"{SCR_DIR}/mol.qout.opt_0")
        shutil.copyfile(f"{TEST_DIR}/5952_frag16/mol.qout.freq_0", f"{SCR_DIR}/mol.qout.freq_0")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem -slurm",
            max_cores=32,
            input_file="mol.qin",
            output_file="mol.qout",
            linked=False,
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_0",
            backup=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_0",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/5952_frag16/mol.qin.freq_0").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        with pytest.raises(StopIteration):
            job.__next__()


@unittest.skipIf(ob is None, "openbabel not installed")
class OptFFTest5690(TestCase):
    def setUp(self):
        os.makedirs(SCR_DIR)
        shutil.copyfile(f"{TEST_DIR}/5690_frag18/mol.qin.orig", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/5690_frag18/mol.qout.opt_0", f"{SCR_DIR}/mol.qout.opt_0")
        shutil.copyfile(f"{TEST_DIR}/5690_frag18/mol.qout.freq_0", f"{SCR_DIR}/mol.qout.freq_0")
        shutil.copyfile(f"{TEST_DIR}/5690_frag18/mol.qin.freq_0", f"{SCR_DIR}/mol.qin.freq_0")
        shutil.copyfile(f"{TEST_DIR}/5690_frag18/mol.qin.freq_1", f"{SCR_DIR}/mol.qin.freq_1")
        shutil.copyfile(f"{TEST_DIR}/5690_frag18/mol.qin.freq_2", f"{SCR_DIR}/mol.qin.freq_2")
        shutil.copyfile(f"{TEST_DIR}/5690_frag18/mol.qout.opt_1", f"{SCR_DIR}/mol.qout.opt_1")
        shutil.copyfile(f"{TEST_DIR}/5690_frag18/mol.qout.freq_1", f"{SCR_DIR}/mol.qout.freq_1")
        shutil.copyfile(f"{TEST_DIR}/5690_frag18/mol.qout.opt_2", f"{SCR_DIR}/mol.qout.opt_2")
        shutil.copyfile(f"{TEST_DIR}/5690_frag18/mol.qout.freq_2", f"{SCR_DIR}/mol.qout.freq_2")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem -slurm",
            max_cores=32,
            input_file="mol.qin",
            output_file="mol.qout",
            linked=False,
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_0",
            backup=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_0",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/5690_frag18/mol.qin.freq_0").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_1",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/5690_frag18/mol.qin.opt_1").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_1",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/5690_frag18/mol.qin.freq_1").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_2",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/5690_frag18/mol.qin.opt_2").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_2",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/5690_frag18/mol.qin.freq_2").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        with pytest.raises(StopIteration):
            job.__next__()


@unittest.skipIf(ob is None, "openbabel not installed")
class OptFFSmallNegFreqTest(TestCase):
    def setUp(self):
        os.makedirs(f"{SCR_DIR}/scratch", exist_ok=True)
        shutil.copyfile(f"{TEST_DIR}/small_neg_freq/mol.qin.orig", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/small_neg_freq/mol.qin.opt_0", f"{SCR_DIR}/mol.qin.opt_0")
        shutil.copyfile(f"{TEST_DIR}/small_neg_freq/mol.qout.opt_0", f"{SCR_DIR}/mol.qout.opt_0")
        shutil.copyfile(f"{TEST_DIR}/small_neg_freq/mol.qout.freq_0", f"{SCR_DIR}/mol.qout.freq_0")
        shutil.copyfile(f"{TEST_DIR}/small_neg_freq/mol.qout.opt_1", f"{SCR_DIR}/mol.qout.opt_1")
        shutil.copyfile(f"{TEST_DIR}/small_neg_freq/mol.qout.freq_1", f"{SCR_DIR}/mol.qout.freq_1")
        shutil.copyfile(f"{TEST_DIR}/small_neg_freq/mol.qout.opt_2", f"{SCR_DIR}/mol.qout.opt_2")
        shutil.copyfile(f"{TEST_DIR}/small_neg_freq/mol.qout.freq_2", f"{SCR_DIR}/mol.qout.freq_2")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem -slurm",
            max_cores=32,
            input_file="mol.qin",
            output_file="mol.qout",
            linked=True,
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_0",
            save_scratch=True,
            backup=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_0",
            save_scratch=True,
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/small_neg_freq/mol.qin.freq_0").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        shutil.copyfile(
            os.path.join(SCR_DIR, "mol.qin"),
            os.path.join(SCR_DIR, "mol.qin.freq_0"),
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_1",
            save_scratch=True,
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/small_neg_freq/mol.qin.opt_1").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        shutil.copyfile(
            os.path.join(SCR_DIR, "mol.qin"),
            os.path.join(SCR_DIR, "mol.qin.opt_1"),
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_1",
            save_scratch=True,
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/small_neg_freq/mol.qin.freq_1").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        shutil.copyfile(
            os.path.join(SCR_DIR, "mol.qin"),
            os.path.join(SCR_DIR, "mol.qin.freq_1"),
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_2",
            save_scratch=True,
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/small_neg_freq/mol.qin.opt_2").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        shutil.copyfile(
            os.path.join(SCR_DIR, "mol.qin"),
            os.path.join(SCR_DIR, "mol.qin.opt_2"),
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_2",
            save_scratch=True,
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/small_neg_freq/mol.qin.freq_2").as_dict()
            == QCInput.from_file(os.path.join(SCR_DIR, "mol.qin")).as_dict()
        )
        shutil.copyfile(
            os.path.join(SCR_DIR, "mol.qin"),
            os.path.join(SCR_DIR, "mol.qin.freq_2"),
        )
        with pytest.raises(StopIteration):
            job.__next__()


@unittest.skipIf(ob is None, "openbabel not installed")
class OptFFSingleFreqFragsTest(TestCase):
    def setUp(self):
        os.makedirs(f"{SCR_DIR}/scratch", exist_ok=True)
        shutil.copyfile(f"{TEST_DIR}/single_freq_frag/mol.qin.orig", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/single_freq_frag/mol.qin.opt_0", f"{SCR_DIR}/mol.qin.opt_0")
        shutil.copyfile(f"{TEST_DIR}/single_freq_frag/mol.qout.opt_0", f"{SCR_DIR}/mol.qout.opt_0")
        shutil.copyfile(f"{TEST_DIR}/single_freq_frag/mol.qin.freq_0", f"{SCR_DIR}/mol.qin.freq_0")
        shutil.copyfile(f"{TEST_DIR}/single_freq_frag/mol.qout.freq_0", f"{SCR_DIR}/mol.qout.freq_0")

        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem -slurm",
            max_cores=32,
            input_file="mol.qin",
            output_file="mol.qout",
            linked=True,
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".opt_0",
            save_scratch=True,
            backup=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_0",
            save_scratch=True,
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/single_freq_frag/mol.qin.freq_0").as_dict()
            == QCInput.from_file(f"{SCR_DIR}/mol.qin").as_dict()
        )
        shutil.copyfile(f"{SCR_DIR}/mol.qin", f"{SCR_DIR}/mol.qin.freq_0")

        with pytest.raises(StopIteration):
            job.__next__()


@unittest.skipIf(ob is None, "openbabel not installed")
class TSFFTest(TestCase):
    def setUp(self):
        os.makedirs(SCR_DIR)
        shutil.copyfile(f"{TEST_DIR}/fftsopt_no_freqfirst/mol.qin.freq_0", f"{SCR_DIR}/test.qin")
        shutil.copyfile(f"{TEST_DIR}/fftsopt_no_freqfirst/mol.qout.ts_0", f"{SCR_DIR}/test.qout.ts_0")
        shutil.copyfile(f"{TEST_DIR}/fftsopt_no_freqfirst/mol.qout.freq_0", f"{SCR_DIR}/test.qout.freq_0")
        shutil.copyfile(f"{TEST_DIR}/fftsopt_no_freqfirst/mol.qin.freq_0", f"{SCR_DIR}/test.qin.freq_0")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem",
            max_cores=32,
            input_file="test.qin",
            output_file="test.qout",
            linked=False,
            transition_state=True,
        )
        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=32,
            multimode="openmp",
            input_file="test.qin",
            output_file="test.qout",
            suffix=".ts_0",
            backup=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        expected_next = QCJob(
            qchem_command="qchem",
            max_cores=32,
            multimode="openmp",
            input_file="test.qin",
            output_file="test.qout",
            suffix=".freq_0",
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/fftsopt_no_freqfirst/mol.qin.freq_0").as_dict()
            == QCInput.from_file(f"{SCR_DIR}/test.qin").as_dict()
        )
        with pytest.raises(StopIteration):
            job.__next__()


@unittest.skipIf(ob is None, "openbabel not installed")
class TSFFFreqfirstTest(TestCase):
    def setUp(self):
        os.makedirs(f"{SCR_DIR}/scratch", exist_ok=True)
        shutil.copyfile(f"{TEST_DIR}/fftsopt_freqfirst/mol.qin.orig", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/fftsopt_freqfirst/mol.qin.freq_pre", f"{SCR_DIR}/mol.qin.freq_pre")
        shutil.copyfile(f"{TEST_DIR}/fftsopt_freqfirst/mol.qout.freq_pre", f"{SCR_DIR}/mol.qout.freq_pre")
        shutil.copyfile(f"{TEST_DIR}/fftsopt_freqfirst/mol.qout.ts_0", f"{SCR_DIR}/mol.qout.ts_0")
        shutil.copyfile(f"{TEST_DIR}/fftsopt_freqfirst/mol.qout.freq_0", f"{SCR_DIR}/mol.qout.freq_0")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem -slurm",
            max_cores=32,
            input_file="mol.qin",
            output_file="mol.qout",
            linked=True,
            transition_state=True,
            freq_before_opt=True,
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_pre",
            save_scratch=True,
            backup=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".ts_0",
            save_scratch=True,
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/fftsopt_freqfirst/mol.qin.ts_0").as_dict()
            == QCInput.from_file(f"{SCR_DIR}/mol.qin").as_dict()
        )
        shutil.copyfile(f"{SCR_DIR}/mol.qin", f"{SCR_DIR}/mol.qin.ts_0")
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_0",
            save_scratch=True,
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/fftsopt_freqfirst/mol.qin.freq_0").as_dict()
            == QCInput.from_file(f"{SCR_DIR}/mol.qin").as_dict()
        )
        shutil.copyfile(f"{SCR_DIR}/mol.qin", f"{SCR_DIR}/mol.qin.freq_0")
        with pytest.raises(StopIteration):
            job.__next__()


@unittest.skipIf(ob is None, "openbabel not installed")
class TSFFFreqFirstMultipleCyclesTest(TestCase):
    def setUp(self):
        os.makedirs(f"{SCR_DIR}/scratch", exist_ok=True)
        shutil.copyfile(f"{TEST_DIR}/fftsopt_multiple_cycles/mol.qin.orig", f"{SCR_DIR}/mol.qin")
        shutil.copyfile(f"{TEST_DIR}/fftsopt_multiple_cycles/mol.qin.freq_pre", f"{SCR_DIR}/mol.qin.freq_pre")
        shutil.copyfile(f"{TEST_DIR}/fftsopt_multiple_cycles/mol.qout.freq_pre", f"{SCR_DIR}/mol.qout.freq_pre")
        shutil.copyfile(f"{TEST_DIR}/fftsopt_multiple_cycles/mol.qout.ts_0", f"{SCR_DIR}/mol.qout.ts_0")
        shutil.copyfile(f"{TEST_DIR}/fftsopt_multiple_cycles/mol.qout.freq_0", f"{SCR_DIR}/mol.qout.freq_0")
        shutil.copyfile(f"{TEST_DIR}/fftsopt_multiple_cycles/mol.qout.ts_1", f"{SCR_DIR}/mol.qout.ts_1")
        shutil.copyfile(f"{TEST_DIR}/fftsopt_multiple_cycles/mol.qout.freq_1", f"{SCR_DIR}/mol.qout.freq_1")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)

    def test_OptFF(self):
        job = QCJob.opt_with_frequency_flattener(
            qchem_command="qchem -slurm",
            max_cores=32,
            input_file="mol.qin",
            output_file="mol.qout",
            linked=True,
            transition_state=True,
            freq_before_opt=True,
        )
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_pre",
            save_scratch=True,
            backup=True,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".ts_0",
            save_scratch=True,
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/fftsopt_multiple_cycles/mol.qin.ts_0").as_dict()
            == QCInput.from_file(f"{SCR_DIR}/mol.qin").as_dict()
        )
        shutil.copyfile(f"{SCR_DIR}/mol.qin", f"{SCR_DIR}/mol.qin.ts_0")
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_0",
            save_scratch=True,
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/fftsopt_multiple_cycles/mol.qin.freq_0").as_dict()
            == QCInput.from_file(f"{SCR_DIR}/mol.qin").as_dict()
        )
        shutil.copyfile(f"{SCR_DIR}/mol.qin", f"{SCR_DIR}/mol.qin.freq_0")
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".ts_1",
            save_scratch=True,
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/fftsopt_multiple_cycles/mol.qin.ts_1").as_dict()
            == QCInput.from_file(f"{SCR_DIR}/mol.qin").as_dict()
        )
        shutil.copyfile(f"{SCR_DIR}/mol.qin", f"{SCR_DIR}/mol.qin.ts_1")
        expected_next = QCJob(
            qchem_command="qchem -slurm",
            max_cores=32,
            multimode="openmp",
            input_file="mol.qin",
            output_file="mol.qout",
            suffix=".freq_1",
            save_scratch=True,
            backup=False,
        ).as_dict()
        assert next(job).as_dict() == expected_next
        assert (
            QCInput.from_file(f"{TEST_DIR}/fftsopt_multiple_cycles/mol.qin.freq_1").as_dict()
            == QCInput.from_file(f"{SCR_DIR}/mol.qin").as_dict()
        )
        shutil.copyfile(f"{SCR_DIR}/mol.qin", f"{SCR_DIR}/mol.qin.freq_1")

        with pytest.raises(StopIteration):
            job.__next__()
