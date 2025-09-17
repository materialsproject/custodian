"""Created 17 June, 2024"""

import os

import numpy as np
import pytest
from monty.os.path import zpath
from pymatgen.core import Lattice, Structure
from pymatgen.io.vasp import Kpoints
from pymatgen.util.testing import MatSciTest

from custodian.vasp.utils import _estimate_num_k_points_from_kspacing, increase_k_point_density
from tests.conftest import TEST_FILES


class TestKPointUtils(MatSciTest):
    large_structure = Structure.from_file(zpath(os.path.join(TEST_FILES, "POSCAR_mp-1200292")))

    small_structure = Structure(
        Lattice.from_parameters(a=3.8, b=3.8, c=3.8, alpha=60.0, beta=60.0, gamma=60.0),
        ["Si", "Si"],
        [[(-1) ** i * 0.125 for _ in range(3)] for i in range(2)],
    )

    def test_k_point_estimate(self) -> None:
        kspacing_values = [1, 0.8, 0.6, 0.4, 0.2, 0.1]
        expected_kpoints_per_axis = [(1, 1, 1), (1, 1, 1), (1, 1, 1), (2, 1, 1), (3, 2, 2), (5, 4, 4)]
        assert all(
            _estimate_num_k_points_from_kspacing(self.large_structure, kspacing) == expected_kpoints_per_axis[i]
            for i, kspacing in enumerate(kspacing_values)
        )

    def test_kpoint_density_increase(self):
        new_kpoints = increase_k_point_density(Kpoints(), self.large_structure, force_gamma=True, min_kpoints=4)
        assert new_kpoints["kpoints"] == ((2, 2, 1),)

        new_kpoints = increase_k_point_density(2, self.large_structure, force_gamma=True, min_kpoints=10)
        assert new_kpoints["KSPACING"] == pytest.approx(0.229885)
        new_kpoints_divis = _estimate_num_k_points_from_kspacing(self.large_structure, new_kpoints["KSPACING"])
        assert np.prod(new_kpoints_divis) == 12

        new_kpoints = increase_k_point_density(Kpoints(), self.small_structure, force_gamma=True, min_kpoints=14)
        assert new_kpoints["kpoints"] == ((3, 3, 3),)
