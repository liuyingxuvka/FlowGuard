"""FG-814 check: the output contract (design 7.2), exit codes, `--json`, new vs open
across runs, `.flowguard/conflicts.json`, and the time bound of every call."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys

import pytest

from checkrun import Run, run_check
from conftest import DATA

KIT = DATA / "kit"
RENDERER = shutil.which("node") is not None       # pictures are drawn by Mermaid in headless Chromium
JSON_KEYS = ["verdict", "exit", "complete", "conflicts", "warnings", "surviving_breakages", "setting_proposals",
             "errors", "unknown", "models", "parts",
             "declared_routes", "closed", "resume", "running"]

DIAL = '''
from flowguard.flow import Model, need
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
from flowguard.flow import Model, need
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
from flowguard.flow import Model
m = Model("lamp")
m.field("on", [False, True], False)

@m.action()
def flip(s):
    s["on"] = not s["on"]
m.always("the lamp stays off", lambda s: not s["on"], source="R1")
MODEL = m
'''

HIDDEN = '''
from flowguard.flow import Model, need
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
from flowguard.flow import Model
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
    assert re.fullmatch(r"NEW STUCK workshop: T1 stuck in cond='repair', branch='library': "
                        r"cond\[\*\] = 'repair' and branch\[\*\] = 'library' can never change again "
                        r"\(tools T1, T2\)   \[C-[0-9a-f]{12}\]", heads[0])
    i = run.lines.index(heads[0])
    stuck = run.lines[i:i + 15]
    assert stuck[1:8] == ["  rent(t='T1') refused: 'not on the shelf' (R4)",
                          "  arrive(t='T1') refused: 'not on the way' (R10)",     # the exit that never works
                          "  repaired(t='T1') refused: 'not in repair' (R9)",
                          "  move(t='T1', b='main') refused: 'only shelf tools move' (R6)",
                          "  later, where cond[*] = 'repair': give_back(t='T1') refused: 'not on loan' (R9)",
                          "  later, where cond[*] = 'repair': repaired(t='T1') refused: 'repairs only at main' "
                          "(R10)",
                          "  entered by rent(t='T1') (R4)"]
    assert stuck[8] == ('  requests: R4 "Members rent tools from the shelf of a branch." | '
                        'R6 "Tools on the shelf can be moved between the main branch and the library corner." | '
                        'R9 "A tool goes to maintenance after every few rentals." | '
                        'R10 "Repairs are done only at the main branch."')
    assert stuck[9] == "  state: cond[T1]='loan', branch[T1]='library', rentals[T1]=4"
    assert stuck[10].startswith("  path (8 steps): rent(t='T1') ; give_back(t='T1') ;")
    assert stuck[11] == ("  then also stuck: progress 'a tool in repair or on the way gets back "
                         "to a shelf' (1 counter value folded: rentals[*])")
    assert stuck[12] == "  note: clamped at maintain_every: more rentals behave the same"
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


UNSTORED = '''
from flowguard.flow import Model, need
m = Model("door")
m.field("open", [False, True], False, source="R1")

@m.action(source="R2")
def open_door(s):
    need(not s["open"], "already open", source="R3")
    s["open"] = True

@m.action(source="R1")
def close(s):
    need(s["open"], "already closed")
    s["open"] = False
MODEL = m
'''


def test_a_source_that_names_no_stored_request_is_a_model_warning(project):
    """A7: an id no request is stored under is a visible warning, not only "(not a stored
    request)" beside a conflict; storing the owner's words with `req add` ends it at the next
    check, with no change to the model."""
    project.request("R1", "Doors open and close.\n")
    project.flow("door", UNSTORED)
    run = timed(project.root)
    assert run.code == 0 and run.first == "clean, complete; 2 model warnings"
    assert any(line.startswith("model warning door: source 'R2' is not a stored request (action open_door): "
                               "request_unknown: R2 is not stored; store it first: ")
               and "req add" in line and "--id R2" in line for line in run.lines)
    assert any(line.startswith("model warning door: source 'R3' is not a stored request (a guard of open_door "
                               "(line 7)): ") for line in run.lines)
    assert not any("'R1'" in line for line in run.lines)

    words = project.root / "words.txt"
    words.write_text("A closed door can be opened.\n", encoding="utf-8")
    added = subprocess.run([sys.executable, "-m", "flowguard", "req", "add", str(words), "--id", "R2"],
                           cwd=project.root, capture_output=True, text=True)
    assert added.returncode == 0, added.stderr
    again = timed(project.root)
    assert again.first == "clean, complete; 1 model warning"
    assert not any("'R2'" in line for line in again.lines)


def test_a_model_error_has_its_location_and_exit_2(project):
    """A model that does not load was not explored: the first line never calls the check
    complete (it says UNKNOWN for that model), and --json and conflicts.json agree."""
    project.flow("broken", BROKEN_LOAD)
    project.flow("dial", DIAL)
    run = timed(project.root)
    assert run.code == 2
    assert run.first == "1 model error; UNKNOWN: broken not explored (model error)"
    data = timed(project.root, "--json").data
    assert data["complete"] is False and data["unknown"] == ["broken"]
    saved = json.loads((project.root / ".flowguard/conflicts.json").read_text())
    assert saved["complete"] is False and saved["unknown"] == ["broken"]
    assert ("MODEL ERROR broken: .flowguard/flow/broken.py:4: loading raised RuntimeError: the model cannot load"
            in run.lines)
    assert "broken: not explored (model error)" in run.lines
    project.kit().flow_from(KIT / "workshop_naive.py", "workshop")
    run = timed(project.root)
    assert run.code == 2 and run.first == "6 new conflicts; 1 model error; UNKNOWN: broken not explored (model error)"


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
    assert data["conflicts"][0]["requests"][0] == ["R4", "Members rent tools from the shelf of a branch."]
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
    from checkrun import gone, wait_until
    from flowguard.flow.jobs import read_json
    project.kit().flow_from(KIT / "workshop_naive.py")
    seen = []
    for seed in (0, 1, 2):
        cache = project.root / ".flowguard" / "cache"
        if cache.exists():
            shutil.rmtree(cache)
        (project.root / ".flowguard" / "conflicts.json").unlink(missing_ok=True)
        run = timed(project.root, "--json", seed=seed)
        assert run.code == 1, run.out + run.err
        data = run.data
        seen.append(([c["id"] for c in data["conflicts"]],
                     (project.root / ".flowguard/conflicts.json").read_bytes()))
        pids = {p["worker"] for p in data["parts"] if p["worker"] is not None}
        pids.update(read_json(path)["pid"] for path in cache.glob("flow/jobs/*/*/guardian.json"))
        assert wait_until(lambda: all(gone(pid) for pid in pids), 5) is not None
    assert seen[0] == seen[1] == seen[2]


# ---------------------------------------------------------------------- conflicts.json
def test_checking_one_model_keeps_the_others_open_conflicts(project):
    """Review round 2, item 4: `check lamp` printed "1 open conflict" (lamp's own) and
    exited as if the project held nothing else, while 6 proven conflicts of workshop_naive
    stayed open and blocking in conflicts.json (status said blocked). A check of some
    models leaves the others' conflicts open: they are listed as open, with what keeps
    them, and count for the exit code."""
    project.kit().flow_from(KIT / "workshop_naive.py")
    project.flow("lamp", LAMP)
    first = timed(project.root)
    assert first.first == "7 new conflicts; complete"
    path = project.root / ".flowguard/conflicts.json"
    before = path.read_bytes()
    run = timed(project.root, "lamp")
    assert run.first == "7 open conflicts; complete" and run.code == 1
    left = [line for line in run.lines if "kept: this check left workshop_naive out" in line]
    assert len(left) == 6 and all(line.startswith("OPEN ") for line in left), run.out
    data = timed(project.root, "lamp", "--json").data
    assert data["exit"] == 1 and len(data["conflicts"]) == 7 and not any(c["new"] for c in data["conflicts"])
    assert path.read_bytes() == before                 # unchanged result: the file is unchanged
    (project.root / ".flowguard/flow/workshop_naive.py").unlink()
    run = timed(project.root, "lamp")
    assert run.first == "7 open conflicts; complete" and run.code == 1
    assert sum("its model file .flowguard/flow/workshop_naive.py is gone" in line for line in run.lines) == 6
    saved = json.loads(path.read_text())               # a deleted model's conflicts stay open (G1)
    assert {c["model"] for c in saved["conflicts"]} == {"lamp", "workshop_naive"}
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


def test_full_says_on_its_first_line_that_deliberate_breakages_survive(project):
    """A8: a --full check whose deliberate breakages some survive never says a bare "clean":
    its first line counts them and points below, then the other model warnings."""
    project.kit().flow_from(KIT / "workshop.py")
    run = timed(project.root, "--full")
    warnings = [line for line in run.lines if line.startswith("model warning workshop: ")]
    survivors = [line for line in warnings if line.startswith("model warning workshop: mutant survives: ")]
    assert len(survivors) == 4 and len(warnings) == 5, run.out
    assert run.code == 0 and run.first == ("clean, complete; 4 deliberate breakages not caught - see below; "
                                           "1 other model warning")
    plain = timed(project.root)
    assert plain.first == "clean, complete; 1 model warning"


def test_full_verifies_the_renaming_without_reduction(project):
    project.kit().flow_from(KIT / "workshop.py")
    run = timed(project.root, "--full")
    assert run.code == 0
    assert run.lines[-1].endswith("; symmetry verified (324 states unreduced)")
    plain = timed(project.root, "--json").data
    assert not plain["parts"][0]["cached"]           # --full is another part: its own digest
    assert not plain["models"]["workshop"]["symmetry"]


def test_a_hidden_asymmetry_is_never_reduced(project):
    """G3 round 2: an id compared with a value the rule cannot follow (here made from text in
    a helper) is a doubt, so the plain check already explores every renaming and finds that
    only T1 is stuck; it once relied on --full to catch it. (The unreduced comparison that
    --full adds stays as the backstop: test_symmetry.py forces a reduction to exercise it.)"""
    project.file(".flowguard/flow/_ids.py", 'FAVOURITE = "T" + "1"\n')
    project.flow("tools", HIDDEN)
    plain = run_check(project.root)
    assert plain.code == 1 and not any(line.startswith("MODEL ERROR") for line in plain.lines)
    assert "T1 stuck with cond='loan'" in plain.out and "(tools T1)" in plain.out
    assert ("tools not explored up to renaming (in doubt: .flowguard/flow/tools.py:15 compares a tool id with a "
            "value the rule cannot follow); every renaming explored") in plain.lines[-1]
    full = run_check(project.root, "--full")
    assert full.code == 1 and not any(line.startswith("MODEL ERROR") for line in full.lines)


# ---------------------------------------------------------------------- the guide
def test_the_guide_states_what_check_prints(project):
    howto = (DATA.parents[2] / "flowguard" / "flow" / "HOWTO.md").read_text(encoding="utf-8")
    [model] = [code for kind, code in blocks(howto) if kind == "python" and "MODEL = m" in code]
    clean_text, broken_text = [code for kind, code in blocks(howto) if kind == "text"]
    assert "With R1 and R2 stored, `check` prints:" in howto
    project.request("R1", "Parcels wait in the one locker.\n")
    project.request("R2", "A parcel goes back after keep_days nights.\n")
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
    from flowguard.flow import cli, jobs
    from flowguard.flow.parts import PartResult, PartSpec
    from flowguard.flow.checks import make_finding
    f = make_finding("BROKEN", "conflict", "m", "always 'x'", "always 'x' is broken by an order of steps",
                     sources=["R1"], path=["a()"])
    pic = f".flowguard/cache/flow/pictures/m-{f.id[2:]}.svg"
    (project.root / pic).parent.mkdir(parents=True)
    (project.root / pic).write_text("<svg/>")
    item = jobs.Planned(PartSpec("core", "m", (("max_states", 10),)), ".flowguard/flow/m.py")
    result = PartResult("core", "m", "d", True, [f.to_json()],
                        {"loaded": True, "reach_line": "m: complete, 1 state", "reach": {"symmetry": [], "states": 1},
                         "covers": [], "families": [], "objects": {}, "unknown": [], "sources": {}}, [], [pic])
    outcome = jobs.Outcome([item], [result], [True], [None], True)
    lines, data = cli.render(project.root, cli.assemble(project.root, outcome, None), "resume")
    assert lines[0] == "1 new conflict; complete"
    assert f"  picture: {pic}" in lines
    assert data["conflicts"][0]["picture"] == pic


def test_status_lines_read_the_last_final_check(project):
    from flowguard.flow.cli import status_lines
    assert status_lines(project.root) == []                  # no flow model and no check: nothing to say
    project.flow("dial", DIAL)
    assert status_lines(project.root) == ["flow models: no check recorded (run python -m flowguard check)"]
    timed(project.root)
    assert status_lines(project.root) == ["flow models: clean"]
    project.kit().flow_from(KIT / "workshop_naive.py")
    timed(project.root)
    [line] = status_lines(project.root)
    assert line.startswith("flow models: 6 open conflicts (C-") and line.endswith("release fails until fixed; CI fails only when it runs release; without a hook a commit is not blocked")
    assert "a commit is blocked" not in line        # acceptance A6: nothing stops a commit unless a hook runs it


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
    from flowguard.flow import cli
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
    assert first.startswith("rental: STUCK T1 stuck in cond='repair', branch='library'") and "6 boxes, 9 arrows" in first
    assert "flowchart LR" in res.stdout
    assert all(line.startswith("show: ") for line in res.stderr.splitlines())     # progress only, after 2 s

    project.flow("slow", 'import time\nfrom flowguard.flow import Model, need\nm = Model("slow")\n'
                         'm.field("n", range(0, 8), 0)\n\n@m.action()\ndef tick(s):\n    time.sleep(0.4)\n'
                         '    need(s["n"] < 7, "at the end")\n    s["n"] += 1\n\n@m.action()\ndef reset(s):\n'
                         '    need(s["n"] == 7, "not at the end")\n    s["n"] = 0\nMODEL = m\n')
    res, seconds = show("slow", "--wait", "1")
    assert res.returncode == 4 and seconds < 4
    assert res.stdout.startswith("RUNNING: ") and res.stdout.count("\n") == 1
    assert res.stdout.rstrip().endswith("; resume with: python -m flowguard show slow --wait 1")
    res, _ = show("slow", "--wait", "1", "--json")
    data = json.loads(res.stdout)
    assert data["exit"] == 4 and data["resume"] == "python -m flowguard show slow --wait 1 --json"
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
    project.flow_from(DATA / "toy_flow" / "rental_planted.py", "rental")
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
    from flowguard.map.requests import store_request
    for p in (desk / "requests").glob("*.md"):
        store_request(project.root, p.read_bytes(), identifier=p.stem)
    project.flow_from(desk / "desk.py")
    assert timed(project.root).code == 0
    project.flow_from(desk / "desk_naive.py", "desk")
    run = timed(project.root)
    assert run.code == 1 and "clean" not in run.first
    [head] = [line for line in run.lines if line.startswith("NEW STUCK")]
    assert "where[*] = 'repair'" in head and "B1 stuck with where='repair'" in head
    assert 'R4 "Damaged books go to repair and come back to the shelf when repaired."' in run.out


def test_a_capped_check_never_closes_a_proven_conflict(project):
    """G1 (M6, as the coordinator decided): a conflict proven by a complete check stays open
    and blocking through every capped check, also once its stored shrunk path no longer
    replays; it closes only when a complete check of its model no longer finds it."""
    from flowguard.flow.cli import status_lines
    saved = project.root / ".flowguard/conflicts.json"
    for rid in ("R4", "R6", "R8", "R10"):                # the requests the rental model names
        project.request(rid, f"Request {rid[1:]} of the rental shop.\n")
    project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    assert timed(project.root).first == "1 new conflict; complete"
    [cid] = [c["id"] for c in json.loads(saved.read_text())["conflicts"]]

    capped = timed(project.root, "--max-states", "3")
    assert capped.code == 1 and capped.first == "1 open conflict; UNKNOWN: rental capped at 3 states"
    [line] = [x for x in capped.lines if x.startswith("OPEN ")]
    assert line.startswith("OPEN STUCK rental: ") and f"[{cid}]" in line
    assert line.endswith("(kept: its stored path still reproduces it; this check is capped)")
    data = json.loads(saved.read_text())
    assert [c["id"] for c in data["conflicts"]] == [cid] and data["unknown"] == ["rental"]
    [status] = status_lines(project.root)
    assert f"1 open conflict ({cid}); release fails until fixed; CI fails only when it runs release; without a hook a commit is not blocked" in status
    assert "UNKNOWN for rental (does not block)" not in status

    path = project.root / ".flowguard/flow/rental.py"
    path.write_text("\n".join(x for x in path.read_text().splitlines() if 'need(s["branch", t]' not in x) + "\n")
    fixed = timed(project.root, "--max-states", "4")             # 6 states now; 4 from where the path ends
    assert fixed.code == 1 and fixed.first == "1 open conflict; UNKNOWN: rental capped at 4 states", fixed.out
    assert not any(x.startswith("closed ") for x in fixed.lines), fixed.out
    [line] = [x for x in fixed.lines if x.startswith("OPEN ")]
    assert f"[{cid}]" in line and "(kept: its stored path no longer replays (from where its path ends, " in line, line
    assert line.endswith("this check is capped; a complete check will settle it)"), line
    assert [c["id"] for c in json.loads(saved.read_text())["conflicts"]] == [cid]
    complete = timed(project.root)                               # only a complete check closes it
    assert complete.code == 0 and complete.first == "clean, complete", complete.out
    assert f"closed {cid} STUCK rental: a complete check of rental no longer finds it" in complete.lines
    assert json.loads(saved.read_text())["conflicts"] == []


NO_TRANSIT = [
    ('m.field("cond", ["shop", "loan", "transit", "repair"], "shop", over=TOOLS, source="R4",\n'
     '        value_sources={"transit": "R10"})',
     'm.field("cond", ["shop", "loan", "repair"], "shop", over=TOOLS, source="R4")'),
    ('@m.action(t=TOOLS, source="R10")\ndef arrive(s, t):\n    need(s["cond", t] == "transit", "not on the way")\n'
     '    s["cond", t], s["branch", t] = "repair", "main"\n', ""),
    ('when=lambda s, t: s["cond", t] in ("transit", "repair")', 'when=lambda s, t: s["cond", t] == "repair"'),
    ('m.reach("a tool due at the library goes to main", lambda s: any(s["cond", t] == "transit" for t in TOOLS),\n'
     '        source="R10")\n', "")]


def test_a_capped_check_after_a_settings_change_keeps_every_proven_conflict(project):
    """G1 round 4 (the coordinator's decision, design M6 changed): with maintain_every
    changed from 4 to 3 the stored paths no longer replay, and a capped check closed all
    three proven conflicts ("no conflict found; UNKNOWN", exit 3, status "does not
    block"); the next complete check found the same three again as NEW. A failed replay
    now closes nothing: they stay open and block, marked so, and the complete check that
    still finds them reports them as open."""
    from flowguard.flow.cli import status_lines
    saved = project.root / ".flowguard/conflicts.json"
    text = (KIT / "workshop_naive.py").read_text()
    for old, new in NO_TRANSIT:
        assert old in text
        text = text.replace(old, new)
    project.kit().flow("workshop", text)
    first = timed(project.root)
    assert first.code == 1 and first.first == "3 new conflicts; complete", first.out
    ids = sorted(c["id"] for c in json.loads(saved.read_text())["conflicts"])
    config = project.root / "counter" / "config.py"
    config.write_text(config.read_text().replace("maintain_every: int = 4", "maintain_every: int = 3"))
    capped = timed(project.root, "--max-states", "30")
    assert capped.code == 1, capped.out
    assert capped.first == "3 open conflicts; UNKNOWN: workshop capped at 30 states", capped.out
    assert not any(x.startswith(("closed ", "NEW ")) for x in capped.lines), capped.out
    opened = [x for x in capped.lines if x.startswith("OPEN ")]
    assert len(opened) == 3, capped.out
    for line in opened:
        assert "(kept: its stored path no longer replays (step " in line, line
        assert line.endswith("this check is capped; a complete check will settle it)"), line
    assert sorted(c["id"] for c in json.loads(saved.read_text())["conflicts"]) == ids
    [status] = status_lines(project.root)
    assert "3 open conflicts" in status and "release fails until fixed; CI fails only when it runs release; without a hook a commit is not blocked" in status, status
    assert "does not block" not in status, status
    again = timed(project.root)
    assert again.code == 1 and again.first == "3 open conflicts; complete", again.out
    assert sorted(c["id"] for c in json.loads(saved.read_text())["conflicts"]) == ids


@pytest.mark.parametrize("model, old, new", [
    ("rental_naive", "return_damaged", "return_broken"),       # an action of the stored path
    ("rental_naive", '"branch"', '"site"'),                    # the stuck field
    ("lamp", '"the lamp stays off"', '"the lamp is off"')])    # the broken rule
def test_a_rename_closes_no_conflict_under_a_capped_check(project, model, old, new):
    """G1 (M6): a replay that meets a call, field or rule the model no longer has under its
    old name decides nothing (a rename is no evidence the conflict is gone); the capped
    check keeps the conflict. A renamed action leaves the fingerprint as it was: the next
    complete check finds the same conflict again."""
    saved = project.root / ".flowguard/conflicts.json"
    if model == "lamp":
        path = project.flow("rental", LAMP)
    else:
        path = project.flow_from(DATA / "planted" / f"{model}.py", "rental")
    assert timed(project.root).code == 1
    [cid] = [c["id"] for c in json.loads(saved.read_text())["conflicts"]]
    path.write_text(path.read_text().replace(old, new))
    cap = "1" if model == "lamp" else "3"
    capped = timed(project.root, "--max-states", cap)
    assert capped.code == 1 and capped.first == f"1 open conflict; UNKNOWN: rental capped at {cap} states", capped.out
    [line] = [x for x in capped.lines if x.startswith("OPEN ")]
    assert f"[{cid}]" in line and "is no " in line and line.endswith("this check is capped)"), line
    assert not any(x.startswith("closed ") for x in capped.lines)
    assert [c["id"] for c in json.loads(saved.read_text())["conflicts"]] == [cid]
    if old == "return_damaged":
        again = timed(project.root)
        assert again.code == 1 and again.first == "1 open conflict; complete" and f"[{cid}]" in again.out


def test_a_renamed_or_deleted_model_file_keeps_its_conflicts(project):
    """G1 (M6): the conflicts of a model whose file is gone stay open (in the output and in
    conflicts.json, so in status) under every check; nothing explored that model's scope.
    They close when a complete check of that model no longer finds them."""
    from flowguard.flow.cli import status_lines
    saved = project.root / ".flowguard/conflicts.json"
    path = project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    assert timed(project.root).code == 1
    [cid] = [c["id"] for c in json.loads(saved.read_text())["conflicts"]]
    moved = path.with_name("rental2.py")
    path.rename(moved)
    capped = timed(project.root, "--max-states", "3")
    assert capped.code == 1 and capped.first == "1 open conflict; UNKNOWN: rental2 capped at 3 states", capped.out
    [line] = [x for x in capped.lines if x.startswith("OPEN ")]
    assert line.startswith("OPEN STUCK rental: ") and f"[{cid}]" in line
    assert line.endswith("(kept: its model file .flowguard/flow/rental.py is gone; it closes only when a complete "
                         "check of rental no longer finds it)")
    assert cid in [c["id"] for c in json.loads(saved.read_text())["conflicts"]]
    [status] = status_lines(project.root)
    assert f"1 open conflict ({cid}); release fails until fixed; CI fails only when it runs release; without a hook a commit is not blocked" in status
    full = timed(project.root)                     # rental2's own conflict is new; rental's stays
    assert full.code == 1 and full.first == "1 new conflict, 1 open; complete"
    assert f"[{cid}] (kept: its model file .flowguard/flow/rental.py is gone" in full.out
    moved.unlink()
    assert timed(project.root).code == 1 and cid in saved.read_text()
    project.flow_from(DATA / "planted" / "rental_fixed.py", "rental")
    fixed = timed(project.root, "rental")
    assert f"[{cid}]" not in fixed.out and cid not in saved.read_text()


def test_a_model_error_closes_no_conflict(project):
    """A model that does not load was not explored: its proven conflicts stay open."""
    saved = project.root / ".flowguard/conflicts.json"
    path = project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    assert timed(project.root).code == 1
    [cid] = [c["id"] for c in json.loads(saved.read_text())["conflicts"]]
    text = path.read_text()
    path.write_text(text + "\nraise RuntimeError('half edited')\n")
    run = timed(project.root)
    assert run.code == 2 and f"[{cid}]" in run.out
    assert "(kept: proven by an earlier complete check; the model does not load)" in run.out
    assert [c["id"] for c in json.loads(saved.read_text())["conflicts"]] == [cid]


CUT_SHORT = [('''    need(s["cond", t] == "loan", "not out")
    s["cond", t] = "repair"''', '''    need(s["cond", t] == "loan", "not out")
    if s["branch", t] == "library":
        raise RuntimeError("no repair desk here")
    s["cond", t] = "repair"'''),
             ('''    s["branch", t] = "library" if s["branch", t] == "main" else "main"''', '''    if s["branch", t] == "library":
        raise RuntimeError("no van back")
    s["branch", t] = "library"''')]


def test_a_model_error_in_the_search_closes_nothing_and_proves_nothing(project):
    """G1 round 2: a model that loads but raises during the search was counted as a complete
    exploration. Its proven STUCK vanished from the output and conflicts.json with no
    "closed" line, and the cut-short graph made false conflicts that were stored as proven.
    A search a model error cuts short decides no STUCK and no NEVER REACHED, closes nothing,
    and says it was cut short."""
    from flowguard.flow.cli import status_lines
    saved = project.root / ".flowguard/conflicts.json"
    path = project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    assert timed(project.root).code == 1
    [cid] = [c["id"] for c in json.loads(saved.read_text())["conflicts"]]
    text = path.read_text()
    cut = text
    for old, new in CUT_SHORT:
        assert old in cut
        cut = cut.replace(old, new)
    path.write_text(cut)
    run = timed(project.root)
    assert run.code == 2, run.out
    assert run.first == "1 open conflict; 2 model errors; UNKNOWN: rental cut short by a model error", run.out
    assert not any(x.startswith(("NEW ", "closed ")) for x in run.lines), run.out
    [line] = [x for x in run.lines if x.startswith("OPEN ")]
    assert f"[{cid}]" in line and line.endswith("a model error cut this check short)"), line
    assert "rental: CUT SHORT by 2 model errors: UNKNOWN for STUCK, NEVER REACHED" in run.out
    data = json.loads(saved.read_text())
    assert [c["id"] for c in data["conflicts"]] == [cid] and data["unknown"] == ["rental"]
    [status] = status_lines(project.root)
    assert "release fails until fixed; CI fails only when it runs release; without a hook a commit is not blocked" in status and "rental (2 model errors" in status, status
    path.write_text(text)                                        # restored: a capped check keeps only the real one
    capped = timed(project.root, "--max-states", "3")
    assert capped.code == 1 and capped.first == "1 open conflict; UNKNOWN: rental capped at 3 states", capped.out
    assert [c["id"] for c in json.loads(saved.read_text())["conflicts"]] == [cid]


CLOCK_ERROR = '''
from flowguard.flow import Model, need

m = Model("clock")
m.field("day", range(0, 6), 0)
m.field("lamp", [False, True], False)


@m.action()
def tick(s):
    need(s["day"] < 5, "the last day")
    s["day"] += 1


@m.action()
def flip(s):
    s["lamp"] = not s["lamp"]


m.always("the lamp is read", lambda s: {}["x"] if s["day"] > 1 else True)
MODEL = m
'''


def test_one_model_error_met_in_many_states_is_counted_once(project):
    """Review of round 5, item 4: a rule that raises the same error in every state from day 2
    on gave "1 model error" in the first line and "CUT SHORT by 8 model errors" in the reach
    line (one per state where it was met). Both now count the model errors to fix: one."""
    project.flow("clock", CLOCK_ERROR)
    run = timed(project.root)
    assert run.code == 2, run.out
    assert run.first.startswith("no conflict found; 1 model error; UNKNOWN: clock cut short by a model error"), run.out
    assert len([x for x in run.lines if x.startswith("MODEL ERROR ")]) == 1, run.out
    assert "clock: CUT SHORT by 1 model error: UNKNOWN for" in run.out, run.out


def test_the_text_names_the_declared_second_routes(project):
    """G4: a kept second route is printed in the text, not only in --json."""
    text = (DATA / "toy_flow" / "rental_planted.py").read_text(encoding="utf-8").replace(
        "MODEL = m\n", 'm.second_route("repaired", "repair_anywhere", source="R7", why="main is often busy")\nMODEL = m\n')
    project.request("R7", "Repair the tool where it is when the main workshop is busy.")
    project.flow("rental", text)
    run = timed(project.root)
    assert ('declared second route rental: repaired / repair_anywhere (R7 "Repair the tool where it is when the main '
            'workshop is busy."; keeps FALLBACK ROUTE): main is often busy') in run.lines


MERGED = "<<<<<<< HEAD\n{\"conflicts\": []}\n=======\n{\"conflicts\": []}\n>>>>>>> other\n"


@pytest.mark.parametrize("text, reason", [
    (MERGED, "it holds git merge markers"),
    ("{\"conflicts\": [\n", "it is not valid JSON"),
    ("[1, 2]\n", "it is not a JSON object"),
    ("{\"conflicts\": [{\"x\": 1}], \"unknown\": []}\n", "conflicts[0] has no 'id'"),
    ("{\"conflicts\": [], \"unknown\": 3}\n", "'unknown' is not a list"),
])
def test_an_unreadable_conflicts_file_stops_check_and_show_in_one_line(project, text, reason):
    """Acceptance A1: a corrupt or merge-marked conflicts.json (it is committed, so a merge can
    leave markers in it) is named with the step that restores it, as status names it, and
    check and show exit 2, never with a traceback and never with 1 (the conflict code). The
    file is left as it was: nothing is decided about open conflicts it may hold."""
    import subprocess
    from checkrun import command, env
    project.flow("dial", DIAL)
    saved = project.root / ".flowguard/conflicts.json"
    saved.write_text(text, encoding="utf-8")
    for verb in ("check", "show"):
        res = subprocess.run(command(verb), cwd=project.root, capture_output=True, text=True, env=env(), timeout=60)
        assert res.returncode == 2, (verb, res.stdout, res.stderr)
        [line] = res.stdout.splitlines()
        assert line.startswith(f".flowguard/conflicts.json cannot be read ({reason}"), line
        assert "until it is restored (" in line and "from your project backup" in line, line
        assert "Traceback" not in res.stderr, res.stderr
        res = subprocess.run(command(verb, "--json"), cwd=project.root, capture_output=True, text=True, env=env(),
                             timeout=60)
        data = json.loads(res.stdout)
        assert res.returncode == 2 and data["exit"] == 2
        assert (data.get("verdict") or data.get("message")).startswith(".flowguard/conflicts.json cannot be read")
    assert saved.read_text(encoding="utf-8") == text
    from flowguard.flow.cli import status_lines
    [status] = status_lines(project.root)
    assert status.startswith(f"flow models: .flowguard/conflicts.json cannot be read ({reason}")


def test_a_merge_marked_conflicts_file_names_the_merge_step(project):
    """git checkout -- FILE refuses an unmerged file, so the merge case names taking one side."""
    from flowguard.flow.project import ProjectError, read_conflicts
    project.flow("dial", DIAL)
    project.file(".flowguard/conflicts.json", '{"conflicts": []}\n')
    project.commit()
    (project.root / ".flowguard/conflicts.json").write_text(MERGED, encoding="utf-8")
    with pytest.raises(ProjectError) as caught:
        read_conflicts(project.root)
    assert "git checkout --ours -- .flowguard/conflicts.json" in str(caught.value)
    assert str(caught.value).endswith("; then run python -m flowguard check)")


@pytest.mark.parametrize("verb", ["check", "show"])
def test_an_internal_error_exits_2_never_1(project, monkeypatch, verb):
    """Acceptance A1: an unexpected error inside check or show prints one "internal error:"
    line with its place and exits 2; exit 1 means a conflict and nothing else."""
    import io
    from flowguard.flow import cli, diagram, jobs

    def boom(*a, **k):
        raise KeyError("id")
    monkeypatch.setattr(jobs, "plan", boom)
    monkeypatch.setattr(diagram, "show_main", boom)
    project.flow("dial", DIAL)
    for extra in ([], ["--json"]):
        out = io.StringIO()
        assert cli.main([verb, "--root", str(project.root), *extra], out=out, err=io.StringIO()) == 2
        text = out.getvalue()
        if extra:
            data = json.loads(text)
            text = data.get("verdict") or data.get("message")
        assert text.startswith("internal error: KeyError: 'id' (flowguard/flow/cli.py:"), text


def test_release_runs_the_full_check_with_its_mutants(project):
    """G5 / design 7.6: the release entry runs check --full (mutation and the unreduced
    symmetry check); a conflict or a model error stops the release, UNKNOWN does not.
    The move-in wires the legacy `release` to cli.release (s1aplan/MOVE_IN.md)."""
    import io
    from flowguard.flow import cli
    project.kit().flow_from(KIT / "workshop.py")
    out = io.StringIO()
    assert cli.release(project.root, out=out, err=io.StringIO()) is True
    text = out.getvalue()
    assert text.startswith("clean, complete") and "mutant survives" in text and "symmetry verified" in text
    project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    out = io.StringIO()
    assert cli.release(project.root, out=out, err=io.StringIO()) is False
    assert "  cause (check --full): without guard 'repairs only at main'" in out.getvalue()


FAR_CORNER = '''
from flowguard.flow import Model, need
m = Model("grow")
m.setting("top", 2, vary=[60, 3])
m.field("a", range(0, 61), 0)
m.field("b", range(0, 400), 0)
m.field("done", [False, True], False)

@m.action()
def up(s):
    need(s["a"] < m.settings["top"], "at the top")
    s["a"] += 1

@m.action()
def side(s):
    need(s["b"] < 399, "at the end")
    s["b"] += 1

@m.action()
def finish(s):
    need(s["a"] == 60 and s["b"] == 399, "not at the far corner")
    s["done"] = True
MODEL = m
'''


def test_a_capped_one_setting_change_is_undecided_not_a_no(project):
    """G7 round 2: only top=60 can reach the far corner, and that variant is capped (more
    than 20,000 states), so no complete change reaches it and top=60 is undecided. The
    text once said "no one-setting change reaches it; UNKNOWN with top=60 (capped)", which
    contradicts itself; it now reads like the never-taken line warning, and a change that
    did reach an item beside an undecided one is no longer "only"."""
    project.flow("grow", FAR_CORNER)
    run = timed(project.root)
    assert run.code == 1, run.out
    assert "  no complete one-setting change reaches it; undecided: top=60 (capped)" in run.lines, run.out
    assert ("model warning grow: done = True is never reached (no complete one-setting change reaches it; "
            "undecided: top=60 (capped))") in run.lines, run.out
    assert "model warning grow: a = 3 is never reached (reached only with top=60, top=3)" in run.lines, run.out
    assert not any("UNKNOWN with" in line or "no one-setting change reaches it;" in line for line in run.lines)


GOAL = '''
from flowguard.flow import Model, need
m = Model("goal")
m.field("a", range(0, 61), 0)
m.field("b", range(0, 400), 0)
m.field("done", [False, True], False)

@m.action()
def up(s):
    need(s["a"] < TOP, "at the top")
    s["a"] += 1

@m.action()
def side(s):
    s["b"] = s["b"] + 1 if s["b"] < WIDTH else 0         # goes round: the model never halts

@m.action(source="R1")
def finish(s):
    need(s["a"] == 60, "not at the top")
    s["done"] = not s["done"]
m.reach("finished", lambda s: s["done"], source="R1")
MODEL = m
'''


def test_a_capped_check_that_reaches_a_never_reached_item_keeps_it_until_a_complete_check(project):
    """G1 round 4 (the coordinator's decision): a capped check never closes a proven
    conflict, also a NEVER REACHED one its search reaches (it once closed it: "this check
    reaches it", exit 3). It stays open and blocking, and says the capped check reaches it
    now, so the line agrees with the reach line; a complete check of the model closes it."""
    project.request("R1", "# Request 1: the goal can be reached\n")
    saved = project.root / ".flowguard/conflicts.json"
    path = project.flow("goal", GOAL.replace("TOP", "2").replace("WIDTH", "3"))
    first = timed(project.root)
    assert first.code == 1 and first.first == "2 new conflicts; complete", first.out
    ids = {c["subject"]: c["id"] for c in json.loads(saved.read_text())["conflicts"]}
    assert set(ids) == {"action finish", "reach 'finished'"}, ids
    path.write_text(GOAL.replace("TOP", "60").replace("WIDTH", "399"))     # 48,800 states: capped below
    capped = timed(project.root, "--max-states", "5000")
    assert capped.code == 1, capped.out
    assert capped.first == "2 open conflicts; UNKNOWN: goal capped at 5,000 states", capped.out
    assert not any(x.startswith("closed ") for x in capped.lines), capped.out
    for subject, cid in ids.items():
        [line] = [x for x in capped.lines if x.startswith("OPEN NEVER REACHED goal: ") and f"[{cid}]" in x]
        assert line.endswith("(kept: this check reaches it now; this check is capped; a complete check will "
                             "settle it)"), line
    assert sorted(c["id"] for c in json.loads(saved.read_text())["conflicts"]) == sorted(ids.values())
    path.write_text(GOAL.replace("TOP", "60").replace("WIDTH", "3"))       # small enough to explore completely
    complete = timed(project.root)
    assert complete.code == 0, complete.out
    for subject, cid in ids.items():
        assert f"closed {cid} NEVER REACHED goal: a complete check of goal no longer finds it" in complete.lines
    assert json.loads(saved.read_text())["conflicts"] == []


def test_a_capped_check_that_does_not_reach_a_never_reached_item_keeps_it(project):
    project.request("R1", "# Request 1: the goal can be reached\n")
    saved = project.root / ".flowguard/conflicts.json"
    path = project.flow("goal", GOAL.replace("TOP", "2").replace("WIDTH", "3"))
    assert timed(project.root).code == 1
    path.write_text(GOAL.replace("TOP", "2").replace("WIDTH", "399"))      # still unreachable; capped
    capped = timed(project.root, "--max-states", "500")
    assert capped.code == 1 and capped.first == "2 open conflicts; UNKNOWN: goal capped at 500 states", capped.out
    assert len(json.loads(saved.read_text())["conflicts"]) == 2


WITHDRAW = '''
from flowguard.flow import Model, need
m = Model("books")
BOOKS = m.objects("book", "B1", "B2")
m.field("where", ["shelf", "loan", "lost", "gone"], "shelf", over=BOOKS)
m.field("day", range(0, 8), 0)

@m.action()
def tick(s):
    need(s["day"] < 7, "the last day")
    s["day"] += 1

@m.action(b=BOOKS)
def lend(s, b):
    need(s["where", b] == "shelf", "not on the shelf")
    s["where", b] = "loan"

@m.action(b=BOOKS)
def give_back(s, b):
    need(s["where", b] == "loan", "not out")
    s["where", b] = "shelf"

@m.action(b=BOOKS)
def withdraw(s, b):
    need(s["where", b] == "lost", "not lost")
    s["where", b] = "gone"
m.terminal("where", ["gone"])
MODEL = m
'''


@pytest.mark.parametrize("renames", [
    [("def withdraw", "def retire")],
    [('"gone"', '"retired"')],
    [("def withdraw", "def retire"), ('"gone"', '"retired"')],
    [('''@m.action(b=BOOKS)
def withdraw(s, b):
    need(s["where", b] == "lost", "not lost")
    s["where", b] = "gone"
''', ""), ('"lost", "gone"', '"lost"'), ('m.terminal("where", ["gone"])', "")],
], ids=["action", "value", "both", "removed"])
def test_a_capped_check_closes_no_never_reached_item_the_model_no_longer_has(project, renames):
    """G1 round 3: a capped check closed a stored NEVER REACHED conflict whenever its subject
    was missing from the list of items the search did not reach, and an action or value
    the model renamed or removed is missing from that list too: 'closed ...: this check
    reaches it' for an item nothing reached, exit 3 and conflicts.json emptied. Only an
    item the model defines now and an explored state reaches closes it; a renamed or
    removed one is kept like any other proven conflict of a capped check."""
    from flowguard.flow.cli import status_lines
    saved = project.root / ".flowguard/conflicts.json"
    path = project.flow("books", WITHDRAW)
    first = timed(project.root)
    assert first.code == 1 and first.first == "2 new conflicts; complete", first.out
    ids = sorted(c["id"] for c in json.loads(saved.read_text())["conflicts"])
    assert len(ids) == 2
    text = WITHDRAW
    for old, new in renames:
        assert old in text
        text = text.replace(old, new)
    path.write_text(text)
    capped = timed(project.root, "--max-states", "10")
    assert capped.code == 1, capped.out
    assert capped.first == "2 open conflicts; UNKNOWN: books capped at 10 states", capped.out
    assert not any(x.startswith("closed ") for x in capped.lines), capped.out
    opened = [x for x in capped.lines if x.startswith("OPEN NEVER REACHED books: ")]
    assert len(opened) == 2 and all(x.endswith("this check is capped)") for x in opened), capped.out
    assert sorted(c["id"] for c in json.loads(saved.read_text())["conflicts"]) == ids
    [status] = status_lines(project.root)
    assert "2 open conflicts" in status and "release fails until fixed; CI fails only when it runs release; without a hook a commit is not blocked" in status, status
