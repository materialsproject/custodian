from custodian.vasp.validators import VasprunXMLValidator, VaspFilesValidator

import os
import unittest

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        'test_files')
cwd = os.getcwd()

class VasprunXMLValidatorTest(unittest.TestCase):

    def test_check_and_correct(self):
        os.chdir(os.path.join(test_dir, "bad_vasprun"))
        h = VasprunXMLValidator()
        self.assertTrue(h.check())

        #Unconverged still has a valid vasprun.
        os.chdir(os.path.join(test_dir, "unconverged"))
        self.assertFalse(h.check())

    def test_as_dict(self):
        h = VasprunXMLValidator()
        d = h.as_dict()
        h2 = VasprunXMLValidator.from_dict(d)
        self.assertIsInstance(h2, VasprunXMLValidator)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cwd)

class VaspFilesValidatorTest(unittest.TestCase):

    def test_check_and_correct(self):
        # just an example where CONTCAR is not present
        os.chdir(os.path.join(test_dir, "positive_energy"))
        h = VaspFilesValidator()
        self.assertTrue(h.check())

        os.chdir(os.path.join(test_dir, "postprocess"))
        self.assertFalse(h.check())

    def test_as_dict(self):
        h = VaspFilesValidator()
        d = h.as_dict()
        h2 = VaspFilesValidator.from_dict(d)
        self.assertIsInstance(h2, VaspFilesValidator)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cwd)

if __name__ == "__main__":
    unittest.main()
