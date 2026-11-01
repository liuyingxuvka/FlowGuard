"""FG-814 check: the output contract (design 7.2), exit codes, `--json`, new vs open
across runs, `.flowguard/conflicts.json`, and the time bound of every call."""
from __future__ import annotations

import json
import re
import shutil

import pytest

from checkrun import Run, run_check
from conftest import DATA

KIT = DATA / "kit"
RENDERER = shutil.which("node") is not None       # pictures are drawn by Mermaid in headless Chromium
JSON_KEYS = ["verdict", "exit", "complete", "conflicts", "warnings", "errors", "unknown", "models", "parts",
             "declared_routes", "resume", "running"]

DIAL = '''
from flowguard._next import Model, need
m = Model("dial")
m.field("pos", range(0, 5), 0, note="0..4; the dial stops at 2")

@m.action()
def up(s):
    need(s["pos"] < 2, "at the top")
    s["pos"] += 1

@m.action()
def down(s):
    need(s["pos"] > 0, "at the bottom")
    s["pos"] -= 1
MODEL = m
'''

COUNTERS = '''
from flowguard._next import Model, need
m = Model("counters")
for name in ("a", "b", "c"):
    m.field(name, range(0, 50), 0)

@m.action(k=["a", "b", "c"])
def bump(s, k):
    need(s[k] < 49, "full")
    s[k] += 1

@m.action()
def drain(s):
    need(s["a"] == 49 and s["b"] == 49 and s["c"] == 49, "not full")
    s["a"], s["b"], s["c"] = 0, 0, 0
m.always("few at once", lambda s: RULE)
m.progress("the counters drain", when=lambda s: s["a"] == 49, goal=lambda s: s["a"] == 0)
MODEL = m
'''

LAMP = '''
from flowguard._next import Model
m = Model("lamp")
m.field("on", [False, True], False)

@m.action()
def flip(s):
    s["on"] = not s["on"]
m.always("the lamp stays off", lambda s: not s["on"], source="R1")
MODEL = m
'''

HIDDEN = '''
from flowguard._next import Model, need
from _ids import FAVOURITE
m = Model("tools")
TOOLS = m.objects("tool", "T1", "T2")
m.field("cond", ["shop", "loan"], "shop", over=TOOLS)

@m.action(t=TOOLS)
def rent(s, t):
    need(s["cond", t] == "shop", "busy")
    s["cond", t] = "loan"

@m.action(t=TOOLS)
def back(s, t):
    need(s["cond", t] == "loan", "not out")
    need(t != FAVOURITE, "the favourite stays out")
    s["cond", t] = "shop"
MODEL = m
'''

BROKEN_LOAD = '''
from flowguard._next import Model
m = Model("broken")
m.field("x", [0, 1], 0)
raise RuntimeError("the model cannot load")
'''


def timed(root, *args, wait=None, **kw) -> Run:
    """Every call ends before its wait plus 3 s (the default wait is 90 s)."""
    run = run_check(root, *args, **kw)
    limit = (wait if wait is not None else 90) + 3
    assert run.seconds < limit, (run.seconds, run.out, run.err)
    return run


def blocks(text):
    return re.findall(r"```(\w+)\n(.*?)```", text, re.S)


# ---------------------------------------------------------------------- verdict forms and exit codes
def test_not_a_project_and_usage_errors(tmp_path):
    run = timed(tmp_path, wait=0)
    assert run.code == 2 and run.first.startswith("not a FlowGuard project")
    assert len(run.lines) == 1
    data = timed(tmp_path, "--json", wait=0).data
    assert data["exit"] == 2 and data["verdict"].startswith("not a FlowGuard project")
    assert list(data) == JSON_KEYS
    (tmp_path / ".flowguard").mkdir()
    run = timed(tmp_path, "--wait", "-1", wait=0)
    assert run.code == 2 and run.first.startswith("usage error: argument --wait")
    run = timed(tmp_path, "--nope", wait=0)
    assert run.code == 2 and run.first.startswith("usage error: unrecognized arguments: --nope")
    (tmp_path / "elsewhere.py").write_text("MODEL = None\n")
    run = timed(tmp_path, "elsewhere.py", wait=0)
    assert run.code == 2 and run.first.startswith("elsewhere.py: models live in .flowguard/flow/")


