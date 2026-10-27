"""Tests of the model and its real native implementation."""
import pytest
from pathlib import Path


from _fg_helpers import (
    target__target_life_cycle_fixture_helpers,
    map_impact_of as impact_of,
    map_write as write,
)

@pytest.mark.parametrize('changed,expected,tests', [
    ('child.py', {'child', 'parent'}, ['tests/test_child.py']),
    ('_shared.py', {'child', 'parent'}, []),
    ('_leaf.py', {'child', 'parent'}, []),
    ('grand.py', {'grand', 'parent'}, ['tests/test_grand.py']),
    ('parent.py', {'parent'}, ['tests/test_parent.py']),
    ('_unused.py', set(), []),
])
def test_change_selects_importers_and_ancestors_of_a_changed_model(impact_project, changed, expected, tests):
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




def test_new_parent_value_names_slicing_sibling(tmp_path):
    from flowguard.map.port import slicing_siblings
    from flowguard.map.mapfile import load_map, ignore_patterns
    from flowguard.map.inventory import build_inventory
    from flowguard.map.targetfile import build_target_view, load_target
    from flowguard.map.tree import build_tree
    factory = target__target_life_cycle_fixture_helpers("_target_fixture")["slicing_project"]
    for reads in (False, True):
        root = factory(tmp_path / str(reads), reads_field=reads)
        data = load_map(root)
        inv = build_inventory(root, ignore_patterns(data), write_cache=False)
        before = build_tree(root, data, inv)
        view = build_target_view(root, data, load_target(root))
        tree = build_tree(root, view.data, inv, view=view)
        ports = {mid: node.contract["port"] for mid, node in tree.nodes.items() if "port" in node.contract}
        actual = slicing_siblings("check", before.nodes["check"].contract["port"], ports["check"], tree, ports)
        assert actual == ([] if reads else [("publish", "gate", "flag", ("held",))])
