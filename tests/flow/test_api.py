"""FG-811/812 authoring API: sources and their inheritance, attribution per kind, notes,
the concurrency line, declaration errors, errors in model code, path-free fingerprints."""
from __future__ import annotations

import json

import pytest

from flowguard.flow.checks import CONFLICT, ERROR_CLS, Finding, check_model, fingerprint, reach_line
from flowguard.flow.explore import explore
from flowguard.flow.model import ModelError, load_model

from conftest import DATA

KIT = DATA / "kit"


def load(project, name):
    return load_model(project.root / ".flowguard" / "flow" / f"{name}.py", project.root)


def kit_report(project, name):
    project.kit().flow_from(KIT / f"{name}.py")
    return check_model(load(project, name))


def one(report, kind):
    found = [f for f in report.findings if f.kind == kind]
    assert len(found) == 1, [f.subject for f in found]
    return found[0]


# ---------------------------------------------------------------- the design example (DESIGN 2.2)
def test_the_design_example_is_clean(project):
    report = kit_report(project, "workshop")
    assert report.findings == []
    assert len(report.graph.states) == 171 and report.graph.complete


def test_attribution_per_kind_on_the_naive_example(project):
    report = kit_report(project, "workshop_naive")
    stuck, broken, contra = one(report, "STUCK"), one(report, "BROKEN"), one(report, "CONTRADICTION")
    assert stuck.subject == "branch[*] = 'library'" and stuck.objects == ("T1", "T2")
    assert {"R6", "R10"} <= set(stuck.sources)          # the move guard and the repair guard
    assert stuck.sources == ("R4", "R6", "R9", "R10")    # natural order, union with consequences
    assert len(stuck.path) == 8
    assert stuck.state == "cond[T1]='loan', branch[T1]='library', rentals[T1]=4"
    assert stuck.detail["consequences"] == ["cond[*] = 'repair'",
                                            "progress 'a tool in repair or on the way gets back to a shelf'",
                                            "rentals[*] = 4"]
    # cond[*] = 'repair' freezes with the branch: the headline names it, the consequences line does not repeat it
    assert stuck.detail["shown_consequences"] == stuck.detail["consequences"][1:2]
    assert stuck.detail["folded"] == {"count": 1, "fields": ["rentals[*]"]}
    assert "R10" in broken.sources and broken.subject == "always 'a tool in repair is at main'"
    assert contra.sources == ("R10",)                    # the option's and the refusing guard's
    assert contra.text == ("option 'workshop: repaired' is offered, but repaired(t='T1') refuses: "
                           "'repairs only at main'")


def test_a_guard_without_source_carries_its_action_source(project):
    report = kit_report(project, "workshop_naive")
    refused = one(report, "STUCK").detail["refused"]
    assert ("move(t='T1', b='main')", "only shelf tools move", "R6") in {
        (r["call"], r["reason"], r["source"]) for r in refused}            # the action's R6, inherited
    g = report.graph
    explicit = [r for r in g.refusals if r.reason == "repairs only at main"]
    assert [(r.source, r.file) for r in explicit] == [("R10", ".flowguard/flow/workshop_naive.py")]


MARKED = '''
from flowguard.flow import Model, need
m = Model("doors")
m.field("door", ["shut", "open", "locked"], "shut", source="R1")
m.field("alarm", ["off", "on"], "off", source="R2", note="the alarm only matters while locked")

@m.action(source="R1")
def open_door(s):
    need(s["door"] == "shut", "not shut")
    s["door"] = "open"

@m.action(source="R1")
def close(s):
    need(s["door"] == "open", "not open")
    with s.source("R3"):                  # R3: closing at night locks it
        s["door"] = "locked"

m.always("never locked", lambda s: s["door"] != "locked", source="R5", note="R5 forbids locking")
MODEL = m
'''


