.. image:: https://travis-ci.org/materialsproject/custodian.png

Custodian is a simple, robust and flexible just-in-time (JIT) job management
framework written in Python. Using custodian, you can create wrappers that
perform error checking, job management and error recovery. It has a simple
plugin framework that allows you to develop specific job management workflows
for different applications.

The specific use case for custodian is for long running jobs,
with potentially random errors. For example, there may be a script that takes
several days to run on a server, with a 1% chance of some IO error causing
the job to fail. Using custodian, one can develop a mechanism to gracefully
recover from the error, and potentially restart the job if necessary.

Custodian is now in an very early alpha, and there may be many frequent API
changes. Please use with care.

Getting custodian
=================

Stable version
--------------

The version at the Python Package Index (PyPI) is always the latest stable
release that will be hopefully, be relatively bug-free. The easiest way to
install custodian on any system is to use easy_install or pip, as follows::

    easy_install custodian

or::

    pip install custodian

Some plugins (e.g., vasp management) require additional setup (please see
`pymatgen's documentation <http://pythonhosted.org/pymatgen/>`_).

Developmental version
---------------------

The bleeding edge developmental version is at the custodian's `Github repo
<https://github.com/materialsproject/custodian>`_. The developmental
version is likely to be more buggy, but may contain new features. The
Github version include test files as well for complete unit testing. After
cloning the source, you can type::

    python setup.py install

or to install the package in developmental mode::

    python setup.py develop

Requirements
============

Custodian requires Python 2.7+. There are no other required dependencies.

Optional dependencies
---------------------

Optional libraries that are required if you need certain features:

1. pymatgen 2.5+: To use the plugin for VASP.
2. nose - For complete unittesting.

Basic usage
===========

The main class in the workflow is known as Custodian, which manages a series
of jobs with a list of error handlers. To use custodian, you need to implement
concrete implementation of the abstract base classes custodian.custodian.Job
and custodian.custodian.ErrorHandler. An very simple example implementation is
given in the examples.py script in the scripts directory.

Other specific examples for electronic structure calculations based on the
Vienna Ab Initio Simulation Package (VASP) are implemented in the
custodian.vasp package. A simple example of a script using Custodian to run a
two-relaxation VASP job is as follows:

.. code-block:: python

    from custodian.custodian import Custodian
    from custodian.vasp.handlers import VaspErrorHandler, UnconvergedErrorHandler
    from custodian.vasp.jobs import VaspJob

    handlers = [VaspErrorHandler(), UnconvergedErrorHandler(),
                PoscarErrorHandler()]
    jobs = VaspJob.double_relaxation_run(args.command.split())
    c = Custodian(handlers, jobs, max_errors=10)
    c.run()
