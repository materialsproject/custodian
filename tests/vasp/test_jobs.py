import multiprocessing
import os
import shutil
import subprocess
import unittest
from glob import glob
from unittest.mock import Mock, patch

import pymatgen
import pytest
from monty.os import cd
from monty.tempfile import ScratchDir
from pymatgen.core import Structure
from pymatgen.io.vasp import Incar, Kpoints, Poscar
from pymatgen.io.vasp.sets import MPRelaxSet

from custodian.vasp.jobs import GenerateVaspInputJob, VaspJob, VaspNEBJob, _gamma_point_only_check
from tests.conftest import TEST_FILES

pymatgen.core.SETTINGS["PMG_VASP_PSP_DIR"] = TEST_FILES


class TestVaspJob:
    def test_as_from_dict(self) -> None:
        v = VaspJob(["hello"])
        v2 = VaspJob.from_dict(v.as_dict())
        assert isinstance(v2, VaspJob)
        assert v2.vasp_cmd == ("hello",)

    def test_setup(self) -> None:
        with cd(TEST_FILES), ScratchDir(".", copy_from_current_on_enter=True):
            v = VaspJob(["hello"], auto_npar=True)
            v.setup()
            incar = Incar.from_file("INCAR")
            count = multiprocessing.cpu_count()
            # Need at least 3 CPUs for NPAR to be greater than 1
            if count > 3:
                assert incar["NPAR"] > 1

    def test_setup_run_no_kpts(self) -> None:
        # just make sure v.setup() and v.run() exit cleanly when no KPOINTS file is present
        with cd(f"{TEST_FILES}/kspacing"), ScratchDir(".", copy_from_current_on_enter=True):
            v = VaspJob(["hello"], auto_npar=True)
            v.setup()
            with pytest.raises(FileNotFoundError):
                # a FileNotFoundError indicates that v.run() tried to run
                # subprocess.Popen(cmd, stdout=f_std, stderr=f_err) with
                # cmd == "hello", so it successfully parsed the input file
                # directory.
                v.run()

    def test_update_incar(self) -> None:
        # just make sure v.setup() and v.run() exit cleanly when no KPOINTS file is present
        with cd(f"{TEST_FILES}/update_incar"), ScratchDir(".", copy_from_current_on_enter=True):
            incar = Incar.from_file("INCAR")
            assert incar["NBANDS"] == 200
            v = VaspJob(["hello"], update_incar=True)
            v.setup()
            incar = Incar.from_file("INCAR")
            assert incar["NBANDS"] == 224

    def test_postprocess(self) -> None:
        with cd(f"{TEST_FILES}/postprocess"), ScratchDir(".", copy_from_current_on_enter=True):
            shutil.copy("INCAR", "INCAR.backup")

            v = VaspJob(["hello"], final=False, suffix=".test", copy_magmom=True)
            v.postprocess()
            incar = Incar.from_file("INCAR")
            incar_prev = Incar.from_file("INCAR.test")

            for file in (
                "INCAR",
                "KPOINTS",
                "CONTCAR",
                "OSZICAR",
                "OUTCAR",
                "POSCAR",
                "vasprun.xml",
            ):
                assert os.path.isfile(f"{file}.test")
                os.remove(f"{file}.test")
            shutil.move("INCAR.backup", "INCAR")

            assert incar["MAGMOM"] == pytest.approx([3.007, 1.397, -0.189, -0.189])
            assert incar_prev["MAGMOM"] == pytest.approx([5, -5, 0.6, 0.6])

    def test_continue(self) -> None:
        # Test the continuation functionality
        with cd(f"{TEST_FILES}/postprocess"):
            # Test default functionality
            with ScratchDir(".", copy_from_current_on_enter=True):
                v = VaspJob("hello", auto_continue=True)
                v.setup()
                assert os.path.isfile("continue.json"), "continue.json not created"
                v.setup()
                assert Poscar.from_file("CONTCAR").structure == Poscar.from_file("POSCAR").structure
                assert Incar.from_file("INCAR")["ISTART"] == 1
                v.postprocess()
                assert not os.path.isfile("continue.json"), "continue.json not deleted after postprocessing"
            # Test explicit action functionality
            with ScratchDir(".", copy_from_current_on_enter=True):
                v = VaspJob(
                    ["hello"],
                    auto_continue=[{"dict": "INCAR", "action": {"_set": {"ISTART": 1}}}],
                )
                v.setup()
                v.setup()
                assert Poscar.from_file("CONTCAR").structure != Poscar.from_file("POSCAR").structure
                assert Incar.from_file("INCAR")["ISTART"] == 1
                v.postprocess()

    def test_static(self) -> None:
        # Just a basic test of init.
        VaspJob.double_relaxation_run(["vasp"])


