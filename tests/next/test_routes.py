"""FG-813: model-level one-route checks (M15 in the model).

The prototype's toy rental model with seven planted over-defences (P1..P7) reports every
one, including the fallback that hides the R10 dead end; the one-route version reports no
route and shows the dead end; a second route named with `m.second_route(..., source=)` is
listed, not reported. On every golden E7 model the per-kind counts equal the prototype's
`summary:` lines. With interchangeable objects the findings equal the unreduced ones.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from flowguard._next.checks import CONFLICT, WARNING, check_model
from flowguard._next.explore import Bounds, explore
from flowguard._next.model import ModelError, load_model
from flowguard._next.parts import PartContext, PartSpec, run_part
from flowguard._next.routes import ForceIfs, check_routes, judge, observe

from conftest import DATA, REPO
from route_machines import load_forced_machines

TOY = DATA / "toy_next"
BRANCH = DATA / "branch"
GOLDEN = DATA / "golden" / "models"
KIND_KEY = {"DUPLICATE ROUTE": "duplicate", "SUBSUMED ACTION": "redundant", "FALLBACK ROUTE": "fallback",
            "STATUS-ONLY FALLBACK": "fallback_status", "SAME-RESULT BRANCH": "same_result_branch",
            "NEVER TAKEN": "never_taken", "DEAD GUARD": "dead_guard"}


def routes(project, src, name=None, max_states=200_000, reduce=True):
    path = project.flow_from(src, name) if isinstance(src, Path) else project.flow(name, src)
    force = ForceIfs(path)
    loaded = load_model(path, project.root, transform=force)
    graph = explore(loaded.model, Bounds(max_states), reduce=reduce)
    return check_routes(loaded.model, graph, force.ifs), loaded


def summary(findings):
    got = Counter(KIND_KEY[f.kind] for f in findings)
    return "summary: " + (", ".join(f"{k} {v}" for k, v in sorted(got.items())) or "none")


def prototype_summaries(report_file):
    return [line for line in report_file.read_text(encoding="utf-8").splitlines() if line.startswith("summary:")]


def by_kind(report, kind):
    return [f for f in report.findings if f.kind == kind]


# ---------------------------------------------------------------------- the planted toy
def test_every_planted_over_defence_is_reported(project):
    report, loaded = routes(project, TOY / "rental_planted.py")
    assert report.complete
    assert summary(report.raw) == prototype_summaries(BRANCH / "toy_rental_planted.txt")[0]

    dup = {f.subject: f for f in by_kind(report, "DUPLICATE ROUTE")}
    assert set(dup) == {"rent(channel)", "give_back == return_ok"}                       # P3, P2
    assert all(f.cls == CONFLICT for f in dup.values())
    [sub] = by_kind(report, "SUBSUMED ACTION")                                           # P4
    assert sub.subject == "return_at_main" and sub.cls == CONFLICT
    assert [c for c, _ in sub.detail["covered_by"]] == ["return_ok(t='T1')", "give_back(t='T1')"]

    [fb] = by_kind(report, "FALLBACK ROUTE")                                             # P1
    assert fb.cls == CONFLICT and fb.subject == "repair_anywhere / repaired"
    reasons = {(r["refuses"], r["reason"]) for r in fb.detail["refusals"]}
    assert reasons == {("repaired(t='T1')", "main is busy"),
                       ("repair_anywhere(t='T1')", "main is free: use repaired")}
    assert fb.detail["decided_by"] == [["main_busy", ["False"], ["True"]]]
    assert fb.path == ("rent(t='T1', channel='desk')", "return_damaged(t='T1')", "workshop()")
    assert fb.state == "cond[T1]='repair', main_busy=True"

    same = {f.line for f in by_kind(report, "SAME-RESULT BRANCH")}
    assert same == {48, 72}                                                              # P5 (and P6's if)
    [never] = by_kind(report, "NEVER TAKEN")                                             # P6
    assert never.line == 73 and never.detail["lines"] == [73] and never.detail["runs_with"] == []
    [dead] = by_kind(report, "DEAD GUARD")                                               # P7
    assert dead.line == 22
    assert {f.cls for f in report.findings if f.kind in ("SAME-RESULT BRANCH", "NEVER TAKEN", "DEAD GUARD")} == {WARNING}

    core = check_model(loaded)                       # the generic checks alone say nothing ...
    assert [f for f in core.findings if f.cls == CONFLICT] == []
    conflicts = [f for f in core.findings + report.findings if f.cls == CONFLICT]
    assert len(conflicts) == 4                        # ... the overall verdict is not clean


def test_one_route_shows_the_dead_end_the_fallback_hid(project):
    report, loaded = routes(project, TOY / "rental_one_route.py")
    assert report.complete and report.findings == []
    assert summary(report.raw) == prototype_summaries(BRANCH / "toy_rental_one_route.txt")[0] == "summary: none"
    [stuck] = [f for f in check_model(loaded).findings if f.kind == "STUCK"]
    assert stuck.state == "cond[T1]='repair', branch[T1]='library'"
    assert stuck.path == ("transfer(t='T1')", "rent(t='T1')", "return_damaged(t='T1')")


def test_a_fallback_without_its_guard_is_a_subsumed_action(project):
    report, _ = routes(project, TOY / "rental_fallback_noguard.py")
    assert summary(report.raw) == prototype_summaries(BRANCH / "toy_rental_fallback_noguard.txt")[0]
    assert by_kind(report, "FALLBACK ROUTE") == []
    sub = {f.subject: f for f in by_kind(report, "SUBSUMED ACTION")}
    assert [c for c, _ in sub["repaired"].detail["covered_by"]] == ["repair_anywhere(t='T1')"]


def test_a_fallback_that_also_leaves_a_note_is_a_fallback_route(project):
    """G4: the second route makes the first one's whole change and also writes a side field
    nothing reads (a note). The prototype called it status-only (a warning); it is the same
    main effect by a second route, a FALLBACK ROUTE conflict. Only this one differs from
    the prototype's report (s1aplan/routes_e7.md: none of the E7 models has such a pair)."""
    report, _ = routes(project, TOY / "rental_fallback_note2.py")
    proto = prototype_summaries(BRANCH / "toy_rental_fallback_note2.txt")[0]
    assert summary(report.raw) == proto.replace("dead_guard 1, duplicate 2, fallback_status 1",
                                                "dead_guard 1, duplicate 2, fallback 1")
    assert by_kind(report, "STATUS-ONLY FALLBACK") == []
    [fb] = by_kind(report, "FALLBACK ROUTE")
    assert fb.cls == CONFLICT and fb.subject == "repair_anywhere / repaired"
    assert fb.detail["also"] == ["note[T1]"] and fb.detail["decided_by"][0][0] == "main_busy"
    assert "repair_anywhere(t='T1') also changes note[T1]" in fb.text


