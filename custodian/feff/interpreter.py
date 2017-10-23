# coding: utf-8

from __future__ import unicode_literals

from custodian.ansible.actions import FileActions, DictActions
from custodian.ansible.interpreter import Modder
from pymatgen.io.feff.sets import FEFFDirectoryInput


class FeffModder(Modder):
    def __init__(self, actions=None, strict=True, feffinp=None):
        """
        Initializes a Modder for VaspInput sets

        Args:
            actions ([Action]): A sequence of supported actions. See
                :mod:`custodian.ansible.actions`. Default is None,
                which means DictActions and FileActions are supported.
            strict (bool): Indicating whether to use strict mode. In non-strict
                mode, unsupported actions are simply ignored without any
                errors raised. In strict mode, if an unsupported action is
                supplied, a ValueError is raised. Defaults to True.
            feffinp (FEFFInput): A FeffInput object from the current directory.
                Initialized automatically if not passed (but passing it will
                avoid having to reparse the directory).
        """
        self.feffinp = feffinp or FEFFDirectoryInput.from_directory('.')
        actions = actions or [FileActions, DictActions]
        super(FeffModder, self).__init__(actions, strict)

    def apply_actions(self, actions):
        """
        Applies a list of actions to the Vasp Input Set and rewrites modified
        files.
        Args:
            actions [dict]: A list of actions of the form {'file': filename,
                'action': moddermodification} or {'dict': vaspinput_key,
                'action': moddermodification}
        """
        modified = []
        for a in actions:
            if "dict" in a:
                k = a["dict"]
                modified.append(k)
                self.feffinp[k] = self.modify_object(a["action"], self.feffinp[k])
            elif "file" in a:
                self.modify(a["action"], a["file"])
            else:
                raise ValueError("Unrecognized format: {}".format(a))
        for f in modified:
            self.feffinp[f].write_file(f)