"""
This module defines various classes of supported actions. All actions are
implemented as static methods, but are defined using classes (as opposed to
modules) so that a set of well-defined actions can be namespaced easily.
"""

import os
import shutil


def get_nested_dict(input_dict, key):
    """Helper function to interpret a nested dict input."""
    current = input_dict
    toks = key.split("->")
    n = len(toks)
    for i, tok in enumerate(toks):
        if tok not in current and i < n - 1:
            current[tok] = {}
        elif i == n - 1:
            return current, toks[-1]
        current = current[tok]
    return None


class DictActions:
    """Class to implement the supported mongo-like modifications on a dict.

    Supported keywords include the following Mongo-based keywords, with the
    usual meanings (refer to Mongo documentation for information):

        _inc
        _set
        _unset
        _push
        _push_all
        _add_to_set (but _each is not supported)
        _pop
        _pull
        _pull_all
        _rename

    However, note that "_set" does not support modification of nested dicts
    using the mongo {"a.b":1} notation. This is because mongo does not allow
    keys with "." to be inserted. Instead, nested dict modification is
    supported using a special "->" keyword, e.g. {"a->b": 1}
    """

    @staticmethod
    def set(input_dict, settings, directory=None):
        """
        Sets a value using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for k, v in settings.items():
            (d, key) = get_nested_dict(input_dict, k)
            d[key] = v

    @staticmethod
    def unset(input_dict, settings, directory=None):
        """
        Unset a value using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for key in settings:
            dct, inner_key = get_nested_dict(input_dict, key)
            del dct[inner_key]

    @staticmethod
    def push(input_dict, settings, directory=None):
        """
        Push to a list using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for k, v in settings.items():
            (d, key) = get_nested_dict(input_dict, k)
            if key in d:
                d[key].append(v)
            else:
                d[key] = [v]

    @staticmethod
    def push_all(input_dict, settings, directory=None):
        """
        Push multiple items to a list using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for k1, val in settings.items():
            dct, k2 = get_nested_dict(input_dict, k1)
            if k2 in dct:
                dct[k2] += val
            else:
                dct[k2] = val

    @staticmethod
    def inc(input_dict, settings, directory=None):
        """
        Increment a value using MongdoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for k, v in settings.items():
            (d, key) = get_nested_dict(input_dict, k)
            if key in d:
                d[key] += v
            else:
                d[key] = v

    @staticmethod
    def rename(input_dict, settings, directory=None):
        """
        Rename a key using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for key, v in settings.items():
            if val := input_dict.pop(key, None):
                input_dict[v] = val

    @staticmethod
    def add_to_set(input_dict, settings, directory=None):
        """
        Add to set using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for k, v in settings.items():
            (d, key) = get_nested_dict(input_dict, k)
            if key in d and (not isinstance(d[key], list)):
                raise ValueError(f"Keyword {k} does not refer to an array.")
            if key in d and v not in d[key]:
                d[key].append(v)
            elif key not in d:
                d[key] = v

    @staticmethod
    def pull(input_dict, settings, directory=None):
        """
        Pull an item using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for k1, val in settings.items():
            dct, k2 = get_nested_dict(input_dict, k1)
            if k2 in dct and (not isinstance(dct[k2], list)):
                raise ValueError(f"Keyword {k1} does not refer to an array.")
            if k2 in dct:
                dct[k2] = [itm for itm in dct[k2] if itm != val]

    @staticmethod
    def pull_all(input_dict, settings, directory=None):
        """
        Pull multiple items to a list using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for key, val in settings.items():
            if key in input_dict and (not isinstance(input_dict[key], list)):
                raise ValueError(f"Keyword {key} does not refer to an array.")
            for itm in val:
                DictActions.pull(input_dict, {key: itm})

    @staticmethod
    def pop(input_dict, settings, directory=None):
        """
        Pop item from a list using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for k, v in settings.items():
            (d, key) = get_nested_dict(input_dict, k)
            if key in d and (not isinstance(d[key], list)):
                raise ValueError(f"Keyword {k} does not refer to an array.")
            if v == 1:
                d[key].pop()
            elif v == -1:
                d[key].pop(0)


class FileActions:
    """
    Class of supported file actions. For FileActions, the modder class takes in
    a filename as a string. The filename should preferably be a full path to
    avoid ambiguity.
    """

    @staticmethod
    def file_create(filename, settings, directory):
        """
        Creates a file.

        Args:
            filename (str): Filename.
            settings (dict): Must be {"content": actual_content}
            directory (str): Directory to create file in
        """
        if len(settings) != 1:
            raise ValueError("Settings must only contain one item with key 'content'.")
        for k, v in settings.items():
            if k == "content":
                with open(filename, "w") as file:
                    file.write(v)

    @staticmethod
    def file_move(filename, settings, directory):
        """
        Moves a file. {'_file_move': {'dest': 'new_file_name'}}.

        Args:
            filename (str): Filename.
            settings (dict): Must be {"dest": path of new file}
            directory (str): Directory to move file from and to
        """
        if len(settings) != 1:
            raise ValueError("Settings must only contain one item with key 'dest'.")
        for k, v in settings.items():
            if k == "dest":
                shutil.move(os.path.join(directory, filename), os.path.join(directory, v))

    @staticmethod
    def file_delete(filename, settings, directory):
        """
        Deletes a file. {'_file_delete': {'mode': "actual"}}.

        Args:
            filename (str): Filename.
            settings (dict): Must be {"mode": actual/simulated}. Simulated
                mode only prints the action without performing it.
            directory (str): Directory to delete file in
        """
        if len(settings) != 1:
            raise ValueError("Settings must only contain one item with key 'mode'.")
        for k, v in settings.items():
            if k == "mode" and v == "actual":
                try:
                    os.remove(os.path.join(directory, filename))
                except OSError:
                    # Skip file not found error.
                    pass
            elif k == "mode" and v == "simulated":
                print(f"Simulated removal of {filename}")

    @staticmethod
    def file_copy(filename, settings, directory):
        """
        Copies a file. {'_file_copy': {'dest': 'new_file_name'}}.

        Args:
            filename (str): Filename.
            settings (dict): Must be {"dest": path of new file}
            directory (str): Directory to copy file to/from
        """
        for k, v in settings.items():
            if k.startswith("dest"):
                shutil.copyfile(os.path.join(directory, filename), os.path.join(directory, v))

    @staticmethod
    def file_modify(filename, settings, directory):
        """
        Modifies file access.

        Args:
            filename (str): Filename.
            settings (dict): Can be "mode" or "owners"
            directory (str): Directory to modify file in
        """
        for k, v in settings.items():
            if k == "mode":
                os.chmod(os.path.join(directory, filename), v)
            if k == "owners":
                os.chown(os.path.join(directory, filename), v)
