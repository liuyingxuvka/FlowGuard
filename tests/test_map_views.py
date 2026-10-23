"""Finite checks for the human/agent map views, including strict output budgets."""
from pathlib import Path

from flowguard.map.inventory import Inventory, PyInfo
from flowguard.map.views import file_outline, find_owners, render_show


def _inventory(root):
    return Inventory(root, [], [], [], {}, {}, {})


def _component(name, *, responsibilities=(), summary=''):
    return dict(id=name, summary=summary, responsibilities=list(responsibilities),
                files=[], status='draft', fingerprint='', layer='', depends_on=[])


def test_show_budget_keeps_flows_and_names_hidden_components(tmp_path):
    data = dict(project='demo', components=[_component('alpha', summary='a' * 200), _component('beta', summary='b' * 200)],
                flows=[dict(id='checkout', summary='request to result', steps=['alpha:run'])])
    inv = _inventory(tmp_path)
    full = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert '> flow checkout' in full and 'truncated' not in full
    bounded = render_show(tmp_path, data, inv, component=None, detail=False, budget=260)
    assert len(bounded) <= 260
    assert '> flow checkout' in bounded and 'not shown:' in bounded
    for budget in (0, 20, 80, 100, 400):
        assert len(render_show(tmp_path, data, inv, component=None, detail=False, budget=budget)) <= budget


def test_find_responsibility_breaks_equal_summary_score(tmp_path):
    data = dict(components=[_component('alpha', summary='impact selection'),
                            _component('map-analysis', responsibilities=['impact selection'])])
    scores = find_owners(data, _inventory(tmp_path), ['impact', 'selection'])
    assert scores[0][1] == 'map-analysis'
    assert scores[0][0] == scores[1][0]


def test_find_matches_plural_and_camel_case_words(tmp_path):
    data = dict(components=[_component('api', summary='cancel endpoint', responsibilities=['route cancel requests']),
                            _component('orders', responsibilities=['place orders and cancel them'])])
    assert find_owners(data, _inventory(tmp_path), ['cancel', 'order'])[0][1] == 'orders'
    inv = Inventory(tmp_path, ['shop/svc.py'], ['shop/svc.py'], [], {'shop/svc.py': PyInfo('shop.svc', {'OrderService'})}, {}, {})
    data = dict(components=[dict(_component('svc'), files=['shop/svc.py'])])
    assert [hit[1] for hit in find_owners(data, inv, ['order'])] == ['svc']


def test_digest_captures_module_assignments_and_guarded_definitions_without_bodies(tmp_path):
    (tmp_path / 'api.py').write_text('''VERSION = 3
if VERSION:
    def guarded(value):
        secret_body = value + 9
        return secret_body
try:
    class Service:
        def run(self, value):
            return value
except ImportError:
    def fallback(value):
        return value
''', encoding='utf-8')
    output = '\n'.join(file_outline(tmp_path, 'api.py'))
    assert 'VERSION = 3' in output
    assert 'guarded(value)' in output and 'class Service' in output and 'fallback(value)' in output
    assert 'secret_body' not in output and 'return value' not in output


def test_find_ranks_the_component_that_defines_an_exact_symbol_first(tmp_path):
    inv = Inventory(tmp_path, ['owner.py'], ['owner.py'], [],
                    {'owner.py': PyInfo('owner', {'anchor_problems', 'Thing.anchor_problems'})}, {}, {})
    data = dict(components=[_component('descriptions', summary='anchor problems',
                                       responsibilities=['anchor problems']),
                            dict(_component('implementation'), files=['owner.py'])])
    for words in (['anchor_problems'], ['ANCHOR_PROBLEMS'], ['Thing.anchor_problems']):
        assert find_owners(data, inv, words)[0][1] == 'implementation'