def test_marked_effects_and_notes_reach_the_findings(project):
    project.flow("doors", MARKED)
    report = check_model(load(project, "doors"))
    broken = one(report, "BROKEN")
    assert broken.sources == ("R1", "R3", "R5")          # rule, actions on the path, marked effect
    assert broken.detail["notes"] == ["R5 forbids locking"]
    never = [f for f in report.findings if f.subject == "value alarm = 'on'"]
    assert never[0].detail["notes"] == ["the alarm only matters while locked"]
    assert never[0].sources == ("R2",)                   # a value carries its field's source


def test_a_stuck_finding_names_its_notes(project):
    report = kit_report(project, "workshop_naive")
    assert one(report, "STUCK").detail["notes"] == ["clamped at maintain_every: more rentals behave the same"]


# ---------------------------------------------------------------- the reach line
def test_concurrent_covered_code_is_named(project):
    project.kit()
    project.file("counter/worker.py", "import os\nimport threading\n\nclass Worker:\n    pass\n")
    text = (KIT / "workshop.py").read_text().replace('covers=["counter/core.py:Counter"]',
                                                     'covers=["counter/core.py:Counter", "counter/worker.py:Worker"]')
    project.flow("workshop", text)
    report = check_model(load(project, "workshop"))
    assert report.reach["concurrency"] == ["counter/worker.py:2 imports threading"]
    assert reach_line(report.reach).endswith("; concurrency not checked (counter/worker.py:2 imports threading)")
    assert "counter/worker.py" in load(project, "workshop").reads


def test_sequential_covered_code_has_no_concurrency_line(project):
    report = kit_report(project, "workshop")
    assert report.reach["concurrency"] == [] and "concurrency" not in reach_line(report.reach)


# ---------------------------------------------------------------- declaration errors
BASE = '''
from flowguard.flow import Model, need
m = Model("m"{model_args})
m.field("x", [0, 1, 2], 0)

@m.action()
def up(s):
    need(s["x"] < 2, "top")
    s["x"] += 1
{extra}
MODEL = m
'''


@pytest.mark.parametrize("model_args, extra, text", [
    ("", 'm.field("y", [1, 2], 0)', "init 0 of y is not in its domain"),
    ("", '@m.action(n=[1])\ndef down(s, n, source):\n    pass', "'source' is a reserved word"),
    ("", '@m.action(n=[1])\ndef down(s, k):\n    pass', r"declares parameters \(n\) but the function takes \(k\)"),
    ("", 'm.option("go", lambda s: True, action="fly")', "names action 'fly', which does not exist"),
    ("", 'm.only_when("w", "fly", lambda s: True)', "names action 'fly'"),
    ("", 'm.after("w", "fly", lambda b, a: True)', "names action 'fly'"),
    ("", 'm.second_route("up", "fly", source="R1", why="both")', "names action 'fly'"),
    ("", 'm.second_route("up", "up", source="R1", why="both")', "two different actions"),
    ("", 'm.second_route("up", "down", why="both")', "missing 1 required keyword-only argument"),
    ("", 'm.field("x", [0, 1], 0)', "field x is declared twice"),
    ("", 'm.objects("tool", "A", "B", "C", "D", "E")', "at most 4 ids"),
    ("", 'm.always("a", lambda s: True)\nm.always("a", lambda s: True)', "rule name 'a' is used twice"),
    ("", 'm.terminal("z", ["done"])', "terminal names field 'z'"),
    ("", 'm.always("a", lambda s: True, source=4)', "source= must be a request id"),
    (', covers=["nowhere.py"]', "", "no file 'nowhere.py'"),
    (', covers=["counter/core.py:Nope"]', "", "has no class Nope"),
    (', covers=["counter/core.py:Counter.nope"]', "", "has no method nope"),
])
def test_declaration_errors_are_model_errors(project, model_args, extra, text):
    project.kit()
    project.flow("m", BASE.format(model_args=model_args, extra=extra))
    with pytest.raises((ModelError, TypeError), match=text):
        load(project, "m")


