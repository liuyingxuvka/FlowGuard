"""Finite checks for the human/agent map views, including strict output budgets."""
import json
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
    bounded = render_show(tmp_path, data, inv, component=None, detail=False, budget=390)
    assert len(bounded) <= 390
    assert '> flow checkout' in bounded and 'not shown:' in bounded
    for budget in (0, 20, 80, 100, 400):
        assert len(render_show(tmp_path, data, inv, component=None, detail=False, budget=budget)) <= budget


def test_find_responsibility_breaks_equal_summary_score(tmp_path):
    data = dict(components=[_component('alpha', summary='impact selection'),
                            _component('records', responsibilities=['impact selection'])])
    scores = find_owners(data, _inventory(tmp_path), ['impact', 'selection'])
    assert scores[0][1] == 'records'
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
    assert text.startswith('# demo: system, 3 components, layers (top > bottom) entry > domain; architecture: 1 error(s), 3 warning(s), 1 accepted debt(s); python -m flowguard read --review ranks them')
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
    assert '1 error(s), 3 warning(s), 2 accepted debt(s)' in render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)


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
class TestA:
    def test_same(self): pass
class TestB:
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
TESTED_BY = {"a": ["tests/test_app.py:test_run", "tests/test_app.py:TestA.test_same"]}
RULES = [Invariant("a", "rule a", None), Invariant(name="b", description="rule b", predicate=None)]
def build_explorer(): return Explorer(Workflow(()), (0,), (), invariants=RULES)
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
        assert sum(line.lstrip().startswith(label) for line in detail.splitlines() if line.startswith(' ')) == 3
    assert 'rules: a: rule a; b: rule b' in detail and 'known-bad: x, y' in detail and 'untested: b' in detail
    assert 'rules: not readable statically; python -m flowguard map models child prints them' in detail
    assert 'known-bad: x, y' in detail and 'not_a_variant' not in detail and 'from TESTED_BY' not in detail
    assert '4 functions, 3 bound' in detail and 'TestB.test_same' in detail
    assert 'test_not_a_function' not in detail
    assert 'not modeled: 1' in detail and 'Run -> facet_app.py:run' in detail
    assert 'app_imports_store' in detail and '(generated by the system model)' in detail
    assert 'test_run (not nested)' not in detail
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert ', 1 rules' in overview and 'model parent: Protect app behavior. (2 rules, 2 known-bad, 2 tests +2 in children)' in overview
    diagram = render_mermaid(tmp_path, data, inv)
    assert 'app<br/>1 rules' in diagram and 'model parent<br/>2 rules, 2 known-bad' in diagram
    root = render_show(tmp_path, data, inv, component='system', detail=False, budget=8000)
    assert 'purpose: facets: 2 components' in root and 'no unaccepted dependency cycle' in root
    assert '4 functions, 3 bound' in root
    write('.flowguard/models/facet_child.py', child.replace(
        'TESTED_BY = {"child_rule": ["tests/test_app.py:test_extra"], "ambiguous": ["tests/test_app.py:test_same"]}\n', ''))
    unknown = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert '(? rules, 1 known-bad, 0 tests)' in unknown
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


def _fg232_view_project(tmp_path):
    import json
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory

    marker = tmp_path / 'fg232-read-imported-code.txt'
    guarded = f'from pathlib import Path\nPath({str(marker)!r}).write_text("imported")\n'
    sources = {
        'view232_members.py': guarded + 'class Members:\n    def may_borrow(self): return True\n',
        'view232_catalog.py': guarded + 'class Catalog:\n' + ''.join(
            f'    def {name}(self): return True\n'
            for name in ('take', 'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta')),
        'view232_utils.py': guarded + 'LABEL = "module only"\n',
        'view232_loans.py': guarded + '''from view232_members import Members
import view232_catalog as stock
import view232_utils
class LoanService:
    def __init__(self, catalog=None):
        self.members = Members()
        self.catalog = catalog or stock.Catalog()
    def borrow(self):
        self.members.may_borrow()
        return self.catalog.take()
    def inventory(self):
        self.catalog.alpha()
        self.catalog.beta()
        self.catalog.gamma()
        self.catalog.delta()
        self.catalog.epsilon()
        self.catalog.zeta()
        self.catalog.eta()
        return self.catalog.alpha()
''',
        'view232_subject.py': guarded + '''def by_model(): return True
def by_scope(): return True
def by_test(): return True
def unexplained(): return True
class Ledger:
    def __init__(self): self.total = 0
    def record(self): self.total += 1
    def purge(self): self.total -= 1
''',
        'tests/test_subject.py': guarded + '''from view232_subject import by_test
def test_by_test(): assert by_test() is True
''',
        '.flowguard/models/borrow_contract.py': guarded + '''MODEL_ID = "borrow_contract"
COMPONENTS = ["loans"]
IMPLEMENTED_BY = {"Borrow": "view232_loans.py:LoanService.borrow"}
NOT_MODELED = {"view232_subject.py:by_scope": "Separate integration check"}
def build_explorer(): raise AssertionError("read explored a user model")
def conformance(): raise AssertionError("read replayed user code")
''',
        '.flowguard/models/subject_contract.py': guarded + '''MODEL_ID = "subject_contract"
COMPONENTS = ["subject"]
IMPLEMENTED_BY = {"ByModel": "view232_subject.py:by_model", "Record": "view232_subject.py:Ledger.record"}
def build_explorer(): raise AssertionError("read explored a user model")
def conformance(): raise AssertionError("read replayed user code")
''',
    }
    for relative, source in sources.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
    data = dict(schema='flowguard.map.v1', project='FG232 read fixture', layers=[], components=[
        dict(_component('loans', summary='Borrow items', responsibilities=['coordinate borrowing']),
             files=['view232_loans.py'], tests=[], models=['.flowguard/models/borrow_contract.py'],
             entrypoints=['view232_loans.py:LoanService.borrow'], depends_on=['catalog', 'members', 'utils']),
        dict(_component('catalog', summary='Store items', responsibilities=['store catalog']),
             files=['view232_catalog.py'], tests=[], models=[]),
        dict(_component('members', summary='Check members', responsibilities=['allow members']),
             files=['view232_members.py'], tests=[], models=[]),
        dict(_component('utils', summary='Labels', responsibilities=['label items']),
             files=['view232_utils.py'], tests=[], models=[]),
        dict(_component('subject', summary='Coverage examples', responsibilities=['process examples']),
             files=['view232_subject.py'], tests=['tests/test_subject.py'], models=['.flowguard/models/subject_contract.py'],
             entrypoints=[f'view232_subject.py:{name}' for name in ('by_model', 'by_scope', 'by_test', 'unexplained')]),
    ], flows=[
        dict(id='borrow', summary='Borrow an item', steps=['loans:LoanService.borrow', 'members:Members.may_borrow',
                                                        'catalog:Catalog.take'], model='.flowguard/models/borrow_contract.py'),
        dict(id='audit', summary='Audit catalog', steps=['loans:LoanService.inventory', 'catalog:Catalog.alpha']),
    ], accepted_debts=[])
    (tmp_path / '.flowguard/map.json').write_text(json.dumps(data), encoding='utf-8')
    return data, build_inventory(tmp_path, DEFAULT_IGNORE), marker


