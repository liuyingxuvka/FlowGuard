"""Structural hazards are computed information alongside genuine finite model proofs."""

import json
import sys
from dataclasses import asdict, dataclass

from flowguard import FunctionResult, Workflow
from flowguard.hazards import infer_topology_digest
from flowguard.map import cli, proof


@dataclass(frozen=True)
class Event:
    kind: str = "submit"


@dataclass(frozen=True)
class State:
    status: str = "idle"
    saved_record: str = ""


class SaveRecord:
    name = "SaveRecord"
    reads = ("status",)
    writes = ("saved_record", "status")
    side_effects = ("database_write",)

    def apply(self, input_obj, state):
        return (FunctionResult(input_obj, State("done", "saved"), label="saved"),)


def test_digest_derives_topology_landmarks_from_model_shape_and_usage():
    class LegacyRemoteSaveRecord(SaveRecord):
        name = "LegacyRemoteSaveRecord"

    digest = infer_topology_digest(
        workflow=Workflow((LegacyRemoteSaveRecord(),), name="save"),
        initial_states=(State(),), external_inputs=(Event(),))
    landmark_types = {landmark.landmark_type for landmark in digest.landmarks}
    assert "side_effect_repeat" in landmark_types
    assert "legacy_or_compatibility_path" in landmark_types
    assert "external_confirmation_boundary" in landmark_types


def test_single_state_writer_with_effect_is_not_shared():
    digest = infer_topology_digest(workflow=Workflow((SaveRecord(),), name="save"),
                                   initial_states=(State(),), external_inputs=())
    assert [item for item in digest.landmarks if item.landmark_type == "shared_writer"] == []


def test_two_distinct_state_writers_are_still_shared():
    class SecondSave(SaveRecord):
        name = "SecondSave"
        side_effects = ()

    digest = infer_topology_digest(workflow=Workflow((SaveRecord(), SecondSave()), name="two saves"),
                                   initial_states=(State(),), external_inputs=())
    shared = next(item for item in digest.landmarks
                  if item.landmark_id == "landmark:shared-writer:saved_record")
    assert shared.anchor_ids == ("edge:0:SaveRecord", "edge:1:SecondSave")


def test_topology_review_reads_a_choice_workflow():
    workflow = Workflow((SaveRecord(), SaveRecord()), name="operations", mode="choice")
    digest = infer_topology_digest(workflow=workflow, initial_states=(State(),), external_inputs=())
    edges = [edge for edge in digest.edges if edge.edge_kind == "workflow_edge"]
    assert len(edges) == 2 and {edge.source_id for edge in edges} == {"workflow:root"}
    assert {edge.target_id for edge in edges} == {"block:0:SaveRecord", "block:1:SaveRecord"}
    assert "workflow:root" in {node.node_id for node in digest.nodes}
    assert all(edge.reads == SaveRecord.reads and edge.writes == SaveRecord.writes
               and edge.side_effects == SaveRecord.side_effects for edge in edges)


