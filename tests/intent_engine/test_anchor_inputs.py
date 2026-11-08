"""Round 19: short comments classify only primitive inputs and keep context intact."""
import ast
from contextlib import closing
from decimal import Decimal

from flowguard.intent import anchors as A
from flowguard.intent import cells
from flowguard.structure import build


def source(tmp_path, text):
    path = tmp_path / 'app.py'
    path.write_text(text)
    return A.collect_sources(tmp_path, [('app.py', 'app')])


def test_short_sensor_classifies_connection_and_preserves_full_real_signature(tmp_path):
    index = source(tmp_path, '''# flowguard: sensor AVAILABLE
def can_hire(db: sqlite3.Connection, item_id: int, stock: int, reserved: int) -> bool:
    return stock > reserved
''')
    assert index.status == 'ok'
    anchor, = index.entries
    assert [p.name for p in anchor.inputs] == ['item_id', 'stock', 'reserved']
    assert [p.name for p in anchor.contexts] == ['db']
    assert anchor.output == '' and anchor.output_type == 'bool'
    assert all(not p.unit for p in anchor.parameters)


def test_semicolon_overrides_primitive_context_and_optional_units(tmp_path):
    index = source(tmp_path, '''# flowguard: sensor AVAILABLE(stock: count, reserved; db, item_id)
def can_hire(db, item_id: int, stock: int, reserved: int) -> bool:
    return stock > reserved
''')
    anchor, = index.entries
    assert index.status == 'ok'
    assert [(p.name, p.unit) for p in anchor.inputs] == [('stock', 'count'), ('reserved', '')]
    assert [p.name for p in anchor.contexts] == ['db', 'item_id']
    reading = A.decision_reading(tmp_path, anchor)
    assert set(reading.kinds) == {'stock', 'reserved'}
    assert reading.reading.planes and not reading.issues
    space = cells.build_space(reading.kinds, reading.reading.consts, reading.reading.planes, reading.reading.links)
    assert space.complete
    assert {row['stock'] > row['reserved'] for row in space.cells} == {False, True}


def test_short_event_keeps_object_context_without_return_contract(tmp_path):
    index = source(tmp_path, '''class Store:
    # flowguard: event SAVED
    def save(self, artifact_id: str) -> None: pass
''')
    anchor, = index.entries
    assert index.status == 'ok' and anchor.receiver == 'self'
    assert anchor.kind == 'event' and anchor.output_type == ''
    assert [p.name for p in anchor.inputs] == ['artifact_id']


def test_decimal_constructor_and_module_constants_feed_existing_linear_reader(tmp_path):
    index = source(tmp_path, '''from decimal import Decimal
LIMIT = Decimal("20")
# flowguard: sensor STANDING
def standing(owed: Decimal, stock: int, reserved: int) -> bool:
    return owed <= Decimal("20") and stock > reserved + 2
''')
    reading = A.decision_reading(tmp_path, index.entries[0])
    assert reading.reading.consts['owed'] == [Decimal('20')]
    assert reading.reading.planes and not reading.issues
    assert reading.literal_globals['LIMIT'] == Decimal('20')
    assert reading.dependencies_complete
    space = cells.build_space(reading.kinds, reading.reading.consts, reading.reading.planes, reading.reading.links, reading.reading.reasons, reading.reading.hints)
    assert space.complete
    assert Decimal('20') in space.pts['owed']
    assert any(row['stock'] == row['reserved'] + 2 for row in space.cells)


def test_unknown_parameter_keeps_other_parameter_bounds_and_is_named(tmp_path):
    index = source(tmp_path, '''# flowguard: sensor MIXED
def mixed(age: int, unknown) -> bool:
    return age >= 18 and unknown
''')
    reading = A.decision_reading(tmp_path, index.entries[0])
    assert set(reading.kinds) == {'age'}
    assert reading.reading.consts['age'] == [18]
    assert any(i.code == 'range-missing' and i.message.startswith('unknown:') for i in reading.issues)
    assert not any(i.code == 'range-missing' and i.message.startswith('age:') for i in reading.issues)


