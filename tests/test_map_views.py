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
    write('.flowguard/models/rooted.py', 'MODEL_ID="rooted"\nPARENT="system"\nDESIGN_ONLY="Abstract root probe"\ndef build_explorer(): pass\n')
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
    parent = next(line for line in lines if 'model parent ' in line)
    child = next(line for line in lines if 'model child ' in line)
    assert len(child) - len(child.lstrip()) == len(parent) - len(parent.lstrip()) + 2
    assert text.index('model rooted ') < text.index('## app')
    assert 'cycle (debt)' in text and 'cycle shrank' in text and 'layer_violation' in text
    assert '> flow request:' in text and 'model: parent' in text
    detail = render_show(tmp_path, data, inv, component='store', detail=False, budget=8000)
    assert 'model parent ' in detail and '(home app)' in detail
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
    (directory / 'parent.py').write_text('MODEL_ID="audit.current"\nCOMPONENTS=["a-b"]\nDESIGN_ONLY="Diagram probe"\nimport child\ndef build_explorer(): pass\n')
    (directory / 'child.py').write_text('MODEL_ID="audit-current"\nCOMPONENTS=["a.b"]\nDESIGN_ONLY="Diagram probe"\ndef build_explorer(): pass\n')
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
    models = re.findall(r'^\s*(m_\w+)\(\["model ([^"]+)"\]\)', text, re.M)
    model_ids = {label: node for node, label in models}
    assert f"{model_ids['audit.current']} --> {model_ids['audit-current']}" in text
    limited = render_mermaid(tmp_path, data, inv, component='a-b')
    assert 'a.b' not in limited and 'audit.current' in limited and 'audit-current' in limited
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
    (directory / 'local.py').write_text('MODEL_ID="local"\nCOMPONENTS=["system"]\nDESIGN_ONLY="Component probe"\ndef build_explorer(): pass\n')
    (directory / 'rooted.py').write_text('MODEL_ID="rooted"\nPARENT="system"\nDESIGN_ONLY="Root probe"\ndef build_explorer(): pass\n')
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    tree = build_tree(tmp_path, data, inv)
    assert {n.id for n in tree.models_for_component('system')} == {'local'}
    full = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert full.count('model local ') == full.count('model rooted ') == 1
    focused = render_mermaid(tmp_path, data, inv, component='system')
    assert 'model local' in focused and 'model rooted' not in focused
