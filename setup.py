# coding: utf-8
# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import os
from io import open

from setuptools import setup, find_packages

with open("README.rst") as f:
    long_desc = f.read()
    ind = long_desc.find("\n")
    long_desc = long_desc[ind + 1:]

setup(
    name="custodian",
    packages=find_packages(),
    version="1.0.2",
    install_requires=["monty>=0.9.0", "six"],
    extras_require={"vasp, nwchem, qchem": ["pymatgen>=3.3.1"]},
    package_data={},
    author="Shyue Ping Ong, William Davidson Richards, Stephen Dacek, "
           "Xiaohui Qu",
    author_email="ongsp@ucsd.edu",
    maintainer="Shyue Ping Ong",
    url="https://github.com/materialsproject/custodian",
    license="MIT",
    description="A simple JIT job management framework in Python.",
    long_description=long_desc,
    keywords=["jit", "just-in-time", "job", "management", "vasp"],
    classifiers=[
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: Chemistry",
        "Topic :: Software Development :: Libraries :: Python Modules"
    ],
    entry_points={
          'console_scripts': [
              'cstdn = custodian.cli.cstdn:main',
              'run_vasp = custodian.cli.run_vasp:main',
              'run_nwchem = custodian.cli.run_nwchem:main',
              'converge_kpoints = custodian.cli.converge_kpoints:main',
              'converge_geometry = custodian.cli.converge_geometry:main',
          ]
    }
)
