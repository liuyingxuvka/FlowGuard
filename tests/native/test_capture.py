"""Native facts keep failed calls, while engine faults reach the caller."""

import hashlib
from pathlib import Path

import pytest

from flowguard.native import session as project
from flowguard.native.capture import iter_steps
from flowguard.map.common import normalize_newlines


PROGRAM = '''class Refusal(Exception):
    pass

class Program:
    def __init__(self):
        self.value = 0
    def normal(self, amount=1):
        self.value += amount
        print("accepted", amount)
        return self.value
    def refuse(self, reason="blocked"):
        print("refused", reason)
        raise Refusal(reason)
    def crash(self):
        self.value += 1
        print("before crash")
        raise ValueError("actual SUT crash")
    def opaque(self):
        self.hidden = object()
    def catch_engine(self):
        try:
            return self.normal()
        except BaseException:
            return "hidden engine failure"
    def handled(self):
        try:
            raise LookupError("primary failed")
        except LookupError:
            self.value += 3
            return "recovered"
'''


@pytest.fixture
def spec(tmp_path):
    (tmp_path / "program.py").write_text(PROGRAM, encoding="utf-8")
    handler_line = PROGRAM[:PROGRAM.index("            self.value += 3")].count("\n") + 1
    return {"root": str(tmp_path), "system": "program:Program", "classes": ["program:Program"],
            "refusal": ["program:Refusal"], "shipped": {}, "entities": {}, "entity_queries": {},
            "capture_shape": {"wire": 2, "queries": {}},
            "statements": [{"id": "fixture-handler", "path": "program.py", "function": "Program.handled",
                            "line": handler_line, "unambiguous": True}]}


def inject_child(monkeypatch, control, owner=project):
    """Inject a fault in the real isolated worker, not a mocked replay result."""
    original = owner.run_isolated_process

    def controlled(command, **kwargs):
        command = list(command)
        command[2] = control + "\n" + command[2]
        return original(command, **kwargs)

    monkeypatch.setattr(owner, "run_isolated_process", controlled)


def test_actual_success_refusal_and_crash_keep_inputs_and_observations(spec):
    calls = [{"name": "normal", "kwargs": {"amount": 2}},
             {"name": "refuse", "args": ["closed"]}, {"name": "crash"}]
    result = project.replay(spec, calls)
    actual = result["steps"]
    captured = list(iter_steps(result["rule_captures"]))
    by_name = {row["call"]["name"]: row for row in captured}
    assert set(by_name) == {"normal", "refuse", "crash"}
    for raw in actual:
        row = by_name[raw["call"]["name"]]
        assert row["call"] == raw["call"]
        assert row["outcome"] == raw["outcome"]
        assert row["snapshot_before"] == raw["before"]
        assert row["snapshot_after"] == raw["after"]
        assert row["value"] == raw["value"]
        assert row["exception"] == raw["exception"]
        assert row["stdout"] == raw["stdout"]
        assert row["stderr"] == raw["stderr"]
        assert row["unchanged"] == (raw["before_key"] == raw["after_key"])
    accepted, refused, crashed = actual
    assert accepted["outcome"] == "success" and accepted["value"]["root"] == 2
    assert accepted["stdout"] == "accepted 2\n"
    assert by_name["normal"]["args_graph"]["nodes"][0]["items"] == [["amount", 2]]
    assert refused["outcome"] == "refusal" and refused["before"] == refused["after"]
    assert refused["exception"]["type"] == "program:Refusal"
    assert refused["stdout"] == "refused closed\n"
    assert crashed["outcome"] == "crash" and crashed["before"] != crashed["after"]
    assert crashed["exception"]["type"] == "builtins:ValueError"
    expected_line = PROGRAM[:PROGRAM.index('        raise ValueError')].count("\n") + 1
    assert crashed["exception"]["source"] == {"path": "program.py", "line": expected_line,
                                               "function": "Program.crash"}
    assert result["rule_captures"]["native_evidence"] == {"version": 1, "status": "current", "missing_steps": []}


