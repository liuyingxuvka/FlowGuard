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
    def __init__(self, bad=False): self.bad = bad
    def apply(self, value, state):
        records = state.records + (("lost",) if self.bad else ("record",))
        return [FunctionResult(len(records), RecordState(records, "complete", True))]
def ordered(state, trace):
    return (state == RecordState() or state == RecordState(("route",), "routing", False)
            or state == RecordState(("route", "record"), "complete", True))
def explorer(bad=False):
    return Explorer(Workflow((Router(), Record(bad)), name="recording"), initial_states=(RecordState(),),
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
    # Three real shared fields, both repeatable append effects and a completion
    # node produce enough actual candidates to exercise the display cap.
    assert len(result.hazards) > 5
    lines = [line for line in output.splitlines() if line.startswith("      hazard: ")]
    assert lines == [f"      hazard: {hazard}" for hazard in result.hazards[:5]] + [
        f"      hazard: +{len(result.hazards) - 5} more"]
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
