# coding: utf-8

from __future__ import unicode_literals, division, print_function

"""
Created on Jun 1, 2012
"""


__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Jun 1, 2012"

import unittest
import random
from custodian.custodian import Job, ErrorHandler, Custodian, Validator
import os
import glob
import shutil


class ExampleJob(Job):

    def __init__(self, jobid, params={"initial": 0, "total": 0}):
        self.jobid = jobid
        self.params = params

    def setup(self):
        self.params["initial"] = 0
        self.params["total"] = 0

    def run(self):
        sequence = [random.uniform(0, 1) for i in range(100)]
        self.params["total"] = self.params["initial"] + sum(sequence)

    def postprocess(self):
        pass

    @property
    def name(self):
        return "ExampleJob{}".format(self.jobid)


class ExampleHandler(ErrorHandler):

    def __init__(self, params):
        self.params = params

    def check(self):
        return self.params["total"] < 50

    def correct(self):
        self.params["initial"] += 1
        return {"errors": "total < 50", "actions": "increment by 1"}


class ExampleHandler2(ErrorHandler):
    """
    This handler always result in an error.
    """

    def __init__(self, params):
        self.params = params

    def check(self):
        return True

    def correct(self):
        self.has_error = True
        return {"errors": "Unrecoverable error", "actions": None}


class ExampleHandler2b(ExampleHandler2):
    """
    This handler always result in an error. No runtime error though
    """
    raises_runtime_error = False

    def correct(self):
        self.has_error = True
        return {"errors": "Unrecoverable error", "actions": []}


class ExampleValidator1(Validator):

    def check(self):
        return False


class ExampleValidator2(Validator):

    def check(self):
        return True


class CustodianTest(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    def test_run(self):
        njobs = 100
        params = {"initial": 0, "total": 0}
        c = Custodian([ExampleHandler(params)],
                      [ExampleJob(i, params) for i in range(njobs)],
                      max_errors=njobs)
        output = c.run()
        self.assertEqual(len(output), njobs)
        print(ExampleHandler(params).as_dict())

    def test_unrecoverable(self):
        njobs = 100
        params = {"initial": 0, "total": 0}
        h = ExampleHandler2(params)
        c = Custodian([h],
                      [ExampleJob(i, params) for i in range(njobs)],
                      max_errors=njobs)
        self.assertRaises(RuntimeError, c.run)
        self.assertTrue(h.has_error)
        h = ExampleHandler2b(params)
        c = Custodian([h],
                      [ExampleJob(i, params) for i in range(njobs)],
                      max_errors=njobs)
        c.run()
        self.assertTrue(h.has_error)

    def test_validators(self):
        njobs = 100
        params = {"initial": 0, "total": 0}
        c = Custodian([ExampleHandler(params)],
                      [ExampleJob(i, params) for i in range(njobs)],
                      [ExampleValidator1()],
                      max_errors=njobs)
        output = c.run()
        self.assertEqual(len(output), njobs)

        njobs = 100
        params = {"initial": 0, "total": 0}
        c = Custodian([ExampleHandler(params)],
                      [ExampleJob(i, params) for i in range(njobs)],
                      [ExampleValidator2()],
                      max_errors=njobs)
        self.assertRaises(RuntimeError, c.run)

    def tearDown(self):
        for f in glob.glob("custodian.*.tar.gz"):
            os.remove(f)
        os.remove("custodian.json")
        os.chdir(self.cwd)


class CustodianCheckpointTest(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        os.chdir(os.path.join(os.path.dirname(__file__), "..", "..",
                              "test_files", "checkpointing"))
        shutil.copy(os.path.join('backup.tar.gz'),
                    'custodian.chk.3.tar.gz')

    def test_checkpoint_loading(self):
        njobs = 5
        params = {"initial": 0, "total": 0}
        c = Custodian([ExampleHandler(params)],
                      [ExampleJob(i, params) for i in range(njobs)],
                      [ExampleValidator1()],
                      max_errors=100, checkpoint=True)
        self.assertEqual(len(c.run_log), 3)
        self.assertEqual(len(c.run()), 5)

    def tearDown(self):
        os.remove("custodian.json")
        os.chdir(self.cwd)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
