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
from monty.serialization import loadfn
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

    def test_setup(self, tmp_path) -> None:
        with cd(TEST_FILES), ScratchDir(str(tmp_path), copy_from_current_on_enter=True):
            v = VaspJob(["hello"], auto_npar=True)
            v.setup()
            incar = Incar.from_file("INCAR")
            count = multiprocessing.cpu_count()
            # Need at least 3 CPUs for NPAR to be greater than 1
            if count > 3:
                assert incar["NPAR"] > 1

    def test_setup_run_no_kpts(self, tmp_path) -> None:
        # just make sure v.setup() and v.run() exit cleanly when no KPOINTS file is present
        with cd(f"{TEST_FILES}/kspacing"), ScratchDir(str(tmp_path), copy_from_current_on_enter=True):
            v = VaspJob(["hello"], auto_npar=True)
            v.setup()
            with pytest.raises(FileNotFoundError):
                # a FileNotFoundError indicates that v.run() tried to run
                # subprocess.Popen(cmd, stdout=f_std, stderr=f_err) with
                # cmd == "hello", so it successfully parsed the input file
                # directory.
                v.run()

    def test_update_incar(self, tmp_path) -> None:
        # just make sure v.setup() and v.run() exit cleanly when no KPOINTS file is present
        with cd(f"{TEST_FILES}/update_incar"), ScratchDir(str(tmp_path), copy_from_current_on_enter=True):
            incar = Incar.from_file("INCAR")
            assert incar["NBANDS"] == 200
            v = VaspJob(["hello"], update_incar=True)
            v.setup()
            incar = Incar.from_file("INCAR")
            assert incar["NBANDS"] == 224

    def test_postprocess(self, tmp_path) -> None:
        with cd(f"{TEST_FILES}/postprocess"), ScratchDir(str(tmp_path), copy_from_current_on_enter=True):
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

    def test_continue(self, tmp_path) -> None:
        # Test the continuation functionality
        with cd(f"{TEST_FILES}/postprocess"):
            # Test default functionality
            with ScratchDir(str(tmp_path), copy_from_current_on_enter=True):
                v = VaspJob("hello", auto_continue=True)
                v.setup()
                assert os.path.isfile("continue.json"), "continue.json not created"
                v.setup()
                assert Poscar.from_file("CONTCAR").structure == Poscar.from_file("POSCAR").structure
                assert Incar.from_file("INCAR")["ISTART"] == 1
                v.postprocess()
                assert not os.path.isfile("continue.json"), "continue.json not deleted after postprocessing"
            # Test explicit action functionality
            with ScratchDir(str(tmp_path), copy_from_current_on_enter=True):
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

    def test_setup(self, tmp_path) -> None:
        with cd(f"{TEST_FILES}/setup_neb"), ScratchDir(str(tmp_path), copy_from_current_on_enter=True):
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

    def test_postprocess(self, tmp_path) -> None:
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

        shutil.copytree(f"{TEST_FILES}/postprocess_neb", tmp_path, dirs_exist_ok=True)
        with cd(tmp_path):
            v = VaspNEBJob("hello", final=False, suffix=".test")
            v.postprocess()

            for file in neb_outputs:
                assert os.path.isfile(f"{file}.test")

            sub_folders = glob("[0-9][0-9]")
            assert sub_folders
            for sf in sub_folders:
                for file in neb_sub_outputs:
                    if os.path.isfile(f"{sf}/{file}"):
                        assert os.path.isfile(f"{sf}/{file}.test")


class TestGenerateVaspInputJob:
    def test_run(self, tmp_path) -> None:
        with cd(tmp_path):
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

    def test_graceful_stopcar_success(self, mocks: SimpleNamespace, tmp_path) -> None:
        """STOPCAR is written, VASP exits on its own, no signals sent and STOPCAR cleaned up."""
        mocks.job.graceful_termination = True
        mocks.process.poll.return_value = None
        stopcar = tmp_path / "STOPCAR"

        def fake_wait(timeout):
            assert stopcar.read_text() == "LABORT = .TRUE.\n"

        mocks.process.wait.side_effect = fake_wait
        mocks.job.terminate(directory=str(tmp_path))

        mocks.process.wait.assert_called_once_with(timeout=300.0)
        mocks.killpg.assert_not_called()
        mocks.logger.info.assert_any_call("Process 12345 stopped gracefully via STOPCAR")
        assert not stopcar.exists()

    def test_graceful_stopcar_timeout(self, mocks: SimpleNamespace, tmp_path) -> None:
        """Falls back to SIGTERM when VASP does not exit after the STOPCAR."""
        mocks.job.graceful_termination = True
        mocks.job.graceful_termination_timeout = 5.0
        mocks.process.poll.return_value = None
        mocks.process.wait.side_effect = [subprocess.TimeoutExpired("vasp", 5), None]
        mocks.job.terminate(directory=str(tmp_path))

        mocks.logger.warning.assert_any_call("STOPCAR timeout (5.0s), falling back to signals")
        mocks.killpg.assert_called_once_with(67890, signal.SIGTERM)
        assert not (tmp_path / "STOPCAR").exists()

    def test_graceful_stopcar_removed_by_vasp(self, mocks: SimpleNamespace, tmp_path) -> None:
        """No error when VASP has already deleted the STOPCAR on exit."""
        mocks.job.graceful_termination = True
        mocks.process.poll.return_value = None
        stopcar = tmp_path / "STOPCAR"
        mocks.process.wait.side_effect = lambda timeout: stopcar.unlink()
        mocks.job.terminate(directory=str(tmp_path))

        mocks.killpg.assert_not_called()
        mocks.logger.info.assert_any_call("Process 12345 stopped gracefully via STOPCAR")
        assert not stopcar.exists()

    @pytest.mark.parametrize("terminate_times_out", [False, True])
    def test_windows_skips_process_group(self, mocks: SimpleNamespace, monkeypatch, terminate_times_out: bool) -> None:
        """On Windows no process-group signals are sent; the parent process is terminated/killed directly."""
        monkeypatch.setattr("custodian.vasp.jobs.os.name", "nt")
        mocks.process.poll.return_value = None
        if terminate_times_out:
            mocks.process.wait.side_effect = [subprocess.TimeoutExpired("vasp", 10), None]
        mocks.job.terminate()

        mocks.killpg.assert_not_called()
        mocks.logger.warning.assert_any_call("Falling back to killing parent process 12345")
        mocks.process.terminate.assert_called_once()
        assert mocks.process.kill.called is terminate_times_out

    def test_graceful_stopcar_write_fails(self, mocks: SimpleNamespace, tmp_path) -> None:
        """Falls back to SIGTERM immediately when the STOPCAR cannot be written."""
        mocks.job.graceful_termination = True
        mocks.process.poll.return_value = None
        mocks.job.terminate(directory=str(tmp_path / "missing"))

        mocks.killpg.assert_called_once_with(67890, signal.SIGTERM)
        mocks.process.wait.assert_called_once_with(timeout=10.0)

    def test_neb_graceful_stopcar(self, mocks: SimpleNamespace, tmp_path) -> None:
        """VaspNEBJob supports the same graceful termination options."""
        job = VaspNEBJob(vasp_cmd=["srun", "vasp"], graceful_termination=True, graceful_termination_timeout=60.0)
        job._vasp_process = mocks.process
        mocks.process.poll.return_value = None
        job.terminate(directory=str(tmp_path))

        mocks.process.wait.assert_called_once_with(timeout=60.0)
        mocks.killpg.assert_not_called()

    def test_neb_default_terminate(self, mocks: SimpleNamespace) -> None:
        """VaspNEBJob.terminate works with default settings (previously lacked terminate_timeout)."""
        job = VaspNEBJob(vasp_cmd=["srun", "vasp"])
        job._vasp_process = mocks.process
        mocks.process.poll.return_value = None
        job.terminate()

        mocks.killpg.assert_called_once_with(67890, signal.SIGTERM)
        mocks.process.wait.assert_called_once_with(timeout=10.0)

    @pytest.mark.skipif(sys.platform == "win32", reason="sleep command and PGID not available")
    def test_integration_with_real_process(self) -> None:
        """Integration test with real subprocess (POSIX only)."""
        vasp_job = VaspJob.__new__(VaspJob)
        vasp_job.terminate_timeout = 10.0
        vasp_job.graceful_termination = False
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


