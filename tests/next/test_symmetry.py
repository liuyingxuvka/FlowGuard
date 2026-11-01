"""FG-811 symmetry: interchangeable object ids explored up to renaming, kept sound by the
scalarset rule, the start-state rule and the unreduced comparison; printed paths are real runs."""
from __future__ import annotations

import pytest

from flowguard._next.checks import check_model, verify_symmetry
from flowguard._next.explore import Bounds, Symmetry, explore, replay
from flowguard._next.model import ModelError, State, load_model

from conftest import DATA

SCALE = DATA / "scale" / "bring_3_2.py"
SYM = DATA / "sym" / "workshop_r10.py"


def load(project, src, name=None):
    path = project.flow_from(src, name)
    return load_model(path, project.root)


@pytest.fixture(scope="module")
def bring(tmp_path_factory):
    from conftest import Project
    project = Project(tmp_path_factory.mktemp("bring") / "p")
    loaded = load(project, SCALE)
    reduced = check_model(loaded)
    plain = check_model(loaded, reduce=False)
    return loaded, reduced, plain


def test_reduced_count_is_the_number_of_canonical_forms(bring):
    loaded, reduced, plain = bring
    sym = Symmetry.of(loaded.model)
    assert sym.kinds == ["tool", "member"] and sym.n == 12
    assert len(plain.graph.states) == 54_872 and plain.graph.complete
    canon = {sym.canon(t)[0] for t in plain.graph.states}
    assert len(reduced.graph.states) == len(canon) == 5_016
    assert set(reduced.graph.states) == canon


def test_reduced_and_unreduced_give_the_same_fingerprints(bring):
    _, reduced, plain = bring
    assert [f.id for f in reduced.findings] == [f.id for f in plain.findings]
    assert reduced.holds == plain.holds
    assert reduced.reach["symmetry"] == ["tool", "member"] and plain.reach["symmetry"] == []


VARIANTS = {
    # holds can never end: progress lost per tool, a per-object finding over id-valued fields
    "endless_hold": lambda t: t.replace('need(s["holder", t] in (None, mem), "held for another")',
                                        'need(s["holder", t] is None, "held")').replace(
        "@m.action(t=TOOLS, mem=MEMBERS)\ndef cancel", "def cancel").replace(
        "@m.action()\ndef advance", "def advance").replace(
        'm.objects("tool", "T1", "T2", "T3")', 'm.objects("tool", "T1", "T2")'),
}


def lending(stuck=True):
    return f'''
from flowguard._next import Model, need
m = Model("lending")
MEMBERS = m.objects("member", "M1", "M2", "M3")
m.field("holder", [None] + MEMBERS, None, source="R1")
m.field("banned", [False, True], False, source="R2")

@m.action(mem=MEMBERS, source="R1")
def lend(s, mem):
    need(s["holder"] is None, "lent out")
    s["holder"] = mem

@m.action(mem=MEMBERS, source="R1")
def back(s, mem):
    need(s["holder"] == mem, "not the holder")
    need({"not s['banned']" if stuck else "True"}, "banned members cannot return", source="R2")
    s["holder"] = None

@m.action(source="R2")
def ban(s):
    need(s["holder"] is not None, "nobody to ban")
    s["banned"] = True
MODEL = m
'''


@pytest.mark.parametrize("name", ["workshop_r10", "endless_hold", "lending", "workshop_naive"])
def test_findings_are_the_same_with_and_without_renaming(project, name):
    if name == "workshop_r10":
        loaded = load(project, SYM)
    elif name == "lending":
        project.flow("lending", lending())
        loaded = load_model(project.root / ".flowguard/flow/lending.py", project.root)
    elif name == "workshop_naive":
        project.kit()
        loaded = load(project, DATA / "kit" / "workshop_naive.py")
    else:
        project.flow(name, VARIANTS[name](SCALE.read_text()))
        loaded = load_model(project.root / f".flowguard/flow/{name}.py", project.root)
    reduced = check_model(loaded)
    plain = check_model(loaded, reduce=False)
    assert reduced.graph.sym is not None and len(reduced.graph.states) < len(plain.graph.states)
    assert reduced.findings, "the variant must have findings"
    assert [(f.id, f.objects, len(f.path)) for f in reduced.findings] == \
           [(f.id, f.objects, len(f.path)) for f in plain.findings]
    assert verify_symmetry(loaded, Bounds(), reduced)["verified"] is True


def test_an_id_valued_field_is_stuck_once_for_every_member(project):
    project.flow("lending", lending())
    report = check_model(load_model(project.root / ".flowguard/flow/lending.py", project.root))
    [stuck] = [f for f in report.findings if f.kind == "STUCK"]
    assert stuck.subject == "holder = '<member>'" and stuck.objects == ("M1", "M2", "M3")
    assert stuck.sources == ("R1", "R2")
    refused = {(r["call"], r["reason"], r["source"]) for r in stuck.detail["refused"]}
    assert ("back(mem='M1')", "banned members cannot return", "R2") in refused


