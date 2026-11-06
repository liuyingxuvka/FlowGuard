"""Finite partitions, uncapped products and exact linear region representatives."""
from datetime import date, datetime, timedelta
from decimal import Decimal as D
from enum import Enum
from fractions import Fraction
from itertools import product
from typing import Literal

import pytest

from flowguard.intent import cells as C
from flowguard.intent import linear as L


class Status(Enum):
    OPEN = 'open'
    CLOSED = 'closed'


def space_for(functions, fields):
    kinds = {name: C.kind_of(spec) for name, spec in fields.items()}
    readings = [C.read_predicate(fn, fields) for fn in functions]
    return C.build_space(
        kinds, {name: [v for rd in readings for v in rd.consts[name]] for name in fields},
        planes=[p for rd in readings for p in rd.planes],
        links={link for rd in readings for link in rd.links},
        reasons=[why for rd in readings for why in rd.reasons],
        hints={name: [v for rd in readings for v in rd.hints.get(name, [])] for name in fields},
    )


@pytest.mark.parametrize('spec,values', [
    (bool, [False, True]), (Status, list(Status)),
    (Literal['open', 'closed'], ['open', 'closed', '<other>']),
    (int | None, [0, 1, None]), (D, [D(0), D(1)]),
])
def test_declared_types_and_optional(spec, values):
    assert C.points(C.kind_of(spec), []) == values


def test_literal_other_is_not_mistaken_for_unseen_value():
    values = C.points(C.kind_of(str), ['<other>'])
    assert '<other>' in values and any(value != '<other>' for value in values)


@pytest.mark.parametrize('spec,bound,epsilon', [
    (int, 17, 1), (float, 1.25, .01), (D, D('2.300'), D('.001')),
    (date, date(2026, 8, 17), timedelta(days=1)),
    (datetime, datetime(2026, 8, 17, 10), timedelta(seconds=1)),
    (timedelta, timedelta(hours=2), timedelta(seconds=1)),
])
def test_boundaries_and_far_points(spec, bound, epsilon):
    values = C.points(C.kind_of(spec), [bound])
    assert {bound - epsilon, bound, bound + epsilon} <= set(values)
    assert min(values) < bound - epsilon and max(values) > bound + epsilon


def test_finer_decimal_precision_wins_for_equal_constants():
    values = C.points(C.kind_of(D), [D('5'), D('5.00')])
    assert {D('4.99'), D('5.00'), D('5.01')} <= set(values)


@pytest.mark.parametrize('bound', [date.min, date.max, datetime.min, datetime.max])
def test_finite_date_endpoints_do_not_crash(bound):
    values = C.points(C.kind_of(type(bound)), [bound])
    assert bound in values and all(type(value) is type(bound) for value in values)


def test_no_cell_budget_can_truncate_a_complete_product():
    space = C.build_space({f'b{i}': C.kind_of(bool) for i in range(15)}, {})
    assert space.complete and len(space.cells) == space.total == 32768
    assert len({tuple(cell.values()) for cell in space.cells}) == 32768


def sum_low(a, b):
    return a + b < 7


def sum_high(a, b):
    return a + b >= 8


def difference(a, b):
    return a - b > 3


def constant_multiple(a, b):
    return a * D('0.25') + b * D('0.5') <= D('7.5')


def constant_ratio(a, b):
    return a / D('2') - b >= D('1.25')


def subtotal_and_fee(a, b):
    return a + b < D('10.10')


def days_and_due(a, b):
    return a + timedelta(days=b) < date(2026, 9, 17)


def elapsed_days(a, b):
    return (a - b).days >= 4


def datetime_difference(a, b):
    return (a - b).total_seconds() <= 3600


@pytest.mark.parametrize('functions,fields,oracle_values', [
    ([sum_low, sum_high, difference], {'a': int, 'b': int}, range(-10, 12)),
    ([constant_multiple, constant_ratio, subtotal_and_fee], {'a': D, 'b': D},
     [D(i) / D(4) for i in range(-12, 45)]),
])
def test_linear_regions_cover_all_oracle_truth_vectors(functions, fields, oracle_values):
    space = space_for(functions, fields)
    assert space.complete, space.reasons
    actual = {tuple(fn(**cell) for fn in functions) for cell in space.cells}
    expected = {tuple(fn(a, b) for fn in functions) for a, b in product(oracle_values, repeat=2)}
    assert expected <= actual


