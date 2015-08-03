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

import random
from custodian.custodian import Job, ErrorHandler, Custodian


class ExampleJob(Job):
    """
    This example job simply sums a random sequence of 100 numbers between 0
    and 1, adds it to an initial value and puts the value in 'total'
    key in params.
    """

    def __init__(self, jobid, params={"initial": 0, "total": 0}):
        """
        The initialization of the ExampleJob requires a jobid,
        something to simply identify a job, and a params argument,
        which is a mutable dict that enables storage of the results and can
        be transferred from Job to Handler.
        """
        self.jobid = jobid
        self.params = params

    def setup(self):
        """
        The setup sets the initial and total values to zero at the start of
        a Job.
        """
        self.params["initial"] = 0
        self.params["total"] = 0

    def run(self):
        """
        Doing the actual run, i.e., generating a random sequence of 100
        numbers between 0 and 1, summing it and adding it to the inital value
        to get the total value.
        """
        print "Running job {}".format(self.jobid)
        sequence = [random.uniform(0, 1) for i in range(100)]
        self.params["total"] = self.params["initial"] + sum(sequence)
        print "Current total = {}".format(self.params["total"])

    def postprocess(self):
        # Simply just print a success message.
        print "Success for job {}".format(self.jobid)

    def name(self):
        """
        A name for the job.
        """
        return "ExampleJob{}".format(self.jobid)

    @property
    def to_dict(self):
        """
        All Jobs must implement a to_dict property that returns a JSON
        serializable dict to enable Custodian to log the job information in a
        json file.
        """
        return {"jobid": self.jobid}

    @staticmethod
    def from_dict(d):
        """
        Similarly, all Jobs must implement a from_dict static method
        that takes in a dict of the form returned by to_dict and returns a
        actual Job.
        """
        return ExampleJob(d["jobid"])


class ExampleHandler(ErrorHandler):
    """
    This example error handler checks if the value of total is >= 50. If it is
    not, the handler increments the initial value and rerun the ExampleJob
    until a total >= 50 is obtained.
    """

    def __init__(self, params):
        """
        The initialization of the ExampleHandler takes in the same params
        argument, which should contain the results from the ExampleJob.
        """
        self.params = params

    def check(self):
        """
        The check() step should return a boolean indicating if there are
        errors. In this case, we define an error to be a situation where the
        total is less than 50.
        """
        return self.params["total"] < 50

    def correct(self):
        """
        The correct() step should fix any errors and return a dict
        summarizing the actions taken. In this case, we increment the initial
        value by 1 in an attempt to increase the total.
        """
        self.params["initial"] += 1
        print "Total < 50. Incrementing initial to {}".format(
            self.params["initial"])
        return {"errors": "total < 50", "actions": "increment by 1"}

    @property
    def is_monitor(self):
        """
        This property indicates whether this handler is a monitor, i.e.,
        whether it turns in the background as the run is taking place and
        correcting errors.
        """
        return False

    @property
    def to_dict(self):
        """
        Similar to Jobs, ErrorHandlers should have a to_dict property that
        returns a JSON-serializable dict.
        """
        return {}

    @staticmethod
    def from_dict(d):
        """
        Similar to Jobs, ErrorHandlers should have a from_dict static property
        that returns the Example Handler from a JSON-serializable dict.
        """
        return ExampleHandler()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    njobs = 100
    params = {"initial": 0, "total": 0}
    c = Custodian([ExampleHandler(params)],
                  [ExampleJob(i, params) for i in xrange(njobs)],
                  max_errors=njobs)
    output = c.run()
    total_errors = sum([len(d["corrections"]) for d in output])
    print
    print "Total errors = {}".format(total_errors)