def test_option_parameters_must_be_the_action_parameters(project):
    project.flow("m", BASE.format(model_args="", extra='m.option("go", lambda s, n: True, action="up", n=[1])'))
    with pytest.raises(ModelError, match="passes its arguments to the action by name"):
        load(project, "m")


def test_a_file_without_model_is_a_model_error(project):
    project.flow("old", BASE.format(model_args="", extra="").replace("MODEL = m", "MACHINE = m"))
    with pytest.raises(ModelError, match=r"defines no MODEL \(MACHINE is not read: write MODEL = m\)"):
        load(project, "old")


def test_an_exception_while_loading_names_its_line(project):
    project.flow("bad", BASE.format(model_args="", extra="1 / 0"))
    with pytest.raises(ModelError, match="loading raised ZeroDivisionError") as err:
        load(project, "bad")
    assert (err.value.file, err.value.line) == (".flowguard/flow/bad.py", 9)


@pytest.mark.parametrize("body, text", [
    ('s["x"] = {}["k"]', "raised KeyError"),
    ('s["x"] = 7', "sets x=7, not in its domain"),
    ('s["typo"] = 1', "wrote unknown field(s) ['typo']"),
])
def test_errors_in_model_code_are_model_errors_with_location(project, body, text):
    project.flow("m", BASE.format(model_args="", extra=f'@m.action()\ndef bad(s):\n    {body}'))
    report = check_model(load(project, "m"))
    errors = [f for f in report.findings if f.cls == ERROR_CLS]
    assert errors and all(text in f.text for f in errors)
    assert report.findings[-1].cls == ERROR_CLS          # model errors come last
    if "KeyError" in text:
        assert errors[0].line == 11 and errors[0].detail["file"] == ".flowguard/flow/m.py"


def test_a_failing_rule_is_a_model_error_not_a_broken_rule(project):
    project.flow("m", BASE.format(model_args="", extra='m.always("r", lambda s: s["nope"] == 1)'))
    report = check_model(load(project, "m"))
    assert [f.kind for f in report.findings] == ["MODEL ERROR"]
    assert "always 'r' raised KeyError" in report.findings[0].text


# ---------------------------------------------------------------- identity
def test_fingerprints_ignore_paths_and_unrelated_edits(project):
    project.kit()
    project.flow_from(KIT / "workshop_naive.py", "a")
    text = (KIT / "workshop_naive.py").read_text()
    noisy = text.replace("MODEL = m", '''
m.field("radio", ["off", "on"], "off")

@m.action()
def tune(s):
    s["radio"] = "on" if s["radio"] == "off" else "off"

MODEL = m''')
    project.flow("b", noisy.replace('"workshop"', '"workshop"', 1))
    a = check_model(load(project, "a"))
    b = check_model(load(project, "b"))
    ida = {(f.kind, f.subject, f.sources) for f in a.findings}
    idb = {(f.kind, f.subject, f.sources) for f in b.findings}
    assert ida == idb
    assert len(b.graph.states) == 2 * len(a.graph.states)
    assert fingerprint("STUCK", "a", "branch[*] = 'library'", ["R10", "R4", "R9", "R6"]) == one(a, "STUCK").id
    assert fingerprint("STUCK", "a", "branch[*] = 'library'", ["R4"]) != one(a, "STUCK").id


def test_findings_round_trip_through_json(project):
    report = kit_report(project, "workshop_naive")
    for f in report.findings:
        d = f.to_json()
        assert json.loads(json.dumps(d)) == d
        assert Finding.from_json(d).to_json() == d
        assert "states" not in d["detail"]


def test_the_search_records_no_effects(project):
    project.kit().flow_from(KIT / "workshop.py")
    g = explore(load(project, "workshop").model)
    assert all(type(t) is tuple for t in g.states)


