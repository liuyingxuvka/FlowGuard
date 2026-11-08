"""Real source bindings and positive/negative controls for code-owned anchors."""
from contextlib import closing, contextmanager
from dataclasses import replace
from decimal import Decimal
import importlib
from pathlib import Path
import sys
import types

import pytest

from flowguard.intent import anchors as A
from flowguard.intent.cells import Raised
from flowguard.structure import build


def source(tmp_path, text, *, name='decision'):
    root = tmp_path / name
    root.mkdir()
    module = 'decision_' + name + '_' + str(abs(hash(str(tmp_path))))
    file = module + '.py'
    (root / file).write_text(text, encoding='utf-8')
    index = A.collect_sources(root, [(file, module)])
    return root, index


@contextmanager
def session(root):
    # K1's worker-independent test seam, preserving the production ContextVar
    # boundary while the sole calibration backend is integrated by its owner.
    token = A._SESSION.set(root.resolve())
    try:
        yield
    finally:
        A._SESSION.reset(token)


GOOD = '''# flowguard: sensor eligibility(age: years, active: 1) -> allowed: bool
def eligible(age: int, active: bool) -> bool:
    return age >= 18 and active
'''


def test_single_map_fact_path_and_warm_comment_identity(tmp_path):
    root, direct = source(tmp_path, GOOD)
    with closing(build(root, tmp_path / 'map.sqlite', workers=1)) as graph:
        indexed = A.collect(graph)
        assert indexed == direct
        assert indexed.status == 'ok'
        anchor, = indexed.named('eligibility')
        assert anchor.kind == 'sensor' and anchor.parameters[0].source_type == 'int'
        assert (anchor.line, anchor.target_line, anchor.output) == (1, 2, 'allowed')
        assert graph.functions()[anchor.target]['qual'] == 'eligible'
    path = root / anchor.file
    path.write_text(GOOD.replace('years', '?'))
    with closing(build(root, tmp_path / 'map.sqlite', workers=1)) as graph:
        assert A.collect(graph).status == 'grey'
        assert graph.stats['parsed'] == 1


def test_sensor_event_states_and_test_roles_share_index(tmp_path):
    text = '''# flowguard: states Order.status = pending | paid
class Order:
    status: str
    def __init__(self): self.status = 'pending'

# flowguard: event saved(document: str)
def save(document: str) -> None: pass

# flowguard: sensor permit(active: 1) -> allowed: bool
def check(active: bool) -> bool: return active
'''
    root, index = source(tmp_path, text)
    assert index.status == 'ok'
    assert {a.kind for a in index.entries} == {'sensor', 'states', 'event'}
    state, = index.named('Order.status')
    assert state.values == ('pending', 'paid')
    event, = index.named('saved')
    test = A.collect_sources(root, [(event.file, event.module, True)])
    assert {a.source_role for a in test.entries} == {'test'}


@pytest.mark.parametrize('old,new,code', [
    ('age: years, active: 1', 'age: years', 'signature'),
    ('age: years, active: 1', 'aged: years, active: 1', 'signature'),
    ('allowed: bool', 'allowed: str', 'return'),
    ('age: years', 'age: ?', 'unit-missing'),
    ('age: int', 'age', 'type-missing'),
])
def test_signature_and_return_counterexamples(tmp_path, old, new, code):
    _, index = source(tmp_path, GOOD.replace(old, new))
    assert any(i.code == code for i in index.issues)
    assert index.status == ('grey' if code.endswith('missing') else 'red')


def test_annotated_units_are_checked_without_importing_project(tmp_path):
    text = '''from typing import Annotated
# flowguard: sensor length(x: seconds) -> positive: bool
def positive(x: Annotated[float, 'm']) -> bool: return x > 0
'''
    _, index = source(tmp_path, text)
    assert any(i.code == 'unit' for i in index.issues)


def test_missing_function_and_field_are_red_and_strings_are_not_comments(tmp_path):
    _, index = source(tmp_path, '''words = "# flowguard: sensor ignored() -> out: bool"
# flowguard: sensor gone(x: 1) -> out: bool
OTHER = 1
def unrelated(x: int) -> bool: return x > 0
# flowguard: states Missing.value = a | b
''')
    assert not index.named('ignored')
    assert len(index.named('gone')) == 1
    assert all(a.status == 'red' for a in index.entries)


@pytest.mark.parametrize('states', ['a | a', '[1] | b', 'a | ('])
def test_malformed_states_are_findings_not_reader_crashes(tmp_path, states):
    _, index = source(tmp_path, '# flowguard: states Order.status = ' + states + '\nclass Order:\n    status: str\n')
    assert index.status == 'red'


