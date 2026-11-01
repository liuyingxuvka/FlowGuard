"""Rule judgments use complete admitted native ledgers across public origins."""

import sys

import pytest

from flowguard.behave import engine
from flowguard.behave.project import replay
from flowguard.behave.rules import collect_rules, judge
from flowguard.map.requests import store_request

from .test_gc4_saved_files import history

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot rules need Python 3.12")


def test_actual_ts2_and_setting_baseline_ledgers_have_no_blanket_gap():
    from flowguard.behave.capture import Ledger
    spec = {"entities": {}, "queries": [], "actions": []}
    ledger = Ledger(spec).dump()
    native = {"rule_captures": ledger, "states": [], "events": []}
    captures = engine._rule_captures(spec, [{"facts": native}],
        {"prefixes": [{"prefix": []}], "rule_captures": ledger}, None,
        {"files": []}, {"profiles": [{"setting": "limit"}], "rule_captures": ledger})
    assert captures["complete"], captures["missing"]
    assert not captures["missing"]


PROGRAM = '''class Program:
    def __init__(self): self._units = {}
    def add_unit(self, unit_id, name): self._units[unit_id] = 0
    def units(self): return list(self._units)
    def tick(self, unit_id): self._units[unit_id] = 4
    def count(self, unit_id): return self._units[unit_id]
'''


def norm(root, body, quote="The count must be at most 3."):
    path = root / "tests/rules/limits/test_limit.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('from flowguard.behave.rules import rule, owner\n\n'
                    f'@rule(owner("R1", {quote!r}))\ndef test_limit(step):\n' + body)
    store_request(root, (quote + "\n").encode(), identifier="R1")
    return path


def run(root):
    return engine.audit(root, worlds=["small"], seeds=[0], steps=1,
                        node_cap=4, alphabet_cap=8, use_cache=False)


def fresh_rule(root, facts, action):
    plan = collect_rules(root)
    judged = judge(plan, facts["rule_captures"])
    row = next(row for row in judged["candidates"] if row["action"] == action)
    candidate = engine._rule_candidate(row, engine.content_identity(engine._execution_spec(root)), facts["footprint"])
    candidate["judgment_identity"] = plan["identity"]
    proof = engine.prove(root, candidate, persist=False)
    assert proof["matched"], proof
    assert proof["proof"]["execution"]["child_pid"] != facts["execution"]["child_pid"]
    return row, proof


def test_real_ts2_admission_rejects_independent_norm_when_ordinary_test_agrees_with_wrong_code(tmp_path):
    (tmp_path / "program.py").write_text(PROGRAM)
    norm(tmp_path, '    if step.name == "tick" and step.args["unit_id"] == "U7":\n'
                   '        assert step.after.count("U7") <= 3\n')
    (tmp_path / "tests/test_same_wrong_answer.py").write_text('''from program import Program
def test_same_wrong_answer():
    subject = Program()
    subject.add_unit("U7", "seven")
    subject.tick("U7")
    assert subject.count("U7") == 4
''')
    result = run(tmp_path)
    assert not result["errors"], result["errors"]
    item, = [row for row in result["items"] if row["label"] == "BROKEN"]
    assert item["action"] == "tick" and item["proof"]["matched"]
    assert any(call.get("args") == ["U7"] for call in item["prefix"])
    assert result["rules"]["capture_scope"]["complete"], result["rules"]


def test_actual_directed_branch_is_judged_even_when_primary_walk_did_not_take_it(tmp_path):
    (tmp_path / "program.py").write_text(PROGRAM.replace("= 4", "= 3")
        + '\n    def spare(self, unit_id): self._units[unit_id] = 4\n')
    norm(tmp_path, '    if step.name == "spare":\n'
                   '        for unit in step.after.units():\n'
                   '            assert step.after.count(unit) <= 3\n')
    result = run(tmp_path)
    assert not result["errors"], result["errors"]
    assert result["runs"][0]["facts"]["events"][0]["call"]["name"] == "tick"
    item, = [row for row in result["items"] if row["label"] == "BROKEN"]
    assert item["action"] == "spare" and item["proof"]["matched"]
    assert result["rules"]["capture_scope"]["complete"], result["rules"]


