---
layout: default
title: custodian.gaussian.md
nav_exclude: true
---

# custodian.gaussian package

This package implements various Gaussian Jobs and Error Handlers.

* [custodian.gaussian.handlers module](custodian.gaussian.handlers.md)
  * [`GaussianErrorHandler`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.GaussianErrorHandler)
    * [`GaussianErrorHandler.GRID_NAMES`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.GaussianErrorHandler.GRID_NAMES)
    * [`GaussianErrorHandler.MEM_UNITS`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.GaussianErrorHandler.MEM_UNITS)
    * [`GaussianErrorHandler.activate_better_guess`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.GaussianErrorHandler.activate_better_guess)
    * [`GaussianErrorHandler.check()`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.GaussianErrorHandler.check)
    * [`GaussianErrorHandler.conv_criteria`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.GaussianErrorHandler.conv_criteria)
    * [`GaussianErrorHandler.convert_mem()`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.GaussianErrorHandler.convert_mem)
    * [`GaussianErrorHandler.correct()`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.GaussianErrorHandler.correct)
    * [`GaussianErrorHandler.error_defs`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.GaussianErrorHandler.error_defs)
    * [`GaussianErrorHandler.error_patt`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.GaussianErrorHandler.error_patt)
    * [`GaussianErrorHandler.grid_patt`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.GaussianErrorHandler.grid_patt)
    * [`GaussianErrorHandler.recom_mem_patt`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.GaussianErrorHandler.recom_mem_patt)
  * [`WallTimeErrorHandler`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.WallTimeErrorHandler)
    * [`WallTimeErrorHandler.check()`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.WallTimeErrorHandler.check)
    * [`WallTimeErrorHandler.correct()`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.WallTimeErrorHandler.correct)
    * [`WallTimeErrorHandler.is_monitor`](custodian.gaussian.handlers.md#custodian.gaussian.handlers.WallTimeErrorHandler.is_monitor)
* [custodian.gaussian.jobs module](custodian.gaussian.jobs.md)
  * [`GaussianJob`](custodian.gaussian.jobs.md#custodian.gaussian.jobs.GaussianJob)
    * [`GaussianJob.generate_better_guess()`](custodian.gaussian.jobs.md#custodian.gaussian.jobs.GaussianJob.generate_better_guess)
    * [`GaussianJob.postprocess()`](custodian.gaussian.jobs.md#custodian.gaussian.jobs.GaussianJob.postprocess)
    * [`GaussianJob.run()`](custodian.gaussian.jobs.md#custodian.gaussian.jobs.GaussianJob.run)
    * [`GaussianJob.setup()`](custodian.gaussian.jobs.md#custodian.gaussian.jobs.GaussianJob.setup)
    * [`GaussianJob.terminate()`](custodian.gaussian.jobs.md#custodian.gaussian.jobs.GaussianJob.terminate)