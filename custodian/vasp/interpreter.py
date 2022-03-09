"""
Implements various interpreters and modders for VASP.
"""

from pymatgen.io.vasp.inputs import VaspInput

from custodian.ansible.actions import DictActions, FileActions
from custodian.ansible.interpreter import Modder


class VaspModder(Modder):
    """
    A Modder for VaspInputSets.
    """

    def __init__(self, actions=None, strict=True, vi=None):
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
            vi (VaspInput): A VaspInput object from the current directory.
                Initialized automatically if not passed (but passing it will
                avoid having to reparse the directory).
        """
        self.vi = vi or VaspInput.from_directory(".")
        actions = actions or [FileActions, DictActions]
        super().__init__(actions, strict)

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
                self.vi[k] = self.modify_object(a["action"], self.vi[k])
            elif "file" in a:
                self.modify(a["action"], a["file"])
            else:
                raise ValueError(f"Unrecognized format: {a}")
        for f in modified:
            self.vi[f].write_file(f)
