"""FG-811 planted known-bad models: each is caught, every time.

Four planted defects (an extra guard that makes a dead end, a removed transition that makes
an action unreachable, a declared end made unreachable, an order that breaks a rule), each
checked in fresh processes under PYTHONHASHSEED 0, 1 and 2: the same conflict with the same
fingerprint every time. The good version of each is clean of conflicts.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from flowguard.flow.checks import CONFLICT, check_model
from flowguard.flow.model import load_model

from conftest import DATA, findings_under_seeds

PLANTED = DATA / "planted"
HOWTO = Path(__file__).parents[2] / "flowguard" / "flow" / "HOWTO.md"


def howto_model():
    text = HOWTO.read_text(encoding="utf-8")
    blocks = re.findall(r"```python\n(.*?)```", text, re.S)
    return next(b for b in blocks if "MODEL = m" in b)


def conflicts(project, name):
    report = check_model(load_model(project.root / ".flowguard" / "flow" / f"{name}.py", project.root))
    return [f for f in report.findings if f.cls == CONFLICT], report


CASES = [
    # (planted file, good file, kind, subject)
    ("rental_naive", "rental_fixed", "STUCK", "branch[*] = 'library'"),
    ("rental_no_transit", "rental_fixed", "NEVER REACHED", "action receive"),
    ("tool_life_end_unreachable", "tool_life", "NEVER REACHED", "value cond[*] = 'retired'"),
]


@pytest.mark.parametrize("bad, good, kind, subject", CASES, ids=[c[0] for c in CASES])
def test_planted_model_is_caught_every_time(project, bad, good, kind, subject):
    path = project.flow_from(PLANTED / f"{bad}.py")
    runs = findings_under_seeds(project.root, path)
    for run in runs:
        hits = [f for f in run if f[0] == CONFLICT and f[1] == kind and f[2] == subject]
        assert len(hits) == 1, run
    assert runs[0] == runs[1] == runs[2]                 # same findings, same fingerprints
    project.flow_from(PLANTED / f"{good}.py")
    found, _ = conflicts(project, good)
    assert found == []


def test_dead_end_has_the_prototype_path(project):
    project.flow_from(PLANTED / "rental_naive.py")
    found, _ = conflicts(project, "rental_naive")
    stuck = next(f for f in found if f.kind == "STUCK")
    assert stuck.path == ("transfer(t='T1')", "rent(t='T1')", "return_damaged(t='T1')")
    assert stuck.state == "cond[T1]='repair', branch[T1]='library'"
    assert "cond[*] = 'repair'" in stuck.detail["consequences"]       # as the prototype groups it
    assert "R10" in stuck.sources and "R6" in stuck.sources


def test_unreachable_end_is_explained_as_a_declared_end(project):
    project.flow_from(PLANTED / "tool_life_end_unreachable.py")
    found, _ = conflicts(project, "tool_life_end_unreachable")
    end = next(f for f in found if f.subject == "value cond[*] = 'retired'")
    assert end.detail["why"] == "declared end"
    assert "R12" in end.sources
    assert end.detail["explained"] == []                 # no setting reaches it


def test_an_order_breaks_a_rule(project):
    good = howto_model()
    bad = "\n".join(line for line in good.splitlines() if '"the locker is full"' not in line) + "\n"
    assert bad != good
    project.flow("parcels", good)
    found, _ = conflicts(project, "parcels")
    assert found == []
    path = project.flow("parcels_full", bad)
    runs = findings_under_seeds(project.root, path)
    for run in runs:
        assert [f[1:3] for f in run if f[0] == CONFLICT] == [["BROKEN", "always 'one parcel at a time in the locker'"]]
    assert runs[0] == runs[1] == runs[2]
    found, report = conflicts(project, "parcels_full")
    assert found[0].path == ("deliver(p='P1')", "deliver(p='P2')")
