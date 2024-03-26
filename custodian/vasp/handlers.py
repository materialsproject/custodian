"""
This module implements specific error handlers for VASP runs. These handlers
try to detect common errors in vasp runs and attempt to fix them on the fly
by modifying the input files.
"""

from __future__ import annotations

import datetime
import logging
import multiprocessing
import os
import re
import shutil
import time
import warnings
from collections import Counter
from math import prod

import numpy as np
from monty.dev import deprecated
from monty.io import zopen
from monty.os.path import zpath
from monty.serialization import loadfn
from pymatgen.core.structure import Structure
from pymatgen.io.vasp.inputs import Incar, Kpoints, Poscar, VaspInput
from pymatgen.io.vasp.outputs import Oszicar
from pymatgen.io.vasp.sets import MPScanRelaxSet
from pymatgen.transformations.standard_transformations import SupercellTransformation

from custodian.ansible.actions import FileActions
from custodian.ansible.interpreter import Modder
from custodian.custodian import ErrorHandler
from custodian.utils import backup
from custodian.vasp.interpreter import VaspModder
from custodian.vasp.io import load_outcar, load_vasprun

__author__ = (
    "Shyue Ping Ong, William Davidson Richards, Anubhav Jain, Wei Chen, "
    "Stephen Dacek, Andrew Rosen, Janosh Riebesell"
)
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "ongsp@ucsd.edu"
__status__ = "Beta"
__date__ = "2/4/13"

VASP_BACKUP_FILES = {
    "INCAR",
    "KPOINTS",
    "POSCAR",
    "OUTCAR",
    "CONTCAR",
    "OSZICAR",
    "vasprun.xml",
    "vasp.out",
    "std_err.txt",
}


