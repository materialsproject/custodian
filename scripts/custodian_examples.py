#!/usr/bin/env python

"""
This module provides an demonstration of how to use the Custodian framework.
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__date__ = "2/17/13"

import numpy as np

from custodian.custodian import Job, ErrorHandler, Custodian


class ExampleJob(Job):
    """
    This example job simply sums a random sequence of 100 numbers between 0
    and 1, adds it to an initial value and puts the value in 'total'
    key in params.
    """

    def __init__(self, jobid, params={"initial": 0, "total": 0}):
        self.jobid = jobid
        self.params = params

    def setup(self):
        # The initial and total values should be set to zero at the start of
        # a Job.
        self.params["initial"] = 0
        self.params["total"] = 0

    def run(self):
        print "Running job {}".format(self.jobid)
        sequence = np.random.rand(100, 1)
        self.params["total"] = self.params["initial"] + np.sum(sequence)
        print "Current total = {}".format(self.params["total"])

    def postprocess(self):
        # Simply just print a success message.
        print "Success for job {}".format(self.jobid)

    def name(self):
        return "ExampleJob{}".format(self.jobid)

    @property
    def to_dict(self):
        return {"jobid": self.jobid}

    @staticmethod
    def from_dict(d):
        return ExampleJob(d["jobid"])


class ExampleHandler(ErrorHandler):
    """
    This example error handler checks if the value of total is >= 50. If it is
    not, the handler increments the initial value and rerun the ExampleJob
    until a total >= 50 is obtained.
    """

    def __init__(self, params):
        self.params = params

    def check(self):
        return self.params["total"] < 50

    def correct(self):
        # Increment the initial value by 1.
        self.params["initial"] += 1
        print "Total < 50. Incrementing initial to {}".format(
            self.params["initial"])
        return {"errors": "total < 50", "actions": "increment by 1"}

    @property
    def is_monitor(self):
        return False

    @property
    def to_dict(self):
        return {}

    @staticmethod
    def from_dict(d):
        return ExampleHandler()


if __name__ == "__main__":
    njobs = 100
    params = {"initial": 0, "total": 0}
    c = Custodian([ExampleHandler(params)],
                  [ExampleJob(i, params) for i in xrange(njobs)],
                  max_errors=njobs)
    output = c.run()
    total_errors = sum([len(d["corrections"]) for d in output])
    print
    print "Total errors = {}".format(total_errors)