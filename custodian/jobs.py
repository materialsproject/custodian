#!/usr/bin/env python

'''
Created on May 2, 2012
'''

from __future__ import division

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "May 2, 2012"

import abc


class Job(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def setup(self):
        """
        Allows for pre-processing steps.
        """
        pass

    @abc.abstractmethod
    def run(self):
        """
        Actual work done.
        """
        pass

    @abc.abstractmethod
    def postprocess(self):
        """
        Post-processing after a job. Can be a cleanup, analysis of results, or
        anything actually.
        """
        pass

    @abc.abstractproperty
    def name(self):
        """
        A nice string name for the job.
        """
        pass

