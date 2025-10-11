---
layout: default
title: custodian.feff.interpreter.md
nav_exclude: true
---

# custodian.feff.interpreter module

Implements various interpreters and modders for FEFF calculations.

## *class* custodian.feff.interpreter.FeffModder(actions=None, strict=True, feffinp=None)

Bases: [`Modder`](custodian.ansible.interpreter.md#custodian.ansible.interpreter.Modder)

A Modder for FeffInput sets

* **Parameters**
  * **actions** (    *[**Action**]*) – A sequence of supported actions. See
  * **actions** – A sequence of supported actions. See
    [`custodian.ansible.actions`](custodian.ansible.actions.md#module-custodian.ansible.actions). Default is None,
    which means DictActions and FileActions are supported.
  * **strict** (*bool*) – Indicating whether to use strict mode. In non-strict
    mode, unsupported actions are simply ignored without any
    errors raised. In strict mode, if an unsupported action is
    supplied, a ValueError is raised. Defaults to True.
  * **feffinp** (*FEFFInput*) – A FeffInput object from the current directory.
    Initialized automatically if not passed (but passing it will
    avoid having to reparse the directory).

### apply_actions(actions)

Applies a list of actions to the FEFF Input Set and rewrites modified
files.

* **Parameters**

  **[****dict****]** (*actions*) – A list of actions of the form {‘file’: filename,
  ‘action’: moddermodification} or {‘dict’: feffinput_key,
  ‘action’: moddermodification}