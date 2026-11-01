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
    # G3 round 2: an id compared with a value the rule cannot follow is a doubt: no reduction
    assert "compares a tool id with a value the rule cannot follow" in loaded.model._symmetry_doubt
    assert check_model(loaded).graph.sym is None
    # the unreduced comparison is the backstop for what no rule sees: forced reduction is caught
    del loaded.model.__dict__["_symmetry_doubt"]
    loaded.model.__dict__.pop("_symmetry", None)
    reduced = check_model(loaded)
    assert reduced.graph.sym is not None
    result = verify_symmetry(loaded, Bounds(), reduced)
    assert result["verified"] is False and result["finding"].kind == "MODEL ERROR"
    assert "not interchangeable" in result["text"]


def test_explore_without_reduction_is_the_plain_search(project):
    loaded = load(project, SYM)
    assert len(explore(loaded.model, reduce=False).states) == 144


def test_symmetric_findings_are_the_same_under_every_hash_seed(project):
    from conftest import findings_under_seeds
    project.kit()
    path = project.flow_from(DATA / "kit" / "workshop_naive.py")
    runs = findings_under_seeds(project.root, path)
    assert runs[0] == runs[1] == runs[2] and runs[0]
    lend = project.flow("lending", lending())
    runs = findings_under_seeds(project.root, lend)
    assert runs[0] == runs[1] == runs[2] and runs[0]


MACHINES = '''
from flowguard._next import Model, need
m = Model("machines")
MACHINES = m.objects("machine", "M1", "M2")
m.field("state", ["idle", "busy"], "idle", over=MACHINES)
m.field("holder", [None] + MACHINES, None)

@m.action(t=MACHINES)
def start(s, t):
    need(all(s["state", x] == "idle" for x in MACHINES), "one at a time")
    s["state", t], s["holder"] = "busy", t

@m.action(t=MACHINES, u=MACHINES)
def hand_over(s, t, u):
    need(USE, "only to a later machine")
    need(s["state", t] == "busy" and s["state", u] == "idle", "nothing to hand over")
    s["state", t], s["state", u], s["holder"] = "idle", "busy", u
EXTRA
MODEL = m
'''


@pytest.mark.parametrize("use, extra, text", [
    ("t < u", "", "compares machine ids by order"),
    ("min(t, u) == t", "", "min(...) orders machine ids"),
    ("s['holder'] is None or s['holder'] <= u", "", "compares machine ids by order"),
    ("True", "m.always('first in line', lambda s: sorted(x for x in MACHINES if s['state', x] == 'busy') != ['M2'])",
     "the literal 'M2' names one machine id"),
    ("True", "m.reach('ordered', lambda s, x: s['holder'] is not None and s['holder'] > x, over=MACHINES)",
     "compares machine ids by order"),
])
def test_ordering_interchangeable_ids_anywhere_is_a_model_error(project, use, extra, text):
    """G3: the rule covers action parameters, rule and option parameters and field values
    that hold ids, not only the names bound to m.objects (once a false "clean, complete")."""
    project.flow("machines", MACHINES.replace("USE", use).replace("EXTRA", extra))
    with pytest.raises(ModelError, match="treats machine ids asymmetrically") as err:
        load_model(project.root / ".flowguard/flow/machines.py", project.root)
    assert text in err.value.text


def test_a_parameter_ordered_by_its_text_is_explored_without_renaming(project):
    """G3: when the rule cannot tell that a use treats ids alike (here the id's text goes to
    a function the model does not define), the model is explored without reduction, and the
    reach line says so: in doubt, never a reduced (possibly false) clean."""
    project.file("plant/rank.py", "def rank(machine):\n    return int(machine[1:])\n")
    project.flow("machines", MACHINES.replace("USE", "rank(t) < 2").replace(
        "from flowguard._next import Model, need", "from flowguard._next import Model, need\nfrom plant.rank import rank"
    ).replace("EXTRA", ""))
    loaded = load_model(project.root / ".flowguard/flow/machines.py", project.root)
    report = check_model(loaded)
    assert report.graph.sym is None and len(report.graph.states) == len(explore(loaded.model, reduce=False).states)
    assert report.reach["symmetry_doubt"].startswith(".flowguard/flow/machines.py:")
    assert "passes a machine id to rank()" in report.reach["symmetry_doubt"]
    from flowguard._next.checks import reach_line
    line = reach_line(report.reach)
    assert "machines not explored up to renaming (in doubt:" in line and "every renaming explored" in line
    assert any(f.kind == "STUCK" for f in report.findings)          # M2 is stuck busy: found, not reduced away