def test_duplicate_name_role_mismatch_red_but_same_role_two_sites_remain(tmp_path):
    text = GOOD + '\n' + GOOD.replace('eligible(', 'again(')
    _, index = source(tmp_path, text)
    assert index.status == 'ok' and len(index.named('eligibility')) == 2
    _, wrong = source(tmp_path, text.replace('def again(age: int, active: bool)', 'def again(age: int, active: bool)').replace('sensor eligibility(age: years', 'sensor eligibility(age: seconds', 1), name='wrong')
    assert any(i.code == 'identity' for i in wrong.issues)


def test_draft_uses_existing_cells_and_missing_numeric_bounds_stays_grey(tmp_path):
    root, _ = source(tmp_path, GOOD + '\ndef raw(x: int) -> int: return x\n')
    with closing(build(root, tmp_path / 'map.sqlite', workers=1)) as graph:
        target = next(n['id'] for n in graph.nodes() if n['qual'] == 'eligible')
        draft = A.draft(graph, target)
        assert draft.text == '# flowguard: sensor eligible' and draft.status == 'ok'
        assert {17, 18, 19} <= set(draft.ranges['points']['age'])
        assert draft.ranges['points']['active'] == [False, True]
        unknown = A.draft(graph, next(n['id'] for n in graph.nodes() if n['qual'] == 'raw'))
        assert not unknown.ranges['complete'] and any('no readable comparison' in i.message for i in unknown.issues)


def test_decision_reading_keeps_source_ast_and_local_dependency_signature(tmp_path):
    root, index = source(tmp_path, 'LIMIT = 18\n' + GOOD.replace('age >= 18', 'age >= LIMIT'))
    anchor, = index.entries
    read = A.decision_reading(root, anchor)
    assert read.reading.consts['age'] == [18]
    assert read.dependencies_complete
    assert 'literal:' + anchor.module + ':LIMIT' in read.dependencies
    assert read.node.name == 'eligible'


def test_true_source_call_and_mutated_same_object_stays_observed(tmp_path):
    root, index = source(tmp_path, GOOD)
    anchor, = index.entries
    with session(root):
        assert A.observe(root, anchor, {'age': 18, 'active': True}).value is True
        module = sys.modules[anchor.module]
        original = module.eligible.__code__
        constants = tuple(21 if c == 18 else c for c in original.co_consts)
        module.eligible.__code__ = original.replace(co_consts=constants)
        try:
            assert A.observe(root, anchor, {'age': 18, 'active': True}).value is False
        finally:
            module.eligible.__code__ = original


def test_real_runtime_exception_retains_type_and_message(tmp_path):
    text = '''# flowguard: sensor valid(x: 1) -> allowed: bool
def valid(x: int) -> bool:
    if x < 0: raise ValueError('actual negative input')
    return True
'''
    root, index = source(tmp_path, text)
    with session(root):
        result = A.observe(root, index.entries[0], {'x': -1})
    assert result.status == 'ok' and isinstance(result.value, Raised)
    assert type(result.value.error) is ValueError and str(result.value.error) == 'actual negative input'


@pytest.mark.parametrize('prefix,body', [
    ('', 'import side_effect\n    return x > 0'),
    ('CACHE=[]\n', 'CACHE.append(x)\n    return x > 0'),
    ('', 'global changed\n    changed = x\n    return True'),
    ('def print(x):\n    open("marker", "w").write("bad")\n', 'print(x)\n    return True'),
    ('def helper(x):\n    open("marker", "w").write("bad")\n    return True\n', 'return helper(x)'),
    ('class C:\n    def __class_getitem__(cls, key):\n        open("marker", "w").write("bad")\n        return True\n', 'return C[x]'),
    ('from pathlib import Path\nPath("marker").write_text("bad")\n', 'return x > 0'),
    ('import os\n', 'return x > 0'),
])
def test_unproved_calls_state_imports_and_initialization_are_grey_without_execution(tmp_path, prefix, body):
    root, index = source(tmp_path, prefix + '# flowguard: sensor check(x: 1) -> allowed: bool\ndef check(x: int) -> bool:\n    ' + body + '\n')
    with session(root):
        result = A.observe(root, index.entries[0], {'x': 1})
    assert result.status == 'grey'
    assert index.entries[0].module not in sys.modules
    assert not (root / 'marker').exists()


def test_custom_primitive_subclass_cannot_smuggle_comparison_hook(tmp_path):
    root, index = source(tmp_path, GOOD)
    called = []
    class EvilInt(int):
        def __ge__(self, other):
            called.append(True)
            return True
    with session(root):
        observed = A.observe(root, index.entries[0], {'age': EvilInt(18), 'active': True})
    assert observed.status == 'red' and not called