def test_show_renders_the_model_tree_and_cheap_debt_rules(tmp_path, monkeypatch):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map import lint, proof

    def write(path, text):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    write('app.py', 'import store\ndef run(): return True\n')
    write('store.py', 'import app\ndef save(): return True\n')
    write('spare.py', 'def idle(): pass\n')
    write('tests/test_app.py', 'def test_run(): pass\n')
    contract = 'MODEL_ID = {mid!r}\nCOMPONENTS = {components!r}\nIMPLEMENTED_BY = {{"Run": "app.py:run"}}\ndef build_explorer(): pass\n'
    write('.flowguard/models/parent.py', contract.format(mid='parent', components=['app', 'store']) +
          'import child\nTESTED_BY = {"works": ["tests/test_app.py:test_run"]}\n')
    write('.flowguard/models/child.py', contract.format(mid='child', components=['app']))
    write('.flowguard/models/rooted.py', 'MODEL_ID="rooted"\nPARENT="system"\nIMPLEMENTED_BY={"Run":"app.py:run"}\ndef conformance(): pass\ndef build_explorer(): pass\n')
    data = dict(project='demo', layers=['entry', 'domain'], components=[
        dict(_component('app'), files=['app.py'], layer='entry'),
        dict(_component('store'), files=['store.py'], layer='domain'),
        dict(_component('spare'), files=['spare.py'], layer='domain')],
        flows=[dict(id='request', steps=['app:run'], model='.flowguard/models/parent.py')],
        accepted_debts=[dict(code='dependency_cycle', component='app', contains='store spare', reason='Legacy larger scope')])
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)

    def forbidden(*args, **kwargs):
        raise AssertionError('read must not run full lint or models')

    monkeypatch.setattr(lint, 'run_lint', forbidden)
    monkeypatch.setattr(proof, 'run_models', forbidden)
    text = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert text.startswith('# demo: system, 3 components, layers (top > bottom) entry > domain; architecture: 1 error(s), 1 accepted debt(s)')
    lines = text.splitlines()
    parent = next(line for line in lines if 'model parent:' in line)
    child = next(line for line in lines if 'model child:' in line)
    assert len(child) - len(child.lstrip()) == len(parent) - len(parent.lstrip()) + 2
    assert text.index('model rooted:') < text.index('## app')
    assert 'cycle (debt)' in text and 'cycle shrank' in text and 'layer_violation' in text
    assert '> flow request:' in text and 'model: parent' in text
    detail = render_show(tmp_path, data, inv, component='store', detail=False, budget=8000)
    assert 'model parent:' in detail and '(home app)' in detail
    assert 'works -> tests/test_app.py:test_run' in detail
    data['accepted_debts'].append(dict(code='dependency_cycle', members=['app', 'store'], reason='Exact scope'))
    assert '1 error(s), 2 accepted debt(s)' in render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)


def test_mermaid_export_has_one_node_per_component_and_model(tmp_path, capsys):
    import json
    import re
    import pytest
    from flowguard.__main__ import main
    from flowguard.map import cli
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.views import render_mermaid

    directory = tmp_path / '.flowguard/models'
    directory.mkdir(parents=True)
    (tmp_path / 'one.py').write_text('def run(): return True\n')
    (tmp_path / 'two.py').write_text('def run(): return False\n')
    (directory / 'parent.py').write_text('MODEL_ID="audit.current"\nCOMPONENTS=["a-b"]\nIMPLEMENTED_BY={"One":"one.py:run"}\ndef conformance(): pass\nimport child\ndef build_explorer(): pass\n')
    (directory / 'child.py').write_text('MODEL_ID="audit-current"\nCOMPONENTS=["a.b"]\nIMPLEMENTED_BY={"Run":"two.py:run"}\ndef conformance(): pass\ndef build_explorer(): pass\n')
    data = dict(schema='flowguard.map.v1', project='demo "quoted"', layers=['entry "tier"', 'empty layer'], components=[
        dict(_component('a-b'), files=['one.py'], layer='entry "tier"'),
        dict(_component('a.b'), files=['two.py'])])
    (tmp_path / '.flowguard/map.json').write_text(json.dumps(data))
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    text = render_mermaid(tmp_path, data, inv)
    assert text.startswith('flowchart TD\n')
    definitions = re.findall(r'^\s*([A-Za-z0-9_]+)(?:\[|\(\[)', text, re.M)
    assert len(definitions) == len(set(definitions)) == 5
    assert sum(name.startswith('c_') for name in definitions) == 2
    assert sum(name.startswith('m_') for name in definitions) == 2
    assert all(re.fullmatch('[A-Za-z0-9_]+', name) for name in definitions)
    assert text.count('subgraph ') == len(re.findall(r'^\s*end$', text, re.M)) == 3
    assert 'unlayered' in text
    assert 'audit.current' in text and 'audit-current' in text
    # Sanitized-name collisions cannot merge component or model nodes.
    models = re.findall(r'^\s*(m_\w+)\(\["model ([^"]+)<br/>[^\"]+"\]\)', text, re.M)
    model_ids = {label: node for node, label in models}
    assert f"{model_ids['audit.current']} --> {model_ids['audit-current']}" in text
    limited = render_mermaid(tmp_path, data, inv, component='a-b')
    assert 'a.b' not in limited and 'audit.current' in limited and 'audit-current' in limited
    assert limited.count('subgraph ') == 1
    assert 'empty layer' not in limited and 'unlayered' not in limited
    assert cli.main(['--root', str(tmp_path), 'show', '--mermaid', '--budget', '1']) == 0
    assert capsys.readouterr().out.startswith('flowchart TD\n')
    assert main(['read', '--root', str(tmp_path), '--mermaid', '--component', 'a-b']) == 0
    assert capsys.readouterr().out == limited + '\n'
    with pytest.raises(SystemExit) as error:
        main(['read', '--mermaid', '--find', 'run'])
    assert error.value.code == 2


    # A real component named system is distinct from the reserved root node.
    from flowguard.map.tree import build_tree
    (tmp_path / 'system_code.py').write_text('def run(): pass\n')
    data['components'].append(dict(_component('system'), files=['system_code.py']))
    (directory / 'local.py').write_text('MODEL_ID="local"\nCOMPONENTS=["system"]\nIMPLEMENTED_BY={"Run":"system_code.py:run"}\ndef conformance(): pass\ndef build_explorer(): pass\n')
    (directory / 'rooted.py').write_text('MODEL_ID="rooted"\nPARENT="system"\nIMPLEMENTED_BY={"Run":"one.py:run"}\ndef conformance(): pass\ndef build_explorer(): pass\n')
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    tree = build_tree(tmp_path, data, inv)
    assert {n.id for n in tree.models_for_component('system')} == {'local'}
    full = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert full.count('model local:') == full.count('model rooted:') == 1
    focused = render_mermaid(tmp_path, data, inv, component='system')
    assert 'model local' in focused and 'model rooted' not in focused


