"""FG-811 known-bad, always on: every model is made wrong on purpose (drop a guard, widen a
guard, remove a transition, make a declared end unreachable) and checked again; a mutant
no check catches is a model warning, so a model whose checks cannot fail is visible.
Equivalent mutants are not listed; a capped mutant is unknown, never survived or caught;
the part runs only with --full.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from flowguard.flow import parts
from flowguard.flow.checks import WARNING
from flowguard.flow.explore import Bounds, explore
from flowguard.flow.model import load_model
from flowguard.flow.mutate import guard_mutants, run_mutants
from flowguard.flow.parts import PartContext, PartSpec, run_part
from flowguard.flow.routes import ForceIfs, check_routes

from conftest import DATA, REPO

HOWTO = Path(__file__).parents[2] / "flowguard" / "flow" / "HOWTO.md"


def parcels():
    text = HOWTO.read_text(encoding="utf-8")
    return next(b for b in re.findall(r"```python\n(.*?)```", text, re.S) if "MODEL = m" in b)


def mutate(project, src, name=None, max_states=200_000):
    path = project.flow_from(src, name) if isinstance(src, Path) else project.flow(name, src)
    return run_mutants(load_model(path, project.root), Bounds(max_states)), path


def outcome(report, what):
    [o] = [o for o in report.outcomes if o["what"] == what]
    return o


def test_parcel_locker_guards_are_caught_except_the_reviewed_survivors(project):
    report, _ = mutate(project, parcels(), "parcels")
    assert report.complete
    guards = {o["what"]: o["outcome"] for o in report.outcomes if o["op"] in ("drop guard", "widen guard")}
    # Reviewed: no rule of the guide's model says a collected or returned parcel cannot be
    # delivered again, picked up from the depot, or replaced while in use; only the full
    # locker is a promise ("one parcel at a time in the locker").
    assert guards == {
        "drop guard 'not at the depot' (deliver, line 16)": "survived",
        "drop guard 'the locker is full' (deliver, line 17)": "caught",
        "drop guard 'not in the locker' (pick_up, line 23)": "survived",
        "drop guard 'slot in use' (new_parcel, line 38)": "survived",
    }
    assert outcome(report, "drop guard 'the locker is full' (deliver, line 17)")["by"] == [
        "BROKEN always 'one parcel at a time in the locker'"]
    survivors = {f.subject for f in report.findings}
    assert {"drop guard 'not at the depot' in deliver", "drop guard 'not in the locker' in pick_up",
            "drop guard 'slot in use' in new_parcel"} <= survivors
    assert all(f.kind == "MUTANT SURVIVES" and f.cls == WARNING for f in report.findings)
    [f] = [f for f in report.findings if f.subject == "drop guard 'not at the depot' in deliver"]
    assert f.text == ("mutant survives: drop guard 'not at the depot' (deliver, line 16): "
                      "no rule or generic check fails without it")
    assert f.sources == ("R1",)


def test_without_rules_graph_changing_guard_drops_survive_and_are_listed(project):
    report, _ = mutate(project, DATA / "planted" / "tool_life.py")
    survived = {o["what"] for o in report.outcomes if o["outcome"] == "survived" and o["op"] == "drop guard"}
    assert survived == {"drop guard 'not in repair' (repaired, line 25)", "drop guard 'not in repair' (retire, line 32)",
                        "drop guard 'not worn out yet' (retire, line 33)"}
    caught = {o["what"]: o["by"] for o in report.outcomes if o["outcome"] == "caught" and o["op"] == "drop guard"}
    for what in ("drop guard 'not on the shelf' (rent, line 13)", "drop guard 'not on loan' (give_back, line 19)"):
        # a retired tool rented (or sent to repair) again leaves its declared end; its repair count
        # running out at 3 is a bounded counter's end and no dead end by itself (acceptance A5)
        assert any("cond = 'retired' is declared an end (m.terminal('cond', ...)), but" in b and "leaves it" in b
                   for b in caught[what]), caught
    listed = {f.detail["what"] for f in report.findings}
    assert survived <= listed


def test_every_operator_runs_and_ends_and_transitions_are_caught(project):
    report, _ = mutate(project, DATA / "planted" / "tool_life.py")
    ops = {o["op"] for o in report.outcomes}
    assert ops == {"drop guard", "widen guard", "remove transition", "end unreachable"}
    end = outcome(report, "make end cond='retired' unreachable")
    assert end["outcome"] == "caught" and "NEVER REACHED value cond[*] = 'retired'" in end["by"]
    assert outcome(report, "remove transition: retire keeps cond unchanged (line 30)")["outcome"] == "caught"
    widen = outcome(report, "widen guard 'worn out: retire it' (repaired, line 26): `<` -> `<=` in "
                            "`s['repairs', t] < 3`")
    assert widen["outcome"] == "caught"           # repairs runs out of its domain: a model error


def test_conjunct_drops_are_widened_guards(project):
    path = project.flow("pair", '''
        from flowguard.flow import Model, need
        m = Model("pair")
        m.field("a", [0, 1], 0)
        m.field("b", [0, 1], 0)
        @m.action()
        def both(s):
            need(s["a"] == 0 and s["b"] == 0, "both clear")
            s["a"] = 1
        @m.action()
        def other(s):
            s["b"] = 1 - s["b"]
        MODEL = m
        ''')
    loaded = load_model(path, project.root)
    widen = [m.what for m in guard_mutants(loaded.model) if m.op == "widen guard"]
    assert widen == ["widen guard 'both clear' (both, line 7): drop `s['a'] == 0`",
                     "widen guard 'both clear' (both, line 7): drop `s['b'] == 0`"]


def test_equivalent_mutants_are_not_listed_and_sit_on_dead_or_untaken_guards(project):
    for src in (DATA / "toy_flow" / "rental_planted.py", DATA / "kit" / "workshop.py",
                DATA / "toy_flow" / "rental_r10_fixed.py"):
        if (src.parent / "counter").is_dir() and not (project.root / "counter").exists():
            project.kit()
        report, path = mutate(project, src)
        equivalent = [o for o in report.outcomes if o["outcome"] == "equivalent"]
        assert equivalent, src.name
        assert not {o["what"] for o in equivalent} & {f.detail["what"] for f in report.findings}
        force = ForceIfs(path)
        loaded = load_model(path, project.root, transform=force)
        routes = check_routes(loaded.model, explore(loaded.model, Bounds()), force.ifs)
        quiet = {f.line for f in routes.findings if f.kind == "DEAD GUARD"}
        quiet |= {ln for f in routes.findings if f.kind == "NEVER TAKEN" for ln in f.detail["lines"]}
        for o in equivalent:
            if o["op"] == "drop guard":
                line = int(re.search(r"line (\d+)\)", o["what"]).group(1))
                assert line in quiet, (src.name, o["what"])


CAPPED = '''
from flowguard.flow import Model, need
m = Model("counter")
m.field("c", range(0, 10), 0)
@m.action()
def inc(s):
    need(s["c"] < 2, "at the limit")
    s["c"] += 1
MODEL = m
'''


def test_a_capped_mutant_is_unknown(project):
    report, _ = mutate(project, CAPPED, "counter", max_states=5)
    drop = outcome(report, "drop guard 'at the limit' (inc, line 6)")
    assert drop["outcome"] == "unknown"
    assert not report.complete and report.unknown == ["mutation"]
    assert "drop guard 'at the limit' in inc" not in {f.subject for f in report.findings}
    widen = outcome(report, "widen guard 'at the limit' (inc, line 6): `<` -> `<=` in `s['c'] < 2`")
    assert widen["outcome"] == "caught"           # 4 states fit: decided (the end moves from c = 2 to c = 3)
    assert "STUCK c = 3" in widen["by"], widen


def test_a_capped_original_decides_nothing(project):
    report, _ = mutate(project, CAPPED, "counter", max_states=2)
    assert not report.complete and report.outcomes == [] and report.findings == []
    assert report.unknown == ["mutation"]


def test_mutants_run_only_with_full():
    assert "mutate" not in parts.kinds()
    assert "mutate" in parts.kinds(full=True)


def test_the_mutate_part(project):
    path = project.flow("parcels", parcels())
    result = run_part(PartContext(project.root, PartSpec("mutate", "parcels"), path, project.root / "cache"))
    assert result.kind == "mutate" and result.complete
    assert result.reads == [".flowguard/flow/parcels.py"]
    assert result.info["counts"]["caught"] >= 2 and result.info["counts"]["survived"] >= 3
    assert {f["kind"] for f in result.findings} == {"MUTANT SURVIVES"}
    broken = project.flow("broken", "from flowguard.flow import Model\nm = Model('x')\n")
    result = run_part(PartContext(project.root, PartSpec("mutate", "broken"), broken, project.root / "cache"))
    assert [f["kind"] for f in result.findings] == ["MODEL ERROR"]


_SEED_SCRIPT = """
import json, sys
from pathlib import Path
from flowguard.flow.model import load_model
from flowguard.flow.explore import Bounds
from flowguard.flow.mutate import run_mutants
root, path = Path(sys.argv[1]), Path(sys.argv[2])
report = run_mutants(load_model(path, root), Bounds())
print(json.dumps([report.outcomes, [[f.subject, f.id] for f in report.findings]]))
"""


def test_the_same_mutants_and_fingerprints_under_every_hash_seed(project):
    path = project.flow_from(DATA / "planted" / "tool_life.py")
    runs = []
    for seed in (0, 1, 2):
        env = {**os.environ, "PYTHONHASHSEED": str(seed), "PYTHONPATH": str(REPO)}
        res = subprocess.run([sys.executable, "-c", _SEED_SCRIPT, str(project.root), str(path)],
                             capture_output=True, text=True, env=env, timeout=300)
        assert res.returncode == 0, res.stderr
        runs.append(json.loads(res.stdout))
    assert runs[0] == runs[1] == runs[2] and runs[0][1]


def test_a_guard_whose_drop_removes_a_conflict_is_named_as_its_cause(project):
    """G5: dropping the sourced guard 'repairs only at main' (R10) removes the dead end. That
    is the guard's part in the conflict (attribution), never a survivor inviting to delete it."""
    report, _ = mutate(project, DATA / "planted" / "rental_naive.py")
    drop = outcome(report, "drop guard 'repairs only at main' (repaired, line 32)")
    assert drop["outcome"] == "cause" and drop["removes"] and drop["by"] == []
    assert not [f for f in report.findings if "repairs only at main" in f.text]
    [(cid, causes)] = report.causes.items()
    [r10] = [c for c in causes if c["requested"]]                     # the one guard with its own source=
    assert r10["what"] == "drop guard 'repairs only at main' (repaired, line 32)" and r10["sources"] == ["R10"]
    assert not [o for o in report.outcomes if o["outcome"] == "survived" and o.get("removes")]


