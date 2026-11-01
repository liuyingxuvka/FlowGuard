"""FG-812 classes: conflicts versus model warnings (M3).

With every rule removed (the shim's drop_rules flag), the generic checks alone still report
the dead end, the never-happening actions, the offered-but-refused option and the
unreachable declared end as conflicts, while wide counter domains are warnings only.
"""
from __future__ import annotations

import pytest

from flowguard._next.checks import CONFLICT, WARNING, check_model
from flowguard._next.model import Loaded, load_model

from conftest import DATA
from golden_machine import load_machines

MODELS = DATA / "golden" / "models"


def report_of(path, n=0, drop_rules=True):
    model = load_machines(path, drop_rules=drop_rules)[n]
    assert not model.rules or not drop_rules
    return check_model(Loaded(model, ()))


def by_class(report, cls):
    return [f for f in report.findings if f.cls == cls]


def test_dead_end_without_rules_is_a_conflict():
    report = report_of(MODELS / "e7_mach_sonnet1_R10" / "model.py")
    stuck = [f for f in by_class(report, CONFLICT) if f.kind == "STUCK"]
    assert [f.subject for f in stuck] == ["branch[*] = 'east'"]
    assert stuck[0].objects == ("T1", "T2")             # one finding for both tools
    assert stuck[0].detail["consequences"] == ["cond[*] = 'repair'"]
    assert len(stuck[0].path) == 4


def test_never_happens_is_a_conflict_and_wide_counters_are_warnings():
    report = report_of(MODELS / "e7b_machine_haiku1" / "model.py")
    conflicts = [f.subject for f in by_class(report, CONFLICT)]
    assert conflicts == ["action inspect_pass", "action inspect_fail"]
    raw_warnings = [f for f in report.raw if f.cls == WARNING]
    assert len(raw_warnings) == 11                       # 10 counter values and where='inspection'
    assert {f.kind for f in raw_warnings} == {"NEVER REACHED"}
    assert "value where[*] = 'inspection'" in {f.subject for f in raw_warnings}
    inspect = next(f for f in report.findings if f.subject == "action inspect_pass")
    assert inspect.detail["explained"] == ["maintain_every=0", "maintain_every=8", "inspect_every=1",
                                           "inspect_every=2"]


def test_worded_screen_option_refused_is_a_conflict():
    report = report_of(MODELS / "e7_mach_haiku2_R11" / "variants.py", n=0)
    contra = [f for f in by_class(report, CONFLICT) if f.kind == "CONTRADICTION"]
    assert [f.subject for f in contra] == ["option 'bring'"]
    assert contra[0].detail["reason"] == "not held for them elsewhere, or not on the shelf"
    assert len(contra[0].path) == 7


def test_unreachable_declared_end_is_a_conflict(project):
    project.flow_from(DATA / "planted" / "tool_life_end_unreachable.py", "tools")
    report = check_model(load_model(project.root / ".flowguard/flow/tools.py", project.root))
    end = next(f for f in report.findings if f.subject == "value cond[*] = 'retired'")
    assert end.cls == CONFLICT and end.detail["why"] == "declared end"


SOURCED = '''
from flowguard._next import Model, need

m = Model("lamp")
m.field("light", ["off", "on", "blinking"], "off", source="R1")

@m.action(source="R1")
def switch(s):
    s["light"] = "on" if s["light"] == "off" else "off"

m.always("the lamp never blinks", lambda s: s["light"] != "blinking"{rule_source})
MODEL = m
'''


def test_value_named_by_a_sourced_rule_is_a_conflict_unsourced_a_warning(project):
    project.flow("sourced", SOURCED.format(rule_source=', source="R2"'))
    project.flow("unsourced", SOURCED.format(rule_source=""))
    flow = project.root / ".flowguard" / "flow"
    sourced = check_model(load_model(flow / "sourced.py", project.root))
    unsourced = check_model(load_model(flow / "unsourced.py", project.root))
    [a] = [f for f in sourced.findings if f.subject == "value light = 'blinking'"]
    [b] = [f for f in unsourced.findings if f.subject == "value light = 'blinking'"]
    assert (a.cls, b.cls) == (CONFLICT, WARNING)
    assert a.detail["why"] == "named by always 'the lamp never blinks'"
    assert set(a.sources) == {"R1", "R2"}


