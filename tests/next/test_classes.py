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
