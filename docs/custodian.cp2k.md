---
layout: default
title: custodian.cp2k.md
nav_exclude: true
---

# custodian.cp2k package

This package implements various CP2K Jobs and Error Handlers.

## Subpackages


* [custodian.cp2k.tests package](custodian.cp2k.tests.md)




        * [custodian.cp2k.tests.test_handlers module](custodian.cp2k.tests.test_handlers.md)


        * [custodian.cp2k.tests.test_jobs module](custodian.cp2k.tests.test_jobs.md)




* [custodian.cp2k.handlers module](custodian.cp2k.handlers.md)


* [custodian.cp2k.interpreter module](custodian.cp2k.interpreter.md)


    * [`Cp2kModder`](custodian.cp2k.interpreter.md#custodian.cp2k.interpreter.Cp2kModder)


        * [`Cp2kModder.apply_actions()`](custodian.cp2k.interpreter.md#custodian.cp2k.interpreter.Cp2kModder.apply_actions)


* [custodian.cp2k.jobs module](custodian.cp2k.jobs.md)


    * [`Cp2kJob`](custodian.cp2k.jobs.md#custodian.cp2k.jobs.Cp2kJob)


        * [`Cp2kJob.double_job()`](custodian.cp2k.jobs.md#custodian.cp2k.jobs.Cp2kJob.double_job)


        * [`Cp2kJob.gga_static_to_hybrid()`](custodian.cp2k.jobs.md#custodian.cp2k.jobs.Cp2kJob.gga_static_to_hybrid)


        * [`Cp2kJob.postprocess()`](custodian.cp2k.jobs.md#custodian.cp2k.jobs.Cp2kJob.postprocess)


        * [`Cp2kJob.pre_screen_hybrid()`](custodian.cp2k.jobs.md#custodian.cp2k.jobs.Cp2kJob.pre_screen_hybrid)


        * [`Cp2kJob.run()`](custodian.cp2k.jobs.md#custodian.cp2k.jobs.Cp2kJob.run)


        * [`Cp2kJob.setup()`](custodian.cp2k.jobs.md#custodian.cp2k.jobs.Cp2kJob.setup)


        * [`Cp2kJob.terminate()`](custodian.cp2k.jobs.md#custodian.cp2k.jobs.Cp2kJob.terminate)


* [custodian.cp2k.utils module](custodian.cp2k.utils.md)


    * [`activate_diag()`](custodian.cp2k.utils.md#custodian.cp2k.utils.activate_diag)


    * [`activate_ot()`](custodian.cp2k.utils.md#custodian.cp2k.utils.activate_ot)


    * [`can_use_ot()`](custodian.cp2k.utils.md#custodian.cp2k.utils.can_use_ot)


    * [`cleanup_input()`](custodian.cp2k.utils.md#custodian.cp2k.utils.cleanup_input)


    * [`get_conv()`](custodian.cp2k.utils.md#custodian.cp2k.utils.get_conv)


    * [`restart()`](custodian.cp2k.utils.md#custodian.cp2k.utils.restart)


    * [`tail()`](custodian.cp2k.utils.md#custodian.cp2k.utils.tail)


* [custodian.cp2k.validators module](custodian.cp2k.validators.md)


    * [`Cp2kOutputValidator`](custodian.cp2k.validators.md#custodian.cp2k.validators.Cp2kOutputValidator)


        * [`Cp2kOutputValidator.check()`](custodian.cp2k.validators.md#custodian.cp2k.validators.Cp2kOutputValidator.check)


        * [`Cp2kOutputValidator.exit`](custodian.cp2k.validators.md#custodian.cp2k.validators.Cp2kOutputValidator.exit)


        * [`Cp2kOutputValidator.kill`](custodian.cp2k.validators.md#custodian.cp2k.validators.Cp2kOutputValidator.kill)


        * [`Cp2kOutputValidator.no_children`](custodian.cp2k.validators.md#custodian.cp2k.validators.Cp2kOutputValidator.no_children)


    * [`Cp2kValidator`](custodian.cp2k.validators.md#custodian.cp2k.validators.Cp2kValidator)


        * [`Cp2kValidator.check()`](custodian.cp2k.validators.md#custodian.cp2k.validators.Cp2kValidator.check)


        * [`Cp2kValidator.exit`](custodian.cp2k.validators.md#custodian.cp2k.validators.Cp2kValidator.exit)


        * [`Cp2kValidator.kill`](custodian.cp2k.validators.md#custodian.cp2k.validators.Cp2kValidator.kill)


        * [`Cp2kValidator.no_children`](custodian.cp2k.validators.md#custodian.cp2k.validators.Cp2kValidator.no_children)