def test_value_with_a_value_source_is_a_conflict(project):
    project.flow("lamp", SOURCED.format(rule_source="").replace(
        'source="R1")\n\n@m.action', 'source="R1", value_sources={"blinking": "R3"})\n\n@m.action'))
    report = check_model(load_model(project.root / ".flowguard/flow/lamp.py", project.root))
    [f] = [f for f in report.findings if f.subject == "value light = 'blinking'"]
    assert f.cls == CONFLICT and f.sources == ("R3",)


def test_output_order_is_conflicts_then_warnings_then_errors():
    report = report_of(MODELS / "e7b_machine_haiku1" / "model.py", drop_rules=False)
    order = [f.cls for f in report.findings]
    assert order == sorted(order, key=["conflict", "warning", "error"].index)


SHELF = '''
from flowguard._next import Model, need

m = Model("shelf")
BOOKS = m.objects("book", "B1", "B2")
m.field("where", ["shelf", "loan", "repair"], "shelf", over=BOOKS, source="R1", value_sources={"repair": "R4"})

@m.action(b=BOOKS, source="R1")
def lend(s, b):
    need(s["where", b] == "shelf", "not on the shelf")
    s["where", b] = "loan"

@m.action(b=BOOKS, source="R1")
def give_back(s, b):
    need(s["where", b] == "loan", "not on loan")
    s["where", b] = "shelf"

@m.action(b=BOOKS, source="R4")
def damaged(s, b):
    need(s["where", b] == "loan", "not on loan")
    s["where", b] = "repair"
EXTRA
MODEL = m
'''


def test_a_value_never_left_where_its_object_freezes_is_a_dead_end(project):
    """G8 (s1aplan/undeclared_end.md): a value no state leaves, after which nothing of the
    object ever changes again, is a STUCK conflict unless m.terminal declares it. A book sent
    to repair that never comes back is not taken as the end of its life any more."""
    flow = project.root / ".flowguard" / "flow"
    project.flow("forgotten", SHELF.replace("EXTRA", ""))
    report = check_model(load_model(flow / "forgotten.py", project.root))
    [end] = [f for f in report.findings if f.kind == "STUCK"]
    assert end.cls == CONFLICT and end.subject == "where[*] = 'repair'" and end.objects == ("B1", "B2")
    assert end.detail["stuck"] == "end" and end.path == ("lend(b='B1')", "damaged(b='B1')")
    assert "R4" in end.sources and "R1" in end.sources
    assert "m.terminal('where', ['repair'])" in end.text and "B1 stuck with where='repair'" in end.text
    assert not [f for f in report.findings if f.kind == "UNDECLARED END"]
    project.flow("declared", SHELF.replace("EXTRA", 'm.terminal("where", ["repair"], source="R4")'))
    report = check_model(load_model(flow / "declared.py", project.root))
    assert not [f for f in report.findings if f.cls == CONFLICT]
    project.flow("fixed", SHELF.replace("EXTRA", '''
@m.action(b=BOOKS, source="R4")
def repaired(s, b):
    need(s["where", b] == "repair", "not in repair")
    s["where", b] = "shelf"
'''))
    report = check_model(load_model(flow / "fixed.py", project.root))
    assert report.findings == []


MARKER = '''
from flowguard._next import Model, need

m = Model("marker")
BOOKS = m.objects("book", "B1", "B2")
m.field("where", ["shelf", "loan", "repair"], "shelf", over=BOOKS, source="R1")
m.field("flag", ["new", "used"], "new", over=BOOKS, source="R1", note="set on the first loan, never reset")
m.field("mended", [0, 1], 0, over=BOOKS, source="R4")

@m.action(b=BOOKS, source="R1")
def lend(s, b):
    need(s["where", b] == "shelf", "not on the shelf")
    s["where", b], s["flag", b] = "loan", "used"

@m.action(b=BOOKS, source="R1")
def give_back(s, b):
    need(s["where", b] == "loan", "not on loan")
    s["where", b] = "shelf"

@m.action(b=BOOKS, source="R4")
def damaged(s, b):
    need(s["where", b] == "loan", "not on loan")
    s["where", b] = "repair"

@m.action(b=BOOKS, source="R4")
def repaired(s, b):
    need(s["where", b] == "repair", "not in repair")
    need(s["mended", b] < 1, "mended once already")
    s["where", b], s["mended", b] = "shelf", 1
MODEL = m
'''


