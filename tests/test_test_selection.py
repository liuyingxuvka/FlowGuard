"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_parametrized_anchor_selects_its_case_only(tmp_path):
    from _fg_helpers import map__select_test_fixture as _select_test_fixture
    from flowguard.map.impact import select_tests,Impact,run_commands
    data,inv,tree=_select_test_fixture(tmp_path)
    path=tmp_path/'tests/test_core.py'
    path.write_text('import pytest\n@pytest.mark.parametrize("x",[1,2],ids=["one","two"])\ndef test_bound(x): assert x\ndef test_noop(): pass\ndef test_last(): pass\n')
    tree.nodes['child'].contract['TESTED_BY']={'safe':['tests/test_core.py:test_bound[one]']}
    result=select_tests(tmp_path,data,inv,tree,{'child'},set())
    assert result['nodes']=={'tests/test_core.py':['test_bound[one]']}
    impact=Impact([],[],[],[],['tests/test_core.py'],[],[],test_functions=result['nodes'])
    assert 'tests/test_core.py::test_bound[one]' in run_commands(impact)[0]


def test_test_calling_through_same_file_helper_is_selected(tmp_path):
    from _fg_helpers import map__select_test_fixture as _select_test_fixture
    from flowguard.map.impact import select_tests
    data,inv,tree=_select_test_fixture(tmp_path)
    result=select_tests(tmp_path,data,inv,tree,{'child'},{'core.py#own'})
    assert {'test_bound','test_call','test_help'}<=set(result['nodes']['tests/test_core.py'])
    assert 'test_indirect' not in result['nodes']['tests/test_core.py']


def test_half_selected_file_runs_whole(tmp_path):
    from _fg_helpers import map__select_test_fixture as _select_test_fixture
    from flowguard.map.impact import select_tests
    data,inv,tree=_select_test_fixture(tmp_path)
    result=select_tests(tmp_path,data,inv,tree,set(),{'core.py#own'})
    assert 'tests/test_half.py' in result['whole_files']
    assert 'tests/test_core.py' not in result['whole_files']


def test_cli_test_reaching_through_main_is_counted_as_also_reached(tmp_path):
    from _fg_helpers import map__select_test_fixture as _select_test_fixture
    from flowguard.map.impact import select_tests
    data,inv,tree=_select_test_fixture(tmp_path)
    result=select_tests(tmp_path,data,inv,tree,set(),{'core.py#own'})
    assert result['also_reached']==['2 test functions call core.py:own only through other functions (python -m flowguard change --broad)']