# ---------------------------------------------------------------------------
# Helpers and fixtures for the extended VaspJob / VaspNEBJob tests.
# All of these work in a pytest ``tmp_path``; nothing is written to tests/files.
# ---------------------------------------------------------------------------


def _copy_inputs(dest, files=("INCAR", "POSCAR", "POTCAR", "KPOINTS")) -> None:
    for file in files:
        shutil.copy(f"{TEST_FILES}/{file}", dest / file)


@pytest.fixture
def vasp_dir(tmp_path, monkeypatch):
    """A tmp directory holding a standard INCAR/POSCAR/POTCAR/KPOINTS set, used as cwd."""
    _copy_inputs(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def mock_popen(monkeypatch):
    """Replace subprocess.Popen in custodian.vasp.jobs so nothing is executed."""
    popen = Mock(name="Popen")
    monkeypatch.setattr("custodian.vasp.jobs.subprocess.Popen", popen)
    return popen


@pytest.fixture
def sentry_scope(monkeypatch):
    """Enable the Sentry branch of VaspJob.__init__ with a fake sentry_sdk."""
    scope = Mock()
    ctx = Mock(__enter__=Mock(return_value=scope), __exit__=Mock(return_value=False))
    monkeypatch.setitem(sys.modules, "sentry_sdk", SimpleNamespace(configure_scope=lambda: ctx))
    monkeypatch.setattr("custodian.vasp.jobs.SENTRY_DSN", "https://fake@sentry/1")
    return scope


def _write_gamma_kpoints(path, gamma_only: bool = True) -> None:
    kpts = (1, 1, 1) if gamma_only else (4, 4, 4)
    Kpoints.gamma_automatic(kpts).write_file(path / "KPOINTS")


class TestVaspJobInit:
    @pytest.mark.parametrize(
        ("vasp_cmd", "expected_path"),
        [(["mpirun", "vasp_std"], "/opt/bin/vasp_std"), ("srun vasp_gam", "/opt/bin/vasp_gam")],
    )
    def test_sentry_tags(self, sentry_scope, monkeypatch, vasp_cmd, expected_path) -> None:
        monkeypatch.setattr("custodian.vasp.jobs.which", lambda cmd: f"/opt/bin/{cmd}")
        VaspJob(vasp_cmd)
        sentry_scope.set_tag.assert_any_call("vasp_path", expected_path)
        sentry_scope.set_tag.assert_any_call("vasp_cmd", vasp_cmd)

    @pytest.mark.xfail(
        strict=True,
        reason="VaspJob.__init__ only resolves vasp_path for str/list vasp_cmd; a tuple leaves vasp_path "
        "unbound, so the UnboundLocalError is swallowed and the vasp_path tag is never set",
    )
    def test_sentry_tags_tuple_cmd(self, sentry_scope, monkeypatch) -> None:
        monkeypatch.setattr("custodian.vasp.jobs.which", lambda cmd: f"/opt/bin/{cmd}")
        VaspJob(("mpirun", "vasp_std"))
        sentry_scope.set_tag.assert_any_call("vasp_path", "/opt/bin/vasp_std")

    def test_sentry_tag_failure_still_tags_cmd(self, sentry_scope, monkeypatch) -> None:
        monkeypatch.setattr("custodian.vasp.jobs.which", Mock(side_effect=RuntimeError("boom")))
        VaspJob(["vasp_std"])
        sentry_scope.set_tag.assert_called_once_with("vasp_cmd", ["vasp_std"])

    def test_gamma_vasp_cmd_is_tuple(self) -> None:
        job = VaspJob(["mpirun", "vasp_std"], gamma_vasp_cmd=["mpirun", "vasp_gam"])
        assert job.vasp_cmd == ("mpirun", "vasp_std")
        assert job.gamma_vasp_cmd == ("mpirun", "vasp_gam")
        assert VaspJob(["vasp"]).gamma_vasp_cmd is None


class TestVaspJobSetup:
    @pytest.mark.parametrize("do_backup", [True, False])
    def test_backup(self, vasp_dir, do_backup) -> None:
        VaspJob(["vasp"], backup=do_backup).setup()
        for file in ("INCAR", "POSCAR", "POTCAR", "KPOINTS"):
            assert (vasp_dir / f"{file}.orig").is_file() is do_backup

    def test_backup_without_kpoints(self, vasp_dir) -> None:
        (vasp_dir / "KPOINTS").unlink()
        VaspJob(["vasp"]).setup()
        assert not (vasp_dir / "KPOINTS.orig").exists()
        assert (vasp_dir / "INCAR.orig").is_file()

    def test_backup_respects_directory(self, tmp_path, monkeypatch) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        _copy_inputs(run_dir)
        monkeypatch.chdir(tmp_path)
        VaspJob(["vasp"]).setup(directory=str(run_dir))
        assert (run_dir / "INCAR.orig").is_file()
        assert not (tmp_path / "INCAR.orig").exists()

    @pytest.mark.parametrize(
        ("nslots", "expected_npar"),
        # conftest pins multiprocessing.cpu_count() to 64 -> NPAR = 8. For a prime core
        # count no divisor exists in [sqrt(n), n), so NPAR stays at the input value (1).
        [(None, 8), ("16", 4), ("12", 3), ("7", 1)],
    )
    def test_auto_npar(self, vasp_dir, monkeypatch, nslots, expected_npar) -> None:
        if nslots is None:
            monkeypatch.delenv("NSLOTS", raising=False)
        else:
            monkeypatch.setenv("NSLOTS", nslots)
        VaspJob(["vasp"], auto_npar=True).setup()
        assert Incar.from_file("INCAR")["NPAR"] == expected_npar

    @pytest.mark.parametrize("tag", ["LHFCALC", "LRPA", "LEPSILON"])
    def test_auto_npar_skipped_for_hf_rpa_dfpt(self, vasp_dir, tag) -> None:
        incar = Incar.from_file("INCAR")
        incar[tag] = True
        incar.write_file("INCAR")
        VaspJob(["vasp"], auto_npar=True).setup()
        assert Incar.from_file("INCAR")["NPAR"] == 1

    @pytest.mark.parametrize("ibrion", [5, 6, 7, 8])
    def test_auto_npar_removes_npar_for_hessian(self, vasp_dir, ibrion) -> None:
        incar = Incar.from_file("INCAR")
        incar["IBRION"] = ibrion
        incar.write_file("INCAR")
        VaspJob(["vasp"], auto_npar=True).setup()
        assert "NPAR" not in Incar.from_file("INCAR")

    def test_auto_npar_missing_incar_is_ignored(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        VaspJob(["vasp"], auto_npar=True, backup=False).setup()
        assert not (tmp_path / "INCAR").exists()

    def test_auto_continue_writes_default_actions(self, vasp_dir) -> None:
        VaspJob(["vasp"], auto_continue=True).setup()
        actions = loadfn("continue.json")["actions"]
        assert actions == [
            {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}},
            {"dict": "INCAR", "action": {"_set": {"ISTART": 1}}},
        ]
        # First setup only records actions; it must not touch the INCAR.
        assert "ISTART" not in Incar.from_file("INCAR")

    def test_auto_continue_applies_actions_and_backs_up(self, vasp_dir) -> None:
        shutil.copy(f"{TEST_FILES}/CONTCAR", "CONTCAR")
        job = VaspJob(["vasp"], auto_continue=True)
        job.setup()
        job.setup()
        assert (vasp_dir / "prev_run.1.tar.gz").is_file()
        assert Incar.from_file("INCAR")["ISTART"] == 1
        assert Poscar.from_file("POSCAR").structure == Poscar.from_file("CONTCAR").structure

    def test_update_incar_failure_is_logged(self, vasp_dir) -> None:
        orig = Incar.from_file("INCAR")
        with patch("custodian.vasp.jobs.logger") as logger:
            VaspJob(["vasp"], update_incar=True).setup()
        assert logger.error.call_count == 1
        assert "Unable to update INCAR" in logger.error.call_args[0][0]
        assert Incar.from_file("INCAR") == orig

    def test_settings_override(self, vasp_dir) -> None:
        shutil.copy(f"{TEST_FILES}/CONTCAR", "CONTCAR")
        override = [
            {"dict": "INCAR", "action": {"_set": {"ISTART": 1, "EDIFFG": -0.02}}},
            {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}},
        ]
        VaspJob(["vasp"], settings_override=override).setup()
        incar = Incar.from_file("INCAR")
        assert incar["ISTART"] == 1
        assert incar["EDIFFG"] == -0.02
        assert Poscar.from_file("POSCAR").structure == Poscar.from_file("CONTCAR").structure
        # backup happens before the override is applied
        assert "ISTART" not in Incar.from_file("INCAR.orig")


