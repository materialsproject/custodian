Custodian
=========

Custodian is a simple, robust and flexible just-in-time (JIT) job management
framework written in Python. Using custodian, you can create wrappers that
perform error checking, job management and error recovery. It has a simple
plugin framework that allows you to develop specific job management workflows
for different applications.

Error recovery is an important aspect of many *high-throughput* projects that
generate data on a large scale. When you are running on the order of hundreds
of thousands of jobs, even an error rate of 1% would mean thousands of errored
jobs that would be impossible to deal with on a case-by-case basis.

The specific use case for custodian is for long running jobs, with potentially
random errors. For example, there may be a script that takes several days to
run on a server, with a 1% chance of some IO error causing the job to fail.
Using custodian, one can develop a mechanism to gracefully recover from the
error, and restart the job with modified parameters if necessary.

The current version of Custodian also comes with two sub-packages for error
handling for Vienna Ab Initio Simulation Package (VASP), NwChem and QChem
calculations.

Change log
==========

v2019.2.10
----------
* Improved slow convergence handling. (@shyamd)

v2019.2.7
---------
* Improved error logging.
* Improved handling of frozen jobs and potim errors.
* Improved Exceptino handling. (Guido Petretto)


:doc:`Older versions </changelog>`

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
`pymatgen's documentation`_).

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

1. Python Materials Genomics (`pymatgen`_) 2.8.10+: To use the plugin for
   VASP, NwChem and Qchem. Please install using::

    pip install pymatgen

   For more information, please consult `pymatgen's documentation`_.
2. nose - For complete unittesting.

Usage
=====

The main class in the workflow is known as Custodian, which manages a series
of jobs with a list of error handlers. The general workflow for Custodian is
presented in the figure below.

.. figure:: _static/Custodian.png
    :width: 500px
    :align: center
    :alt: Custodian workflow
    :figclass: align-center

    Overview of the Custodian workflow.

The Custodian class takes in two general inputs - a **list of Jobs** and
a **list of ErrorHandlers**. **Jobs** should be subclasses of the
:class:`custodian.custodian.Job` abstract base class and **ErrorHandlers**
should be subclasses of the :class:`custodian.custodian.ErrorHandler` abstract
base class. To use custodian, you need to implement concrete implementations
of these abstract base classes.

Simple example
--------------

An very simple example implementation is given in the custodian_examples.py
script in the scripts directory. We will now go through the example in detail
here.

The ExampleJob has the following code.

.. code-block:: python

    class ExampleJob(Job):

        def __init__(self, jobid, params=None):
            if params is None:
                params = {"initial": 0, "total": 0}
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


The ExampleJob simply sums a random sequence of 100 numbers between 0 and
1, adds it to an initial value and puts the value in 'total' variable. The
ExampleJob subclasses the Job abstract base class, and implements the necessary
API comprising of just three key methods: **setup(), run(),
and postprocess()**.

Let us now define an ErrorHandler that will check if the total value is >= 50,
and if it is not, it will increment the initial value by 1 and rerun the
ExampleJob again.

.. code-block:: python


    class ExampleHandler(ErrorHandler):

        def __init__(self, params):
            self.params = params

        def check(self):
            return self.params["total"] < 50

        def correct(self):
            self.params["initial"] += 1
            return {"errors": "total < 50", "actions": "increment by 1"}

As you can see above, the ExampleHandler subclasses the ErrorHandler abstract
base class, and implements the necessary API comprising of just two key
methods: **check() and correct()**.

The transfer of information between the Job and ErrorHandler is done using
the params argument in this example, which is not ideal but is sufficiently
for demonstrating the Custodian API. In real world usage,
a more common transfer of information may involve the Job writing the output
to a file, and the ErrorHandler checking the contents of those files to
detect error situations.

To run the job, one simply needs to supply a list of ExampleJobs and
ErrorHandlers to a Custodian.

.. code-block:: python

    njobs = 100
    params = {"initial": 0, "total": 0}
    c = Custodian([ExampleHandler(params)],
                  [ExampleJob(i, params) for i in xrange(njobs)],
                  max_errors=njobs)
    c.run()

If you run custodian_example.py in the scripts directory, you will noticed that
a **custodian.json** file was generated, which summarizes the jobs that have
been run and any corrections performed.

Practical example: Electronic structure calculations
----------------------------------------------------

A practical example where the Custodian framework is particularly useful is
in the area of electronic structure calculations. Electronic structure
calculations tend to be long running and often terminates due to errors,
random or otherwise. Such errors become a major issue in projects that
performs such calculations in high throughput, such as the `Materials
Project`_.

The Custodian package comes with a fairly comprehensive plugin to deal
with jobs (:mod:`custodian.vasp.jobs`) and errors
(:mod:`custodian.vasp.handlers`) in electronic structure calculations based
on the Vienna Ab Initio Simulation Package (VASP). To do this,
Custodian uses the Python Materials Genomics (`pymatgen`_) package to
perform analysis and io from VASP input and output files.