def test_gc2_ui_trial_uses_same_capture_and_fresh_rule_producer(tmp_path):
    view = '''
class View:
    def __init__(self, program):
        self.program = program
        self.screen = "home"
    def options(self): return ["raise"]
    def choose(self, option, **inputs):
        if option == "raise": self.program.tick("U1")
'''
    (tmp_path / "program.py").write_text(PROGRAM + view)
    norm(tmp_path, '    if step.name == "choose":\n'
                   '        assert step.after.count("U1") <= 3\n')
    spec = engine._execution_spec(tmp_path)
    construction = {"construct": "ui", "receiver": "ui:0", "args": []}
    facts = replay(spec, [], {"world": "small"}, operation="agreement",
        options={"facts": {}, "states": [{"start": {"world": "small"},
                  "prefix": [construction], "outcomes": ["success"]}]})
    assert facts["compared"]
    row, _ = fresh_rule(tmp_path, facts, "choose")
    assert row["prefix"] == [construction, {"receiver": "ui:0", "name": "choose", "args": ["raise"], "kwargs": {}}]


def test_loaded_public_file_origin_is_judged_and_freshly_replayed(history):
    collected = engine.collect_saves(history, steps=1, node_cap=2, alphabet_cap=16)
    saved = next(row for row in collected["saves"] if row["file"]["name"] == "fixtures/committed.json")
    norm(history, '    if step.name == "load":\n'
                  '        for unit in step.after.units():\n'
                  '            assert step.after.status(unit) != "active"\n',
                  quote="Loaded units must not be active.")
    spec = engine._execution_spec(history)
    facts = replay(spec, [], operation="saved", options={"saves": [saved], "seed": 0,
                   "steps": 1, "node_cap": 2, "alphabet_cap": 16})
    assert facts["files"][0]["status"] == "loaded"
    row, _ = fresh_rule(history, facts, "load")
    assert row["start"]["files"] == {saved["file"]["name"]: saved["file"]["bytes"]}


def test_missing_producer_and_ordinary_clean_iteration_do_not_expand_prefixes(tmp_path, monkeypatch):
    from flowguard.behave import rules
    from flowguard.behave.capture import Ledger
    spec = {"actions": ["tick"], "entities": {"unit": {"list": "units"}}, "queries": ["count"]}
    observed = {"values": [{"query": "count", "args": ["U1"], "value": 3}],
                "unknown": [], "identifiers": {"unit": ["U1"]}}
    ledger = Ledger(spec)
    ledger.step({}, [{"name": "tick", "args": ["U1"]}], ["success"],
        {"before_key": "before", "after_key": "after", "outcome": "success", "resolved_args": {"unit_id": "U1"}}, observed, observed)
    captures = ledger.dump()
    norm(tmp_path, '    assert step.after.count("U1") <= 3\n')
    monkeypatch.setattr(rules, "failure_context", lambda row: pytest.fail("a clean evaluation expanded its prefix"))
    assert judge(collect_rules(tmp_path), captures)["rules"][0]["status"] == "clean"
    incomplete = engine._rule_captures(spec, [{"facts": {"rule_captures": captures, "reach": {}}}],
                                      {}, None, {"files": []}, {})
    assert not incomplete["complete"] and any("reach" in reason for reason in incomplete["missing"])
    assert judge(collect_rules(tmp_path), incomplete)["rules"][0]["status"] == "not-judged"


