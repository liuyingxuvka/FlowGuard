"""The inputs same-name copies are compared on (design 4.5): the union of the recorded calls, each recorded
number +-1 and the copies' numeric constants, at most 64 inputs, judged input by input."""
import ast

from flowguard.intent import signals
from flowguard.intent.plugin import _sealed_numbers


def _numbers(source, qual='f'):
    return _sealed_numbers(ast.parse(source), qual)


def test_a_copy_uses_the_numbers_as_its_source_spells_them():
    assert _numbers('def f(days):\n    return days >= -5 and days != -0.5 and days < +3\n') == [-5, -0.5, 3]
    # 1 and 1.0 are different JSON inputs: both stay, each with its own type
    found = _numbers('def f(x):\n    return x == 1 or x == 1.0\n')
    assert found == [1, 1.0] and [type(number) for number in found] == [int, float]
    # every number of a literal tuple, list, set or dict constant the copy (or its helper) reads
    found = _numbers('BOUNDS = (3, -7)\nTABLE = {"a": [2.5, 9], 4: "x"}\nNAME = "x"\n'
                     'def helper(x):\n    return x in TABLE\n'
                     'def f(x):\n    return BOUNDS[0] <= x <= BOUNDS[1] or helper(x) or x == NAME\n')
    assert found == [0, 1, 3, -7, 2.5, 9, 4], found
    # a bool, None or string is no number; a constant built by a call is no literal
    assert _numbers('LIMIT = int("3")\ndef f(x):\n    return x is True or x is None or x == "3" or x == LIMIT\n') == []
    assert _numbers('def g(x):\n    return 1\n') is None


def _union(recorded, numbers):
    inputs, left = signals.copy_inputs(recorded, numbers)
    return inputs


def test_recorded_inputs_come_first_then_every_constant_then_the_neighbours():
    recorded = [{'days': days} for days in range(100, 500, 10)]           # 40 recorded calls
    inputs, left = signals.copy_inputs(recorded, [3, 7])
    assert inputs[:40] == recorded and inputs[40:42] == [{'days': 3}, {'days': 7}], inputs[38:44]
    assert inputs[42:44] == [{'days': 99}, {'days': 101}], inputs[40:46]
    assert len(inputs) == 64 and left == dict(recorded=0, numbers=0), (len(inputs), left)


def test_the_neighbours_of_recorded_numbers_and_of_constants_are_tried():
    # each neighbour moves one field and keeps the others as recorded
    assert _union([{'x': 100, 'y': 200}], []) == [
        {'x': 100, 'y': 200}, {'x': 99, 'y': 200}, {'x': 101, 'y': 200}, {'x': 100, 'y': 199}, {'x': 100, 'y': 201}]
    inputs = _union([{'days': 0, 'name': 'a'}], [3])
    assert inputs == [{'days': 0, 'name': 'a'}, {'days': 3, 'name': 'a'}, {'days': -1, 'name': 'a'},
                      {'days': 1, 'name': 'a'}, {'days': 2, 'name': 'a'}, {'days': 4, 'name': 'a'}], inputs


def test_no_more_than_64_inputs_and_each_only_once():
    recorded = [{'a': number, 'b': -number} for number in range(30)]
    inputs = _union(recorded, [1000, 2000, 1000.0])
    assert len(inputs) == 64 and inputs[:30] == recorded, len(inputs)
    assert len({repr(sorted(row.items())) for row in inputs}) == 64
    assert _union([{'a': 1}, {'a': 1}], []) == [{'a': 1}, {'a': 0}, {'a': 2}]
    # the same number of several copies is one number; 3 and 3.0 stay two
    assert _union([{'a': 0}], [3, 3, 3.0, 3]) == [{'a': 0}, {'a': 3}, {'a': 3.0}, {'a': -1}, {'a': 1},
                                                  {'a': 2}, {'a': 4}, {'a': 2.0}, {'a': 4.0}]


def test_a_boolean_or_none_never_gains_arithmetic_or_constants_and_infinity_never_enters():
    inputs = _union([{'flag': True, 'none': None}, {'flag': False, 'none': None}], [3, float('inf')])
    assert inputs == [{'flag': True, 'none': None}, {'flag': False, 'none': None}], inputs
    assert _union([{'rate': 1.5}], [float('inf'), float('nan')]) == [{'rate': 1.5}, {'rate': 0.5}, {'rate': 2.5}]


