import os

from ez_setup import use_setuptools
use_setuptools()
from setuptools import setup, find_packages

with open("README.rst") as f:
    long_desc = f.read()
    ind = long_desc.find("\n")
    long_desc = long_desc[ind + 1:]

setup(
    name="custodian",
    packages=find_packages(),
    version="0.7.5",
    install_requires=["monty>=0.3.1"],
    extras_require={"vasp, nwchem, qchem": ["pymatgen>=2.9.0"]},
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
        "Programming Language :: Python :: 2.7",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: Chemistry",
        "Topic :: Software Development :: Libraries :: Python Modules"
    ],
    scripts=[os.path.join("scripts", f) for f in os.listdir("scripts")]
)