class TestVaspNEBJob:
    def test_as_from_dict(self) -> None:
        v = VaspNEBJob(["hello"])
        v2 = VaspNEBJob.from_dict(v.as_dict())
        assert isinstance(v2, VaspNEBJob)
        assert v2.vasp_cmd == ("hello",)

    def test_setup(self) -> None:
        with cd(f"{TEST_FILES}/setup_neb"), ScratchDir(".", copy_from_current_on_enter=True):
            v = VaspNEBJob("hello", half_kpts=True)
            v.setup()

            incar = Incar.from_file("INCAR")
            count = multiprocessing.cpu_count()
            if count > 3:
                assert incar["NPAR"] > 1

            kpt = Kpoints.from_file("KPOINTS")
            kpt_pre = Kpoints.from_file("KPOINTS.orig")
            assert kpt_pre.style.name == "Monkhorst"
            assert kpt.style.name == "Gamma"

    def test_postprocess(self) -> None:
        neb_outputs = ["INCAR", "KPOINTS", "POTCAR", "vasprun.xml"]
        neb_sub_outputs = [
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

        with cd(f"{TEST_FILES}/postprocess_neb"):
            postprocess_neb = os.path.abspath(".")

            v = VaspNEBJob("hello", final=False, suffix=".test")
            v.postprocess()

            for file in neb_outputs:
                assert os.path.isfile(f"{file}.test")
                os.remove(f"{file}.test")

            sub_folders = glob("[0-9][0-9]")
            for sf in sub_folders:
                os.chdir(f"{postprocess_neb}/{sf}")
                for file in neb_sub_outputs:
                    if os.path.isfile(file):
                        assert os.path.isfile(f"{file}.test")
                        os.remove(f"{file}.test")


class TestGenerateVaspInputJob:
    def test_run(self) -> None:
        with ScratchDir("."):
            for file in ("INCAR", "POSCAR", "POTCAR", "KPOINTS"):
                shutil.copy(f"{TEST_FILES}/{file}", file)
            old_incar = Incar.from_file("INCAR")
            v = GenerateVaspInputJob("pymatgen.io.vasp.sets.MPNonSCFSet", contcar_only=False)
            v.run()
            incar = Incar.from_file("INCAR")
            assert incar["ICHARG"] == 11
            assert old_incar["ICHARG"] == 1
            kpoints = Kpoints.from_file("KPOINTS")
            assert str(kpoints.style) == "Reciprocal"


class TestAutoGamma:
    """
    Test that a VASP job can automatically detect when only 1 k-point at GAMMA is used.
    """

    def test_gamma_checks(self) -> None:
        # Isolated atom in PBC
        structure = Structure(
            lattice=[[15 + 0.1 * i if i == j else 0.0 for j in range(3)] for i in range(3)],
            species=["Na"],
            coords=[[0.5 for _ in range(3)]],
        )

        vis = MPRelaxSet(structure=structure)
        assert vis.kpoints.kpts == [(1, 1, 1)]
        assert _gamma_point_only_check(vis.get_input_set())

        # no longer Gamma-centered
        vis = MPRelaxSet(structure=structure, user_kpoints_settings=Kpoints(kpts=[2, 1, 1]))
        assert not _gamma_point_only_check(vis.get_input_set())

        vis = MPRelaxSet(structure=structure, user_kpoints_settings=Kpoints(kpts_shift=(0.1, 0.0, 0.0)))
        assert not _gamma_point_only_check(vis.get_input_set())

        # KSPACING-related checks
        vis = MPRelaxSet(structure=structure, user_incar_settings={"KSPACING": 0.005})
        assert not _gamma_point_only_check(vis.get_input_set())

        vis = MPRelaxSet(structure=structure, user_incar_settings={"KSPACING": 50})
        assert _gamma_point_only_check(vis.get_input_set())


class TestVaspJobTerminate(unittest.TestCase):
    """Unit tests for the VaspJob.terminate() method."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a VaspJob instance with minimal required parameters
        self.vasp_job = VaspJob(vasp_cmd=["srun", "vasp"])

        # Mock the _vasp_process attribute
        self.mock_process = Mock()
        self.vasp_job._vasp_process = self.mock_process

        # Set up logging capture
        self.logger_patcher = patch("custodian.vasp.jobs.logger")
        self.mock_logger = self.logger_patcher.start()

    def tearDown(self):
        """Clean up after each test method."""
        self.logger_patcher.stop()

    def test_terminate_process_already_finished(self):
        """Test termination when process has already finished (poll returns non-None)."""
        # Arrange
        self.mock_process.poll.return_value = 0  # Process already finished

        # Act
        self.vasp_job.terminate()

        # Assert
        self.mock_process.poll.assert_called_once()
        self.mock_logger.warning.assert_called_once_with("The process was already done!")
        self.mock_process.terminate.assert_not_called()
        self.mock_process.kill.assert_not_called()

    def test_terminate_graceful_success(self):
        """Test successful graceful termination."""
        # Arrange
        self.mock_process.poll.return_value = None  # Process is running
        self.mock_process.pid = 12345
        self.mock_process.terminate.return_value = None
        self.mock_process.wait.return_value = None

        # Act
        self.vasp_job.terminate()

        # Assert
        self.mock_process.poll.assert_called_once()
        self.mock_process.terminate.assert_called_once()
        self.mock_process.wait.assert_called_once_with(timeout=10)
        self.mock_logger.info.assert_called_once_with("Killing PID 12345")
        self.mock_process.kill.assert_not_called()

    def test_terminate_graceful_timeout_then_force_kill(self):
        """Test graceful termination timeout leading to force kill."""
        # Arrange
        self.mock_process.poll.return_value = None  # Process is running
        self.mock_process.pid = 12345
        self.mock_process.terminate.return_value = None
        self.mock_process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="vasp", timeout=10),  # First call times out
            None,  # Second call succeeds
        ]

        # Act
        self.vasp_job.terminate()

        # Assert
        self.mock_process.poll.assert_called_once()
        self.mock_process.terminate.assert_called_once()
        assert self.mock_process.wait.call_count == 2
        self.mock_process.kill.assert_called_once()

        # Check logging calls
        self.mock_logger.info.assert_called_once_with("Killing PID 12345")
        self.mock_logger.warning.assert_called_once_with("Graceful termination did not work. Force killing PID 12345")

    def test_terminate_exception_during_graceful_termination(self):
        """Test handling of exceptions during graceful termination."""
        # Arrange
        self.mock_process.poll.return_value = None
        self.mock_process.pid = 12345
        self.mock_process.terminate.side_effect = OSError("Permission denied")

        # Act & Assert
        with pytest.raises(OSError):
            self.vasp_job.terminate()

        self.mock_process.terminate.assert_called_once()

    def test_terminate_exception_during_force_kill(self):
        """Test handling of exceptions during force kill."""
        # Arrange
        self.mock_process.poll.return_value = None
        self.mock_process.pid = 12345
        self.mock_process.terminate.return_value = None
        self.mock_process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="vasp", timeout=10),  # Graceful timeout
            OSError("Process not found"),  # Force kill fails
        ]
        self.mock_process.kill.return_value = None

        # Act & Assert
        with pytest.raises(OSError):
            self.vasp_job.terminate()

        self.mock_process.terminate.assert_called_once()
        self.mock_process.kill.assert_called_once()

    def test_terminate_multiple_calls(self):
        """Test calling terminate multiple times."""
        # Arrange
        self.mock_process.poll.side_effect = [None, 0]  # Running, then finished
        self.mock_process.pid = 12345
        self.mock_process.terminate.return_value = None
        self.mock_process.wait.return_value = None

        # Act
        self.vasp_job.terminate()  # First call
        self.vasp_job.terminate()  # Second call

        # Assert
        assert self.mock_process.poll.call_count == 2
        self.mock_process.terminate.assert_called_once()  # Only called on first invocation
        self.mock_logger.warning.assert_called_once_with("The process was already done!")

    @patch("custodian.vasp.jobs.VaspJob.__init__", return_value=None)
    def test_terminate_integration_with_real_process(self, mock_init):
        """Test termination with a real subprocess (integration-style test)."""
        # Arrange
        vasp_job = VaspJob.__new__(VaspJob)  # Create instance without calling __init__

        real_process = subprocess.Popen(["sleep", "10"])
        vasp_job._vasp_process = real_process

        with patch("custodian.vasp.jobs.logger") as mock_logger:
            vasp_job.terminate()
        assert real_process.poll() is not None  # Process should be terminated
        mock_logger.info.assert_called_once()


class TestVaspJobTerminateEdgeCases(unittest.TestCase):
    """Additional edge case tests for VaspJob.terminate()."""

    def setUp(self):
        self.vasp_job = VaspJob(vasp_cmd=["vasp"])
        self.mock_process = Mock()
        self.vasp_job._vasp_process = self.mock_process

    @patch("custodian.vasp.jobs")
    def test_terminate_wait_with_different_timeout_behavior(self, mock_logger):
        """Test different timeout behaviors in wait()."""
        # Test case where wait() is called twice with different outcomes
        self.mock_process.poll.return_value = None
        self.mock_process.pid = 9999
        self.mock_process.terminate.return_value = None

        # First wait times out, second wait after kill succeeds
        self.mock_process.wait.side_effect = [subprocess.TimeoutExpired("vasp", 10), None]

        self.vasp_job.terminate()

        assert self.mock_process.wait.call_count == 2
        self.mock_process.kill.assert_called_once()