def test_read_component_prints_five_facets_for_component_and_models(tmp_path):
    import sys
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.views import render_mermaid

    def write(path, text):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    write('facet_app.py', 'raise RuntimeError("user code must not import")\ndef run(): return True\ndef side(): pass\n')
    write('store.py', 'def save(): pass\n')
    write('tests/test_app.py', '''test_not_a_function = True
def test_run(): pass
def test_extra(): pass
class A:
    def test_same(self): pass
class B:
    def test_same(self): pass
''')
    parent = '''"""Protect app behavior.
The second purpose line is not the purpose summary.
"""
raise RuntimeError("model must not import")
import facet_child
MODEL_ID = "parent"
COMPONENTS = ["app"]
IMPLEMENTED_BY = {"Run": "facet_app.py:run"}
NOT_MODELED = {"facet_app.py:side": "Separate integration check"}
TESTED_BY = {"a": ["tests/test_app.py:test_run", "tests/test_app.py:A.test_same"]}
RULES = [Invariant("a", "rule a", None), Invariant(name="b", description="rule b", predicate=None)]
def build_explorer(): raise RuntimeError("no exploration in read")
def broken_variants():
    metadata = {"not_a_variant": 1}
    return {"x": metadata, "y": {"also_not_a_variant": 2}}
'''
    child = '''raise RuntimeError("child must not import")
MODEL_ID = "child"
COMPONENTS = ["app"]
IMPLEMENTED_BY = {"Run": "facet_app.py:run"}
TESTED_BY = {"child_rule": ["tests/test_app.py:test_extra"], "ambiguous": ["tests/test_app.py:test_same"]}
def build_explorer(): raise RuntimeError("no exploration in read")
def broken_variants():
    metadata = {"not_a_variant": 1}
    return {name: metadata for name in ("dynamic",)}
'''
    write('.flowguard/models/facet_parent.py', parent)
    write('.flowguard/models/facet_child.py', child)
    data = dict(project='facets', layers=['entry', 'domain'], components=[
        dict(_component('app', summary='Handle app requests', responsibilities=['handle requests']),
             files=['facet_app.py'], tests=['tests/test_app.py'], layer='domain'),
        dict(_component('store', summary='Save data', responsibilities=['save data']), files=['store.py'], layer='entry')])
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    detail = render_show(tmp_path, data, inv, component='app', detail=False, budget=8000)
    for label in ('purpose:', 'rules:', 'known-bad:', 'code:', 'tests:'):
        assert sum(line.lstrip().startswith(label) for line in detail.splitlines()) == 3
    assert 'rules: a, b' in detail and 'known-bad: x, y' in detail and 'untested: b' in detail
    assert 'rules: ambiguous, child_rule (from TESTED_BY)' in detail
    assert 'known-bad: built at run time' in detail and 'not_a_variant' not in detail
    assert '4 functions, 3 bound' in detail and 'B.test_same' in detail
    assert 'test_not_a_function' not in detail
    assert 'not modeled: 1' in detail and 'Run -> facet_app.py:run' in detail
    assert 'app_imports_store' in detail and '(generated by the system model)' in detail
    assert 'test_run (not nested)' not in detail
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert ', 1 rules' in overview and 'model parent: Protect app behavior. (2 rules, 2 known-bad, 2 tests)' in overview
    diagram = render_mermaid(tmp_path, data, inv)
    assert 'app<br/>1 rules' in diagram and 'model parent<br/>2 rules, 2 known-bad' in diagram
    root = render_show(tmp_path, data, inv, component='system', detail=False, budget=8000)
    assert 'purpose: facets: 2 components' in root and 'no unaccepted dependency cycle' in root
    assert '4 functions, 3 bound' in root
    write('.flowguard/models/facet_child.py', child.replace(
        'TESTED_BY = {"child_rule": ["tests/test_app.py:test_extra"], "ambiguous": ["tests/test_app.py:test_same"]}\n', ''))
    unknown = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert '(? rules, ? known-bad, 0 tests)' in unknown
    assert not {'facet_app', 'facet_parent', 'facet_child', '_flowguard_model_facet_parent', '_flowguard_model_facet_child'} & set(sys.modules)


