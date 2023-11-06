---
layout: default
title: custodian.lobster.md
nav_exclude: true
---

# custodian.lobster package

This package implements Lobster Jobs and Error Handlers.

## Subpackages

* [custodian.lobster.tests package]()
  ```none
    * [custodian.lobster.tests.test_handlers module](custodian.lobster.tests.test_handlers.md)


    * [custodian.lobster.tests.test_jobs module](custodian.lobster.tests.test_jobs.md)
  ```
* [custodian.lobster.handlers module](custodian.lobster.handlers.md)
  * [`ChargeSpillingValidator`](custodian.lobster.handlers.md#custodian.lobster.handlers.ChargeSpillingValidator)
    * [`ChargeSpillingValidator.check()`](custodian.lobster.handlers.md#custodian.lobster.handlers.ChargeSpillingValidator.check)
  * [`EnoughBandsValidator`](custodian.lobster.handlers.md#custodian.lobster.handlers.EnoughBandsValidator)
    * [`EnoughBandsValidator.check()`](custodian.lobster.handlers.md#custodian.lobster.handlers.EnoughBandsValidator.check)
  * [`LobsterFilesValidator`](custodian.lobster.handlers.md#custodian.lobster.handlers.LobsterFilesValidator)
    * [`LobsterFilesValidator.check()`](custodian.lobster.handlers.md#custodian.lobster.handlers.LobsterFilesValidator.check)
* [custodian.lobster.jobs module](custodian.lobster.jobs.md)
  * [`LobsterJob`](custodian.lobster.jobs.md#custodian.lobster.jobs.LobsterJob)
    * [`LobsterJob.postprocess()`](custodian.lobster.jobs.md#custodian.lobster.jobs.LobsterJob.postprocess)
    * [`LobsterJob.run()`](custodian.lobster.jobs.md#custodian.lobster.jobs.LobsterJob.run)
    * [`LobsterJob.setup()`](custodian.lobster.jobs.md#custodian.lobster.jobs.LobsterJob.setup)