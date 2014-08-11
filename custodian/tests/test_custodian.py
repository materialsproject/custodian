#!/usr/bin/env python

"""
Created on Jun 1, 2012
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Jun 1, 2012"

import unittest
import random
from custodian.custodian import Job, ErrorHandler, Custodian
import os
import glob


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

    @staticmethod
    def from_dict(d):
        return ExampleJob(d["jobid"])


class ExampleHandler(ErrorHandler):

    def __init__(self, params):
        self.params = params

    def check(self):
        return self.params["total"] < 50

    def correct(self):
        self.params["initial"] += 1
        return {"errors": "total < 50", "actions": "increment by 1"}

    @staticmethod
    def from_dict(d):
        return ExampleHandler()


class ExampleHandler2(ErrorHandler):
    """
    This handler always result in an error.
    """

    def __init__(self, params):
        self.params = params

    def check(self):
        return True

    def correct(self):
        return {"errors": "errored", "actions": None}

    @staticmethod
    def from_dict(d):
        return ExampleHandler()


class CustodianTest(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    def test_run(self):
        njobs = 100
        params = {"initial": 0, "total": 0}
        c = Custodian([ExampleHandler(params)],
                      [ExampleJob(i, params) for i in xrange(njobs)],
                      max_errors=njobs, log_file=None)
        output = c.run()
        self.assertEqual(len(output), njobs)
        print ExampleHandler(params).to_dict

    def test_unrecoverable(self):
        njobs = 100
        params = {"initial": 0, "total": 0}
        c = Custodian([ExampleHandler2(params)],
                      [ExampleJob(i, params) for i in xrange(njobs)],
                      max_errors=njobs, log_file=None)
        self.assertRaises(RuntimeError, c.run)

    def tearDown(self):
        for f in glob.glob("custodian.*.tar.gz"):
            os.remove(f)
        os.remove("custodian.json")
        os.chdir(self.cwd)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
