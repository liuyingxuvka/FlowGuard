"""FG-811 symmetry, the static rule on per-id order: a model is explored up to renaming only
while no rule, guard or helper can tell the ids apart by their declared order (a loop that
carries a value from one id to the next, a list of per-id values in the declared order, a
builtin hidden by a binding, ids a helper returns); every other use is a doubt or a model error."""
from __future__ import annotations

import pytest

from flowguard.flow.checks import check_model
from flowguard.flow.model import ModelError, load_model


CARRY = '''
from flowguard.flow import Model, need
m = Model("tools")
TOOLS = m.objects("tool", "T1", "T2")
m.field("busy", [False, True], False, over=TOOLS)
m.field("pick", [False, True], False, over=TOOLS)
m.field("mark", [False, True], False)
m.field("count", range(0, 3), 0)
HELPERS

@m.action(t=TOOLS)
def take(s, t):
    need(not s["busy", t], "busy")
    s["busy", t] = True

@m.action(t=TOOLS)
def free(s, t):
    need(s["busy", t], "not busy")
    GUARD
    s["busy", t] = False
m.progress("a taken tool is freed", over=TOOLS, when=lambda s, t: s["busy", t], goal=lambda s, t: not s["busy", t])
MODEL = m
'''

CARRIED = {
    "a flag set by the one before": ("", '''ok, before = False, True
    for u in TOOLS:
        if u == t and before:
            ok = True
        before = False
    need(not ok, "the first stays busy")'''),
    "a position counter": ("", '''pos, seen = 0, False
    for u in TOOLS:
        if u == t:
            seen = True
        if not seen:
            pos += 1
    need(pos != 0, "the first stays busy")'''),
    "a position counter in one expression": ("", '''pos, seen = 0, False
    for u in TOOLS:
        seen = seen or u == t
        pos += 0 if seen else 1
    need(pos != 0, "the first stays busy")'''),
    "a rank counter": ("", '''k, mine = 0, 0
    for u in TOOLS:
        k += 1
        if u == t:
            mine = k
    need(mine != 1, "the first stays busy")'''),
    "a list filled in their order": ("", '''order = []
    for u in TOOLS:
        order.append(u == t)
    need(not order[0], "the first stays busy")'''),
    "a state cell the last one writes": ("", '''for u in TOOLS:
        s["mark"] = u == t
    need(not s["mark"], "the last stays busy")
    s["mark"] = False'''),
    "a state cell written through a helper": ('''def note(s, u, t):
    s["mark"] = u == t''', '''for u in TOOLS:
        note(s, u, t)
    need(not s["mark"], "the last stays busy")
    s["mark"] = False'''),
    "a cell of each that the later ones read": ("", '''for u in TOOLS:
        if not any(s["pick", v] for v in TOOLS):
            s["pick", u] = True
    need(not s["pick", t], "the first stays busy")
    for w in TOOLS:
        s["pick", w] = False'''),
    "a counter cell the later ones read": ("", '''for u in TOOLS:
        if u == t and s["count"] == 0:
            s["mark"] = True
        s["count"] = 1
    need(not s["mark"], "the first stays busy")
    s["count"] = 0'''),
    "a table filled in their order": ("", '''seen = {}
    for u in TOOLS:
        seen[len(seen)] = u == t
    need(not seen[0], "the first stays busy")'''),
    "a list changed by code the rule does not read": ("import heapq", '''order = []
    for u in TOOLS:
        heapq.heappush(order, (len(order), u == t))
    need(not order[0][1], "the first stays busy")'''),
    "a lazy filter that reads what the loop writes": ("", '''for u in (x for x in TOOLS if not any(s["pick", y] for y in TOOLS)):
        s["pick", u] = True
    need(not s["pick", t], "the first stays busy")
    for w in TOOLS:
        s["pick", w] = False'''),
    "any() over a helper that writes each one's cell": ('''def grab(s, u):
    s["pick", u] = True
    return True''', '''any(grab(s, u) for u in TOOLS)
    need(not s["pick", t], "the first stays busy")
    for w in TOOLS:
        s["pick", w] = False'''),
}


