# coding: utf-8

from __future__ import unicode_literals

from custodian.ansible.actions import FileActions, DictActions
from custodian.ansible.interpreter import Modder
from pymatgen.io.feff.sets import FEFFDictSet
import six
import os


class FeffModder(Modder):
    def __init__(self, actions=None, strict=True, feffinp=None):
        """
        Initializes a Modder for FeffInput sets

        Args:
            actions ([Action]): A sequence of supported actions. See
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
        self.feffinp = feffinp or FEFFDictSet.from_directory('.')
        self.feffinp = self.feffinp.all_input()
        actions = actions or [FileActions, DictActions]
        super(FeffModder, self).__init__(actions, strict)

    def apply_actions(self, actions):
        """
        Applies a list of actions to the FEFF Input Set and rewrites modified
        files.
        Args:
            actions [dict]: A list of actions of the form {'file': filename,
                'action': moddermodification} or {'dict': feffinput_key,
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
        if modified:
            feff = self.feffinp
            feff_input = "\n\n".join(str(feff[k]) for k in
                                     ["HEADER", "PARAMETERS", "POTENTIALS", "ATOMS"]
                                     if k in feff)
            for k, v in six.iteritems(feff):
                with open(os.path.join('.', k), "w") as f:
                    f.write(str(v))

            with open(os.path.join('.', "feff.inp"), "w") as f:
                f.write(feff_input)
