---
layout: default
title: custodian.vasp.interpreter.md
nav_exclude: true
---

# custodian.vasp.interpreter module

Implements various interpreters and modders for VASP.

## *class* custodian.vasp.interpreter.VaspModder(actions=None, strict=True, vi=None)

Bases: [`Modder`](custodian.ansible.interpreter.md#custodian.ansible.interpreter.Modder)

A Modder for VaspInputSets.

Initializes a Modder for VaspInput sets

* **Parameters**
  * **actions** (  *[**Action**]*) – A sequence of supported actions. See
    [`custodian.ansible.actions`](custodian.ansible.actions.md#module-custodian.ansible.actions). Default is None,
    which means DictActions and FileActions are supported.
  * **strict** (*bool*) – Indicating whether to use strict mode. In non-strict
    mode, unsupported actions are simply ignored without any
    errors raised. In strict mode, if an unsupported action is
    supplied, a ValueError is raised. Defaults to True.
  * **vi** (*VaspInput*) – A VaspInput object from the current directory.
    Initialized automatically if not passed (but passing it will
    avoid having to reparse the directory).

### apply_actions(actions)

Applies a list of actions to the Vasp Input Set and rewrites modified
files.
:param actions [dict]: A list of actions of the form {‘file’: filename,

> ‘action’: moddermodification} or {‘dict’: vaspinput_key,
> ‘action’: moddermodification}