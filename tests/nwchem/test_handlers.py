import glob
import os
import shutil
import unittest

from custodian import TEST_FILES
from custodian.nwchem.handlers import NwchemErrorHandler

__author__ = "shyuepingong"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__status__ = "Beta"
__date__ = "6/18/13"


class NwchemErrorHandlerTest(unittest.TestCase):
    def test_check_correct(self):
        os.chdir(f"{TEST_FILES}/nwchem")
        shutil.copy("C1N1Cl1_1.nw", "C1N1Cl1_1.nw.orig")
        h = NwchemErrorHandler(output_filename="C1N1Cl1_1.nwout")
        h.check()
        h.correct()
        shutil.move("C1N1Cl1_1.nw.orig", "C1N1Cl1_1.nw")
        shutil.copy("Li1_1.nw", "Li1_1.nw.orig")
        h = NwchemErrorHandler(output_filename="Li1_1.nwout")
        h.check()
        h.correct()
        shutil.move("Li1_1.nw.orig", "Li1_1.nw")
        for f in glob.glob("error.*.tar.gz"):
            os.remove(f)