def test_a_second_route_whose_extra_field_changes_behaviour_stays_status_only(project):
    """A field some action's guard or effect depends on is no side field: a pair that differs
    there keeps the status-only warning (sonnet1_R11's transfer / bring with sentvia)."""
    text = (TOY / "rental_fallback_note2.py").read_text(encoding="utf-8")
    text = text.replace('    need(s["cond", t] == "shop", "only shelf tools move")\n    if',
                        '    need(s["cond", t] == "shop", "only shelf tools move")\n'
                        '    need(s["note", t] == "", "a tool repaired away stays where it is")\n    if')
    report, _ = routes(project, text, name="read_note")
    assert by_kind(report, "FALLBACK ROUTE") == []
    assert [f.subject for f in by_kind(report, "STATUS-ONLY FALLBACK")] == ["repair_anywhere / repaired on cond"]


@pytest.mark.parametrize("rule", [
    'm.always("a note is one we know", lambda s: all(s["note", t] in ("", "repaired away") for t in TOOLS))',
    'm.always("a note only after a repair", lambda s: all(s["note", t] == "" or s["cond", t] != "loan" '
    'for t in TOOLS))',
    'm.reach("a tool repaired away", lambda s: any(s["note", t] == "repaired away" for t in TOOLS))',
])
def test_a_rule_that_reads_the_extra_field_leaves_it_a_side_field(project, rule):
    """G4 round 2: a side field is decided by what the actions do with it, not by whether
    some statement reads it. A promise that reads the note (and holds) changes no call, so
    the fallback that also writes the note is still a FALLBACK ROUTE (once a warning)."""
    text = (TOY / "rental_fallback_note2.py").read_text(encoding="utf-8").replace("MODEL = m\n", rule + "\nMODEL = m\n")
    report, _ = routes(project, text, name="rule_note")
    [fb] = by_kind(report, "FALLBACK ROUTE")
    assert fb.cls == CONFLICT and fb.subject == "repair_anywhere / repaired"
    assert "repair_anywhere(t='T1') also changes note[T1]" in fb.text
    assert by_kind(report, "STATUS-ONLY FALLBACK") == []


