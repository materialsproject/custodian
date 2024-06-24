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
    tokens = key.split("->")
    n = len(tokens)
    for i, tok in enumerate(tokens):
        if tok not in current and i < n - 1:
            current[tok] = {}
        elif i == n - 1:
            return current, tokens[-1]
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
    def set(input_dict, settings, directory=None) -> None:
        """
        Sets a value using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for key, val in settings.items():
            dct, sub_key = get_nested_dict(input_dict, key)
            dct[sub_key] = val

    @staticmethod
    def unset(input_dict, settings, directory=None) -> None:
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
    def push(input_dict, settings, directory=None) -> None:
        """
        Push to a list using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for key, val in settings.items():
            dct, sub_key = get_nested_dict(input_dict, key)
            if sub_key in dct:
                dct[sub_key].append(val)
            else:
                dct[sub_key] = [val]

    @staticmethod
    def push_all(input_dict, settings, directory=None) -> None:
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
    def inc(input_dict, settings, directory=None) -> None:
        """
        Increment a value using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for key, val in settings.items():
            dct, sub_key = get_nested_dict(input_dict, key)
            if sub_key in dct:
                dct[sub_key] += val
            else:
                dct[sub_key] = val

    @staticmethod
    def rename(input_dict, settings, directory=None) -> None:
        """
        Rename a key using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for key, val in settings.items():
            if input_val := input_dict.pop(key, None):
                input_dict[val] = input_val

    @staticmethod
    def add_to_set(input_dict, settings, directory=None) -> None:
        """
        Add to set using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for key, val in settings.items():
            dct, sub_key = get_nested_dict(input_dict, key)
            if sub_key in dct and (not isinstance(dct[sub_key], list)):
                raise ValueError(f"Keyword {key} does not refer to an array.")
            if sub_key in dct and val not in dct[sub_key]:
                dct[sub_key].append(val)
            elif sub_key not in dct:
                dct[sub_key] = val

    @staticmethod
    def pull(input_dict, settings, directory=None) -> None:
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
    def pull_all(input_dict, settings, directory=None) -> None:
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
    def pop(input_dict, settings, directory=None) -> None:
        """
        Pop item from a list using MongoDB syntax.

        Args:
            input_dict (dict): The input dictionary to be modified.
            settings (dict): The specification of the modification to be made.
            directory (None): dummy parameter for compatibility with FileActions
        """
        for key, val in settings.items():
            dct, sub_key = get_nested_dict(input_dict, key)
            if sub_key in dct and (not isinstance(dct[sub_key], list)):
                raise ValueError(f"Keyword {key} does not refer to an array.")
            if val == 1:
                dct[sub_key].pop()
            elif val == -1:
                dct[sub_key].pop(0)


class FileActions:
    """
    Class of supported file actions. For FileActions, the modder class takes in
    a filename as a string. The filename should preferably be a full path to
    avoid ambiguity.
    """

    @staticmethod
    def file_create(filename, settings, directory) -> None:
        """
        Creates a file.

        Args:
            filename (str): Filename.
            settings (dict): Must be {"content": actual_content}
            directory (str): Directory to create file in
        """
        if len(settings) != 1:
            raise ValueError("Settings must only contain one item with key 'content'.")
        for key, val in settings.items():
            if key == "content":
                with open(filename, "w") as file:
                    file.write(val)

    @staticmethod
    def file_move(filename, settings, directory) -> None:
        """
        Moves a file. {'_file_move': {'dest': 'new_file_name'}}.

        Args:
            filename (str): Filename.
            settings (dict): Must be {"dest": path of new file}
            directory (str): Directory to move file from and to
        """
        if len(settings) != 1:
            raise ValueError("Settings must only contain one item with key 'dest'.")
        for key, val in settings.items():
            if key == "dest":
                shutil.move(os.path.join(directory, filename), os.path.join(directory, val))

    @staticmethod
    def file_delete(filename, settings, directory) -> None:
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
        for key, val in settings.items():
            if key == "mode" and val == "actual":
                try:
                    os.remove(os.path.join(directory, filename))
                except OSError:
                    # Skip file not found error.
                    pass
            elif key == "mode" and val == "simulated":
                print(f"Simulated removal of {filename}")

    @staticmethod
    def file_copy(filename, settings, directory) -> None:
        """
        Copies a file. {'_file_copy': {'dest': 'new_file_name'}}.

        Args:
            filename (str): Filename.
            settings (dict): Must be {"dest": path of new file}
            directory (str): Directory to copy file to/from
        """
        for key, val in settings.items():
            if key.startswith("dest"):
                shutil.copyfile(os.path.join(directory, filename), os.path.join(directory, val))

    @staticmethod
    def file_modify(filename, settings, directory) -> None:
        """
        Modifies file access.

        Args:
            filename (str): Filename.
            settings (dict): Can be "mode" or "owners"
            directory (str): Directory to modify file in
        """
        for key, val in settings.items():
            if key == "mode":
                os.chmod(os.path.join(directory, filename), val)
            if key == "owners":
                # TODO fix this mypy error, missing 3rd positional argument to chown
                os.chown(os.path.join(directory, filename), val)  # type: ignore[call-arg]
