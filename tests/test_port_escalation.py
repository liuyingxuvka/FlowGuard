"""Tests of the model and its real native implementation."""
import pytest
from pathlib import Path


@pytest.mark.parametrize('changed,expected,tests', [
    ('child.py', {'child', 'parent'}, ['tests/test_child.py']),
    ('_shared.py', {'child', 'parent'}, []),
    ('_leaf.py', {'child', 'parent'}, []),
    ('grand.py', {'grand', 'parent'}, ['tests/test_grand.py']),
    ('parent.py', {'parent'}, ['tests/test_parent.py']),
    ('_unused.py', set(), []),
])
def test_change_selects_importers_and_ancestors_of_a_changed_model(impact_project, changed, expected, tests):
    from _fg_helpers import map_write as write, map_impact_of as impact_of
    root, data = impact_project
    for mid in ('parent', 'child', 'grand'):
        content = (f'MODEL_ID = {mid!r}\nIMPLEMENTED_BY = {{"Probe": "tests/test_{mid}.py:test_safe"}}\ndef conformance(): pass\n'
                   f'TESTED_BY = {{"safe": ["tests/test_{mid}.py:test_safe"]}}\ndef build_explorer(): pass\n')
        content += {'parent': 'import child\nimport _shared\n', 'child': 'from _shared import VALUE\n',
                    'grand': 'PARENT = "parent"\n'}[mid]
        write(root, f'.flowguard/models/{mid}.py', content)
        write(root, f'tests/test_{mid}.py', 'def test_safe(): assert True\n')
    write(root, '.flowguard/models/_shared.py', 'PARENT = None\nfrom _leaf import VALUE\n')
    write(root, '.flowguard/models/_leaf.py', 'VALUE = 1\n')
    write(root, '.flowguard/models/_unused.py', 'VALUE = 2\n')
    path = '.flowguard/models/' + changed
    impact = impact_of(root, data, [path], broad=True)
    assert set(impact.model_ids) == expected
    assert impact.tests == tests  # added importers/ancestors do not add their TESTED_BY tests
    assert not impact.direct and not impact.dependents and not impact.blocked
    assert impact.no_checks == ([path] if changed == '_unused.py' else [])


    # Reverse model imports remain selected even without the broad ancestry loop.
    direct = impact_of(root, data, [path])
    if changed in {"child.py", "_shared.py", "_leaf.py"}:
        assert {"child", "parent"} <= set(direct.model_ids)
