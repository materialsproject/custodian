"""
The ansible package provides modules that provides a mongo-like syntax for
making modifications to dicts, objects and files. The mongo-like syntax
itself is a dict.

The main use of this package is to allow changes to objects or files to be
stored in a json file or MongoDB database, i.e., a form of version control
or tracked changes (though without undo capability unless the input is
stored at each step).
"""

from .actions import DictActions, FileActions
from .interpreter import Modder
