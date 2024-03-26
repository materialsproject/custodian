"""This is a master vasp running script to converging kpoints for a calculation."""

import logging

from pymatgen.io.vasp.inputs import VaspInput
from pymatgen.io.vasp.outputs import Vasprun

from custodian.custodian import Custodian
from custodian.vasp.handlers import UnconvergedErrorHandler, VaspErrorHandler
from custodian.vasp.jobs import VaspJob

FORMAT = "%(asctime)s %(message)s"
logging.basicConfig(format=FORMAT, level=logging.INFO, filename="run.log")


def get_runs(vasp_command, target=1e-3, max_steps=10, mode="linear"):
    """Generate the runs using a generator until convergence is achieved."""
    energy = 0
    vasp_input = VaspInput.from_directory(".")
    kpoints = vasp_input["KPOINTS"].kpts[0]
    for step in range(max_steps):
        m = [(kpt * (step + 1)) for kpt in kpoints] if mode == "linear" else [(kpt + 1) for kpt in kpoints]
        if step == 0:
            settings = None
            backup = True
        else:
            backup = False
            v = Vasprun("vasprun.xml")
            e_per_atom = v.final_energy / len(v.final_structure)
            ediff = abs(e_per_atom - energy)
            if ediff < target:
                logging.info(f"Converged to {ediff} eV/atom!")
                break
            energy = e_per_atom
            settings = [
                {"dict": "INCAR", "action": {"_set": {"ISTART": 1}}},
                {"dict": "KPOINTS", "action": {"_set": {"kpoints": [m]}}},
                {
                    "filename": "CONTCAR",
                    "action": {"_file_copy": {"dest": "POSCAR"}},
                },
            ]
        yield VaspJob(
            vasp_command,
            final=False,
            backup=backup,
            suffix=f".kpoints.{'x'.join(map(str, m))}",
            settings_override=settings,
        )


def do_run(args):
    """Perform the run."""
    handlers = [VaspErrorHandler(), UnconvergedErrorHandler()]
    c = Custodian(
        handlers,
        get_runs(
            vasp_command=args.command.split(),
            target=args.target,
            mode=args.mode,
            max_steps=args.max_steps,
        ),
        max_errors=10,
    )
    c.run()


def main():
    """Main method."""
    import argparse

    parser = argparse.ArgumentParser(
        description="""
    converge_kpoints perform a KPOINTS convergence. What this script will do
    is to run a particular VASP run with increasing multiples of the initial
    KPOINT grid until a target convergence in energy per atom is reached.
    For example, let's say you have vasp input files that has a k-point grid
    of 1x1x1. This script will perform sequence jobs with k-point grids of
    1x1x1, 2x2x2, 3x3x3, 4x4x4, ... until convergence is achieved. The
    default convergence criteria is 1meV/atom, but this can be set using the
    --target option.
    """,
        epilog="""Author: Shyue Ping Ong""",
    )

    parser.add_argument(
        "-c",
        "--command",
        dest="command",
        nargs="?",
        default="pvasp",
        type=str,
        help="VASP command. Defaults to pvasp. If you are using mpirun, set this to something like 'mpirun pvasp'.",
    )

    parser.add_argument(
        "-i",
        "--increment_mode",
        dest="mode",
        nargs="?",
        default="linear",
        type=str,
        choices=["linear", "inc"],
        help="Mode for increasing kpoints. In linear mode, multiples of "
        "the existing kpoints are done. E.g., 2x4x2 -> 4x8x4 -> 6x12x6. "
        "In inc mode, all KPOINTS are incremented by 1 at each stage, "
        "i.e., 2x4x2 -> 3x5x3 ->4x6x4. Note that the latter mode does "
        "not preserve KPOINTS symmetry, though it is probably less "
        "expensive.",
    )

    parser.add_argument(
        "-m",
        "--max_steps",
        dest="max_steps",
        nargs="?",
        default=10,
        type=int,
        help="The maximum number of KPOINTS increment steps. This puts an "
        "upper bound on the largest KPOINT converge grid attempted.",
    )

    parser.add_argument(
        "-t",
        "--target",
        dest="target",
        nargs="?",
        default=0.001,
        type=float,
        help="The target converge in energy per atom to achieve "
        "convergence. E.g., 1e-3 means the KPOINTS will be increased "
        "until a converged of 1meV is reached.",
    )

    args = parser.parse_args()
    do_run(args)


if __name__ == "__main__":
    main()
