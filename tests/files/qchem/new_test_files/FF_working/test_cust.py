import pytest

from custodian import Custodian

pytest.importorskip("openbabel")

from custodian.qchem.handlers import QChemErrorHandler  # noqa: E402
from custodian.qchem.jobs import QCJob  # noqa: E402

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

c = Custodian([myhandler], job, max_errors_per_job=10, max_errors=10)

c.run()