# ---------------------------------------------------------------- what the parts build on
def test_a_transform_rewrites_the_model_file_only(project):
    import ast as _ast

    class DropNeeds(_ast.NodeTransformer):
        def visit_Expr(self, node):
            call = node.value
            if isinstance(call, _ast.Call) and getattr(call.func, "id", None) == "need":
                return _ast.Pass()
            return node

    project.flow("m", BASE.format(model_args="", extra='m.terminal("x", [2])'))     # x = 2 ends it on purpose
    plain = load_model(project.root / ".flowguard/flow/m.py", project.root)
    dropped = load_model(project.root / ".flowguard/flow/m.py", project.root,
                         transform=lambda tree: DropNeeds().visit(tree))
    assert [f.kind for f in check_model(plain).findings] == []
    assert [f.kind for f in check_model(dropped).findings] == ["MODEL ERROR"]   # x = 3 is outside 0..2


def test_calls_and_replace_actions(project):
    project.kit().flow_from(KIT / "workshop.py")
    model = load(project, "workshop").model
    calls = model.calls()
    assert [c.step()[0] for c in calls[:3]] == ["rent", "rent", "give_back"]
    assert [c.index for c in calls] == list(range(len(calls)))
    assert len(calls) == 2 + 2 + 2 + 2 + 4
    copy = model.replace_actions(model.actions[:1])
    assert [c.action.name for c in copy.calls()] == ["rent", "rent"] and len(model.calls()) == 12


NONDETERMINISTIC = '''
from flowguard.flow import Model, need
SEEN = set()
m = Model("once")
m.field("x", [0, 1, 2], 0)

@m.action()
def up(s):
    need(s["x"] not in SEEN, "already went up from here")
    SEEN.add(s["x"])
    s["x"] = min(s["x"] + 1, 2)

m.always("x stays below 2", lambda s: s["x"] < 2)
m.terminal("x", [2])
MODEL = m
'''


def test_a_model_that_answers_differently_on_replay_is_a_model_error(project):
    project.flow("once", NONDETERMINISTIC)
    report = check_model(load(project, "once"))
    kinds = [f.kind for f in report.findings]
    assert kinds == ["BROKEN", "MODEL ERROR"]
    assert "does not give the same result twice" in report.findings[-1].text


def test_a_stuck_report_names_the_object_its_refusals_and_its_way_in(project):
    """G2 (M5): the stuck tool's own fields in the headline, every call that would change it
    and refuses there with reason and request (the R10 guard included, where the repair
    consequence sets in), and the step that entered it."""
    report = kit_report(project, "workshop_naive")
    stuck = one(report, "STUCK")
    assert stuck.text.startswith("T1 stuck in cond='repair', branch='library': cond[*] = 'repair' and "
                                 "branch[*] = 'library' can never change again")
    refused = [(r["call"].partition("(")[0], r["reason"], r["source"]) for r in stuck.detail["refused"]]
    assert refused == [("rent", "not on the shelf", "R4"), ("arrive", "not on the way", "R10"),
                       ("repaired", "not in repair", "R9"), ("move", "only shelf tools move", "R6")]
    later = [(r["at"], r["call"], r["reason"], r["source"]) for r in stuck.detail["later"]]
    assert ("cond[*] = 'repair'", "repaired(t='T1')", "repairs only at main", "R10") in later
    assert stuck.detail["entered"] == {"call": "rent(t='T1')", "sources": ["R4"]}

    project.flow_from(DATA / "planted" / "rental_naive.py")
    rental = one(check_model(load_model(project.root / ".flowguard/flow/rental_naive.py", project.root)), "STUCK")
    assert rental.text.startswith("T1 stuck in cond='repair', branch='library': ")
    assert ("repaired(t='T1')", "repairs only at main", "R10") in {
        (r["call"], r["reason"], r["source"]) for r in rental.detail["refused"]}
    assert rental.detail["entered"] == {"call": "return_damaged(t='T1')", "sources": ["R8"]}
