# coding: utf-8

from __future__ import unicode_literals, division


__author__ = "ndardenne"
__version__ = "0.1"
__status__ = "Beta"
__date__ = "6/17/15"


import unittest
import os
import shutil
import glob

from custodian.gaussian.handlers import GaussianErrorHandler


test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        'test_files', "gaussian")


class GaussianErrorHandlerTest(unittest.TestCase):

    def test_check_correct(self):
        os.chdir(test_dir)
        shutil.copy("ferrocene_631G0.gau", "ferrocene_631G0.gau.orig")
        h = GaussianErrorHandler(output_filename="ferrocene_631G0.log")
        h.check()
        h.correct()
        shutil.move("ferrocene_631G0.gau.orig", "ferrocene_631G0.gau")
        for f in glob.glob("error.*.tar.gz"):
            os.remove(f)

if __name__ == "__main__":
    unittest.main()