class TestVaspJobRun:
    def test_run_launches_popen(self, vasp_dir, mock_popen) -> None:
        job = VaspJob(["mpirun", "-np", "4", "vasp_std"], auto_gamma=False)
        proc = job.run()

        assert proc is mock_popen.return_value
        assert job._vasp_process is proc
        args, kwargs = mock_popen.call_args
        assert args[0] == ["mpirun", "-np", "4", "vasp_std"]
        assert kwargs["cwd"] == "./"
        assert kwargs["start_new_session"] is True
        assert kwargs["stdout"].name == "./vasp.out"
        assert kwargs["stderr"].name == "./std_err.txt"
        assert (vasp_dir / "vasp.out").is_file()
        assert (vasp_dir / "std_err.txt").is_file()

    def test_run_custom_output_files_and_directory(self, tmp_path, monkeypatch, mock_popen) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        job = VaspJob(["vasp_std"], output_file="out.log", stderr_file="err.log", auto_gamma=False)
        job.run(directory=str(run_dir))
        assert mock_popen.call_args.kwargs["cwd"] == str(run_dir)
        assert (run_dir / "out.log").is_file()
        assert (run_dir / "err.log").is_file()

    @pytest.mark.parametrize(
        ("gamma_only", "gamma_cmd", "available", "expected"),
        [
            # Gamma-only run, default ".gamma" suffix exists
            (True, None, {"vasp_std.gamma"}, ["mpirun", "vasp_std.gamma"]),
            # Gamma-only run, explicit gamma command exists
            (True, ["srun", "vasp_gam"], {"vasp_gam"}, ["srun", "vasp_gam"]),
            # Explicit gamma command not on PATH -> fall back to ".gamma" suffix
            (True, ["srun", "vasp_gam"], {"vasp_std.gamma"}, ["mpirun", "vasp_std.gamma"]),
            # Gamma-only run but no gamma executable at all -> regular command
            (True, None, set(), ["mpirun", "vasp_std"]),
            # Not gamma-only -> regular command regardless of availability
            (False, ["srun", "vasp_gam"], {"vasp_gam", "vasp_std.gamma"}, ["mpirun", "vasp_std"]),
        ],
    )
    def test_auto_gamma_cmd_selection(
        self, vasp_dir, monkeypatch, mock_popen, gamma_only, gamma_cmd, available, expected
    ) -> None:
        _write_gamma_kpoints(vasp_dir, gamma_only=gamma_only)
        monkeypatch.setattr("custodian.vasp.jobs.which", lambda cmd: f"/bin/{cmd}" if cmd in available else None)
        job = VaspJob(["mpirun", "vasp_std"], gamma_vasp_cmd=gamma_cmd)
        job.run()
        assert list(mock_popen.call_args[0][0]) == expected
        # The stored command must not be mutated by the ".gamma" suffixing.
        assert job.vasp_cmd == ("mpirun", "vasp_std")

    def test_auto_gamma_disabled(self, vasp_dir, monkeypatch, mock_popen) -> None:
        _write_gamma_kpoints(vasp_dir, gamma_only=True)
        which = Mock(return_value="/bin/x")
        monkeypatch.setattr("custodian.vasp.jobs.which", which)
        VaspJob(["vasp_std"], auto_gamma=False).run()
        assert mock_popen.call_args[0][0] == ["vasp_std"]
        which.assert_not_called()


class TestVaspJobPostprocess:
    @pytest.fixture
    def pp_dir(self, tmp_path, monkeypatch):
        for file in ("CONTCAR", "INCAR", "KPOINTS", "OSZICAR", "OUTCAR", "POSCAR", "POTCAR.gz", "vasprun.xml"):
            shutil.copy(f"{TEST_FILES}/postprocess/{file}", tmp_path / file)
        (tmp_path / "vasp.out").write_text("vasp output\n")
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def test_final_with_suffix_moves(self, pp_dir) -> None:
        VaspJob(["vasp"], final=True, suffix=".relax2").postprocess()
        for file in ("INCAR", "KPOINTS", "CONTCAR", "OSZICAR", "OUTCAR", "POSCAR", "vasprun.xml", "vasp.out"):
            assert (pp_dir / f"{file}.relax2").is_file()
            assert not (pp_dir / file).exists()
        # Files not in VASP_OUTPUT_FILES are untouched
        assert (pp_dir / "POTCAR.gz").is_file()
        assert not (pp_dir / "POTCAR.gz.relax2").exists()

    def test_non_final_with_suffix_copies(self, pp_dir) -> None:
        VaspJob(["vasp"], final=False, suffix=".relax1").postprocess()
        for file in ("INCAR", "OUTCAR", "vasp.out"):
            assert (pp_dir / file).is_file()
            assert (pp_dir / f"{file}.relax1").is_file()

    @pytest.mark.parametrize("final", [True, False])
    def test_no_suffix_leaves_files(self, pp_dir, final) -> None:
        before = sorted(os.listdir(pp_dir))
        VaspJob(["vasp"], final=final).postprocess()
        assert sorted(os.listdir(pp_dir)) == before

    def test_copy_magmom_only_for_non_final(self, pp_dir) -> None:
        VaspJob(["vasp"], final=True, copy_magmom=True).postprocess()
        assert Incar.from_file("INCAR")["MAGMOM"] == pytest.approx([5, -5, 0.6, 0.6])

    def test_copy_magmom_failure_is_logged(self, pp_dir) -> None:
        (pp_dir / "OUTCAR").unlink()
        with patch("custodian.vasp.jobs.logger") as logger:
            VaspJob(["vasp"], final=False, copy_magmom=True).postprocess()
        logger.error.assert_called_once_with("MAGMOM copy from OUTCAR to INCAR failed")
        assert Incar.from_file("INCAR")["MAGMOM"] == pytest.approx([5, -5, 0.6, 0.6])

    def test_removes_continue_json(self, pp_dir) -> None:
        (pp_dir / "continue.json").write_text("{}")
        VaspJob(["vasp"]).postprocess()
        assert not (pp_dir / "continue.json").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process group tests")