class VaspErrorHandler(ErrorHandler):
    """
    Master VaspErrorHandler class that handles a number of common errors
    that occur during VASP runs.
    """

    is_monitor = True

    error_msgs = {
        "tet": [
            "Tetrahedron method fails",
            "tetrahedron method fails",
            "Fatal error detecting k-mesh",
            "Fatal error: unable to match k-point",
            "Routine TETIRR needs special values",
            "Tetrahedron method fails (number of k-points < 4)",
            "BZINTS",
        ],
        "inv_rot_mat": ["rotation matrix was not found (increase SYMPREC)"],
        "brmix": ["BRMIX: very serious problems"],
        "subspacematrix": ["WARNING: Sub-Space-Matrix is not hermitian in DAV"],
        "tetirr": ["Routine TETIRR needs special values"],
        "incorrect_shift": ["Could not get correct shifts"],
        "real_optlay": ["REAL_OPTLAY: internal error", "REAL_OPT: internal ERROR"],
        "rspher": ["ERROR RSPHER"],
        "dentet": ["DENTET"],  # reason for this warning is that the Fermi level cannot be determined accurately
        # enough by the tetrahedron method
        # https://vasp.at/forum/viewtopic.php?f=3&t=416&p=4047&hilit=dentet#p4047
        "too_few_bands": ["TOO FEW BANDS"],
        "triple_product": ["ERROR: the triple product of the basis vectors"],
        "rot_matrix": ["Found some non-integer element in rotation matrix", "SGRCON"],
        "brions": ["BRIONS problems: POTIM should be increased"],
        "pricel": ["internal error in subroutine PRICEL"],
        "zpotrf": ["LAPACK: Routine ZPOTRF failed", "Routine ZPOTRF ZTRTRI"],
        "amin": ["One of the lattice vectors is very long (>50 A), but AMIN"],
        "zbrent": ["ZBRENT: fatal internal in", "ZBRENT: fatal error in bracketing"],
        # Note that PSSYEVX and PDSYEVX errors are identical up to LAPACK routine:
        # P<prec>SYEVX uses <prec> = S(ingle) or D(ouble) precision
        "pssyevx": ["ERROR in subspace rotation PSSYEVX"],
        "pdsyevx": ["ERROR in subspace rotation PDSYEVX"],
        "eddrmm": ["WARNING in EDDRMM: call to ZHEGV failed"],
        "edddav": ["Error EDDDAV: Call to ZHEGV failed"],
        "algo_tet": ["ALGO=A and IALGO=5X tend to fail"],
        "grad_not_orth": ["EDWAV: internal error, the gradient is not orthogonal"],
        "nicht_konv": ["ERROR: SBESSELITER : nicht konvergent"],
        "zheev": ["ERROR EDDIAG: Call to routine ZHEEV failed!"],
        "eddiag": ["ERROR in EDDIAG: call to ZHEEV/ZHEEVX/DSYEV/DSYEVX failed"],
        "elf_kpar": ["ELF: KPAR>1 not implemented"],
        "elf_ncl": ["WARNING: ELF not implemented for non collinear case"],
        "rhosyg": ["RHOSYG"],
        "posmap": ["POSMAP"],
        "point_group": ["group operation missing"],
        "pricelv": ["PRICELV: current lattice and primitive lattice are incommensurate"],
        "symprec_noise": ["determination of the symmetry of your systems shows a strong"],
        "dfpt_ncore": ["PEAD routines do not work for NCORE", "remove the tag NPAR from the INCAR file"],
        "bravais": ["Inconsistent Bravais lattice"],
        "nbands_not_sufficient": ["number of bands is not sufficient"],
        "hnform": ["HNFORM: k-point generating"],
        "coef": ["while reading plane", "while reading WAVECAR"],
        "set_core_wf": ["internal error in SET_CORE_WF"],
        "read_error": ["Error reading item", "Error code was IERR= 5"],
    }

    def __init__(
        self,
        output_filename="vasp.out",
        errors_subset_to_catch=None,
        vtst_fixes=False,
        **kwargs,
    ):
        """Initialize the handler with the output file to check.

        Args:
            output_filename (str): This is the file where the stdout for vasp
                is being redirected. The error messages that are checked are
                present in the stdout. Defaults to "vasp.out", which is the
                default redirect used by :class:`custodian.vasp.jobs.VaspJob`.
            errors_subset_to_detect (list): A subset of errors to catch. The
                default is None, which means all supported errors are detected.
                Use this to catch only a subset of supported errors.
                E.g., ["eddrmm", "zheev"] will only catch the eddrmm and zheev
                errors, and not others. If you wish to only exclude one or
                two of the errors, you can create this list by the following
                lines:

                ```
                subset = list(VaspErrorHandler().error_msgs)
                subset.remove("eddrmm")

                handler = VaspErrorHandler(errors_subset_to_catch=subset)
                ```
            vtst_fixes (bool): Whether to consider VTST optimizers. Defaults to
                False for compatibility purposes, but if you have VTST, you
                would likely benefit from setting this to True.
            **kwargs: Ignored. Added to increase signature flexibility.
        """
        self.output_filename = output_filename
        self.errors = set()
        self.error_count = Counter()
        self.errors_subset_to_catch = errors_subset_to_catch or list(VaspErrorHandler.error_msgs)
        self.vtst_fixes = vtst_fixes
        self.logger = logging.getLogger(type(self).__name__)

    def check(self, directory="./"):
        """Check for error."""
        incar = Incar.from_file(os.path.join(directory, "INCAR"))
        self.errors = set()
        error_msgs = set()
        with zopen(os.path.join(directory, self.output_filename), mode="rt") as file:
            text = file.read()

            # Check for errors
            for err in self.errors_subset_to_catch:
                for msg in self.error_msgs[err]:
                    if text.find(msg) != -1:
                        # this checks if we want to run a charged
                        # computation (e.g., defects) if yes we don't
                        # want to kill it because there is a change in
                        # e-density (brmix error)
                        if err == "brmix" and "NELECT" in incar:
                            continue
                        self.errors.add(err)
                        error_msgs.add(msg)
        for msg in error_msgs:
            self.logger.error(msg, extra={"incar": incar.as_dict()})
        return len(self.errors) > 0

    def correct(self, directory="./"):
        """Perform corrections."""
        backup(VASP_BACKUP_FILES | {self.output_filename}, directory=directory)
        actions = []
        vi = VaspInput.from_directory(directory)

        if self.errors.intersection(["tet", "dentet"]):
            # follow advice in this thread
            # https://vasp.at/forum/viewtopic.php?f=3&t=416&p=4047&hilit=dentet#p4047
            err_type = "tet" if "tet" in self.errors else "dentet"
            if self.error_count[err_type] == 0:
                if vi["INCAR"].get("KSPACING"):
                    # decrease KSPACING by 20% in each direction (approximately double no. of kpoints)
                    action = {"_set": {"KSPACING": vi["INCAR"].get("KSPACING") * 0.8}}
                    actions.append({"dict": "INCAR", "action": action})
                elif vi["KPOINTS"] and vi["KPOINTS"].num_kpts < 1:
                    # increase KPOINTS by 20% in each direction (approximately double no. of kpoints)
                    new_kpts = tuple(int(round(num * 1.2, 0)) for num in vi["KPOINTS"].kpts[0])
                    actions.append({"dict": "KPOINTS", "action": {"_set": {"kpoints": (new_kpts,)}}})
                elif vi["KPOINTS"] and vi["KPOINTS"].num_kpts >= 1:
                    n_kpts = vi["KPOINTS"].num_kpts * 1.2
                    new_kpts = tuple([int(round(n_kpts**1 / 3, 0))] * 3)
                    actions.append(
                        {"dict": "KPOINTS", "action": {"_set": {"generation_style": "Gamma", "kpoints": (new_kpts,)}}}
                    )
            else:
                actions.append({"dict": "INCAR", "action": {"_set": {"ISMEAR": 0, "SIGMA": 0.05}}})
            self.error_count[err_type] += 1

        # Missing AMIN error handler:
        # previously, custodian would kill the job without letting it run if AMIN was flagged
        if "amin" in self.errors and vi["INCAR"].get("AMIN", 0.1) > 0.01:
            actions.append({"dict": "INCAR", "action": {"_set": {"AMIN": 0.01}}})

        if "inv_rot_mat" in self.errors and vi["INCAR"].get("SYMPREC", 1e-5) > 1e-8:
            actions.append({"dict": "INCAR", "action": {"_set": {"SYMPREC": 1e-8}}})

        if "brmix" in self.errors:
            # If there is not a valid OUTCAR already, increment
            # error count to 1 to skip first fix
            if self.error_count["brmix"] == 0:
                try:
                    assert load_outcar(zpath(os.path.join(directory, "OUTCAR"))).is_stopped is False
                except Exception:
                    self.error_count["brmix"] += 1

            if self.error_count["brmix"] == 0:
                # Valid OUTCAR - simply rerun the job and increment
                # error count for next time
                actions.append({"dict": "INCAR", "action": {"_set": {"ISTART": 1}}})
                self.error_count["brmix"] += 1

            elif self.error_count["brmix"] == 1 and vi["INCAR"].get("IMIX", 4) != 1:
                # Use Kerker mixing w/ default values for other parameters
                actions.append({"dict": "INCAR", "action": {"_set": {"IMIX": 1}}})
                self.error_count["brmix"] += 1

            elif (
                self.error_count["brmix"] == 2
                and vi["KPOINTS"]
                and vi["KPOINTS"].style == Kpoints.supported_modes.Gamma
            ):
                actions.append(
                    {
                        "dict": "KPOINTS",
                        "action": {"_set": {"generation_style": "Monkhorst"}},
                    }
                )
                if "IMIX" in vi["INCAR"]:
                    actions.append({"dict": "INCAR", "action": {"_unset": {"IMIX": 1}}})
                self.error_count["brmix"] += 1

            elif (
                self.error_count["brmix"] in {2, 3}
                and vi["KPOINTS"]
                and vi["KPOINTS"].style == Kpoints.supported_modes.Monkhorst
            ):
                actions.append({"dict": "KPOINTS", "action": {"_set": {"generation_style": "Gamma"}}})
                if "IMIX" in vi["INCAR"]:
                    actions.append({"dict": "INCAR", "action": {"_unset": {"IMIX": 1}}})
                self.error_count["brmix"] += 1

                if vi["KPOINTS"] and vi["KPOINTS"].num_kpts < 1 and all(n % 2 == 0 for n in vi["KPOINTS"].kpts[0]):
                    new_kpts = (tuple(n + 1 for n in vi["KPOINTS"].kpts[0]),)
                    actions.append(
                        {
                            "dict": "KPOINTS",
                            "action": {"_set": {"kpoints": new_kpts}},
                        }
                    )

            elif self.error_count["brmix"] in {2, 3} and vi["INCAR"].get("KSPACING"):
                actions.append({"dict": "INCAR", "action": {"_set": {"KGAMMA": True}}})

            else:
                if vi["INCAR"].get("ISYM", 2) > 0:
                    actions.append({"dict": "INCAR", "action": {"_set": {"ISYM": 0}}})
                if vi["KPOINTS"] and vi["KPOINTS"].style == Kpoints.supported_modes.Monkhorst:
                    actions.append(
                        {
                            "dict": "KPOINTS",
                            "action": {"_set": {"generation_style": "Gamma"}},
                        }
                    )
                if vi["KPOINTS"] and vi["KPOINTS"].style == Kpoints.supported_modes.Monkhorst:
                    actions.append(
                        {
                            "dict": "KPOINTS",
                            "action": {"_set": {"generation_style": "Gamma"}},
                        }
                    )

                # Based on VASP forum's recommendation, you should delete the
                # CHGCAR and WAVECAR when dealing with this error.
                # A.S.R.: Then why only delete them now?
                if vi["INCAR"].get("ICHARG", 0) < 10:
                    actions += [
                        {"file": "CHGCAR", "action": {"_file_delete": {"mode": "actual"}}},
                        {"file": "WAVECAR", "action": {"_file_delete": {"mode": "actual"}}},
                    ]
                self.error_count["brmix"] += 1

        if "zpotrf" in self.errors:
            # Usually caused by short bond distances. If on the first step,
            # volume needs to be increased. Otherwise, it was due to a step
            # being too big and POTIM should be decreased. If a static run
            # try turning off symmetry. This also happens if NCORE or NPAR
            # is set to a large value for a small structure.

            try:
                oszicar = Oszicar(os.path.join(directory, "OSZICAR"))
                nsteps = len(oszicar.ionic_steps)
            except Exception:
                nsteps = 0

            if vi["INCAR"].get("ISYM", 2) > 0:
                actions.append({"dict": "INCAR", "action": {"_set": {"ISYM": 0}}})

            # The natoms of 5 was chosen somewhat arbitrarily. Could be worth revisiting to fine-tune.
            if len(vi["POSCAR"].structure) < 5 and (vi["INCAR"].get("NCORE", 1) > 1 or vi["INCAR"].get("NPAR", 1) > 1):
                actions.append({"dict": "INCAR", "action": {"_set": {"NCORE": 1}}})
                if vi["INCAR"].get("NPAR", 1) > 1:
                    actions.append({"dict": "INCAR", "action": {"_unset": {"NPAR": 1}}})
            elif vi["INCAR"].get("NSW", 0) > 0:
                if nsteps == 0:
                    s = vi["POSCAR"].structure
                    s.apply_strain(0.2)
                    actions.append({"dict": "POSCAR", "action": {"_set": {"structure": s.as_dict()}}})
                else:
                    potim = round(vi["INCAR"].get("POTIM", 0.5) / 2.0, 2)
                    actions.append({"dict": "INCAR", "action": {"_set": {"POTIM": potim}}})

        if self.errors.intersection(["subspacematrix"]):
            if self.error_count["subspacematrix"] == 0 and vi["INCAR"].get("LREAL", False) is not False:
                actions.append({"dict": "INCAR", "action": {"_set": {"LREAL": False}}})
            elif self.error_count["subspacematrix"] == 1 and vi["INCAR"].get("PREC", "Normal") != "Accurate":
                actions.append({"dict": "INCAR", "action": {"_set": {"PREC": "Accurate"}}})
            self.error_count["subspacematrix"] += 1

        if (
            self.errors.intersection(["rspher", "real_optlay", "nicht_konv"])
            and vi["INCAR"].get("LREAL", False) is not False
        ):
            actions.append({"dict": "INCAR", "action": {"_set": {"LREAL": False}}})

        if (
            self.errors.intersection(["tetirr", "incorrect_shift"])
            and vi["KPOINTS"]
            and vi["KPOINTS"].style == Kpoints.supported_modes.Monkhorst
        ):
            actions.append(
                {
                    "dict": "KPOINTS",
                    "action": {"_set": {"generation_style": "Gamma"}},
                }
            )

        if "rot_matrix" in self.errors:
            if vi["KPOINTS"] and vi["KPOINTS"].style == Kpoints.supported_modes.Monkhorst:
                action = {"_set": {"generation_style": "Gamma"}}
                actions.append({"dict": "KPOINTS", "action": action})
            elif vi["INCAR"].get("ISYM", 2) > 0:
                actions.append({"dict": "INCAR", "action": {"_set": {"ISYM": 0}}})

        if "triple_product" in self.errors:
            s = vi["POSCAR"].structure
            trans = SupercellTransformation(((1, 0, 0), (0, 0, 1), (0, 1, 0)))
            new_s = trans.apply_transformation(s)
            actions.append(
                {
                    "dict": "POSCAR",
                    "action": {"_set": {"structure": new_s.as_dict()}},
                    "transformation": trans.as_dict(),
                }
            )

        if "pricel" in self.errors and vi["INCAR"].get("SYMPREC", 1e-5) > 1e-8:
            actions.append({"dict": "INCAR", "action": {"_set": {"SYMPREC": 1e-8, "ISYM": 0}}})

        if "coef" in self.errors:
            actions.append({"file": "WAVECAR", "action": {"_file_delete": {"mode": "actual"}}})

        if "brions" in self.errors:
            # Copy CONTCAR to POSCAR so we do not lose our progress.
            actions.append({"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}})

            # By default, increase POTIM per the VASP error message. But if that does not work,
            # we should try IBRION = 2 since it is less sensitive to POTIM.
            potim = round(vi["INCAR"].get("POTIM", 0.5) + 0.1, 2)
            if self.error_count["brions"] == 1 and vi["INCAR"].get("IBRION", 0) == 1:
                # Reset POTIM to default value and switch to IBRION = 2
                actions.append({"dict": "INCAR", "action": {"_set": {"IBRION": 2, "POTIM": 0.5}}})
            else:
                # Increase POTIM
                actions.append({"dict": "INCAR", "action": {"_set": {"POTIM": potim}}})
            self.error_count["brions"] += 1

        if "zbrent" in self.errors:
            # ZBRENT is caused by numerical noise in the forces, often near the PES minimum
            # This is often a severe problem for systems with many atoms, flexible
            # structures (e.g. zeolites, MOFs), and surfaces with adsorbates present. It is
            # a tricky one to resolve and generally occurs with IBRION = 2, which is otherwise
            # a fairly robust optimization algorithm.
            #
            # VASP recommends moving CONTCAR to POSCAR and tightening EDIFF to improve the forces.
            # That is our first option, along with setting NELMIN to 8 to ensure the forces are
            # high quality. Our backup option if this does not help is to switch to IBRION = 1.
            #
            # If the user has specified vtst_fixes = True, we instead switch right away to FIRE, which is known
            # to be much more robust near the PES minimum. It is not the default because it requires
            # VTST to be installed.

            ediff = vi["INCAR"].get("EDIFF", 1e-4)

            # Copy CONTCAR to POSCAR. This should always be done so we don't lose our progress.
            actions.append({"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}})

            # Tighten EDIFF per the VASP warning message. We tighten it by a factor of 10 unless
            # it is > 1e-6 (in which case we set it to 1e-6) or 1e-8 in which case we stop tightening
            if ediff > 1e-8:
                if ediff > 1e-6:
                    actions.append({"dict": "INCAR", "action": {"_set": {"EDIFF": 1e-6}}})
                else:
                    actions.append({"dict": "INCAR", "action": {"_set": {"EDIFF": ediff / 10}}})

            # Set NELMIN to 8 to further ensure we have accurate forces. NELMIN of 4 to 8 is also
            # recommended if IBRION = 1 is set anyway.
            if vi["INCAR"].get("NELMIN", 2) < 8:
                actions.append({"dict": "INCAR", "action": {"_set": {"NELMIN": 8}}})

            # FIRE almost always resolves this issue but requires VTST to be installed. We provide
            # it as a non-default option for the user. It is also not very sensitive to POTIM, unlike
            # IBRION = 1. FIRE requires accurate forces but is unlikely to run into the zbrent issue.
            # Since accurate forces are required for FIRE, we also need EDIFF to be tight and NELMIN
            # to be set, e.g. to 8. This was already done above.
            if self.vtst_fixes:
                if vi["INCAR"].get("IOPT", 0) != 7:
                    actions.append({"dict": "INCAR", "action": {"_set": {"IOPT": 7, "IBRION": 3, "POTIM": 0}}})
            else:
                # By default, we change IBRION to 1 if the first CONTCAR to POSCAR swap did not work.
                # We do not do this right away because IBRION = 1 is very sensitive to POTIM, which may
                # cause a brions error downstream. We want to avoid the loop condition of zbrent -->
                # switch to IBRION = 1 --> brions --> increase POTIM --> brions --> switch back to IBRION = 2
                # --> zbrent --> and so on. The best way to avoid this is trying to get it to converge in the
                # first place without switching IBRION to 1.
                if self.error_count["zbrent"] == 1:
                    actions.append({"dict": "INCAR", "action": {"_set": {"IBRION": 1}}})

            self.error_count["zbrent"] += 1

        if "too_few_bands" in self.errors:
            nbands = None
            if "NBANDS" in vi["INCAR"]:
                nbands = vi["INCAR"]["NBANDS"]
            else:
                with open(os.path.join(directory, "OUTCAR")) as file:
                    for line in file:
                        # Have to take the last NBANDS line since sometimes VASP
                        # updates it automatically even if the user specifies it.
                        # The last one is marked by NBANDS= (no space).
                        if "NBANDS=" in line:
                            try:
                                d = line.split("=")
                                nbands = int(d[-1].strip())
                                break
                            except (IndexError, ValueError):
                                pass
            if nbands:
                new_nbands = max(int(1.1 * nbands), nbands + 1)  # This handles the case when nbands is too low (< 8).
                actions.append({"dict": "INCAR", "action": {"_set": {"NBANDS": new_nbands}}})

        if self.errors & {"pssyevx", "pdsyevx"} and vi["INCAR"].get("ALGO", "Normal").lower() != "normal":
            actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Normal"}}})

        if "eddrmm" in self.errors:
            # RMM algorithm is not stable for this calculation
            # Copy CONTCAR to POSCAR if CONTCAR has already been populated.
            try:
                is_contcar = Poscar.from_file(os.path.join(directory, "CONTCAR"))
            except Exception:
                is_contcar = False
            if is_contcar:
                actions.append({"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}})
            if vi["INCAR"].get("ALGO", "Normal").lower() in {"fast", "veryfast"}:
                actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Normal"}}})
            else:
                potim = round(vi["INCAR"].get("POTIM", 0.5) / 2.0, 2)
                actions.append({"dict": "INCAR", "action": {"_set": {"POTIM": potim}}})
            if vi["INCAR"].get("ICHARG", 0) < 10:
                actions += [
                    {"file": "CHGCAR", "action": {"_file_delete": {"mode": "actual"}}},
                    {"file": "WAVECAR", "action": {"_file_delete": {"mode": "actual"}}},
                ]
            self.error_count["eddrmm"] += 1

        if "edddav" in self.errors:
            # Copy CONTCAR to POSCAR if CONTCAR has already been populated.
            try:
                is_contcar = Poscar.from_file(os.path.join(directory, "CONTCAR"))
            except Exception:
                is_contcar = False
            if is_contcar:
                actions.append({"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}})
            if vi["INCAR"].get("ICHARG", 0) < 10:
                actions.append({"file": "CHGCAR", "action": {"_file_delete": {"mode": "actual"}}})

            # This sometimes comes up with ALGO = Fast. We will switch the ALGO.
            if vi["INCAR"].get("ALGO", "Normal").lower() != "all":
                actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "All"}}})

            # This can sometimes be due to load-balancing issues for small systems.
            # See bottom of https://www.vasp.at/wiki/index.php/NCORE. A.S.R. ran some
            # tests and found: 1) Changing LPLANE and NSIM does not help. 2) The suggestion
            # of NCORE = # cores is not robust for KNL (too high). 3) Setting NPAR = sqrt(# cores)
            # does not always resolve the issue. The best solution, aside from requesting fewer
            # resources, seems to be to just increase NCORE slightly. That's what I do here.
            nprocs = multiprocessing.cpu_count()
            try:
                nelect = load_outcar(os.path.join(directory, "OUTCAR")).nelect
            except Exception:
                nelect = 1  # dummy value
            if nelect < nprocs:
                actions.append({"dict": "INCAR", "action": {"_set": {"NCORE": vi["INCAR"].get("NCORE", 1) * 2}}})

        if "grad_not_orth" in self.errors:
            # Often coincides with algo_tet, in which the algo_tet error handler will also resolve grad_not_orth.
            # When not present alongside algo_tet, the grad_not_orth error is due to how VASP is compiled.
            # Depending on the optimization flag and choice of compiler, the ALGO = All and Damped algorithms
            # may not work. The only fix is either to change ALGO or to recompile VASP. Since meta-GGAs/hybrids
            # are often used with ALGO = All (and hybrids are incompatible with ALGO = VeryFast/Fast and slow with
            # ALGO = Normal), we do not adjust ALGO in these cases.
            if vi["INCAR"].get("METAGGA", "none") == "none" and not vi["INCAR"].get("LHFCALC", False):
                if vi["INCAR"].get("ALGO", "Normal").lower() in {"all", "damped"}:
                    actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Fast"}}})
                elif 53 <= vi["INCAR"].get("IALGO", 38) <= 58:
                    actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Fast"}, "_unset": {"IALGO": 38}}})
            if "algo_tet" not in self.errors:
                warnings.warn(
                    "EDWAV error reported by VASP without a simultaneous algo_tet error. You may wish to consider "
                    "recompiling VASP with the -O1 optimization if you used -O2 and this error keeps cropping up.",
                    UserWarning,
                )

        if self.errors & {"zheev", "eddiag"}:
            # Copy CONTCAR to POSCAR if CONTCAR has already been populated.
            try:
                is_contcar = Poscar.from_file(os.path.join(directory, "CONTCAR"))
            except Exception:
                is_contcar = False
            if is_contcar:
                actions.append({"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}})
            if vi["INCAR"].get("ALGO", "Normal").lower() == "fast":
                actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Normal"}}})
            elif vi["INCAR"].get("ALGO", "Normal").lower() == "normal":
                actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "exact"}}})

        if "elf_kpar" in self.errors and vi["INCAR"].get("KPAR", 1) != 1:
            actions.append({"dict": "INCAR", "action": {"_set": {"KPAR": 1}}})

        if "rhosyg" in self.errors:
            if vi["INCAR"].get("SYMPREC", 1e-5) < 1e-4:
                actions.append({"dict": "INCAR", "action": {"_set": {"SYMPREC": 1e-4}}})
            else:
                actions.append({"dict": "INCAR", "action": {"_set": {"ISYM": 0}}})

        if symprec_errors := self.errors & {"posmap", "pricelv"}:
            # VASP advises to decrease or increase SYMPREC by an order of magnitude
            # the default SYMPREC value is 1e-5
            # For PRICELV, see https://www.vasp.at/forum/viewtopic.php?p=25608
            if all(self.error_count[key] == 0 for key in symprec_errors):
                # first, reduce by 10x
                orig_symprec = vi["INCAR"].get("SYMPREC", 1e-5)
                actions.append({"dict": "INCAR", "action": {"_set": {"SYMPREC": orig_symprec / 10}}})
            elif all(self.error_count[key] <= 1 for key in symprec_errors):
                # next, increase by 100x (10x the original)
                orig_symprec = vi["INCAR"].get("SYMPREC", 1e-6)
                actions.append({"dict": "INCAR", "action": {"_set": {"SYMPREC": orig_symprec * 100}}})
            elif any(self.error_count[key] > 1 for key in symprec_errors) and vi["INCAR"].get("ISYM", 2) > 0:
                # Failing that, disable symmetry altogether
                actions.append({"dict": "INCAR", "action": {"_set": {"ISYM": 0}}})

            for key in symprec_errors:
                self.error_count[key] += 1

        if "point_group" in self.errors and vi["INCAR"].get("ISYM", 2) > 0:
            actions.append({"dict": "INCAR", "action": {"_set": {"ISYM": 0}}})

        if "symprec_noise" in self.errors and vi["INCAR"].get("ISYM", 2) > 0:
            if vi["INCAR"].get("SYMPREC", 1e-5) > 1e-6:
                actions.append({"dict": "INCAR", "action": {"_set": {"SYMPREC": 1e-6}}})
            else:
                actions.append({"dict": "INCAR", "action": {"_set": {"ISYM": 0}}})

        if "dfpt_ncore" in self.errors:
            # note that when using "_unset" action, the value is ignored
            if "NCORE" in vi["INCAR"]:
                actions.append({"dict": "INCAR", "action": {"_unset": {"NCORE": 0}}})
            if "NPAR" in vi["INCAR"]:
                actions.append({"dict": "INCAR", "action": {"_unset": {"NPAR": 0}}})

        if "bravais" in self.errors:
            # VASP recommends refining the lattice parameters or changing SYMPREC.
            # Appears to occur when SYMPREC is very low, so we change it to
            # the default if it's not already. If it's the default, we x10.
            vasp_recommended_symprec = 1e-6  # https://www.vasp.at/forum/viewtopic.php?f=3&t=19109
            symprec = vi["INCAR"].get("SYMPREC", vasp_recommended_symprec)
            if symprec < vasp_recommended_symprec:
                actions.append({"dict": "INCAR", "action": {"_set": {"SYMPREC": vasp_recommended_symprec}}})
            elif symprec < 1e-4:
                # try 10xing symprec twice, then set ISYM=0 to not impose potentially artificial symmetry from
                # too loose symprec on charge density
                actions.append({"dict": "INCAR", "action": {"_set": {"SYMPREC": symprec * 10}}})
            else:
                actions.append({"dict": "INCAR", "action": {"_set": {"ISYM": 0}}})
            self.error_count["bravais"] += 1

        if "nbands_not_sufficient" in self.errors:
            # There is something very wrong about the value of NBANDS. We don't make
            # any updates to NBANDS though because it's likely the user screwed something
            # up pretty badly during setup. For instance, this has happened to me if
            # MAGMOM = 2*nan or something similar.

            # Unfixable error. Just return None for actions.
            warnings.warn("Double-check your INCAR. Something is potentially wrong.", UserWarning)
            return {"errors": ["nbands_not_sufficient"], "actions": None}

        if "set_core_wf" in self.errors:
            # Unfixable error where the solution is to update the POTCARs
            warnings.warn(
                "We suggest using a new version of the POTCAR files to resolve the SET_CORE_WF error.", UserWarning
            )
            return {"errors": ["set_core_wf"], "actions": None}

        if "read_error" in self.errors:
            # Unfixable error --- the user made a mistake in the INCAR
            warnings.warn("Looks like you made a typo in the INCAR. Please double-check it.", UserWarning)
            return {"errors": ["read_error"], "actions": None}

        if "hnform" in self.errors and vi["INCAR"].get("ISYM", 2) > 0:
            # The only solution is to change your k-point grid or disable symmetry
            # For internal calculation compatibility's sake, we do the latter
            actions.append({"dict": "INCAR", "action": {"_set": {"ISYM": 0}}})

        if "algo_tet" in self.errors:
            # NOTE: This is the algo_tet handler response.
            algo = vi["INCAR"].get("ALGO", "Normal").lower()
            # ALGO=All/Damped / IALGO=5X often fails with ISMEAR < 0. There are two options VASP
            # suggests: 1) Use ISMEAR = 0 (and a small sigma) to get the SCF to converge.
            # 2) Use ALGO = Damped but only *after* an ISMEAR = 0 run where the wavefunction
            # has been stored and read in for the subsequent run.
            if (
                (algo in {"all", "damped"} or (50 <= vi["INCAR"].get("IALGO", 38) <= 59))
                and vi["INCAR"].get("ISMEAR", 1) < 0
                and self.error_count["algo_tet"] == 0
            ):
                # first recovery attempt is to set ALGO to fast. Could fail again in which
                # case we end up here again if some other handler switches algo back to all/damped.
                # This time try the recovery below.
                actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Fast"}}})
            #
            # We will only hit the 2nd algo_tet error if the ALGO was changed back from Fast to All/Damped
            # by e.g. NonConvergingErrorHandler
            # NOTE this relies on self.errors being reset on empty set on every .check call
            if self.error_count["algo_tet"] > 0:
                actions.append({"dict": "INCAR", "action": {"_set": {"ISMEAR": 0, "SIGMA": 0.05}}})
                if vi["INCAR"].get("NEDOS") or vi["INCAR"].get("EMIN") or vi["INCAR"].get("EMAX"):
                    warnings.warn(
                        "This looks like a DOS run. You may want to follow-up this job with ALGO = Damped"
                        " and ISMEAR = -5, using the wavefunction from the current job.",
                        UserWarning,
                    )
            self.error_count["algo_tet"] += 1

        VaspModder(vi=vi, directory=directory).apply_actions(actions)
        return {"errors": list(self.errors), "actions": actions}


class LrfCommutatorHandler(ErrorHandler):
    """
    Corrects LRF_COMMUTATOR errors by setting LPEAD=True if not already set.
    Note that switching LPEAD=T can slightly change results versus the
    default due to numerical evaluation of derivatives.
    """

    is_monitor = True

    error_msgs = {"lrf_comm": ["LRF_COMMUTATOR internal error"]}

    def __init__(self, output_filename: str = "std_err.txt"):
        """Initialize the handler with the output file to check.

        Args:
            output_filename (str): This is the file where the stderr for vasp
                is being redirected. The error messages that are checked are
                present in the stderr. Defaults to "std_err.txt", which is the
                default redirect used by :class:`custodian.vasp.jobs.VaspJob`.
        """
        self.output_filename = output_filename
        self.errors: set[str] = set()
        self.error_count: Counter = Counter()

    def check(self, directory="./"):
        """Check for error."""
        self.errors = set()
        with open(os.path.join(directory, self.output_filename)) as file:
            for line in file:
                line = line.strip()
                for err, msgs in LrfCommutatorHandler.error_msgs.items():
                    for msg in msgs:
                        if line.find(msg) != -1:
                            self.errors.add(err)
        return len(self.errors) > 0

    def correct(self, directory="./"):
        """Perform corrections."""
        backup(VASP_BACKUP_FILES | {self.output_filename}, directory=directory)
        actions = []
        vi = VaspInput.from_directory(directory)

        if (
            "lrf_comm" in self.errors
            and load_outcar(zpath(os.path.join(directory, "OUTCAR"))).is_stopped is False
            and not vi["INCAR"].get("LPEAD")
        ):
            actions.append({"dict": "INCAR", "action": {"_set": {"LPEAD": True}}})

        VaspModder(vi=vi, directory=directory).apply_actions(actions)
        return {"errors": list(self.errors), "actions": actions}


class StdErrHandler(ErrorHandler):
    """
    Master StdErr class that handles a number of common errors
    that occur during VASP runs with error messages only in
    the standard error.
    """

    is_monitor = True

    error_msgs = {
        "kpoints_trans": ["internal error in GENERATE_KPOINTS_TRANS: number of G-vector changed in star"],
        "out_of_memory": ["Allocation would exceed memory limit"],
    }

    def __init__(self, output_filename: str = "std_err.txt"):
        """Initialize the handler with the output file to check.

        Args:
            output_filename (str): This is the file where the stderr for vasp
                is being redirected. The error messages that are checked are
                present in the stderr. Defaults to "std_err.txt", which is the
                default redirect used by :class:`custodian.vasp.jobs.VaspJob`.
        """
        self.output_filename = output_filename
        self.errors: set[str] = set()
        self.error_count: Counter = Counter()

    def check(self, directory="./"):
        """Check for error."""
        self.errors = set()
        with open(os.path.join(directory, self.output_filename)) as file:
            for line in file:
                line = line.strip()
                for err, msgs in StdErrHandler.error_msgs.items():
                    for msg in msgs:
                        if line.find(msg) != -1:
                            self.errors.add(err)
        return len(self.errors) > 0

    def correct(self, directory="./"):
        """Perform corrections."""
        backup(VASP_BACKUP_FILES | {self.output_filename}, directory=directory)
        actions = []
        vi = VaspInput.from_directory(directory)

        if "kpoints_trans" in self.errors and self.error_count["kpoints_trans"] == 0:
            m = prod(vi["KPOINTS"].kpts[0])
            m = max(int(round(m ** (1 / 3))), 1)
            if vi["KPOINTS"] and vi["KPOINTS"].style.name.lower().startswith("m"):
                m += m % 2
            actions.append({"dict": "KPOINTS", "action": {"_set": {"kpoints": [[m] * 3]}}})
            self.error_count["kpoints_trans"] += 1

        if "out_of_memory" in self.errors and vi["INCAR"].get("KPAR", 1) > 1:
            reduced_kpar = max(vi["INCAR"].get("KPAR", 1) // 2, 1)
            actions.append({"dict": "INCAR", "action": {"_set": {"KPAR": reduced_kpar}}})

        VaspModder(vi=vi, directory=directory).apply_actions(actions)
        return {"errors": list(self.errors), "actions": actions}


class AliasingErrorHandler(ErrorHandler):
    """
    Master VaspErrorHandler class that handles a number of common errors
    that occur during VASP runs.
    """

    is_monitor = True

    error_msgs = {
        "aliasing": ["WARNING: small aliasing (wrap around) errors must be expected"],
        "aliasing_incar": ["Your FFT grids (NGX,NGY,NGZ) are not sufficient for an accurate"],
    }

    def __init__(self, output_filename: str = "vasp.out"):
        """Initialize the handler with the output file to check.

        Args:
            output_filename (str): This is the file where the stdout for vasp
                is being redirected. The error messages that are checked are
                present in the stdout. Defaults to "vasp.out", which is the
                default redirect used by :class:`custodian.vasp.jobs.VaspJob`.
        """
        self.output_filename = output_filename
        self.errors: set[str] = set()

    def check(self, directory="./"):
        """Check for error."""
        incar = Incar.from_file(os.path.join(directory, "INCAR"))
        self.errors = set()
        with open(os.path.join(directory, self.output_filename)) as file:
            for line in file:
                line = line.strip()
                for err, msgs in AliasingErrorHandler.error_msgs.items():
                    for msg in msgs:
                        if line.find(msg) != -1:
                            # this checks if we want to run a charged
                            # computation (e.g., defects) if yes we don't
                            # want to kill it because there is a change in e-
                            # density (brmix error)
                            if err == "brmix" and "NELECT" in incar:
                                continue
                            self.errors.add(err)
        return len(self.errors) > 0

    def correct(self, directory="./"):
        """Perform corrections."""
        backup(VASP_BACKUP_FILES | {self.output_filename}, directory=directory)
        actions = []
        vi = VaspInput.from_directory(directory)

        if "aliasing" in self.errors:
            with open(os.path.join(directory, "OUTCAR")) as file:
                grid_adjusted = False
                changes_dict = {}
                r = re.compile(r".+aliasing errors.*(NG.)\s*to\s*(\d+)")
                for line in file:
                    m = r.match(line)
                    if m:
                        changes_dict[m.group(1)] = int(m.group(2))
                        grid_adjusted = True
                    # Ensure that all NGX, NGY, NGZ have been checked
                    if grid_adjusted and "NGZ" in line:
                        actions.append({"dict": "INCAR", "action": {"_set": changes_dict}})
                        if vi["INCAR"].get("ICHARG", 0) < 10:
                            delete_chgcar = {"file": "CHGCAR", "action": {"_file_delete": {"mode": "actual"}}}
                            delete_wavecar = {"file": "WAVECAR", "action": {"_file_delete": {"mode": "actual"}}}
                            actions += [delete_chgcar, delete_wavecar]
                        break

        if "aliasing_incar" in self.errors:
            # vasp seems to give different warnings depending on whether the
            # aliasing error was caused by user supplied inputs
            dct = {k: 1 for k in ("NGX", "NGY", "NGZ") if k in vi["INCAR"]}
            actions.append({"dict": "INCAR", "action": {"_unset": dct}})

            if vi["INCAR"].get("ICHARG", 0) < 10:
                actions += [
                    {
                        "file": "CHGCAR",
                        "action": {"_file_delete": {"mode": "actual"}},
                    },
                    {
                        "file": "WAVECAR",
                        "action": {"_file_delete": {"mode": "actual"}},
                    },
                ]

        VaspModder(vi=vi, directory=directory).apply_actions(actions)
        return {"errors": list(self.errors), "actions": actions}


class DriftErrorHandler(ErrorHandler):
    """Corrects for total drift exceeding the force convergence criteria."""

    def __init__(self, max_drift=None, to_average=3, enaug_multiply=2):
        """Initialize the handler with max drift
        Args:
            max_drift (float): This defines the max drift. Leaving this at the default of None gets the max_drift from
                EDFIFFG.
        """
        self.max_drift = max_drift
        self.to_average = int(to_average)
        self.enaug_multiply = enaug_multiply

    def check(self, directory="./"):
        """Check for error."""
        incar = Incar.from_file(os.path.join(directory, "INCAR"))
        if incar.get("EDIFFG", 0.1) >= 0 or incar.get("NSW", 0) <= 1:
            # Only activate when force relaxing and ionic steps
            # NSW check prevents accidental effects when running DFPT
            return False

        if not self.max_drift:
            self.max_drift = incar["EDIFFG"] * -1

        try:
            outcar = load_outcar(os.path.join(directory, "OUTCAR"))
        except Exception:
            # Can't perform check if Outcar not valid
            return False

        if len(outcar.data.get("drift", [])) < self.to_average:
            # Ensure enough steps to get average drift
            return False

        curr_drift = outcar.data.get("drift", [])[::-1][: self.to_average]
        curr_drift = np.average([np.linalg.norm(dct) for dct in curr_drift])
        return curr_drift > self.max_drift

    def correct(self, directory="./"):
        """Perform corrections."""
        backup(VASP_BACKUP_FILES, directory=directory)
        actions = []
        vi = VaspInput.from_directory(directory)

        incar = vi["INCAR"]
        outcar = load_outcar(os.path.join(directory, "OUTCAR"))

        # Move CONTCAR to POSCAR
        actions.append({"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}})

        # Set PREC to High so ENAUG can be used to control Augmentation Grid Size
        if incar.get("PREC", "Accurate").lower() != "high":
            actions += [
                {"dict": "INCAR", "action": {"_set": {"PREC": "High"}}},
                {"dict": "INCAR", "action": {"_set": {"ENAUG": incar.get("ENCUT", 520) * 2}}},
            ]
        # PREC is already high and ENAUG set so just increase it
        else:
            actions.append(
                {
                    "dict": "INCAR",
                    "action": {"_set": {"ENAUG": int(incar.get("ENAUG", 1040) * self.enaug_multiply)}},
                }
            )

        curr_drift = outcar.data.get("drift", [])[::-1][: self.to_average]
        curr_drift = np.average([np.linalg.norm(dct) for dct in curr_drift])
        VaspModder(vi=vi, directory=directory).apply_actions(actions)
        return {
            "errors": f"Excessive drift {curr_drift} > {self.max_drift}",
            "actions": actions,
        }


class MeshSymmetryErrorHandler(ErrorHandler):
    """
    Corrects the mesh symmetry error in VASP. This error is sometimes
    non-fatal. So this error handler only checks at the end of the run,
    and if the run has converged, no error is recorded.
    """

    is_monitor = False

    def __init__(self, output_filename: str = "vasp.out", output_vasprun="vasprun.xml"):
        """Initialize the handler with the output files to check.

        Args:
            output_filename (str): This is the file where the stdout for vasp
                is being redirected. The error messages that are checked are
                present in the stdout. Defaults to "vasp.out", which is the
                default redirect used by :class:`custodian.vasp.jobs.VaspJob`.
            output_vasprun (str): Filename for the vasprun.xml file. Change
                this only if it is different from the default (unlikely).
        """
        self.output_filename = output_filename
        self.output_vasprun = output_vasprun

    def check(self, directory="./"):
        """Check for error."""
        msg = "Reciprocal lattice and k-lattice belong to different class of lattices."

        vi = VaspInput.from_directory(directory)
        # disregard this error if KSPACING is set and no KPOINTS file is generated
        if vi["INCAR"].get("KSPACING", False):
            return False

        # According to VASP admins, you can disregard this error
        # if symmetry is off (i.e. ISYM = -1 or 0)
        # Also disregard if automatic KPOINT generation is used
        if vi["INCAR"].get("ISYM", 2) <= 0 or (
            vi["KPOINTS"] and vi["KPOINTS"].style == Kpoints.supported_modes.Automatic
        ):
            return False

        try:
            v = load_vasprun(os.path.join(directory, self.output_vasprun))
            if v.converged:
                return False
        except Exception:
            pass
        with open(os.path.join(directory, self.output_filename)) as file:
            for line in file:
                line = line.strip()
                if line.find(msg) != -1:
                    return True
        return False

    def correct(self, directory="./"):
        """Perform corrections."""
        backup(VASP_BACKUP_FILES | {self.output_filename}, directory=directory)
        vi = VaspInput.from_directory(directory)
        m = prod(vi["KPOINTS"].kpts[0])
        m = max(int(round(m ** (1 / 3))), 1)
        if vi["KPOINTS"] and vi["KPOINTS"].style.name.lower().startswith("m"):
            m += m % 2
        actions = [{"dict": "KPOINTS", "action": {"_set": {"kpoints": [[m] * 3]}}}]
        VaspModder(vi=vi, directory=directory).apply_actions(actions)
        return {"errors": ["mesh_symmetry"], "actions": actions}


class UnconvergedErrorHandler(ErrorHandler):
    """Check if a run is converged."""

    is_monitor = False

    def __init__(self, output_filename: str = "vasprun.xml"):
        """Initialize the handler with the output file to check.

        Args:
            output_filename (str): Filename for the vasprun.xml file. Change
                this only if it is different from the default (unlikely).
        """
        self.output_filename = output_filename

    def check(self, directory="./"):
        """Check for error."""
        try:
            v = load_vasprun(os.path.join(directory, self.output_filename))
            if not v.converged:
                return True
        except Exception:
            pass
        return False

    def correct(self, directory="./"):
        """Perform corrections."""
        v = load_vasprun(os.path.join(directory, self.output_filename))
        algo = v.incar.get("ALGO", "Normal").lower()
        actions = []
        errors = ["Unconverged"]
        if not v.converged_electronic:
            # NOTE: This is the amin error handler
            # Sometimes an AMIN warning can appear with large unit cell dimensions, so we'll address it now
            if max(v.final_structure.lattice.abc) > 50.0 and v.incar.get("AMIN", 0.1) > 0.01:
                actions.append({"dict": "INCAR", "action": {"_set": {"AMIN": 0.01}}})

            if (
                v.incar.get("ISMEAR", -1) >= 0
                and v.incar.get("METAGGA", "--") != "--"
                and (algo != "all" or (not 50 <= v.incar.get("IALGO", 38) <= 59))
            ):
                # If meta-GGA, go straight to Algo = All only if ISMEAR is greater or equal 0.
                # Algo = All is recommended in the VASP manual and some meta-GGAs explicitly
                # say to set Algo = All for proper convergence. I am using "--" as the check
                # for METAGGA here because this is the default in the vasprun.xml file
                actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "All"}}})

            # If a hybrid is used, do not set Algo = Fast or VeryFast. Hybrid calculations do not
            # support these algorithms, but no warning is printed.
            if v.incar.get("LHFCALC", False):
                if v.incar.get("ISMEAR", -1) >= 0 or not 50 <= v.incar.get("IALGO", 38) <= 59:
                    if algo != "all":
                        actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "All"}}})
                    # See the VASP manual section on LHFCALC for more information.
                    elif algo != "damped":
                        actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Damped", "TIME": 0.5}}})
                else:
                    actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Normal"}}})

            # Ladder from VeryFast to Fast to Normal to All
            # (except for meta-GGAs and hybrids).
            # These progressively switch to more stable but more
            # expensive algorithms.
            if len(actions) == 0:
                if algo == "veryfast":
                    actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Fast"}}})
                elif algo == "fast":
                    actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Normal"}}})
                elif algo == "normal" and v.incar.get("ISMEAR", 1) >= 0:
                    # NB: default for ISMEAR is 1. To avoid algo_tet errors, only set
                    # ALGO = ALL if ISMEAR >= 0
                    actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "All"}}})
                else:
                    # Try mixing as last resort
                    new_settings = {
                        "ISTART": 1,
                        "ALGO": "Normal",
                        "NELMDL": -6,
                        "BMIX": 0.001,
                        "AMIX_MAG": 0.8,
                        "BMIX_MAG": 0.001,
                    }

                    if not all(v.incar.get(k, "") == val for k, val in new_settings.items()):
                        actions.append({"dict": "INCAR", "action": {"_set": new_settings}})

        elif not v.converged_ionic:
            # Just continue optimizing and let other handlers fix ionic
            # optimizer parameters
            actions += [
                {"dict": "INCAR", "action": {"_set": {"IBRION": 1}}},
                {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}},
            ]

        if actions:
            vi = VaspInput.from_directory(directory)

            # Check for PSMAXN errors - see extensive discussion here
            # https://github.com/materialsproject/custodian/issues/133
            # Only correct PSMAXN when run didn't converge for fixable reasons
            if os.path.isfile(os.path.join(directory, "OUTCAR")):
                with open(os.path.join(directory, "OUTCAR")) as file:
                    outcar_as_str = file.read()
                if "PSMAXN for non-local potential too small" in outcar_as_str:
                    if vi["INCAR"].get("LREAL", False) not in (False, "False", "false"):
                        actions += [
                            {"dict": "INCAR", "action": {"_set": {"LREAL": False}}},
                        ]
                    errors += ["psmaxn"]

            backup(VASP_BACKUP_FILES, directory=directory)
            VaspModder(vi=vi, directory=directory).apply_actions(actions)
            return {"errors": errors, "actions": actions}

        # Unfixable error. Just return None for actions.
        return {"errors": errors, "actions": None}