def test_stale_identity_and_wrong_runtime_return_are_red(tmp_path):
    root, index = source(tmp_path, GOOD)
    anchor, = index.entries
    with session(root):
        first = A.observe(root, anchor, {'age': 20, 'active': True})
        assert first.status == 'ok'
        (root / anchor.file).write_text(GOOD.replace('return age >= 18 and active', 'return "wrong"'))
        stale = A.observe(root, anchor, {'age': 20, 'active': True})
        assert stale.status == 'red' and 'source changed' in stale.reasons[0]
        fresh = A.collect_sources(root, [(anchor.file, anchor.module)]).entries[0]
        wrong = A.observe(root, fresh, {'age': 20, 'active': True})
        assert wrong.status == 'red' and wrong.value == 'wrong'


def test_closed_typed_same_module_helper_preserves_real_changes(tmp_path):
    text = '''def helper(active: bool) -> bool: return active
# flowguard: sensor allowed(active: 1) -> result: bool
def allowed(active: bool) -> bool: return helper(active)
'''
    root, index = source(tmp_path, text)
    with session(root):
        assert A.observe(root, index.entries[0], {'active': True}).value is True
        (root / index.entries[0].file).write_text(text.replace('return active', 'return not active'))
        changed = A.collect_sources(root, [(index.entries[0].file, index.entries[0].module)]).entries[0]
        assert A.observe(root, changed, {'active': True}).value is False
    assert A.decision_reading(root, changed).dependencies_complete


@pytest.mark.parametrize('text', [
    '''class C:
    def __class_getitem__(cls, key):
        open('marker', 'w').write('bad')
        return True
# flowguard: sensor check(x: 1) -> result: bool
def check(x: int) -> bool:
    x = C
    return x[0]
''',
    '''class C:
    def __class_getitem__(cls, key):
        open('marker', 'w').write('bad')
        return True
def hidden(active: bool) -> bool: return C
def use(value: bool) -> bool: return value[0]
# flowguard: sensor check(active: 1) -> result: bool
def check(active: bool) -> bool: return use(hidden(active))
''',
    '''def hidden(value: bool) -> bool:
    open('marker', 'w').write('bad')
    return value
# flowguard: sensor check(value: 1) -> result: bool
def check(value: bool) -> bool: return hidden(value)
''',
])
def test_helper_and_rebound_input_cannot_smuggle_nonprimitive_operations(tmp_path, text):
    root, index = source(tmp_path, text)
    anchor, = index.entries
    with session(root):
        result = A.observe(root, anchor, {p.name: True if p.source_type == 'bool' else 1 for p in anchor.parameters})
    assert result.status == 'grey'
    assert anchor.module not in sys.modules


def test_source_comment_not_an_external_anchor_binding(tmp_path):
    root, index = source(tmp_path, GOOD + '\ndef unbound(age: int, active: bool) -> bool: return True\n')
    forged = replace(index.entries[0], qual='unbound', target_line=5)
    with session(root):
        result = A.observe(root, forged, {'age': 1, 'active': True})
    assert result.status == 'red' and 'source comment' in result.reasons[0]
    assert forged.module not in sys.modules


def test_state_field_in_nested_class_is_not_the_outer_field(tmp_path):
    _, missing = source(tmp_path, '# flowguard: states Outer.status = pending\nclass Outer:\n    class Inner:\n        status: str\n')
    assert missing.status == 'red'
    _, invalid = source(tmp_path, '# flowguard: states Order.status = pending\nclass Order:\n    status = "not-pending"\n', name='invalid')
    assert invalid.status == 'red' and any(i.code == 'states-values' for i in invalid.issues)


def test_parameter_names_not_comment_order_and_optional_spelling(tmp_path):
    _, index = source(tmp_path, GOOD.replace('age: years, active: 1', 'active: 1, age: years'))
    assert index.status == 'ok'
    assert [p.name for p in index.entries[0].parameters] == ['age', 'active']
    _, optional = source(tmp_path, '''from typing import Optional
# flowguard: event received(value: Optional[int])
def received(value: int | None) -> None: pass
''', name='optional')
    assert optional.status == 'ok'