class TestVaspJobTerminateSigkill:
    @pytest.fixture
    def job(self):
        job = VaspJob(["vasp"])
        job._vasp_process = Mock(pid=111)
        job._vasp_process.poll.return_value = None
        job._vasp_process.wait.side_effect = [subprocess.TimeoutExpired("vasp", 10), None, None]
        return job

    def test_sigkill_process_group_gone(self, job) -> None:
        with (
            patch("os.getpgid", return_value=222),
            patch("os.killpg", side_effect=[None, ProcessLookupError]) as killpg,
            patch("custodian.vasp.jobs.logger") as logger,
        ):
            job.terminate()
        assert killpg.call_count == 2
        logger.warning.assert_called_with("Process group 222 not found")
        job._vasp_process.terminate.assert_not_called()

    def test_sigkill_oserror_falls_back_to_parent(self, job) -> None:
        with (
            patch("os.getpgid", return_value=222),
            patch("os.killpg", side_effect=[None, OSError("denied")]),
            patch("custodian.vasp.jobs.logger") as logger,
        ):
            job.terminate()
        logger.warning.assert_any_call("SIGKILL to process group 222 failed: denied")
        logger.warning.assert_any_call("Falling back to killing parent process 111")
        job._vasp_process.terminate.assert_called_once()
        job._vasp_process.kill.assert_not_called()


class TestDoubleRelaxationRun:
    def test_defaults(self) -> None:
        relax1, relax2 = VaspJob.double_relaxation_run(["vasp"])
        assert (relax1.suffix, relax1.final, relax1.backup) == (".relax1", False, True)
        assert (relax2.suffix, relax2.final, relax2.backup) == (".relax2", True, False)
        assert relax1.auto_npar is relax2.auto_npar is True
        assert relax1.settings_override is None
        assert relax2.settings_override == [
            {"dict": "INCAR", "action": {"_set": {"ISTART": 1, "EDIFFG": -0.05}}},
            {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}},
        ]

    @pytest.mark.parametrize("ediffg", [None, 0])
    def test_no_ediffg(self, ediffg) -> None:
        _, relax2 = VaspJob.double_relaxation_run(["vasp"], ediffg=ediffg)
        assert relax2.settings_override[0]["action"]["_set"] == {"ISTART": 1}

    def test_passthrough_kwargs(self) -> None:
        jobs = VaspJob.double_relaxation_run(["vasp"], auto_npar=False, auto_continue=True)
        assert all(job.auto_npar is False for job in jobs)
        assert all(job.auto_continue is True for job in jobs)

    def test_half_kpts_first_relax(self, vasp_dir) -> None:
        relax1, relax2 = VaspJob.double_relaxation_run(["vasp"], half_kpts_first_relax=True, auto_npar=False)
        low = relax1.settings_override[0]
        assert low["dict"] == "KPOINTS"
        # 8x2x2 -> 4x1x1, rounded to integers
        assert [tuple(k) for k in low["action"]["_set"]["kpoints"]] == [(4, 1, 1)]
        restore = relax2.settings_override[-1]
        assert restore["dict"] == "KPOINTS"
        assert [tuple(k) for k in restore["action"]["_set"]["kpoints"]] == [(8, 2, 2)]

        # Applying the overrides really writes the halved and then the original grid.
        shutil.copy(f"{TEST_FILES}/CONTCAR", "CONTCAR")
        relax1.setup()
        assert tuple(Kpoints.from_file("KPOINTS").kpts[0]) == (4, 1, 1)
        relax2.setup()
        assert tuple(Kpoints.from_file("KPOINTS").kpts[0]) == (8, 2, 2)
        assert Incar.from_file("INCAR")["ISTART"] == 1

    def test_half_kpts_first_relax_without_kpoints(self, vasp_dir) -> None:
        (vasp_dir / "KPOINTS").unlink()
        relax1, relax2 = VaspJob.double_relaxation_run(["vasp"], half_kpts_first_relax=True)
        assert relax1.settings_override is None
        assert len(relax2.settings_override) == 2

    def test_half_kpts_first_relax_directory(self, tmp_path, monkeypatch) -> None:
        _copy_inputs(tmp_path)
        monkeypatch.chdir(f"{TEST_FILES}/kspacing")  # no KPOINTS here; must use `directory`
        relax1, _ = VaspJob.double_relaxation_run(["vasp"], half_kpts_first_relax=True, directory=str(tmp_path))
        assert [tuple(k) for k in relax1.settings_override[0]["action"]["_set"]["kpoints"]] == [(4, 1, 1)]


class TestMetaGGAOptRun:
    @pytest.mark.parametrize(("metagga", "expected"), [(None, "SCAN"), ("R2scan", "R2scan")])
    def test_jobs(self, vasp_dir, metagga, expected) -> None:
        incar = Incar.from_file("INCAR")
        if metagga:
            incar["METAGGA"] = metagga
        incar.write_file("INCAR")

        jobs = VaspJob.metagga_opt_run(["vasp"], auto_npar=False)
        assert [job.suffix for job in jobs] == [".precondition", ".relax1", ".relax2"]
        assert [job.final for job in jobs] == [False, False, True]
        assert [job.backup for job in jobs] == [True, False, False]
        assert all(job.auto_npar is False for job in jobs)

        assert jobs[0].settings_override == [
            {"dict": "INCAR", "action": {"_set": {"METAGGA": None, "LWAVE": True, "NSW": 0}}}
        ]
        assert jobs[1].settings_override == [
            {
                "dict": "INCAR",
                "action": {"_set": {"METAGGA": expected, "ISTART": 1, "NSW": 99, "LWAVE": False}},
            },
            {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}},
        ]
        assert jobs[2].settings_override[0]["action"]["_set"] == {"ISTART": 1, "EDIFFG": -0.05}

    def test_nsw_lwave_defaults(self, vasp_dir) -> None:
        incar = Incar.from_file("INCAR")
        del incar["NSW"]
        del incar["LWAVE"]
        incar.write_file("INCAR")
        jobs = VaspJob.metagga_opt_run(["vasp"])
        settings = jobs[1].settings_override[0]["action"]["_set"]
        assert settings["NSW"] == 99
        assert settings["LWAVE"] is False

    def test_half_kpts_first_relax(self, vasp_dir) -> None:
        jobs = VaspJob.metagga_opt_run(["vasp"], half_kpts_first_relax=True)
        relax1_settings = jobs[1].settings_override
        # The halved KPOINTS override comes first, then the metaGGA restart settings.
        assert relax1_settings[0]["dict"] == "KPOINTS"
        assert [tuple(k) for k in relax1_settings[0]["action"]["_set"]["kpoints"]] == [(4, 1, 1)]
        assert relax1_settings[1]["action"]["_set"]["METAGGA"] == "SCAN"
        assert [tuple(k) for k in jobs[2].settings_override[-1]["action"]["_set"]["kpoints"]] == [(8, 2, 2)]

    def test_precondition_then_metagga_setup(self, vasp_dir) -> None:
        incar = Incar.from_file("INCAR")
        incar["METAGGA"] = "R2scan"
        incar.write_file("INCAR")
        shutil.copy(f"{TEST_FILES}/CONTCAR", "CONTCAR")
        pre, relax1, _ = VaspJob.metagga_opt_run(["vasp"], auto_npar=False)

        pre.setup()
        incar = Incar.from_file("INCAR")
        # METAGGA is "unset" by writing METAGGA = None
        assert str(incar["METAGGA"]).lower() == "none"
        assert incar["NSW"] == 0
        assert incar["LWAVE"] is True
        assert Incar.from_file("INCAR.orig")["METAGGA"].lower() == "r2scan"

        relax1.setup()
        incar = Incar.from_file("INCAR")
        assert incar["METAGGA"].lower() == "r2scan"
        assert incar["NSW"] == 99
        assert incar["ISTART"] == 1
        assert incar["LWAVE"] is False

    @pytest.mark.parametrize("auto_continue", [True, False])
    def test_auto_continue_forwarded(self, vasp_dir, auto_continue) -> None:
        jobs = VaspJob.metagga_opt_run(["vasp"], auto_continue=auto_continue)
        assert [job.auto_continue for job in jobs] == [auto_continue] * 3