def test_a_one_way_marker_is_no_end_and_hides_no_dead_end(project):
    """A value never left after which the object still changes (a flag set once) ends
    nothing: it is no finding, and it does not hide the dead end of the object's other
    fields (a book mended once and damaged again stays in repair)."""
    project.flow("marker", MARKER)
    report = check_model(load_model(project.root / ".flowguard/flow/marker.py", project.root))
    assert [(f.kind, f.subject) for f in report.findings if f.cls == CONFLICT] == [("STUCK", "where[*] = 'repair'")]
    assert not [f for f in report.findings if "flag" in f.subject]
    assert report.reach["ends"] == []


WAITING = '''
from flowguard._next import Model, need

m = Model("waiting")
BOOKS = m.objects("book", "B1", "B2")
m.field("where", ["shelf", "loan", "repair"], "shelf", over=BOOKS, source="R1", value_sources={"repair": "R4"})
m.field("waiting", range(0, 3), 0, over=BOOKS, source="R4", note="nights in repair, 0..2")

@m.action(b=BOOKS, source="R1")
def lend(s, b):
    need(s["where", b] == "shelf", "not on the shelf")
    s["where", b] = "loan"

@m.action(b=BOOKS, source="R1")
def give_back(s, b):
    need(s["where", b] == "loan", "not on loan")
    s["where", b] = "shelf"

@m.action(b=BOOKS, source="R4")
def damaged(s, b):
    need(s["where", b] == "loan", "not on loan")
    s["where", b], s["waiting", b] = "repair", 0

@m.action(source="R4")
def night(s):
    for b in BOOKS:
        if s["where", b] == "repair":
            s["waiting", b] = min(s["waiting", b] + 1, 2)
MODEL = m
'''


def test_a_dead_end_with_a_counter_that_still_ticks_is_a_dead_end(project):
    """G8 (round 2): a book sent to repair that nothing repairs, with a counter that still
    ticks there until it is clamped, comes to a halt: only finitely many changes follow the
    value, then nothing of the book changes again. It is a dead end (it once was "clean")."""
    project.flow("waiting", WAITING)
    report = check_model(load_model(project.root / ".flowguard/flow/waiting.py", project.root))
    [end] = [f for f in report.findings if f.cls == CONFLICT]
    assert end.kind == "STUCK" and end.subject == "where[*] = 'repair'" and end.detail["stuck"] == "end"
    assert "B1 stuck with where='repair', waiting=2" in end.text
    assert end.path == ("lend(b='B1')", "damaged(b='B1')", "night()", "night()")
    assert "m.terminal('where', ['repair'])" in end.text


RESERVE = '''

@m.action(b=BOOKS, source="R5")
def reserve(s, b):
    need(not s["reserved", b], "reserved already")
    s["reserved", b] = True


@m.action(b=BOOKS, source="R5")
def cancel(s, b):
    need(s["reserved", b], "not reserved")
    s["reserved", b] = False
'''

ONLY_WHERE = '''
from flowguard._next import Model, need

m = Model("shelf")
BOOKS = m.objects("book", "B1", "B2")
m.field("where", ["shelf", "loan", "repair"], "shelf", over=BOOKS, source="R1", value_sources={"repair": "R4"})
m.field("reserved", [False, True], False, over=BOOKS, source="R5")

@m.action(b=BOOKS, source="R1")
def lend(s, b):
    need(s["where", b] == "shelf", "not on the shelf")
    s["where", b] = "loan"

@m.action(b=BOOKS, source="R1")
def give_back(s, b):
    need(s["where", b] == "loan", "not on loan")
    s["where", b] = "shelf"

@m.action(b=BOOKS, source="R4")
def damaged(s, b):
    need(s["where", b] == "loan", "not on loan")
    s["where", b] = "repair"
''' + RESERVE + "MODEL = m\n"


