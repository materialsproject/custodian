---
layout: default
title: custodian.cp2k.interpreter.md
nav_exclude: true
---

# custodian.cp2k.interpreter module

CP2K adapted interpreter and modder for custodian.

## *class* custodian.cp2k.interpreter.Cp2kModder(filename=’cp2k.inp’, actions=None, strict=True, ci=None)

Bases: [`Modder`](custodian.ansible.interpreter.md#custodian.ansible.interpreter.Modder)

Cp2kModder is a lightweight class for applying modifications to cp2k input files. It
also supports modifications that are file operations (e.g. copying).

Initializes a Modder for Cp2kInput sets

* **Parameters**
  * **filename** (*str*) – name of cp2k input file to modify. This file will be overwritten
    if actions are applied.
  * **actions** (  *[**Action**]*) – A sequence of supported actions. See
    [`custodian.ansible.actions`](custodian.ansible.actions.md#module-custodian.ansible.actions). Default is None,
    which means DictActions and FileActions are supported.
  * **strict** (*bool*) – Indicating whether to use strict mode. In non-strict
    mode, unsupported actions are simply ignored without any
    errors raised. In strict mode, if an unsupported action is
    supplied, a ValueError is raised. Defaults to True.
  * **ci** (*Cp2kInput*) – A Cp2kInput object from the current directory.
    Initialized automatically if not passed (but passing it will
    avoid having to reparse the directory).

### apply_actions(actions)

Applies a list of actions to the CP2K Input Set and rewrites modified
files.
:param actions [dict]: A list of actions of the form {‘file’: filename,

> ‘action’: moddermodification} or {‘dict’: cp2k_key,
> ‘action’: moddermodification}