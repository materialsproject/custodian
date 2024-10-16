import os
from pathlib import Path
from unittest import mock
from unittest.mock import ANY, MagicMock, patch

import psutil

from custodian.jdftx.jobs import JDFTxJob

TEST_DIR = Path(__file__).resolve().parent.parent
TEST_FILES = f"{TEST_DIR}/files/jdftx"


def create_mock_process(
    name="jdftx", open_files=None, pid=12345, name_side_effect=None, wait_side_effect=None, terminate_side_effect=None
):
    if open_files is None:  # Set a default value if not provided
        open_files = [MagicMock(path=os.path.join("default_path", "jdftx.out"))]

    mock_process = mock.Mock(spec=psutil.Process)
    mock_process.name.return_value = name
    mock_process.open_files.return_value = open_files
    mock_process.pid = pid
    mock_process.name.side_effect = name_side_effect
    mock_process.wait.side_effect = wait_side_effect
    mock_process.terminate.side_effect = terminate_side_effect
    return mock_process


def test_jdftx_job_init(jdftx_job):
    assert jdftx_job.jdftx_cmd == "jdftx"
    assert jdftx_job.input_file == "init.in"
    assert jdftx_job.output_file == "jdftx.out"
    assert jdftx_job.stderr_file == "std_err.txt"


def test_jdftx_job_setup(jdftx_job, tmp_path):
    jdftx_job.setup(str(tmp_path))
    # Setup method doesn't do anything, so just checking that it doesn't raise an exception


def test_jdftx_job_run(jdftx_job, tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_process = MagicMock()
        mock_run.return_value = mock_process

        result = jdftx_job.run(str(tmp_path))

        assert result == mock_process
        mock_run.assert_called_once_with(
            ["jdftx", "-i", "init.in", "-o", "jdftx.out"],
            cwd=str(tmp_path),
            stdout=ANY,
            stderr=ANY,
            shell=False,
            check=False,
        )


def test_jdftx_job_run_creates_output_files(jdftx_job, tmp_path):
    with patch("subprocess.run"):
        jdftx_job.run(str(tmp_path))

    assert os.path.exists(os.path.join(str(tmp_path), "jdftx.out"))
    assert os.path.exists(os.path.join(str(tmp_path), "std_err.txt"))


def test_jdftx_job_postprocess(jdftx_job, tmp_path):
    jdftx_job.postprocess(str(tmp_path))
    # Postprocess method doesn't do anything, so we just check that it doesn't raise an exception


@mock.patch("psutil.pid_exists")
@mock.patch("subprocess.run")
@mock.patch.object(JDFTxJob, "terminate_process", autospec=True)
def test_jdftx_job_terminate(mock_terminate_process, mock_subprocess_run, mock_pid_exists, jdftx_job, tmp_path, caplog):
    open_files = [MagicMock(path=os.path.join(str(tmp_path), jdftx_job.output_file))]
    # Test when JDFTx process exists
    mock_process = create_mock_process(name="jdftx", open_files=open_files, pid=12345)

    with patch("psutil.process_iter", return_value=[mock_process]):
        mock_pid_exists.return_value = True
        jdftx_job.terminate(str(tmp_path))
        mock_terminate_process.assert_called_once_with(mock_process)
        mock_subprocess_run.assert_not_called()

    mock_terminate_process.reset_mock()
    mock_subprocess_run.reset_mock()

    # Test when no JDFTx process exists
    mock_process = create_mock_process(name="vasp", open_files=open_files, pid=12345)

    with patch("psutil.process_iter", return_value=[mock_process]):
        jdftx_job.terminate(str(tmp_path))
        mock_terminate_process.assert_not_called()
        mock_subprocess_run.assert_called_once_with(["killall", "jdftx"], check=False)

    mock_terminate_process.reset_mock()
    mock_subprocess_run.reset_mock()

    # Test when psutil.process_iter raises NoSuchProcess
    mock_process = create_mock_process(
        name="jdftx", open_files=open_files, pid=12345, name_side_effect=psutil.NoSuchProcess(pid=12345)
    )

    with caplog.at_level("WARNING"):
        with patch("psutil.process_iter", return_value=[mock_process]):
            jdftx_job.terminate(str(tmp_path))
            mock_terminate_process.assert_not_called()
            mock_subprocess_run.assert_called_with(["killall", "jdftx"], check=False)

        assert "Exception" in caplog.text
        assert "encountered while killing JDFTx" in caplog.text

    mock_terminate_process.reset_mock()
    mock_subprocess_run.reset_mock()

    # Test when psutil.process_iter raises AccessDenied
    with caplog.at_level("WARNING"):
        mock_process = create_mock_process(
            name="jdftx", open_files=open_files, pid=12345, name_side_effect=psutil.AccessDenied(pid=12345)
        )
        with patch("psutil.process_iter", return_value=[mock_process]):
            jdftx_job.terminate(str(tmp_path))
            mock_terminate_process.assert_not_called()
            mock_subprocess_run.assert_called_with(["killall", "jdftx"], check=False)

        assert "Exception" in caplog.text
        assert "encountered while killing JDFTx" in caplog.text


def test_terminate_process(jdftx_job, caplog):
    # Test successful termination
    mock_process = create_mock_process()
    mock_process.terminate.return_value = None  # Simulate successful termination
    mock_process.wait.return_value = None  # Simulate process finished immediately
    with caplog.at_level("INFO"):
        jdftx_job.terminate_process(mock_process)

    mock_process.terminate.assert_called_once()
    mock_process.wait.assert_called_once()

    assert "Process" in caplog.text
    assert "terminated gracefully" in caplog.text

    mock_process.reset_mock()

    # Test when process doesn't terminate gracefully
    mock_process = create_mock_process(pid=12345, wait_side_effect=psutil.TimeoutExpired(seconds=5))
    mock_process.terminate.return_value = None

    jdftx_job.terminate_process(mock_process)
    mock_process.terminate.assert_called_once()
    mock_process.kill.assert_called_once()
    mock_process.wait.assert_called()

    mock_process.reset_mock()

    # Test when process raises NoSuchProcess
    mock_process = create_mock_process(pid=12345, terminate_side_effect=psutil.NoSuchProcess(pid=12345))
    with caplog.at_level("WARNING"):
        jdftx_job.terminate_process(mock_process)

    assert "Error while terminating process" in caplog.text

    mock_process.reset_mock()

    # Test when process raises AccessDenied
    mock_process = create_mock_process(pid=12345, terminate_side_effect=psutil.AccessDenied(pid=12345))

    with caplog.at_level("WARNING"):
        jdftx_job.terminate_process(mock_process)

    assert "Error while terminating process" in caplog.text