A simple example of a script using Custodian to run a two-relaxation VASP job
is as follows:

.. code-block:: python

    from custodian.custodian import Custodian
    from custodian.vasp.handlers import VaspErrorHandler, \
        UnconvergedErrorHandler, PoscarErrorHandler, DentetErrorHandler
    from custodian.vasp.jobs import VaspJob

    handlers = [VaspErrorHandler(), UnconvergedErrorHandler(),
                PoscarErrorHandler(), DentetErrorHandler()]
    jobs = VaspJob.double_relaxation_run(args.command.split())
    c = Custodian(handlers, jobs, max_errors=10)
    c.run()

The above will gracefully deal with many VASP errors encountered during
relaxation. For example, it will correct ISMEAR to 0 if there are
insufficient KPOINTS to use ISMEAR = -5.

Using custodian, you can even setup potentially indefinite jobs,
e.g. kpoints convergence jobs with a target energy convergence. Please see the
converge_kpoints script in the scripts for an example.

.. versionadded:: 0.4.3

    A new package for dealing with NwChem calculations has been added.
    NwChem is an open-source code for performing computational chemistry
    calculations.

cstdn - A yaml-spec controlled job
==================================

Custodian now comes with a cstdn script, which allows you to do fine-grained
control of a job using a yaml spec file. Below is an annotated example of how
you can specify a double VASP relaxation followed by a static calculation.
Minor modifications would allow very customizable calculations, though this is
obviously not meant for highly complex workflows. For those, usage of `FireWorks
<https://materialsproject.github.io/fireworks/>`_ is highly recommended.

Sample yaml spec::

    # Specifies a list of jobs to run.
    # Each job is specified by a `jb: <full class path>` with parameters specified
    # via the params dict.

    jobs:
    - jb: custodian.vasp.jobs.VaspJob
      params:
        final: False
        suffix: .relax1
    - jb: custodian.vasp.jobs.VaspJob
      params:
        final: False
        suffix: .relax2
        settings_override:
        - {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}}
    - jb: custodian.vasp.jobs.VaspJob
      params:
        final: True
        suffix: .static3
        settings_override:
        - {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}}
        - {"dict": "INCAR", "action": {"_set": {"NSW": 0}}}


    # This key specifies parameters common to all jobs.
    # Keys starting with $ are expanded to the environmental values.
    # The example below means the parameter vasp_cmd is set to the value with
    # $PBS_NODEFILE expanded.

    jobs_common_params:
      $vasp_cmd: ["mpirun", "-machinefile", "$PBS_NODEFILE", "-np", "24", "vasp"]


    # Specifies a list of error handlers in the same format as jobs. Similarly,
    # parameters passed to the handler __init__ can be configured the same
    # way as for jobs.
    handlers:
    - hdlr: custodian.vasp.handlers.VaspErrorHandler
    - hdlr: custodian.vasp.handlers.AliasingErrorHandler
    - hdlr: custodian.vasp.handlers.MeshSymmetryErrorHandler

    # Specifies a list of error handlers in the same format as jobs.
    validators:
    - vldr: custodian.vasp.validators.VasprunXMLValidator

    #This sets all custodian running parameters.
    custodian_params:
      max_errors: 10
      scratch_dir: /tmp
      gzipped_output: True
      checkpoint: True

You can then run the job using the following command::

    cstdn run <path to yaml file>

API/Reference Docs
==================

The API docs are generated using Sphinx auto-doc and outlines the purpose of all
modules and classes, and the expected argument and returned objects for most
methods. They are available at the link below.

:doc:`custodian API docs </modules>`

How to cite custodian
=====================

If you use custodian in your research, especially the VASP component, please
consider citing the following work::

    Shyue Ping Ong, William Davidson Richards, Anubhav Jain, Geoffroy Hautier,
    Michael Kocher, Shreyas Cholia, Dan Gunter, Vincent Chevrier, Kristin A.
    Persson, Gerbrand Ceder. *Python Materials Genomics (pymatgen) : A Robust,
    Open-Source Python Library for Materials Analysis.* Computational
    Materials Science, 2013, 68, 314–319. `doi:10.1016/j.commatsci.2012.10.028
    <http://dx.doi.org/10.1016/j.commatsci.2012.10.028>`_

License
=======

Custodian is released under the MIT License. The terms of the license are as
follows::

    The MIT License (MIT)
    Copyright (c) 2011-2012 MIT & LBNL

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software")
    , to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.

.. _`pymatgen's documentation`: http://pymatgen.org
.. _`Materials Project`: https://www.materialsproject.org
.. _`pymatgen`: https://pypi.python.org/pypi/pymatgen
