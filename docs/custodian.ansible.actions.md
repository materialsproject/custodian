---
layout: default
title: custodian.ansible.actions.md
nav_exclude: true
---

# custodian.ansible.actions module

This module defines various classes of supported actions. All actions are
implemented as static methods, but are defined using classes (as opposed to
modules) so that a set of well-defined actions can be namespaced easily.


### _class_ custodian.ansible.actions.DictActions()
Bases: `object`

Class to implement the supported mongo-like modifications on a dict.
Supported keywords include the following Mongo-based keywords, with the
usual meanings (refer to Mongo documentation for information):

> _inc
> _set
> _unset
> _push
> _push_all
> _add_to_set (but _each is not supported)
> _pop
> _pull
> _pull_all
> _rename

However, note that “_set” does not support modification of nested dicts
using the mongo {“a.b”:1} notation. This is because mongo does not allow
keys with “.” to be inserted. Instead, nested dict modification is
supported using a special “->” keyword, e.g. {“a->b”: 1}


#### _static_ add_to_set(input_dict, settings)
Add to set using MongoDB syntax.


* **Parameters**


    * **input_dict** (*dict*) – The input dictionary to be modified.


    * **settings** (*dict*) – The specification of the modification to be made.



#### _static_ inc(input_dict, settings)
Increment a value using MongdoDB syntax.


* **Parameters**


    * **input_dict** (*dict*) – The input dictionary to be modified.


    * **settings** (*dict*) – The specification of the modification to be made.



#### _static_ pop(input_dict, settings)
Pop item from a list using MongoDB syntax.


* **Parameters**


    * **input_dict** (*dict*) – The input dictionary to be modified.


    * **settings** (*dict*) – The specification of the modification to be made.



#### _static_ pull(input_dict, settings)
Pull an item using MongoDB syntax.


* **Parameters**


    * **input_dict** (*dict*) – The input dictionary to be modified.


    * **settings** (*dict*) – The specification of the modification to be made.



#### _static_ pull_all(input_dict, settings)
Pull multiple items to a list using MongoDB syntax.


* **Parameters**


    * **input_dict** (*dict*) – The input dictionary to be modified.


    * **settings** (*dict*) – The specification of the modification to be made.



#### _static_ push(input_dict, settings)
Push to a list using MongoDB syntax.


* **Parameters**


    * **input_dict** (*dict*) – The input dictionary to be modified.


    * **settings** (*dict*) – The specification of the modification to be made.



#### _static_ push_all(input_dict, settings)
Push multiple items to a list using MongoDB syntax.


* **Parameters**


    * **input_dict** (*dict*) – The input dictionary to be modified.


    * **settings** (*dict*) – The specification of the modification to be made.



#### _static_ rename(input_dict, settings)
Rename a key using MongoDB syntax.


* **Parameters**


    * **input_dict** (*dict*) – The input dictionary to be modified.


    * **settings** (*dict*) – The specification of the modification to be made.



#### _static_ set(input_dict, settings)
Sets a value using MongoDB syntax.


* **Parameters**


    * **input_dict** (*dict*) – The input dictionary to be modified.


    * **settings** (*dict*) – The specification of the modification to be made.



#### _static_ unset(input_dict, settings)
Unsets a value using MongoDB syntax.


* **Parameters**


    * **input_dict** (*dict*) – The input dictionary to be modified.


    * **settings** (*dict*) – The specification of the modification to be made.



### _class_ custodian.ansible.actions.FileActions()
Bases: `object`

Class of supported file actions. For FileActions, the modder class takes in
a filename as a string. The filename should preferably be a full path to
avoid ambiguity.


#### _static_ file_copy(filename, settings)
Copies a file. {‘_file_copy’: {‘dest’: ‘new_file_name’}}


* **Parameters**


    * **filename** (*str*) – Filename.


    * **settings** (*dict*) – Must be {“dest”: path of new file}



#### _static_ file_create(filename, settings)
Creates a file.


* **Parameters**


    * **filename** (*str*) – Filename.


    * **settings** (*dict*) – Must be {“content”: actual_content}



#### _static_ file_delete(filename, settings)
Deletes a file. {‘_file_delete’: {‘mode’: “actual”}}


* **Parameters**


    * **filename** (*str*) – Filename.


    * **settings** (*dict*) – Must be {“mode”: actual/simulated}. Simulated
    mode only prints the action without performing it.



#### _static_ file_modify(filename, settings)
Modifies file access


* **Parameters**


    * **filename** (*str*) – Filename.


    * **settings** (*dict*) – Can be “mode” or “owners”



#### _static_ file_move(filename, settings)
Moves a file. {‘_file_move’: {‘dest’: ‘new_file_name’}}


* **Parameters**


    * **filename** (*str*) – Filename.


    * **settings** (*dict*) – Must be {“dest”: path of new file}



### custodian.ansible.actions.get_nested_dict(input_dict, key)
Helper function to interpret a nested dict input.