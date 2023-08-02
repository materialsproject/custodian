---
layout: default
title: custodian.ansible.md
nav_exclude: true
---

# custodian.ansible package

The ansible package provides modules that provides a mongo-like syntax for
making modifications to dicts, objects and files. The mongo-like syntax
itself is a dict.

The main use of this package is to allow changes to objects or files to be
stored in a json file or MongoDB database, i.e., a form of version control
or tracked changes (though without undo capability unless the input is
stored at each step).

## Subpackages


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