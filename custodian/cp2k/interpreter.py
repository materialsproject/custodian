"""
CP2K adapted interpreter and modder for custodian.
"""

from custodian.ansible.actions import FileActions, DictActions
from custodian.ansible.interpreter import Modder
from pymatgen.io.cp2k.inputs import Cp2kInput


class Cp2kModder(Modder):

    def __init__(self, filename='cp2k.inp', actions=None, strict=True, ci=None):
        """
        Initializes a Modder for Cp2kInput sets

        Args:
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
        self.ci = ci or Cp2kInput.from_file(filename)
        self.filename = filename
        actions = actions or [FileActions, DictActions]
        super(Cp2kModder, self).__init__(actions, strict)

    def apply_actions(self, actions):
        """
        Applies a list of actions to the CP2K Input Set and rewrites modified
        files.
        Args:
            actions [dict]: A list of actions of the form {'file': filename,
                'action': moddermodification} or {'dict': cp2k_key,
                'action': moddermodification}
        """
        modified = []
        for a in actions:
            if "dict" in a:
                k = a["dict"]
                modified.append(k)
                self._modify(a['action'], self.ci)
            elif "file" in a:
                self.modify(a["action"], a["file"])
                self.ci = Cp2kInput.from_file(self.filename)
            else:
                raise ValueError("Unrecognized format: {}".format(a))
        self.ci.write_file(self.filename)

    def _modify(self, modification, obj):
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
        for action, settings in modification.items():
            getattr(obj, action[1:])(settings)







