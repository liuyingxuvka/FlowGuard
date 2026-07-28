"""FlowGuard Risk Purpose Header.

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the proactive adversarial scenario synthesis upgrade.
Guards against: creating a parallel test workflow, treating generated challenge
routes as passing evidence, hiding why generated routes are risky, bypassing
existing helper packs, and skipping replay/alignment/ledger handoff semantics.
Use before editing: run before changing scenario-matrix generation, helper
packs, or docs for proactive bug discovery.
Run: `python .flowguard/adversarial_scenario_synthesis/run_checks.py`
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    Scenario,
    ScenarioExpectation,
    Workflow,
    review_scenarios,
)


@dataclass(frozen=True)
class SynthesisPlan:
    existing_scenario_flow: bool = False
    deterministic_patterns: bool = False
    model_trace_evidence_used: bool = False
    bounded_generation: bool = False
    generated_needs_review: bool = False
    risk_explanation_visible: bool = False
    packs_reuse_builder: bool = False
    replay_alignment_ledger_handoff: bool = False
    parallel_workflow_created: bool = False
    generated_claimed_as_pass: bool = False
    fixed_pattern_only: bool = False
    finalized: bool = False


@dataclass(frozen=True)
class PlanStep:
    name: str


class ApplySynthesisStep:
    name = "ApplySynthesisStep"
    reads = ("SynthesisPlan",)
    writes = ("SynthesisPlan",)
    input_description = "adversarial synthesis implementation decision"
    output_description = "updated implementation plan state"
    accepted_input_type = PlanStep

    def apply(
        self,
        input_obj: PlanStep,
        state: SynthesisPlan,
    ) -> Iterable[FunctionResult]:
        new_state = apply_step(input_obj.name, state)
        yield FunctionResult(
            output=input_obj,
            new_state=new_state,
            label=input_obj.name,
            reason=f"applied adversarial synthesis decision {input_obj.name}",
        )


def apply_step(step: str, state: SynthesisPlan) -> SynthesisPlan:
    if step == "extend_scenario_builder":
        return replace(state, existing_scenario_flow=True)
    if step == "add_deterministic_patterns":
        return replace(state, deterministic_patterns=True)
    if step == "use_model_trace_evidence":
        return replace(state, model_trace_evidence_used=True)
    if step == "preserve_limits":
        return replace(state, bounded_generation=True)
    if step == "default_needs_human_review":
        return replace(state, generated_needs_review=True)
    if step == "attach_risk_notes":
        return replace(state, risk_explanation_visible=True)
    if step == "packs_call_builder":
        return replace(state, packs_reuse_builder=True)
    if step == "handoff_to_replay_alignment_ledger":
        return replace(state, replay_alignment_ledger_handoff=True)
    if step == "create_parallel_workflow":
        return replace(state, parallel_workflow_created=True)
    if step == "mark_generated_as_pass":
        return replace(state, generated_claimed_as_pass=True)
    if step == "fixed_pattern_only":
        return replace(state, fixed_pattern_only=True)
    if step == "finalize":
        return replace(state, finalized=True)
    return state


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(message: str) -> InvariantResult:
    return InvariantResult.fail(message)


def no_parallel_workflow(state: SynthesisPlan, _trace: object) -> InvariantResult:
    if state.parallel_workflow_created:
        return _fail("adversarial synthesis must extend ScenarioMatrixBuilder, not create a parallel workflow")
    if state.finalized and not state.existing_scenario_flow:
        return _fail("final plan must preserve the existing Scenario Sandbox flow")
    return _pass()


def generated_routes_remain_candidate_evidence(state: SynthesisPlan, _trace: object) -> InvariantResult:
    if state.generated_claimed_as_pass:
        return _fail("generated challenge routes cannot be treated as passing evidence without an oracle")
    if state.finalized and not state.generated_needs_review:
        return _fail("generated routes must default to needs_human_review")
    return _pass()


def bounded_deterministic_patterns_required(state: SynthesisPlan, _trace: object) -> InvariantResult:
    if not state.finalized:
        return _pass()
    if not state.deterministic_patterns:
        return _fail("challenge routes must be deterministic and named")
    if not state.bounded_generation:
        return _fail("challenge routes must preserve sequence and scenario limits")
    return _pass()


def model_trace_evidence_drives_challenges(state: SynthesisPlan, _trace: object) -> InvariantResult:
    if state.fixed_pattern_only:
        return _fail("challenge routes cannot be only fixed A/B/A-style input permutations")
    if state.finalized and not state.model_trace_evidence_used:
        return _fail("final plan must derive challenge routes from Explorer traces or model evidence")
    return _pass()


def risk_and_pack_integration_visible(state: SynthesisPlan, _trace: object) -> InvariantResult:
    if not state.finalized:
        return _pass()
    if not state.risk_explanation_visible:
        return _fail("challenge routes must explain why the route is risky")
    if not state.packs_reuse_builder:
        return _fail("helper packs must reuse the scenario builder path")
    return _pass()


def downstream_evidence_handoff_preserved(state: SynthesisPlan, _trace: object) -> InvariantResult:
    if state.finalized and not state.replay_alignment_ledger_handoff:
        return _fail("final plan must preserve replay, alignment, and ledger handoff semantics")
    return _pass()


def workflow() -> Workflow:
    return Workflow((ApplySynthesisStep(),), name="adversarial_scenario_synthesis")


def invariants() -> tuple[Invariant, ...]:
    return (
        Invariant("no_parallel_workflow", "Use existing scenario flow", no_parallel_workflow),
        Invariant(
            "generated_routes_remain_candidate_evidence",
            "Generated routes stay candidate evidence",
            generated_routes_remain_candidate_evidence,
        ),
        Invariant(
            "bounded_deterministic_patterns_required",
            "Patterns are deterministic and bounded",
            bounded_deterministic_patterns_required,
        ),
        Invariant(
            "model_trace_evidence_drives_challenges",
            "Model trace evidence drives challenge routes",
            model_trace_evidence_drives_challenges,
        ),
        Invariant(
            "risk_and_pack_integration_visible",
            "Risk notes and pack integration are visible",
            risk_and_pack_integration_visible,
        ),
        Invariant(
            "downstream_evidence_handoff_preserved",
            "Replay, alignment, and ledger handoff remain intact",
            downstream_evidence_handoff_preserved,
        ),
    )


def _scenario(name: str, steps: tuple[str, ...], expected_violations: tuple[str, ...] = ()) -> Scenario:
    if expected_violations:
        expectation = ScenarioExpectation(
            expected_status="violation",
            expected_violation_names=expected_violations,
            summary=f"expected violations: {', '.join(expected_violations)}",
        )
    else:
        expectation = ScenarioExpectation(expected_status="ok", summary="valid synthesis plan")
    return Scenario(
        name=name,
        description=name.replace("_", " "),
        initial_state=SynthesisPlan(),
        external_input_sequence=tuple(PlanStep(step) for step in steps),
        workflow=workflow(),
        invariants=invariants(),
        expected=expectation,
        tags=("adversarial_scenario_synthesis",),
    )


def scenarios() -> tuple[Scenario, ...]:
    good_steps = (
        "extend_scenario_builder",
        "add_deterministic_patterns",
        "use_model_trace_evidence",
        "preserve_limits",
        "default_needs_human_review",
        "attach_risk_notes",
        "packs_call_builder",
        "handoff_to_replay_alignment_ledger",
        "finalize",
    )
    return (
        _scenario("good_existing_flow_candidate_routes", good_steps),
        _scenario(
            "broken_parallel_workflow",
            ("create_parallel_workflow",) + good_steps,
            ("no_parallel_workflow",),
        ),
        _scenario(
            "broken_generated_routes_claim_pass",
            ("extend_scenario_builder", "mark_generated_as_pass", "finalize"),
            ("generated_routes_remain_candidate_evidence",),
        ),
        _scenario(
            "broken_fixed_pattern_only",
            (
                "extend_scenario_builder",
                "add_deterministic_patterns",
                "fixed_pattern_only",
                "preserve_limits",
                "default_needs_human_review",
                "attach_risk_notes",
                "packs_call_builder",
                "handoff_to_replay_alignment_ledger",
                "finalize",
            ),
            ("model_trace_evidence_drives_challenges",),
        ),
        _scenario(
            "broken_missing_pack_and_risk_notes",
            (
                "extend_scenario_builder",
                "add_deterministic_patterns",
                "preserve_limits",
                "default_needs_human_review",
                "handoff_to_replay_alignment_ledger",
                "finalize",
            ),
            ("risk_and_pack_integration_visible",),
        ),
        _scenario(
            "broken_unbounded_routes",
            (
                "extend_scenario_builder",
                "add_deterministic_patterns",
                "default_needs_human_review",
                "attach_risk_notes",
                "packs_call_builder",
                "handoff_to_replay_alignment_ledger",
                "finalize",
            ),
            ("bounded_deterministic_patterns_required",),
        ),
        _scenario(
            "broken_missing_downstream_handoff",
            (
                "extend_scenario_builder",
                "add_deterministic_patterns",
                "preserve_limits",
                "default_needs_human_review",
                "attach_risk_notes",
                "packs_call_builder",
                "finalize",
            ),
            ("downstream_evidence_handoff_preserved",),
        ),
    )


def run_review():
    return review_scenarios(scenarios())


__all__ = ["PlanStep", "SynthesisPlan", "invariants", "run_review", "scenarios", "workflow"]
