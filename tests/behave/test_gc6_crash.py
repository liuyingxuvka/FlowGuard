"""Generated file calls and real refusal observations share the native runner."""

import json
import sys

import pytest

from flowguard.behave.checks import _output_multiset
from flowguard.behave.engine import prove
from flowguard.behave.project import replay
from flowguard.behave.report import render
from flowguard.behave.skeleton import derive

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")

CSV_PROGRAM = '''import csv

class Refusal(Exception): pass
FIELDS = {"code": str, "title": str, "count": int}
REQUIRED = ("code", "title")

def read_rows(path, fields, required):
    with open(path, newline="", encoding="utf-8") as stream:
        result = []
        for raw in csv.DictReader(stream):
            row = {key: (value or "").strip() for key, value in raw.items()}
            if any(not row.get(key) for key in required):
                raise Refusal("missing required value")
            result.append({key: fields[key](value) for key, value in row.items()})
        return result

class Program:
    def __init__(self): self._units = []
    def add_unit(self, code, title, count=0): self._units.append((code, title, count))
    def units(self): return [row[0] for row in self._units]
    def import_units(self, path):
        rows = read_rows(path, FIELDS, REQUIRED)
        for row in rows: self.add_unit(**row)
'''


def test_file_inputs_generated(tmp_path):
    (tmp_path / "program.py").write_text(CSV_PROGRAM)
    spec = derive(tmp_path)
    assert len(spec["file_schemas"]) == 1
    facts = replay(spec, [], operation="crashes")
    assert {row["kind"]: row["outcome"] for row in facts["inputs"]} == {
        "normal": "success", "extra cell": "crash", "missing cell": "refusal"}
    assert not facts["unknown"]
    candidate, = facts["candidates"]
    assert candidate["label"] == "CRASH"
    exception = candidate["violation"]["exception"]
    assert exception["type"] == "builtins:AttributeError"
    assert exception["source"]["path"] == "program.py"
    assert exception["source"]["line"] == CSV_PROGRAM[:CSV_PROGRAM.index('            row =')].count("\n") + 1
    proof = prove(tmp_path, candidate, persist=False)
    assert proof["matched"] and proof["state"] == "reproduced"
    shown = {**candidate, "id": proof["id"], "proof": proof}
    result = {"identity": proof["identity"], "runs": [], "errors": [], "coverage": {"hit_functions": [], "known_functions": 0, "ui": "not requested", "front_doors": []},
              "items": [shown], "facts_reused": 0, "missing_checks": ["GC7", "GC8", "GC9"]}
    assert "CRASH import_units(<file: extra cell>): AttributeError:" in render(result)
    assert json.loads(render(result, as_json=True))["items"][0]["violation"]["exception"]["source"] == exception["source"]


def test_refused_call_changes_nothing(tmp_path):
    path = tmp_path / "program.py"
    source = '''from pathlib import Path
class Refusal(Exception): pass
class Program:
    def __init__(self): self._hidden = 0
    def advance(self):
        MUTATION
        raise Refusal("blocked")
'''
    path.write_text(source.replace("MUTATION", "pass"))
    spec = derive(tmp_path)
    trace = replay(spec, [{"name": "advance"}])
    row, = trace["steps"]
    evidence = {"prefix": [], "outcomes": [], "start": {}, "row": row}
    clean = replay(spec, [], operation="crashes", options={"facts": {"failures": [evidence]}, "generate": False})
    assert row["before_key"] == row["after_key"] and not clean["candidates"]
    path.write_text(source.replace("MUTATION", 'self._hidden += 1; Path("state.txt").write_text("changed")'))
    spec = derive(tmp_path)
    row, = replay(spec, [{"name": "advance"}])["steps"]
    evidence["row"] = row
    changed = replay(spec, [], operation="crashes", options={"facts": {"failures": [evidence]}, "generate": False})
    candidate, = changed["candidates"]
    assert candidate["label"] == "REFUSED CHANGED STATE"
    assert row["before"]["graph"] != row["after"]["graph"] and row["before"]["files"] != row["after"]["files"]
    assert prove(tmp_path, candidate, persist=False)["matched"]


def test_identical_messages_in_one_step_count_twice(tmp_path):
    path = tmp_path / "program.py"
    source = '''class Program:
    def emit(self):
        for message in MESSAGES: print(message)
        raise ValueError("unexpected")
'''
    observed = []
    for messages in (["same", "same", "other"], ["other", "same", "same"], ["same", "other"]):
        path.write_text(source.replace("MESSAGES", repr(messages)))
        row, = replay(derive(tmp_path), [{"name": "emit"}])["steps"]
        assert row["outcome"] == "crash"  # Builtin ValueError is not an application refusal.
        observed.append(_output_multiset(row))
    assert observed[0] == observed[1] and observed[0] != observed[2]
    assert {row["value"]: row["count"] for row in observed[0]["stdout"]} == {"same": 2, "other": 1}
