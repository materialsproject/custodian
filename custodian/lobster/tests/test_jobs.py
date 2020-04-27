import os
import shutil
import unittest

from custodian.lobster.jobs import LobsterJob
from monty.os import cd
from monty.tempfile import ScratchDir

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
test_files_lobster2 = os.path.join(MODULE_DIR, '../../../test_files/lobster/lobsterins')
test_files_lobster3 = os.path.join(MODULE_DIR, '../../../test_files/lobster/vasp_lobster_output')

VASP_OUTPUT_FILES = ["OUTCAR", "vasprun.xml", "CHG", "CHGCAR", "CONTCAR", "INCAR", "KPOINTS", "POSCAR", "POTCAR",
                     "DOSCAR", "EIGENVAL", "IBZKPT", "OSZICAR", "PCDAT", "PROCAR", "REPORT", "WAVECAR", "XDATCAR"]


class LobsterJobTest(unittest.TestCase):
    """
    similar to VaspJobTest
    ommit test of run
    """

    def test_to_from_dict(self):
        v = LobsterJob(lobster_cmd="hello")
        v2 = LobsterJob.from_dict(v.as_dict())
        self.assertEqual(type(v2), type(v))
        self.assertEqual(v2.lobster_cmd, "hello")

    def test_setup(self):
        with cd(test_files_lobster2):
            with ScratchDir('.', copy_from_current_on_enter=True) as d:
                # check if backup is done correctly
                v = LobsterJob("hello", backup=True)
                v.setup()
                self.assertTrue(os.path.exists("lobsterin.orig"))
                # check if backup id done correctly
            with ScratchDir('.', copy_from_current_on_enter=True) as d:
                v = LobsterJob("hello", backup=False)
                v.setup()
                self.assertFalse(os.path.exists("lobsterin.orig"))

    def test_postprocess(self):
        # test gzipped and zipping of additional files
        with cd(os.path.join(test_files_lobster3)):
            with ScratchDir('.', copy_from_current_on_enter=True) as d:
                shutil.copy('lobsterin', 'lobsterin.orig')
                v = LobsterJob("hello", gzipped=True, add_files_to_gzip=VASP_OUTPUT_FILES)
                v.postprocess()
                self.assertTrue(os.path.exists("WAVECAR.gz"))
                self.assertTrue(os.path.exists("lobsterin.gz"))
                self.assertTrue(os.path.exists("lobsterout.gz"))
                self.assertTrue(os.path.exists("INCAR.gz"))
                self.assertTrue(os.path.exists("lobsterin.orig.gz"))

            with ScratchDir('.', copy_from_current_on_enter=True) as d:
                shutil.copy('lobsterin', 'lobsterin.orig')
                v = LobsterJob("hello", gzipped=False, add_files_to_gzip=VASP_OUTPUT_FILES)
                v.postprocess()
                self.assertTrue(os.path.exists("WAVECAR"))
                self.assertTrue(os.path.exists("lobsterin"))
                self.assertTrue(os.path.exists("lobsterout"))
                self.assertTrue(os.path.exists("INCAR"))
                self.assertTrue(os.path.exists("lobsterin.orig"))


if __name__ == '__main__':
    unittest.main()
