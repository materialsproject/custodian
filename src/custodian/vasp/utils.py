"""Utility methods for VASP error handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from pymatgen.io.vasp.inputs import Kpoints

if TYPE_CHECKING:
    from pymatgen.core import Structure


def _estimate_num_k_points_from_kspacing(structure: Structure, kspacing: float) -> tuple[int, ...]:
    """
    Estimate the number of k-points used by VASP.

    Inputs:
        structure (Structure): structure used in the calculation
        kspacing (float): KSPACING used in the calculation
    Returns:
        tuple[int,int,int] : the number of estimated k-points on each axis.

    Note that there is a typo in the VASP manual:
        https://www.vasp.at/wiki/index.php/KSPACING
    The inner product between direct a_i and reciprocal b_i
    lattice vectors is conventionally a_i . b_j = 2 pi delta_ij

    That leads to an extra 2 pi factor in the expression for the
    number of k-points per axis from KSPACING. The formula used
    below has been checked for accuracy against VASP calculations.
    """
    return tuple(int(max(1, np.ceil(structure.lattice.reciprocal_lattice.abc[i] / kspacing))) for i in range(3))


def increase_k_point_density(
    kpoints: Kpoints | dict | float,
    structure: Structure,
    factor: float = 0.1,
    max_inc: int = 500,
    min_kpoints: int = 1,
    force_gamma: bool = True,
) -> dict:
    """
    Inputs:
        kpoints (Kpoints, dict, float, int) :
            If a dict or Kpoints object: original Kpoints used in the calculation
            If a float: the original KSPACING used in the calculation
        structure (Structure) : associated structure
        factor (float) : factor used to increase k-point density.
            The first increase uses approximately (1 + factor) higher k-point density.
            The second increase: ~ (1 + 2*factor) higher k-kpoint density, etc.
        max_inc (int) : the maximum permitted increases in k-point density
            before giving up
        min_kpoints (int): The minimum permitted number of k-points.
            Can be useful if using the tetrahedron method, where
            at least 4 k-points are needed.
        force_gamma (bool) = True: whether to use Gamma-centered or
            Monkhorst-Pack grids
    Outputs:
        dict :
            The new Kpoints object / KSPACING consistent with constraints.
            If an empty dict, no new k-point mesh could be found.
    """
    uses_kspacing = isinstance(kpoints, float | int)

    if uses_kspacing:
        orig_num_kpoints = np.prod(_estimate_num_k_points_from_kspacing(structure, kpoints))  # type: ignore[arg-type]

    else:
        if isinstance(kpoints, Kpoints):
            kpoints = kpoints.as_dict()

        orig_num_kpoints = np.prod(kpoints["kpoints"][0])  # type: ignore[index]

        # try to approximate k-points per reciprocal atom used in pymatgen
        lengths = structure.lattice.abc
        mult = max([nk * lengths[ik] for ik, nk in enumerate(kpoints["kpoints"][0])])  # type: ignore[index]
        ngrid = mult**3 / np.prod(lengths)
        kppa = len(structure) * ngrid

    mult_fac = 1.0 + factor
    min_kpoints = max(min_kpoints, 1)

    success = False
    for _ in range(max_inc):
        if uses_kspacing:
            new_kpoints: dict[str, Any] = {"KSPACING": round(kpoints / mult_fac, 6), "KGAMMA": force_gamma}  # type: ignore[operator]
            new_nk = _estimate_num_k_points_from_kspacing(structure, new_kpoints["KSPACING"])
        else:
            kpts = Kpoints.automatic_density(structure, mult_fac * kppa, force_gamma=force_gamma)  # type: ignore
            new_kpoints = {
                "generation_style": str(kpts.style),
                "kpoints": (tuple(kpts.kpts[0]),),
            }
            new_nk = new_kpoints["kpoints"][0]  # type: ignore[index]

        if (new_num_kpoints := np.prod(new_nk)) > orig_num_kpoints and (new_num_kpoints >= min_kpoints):
            success = True
            break

        mult_fac += factor

    return new_kpoints if success else {}  # type: ignore
