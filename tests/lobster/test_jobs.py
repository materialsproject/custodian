import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from monty.os import cd
from monty.tempfile import ScratchDir

from custodian.lobster.jobs import LOBSTEROUTPUT_FILES, LobsterJob
from tests.conftest import TEST_FILES

test_files_lobster2 = f"{TEST_FILES}/lobster/lobsterins"
test_files_lobster3 = f"{TEST_FILES}/lobster/vasp_lobster_output"
test_files_lobster4 = f"{TEST_FILES}/lobster/vasp_lobster_output_v51"

VASP_OUTPUT_FILES = (
    "OUTCAR",
    "vasprun.xml",
    "CHG",
    "CHGCAR",
    "CONTCAR",
    "INCAR",
    "KPOINTS",
    "POSCAR",
    "POTCAR",
    "DOSCAR",
    "EIGENVAL",
    "IBZKPT",
    "OSZICAR",
    "PCDAT",
    "PROCAR",
    "REPORT",
    "WAVECAR",
    "XDATCAR",
)

LOBSTERINPUT_FILES = ("lobsterin",)

LOBSTER_FILES = (
    "lobsterin",
    "lobsterin.orig",
    "lobsterout",
    "CHARGE.lobster",
    "COHPCAR.lobster",
    "COOPCAR.lobster",
    "DOSCAR.lobster",
    "GROSSPOP.lobster",
    "ICOHPLIST.lobster",
    "ICOOPLIST.lobster",
    "lobster.out",
    "projectionData.lobster",
    "MadelungEnergies.lobster",
    "SitePotentials.lobster",
    "bandOverlaps.lobster",
    "ICOBILIST.lobster",
    "COBICAR.lobster",
    "DOSCAR.LSO.lobster",
)

FW_FILES = ("custodian.json", "FW.json", "FW_submit.script")


class TestLobsterJob:
    """Similar to VaspJobTest. Omit test of run."""

    def test_as_from_dict(self) -> None:
        v = LobsterJob(lobster_cmd="hello")
        v2 = LobsterJob.from_dict(v.as_dict())
        assert isinstance(v2, LobsterJob)
        assert v2.lobster_cmd == "hello"

    def test_setup(self) -> None:
        with cd(test_files_lobster2):
            with ScratchDir(".", copy_from_current_on_enter=True):
                # check if backup is done correctly
                v = LobsterJob("hello", backup=True)
                v.setup()
                assert os.path.isfile("lobsterin.orig")
                # check if backup id done correctly
            with ScratchDir(".", copy_from_current_on_enter=True):
                v = LobsterJob("hello", backup=False)
                v.setup()
                assert not os.path.isfile("lobsterin.orig")

    def test_postprocess(self) -> None:
        # test gzipped and zipping of additional files
        src_path = Path(test_files_lobster3).absolute()
        for gzipped in (True, False):
            with TemporaryDirectory() as tmp_dir:
                cwd = Path(tmp_dir).absolute()
                for file_obj in Path(src_path).glob("*"):
                    if file_obj.is_file():
                        shutil.copy(src_path / file_obj, cwd / file_obj.name)
                    shutil.copy(src_path / "lobsterin", cwd / "lobsterin.orig")
                with cd(cwd):
                    v = LobsterJob("hello", gzipped=gzipped, add_files_to_gzip=VASP_OUTPUT_FILES)
                    v.postprocess()
                    assert all(
                        os.path.isfile(f"{file}{'.gz' if gzipped else ''}")
                        for file in (*VASP_OUTPUT_FILES, *LOBSTER_FILES, *FW_FILES)
                    )

    def test_postprocess_v51(self) -> None:
        # test gzipped and zipping of additional files for lobster v5.1
        src_path = Path(test_files_lobster4).absolute()
        for gzipped in (True, False):
            with TemporaryDirectory() as tmp_dir:
                cwd = Path(tmp_dir).absolute()
                for file_obj in Path(src_path).glob("*"):
                    if file_obj.is_file():
                        shutil.copy(src_path / file_obj, cwd / file_obj.name)
                    shutil.copy(src_path / "lobsterin", cwd / "lobsterin.orig")
                with cd(cwd):
                    v = LobsterJob("hello", gzipped=gzipped, add_files_to_gzip=VASP_OUTPUT_FILES)
                    v.postprocess()
                    assert all(
                        os.path.isfile(f"{file}{'.gz' if gzipped else ''}")
                        for file in {*VASP_OUTPUT_FILES, *LOBSTEROUTPUT_FILES, *FW_FILES}.difference(
                            {"POSCAR.lobster", "bandOverlaps.lobster"}  # these files are not in the directory
                        )
                    )