def test_the_other_toys_match_the_prototype(project):
    for name in ("rental_fallback_note", "rental_r10_fixed", "rental_r10_naive"):
        report, _ = routes(project, TOY / f"{name}.py")
        assert summary(report.raw) == prototype_summaries(BRANCH / f"toy_{name}.txt")[0], name


# ---------------------------------------------------------------------- declared second routes
def stored(project, rid="R7"):
    project.request(rid, "Repair the tool where it is when the main workshop is busy.")


def with_second_route(pair, source="R7"):
    text = (TOY / "rental_planted.py").read_text(encoding="utf-8")
    a, b = pair
    line = f'm.second_route("{a}", "{b}", source="{source}", why="the owner asked for it")\n'
    return text.replace("MODEL = m\n", line + "MODEL = m\n")


def test_a_sourced_second_route_is_listed_not_reported(project):
    stored(project)
    report, _ = routes(project, with_second_route(("repaired", "repair_anywhere")), name="declared")
    assert by_kind(report, "FALLBACK ROUTE") == []
    assert report.declared == [{"actions": ["repaired", "repair_anywhere"], "source": "R7",
                                "why": "the owner asked for it", "line": 84, "keeps": ["FALLBACK ROUTE"]}]
    # nothing else is exempted: the other planted conflicts stay
    assert {f.kind for f in report.findings if f.cls == CONFLICT} == {"DUPLICATE ROUTE", "SUBSUMED ACTION"}

    report, _ = routes(project, with_second_route(("give_back", "return_ok")), name="declared2")
    assert {f.subject for f in by_kind(report, "DUPLICATE ROUTE")} == {"rent(channel)"}
    assert len(by_kind(report, "FALLBACK ROUTE")) == 1
    assert report.declared[0]["keeps"] == ["DUPLICATE ROUTE"]


def test_a_declaration_that_matches_nothing_keeps_nothing(project):
    stored(project)
    report, _ = routes(project, with_second_route(("rent", "transfer")), name="unmatched")
    assert len(by_kind(report, "FALLBACK ROUTE")) == 1
    assert report.declared[0]["keeps"] == []


def test_a_second_route_must_name_a_stored_request(project):
    """G4: m.second_route(source=...) keeps a second route only for a request the owner
    stored; an invented id is a model error, not a silent exemption."""
    path = project.flow("made_up", with_second_route(("repaired", "repair_anywhere"), source="R999"))
    with pytest.raises(ModelError, match=r"second_route\('repaired', 'repair_anywhere'\): source 'R999' is no "
                                         r"stored request \(\.flowguard/requests/R999\.md\)") as err:
        load_model(path, project.root)
    assert err.value.line == 84
    assert ".flowguard/requests/R999.md" in err.value.reads          # adding it makes the check run again
    project.request("R999", "Repair where the tool is when main is busy.")
    loaded = load_model(path, project.root)
    assert ".flowguard/requests/R999.md" in loaded.reads


@pytest.mark.parametrize("source", ["../../README", "R7/../R7", "/etc/hostname", "R 7", ""])
def test_a_second_route_source_is_a_request_id_not_a_path(project, source):
    """G4 round 2: source= names a request in .flowguard/requests/ by its id; a path that
    reaches another file (once '../../README' passed as a stored request) is a model error,
    and no report prints another file's first line as a request's words."""
    from flowguard._next.project import request_lines
    stored(project)
    (project.root / "README.md").write_text("# Some readme\n")
    path = project.flow("made_up", with_second_route(("repaired", "repair_anywhere"), source=source))
    with pytest.raises(ModelError, match=r"second_route\('repaired', 'repair_anywhere'\): source"):
        load_model(path, project.root)
    assert request_lines(project.root, ["../../README"]) == [("../../README", "(not a stored request)")]


# ---------------------------------------------------------------------- the E7 census
def golden_files():
    out = []
    for model_file in sorted(GOLDEN.glob("*/*.py")):
        flat = model_file.parent.name.replace("_mach_", "_").replace("_machine_", "_") + "_" + model_file.stem
        out.append((model_file, BRANCH / f"{flat}.txt"))
    return out


@pytest.mark.parametrize("model_file, report_file", golden_files(),
                         ids=[f"{m.parent.name}/{m.stem}" for m, _ in golden_files()])