def test_merged_findings_on_the_e7_workshop(project):
    report = check_model(load(project, SYM))
    assert [(f.kind, f.subject, f.objects) for f in report.findings] == [
        ("STUCK", "branch[*] = 'east'", ("T1", "T2")),
        ("BROKEN", "always 'workshop sees every tool in repair'", ())]
    assert len(report.graph.states) == 78                     # 144 without renaming


def test_printed_paths_are_real_runs(bring, project):
    loaded = load(project, SYM)
    for report in (check_model(loaded), bring[1]):
        g = report.graph
        for i in range(0, len(g.states), max(1, len(g.states) // 200)):
            calls = g.path_calls(i)
            t = g.init
            for c in calls:                                   # every step works from the last state
                call = g.calls[c]
                w = State(zip(g.keys, t))
                call.action.fn(w, *call.args)
                t = tuple(w[k] for k in g.keys)
            assert t == g.end_state(i)
            assert g.sym.canon(t)[0] == g.states[i]
            assert len(replay(g, calls)) == len(calls)


SCALARSET = '''
from flowguard._next import Model, need
m = Model("tools")
TOOLS = m.objects("tool", "T1", "T2")
m.field("cond", ["shop", "loan"], {init}, over=TOOLS)

@m.action(t=TOOLS)
def rent(s, t):
    need(s["cond", t] == "shop", "busy")
    s["cond", t] = "loan"
{extra}
MODEL = m
'''


@pytest.mark.parametrize("init, extra, text, line", [
    ('"shop"', 'm.always("first", lambda s: s["cond", TOOLS[0]] == "shop")', "TOOLS[...] picks one tool id", 10),
    ('"shop"', 'm.always("named", lambda s: s["cond", "T1"] == "shop")', "the literal 'T1' names one tool id", 10),
    ('"shop"', 'm.always("o", lambda s: sorted(TOOLS) == [])', "sorted(TOOLS) depends on the order", 10),
    ('"shop"', 'def first(s):\n    for t in TOOLS:\n        if s["cond", t] == "loan":\n            return t',
     "a loop over TOOLS that stops early", 11),
    ('"shop"', 'x = TOOLS.index("T2")', "TOOLS.index depends on the order", 10),
])
def test_asymmetric_use_of_ids_is_a_model_error_naming_the_line(project, init, extra, text, line):
    project.flow("tools", SCALARSET.format(init=init, extra=extra))
    with pytest.raises(ModelError, match="treats tool ids asymmetrically") as err:
        load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert text in err.value.text and (err.value.file, err.value.line) == (".flowguard/flow/tools.py", line)


def test_objects_must_start_alike(project):
    project.flow("tools", SCALARSET.format(init='{"T1": "shop", "T2": "loan"}', extra="").replace(
        '"T1": "shop", "T2": "loan"', 'k: v for k, v in zip(TOOLS, ["shop", "loan"])'))
    with pytest.raises(ModelError, match=r"zip\(TOOLS\)|start state tells objects"):
        load_model(project.root / ".flowguard/flow/tools.py", project.root)


def test_symmetric_use_is_accepted(project):
    project.flow("tools", SCALARSET.format(init='"shop"', extra='''
m.field("holder", [None] + TOOLS, None)
OTHERS = TOOLS
m.always("count", lambda s: sum(s["cond", t] == "loan" for t in OTHERS) <= len(TOOLS))
m.reach("some on loan", lambda s: any(s["cond", t] == "loan" for t in TOOLS) and "T1" not in [])'''.replace(
        ' and "T1" not in []', '')))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert check_model(loaded).graph.sym is not None


def test_an_unreduced_capped_run_verifies_nothing(project):
    loaded = load(project, SYM)
    reduced = check_model(loaded)
    result = verify_symmetry(loaded, Bounds(100), reduced)
    assert result == {"verified": None, "text": "symmetry not verified (unreduced search capped)", "finding": None}


def test_a_hidden_asymmetry_is_caught_by_the_unreduced_run(project):
    # the scalarset rule reads the model file only; a setting can still hide an id comparison
    project.flow("tools", SCALARSET.format(init='"shop"', extra='''
m.setting("favourite", "T1")
@m.action(t=TOOLS)
def back(s, t):
    need(s["cond", t] == "loan", "not out")
    need(t != m.settings["favourite"], "the favourite stays out")
    s["cond", t] = "shop"
'''))
    with pytest.raises(ModelError, match="the literal 'T1'"):
        load_model(project.root / ".flowguard/flow/tools.py", project.root)
    helper = project.file(".flowguard/flow/_ids.py", 'FAVOURITE = "T" + "1"\n')
    assert helper.exists()
    project.flow("tools", SCALARSET.format(init='"shop"', extra='''
from _ids import FAVOURITE
@m.action(t=TOOLS)
def back(s, t):
    need(s["cond", t] == "loan", "not out")
    need(t != FAVOURITE, "the favourite stays out")
    s["cond", t] = "shop"
'''))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    reduced = check_model(loaded)
    result = verify_symmetry(loaded, Bounds(), reduced)
    assert result["verified"] is False and result["finding"].kind == "MODEL ERROR"
    assert "not interchangeable" in result["text"]


def test_explore_without_reduction_is_the_plain_search(project):
    loaded = load(project, SYM)
    assert len(explore(loaded.model, reduce=False).states) == 144