def test_old_capture_without_actual_call_evidence_remains_unknown(spec):
    from flowguard.native.capture import Ledger

    captured = project.replay(spec, [{"name": "normal"}])["rule_captures"]
    captured.pop("native_evidence")
    captured.pop("snapshots")
    for row in captured["steps"].values():
        row.pop("evidence_status")
    ledger = Ledger(spec)
    ledger.update(captured)
    assert ledger.dump()["native_evidence"]["status"] == "unknown"
    assert ledger.dump()["native_evidence"]["missing_steps"]


def test_old_empty_capture_never_invents_a_current_native_receipt():
    from flowguard.native.capture import Ledger

    ledger = Ledger({})
    ledger.update({"wire": 2, "prefixes": {"p": {"start": {}}},
                   "observations": {"o": {"state_key": "s", "observation": {}}},
                   "states": {"o": "p"}, "steps": {}, "complete": True, "missing": []})
    assert ledger.dump()["native_evidence"]["status"] == "unknown"


def test_unknown_snapshot_is_typed_and_never_an_empty_success(spec):
    with pytest.raises(project.UnsupportedWorld, match="opaque state") as failure:
        project.replay(spec, [{"name": "opaque"}])
    assert failure.value.evidence_status == "unknown"


def test_observer_fault_reaches_caller_as_engine_error(spec, monkeypatch):
    inject_child(monkeypatch, '''from flowguard.native import session as native
capture = native._ObservedState.capture
def broken_capture(self, frame):
    if frame.f_code.co_name == "normal":
        raise RuntimeError("injected observer fault")
    return capture(self, frame)
native._ObservedState.capture = broken_capture
''')
    with pytest.raises(RuntimeError, match="injected observer fault") as failure:
        project.replay(spec, [{"name": "normal"}])
    assert type(failure.value).__name__ == "NativeEngineError"
    assert failure.value.phase == "observer"




def test_sut_catch_all_cannot_hide_an_observer_fault(spec, monkeypatch):
    inject_child(monkeypatch, '''from flowguard.native import session as native
capture = native._ObservedState.capture
def broken_capture(self, frame):
    if frame.f_code.co_name == "normal":
        raise RuntimeError("observer fault caught inside SUT")
    return capture(self, frame)
native._ObservedState.capture = broken_capture
''')
    with pytest.raises(project.NativeEngineError, match="observer fault caught inside SUT") as failure:
        project.replay(spec, [{"name": "catch_engine"}])
    assert failure.value.phase == "observer"


def assert_ordered_handler_events(events):
    events = [event for event in events if event["path"] == "program.py"
              and event["function"] == "Program.handled"]
    exception = next(index for index, event in enumerate(events) if event["kind"] == "exception"
                     and event["exception"]["type"] == "builtins:LookupError")
    handler = next(index for index, event in enumerate(events) if event["kind"] == "statement"
                   and event["statement"] == "fixture-handler")
    returned = next(index for index, event in enumerate(events) if event["kind"] == "return")
    assert exception < handler < returned


def test_ordered_events_keep_caught_failure_then_handler_and_return(spec):
    result = project.replay(spec, [{"name": "handled"}])
    row, = result["steps"]
    assert row["outcome"] == "success" and row["value"]["root"] == "recovered"
    assert_ordered_handler_events(row["events"])


def test_native_observer_uses_the_same_trace_path_without_monitoring(spec, monkeypatch):
    inject_child(monkeypatch, '''import sys
class ForbiddenMonitoring:
    def __getattr__(self, name):
        raise AssertionError("native capture unexpectedly used sys.monitoring")
sys.monitoring = ForbiddenMonitoring()
''')
    result = project.replay(spec, [{"name": "normal"}])
    assert result["steps"][0]["outcome"] == "success"
    assert len(list(iter_steps(result["rule_captures"]))) == 1


