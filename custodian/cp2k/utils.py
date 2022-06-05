"""
This module holds different utility functions. Mainly used by handlers.
"""

import itertools
import os
from collections import deque

from pymatgen.io.cp2k.inputs import Cp2kInput
from pymatgen.io.cp2k.outputs import Cp2kOutput


def restart(actions, output_file, input_file, no_actions_needed=False):
    """
    Helper function. To discard old restart if convergence is already good, and copy
    the restart file to the input file. Restart also supports switching back and forth
    between OT and diagonalization as needed based on convergence behavior. If OT is not
    being used and a band gap exists, then OT will be activated.

    Args:
        actions (list): list of actions that the handler is going to return to custodian. If
            no actions are present, then non are added by this function
        output_file (str): the cp2k output file name.
        input_file (str): the cp2k input file name.
    """
    if actions or no_actions_needed:
        o = Cp2kOutput(output_file)
        ci = Cp2kInput.from_file(input_file)
        restart_file = o.filenames.get("restart")
        restart_file = restart_file[-1] if restart_file else None
        if ci.check("force_eval/dft"):
            wfn_restart = ci["force_eval"]["dft"].get("wfn_restart_file_name")
        else:
            wfn_restart = None

        # If convergence is already pretty good, or we have moved to a new ionic step,
        # discard the old WFN
        if wfn_restart:
            conv = get_conv(output_file)
            if (conv and conv[-1] <= 1e-5) or restart_file:
                actions.append(
                    {"dict": input_file, "action": {"_unset": {"FORCE_EVAL": {"DFT": "WFN_RESTART_FILE_NAME"}}}}
                )

        # If issues arose after some ionic steps and corrections are possible
        # then switch the restart file to the input file.
        if restart_file:
            actions.insert(
                0,
                {
                    "file": os.path.abspath(restart_file),
                    "action": {"_file_copy": {"dest": os.path.abspath(input_file)}},
                },
            )


# TODO Not sure I like this solution
def cleanup_input(ci):
    """
    Intention is to use this to remove problematic parts of the input file.

        (1) The "POTENTIAL" section within KIND cannot be empty, but the number
            sequences used inside do not play nice with the input parser

    """
    if not hasattr(ci, "subsections") or not ci.subsections:
        return
    if any(k.upper() == "POTENTIAL" for k in ci.subsections):
        ci.subsections.pop("POTENTIAL")
    for k, v in ci.subsections.items():
        cleanup_input(v)


def activate_ot(actions, ci):
    """
    Activate OT scheme.

    actions (list):
        list of actions that are being applied. Will be modified in-place

    ci (Cp2kInput):
        Cp2kInput object, used to coordinate settings
    """

    eps_scf = ci["force_eval"]["dft"]["scf"]["eps_scf"]

    ot_actions = [
        {
            "dict": "cp2k.inp",
            "action": [
                (
                    "_unset",
                    {"FORCE_EVAL": {"DFT": "SCF"}},
                )
            ],
        },
        {
            "dict": "cp2k.inp",
            "action": [
                (
                    "_set",
                    {
                        "FORCE_EVAL": {
                            "DFT": {
                                "SCF": {
                                    "MAX_SCF": 20,
                                    "OT": {
                                        "ENERGY_GAP": 0.01,
                                        "ALGORITHM": "STRICT",
                                        "PRECONDITIONER": "FULL_ALL",
                                        "MINIMIZER": "DIIS",
                                        "LINESEARCH": "2PNT",
                                    },
                                    "OUTER_SCF": {"MAX_SCF": 20, "EPS_SCF": eps_scf},
                                }
                            }
                        }
                    },
                )
            ],
        },
    ]
    actions.extend(ot_actions)


def activate_diag(actions):
    """
    Activate diagonalization

    actions (list):
        list of actions that are being applied. Will be modified in-place
    """

    diag_actions = [
        {"dict": "cp2k.inp", "action": ("_unset", {"FORCE_EVAL": {"DFT": {"SCF": "OT"}}})},
        {"dict": "cp2k.inp", "action": ("_unset", {"FORCE_EVAL": {"DFT": {"SCF": "OUTER_SCF"}}})},
        {
            "dict": "cp2k.inp",
            "action": (
                "_set",
                {
                    "FORCE_EVAL": {
                        "DFT": {
                            "SCF": {
                                "MAX_SCF": 200,
                                "ADDED_MOS": 100,  # TODO needs to be dynamic value
                                "MAX_DIIS": 15,
                                "DIAGONALIZATION": {},
                                "MIXING": {"ALPHA": 0.05},
                                "SMEAR": {"ELEC_TEMP": 300, "METHOD": "FERMI_DIRAC"},
                            }
                        }
                    }
                },
            ),
        },
    ]
    actions.extend(diag_actions)


def can_use_ot(output, ci, minimum_band_gap=0.1):
    """
    Check whether OT can be used:
        OT should not already be activated
        The output should show that the system has a band gap that is greater than minimum_band_gap

    Args:
        output (Cp2kOutput): cp2k output object for determining band gap
        ci (Cp2kInput): cp2k input object for determining if OT is already active
        minimum_band_gap (float): the minimum band gap for OT
    """
    output.parse_dos()
    if (
        not ci.check("FORCE_EVAL/DFT/SCF/OT")
        and not ci.check("FORCE_EVAL/DFT/KPOINTS")
        and output.band_gap
        and output.band_gap > minimum_band_gap
    ):
        return True
    return False


def tail(filename, n=10):
    """
    Returns the last n lines of a file as a list (including empty lines)
    """
    with open(filename) as f:
        t = deque(f, n)
        if t:
            return t
        return [""] * n


def get_conv(outfile):
    """
    Helper function to get the convergence info from SCF loops

    Args:
        outfile (str): output file to parse
    Returns:
        returns convergence info (change in energy between SCF steps) as a
        single list (flattened across outer scf loops).
    """
    out = Cp2kOutput(outfile, auto_load=False, verbose=False)
    out.parse_scf_opt()
    return list(itertools.chain.from_iterable(out.data["convergence"]))
