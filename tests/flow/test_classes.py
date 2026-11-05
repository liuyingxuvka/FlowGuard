"""FG-812 classes: conflicts versus model warnings (M3).

With every rule removed (the shim's drop_rules flag), the generic checks alone still report
the dead end, the never-happening actions, the offered-but-refused option and the
unreachable declared end as conflicts, while wide counter domains are warnings only.
"""
from __future__ import annotations

import pytest

from flowguard.flow.checks import CONFLICT, WARNING, check_model
from flowguard.flow.model import Loaded, load_model

from _flow_project import DATA
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
from flowguard.flow import Model, need

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
from flowguard.flow import Model, need

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
from flowguard.flow import Model, need

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
from flowguard.flow import Model, need

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
from flowguard.flow import Model, need

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
from flowguard.flow import Model, need

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
from flowguard.flow import Model, need

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


SCRAP = '''
from flowguard.flow import Model, need

m = Model("scrap yard")
TOOLS = m.objects("tool", "T1")
m.field("cond", ["shop", "loan", "lost"], "shop", over=TOOLS, source="R1")
m.field("branch", ["main", "library", "scrap"], "main", over=TOOLS, source="R6")
m.terminal("cond", ["lost"], source="R4")

@m.action(t=TOOLS, source="R1")
def rent(s, t):
    need(s["cond", t] == "shop" and s["branch", t] != "scrap", "not on a shelf")
    s["cond", t] = "loan"

@m.action(t=TOOLS, source="R1")
def give_back(s, t):
    need(s["cond", t] == "loan", "not out")
    s["cond", t] = "shop"

@m.action(t=TOOLS, source="R4")
def lose(s, t):
    need(s["cond", t] == "loan", "not out")
    s["cond", t] = "lost"

@m.action(t=TOOLS, source="R6")
def transfer(s, t):
    need(s["cond", t] == "shop" and s["branch", t] != "scrap", "only shelf tools move")
    s["branch", t] = "library" if s["branch", t] == "main" else "main"

@m.action(t=TOOLS, source="R7")
def scrap(s, t):
    need(s["cond", t] == "shop" and s["branch", t] == "main", "only at main")
    s["branch", t] = "scrap"
MODEL = m
'''


def test_a_lost_tool_is_no_dead_end_of_a_field_with_an_undeclared_end(project):
    """Review round 2, minor: once another value of a field (branch = 'scrap', where the tool
    halts) was taken as an undeclared end, a lost tool (its declared end) was reported as
    "branch[*] = 'main' can never change again". A field's own undeclared end keeps the
    exemption of an object that has reached its declared end."""
    project.flow("scrap", SCRAP)
    report = check_model(load_model(project.root / ".flowguard/flow/scrap.py", project.root))
    stuck = [f.subject for f in report.findings if f.cls == CONFLICT and f.kind == "STUCK"]
    assert "branch[*] = 'scrap'" in stuck, stuck                       # the undeclared end itself
    assert "branch[*] = 'main'" not in stuck and "branch[*] = 'library'" not in stuck, stuck


ONE_BOOK = '''
from flowguard.flow import Model, need

m = Model("book", note="one book at the desk")
m.field("where", ["shelf", "held", "loan", "repair"], "shelf", source="R1", value_sources={"repair": "R4"})
m.field("day", range(0, 4), 0, note="a clock that runs out: day 3 is its last")
EXTRA


@m.action(source="R1")
def hold(s):
    need(s["where"] == "shelf", "not on the shelf")
    s["where"] = "held"


@m.action(source="R1")
def lend(s):
    need(s["where"] == "held", "not held")
    s["where"] = "loan"


@m.action(source="R3")
def give_back(s):
    need(s["where"] == "loan", "not on loan")
    s["where"] = "shelf"


@m.action(source="R4")
def damaged(s):
    need(s["where"] == "loan", "not on loan")
    s["where"] = "repair"


@m.action()
def tick(s):
    need(s["day"] < 3, "the last day")
    s["day"] += 1
MODEL = m
'''

