#!/usr/bin/env python

"""
This module implements basic kinds of jobs for QChem runs.
"""

from __future__ import division
from pymatgen.serializers.json_coders import MSONable
from custodian.custodian import Job

__author__ = "Xiaohui Qu"
__version__ = "0.1"
__maintainer__ = "Xiaohui Qu"
__email__ = "xhqu1981@gmail.com"
__status__ = "alpha"
__date__ = "12/03/13"



class QchemJob(Job, MSONable):
    """
    A basis QChem Job.
    """
    def __init__(self):
        """
        This constructor is necessarily complex due to the need for
        flexibility. For standard kinds of runs, it's often better to use one
        of the static constructors.
        """