def test_an_empty_flow_directory(project):
    run = timed(project.root)
    assert (run.code, run.out) == (0, "no flow models in .flowguard/flow/\n")


def test_clean_complete_with_the_reach_line(project):
    project.kit().flow_from(KIT / "workshop.py")
    run = timed(project.root)
    assert run.code == 0
    assert run.lines == ["clean, complete; 1 model warning",       # the routes part: a guard the rule makes dead
                         'model warning workshop: line 45: need(s["branch", t] == "main", "repairs only at main", '
                         'source="R10")  (checked, never refuses)',
                         "workshop: complete, 171 states (tools explored up to renaming); settings "
                         "maintain_every=4 (counter/config.py: Config.maintain_every)"]
    saved = json.loads((project.root / ".flowguard/conflicts.json").read_text())
    assert saved["conflicts"] == [] and saved["complete"] and saved["unknown"] == []


def test_model_warnings_are_counted_on_the_clean_line(project):
    project.flow("dial", DIAL)
    run = timed(project.root)
    assert run.code == 0
    assert run.lines[0] == "clean, complete; 2 model warnings"
    assert run.lines[1:3] == ["model warning dial: pos = 3 is never reached (no one-setting change reaches it)",
                              "model warning dial: pos = 4 is never reached (no one-setting change reaches it)"]
    assert run.lines[3] == "dial: complete, 3 states"


def test_new_conflicts_in_full_then_open_on_one_line(project):
    project.kit().flow_from(KIT / "workshop_naive.py", "workshop")
    run = timed(project.root)
    assert run.code == 1
    assert run.first == "6 new conflicts; complete"
    heads = [line for line in run.lines if line.startswith("NEW ")]
    assert len(heads) == 6
    assert re.fullmatch(r"NEW STUCK workshop: T1 stuck with cond='loan', branch='library', rentals=4: "
                        r"branch\[\*\] = 'library' can never change again "
                        r"\(tools T1, T2\)   \[C-[0-9a-f]{12}\]", heads[0])
    i = run.lines.index(heads[0])
    stuck = run.lines[i:i + 14]
    assert stuck[1:7] == ["  rent(t='T1') refused: 'not on the shelf' (R4)",
                          "  repaired(t='T1') refused: 'not in repair' (R9)",
                          "  move(t='T1', b='main') refused: 'only shelf tools move' (R6)",
                          "  later, where cond[*] = 'repair': give_back(t='T1') refused: 'not on loan' (R9)",
                          "  later, where cond[*] = 'repair': repaired(t='T1') refused: 'repairs only at main' "
                          "(R10)",
                          "  entered by rent(t='T1') (R4)"]
    assert stuck[7] == ('  requests: R4 "# Request 4: renting tools" | R6 "# Request 6: two branches" | '
                        'R9 "# Request 9: regular maintenance" | R10 "Repairs are done only at the main branch."')
    assert stuck[8] == "  state: cond[T1]='loan', branch[T1]='library', rentals[T1]=4"
    assert stuck[9].startswith("  path (8 steps): rent(t='T1') ; give_back(t='T1') ;")
    assert stuck[10] == ("  then also stuck: cond[*] = 'repair'; progress 'a tool in repair or on the way gets back "
                         "to a shelf' (1 counter value folded: rentals[*])")
    assert stuck[11] == "  note: clamped at maintain_every: more rentals behave the same"
    assert "  no one-setting change reaches it" in run.lines
    assert run.lines[-1].startswith("workshop: complete, 171 states")
    ids = [h.rsplit("[", 1)[1][:-1] for h in heads]

    again = timed(project.root)
    assert again.code == 1 and again.first == "6 open conflicts; complete"
    assert [line.rsplit("[", 1)[1][:-1] for line in again.lines if line.startswith("OPEN ")] == ids
    assert not any(line.startswith(("NEW ", "  ")) for line in again.lines)

    project.flow("lamp", LAMP)
    third = timed(project.root)
    assert third.code == 1 and third.first == "1 new conflict, 6 open; complete"
    assert [line for line in third.lines if line.startswith("NEW ")] == [
        "NEW BROKEN lamp: always 'the lamp stays off' is broken by an order of steps   ["
        + third.lines[1].rsplit("[", 1)[1]]
    assert third.lines[2:4] == ['  requests: R1 "(not a stored request)"', "  state: on=True"]