def test_target_show_keeps_current_character_budgets_without_running_checks(tmp_path, monkeypatch):
    from flowguard.map import check, lint, proof, target
    from flowguard.map.targetfile import Target

    data = dict(project='budget-demo', layers=['domain'], components=[
        dict(_component('alpha', summary='Original purpose', responsibilities=['serve alpha']), layer='domain'),
        dict(_component('beta', summary='Unchanged purpose', responsibilities=['serve beta']), layer='domain')],
        flows=[dict(id='request', summary='request to alpha', steps=['alpha:run'])])
    replacement = dict(data['components'][0], summary='A changed purpose ' + 'x' * 12000)
    replacement.pop('status')
    replacement.pop('fingerprint')
    draft = Target('explain alpha', dict(schema='flowguard.target.v1', goal='explain alpha',
        components=[replacement], flows=[], remove=[]), {}, {'component': set(), 'flow': set(), 'model': set()})

    def forbidden(*args, **kwargs):
        raise AssertionError('a target read must not execute models or checks')

    with monkeypatch.context() as scoped:
        for name in ('run_models', 'run_model', 'run_model_in_process', '_load'):
            scoped.setattr(proof, name, forbidden)
        scoped.setattr(check, 'run_check', forbidden)
        scoped.setattr(lint, 'run_lint', forbidden)
        scoped.setattr(target, 'check_target', forbidden)
        full = render_show(tmp_path, data, _inventory(tmp_path), component=None, detail=False,
                           budget=8000, target=draft)
        assert len(full) <= 8000 and 'target:' in full
        for budget in (0, 80, 260):
            bounded = render_show(tmp_path, data, _inventory(tmp_path), component=None, detail=False,
                                  budget=budget, target=draft)
            assert len(bounded) <= budget
            if budget == 260:
                assert 'truncated' in bounded


def test_target_snapshots_keep_their_own_inventory_classification(tmp_path, monkeypatch):
    from flowguard.map import check, lint, proof, target
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import component_graph
    from flowguard.map.targetfile import Target

    (tmp_path / 'test_reclassified.py').write_text('def test_live():\n    raise AssertionError("read executed a test")\n')
    (tmp_path / 'resource.txt').write_text('exact code resource\n')
    component = dict(_component('alpha', summary='Own an explicit code resource', responsibilities=['serve alpha']),
                     files=['test_reclassified.py', 'resource.txt'], tests=['test_reclassified.py'])
    data = dict(project='classification', components=[component], flows=[])
    replacement = {key: value for key, value in component.items() if key not in {'status', 'fingerprint'}}
    replacement['files'] = []
    draft = Target('use the Python file as a test', dict(schema='flowguard.target.v1', goal='use the Python file as a test',
        components=[replacement], flows=[], remove=[]), {}, {'component': set(), 'flow': set(), 'model': set()})
    inventory = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    component_graph(data, inventory)
    assert len(inventory.source) == 2 and not inventory.tests

    def forbidden(*args, **kwargs):
        raise AssertionError('a target read must not execute models or checks')

    with monkeypatch.context() as scoped:
        for name in ('run_models', 'run_model', 'run_model_in_process', '_load'):
            scoped.setattr(proof, name, forbidden)
        scoped.setattr(check, 'run_check', forbidden)
        scoped.setattr(lint, 'run_lint', forbidden)
        scoped.setattr(target, 'check_target', forbidden)
        detail = render_show(tmp_path, data, inventory, component='alpha', detail=True, budget=8000, target=draft)
        assert 'tests: 1 files: test_reclassified.py; 1 functions, 0 bound' in detail, detail
        assert 'was: 0 files: -; 0 functions, 0 bound' in detail, detail
        system = render_show(tmp_path, data, inventory, component='system', detail=True, budget=8000, target=draft)
        assert 'code: 1 components, 1 source files' in system, system
        assert 'was: 1 components, 2 source files' in system, system
        assert 'tests: 1 files: test_reclassified.py; 1 functions, 0 bound' in system, system
        assert 'was: 0 files: -; 0 functions, 0 bound' in system, system
        assert '(+0 ~1 -0 nodes)' in system, system
    assert len(inventory.source) == 1 and inventory.tests == ['test_reclassified.py']
