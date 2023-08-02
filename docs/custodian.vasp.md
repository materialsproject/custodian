---
layout: default
title: custodian.vasp.md
nav_exclude: true
---

# custodian.vasp package

This package implements various VASP Jobs and Error Handlers.

## Subpackages


* [custodian.vasp.tests package](custodian.vasp.tests.md)




        * [custodian.vasp.tests.conftest module](custodian.vasp.tests.conftest.md)


        * [custodian.vasp.tests.test_handlers module](custodian.vasp.tests.test_handlers.md)


        * [custodian.vasp.tests.test_jobs module](custodian.vasp.tests.test_jobs.md)


        * [custodian.vasp.tests.test_validators module](custodian.vasp.tests.test_validators.md)




* [custodian.vasp.handlers module](custodian.vasp.handlers.md)


    * [`AliasingErrorHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.AliasingErrorHandler)


        * [`AliasingErrorHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.AliasingErrorHandler.check)


        * [`AliasingErrorHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.AliasingErrorHandler.correct)


        * [`AliasingErrorHandler.error_msgs`](custodian.vasp.handlers.md#custodian.vasp.handlers.AliasingErrorHandler.error_msgs)


        * [`AliasingErrorHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.AliasingErrorHandler.is_monitor)


    * [`CheckpointHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.CheckpointHandler)


        * [`CheckpointHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.CheckpointHandler.check)


        * [`CheckpointHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.CheckpointHandler.correct)


        * [`CheckpointHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.CheckpointHandler.is_monitor)


        * [`CheckpointHandler.is_terminating`](custodian.vasp.handlers.md#custodian.vasp.handlers.CheckpointHandler.is_terminating)


    * [`DriftErrorHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.DriftErrorHandler)


        * [`DriftErrorHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.DriftErrorHandler.check)


        * [`DriftErrorHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.DriftErrorHandler.correct)


    * [`FrozenJobErrorHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.FrozenJobErrorHandler)


        * [`FrozenJobErrorHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.FrozenJobErrorHandler.check)


        * [`FrozenJobErrorHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.FrozenJobErrorHandler.correct)


        * [`FrozenJobErrorHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.FrozenJobErrorHandler.is_monitor)


    * [`IncorrectSmearingHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.IncorrectSmearingHandler)


        * [`IncorrectSmearingHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.IncorrectSmearingHandler.check)


        * [`IncorrectSmearingHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.IncorrectSmearingHandler.correct)


        * [`IncorrectSmearingHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.IncorrectSmearingHandler.is_monitor)


    * [`LargeSigmaHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.LargeSigmaHandler)


        * [`LargeSigmaHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.LargeSigmaHandler.check)


        * [`LargeSigmaHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.LargeSigmaHandler.correct)


        * [`LargeSigmaHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.LargeSigmaHandler.is_monitor)


    * [`LrfCommutatorHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.LrfCommutatorHandler)


        * [`LrfCommutatorHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.LrfCommutatorHandler.check)


        * [`LrfCommutatorHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.LrfCommutatorHandler.correct)


        * [`LrfCommutatorHandler.error_msgs`](custodian.vasp.handlers.md#custodian.vasp.handlers.LrfCommutatorHandler.error_msgs)


        * [`LrfCommutatorHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.LrfCommutatorHandler.is_monitor)


    * [`MeshSymmetryErrorHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.MeshSymmetryErrorHandler)


        * [`MeshSymmetryErrorHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.MeshSymmetryErrorHandler.check)


        * [`MeshSymmetryErrorHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.MeshSymmetryErrorHandler.correct)


        * [`MeshSymmetryErrorHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.MeshSymmetryErrorHandler.is_monitor)


    * [`NonConvergingErrorHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.NonConvergingErrorHandler)


        * [`NonConvergingErrorHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.NonConvergingErrorHandler.check)


        * [`NonConvergingErrorHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.NonConvergingErrorHandler.correct)


        * [`NonConvergingErrorHandler.from_dict()`](custodian.vasp.handlers.md#custodian.vasp.handlers.NonConvergingErrorHandler.from_dict)


        * [`NonConvergingErrorHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.NonConvergingErrorHandler.is_monitor)


    * [`PositiveEnergyErrorHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.PositiveEnergyErrorHandler)


        * [`PositiveEnergyErrorHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.PositiveEnergyErrorHandler.check)


        * [`PositiveEnergyErrorHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.PositiveEnergyErrorHandler.correct)


        * [`PositiveEnergyErrorHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.PositiveEnergyErrorHandler.is_monitor)


    * [`PotimErrorHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.PotimErrorHandler)


        * [`PotimErrorHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.PotimErrorHandler.check)


        * [`PotimErrorHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.PotimErrorHandler.correct)


        * [`PotimErrorHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.PotimErrorHandler.is_monitor)


    * [`ScanMetalHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.ScanMetalHandler)


        * [`ScanMetalHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.ScanMetalHandler.check)


        * [`ScanMetalHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.ScanMetalHandler.correct)


        * [`ScanMetalHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.ScanMetalHandler.is_monitor)


    * [`StdErrHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.StdErrHandler)


        * [`StdErrHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.StdErrHandler.check)


        * [`StdErrHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.StdErrHandler.correct)


        * [`StdErrHandler.error_msgs`](custodian.vasp.handlers.md#custodian.vasp.handlers.StdErrHandler.error_msgs)


        * [`StdErrHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.StdErrHandler.is_monitor)


    * [`StoppedRunHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.StoppedRunHandler)


        * [`StoppedRunHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.StoppedRunHandler.check)


        * [`StoppedRunHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.StoppedRunHandler.correct)


        * [`StoppedRunHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.StoppedRunHandler.is_monitor)


        * [`StoppedRunHandler.is_terminating`](custodian.vasp.handlers.md#custodian.vasp.handlers.StoppedRunHandler.is_terminating)


    * [`UnconvergedErrorHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.UnconvergedErrorHandler)


        * [`UnconvergedErrorHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.UnconvergedErrorHandler.check)


        * [`UnconvergedErrorHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.UnconvergedErrorHandler.correct)


        * [`UnconvergedErrorHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.UnconvergedErrorHandler.is_monitor)


    * [`VaspErrorHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.VaspErrorHandler)


        * [`VaspErrorHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.VaspErrorHandler.check)


        * [`VaspErrorHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.VaspErrorHandler.correct)


        * [`VaspErrorHandler.error_msgs`](custodian.vasp.handlers.md#custodian.vasp.handlers.VaspErrorHandler.error_msgs)


        * [`VaspErrorHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.VaspErrorHandler.is_monitor)


    * [`WalltimeHandler`](custodian.vasp.handlers.md#custodian.vasp.handlers.WalltimeHandler)


        * [`WalltimeHandler.check()`](custodian.vasp.handlers.md#custodian.vasp.handlers.WalltimeHandler.check)


        * [`WalltimeHandler.correct()`](custodian.vasp.handlers.md#custodian.vasp.handlers.WalltimeHandler.correct)


        * [`WalltimeHandler.is_monitor`](custodian.vasp.handlers.md#custodian.vasp.handlers.WalltimeHandler.is_monitor)


        * [`WalltimeHandler.is_terminating`](custodian.vasp.handlers.md#custodian.vasp.handlers.WalltimeHandler.is_terminating)


        * [`WalltimeHandler.raises_runtime_error`](custodian.vasp.handlers.md#custodian.vasp.handlers.WalltimeHandler.raises_runtime_error)


* [custodian.vasp.interpreter module](custodian.vasp.interpreter.md)


    * [`VaspModder`](custodian.vasp.interpreter.md#custodian.vasp.interpreter.VaspModder)


        * [`VaspModder.apply_actions()`](custodian.vasp.interpreter.md#custodian.vasp.interpreter.VaspModder.apply_actions)


* [custodian.vasp.jobs module](custodian.vasp.jobs.md)


    * [`GenerateVaspInputJob`](custodian.vasp.jobs.md#custodian.vasp.jobs.GenerateVaspInputJob)


        * [`GenerateVaspInputJob.postprocess()`](custodian.vasp.jobs.md#custodian.vasp.jobs.GenerateVaspInputJob.postprocess)


        * [`GenerateVaspInputJob.run()`](custodian.vasp.jobs.md#custodian.vasp.jobs.GenerateVaspInputJob.run)


        * [`GenerateVaspInputJob.setup()`](custodian.vasp.jobs.md#custodian.vasp.jobs.GenerateVaspInputJob.setup)


    * [`VaspJob`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob)


        * [`VaspJob.constrained_opt_run()`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob.constrained_opt_run)


        * [`VaspJob.double_relaxation_run()`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob.double_relaxation_run)


        * [`VaspJob.full_opt_run()`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob.full_opt_run)


        * [`VaspJob.metagga_opt_run()`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob.metagga_opt_run)


        * [`VaspJob.postprocess()`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob.postprocess)


        * [`VaspJob.run()`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob.run)


        * [`VaspJob.setup()`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob.setup)


        * [`VaspJob.terminate()`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob.terminate)


    * [`VaspNEBJob`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspNEBJob)


        * [`VaspNEBJob.postprocess()`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspNEBJob.postprocess)


        * [`VaspNEBJob.run()`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspNEBJob.run)


        * [`VaspNEBJob.setup()`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspNEBJob.setup)


* [custodian.vasp.validators module](custodian.vasp.validators.md)


    * [`VaspAECCARValidator`](custodian.vasp.validators.md#custodian.vasp.validators.VaspAECCARValidator)


        * [`VaspAECCARValidator.check()`](custodian.vasp.validators.md#custodian.vasp.validators.VaspAECCARValidator.check)


    * [`VaspFilesValidator`](custodian.vasp.validators.md#custodian.vasp.validators.VaspFilesValidator)


        * [`VaspFilesValidator.check()`](custodian.vasp.validators.md#custodian.vasp.validators.VaspFilesValidator.check)


    * [`VaspNpTMDValidator`](custodian.vasp.validators.md#custodian.vasp.validators.VaspNpTMDValidator)


        * [`VaspNpTMDValidator.check()`](custodian.vasp.validators.md#custodian.vasp.validators.VaspNpTMDValidator.check)


    * [`VasprunXMLValidator`](custodian.vasp.validators.md#custodian.vasp.validators.VasprunXMLValidator)


        * [`VasprunXMLValidator.check()`](custodian.vasp.validators.md#custodian.vasp.validators.VasprunXMLValidator.check)


    * [`check_broken_chgcar()`](custodian.vasp.validators.md#custodian.vasp.validators.check_broken_chgcar)