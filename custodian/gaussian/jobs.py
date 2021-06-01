# coding: utf-8

'''
This module implements basic kinds of jobs for Gaussian runs.
'''

import copy
import shutil
import logging
import subprocess

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
                         backup=True):

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
                
                # TODO: add a checkpoint that checkpoint file is present
                gin = copy.deepcopy(orig_input)
                gin.molecule = lower_output.final_structure
                gin.route_parameters['Guess'] = 'Read'
                gin.route_parameters['Geom'] = 'Checkpoint'
                gin.write_file(input_file)
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


