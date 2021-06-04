# coding: utf-8

"""
This module implements basic kinds of jobs for Gaussian runs.
"""

import os
import shutil
import logging
import subprocess

from fnmatch import filter

from pymatgen.io.gaussian import GaussianInput, GaussianOutput

from custodian.custodian import Job
from custodian.gaussian.handlers import GaussianErrorHandler


__author__ = 'Rasha Atwi'
__version__ = '0.0'
__maintainer__ = 'Rasha Atwi'
__email__ = 'rasha.atwi@stonybrook.edu'
__status__ = 'Alpha'
__date__ = '5/13/21'

logger = logging.getLogger(__name__)


class GaussianJob(Job):
    def __init__(
            self,
            gaussian_cmd,
            input_file,
            output_file,
            stderr_file='stderr.txt',
            backup=True):
        self.gaussian_cmd = gaussian_cmd
        self.input_file = input_file
        self.output_file = output_file
        self.stderr_file = stderr_file
        self.backup = backup

    def setup(self):
        if self.backup:
            shutil.copy(self.input_file, '{}.orig'.format(self.input_file))

    def run(self):
        logger.info('Running command: {}'.format(self.gaussian_cmd))
        with open(self.output_file, 'w') as out_file, \
                open(self.stderr_file, 'w', buffering=1) as error_file:
            process = subprocess.Popen(self.gaussian_cmd,
                                       stdout=out_file,
                                       stderr=error_file,
                                       shell=True)
        return process

    def postprocess(self):
        pass

    @classmethod
    def better_scf_guess(cls,
                         gaussian_cmd,
                         input_file,
                         output_file,
                         stderr_file='stderr.txt',
                         backup=True,
                         cart_coords=True):

        orig_input = GaussianInput.from_file(input_file)
        yield(GaussianJob(gaussian_cmd=gaussian_cmd,
                          input_file=input_file,
                          output_file=output_file,
                          stderr_file=stderr_file,
                          backup=backup))
        if GaussianErrorHandler.activate_better_scf_guess:
            # continue only if other corrections are invalid or failed
            lower_output = GaussianOutput(output_file)
            if len(lower_output.errors) == 0:
                # if the calculation at the lower level of theory succeeded
                if not filter(os.listdir('.'), '*.[Cc][Hh][Kk]'):
                    raise FileNotFoundError('Missing checkpoint file. Required '
                                            'to read initial guesses')

                gin = GaussianInput(
                    mol=None,
                    charge=orig_input.charge,
                    spin_multiplicity=orig_input.spin_multiplicity,
                    title=orig_input.title,
                    functional=orig_input.functional,
                    basis_set=orig_input.basis_set,
                    route_parameters=lower_output.route_parameters,
                    input_parameters=orig_input.input_parameters,
                    link0_parameters=orig_input.link0_parameters,
                    dieze_tag=orig_input.dieze_tag,
                    gen_basis=orig_input.gen_basis)
                gin.route_parameters['Guess'] = 'Read'
                gin.route_parameters['Geom'] = 'Checkpoint'
                gin.write_file(input_file, cart_coords=cart_coords)

                yield(GaussianJob(gaussian_cmd=gaussian_cmd,
                                  input_file=input_file,
                                  output_file=output_file,
                                  stderr_file=stderr_file,
                                  backup=backup))
            else:
                logger.info('Failed to generate a better initial SCF guess')
                
        else:
            logger.info('SCF calculation completed normally without having '
                        'to generate a better initial guess')


