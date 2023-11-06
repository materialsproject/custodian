---
layout: default
title: custodian.cp2k.utils.md
nav_exclude: true
---

# custodian.cp2k.utils module

This module holds different utility functions. Mainly used by handlers.

## custodian.cp2k.utils.activate_diag(actions)

Activate diagonalization

actions (list):

```none
list of actions that are being applied. Will be modified in-place
```

## custodian.cp2k.utils.activate_ot(actions, ci)

Activate OT scheme.

actions (list):

```none
list of actions that are being applied. Will be modified in-place
```

ci (Cp2kInput):

```none
Cp2kInput object, used to coordinate settings
```

## custodian.cp2k.utils.can_use_ot(output, ci, minimum_band_gap=0.1)

Check whether OT can be used:

```none
OT should not already be activated
The output should show that the system has a band gap that is greater than minimum_band_gap
```

* **Parameters**
  * **output** (*Cp2kOutput*) – cp2k output object for determining band gap
  * **ci** (*Cp2kInput*) – cp2k input object for determining if OT is already active
  * **minimum_band_gap** (*float*) – the minimum band gap for OT

## custodian.cp2k.utils.cleanup_input(ci)

Intention is to use this to remove problematic parts of the input file.

> 1. The “POTENTIAL” section within KIND cannot be empty, but the number
>    sequences used inside do not play nice with the input parser

## custodian.cp2k.utils.get_conv(outfile)

Helper function to get the convergence info from SCF loops

* **Parameters**

  **outfile** (*str*) – output file to parse
* **Returns**

  returns convergence info (change in energy between SCF steps) as a
  single list (flattened across outer scf loops).

## custodian.cp2k.utils.restart(actions, output_file, input_file, no_actions_needed=False)

Helper function. To discard old restart if convergence is already good, and copy
the restart file to the input file. Restart also supports switching back and forth
between OT and diagonalization as needed based on convergence behavior. If OT is not
being used and a band gap exists, then OT will be activated.

* **Parameters**
  * **actions** (*list*) – list of actions that the handler is going to return to custodian. If
    no actions are present, then non are added by this function
  * **output_file** (*str*) – the cp2k output file name.
  * **input_file** (*str*) – the cp2k input file name.

## custodian.cp2k.utils.tail(filename, n=10)

Returns the last n lines of a file as a list (including empty lines)