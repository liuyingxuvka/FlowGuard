"""FG-811 golden: the new engine reproduces the prototype's conclusions on the E7 models.

Each golden file (`data/golden/out/<session>__<file>.out`) is the prototype's output for
`data/golden/models/<session>/<file>.py`. Compared per machine: state count and
completeness, steps, STUCK roots and their consequences (key, value, kind, state count),
progress lost, NEVER REACHED items with their explanation lists, BROKEN rules,
CONTRADICTION options, the shortest path length of every finding, errors, the rules that
hold, the declared/derived ends. Only the class may differ (M3): unreached field values
without a source are model warnings, so a model whose only findings were such values
is now clean. One finding is new (G8, s1aplan/undeclared_end.md): a derived end the
prototype listed under ENDS ("if that is not the design, it is a dead end") is also a
STUCK conflict when no m.terminal declares it; it is compared separately. And where a
counter value and another value are stuck in as many states, the new engine names the group
by the other value (G2: a report is named by the object's state, the counter is folded under
it), while the prototype took the first by key: groups are compared as sets of labels, and the
root may differ from the prototype's only that way.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from flowguard._next.checks import CONFLICT, WARNING, check_model
from flowguard._next.explore import Bounds
from flowguard._next.model import Loaded

from golden_machine import load_machines

DATA = Path(__file__).parent / "data" / "golden"
OUTS = sorted((DATA / "out").glob("*.out"))


def parse_out(text):
    """The prototype report, per machine."""
    blocks, cur, section = [], None, None
    lines = text.splitlines()
    exit_code = int(lines[-1].split("=")[1])
    in_under = False
    for line in lines[:-1]:
        if line.startswith("machine: "):
            cur = {"name": line[9:], "stuck": [], "never": [], "reach": [], "broken": [], "contra": [],
                   "holds": [], "ends": [], "errors": 0, "world_can_end": False}
            blocks.append(cur)
            section = None
            continue
        if not line.strip() or cur is None:
            continue
        m = re.match(r"explored: ([\d,]+) states, ([\d,]+) steps, .*, (complete|CAPPED)", line)
        if m:
            cur["states"] = int(m.group(1).replace(",", ""))
            cur["steps"] = int(m.group(2).replace(",", ""))
            cur["complete"] = m.group(3) == "complete"
            continue
        head = re.match(r"(STUCK|NEVER REACHED|BROKEN|CONTRADICTION|ERROR|RULES|ENDS)\b", line)
        if head:
            section = head.group(1)
            if section == "ERROR":
                cur["errors"] = int(re.match(r"ERROR \((\d+)\)", line).group(1))
            continue
        if line.startswith("verdict:") or line.startswith("settings"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()
        if section == "STUCK":
            if indent <= 4:
                in_under = body.startswith("stuck only in states")
            if indent == 2:
                cur["stuck"].append({"label": body, "path": None, "under": []})
            elif indent == 4 and body.startswith("path ("):
                cur["stuck"][-1]["path"] = int(re.match(r"path \((\d+) step", body).group(1))
            elif indent == 6 and in_under:
                cur["stuck"][-1]["under"].append(body)
        elif section == "NEVER REACHED" and indent == 2:
            if body.startswith("(explanations:"):
                continue
            m = re.match(r"(.*?)  \((reached only with (.*)|no one-setting change reaches it either)\)$", body)
            if body.startswith("reach "):
                cur["reach"].append(body)
            elif m:
                cur["never"].append((m.group(1), m.group(3).split(", ") if m.group(3) else []))
            else:
                cur["never"].append((body, None))
        elif section == "BROKEN":
            if indent == 2:
                cur["broken"].append([body, None])
            elif indent == 4 and body.startswith("path ("):
                cur["broken"][-1][1] = int(re.match(r"path \((\d+) step", body).group(1))
        elif section == "CONTRADICTION":
            if indent == 2:
                cur["contra"].append([body, None])
            elif indent == 4 and body.startswith("path ("):
                cur["contra"][-1][1] = int(re.match(r"path \((\d+) step", body).group(1))
        elif section == "RULES" and indent == 2:
            cur["holds"].append(body)
        elif section == "ENDS" and indent == 2:
            if body.startswith("note:"):
                cur["world_can_end"] = True
                section = "ENDS-NOTE"
            else:
                cur["ends"].append(body)
    return blocks, exit_code


def render(report):
    """The new report in the prototype's terms (classes aside)."""
    g = report.graph
    out = {"states": len(g.states), "steps": g.steps, "complete": g.complete, "stuck": [], "never": [],
           "reach": [], "broken": [], "contra": [], "holds": [], "ends": [], "errors": 0, "classes": {},
           "undeclared": [], "world_can_end": report.reach["world_can_end"]}
    for f in report.raw:
        d = f.detail
        if f.kind == "STUCK" and d["stuck"] == "end":
            out["undeclared"].append(d["label"].split(":", 1)[0])
        elif f.kind == "STUCK":
            out["stuck"].append({"label": d["label"], "path": len(f.path), "under": d["consequence_labels"]})
        elif f.kind == "NEVER REACHED":
            if d["item"] == "reach":
                out["reach"].append(d["label"])
            else:
                out["never"].append((d["label"], d["explained"]))
            out["classes"][d["label"]] = f.cls
        elif f.kind == "BROKEN":
            out["broken"].append([f"{d['rule']} {d['name']!r}", len(f.path)])
        elif f.kind == "CONTRADICTION":
            out["contra"].append([f"option {d['option']!r} is offered, but {d['call']} refuses: {d['reason']!r}",
                                  len(f.path)])
        elif f.kind == "MODEL ERROR":
            out["errors"] += 1
    n = len(g.states)
    for label, status in report.holds:
        word = {"holds": f"HOLDS (complete, {n:,} states)", "reached": "reached"}[status]
        if label.startswith("progress "):
            word = "HOLDS (complete)"
        out["holds"].append(f"{label}: {word}")
    for name, vs, declared in report.reach["ends"]:
        out["ends"].append(f"{name} = {', '.join(vs)}" + (
            "  (declared)" if declared else
            "  (never left by any state; if that is not the design, it is a dead end)"))
    return out