NEVER_FREED = '''
from flowguard.flow import Model, need

m = Model("tools", note="two tools on a plain list: T1 is never freed")
TOOLS = ["T1", "T2"]
m.field("busy", [False, True], False, over=TOOLS, source="R1")
m.field("uses", range(0, 3), 0, note="a total that stops at 2")
EXTRA


@m.action(t=TOOLS, source="R1")
def take(s, t):
    need(not s["busy", t], "busy")
    s["busy", t] = True
    s["uses"] = min(s["uses"] + 1, 2)


@m.action(t=TOOLS, source="R1")
def free(s, t):
    need(s["busy", t], "not busy")
    need(t != "T1", "T1 is never freed")
    s["busy", t] = False
MODEL = m
'''


@pytest.mark.parametrize("name, text, subject, head", [
    ("one book", ONE_BOOK, "where = 'repair'", "stuck with where='repair'"),
    ("a never-freed tool", NEVER_FREED, "busy[*] = True", "T1 stuck with busy=True"),
])
def test_a_value_never_left_is_a_dead_end_for_plain_fields_and_any_domain(project, name, text, subject, head):
    """G8 round 4: the undeclared-end rule judged only text values of per-object fields. A
    one-book desk on a plain field (damaged -> 'repair', no way back) and a tool on a plain
    list that is never freed (busy False/True) were "clean, complete": nothing of the book,
    nothing of T1 ever changes again. Such a value is now a STUCK end unless m.terminal
    declares it. A clock that runs out (day 3) and a total that stops (uses 2) are no end:
    only the step that advances them is lost."""
    flow = project.root / ".flowguard" / "flow"
    project.flow("naive", text.replace("EXTRA", ""))
    report = check_model(load_model(flow / "naive.py", project.root))
    stuck = [f for f in report.findings if f.kind == "STUCK"]
    assert [f.subject for f in stuck] == [subject], [f.text for f in stuck]
    [end] = stuck
    assert end.cls == CONFLICT and end.detail["stuck"] == "end" and head in end.text, end.text
    family = subject.split(" ")[0].split("[")[0]
    value = subject.split(" = ")[1]
    assert f"m.terminal({family!r}, [{value}])" in end.text, end.text
    project.flow("declared", text.replace("EXTRA", f"m.terminal({family!r}, [{value}])"))
    report = check_model(load_model(flow / "declared.py", project.root))
    assert not [f for f in report.findings if f.kind == "STUCK"], [f.text for f in report.findings]


INT_PHASE = '''
from flowguard.flow import Model, need

m = Model("book", note="the book's place as a number: 0 shelf, 1 loan, 2 repair; nothing repairs it")
m.field("phase", range(0, 3), 0, source="R1")
m.field("day", range(0, 3), 0, note="a day clock that keeps running")


@m.action(source="R1")
def lend(s):
    need(s["phase"] == 0, "not on the shelf")
    s["phase"] = 1


@m.action(source="R1")
def give_back(s):
    need(s["phase"] == 1, "not on loan")
    s["phase"] = 0


@m.action(source="R4")
def damaged(s):
    need(s["phase"] == 1, "not on loan")
    s["phase"] = 2


@m.action()
def night(s):
    s["day"] = (s["day"] + 1) % 3
MODEL = m
'''

INT_PHASE_TOOLS = '''
from flowguard.flow import Model, need

m = Model("tools", note="each tool's place as a number: 0 shelf, 1 loan, 2 repair; nothing repairs it")
TOOLS = OBJECTS
m.field("phase", range(0, 3), 0, over=TOOLS, source="R1")
m.field("age", [0, 1], 0, over=TOOLS, note="each tool's own clock")


@m.action(t=TOOLS, source="R1")
def rent(s, t):
    need(s["phase", t] == 0, "not on the shelf")
    s["phase", t] = 1


@m.action(t=TOOLS, source="R1")
def give_back(s, t):
    need(s["phase", t] == 1, "not on loan")
    s["phase", t] = 0


@m.action(t=TOOLS, source="R4")
def damaged(s, t):
    need(s["phase", t] == 1, "not on loan")
    s["phase", t] = 2


@m.action(t=TOOLS)
def age(s, t):
    s["age", t] = 1 - s["age", t]
MODEL = m
'''