class IncorrectSmearingHandler(ErrorHandler):
    """
    Check if a calculation is a metal (zero bandgap), has been run with
    ISMEAR=-5, and is not a static calculation, which is only appropriate for
    semiconductors. If this occurs, this handler will rerun the calculation
    using the smearing settings appropriate for metals (ISMEAR=2, SIGMA=0.2).
    """

    is_monitor = False

    def __init__(self, output_filename: str = "vasprun.xml"):
        """Initialize the handler with the output file to check.

        Args:
            output_filename (str): Filename for the vasprun.xml file. Change
                this only if it is different from the default (unlikely).
        """
        self.output_filename = output_filename

    def check(self, directory="./"):
        """Check for error."""
        try:
            v = load_vasprun(os.path.join(directory, self.output_filename))
            # check whether bandgap is zero, tetrahedron smearing was used
            # and relaxation is performed.
            if v.eigenvalue_band_properties[0] == 0 and v.incar.get("ISMEAR", 1) < -3 and v.incar.get("NSW", 0) > 1:
                return True
        except Exception:
            pass
        return False

    def correct(self, directory="./"):
        """Perform corrections."""
        backup(VASP_BACKUP_FILES | {self.output_filename}, directory=directory)
        vi = VaspInput.from_directory(directory)

        actions = [
            {"dict": "INCAR", "action": {"_set": {"ISMEAR": 2}}},
            {"dict": "INCAR", "action": {"_set": {"SIGMA": 0.2}}},
        ]

        VaspModder(vi=vi, directory=directory).apply_actions(actions)
        return {"errors": ["IncorrectSmearing"], "actions": actions}