def test_short_draft_has_real_inputs_context_and_relational_cells(tmp_path):
    source(tmp_path, '''def can_hire(db: object, stock: int, reserved: int) -> bool:
    return stock > reserved
''')
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        draft = A.draft(graph, 'app:can_hire')
    assert draft.text == '# flowguard: sensor can_hire'
    assert draft.status == 'ok'
    assert draft.ranges['inputs'] == ['stock', 'reserved']
    assert draft.ranges['context'] == ['db']
    assert draft.ranges['complete']


def test_annotation_calls_and_rebound_constructors_are_never_executed(tmp_path):
    source(tmp_path, '''from decimal import Decimal
def Decimal(text):
    open("marker", "w").write(text)
# flowguard: sensor DANGER
def danger(x: leak()) -> bool:
    return x > Decimal("20")
''')
    assert not (tmp_path / 'marker').exists()
    tree = ast.parse((tmp_path / 'app.py').read_text())
    assert 'Decimal' not in A._literal_globals(tree)
    index = A.collect_sources(tmp_path, [('app.py', 'app')])
    assert index.entries[0].contexts[0].name == 'x'


def test_semicolon_cannot_silently_drop_or_duplicate_real_parameters(tmp_path):
    for comment in ('X(x; x)', 'X(x; missing)', 'X(x;)', 'X(; x) -> out: bool'):
        index = source(tmp_path, '# flowguard: sensor ' + comment + '\ndef f(x: int, y: bool) -> bool: return y\n')
        assert index.status == 'red'


def test_one_kind_owner_uses_actual_primitive_only_for_unannotated_input():
    import pytest
    assert A.parameter_kind(A.Parameter('value', '', '?'), 12).name == 'int'
    assert A.parameter_kind(A.Parameter('value', '', '?'), False).name == 'bool'
    assert A.parameter_kind(A.Parameter('id', '', 'int', 'context'), 12) is None
    with pytest.raises(ValueError, match='actual primitive is unavailable'):
        A.parameter_kind(A.Parameter('value', '', '?'), object())


def test_project_enum_is_an_input_without_importing_its_annotation(tmp_path):
    import enum
    index = source(tmp_path, '''from enum import Enum as E
class Role(E):
    MEMBER = 'member'
    ADMIN = 'admin'
# flowguard: sensor ACCESS
def access(role: Role) -> bool: return role == Role.ADMIN
''')
    anchor, = index.entries
    assert index.status == 'ok' and [p.name for p in anchor.inputs] == ['role']
    class Role(enum.Enum):
        MEMBER = 'member'
        ADMIN = 'admin'
    kind = A.parameter_kind(anchor.inputs[0], Role.MEMBER)
    assert kind.literals == (Role.MEMBER, Role.ADMIN) and kind.enum_type is Role
    assert 'app' not in __import__('sys').modules


def test_same_name_contexts_can_differ_but_input_roles_are_still_checked(tmp_path):
    index = source(tmp_path, '''# flowguard: sensor SAME(x; db)
def check(x: int, db: object) -> bool: return x > 1
# flowguard: sensor SAME(x; cache)
def other(x: int, cache: dict) -> bool: return x > 1
''')
    assert index.status == 'ok'
    changed = (tmp_path / 'app.py').read_text().replace('other(x: int', 'other(x: float')
    index = source(tmp_path, changed)
    assert index.status == 'red' and any(i.code == 'identity' for i in index.issues)


def test_stdlib_type_aliases_are_read_without_evaluating_annotations(tmp_path):
    index = source(tmp_path, '''from decimal import Decimal as D
from typing import Literal as L
# flowguard: sensor FEE
def fee(owed: D, role: L['member', 'admin']) -> bool:
    return owed <= D("20") and role == 'admin'
''')
    anchor, = index.entries
    assert [p.source_type for p in anchor.inputs] == ['Decimal', "Literal['member', 'admin']"]
    reading = A.decision_reading(tmp_path, anchor)
    assert reading.kinds['owed'].name == 'dec'
    assert reading.reading.consts['owed'] == [Decimal('20')]
    assert not reading.issues


