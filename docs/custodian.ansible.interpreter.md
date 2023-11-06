---
layout: default
title: custodian.ansible.interpreter.md
nav_exclude: true
---

# custodian.ansible.interpreter module

This module implements a Modder class that performs modifications on objects
using support actions.

## *class* custodian.ansible.interpreter.Modder(actions=None, strict=True)

Bases: `object`

Class to modify a dict/file/any object using a mongo-like language.
Keywords are mostly adopted from mongo’s syntax, but instead of $, an
underscore precedes action keywords. This is so that the modification can
be inserted into a mongo db easily.

Allowable actions are supplied as a list of classes as an argument. Refer
to the action classes on what the actions do. Action classes are in
pymatpro.ansible.actions.

Examples:

> > > modder = Modder()
> > > d = {“Hello”: “World”}
> > > mod = {‘_set’: {‘Hello’:’Universe’, ‘Bye’: ‘World’}}
> > > modder.modify(mod, d)
> > > d[‘Bye’]
> > > ‘World’
> > > d[‘Hello’]
> > > ‘Universe’

Initializes a Modder from a list of supported actions.

* **Parameters**
  * **actions** (*[**Action**]*) – A sequence of supported actions. See
    [`custodian.ansible.actions`](custodian.ansible.actions.md#module-custodian.ansible.actions). Default is None,
    which means only DictActions are supported.
  * **strict** (*bool*) – Indicating whether to use strict mode. In non-strict
    mode, unsupported actions are simply ignored without any
    errors raised. In strict mode, if an unsupported action is
    supplied, a ValueError is raised. Defaults to True.

### modify(modification, obj)

Note that modify makes actual in-place modifications. It does not
return a copy.

* **Parameters**
  * **modification** (*dict*) – Modification must be {action_keyword :
    settings}. E.g., {‘_set’: {‘Hello’:’Universe’, ‘Bye’: ‘World’}}
  * **obj** (*dict/str/object*) – Object to modify depending on actions. For
    example, for DictActions, obj will be a dict to be modified.
    For FileActions, obj will be a string with a full pathname to a
    file.

### modify_object(modification, obj)

Modify an object that supports pymatgen’s as_dict() and from_dict API.

* **Parameters**
  * **modification** (*dict*) – Modification must be {action_keyword :
    settings}. E.g., {‘_set’: {‘Hello’:’Universe’, ‘Bye’: ‘World’}}
  * **obj** (*object*) – Object to modify