import pytest

from custodian import Custodian
from custodian.qchem.handlers import QChemErrorHandler
from custodian.qchem.jobs import QCJob

pytest.importorskip("openbabel")
my_input = "test.qin"
my_output = "test.qout"

job = QCJob.opt_with_frequency_flattener(
    qchem_command="qchem -slurm",
    multimode="openmp",
    input_file=my_input,
    output_file=my_output,
    max_iterations=10,
    max_molecule_perturb_scale=0.3,
    max_cores=12,
)
myhandler = QChemErrorHandler(input_file=my_input, output_file=my_output)

cust = Custodian([myhandler], job, max_errors_per_job=10, max_errors=10)

cust.run()