def test_recorded_inputs_alone_over_the_cap_leave_every_constant_its_place_and_the_cut_is_counted():
    # 80 recorded calls (four copies, 20 each) would fill the 64 inputs alone and push 3 and 7 out.
    recorded = [{'days': days} for days in range(1000, 1800, 10)]
    inputs, left = signals.copy_inputs(recorded, [3, 7])
    assert inputs == [*recorded[:62], {'days': 3}, {'days': 7}], inputs[60:]
    assert left == dict(recorded=18, numbers=0), left


def test_a_lookup_table_takes_at_most_half_the_inputs_and_the_untried_numbers_are_counted():
    # Three copies read the same 5,000-number table; 60 recorded inputs of three fields.
    recorded = [{'a': number, 'b': 100 + number, 'c': 'x'} for number in range(60)]
    table = list(range(10_000, 15_000))
    inputs, left = signals.copy_inputs(recorded, table * 3)
    assert len(inputs) == 64 and inputs[:32] == recorded[:32], inputs[:34]
    assert inputs[32:] == [{**recorded[0], 'a': number} for number in range(10_000, 10_032)], inputs[32:]
    assert left == dict(recorded=28, numbers=4968), left


def test_the_union_is_built_lazily_and_stops_at_the_cap():
    # Each recorded input with each number would be 60 x 2 x 6,000 rows (hundreds of MB) before the cut at 64.
    import tracemalloc
    recorded = [{'a': number, 'b': 100 + number, 'c': 'x'} for number in range(60)]
    numbers = list(range(20_000, 22_000)) * 3
    tracemalloc.start()
    try:
        inputs, left = signals.copy_inputs(recorded, numbers)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert len(inputs) == 64 and left == dict(recorded=28, numbers=1968), left
    assert peak < 2_000_000, peak


def test_each_input_is_judged_against_the_baseline_of_the_same_input():
    same = lambda left, right: left == right
    rows = [
        # agreed at the baseline, differ now: red
        ('days=7', [('a', True), ('b', False)], {'a': (False, False), 'b': (False, False)}, set()),
        # differed at the baseline already: before
        ('days=91', [('a', False), ('b', True)], {'a': (False, False), 'b': (True, False)}, set()),
        # b's baseline did not run here: not compared
        ('days=-1', [('a', False), ('b', True)], {'a': (False, False)}, {'b'}),
        # agree now: nothing to say, whatever the baseline did
        ('days=0', [('a', True), ('b', True)], {'a': (True, False), 'b': (False, False)}, set()),
    ]
    red, before, unknown = signals.copy_partition(rows, same, str, total=2)
    assert [line[0] for line in red] == ['days=7'], red
    assert [line[0] for line in before] == ['days=91'], before
    assert [line[0] for line in unknown] == ['days=-1'], unknown
    # both raised the same exception at the baseline: not compared either (a result that only looks like one is)
    raised = [('days=-2', [('a', False), ('b', True)], {'a': ({'raises': 'E'}, True), 'b': ({'raises': 'E'}, True)}, set())]
    assert [[line[0] for line in lines] for lines in signals.copy_partition(raised, same, str, total=2)] == [[], [], ['days=-2']]
    returned = [('days=-2', [('a', False), ('b', True)], {'a': ({'raises': 'E'}, False), 'b': ({'raises': 'E'}, False)}, set())]
    assert [[line[0] for line in lines] for lines in signals.copy_partition(returned, same, str, total=2)] == [['days=-2'], [], []]
    # a copy that did not exist at the baseline cannot have agreed with anything: its difference is red
    red, before, unknown = signals.copy_partition([('n=2', [('a', 3), ('new', 4)], {'a': (3, False)}, set())], same, str, total=2)
    assert [line[0] for line in red] == ['n=2'] and not before and not unknown


def test_three_copies_a_new_pair_is_red_beside_an_old_one_on_the_same_input():
    same = lambda left, right: left == right
    # c already differed from a and b at the baseline; b now differs from a too
    rows = [('x=1', [('a', 1), ('b', 2), ('c', 3)], {'a': (1, False), 'b': (1, False), 'c': (3, False)}, set())]
    red, before, unknown = signals.copy_partition(rows, same, str, total=3)
    assert [line[3] for line in red] == [{frozenset('ab')}], red
    assert [line[3] for line in before] == [{frozenset('ac'), frozenset('bc')}] and not unknown, before
