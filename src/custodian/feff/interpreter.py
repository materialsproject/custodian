"""Implements various interpreters and modders for FEFF calculations."""

import os

from pymatgen.io.feff.sets import FEFFDictSet

from custodian.ansible.actions import DictActions, FileActions
from custodian.ansible.interpreter import Modder


class FeffModder(Modder):
    """A Modder for FeffInput sets."""

    def __init__(self, actions=None, strict=True, feffinp=None, directory="./") -> None:
        """Initialize a FeffModder.

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
                avoid having to re-parse the directory).
            directory (str): The directory containing the FeffInput set. Defaults to "./".
        """
        self.directory = directory
        self.feffinp = feffinp or FEFFDictSet.from_directory(self.directory)
        self.feffinp = self.feffinp.all_input()
        actions = actions or [FileActions, DictActions]
        super().__init__(actions, strict, directory=directory)

    def apply_actions(self, actions) -> None:
        """
        Applies a list of actions to the FEFF Input Set and rewrites modified
        files.

        Args:
            actions (dict): A list of actions of the form {'file': filename,
                'action': moddermodification} or {'dict': feffinput_key,
                'action': moddermodification}
        """
        modified = []
        for action in actions:
            if "dict" in action:
                key = action["dict"]
                modified.append(key)
                self.feffinp[key] = self.modify_object(action["action"], self.feffinp[key])  # type:ignore[index]
            elif "file" in action:
                self.modify(action["action"], action["file"])
            else:
                raise ValueError(f"Unrecognized format: {action}")
        if modified:
            feff = self.feffinp
            feff_input = "\n\n".join(
                str(feff[key])  # type:ignore[index,operator]
                for key in ("HEADER", "PARAMETERS", "POTENTIALS", "ATOMS")
                if key in feff  # type:ignore[index,operator]
            )
            for key, val in feff.items():  # type:ignore[union-attr]
                with open(os.path.join(self.directory, key), "w") as file:
                    file.write(str(val))

            with open(os.path.join(self.directory, "feff.inp"), "w") as file:
                file.write(feff_input)