def test_recordings_keep_each_pytest_outcome_and_normalized_test_identity(spec):
    root = Path(spec["root"])
    tests = root / "tests"
    tests.mkdir()
    source = tests / "test_program.py"
    source.write_bytes(b'''from program import Program\r\n\r\ndef test_pass():\r\n    assert Program().handled() == "recovered"\r\n\r\ndef test_fail():\r\n    assert Program().normal(2) == 3\r\n''')
    result = project.replay(spec, [], operation="record")
    assert result["pytest_exitcode"] == 1
    rows = {row["test"]: row for row in result["recordings"]}
    assert set(rows) == {"tests/test_program.py::test_pass", "tests/test_program.py::test_fail"}
    digest = hashlib.sha256(normalize_newlines(source.read_bytes())).hexdigest()
    for nodeid, row in rows.items():
        assert row["source"] == str(source.resolve()) and row["digest"] == digest
        assert row["stop"] is None
        expected = "passed" if nodeid.endswith("test_pass") else "failed"
        assert row["pytest_outcome"] == expected
        assert [(report["when"], report["outcome"]) for report in row["pytest_reports"]] == [
            ("setup", "passed"), ("call", expected), ("teardown", "passed")]
        assert row["events"][0]["outcome"] == "success"
        if expected == "passed":
            assert_ordered_handler_events(row["observer_events"])
        else:
            assert not any(event["function"] == "Program.handled" for event in row["observer_events"])


def test_input_evidence_distinguishes_current_stale_missing_and_unknown(tmp_path):
    from flowguard.native.inputs import file_stamp, footprint_evidence

    source = tmp_path / "input.txt"
    source.write_text("original", encoding="utf-8")
    footprint = {"reusable": True, "files": {str(source): file_stamp(source)}, "directories": {}}
    current = footprint_evidence(footprint)
    assert current.status == "current" and current.identity
    source.write_text("changed", encoding="utf-8")
    stale = footprint_evidence(footprint)
    assert stale.status == "stale" and stale.identity is None and stale.reason == str(source)
    source.unlink()
    missing = footprint_evidence(footprint)
    assert missing.status == "missing" and missing.identity is None and missing.reason == str(source)
    for unavailable in (None, {}, {"reusable": False}, {"reusable": True}):
        unknown = footprint_evidence(unavailable)
        assert unknown.status == "unknown" and unknown.identity is None


def test_unreadable_input_evidence_has_no_current_identity(tmp_path, monkeypatch):
    from flowguard.native import inputs

    source = tmp_path / "input.txt"
    source.write_text("original", encoding="utf-8")
    footprint = {"reusable": True, "files": {str(source): inputs.file_stamp(source)}, "directories": {}}

    def unreadable(path):
        raise PermissionError("injected denied native input read")

    monkeypatch.setattr(inputs, "file_stamp", unreadable)
    result = inputs.footprint_evidence(footprint)
    assert result.status == "unreadable" and result.identity is None
    assert "denied native input read" in result.reason


def test_argument_capture_fault_reaches_caller_as_engine_error(spec, monkeypatch):
    inject_child(monkeypatch, '''from flowguard.native import session as native
pack = native._Graph.pack
def broken_argument_pack(self, value):
    if type(value) is dict and set(value) == {"amount"}:
        raise TypeError("injected argument capture fault")
    return pack(self, value)
native._Graph.pack = broken_argument_pack
''')
    with pytest.raises(project.NativeEngineError, match="injected argument capture fault") as failure:
        project.replay(spec, [{"name": "normal", "kwargs": {"amount": 2}}])
    assert failure.value.phase == "execution"


def test_ui_constructor_refusal_is_an_actual_unchanged_call(spec):
    source = Path(spec["root"]) / "program.py"
    source.write_text(PROGRAM + '''
class Interface:
    def __init__(self, system):
        raise Refusal("no interface")
''', encoding="utf-8")
    spec = {**spec, "ui": "program:Interface", "classes": [*spec["classes"], "program:Interface"]}
    result = project.replay(spec, [{"construct": "ui", "receiver": "ui:0"}])
    row, = result["steps"]
    assert row["outcome"] == "refusal"
    assert row["exception"]["type"] == "program:Refusal"
    assert row["exception"]["message"] == "no interface"
    assert row["unchanged"] and row["before"] == row["after"]
    captured, = iter_steps(result["rule_captures"])
    assert captured["outcome"] == "refusal" and captured["exception"] == row["exception"]
    assert captured["snapshot_before"] == captured["snapshot_after"] == row["before"]