def test_a_model_error_has_its_location_and_exit_2(project):
    project.flow("broken", BROKEN_LOAD)
    project.flow("dial", DIAL)
    run = timed(project.root)
    assert run.code == 2
    assert run.first == "1 model error; complete"
    assert ("MODEL ERROR broken: .flowguard/flow/broken.py:4: loading raised RuntimeError: the model cannot load"
            in run.lines)
    assert "broken: not explored (model error)" in run.lines
    project.kit().flow_from(KIT / "workshop_naive.py", "workshop")
    run = timed(project.root)
    assert run.code == 2 and run.first == "6 new conflicts; 1 model error; complete"


def test_a_capped_model_is_unknown_never_clean(project):
    project.flow("counters", COUNTERS.replace("RULE", "True"))
    run = timed(project.root, "--max-states", "1000")
    assert run.code == 3
    assert run.first == ("no conflict found; UNKNOWN: counters capped at 1,000 states "
                         "(STUCK, NEVER REACHED, routes, 2 rules undecided)")
    data = timed(project.root, "--max-states", "1000", "--json").data
    for text in (run.out, json.dumps(data)):
        assert "clean" not in text.lower() and "holds" not in text.lower()
    assert data["exit"] == 3 and data["unknown"] == ["counters"] and data["complete"] is False
    assert json.loads((project.root / ".flowguard/conflicts.json").read_text())["unknown"] == ["counters"]

    project.flow("counters", COUNTERS.replace("RULE", 's["a"] + s["b"] < 3'))
    run = timed(project.root, "--max-states", "1000")
    assert run.code == 1
    assert run.first == "1 new conflict; UNKNOWN: counters capped at 1,000 states"
    assert "  path (3 steps): bump(k='a') ; bump(k='a') ; bump(k='a')" in run.lines
    saved = json.loads((project.root / ".flowguard/conflicts.json").read_text())
    assert saved["unknown"] == ["counters"] and [c["kind"] for c in saved["conflicts"]] == ["BROKEN"]


# ---------------------------------------------------------------------- --json
def test_json_is_one_line_with_the_contract_keys(project):
    project.kit().flow_from(KIT / "workshop_naive.py")
    project.flow("dial", DIAL)
    data = timed(project.root, "--json").data
    assert list(data) == JSON_KEYS
    assert data["verdict"] == "6 new conflicts; complete" and data["exit"] == 1 and data["complete"]
    assert len(data["conflicts"]) == 6 and all(c["new"] for c in data["conflicts"])
    assert data["conflicts"][0]["requests"][0] == ["R4", "# Request 4: renting tools"]
    pictures = [c["picture"] for c in data["conflicts"]]
    assert all(p == f".flowguard/cache/flow/pictures/workshop_naive-{c['id'][2:]}.{'svg' if RENDERER else 'mmd'}"
               for p, c in zip(pictures, data["conflicts"]))
    assert all((project.root / p).is_file() for p in pictures)
    assert [(w["model"], w["kind"]) for w in data["warnings"]] == [
        ("dial", "NEVER REACHED"), ("dial", "NEVER REACHED"),
        ("workshop_naive", "SAME-RESULT BRANCH"), ("workshop_naive", "NEVER TAKEN")]
    assert data["errors"] == [] and data["unknown"] == []
    assert data["models"]["dial"]["reach"] == "dial: complete, 3 states"
    assert [(p["kind"], p["model"], p["cached"]) for p in data["parts"]] == [
        ("core", "dial", False), ("routes", "dial", False), ("core", "workshop_naive", False),
        ("routes", "workshop_naive", False)]
    assert data["resume"] is None and data["running"] is None and data["declared_routes"] == []
    again = timed(project.root, "--json").data
    assert all(p["cached"] for p in again["parts"]) and not any(c["new"] for c in again["conflicts"])
    assert again["verdict"] == "6 open conflicts; complete"