def _fg232_count_discovery(monkeypatch):
    from flowguard.map import views

    calls = []
    original = views.discover_inventory

    def _fg232_counted_discovery(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(views, 'discover_inventory', _fg232_counted_discovery)
    return calls


def test_read_component_names_the_symbols_used_on_each_edge(tmp_path, monkeypatch):
    import sys

    data, inv, marker = _fg232_view_project(tmp_path)
    calls = _fg232_count_discovery(monkeypatch)
    focused = render_show(tmp_path, data, inv, component='loans', detail=False, budget=8000)
    assert len(calls) == 1
    lines = [line.strip() for line in focused.splitlines()]
    assert ('uses catalog: Catalog, Catalog.alpha, Catalog.beta, Catalog.delta, '
            'Catalog.epsilon, Catalog.eta (+3 more)') in lines
    assert any(line.startswith('uses members: ') and 'Members.may_borrow' in line for line in lines)
    assert 'uses utils: (module import only)' in lines
    calls.clear()
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert len(calls) == 1
    assert 'uses: catalog, members, utils' in overview and 'uses catalog:' not in overview
    assert next(line for line in overview.splitlines() if '> flow audit:' in line).endswith(' (no model)')
    assert not marker.exists()
    assert not any(name.startswith('view232_') for name in sys.modules)


def test_mermaid_draws_dependencies_and_flows(tmp_path, monkeypatch):
    import json
    import sys
    from flowguard.map.targetfile import load_target
    from flowguard.map.views import render_mermaid

    data, inv, marker = _fg232_view_project(tmp_path)
    calls = _fg232_count_discovery(monkeypatch)
    diagram = render_mermaid(tmp_path, data, inv)
    assert len(calls) == 1
    assert 'c_loans -.-> c_catalog' in diagram and 'c_loans -.-> c_members' in diagram
    assert 'f_borrow["flow borrow<br/>model borrow_contract"]' in diagram
    assert 'f_audit["flow audit<br/>no model"]' in diagram
    assert 'f_borrow -->|"1"| c_loans' in diagram
    assert 'f_borrow -->|"2"| c_members' in diagram
    assert 'f_borrow -->|"3"| c_catalog' in diagram
    assert 'f_borrow --> m_borrow_contract' in diagram

    path = tmp_path / '.flowguard/target/map.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(schema='flowguard.target.v1', goal='plan a future audit', components=[],
        flows=[dict(id='future', summary='Future audit', steps=['loans:LoanService.inventory', 'catalog:Catalog.alpha'])],
        remove=[])), encoding='utf-8')
    target = load_target(tmp_path)
    assert target is not None
    calls.clear()
    merged = render_mermaid(tmp_path, data, inv, target=target)
    assert len(calls) == 1
    future = next(line for line in merged.splitlines() if 'flow future' in line)
    assert 'no model' in future
    assert 'f_future -->|"1"| c_loans' in merged and 'f_future -->|"2"| c_catalog' in merged
    calls.clear()
    current = render_mermaid(tmp_path, data, inv)
    assert len(calls) == 1 and current == diagram
    assert 'flow future' not in current
    assert not marker.exists()
    assert not any(name.startswith('view232_') for name in sys.modules)

    # A logical filename can retire its old identity and contain the replacement.
    # An active flow uses the new model; the removed flow keeps the old node.
    draft = json.loads(path.read_text(encoding='utf-8'))
    draft['remove'] = ['flow:borrow', 'model:borrow_contract']
    draft['flows'][0]['model'] = '.flowguard/models/borrow_contract.py'
    path.write_text(json.dumps(draft), encoding='utf-8')
    model = tmp_path / '.flowguard/target/models/borrow_contract.py'
    model.parent.mkdir(parents=True)
    original_model = (tmp_path / '.flowguard/models/borrow_contract.py').read_text(encoding='utf-8')
    assert original_model.count('MODEL_ID = "borrow_contract"') == 1
    model.write_text(original_model.replace('MODEL_ID = "borrow_contract"',
                                           'MODEL_ID = "borrow_contract_v2"'), encoding='utf-8')
    calls.clear()
    replacement = render_mermaid(tmp_path, data, inv, target=load_target(tmp_path))
    assert len(calls) == 1
    assert 'f_future["flow future<br/>model borrow_contract_v2"]' in replacement
    assert 'f_borrow["flow borrow<br/>model borrow_contract"]' in replacement
    edges = {line.strip() for line in replacement.splitlines()}
    assert 'f_future --> m_borrow_contract_v2' in edges
    assert 'f_future --> m_borrow_contract' not in edges
    assert 'f_borrow --> m_borrow_contract' in edges
    assert 'f_borrow --> m_borrow_contract_v2' not in edges
    assert 'class m_borrow_contract removed' in replacement
    assert not marker.exists()
    assert not any(name.startswith('view232_') for name in sys.modules)


def test_coverage_line_counts_explained_entrypoints(tmp_path, monkeypatch):
    import sys
    import pytest
    from flowguard.map import proof
    from flowguard.map.lint import run_lint

    data, inv, marker = _fg232_view_project(tmp_path)
    before = [(finding.level, finding.code, finding.component, finding.message)
              for finding in run_lint(tmp_path, data, inv)]
    calls = _fg232_count_discovery(monkeypatch)

    def _fg232_forbid_execution(*args, **kwargs):
        raise AssertionError('read must not execute a user model or pytest')

    with monkeypatch.context() as guard:
        for name in ('run_models', 'run_model', 'run_model_in_process', '_load'):
            guard.setattr(proof, name, _fg232_forbid_execution)
        guard.setattr(pytest, 'main', _fg232_forbid_execution)
        focused = render_show(tmp_path, data, inv, component='subject', detail=False, budget=8000)
        assert len(calls) == 1
        line = next(line for line in focused.splitlines()
                    if 'coverage: entrypoints 2 of 4 bound (model 1, test 1), 1 by reason, 0 unlisted; state writers 1 of 2 bound (model 1, test 0), 0 by reason;' in line)
        unexplained = line.partition('; unexplained: ')[2]
        assert 'view232_subject.py:unexplained' in unexplained and 'view232_subject.py:Ledger.purge' in unexplained
        assert 'view232_subject.py:by_model' not in unexplained and 'view232_subject.py:by_scope' not in unexplained
        assert 'view232_subject.py:by_test' not in unexplained and 'Ledger.__init__' not in unexplained
        calls.clear()
        overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
        assert len(calls) == 1
    assert ('coverage: entrypoints 3 of 5 bound (model 2, test 1), 1 by reason, 0 unlisted; state writers 1 of 2 bound (model 1, test 0), 0 by reason') in overview
    assert len(overview) <= 8000 and 'truncated' not in overview
    after = [(finding.level, finding.code, finding.component, finding.message)
             for finding in run_lint(tmp_path, data, inv)]
    assert after == before
    assert not marker.exists()
    assert not any(name.startswith('view232_') for name in sys.modules)


