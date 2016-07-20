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
def make_doc(ctx):
    with cd("docs"):
        ctx.run("sphinx-apidoc -o . -f ../custodian")
        ctx.run("rm custodian*.tests.rst")
        for f in glob.glob("docs/*.rst"):
            if f.startswith('docs/custodian') and f.endswith('rst'):
                newoutput = []
                suboutput = []
                subpackage = False
                with open(f, 'r') as fid:
                    for line in fid:
                        clean = line.strip()
                        if clean == "Subpackages":
                            subpackage = True
                        if not subpackage and not clean.endswith("tests"):
                            newoutput.append(line)
                        else:
                            if not clean.endswith("tests"):
                                suboutput.append(line)
                            if clean.startswith("custodian") and not clean.endswith("tests"):
                                newoutput.extend(suboutput)
                                subpackage = False
                                suboutput = []

                with open(f, 'w') as fid:
                    fid.write("".join(newoutput))

        ctx.run("make html")


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
    make_doc(ctx)
    publish(ctx)
