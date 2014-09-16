# coding: utf-8

from __future__ import unicode_literals, division

"""
TODO: Change the module doc.
"""


__author__ = "shyuepingong"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__status__ = "Beta"
__date__ = "6/18/13"


import unittest
import os
import shutil
import glob

from custodian.nwchem.handlers import NwchemErrorHandler


test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        'test_files', "nwchem")


class NwchemErrorHandlerTest(unittest.TestCase):

    def test_check_correct(self):
        os.chdir(test_dir)
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

if __name__ == "__main__":
    unittest.main()