def _fg233_nested_project(tmp_path):
    import json
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory

    data, _inv, marker = _fg232_view_project(tmp_path)
    data['layers'] = ['records']
    for component in data['components']:
        component['layer'] = 'records'
        if component['id'] in {'catalog', 'loans'}:
            component['parent'] = 'records'
        if component['id'] == 'loans':
            component['tests'] = ['tests/test_parent233_loans.py']
    parent = dict(_component('records', summary='Inventory subsystem', responsibilities=['group inventory']),
                  layer='records', tests=[], models=[])
    data['components'].insert(0, parent)
    path = tmp_path / 'tests/test_parent233_loans.py'
    path.write_text('from view232_loans import LoanService\ndef test_borrow(): assert LoanService().borrow() is True\n',
                    encoding='utf-8')
    (tmp_path / '.flowguard/map.json').write_text(json.dumps(data), encoding='utf-8')
    return data, build_inventory(tmp_path, DEFAULT_IGNORE), marker


def test_component_parent_nests_and_rolls_up(tmp_path, capsys):
    import re
    import sys
    from flowguard.__main__ import main
    from flowguard.map.views import render_mermaid

    data, inv, marker = _fg233_nested_project(tmp_path)
    assert main(['map', '--root', str(tmp_path), 'check']) == 0
    output = capsys.readouterr().out
    assert '0 error(s)' in output and 'component_empty' not in output
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    headings = [line for line in overview.splitlines() if line.lstrip().startswith('## ')]
    ids = [line.lstrip().split()[1] for line in headings]
    parent_index = ids.index('records')
    assert set(ids[parent_index + 1:parent_index + 3]) == {'catalog', 'loans'}
    parent_line = headings[parent_index]
    assert parent_line.startswith('## records ')
    assert all(line.startswith('  ## ') for line in headings[parent_index + 1:parent_index + 3])
    child_paths = ('view232_catalog.py', 'view232_loans.py')
    expected_loc = sum(inv.loc[path] for path in child_paths)
    assert f'2 files/{expected_loc} loc' in parent_line and ', 3 rules' in parent_line
    assert ('coverage: entrypoints 3 of 5 bound (model 2, test 1), 1 by reason, 0 unlisted; '
            'state writers 1 of 2 bound (model 1, test 0), 0 by reason') in overview
    assert len(overview) <= 8000 and 'truncated' not in overview

    focused = render_show(tmp_path, data, inv, component='records', detail=False, budget=8000)
    assert '## records ' in focused and '  ## catalog ' in focused and '  ## loans ' in focused
    assert '## subject ' not in focused and 'model borrow_contract:' in focused
    parent_block = focused.split('## records ', 1)[1].split('  ## ', 1)[0]
    assert '1 functions' in parent_block and 'test_borrow' in parent_block
    diagram = render_mermaid(tmp_path, data, inv, component='records')
    assert 'subgraph sg_c_records["records"]' in diagram
    start = diagram.index('subgraph sg_c_records["records"]')
    # Both children are leaves, so the next subgraph end closes records.
    subsystem = re.split(r'\n\s*end(?:\n|$)', diagram[start:], maxsplit=1)[0]
    assert all(re.search(r'\bc_' + name + r'\[', subsystem) for name in ('records', 'catalog', 'loans'))
    assert not marker.exists()
    assert not any(name.startswith('view232_') for name in sys.modules)


def test_read_observes_hidden_names_missing_summary_and_model_counts(tmp_path):
    """Valid adversarial read inputs preserve names, budget, purpose and no-import promises."""
    import sys
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory

    def write(relative, source):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    write("alpha.py", "def run(): return True\n")
    write("beta.py", "def run(): return True\n")
    write("tests/test_alpha.py", "def test_run(): pass\n")
    write(".flowguard/models/read_probe.py", '''"""Explain read probe behavior."""
from pathlib import Path
Path(__file__).parents[2].joinpath("model_import.marker").write_text("imported")
MODEL_ID = "read_probe"
COMPONENTS = ["alpha"]
IMPLEMENTED_BY = {"Run": "alpha.py:run"}
TESTED_BY = {"works": ["tests/test_alpha.py:test_run"]}
RULES = [Invariant("works", "works", None), Invariant("stable", "stable", None)]
def build_explorer(): return Explorer(Workflow(()), (0,), (), invariants=RULES)
def broken_variants(): return {"one": None, "two": None}
''')
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False, write_cache=False)
    for budget, missing in ((8000, False), (8000, True), (420, True)):
        components = [dict(_component(cid, summary=("Serve " + cid) * 30), files=[cid + ".py"],
                           tests=["tests/test_alpha.py"] if cid == "alpha" else [], models=[])
                      for cid in ("alpha", "beta")]
        if missing:
            components[0].pop("summary")
        data = dict(project="read fixture", layers=[], components=components, flows=[])
        output = render_show(tmp_path, data, inv, component=None, detail=False, budget=budget)
        assert len(output) <= budget
        if budget == 420:
            notice = next(line for line in output.splitlines() if "truncated" in line and "not shown:" in line)
            assert "alpha" in notice.partition("not shown:")[2] and "beta" in notice.partition("not shown:")[2]
        else:
            assert "## alpha [" in output and "## beta [" in output and "truncated" not in output
            assert "model read_probe: Explain read probe behavior. (2 rules, 2 known-bad, 1 tests)" in output
            if missing:
                assert "(no summary yet)" in output.split("## alpha [", 1)[1].split("\n## beta [", 1)[0]
        assert not (tmp_path / "model_import.marker").exists()
        model_dir = (tmp_path / ".flowguard/models").resolve()
        assert not any(isinstance((file := vars(module).get("__file__")), str)
                       and Path(file).resolve().is_relative_to(model_dir)
                       for module in tuple(sys.modules.values()) if module is not None)


