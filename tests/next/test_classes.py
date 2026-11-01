"""FG-812 classes: conflicts versus model warnings (M3).

With every rule removed (the shim's drop_rules flag), the generic checks alone still report
the dead end, the never-happening actions, the offered-but-refused option and the
unreachable declared end as conflicts, while wide counter domains are warnings only.
"""
from __future__ import annotations

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