def test_recorder_snapshot_fault_escapes_pytest_as_capture_engine_error(spec, monkeypatch):
    tests = Path(spec["root"]) / "tests"
    tests.mkdir()
    (tests / "test_program.py").write_text(
        'from program import Program\n\ndef test_create():\n    assert Program().normal() == 1\n', encoding="utf-8")
    inject_child(monkeypatch, '''from flowguard.native import testrec
snapshot = testrec.snapshot
fault_injected = False
def broken_recording_snapshot(objects, *args, **kwargs):
    global fault_injected
    if objects and not fault_injected:
        fault_injected = True
        raise TypeError("injected recorder snapshot fault")
    return snapshot(objects, *args, **kwargs)
testrec.snapshot = broken_recording_snapshot
''')
    with pytest.raises(project.NativeEngineError, match="injected recorder snapshot fault") as failure:
        project.replay(spec, [], operation="record")
    assert failure.value.phase == "capture"


def test_recorder_outcome_fault_cannot_be_hidden_by_passing_test(spec, monkeypatch):
    tests = Path(spec["root"]) / "tests"
    tests.mkdir()
    (tests / "test_program.py").write_text('''from program import Program
def test_catch():
    program = Program()
    try:
        program.refuse()
    except BaseException:
        pass
''', encoding="utf-8")
    inject_child(monkeypatch, '''from flowguard.native import testrec
def broken_outcome(*args, **kwargs):
    raise TypeError("injected recorder outcome fault")
testrec._Recorder.outcome = broken_outcome
''')
    with pytest.raises(project.NativeEngineError, match="injected recorder outcome fault") as failure:
        project.replay(spec, [], operation="record")
    assert failure.value.phase == "capture"


def test_initial_sut_constructor_crash_is_unknown_with_actual_exception(spec):
    source = Path(spec["root"]) / "program.py"
    source.write_text(PROGRAM.replace("        self.value = 0", '        raise ValueError("actual constructor crash")'))
    with pytest.raises(project.UnsupportedWorld, match="actual constructor crash") as failure:
        project.replay(spec, [])
    assert failure.value.evidence_status == "unknown"
    assert failure.value.outcome == "crash"
    assert failure.value.exception["type"] == "builtins:ValueError"


def test_observer_only_recording_retains_test_evidence_without_object_prefix(tmp_path):
    (tmp_path / "library.py").write_text('''def handled():
    try:
        raise ValueError("primary failure")
    except ValueError:
        return "fallback"
''')
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_library.py").write_text('''from library import handled
def test_chosen():
    assert handled() == "fallback"
    assert handled() == "fallback"
def test_omitted():
    assert False, "the selected-target recording must not run this test"
''')
    observed_spec = {"root": str(tmp_path), "classes": []}
    result = project.replay(observed_spec, [], operation="record",
                            options={"test_nodeids": ["tests/test_library.py::test_chosen"]})
    assert result["pytest_exitcode"] == 0
    row, = result["recordings"]
    assert row["test"] == "tests/test_library.py::test_chosen"
    assert row["pytest_outcome"] == "passed"
    assert row["stop"]["kind"] == "no-system" and row["stop"]["evidence_status"] == "unknown"
    events = [event for event in row["observer_events"] if event["path"] == "library.py"]
    assert any(event["kind"] == "exception" and event["exception"]["type"] == "builtins:ValueError" for event in events)
    assert events[-1]["kind"] == "return"
    failures = [event for event in events if event["kind"] == "exception"]
    assert len(failures) == 2 and len({event["call_token"] for event in failures}) == 2
    for failure in failures:
        own = [event for event in events if event["call_token"] == failure["call_token"]]
        assert own[-1]["kind"] == "return"
        assert own[-1]["return_status"] == "returned"
        assert own[-1]["result"] == {"status": "current", "value": "fallback"}


def test_native_events_separate_repeated_public_invocations(spec):
    result = project.replay(spec, [{"name": "handled"}, {"name": "handled"}])
    token_sets = [{event["call_token"] for event in row["events"] if event["function"] == "Program.handled"}
                  for row in result["steps"]]
    assert all(len(tokens) == 1 for tokens in token_sets)
    assert token_sets[0].isdisjoint(token_sets[1])


def test_return_events_keep_scalar_results_and_parent_invocation(spec):
    source = Path(spec["root"]) / "program.py"
    source.write_text(PROGRAM + '''
    def primary(self, value): return value
    def alternate(self): return 9
    def route(self, value): return self.primary(value) or self.alternate()
    def complex_result(self): return [1, 2]