@pytest.mark.parametrize("how", list(CARRIED))
def test_a_loop_that_carries_a_value_from_one_id_to_the_next_is_never_reduced(project, how):
    """G3 round 3: T1 can never be freed, so unreduced T1 is stuck. A loop over the ids
    that carries a flag, a counter, a list or a state cell from one id to the next picks an
    id by its place in the declared order without any index, break or ordering operator,
    and each of these was explored up to renaming: "clean, complete", exit 0 (only check
    --full saw it). Such a loop is now a doubt: the model is explored without renaming and
    the stuck tool is found."""
    helpers, guard = CARRIED[how]
    project.flow("tools", CARRY.replace("HELPERS", helpers).replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    doubt = loaded.model.__dict__.get("_symmetry_doubt")
    assert doubt, "no doubt recorded"
    report = check_model(loaded)
    assert report.graph.sym is None, "reduced although an id may be told apart"
    assert any(f.kind == "STUCK" for f in report.findings), [f.kind for f in report.findings]


ALIKE = {
    "a count of the busy ones": ("", '''n = 0
    for u in TOOLS:
        if s["busy", u]:
            n += 1
    need(n >= 1, "none busy")'''),
    "a flag any one sets": ("", '''found = False
    for u in TOOLS:
        if s["busy", u] and u == t:
            found = True
    need(found, "not busy")'''),
    "a value read afresh for each": ("", '''for u in TOOLS:
        b = s["busy", u]
        if b and u == t:
            c = not b
            need(not c, "never")'''),
    "a value set on both branches": ("", '''for u in TOOLS:
        if s["busy", u]:
            w = 1
        else:
            w = 0
        need(w >= 0, "never")'''),
    "each one's own cells, through a helper": ('''def unpick(s, u):
    if s["pick", u]:
        s["pick", u] = False''', '''for u in TOOLS:
        unpick(s, u)
        s["pick", u] = s["pick", u] and s["busy", u]'''),
    "a shared flag every one sets alike": ("", '''for u in TOOLS:
        if s["busy", u]:
            s["mark"] = False'''),
    "a shared counter every one bumps": ("", '''for u in TOOLS:
        if s["busy", u] and s["pick", u]:
            s["count"] -= 1
    need(s["count"] >= 0, "below zero")'''),
    "each pair's own cells in nested loops": ('''PAIRS = [(a, b) for a in TOOLS for b in TOOLS]
m.field("link", [False, True], False, over=PAIRS)''', '''for u in TOOLS:
        for v in TOOLS:
            s["link", (u, v)] = False'''),
}


@pytest.mark.parametrize("how", list(ALIKE))
def test_a_loop_that_treats_every_id_alike_keeps_the_renaming(project, how):
    """The other side: a count, a flag any id can set, a value read afresh for each id,
    each id's own state cells (also through a helper), and a shared state cell that every
    id sets to the same constant or bumps by the same amount do not depend on the order of
    the ids, so the model is still explored up to renaming."""
    helpers, guard = ALIKE[how]
    project.flow("tools", CARRY.replace("HELPERS", helpers).replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert loaded.model.__dict__.get("_symmetry_doubt") is None, loaded.model.__dict__.get("_symmetry_doubt")
    assert check_model(loaded).graph.sym is not None


def test_two_loops_that_reuse_one_name_are_no_pick_by_place(project):
    """A loop over the ids whose name a later loop binds again: the later loop reads its own
    binding, not the id the first one kept. Reading it there was taken as a pick by place,
    a model error for a model that treats every id alike."""
    guard = '''for u in TOOLS:
        s["pick", u] = False
    for u in TOOLS:
        need(not s["pick", u], "picked")'''
    project.flow("tools", CARRY.replace("HELPERS", "").replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert loaded.model.__dict__.get("_symmetry_doubt") is None, loaded.model.__dict__.get("_symmetry_doubt")
    assert check_model(loaded).graph.sym is not None


@pytest.mark.parametrize("guard", ['''for u in TOOLS:
        pass
    for u in []:
        pass
    s["pick", u] = True''', '''for u in TOOLS:
        for u in TOOLS:
            pass
        s["pick", u] = True'''])
def test_a_loop_name_read_after_a_later_loop_is_still_a_pick_by_place(project, guard):
    project.flow("tools", CARRY.replace("HELPERS", "").replace("GUARD", guard))
    with pytest.raises(ModelError, match="keeps 'u' after it ends"):
        load_model(project.root / ".flowguard/flow/tools.py", project.root)


IN_DECLARED_ORDER = {
    "a rule, against a set": ('m.always("never the first alone", lambda s: tuple(s["busy", u] for u in TOOLS) '
                              'not in {(True, False)})', "pass", "BROKEN"),
    "a rule, against a list": ('m.always("never the first alone", lambda s: tuple(s["busy", u] for u in TOOLS) '
                               'not in [(True, False)])', "pass", "BROKEN"),
    "a rule, against a tuple": ('m.always("never the first alone", lambda s: [s["busy", u] for u in TOOLS] '
                                'not in ([True, False],))', "pass", "BROKEN"),
    "a rule, inside a list searched": ('m.always("never the first alone", lambda s: (True, False) '
                                       'not in [tuple(s["busy", u] for u in TOOLS)])', "pass", "BROKEN"),
    "a guard, against a set": ("", 'need(tuple(u == t for u in TOOLS) not in {(True, False)}, "the first stays busy")',
                               "STUCK"),
    "a guard, against a list": ("", 'need(tuple(u == t for u in TOOLS) not in [(True, False)], "the first stays busy")',
                                "STUCK"),
    "a guard, against a tuple": ("", 'need(tuple(u == t for u in TOOLS) not in ((True, False),), '
                                     '"the first stays busy")', "STUCK"),
    "a rule, a value of a list searched": ('m.always("never the first alone", lambda s: not any(v == (True, False) '
                                           'for v in [tuple(s["busy", u] for u in TOOLS)]))', "pass", "BROKEN"),
    "a guard, a loop over a list holding it": ("", 'for v in [tuple(u == t for u in TOOLS)]:\n'
                                                   '        need(v != (True, False), "the first stays busy")', "STUCK"),
    "progress when=": ('m.progress("the second is freed at once", over=TOOLS, when=lambda s, t: '
                       'tuple(u == t for u in TOOLS) in {(False, True)} and s["busy", t], goal=lambda s, t: False)',
                       "pass", "STUCK"),
}


def _never_reduced(project, helpers, guard, kind):
    project.flow("tools", CARRY.replace("HELPERS", helpers).replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    doubt = loaded.model.__dict__.get("_symmetry_doubt") or ""
    assert "a list in the declared order of the tool ids" in doubt, doubt
    report = check_model(loaded)
    assert report.graph.sym is None, "reduced although a tool may be told apart"
    plain = check_model(loaded, reduce=False)
    assert sorted((f.kind, f.subject, tuple(f.objects)) for f in report.findings) == \
        sorted((f.kind, f.subject, tuple(f.objects)) for f in plain.findings)
    assert any(f.kind == kind for f in report.findings), [f.kind for f in report.findings]


@pytest.mark.parametrize("how", list(IN_DECLARED_ORDER))
def test_a_list_in_the_declared_order_searched_for_in_a_container_is_never_reduced(project, how):
    """G3 round 4: a tuple of per-id values in the declared order, looked up with in / not
    in among literal tuples, tells T1 from T2 exactly as == against such a tuple does, and
    == was already a doubt. In a rule, a guard or a progress when= it was explored up to
    renaming: "clean, complete" for a rule only the first tool alone breaks, a stuck tool
    reported for both tools or missed. It is now a doubt: no renaming, the conflict found."""
    _never_reduced(project, *IN_DECLARED_ORDER[how])


VALS = 'tuple(s["busy", u] for u in TOOLS)'
ID_TEST = "tuple(u == t for u in TOOLS)"
INSIDE_AND_OR = {
    "or (), not in a set": (f'm.always("never the first alone", lambda s: ({VALS} or ()) not in {{(True, False)}})',
                            "pass", "BROKEN"),
    "True and, not in a set": (f'm.always("never the first alone", lambda s: (True and {VALS}) '
                               f'not in {{(True, False)}})', "pass", "BROKEN"),
    "or (), !=": (f'm.always("never the first alone", lambda s: ({VALS} or ()) != (True, False))', "pass", "BROKEN"),
    "and inside or": (f'm.always("never the first alone", lambda s: (({VALS} and {VALS}) or ()) '
                      f'not in {{(True, False)}})', "pass", "BROKEN"),
    "a guard, or ()": ("", f'need(({ID_TEST} or ()) not in {{(True, False)}}, "the first stays busy")', "STUCK"),
    "a guard, a name bound to or ()": ("", f'v = {ID_TEST} or ()\n    need(v not in {{(True, False)}}, '
                                           f'"the first stays busy")', "STUCK"),
    "progress when=, or ()": (f'm.progress("the second is freed at once", over=TOOLS, when=lambda s, t: '
                              f'({ID_TEST} or ()) in {{(False, True)}} and s["busy", t], goal=lambda s, t: False)',
                              "pass", "STUCK"),
}


@pytest.mark.parametrize("how", list(INSIDE_AND_OR))
def test_a_list_in_the_declared_order_inside_and_or_is_still_judged(project, how):
    """G3 round 5: the same per-id tuple wrapped in `or` / `and` (`(vals or ())`,
    `(True and vals)`) was not judged at all: an operand of and/or counted as a default and
    the and/or itself held nothing the rule followed. "clean, complete; tools explored up
    to renaming", exit 0, for a rule only the first tool alone breaks (--full: the objects
    are not interchangeable). The value of `a or b` is one of its operands, so it holds
    what they hold and is judged where it is used, as `a if c else b` already was."""
    _never_reduced(project, *INSIDE_AND_OR[how])


def test_and_or_over_values_the_rule_follows_differently_is_a_doubt(project):
    """The other side: an and/or (or an if-else) whose operands hold different things, one
    id and a list of ids, is judged by neither alone; it turns the renaming off. So does one
    that may give an id or a value the rule cannot follow (an id made from text): its use
    is judged by the id alone (test_an_id_in_a_container_or_text_...)."""
    guard = 'need((t or [u for u in TOOLS]) != "", "never")'
    project.flow("tools", CARRY.replace("HELPERS", "").replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    doubt = loaded.model.__dict__.get("_symmetry_doubt") or ""
    assert "picks between values the rule follows differently, or one it cannot follow" in doubt, doubt


@pytest.mark.parametrize("helpers, guard", [
    ("", 'need(True in tuple(u == t for u in TOOLS), "never")'),
    ("", 'need(s["busy", t] in (True, False), "never")'),
    ("", 'need(any(x for x in [s["busy", u] for u in TOOLS]), "none busy")'),
    ("", 'need(len([*(s["busy", u] for u in TOOLS)]) == 2, "never")')])
def test_a_search_among_values_in_the_declared_order_keeps_the_renaming(project, helpers, guard):
    """The other side: looking a value up among per-id values (whatever their order), a
    per-id value among constants, and the ids spread into a list treat every id alike."""
    project.flow("tools", CARRY.replace("HELPERS", helpers).replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert loaded.model.__dict__.get("_symmetry_doubt") is None, loaded.model.__dict__.get("_symmetry_doubt")
    assert check_model(loaded).graph.sym is not None


@pytest.mark.parametrize("guard", [
    'need(tuple(sorted(s["busy", u] for u in TOOLS)) not in {(False, True)}, "never")',
    'need(sorted(s["busy", u] for u in TOOLS)[0] or True, "never")',
    'need(set(s["busy", u] for u in TOOLS) != {True}, "never")',
    'need(frozenset([s["busy", u] for u in TOOLS]) != frozenset(), "never")'])
def test_per_id_values_sorted_or_put_in_a_set_keep_the_renaming(project, guard):
    """G3 round 5, minor: per-id values sorted by value, or put in a set, keep no
    trace of the declared order (the values are no ids, or ids the rule does not follow),
    yet a search or a comparison of them turned the renaming off, and [0] of the sorted
    values (the least value) was a model error ("picks one tool id by its place")."""
    project.flow("tools", CARRY.replace("HELPERS", "").replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert loaded.model.__dict__.get("_symmetry_doubt") is None, loaded.model.__dict__.get("_symmetry_doubt")
    assert check_model(loaded).graph.sym is not None


@pytest.mark.parametrize("guard, text", [
    ('need(next(iter({s["busy", u] for u in TOOLS})) or True, "never")', "next(...) picks one tool id"),
    ('for v in {s["busy", u] for u in TOOLS}:\n        need(v, "never")\n        break', "stops early"),
    ('need(sorted((s["busy", u] for u in TOOLS), key=lambda x: 0)[0] is not True, "the first stays busy")',
     "picks one tool id by its place"),
    ('need(tuple(set(s["busy", u] for u in TOOLS)) != (True,), "never")', None)])
def test_per_id_values_in_the_order_a_set_or_a_stable_sort_keeps_are_judged(project, guard, text):
    """The other side: a set iterates its items in the order they went in when their hashes
    collide (set(...) of per-id values already said so, {... for u in TOOLS} was not judged
    at all), and a sort by a key keeps the declared order among equal keys. Those uses are
    judged in the declared order: a pick by place is a model error, a comparison a doubt."""
    project.flow("tools", CARRY.replace("HELPERS", "").replace("GUARD", guard))
    path = project.root / ".flowguard/flow/tools.py"
    if text is not None:
        with pytest.raises(ModelError, match="treats tool ids asymmetrically") as err:
            load_model(path, project.root)
        assert text in err.value.text, err.value.text
        return
    loaded = load_model(path, project.root)
    assert "a list in the declared order" in (loaded.model.__dict__.get("_symmetry_doubt") or "")
    assert check_model(loaded).graph.sym is None


@pytest.mark.parametrize("guard", [
    'need(tuple(map(lambda u: s["busy", u], TOOLS)) not in {(True, False)}, "the first stays busy")',
    'need(len(list(filter(lambda u: s["busy", u], TOOLS))) != 1 or s["busy", t], "never")'])
def test_ids_passed_to_map_or_filter_are_a_doubt_not_a_model_error(project, guard):
    """G3 round 5, minor: map(f, TOOLS) and filter(f, TOOLS) were a model error ("uses
    TOOLS in a way that can tell the tool ids apart") whatever f did. The rule does not
    follow f, so the ids passed to it are a doubt: the model loads and is explored without
    renaming."""
    project.flow("tools", CARRY.replace("HELPERS", "").replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    doubt = loaded.model.__dict__.get("_symmetry_doubt") or ""
    assert "passes a tool id to " in doubt, doubt
    assert check_model(loaded).graph.sym is None


SECOND_ONLY = '"the second stays busy"'
HIDDEN = {
    "sorted = list": ("sorted = list", f"need(sorted(u == t for u in TOOLS) != [False, True], {SECOND_ONLY})"),
    "an import as set": ("from builtins import tuple as set",
                         f"need(set(u == t for u in TOOLS) != (False, True), {SECOND_ONLY})"),
    "frozenset = tuple": ("frozenset = tuple", f"need(frozenset(u == t for u in TOOLS) != (False, True), {SECOND_ONLY})"),
    "set = tuple around a tuple": ("set = tuple", f"need(set(tuple(u == t for u in TOOLS)) != (False, True), "
                                                  f"{SECOND_ONLY})"),
    "a loop target": ("for sorted in [list]:\n    pass",
                      f"need(sorted(u == t for u in TOOLS) != [False, True], {SECOND_ONLY})"),
    "a global set in a def": ("def _hide():\n    global sorted\n    sorted = list\n_hide()",
                              f"need(sorted(u == t for u in TOOLS) != [False, True], {SECOND_ONLY})"),
    "a lambda parameter": ("", f"need((lambda sorted=list: sorted(u == t for u in TOOLS))() != [False, True], "
                               f"{SECOND_ONLY})"),
    "a star import of a module the rule does not read": (
        "from app.util import *", f"need(sorted(u == t for u in TOOLS) != [False, True], {SECOND_ONLY})"),
    "a def named like a cache decorator": (
        "def cache(f):\n    return lambda x: x.endswith('2')\n@cache\ndef second(x):\n    return False",
        f"need(not second(t), {SECOND_ONLY})"),
    "an attribute named like a cache decorator": (
        "import types\nF = types.SimpleNamespace(cache=lambda f: (lambda x: x.endswith('2')))\n@F.cache\n"
        "def second(x):\n    return False", f"need(not second(t), {SECOND_ONLY})"),
}


@pytest.mark.parametrize("how", list(HIDDEN))
def test_a_builtin_hidden_by_any_binding_is_never_judged_as_the_builtin(project, how):
    """G3 round 6 (a): sorted(), set() and frozenset() of per-id values keep the renaming
    by the builtin's name, and only a def of that name was a doubt. `sorted = list`, `from
    builtins import tuple as set`, `frozenset = tuple`, a loop target, a global, a lambda
    parameter or a star import of a module the rule does not read hide the builtin as well:
    "clean, complete; tools explored up to renaming", exit 0, for a guard only the second
    tool fails (81aa362a: a doubt and the stuck tool found). A decorator named like a cache
    (a def named cache, an attribute .cache of anything but functools) was taken to keep the
    function it decorates. Each is now a doubt: no renaming, T2 found stuck."""
    helpers, guard = HIDDEN[how]
    project.file("app/__init__.py", "")
    project.file("app/util.py", "def sorted(x):\n    return list(x)\n")
    project.flow("tools", CARRY.replace("HELPERS", helpers).replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert loaded.model.__dict__.get("_symmetry_doubt"), "no doubt recorded"
    report = check_model(loaded)
    assert report.graph.sym is None, "reduced although a tool may be told apart"
    plain = check_model(loaded, reduce=False)
    assert sorted((f.kind, f.subject, tuple(f.objects)) for f in report.findings) == \
        sorted((f.kind, f.subject, tuple(f.objects)) for f in plain.findings)
    assert any(f.kind == "STUCK" for f in report.findings), [f.kind for f in report.findings]


@pytest.mark.parametrize("helpers, text", [
    ("import builtins", "imports the builtins module"),
    ("def _h():\n    return __builtins__", "__builtins__")])
def test_a_model_that_can_change_the_builtins_is_a_doubt(project, helpers, text):
    """The builtins module itself (import builtins, __builtins__) can rename any builtin the
    rule judges by name for every file at once (builtins.sorted = list): a doubt."""
    project.flow("tools", CARRY.replace("HELPERS", helpers).replace("GUARD", "pass"))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert text in (loaded.model.__dict__.get("_symmetry_doubt") or ""), loaded.model.__dict__.get("_symmetry_doubt")


@pytest.mark.parametrize("helpers, guard", [
    ("from builtins import sorted", 'need(sorted(s["busy", u] for u in TOOLS)[0] or True, "never")'),
    ("def label(id, max=2):\n    return id", 'need(label(t) == t, "never")'),
    ("from functools import lru_cache\n@lru_cache\ndef first(x):\n    return True", 'need(first(t), "never")'),
    ("import functools\n@functools.cache\ndef first(x):\n    return True", 'need(first(t), "never")')])
def test_the_real_builtin_or_a_parameter_never_called_keeps_the_renaming(project, helpers, guard):
    """The other side: an import of the builtin itself, flowguard's need, a cache from
    functools, and a parameter named like a builtin that is never called hide nothing."""
    project.flow("tools", CARRY.replace("HELPERS", helpers).replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert loaded.model.__dict__.get("_symmetry_doubt") is None, loaded.model.__dict__.get("_symmetry_doubt")
    assert check_model(loaded).graph.sym is not None


EQUAL_BUT_DIFFERENT = "(0 if u == t else False for u in TOOLS)"
PICKED_IN_ORDER = {
    "sorted, shown as text": f'need(str(sorted({EQUAL_BUT_DIFFERENT})) != "[False, 0]", {SECOND_ONLY})',
    "sorted in reverse": f'need(str(sorted({EQUAL_BUT_DIFFERENT}, reverse=True)) != "[False, 0]", {SECOND_ONLY})',
    "max, shown as text": f'need(str(max({EQUAL_BUT_DIFFERENT})) != "False", {SECOND_ONLY})',
    "min, tested with is": f'need(min({EQUAL_BUT_DIFFERENT}) is not False, {SECOND_ONLY})',
    "max with a key": f'need(max((u == t for u in TOOLS), key=lambda v: 0), {SECOND_ONLY})',
    "min with a key": f'need(min((u == t for u in TOOLS), key=lambda v: 0), {SECOND_ONLY})',
    "max of two lists": f'need(max([u == t for u in TOOLS], [False, False]) != [False, True], {SECOND_ONLY})',
    "sum of lists": f'need(sum(([u == t] for u in TOOLS), []) != [False, True], {SECOND_ONLY})',
    "sum of tuples": f'need(sum(((u == t,) for u in TOOLS), ()) != (False, True), {SECOND_ONLY})',
}


@pytest.mark.parametrize("how", list(PICKED_IN_ORDER))
def test_per_id_values_sorted_picked_or_added_where_the_order_shows_are_never_reduced(project, how):
    """G3 round 6 (b): a stable sort, min() and max() keep the first of equal values, so
    per-id values that compare equal but differ (0 and False) come out in the declared
    order: str(sorted(...)) told T1 from T2 under renaming ("clean, complete" for a guard
    only the second tool fails; 81aa362a: a doubt). The same holds for min()/max() with a
    key (the first of the values the key ranks alike), max() of the list itself against
    another list (compared in the declared order), and sum() of lists, tuples or floats
    (joined and rounded in order). Each is now a doubt: no renaming, T2 found stuck."""
    project.flow("tools", CARRY.replace("HELPERS", "").replace("GUARD", PICKED_IN_ORDER[how]))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert loaded.model.__dict__.get("_symmetry_doubt"), "no doubt recorded"
    report = check_model(loaded)
    assert report.graph.sym is None, "reduced although a tool may be told apart"
    plain = check_model(loaded, reduce=False)
    assert sorted((f.kind, f.subject, tuple(f.objects)) for f in report.findings) == \
        sorted((f.kind, f.subject, tuple(f.objects)) for f in plain.findings)
    assert any(f.kind == "STUCK" for f in report.findings), [f.kind for f in report.findings]


def test_a_sum_of_per_id_floats_is_a_doubt(project):
    """Floats are rounded in the order they are added: on Python 3.11, sum([0.1, 1e16], 1.0)
    and sum([1e16, 0.1], 1.0) differ (3.12 compensates, but no exactness is promised)."""
    guard = f'need(sum((1e16 if u == t else 0.1 for u in TOOLS), 1.0) != 1e16, {SECOND_ONLY})'
    project.flow("tools", CARRY.replace("HELPERS", "").replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert "sum() of per-id values that are no whole numbers" in (loaded.model.__dict__.get("_symmetry_doubt") or "")
    assert check_model(loaded).graph.sym is None


@pytest.mark.parametrize("guard", [
    'need(max(s["count"] + (u == t) for u in TOOLS) >= 0, "never")',
    'need(sum(1 for u in TOOLS if s["busy", u]) <= 2, "never")',
    'need(sum(s["busy", u] for u in TOOLS) <= 2, "never")',
    'need(min(str(s["busy", u]) for u in TOOLS) != "", "never")',
    'need(str(sorted((s["busy", u], s["pick", u]) for u in TOOLS)) != "", "never")',
    'vals = [s["busy", u] for u in TOOLS]\n    need(str(max(vals)) != "", "never")'])
def test_per_id_values_that_are_equal_only_when_the_same_keep_the_renaming(project, guard):
    """The other side: whole numbers, flags and texts sorted, picked or added give the same
    result in every order of the ids (equal values are the same value, sums are exact)."""
    project.flow("tools", CARRY.replace("HELPERS", "").replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert loaded.model.__dict__.get("_symmetry_doubt") is None, loaded.model.__dict__.get("_symmetry_doubt")
    assert check_model(loaded).graph.sym is not None


IN_A_COMPREHENSION = {
    "a list comprehension": f'need([{ID_TEST} for _ in (0,)] != [(False, True)], {SECOND_ONLY})',
    "a set comprehension": f'need({{{ID_TEST} for _ in (0,)}} != {{(False, True)}}, {SECOND_ONLY})',
    "a generator in set()": f'need(set({ID_TEST} for _ in (0,)) != {{(False, True)}}, {SECOND_ONLY})',
    "a generator searched with in": f'need((False, True) not in ({ID_TEST} for _ in range(1)), {SECOND_ONLY})',
    "a dict comprehension's value": f'need({{1: {ID_TEST} for _ in (0,)}} != {{1: (False, True)}}, {SECOND_ONLY})',
    "a dict comprehension's key": f'need({{{ID_TEST}: 1 for _ in (0,)}} != {{(False, True): 1}}, {SECOND_ONLY})',
    "a comprehension over a generator": f'need({{x for x in ({ID_TEST} for _ in (0,))}} != {{(False, True)}}, '
                                        f'{SECOND_ONLY})',
    "rows of a comprehension over the ids": f'need(not any(r == (False, True) for r in [{ID_TEST} for _ in TOOLS]), '
                                            f'{SECOND_ONLY})',
    "an id among a dict's values": f'need(not {{0: t}}[0].endswith("2"), {SECOND_ONLY})',
}


@pytest.mark.parametrize("how", list(IN_A_COMPREHENSION))
def test_a_list_in_the_declared_order_made_the_item_of_a_comprehension_is_never_reduced(project, how):
    """G3 round 6 (c): a tuple of per-id values in the declared order put into a display
    ([v], {v}, {1: v}) was a doubt, but the same tuple as the item of a list, set,
    generator or dict comprehension (`[v for _ in (0,)]`, `{1: v for _ in (0,)}`) was not
    judged, and the comprehension held "ids in data order": "clean, complete" for a guard
    only the second tool fails. An id among a mapping's values was not followed at all
    (`{0: t}[0]` is t). Both are now a doubt: no renaming, T2 found stuck."""
    project.flow("tools", CARRY.replace("HELPERS", "").replace("GUARD", IN_A_COMPREHENSION[how]))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert loaded.model.__dict__.get("_symmetry_doubt"), "no doubt recorded"
    report = check_model(loaded)
    assert report.graph.sym is None, "reduced although a tool may be told apart"
    plain = check_model(loaded, reduce=False)
    assert sorted((f.kind, f.subject, tuple(f.objects)) for f in report.findings) == \
        sorted((f.kind, f.subject, tuple(f.objects)) for f in plain.findings)
    assert any(f.kind == "STUCK" for f in report.findings), [f.kind for f in report.findings]


def test_a_comprehension_item_in_a_progress_when_is_never_reduced(project):
    """The reviewer's progress form: the reduced run reported T1 stuck, the plain run T2."""
    when = f"[{ID_TEST} for _ in (0,)] == [(False, True)] and s['busy', t]"
    text = CARRY.replace("HELPERS", "").replace("GUARD", "pass").replace(
        "MODEL = m", f'm.progress("the second is freed at once", over=TOOLS, when=lambda s, t: {when}, '
                     f'goal=lambda s, t: False)\nMODEL = m')
    project.flow("tools", text)
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert loaded.model.__dict__.get("_symmetry_doubt"), "no doubt recorded"
    assert check_model(loaded).graph.sym is None


RETURNED = {
    "a lambda called where it stands": ("", f"need((lambda: {ID_TEST})() != (False, True), {SECOND_ONLY})"),
    "a lambda bound to a name": ("", f"get = lambda: {ID_TEST}\n    need(get() != (False, True), {SECOND_ONLY})"),
    "a lambda in a list": ("", f"need([lambda: {ID_TEST}][0]() != (False, True), {SECOND_ONLY})"),
    "a lambda's default": ("", f"need((lambda v={ID_TEST}: v)() != (False, True), {SECOND_ONLY})"),
    "a lambda passed to a helper": ("def call(f):\n    return f()",
                                    f"need(call(lambda: {ID_TEST}) != (False, True), {SECOND_ONLY})"),
    "a def passed to a helper": ("def call(f):\n    return f()",
                                 f"def get():\n        return {ID_TEST}\n    need(call(get) != (False, True), "
                                 f"{SECOND_ONLY})"),
    "a def bound to another name": ("", f"def get():\n        return {ID_TEST}\n    other = get\n"
                                        f"    need(other() != (False, True), {SECOND_ONLY})"),
    "a helper that returns a set of it": ("def vals(t):\n    return set(tuple(u == t for u in TOOLS) for _ in (0,))",
                                          f"need(vals(t) != {{(False, True)}}, {SECOND_ONLY})"),
}


@pytest.mark.parametrize("how", list(RETURNED))
def test_ids_a_function_returns_where_the_rule_does_not_follow_the_call_are_never_reduced(project, how):
    """G3 round 6 (c): what a helper returns is followed to the calls of it by name. A
    lambda's value goes to whoever calls the lambda (`(lambda: v)()`, a name bound to it, a
    helper it is passed to), and so does a def's when it is passed or renamed: none of
    those calls was judged, "clean, complete" for a guard only the second tool fails. Ids
    returned by a function that the engine does not call, and that is not only called by
    its name, are now a doubt: no renaming, T2 found stuck."""
    helpers, guard = RETURNED[how]
    project.flow("tools", CARRY.replace("HELPERS", helpers).replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert loaded.model.__dict__.get("_symmetry_doubt"), "no doubt recorded"
    report = check_model(loaded)
    assert report.graph.sym is None, "reduced although a tool may be told apart"
    plain = check_model(loaded, reduce=False)
    assert sorted((f.kind, f.subject, tuple(f.objects)) for f in report.findings) == \
        sorted((f.kind, f.subject, tuple(f.objects)) for f in plain.findings)
    assert any(f.kind == "STUCK" for f in report.findings), [f.kind for f in report.findings]


@pytest.mark.parametrize("helpers, guard", [
    ("def same(x):\n    return x", 'need(same(t) == t, "never")'),
    ("", 'need(all(x == x for x in [t for _ in (0,)]), "never")'),
    ("", 'need(any(v == t for v in {t: 1}), "never")'),
    ("def offered(s, t):\n    return t if s['busy', t] else None\nm.option('free', offered, t=TOOLS)", "pass")])
def test_ids_returned_to_calls_the_rule_follows_keep_the_renaming(project, helpers, guard):
    """The other side: a helper called by its name, an id as the item of a comprehension or
    as a mapping's key, and a function the engine calls (its value is only taken as true or
    false) treat every id alike."""
    project.flow("tools", CARRY.replace("HELPERS", helpers).replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert loaded.model.__dict__.get("_symmetry_doubt") is None, loaded.model.__dict__.get("_symmetry_doubt")
    assert check_model(loaded).graph.sym is not None


@pytest.mark.parametrize("helpers, guard", [
    ('m.field("held", [frozenset(), frozenset({"a"}), frozenset({"b"})], frozenset(), over=TOOLS)',
     'need(str(sorted(s["held", u] for u in TOOLS)) != "", "never")'),
    ("vals = [0, False]", 'global vals\n    need(str(max(vals)) != "", "never")\n    vals = [s["busy", u] for u in TOOLS]')])
def test_per_id_values_the_rule_cannot_rank_alike_in_every_order_are_a_doubt(project, helpers, guard):
    """Sets are only partly ordered: sorted() and max() keep the declared order among sets
    neither of which holds the other ({'a'} and {'b'}), as among equal values that differ.
    And a name the function declares global may hold what another function put there, so
    its own assignments do not tell its values."""
    project.flow("tools", CARRY.replace("HELPERS", helpers).replace("GUARD", guard))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert "keeps the first of them in the declared order" in (loaded.model.__dict__.get("_symmetry_doubt") or ""), \
        loaded.model.__dict__.get("_symmetry_doubt")
    assert check_model(loaded).graph.sym is None


STORE = '''
from flowguard.flow import Model, need
m = Model("tools")
TOOLS = m.objects("tool", "T1", "T2")
SNAPS = [(a, b) for a in ("idle", "busy") for b in ("idle", "busy")]
m.field("busy", ["idle", "busy"], "idle", over=TOOLS, source="R1")
m.field("log", SNAPS, ("idle", "idle"))
m.field("seen", SNAPS, ("idle", "idle"), over=TOOLS)
HELP

@m.action(t=TOOLS, source="R1")
def take(s, t):
    need(s["busy", t] == "idle", "busy")
    s["busy", t] = "busy"

@m.action(t=TOOLS, source="R1")
def free(s, t):
    need(s["busy", t] == "busy", "not busy")
    s["busy", t] = "idle"

ACT
RULE
MODEL = m
'''
NOT_SECOND_ALONE = "m.always('x', lambda s: s['log'] != ('idle', 'busy'), source='R1')"
WRITE_LOG = "@m.action(source='R1')\ndef write_log(s):\n    "
STORED = {   # the reviewer's nine variants (rf3/sym/cases_store2.py), plus a writer helper and a kind list
    "a tuple of a generator": (WRITE_LOG + "s['log'] = tuple(s['busy', u] for u in TOOLS)", NOT_SECOND_ALONE, ""),
    "through a name": (WRITE_LOG + "v = tuple(s['busy', u] for u in TOOLS)\n    s['log'] = v", NOT_SECOND_ALONE, ""),
    "a tuple of a list comprehension": (WRITE_LOG + "s['log'] = tuple([s['busy', u] for u in TOOLS])",
                                        NOT_SECOND_ALONE, ""),
    "a helper's result": (WRITE_LOG + "s['log'] = snap(s)", NOT_SECOND_ALONE,
                          "def snap(s):\n    return tuple(s['busy', u] for u in TOOLS)"),
    "a per-id field": ("@m.action(t=TOOLS, source='R1')\ndef look(s, t):\n    s['seen', t] = tuple(s['busy', u] for u in TOOLS)",
                       "m.always('x', lambda s: all(s['seen', u] != ('idle', 'busy') for u in TOOLS), source='R1')", ""),
    "a parameterised writer": ("@m.action(t=TOOLS, source='R1')\ndef write_log(s, t):\n    need(s['busy', t] == 'busy', 'idle')\n"
                               "    s['log'] = tuple(s['busy', u] for u in TOOLS)", NOT_SECOND_ALONE, ""),
    "starred": (WRITE_LOG + "s['log'] = (*(s['busy', u] for u in TOOLS),)", NOT_SECOND_ALONE, ""),
    "a rule reading one place": (WRITE_LOG + "s['log'] = tuple(s['busy', u] for u in TOOLS)",
                                 "m.always('x', lambda s: s['log'][0] == 'busy' or s['log'][1] == 'idle', source='R1')", ""),
    "a guard reading it": (WRITE_LOG + "s['log'] = tuple(s['busy', u] for u in TOOLS)\n@m.action(t=TOOLS, source='R1')\n"
                           "def alarm(s, t):\n    need(s['log'] == ('idle', 'busy'), 'no')\n    s['busy', t] = 'busy'",
                           "m.always('y', lambda s: True, source='R1')", ""),
    "a helper that writes it": (WRITE_LOG + "put(s, tuple(s['busy', u] for u in TOOLS))", NOT_SECOND_ALONE,
                                "def put(s, v):\n    s['log'] = v"),
    "a list comprehension written through a name": (WRITE_LOG + "row = [s['busy', u] for u in TOOLS]\n"
                                                    "    s['log'] = tuple(row)", NOT_SECOND_ALONE, ""),
}


@pytest.mark.parametrize("how", list(STORED))
def test_per_id_values_in_the_declared_order_written_into_the_state_are_never_reduced(project, how):
    """Acceptance A4: a tuple of per-id values in the declared order compared as a whole was a
    doubt, but the same tuple written into a state field was never judged: the field keeps
    the order of the tool ids, and a rule or guard reading it told them apart unseen ("clean,
    complete" for a rule `take(T2) ; write_log()` breaks, a false NEVER REACHED for a guard).
    Writing it into the state is now a doubt: no renaming, and the reduced and plain checks
    find the same."""
    act, rule, help_ = STORED[how]
    project.flow("tools", STORE.replace("ACT", act).replace("RULE", rule).replace("HELP", help_))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    doubt = loaded.model.__dict__.get("_symmetry_doubt") or ""
    assert "into the state" in doubt, doubt
    report = check_model(loaded)
    assert report.graph.sym is None, "reduced although the stored order tells the tools apart"
    plain = check_model(loaded, reduce=False)
    assert sorted((f.cls, f.kind, f.subject, tuple(f.objects)) for f in report.findings) == \
        sorted((f.cls, f.kind, f.subject, tuple(f.objects)) for f in plain.findings)


@pytest.mark.parametrize("write", [
    "s['n'] = sum(s['busy', u] == 'busy' for u in TOOLS)",
    "s['n'] = len([u for u in TOOLS if s['busy', u] == 'busy'])",
    "s['all'] = frozenset(s['busy', u] for u in TOOLS)",
    "s['all'] = frozenset(s['busy', u] for u in TOOLS if s['busy', u] == 'busy')",
    "s['n'] = min(2, sum(1 for u in TOOLS if s['busy', u] == 'busy'))",
])
def test_what_every_order_of_the_ids_gives_alike_may_be_written_and_keeps_the_renaming(project, write):
    """The other side: a count, or a set, of the per-id values is the same in every order of the
    ids, so writing it into the state tells no tool apart."""
    text = STORE.replace("HELP", 'm.field("n", range(0, 3), 0)\nm.field("all", [frozenset(), frozenset({"idle"}), '
                                 'frozenset({"busy"}), frozenset({"idle", "busy"})], frozenset())')
    text = text.replace("ACT", WRITE_LOG + write).replace("RULE", "")
    project.flow("tools", text)
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert loaded.model.__dict__.get("_symmetry_doubt") is None, loaded.model.__dict__.get("_symmetry_doubt")
    assert check_model(loaded).graph.sym is not None