def test_the_same_fingerprints_and_file_under_every_hash_seed(project):
    project.kit().flow_from(KIT / "workshop_naive.py")
    seen = []
    for seed in (0, 1, 2):
        shutil.rmtree(project.root / ".flowguard" / "cache", ignore_errors=True)
        (project.root / ".flowguard" / "conflicts.json").unlink(missing_ok=True)
        data = timed(project.root, "--json", seed=seed).data
        seen.append(([c["id"] for c in data["conflicts"]],
                     (project.root / ".flowguard/conflicts.json").read_bytes()))
    assert seen[0] == seen[1] == seen[2]


# ---------------------------------------------------------------------- conflicts.json
def test_checking_one_model_keeps_the_others_open_conflicts(project):
    project.kit().flow_from(KIT / "workshop_naive.py")
    project.flow("lamp", LAMP)
    first = timed(project.root)
    assert first.first == "7 new conflicts; complete"
    path = project.root / ".flowguard/conflicts.json"
    before = path.read_bytes()
    run = timed(project.root, "lamp")
    assert run.first == "1 open conflict; complete"
    assert path.read_bytes() == before                 # unchanged result: the file is unchanged
    (project.root / ".flowguard/flow/workshop_naive.py").unlink()
    timed(project.root, "lamp")
    saved = json.loads(path.read_text())
    assert {c["model"] for c in saved["conflicts"]} == {"lamp"}
    assert list(saved["models"]) == ["lamp"]
    assert set(saved) == {"engine", "tree", "complete", "conflicts", "unknown", "warnings", "models"}


# ---------------------------------------------------------------------- warnings from the caller and --full
def test_overlapping_views_warn_from_recorded_facts(project):
    project.kit().flow_from(KIT / "workshop.py")
    project.flow("maintenance", (KIT / "workshop.py").read_text().replace('Model("workshop"', 'Model("maint"'))
    run = timed(project.root)
    assert run.code == 0 and run.first == "clean, complete; 8 model warnings"
    assert ("model warning maintenance: field 'branch' is also declared by workshop; overlapping views of "
            "counter/core.py (one owner per field)") in run.lines


def test_full_verifies_the_renaming_without_reduction(project):
    project.kit().flow_from(KIT / "workshop.py")
    run = timed(project.root, "--full")
    assert run.code == 0
    assert run.lines[-1].endswith("; symmetry verified (324 states unreduced)")
    plain = timed(project.root, "--json").data
    assert not plain["parts"][0]["cached"]           # --full is another part: its own digest
    assert not plain["models"]["workshop"]["symmetry"]


def test_full_turns_a_hidden_asymmetry_into_a_model_error(project):
    project.file(".flowguard/flow/_ids.py", 'FAVOURITE = "T" + "1"\n')
    project.flow("tools", HIDDEN)
    plain = run_check(project.root)
    assert plain.code == 1 and not any(line.startswith("MODEL ERROR") for line in plain.lines)
    full = run_check(project.root, "--full")
    assert full.code == 2
    assert full.first.endswith("; 1 model error; complete")
    assert any(line.startswith("MODEL ERROR tools: objects are not interchangeable") for line in full.lines)


# ---------------------------------------------------------------------- the guide
def test_the_guide_states_what_check_prints(project):
    howto = (DATA.parents[2] / "flowguard" / "_next" / "HOWTO.md").read_text(encoding="utf-8")
    [model] = [code for kind, code in blocks(howto) if kind == "python" and "MODEL = m" in code]
    clean_text, broken_text = [code for kind, code in blocks(howto) if kind == "text"]
    project.flow("parcels", model)
    run = timed(project.root)
    assert run.out == clean_text
    project.flow("parcels", "\n".join(l for l in model.splitlines() if '"the locker is full"' not in l) + "\n")
    run = timed(project.root)
    stated = broken_text.splitlines()
    assert run.first == stated[0]
    rest = iter(run.lines[1:])
    for line in stated[1:]:                         # the guide shortens: each line starts one printed
        assert any(printed.startswith(line) for printed in rest), line


