---
layout: default
title: custodian.cp2k.validators.md
nav_exclude: true
---

# custodian.cp2k.validators module

Validators for CP2K calculations.


### _class_ custodian.cp2k.validators.Cp2kOutputValidator(output_file='cp2k.out')
Bases: `Cp2kValidator`

Checks that a valid cp2k output file was generated


* **Parameters**

    **output_file** (*str*) – cp2k output file to analyze



#### check()
Check for valid output. Checks that the end of the
program was reached, and that convergence was
achieved.


#### _property_ exit()
Don’t raise error, but exit the job


#### _property_ kill()
Kill the job with raise error.


#### _property_ no_children()
Job should not have children


### _class_ custodian.cp2k.validators.Cp2kValidator()
Bases: [`Validator`](custodian.custodian.md#custodian.custodian.Validator)

Base validator.


#### _abstract_ check()
Check whether validation failed. Here, True means
validation failed.


#### _abstract property_ exit()
Don’t raise error, but exit the job


#### _abstract property_ kill()
Kill the job with raise error.


#### _abstract property_ no_children()
Job should not have children