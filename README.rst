.. image:: https://travis-ci.org/materialsproject/custodian.png

Custodian is a simple, robust and flexible just-in-time job management
framework written in Python. Using custodian, you can create wrappers that
perform error checking, job management and error recovery. It has a simple
plugin framework that allows you to develop specific job management workflows
for different applications.

Custodian is now in an very early alpha. Use with care.

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
`custodian's documentation <http://packages.python.org/custodian>`_).

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