@pytest.mark.parametrize("name, text, subject", [
    ("a plain field", INT_PHASE, "phase = 2"),
    ("a plain list", INT_PHASE_TOOLS.replace("OBJECTS", '["T1", "T2"]'), "phase[*] = 2"),
    ("interchangeable tools", INT_PHASE_TOOLS.replace("OBJECTS", 'm.objects("tool", "T1", "T2")'), "phase[*] = 2"),
])
def test_a_number_used_as_a_state_is_a_dead_end_while_a_clock_runs(project, name, text, subject):
    """G8 round 5: the own step of a number (a step that changes only this field) was never
    a lost step, so a place coded as a number (0 shelf, 1 loan, 2 repair; nothing leaves
    2) was "clean, complete", exit 0, while a day clock or an age kept running: lend and
    give_back change only `phase`. The same model with text values was a STUCK. Only a
    step that counts the number toward the value (a clock that runs out, a total that
    stops) is the field's own step; give_back takes the number away from 2 and is lost."""
    project.flow("book", text)
    report = check_model(load_model(project.root / ".flowguard/flow/book.py", project.root))
    stuck = [f for f in report.findings if f.kind == "STUCK"]
    assert [f.subject for f in stuck] == [subject], [f.text for f in stuck]
    [end] = stuck
    assert end.cls == CONFLICT and end.detail["stuck"] == "end", end.text
    assert "can never again give_back" in end.text and "m.terminal('phase', [2])" in end.text, end.text


COUNTDOWN = '''
from flowguard.flow import Model, need

m = Model("lamp")
m.field("left", range(0, 3), 2, note="uses left: counts down to 0 and stops there")
m.field("warnings", range(0, 3), 0, note="counts up to 2 and stops there")
m.field("on", [False, True], False)


@m.action()
def use(s):
    need(s["left"] > 0, "used up")
    s["left"] -= 1


@m.action()
def warn(s):
    need(s["warnings"] < 2, "warned twice")
    s["warnings"] += 1


@m.action()
def flip(s):
    s["on"] = not s["on"]
MODEL = m
'''


def test_a_number_that_counts_to_its_last_value_while_the_model_goes_on_is_no_end(project):
    """The other side of G8 round 5: a number whose own step only counts toward the value
    no state leaves (left 2, 1, 0; warnings 0, 1, 2) has run out there, as a clock that
    runs out does; the lamp goes on, so nothing is reported."""
    project.flow("lamp", COUNTDOWN)
    report = check_model(load_model(project.root / ".flowguard/flow/lamp.py", project.root))
    assert not [f for f in report.findings if f.kind == "STUCK"], [f.text for f in report.findings]


DAYS = '''
"""Days and overdue loans (R1, R3): three days are enough to see every order."""
from flowguard.flow import Model, need
m = Model("days", note="days 1..3; a loan rented on a day is due after one day here")
m.field("day", range(1, 4), 1, source="R1")
m.field("loan", ["none", "open", "overdue"], "none", source="R3")

@m.action(source="R1")
def rent(s):
    need(s["loan"] == "none", "on loan")
    s["loan"] = "open"

@m.action(source="R1")
def return_tool(s):
    need(s["loan"] != "none", "not on loan")
    s["loan"] = "none"

@m.action(source="R1")
def advance(s):
    need(s["day"] < 3, "the last day modelled")
    s["day"] += 1
    if s["loan"] == "open":
        s["loan"] = "overdue"
MODEL = m
'''

TOOL_DAYS = '''
from flowguard.flow import Model, need
m = Model("tools")
TOOLS = OBJECTS
m.field("age", range(0, 3), 0, over=TOOLS, note="each tool's own clock, 0..2")
m.field("shiny", [False, True], False, over=TOOLS)

@m.action(t=TOOLS)
def tick(s, t):
    need(s["age", t] < 2, "as old as modelled")
    s["age", t] += 1
    s["shiny", t] = False

@m.action(t=TOOLS)
def polish(s, t):
    s["shiny", t] = not s["shiny", t]
MODEL = m
'''


