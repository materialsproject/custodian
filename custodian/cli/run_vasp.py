"""
This is a master vasp running script to perform various combinations of VASP
runs.
"""

import logging
import sys

from pymatgen.io.vasp.inputs import Incar, Kpoints, VaspInput
from ruamel.yaml import YAML

from custodian.custodian import Custodian
from custodian.vasp.jobs import VaspJob


def load_class(mod, name):
    """Load the class from mod and name specification."""
    toks = name.split("?")
    params = {}
    if len(toks) == 2:
        for tok in toks[-1].split(","):
            p_toks = tok.split("=")
            params[p_toks[0]] = YAML(typ="rt").load(p_toks[1])
    elif len(toks) > 2:
        print("Bad handler specification")
        sys.exit(-1)
    mod = __import__(mod, globals(), locals(), [toks[0]], 0)
    return getattr(mod, toks[0])(**params)


def get_jobs(args):
    """Returns a generator of jobs. Allows of "infinite" jobs."""
    vasp_command = args.command.split()
    # save initial INCAR for rampU runs
    n_ramp_u = args.jobs.count("rampU")
    ramps = 0
    if n_ramp_u:
        incar = Incar.from_file("INCAR")
        ldauu = incar["LDAUU"]
        ldauj = incar["LDAUJ"]

    n_jobs = len(args.jobs)
    post_settings = []  # append to this list to have settings applied on next job
    for i, job in enumerate(args.jobs):
        final = i == n_jobs - 1
        suffix = "." + job if any(char.isdigit() for char in job) else f".{job}{i + 1}"
        settings = post_settings
        post_settings = []
        backup = i == 0
        copy_magmom = False
        vinput = VaspInput.from_directory(".")
        if i > 0:
            settings.append({"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}})

        job_type = job.lower()
        auto_npar = True

        if args.no_auto_npar:
            auto_npar = False

        if job_type.startswith("static_derived"):
            from pymatgen.io.vasp.sets import MPStaticSet

            vis = MPStaticSet.from_prev_calc(
                ".",
                user_incar_settings={"LWAVE": True, "EDIFF": 1e-6},
                ediff_per_atom=False,
            )
            settings += [
                {"dict": "INCAR", "action": {"_set": dict(vis.incar)}},
                {"dict": "KPOINTS", "action": {"_set": vis.kpoints.as_dict()}},
            ]

        if job_type.startswith("static_dielectric_derived"):
            from pymatgen.io.vasp.sets import MPStaticDielectricDFPTVaspInputSet, MPStaticSet

            # vis = MPStaticSet.from_prev_calc(
            #     ".",
            #     user_incar_settings={
            #         "EDIFF": 1e-6,
            #         "IBRION": 8,
            #         "LEPSILON": True,
            #         "LREAL": False,
            #         "LPEAD": True,
            #         "ISMEAR": 0,
            #         "SIGMA": 0.01,
            #     },
            #     ediff_per_atom=False,
            # )
            vis = MPStaticDielectricDFPTVaspInputSet()
            incar = vis.get_incar(vinput["POSCAR"].structure)
            unset = {}
            for key in ("NPAR", "KPOINT_BSE", "LAECHG", "LCHARG", "LVHAR", "NSW"):
                incar.pop(key, None)
                if key in vinput["INCAR"]:
                    unset[key] = 1
            kpoints = vis.get_kpoints(vinput["POSCAR"].structure)
            settings += [
                {"dict": "INCAR", "action": {"_set": dict(incar), "_unset": unset}},
                {"dict": "KPOINTS", "action": {"_set": kpoints.as_dict()}},
            ]
            auto_npar = False
        elif job_type.startswith("static") and vinput["KPOINTS"]:
            m = [kpt * args.static_kpoint for kpt in vinput["KPOINTS"].kpts[0]]
            settings += [
                {"dict": "INCAR", "action": {"_set": {"NSW": 0}}},
                {"dict": "KPOINTS", "action": {"_set": {"kpoints": [m]}}},
            ]

        elif job_type.startswith("nonscf_derived"):
            from pymatgen.io.vasp.sets import MPNonSCFSet

            vis = MPNonSCFSet.from_prev_calc(".", copy_chgcar=False, user_incar_settings={"LWAVE": True})
            settings += [
                {"dict": "INCAR", "action": {"_set": dict(vis.incar)}},
                {"dict": "KPOINTS", "action": {"_set": vis.kpoints.as_dict()}},
            ]

        elif job_type.startswith("optics_derived"):
            from pymatgen.io.vasp.sets import MPNonSCFSet

            vis = MPNonSCFSet.from_prev_calc(
                ".",
                optics=True,
                copy_chgcar=False,
                nedos=2001,
                mode="uniform",
                nbands_factor=5,
                user_incar_settings={
                    "LWAVE": True,
                    "ALGO": "Exact",
                    "SIGMA": 0.01,
                    "EDIFF": 1e-6,
                },
                ediff_per_atom=False,
            )
            settings += [
                {"dict": "INCAR", "action": {"_set": dict(vis.incar)}},
                {"dict": "KPOINTS", "action": {"_set": vis.kpoints.as_dict()}},
            ]

        elif job_type.startswith("rampu"):
            f = ramps / (n_ramp_u - 1)
            settings.append(
                {
                    "dict": "INCAR",
                    "action": {
                        "_set": {
                            "LDAUJ": [j * f for j in ldauj],
                            "LDAUU": [u * f for u in ldauu],
                        }
                    },
                }
            )
            copy_magmom = True
            ramps += 1
        elif job_type.startswith(("quick_relax", "quickrelax")):
            kpoints = vinput["KPOINTS"]
            incar = vinput["INCAR"]
            structure = vinput["POSCAR"].structure
            if "ISMEAR" in incar:
                post_settings.append({"dict": "INCAR", "action": {"_set": {"ISMEAR": incar["ISMEAR"]}}})
            else:
                post_settings.append({"dict": "INCAR", "action": {"_unset": {"ISMEAR": 1}}})
            post_settings.append({"dict": "KPOINTS", "action": {"_set": kpoints.as_dict()}})
            # lattice vectors with length < 9 will get >1 KPOINT
            low_kpoints = Kpoints.gamma_automatic([max(int(18 / length), 1) for length in structure.lattice.abc])
            settings += [
                {"dict": "INCAR", "action": {"_set": {"ISMEAR": 0}}},
                {"dict": "KPOINTS", "action": {"_set": low_kpoints.as_dict()}},
            ]

            # let vasp determine encut (will be lower than
            # needed for compatibility with other runs)
            if "ENCUT" in incar:
                post_settings.append({"dict": "INCAR", "action": {"_set": {"ENCUT": incar["ENCUT"]}}})
                settings.append({"dict": "INCAR", "action": {"_unset": {"ENCUT": 1}}})

        elif job_type.startswith("relax"):
            pass
        elif job_type.startswith("full_relax"):
            yield from VaspJob.full_opt_run(vasp_command)
        else:
            print(f"Unsupported job type: {job}")
            sys.exit(-1)

        if not job_type.startswith("full_relax"):
            yield VaspJob(
                vasp_command,
                final=final,
                suffix=suffix,
                backup=backup,
                settings_override=settings,
                copy_magmom=copy_magmom,
                auto_npar=auto_npar,
            )


def do_run(args):
    """Do the run."""
    FORMAT = "%(asctime)s %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO, filename="run.log")
    logging.info(f"Handlers used are {args.handlers}")
    handlers = [load_class("custodian.vasp.handlers", handler) for handler in args.handlers]
    validators = [load_class("custodian.vasp.validators", validator) for validator in args.validators]

    c = Custodian(
        handlers,
        get_jobs(args),
        validators,
        max_errors=args.max_errors,
        scratch_dir=args.scratch,
        gzipped_output=args.gzip,
        checkpoint=True,
    )
    c.run()


def main():
    """Main method."""
    import argparse

    parser = argparse.ArgumentParser(
        description="run_vasp is a master script to perform various kinds of VASP runs.",
        epilog="Author: Shyue Ping Ong",
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
        "--no_auto_npar",
        action="store_true",
        help="Set to true to turn off auto_npar. Useful for certain machines "
        "and calculations where you want absolute control.",
    )

    parser.add_argument(
        "-z",
        "--gzip",
        dest="gzip",
        action="store_true",
        help="Add this option to gzip the final output. Do not gzip if you "
        "are going to perform an additional static run.",
    )

    parser.add_argument(
        "-s",
        "--scratch",
        dest="scratch",
        nargs="?",
        default=None,
        type=str,
        help="Scratch directory to perform run in. Specify the root scratch "
        "directory as the code will automatically create a temporary "
        "subdirectory to run the job.",
    )

    parser.add_argument(
        "-ks",
        "--kpoint-static",
        dest="static_kpoint",
        nargs="?",
        default=1,
        type=int,
        help="The multiplier to use for the KPOINTS of a static run (if "
        "any). For example, setting this to 2 means that if your "
        "original run was done using a k-point grid of 2x3x3, "
        "the static run will be done with a k-point grid of 4x6x6. This "
        "defaults to 1, i.e., static runs are performed with the same "
        "k-point grid as relaxation runs.",
    )

    parser.add_argument(
        "-me",
        "--max-errors",
        dest="max_errors",
        nargs="?",
        default=10,
        type=int,
        help="Maximum number of errors to allow before quitting",
    )

    parser.add_argument(
        "-hd",
        "--handlers",
        dest="handlers",
        nargs="+",
        default=[
            "VaspErrorHandler",
            "MeshSymmetryErrorHandler",
            "UnconvergedErrorHandler",
            "NonConvergingErrorHandler",
            "PotimErrorHandler",
        ],
        type=str,
        help="The ErrorHandlers to use specified as string class names, "
        "with optional arguments specified as a url-like string. For "
        "example, VaspErrorHandler?output_filename=myfile.out specifies a "
        "VaspErrorHandler with output_name set to myfile.out. Multiple "
        "arguments are joined by a comma. E.g., MyHandler?myfile=a,"
        "data=1. The arguments are deserialized using yaml.",
    )

    parser.add_argument(
        "-vd",
        "--validators",
        dest="validators",
        nargs="+",
        default=["VasprunXMLValidator"],
        type=str,
        help="The Validators to use specified as string class names, "
        "with optional arguments specified as a url-like string. For "
        "example, VaspErrorHandler?output_filename=myfile.out specifies a "
        "VaspErrorHandler with output_name set to myfile.out. Multiple "
        "arguments are joined by a comma. E.g., MyHandler?myfile=a,"
        "data=1. The arguments are deserialized using yaml.",
    )

    parser.add_argument(
        "jobs",
        metavar="jobs",
        type=str,
        nargs="+",
        default=["relax", "relax"],
        help="Jobs to execute. Only sequences of relax, "
        "quickrelax, static, rampU, full_relax, static_derived, "
        "nonscf_derived, optics_derived are "
        'supported at the moment. For example, "relax relax static" '
        "will run a double relaxation followed by a static "
        "run. By default, suffixes are given sequential numbering,"
        "but this can be overridden by adding a number to the job"
        "type, e.g. relax5 relax6 relax7",
    )

    args = parser.parse_args()
    do_run(args)