''')
    result = project.replay(spec, [{"name": "route", "args": [False]},
                                   {"name": "route", "args": [None]}, {"name": "complex_result"}])
    for row, expected in zip(result["steps"], [False, None]):
        returns = {event["function"]: event for event in row["events"] if event["kind"] == "return"}
        primary, alternate, route = (returns["Program." + name] for name in ("primary", "alternate", "route"))
        assert primary["return_status"] == "returned" and primary["result"] == {"status": "current", "value": expected}
        assert primary["parent_call_token"] == alternate["parent_call_token"] == route["call_token"]
        assert alternate["result"] == route["result"] == {"status": "current", "value": 9}
    complex_return = next(event for event in result["steps"][-1]["events"] if event["kind"] == "return")
    assert complex_return["result"]["status"] == "unknown"


def test_exceptional_return_never_fabricates_a_returned_none(spec):
    result = project.replay(spec, [{"name": "crash"}])
    returned = next(event for event in result["steps"][0]["events"] if event["kind"] == "return")
    assert returned["return_status"] == "raised"
    assert returned["result"]["status"] == "unknown"


def test_return_fact_fault_reaches_caller_as_observer_error(spec, monkeypatch):
    inject_child(monkeypatch, '''from flowguard.native import session as native
def broken_returned(*args, **kwargs):
    raise TypeError("injected return fact fault")
native._ObservedState.returned = broken_returned
''')
    with pytest.raises(project.NativeEngineError, match="injected return fact fault") as failure:
        project.replay(spec, [{"name": "normal"}])
    assert failure.value.phase == "observer"


def test_actual_public_inventory_keeps_owner_and_never_invokes_property(spec):
    source = Path(spec["root"]) / "program.py"
    source.write_text(PROGRAM.replace('class Program:', '''class Base:
    def inherited(self): return 1

class Program(Base):''') + '''
    @property
    def visible(self): raise AssertionError("inventory invoked property")
    @staticmethod
    def static_call(): return 1
    @classmethod
    def class_call(cls): return 2
''')
    spec["classes"].append("program:Base")
    result = project.replay(spec, [])
    inventory = {row["name"]: row for row in result["inventory"]["system"]}
    assert inventory["normal"] == {"name": "normal", "owner": "program:Program", "kind": "method"}
    assert inventory["inherited"]["owner"] == "program:Base"
    assert inventory["visible"]["kind"] == "property"
    assert inventory["static_call"]["kind"] == "static"
    assert inventory["class_call"]["kind"] == "class"
    assert result["inventory_limits"] == {"system": []}
    sources = result["inventory_sources"]["system"]
    assert sources[0] == {"owner": "program:Program", "symbol": "Program", "path": str(source)}
    assert sources[1] == {"owner": "program:Base", "symbol": "Base", "path": str(source)}


def test_inventory_source_is_the_declaring_binding_not_a_decorator_wrapper(spec):
    root = Path(spec["root"])
    (root / "decorators.py").write_text('''def decorate(fn):
    def wrapper(self): raise AssertionError("inventory called decorator wrapper")
    return wrapper
''')
    source = root / "program.py"
    source.write_text('''from decorators import decorate
class Refusal(Exception): pass
class Program:
    @decorate
    def repair(self): pass
''')
    result = project.replay(spec, [])
    assert result["inventory"]["system"] == [{"name": "repair", "owner": "program:Program", "kind": "method"}]
    assert result["inventory_sources"]["system"][0] == {
        "owner": "program:Program", "symbol": "Program", "path": str(source)}


def test_inventory_names_actual_dynamic_lookup_limits(spec):
    source = Path(spec["root"]) / "program.py"
    source.write_text(PROGRAM + '''
    def __getattr__(self, name):
        if name == "dynamic_operation": return lambda: 1
        raise AttributeError(name)
    def __getattribute__(self, name):
        return object.__getattribute__(self, name)
''')
    result = project.replay(spec, [])
    assert result["inventory_limits"] == {"system": ["dynamic attribute lookup (__getattr__)",
                                                     "custom attribute lookup (__getattribute__)"]}