def test_read_component_never_hides_the_requested_component(tmp_path):
    """A component larger than the budget is shortened inside its block, never hidden."""
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory

    def write(relative, source):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    names = [f"test_case_{index:03d}" for index in range(300)]
    write("big.py", "def run(): return True\n")
    write("tests/test_big.py", "".join(f"def {name}(): pass\n" for name in names))
    bound = ", ".join(f'"tests/test_big.py:{name}"' for name in names)
    write(".flowguard/models/big_model.py", f'''"""Protect the big component."""
MODEL_ID = "big_model"
COMPONENTS = ["big"]
IMPLEMENTED_BY = {{"Run": "big.py:run"}}
TESTED_BY = {{"works": [{bound}]}}
RULES = [Invariant("works", "works", None)]
def build_explorer(): raise RuntimeError("read must not explore")
def broken_variants(): return {{"one": None}}
''')
    data = dict(project="big", layers=[], flows=[], components=[
        dict(_component("big", summary="Serve the big component " * 20, responsibilities=["serve"]),
             files=["big.py"], tests=["tests/test_big.py"])])
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False, write_cache=False)
    labels = ("purpose:", "rules:", "known-bad:", "code:", "tests:")
    for budget in (8000, 600):
        output = render_show(tmp_path, data, inv, component="big", detail=False, budget=budget)
        assert len(output) <= budget
        assert "## big" in output and "not shown: big" not in output
        assert all(any(line.lstrip().startswith(label) for line in output.splitlines()) for label in labels)
    assert "+297 more" in render_show(tmp_path, data, inv, component="big", detail=False, budget=8000)
    full = render_show(tmp_path, data, inv, component="big", detail=False, budget=200000)
    assert all(f"tests/test_big.py:{name}" in full for name in names[:3])
    assert "+297 more" in full and names[3] not in full.split("model big_model", 1)[1]


_PROBE_HEAD = '''"""Probe."""
from flowguard.core import Invariant
from flowguard.explorer import Explorer
from flowguard.workflow import Workflow
'''


def _static_project(tmp_path, models):
    """One component `app` anchored by the given models; read never imports them."""
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory

    for relative, source in {"app.py": "def run(): return True\n", "tests/test_app.py": "def test_run(): pass\n",
                             **models}.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    data = dict(project="static", layers=[], flows=[], components=[
        dict(_component("app", summary="Serve app", responsibilities=["serve"]), files=["app.py"],
             tests=["tests/test_app.py"])])
    return data, build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False, write_cache=False)


def _runtime_names(tmp_path):
    """Import the fixture models (only in the test) for their real names."""
    import importlib.util
    import sys
    models = tmp_path / ".flowguard/models"
    before, found = set(sys.modules), {}
    sys.path.insert(0, str(models))
    try:
        for path in sorted(models.glob("[!_]*.py")):
            spec = importlib.util.spec_from_file_location(f"_static_truth_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            found[module.MODEL_ID] = ({rule.name: rule.description for rule in module.build_explorer().invariants},
                                      sorted(module.broken_variants()))
    finally:
        sys.path.remove(str(models))
        for name in set(sys.modules) - before:
            sys.modules.pop(name, None)
    return found


def _assert_static_equals_runtime(tmp_path, data, inv):
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    detail = render_show(tmp_path, data, inv, component="app", detail=False, budget=8000)
    lines = detail.splitlines()
    for mid, (rules, bads) in _runtime_names(tmp_path).items():
        row = next(line for line in overview.splitlines() if line.strip().startswith(f"model {mid}: "))
        assert f"({len(rules)} rules, {len(bads)} known-bad," in row, row
        at = next(index for index, line in enumerate(lines) if line.strip().startswith(f"model {mid}: "))
        facets = {line.strip().partition(": ")[0]: line.strip().partition(": ")[2] for line in lines[at + 1:at + 6]}
        assert facets["rules"] == "; ".join(f"{name}: {text}" for name, text in sorted(rules.items()))
        assert facets["known-bad"] == ", ".join(bads)


_HELPER_SPLIT_MODELS = {
    ".flowguard/models/_probe_common.py": _PROBE_HEAD + (
        'def _ok(state, trace): return True\n'
        'A = Invariant("a_rule", "a holds", _ok)\nB = Invariant("b_rule", "b holds", _ok)\nBOTH = (A, B)\n'),
    ".flowguard/models/probe_child.py": _PROBE_HEAD + (
        'from _probe_common import A, B\nMODEL_ID = "probe_child"\nPARENT = "probe_parent"\n'
        'IMPLEMENTED_BY = {"Run": "app.py:run"}\nTESTED_BY = {"a_rule": ["tests/test_app.py:test_run"]}\n'
        'def _explorer():\n    return Explorer(Workflow(()), (0,), (), invariants=(A, B))\n'
        'def build_explorer(): return _explorer()\ndef broken_variants(): return {"child_bad": _explorer()}\n'),
    ".flowguard/models/probe_parent.py": _PROBE_HEAD + (
        'from _probe_common import BOTH\nMODEL_ID = "probe_parent"\nIMPLEMENTED_BY = {"Run": "app.py:run"}\n'
        'def _explorer():\n    return Explorer(Workflow(()), (0,), (), invariants=BOTH)\n'
        'def build_explorer(): return _explorer()\ndef broken_variants(): return {"parent_bad": _explorer()}\n'),
    ".flowguard/models/probe_wrapper.py": _PROBE_HEAD + (
        'MODEL_ID = "probe_wrapper"\nIMPLEMENTED_BY = {"Run": "app.py:run"}\n'
        'def _rule(name, text):\n    return Invariant(name, text, lambda state, trace: True)\n'
        'RULES = (_rule("x_rule", "x holds"), _rule("y_rule", "y holds"))\n'
        'def _explorer(kind=""):\n    return Explorer(Workflow(()), (0,), (), invariants=RULES)\n'
        'def build_explorer(): return _explorer()\n'
        'def broken_variants():\n    return {name: _explorer(name) for name in ("x_bad", "y_bad")}\n'),
}


def test_static_rules_follow_helpers_and_wrappers(tmp_path):
    data, inv = _static_project(tmp_path, _HELPER_SPLIT_MODELS)
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert "model probe_child: Probe. (2 rules, 1 known-bad, 1 tests)" in overview
    assert "model probe_parent: Probe. (2 rules, 1 known-bad, 0 tests +1 in children)" in overview
    assert "model probe_wrapper: Probe. (2 rules, 2 known-bad, 0 tests)" in overview
    _assert_static_equals_runtime(tmp_path, data, inv)


def test_parent_model_rolls_up_child_tests(tmp_path):
    data, inv = _static_project(tmp_path, _HELPER_SPLIT_MODELS)
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert "+1 in children" in next(line for line in overview.splitlines() if "model probe_parent:" in line)
    detail = render_show(tmp_path, data, inv, component="app", detail=False, budget=8000)
    lines = detail.splitlines()
    at = next(index for index, line in enumerate(lines) if "model probe_parent:" in line)
    tests = next(line for line in lines[at + 1:at + 7] if line.strip().startswith("tests:"))
    assert "children: 1 tests in probe_child" in tests


