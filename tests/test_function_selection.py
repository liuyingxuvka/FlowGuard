"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_owned_edit_does_not_select_composing_parent(tmp_path):
    from _fg_helpers import map_function_fixture as function_fixture
    helper=function_fixture()
    for case in ('body','helper'):
        root=tmp_path/case;root.mkdir()
        impact=helper['native_case'](root,case)
        assert impact.model_ids==['child']
        assert 'parent' not in impact.model_ids


def test_module_binding_change_selects_importer_functions(tmp_path):
    from _fg_helpers import map_function_fixture as function_fixture
    from flowguard.map.impact import render_impact
    impact=function_fixture()['native_case'](tmp_path,'binding')
    assert 'importer' in impact.model_ids
    assert 'api.py:call' in impact.changed_functions
    assert 'UNCERTAIN: core.py' not in render_impact(impact)


def test_removed_function_is_uncertain(tmp_path):
    from _fg_helpers import map_function_fixture as function_fixture
    from flowguard.map.impact import render_impact
    impact=function_fixture()['native_case'](tmp_path,'removed')
    assert impact.model_ids and impact.uncertain_files['core.py']
    assert 'UNCERTAIN: core.py:' in render_impact(impact)


def test_no_git_uses_stale_components(tmp_path):
    from _fg_helpers import map_function_fixture as function_fixture
    from flowguard.map.impact import render_impact
    impact=function_fixture()['native_case'](tmp_path,'no_git')
    assert impact.tests==['tests/test_core.py']
    assert impact.changed==['core.py']
    assert 'NO GIT: changed files = the files of 1 component(s)' in render_impact(impact)
    assert 'a test file edited alone is not seen: run it by path' in render_impact(impact)
