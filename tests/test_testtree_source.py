"""Retained public source and native-test inventory contracts."""
from flowguard.map.testtree import test_functions as functions, resolve_test_anchor


def test_unittest_and_same_file_base_classes_count():
    text='''import unittest
class Base(unittest.TestCase):
    def test_base(self): pass
class Suite(Base):
    def test_own(self): pass
class Helper:
    def test_inherited(self): pass
class TestChild(Helper): pass
'''
    assert set(functions(text))=={'Base.test_base','Suite.test_base','Suite.test_own','TestChild.test_inherited'}

def test_bare_method_tested_by_resolves_by_suffix(tmp_path):
    path=tmp_path/'test_case.py';path.write_text('import unittest\nclass Suite(unittest.TestCase):\n    def test_value(self): pass\n')
    assert resolve_test_anchor(path,'test_value')=='Suite.test_value'
    assert resolve_test_anchor(path,'Suite::test_value[case]')=='Suite.test_value'