# ---------------------------------------------------------------------- rendering units
def test_a_picture_written_for_a_conflict_is_printed(project):
    from flowguard._next import cli, jobs
    from flowguard._next.parts import PartResult, PartSpec
    from flowguard._next.checks import make_finding
    f = make_finding("BROKEN", "conflict", "m", "always 'x'", "always 'x' is broken by an order of steps",
                     sources=["R1"], path=["a()"])
    pic = f".flowguard/cache/flow/pictures/m-{f.id[2:]}.svg"
    (project.root / pic).parent.mkdir(parents=True)
    (project.root / pic).write_text("<svg/>")
    item = jobs.Planned(PartSpec("core", "m", (("max_states", 10),)), ".flowguard/flow/m.py")
    result = PartResult("core", "m", "d", True, [f.to_json()],
                        {"loaded": True, "reach_line": "m: complete, 1 state", "reach": {"symmetry": [], "states": 1},
                         "covers": [], "families": [], "objects": {}, "unknown": []}, [], [pic])
    outcome = jobs.Outcome([item], [result], [True], [None], True)
    lines, data = cli.render(project.root, cli.assemble(project.root, outcome, None), "resume")
    assert lines[0] == "1 new conflict; complete"
    assert f"  picture: {pic}" in lines
    assert data["conflicts"][0]["picture"] == pic


def test_status_lines_read_the_last_final_check(project):
    from flowguard._next.cli import status_lines
    assert status_lines(project.root) == ["flow models: no check recorded (run check)"]
    project.flow("dial", DIAL)
    timed(project.root)
    assert status_lines(project.root) == ["flow models: clean"]
    project.kit().flow_from(KIT / "workshop_naive.py")
    timed(project.root)
    [line] = status_lines(project.root)
    assert line.startswith("flow models: 6 open conflicts (C-") and line.endswith("a commit is blocked until fixed")


@pytest.mark.parametrize("args", [(), ("--json",)])
def test_nothing_comes_before_the_verdict(project, args):
    project.flow("dial", DIAL)
    run = timed(project.root, *args)
    first = run.first if not args else run.data["verdict"]
    assert first.startswith("clean, complete")
    assert run.err == ""


def test_show_runs_its_parts_in_the_worker_under_the_wait_contract(project):
    """`show` takes the options of design 6.3 and draws through the job system: the caller
    runs no model code, a check before makes its conflicts a cache hit, and a part not
    finished within --wait leaves it RUNNING with the command that resumes."""
    import subprocess
    import time
    from checkrun import command, env
    from flowguard._next import cli
    args = cli.parser().parse_args(["show", "workshop:T1", "--before", "HEAD", "--focus", "2", "--story"])
    assert (args.what, args.before, args.focus, args.story, args.max_boxes, args.max_arrows, args.wait,
            args.max_states) == ("workshop:T1", "HEAD", 2, True, 12, 20, 90.0, 200_000)

    def show(*argv):
        start = time.monotonic()
        res = subprocess.run(command("show", *argv), cwd=project.root, capture_output=True, text=True, env=env(),
                             timeout=60)
        return res, time.monotonic() - start

    project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    assert timed(project.root).code == 1                          # check first: show reuses its parts
    res, _ = show()
    assert res.returncode == 0, res.stdout + res.stderr
    first = res.stdout.splitlines()[0]
    assert first.startswith("rental: STUCK branch[*] = 'library'") and "6 boxes, 9 arrows" in first
    assert "flowchart LR" in res.stdout
    assert all(line.startswith("show: ") for line in res.stderr.splitlines())     # progress only, after 2 s

    project.flow("slow", 'import time\nfrom flowguard._next import Model, need\nm = Model("slow")\n'
                         'm.field("n", range(0, 8), 0)\n\n@m.action()\ndef tick(s):\n    time.sleep(0.4)\n'
                         '    need(s["n"] < 7, "at the end")\n    s["n"] += 1\n\n@m.action()\ndef reset(s):\n'
                         '    need(s["n"] == 7, "not at the end")\n    s["n"] = 0\nMODEL = m\n')
    res, seconds = show("slow", "--wait", "1")
    assert res.returncode == 4 and seconds < 4
    assert res.stdout.startswith("RUNNING: ") and res.stdout.count("\n") == 1
    assert res.stdout.rstrip().endswith("; resume with: python -m flowguard._next show slow --wait 1")
    res, _ = show("slow", "--wait", "1", "--json")
    data = json.loads(res.stdout)
    assert data["exit"] == 4 and data["resume"] == "python -m flowguard._next show slow --wait 1 --json"
    res, _ = show("slow", "--wait", "40")
    assert res.returncode == 0 and res.stdout.startswith("slow: ") and "flowchart LR" in res.stdout
    res, _ = show("nosuch", "--json")
    assert res.returncode == 2 and json.loads(res.stdout)["message"] == "nosuch: no such model (models: rental, slow)"