def _group(s):
    return frozenset([s["label"]] + s["under"]), s["path"]


def _counter(label):
    return re.match(r"\S+ = -?\d+: ", label) is not None


def _states(label):
    return re.search(r"\((\d[\d,]*) states?, complete search\)", label).group(1)


CASES = [pytest.param(p, id=p.stem) for p in OUTS]


@pytest.fixture(autouse=True)
def _no_mv(monkeypatch):
    monkeypatch.delenv("MV", raising=False)          # sonnet1_R9 reads it


@pytest.mark.parametrize("out_path", CASES)
def test_golden(out_path):
    session, _, file = out_path.stem.partition("__")
    model_path = DATA / "models" / session / f"{file}.py"
    blocks, exit_code = parse_out(out_path.read_text(encoding="utf-8"))
    models = load_machines(model_path)
    assert len(models) == len(blocks)
    any_conflict = False
    for model, want in zip(models, blocks):
        assert model.name == want["name"]
        report = check_model(Loaded(model, ()), Bounds())
        got = render(report)
        for key in ("states", "steps", "complete", "errors"):
            assert got[key] == want[key], (model.name, key)
        assert [_group(s) for s in got["stuck"]] == [_group(s) for s in want["stuck"]], model.name
        for g_, w_ in zip(got["stuck"], want["stuck"]):
            if g_["label"] != w_["label"]:          # only a counter root gives way to a value stuck as long
                assert _counter(w_["label"]) and not _counter(g_["label"]), (model.name, g_["label"])
                assert _states(g_["label"]) == _states(w_["label"]), model.name
        assert got["never"] == want["never"], model.name
        assert got["reach"] == want["reach"], model.name
        assert got["broken"] == want["broken"], model.name
        assert got["contra"] == want["contra"], model.name
        assert got["holds"] == want["holds"], model.name
        assert got["ends"] == want["ends"], model.name
        assert got["world_can_end"] == want["world_can_end"], model.name
        # G8: every derived (undeclared) end of the prototype is now also a dead end
        derived = sorted(e.split("  (", 1)[0] for e in want["ends"] if not e.endswith("(declared)"))
        assert sorted({u.split("[", 1)[0] + " = " + u.split(" = ", 1)[1] for u in got["undeclared"]}) == derived
        # M3 classes: values without a source are warnings, everything else a conflict
        for label, cls in got["classes"].items():
            assert cls == (WARNING if label.startswith("value ") else CONFLICT), label
        any_conflict |= any(f.cls == CONFLICT for f in report.findings)
    only_values = all(not b["stuck"] and not b["broken"] and not b["contra"] and not b["reach"]
                      and all(label.startswith("value ") for label, _ in b["never"]) for b in blocks)
    expected = 1 if exit_code == 1 and not only_values else 0
    assert (1 if any_conflict else 0) == expected