def test_rules_never_come_from_tested_by_keys(tmp_path):
    data, inv = _static_project(tmp_path, {".flowguard/models/opaque.py": '''"""Opaque rules."""
MODEL_ID = "opaque"
IMPLEMENTED_BY = {"Run": "app.py:run"}
TESTED_BY = {"keyed_rule": ["tests/test_app.py:test_run"]}
def build_explorer(): return make_explorer()
def broken_variants(): return make_variants()
'''})
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert "model opaque: Opaque rules. (? rules, ? known-bad, 1 tests)" in overview
    detail = render_show(tmp_path, data, inv, component="app", detail=False, budget=8000)
    assert "rules: not readable statically; python -m flowguard map models opaque prints them" in detail
    assert "from TESTED_BY" not in detail and "rules: keyed_rule" not in detail


def test_static_known_bad_follow_loops_and_tuple_targets(tmp_path):
    explorer = 'def _explorer(kind=""):\n    return Explorer(Workflow(()), (0,), (), invariants=RULES)\n'
    data, inv = _static_project(tmp_path, {
        ".flowguard/models/probe_tuple.py": _PROBE_HEAD + (
            'MODEL_ID = "probe_tuple"\nIMPLEMENTED_BY = {"Run": "app.py:run"}\n'
            'RULES = (Invariant("t_rule", "t holds", lambda state, trace: True),)\n' + explorer +
            'def build_explorer(): return _explorer()\n'
            'def broken_variants():\n'
            '    return {name: _explorer(kind) for name, kind in (("a_bad", "a"), ("b_bad", "b"))}\n'),
        ".flowguard/models/probe_loop.py": _PROBE_HEAD + (
            'MODEL_ID = "probe_loop"\nIMPLEMENTED_BY = {"Run": "app.py:run"}\n'
            'RULES = (Invariant("l_rule", "l holds", lambda state, trace: True),)\n'
            'FEATURES = {"one": ("x", "m_one", 1), "two": ("y", "m_two", 2)}\nEXPECTED = {"alpha": 1, "beta": 2}\n'
            + explorer + 'def build_explorer(): return _explorer()\n'
            'def broken_variants():\n    result = {}\n'
            '    for _, mutation, _ in FEATURES.values():\n        result[mutation] = _explorer(mutation)\n'
            '    for case in EXPECTED:\n        result[f"ignore_{case}"] = _explorer(case)\n    return result\n'),
        ".flowguard/models/probe_items.py": _PROBE_HEAD + (
            'MODEL_ID = "probe_items"\nIMPLEMENTED_BY = {"Run": "app.py:run"}\n'
            'RULES = (Invariant("i_rule", "i holds", lambda state, trace: True),)\n' + explorer +
            'def build_explorer(): return _explorer()\n'
            'def broken_variants():\n    bad = {"p_bad": 1, "q_bad": 2}\n'
            '    return {**{name: _explorer() for name, _ in bad.items()}, "r_bad": _explorer()}\n'),
    })
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert "model probe_loop: Probe. (1 rules, 4 known-bad, 0 tests)" in overview
    assert "model probe_tuple: Probe. (1 rules, 2 known-bad, 0 tests)" in overview
    assert "model probe_items: Probe. (1 rules, 3 known-bad, 0 tests)" in overview
    _assert_static_equals_runtime(tmp_path, data, inv)


def test_kit_model_facets_are_static_and_complete(tmp_path):
    """Feature-kit rules, known-bad and the defect/benign case table are read without importing."""
    import sys
    data, inv = _static_project(tmp_path, {".flowguard/models/probe_kit.py": '''"""Probe."""
from pathlib import Path
Path(__file__).parents[2].joinpath("model_import.marker").write_text("imported")
from flowguard.kit import Feature, feature_explorer, feature_variants
MODEL_ID = "probe_kit"
IMPLEMENTED_BY = {"Run": "app.py:run"}
FEATURES = (Feature("d_one", True, ("c1",), lambda plan: plan), Feature("d_two", True, ("c2",), lambda plan: plan),
            Feature("b_one", False, (), lambda plan: plan))
def build_explorer(): return feature_explorer(FEATURES, codes="first")
def broken_variants(): return feature_variants(FEATURES, codes="first")
'''})
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    detail = render_show(tmp_path, data, inv, component="app", detail=False, budget=8000)
    assert not (tmp_path / "model_import.marker").exists()
    assert not any(isinstance((file := vars(module).get("__file__")), str) and "probe_kit" in file
                   for module in tuple(sys.modules.values()) if module is not None)
    assert "model probe_kit: Probe. (4 rules, 3 known-bad, 0 tests)" in overview
    assert "cases: 2 defects (d_one, d_two), 1 benign (b_one)" in detail
    assert "cases:" not in overview
    (tmp_path / "model_import.marker").unlink(missing_ok=True)
    _assert_kit_matches_runtime(tmp_path, detail)


def _assert_kit_matches_runtime(tmp_path, detail):
    lines = detail.splitlines()
    for mid, (rules, bads) in _runtime_names(tmp_path).items():
        at = next(index for index, line in enumerate(lines) if line.strip().startswith(f"model {mid}: "))
        facets = {line.strip().partition(": ")[0]: line.strip().partition(": ")[2] for line in lines[at + 1:at + 6]}
        shown = [item for item in facets["rules"].split("; ") if not item.startswith("cases: ")]
        assert shown == [f"{name}: {text}" for name, text in sorted(rules.items())]
        assert facets["known-bad"] == ", ".join(bads)