def _scale_contcar(directory, vol_scale: float) -> None:
    structure = Poscar.from_file(directory / "POSCAR").structure
    structure.scale_lattice(structure.volume * vol_scale)
    Poscar(structure).write_file(directory / "CONTCAR")


class TestFullOptRun:
    def test_runs_until_volume_converged(self, vasp_dir) -> None:
        gen = VaspJob.full_opt_run(["vasp"], vol_change_tol=0.02, auto_npar=False)

        job1 = next(gen)
        assert (job1.suffix, job1.backup, job1.final) == (".relax1", True, False)
        assert job1.settings_override is None
        assert job1.auto_npar is False
        job1.setup()
        _scale_contcar(vasp_dir, 1.10)  # 10% volume change -> keep going

        job2 = next(gen)
        assert (job2.suffix, job2.backup) == (".relax2", False)
        assert job2.settings_override == [
            {"dict": "INCAR", "action": {"_set": {"ISTART": 1, "EDIFFG": -0.05}}},
            {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}},
        ]
        job2.setup()
        assert Poscar.from_file("POSCAR").structure == Poscar.from_file("CONTCAR").structure
        assert Incar.from_file("INCAR")["EDIFFG"] == -0.05
        _scale_contcar(vasp_dir, 1.01)  # 1% volume change -> converged

        with pytest.raises(StopIteration):
            next(gen)

    def test_negative_volume_change(self, vasp_dir) -> None:
        gen = VaspJob.full_opt_run(["vasp"], vol_change_tol=0.02)
        next(gen)
        _scale_contcar(vasp_dir, 0.90)
        assert next(gen).suffix == ".relax2"

    def test_max_steps(self, vasp_dir) -> None:
        jobs = []
        for job in VaspJob.full_opt_run(["vasp"], max_steps=3, ediffg=None):
            jobs.append(job)
            _scale_contcar(vasp_dir, 1.5)  # never converges
        assert [job.suffix for job in jobs] == [".relax1", ".relax2", ".relax3"]
        assert jobs[1].settings_override[0]["action"]["_set"] == {"ISTART": 1}

    def test_half_kpts_first_relax(self, vasp_dir) -> None:
        gen = VaspJob.full_opt_run(["vasp"], half_kpts_first_relax=True)
        job1 = next(gen)
        assert job1.settings_override[0]["dict"] == "KPOINTS"
        _scale_contcar(vasp_dir, 1.10)
        job2 = next(gen)
        assert job2.settings_override[-1] == {
            "dict": "KPOINTS",
            "action": {"_set": Kpoints.from_file("KPOINTS").as_dict()},
        }
        _scale_contcar(vasp_dir, 1.10)
        # Only the second job restores the original k-point grid.
        assert len(next(gen).settings_override) == 2

    @pytest.mark.parametrize(("kpts", "expected"), [((8, 4, 2), [4, 2, 1]), ((3, 5, 1), [2, 2, 1])])
    def test_half_kpts_are_integers(self, vasp_dir, kpts, expected) -> None:
        Kpoints.monkhorst_automatic(kpts).write_file("KPOINTS")
        job1 = next(VaspJob.full_opt_run(["vasp"], half_kpts_first_relax=True))
        new_kpts = list(job1.settings_override[0]["action"]["_set"]["kpoints"][0])
        assert new_kpts == expected
        assert all(isinstance(k, int) for k in new_kpts)
        # Matches double_relaxation_run's halving.
        relax1, _ = VaspJob.double_relaxation_run(["vasp"], half_kpts_first_relax=True)
        assert list(relax1.settings_override[0]["action"]["_set"]["kpoints"][0]) == expected

    def test_half_kpts_first_relax_without_kpoints(self, vasp_dir) -> None:
        (vasp_dir / "KPOINTS").unlink()
        gen = VaspJob.full_opt_run(["vasp"], half_kpts_first_relax=True)
        assert next(gen).settings_override is None
        _scale_contcar(vasp_dir, 1.10)
        assert len(next(gen).settings_override) == 2


class _FakeVasprun:
    """Stand-in for Vasprun used by constrained_opt_run.

    Reads the current POSCAR and returns an energy from a model E(x) of the constrained
    lattice parameter.
    """

    energy_fn = staticmethod(lambda x: 0.0)
    lattice_index = 2
    calls: list = []

    def __init__(self, filename, **kwargs) -> None:
        type(self).calls.append(filename)
        structure = Poscar.from_file("POSCAR").structure
        self.final_structure = SimpleNamespace(
            lattice=SimpleNamespace(abc=structure.lattice.abc, matrix=structure.lattice.matrix.copy()),
            species=structure.species,
            frac_coords=structure.frac_coords,
        )
        self.final_energy = type(self).energy_fn(structure.lattice.abc[type(self).lattice_index])


@pytest.fixture
def fake_vasprun(monkeypatch):
    def _install(energy_fn, lattice_index=2):
        cls = type("FakeVasprun", (_FakeVasprun,), {"calls": []})
        cls.energy_fn = staticmethod(energy_fn)
        cls.lattice_index = lattice_index
        monkeypatch.setattr("custodian.vasp.jobs.Vasprun", cls)
        return cls

    return _install


def _drive_constrained(gen) -> list:
    """Run the constrained_opt_run generator, applying each job's setup like Custodian would."""
    jobs = []
    for job in gen:
        job.setup()
        jobs.append(job)
    return jobs


def _read_eos(path) -> list[tuple[float, ...]]:
    lines = (path / "EOS.txt").read_text().splitlines()
    return [tuple(float(v) for v in line.split()) for line in lines[1:]]


def _suffix_x(job) -> float:
    return float(job.suffix.removeprefix(".static."))


