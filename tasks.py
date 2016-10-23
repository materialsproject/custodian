"""
Deployment file to facilitate releases of custodian.
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Apr 29, 2012"

import glob

from invoke import task
from monty.os import cd
from custodian import __version__ as ver

@task
def publish(ctx):
    ctx.run("python setup.py release")


@task
def test(ctx):
    ctx.run("nosetests")


@task
def setver(ctx):
    ctx.run("sed s/version=.*,/version=\\\"{}\\\",/ setup.py > newsetup".format(ver))
    ctx.run("mv newsetup setup.py")


@task
def release(ctx):
    setver(ctx)
    test(ctx)
    publish(ctx)
