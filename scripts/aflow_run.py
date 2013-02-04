#!/usr/bin/env python

"""
TODO: Change the module doc.
"""

from __future__ import division

__author__ = "shyuepingong"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__status__ = "Beta"
__date__ = "2/4/13"

import logging

from custodian.custodian import Custodian
from pymatpro.custodian.handlers import IncarErrorHandler,\
    KpointsErrorHandler, UnconvergedErrorHandler
from pymatpro.custodian.jobs import BasicVaspJob, SecondRelaxationVaspJob


def aflow_run():
    #An example of an aflow run.

    FORMAT = '%(asctime)s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO, filename="run.log")
    handlers = [IncarErrorHandler(), KpointsErrorHandler(),
                UnconvergedErrorHandler()]
    jobs = [BasicVaspJob(), SecondRelaxationVaspJob()]
    c = Custodian(handlers, jobs, max_errors=10)
    c.run()

if __name__ == "__main__":
    aflow_run()