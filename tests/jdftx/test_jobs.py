import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, ANY
import psutil
from custodian.jdftx.jobs import JDFTxJob

TEST_DIR = Path(__file__).resolve().parent.parent
TEST_FILES = f"{TEST_DIR}/files/jdftx"

@pytest.fixture
def jdftx_job():
    return JDFTxJob(jdftx_cmd="jdftx")

@pytest.fixture
def mock_process(tmp_path, jdftx_job):
    process = MagicMock(spec=psutil.Process)
    process.name.return_value = "jdftx"
    process.pid = 12345
    process.open_files.return_value = [MagicMock(path=os.path.join(str(tmp_path), jdftx_job.output_file))]
    return process


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

def test_jdftx_job_run_creates_output_files(jdftx_job, temp_dir):
    with patch("subprocess.run"):
        jdftx_job.run(str(temp_dir))

    assert os.path.exists(os.path.join(str(temp_dir), "jdftx.out"))
    assert os.path.exists(os.path.join(str(temp_dir), "std_err.txt"))

def test_jdftx_job_postprocess(jdftx_job, tmp_path):
    jdftx_job.postprocess(str(tmp_path))
    # Postprocess method doesn't do anything, so we just check that it doesn't raise an exception

@patch("psutil.process_iter")
@patch("psutil.pid_exists")
@patch("subprocess.run")
@patch.object(JDFTxJob, 'terminate_process', autospec=True)
def test_jdftx_job_terminate(mock_terminate_process, mock_subprocess_run, mock_pid_exists, mock_process_iter, jdftx_job, mock_process, tmp_path):
    jdftx_job.output_file = "jdftx.out"  # Ensure this matches the actual output file name
    run_path = os.path.join(str(tmp_path), jdftx_job.output_file)
    mock_process.open_files.return_value = [MagicMock(path=run_path)]
    mock_process.name.return_value = "jdftx"
    mock_process_iter.return_value = [mock_process]

    # Test successful termination
    mock_pid_exists.return_value = True
    jdftx_job.terminate(str(tmp_path))
    mock_terminate_process.assert_called_once_with(mock_process)
    mock_subprocess_run.assert_not_called()

    mock_terminate_process.reset_mock()
    mock_subprocess_run.reset_mock()

    # Test when process doesn't exist
    mock_process.name.return_value = "not_jdft"
    jdftx_job.terminate(str(tmp_path))
    mock_terminate_process.assert_not_called()
    mock_subprocess_run.assert_called_once_with(["killall", "jdftx"], check=False)

    mock_terminate_process.reset_mock()
    mock_subprocess_run.reset_mock()

    # Test when psutil raises exceptions
    mock_pid_exists.return_value = "jdftx"
    mock_process_iter.side_effect = psutil.NoSuchProcess(pid=12345)
    jdftx_job.terminate(str(tmp_path))
    mock_subprocess_run.assert_called_with(["killall", "jdftx"], check=False)

    mock_terminate_process.reset_mock()
    mock_subprocess_run.reset_mock()
    mock_pid_exists.side_effect = None
    mock_process_iter.side_effect = None

    #mock_pid_exists.return_value = True
    mock_process_iter.side_effect = psutil.AccessDenied(pid=12345)
    jdftx_job.terminate(str(tmp_path))
    mock_subprocess_run.assert_called_with(["killall", "jdftx"], check=False)

@patch("psutil.Process")
def test_terminate_process(mock_process, jdftx_job):
    process = mock_process.return_value
    
    # Test successful termination
    jdftx_job.terminate_process(process)
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=5)

    process.reset_mock()

    # Test when process doesn't terminate gracefully
    process.wait.side_effect = [psutil.TimeoutExpired(5), None]
    jdftx_job.terminate_process(process)
    process.kill.assert_called_once()

    # Test when process raises NoSuchProcess
    process.terminate.side_effect = psutil.NoSuchProcess(pid=12345)
    jdftx_job.terminate_process(process)

    process.reset_mock()

    # Test when process raises AccessDenied
    process.terminate.side_effect = psutil.AccessDenied(pid=12345)
    jdftx_job.terminate_process(process)

def test_jdftx_job_with_custom_parameters():
    custom_job = JDFTxJob(
        jdftx_cmd="custom_jdftx",
        input_file="custom.in",
        output_file="custom.out",
        stderr_file="custom_err.txt"
    )
    
    assert custom_job.jdftx_cmd == "custom_jdftx"
    assert custom_job.input_file == "custom.in"
    assert custom_job.output_file == "custom.out"
    assert custom_job.stderr_file == "custom_err.txt"
