"""CP2K adapted interpreter and modder for custodian."""

import os

from pymatgen.io.cp2k.inputs import Cp2kInput

from custodian.ansible.actions import DictActions, FileActions
from custodian.ansible.interpreter import Modder
from custodian.cp2k.utils import cleanup_input

__author__ = "Nicholas Winner"
__version__ = "1.0"
__email__ = "nwinner@berkeley.edu"
__date__ = "October 2021"


class Cp2kModder(Modder):
    """
    Cp2kModder is a lightweight class for applying modifications to cp2k input files. It
    also supports modifications that are file operations (e.g. copying).
    """

    def __init__(self, filename="cp2k.inp", actions=None, strict=True, ci=None, directory="./"):
        """Initialize a Modder for Cp2kInput sets.

        Args:
            filename (str): name of cp2k input file to modify. This file will be overwritten
                if actions are applied.
            actions ([Action]): A sequence of supported actions. See
                :mod:`custodian.ansible.actions`. Default is None,
                which means DictActions and FileActions are supported.
            strict (bool): Indicating whether to use strict mode. In non-strict
                mode, unsupported actions are simply ignored without any
                errors raised. In strict mode, if an unsupported action is
                supplied, a ValueError is raised. Defaults to True.
            ci (Cp2kInput): A Cp2kInput object from the current directory.
                Initialized automatically if not passed (but passing it will
                avoid having to reparse the directory).
        """
        self.directory = directory
        self.ci = ci or Cp2kInput.from_file(os.path.join(self.directory, filename))
        self.filename = filename
        actions = actions or [FileActions, DictActions]
        super().__init__(actions, strict)

    def apply_actions(self, actions):
        """
        Applies a list of actions to the CP2K Input Set and rewrites modified
        files.

        Args:
            actions (dict): A list of actions of the form {'file': filename,
                'action': moddermodification} or {'dict': cp2k_key,
                'action': moddermodification}.
        """
        modified = []
        for action in actions:
            if "dict" in action:
                k = action["dict"]
                modified.append(k)
                Cp2kModder._modify(action["action"], self.ci)
            elif "file" in action:
                self.modify(action["action"], action["file"])
                self.ci = Cp2kInput.from_file(os.path.join(self.directory, self.filename))
            else:
                raise ValueError(f"Unrecognized format: {action}")
        cleanup_input(self.ci)
        self.ci.write_file(os.path.join(self.directory, self.filename))

    @staticmethod
    def _modify(modification, obj):
        """
        Note that modify makes actual in-place modifications. It does not
        return a copy.

        Args:
            modification (dict): Modification must be {action_keyword :
                settings}. E.g., {'_set': {'Hello':'Universe', 'Bye': 'World'}}
            obj (dict/str/object): Object to modify depending on actions. For
                example, for DictActions, obj will be a dict to be modified.
                For FileActions, obj will be a string with a full pathname to a
                file.
        """
        modification = list(modification.items()) if isinstance(modification, dict) else modification
        for action, settings in modification:
            try:
                getattr(obj, action[1:])(settings)
            except KeyError:
                continue