def _write_recording_project(root):
    (root / "hazard_recording_app.py").write_text('''records = []
status = "idle"
done = False

def route(value):
    global status, done
    records.append(("route", value))
    status, done = "routing", False
    return value

def complete_record(value):
    global status, done
    records.append(("record", value))
    status, done = "complete", True
    return len(records)
''', encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_recording.py").write_text('''import hazard_recording_app as app

def test_records():
    app.records.clear()
    assert app.complete_record(app.route(1)) == 2
    assert app.records == [("route", 1), ("record", 1)]
    assert app.status == "complete" and app.done is True
''', encoding="utf-8")
    directory = root / ".flowguard/models"
    directory.mkdir(parents=True)
    path = directory / "hazard_recording.py"
    path.write_text('''from dataclasses import dataclass
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
MODEL_ID = "hazard_recording"
COMPONENTS = ["app"]
IMPLEMENTED_BY = {"Router": "hazard_recording_app.py:route", "Record": "hazard_recording_app.py:complete_record"}
TESTED_BY = {"recorded_in_order": ["tests/test_recording.py:test_records"]}
@dataclass(frozen=True)
class RecordState:
    records: tuple = ()
    status: str = "idle"
    done: bool = False
class Router:
    name = "Router"
    reads = ("records",)
    writes = ("records", "status", "done")
    side_effects = ("records_append",)
    def apply(self, value, state):
        return [FunctionResult(value, RecordState(state.records + ("route",), "routing", False))]
class Record:
    name = "CompleteRecord"
    reads = ("records",)
    writes = ("records", "status", "done")
    side_effects = ("records_append",)
    def apply(self, value, state):
        records = state.records + ("record",)
        return [FunctionResult(len(records), RecordState(records, "complete", True))]
class Lose:
    # The known-bad variant adds this block; the two anchored writers stay unchanged.
    name = "Lose"
    reads = ("records",)
    writes = ("lost",)
    def apply(self, value, state):
        return [FunctionResult(value, RecordState(state.records + ("lost",), state.status, state.done))]
def ordered(state, trace):
    return (state == RecordState() or state == RecordState(("route",), "routing", False)
            or state == RecordState(("route", "record"), "complete", True))
def explorer(bad=False):
    return Explorer(Workflow((Router(), Record(), *((Lose(),) if bad else ())), name="recording"), initial_states=(RecordState(),),
                    external_inputs=(0, 1), max_sequence_length=1, progress_steps=0,
                    invariants=(Invariant("recorded_in_order", "route and record complete in order", ordered),))
def build_explorer(): return explorer()
def broken_variants(): return {"loses_record": explorer(True)}
def conformance():
    import hazard_recording_app as app
    facts = []
    for value in (0, 1):
        app.records.clear()
        app.status, app.done = "idle", False
        routed = app.route(value)
        count = app.complete_record(routed)
        facts.extend((Fact("return", routed == value and count == 2),
                      Fact("records", app.records == [("route", value), ("record", value)]),
                      Fact("completion", app.status == "complete" and app.done is True)))
    return CodeFactsReport(tuple(facts))
''', encoding="utf-8")
    (root / ".flowguard/map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": [dict(
        id="app", summary="Records routed values", responsibilities=["record routed values in order"],
        files=["hazard_recording_app.py"], entrypoints=["hazard_recording_app.py:route"],
        tests=["tests/test_recording.py"], models=[".flowguard/models/hazard_recording.py"],
        depends_on=[], status="draft")]}), encoding="utf-8")
    return path


def test_two_blocks_writing_one_field_print_a_shared_writer_hazard(tmp_path, capsys, monkeypatch):
    _write_recording_project(tmp_path)
    actual = cli.run_models
    captured = []

    def capture(*args, **kwargs):
        results = actual(*args, **kwargs)
        captured.extend(results)
        return results

    monkeypatch.setattr(cli, "run_models", capture)
    assert cli.main(["--root", str(tmp_path), "models", "hazard_recording", "--tests"]) == 0
    output = capsys.readouterr().out
    assert "PASS  hazard_recording" in output and "hazard: shared_writer:" in output, output
    assert "records" in output and "Router" in output and "CompleteRecord" in output, output
    result = next(result for result in captured if result.model == "hazard_recording")
    assert result.status == "pass" and not result.problems
    # The shared fields (one hint for the one writer set), both repeatable append effects and a
    # completion node give more open hints than the display cap of three.
    assert len(result.hazards) > 3
    lines = [line for line in output.splitlines() if line.startswith("      hazard")]
    assert lines == [f"      hazard: {hazard}" for hazard in result.hazards[:3]] + [
        f"      hazards: {len(result.hazards)} open (3 shown), {len(result.closed_hazards)} closed by known-bad "
        "variants or invariants"]
    payload = json.loads(json.dumps(asdict(result)))
    assert proof.ModelResult(**payload).hazards == result.hazards
    payload.pop("hazards")
    assert proof.ModelResult(**payload).hazards == []


def test_hazards_never_change_the_verdict(tmp_path, monkeypatch):
    path = _write_recording_project(tmp_path)
    calls = []

    def failed_inference(explorer):
        calls.append(explorer)
        raise RuntimeError("inference probe failed")

    monkeypatch.setattr(proof, "model_hazards", failed_inference)
    saved_path = sys.path[:]
    names = ("hazard_recording_app", "_flowguard_model_hazard_recording")
    previous = {name: sys.modules.pop(name) for name in names if name in sys.modules}
    try:
        result = proof.run_model_in_process(tmp_path, path)
    finally:
        sys.path[:] = saved_path
        for name in names:
            sys.modules.pop(name, None)
        sys.modules.update(previous)
    assert len(calls) == 1 and calls[0].workflow.blocks[0].name == "Router"
    assert result.status == "pass" and not result.problems, result
    assert result.hazards == ["inference failed: inference probe failed"]
    assert "      hazard: inference failed: inference probe failed" in proof.render_results([result])


def test_hazard_words_match_whole_words_only():
    """`ValidateSystem` reading `threshold` and `schema` is no legacy path; `LegacyImport` is."""
    from flowguard.hazards import derive_topology_hazard_candidates

    class ValidateSystem:
        name = "ValidateSystem"
        reads = ("threshold", "schema")
        writes = ("verdict",)

    class LegacyImport(ValidateSystem):
        name = "LegacyImport"

    def kinds(block):
        digest = infer_topology_digest(workflow=Workflow((block,), name="check"), initial_states=(), external_inputs=())
        return {candidate.landmark_type for candidate in derive_topology_hazard_candidates(digest)}

    assert "legacy_or_compatibility_path" not in kinds(ValidateSystem())
    assert "legacy_or_compatibility_path" in kinds(LegacyImport())


def test_same_type_nodes_give_one_hazard():
    """Three inputs of one type are one node: a single parent_child_compression hazard."""
    from flowguard.hazards import derive_topology_hazard_candidates

    @dataclass(frozen=True)
    class Request:
        parent: str = ""

    digest = infer_topology_digest(workflow=Workflow((SaveRecord(),), name="save"), initial_states=(State(),),
                                   external_inputs=(Request("a"), Request("b"), Request("c")))
    found = [c for c in derive_topology_hazard_candidates(digest) if c.landmark_type == "parent_child_compression"]
    assert len(found) == 1, found


_TOTAL_MODEL = '''from dataclasses import dataclass
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
MODEL_ID = "hazard_total"
COMPONENTS = ["app"]
IMPLEMENTED_BY = {"AddOne": "hazard_total_app.py:add_one"}
class AddOne:
    name = "AddOne"
    reads = ("total",)
    writes = ("total",)
    def apply(self, value, state):
        return [FunctionResult(value, state + 1)]
class AddTwo(AddOne):
    name = "AddTwo"
    def apply(self, value, state):
        return [FunctionResult(value, state + 2)]
class WrongAddTwo(AddTwo):
    def apply(self, value, state):
        return [FunctionResult(value, state + 5)]
def explorer(second=None):
    return Explorer(Workflow((AddOne(), second or AddTwo()), name="adding"), initial_states=(0,), external_inputs=(0,),
                    max_sequence_length=1, progress_steps=0,
                    invariants=(Invariant("small_steps", "each step adds at most two", lambda state, trace: state <= 3),))
def build_explorer(): return explorer()
def broken_variants(): return {"adds_five": explorer(WrongAddTwo())}
def conformance():
    import hazard_total_app as app
    return CodeFactsReport((Fact("adds one", app.add_one(0) == 1),))
'''


def test_known_bad_on_the_block_closes_its_hazard(tmp_path, capsys):
    """Two blocks write `total`; a caught known-bad variant replacing one of them closes the shared_writer hint."""
    (tmp_path / "hazard_total_app.py").write_text("def add_one(value):\n    return value + 1\n", encoding="utf-8")
    (tmp_path / ".flowguard/models").mkdir(parents=True)
    (tmp_path / ".flowguard/models/hazard_total.py").write_text(_TOTAL_MODEL, encoding="utf-8")
    (tmp_path / ".flowguard/map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": [dict(
        id="app", summary="Adds", responsibilities=["add numbers"], files=["hazard_total_app.py"], entrypoints=[],
        tests=[], models=[], depends_on=[], status="draft")]}), encoding="utf-8")
    assert cli.main(["--root", str(tmp_path), "models", "hazard_total"]) == 0
    output = capsys.readouterr().out
    assert "hazard: shared_writer" not in output, output
    assert "hazards: 0 open (0 shown), 1 closed by known-bad variants or invariants" in output, output
    assert cli.main(["--root", str(tmp_path), "models", "hazard_total", "--hazards"]) == 0
    listed = capsys.readouterr().out
    assert "shared_writer" in listed and "closed by known-bad adds_five" in listed, listed


def test_hazard_output_is_capped_with_one_summary_line():
    """At most three open hints plus one summary line; --hazards lists every hint."""
    result = proof.ModelResult(model="m", file="m.py", status="pass",
                               hazards=[f"shared_writer: hint {index}" for index in range(5)])
    lines = [line.strip() for line in proof.render_results([result]).splitlines() if "hazard" in line]
    assert lines == ["hazard: shared_writer: hint 0", "hazard: shared_writer: hint 1", "hazard: shared_writer: hint 2",
                     "hazards: 5 open (3 shown), 0 closed by known-bad variants or invariants"], lines
    full = proof.render_results([result], all_hazards=True)
    assert all(f"hint {index}" in full for index in range(5)) and "+" not in full