@pytest.mark.parametrize('fn,fields', [
    (days_and_due, {'a': date, 'b': int}),
    (elapsed_days, {'a': date, 'b': date}),
    (datetime_difference, {'a': datetime, 'b': datetime}),
])
def test_date_duration_linear_reading_has_both_sides(fn, fields):
    space = space_for([fn], fields)
    assert space.complete, space.reasons
    assert {fn(**cell) for cell in space.cells} == {False, True}


def product_of_fields(a, b):
    return a * b >= 10


def a_field_call(a, b):
    return abs(a) + b <= 10


@pytest.mark.parametrize('fn', [product_of_fields, a_field_call])
def test_unknown_atoms_run_the_full_grid_but_are_not_exhaustive(fn):
    space = space_for([fn], {'a': int, 'b': int})
    assert not space.complete and space.label == f'grid {space.total} of {space.total}'
    assert space.reasons and len(space.cells) == space.total


def twice_integer(a, b):
    return 2 * a + 3 * b < 17


def test_integer_projection_with_non_unit_coefficients_stays_incomplete():
    space = space_for([twice_integer], {'a': int, 'b': int})
    assert not space.complete
    assert any('coefficients other than 1' in why for why in space.reasons)


def string_order(a):
    return a < 'middle'


def test_unbounded_ordered_strings_are_not_misrepresented_as_equality_partition():
    space = space_for([string_order], {'a': str})
    assert not space.complete and any('ordered strings' in why for why in space.reasons)


def string_equal(a, b, c, d):
    return a == b and b == c and c != d


def test_distinct_unseen_strings_cover_all_equality_patterns():
    fields = dict.fromkeys('abcd', str)
    space = space_for([string_equal], fields)
    assert space.complete
    assert {string_equal(**cell) for cell in space.cells} == {False, True}
    assert any(len(set(cell.values())) == 4 for cell in space.cells)


def optional_sum(a, b):
    if a is None or b is None:
        return False
    return a + b > 0


def test_optional_linear_group_includes_each_absence_pattern():
    space = space_for([optional_sum], {'a': int | None, 'b': int | None})
    assert space.complete
    assert {(cell['a'] is None, cell['b'] is None) for cell in space.cells} == set(product([False, True], repeat=2))
    assert {optional_sum(**cell) for cell in space.cells} == {False, True}


def test_numeric_outcome_difference_is_not_hidden_by_rounding():
    assert C.same(D('1.0'), 1)
    assert not C.same(D('1.0000000001'), D('1.0'))
    assert not C.same(True, 1)


def test_smallest_counterexample_is_deterministic():
    points = {'a': [-1, 0, 1], 'b': [False, True]}
    cells = [{'a': 1, 'b': True}, {'a': 1, 'b': False}, {'a': -1, 'b': False}]
    assert C.smallest(cells, points) == C.smallest(list(reversed(cells)), points)
    assert C.smallest(cells, points)['b'] is False


def test_fraction_projection_normalizes_plane_identity():
    assert L.Plane({'a': Fraction(1, 2), 'b': Fraction(-3, 2)}, Fraction(1, 4)).key == \
        L.Plane({'a': 1, 'b': -3}, Fraction(1, 2)).key


def test_closed_enum_points_never_invent_values_of_another_type():
    actual = C.points(C.kind_of(Status), ['open', 'date', 40])
    assert actual == list(Status)


def test_an_actual_finite_type_domain_is_complete_without_symbolic_inference():
    fields = {'state': C.kind_of(Status), 'active': C.kind_of(bool)}
    space = C.build_space(fields, {'state': ['unrelated code token']}, reasons=['unmapped internal index'])
    assert space.complete and space.total == 4
    assert {cell['state'] for cell in space.cells} == set(Status)
    assert {cell['active'] for cell in space.cells} == {False, True}


def test_open_strings_do_not_gain_completeness_from_a_small_grid():
    space = C.build_space({'quote': str}, {'quote': ['alpha', 'beta']}, reasons=['unmapped len(quote) boundary'])
    assert not space.complete
    assert 'unmapped len(quote) boundary' in space.reasons