def test_static_facets_match_flowguard_self_models():
    """Every FlowGuard model reads statically the same rule and known-bad names it builds at run time."""
    import importlib.util
    import sys
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.facets import model_facets
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.tree import build_tree

    root = Path(__file__).resolve().parents[1]
    data = load_map(root)
    tree = build_tree(root, data, build_inventory(root, DEFAULT_IGNORE, with_bodies=False, write_cache=False))
    models = str(root / ".flowguard/models")
    added = models not in sys.path
    if added:
        sys.path.append(models)
    try:
        checked = 0
        for mid, node in sorted(tree.nodes.items()):
            if not node.path.startswith(".flowguard/models/"):
                continue
            facets = model_facets(root, node)
            name = f"_flowguard_model_{Path(node.path).stem}"
            spec = importlib.util.spec_from_file_location(name, root / node.path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            assert facets.rules_source == "explorer", mid
            assert list(facets.rules) == sorted(rule.name for rule in module.build_explorer().invariants), mid
            assert list(facets.known_bad) == sorted(module.broken_variants()), mid
            checked += 1
        assert checked >= 13
    finally:
        if added:
            sys.path.remove(models)


def test_read_orders_components_by_layer(tmp_path):
    """Top-level components are listed top-down by layer, keeping map order inside a layer."""
    data = dict(project="layers", layers=["upper", "middle", "lower"], flows=[], components=[
        dict(_component("low", summary="Low"), layer="lower"),
        dict(_component("mid", summary="Mid"), layer="middle"),
        dict(_component("low_child", summary="Child"), layer="lower", parent="low"),
        dict(_component("top", summary="Top"), layer="upper")])
    output = render_show(tmp_path, data, _inventory(tmp_path), component=None, detail=False, budget=8000)
    headings = [line.strip().split(" [", 1)[0][3:] for line in output.splitlines() if line.strip().startswith("## ")]
    assert headings == ["top", "mid", "low", "low_child"], output
    assert "\n\n\n" not in output


def test_read_component_lists_the_rules_it_relies_on(tmp_path):
    """cli calls loans' LoanService.borrow, the anchor of model lending: cli relies on lending's rules."""
    from test_flowguard_target import shelf_project
    from flowguard.map.cli import _context

    root = shelf_project(tmp_path)
    data, inv = _context(root)
    cli = render_show(root, data, inv, component="cli", detail=False, budget=8000)
    assert "relies on: model lending (limit_respected, never_over_lent) via loans: LoanService.borrow" in cli, cli
    loans = render_show(root, data, inv, component="loans", detail=False, budget=8000)
    assert "relies on: model lending" not in loans


def test_read_component_lists_its_flows_and_their_rules(tmp_path):
    """Every component on a flow shows the flow, its step number, the flow's model and its rules."""
    from test_flowguard_target import shelf_project
    from flowguard.map.cli import _context

    root = shelf_project(tmp_path)
    data = json.loads((root / ".flowguard/map.json").read_text(encoding="utf-8"))
    data["flows"][0]["model"] = ".flowguard/models/lending.py"
    (root / ".flowguard/map.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    data, inv = _context(root)
    members = render_show(root, data, inv, component="members", detail=False, budget=8000)
    assert "flows: borrow (step 3 of 4; model lending: limit_respected, never_over_lent)" in members, members


def _coverage_project(tmp_path):
    """Four entrypoints: model-anchored, named by a test, NOT_MODELED, and unexplained."""
    write = lambda relative, text: (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True) or \
        (tmp_path / relative).write_text(text, encoding="utf-8")
    write("app.py", "def run(): return True\ndef tested(): return True\ndef skipped(): return True\ndef loose(): return True\n")
    write("tests/test_app.py", "from app import run, tested\n\ndef test_tested_function():\n    assert tested()\n\n"
          "def test_unbound_run():\n    assert run()\n")
    write(".flowguard/models/app_model.py", '''"""Protect the app."""
MODEL_ID = "app_model"
IMPLEMENTED_BY = {"Run": "app.py:run"}
NOT_MODELED = {"app.py:skipped": "a deliberate no-op kept for the command line"}
TESTED_BY = {}
RULES = (Invariant("works", "works", None),)
def build_explorer(): return Explorer(Workflow(()), (0,), (), invariants=RULES)
def broken_variants(): return {"bad": None}
''')
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    data = dict(project="coverage", layers=[], flows=[], components=[
        dict(_component("app", summary="Serve app", responsibilities=["serve"]), files=["app.py"],
             tests=["tests/test_app.py"], entrypoints=["app.py:run", "app.py:tested", "app.py:skipped", "app.py:loose"])])
    return data, build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False, write_cache=False)


def test_coverage_line_counts_by_source(tmp_path):
    data, inv = _coverage_project(tmp_path)
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert overview.splitlines()[1].startswith("coverage: entrypoints 2 of 4 bound (model 1, test 1), 1 by reason, 0 unlisted; "
                                               "state writers 0 of 0 bound (model 0, test 0), 0 by reason"), overview
    detail = render_show(tmp_path, data, inv, component="app", detail=False, budget=8000)
    code = next(line for line in detail.splitlines() if line.strip().startswith("code:"))
    assert "unexplained: app.py:loose" in code and "(explain: add it to a model's IMPLEMENTED_BY" in code, code


def test_tests_facet_lists_bindable_tests(tmp_path):
    data, inv = _coverage_project(tmp_path)
    detail = render_show(tmp_path, data, inv, component="app", detail=False, budget=8000)
    tests = next(line for line in detail.splitlines() if line.startswith(" ") and line.strip().startswith("tests:") and "functions" in line)
    assert "bindable: tests/test_app.py:test_unbound_run -> model app_model (mentions run)" in tests, tests


def _review_project(tmp_path, *, clean=False):
    """A cycle (ERROR), a hub (used by 3, uses 3, 7 duties), an unexplained writer, a flow with no model."""
    files = {
        'hub.py': 'import lib1\nimport lib2\nimport lib3\ndef run(): return lib1.run() and lib2.run() and lib3.run()\n',
        'lib1.py': 'class Box:\n    def put(self, value):\n        self.value = value\ndef run(): return Box()\n',
        'lib2.py': 'def run(): return True\n', 'lib3.py': 'def run(): return True\n',
        'u1.py': 'import hub\ndef run(): return hub.run()\n', 'u2.py': 'import hub\ndef run(): return hub.run()\n',
        'u3.py': 'import hub\ndef run(): return hub.run()\n',
        'app.py': 'import store\ndef run(): return store.save()\n', 'store.py': 'import app\ndef save(): return True\n',
        '.flowguard/models/probe.py': ('from pathlib import Path\n'
                                       'Path(__file__).parents[2].joinpath("model_import.marker").write_text("imported")\n'
                                       'MODEL_ID = "probe"\nCOMPONENTS = ["lib2"]\nIMPLEMENTED_BY = {"Run": "lib2.py:run"}\n'
                                       'def build_explorer(): pass\ndef broken_variants(): return {"bad": None}\n'),
    }
    if clean:
        files = {'app.py': 'import store\ndef run(): return store.save()\n', 'store.py': 'def save(): return True\n',
                 'tests/test_app.py': 'from app import run\ndef test_run(): assert run()\n'}
    for path, text in files.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text)
    if clean:
        components = [dict(_component('app', summary='Serve app'), files=['app.py'], depends_on=['store'],
                           tests=['tests/test_app.py'], layer='entry'),
                      dict(_component('store', summary='Store'), files=['store.py'], tests=['tests/test_app.py'], layer='domain')]
        return dict(project='clean', layers=['entry', 'domain'], components=components)
    duties = [f'serve hub duty {word}' for word in ('one', 'two', 'three', 'four', 'five', 'six', 'seven')]
    components = [dict(_component(cid), files=[cid + '.py']) for cid in ('app', 'store', 'hub', 'lib1', 'lib2', 'lib3', 'u1', 'u2', 'u3')]
    by_id = {c['id']: c for c in components}
    by_id['app']['depends_on'], by_id['store']['depends_on'] = ['store'], ['app']
    by_id['hub']['depends_on'], by_id['hub']['responsibilities'] = ['lib1', 'lib2', 'lib3'], duties
    for cid in ('u1', 'u2', 'u3'):
        by_id[cid]['depends_on'] = ['hub']
    return dict(project='demo', components=components, flows=[dict(id='trip', steps=['u1:run', 'hub:run'])])


