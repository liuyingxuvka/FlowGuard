"""Finite native contract for the Python function/state verification engine.

This owner executes the real Python library, independently of the portable
JSON interpreter. Passing cases prove only the explicitly declared finite
fixtures. Bad cases pass their oracle only when the real engine exposes the
named failure; they never license production conformance or unbounded proofs.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path

from flowguard.checks import no_duplicate_values
from flowguard.conformance import replay_trace
from flowguard.contract import FunctionContract, check_trace_contracts
from flowguard.core import (
    FunctionResult, Invariant, block_accepts_input, coerce_function_result,
    invoke_block, normalize_function_results,
)
from flowguard.loop import GraphEdge, LoopCheckConfig, check_loops
from flowguard.plan import FlowGuardCheckPlan, ScenarioMatrixConfig
from flowguard.risk import RiskIntent, RiskProfile
from flowguard.risk_templates import KnownBadProof, MinimumModelContract
from flowguard.replay import ReplayInput, ReplayObservation
from flowguard.runner import run_model_first_checks
from flowguard.trace import Trace
from flowguard.workflow import Workflow


MODEL_ID = "python_function_state_verification"
PROTECTED_FAILURE_IDS = (
    "engine_unsupported_invocation_hidden",
    "engine_result_coercion",
    "engine_nondeterministic_branch_loss",
    "engine_exception_or_dead_path_hidden",
    "engine_invariant_or_reachability_miss",
    "engine_incomplete_exploration_claimed_complete",
    "engine_trace_state_corruption",
    "engine_step_contract_violation_hidden",
    "engine_conformance_mismatch_or_expectation_leak",
    "engine_loop_nonprogress_hidden",
)
ENGINE_SOURCE_PATHS = tuple("flowguard/" + name + ".py" for name in (
    "core", "contract", "checks", "explorer", "runner", "trace", "workflow",
    "plan", "replay", "conformance", "loop", "risk", "risk_templates",
))


@dataclass(frozen=True)
class State:
    records: tuple[str, ...] = ()
    cache: tuple[str, ...] = ()


class Record:
    name = "Record"
    reads = ("records",)
    writes = ("records",)

    def apply(self, input_obj, state):
        records = state.records if input_obj in state.records else state.records + (input_obj,)
        return (FunctionResult(input_obj, replace(state, records=records),
                               label="recorded", reason="idempotent append",
                               metadata={"operation": "record"}),)


class DuplicateRecord(Record):
    def apply(self, input_obj, state):
        return (FunctionResult(input_obj, replace(state, records=state.records + (input_obj,)),
                               label="recorded"),)


class Branch:
    name = "Branch"

    def apply(self, input_obj, state):
        return (FunctionResult("left", State(("left",)), label="left"),
                FunctionResult("right", State(("right",)), label="right"))


class RejectInput:
    name = "RejectInput"
    accepted_input_type = int

    def apply(self, input_obj, state):
        raise AssertionError("unaccepted input must not invoke apply")


class RaiseError:
    name = "RaiseError"

    def apply(self, input_obj, state):
        raise ValueError("deliberate owner fixture")


class EmptyResult:
    name = "EmptyResult"

    def apply(self, input_obj, state):
        return ()


class Priority:
    def apply(self, input_obj, state):
        return ("apply", state)

    def run(self, input_obj, state):
        return ("run", state)

    def transition(self, input_obj, state):
        return ("transition", state)

    def __call__(self, input_obj, state):
        return ("call", state)


class RunOnly:
    def run(self, input_obj, state):
        return ("run", state)


class TransitionOnly:
    def transition(self, input_obj, state):
        return ("transition", state)


class Adapter:
    """Real independent state update: never receives an expected trace step."""

    def __init__(self, broken=False):
        self.broken = broken
        self.calls = []

    def reset(self, initial_state):
        self.state = initial_state

    def apply_step(self, request):
        self.calls.append(request)
        if type(request) is not ReplayInput or any(hasattr(request, key) for key in
                ("function_output", "new_state", "old_state", "label", "reason")):
            raise AssertionError("replay leaked an expected output or state")
        value = request.function_input
        if self.broken or value not in self.state.records:
            self.state = replace(self.state, records=self.state.records + (value,))
        return ReplayObservation(request.function_name, value, self.state, "recorded")


def unique_records():
    return no_duplicate_values("records_unique", "retries preserve uniqueness",
                               lambda state: state.records)


def explore(block=None, **kwargs):
    # The formal runner owns exploration. The finite engine oracle consumes
    # its actual report; unrelated audit findings never stand in for an engine verdict.
    summary = run_model_first_checks(FlowGuardCheckPlan(
        workflow=Workflow((block if block is not None else Record(),)),
        initial_states=(State(),), external_inputs=("a",),
        max_sequence_length=kwargs.pop("max_sequence_length", 1),
        scenario_matrix_config=ScenarioMatrixConfig(enabled=False), **kwargs))
    return dict(summary.metadata)["model_check_report"]


def _row(name, kind, ok, observation, finding=""):
    """The oracle verdict and the actual observation are distinct fields."""
    return {"name": name, "case_kind": kind, "ok": bool(ok),
            "expected_ok": True, "observed_status": observation["status"],
            "finding_codes": [finding] if finding else [],
            # The native bridge recursively collects dictionaries as cases.
            # Preserve the complete observation as data without manufacturing
            # another leaf from an inner report's independent `ok` field.
            "observation_json": json.dumps(observation, sort_keys=True)}


def _expect_type_error(callback):
    try:
        callback()
    except TypeError as error:
        return {"status": "violation", "exception": type(error).__name__,
                "message": str(error)}
    return {"status": "ok", "exception": ""}


def run_review():
    """Execute each declared finite fixture once and return its own evidence."""
    cases = []
    # Hook priority and all remaining invocation forms are tested on real core.
    values = tuple(invoke_block(block, "a", State())[0] for block in
                   (Priority(), RunOnly(), TransitionOnly(), lambda value, state: ("call", state)))
    acceptance = (block_accepts_input(RejectInput(), 1, State()),
                  block_accepts_input(RejectInput(), "a", State()))
    class HookPriority(RejectInput):
        def can_accept(self, value):
            return value == "allowed"

    hook_priority = (block_accepts_input(HookPriority(), "allowed", State()),
                     block_accepts_input(HookPriority(), 1, State()))
    cases.append(_row("invocation_and_input_hooks", "good",
                      values == ("apply", "run", "transition", "call") and acceptance == (True, False)
                      and hook_priority == (True, False),
                      {"status": "ok", "invoked": values, "accepted": acceptance,
                       "can_accept_priority": hook_priority}))
    missing = _expect_type_error(lambda: invoke_block(object(), "a", State()))
    cases.append(_row("noninvocable_block_rejected", "bad", missing["status"] == "violation",
                      missing, "engine_unsupported_invocation_hidden"))

    result = FunctionResult("a", State(("a",)), label="recorded", metadata={"z": 2, "a": 1})
    class ObjectResult:
        output = "a"
        state = State(("a",))
        label = "recorded"
    normalized = normalize_function_results((item for item in (result, ("b", State(("b",))))))
    coercion_ok = (coerce_function_result(result) is result
                   and coerce_function_result(ObjectResult()).new_state == State(("a",))
                   and tuple(item.output for item in normalized) == ("a", "b")
                   and result.metadata == (("a", 1), ("z", 2))
                   and normalize_function_results(("a", State())) == (FunctionResult("a", State()),)
                   and normalize_function_results((result, result)) == (result, result)
                   and normalize_function_results(None) == ())
    cases.append(_row("result_forms_and_metadata", "good", coercion_ok,
                      {"status": "ok", "outputs": [item.output for item in normalized]}))
    errors = tuple(_expect_type_error(callback) for callback in (
        lambda: normalize_function_results("not a result"),
        lambda: coerce_function_result(object()), lambda: FunctionResult([], State()),
        lambda: FunctionResult("a", {})))
    cases.append(_row("invalid_result_rejected", "bad",
                      all(item["status"] == "violation" for item in errors),
                      {"status": "violation" if all(item["status"] == "violation" for item in errors) else "ok",
                       "rejections": errors}, "engine_result_coercion"))

    branching = explore(Branch(), required_labels=("left", "right"))
    outcomes = {trace.final_output for trace in branching.traces}
    cases.append(_row("all_nondeterministic_branches", "good", branching.ok and outcomes == {"left", "right"},
                      {"status": "ok" if branching.ok else "violation", "outputs": sorted(outcomes)}))
    unsafe = explore(Branch(), invariants=(Invariant("reject_right", "right branch is unsafe",
                                                   lambda state, trace: "right" not in state.records),))
    cases.append(_row("unsafe_second_branch_detected", "bad",
                      not unsafe.ok and any(item.trace.final_output == "right" for item in unsafe.violations),
                      {"status": "violation" if not unsafe.ok else "ok", "report": unsafe.to_dict()},
                      "engine_nondeterministic_branch_loss"))

    dead = explore(RejectInput())
    empty = explore(EmptyResult())
    raised = explore(RaiseError())
    def raising_invariant(state, trace):
        raise ValueError("deliberate invariant fixture")
    invariant_error = explore(invariants=(Invariant("raises", "must fail closed", raising_invariant),))
    error_ok = (not dead.ok and len(dead.dead_branches) == 1
                and not empty.ok and len(empty.dead_branches) == 1
                and not raised.ok and len(raised.exception_branches) == 1
                and raised.exception_branches[0].error_type == "ValueError"
                and not invariant_error.ok and bool(invariant_error.violations)
                and "ValueError" in invariant_error.violations[0].message)
    cases.append(_row("rejected_empty_and_exception_paths", "bad", error_ok,
                      {"status": "violation" if error_ok else "ok", "dead": dead.to_dict(),
                       "empty": empty.to_dict(), "raised": raised.to_dict(),
                       "invariant_exception": invariant_error.to_dict()},
                      "engine_exception_or_dead_path_hidden"))

    retry = explore(invariants=(unique_records(),), max_sequence_length=2, required_labels=("recorded",))
    duplicate = explore(DuplicateRecord(), invariants=(unique_records(),), max_sequence_length=2,
                        required_labels=("unreachable",))
    cases.append(_row("idempotent_retry_and_reachability", "good", retry.ok and retry.exploration_complete,
                      {"status": "ok" if retry.ok else "violation", "report": retry.to_dict()}))
    cases.append(_row("invariant_and_unreachable_label_detected", "bad",
                      not duplicate.ok and bool(duplicate.violations) and bool(duplicate.reachability_failures),
                      {"status": "violation" if not duplicate.ok else "ok", "report": duplicate.to_dict()},
                      "engine_invariant_or_reachability_miss"))

    bounded = explore(max_sequence_length=2, max_transitions=1)
    cases.append(_row("finite_cutoff_is_not_exhaustive_success", "bad",
                      not bounded.ok and not bounded.exploration_complete
                      and bounded.termination_reason == "max_transitions_exhausted"
                      and bool(bounded.remaining_scope),
                      {"status": "violation" if not bounded.ok else "ok", "report": bounded.to_dict()},
                      "engine_incomplete_exploration_claimed_complete"))

    run = Workflow((Record(), Record())).execute(State(), "a")
    trace = run.completed_paths[0].trace
    immutable = Trace(initial_state=State(), external_inputs=("a",))
    appended = immutable.append(trace.steps[0])
    trace_ok = (len(immutable.steps) == 0 and len(appended.steps) == 1
                and trace.steps[0].old_state == State()
                and trace.steps[1].old_state == trace.steps[0].new_state
                and trace.final_state == State(("a",))
                and trace.final_output == "a" and trace.labels == ("recorded", "recorded")
                and trace.steps[0].metadata == (("operation", "record"),))
    cases.append(_row("immutable_trace_and_state_chain", "good", trace_ok,
                      {"status": "ok" if trace_ok else "violation", "trace": trace.to_dict()}))
    early = Workflow((Record(), RaiseError())).execute(State(), "a",
        terminal_predicate=lambda input_obj, state, trace: bool(state.records))
    early_ok = (len(early.completed_paths) == 1 and not early.exception_branches
                and len(early.completed_paths[0].trace.steps) == 1
                and early.completed_paths[0].state == State(("a",)))
    cases.append(_row("terminal_predicate_stops_later_blocks", "good", early_ok,
                      {"status": "ok" if early_ok else "violation",
                       "trace": early.completed_paths[0].trace.to_dict() if early.completed_paths else {}}))
    corrupt_step = replace(trace.steps[0], new_state=State(("wrong",)))
    corrupt = Trace(initial_state=State(), steps=(corrupt_step,))
    replayed_corrupt = replay_trace(corrupt, Adapter())
    cases.append(_row("corrupt_expected_trace_rejected_by_replay", "bad",
                      not replayed_corrupt.ok and replayed_corrupt.violations[0].rule_name == "projected_state_matches",
                      {"status": "violation" if not replayed_corrupt.ok else "ok", "report": replayed_corrupt.to_dict()},
                      "engine_trace_state_corruption"))

    contract = FunctionContract(function_name="Record", accepted_input_type=str,
                                output_type=str, writes=("records",), forbidden_writes=("cache",))
    correct_contract = check_trace_contracts(trace, (contract,))
    forbidden = Trace(initial_state=State(), steps=(replace(trace.steps[0], new_state=State(("a",), ("a",))),))
    rejected_contract = check_trace_contracts(forbidden, (contract,))
    cases.append(_row("declared_write_contract", "good", correct_contract.ok,
                      {"status": "ok" if correct_contract.ok else "violation", "report": correct_contract.to_dict()}))
    cases.append(_row("forbidden_and_undeclared_write_detected", "bad",
                      not rejected_contract.ok and {"forbidden_write", "undeclared_write"}
                      <= set(rejected_contract.violation_names()),
                      {"status": "violation" if not rejected_contract.ok else "ok", "report": rejected_contract.to_dict()},
                      "engine_step_contract_violation_hidden"))

    adapter = Adapter()
    conformance = replay_trace(trace, adapter)
    broken_adapter = Adapter(broken=True)
    mismatch = replay_trace(trace, broken_adapter)
    cases.append(_row("independent_adapter_receives_only_input", "good",
                      conformance.ok and len(adapter.calls) == 2
                      and all(type(item) is ReplayInput for item in adapter.calls),
                      {"status": "ok" if conformance.ok else "violation", "report": conformance.to_dict()}))
    cases.append(_row("duplicate_implementation_effect_rejected", "bad",
                      not mismatch.ok and mismatch.failed_step_index == 2
                      and mismatch.violations[0].rule_name == "projected_state_matches",
                      {"status": "violation" if not mismatch.ok else "ok", "report": mismatch.to_dict()},
                      "engine_conformance_mismatch_or_expectation_leak"))

    terminating = check_loops(LoopCheckConfig(initial_states=(0,),
        transition_fn=lambda state: (GraphEdge(state, 1, "finish"),) if state == 0 else (),
        is_terminal=lambda state: state == 1, is_success=lambda state: state == 1, required_success=True))
    looping = check_loops(LoopCheckConfig(initial_states=(0,),
        transition_fn=lambda state: (GraphEdge(state, state, "retry"),),
        is_terminal=lambda state: False))
    cases.append(_row("finite_terminal_graph", "good", terminating.ok,
                      {"status": "ok" if terminating.ok else "violation", "report": terminating.to_dict()}))
    cases.append(_row("nonterminal_bottom_cycle_detected", "bad",
                      not looping.ok and bool(looping.non_terminating_components),
                      {"status": "violation" if not looping.ok else "ok", "report": looping.to_dict()},
                      "engine_loop_nonprogress_hidden"))

    # This assertion licenses only consumption of this exact existing report,
    # not the unrelated entry/audit gates of a bare helper plan.
    class CountingRecord(Record):
        def __init__(self):
            self.calls = 0

        def apply(self, input_obj, state):
            self.calls += 1
            return super().apply(input_obj, state)

    # Proofs come only from the counterexamples this invocation actually ran.
    bad_rows = tuple(row for row in cases if row["case_kind"] == "bad")
    bad_names = tuple(row["name"] for row in bad_rows)
    observed_errors = tuple(row["finding_codes"][0] for row in bad_rows)
    complete_bad = (set(observed_errors) == set(PROTECTED_FAILURE_IDS)
                    and len(observed_errors) == len(PROTECTED_FAILURE_IDS)
                    and all(row["ok"] and row["observed_status"] == "violation" for row in bad_rows))
    proofs = tuple(KnownBadProof(
        row["name"], protected_error_class=row["finding_codes"][0],
        method="real_python_engine_counterexample", observed_status="expected_violation",
        observed_failure=row["observation_json"],
        evidence_id="native-scenario:" + MODEL_ID + ":" + row["name"],
    ) for row in bad_rows if row["ok"] and row["observed_status"] == "violation")
    intent = RiskIntent(
        failure_modes=PROTECTED_FAILURE_IDS, protected_error_classes=PROTECTED_FAILURE_IDS,
        protected_harms=("engine hides a finite counterexample or claims incomplete exploration complete",),
        must_model_state=("records", "cache"), must_model_side_effects=("record writes", "replay adapter effects"),
        completion_evidence=("actual finite engine oracle results",),
        adversarial_inputs=bad_names, hard_invariants=("every declared engine failure remains observable",),
        known_bad_cases=bad_names,
        blindspots=("only declared finite Python engine fixtures; no portable interpreter or production conformance",),
    )
    counted = CountingRecord()
    plan = FlowGuardCheckPlan(
        workflow=Workflow((counted,)), initial_states=(State(),), external_inputs=("a",),
        invariants=(unique_records(),), scenario_matrix_config=ScenarioMatrixConfig(enabled=False),
        risk_profile=RiskProfile(modeled_boundary=__doc__, risk_intent=intent),
        minimum_model_contract=MinimumModelContract(
            protected_error_classes=PROTECTED_FAILURE_IDS, modeled_state=intent.must_model_state,
            modeled_side_effects=intent.must_model_side_effects,
            completion_evidence=intent.completion_evidence, known_bad_cases=bad_names),
        known_bad_proofs=proofs,
    )
    initial_summary = run_model_first_checks(plan)
    supplied = dict(initial_summary.metadata)["model_check_report"]
    before = counted.calls
    summary = run_model_first_checks(plan, model_report=supplied)
    consumed = dict(summary.metadata)["model_check_report"]
    gate_names = ("minimum_model_review", "known_bad_proof", "model_check")
    gates = {section.name: section.status for section in summary.sections if section.name in gate_names}
    missing_proof = run_model_first_checks(replace(plan, known_bad_proofs=proofs[:-1]), model_report=supplied)
    negative = next(section for section in missing_proof.sections if section.name == "known_bad_proof")
    same_once = (complete_bad and consumed is supplied and before == 1 and counted.calls == before
                 and set(gates) == set(gate_names) and all(status == "pass" for status in gates.values())
                 and negative.status != "pass")
    cases.append(_row("runner_preserves_supplied_exploration_report", "good", same_once,
                      {"status": "ok" if same_once else "violation", "formal_gates": gates,
                       "missing_proof_status": negative.status,
                       "consumed_same_report": consumed is supplied,
                       "calls_before": before, "calls_after": counted.calls}))
    # Keep typed formal evidence as JSON data, outside the native bridge's leaf dictionary collection.
    return {"native_cases": cases, "claim_boundary": __doc__,
            "formal_entry_json": json.dumps({"plan": plan.to_dict(), "gates": gates,
                "missing_proof_status": negative.status, "missing_proof_findings": negative.findings,
                "complete_executed_bad_cases": complete_bad}, sort_keys=True)}



def export_path_quality_source(model_instance_fingerprint):
    """Export explicit check contracts without executing a native fixture."""
    from flowguard.model_path_quality import compile_declared_path_quality_source
    from flowguard.source_identity import functional_source_fingerprint
    root = Path(__file__).resolve().parents[4]
    paths = (".flowguard/models/owners/" + MODEL_ID + "/model.py",
             ".flowguard/verification/owners/" + MODEL_ID + "/run_checks.py") + ENGINE_SOURCE_PATHS
    specifications = (
        ("noninvocable_block_rejected", "invoke_block", "object without apply/run/transition/call", "TypeError",
         "apply takes priority over run, transition and callable; all four supported forms remain executable"),
        ("invalid_result_rejected", "normalize_function_results/coerce_function_result/FunctionResult",
         "string, opaque object, unhashable output, unhashable state", "four TypeErrors",
         "FunctionResult, duck output/state and pair results normalize without losing metadata or generator items"),
        ("unsafe_second_branch_detected", "Explorer.explore/Workflow.execute", "Branch(left,right)",
         "right counterexample in violations", "both branch results must be visited, including the unsafe second result"),
        ("rejected_empty_and_exception_paths", "Workflow.execute/Explorer.explore",
         "type-rejected input, zero results, ValueError", "dead/dead/exception reports and no success",
         "input rejection never calls apply and zero results or exceptions remain visible"),
        ("invariant_and_unreachable_label_detected", "no_duplicate_values/Explorer.explore",
         "two repeated inputs, duplicate appender, required absent label", "invariant and reachability failures",
         "positive idempotent retry and reachable label both remain covered"),
        ("finite_cutoff_is_not_exhaustive_success", "Explorer.explore", "two-sequence scope, max_transitions=1",
         "ok=False, exploration_complete=False, max_transitions_exhausted, nonempty remaining_scope",
         "a caller-requested diagnostic limit never licenses complete exploration"),
        ("corrupt_expected_trace_rejected_by_replay", "Trace.append/Workflow.execute/replay_trace",
         "expected first new_state changed to wrong record", "projected_state_matches violation",
         "original Trace is immutable; ordered steps retain exact input/output/state/label/metadata"),
        ("forbidden_and_undeclared_write_detected", "check_trace_contracts",
         "Record changes forbidden cache in addition to allowed records", "forbidden_write and undeclared_write",
         "declared records-only writes pass the same FunctionContract"),
        ("duplicate_implementation_effect_rejected", "ReplayInput.from_trace_step/replay_trace",
         "independent adapter appends on repeated input", "second-step projected_state_matches violation",
         "adapter receives input-only ReplayInput, never expected output/new state; idempotent adapter passes"),
        ("nonterminal_bottom_cycle_detected", "check_loops", "one nonterminal self-loop",
         "non_terminating_components and ok=False", "two-state finishing graph has reachable terminal success"),
    )
    contracts = {failure: {"protected_failure_id": failure, "known_bad_case_id": spec[0],
                          "oracle_symbol": "run_review", "real_library_calls": spec[1],
                          "bad_input_and_state": spec[2], "required_observation": spec[3],
                          "positive_preservation": spec[4],
                          "claim_boundary": "exact finite Python engine fixtures; not arbitrary caller models or the portable JSON interpreter"}
                 for failure, spec in zip(PROTECTED_FAILURE_IDS, specifications)}
    return compile_declared_path_quality_source(model_id=MODEL_ID,
        model_instance_fingerprint=model_instance_fingerprint, graph_scope="native_check_contract",
        source_refs=tuple({"path": path, "source_fingerprint": functional_source_fingerprint(root, path)} for path in paths),
        declared_contracts=contracts)
