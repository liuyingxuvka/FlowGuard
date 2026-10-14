"""Finite checks for the human/agent map views, including strict output budgets."""
from pathlib import Path

from flowguard.map.inventory import Inventory
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
