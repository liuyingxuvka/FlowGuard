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