def test_check_full_prints_the_cause_under_its_conflict(project):
    """G5 round 2: every guard whose drop removes the conflict is its cause, the requested one
    (own source=) first and one that carries its action's source after it, in the text and in
    --json (which also lists every other change that removes it); none is a survivor."""
    from checkrun import run_check
    project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    run = run_check(project.root, "--full")
    assert run.code == 1, run.out
    causes = [line for line in run.lines if line.startswith("  cause (check --full): ")]
    assert causes == [
        "  cause (check --full): without guard 'repairs only at main' (repaired, line 32; R10) this conflict "
        "does not occur",
        "  cause (check --full): without guard 'not on the shelf' (rent, line 13; the action's R4) this conflict "
        "does not occur",
        "  cause (check --full): without guard 'not out' (return_ok, line 19; the action's R4) this conflict "
        "does not occur",
        "  cause (check --full): without guard 'only shelf tools move' (transfer, line 38; the action's R6) this "
        "conflict does not occur"], run.out
    assert '  4 other changes of the model remove it too (check --full --json: "causes")' in run.lines
    assert not any("mutant survives: drop guard 'repairs only at main'" in line for line in run.lines)
    assert not any("mutant survives: drop guard 'only shelf tools move'" in line for line in run.lines)
    data = run_check(project.root, "--full", "--json").data
    [conflict] = data["conflicts"]
    whats = [c["what"] for c in conflict["causes"]]
    assert "drop guard 'repairs only at main' (repaired, line 32)" in whats
    assert "drop guard 'only shelf tools move' (transfer, line 38)" in whats
    assert all(c["cause"] or c["op"] not in ("drop guard", "widen guard") for c in conflict["causes"])
