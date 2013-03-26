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

total = 0
initial = 0


class ExampleJob(Job):
    """
    This example job simply sums a random sequence of 100 numbers between 0
    and 1, adds it to an initial value and puts the value in 'total' global
    variable.
    """

    def __init__(self, jobid):
        self.jobid = jobid

    def setup(self):
        global initial
        initial = 0

    def run(self):
        print "Running job {}".format(self.jobid)
        global initial
        global total
        sequence = np.random.rand(100, 1)
        total = initial + np.sum(sequence)
        print "Current total = {}".format(total)

    def postprocess(self):
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
    not, the Example job should be run again until a total >= 50 is obtained.
    """

    def check(self):
        return total < 50

    def correct(self):
        global initial
        initial += 1
        print "Total < 50. Incrementing initial to {}".format(initial)
        return {"errors": "total < 50", "actions": "increment by 1"}

    @property
    def to_dict(self):
        return {}

    @staticmethod
    def from_dict(d):
        return ExampleHandler()


if __name__ == "__main__":
    c = Custodian([ExampleHandler()], [ExampleJob(i) for i in xrange(10)],
                  max_errors=5)
    c.run()
