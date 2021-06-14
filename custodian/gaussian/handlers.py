# coding: utf-8

"""
This module implements error handlers for Gaussian runs.
"""

import os
import re
import glob
import logging

import numpy as np
import matplotlib.pyplot as plt

from matplotlib.ticker import MaxNLocator

from monty.io import zopen

from pymatgen.io.gaussian import GaussianInput, GaussianOutput

from custodian.utils import backup
from custodian.custodian import ErrorHandler

__author__ = 'Rasha Atwi'
__version__ = '0.0'
__maintainer__ = 'Rasha Atwi'
__email__ = 'rasha.atwi@stonybrook.edu'
__status__ = 'Alpha'
__date__ = '5/13/21'


class GaussianErrorHandler(ErrorHandler):
    error_defs = {'Optimization stopped': 'opt_steps',
                  'Convergence failure': 'scf_convergence',
                  'FormBX had a problem': 'linear_bend',
                  'Linear angle in Tors.': 'linear_bend',
                  'Inv3 failed in PCMMkU': 'solute_solvent_surface',
                  'End of file in ZSymb': 'zmatrix',
                  'There are no atoms in this input structure !': 'missing_mol',
                  'Atom specifications unexpectedly found in input stream.': 'found_coords',
                  'End of file reading connectivity.': 'coords',
                  'FileIO operation on non-existent file.': 'missing_file',
                  'No data on chk file.': 'empty_file',
                  'Bad file opened by FileIO': 'bad_file',
                  'Z-matrix optimization but no Z-matrix variables.': 'coord_inputs',
                  'A syntax error was detected in the input line.': 'syntax'}

    error_patt = re.compile('|'.join(list(error_defs)))
    conv_critera = {
        'max_force': re.compile(
            r'\s+(Maximum Force)\s+(-?\d+.?\d*|.*)\s+(-?\d+.?\d*)'),
        'rms_force': re.compile(
            r'\s+(RMS {5}Force)\s+(-?\d+.?\d*|.*)\s+(-?\d+.?\d*)'),
        'max_disp': re.compile(
            r'\s+(Maximum Displacement)\s+(-?\d+.?\d*|.*)\s+(-?\d+.?\d*)'),
        'rms_disp': re.compile(
            r'\s+(RMS {5}Displacement)\s+(-?\d+.?\d*|.*)\s+(-?\d+.?\d*)')}

    grid_patt = re.compile(r'(-?\d{5})')
    GRID_NAMES = ['finegrid', 'fine', 'superfinegrid', 'superfine',
                  'coarsegrid', 'coarse', 'sg1grid', 'sg1',
                  'pass0grid', 'pass0']

    activate_better_guess = False

    def __init__(
            self,
            input_file,
            output_file,
            stderr_file='stderr.txt',
            cart_coords=True,
            scf_max_cycles=100,
            opt_max_cycles=100,
            job_type='normal',
            lower_functional=None,
            lower_basis_set=None,
            prefix='error',
            check_convergence=True
    ):
        self.input_file = input_file
        self.output_file = output_file
        self.stderr_file = stderr_file
        self.cart_coords = cart_coords
        self.errors = set()
        self.gout = None
        self.gin = None
        self.scf_max_cycles = scf_max_cycles
        self.opt_max_cycles = opt_max_cycles
        self.job_type = job_type
        self.lower_functional = lower_functional
        self.lower_basis_set = lower_basis_set
        self.prefix = prefix
        self.check_convergence = check_convergence
        self.conv_data = None
        self.logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def _recursive_lowercase(obj):
        if isinstance(obj, dict):
            updated_obj = {}
            for k, v in obj.items():
                updated_obj[k.lower()] = \
                    GaussianErrorHandler._recursive_lowercase(v)
            return updated_obj
        elif isinstance(obj, str):
            return obj.lower()
        elif hasattr(obj, '__iter__'):
            updated_obj = []
            for i in obj:
                updated_obj.append(GaussianErrorHandler._recursive_lowercase(i))
            return updated_obj
        else:
            return obj

    @staticmethod
    def _recursive_remove_space(obj):
        updated_obj = {}
        for key, value in obj.items():
            if isinstance(value, dict):
                updated_obj[key.strip()] = \
                    GaussianErrorHandler._recursive_remove_space(value)
            elif isinstance(value, str):
                updated_obj[key.strip()] = value.strip()
            else:
                updated_obj[key.strip()] = value
        return updated_obj

    @staticmethod
    def _update_route_params(route_params, key, value):
        obj = route_params.get(key, {})
        if not obj:
            route_params[key] = value
        elif isinstance(obj, str):
            update = {key: {obj: None, **value}} if isinstance(value, dict) \
                else {key: {obj: None, value: None}}
            route_params.update(update)
        elif isinstance(obj, dict):
            update = value if isinstance(value, dict) else {value: None}
            route_params[key].update(update)
        return route_params

    @staticmethod
    def _int_keyword(route_params):
        if 'int' in route_params:
            int_key = 'int'
        elif 'integral' in route_params:
            int_key = 'integral'
        else:
            int_key = ''
        # int_key = 'int' if 'int' in route_params else 'integral'
        return int_key, route_params.get(int_key, '')

    @staticmethod
    def _int_grid(route_params):
        _, int_value = GaussianErrorHandler._int_keyword(route_params)
        options = ['ultrafine', 'ultrafinegrid', '99590']

        if isinstance(int_value, str) and int_value in options:
            return True
        elif isinstance(int_value, dict):
            if int_value.get('grid') in options:
                return True
            if set(int_value) & set(options):
                return True
        return False

    def _add_int(self):
        if GaussianErrorHandler._int_grid(self.gin.route_parameters):
            # nothing int is set or is set to different values
            warning_msg = 'Changing the numerical integration grid. ' \
                          'This will bring changes in the predicted ' \
                          'total energy. It is necessary to use the same ' \
                          'integration grid in all the calculations in ' \
                          'the same study in order for the computed ' \
                          'energies and molecular properties to be ' \
                          'comparable.'

            int_key, int_value = \
                GaussianErrorHandler._int_keyword(self.gin.route_parameters)
            if not int_value and GaussianErrorHandler._not_g16(self.gout):
                # if int keyword is missing and Gaussian version is 03 or
                # 09, set integration grid to ultrafine
                int_key = int_key or 'int'
                self.logger.warning(warning_msg)
                self.gin.route_parameters[int_key] = 'ultrafine'
                return {'integral': 'ultra_fine'}
            elif isinstance(int_value, dict):
                # if int grid is set and is different from ultrafine,
                # set it to ultrafine (works when others int options are
                # specified)
                flag = True if 'grid' in self.gin.route_parameters[int_key] \
                    else False
                for key in self.gin.route_parameters[int_key]:
                    if key in self.GRID_NAMES or self.grid_patt.match(key):
                        self.gin.route_parameters[int_key].pop(key)
                        flag = True
                        break
                if flag or GaussianErrorHandler._not_g16(self.gout):
                    self.logger.warning(warning_msg)
                    self.gin.route_parameters[int_key]['grid'] = 'ultrafine'
                    return {'integral': 'ultra_fine'}
            else:
                if int_value in self.GRID_NAMES or self.grid_patt.match(
                        int_value):
                    # if int grid is set and is different from ultrafine,
                    # set it to ultrafine (works when no other int options
                    # are specified)
                    self.logger.warning(warning_msg)
                    self.gin.route_parameters[int_key] = 'ultrafine'
                    return {'integral': 'ultra_fine'}
                elif GaussianErrorHandler._not_g16(self.gout):
                    # if int grid is not specified, and Gaussian version is
                    # not 16, update with ultrafine integral grid
                    self.logger.warning(warning_msg)
                    GaussianErrorHandler._update_route_params(
                        self.gin.route_parameters, int_key,
                        {'grid': 'ultrafine'})
                    return {'integral': 'ultra_fine'}
        else:
            return {}
        return {}

    @staticmethod
    def _not_g16(gout):
        return '16' not in gout.version

    @staticmethod
    def _monitor_convergence(data):
        fig, ax = plt.subplots(ncols=2, nrows=2, figsize=(12, 10))
        for i, (k, v) in enumerate(data['values'].items()):
            row = int(np.floor(i / 2))
            col = i % 2
            iters = range(0, len(v))
            ax[row, col].plot(iters, v, color='#cf3759', linewidth=2)
            ax[row, col].axhline(y=data['thresh'][k], linewidth=2,
                                 color='black', linestyle='--')
            ax[row, col].tick_params(which='major', length=8)
            ax[row, col].tick_params(axis='both', which='both', direction='in',
                                     labelsize=16)
            ax[row, col].set_xlabel('Iteration', fontsize=16)
            ax[row, col].set_ylabel('{}'.format(k), fontsize=16)
            # ax[row, col].set_xticks(iters)
            ax[row, col].xaxis.set_major_locator(MaxNLocator(integer=True))
            ax[row, col].grid(ls='--', zorder=1)
        plt.tight_layout()
        plt.savefig('convergence.png')

    def check(self):
        self.gin = GaussianInput.from_file(self.input_file)
        self.gin.route_parameters = \
            GaussianErrorHandler._recursive_lowercase(self.gin.route_parameters)
        self.gin.route_parameters = \
            GaussianErrorHandler._recursive_remove_space(
                self.gin.route_parameters)
        self.gout = GaussianOutput(self.output_file)
        self.errors = set()
        error_patts = set()
        # TODO: move this to pymatgen?
        self.conv_data = {'values': {}, 'thresh': {}}
        with zopen(self.output_file) as f:
            for line in f:
                if GaussianErrorHandler.error_patt.search(line):
                    m = GaussianErrorHandler.error_patt.search(line)
                    patt = m.group(0)
                    error_patts.add(patt)
                    self.errors.add(GaussianErrorHandler.error_defs[patt])

                if self.check_convergence and 'opt' in self.gin.route_parameters:
                    for k, v in GaussianErrorHandler.conv_critera.items():
                        if v.search(line):
                            m = v.search(line)
                            if k not in self.conv_data['values']:
                                self.conv_data['values'][k] = [
                                    float(m.group(2))]
                                self.conv_data['thresh'][k] = float(m.group(3))
                            else:
                                self.conv_data['values'][k].append(
                                    float(m.group(2)))
        # TODO: it only plots after the job finishes, modify?
        if self.check_convergence and 'opt' in self.gin.route_parameters:
            if self.conv_data['values']:
                plot_d = self.conv_data['values']
                GaussianErrorHandler._monitor_convergence(self.conv_data)

        for patt in error_patts:
            self.logger.error(patt)
        return len(self.errors) > 0

    def correct(self):
        actions = []
        # to avoid situations like 'linear_bend', where if we backup input_file,
        # it will not be the actual input used in the current calc
        # shutil.copy(self.input_file, f'{self.input_file}.backup')
        backup_files = [self.input_file, self.output_file,
                        self.stderr_file]
        checkpoint = glob.glob('*.[Cc][Hh][Kk]')
        form_checkpoint = glob.glob('*.[Ff][Cc][Hh][Kk]')
        png = glob.glob('convergence.png')
        [backup_files.append(i[0]) for i in [checkpoint, form_checkpoint, png]
         if i]
        backup(backup_files, self.prefix)
        if 'scf_convergence' in self.errors:
            # if the SCF procedure has failed to converge
            if self.gin.route_parameters.get('scf').get('maxcycle') != \
                    str(self.scf_max_cycles):
                # increase number of cycles if not already set or is different
                # from scf_max_cycles
                self.gin.route_parameters['scf']['maxcycle'] = \
                    self.scf_max_cycles
                actions.append({'scf_max_cycles': self.scf_max_cycles})

            elif not {'xqc', 'yqc', 'qc'}.intersection(
                    self.gin.route_parameters.get('scf')):
                # use an alternate SCF converger
                self.gin.route_parameters['scf']['xqc'] = None
                actions.append({'scf_algorithm': 'xqc'})

            elif self.job_type == 'better_guess' and not \
                    GaussianErrorHandler.activate_better_guess:
                # try to get a better initial guess at a lower level of theory
                self.logger.info('SCF calculation failed. Switching to a lower '
                                 'level of theory to get a better initial '
                                 'guess of molecular orbitals')
                # TODO: what if inputs don't work with scf_lot? e.g. extra_basis
                self.gin.functional = self.lower_functional
                self.gin.basis_set = self.lower_basis_set
                GaussianErrorHandler.activate_better_guess = True
                actions.append({'scf_level_of_theory': 'better_scf_guess'})

            else:
                if self.job_type != 'better_guess':
                    self.logger.info(
                        'Try to switch to better_guess job type to '
                        'generate a different initial guess using a '
                        'lower level of theory')
                else:
                    self.logger.info('SCF calculation failed. Exiting...')
                return {'errors': self.errors, 'actions': None}

        elif 'opt_steps' in self.errors:
            int_actions = GaussianErrorHandler._add_int()
            if self.gin.route_parameters.get('opt').get('maxcycles') != \
                    str(self.opt_max_cycles):
                self.gin.route_parameters['opt']['maxcycles'] = \
                    self.opt_max_cycles
                if len(self.gout.structures) > 1:
                    self.gin._mol = self.gout.final_structure
                    actions.append({'structure': 'from_final_structure'})
                actions.append({'opt_max_cycles': self.opt_max_cycles})

            elif self.check_convergence and \
                    all(v[-1] < v[0] for v in
                        self.conv_data['values'].values()):
                self.gin._mol = self.gout.final_structure
                actions.append({'structure': 'from_final_structure'})

            elif int_actions:
                actions.append(int_actions)
                # TODO: check if the defined methods are clean
                # TODO: don't enter this if condition if g16 and ...

            elif self.job_type == 'better_guess' and not \
                    GaussianErrorHandler.activate_better_guess:
                # TODO: check if the logic is correct since this is used with scf
                # try to get a better initial guess at a lower level of theory
                self.logger.info('Geometry optimiztion failed. Switching to a '
                                 'lower level of theory to get a better '
                                 'initial guess of molecular geometry')
                self.gin.functional = self.lower_functional
                self.gin.basis_set = self.lower_basis_set
                GaussianErrorHandler.activate_better_guess = True
                actions.append({'opt_level_of_theory': 'better_geom_guess'})

            else:
                if self.job_type != 'better_guess':
                    self.logger.info(
                        'Try to switch to better_guess job type to '
                        'generate a different initial guess using a '
                        'lower level of theory')
                else:
                    self.logger.info('Geometry optimization failed. Exiting...')
                return {'errors': self.errors, 'actions': None}

        elif 'linear_bend' in self.errors:
            # if there is some linear bend around an angle in the geometry
            # restart the job at the point it stopped while forcing Gaussian
            # to rebuild the set of redundant internals
            if not list(filter(re.compile(r'%[Cc][Hh][Kk]').match,
                               self.gin.link0_parameters.keys())):
                raise KeyError('This remedy reads coords from checkpoint '
                               'file. Consider adding CHK to link0_parameters')
            else:
                self.gin = GaussianInput(
                    mol=None,
                    charge=self.gin.charge,
                    spin_multiplicity=self.gin.spin_multiplicity,
                    title=self.gin.title,
                    functional=self.gin.functional,
                    basis_set=self.gin.basis_set,
                    route_parameters=self.gin.route_parameters,
                    input_parameters=self.gin.input_parameters,
                    link0_parameters=self.gin.link0_parameters,
                    dieze_tag=self.gin.dieze_tag,
                    gen_basis=self.gin.gen_basis)
                actions.append({'coords': 'rebuild_redundant_internals'})

        elif 'solute_solvent_surface' in self.errors:
            # if non-convergence in the iteration of the PCM matrix is
            # encountered, change the type of molecular surface representing
            # the solute-solvent boundary
            # TODO: test
            input_parms = {key.lower() if isinstance(key, str) else
                           key: value for key, value in
                           self.gin.input_parameters.items()}
            if input_parms.get('surface', 'none').lower() != 'sas':
                self.gin.route_parameters.get('scrf', {}).update({'read': None})
                self.gin.input_parameters.update({'surface': 'SAS'})
                actions.append({'surface': 'SAS'})
            else:
                self.logger.info('Not sure how to fix '
                                 'solute_solvent_surface_error if surface is '
                                 'already SAS!')
        os.rename(self.input_file, self.input_file + '.prev')
        self.gin.write_file(self.input_file, self.cart_coords)
        return {'errors': list(self.errors), 'actions': actions}
