---
layout: default
title: API Documentation
nav_order: 6
---

# custodian package

Custodian is a simple, robust and flexible just-in-time (JIT) job management
framework written in Python.

## Subpackages


* [custodian.ansible package](custodian.ansible.md)


    * [Subpackages](custodian.ansible.md#subpackages)


        * [custodian.ansible.tests package](custodian.ansible.tests.md)




            * [custodian.ansible.tests.test_interpreter module](custodian.ansible.tests.test_interpreter.md)




        * [custodian.ansible.actions module](custodian.ansible.actions.md)


            * [`DictActions`](custodian.ansible.actions.md#custodian.ansible.actions.DictActions)


                * [`DictActions.add_to_set()`](custodian.ansible.actions.md#custodian.ansible.actions.DictActions.add_to_set)


                * [`DictActions.inc()`](custodian.ansible.actions.md#custodian.ansible.actions.DictActions.inc)


                * [`DictActions.pop()`](custodian.ansible.actions.md#custodian.ansible.actions.DictActions.pop)


                * [`DictActions.pull()`](custodian.ansible.actions.md#custodian.ansible.actions.DictActions.pull)


                * [`DictActions.pull_all()`](custodian.ansible.actions.md#custodian.ansible.actions.DictActions.pull_all)


                * [`DictActions.push()`](custodian.ansible.actions.md#custodian.ansible.actions.DictActions.push)


                * [`DictActions.push_all()`](custodian.ansible.actions.md#custodian.ansible.actions.DictActions.push_all)


                * [`DictActions.rename()`](custodian.ansible.actions.md#custodian.ansible.actions.DictActions.rename)


                * [`DictActions.set()`](custodian.ansible.actions.md#custodian.ansible.actions.DictActions.set)


                * [`DictActions.unset()`](custodian.ansible.actions.md#custodian.ansible.actions.DictActions.unset)


            * [`FileActions`](custodian.ansible.actions.md#custodian.ansible.actions.FileActions)


                * [`FileActions.file_copy()`](custodian.ansible.actions.md#custodian.ansible.actions.FileActions.file_copy)


                * [`FileActions.file_create()`](custodian.ansible.actions.md#custodian.ansible.actions.FileActions.file_create)


                * [`FileActions.file_delete()`](custodian.ansible.actions.md#custodian.ansible.actions.FileActions.file_delete)


                * [`FileActions.file_modify()`](custodian.ansible.actions.md#custodian.ansible.actions.FileActions.file_modify)


                * [`FileActions.file_move()`](custodian.ansible.actions.md#custodian.ansible.actions.FileActions.file_move)


            * [`get_nested_dict()`](custodian.ansible.actions.md#custodian.ansible.actions.get_nested_dict)


        * [custodian.ansible.interpreter module](custodian.ansible.interpreter.md)


            * [`Modder`](custodian.ansible.interpreter.md#custodian.ansible.interpreter.Modder)


                * [`Modder.modify()`](custodian.ansible.interpreter.md#custodian.ansible.interpreter.Modder.modify)


                * [`Modder.modify_object()`](custodian.ansible.interpreter.md#custodian.ansible.interpreter.Modder.modify_object)


* [custodian.cli package](custodian.cli.md)




    * [custodian.cli.converge_geometry module](custodian.cli.converge_geometry.md)


        * [`do_run()`](custodian.cli.converge_geometry.md#custodian.cli.converge_geometry.do_run)


        * [`get_runs()`](custodian.cli.converge_geometry.md#custodian.cli.converge_geometry.get_runs)


    * [custodian.cli.converge_kpoints module](custodian.cli.converge_kpoints.md)


        * [`do_run()`](custodian.cli.converge_kpoints.md#custodian.cli.converge_kpoints.do_run)


        * [`get_runs()`](custodian.cli.converge_kpoints.md#custodian.cli.converge_kpoints.get_runs)


        * [`main()`](custodian.cli.converge_kpoints.md#custodian.cli.converge_kpoints.main)


    * [custodian.cli.cstdn module](custodian.cli.cstdn.md)


        * [`main()`](custodian.cli.cstdn.md#custodian.cli.cstdn.main)


        * [`print_example()`](custodian.cli.cstdn.md#custodian.cli.cstdn.print_example)


        * [`run()`](custodian.cli.cstdn.md#custodian.cli.cstdn.run)


    * [custodian.cli.run_nwchem module](custodian.cli.run_nwchem.md)


        * [`do_run()`](custodian.cli.run_nwchem.md#custodian.cli.run_nwchem.do_run)


        * [`main()`](custodian.cli.run_nwchem.md#custodian.cli.run_nwchem.main)


    * [custodian.cli.run_vasp module](custodian.cli.run_vasp.md)


        * [`do_run()`](custodian.cli.run_vasp.md#custodian.cli.run_vasp.do_run)


        * [`get_jobs()`](custodian.cli.run_vasp.md#custodian.cli.run_vasp.get_jobs)


        * [`load_class()`](custodian.cli.run_vasp.md#custodian.cli.run_vasp.load_class)


        * [`main()`](custodian.cli.run_vasp.md#custodian.cli.run_vasp.main)


* [custodian.cp2k package](custodian.cp2k.md)


    * [Subpackages](custodian.cp2k.md#subpackages)


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


* [custodian.feff package](custodian.feff.md)


    * [Subpackages](custodian.feff.md#subpackages)


        * [custodian.feff.tests package](custodian.feff.tests.md)




            * [custodian.feff.tests.test_handler module](custodian.feff.tests.test_handler.md)


            * [custodian.feff.tests.test_jobs module](custodian.feff.tests.test_jobs.md)




        * [custodian.feff.handlers module](custodian.feff.handlers.md)


            * [`UnconvergedErrorHandler`](custodian.feff.handlers.md#custodian.feff.handlers.UnconvergedErrorHandler)


                * [`UnconvergedErrorHandler.check()`](custodian.feff.handlers.md#custodian.feff.handlers.UnconvergedErrorHandler.check)


                * [`UnconvergedErrorHandler.correct()`](custodian.feff.handlers.md#custodian.feff.handlers.UnconvergedErrorHandler.correct)


                * [`UnconvergedErrorHandler.is_monitor`](custodian.feff.handlers.md#custodian.feff.handlers.UnconvergedErrorHandler.is_monitor)


        * [custodian.feff.interpreter module](custodian.feff.interpreter.md)


            * [`FeffModder`](custodian.feff.interpreter.md#custodian.feff.interpreter.FeffModder)


                * [`FeffModder.apply_actions()`](custodian.feff.interpreter.md#custodian.feff.interpreter.FeffModder.apply_actions)


        * [custodian.feff.jobs module](custodian.feff.jobs.md)


            * [`FeffJob`](custodian.feff.jobs.md#custodian.feff.jobs.FeffJob)


                * [`FeffJob.postprocess()`](custodian.feff.jobs.md#custodian.feff.jobs.FeffJob.postprocess)


                * [`FeffJob.run()`](custodian.feff.jobs.md#custodian.feff.jobs.FeffJob.run)


                * [`FeffJob.setup()`](custodian.feff.jobs.md#custodian.feff.jobs.FeffJob.setup)


* [custodian.lobster package](custodian.lobster.md)


    * [Subpackages](custodian.lobster.md#subpackages)


        * [custodian.lobster.tests package](custodian.lobster.tests.md)




            * [custodian.lobster.tests.test_handlers module](custodian.lobster.tests.test_handlers.md)


            * [custodian.lobster.tests.test_jobs module](custodian.lobster.tests.test_jobs.md)




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


* [custodian.nwchem package](custodian.nwchem.md)


    * [Subpackages](custodian.nwchem.md#subpackages)


        * [custodian.nwchem.tests package](custodian.nwchem.tests.md)




            * [custodian.nwchem.tests.test_handlers module](custodian.nwchem.tests.test_handlers.md)




        * [custodian.nwchem.handlers module](custodian.nwchem.handlers.md)


            * [`NwchemErrorHandler`](custodian.nwchem.handlers.md#custodian.nwchem.handlers.NwchemErrorHandler)


                * [`NwchemErrorHandler.check()`](custodian.nwchem.handlers.md#custodian.nwchem.handlers.NwchemErrorHandler.check)


                * [`NwchemErrorHandler.correct()`](custodian.nwchem.handlers.md#custodian.nwchem.handlers.NwchemErrorHandler.correct)


        * [custodian.nwchem.jobs module](custodian.nwchem.jobs.md)


            * [`NwchemJob`](custodian.nwchem.jobs.md#custodian.nwchem.jobs.NwchemJob)


                * [`NwchemJob.postprocess()`](custodian.nwchem.jobs.md#custodian.nwchem.jobs.NwchemJob.postprocess)


                * [`NwchemJob.run()`](custodian.nwchem.jobs.md#custodian.nwchem.jobs.NwchemJob.run)


                * [`NwchemJob.setup()`](custodian.nwchem.jobs.md#custodian.nwchem.jobs.NwchemJob.setup)


* [custodian.qchem package](custodian.qchem.md)


    * [Subpackages](custodian.qchem.md#subpackages)


        * [custodian.qchem.tests package](custodian.qchem.tests.md)




            * [custodian.qchem.tests.test_handlers module](custodian.qchem.tests.test_handlers.md)


            * [custodian.qchem.tests.test_job_handler_interaction module](custodian.qchem.tests.test_job_handler_interaction.md)


            * [custodian.qchem.tests.test_jobs module](custodian.qchem.tests.test_jobs.md)




        * [custodian.qchem.handlers module](custodian.qchem.handlers.md)


        * [custodian.qchem.jobs module](custodian.qchem.jobs.md)


        * [custodian.qchem.utils module](custodian.qchem.utils.md)


            * [`perturb_coordinates()`](custodian.qchem.utils.md#custodian.qchem.utils.perturb_coordinates)


            * [`vector_list_diff()`](custodian.qchem.utils.md#custodian.qchem.utils.vector_list_diff)


* [custodian.vasp package](custodian.vasp.md)


    * [Subpackages](custodian.vasp.md#subpackages)


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




* [custodian.custodian module](custodian.custodian.md)


    * [`Custodian`](custodian.custodian.md#custodian.custodian.Custodian)


        * [`Custodian.LOG_FILE`](custodian.custodian.md#custodian.custodian.Custodian.LOG_FILE)


        * [`Custodian.from_spec()`](custodian.custodian.md#custodian.custodian.Custodian.from_spec)


        * [`Custodian.run()`](custodian.custodian.md#custodian.custodian.Custodian.run)


        * [`Custodian.run_interrupted()`](custodian.custodian.md#custodian.custodian.Custodian.run_interrupted)


    * [`CustodianError`](custodian.custodian.md#custodian.custodian.CustodianError)


    * [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)


        * [`ErrorHandler.check()`](custodian.custodian.md#custodian.custodian.ErrorHandler.check)


        * [`ErrorHandler.correct()`](custodian.custodian.md#custodian.custodian.ErrorHandler.correct)


        * [`ErrorHandler.is_monitor`](custodian.custodian.md#custodian.custodian.ErrorHandler.is_monitor)


        * [`ErrorHandler.is_terminating`](custodian.custodian.md#custodian.custodian.ErrorHandler.is_terminating)


        * [`ErrorHandler.max_num_corrections`](custodian.custodian.md#custodian.custodian.ErrorHandler.max_num_corrections)


        * [`ErrorHandler.n_applied_corrections`](custodian.custodian.md#custodian.custodian.ErrorHandler.n_applied_corrections)


        * [`ErrorHandler.raise_on_max`](custodian.custodian.md#custodian.custodian.ErrorHandler.raise_on_max)


        * [`ErrorHandler.raises_runtime_error`](custodian.custodian.md#custodian.custodian.ErrorHandler.raises_runtime_error)


    * [`Job`](custodian.custodian.md#custodian.custodian.Job)


        * [`Job.name`](custodian.custodian.md#custodian.custodian.Job.name)


        * [`Job.postprocess()`](custodian.custodian.md#custodian.custodian.Job.postprocess)


        * [`Job.run()`](custodian.custodian.md#custodian.custodian.Job.run)


        * [`Job.setup()`](custodian.custodian.md#custodian.custodian.Job.setup)


        * [`Job.terminate()`](custodian.custodian.md#custodian.custodian.Job.terminate)


    * [`MaxCorrectionsError`](custodian.custodian.md#custodian.custodian.MaxCorrectionsError)


    * [`MaxCorrectionsPerHandlerError`](custodian.custodian.md#custodian.custodian.MaxCorrectionsPerHandlerError)


    * [`MaxCorrectionsPerJobError`](custodian.custodian.md#custodian.custodian.MaxCorrectionsPerJobError)


    * [`NonRecoverableError`](custodian.custodian.md#custodian.custodian.NonRecoverableError)


    * [`ReturnCodeError`](custodian.custodian.md#custodian.custodian.ReturnCodeError)


    * [`ValidationError`](custodian.custodian.md#custodian.custodian.ValidationError)


    * [`Validator`](custodian.custodian.md#custodian.custodian.Validator)


        * [`Validator.check()`](custodian.custodian.md#custodian.custodian.Validator.check)


* [custodian.utils module](custodian.utils.md)


    * [`backup()`](custodian.utils.md#custodian.utils.backup)


    * [`get_execution_host_info()`](custodian.utils.md#custodian.utils.get_execution_host_info)
