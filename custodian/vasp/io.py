"""Helper functions for dealing with vasp files."""

from pymatgen.io.vasp.outputs import Outcar, Vasprun

from custodian.utils import tracked_lru_cache


@tracked_lru_cache
def load_vasprun(filepath, **vasprun_kwargs):
    """
    Load Vasprun object from file path.
    Caches the output for reuse.

    Args:
        filepath: path to the vasprun.xml file.
        **vasprun_kwargs: kwargs arguments passed to the Vasprun init.

    Returns:
        The Vasprun object
    """
    return Vasprun(filepath, **vasprun_kwargs)


@tracked_lru_cache
def load_outcar(filepath):
    """
    Load Outcar object from file path.
    Caches the output for reuse.

    Args:
        filepath: path to the OUTCAR file.

    Returns:
        The Vasprun object
    """
    return Outcar(filepath)
