---
layout: default
title: custodian.vasp.utils.md
nav_exclude: true
---

# custodian.vasp.utils module

Utility methods for VASP error handlers.

### custodian.vasp.utils.increase_k_point_density(kpoints: Kpoints | dict | float, structure: Structure, factor: float = 0.1, max_inc: int = 500, min_kpoints: int = 1, force_gamma: bool = True)

Inputs:
: kpoints (Kpoints, dict, float, int) :
  : If a dict or Kpoints object: original Kpoints used in the calculation
    If a float: the original KSPACING used in the calculation
  <br/>
  structure (Structure) : associated structure
  factor (float) : factor used to increase k-point density.
  <br/>
  > The first increase uses approximately (1 + factor) higher k-point density.
  > The second increase: ~ (1 + 2\*factor) higher k-kpoint density, etc.
  max_inc (int)
  : before giving up
  <br/>
  min_kpoints (int): The minimum permitted number of k-points.
  : Can be useful if using the tetrahedron method, where
    at least 4 k-points are needed.
  <br/>
  force_gamma (bool) = True: whether to use Gamma-centered or
  : Monkhorst-Pack grids

Outputs:
: dict :
  : The new Kpoints object / KSPACING consistent with constraints.
    If an empty dict, no new k-point mesh could be found.