def test_qualified_stdlib_type_annotations_are_simple_inputs(tmp_path):
    index = source(tmp_path, '''import decimal as dec
import datetime as dates
import typing as t
# flowguard: sensor QUALIFIED
def check(owed: dec.Decimal, day: dates.date, role: t.Literal['a', 'b']) -> bool:
    return owed > 0
''')
    assert [p.source_type for p in index.entries[0].inputs] == ['Decimal', 'date', "Literal['a', 'b']"]



def test_short_and_old_full_copy_are_compatible_without_inventing_units(tmp_path):
    text = """# flowguard: sensor SAME
def short(age: int) -> bool: return age > 18
"""
    text += """
# flowguard: sensor SAME(age: years) -> allowed: bool
def full(age: int) -> bool: return age > 18
# flowguard: sensor SAME(age: years) -> allowed: bool
def other(age: int) -> bool: return age > 18
"""
    assert source(tmp_path, text).status == 'ok'
    assert source(tmp_path, text.replace('other(age: int)', 'other(age: float)')).status == 'red'
    assert source(tmp_path, text.replace('SAME(age: years)', 'SAME(age: seconds)', 1)).status == 'red'
    assert source(tmp_path, text.replace('-> allowed:', '-> forbidden:', 1)).status == 'red'



def test_old_full_connection_parameter_is_context_without_rewriting_the_comment(tmp_path):
    index = source(tmp_path, """# flowguard: sensor AVAILABLE(db: connection, stock: count, reserved: count) -> ok: bool calibrated_by=tests/test_app.py::test_can_hire
def can_hire(db: sqlite3.Connection, stock: int, reserved: int) -> bool:
    return stock > reserved
""")
    anchor, = index.entries
    assert [p.name for p in anchor.contexts] == ['db']
    assert [p.name for p in anchor.inputs] == ['stock', 'reserved']
    assert anchor.calibrated_by == 'tests/test_app.py::test_can_hire'
    assert not A.decision_reading(tmp_path, anchor).issues



def test_real_values_resolve_only_automatically_classified_unknown_parameters(tmp_path):
    import pytest
    index = source(tmp_path, """# flowguard: sensor AUTO
def automatic(db, stock) -> bool: return stock > 0
# flowguard: sensor EXPLICIT(stock; db)
def explicit(db, stock) -> bool: return stock > 0
""")
    automatic, explicit = index.entries
    assert all(p.inferred for p in automatic.parameters)
    assert not any(p.inferred for p in explicit.parameters)
    assert A.parameter_kind(automatic.parameters[0], object()) is None
    assert A.parameter_kind(automatic.parameters[1], 2).name == 'int'
    assert A.parameter_kind(explicit.parameters[0], 2) is None
    with pytest.raises(ValueError, match='simple source type'):
        A.parameter_kind(explicit.parameters[1], object())
    with pytest.raises(ValueError, match='simple source type'):
        A.parameter_kind(automatic.parameters[1])


def test_untyped_short_copy_can_match_explicit_context_without_false_identity_red(tmp_path):
    index = source(tmp_path, """# flowguard: sensor SAME
def automatic(db, stock: int) -> bool: return stock > 0
# flowguard: sensor SAME(stock; db)
def explicit(db, stock: int) -> bool: return stock > 0
""")
    assert index.status == 'ok'



def test_imported_enum_uses_actual_value_but_explicit_context_stays_context(tmp_path):
    import enum
    index = source(tmp_path, """from unimported_dependency import QuoteCase
# flowguard: sensor INFERRED
def inferred(quote: QuoteCase) -> bool: return True
# flowguard: sensor EXPLICIT(; quote)
def explicit(quote: QuoteCase) -> bool: return True
""")
    inferred, explicit = index.entries
    class QuoteCase(enum.Enum):
        EXACT = 'exact'
        CHANGED = 'changed'
    assert inferred.contexts[0].inferred
    kind = A.parameter_kind(inferred.contexts[0], QuoteCase.EXACT)
    assert kind.enum_type is QuoteCase and kind.literals == tuple(QuoteCase)
    assert A.parameter_kind(explicit.contexts[0], QuoteCase.EXACT) is None
    assert 'unimported_dependency' not in __import__('sys').modules