@pytest.mark.parametrize("name, text", [
    ("the rental kit's days", DAYS),
    ("days whose step changes nothing else", DAYS.replace('    if s["loan"] == "open":\n        s["loan"] = "overdue"\n', "")),
    ("a clamped clock", DAYS.replace('    need(s["day"] < 3, "the last day modelled")\n    s["day"] += 1',
                                     '    s["day"] = min(s["day"] + 1, 3)')),
])
def test_a_bounded_clock_whose_step_also_changes_other_fields_is_no_end(project, name, text):
    """Acceptance A5 (review round 3, G8, the rental kit's days R1/R3): day 1..3, advance
    guarded by day < 3 that also marks the open loan overdue, was a STUCK "day = 3 is never
    left ... can never again advance", although a clock that runs out is no such step (the
    HOWTO says so): the own-step exemption needed the step to change the day alone. A number
    every change of which counts toward the value no state leaves is a bounded clock or
    counter; its counting step is its own also when it changes other fields."""
    project.flow("days", text)
    report = check_model(load_model(project.root / ".flowguard/flow/days.py", project.root))
    assert report.graph.complete
    assert not [f for f in report.findings if f.kind == "STUCK"], [f.text for f in report.findings]


@pytest.mark.parametrize("objects", ['["T1", "T2"]', 'm.objects("tool", "T1", "T2")'])
def test_a_per_object_clock_whose_step_also_changes_another_field_is_no_end(project, objects):
    project.flow("tools", TOOL_DAYS.replace("OBJECTS", objects))
    report = check_model(load_model(project.root / ".flowguard/flow/tools.py", project.root))
    assert not [f for f in report.findings if f.kind == "STUCK"], [f.text for f in report.findings]


def test_an_int_coded_status_assigned_other_values_stays_judged_when_its_step_does_more(project):
    """The other side of A5: a place coded as a number whose steps also change other fields
    (lend records the member) is no clock: give_back takes it from 1 back to 0, so not every
    change counts toward 2, and the lost give_back is still a dead end."""
    text = INT_PHASE.replace('m.field("day", range(0, 3), 0, note="a day clock that keeps running")',
                             'm.field("day", range(0, 3), 0, note="a day clock that keeps running")\n'
                             'm.field("holder", ["nobody", "member"], "nobody")')
    text = text.replace('    s["phase"] = 1\n', '    s["phase"], s["holder"] = 1, "member"\n')
    text = text.replace('    s["phase"] = 0\n', '    s["phase"], s["holder"] = 0, "nobody"\n')
    project.flow("book", text)
    report = check_model(load_model(project.root / ".flowguard/flow/book.py", project.root))
    stuck = [f for f in report.findings if f.kind == "STUCK"]
    assert [f for f in stuck if f.cls == CONFLICT and "phase=2" in f.text], [f.text for f in report.findings]


def test_a_declared_end_that_a_step_leaves_is_a_model_error(project):
    """A5 keeps a bounded counter's last value from being a dead end; a declared end must then
    really end: tool_life with rent allowed off the shelf rents a retired tool again, so
    'retired' ends nothing, and the model says so with the path to the step that leaves it."""
    from _flow_project import DATA
    text = (DATA / "planted" / "tool_life.py").read_text().replace(
        '    need(s["cond", t] == "shop", "not on the shelf")\n', "")
    project.flow("tool_life", text)
    report = check_model(load_model(project.root / ".flowguard/flow/tool_life.py", project.root))
    [e] = [f for f in report.findings if f.kind == "MODEL ERROR" and "declared an end" in f.text]
    assert e.text == ("cond = 'retired' is declared an end (m.terminal('cond', ...)), but rent leaves it: an end is "
                      "never left; refuse the step there, or leave 'retired' out of m.terminal"), e.text
    assert e.path[-1].startswith("rent(") and len(e.path) > 1, e.path
    clean = check_model(load_model(project.flow_from(DATA / "planted" / "tool_life.py"), project.root))
    assert not [f for f in clean.findings if "declared an end" in f.text]


