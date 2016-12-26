# coding: utf-8

from __future__ import unicode_literals, division

"""
Created on Jun 1, 2012
"""


__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Jun 1, 2012"

import unittest
import os
import shutil
import glob

import multiprocessing
from custodian.vasp.jobs import VaspJob, VaspNEBJob
from pymatgen.io.vasp import Incar, Kpoints

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        'test_files')


class VaspJobTest(unittest.TestCase):

    def test_to_from_dict(self):
        v = VaspJob("hello")
        v2 = VaspJob.from_dict(v.as_dict())
        self.assertEqual(type(v2), type(v))
        self.assertEqual(v2.vasp_cmd, "hello")

    def test_setup(self):
        if "VASP_PSP_DIR" not in os.environ:
            os.environ["VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
        v = VaspJob("hello")
        v.setup()
        incar = Incar.from_file("INCAR")
        count = multiprocessing.cpu_count()
        if count > 1:
            self.assertGreater(incar["NPAR"], 1)
        shutil.copy("INCAR.orig", "INCAR")
        os.remove("INCAR.orig")
        os.remove("KPOINTS.orig")
        os.remove("POTCAR.orig")
        os.remove("POSCAR.orig")

    def test_postprocess(self):
        os.chdir(os.path.join(test_dir, 'postprocess'))
        shutil.copy('INCAR', 'INCAR.backup')

        v = VaspJob("hello", final=False, suffix=".test", copy_magmom=True)
        v.postprocess()
        incar = Incar.from_file("INCAR")
        incar_prev = Incar.from_file("INCAR.test")

        for f in ['INCAR', 'KPOINTS', 'CONTCAR', 'OSZICAR', 'OUTCAR',
                  'POSCAR', 'vasprun.xml']:
            self.assertTrue(os.path.isfile('{}.test'.format(f)))
            os.remove('{}.test'.format(f))
        shutil.move('INCAR.backup', 'INCAR')

        self.assertAlmostEqual(incar['MAGMOM'], [3.007, 1.397, -0.189, -0.189])
        self.assertAlmostEqual(incar_prev["MAGMOM"], [5, -5, 0.6, 0.6])

    def test_static(self):
        #Just a basic test of init.
        VaspJob.double_relaxation_run(["vasp"])


class VaspNEBJobTest(unittest.TestCase):

    def test_to_from_dict(self):
        v = VaspNEBJob("hello")
        v2 = VaspNEBJob.from_dict(v.as_dict())
        self.assertEqual(type(v2), type(v))
        self.assertEqual(v2.vasp_cmd, "hello")

    def test_setup(self):
        if "VASP_PSP_DIR" not in os.environ:
            os.environ["VASP_PSP_DIR"] = test_dir
        os.chdir(os.path.join(test_dir, 'setup_neb'))

        v = VaspNEBJob("hello", half_kpts=True)
        v.setup()

        incar = Incar.from_file("INCAR")
        count = multiprocessing.cpu_count()
        if count > 1:
            self.assertGreater(incar["NPAR"], 1)

        kpt = Kpoints.from_file("KPOINTS")
        kpt_pre = Kpoints.from_file("KPOINTS.orig")
        self.assertEqual(kpt_pre.style.name, "Monkhorst")
        self.assertEqual(kpt.style.name, "Gamma")

        shutil.copy("KPOINTS.orig", "KPOINTS")
        os.remove("INCAR.orig")
        os.remove("KPOINTS.orig")
        os.remove("POTCAR.orig")
        poscars = glob.glob("[0-9][0-9]/POSCAR.orig")
        for p in poscars:
            os.remove(p)

    def test_postprocess(self):
        neb_outputs = ['INCAR', 'KPOINTS', 'POTCAR', 'vasprun.xml']
        neb_sub_outputs = ['CHG', 'CHGCAR', 'CONTCAR', 'DOSCAR',
                           'EIGENVAL', 'IBZKPT', 'PCDAT', 'POSCAR',
                           'REPORT', 'PROCAR', 'OSZICAR', 'OUTCAR',
                           'WAVECAR', 'XDATCAR']

        os.chdir(os.path.join(test_dir, 'postprocess_neb'))
        postprocess_neb = os.path.abspath(".")

        v = VaspNEBJob("hello", final=False, suffix=".test")
        v.postprocess()

        for f in neb_outputs:
            self.assertTrue(os.path.isfile('{}.test'.format(f)))
            os.remove('{}.test'.format(f))

        sub_folders = glob.glob("[0-9][0-9]")
        for sf in sub_folders:
            os.chdir(os.path.join(postprocess_neb, sf))
            for f in neb_sub_outputs:
                if os.path.exists(f):
                    self.assertTrue(os.path.isfile('{}.test'.format(f)))
                    os.remove('{}.test'.format(f))

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
