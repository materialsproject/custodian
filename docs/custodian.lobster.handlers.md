---
layout: default
title: custodian.lobster.handlers.md
nav_exclude: true
---

# custodian.lobster.handlers module

This module implements specific error handler for Lobster runs.

## *class* custodian.lobster.handlers.ChargeSpillingValidator(output_filename: str = ‘lobsterout’, charge_spilling_limit: float = 0.05)

Bases: [`Validator`](custodian.custodian.md#custodian.custodian.Validator)

Check if spilling is below certain threshold!

* **Parameters**
  * **output_filename** – filename of the output file of lobter, usually lobsterout
  * **charge_spilling_limit** – limit of the charge spilling that will be considered okay

### check()

open lobsterout and find charge spilling

## *class* custodian.lobster.handlers.EnoughBandsValidator(output_filename: str = ‘lobsterout’)

Bases: [`Validator`](custodian.custodian.md#custodian.custodian.Validator)

validates if enough bands for COHP calculation are available

* **Parameters**

  **output_filename** – filename of output file, usually lobsterout

### check()

checks if the VASP calculation had enough bands
:returns: (bool) if True, too few bands have been applied

## *class* custodian.lobster.handlers.LobsterFilesValidator()

Bases: [`Validator`](custodian.custodian.md#custodian.custodian.Validator)

Check for existence of some of the files that lobster

```none
normally create upon running.
```

Check if lobster terminated normally by looking for finished

Dummy init

### check()

Check for errors.