class KspacingMetalHandler(ErrorHandler):
    """
    Check if a SCAN calculation is a metal (zero bandgap) but has been run with
    a KSPACING value appropriate for semiconductors. If this occurs, this handler
    will rerun the calculation using the KSPACING setting appropriate for metals
    (KSPACING=0.22). Note that this handler depends on values set by set_kspacing
    logic in MPScanRelaxSet.
    """

    is_monitor = False

    def __init__(self, output_filename: str = "vasprun.xml"):
        """Initialize the handler with the output file to check.

        Args:
            output_filename (str): Filename for the vasprun.xml file. Change
                this only if it is different from the default (unlikely).
        """
        self.output_filename = output_filename

    def check(self, directory="./"):
        """Check for error."""
        try:
            v = load_vasprun(os.path.join(directory, self.output_filename))
            # check whether bandgap is zero and KSPACING is too large
            # using 0 as fallback value for KSPACING so that this handler does not trigger if KSPACING is not set
            if v.eigenvalue_band_properties[0] == 0 and v.incar.get("KSPACING", 0) > 0.22:
                return True
        except Exception:
            pass
        return False

    def correct(self, directory="./"):
        """Perform corrections."""
        backup(VASP_BACKUP_FILES | {self.output_filename}, directory=directory)
        vi = VaspInput.from_directory(directory)

        _dummy_structure = Structure(
            [1, 0, 0, 0, 1, 0, 0, 0, 1],
            ["I"],
            [[0, 0, 0]],
        )
        new_vis = MPScanRelaxSet(_dummy_structure, bandgap=0)

        actions = []
        actions.append({"dict": "INCAR", "action": {"_set": {"KSPACING": new_vis.incar["KSPACING"]}}})

        VaspModder(vi=vi, directory=directory).apply_actions(actions)
        return {"errors": ["ScanMetal"], "actions": actions}