FINISH = '''
from flowguard._next import Model, need
m = Model("machines")
MACHINES = m.objects("machine", "M1", "M2")
m.field("state", ["idle", "busy"], "idle", over=MACHINES)
PRELUDE

@m.action(t=MACHINES)
def start(s, t):
    need(s["state", t] == "idle", "busy")
    s["state", t] = "busy"

@m.action(t=MACHINES)
def finish(s, t):
    need(s["state", t] == "busy", "idle")
    need(GUARD, "only the first may finish")
    s["state", t] = "idle"
MODEL = m
'''

PAIRS = FINISH.replace("PRELUDE", "PAIRS = [(a, b) for a in MACHINES for b in MACHINES if a != b]").replace(
    '''@m.action(t=MACHINES)
def finish(s, t):
    need(s["state", t] == "busy", "idle")
    need(GUARD, "only the first may finish")
    s["state", t] = "idle"''', '''@m.action(p=PAIRS)
def finish(s, p):
    need(s["state", p[0]] == "busy", "idle")
    need(p[0] > p[1], "only the first may finish")
    s["state", p[0]] = "idle"''')


@pytest.mark.parametrize("prelude, guard, text", [
    ("", "t == list(MACHINES)[0]", "picks one machine id"),
    ("", "t == tuple(MACHINES)[0]", "picks one machine id"),
    ("ORDER = list(MACHINES)", "ORDER.index(t) == 0", "depends on the order of the machine ids"),
    ("ORDER = list(MACHINES)", "t == ORDER[0]", "picks one machine id"),
    ("for u in list(MACHINES):\n    FIRST = u\n    break", "t == FIRST", "stops early"),
    ("", "t == next(iter(set(MACHINES)))", "picks one machine id"),
    ("RANK = dict(zip(list(MACHINES), [0, 1]))", "RANK[t] == 0", None),
    ("PAIRS", None, "compares machine ids by order"),
])
def test_a_pick_from_a_copy_of_the_ids_is_never_reduced(project, prelude, guard, text):
    """G3 (round 2): ids picked from a copy of the id list (list(), tuple(), a module-level
    copy, a loop that breaks, the first of a set), a table built from their order, or an
    action domain derived from them (pairs) once gave "clean, complete" with the renaming on,
    although only M1 may finish and M2 stays busy. Each is now a model error naming the
    use, or (a table the rule cannot judge) a doubt that turns the renaming off."""
    source = PAIRS if prelude == "PAIRS" else FINISH.replace("PRELUDE", prelude).replace("GUARD", guard)
    project.flow("machines", source)
    path = project.root / ".flowguard/flow/machines.py"
    if text is not None:
        with pytest.raises(ModelError, match="treats machine ids asymmetrically") as err:
            load_model(path, project.root)
        assert text in err.value.text, err.value.text
        return
    loaded = load_model(path, project.root)
    report = check_model(loaded)
    assert report.graph.sym is None and report.reach["symmetry_doubt"]
    assert any(f.kind == "STUCK" for f in report.findings)


@pytest.mark.parametrize("extra, text", [
    ('@m.action()\ndef reset(s):\n    s["holder"] = "T" + "1"', "writes a value the rule cannot follow into 'holder'"),
    ('m.always("first field", lambda s: list(s.values())[0] == "shop")', "uses the model state"),
    ('@m.action(t=TOOLS)\ndef peek(s, t):\n    need(eval("t") != "T" + "1", "hidden")', "runs code the rule cannot follow"),
    ('@m.action(t=TOOLS)\ndef peek(s, t):\n    need(t in BLOCKED, "blocked")\nBLOCKED = {"T" + "1"}',
     "looks a tool id up in a value the rule cannot follow"),
])
def test_uses_the_rule_cannot_follow_turn_the_renaming_off(project, extra, text):
    """G3 round 2: text made into an id and written into an id-valued field, reading the
    state other than by key, dynamic code, and membership in a value the rule does not
    follow can each tell the ids apart; in doubt the model is explored without renaming."""
    project.flow("tools", SCALARSET.format(init='"shop"', extra='m.field("holder", [None] + TOOLS, None)\n' + extra))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert text in (loaded.model.__dict__.get("_symmetry_doubt") or ""), loaded.model.__dict__.get("_symmetry_doubt")
    assert check_model(loaded).graph.sym is None


def test_a_function_nothing_runs_is_not_judged(project):
    """A def that is no action, no rule and called by nothing never runs: its parameters
    hold nothing the rule can follow, and judging them would only turn the renaming off."""
    project.flow("tools", SCALARSET.format(init='"shop"', extra='def unused(s, t, u):\n    return t == u'))
    loaded = load_model(project.root / ".flowguard/flow/tools.py", project.root)
    assert loaded.model.__dict__.get("_symmetry_doubt") is None and check_model(loaded).graph.sym is not None