def test_review_ranks_defects_and_states_true_strengths(tmp_path):
    import sys
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.review import render_review

    data = _review_project(tmp_path)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False, write_cache=False)
    text = render_review(tmp_path, data, inv, budget=8000)
    lines = text.splitlines()
    assert lines[0].startswith('# demo review: 9 components, 2 models (with system), 1 flows; architecture: 1 error(s)')
    strengths = next(line for line in lines if line.startswith('strengths: '))
    assert 'no dependency cycles' not in strengths and 'every flow has a model' not in strengths
    assert 'every state writer explained' not in strengths and 'no layer violations' in strengths
    assert any(line.startswith('  ERROR dependency_cycle x1: ') for line in lines)
    steps = lines[lines.index('optimise next:') + 1:]
    numbered = [line for line in steps if line.lstrip()[:2].rstrip('.').isdigit()]
    assert numbered[0].startswith('  1. fix dependency_cycle ')
    split = next(index for index, line in enumerate(numbered) if 'split hub: hub (used by 3, uses 3, 7 duties' in line)
    explain = next(index for index, line in enumerate(numbered) if 'explain lib1' in line)
    assert split < explain
    assert all('references/' in line or 'python -m flowguard' in line for line in numbered)
    assert steps[-1].startswith('declined: ')
    assert len(text) <= 8000
    assert not (tmp_path / 'model_import.marker').exists()
    assert not any(getattr(module, '__file__', None) and str(tmp_path) in str(module.__file__)
                   for module in list(sys.modules.values()))
    small = render_review(tmp_path, data, inv, budget=1500)
    assert len(small) <= 1500 and 'more components (python -m flowguard read)' in small and 'optimise next:' in small


def test_review_of_a_clean_project_lists_its_strengths(tmp_path):
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.review import render_review

    data = _review_project(tmp_path, clean=True)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False, write_cache=False)
    text = render_review(tmp_path, data, inv)
    assert 'strengths: no dependency cycles; no layer violations' in text
    assert 'no accepted debts' in text and 'debts:' not in text
    steps = text.split('optimise next:', 1)[1]
    assert steps.startswith(' nothing to rank') or not any(word in steps for word in (' fix ', ' split '))


def test_find_matches_word_forms(tmp_path):
    data = dict(components=[_component('timed', responsibilities=['rejects expired tokens']),
                            _component('signing', responsibilities=['rotation of signing keys']),
                            _component('orders', responsibilities=['promotion of orders'])])
    inv = _inventory(tmp_path)
    assert find_owners(data, inv, ['expire'])[0][1] == 'timed'
    assert find_owners(data, inv, ['rotate'])[0][1] == 'signing'
    assert find_owners(data, inv, ['rotating'])[0][1] == 'signing'
    assert find_owners(data, inv, ['promote'])[0][1] == 'orders'
    assert find_owners(data, inv, ['order'])[0][1] == 'orders'
    from flowguard.map.views import _stem
    assert len({_stem(word) for word in ('expire', 'expired', 'expires')}) == 1
    assert len({_stem(word) for word in ('rotate', 'rotation', 'rotating')}) == 1
    assert _stem('order') == _stem('orders') and _stem('promote') == _stem('promotion')


def test_find_miss_names_the_closest_owners(tmp_path, capsys):
    import json
    from flowguard.map import cli

    (tmp_path / '.flowguard').mkdir()
    components = [dict(_component('timed', responsibilities=['rejects expired tokens']), files=['timed.py']),
                  dict(_component('signing', responsibilities=['sign payloads']), files=['signing.py'])]
    for cid in ('timed', 'signing'):
        (tmp_path / f'{cid}.py').write_text('def run(): return True\n')
    (tmp_path / '.flowguard/map.json').write_text(json.dumps({'schema': 'flowguard.map.v1', 'project': 'p',
                                                             'components': components}))
    code = cli.main(['--root', str(tmp_path), 'find', 'expiry'])
    output = capsys.readouterr().out
    assert code == 1 and output.startswith('no existing owner found;'), output
    assert 'closest owners (check these before creating a new component):' in output
    assert '  timed: rejects expired tokens' in output and 'signing' not in output


def test_digest_lists_overloads_once(tmp_path):
    from flowguard.map.views import file_outline

    (tmp_path / 'serializer.py').write_text(
        'from typing import overload\nimport typing\n\n\nclass Serializer:\n'
        '    @overload\n    def __init__(self, key: str) -> None: ...\n'
        '    @typing.overload\n    def __init__(self, key: bytes) -> None: ...\n'
        '    def __init__(self, key):\n        self.key = key\n\n\n'
        '@overload\ndef dumps(value: int) -> str: ...\n@overload\ndef dumps(value: str) -> str: ...\n'
        'def dumps(value):\n    return str(value)\n')
    outline = file_outline(tmp_path, 'serializer.py')
    inits = [line for line in outline if '.__init__(' in line]
    dumps = [line for line in outline if 'def dumps(' in line]
    assert len(inits) == 1 and inits[0].endswith(' (+2 overloads)'), outline
    assert len(dumps) == 1 and dumps[0].endswith(' (+2 overloads)'), outline


def test_read_header_counts_debts_that_cover_size_warnings(tmp_path):
    busy = _component('busy', responsibilities=[f'duty {n}' for n in range(9)], summary='Busy')
    busy['tests'] = ['tests/test_busy.py']
    data = dict(project='demo', components=[busy], flows=[])
    inv = _inventory(tmp_path)
    head = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000).splitlines()[0]
    assert '1 warning(s), 0 accepted debt(s)' in head, head
    data['accepted_debts'] = [dict(code='too_many_responsibilities', component='busy', reason='one table of duties')]
    head = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000).splitlines()[0]
    assert '0 warning(s), 1 accepted debt(s)' in head, head


def test_find_bonus_needs_the_joined_query():
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map, ignore_patterns
    from flowguard.map.views import defined_symbols
    root = Path(__file__).resolve().parents[1]
    data = load_map(root)
    inv = build_inventory(root, ignore_patterns(data), with_bodies=False, write_cache=False)
    queries = {"promote target": "map-target", "target check environment error blocks promotion": "map-target", "find_owners": "map-read"}
    for query, cid in queries.items():
        assert find_owners(data, inv, query.split())[0][1] == cid
    owner = next(c for c in data["components"] if c["id"] == "map-target")
    for query in ("promote target", "promote_target", "PromoteTarget"):
        assert any(name == "promote_target" for name, _ in defined_symbols(owner, inv, query.split()))
    generic = next(c for c in data["components"] if c["id"] == "map-file")
    assert not defined_symbols(generic, inv, ["promote", "target"])


