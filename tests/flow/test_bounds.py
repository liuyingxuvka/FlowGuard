"""The state bound: a capped search reports UNKNOWN for what it could not decide, never
"clean" or "holds"; what it found with a path (BROKEN, CONTRADICTION, a reach) stays certain."""
from __future__ import annotations

import json

from flowguard.flow.checks import CONFLICT, check_model, reach_line
from flowguard.flow.explore import Bounds
from flowguard.flow.model import load_model

BIG = '''
from flowguard.flow import Model, need

m = Model("dials", note="five independent dials: 100,000 states")
DIALS = ["a", "b", "c", "d", "e"]
m.field("pos", range(0, 10), 0, over=DIALS)

@m.action(d=DIALS)
def turn(s, d):
    s["pos", d] = (s["pos", d] + 1) % 10

m.always("a dial shows a digit", lambda s: all(0 <= s["pos", d] <= 9 for d in DIALS))
m.progress("a dial can come back to 0", over=DIALS, when=lambda s, d: True, goal=lambda s, d: s["pos", d] == 0)
m.reach("all dials at 9", lambda s: all(s["pos", d] == 9 for d in DIALS))
m.reach("dial a at 2", lambda s: s["pos", "a"] == 2)
{extra}
MODEL = m
'''


def run(project, extra="", max_states=1000):
    project.flow("dials", BIG.format(extra=extra))
    loaded = load_model(project.root / ".flowguard/flow/dials.py", project.root)
    return check_model(loaded, Bounds(max_states))


def words(report):
    text = json.dumps([f.to_json() for f in report.findings] + [report.reach, report.holds, report.unknown])
    return text + reach_line(report.reach)


def test_a_capped_search_says_unknown_and_never_clean(project):
    report = run(project)
    assert not report.graph.complete and len(report.graph.states) == 1000
    assert [f for f in report.findings if f.cls == CONFLICT] == []
    assert report.unknown[:2] == ["STUCK", "NEVER REACHED"]
    assert "progress 'a dial can come back to 0'" in report.unknown
    assert "reach 'all dials at 9'" in report.unknown
    assert "always 'a dial shows a digit'" in report.unknown
    assert dict(report.holds)["reach 'dial a at 2'"] == "reached"          # a presence is certain
    assert {status for _, status in report.holds} == {"unknown", "reached"}
    text = words(report).lower()
    assert "clean" not in text and "holds" not in text
    assert reach_line(report.reach).startswith("dials: CAPPED at 1,000 states: UNKNOWN for STUCK, NEVER REACHED")


def test_a_broken_rule_inside_the_bound_is_still_found(project):
    report = run(project, extra='m.always("dial a stays below 3", lambda s: s["pos", "a"] < 3, source="R7")')
    broken = [f for f in report.findings if f.kind == "BROKEN"]
    assert [f.subject for f in broken] == ["always 'dial a stays below 3'"]
    assert broken[0].cls == CONFLICT and broken[0].path == ("turn(d='a')",) * 3
    assert "STUCK" in report.unknown


def test_the_same_model_is_complete_without_the_bound(project):
    report = run(project, max_states=200_000)
    assert report.graph.complete and len(report.graph.states) == 100_000
    assert report.unknown == []
    assert [f.subject for f in report.findings] == []