def test_public_why_forwards_native_not_applicable_without_changing_proof_classification(tmp_path):
    from flowguard.behave.why import why
    from .test_gc2_offered import PROGRAM as OFFER_PROGRAM, VIEW
    source = OFFER_PROGRAM.replace("PREDICTOR", "why_not_advance").replace("ANSWER", '"blocked"')
    source = source.replace("ACTION", 'raise Refusal("blocked")')
    handled = VIEW.replace("OFFER_GUARD", "pass").replace(
        '            CHOOSE_GUARD\n            self.program.advance(self.unit_id)',
        '            try:\n                self.program.advance(self.unit_id)\n'
        '            except Refusal:\n                self.screen = "blocked"')
    path = tmp_path / "program.py"
    path.write_text((source + handled).replace('self.screen = "blocked"', 'raise'))
    spec = engine._execution_spec(tmp_path)
    construction = {"construct": "ui", "receiver": "ui:0", "args": ["U1"]}
    facts = replay(spec, [], {"world": "small"}, operation="agreement",
        options={"facts": {}, "states": [{"start": {"world": "small"}, "prefix": [construction]}]})
    candidate = next(row for row in facts["candidates"] if row["comparison"].get("other_predictor"))
    candidate.update(identity=engine.content_identity(spec), footprint=facts["footprint"])
    original = engine.prove(tmp_path, candidate)
    assert original["matched"]
    path.write_text(source + handled)
    current = why(tmp_path, original["id"])
    assert current["state"] == "no-longer-reproduces" and not current["matched"]
    assert current["not_applicable"] and "handles" in current["reason"]


def test_native_typed_mapping_default_arguments_and_empty_list_are_faithful(tmp_path):
    from flowguard.behave.capture import iter_steps
    from flowguard.behave.rules import _Step, _Unavailable
    source = '''class Program:
    def __init__(self): self._units = {}
    def add_unit(self, unit_id, name): self._units[unit_id] = {1: 7}
    def units(self): return list(self._units)
    def tick(self, unit_id, payload={"nested": {1: 7}}): self._units[unit_id] = dict(payload["nested"])
    def mapping(self, unit_id): return self._units[unit_id]
    def queue(self, unit_id): return []
'''
    program = tmp_path / "program.py"
    program.write_text(source)
    quote = "Mappings must retain integer key 1 with value 7, and queues are empty lists."
    rule_path = norm(tmp_path, '    if step.name == "tick":\n'
        '        assert step.args["payload"]["nested"][1] == 7\n'
        '        assert step.after.units() == ["U1"]\n'
        '        assert 1 in step.after.mapping("U1")\n'
        '        assert step.after.mapping("U1")[1] == 7\n'
        '        assert step.after.queue("U1") == []\n', quote=quote)
    rule_path.write_text(rule_path.read_text() + f'\n@rule(owner("R1", {quote!r}))\n'
        'def test_state(state):\n'
        '    assert state.units() == ["U1"]\n'
        '    for unit in state.units():\n'
        '        assert 1 in state.mapping(unit)\n'
        '        assert state.mapping(unit)[1] == 7\n'
        '        assert state.queue(unit) == []\n')
    call = {"name": "tick", "args": ["U1"]}
    spec = engine._execution_spec(tmp_path)
    facts = replay(spec, [call], {"world": "small"})
    judged = judge(collect_rules(tmp_path), facts["rule_captures"])
    assert all(row["status"] == "clean" for row in judged["rules"]), judged
    assert not judged["candidates"]
    view = _Step(next(row for row in iter_steps(facts["rule_captures"]) if row["call"] == call), spec)
    assert isinstance(view.args["payload"]["nested"], dict)
    assert isinstance(view.after.queue("U1"), list)
    with pytest.raises(_Unavailable, match="read-only"):
        view.after.mapping("U1")[1] = 9
    with pytest.raises(_Unavailable, match="read-only"):
        view.after.queue("U1").append(9)
    for broken in ('{"1": 7}', '{1: 8}'):
        program.write_text(source.replace('dict(payload["nested"])', broken))
        current_spec = engine._execution_spec(tmp_path)
        current = replay(current_spec, [call], {"world": "small"})
        plan = collect_rules(tmp_path)
        failures = judge(plan, current["rule_captures"])
        row = next(row for row in failures["candidates"] if row["fixture"] == "step")
        candidate = engine._rule_candidate(row, engine.content_identity(current_spec), current["footprint"])
        candidate["judgment_identity"] = plan["identity"]
        proof = engine.prove(tmp_path, candidate, persist=False)
        assert proof["matched"] and proof["state"] == "reproduced", proof