def test_e7_counts_equal_the_prototype(model_file, report_file):
    """Per machine of the file; lines only a sibling machine runs are not NEVER TAKEN. Every
    line the new check reports is also in the prototype's report of that machine."""
    models, ifs = load_forced_machines(model_file)
    observations = [observe(m, explore(m, Bounds()), ifs) for m in models]
    reports = [judge(o, others=[x for x in observations if x is not o]) for o in observations]
    assert [summary(r.raw) for r in reports] == prototype_summaries(report_file)
    sections = report_file.read_text(encoding="utf-8").split("\n\n")
    for report, section in zip(reports, sections):
        proto = {line.strip() for line in section.splitlines()}
        for f in report.raw:
            assert set(f.detail["report"]) <= proto, f.detail["report"]


@pytest.mark.parametrize("name", ["rental_planted", "rental_fallback_noguard", "rental_fallback_note",
                                  "rental_fallback_note2", "rental_r10_fixed"])
def test_toy_report_lines_are_the_prototype_lines(project, name):
    report, _ = routes(project, TOY / f"{name}.py")
    proto = {line.strip() for line in (BRANCH / f"toy_{name}.txt").read_text(encoding="utf-8").splitlines()}
    lines = [line for f in report.raw if not f.detail.get("also") for line in f.detail["report"]]
    assert lines and set(lines) <= proto


def test_every_golden_file_has_a_prototype_report():
    assert len(golden_files()) == 23
    assert all(r.is_file() for _, r in golden_files())


# ---------------------------------------------------------------------- symmetry
@pytest.fixture(scope="module")
def bring(tmp_path_factory):
    from conftest import Project
    project = Project(tmp_path_factory.mktemp("bring") / "p")
    reduced, _ = routes(project, DATA / "scale" / "bring_3_2.py")
    plain, _ = routes(project, DATA / "scale" / "bring_3_2.py", reduce=False)
    return reduced, plain


def test_reduced_routes_equal_the_unreduced_ones(bring):
    reduced, plain = bring
    assert [f.id for f in reduced.findings] == [f.id for f in plain.findings]
    assert summary(reduced.raw) == summary(plain.raw)
    [fb] = by_kind(reduced, "FALLBACK ROUTE")
    assert fb.subject == "bring / transfer"
    assert fb.objects == ("M1", "M2", "T1", "T2", "T3")
    assert fb.detail["pairs"] == by_kind(plain, "FALLBACK ROUTE")[0].detail["pairs"] == 12


def test_reduced_paths_are_real_runs(bring):
    reduced, plain = bring
    [a], [b] = by_kind(reduced, "FALLBACK ROUTE"), by_kind(plain, "FALLBACK ROUTE")
    assert len(a.path) == len(b.path)
    assert a.detail["made_from"] == b.detail["made_from"]   # concrete state counts, not representatives


@pytest.mark.parametrize("src", [DATA / "sym" / "workshop_r10.py", DATA / "kit" / "workshop_naive.py"])
def test_small_symmetric_models_match_unreduced(project, src):
    if (src.parent / "counter").is_dir():
        project.kit()
    reduced, _ = routes(project, src)
    plain, _ = routes(project, src, reduce=False)
    assert [f.id for f in reduced.findings] == [f.id for f in plain.findings]
    assert summary(reduced.raw) == summary(plain.raw)


def test_never_taken_names_the_settings_that_run_it(project):
    report, _ = routes(project, DATA / "sym" / "workshop_r10.py")
    [never] = by_kind(report, "NEVER TAKEN")
    assert never.detail["function"] == "to_repair"
    assert never.detail["runs_with"] == ["to_main_on_repair=1", "to_main_on_repair=2"]


# ---------------------------------------------------------------------- bounds, errors, determinism
def test_a_capped_graph_decides_no_route(project):
    report, _ = routes(project, TOY / "rental_planted.py", max_states=5)
    assert not report.complete
    assert report.findings == [] and report.unknown == ["routes"]
    assert "clean" not in json.dumps(report.info) and "holds" not in json.dumps(report.info)


CAPPED_VARIANT = '''
from flowguard._next import Model, need
m = Model("counter")
S = m.settings
m.setting("limit", 1, vary=[50])
m.field("c", range(0, 2), 0)
m.field("big", [False, True], False)
@m.action()
def tick(s):
    need(s["c"] < S["limit"], "at the limit")
    s["c"] += 1
    if s["c"] > 1:
        s["big"] = True
MODEL = m
'''