def _quiet_fixture(name):
    import runpy
    directory = Path(__file__).parents[1] / ".flowguard/models"
    path = directory / (name + ".py")
    if not path.exists(): path = directory.parent / "target/models" / path.name
    return runpy.run_path(str(path))


def test_closing_debt_hides_one_suggestion(tmp_path):
    from flowguard.map.review import render_review
    from flowguard.map.lint import run_lint
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    data = _quiet_fixture("read_review")["make_fixture"](tmp_path)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    before = render_review(tmp_path, {**data, "accepted_debts": []}, inv)
    assert "model app:" in before
    after = render_review(tmp_path, data, inv)
    assert "model app:" not in after
    assert after.splitlines()[-1] == "declined: 1 (accepted debts; 0 no longer arise)"
    assert not any(f.code == "debt_stale" for f in run_lint(tmp_path, data, inv))
    data["components"][0].pop("state")
    assert "declined: 1 (accepted debts; 1 no longer arise)" in render_review(tmp_path, data, inv)


def test_coverage_counts_calls_not_words(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    data = _quiet_fixture("read_show")["make_fixture"](tmp_path)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    text = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert text.splitlines()[1] == "coverage: entrypoints 2 of 4 bound (model 1, test 1), 1 by reason, 0 unlisted; state writers 0 of 0 bound (model 0, test 0), 0 by reason"
    assert "unexplained: app.py:mentioned" in render_show(tmp_path, data, inv, component="app", detail=False, budget=8000)


def test_tests_line_counts_bound_calling_and_neither(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.testtree import test_functions, resolve_test_anchor, test_calls
    data = _quiet_fixture("read_show")["make_fixture"](tmp_path)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    path = tmp_path / "tests/test_app.py"
    functions = test_functions(path.read_text())
    assert set(functions) == {"test_bound", "test_call", "test_words", "Suite.test_method"}
    assert resolve_test_anchor(path, "test_method[x]") == "Suite.test_method"
    assert resolve_test_anchor(path, "test_bound") == "test_bound"
    calls = test_calls("tests/test_app.py", path.read_text(), inv)
    assert calls["test_words"] == set()
    assert "app.py:modeled" in calls["Suite.test_method"]
    from flowguard.map.inventory import PyInfo
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg/__init__.py").write_text("# export fixture; never imported\n")
    inv.py["pkg/__init__.py"] = PyInfo("pkg", lazy_exports={"modeled": "app"})
    inv.mod_to_path["pkg"] = "pkg/__init__.py"
    aliases = "from pkg import modeled as public\nimport pkg as p\ndef test_public(): assert public() and p.modeled()\n"
    assert test_calls("tests/test_app.py", aliases, inv)["test_public"] == {"app.py:modeled"}
    (tmp_path / "app.py").write_text((tmp_path / "app.py").read_text() + "\nclass Service:\n    def touch(self): return True\ndef wrapper():\n    def hidden(): return True\n    return None\n")
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    constructors = "from app import Service, wrapper\ndef test_construct(): Service(); wrapper()\n"
    values = test_calls("tests/test_app.py", constructors, inv)["test_construct"]
    assert {"app.py:Service", "app.py:Service.touch", "app.py:wrapper"} <= values
    assert "app.py:wrapper.hidden" not in values
    helpers = "from app import modeled as f\nimport app as m\ndef helper(): return f()\ndef deeper(): return helper()\ndef test_helper(): assert helper()\ndef test_deep(): assert deeper()\n"
    calls = test_calls("tests/test_app.py", helpers, inv)
    assert calls["test_helper"] == {"app.py:modeled"}
    assert calls["test_deep"] == set()
    extra = "import unittest\nclass Base(unittest.IsolatedAsyncioTestCase): pass\nclass AsyncSuite(Base):\n    async def test_async(self): pass\nclass Helper:\n    def test_fake(self): pass\nasync def test_top(): pass\n"
    assert set(test_functions(extra)) == {"AsyncSuite.test_async", "test_top"}
    text = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert text.splitlines()[2] == "tests: 4 test functions; 1 bound to a model (TESTED_BY), 2 call a model's code, 1 neither"


def test_read_line_four_counts_models(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    data = _quiet_fixture("read_show")["make_fixture"](tmp_path)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    assert render_show(tmp_path, data, inv, component=None, detail=False, budget=8000).splitlines()[3] == "models: 1 (process 0)"


def test_unbound_models_debt_closes_only_models_no_test_calls(tmp_path):
    from flowguard.map.review import render_review
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    data = _quiet_fixture("read_show")["make_fixture"](tmp_path)
    path = tmp_path / ".flowguard/models/probe.py"
    source = path.read_text(); source = source[:source.index("TESTED_BY=")] + "TESTED_BY={}\ndef build_explorer(): pass\n"
    path.write_text(source)
    data["accepted_debts"] = [dict(code="unbound_models", component="probe", reason="abstract parent; its children have tests")]
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    text = render_review(tmp_path, data, inv)
    assert "bind tests probe: 3 test functions call its code" in text, text
    from flowguard.map.lint import run_lint
    assert any(f.code == "unbound_models" and f.level == "warn" for f in run_lint(tmp_path, data, inv))
    test = tmp_path / "tests/test_app.py"; test.write_text("def test_unrelated(): assert True\n")
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    text = render_review(tmp_path, data, inv)
    assert "bind tests probe:" not in text and "declined: 1 (accepted debts; 0 no longer arise)" in text
    assert not any(f.code == "unbound_models" and f.level == "warn" for f in run_lint(tmp_path, data, inv))


def test_read_component_prints_one_port_line_per_model(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    import runpy
    directory = Path(__file__).parents[1] / ".flowguard/models"
    path = directory / "_target_fixture.py"
    if not path.exists(): path = directory.parent / "target/models/_target_fixture.py"
    helper = runpy.run_path(str(path))
    data = helper["make_port_project"](tmp_path)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    text = render_show(tmp_path, data, inv, component="cli", detail=False, budget=8000)
    ports = [line for line in text.splitlines() if line.strip().startswith("port:")]
    models = [line for line in text.splitlines() if line.strip().startswith("model ")]
    assert len(ports) == len(models) == 2 and all(len(line) <= 200 for line in ports), text
    assert any("out answer=lent|refused -> desk.answer" in line for line in ports), text
    path = tmp_path / ".flowguard/models/lending.py"
    path.write_text(path.read_text().replace('OUTPUTS = {"answer":("lent","refused")}', ''))
    text = render_show(tmp_path, data, inv, component="cli", detail=False, budget=8000)
    assert "out ?" in text
