from custodian.cp2k.jobs import Cp2kJob
from pymatgen.io.cp2k.sets import StaticSet, RelaxSet, HybridStaticSet
from pymatgen.core.structure import Structure
from pymatgen.io.cp2k.outputs import Cp2kOuput

if __name__ == '__main__':
    structure = Structure(lattice=[[3.349399, 0, 1.933776], [1.116466, 3.157843, 1.933776], [0, 0, 3.867552]],
                          species=['Si', 'Si'], coords=[[0, 0, 0], [1.11646617, 0.7894608, 1.93377613]])

    s = StaticSet(structure, auto_supercell=False, eps_default=1e-6)
    s.write_file(input_filename='cp2k.inp')

    cp2k_cmd = ['cp2k.sopt']
    settings_override = {'GLOBAL': {"RUN_TYPE": 'DEBUG'}}
    job = Cp2kJob(cp2k_cmd=cp2k_cmd, input_file='cp2k.inp', output_file='cp2k.out',
                  stderr_file='std_err.txt', suffix="", final=True, backup=True,
                  settings_override=settings_override)
    job.setup()
    job.run()