def test_literal_domain_uses_declared_values_and_missing_type_reading_is_grey(tmp_path):
    root, index = source(tmp_path, '''from typing import Literal
# flowguard: sensor access(role: 1) -> allowed: bool
def access(role: Literal['admin', 'member']) -> bool: return role == 'admin'
def untyped(x): return x == 1
''')
    with closing(build(root, tmp_path / 'map.sqlite', workers=1)) as graph:
        proposed = A.draft(graph, index.entries[0].target)
        assert set(proposed.ranges['points']['role']) == {'admin', 'member'}
    with session(root):
        assert A.observe(root, index.entries[0], {'role': 'admin'}).value is True
        assert A.observe(root, index.entries[0], {'role': 'outside'}).status == 'red'
    _, missing = source(tmp_path, GOOD.replace('age: int', 'age'), name='missing')
    reading = A.decision_reading(root.parent / 'missing', missing.entries[0])
    assert reading.issues and reading.reading.consts == {'active': []}
    assert set(reading.kinds) == {'active'}
    assert any(i.code == 'range-missing' and i.message.startswith('age:') for i in reading.issues)


def test_parser_owner_digest_invalidates_existing_map(tmp_path, monkeypatch):
    from flowguard.structure import store
    root, _ = source(tmp_path, GOOD)
    db = tmp_path / 'map.sqlite'
    with closing(build(root, db, workers=1)):
        pass
    original = store.content_digest
    def changed(path, **kwargs):
        digest = original(path, **kwargs)
        return digest + '-reader-change' if Path(path).resolve() == Path(A.__file__).resolve() else digest
    monkeypatch.setattr(store, 'content_digest', changed)
    with closing(build(root, db, workers=1)) as graph:
        assert graph.stats['parsed'] == 1 and A.collect(graph).status == 'ok'


def test_annotated_parameter_is_observed_and_drafted_without_guessing_unit(tmp_path):
    root, index = source(tmp_path, '''from typing import Annotated
# flowguard: sensor length(x: m) -> positive: bool
def positive(x: Annotated[int, 'm']) -> bool: return x >= 1
''')
    with closing(build(root, tmp_path / 'map.sqlite', workers=1)) as graph:
        proposed = A.draft(graph, index.entries[0].target)
        assert proposed.status == 'ok' and 'x: m' in proposed.text
    with session(root):
        result = A.observe(root, index.entries[0], {'x': 2})
    assert result.status == 'ok' and result.value is True


def test_none_only_input_is_grey_for_enumeration_not_a_crash(tmp_path):
    root, index = source(tmp_path, '''# flowguard: sensor empty(x: 1) -> result: bool
def empty(x: None) -> bool: return x is None
''')
    assert A.decision_reading(root, index.entries[0]).issues
    with closing(build(root, tmp_path / 'map.sqlite', workers=1)) as graph:
        assert A.draft(graph, index.entries[0].target).ranges == {}


def test_calibration_cannot_escape_source_comment_identity(tmp_path):
    root, index = source(tmp_path, GOOD)
    forged = replace(index.entries[0], calibrated_by='tests/test_unbound.py::test_unbound')
    with session(root):
        result = A.observe(root, forged, {'age': 18, 'active': True})
    assert result.status == 'red' and 'source comment' in result.reasons[0]


def test_canonical_dispatch_uses_one_transport_and_nested_backend_scope(tmp_path, monkeypatch):
    root, index = source(tmp_path, GOOD)
    called = []
    backend = types.ModuleType(A.__package__ + '.calibration')
    def execute(actual_root, anchor, values):
        called.append(('transport', actual_root, anchor.target, values))
        return A.Observation('grey', reasons=('transport seam',), anchor=anchor.target)
    @contextmanager
    def backend_session(actual_root):
        called.append(('enter', actual_root))
        try:
            yield
        finally:
            called.append(('exit', actual_root))
    backend.execute, backend._execution_session = execute, backend_session
    monkeypatch.setitem(sys.modules, backend.__name__, backend)
    assert A.observe(root, index.entries[0], {'age': 18, 'active': True}).reasons == ('transport seam',)
    assert index.entries[0].module not in sys.modules
    with A._execution_session(root):
        assert A._SESSION.get() == root.resolve()
    assert A._SESSION.get() is None
    assert [row[0] for row in called] == ['transport', 'enter', 'exit']


def test_import_verification_failure_is_not_a_function_refusal(tmp_path, monkeypatch):
    root, index = source(tmp_path, GOOD)
    anchor, = index.entries
    unverified = types.ModuleType(anchor.module)
    unverified.__file__ = str(root / anchor.file)
    exec(compile(GOOD, unverified.__file__, 'exec'), unverified.__dict__)
    monkeypatch.setitem(sys.modules, anchor.module, unverified)
    with session(root):
        result = A.observe(root, anchor, {'age': 18, 'active': True})
    assert result.status == 'red' and 'imported before source verification' in result.reasons[0]
    assert not isinstance(result.value, Raised)
