---
layout: default
title: custodian.ansible.actions.md
nav_exclude: true
---

# custodian.ansible.actions module

This module defines various classes of supported actions. All actions are
implemented as static methods, but are defined using classes (as opposed to
modules) so that a set of well-defined actions can be namespaced easily.

## *class* custodian.ansible.actions.DictActions()

Bases: `object`

Class to implement the supported mongo-like modifications on a dict.
Supported keywords include the following Mongo-based keywords, with the
usual meanings (refer to Mongo documentation for information):

> \_inc
> \_set
> \_unset
> \_push
> \_push_all
> \_add_to_set (but \_each is not supported)
> \_pop
> \_pull
> \_pull_all
> \_rename

However, note that “_set” does not support modification of nested dicts
using the mongo {“a.b”:1} notation. This is because mongo does not allow
keys with “.” to be inserted. Instead, nested dict modification is
supported using a special “->” keyword, e.g. {“a->b”: 1}

### *static* add_to_set(input_dict, settings)

Add to set using MongoDB syntax.

* **Parameters**
  * **input_dict** (*dict*) – The input dictionary to be modified.
  * **settings** (*dict*) – The specification of the modification to be made.

### *static* inc(input_dict, settings)

Increment a value using MongdoDB syntax.

* **Parameters**
  * **input_dict** (*dict*) – The input dictionary to be modified.
  * **settings** (*dict*) – The specification of the modification to be made.

### *static* pop(input_dict, settings)

Pop item from a list using MongoDB syntax.

* **Parameters**
  * **input_dict** (*dict*) – The input dictionary to be modified.
  * **settings** (*dict*) – The specification of the modification to be made.

### *static* pull(input_dict, settings)

Pull an item using MongoDB syntax.

* **Parameters**
  * **input_dict** (*dict*) – The input dictionary to be modified.
  * **settings** (*dict*) – The specification of the modification to be made.

### *static* pull_all(input_dict, settings)

Pull multiple items to a list using MongoDB syntax.

* **Parameters**
  * **input_dict** (*dict*) – The input dictionary to be modified.
  * **settings** (*dict*) – The specification of the modification to be made.

### *static* push(input_dict, settings)

Push to a list using MongoDB syntax.

* **Parameters**
  * **input_dict** (*dict*) – The input dictionary to be modified.
  * **settings** (*dict*) – The specification of the modification to be made.

### *static* push_all(input_dict, settings)

Push multiple items to a list using MongoDB syntax.

* **Parameters**
  * **input_dict** (*dict*) – The input dictionary to be modified.
  * **settings** (*dict*) – The specification of the modification to be made.

### *static* rename(input_dict, settings)

Rename a key using MongoDB syntax.

* **Parameters**
  * **input_dict** (*dict*) – The input dictionary to be modified.
  * **settings** (*dict*) – The specification of the modification to be made.

### *static* set(input_dict, settings)

Sets a value using MongoDB syntax.

* **Parameters**
  * **input_dict** (*dict*) – The input dictionary to be modified.
  * **settings** (*dict*) – The specification of the modification to be made.

### *static* unset(input_dict, settings)

Unsets a value using MongoDB syntax.

* **Parameters**
  * **input_dict** (*dict*) – The input dictionary to be modified.
  * **settings** (*dict*) – The specification of the modification to be made.

## *class* custodian.ansible.actions.FileActions()

Bases: `object`

Class of supported file actions. For FileActions, the modder class takes in
a filename as a string. The filename should preferably be a full path to
avoid ambiguity.

### *static* file_copy(filename, settings)

Copies a file. {‘_file_copy’: {‘dest’: ‘new_file_name’}}

* **Parameters**
  * **filename** (*str*) – Filename.
  * **settings** (*dict*) – Must be {“dest”: path of new file}

### *static* file_create(filename, settings)

Creates a file.

* **Parameters**
  * **filename** (*str*) – Filename.
  * **settings** (*dict*) – Must be {“content”: actual_content}

### *static* file_delete(filename, settings)

Deletes a file. {‘_file_delete’: {‘mode’: “actual”}}

* **Parameters**
  * **filename** (*str*) – Filename.
  * **settings** (*dict*) – Must be {“mode”: actual/simulated}. Simulated
    mode only prints the action without performing it.

### *static* file_modify(filename, settings)

Modifies file access

* **Parameters**
  * **filename** (*str*) – Filename.
  * **settings** (*dict*) – Can be “mode” or “owners”

### *static* file_move(filename, settings)

Moves a file. {‘_file_move’: {‘dest’: ‘new_file_name’}}

* **Parameters**
  * **filename** (*str*) – Filename.
  * **settings** (*dict*) – Must be {“dest”: path of new file}

## custodian.ansible.actions.get_nested_dict(input_dict, key)

Helper function to interpret a nested dict input.