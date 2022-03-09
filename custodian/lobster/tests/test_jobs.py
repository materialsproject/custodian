import os
import shutil
import unittest
from monty.os import cd
from monty.tempfile import ScratchDir

from custodian.lobster.jobs import LobsterJob

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
test_files_lobster2 = os.path.join(MODULE_DIR, "../../../test_files/lobster/lobsterins")
test_files_lobster3 = os.path.join(MODULE_DIR, "../../../test_files/lobster/vasp_lobster_output")

VASP_OUTPUT_FILES = [
    "OUTCAR",
    "vasprun.xml",
    "CHG",
    "CHGCAR",
    "CONTCAR",
    "INCAR",
    "KPOINTS",
    "POSCAR",
    "POTCAR",
    "DOSCAR",
    "EIGENVAL",
    "IBZKPT",
    "OSZICAR",
    "PCDAT",
    "PROCAR",
    "REPORT",
    "WAVECAR",
    "XDATCAR",
]

LOBSTERINPUT_FILES = ["lobsterin"]

LOBSTER_FILES = [
    "lobsterin",
    "lobsterin.orig",
    "lobsterout",
    "CHARGE.lobster",
    "COHPCAR.lobster",
    "COOPCAR.lobster",
    "DOSCAR.lobster",
    "GROSSPOP.lobster",
    "ICOHPLIST.lobster",
    "ICOOPLIST.lobster",
    "lobster.out",
    "projectionData.lobster",
    "MadelungEnergies.lobster",
    "SitePotentials.lobster",
    "bandOverlaps.lobster",
    "ICOBILIST.lobster",
    "COBICAR.lobster",
]

FW_FILES = ["custodian.json", "FW.json", "FW_submit.script"]


class LobsterJobTest(unittest.TestCase):
    """Similar to VaspJobTest. Omit test of run."""

    def test_to_from_dict(self):
        v = LobsterJob(lobster_cmd="hello")
        v2 = LobsterJob.from_dict(v.as_dict())
        self.assertEqual(type(v2), type(v))
        self.assertEqual(v2.lobster_cmd, "hello")

    def test_setup(self):
        with cd(test_files_lobster2):
            with ScratchDir(".", copy_from_current_on_enter=True):
                # check if backup is done correctly
                v = LobsterJob("hello", backup=True)
                v.setup()
                self.assertTrue(os.path.exists("lobsterin.orig"))
                # check if backup id done correctly
            with ScratchDir(".", copy_from_current_on_enter=True):
                v = LobsterJob("hello", backup=False)
                v.setup()
                self.assertFalse(os.path.exists("lobsterin.orig"))

    def test_postprocess(self):
        # test gzipped and zipping of additional files
        with cd(os.path.join(test_files_lobster3)):
            with ScratchDir(".", copy_from_current_on_enter=True):
                shutil.copy("lobsterin", "lobsterin.orig")
                v = LobsterJob("hello", gzipped=True, add_files_to_gzip=VASP_OUTPUT_FILES)
                v.postprocess()
                for file in VASP_OUTPUT_FILES + LOBSTER_FILES + FW_FILES:
                    filegz = file + ".gz"
                    self.assertTrue(os.path.exists(filegz))

            with ScratchDir(".", copy_from_current_on_enter=True):
                shutil.copy("lobsterin", "lobsterin.orig")
                v = LobsterJob("hello", gzipped=False, add_files_to_gzip=VASP_OUTPUT_FILES)
                v.postprocess()
                for file in VASP_OUTPUT_FILES + LOBSTER_FILES + FW_FILES:
                    self.assertTrue(os.path.exists(file))


if __name__ == "__main__":
    unittest.main()
