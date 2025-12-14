import multiprocessing
import os
import shutil
import signal
import subprocess
import sys
from glob import glob
from types import SimpleNamespace
from typing import TYPE_CHECKING
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

if TYPE_CHECKING:
    from collections.abc import Generator

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


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process group tests")
class TestVaspJobTerminate:
    """Tests for VaspJob.terminate() POSIX process group handling."""

    @pytest.fixture
    def mocks(self) -> "Generator[SimpleNamespace, None, None]":
        """Create VaspJob with mocked process and os functions."""
        job = VaspJob(vasp_cmd=["srun", "vasp"])
        process = Mock(pid=12345)
        job._vasp_process = process

        with (
            patch("custodian.vasp.jobs.logger") as logger,
            patch("os.killpg") as killpg,
            patch("os.getpgid", return_value=67890),
        ):
            yield SimpleNamespace(job=job, process=process, logger=logger, killpg=killpg)

    def test_already_finished(self, mocks: SimpleNamespace) -> None:
        """Early return when process already done."""
        mocks.process.poll.return_value = 0
        mocks.job.terminate()

        mocks.logger.warning.assert_called_with("Process 12345 already terminated")
        mocks.killpg.assert_not_called()

    def test_sigterm_success(self, mocks: SimpleNamespace) -> None:
        """Successful SIGTERM with wait confirmation."""
        mocks.process.poll.return_value = None
        mocks.job.terminate()

        mocks.logger.info.assert_any_call("Sending SIGTERM to process group 67890")
        mocks.killpg.assert_called_once_with(67890, signal.SIGTERM)
        mocks.process.wait.assert_called_once_with(timeout=10.0)
        mocks.logger.info.assert_any_call("Process 12345 terminated gracefully")
        mocks.process.kill.assert_not_called()

    def test_sigkill_after_timeout(self, mocks: SimpleNamespace) -> None:
        """SIGKILL sent when SIGTERM times out."""
        mocks.process.poll.return_value = None
        mocks.process.wait.side_effect = [subprocess.TimeoutExpired("vasp", 10), None]
        mocks.job.terminate()

        assert mocks.killpg.call_count == 2
        mocks.killpg.assert_any_call(67890, signal.SIGTERM)
        mocks.killpg.assert_any_call(67890, signal.SIGKILL)
        mocks.logger.warning.assert_any_call("SIGTERM timeout (10.0s), sending SIGKILL")
        mocks.logger.info.assert_any_call("Process 12345 killed with SIGKILL")

    def test_fallback_after_sigkill_timeout(self, mocks: SimpleNamespace) -> None:
        """Falls back to parent process when SIGKILL also times out."""
        mocks.process.poll.return_value = None
        mocks.process.wait.side_effect = [
            subprocess.TimeoutExpired("vasp", 10),  # after SIGTERM
            subprocess.TimeoutExpired("vasp", 10),  # after SIGKILL
            None,  # after fallback terminate
        ]
        mocks.job.terminate()

        mocks.logger.warning.assert_any_call("Falling back to killing parent process 12345")
        mocks.process.terminate.assert_called_once()

    def test_fallback_with_timeout(self, mocks: SimpleNamespace) -> None:
        """Fallback path uses kill() after terminate() times out."""
        mocks.process.poll.return_value = None
        mocks.process.wait.side_effect = [
            subprocess.TimeoutExpired("vasp", 10),  # after SIGTERM
            subprocess.TimeoutExpired("vasp", 10),  # after SIGKILL
            subprocess.TimeoutExpired("vasp", 10),  # after fallback terminate
            None,  # after fallback kill
        ]
        mocks.job.terminate()

        mocks.process.terminate.assert_called_once()
        mocks.process.kill.assert_called_once()
        mocks.logger.info.assert_any_call("Process 12345 killed")

    def test_process_group_not_found_on_getpgid(self, mocks: SimpleNamespace) -> None:
        """ProcessLookupError when getting PGID."""
        mocks.process.poll.return_value = None
        with patch("os.getpgid", side_effect=ProcessLookupError):
            mocks.job.terminate()

        mocks.logger.warning.assert_called_with("Process group for 12345 not found")
        mocks.killpg.assert_not_called()

    def test_process_group_not_found_on_sigterm(self, mocks: SimpleNamespace) -> None:
        """ProcessLookupError during SIGTERM (process died between getpgid and killpg)."""
        mocks.process.poll.return_value = None
        mocks.killpg.side_effect = ProcessLookupError
        mocks.job.terminate()

        mocks.logger.warning.assert_called_with("Process group 67890 not found")
        mocks.process.terminate.assert_not_called()

    def test_sigterm_oserror_skips_wait(self, mocks: SimpleNamespace) -> None:
        """OSError on SIGTERM skips wait and goes straight to SIGKILL."""
        mocks.process.poll.return_value = None
        mocks.killpg.side_effect = [OSError("Permission denied"), None]  # SIGTERM fails, SIGKILL succeeds
        mocks.job.terminate()

        # Should skip wait and go straight to SIGKILL
        assert mocks.killpg.call_count == 2
        mocks.killpg.assert_any_call(67890, signal.SIGTERM)
        mocks.killpg.assert_any_call(67890, signal.SIGKILL)
        mocks.logger.warning.assert_any_call("SIGTERM to process group 67890 failed: Permission denied")
        # Wait is only called once (after SIGKILL), not after failed SIGTERM
        mocks.process.wait.assert_called_once_with(timeout=10.0)

    @pytest.mark.skipif(sys.platform == "win32", reason="sleep command and PGID not available")
    def test_integration_with_real_process(self) -> None:
        """Integration test with real subprocess (POSIX only)."""
        vasp_job = VaspJob.__new__(VaspJob)
        vasp_job.terminate_timeout = 10.0
        real_process = subprocess.Popen(["sleep", "30"], start_new_session=True)
        vasp_job._vasp_process = real_process
        original_pgid = os.getpgid(real_process.pid)

        with patch("custodian.vasp.jobs.logger"):
            vasp_job.terminate()

        # Process should be confirmed dead (terminate() waits internally)
        assert real_process.poll() is not None
        # Verify process group no longer exists
        with pytest.raises(ProcessLookupError):
            os.killpg(original_pgid, 0)
