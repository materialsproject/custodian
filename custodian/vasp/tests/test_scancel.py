import os
from unittest import TestCase
from custodian.utils import Terminator

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        "test_files",  "scancel")


class TestTerminator(TestCase):

    def test_parse_srun_step_number(self):
        mpi_cmd = "srun"
        std_err_file = os.path.join(test_dir, "srun_std_err_example.txt")
        terminator = Terminator(mpi_cmd, std_err_file)
        step_id = terminator.parse_srun_step_number()
        self.assertEqual(step_id, "2667797.4")