@pytest.mark.parametrize("name", ["desk", "only_where"])
def test_a_dead_end_where_only_a_side_flag_still_toggles_is_a_dead_end(project, name):
    """G8 round 2: books go to repair and nothing repairs them, while a member can reserve
    and cancel a book in any state. The reservation keeps toggling, so the book never comes
    to a halt and the halting rule took repair for a one-way marker: "clean, complete",
    exit 0. A value no state leaves after which the object can never again take steps it
    took before (lend, give back: all but the one that entered it) is a dead end too."""
    if name == "desk":
        project.file("app/__init__.py", "")
        for p in (DATA / "desk" / "app").glob("*.py"):
            project.file(f"app/{p.name}", p.read_text(encoding="utf-8"))
        text = (DATA / "desk" / "desk_naive.py").read_text(encoding="utf-8").replace(
            'm.field("renewed"', 'm.field("reserved", [False, True], False, over=BOOKS, source="R5")\nm.field("renewed"')
        text = text.replace("\nm.option(", RESERVE + "\nm.option(", 1)
    else:
        text = ONLY_WHERE
    project.flow("desk", text)
    report = check_model(load_model(project.root / ".flowguard/flow/desk.py", project.root))
    [end] = [f for f in report.findings if f.cls == CONFLICT and f.subject == "where[*] = 'repair'"]
    assert end.kind == "STUCK" and end.detail["stuck"] == "end", end.text
    assert "B1 stuck with where='repair'" in end.text
    assert "can never again" in end.text and "lend" in end.text and "give_back" in end.text
    assert "m.terminal('where', ['repair'])" in end.text


FUSE = '''
from flowguard._next import Model, need

m = Model("lamps")
LAMPS = m.objects("lamp", "L1", "L2")
m.field("state", ["off", "on"], "off", over=LAMPS, source="R1")
m.field("fuse", ["ok", "blown"], "ok", source="R2")
m.field("count", range(0, 3), 0, source="R3")

@m.action(l=LAMPS, source="R1")
def switch_on(s, l):
    need(s["state", l] == "off", "not off")
    s["state", l] = "on"
    s["count"] = min(s["count"] + 1, 2)
    if s["count"] == 2:
        s["fuse"] = "blown"

@m.action(l=LAMPS, source="R1")
def switch_off(s, l):
    need(s["state", l] == "on", "not on")
    need(s["fuse"] == "ok", "no power")
    s["state", l] = "off"
    s["count"] = 0

@m.action(source="R4")
def replace_fuse(s):
    need(s["fuse"] == "blown", "the fuse is fine")
    need(s["count"] == 0, "the meter is not reset", source="R4")
    s["fuse"] = "ok"
MODEL = m
'''


def test_a_dead_end_names_the_exit_that_never_works_anywhere(project):
    """G2 round 2: the refusals of a STUCK report are every call refused where the object is
    stuck that names no other object, not only the calls that change it somewhere: an exit
    that never succeeds anywhere (replace_fuse, refused by R4) is the real cause and is named
    with its request; it once showed only as a separate NEVER REACHED action."""
    project.flow("lamps", FUSE)
    report = check_model(load_model(project.root / ".flowguard/flow/lamps.py", project.root))
    [stuck] = [f for f in report.findings if f.kind == "STUCK"]
    refused = {(r["call"], r["reason"], r["source"]) for r in stuck.detail["refused"]}
    assert ("replace_fuse()", "the meter is not reset", "R4") in refused
    assert ("switch_off(l='L1')", "no power", "R1") in refused
    assert not any("L2" in call for call, _, _ in refused)
    assert "R4" in stuck.sources


DOOR = '''
from flowguard._next import Model, need

m = Model("door")
m.field("count", range(0, 3), 0, source="R2")
m.field("state", ["open", "locked"], "open", source="R1")

@m.action(source="R1")
def lock(s):
    need(s["state"] == "open", "not open")
    s["state"], s["count"] = "locked", min(s["count"] + 1, 2)

@m.action(source="R1")
def unlock(s):
    need(s["state"] == "locked", "not locked")
    need(s["count"] < 2, "worn out", source="R4")
    s["state"] = "open"

@m.action(source="R2")
def wear(s):
    need(s["state"] == "open", "not open")
    s["count"] = 2

@m.action(source="R2")
def reset(s):
    need(s["state"] == "open", "not open")
    s["count"] = 0
MODEL = m
'''


def test_a_dead_end_is_named_by_its_state_not_by_a_counter(project):
    """G2 round 2: where a counter value and a text value are stuck in the same states, the
    report is named by the text value (the counter is folded under it), not by the counter."""
    project.flow("door", DOOR)
    report = check_model(load_model(project.root / ".flowguard/flow/door.py", project.root))
    [stuck] = [f for f in report.findings if f.kind == "STUCK"]
    assert stuck.subject == "state = 'locked'"
    assert stuck.detail["folded"] == {"count": 1, "fields": ["count"]}
    assert ("unlock()", "worn out", "R4") in {(r["call"], r["reason"], r["source"]) for r in stuck.detail["refused"]}
