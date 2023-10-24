---
layout: default
title: custodian.qchem.utils.md
nav_exclude: true
---

# custodian.qchem.utils module

This module contains utility functions that are useful for Q-Chem jobs.

## custodian.qchem.utils.perturb_coordinates(old_coords, negative_freq_vecs, molecule_perturb_scale, reversed_direction)

Perturbs a structure along the imaginary mode vibrational frequency vectors

old_coords (np.ndarray): Initial molecule coordinates
negative_freq_vecs (list of np.ndarray): Vibrational frequency vectors corresponding to

> imaginary (negative) frequencies

molecule_perturb_scale (float): Scaling factor for coordination modification. The perturbation

```none
vector will be multiplied by this factor.
```

reversed_direction (bool): If True, then perturb in direction opposite of frequency modes.

## custodian.qchem.utils.vector_list_diff(vecs1, vecs2)

Calculates the summed difference of two vectors

Typically this function is used to compare between the different atom-wise
components of a vibrational frequency mode vector.

vecs1 (np.ndarray): Collection of vectors to be compared. Typical dimension

```none
n x 3
```

vecs2 (np.ndarray): Collection of vectors to be compared. Typical dimension

```none
n x 3
```