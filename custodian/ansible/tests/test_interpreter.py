# coding: utf-8

from __future__ import unicode_literals, division

"""
Created on Jun 1, 2012
"""


__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Jun 1, 2012"

import unittest

from custodian.ansible.interpreter import Modder
from custodian.ansible.actions import FileActions


class ModderTest(unittest.TestCase):

    def test_dict_modify(self):
        modder = Modder()
        d = {"Hello": "World"}
        mod = {'_set': {'Hello': 'Universe', 'Bye': 'World'}}
        modder.modify(mod, d)
        self.assertEqual(d, {'Bye': 'World', 'Hello': 'Universe'})
        mod = {'_unset': {'Hello': 1}}
        modder.modify(mod, d)
        self.assertEqual(d, {'Bye': 'World'})
        mod = {'_push': {'List': 1}}
        modder.modify(mod, d)
        self.assertEqual(d, {'Bye': 'World', 'List': [1]})
        mod = {'_push': {'List': 2}}
        modder.modify(mod, d)
        self.assertEqual(d, {'Bye': 'World', 'List': [1, 2]})
        mod = {'_inc': {'num': 5}}
        modder.modify(mod, d)
        self.assertEqual(d, {'Bye': 'World', 'List': [1, 2], 'num': 5})
        mod = {'_inc': {'num': 5}}
        modder.modify(mod, d)
        self.assertEqual(d, {'Bye': 'World', 'List': [1, 2], 'num': 10})
        mod = {'_rename': {'num': 'number'}}
        modder.modify(mod, d)
        self.assertEqual(d, {'Bye': 'World', 'List': [1, 2], 'number': 10})
        mod = {'_add_to_set': {'List': 2}}
        modder.modify(mod, d)
        self.assertEqual(d, {'Bye': 'World', 'List': [1, 2], 'number': 10})
        mod = {'_add_to_set': {'List': 3}}
        modder.modify(mod, d)
        self.assertEqual(d, {'Bye': 'World', 'List': [1, 2, 3], 'number': 10})
        mod = {'_add_to_set': {'number': 3}}
        self.assertRaises(ValueError, modder.modify, mod, d)
        mod = {'_pull': {'List': 1}}
        modder.modify(mod, d)
        self.assertEqual(d, {'Bye': 'World', 'List': [2, 3], 'number': 10})
        mod = {'_pull_all': {'List': [2, 3]}}
        modder.modify(mod, d)
        self.assertEqual(d, {'Bye': 'World', 'List': [], 'number': 10})
        mod = {'_push_all': {'List': list(range(10))}}
        modder.modify(mod, d)
        self.assertEqual(d, {'Bye': 'World',
                             'List': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                             'number': 10})
        mod = {'_pop': {'List': 1}}
        modder.modify(mod, d)
        self.assertEqual(d, {'Bye': 'World',
                             'List': [0, 1, 2, 3, 4, 5, 6, 7, 8],
                             'number': 10})
        mod = {'_pop': {'List':-1}}
        modder.modify(mod, d)
        self.assertEqual(d, {'Bye': 'World', 'List': [1, 2, 3, 4, 5, 6, 7, 8],
                             'number': 10})
        d = {}
        mod = {'_set': {'a->b->c': 100}}
        modder.modify(mod, d)
        self.assertEqual(d, {'a': {'b': {'c': 100}}})
        mod = {'_set': {'a->b->d': 200}}
        modder.modify(mod, d)
        self.assertEqual(d, {'a': {'b': {'c': 100, 'd': 200}}})
        mod = {'_set': {'a->b->d': 300}}
        modder.modify(mod, d)
        self.assertEqual(d, {'a': {'b': {'c': 100, 'd': 300}}})
        mod = {'_unset': {'a->b->d': 300}}
        modder.modify(mod, d)
        self.assertEqual(d, {'a': {'b': {'c': 100}}})
        mod = {'_push': {'a->e->f': 300}}
        modder.modify(mod, d)
        self.assertEqual(d, {'a': {'b': {'c': 100}, 'e': {'f': [300]}}})
        mod = {'_push_all': {'a->e->f': [100, 200]}}
        modder.modify(mod, d)
        self.assertEqual(d, {'a': {'b': {'c': 100},
                                   'e': {'f': [300, 100, 200]}}})
        mod = {'_inc': {'a->b->c': 2}}
        modder.modify(mod, d)
        self.assertEqual(d, {'a': {'b': {'c': 102},
                                   'e': {'f': [300, 100, 200]}}})
        mod = {'_pull': {'a->e->f': 300}}
        modder.modify(mod, d)
        self.assertEqual(d, {'a': {'b': {'c': 102}, 'e': {'f': [100, 200]}}})
        mod = {'_pull_all': {'a->e->f': [100, 200]}}
        modder.modify(mod, d)
        self.assertEqual(d, {'a': {'b': {'c': 102}, 'e': {'f': []}}})
        mod = {'_push_all': {'a->e->f': [101, 201, 301, 401]}}
        modder.modify(mod, d)
        self.assertEqual(d, {'a': {'b': {'c': 102},
                                   'e': {'f': [101, 201, 301, 401]}}})
        mod = {'_pop': {'a->e->f': 1}}
        modder.modify(mod, d)
        self.assertEqual(d, {'a': {'b': {'c': 102},
                                   'e': {'f': [101, 201, 301]}}})
        mod = {'_pop': {'a->e->f':-1}}
        modder.modify(mod, d)
        self.assertEqual(d, {'a': {'b': {'c': 102}, 'e': {'f': [201, 301]}}})

    def test_file_modify(self):
        modder = Modder(actions=[FileActions])
        modder.modify({'_file_create': {'content': 'Test data'}}, 'test_file')
        modder.modify({'_file_copy': {'dest': 'test_file_copy'}}, 'test_file')
        modder.modify({'_file_copy': {'dest1': 'test_file_copy1',
                                      'dest2': 'test_file_copy2'}},
                      'test_file')
        modder.modify({'_file_move': {'dest': 'renamed_test_file'}},
                      'test_file')
        modder.modify({'_file_delete': {'mode': "actual"}},
                      'renamed_test_file')
        modder.modify({'_file_modify': {'mode': 0o666}}, 'test_file_copy')
        modder.modify({'_file_delete': {'mode': "actual"}}, 'test_file_copy')
        modder.modify({'_file_delete': {'mode': "actual"}}, 'test_file_copy1')
        modder.modify({'_file_delete': {'mode': "actual"}}, 'test_file_copy2')

    def test_strict_mode(self):
        modder = Modder(actions=[FileActions])
        d = {"Hello": "World"}
        mod = {'_set': {'Hello': 'Universe', 'Bye': 'World'}}
        self.assertRaises(ValueError, modder.modify, mod, d)

        #In non-strict mode, unknown actions are ignored.
        d = {"Hello": "World"}
        modder = Modder(actions=[FileActions], strict=False)
        modder.modify(mod, d)
        self.assertEqual(d, {"Hello": "World"})

        #File actions not supported
        modder = Modder()
        self.assertRaises(ValueError, modder.modify,
                          {'_file_create': {'content': 'Test data'}},
                          'test_file')

    def test_modify_object(self):
        modder = Modder()
        o = MyObject(1)
        self.assertEqual(o.b["a"], 1)
        mod_o = modder.modify_object({'_set': {'b->a': 20}}, o)
        self.assertEqual(mod_o.b["a"], 20)

class MyObject():

    def __init__(self, a):
        self.b = {'a': a}

    def as_dict(self):
        return {'b': {'a': self.b['a']}}

    @staticmethod
    def from_dict(d):
        return MyObject(d["b"]["a"])

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
