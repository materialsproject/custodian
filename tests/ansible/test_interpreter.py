"""Created on Jun 1, 2012."""


__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Jun 1, 2012"


import pytest

from custodian.ansible.actions import FileActions
from custodian.ansible.interpreter import Modder


class TestModder:
    def test_dict_modify(self):
        modder = Modder()
        dct = {"Hello": "World"}
        mod = {"_set": {"Hello": "Universe", "Bye": "World"}}
        modder.modify(mod, dct)
        assert dct == {"Bye": "World", "Hello": "Universe"}
        mod = {"_unset": {"Hello": 1}}
        modder.modify(mod, dct)
        assert dct == {"Bye": "World"}
        mod = {"_push": {"List": 1}}
        modder.modify(mod, dct)
        assert dct == {"Bye": "World", "List": [1]}
        mod = {"_push": {"List": 2}}
        modder.modify(mod, dct)
        assert dct == {"Bye": "World", "List": [1, 2]}
        mod = {"_inc": {"num": 5}}
        modder.modify(mod, dct)
        assert dct == {"Bye": "World", "List": [1, 2], "num": 5}
        mod = {"_inc": {"num": 5}}
        modder.modify(mod, dct)
        assert dct == {"Bye": "World", "List": [1, 2], "num": 10}
        mod = {"_rename": {"num": "number"}}
        modder.modify(mod, dct)
        assert dct == {"Bye": "World", "List": [1, 2], "number": 10}
        mod = {"_add_to_set": {"List": 2}}
        modder.modify(mod, dct)
        assert dct == {"Bye": "World", "List": [1, 2], "number": 10}
        mod = {"_add_to_set": {"List": 3}}
        modder.modify(mod, dct)
        assert dct == {"Bye": "World", "List": [1, 2, 3], "number": 10}
        mod = {"_add_to_set": {"number": 3}}
        with pytest.raises(ValueError, match="Keyword number does not refer to an array"):
            modder.modify(mod, dct)
        mod = {"_pull": {"List": 1}}
        modder.modify(mod, dct)
        assert dct == {"Bye": "World", "List": [2, 3], "number": 10}
        mod = {"_pull_all": {"List": [2, 3]}}
        modder.modify(mod, dct)
        assert dct == {"Bye": "World", "List": [], "number": 10}
        mod = {"_push_all": {"List": list(range(10))}}
        modder.modify(mod, dct)
        assert dct == {"Bye": "World", "List": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], "number": 10}
        mod = {"_pop": {"List": 1}}
        modder.modify(mod, dct)
        assert dct == {"Bye": "World", "List": [0, 1, 2, 3, 4, 5, 6, 7, 8], "number": 10}
        mod = {"_pop": {"List": -1}}
        modder.modify(mod, dct)
        assert dct == {"Bye": "World", "List": [1, 2, 3, 4, 5, 6, 7, 8], "number": 10}
        dct = {}
        mod = {"_set": {"a->b->c": 100}}
        modder.modify(mod, dct)
        assert dct == {"a": {"b": {"c": 100}}}
        mod = {"_set": {"a->b->dct": 200}}
        modder.modify(mod, dct)
        assert dct == {"a": {"b": {"c": 100, "dct": 200}}}
        mod = {"_set": {"a->b->dct": 300}}
        modder.modify(mod, dct)
        assert dct == {"a": {"b": {"c": 100, "dct": 300}}}
        mod = {"_unset": {"a->b->dct": 300}}
        modder.modify(mod, dct)
        assert dct == {"a": {"b": {"c": 100}}}
        mod = {"_push": {"a->e->f": 300}}
        modder.modify(mod, dct)
        assert dct == {"a": {"b": {"c": 100}, "e": {"f": [300]}}}
        mod = {"_push_all": {"a->e->f": [100, 200]}}
        modder.modify(mod, dct)
        assert dct == {"a": {"b": {"c": 100}, "e": {"f": [300, 100, 200]}}}
        mod = {"_inc": {"a->b->c": 2}}
        modder.modify(mod, dct)
        assert dct == {"a": {"b": {"c": 102}, "e": {"f": [300, 100, 200]}}}
        mod = {"_pull": {"a->e->f": 300}}
        modder.modify(mod, dct)
        assert dct == {"a": {"b": {"c": 102}, "e": {"f": [100, 200]}}}
        mod = {"_pull_all": {"a->e->f": [100, 200]}}
        modder.modify(mod, dct)
        assert dct == {"a": {"b": {"c": 102}, "e": {"f": []}}}
        mod = {"_push_all": {"a->e->f": [101, 201, 301, 401]}}
        modder.modify(mod, dct)
        assert dct == {"a": {"b": {"c": 102}, "e": {"f": [101, 201, 301, 401]}}}
        mod = {"_pop": {"a->e->f": 1}}
        modder.modify(mod, dct)
        assert dct == {"a": {"b": {"c": 102}, "e": {"f": [101, 201, 301]}}}
        mod = {"_pop": {"a->e->f": -1}}
        modder.modify(mod, dct)
        assert dct == {"a": {"b": {"c": 102}, "e": {"f": [201, 301]}}}

    def test_file_modify(self):
        modder = Modder(actions=[FileActions])
        modder.modify({"_file_create": {"content": "Test data"}}, "test_file")
        modder.modify({"_file_copy": {"dest": "test_file_copy"}}, "test_file")
        modder.modify(
            {"_file_copy": {"dest1": "test_file_copy1", "dest2": "test_file_copy2"}},
            "test_file",
        )
        modder.modify({"_file_move": {"dest": "renamed_test_file"}}, "test_file")
        modder.modify({"_file_delete": {"mode": "actual"}}, "renamed_test_file")
        modder.modify({"_file_modify": {"mode": 0o666}}, "test_file_copy")
        modder.modify({"_file_delete": {"mode": "actual"}}, "test_file_copy")
        modder.modify({"_file_delete": {"mode": "actual"}}, "test_file_copy1")
        modder.modify({"_file_delete": {"mode": "actual"}}, "test_file_copy2")

    def test_strict_mode(self):
        modder = Modder(actions=[FileActions])
        dct = {"Hello": "World"}
        mod = {"_set": {"Hello": "Universe", "Bye": "World"}}
        with pytest.raises(ValueError, match="_set is not a supported action"):
            modder.modify(mod, dct)

        # In non-strict mode, unknown actions are ignored.
        dct = {"Hello": "World"}
        modder = Modder(actions=[FileActions], strict=False)
        modder.modify(mod, dct)
        assert dct == {"Hello": "World"}

        # File actions not supported
        modder = Modder()
        with pytest.raises(ValueError, match="_file_create is not a supported action"):
            modder.modify(
                {"_file_create": {"content": "Test data"}},
                "test_file",
            )

    def test_modify_object(self):
        modder = Modder()
        o = MyObject(1)
        assert o.b["a"] == 1
        mod_o = modder.modify_object({"_set": {"b->a": 20}}, o)
        assert mod_o.b["a"] == 20


class MyObject:
    def __init__(self, a):
        self.b = {"a": a}

    def as_dict(self):
        return {"b": {"a": self.b["a"]}}

    @staticmethod
    def from_dict(dct):
        return MyObject(dct["b"]["a"])
