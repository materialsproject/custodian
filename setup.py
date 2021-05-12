# coding: utf-8
# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import os
from io import open

from setuptools import setup, find_packages

with open("README.rst") as f:
    long_desc = f.read()
    ind = long_desc.find("\n")
    long_desc = long_desc[ind + 1 :]

setup(
    name="custodian",
    packages=find_packages(),
    version="2021.2.8",
    install_requires=["monty>=2.0.6", "ruamel.yaml>=0.15.6", "sentry-sdk>=0.8.0"],
    extras_require={"vasp, nwchem, qchem": ["pymatgen>=2019.8.23"]},
    package_data={},
    author="Shyue Ping Ong, William Davidson Richards, Stephen Dacek, Xiaohui Qu, Matthew Horton, Samuel M. Blau",
    author_email="ongsp@ucsd.edu",
    maintainer="Shyue Ping Ong",
    url="https://github.com/materialsproject/custodian",
    license="MIT",
    description="A simple JIT job management framework in Python.",
    long_description=long_desc,
    keywords=["jit", "just-in-time", "job", "management", "vasp"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: Chemistry",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    entry_points={
        "console_scripts": [
            "cstdn = custodian.cli.cstdn:main",
            "run_vasp = custodian.cli.run_vasp:main",
            "run_nwchem = custodian.cli.run_nwchem:main",
            "converge_kpoints = custodian.cli.converge_kpoints:main",
            "converge_geometry = custodian.cli.converge_geometry:main",
        ]
    },
)