NEVER_FREED_ALIKE = '''
from flowguard.flow import Model, need

m = Model("tools", note="two interchangeable tools; nothing frees a tool")
TOOLS = m.objects("tool", "T1", "T2")
m.field("busy", [False, True], False, over=TOOLS, source="R1")


@m.action(t=TOOLS, source="R1")
def take(s, t):
    need(not s["busy", t], "busy")
    s["busy", t] = True
MODEL = m
'''


def test_a_finding_of_interchangeable_objects_names_the_first_one(project):
    """Review of round 5, cosmetic: with m.objects the never-freed STUCK named T2 (the
    renaming's representative of "one tool busy" holds T2 busy), while the plain-list model
    named T1. Among witnesses of one finding as short as each other, the one of the object
    first in order is shown."""
    project.flow("tools", NEVER_FREED_ALIKE)
    report = check_model(load_model(project.root / ".flowguard/flow/tools.py", project.root))
    assert report.graph.sym is not None
    [end] = [f for f in report.findings if f.kind == "STUCK"]
    assert end.text.startswith("T1 stuck with busy=True"), end.text
    assert end.path == ("take(t='T1')",), end.path


CONSTANT = '''
from flowguard.flow import Model, need

m = Model("lamp")
m.field("mode", ["auto", "manual"], "auto", note="no action sets it: it keeps its start")
m.field("level", range(0, 3), 1, note="no action changes it")
m.field("on", [False, True], False)


@m.action()
def flip(s):
    s["on"] = not s["on"]
MODEL = m
'''


def test_a_value_held_from_the_start_that_nothing_changes_is_no_end(project):
    """The other side of G8 round 4: a field no step ever changes keeps its start value in
    every state. That value is never left, but no step enters it either: it is a constant,
    not the end of anything (an unreached domain value is the NEVER REACHED warning's)."""
    project.flow("lamp", CONSTANT)
    report = check_model(load_model(project.root / ".flowguard/flow/lamp.py", project.root))
    assert not [f for f in report.findings if f.kind == "STUCK"], [f.text for f in report.findings]


def test_a_stuck_headline_names_the_state_its_object_is_stuck_in(project):
    """Acceptance A6 (#3): the R10 dead end was named after the field that froze ("branch[*] =
    'library' can never change again") while the tool stuck in repair showed only under "then
    also stuck"; the headline now names every value of the object frozen with it."""
    project.kit()
    path = project.flow_from(DATA / "kit" / "workshop_naive.py", "workshop")
    [f] = [f for f in check_model(load_model(path, project.root)).findings if f.kind == "STUCK"]
    assert f.text.startswith("T1 stuck in cond='repair', branch='library': cond[*] = 'repair' and branch[*] = "
                             "'library' can never change again"), f.text


def test_the_work_after_the_search_says_its_phase(project):
    """Acceptance A6 (#8): the progress line stayed at the same states count while the work after
    the search ran; that work now reports its phase."""
    from flowguard.flow.cli import _current_text
    seen = []
    project.kit()
    path = project.flow_from(DATA / "kit" / "workshop_naive.py", "workshop")
    check_model(load_model(path, project.root), progress=seen.append)
    phases = [d["phase"] for d in seen if "phase" in d]
    assert phases[:2] == ["finding what gets stuck", "finding what is never reached"], phases
    assert any(p.startswith("explaining what is never reached: one-setting change 1 of ") for p in phases), phases
    assert "checking the promises" in phases
    text = _current_text({"model": "workshop", "kind": "core", "states": 25651, "phase": "checking the promises"}, "; ")
    assert text == "; checking the promises in workshop (25,651 states explored)"
    text = _current_text({"model": "workshop", "kind": "mutate", "mutant": 3, "mutants": 12}, "; still ")
    assert text == "; still running mutate of workshop (deliberate breakage 3 of 12)"