PERM = '''
from flowguard._next import Model, need
IMPORTS
m = Model("permits")
TOOLS = m.objects("tool", "T1", "T2")
m.field("perm", ["no", "yes"], "no", over=TOOLS)
m.field("done", [False, True], False, over=TOOLS)
PRELUDE

@m.action()
def grant(s):
    need(all(s["perm", u] == "no" for u in TOOLS), "granted")
    GRANT

@m.action(t=TOOLS)
def finish(s, t):
    need(s["perm", t] == "yes", "no permit")
    need(not s["done", t], "done")
    s["done", t] = True
MODEL = m
'''


@pytest.mark.parametrize("imports, prelude, grant", [
    ("", "", 's["perm", "T" + "1"] = "yes"'),
    ("", "", 's["perm", f"T{1}"] = "yes"'),
    ("", "", 's["perm", "t1".upper()] = "yes"'),
    ("", "", 's["perm", "".join(["T", "1"])] = "yes"'),
    ("", "", 's["perm", chr(84) + "1"] = "yes"'),
    ("", "", 's["perm", m.kinds["tool"][0]] = "yes"'),
    ("", "", 's["perm", [f.obj for f in m.fields if f.obj][0]] = "yes"'),
    ("", "", 'for u in m.kinds["tool"]:\n        s["perm", u] = "yes"\n        break'),
    ("", "PERM = {u: 0 for u in TOOLS}", 's["perm", list(PERM)[0]] = "yes"'),
    ("", "PERM = {u: 0 for u in TOOLS}", 's["perm", tuple(PERM)[0]] = "yes"'),
    ("", "PERM = {u: 0 for u in TOOLS}", 's["perm", [*PERM][0]] = "yes"'),
    ("", "ORDER = [u for u in TOOLS]", 's["perm", [*ORDER][0]] = "yes"'),
    ("", "FIRST, SECOND = list(TOOLS)", 's["perm", FIRST] = "yes"'),
    ("", "[FIRST, SECOND] = TOOLS", 's["perm", FIRST] = "yes"'),
    ("", "", 's["perm", (X := list(TOOLS))[0]] = "yes"'),
    ("", "", 'any((F := u) for u in TOOLS)\n    s["perm", F] = "yes"'),
    ("", "", 's["perm", sum([[u] for u in TOOLS], [])[0]] = "yes"'),
    ("", "def pick(a, b):\n    return a", 's["perm", pick(*TOOLS)] = "yes"'),
    ("", "KEY = ('perm', 'T' + '1')", 's[KEY] = "yes"'),
    ("", "PERM = {u: u for u in TOOLS}\nFAV = 'T' + '1'", 's["perm", PERM[FAV]] = "yes"'),
    ("from counter.ids import MAIN_TOOL", "", 's["perm", MAIN_TOOL] = "yes"'),
    ("from fav import FAV", "", 's["perm", FAV] = "yes"'),
    ("", "", 'need(False, "never")\n\n@m.action(t=TOOLS)\ndef pass_(s, t):\n    need(t in "xT1", "not in the text")\n'
             '    s["perm", t] = "yes"'),
])
def test_ids_made_from_text_or_untracked_sources_are_never_reduced(project, imports, prelude, grant):
    """G3 round 2: grant() gives a permit to one tool only, so unreduced the other tool is
    stuck; with the renaming on, each of these once gave "clean, complete". An id made from
    text, read from the model's declarations or from project code, picked by unpacking or
    from a copy (list() of a table, a starred display, sum(), a spread into parameters, a
    walrus in a comprehension), or found in the text of a constant is a model error or turns
    the renaming off; never a reduced (false) clean."""
    project.file("counter/__init__.py", "")
    project.file("counter/ids.py", 'MAIN_TOOL = "T1"\n')
    project.file("fav.py", 'FAV = "T1"\n')
    project.flow("permits", PERM.replace("IMPORTS", imports).replace("PRELUDE", prelude).replace("GRANT", grant))
    path = project.root / ".flowguard/flow/permits.py"
    try:
        loaded = load_model(path, project.root)
    except ModelError as err:
        assert "treats tool ids asymmetrically" in err.text, err.text
        return
    report = check_model(loaded)
    assert report.graph.sym is None, "reduced although an id may be told apart"
    assert loaded.model.__dict__.get("_symmetry_doubt"), "no doubt recorded"
    assert any(f.kind == "STUCK" for f in report.findings), [f.kind for f in report.findings]