def test_route_conflicts_in_full_with_their_pictures(project):
    """The routes part runs in every check: a fallback prints both refusals and the path to
    where the second route is used, every route conflict has its picture, and show draws it
    with both routes red."""
    import subprocess
    from checkrun import command, env
    project.flow_from(DATA / "toy_next" / "rental_planted.py", "rental")
    run = timed(project.root)
    assert run.code == 1 and run.first == "4 new conflicts; complete"
    heads = [line for line in run.lines if line.startswith("NEW ")]
    assert [h.split()[1:3] for h in heads] == [["DUPLICATE", "ROUTE"], ["DUPLICATE", "ROUTE"], ["SUBSUMED", "ACTION"],
                                               ["FALLBACK", "ROUTE"]]
    i = run.lines.index(heads[3])
    assert run.lines[i + 1:i + 8] == [
        "  requests: the AI's own",
        "  state: cond[T1]='repair', main_busy=True",
        "  path (3 steps): rent(t='T1', channel='desk') ; return_damaged(t='T1') ; workshop()",
        "  for example: cond[T1]: 'repair' -> 'shop'",
        "  where repair_anywhere(t='T1') does it, repaired(t='T1') refuses: 'main is busy' (1 of 2 states)",
        "  where repaired(t='T1') does it, repair_anywhere(t='T1') refuses: 'main is free: use repaired' "
        "(1 of 1 states)",
        f"  picture: .flowguard/cache/flow/pictures/rental-{heads[3].rsplit('[C-', 1)[1][:-1]}."
        + ("svg" if RENDERER else "mmd (Mermaid text: the picture file was not written)")]
    assert sum(line.startswith("  picture: ") for line in run.lines) == 4
    fid = heads[3].rsplit("[", 1)[1][:-1]
    res = subprocess.run(command("show", fid), cwd=project.root, capture_output=True, text=True, env=env(),
                         timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr
    assert res.stdout.startswith(f"rental: FALLBACK ROUTE repair_anywhere / repaired [{fid}]")
    assert "red: the arrows of the routes repair_anywhere, repaired" in res.stdout


def test_a_change_that_sends_books_to_repair_with_no_way_back_is_not_clean(project):
    """G8: the end-to-end naive change (R4 adds `damaged`, nothing repairs) once ended in
    exit 0 "clean": the repair value nothing leaves was taken as the end of a book's life."""
    desk = DATA / "desk"
    shutil.copytree(desk / "app", project.root / "app")
    for p in (desk / "requests").glob("*.md"):
        shutil.copy(p, project.root / ".flowguard" / "requests" / p.name)
    project.flow_from(desk / "desk.py")
    assert timed(project.root).code == 0
    project.flow_from(desk / "desk_naive.py", "desk")
    run = timed(project.root)
    assert run.code == 1 and "clean" not in run.first
    [head] = [line for line in run.lines if line.startswith("NEW STUCK")]
    assert "where[*] = 'repair'" in head and "B1 stuck with where='repair'" in head
    assert 'R4 "Damaged books go to repair and come back to the shelf when repaired."' in run.out
