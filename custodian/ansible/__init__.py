from __future__ import unicode_literals

"""
The ansible package provides modules that provides a mongo-like syntax for
making modifications to dicts, objects and files. The mongo-like syntax
itself is a dict.

The main use of this package is to allow changes to objects or files to be
stored in a json file or MongoDB database, i.e., a form of version control
or tracked changes (though without undo capability unless the input is
stored at each step).
"""

__author__ = "Shyue Ping Ong"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "ongsp@ucsd.edu"
__status__ = "Production"
__date__ = "Feb 1 2013"


from .interpreter import Modder
from .actions import FileActions, DictActions