class TestConstrainedOptRun:
    @pytest.mark.parametrize(("direction", "index"), [("a", 0), ("b", 1), ("c", 2)])
    @pytest.mark.parametrize("algo", ["bfgs", "bisection"])
    def test_converges_to_minimum(self, vasp_dir, fake_vasprun, direction, index, algo) -> None:
        orig = Poscar.from_file("POSCAR").structure.lattice.abc
        x0 = orig[index]
        target = x0 * 0.97
        fake_vasprun(lambda x: 2.0 * (x - target) ** 2, lattice_index=index)

        gen = VaspJob.constrained_opt_run(["vasp"], direction, initial_strain=-0.05, algo=algo, auto_npar=False)
        jobs = _drive_constrained(gen)

        # First job: ISIF=2 relax at the original lattice parameter, with backup.
        assert jobs[0].backup is True
        assert jobs[0].suffix == f".static.{x0}"
        assert jobs[0].settings_override == [{"dict": "INCAR", "action": {"_set": {"ISIF": 2, "NSW": 99}}}]
        assert all(not job.backup and not job.final and job.auto_npar is False for job in jobs[1:])

        # Second job applies the initial strain.
        assert _suffix_x(jobs[1]) == pytest.approx(x0 * 0.95)

        # Subsequent jobs copy POSCAR.<x> to POSCAR and keep ISIF=2.
        for job in jobs[1:]:
            x = _suffix_x(job)
            assert job.settings_override == [
                {"dict": "INCAR", "action": {"_set": {"ISTART": 1, "NSW": 99, "ISIF": 2}}},
                {"file": os.path.join("./", f"POSCAR.{x}"), "action": {"_file_copy": {"dest": "POSCAR"}}},
            ]
            abc = Structure.from_file(vasp_dir / f"POSCAR.{x}").lattice.abc
            assert abc[index] == pytest.approx(x)
            # Other lattice vectors are unchanged.
            for other in {0, 1, 2} - {index}:
                assert abc[other] == pytest.approx(orig[other])

        incar = Incar.from_file("INCAR")
        assert incar["ISIF"] == 2
        assert incar["ISTART"] == 1

        assert (vasp_dir / "EOS.txt").read_text().startswith(f"# {direction} energy\n")
        eos = _read_eos(vasp_dir)
        assert [row[0] for row in eos] == sorted(row[0] for row in eos)
        best_x = min(eos, key=lambda row: row[1])[0]
        assert best_x == pytest.approx(target, abs=0.05)
        # Convergence: the two lowest energies are within e_tol = 10 * EDIFF.
        energies = sorted(row[1] for row in eos)
        assert energies[1] - energies[0] < 10 * incar["EDIFF"]

    @pytest.mark.parametrize(
        ("target_scale", "expect_direction"),
        [
            # Minimum far below the start: extrapolate below the lowest bound.
            (0.85, "below"),
            # Minimum above the start while the initial strain points the wrong way.
            (1.10, "above"),
        ],
    )
    def test_bracketing_outside_bounds(self, vasp_dir, fake_vasprun, target_scale, expect_direction) -> None:
        x0 = Poscar.from_file("POSCAR").structure.lattice.c
        target = x0 * target_scale
        fake_vasprun(lambda x: (x - target) ** 2)

        with patch("custodian.vasp.jobs.logger") as logger:
            jobs = _drive_constrained(
                VaspJob.constrained_opt_run(["vasp"], "c", initial_strain=-0.02, algo="bisection")
            )

        messages = [call.args[0] for call in logger.info.call_args_list]
        assert any(f"Lowest energy lies {expect_direction} bounds" in msg for msg in messages)
        xs = [_suffix_x(job) for job in jobs]
        if expect_direction == "below":
            assert min(xs) < x0 * 0.98
        else:
            assert max(xs) > x0
        best_x = min(_read_eos(vasp_dir), key=lambda row: row[1])[0]
        assert best_x == pytest.approx(target, abs=0.1)

    @staticmethod
    def _tighten_ediff(ediff: float = 1e-10) -> None:
        incar = Incar.from_file("INCAR")
        incar["EDIFF"] = ediff
        incar.write_file("INCAR")

    def test_bfgs_quadratic_fit(self, vasp_dir, fake_vasprun) -> None:
        self._tighten_ediff()
        x0 = Poscar.from_file("POSCAR").structure.lattice.c
        target = x0 * 0.97
        fake_vasprun(lambda x: (x - target) ** 2)

        with patch("custodian.vasp.jobs.logger") as logger:
            jobs = _drive_constrained(
                VaspJob.constrained_opt_run(["vasp"], "c", initial_strain=-0.05, algo="bfgs", max_steps=6)
            )

        messages = [call.args[0] for call in logger.info.call_args_list]
        bfgs_msgs = [msg for msg in messages if msg.startswith("BFGS minimized c = ")]
        assert bfgs_msgs
        # The quadratic fit to an exactly quadratic E(x) lands on the true minimum.
        assert float(bfgs_msgs[0].rsplit("= ", 1)[1].rstrip(".")) == pytest.approx(target, abs=1e-3)
        assert any(_suffix_x(job) == pytest.approx(target, abs=1e-3) for job in jobs)

    def test_bisection_never_uses_fit(self, vasp_dir, fake_vasprun, monkeypatch) -> None:
        import scipy.optimize

        self._tighten_ediff()
        x0 = Poscar.from_file("POSCAR").structure.lattice.c
        fake_vasprun(lambda x: (x - x0 * 0.97) ** 2)
        minimize = Mock()
        monkeypatch.setattr(scipy.optimize, "minimize", minimize)
        with patch("custodian.vasp.jobs.logger") as logger:
            _drive_constrained(
                VaspJob.constrained_opt_run(["vasp"], "c", initial_strain=-0.05, algo="bisection", max_steps=6)
            )
        minimize.assert_not_called()
        assert any(call.args[0].startswith("Bisection c = ") for call in logger.info.call_args_list)

    def test_bfgs_failure_falls_back_to_bisection(self, vasp_dir, fake_vasprun, monkeypatch) -> None:
        import scipy.optimize

        self._tighten_ediff()
        x0 = Poscar.from_file("POSCAR").structure.lattice.c
        target = x0 * 0.97
        fake_vasprun(lambda x: (x - target) ** 2)
        minimize = Mock(return_value=SimpleNamespace(success=False, x=[0.0]))
        monkeypatch.setattr(scipy.optimize, "minimize", minimize)

        with patch("custodian.vasp.jobs.logger") as logger:
            _drive_constrained(
                VaspJob.constrained_opt_run(["vasp"], "c", initial_strain=-0.05, algo="bfgs", max_steps=6)
            )

        assert minimize.called
        messages = [call.args[0] for call in logger.info.call_args_list]
        assert "Negative lattice constant!" in messages
        assert any(msg.startswith("Falling back on bisection c = ") for msg in messages)

    @pytest.mark.parametrize(("atom_relax", "nsw"), [(True, 99), (False, 0)])
    def test_atom_relax(self, vasp_dir, fake_vasprun, atom_relax, nsw) -> None:
        fake_vasprun(lambda x: (x - 4.5) ** 2)
        gen = VaspJob.constrained_opt_run(["vasp"], "c", initial_strain=-0.05, atom_relax=atom_relax, max_steps=2)
        jobs = _drive_constrained(gen)
        assert jobs[0].settings_override[0]["action"]["_set"]["NSW"] == nsw
        assert jobs[1].settings_override[0]["action"]["_set"]["NSW"] == nsw
        assert Incar.from_file("INCAR")["NSW"] == nsw

    def test_max_steps_writes_eos(self, vasp_dir, fake_vasprun) -> None:
        fake_vasprun(lambda x: -x)  # monotonic: never converges
        jobs = _drive_constrained(VaspJob.constrained_opt_run(["vasp"], "c", initial_strain=0.05, max_steps=4))
        assert len(jobs) == 4
        # Energies are only recorded when the next job is generated, so 3 points for 4 jobs.
        assert len(_read_eos(vasp_dir)) == 3

    def test_single_step_writes_empty_eos(self, vasp_dir, fake_vasprun) -> None:
        fake_vasprun(lambda x: 0.0)
        jobs = _drive_constrained(VaspJob.constrained_opt_run(["vasp"], "a", initial_strain=0.01, max_steps=1))
        assert len(jobs) == 1
        assert (vasp_dir / "EOS.txt").read_text() == "# a energy\n"

    @pytest.mark.parametrize(
        ("incar_update", "n_jobs"),
        [
            # Positive EDIFFG is used directly as the energy tolerance: huge -> stop after 2 jobs.
            ({"EDIFFG": 10.0}, 2),
            # Negative EDIFFG (force criterion) falls back to 10 * EDIFF; tiny -> runs to max_steps.
            ({"EDIFFG": -0.01, "EDIFF": 1e-14}, 6),
        ],
    )
    def test_energy_tolerance(self, vasp_dir, fake_vasprun, incar_update, n_jobs) -> None:
        incar = Incar.from_file("INCAR")
        incar.update(incar_update)
        incar.write_file("INCAR")
        fake_vasprun(lambda x: (x - 4.0) ** 2)
        jobs = _drive_constrained(VaspJob.constrained_opt_run(["vasp"], "c", initial_strain=-0.05, max_steps=6))
        assert len(jobs) == n_jobs

    def test_default_ediff(self, vasp_dir, fake_vasprun) -> None:
        incar = Incar.from_file("INCAR")
        del incar["EDIFF"]
        incar.write_file("INCAR")
        x0 = Poscar.from_file("POSCAR").structure.lattice.c
        # Energy difference of 5e-4 between the first two points < default e_tol of 1e-3 -> stop.
        fake_vasprun(lambda x: 0.0 if x > x0 - 0.01 else 5e-4)
        jobs = _drive_constrained(VaspJob.constrained_opt_run(["vasp"], "c", initial_strain=-0.05))
        assert len(jobs) == 2

    def test_reads_vasprun_from_directory(self, vasp_dir, fake_vasprun) -> None:
        fake = fake_vasprun(lambda x: (x - 4.5) ** 2)
        gen = VaspJob.constrained_opt_run(["vasp"], "c", initial_strain=-0.05, directory=str(vasp_dir))
        next(gen)
        next(gen)
        assert fake.calls == [os.path.join(str(vasp_dir), "vasprun.xml")]

    def test_real_structure_lattice_is_writable(self, vasp_dir, monkeypatch) -> None:
        structure = Poscar.from_file("POSCAR").structure
        vasprun = SimpleNamespace(final_structure=structure, final_energy=-1.0)
        monkeypatch.setattr("custodian.vasp.jobs.Vasprun", lambda *args, **kwargs: vasprun)
        gen = VaspJob.constrained_opt_run(["vasp"], "c", initial_strain=-0.05)
        next(gen)
        c0 = structure.lattice.c
        job = next(gen)
        assert _suffix_x(job) == pytest.approx(c0 * 0.95)
        assert Structure.from_file(f"POSCAR.{_suffix_x(job)}").lattice.c == pytest.approx(c0 * 0.95)
        # The Vasprun's structure is not modified in place.
        assert structure.lattice.c == pytest.approx(c0)