@deprecated(
    KspacingMetalHandler,
    "ScanMetalHandler was deprecated on 2023-11-03 and will be removed in a future release. "
    "Use KspacingMetalHandler instead.",
)
class ScanMetalHandler(KspacingMetalHandler):
    """ScanMetalHandler was renamed because MP GGA workflow might also adopt kspacing
    in the future. Keeping this alias during a deprecation period for backwards compatibility.
    """

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the handler with the output file to check.

        Args:
            args: Positional arguments passed to parent class.
            kwargs: Keyword passed to parent class.
        """
        warnings.warn(
            "ScanMetalHandler is deprecated and will be removed in a future release. "
            "Use KspacingMetalHandler instead.",
            DeprecationWarning,
        )
        super().__init__(*args, **kwargs)


class LargeSigmaHandler(ErrorHandler):
    """
    When ISMEAR > 0 (Methfessel-Paxton), monitor the magnitude of the entropy
    term T*S in the OUTCAR file. If the entropy term is larger than 1 meV/atom, reduce the
    value of SIGMA. See VASP documentation for ISMEAR.
    """

    is_monitor = True

    def __init__(self):
        """Initializes the handler with a buffer time."""

    def check(self, directory="./"):
        """Check for error."""
        incar = Incar.from_file(os.path.join(directory, "INCAR"))
        try:
            outcar = load_outcar(os.path.join(directory, "OUTCAR"))
        except Exception:
            # Can't perform check if Outcar not valid
            return False

        if incar.get("ISMEAR", 1) > 0:
            # Read the latest entropy term.
            outcar.read_pattern(
                {"entropy": r"entropy T\*S.*= *(\D\d*\.\d*)"}, postprocess=float, reverse=True, terminate_on_match=True
            )
            n_atoms = Structure.from_file(os.path.join(directory, "POSCAR")).num_sites
            if outcar.data.get("entropy", []):
                entropy_per_atom = abs(np.max(outcar.data.get("entropy"))) / n_atoms

                # if more than 1 meV/atom, reduce sigma
                if entropy_per_atom > 0.001:
                    return True

        return False

    def correct(self, directory="./"):
        """Perform corrections."""
        backup(VASP_BACKUP_FILES, directory=directory)
        actions = []
        vi = VaspInput.from_directory(directory)
        sigma = vi["INCAR"].get("SIGMA", 0.2)

        # Reduce SIGMA by 0.06 if larger than 0.08
        # this will reduce SIGMA from the default of 0.2 to the practical
        # minimum value of 0.02 in 3 steps
        if sigma > 0.08:
            actions.append(
                {
                    "dict": "INCAR",
                    "action": {"_set": {"SIGMA": sigma - 0.06}},
                }
            )
        else:
            # https://vasp.at/wiki/index.php/ISMEAR recommends ISMEAR = 0 if you have
            # no a priori knowledge of your system ("then always use Gaussian smearing"
            actions.append(
                {
                    "dict": "INCAR",
                    "action": {"_set": {"ISMEAR": 0, "SIGMA": 0.05}},
                }
            )

        VaspModder(vi=vi, directory=directory).apply_actions(actions)
        return {"errors": ["LargeSigma"], "actions": actions}


class PotimErrorHandler(ErrorHandler):
    """
    Check if a run has excessively large positive energy changes.
    This is typically caused by too large a POTIM. Runs typically
    end up crashing with some other error (e.g. BRMIX) as the geometry
    gets progressively worse.
    """

    is_monitor = True

    def __init__(self, input_filename="POSCAR", output_filename="OSZICAR", dE_threshold=1):
        """Initialize the handler with the input and output files to check.

        Args:
            input_filename (str): This is the POSCAR file that the run
                started from. Defaults to "POSCAR". Change
                this only if it is different from the default (unlikely).
            output_filename (str): This is the OSZICAR file. Change
                this only if it is different from the default (unlikely).
            dE_threshold (float): The threshold energy change. Defaults to 1eV.
        """
        self.input_filename = input_filename
        self.output_filename = output_filename
        self.dE_threshold = dE_threshold

    def check(self, directory="./"):
        """Check for error."""
        try:
            oszicar = Oszicar(os.path.join(directory, self.output_filename))
            n = len(Poscar.from_file(self.input_filename).structure)
            max_dE = max(s["dE"] for s in oszicar.ionic_steps[1:]) / n
            if max_dE > self.dE_threshold:
                return True
        except Exception:
            return False
        return None

    def correct(self, directory="./"):
        """Perform corrections."""
        backup(VASP_BACKUP_FILES, directory=directory)
        vi = VaspInput.from_directory(directory)
        potim = vi["INCAR"].get("POTIM", 0.5)
        ibrion = vi["INCAR"].get("IBRION", 0)
        if potim < 0.2 and ibrion != 3:
            actions = [{"dict": "INCAR", "action": {"_set": {"IBRION": 3, "SMASS": 0.75}}}]
        elif potim < 0.1:
            actions = [{"dict": "INCAR", "action": {"_set": {"SYMPREC": 1e-8}}}]
        else:
            actions = [{"dict": "INCAR", "action": {"_set": {"POTIM": potim * 0.5}}}]

        VaspModder(vi=vi, directory=directory).apply_actions(actions)
        return {"errors": ["POTIM"], "actions": actions}


class FrozenJobErrorHandler(ErrorHandler):
    """
    Detects an error when the output file has not been updated
    in timeout seconds. Changes ALGO to Normal from Fast.
    """

    is_monitor = True

    def __init__(self, output_filename: str = "vasp.out", timeout=21_600) -> None:
        """Initialize the handler with the output file to check.

        Args:
            output_filename (str): This is the file where the stdout for vasp
                is being redirected. The error messages that are checked are
                present in the stdout. Defaults to "vasp.out", which is the
                default redirect used by :class:`custodian.vasp.jobs.VaspJob`.
            timeout (int): The time in seconds between checks where if there
                is no activity on the output file, the run is considered
                frozen. Defaults to 3600 seconds, i.e., 1 hour.
        """
        self.output_filename = output_filename
        self.timeout = timeout

    def check(self, directory="./"):
        """Check for error."""
        st = os.stat(os.path.join(directory, self.output_filename))
        if time.time() - st.st_mtime > self.timeout:
            return True
        return None

    def correct(self, directory="./"):
        """Perform corrections."""
        backup(VASP_BACKUP_FILES | {self.output_filename}, directory=directory)

        vi = VaspInput.from_directory(directory)
        actions = []
        if vi["INCAR"].get("ALGO", "Normal").lower() == "fast":
            actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Normal"}}})
        else:
            actions.append({"dict": "INCAR", "action": {"_set": {"SYMPREC": 1e-8}}})

        VaspModder(vi=vi, directory=directory).apply_actions(actions)

        return {"errors": ["Frozen job"], "actions": actions}


class NonConvergingErrorHandler(ErrorHandler):
    """
    Check if a run is hitting the maximum number of electronic steps at the
    last nionic_steps ionic steps (default=10). If so, change ALGO using a
    multi-step ladder scheme or kill the job.
    """

    is_monitor = True

    def __init__(self, output_filename: str = "OSZICAR", nionic_steps=10):
        """Initialize the handler with the output file to check.

        Args:
            output_filename (str): This is the OSZICAR file. Change
                this only if it is different from the default (unlikely).
            nionic_steps (int): The threshold number of ionic steps that
                needs to hit the maximum number of electronic steps for the
                run to be considered non-converging.
        """
        self.output_filename = output_filename
        self.nionic_steps = nionic_steps

    def check(self, directory="./"):
        """Check for error."""
        vi = VaspInput.from_directory(directory)
        n_elm = vi["INCAR"].get("NELM", 60)  # number of electronic steps
        try:
            oszicar = Oszicar(os.path.join(directory, self.output_filename))
            elec_steps = oszicar.electronic_steps
            if len(elec_steps) > self.nionic_steps:
                return all(len(e) == n_elm for e in elec_steps[-(self.nionic_steps + 1) : -1])
        except Exception:
            pass
        return False

    def correct(self, directory="./"):
        """Perform corrections."""
        incar = (vi := VaspInput.from_directory(directory))["INCAR"]
        algo = incar.get("ALGO", "Normal").lower()
        amix = incar.get("AMIX", 0.4)
        bmix = incar.get("BMIX", 1.0)
        amin = incar.get("AMIN", 0.1)
        actions = []

        # NOTE: This is the algo_tet handler response.
        if (
            incar.get("ALGO", "Normal").lower() in {"all", "damped"} or (50 <= incar.get("IALGO", 38) <= 59)
        ) and incar.get("ISMEAR", 1) < 0:
            # ALGO=All/Damped / IALGO=5X often fails with ISMEAR < 0. There are two options VASP
            # suggests: 1) Use ISMEAR = 0 (and a small sigma) to get the SCF to converge.
            # 2) Use ALGO = Damped but only *after* an ISMEAR = 0 run where the wavefunction
            # has been stored and read in for the subsequent run.
            #
            # For simplicity, we go with Option 1 here, but if the user wants high-quality
            # DOS then they should consider running a subsequent job with ISMEAR = -5 and
            # ALGO = Damped, provided the wavefunction has been stored.
            actions.append({"dict": "INCAR", "action": {"_set": {"ISMEAR": 0, "SIGMA": 0.05}}})
            if incar.get("NEDOS") or incar.get("EMIN") or incar.get("EMAX"):
                warnings.warn(
                    "This looks like a DOS run. You may want to follow-up this job with ALGO = Damped"
                    " and ISMEAR = -5, using the wavefunction from the current job.",
                    UserWarning,
                )

        # NOTE: This is the amin error handler
        # Sometimes an AMIN warning can appear with large unit cell dimensions, so we'll address it now
        if max(Structure.from_file(os.path.join(directory, "CONTCAR")).lattice.abc) > 50 and amin > 0.01:
            actions.append({"dict": "INCAR", "action": {"_set": {"AMIN": 0.01}}})

        # If a hybrid is used, do not set Algo = Fast or VeryFast. Hybrid calculations do not
        # support these algorithms, but no warning is printed.
        # If meta-GGA, go straight to Algo = All. Algo = All is recommended in the VASP
        # manual and some meta-GGAs explicitly say to set Algo = All for proper convergence.
        # I am using "none" here because METAGGA is a string variable and this is the default
        if (incar.get("LHFCALC", False) or incar.get("METAGGA", "none").lower() != "none") and algo != "all":
            actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "All"}}})

        # Ladder from VeryFast to Fast to Normal to All
        # (except for meta-GGAs and hybrids).
        # These progressively switch to more stable but more
        # expensive algorithms.
        if len(actions) == 0:
            if algo == "veryfast":
                actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Fast"}}})
            elif algo == "fast":
                actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "Normal"}}})
            elif algo == "normal" and incar.get("ISMEAR", 1) >= 0:
                actions.append({"dict": "INCAR", "action": {"_set": {"ALGO": "All"}}})
            elif algo == "all" or (algo == "normal" and incar.get("ISMEAR", 1) < 0):
                if amix > 0.1 and bmix > 0.01:
                    # Try linear mixing
                    actions.append(
                        {
                            "dict": "INCAR",
                            "action": {"_set": {"ALGO": "Normal", "AMIX": 0.1, "BMIX": 0.01, "ICHARG": 2}},
                        }
                    )
                elif bmix < 3.0 and amin > 0.01:
                    # Try increasing bmix
                    actions.append(
                        {
                            "dict": "INCAR",
                            "action": {"_set": {"Algo": "Normal", "AMIN": 0.01, "BMIX": 3.0, "ICHARG": 2}},
                        }
                    )

        if actions:
            backup(VASP_BACKUP_FILES, directory=directory)
            VaspModder(vi=vi, directory=directory).apply_actions(actions)
            return {"errors": ["Non-converging job"], "actions": actions}
        # Unfixable error. Just return None for actions.
        return {"errors": ["Non-converging job"], "actions": None}

    @classmethod
    def from_dict(cls, dct):
        """
        Custom from_dict method to preserve backwards compatibility with
        older versions of Custodian.
        """
        dct.pop("change_algo", None)
        return cls(
            output_filename=dct.get("output_filename", "OSZICAR"),
            nionic_steps=dct.get("nionic_steps", 10),
        )


class WalltimeHandler(ErrorHandler):
    """
    Check if a run is nearing the walltime. If so, write a STOPCAR with
    LSTOP or LABORT = .True.. You can specify the walltime either in the init (
    which is unfortunately necessary for SGE and SLURM systems. If you happen
    to be running on a PBS system and the PBS_WALLTIME variable is in the run
    environment, the wall time will be automatically determined if not set.
    """

    is_monitor = True

    # The WalltimeHandler should not terminate as we want VASP to terminate
    # itself naturally with the STOPCAR.
    is_terminating = False

    # This handler will be unrecoverable, but custodian shouldn't raise an
    # error
    raises_runtime_error = False

    def __init__(self, wall_time=None, buffer_time=300, electronic_step_stop=False):
        """Initialize the handler with a buffer time.

        Args:
            wall_time (int): Total walltime in seconds. If this is None and
                the job is running on a PBS system, the handler will attempt to
                determine the walltime from the PBS_WALLTIME environment
                variable. If the wall time cannot be determined or is not
                set, this handler will have no effect.
            buffer_time (int): The min amount of buffer time in secs at the
                end that the STOPCAR will be written. The STOPCAR is written
                when the time remaining is < the higher of 3 x the average
                time for each ionic step and the buffer time. Defaults to
                300 secs, which is the default polling time of Custodian.
                This is typically sufficient for the current ionic step to
                complete. But if other operations are being performed after
                the run has stopped, the buffer time may need to be increased
                accordingly.
            electronic_step_stop (bool): Whether to check for electronic steps
                instead of ionic steps (e.g. for static runs on large systems or
                static HSE runs, ...). Be careful that results such as density
                or wavefunctions might not be converged at the electronic level.
                Should be used with LWAVE = .True. to be useful. If this is
                True, the STOPCAR is written with LABORT = .TRUE. instead of
                LSTOP = .TRUE.
        """
        if wall_time is not None:
            self.wall_time = wall_time
        elif "PBS_WALLTIME" in os.environ:
            self.wall_time = int(os.environ["PBS_WALLTIME"])
        elif "SBATCH_TIMELIMIT" in os.environ:
            self.wall_time = int(os.environ["SBATCH_TIMELIMIT"])
        else:
            self.wall_time = None
        self.buffer_time = buffer_time
        # Sets CUSTODIAN_WALLTIME_START as the start time to use for
        # future jobs in the same batch environment.  Can also be
        # set manually be the user in the batch environment.
        if "CUSTODIAN_WALLTIME_START" in os.environ:
            self.start_time = datetime.datetime.strptime(
                os.environ["CUSTODIAN_WALLTIME_START"], "%a %b %d %H:%M:%S %Z %Y"
            )
        else:
            self.start_time = datetime.datetime.now()
            os.environ["CUSTODIAN_WALLTIME_START"] = datetime.datetime.strftime(
                self.start_time, "%a %b %d %H:%M:%S UTC %Y"
            )

        self.electronic_step_stop = electronic_step_stop
        self.electronic_steps_timings = [0]
        self.prev_check_time = self.start_time

    def check(self, directory="./"):
        """Check for error."""
        if self.wall_time:
            run_time = datetime.datetime.now() - self.start_time
            total_secs = run_time.total_seconds()
            outcar = load_outcar(os.path.join(directory, "OUTCAR"))
            if not self.electronic_step_stop:
                # Determine max time per ionic step.
                outcar.read_pattern({"timings": r"LOOP\+.+real time(.+)"}, postprocess=float)
                time_per_step = np.max(outcar.data.get("timings")) if outcar.data.get("timings", []) else 0
            else:
                # Determine max time per electronic step.
                outcar.read_pattern({"timings": "LOOP:.+real time(.+)"}, postprocess=float)
                time_per_step = np.max(outcar.data.get("timings")) if outcar.data.get("timings", []) else 0

            # If the remaining time is less than average time for 3
            # steps or buffer_time.
            time_left = self.wall_time - total_secs
            if time_left < max(time_per_step * 3, self.buffer_time):
                return True

        return False

    def correct(self, directory="./"):
        """Perform corrections."""
        content = "LSTOP = .TRUE." if not self.electronic_step_stop else "LABORT = .TRUE."
        # Write STOPCAR
        actions = [{"file": "STOPCAR", "action": {"_file_create": {"content": content}}}]

        modder = Modder(actions=[FileActions], directory=directory)
        for action in actions:
            modder.modify(action["action"], action["file"])
        return {"errors": ["Walltime reached"], "actions": None}


class CheckpointHandler(ErrorHandler):
    """
    This is not an error handler per se, but rather a checkpointer. What this
    does is that every X seconds, a STOPCAR and CHKPT will be written. This
    forces VASP to stop at the end of the next ionic step. The files are then
    copied into a subdir, and then the job is restarted. To use this proper,
    max_errors in Custodian must be set to a very high value, and you
    probably wouldn't want to use any standard VASP error handlers. The
    checkpoint will be stored in subdirs chk_#. This should be used in
    combination with the StoppedRunHandler.
    """

    is_monitor = True

    # The CheckpointHandler should not terminate as we want VASP to terminate
    # itself naturally with the STOPCAR.
    is_terminating = False

    def __init__(self, interval=3600):
        """Initialize the handler with an interval.

        Args:
            interval (int): Interval at which to checkpoint in seconds.
            Defaults to 3600 (1 hr).
        """
        self.interval = interval
        self.start_time = datetime.datetime.now()
        self.chk_counter = 0

    def check(self, directory="./"):
        """Check for error."""
        run_time = datetime.datetime.now() - self.start_time
        total_secs = run_time.seconds + run_time.days * 3600 * 24
        if total_secs > self.interval:
            return True
        return False

    def correct(self, directory="./"):
        """Perform corrections."""
        content = "LSTOP = .TRUE."
        chkpt_content = f'Index: {self.chk_counter}\nTime: "{datetime.datetime.now()}"'
        self.chk_counter += 1

        # Write STOPCAR
        actions = [
            {"file": "STOPCAR", "action": {"_file_create": {"content": content}}},
            {
                "file": "chkpt.yaml",
                "action": {"_file_create": {"content": chkpt_content}},
            },
        ]

        modder = Modder(actions=[FileActions], directory=directory)
        for action in actions:
            modder.modify(action["action"], action["file"])

        # Reset the clock.
        self.start_time = datetime.datetime.now()

        return {"errors": ["Checkpoint reached"], "actions": actions}

    def __str__(self):
        return f"CheckpointHandler with interval {self.interval}"


class StoppedRunHandler(ErrorHandler):
    """
    This is not an error handler per se, but rather a checkpointer. What this
    does is that every X seconds, a STOPCAR will be written. This forces VASP to
    stop at the end of the next ionic step. The files are then copied into a
    subdir, and then the job is restarted. To use this proper, max_errors in
    Custodian must be set to a very high value, and you probably wouldn't
    want to use any standard VASP error handlers. The checkpoint will be
    stored in subdirs chk_#. This should be used in combination with the
    StoppedRunHandler.
    """

    is_monitor = False

    # The CheckpointHandler should not terminate as we want VASP to terminate
    # itself naturally with the STOPCAR.
    is_terminating = False

    def __init__(self):
        """Dummy init."""

    def check(self, directory="./"):
        """Check for error."""
        return os.path.isfile(os.path.join(directory, "chkpt.yaml"))

    def correct(self, directory="./"):
        """Perform corrections."""
        d = loadfn(os.path.join(directory, "chkpt.yaml"))
        i = d["Index"]
        name = shutil.make_archive(os.path.join(directory, f"vasp.chk.{i}"), "gztar")

        actions = [{"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}}]

        modder = Modder(actions=[FileActions], directory=directory)
        for action in actions:
            modder.modify(action["action"], action["file"])

        actions.append({"Checkpoint": name})

        return {"errors": ["Stopped run."], "actions": actions}


class PositiveEnergyErrorHandler(ErrorHandler):
    """
    Check if a run has positive absolute energy.
    If so, change ALGO from Fast to Normal or kill the job.
    """

    is_monitor = True

    def __init__(self, output_filename: str = "OSZICAR"):
        """Initialize the handler with the output file to check.

        Args:
            output_filename (str): This is the OSZICAR file. Change
                this only if it is different from the default (unlikely).
        """
        self.output_filename = output_filename

    def check(self, directory="./"):
        """Check for error."""
        try:
            oszicar = Oszicar(os.path.join(directory, self.output_filename))
            if oszicar.final_energy > 0:
                return True
        except Exception:
            pass
        return False

    def correct(self, directory="./"):
        """Perform corrections."""
        # change ALGO = Fast to Normal if ALGO is !Normal
        vi = VaspInput.from_directory(directory)
        algo = vi["INCAR"].get("ALGO", "Normal").lower()
        if algo not in {"normal", "n"}:
            backup(VASP_BACKUP_FILES | {self.output_filename}, directory=directory)
            actions = [{"dict": "INCAR", "action": {"_set": {"ALGO": "Normal"}}}]
            VaspModder(vi=vi, directory=directory).apply_actions(actions)
            return {"errors": ["Positive energy"], "actions": actions}
        # decrease POTIM if ALGO is 'normal' and IBRION != -1 (i.e. it's not a static calculation)
        if algo == "normal" and vi["INCAR"].get("IBRION", 1) > -1:
            potim = round(vi["INCAR"].get("POTIM", 0.5) / 2.0, 2)
            actions = [{"dict": "INCAR", "action": {"_set": {"POTIM": potim}}}]
            VaspModder(vi=vi, directory=directory).apply_actions(actions)
            return {"errors": ["Positive energy"], "actions": actions}
        # Unfixable error. Just return None for actions.
        return {"errors": ["Positive energy"], "actions": None}
