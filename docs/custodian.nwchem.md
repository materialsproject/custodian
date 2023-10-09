---
layout: default
title: custodian.nwchem.md
nav_exclude: true
---

# custodian.nwchem package

This package implements various Nwchem Jobs and Error Handlers.

## Subpackages

* [custodian.nwchem.tests package]()
  ```none
    * [custodian.nwchem.tests.test_handlers module](custodian.nwchem.tests.test_handlers.md)
  ```
* [custodian.nwchem.handlers module](custodian.nwchem.handlers.md)
  * [`NwchemErrorHandler`](custodian.nwchem.handlers.md#custodian.nwchem.handlers.NwchemErrorHandler)
    * [`NwchemErrorHandler.check()`](custodian.nwchem.handlers.md#custodian.nwchem.handlers.NwchemErrorHandler.check)
    * [`NwchemErrorHandler.correct()`](custodian.nwchem.handlers.md#custodian.nwchem.handlers.NwchemErrorHandler.correct)
* [custodian.nwchem.jobs module](custodian.nwchem.jobs.md)
  * [`NwchemJob`](custodian.nwchem.jobs.md#custodian.nwchem.jobs.NwchemJob)
    * [`NwchemJob.postprocess()`](custodian.nwchem.jobs.md#custodian.nwchem.jobs.NwchemJob.postprocess)
    * [`NwchemJob.run()`](custodian.nwchem.jobs.md#custodian.nwchem.jobs.NwchemJob.run)
    * [`NwchemJob.setup()`](custodian.nwchem.jobs.md#custodian.nwchem.jobs.NwchemJob.setup)