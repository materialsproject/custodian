import pytest
from custodian.jdftx.jobs import JDFTxJob

@pytest.fixture()
def jdftx_job():
    return JDFTxJob(jdftx_cmd="jdftx", output_file="jdftx.out")