@pytest.fixture
def neb_dir(tmp_path, monkeypatch):
    shutil.copytree(f"{TEST_FILES}/setup_neb", tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestVaspNEBJobExtended:
    def test_defaults(self) -> None:
        job = VaspNEBJob(["vasp"], gamma_vasp_cmd=["vasp_gam"])
        assert job.output_file == "neb_vasp.out"
        assert job.stderr_file == "neb_std_err.txt"
        assert job.auto_npar is True
        assert job.half_kpts is False
        assert job.gamma_vasp_cmd == ("vasp_gam",)

    def test_get_neb_dirs(self, neb_dir) -> None:
        (neb_dir / "10").mkdir()
        (neb_dir / "abc").mkdir()
        (neb_dir / "05").write_text("not a dir")
        neb_dirs, neb_sub = VaspNEBJob(["vasp"])._get_neb_dirs("./")
        assert neb_dirs == [os.path.join("./", name) for name in ("00", "01", "02", "03", "04", "10")]
        assert neb_sub == [os.path.join("./", name) for name in ("01", "02", "03", "04")]

    def test_setup_backup(self, neb_dir) -> None:
        VaspNEBJob(["vasp"], auto_npar=False).setup()
        for file in ("INCAR", "KPOINTS", "POTCAR"):
            assert (neb_dir / f"{file}.orig").is_file()
        for image in ("00", "01", "02", "03", "04"):
            assert (neb_dir / image / "POSCAR.orig").is_file()
        assert Incar.from_file("INCAR")["NPAR"] == 2

    def test_setup_no_backup(self, neb_dir) -> None:
        VaspNEBJob(["vasp"], backup=False, auto_npar=False).setup()
        assert not list(neb_dir.glob("**/*.orig"))

    # Prime core count: no divisor in [sqrt(n), n), so the input NPAR (2) is kept.
    @pytest.mark.parametrize(("nslots", "expected"), [(None, 8), ("16", 4), ("7", 2)])
    def test_setup_auto_npar(self, neb_dir, monkeypatch, nslots, expected) -> None:
        if nslots is None:
            monkeypatch.delenv("NSLOTS", raising=False)
        else:
            monkeypatch.setenv("NSLOTS", nslots)
        VaspNEBJob(["vasp"]).setup()
        assert Incar.from_file("INCAR")["NPAR"] == expected

    def test_setup_auto_npar_missing_incar(self, neb_dir) -> None:
        (neb_dir / "INCAR").unlink()
        VaspNEBJob(["vasp"], backup=False).setup()
        assert not (neb_dir / "INCAR").exists()

    @pytest.mark.parametrize(
        ("kpts", "expected", "style"),
        [((8, 4, 2), (4, 2, 1), "Monkhorst"), ((2, 2, 2), (1, 1, 1), "Gamma"), ((3, 1, 1), (1, 1, 1), "Gamma")],
    )
    def test_setup_half_kpts(self, neb_dir, kpts, expected, style) -> None:
        Kpoints.monkhorst_automatic(kpts).write_file("KPOINTS")
        VaspNEBJob(["vasp"], half_kpts=True, auto_npar=False, backup=False).setup()
        new = Kpoints.from_file("KPOINTS")
        assert tuple(new.kpts[0]) == expected
        assert new.style.name == style

    def test_setup_half_kpts_without_kpoints(self, neb_dir) -> None:
        (neb_dir / "KPOINTS").unlink()
        VaspNEBJob(["vasp"], half_kpts=True, auto_npar=False, backup=False).setup()
        assert not (neb_dir / "KPOINTS").exists()

    def test_setup_auto_continue_readonly_stopcar(self, neb_dir) -> None:
        for image in ("01", "02", "03"):
            structure = Poscar.from_file(neb_dir / image / "POSCAR").structure
            structure.perturb(0.05)
            Poscar(structure).write_file(neb_dir / image / "CONTCAR")
        stopcar = neb_dir / "STOPCAR"
        stopcar.write_text("LSTOP = .TRUE.\n")
        stopcar.chmod(0o444)

        VaspNEBJob(["vasp"], auto_continue=True, auto_npar=False, backup=False).setup()

        assert not stopcar.exists()
        for image in ("01", "02", "03"):
            assert (neb_dir / image / "POSCAR").read_text() == (neb_dir / image / "CONTCAR").read_text()

    def test_setup_auto_continue_writable_stopcar_untouched(self, neb_dir) -> None:
        stopcar = neb_dir / "STOPCAR"
        stopcar.write_text("LSTOP = .TRUE.\n")
        before = (neb_dir / "01" / "POSCAR").read_text()
        VaspNEBJob(["vasp"], auto_continue=True, auto_npar=False, backup=False).setup()
        assert stopcar.exists()
        assert (neb_dir / "01" / "POSCAR").read_text() == before

    def test_setup_settings_override(self, neb_dir) -> None:
        override = [{"dict": "INCAR", "action": {"_set": {"IMAGES": 5, "SPRING": -5}}}]
        VaspNEBJob(["vasp"], auto_npar=False, settings_override=override).setup()
        incar = Incar.from_file("INCAR")
        assert incar["IMAGES"] == 5
        assert incar["SPRING"] == -5
        assert Incar.from_file("INCAR.orig")["IMAGES"] == 3

    def test_setup_and_postprocess_respect_directory(self, tmp_path, monkeypatch) -> None:
        run_dir = tmp_path / "neb"
        shutil.copytree(f"{TEST_FILES}/setup_neb", run_dir)
        # Same-named image folders in the cwd must be ignored.
        (tmp_path / "01").mkdir()
        monkeypatch.chdir(tmp_path)
        job = VaspNEBJob(["vasp"], auto_npar=False, suffix=".test")
        job.setup(directory=str(run_dir))
        assert (run_dir / "01" / "POSCAR.orig").is_file()
        assert not (tmp_path / "01" / "POSCAR.orig").exists()

        (run_dir / "02" / "CONTCAR").write_text("contcar")
        job.postprocess(directory=str(run_dir))
        assert (run_dir / "02" / "CONTCAR.test").read_text() == "contcar"

    @pytest.mark.parametrize(
        ("gamma_only", "gamma_cmd", "available", "expected"),
        [
            (True, None, {"vasp_std.gamma"}, ["mpirun", "vasp_std.gamma"]),
            (True, ["srun", "vasp_gam"], {"vasp_gam"}, ["srun", "vasp_gam"]),
            (True, None, set(), ["mpirun", "vasp_std"]),
            (False, None, {"vasp_std.gamma"}, ["mpirun", "vasp_std"]),
        ],
    )
    def test_run(self, neb_dir, monkeypatch, mock_popen, gamma_only, gamma_cmd, available, expected) -> None:
        _write_gamma_kpoints(neb_dir, gamma_only=gamma_only)
        monkeypatch.setattr("custodian.vasp.jobs.which", lambda cmd: f"/bin/{cmd}" if cmd in available else None)
        job = VaspNEBJob(["mpirun", "vasp_std"], gamma_vasp_cmd=gamma_cmd)
        proc = job.run()

        assert proc is mock_popen.return_value
        assert job._vasp_process is proc
        args, kwargs = mock_popen.call_args
        assert list(args[0]) == expected
        assert kwargs["start_new_session"] is True
        assert kwargs["cwd"] == "./"
        assert (neb_dir / "neb_vasp.out").is_file()
        assert (neb_dir / "neb_std_err.txt").is_file()

    def test_run_no_auto_gamma(self, neb_dir, mock_popen) -> None:
        VaspNEBJob(["vasp_std"], auto_gamma=False).run()
        assert mock_popen.call_args[0][0] == ["vasp_std"]


class TestVaspNEBJobPostprocess:
    @pytest.fixture
    def pp_neb(self, tmp_path, monkeypatch):
        shutil.copytree(f"{TEST_FILES}/postprocess_neb", tmp_path, dirs_exist_ok=True)
        (tmp_path / "neb_vasp.out").write_text("out\n")
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def test_final_moves(self, pp_neb) -> None:
        sub_files = sorted(os.listdir(pp_neb / "01"))
        VaspNEBJob(["vasp"], final=True, suffix=".neb").postprocess()
        for file in ("INCAR", "KPOINTS", "POTCAR", "vasprun.xml", "neb_vasp.out"):
            assert (pp_neb / f"{file}.neb").is_file()
            assert not (pp_neb / file).exists()
        assert sorted(os.listdir(pp_neb / "01")) == sorted(f"{file}.neb" for file in sub_files)
        assert (pp_neb / "00" / "POSCAR.neb").is_file()
        assert not (pp_neb / "00" / "POSCAR").exists()

    def test_non_final_copies(self, pp_neb) -> None:
        VaspNEBJob(["vasp"], final=False, suffix=".neb").postprocess()
        for file in ("INCAR", "vasprun.xml", "neb_vasp.out"):
            assert (pp_neb / file).is_file()
            assert (pp_neb / f"{file}.neb").is_file()
        assert (pp_neb / "01" / "OUTCAR").is_file()
        assert (pp_neb / "01" / "OUTCAR.neb").is_file()

    def test_no_suffix_noop(self, pp_neb) -> None:
        before = sorted(str(path.relative_to(pp_neb)) for path in pp_neb.rglob("*"))
        VaspNEBJob(["vasp"], final=True).postprocess()
        assert sorted(str(path.relative_to(pp_neb)) for path in pp_neb.rglob("*")) == before


class TestGenerateVaspInputJobExtended:
    def test_uses_contcar_over_poscar(self, vasp_dir) -> None:
        contcar = Structure.from_file(f"{TEST_FILES}/CONTCAR")
        shutil.copy(f"{TEST_FILES}/CONTCAR", "CONTCAR")
        job = GenerateVaspInputJob("pymatgen.io.vasp.sets.MPStaticSet", user_incar_settings={"NSW": 3})
        assert job.kwargs == {"user_incar_settings": {"NSW": 3}}
        job.setup()
        job.run()
        job.postprocess()
        assert Structure.from_file("POSCAR").matches(contcar)
        assert Structure.from_file("POSCAR").lattice.abc == pytest.approx(contcar.lattice.abc)
        assert Incar.from_file("INCAR")["NSW"] == 3

    def test_contcar_only_without_contcar_raises(self, vasp_dir) -> None:
        job = GenerateVaspInputJob("pymatgen.io.vasp.sets.MPStaticSet")
        with pytest.raises(RuntimeError, match="No CONTCAR/POSCAR detected"):
            job.run()

    def test_directory(self, tmp_path, monkeypatch) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        _copy_inputs(run_dir, files=("POSCAR",))
        monkeypatch.chdir(tmp_path)
        GenerateVaspInputJob("pymatgen.io.vasp.sets.MPStaticSet", contcar_only=False).run(directory=str(run_dir))
        assert (run_dir / "INCAR").is_file()
        assert (run_dir / "KPOINTS").is_file()
        assert not (tmp_path / "INCAR").exists()

    def test_as_from_dict(self) -> None:
        job = GenerateVaspInputJob("pymatgen.io.vasp.sets.MPStaticSet", contcar_only=False)
        job2 = GenerateVaspInputJob.from_dict(job.as_dict())
        assert job2.input_set == "pymatgen.io.vasp.sets.MPStaticSet"
        assert job2.contcar_only is False


class TestGammaPointOnlyCheck:
    @pytest.fixture
    def vis(self):
        structure = Structure(lattice=[[15, 0, 0], [0, 15, 0], [0, 0, 15]], species=["Na"], coords=[[0.5] * 3])
        return MPRelaxSet(structure=structure).get_input_set()

    @pytest.mark.parametrize("tag", ["LEPSILON", "LOPTICS"])
    def test_dfpt_never_gamma(self, vis, tag) -> None:
        assert _gamma_point_only_check(vis)
        vis["INCAR"][tag] = True
        assert not _gamma_point_only_check(vis)

    def test_no_kpoints_no_kspacing(self, vis) -> None:
        vis["KPOINTS"] = None
        vis["INCAR"].pop("KSPACING", None)
        assert not _gamma_point_only_check(vis)

    @pytest.mark.parametrize(("kspacing", "expected"), [(1.0, True), (0.1, False)])
    def test_kspacing_without_kpoints(self, vis, kspacing, expected) -> None:
        vis["KPOINTS"] = None
        vis["INCAR"]["KSPACING"] = kspacing
        assert bool(_gamma_point_only_check(vis)) is expected