def test_a_capped_one_setting_change_leaves_never_taken_undecided(project):
    report, _ = routes(project, CAPPED_VARIANT, name="counter", max_states=10)
    [never] = by_kind(report, "NEVER TAKEN")
    assert never.detail["undecided"] == ["limit=50 (capped)"]
    assert "no complete one-setting change runs it; undecided: limit=50 (capped)" in never.text
    assert "no one-setting change runs it either" not in never.text


def test_a_model_that_answers_differently_twice_is_a_model_error(project):
    path = project.flow("flaky", '''
        from flowguard._next import Model, need
        RUNS = []
        m = Model("flaky")
        m.field("x", [0, 1], 0)
        @m.action()
        def flip(s):
            RUNS.append(1)
            need(len(RUNS) < 3, "tired")
            s["x"] = 1 - s["x"]
        MODEL = m
        ''')
    force = ForceIfs(path)
    loaded = load_model(path, project.root, transform=force)
    graph = explore(loaded.model, Bounds())
    with pytest.raises(ModelError, match="does not give the same result twice"):
        check_routes(loaded.model, graph, force.ifs)
    result = run_part(PartContext(project.root, PartSpec("routes", "flaky"), path, project.root / "cache"))
    [f] = result.findings
    assert f["kind"] == "MODEL ERROR" and "same result twice" in f["text"]


def test_the_wrapped_ifs_change_nothing(project):
    path = project.flow_from(TOY / "rental_planted.py")
    force = ForceIfs(path)
    forced = explore(load_model(path, project.root, transform=force).model, Bounds())
    plain = explore(load_model(path, project.root).model, Bounds())
    assert forced.states == plain.states and [list(r) for r in forced.out] == [list(r) for r in plain.out]
    assert sorted(ln for _, ln in force.ifs) == [48, 72, 74]


def test_the_routes_part(project):
    stored(project)
    path = project.flow("declared", with_second_route(("repaired", "repair_anywhere")))
    result = run_part(PartContext(project.root, PartSpec("routes", "declared"), path, project.root / "cache"))
    assert result.kind == "routes" and result.complete
    assert result.reads == [".flowguard/flow/declared.py", ".flowguard/requests/R7.md"]   # the request is a read
    assert {f["kind"] for f in result.findings if f["cls"] == CONFLICT} == {"DUPLICATE ROUTE", "SUBSUMED ACTION"}
    assert result.info["declared_routes"][0]["keeps"] == ["FALLBACK ROUTE"]

    capped = run_part(PartContext(project.root, PartSpec("routes", "declared", (("max_states", 5),)), path,
                                  project.root / "cache"))
    assert not capped.complete and capped.findings == [] and capped.info["unknown"] == ["routes"]

    broken = project.flow("broken", "from flowguard._next import Model\nm = Model('x')\n")
    result = run_part(PartContext(project.root, PartSpec("routes", "broken"), broken, project.root / "cache"))
    assert [f["kind"] for f in result.findings] == ["MODEL ERROR"]


_SEED_SCRIPT = """
import json, sys
from pathlib import Path
from flowguard._next.model import load_model
from flowguard._next.explore import Bounds, explore
from flowguard._next.routes import ForceIfs, check_routes
root, path = Path(sys.argv[1]), Path(sys.argv[2])
force = ForceIfs(path)
loaded = load_model(path, root, transform=force)
report = check_routes(loaded.model, explore(loaded.model, Bounds()), force.ifs)
print(json.dumps([[f.cls, f.kind, f.subject, f.id, f.text] for f in report.findings]))
"""


@pytest.mark.parametrize("src", [TOY / "rental_planted.py", DATA / "sym" / "workshop_r10.py"])
def test_the_same_findings_under_every_hash_seed(project, src):
    path = project.flow_from(src)
    runs = []
    for seed in (0, 1, 2):
        env = {**os.environ, "PYTHONHASHSEED": str(seed), "PYTHONPATH": str(REPO)}
        res = subprocess.run([sys.executable, "-c", _SEED_SCRIPT, str(project.root), str(path)],
                             capture_output=True, text=True, env=env, timeout=300)
        assert res.returncode == 0, res.stderr
        runs.append(json.loads(res.stdout))
    assert runs[0] == runs[1] == runs[2] and runs[0]
