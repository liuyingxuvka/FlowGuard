"""FlowGuard model for model-topology hazard review.

FlowGuard model
Purpose: ensure experienced-engineer future-risk inference is grounded in model
topology before it affects confidence.
Guards against: generic unanchored AI warnings acting as hard gates, topology
hazards staying as prose only, compatibility history lacking a disposition, and
full confidence before anchored future-use hazards are handled or scoped.
Modeled block shape: Input x State -> Set(Output x State).
Run: python -m flowguard map models model_topology_hazard_review
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class TopologyHazardInput:
    action_type: str


@dataclass(frozen=True)
class TopologyHazardOutput:
    status: str


@dataclass(frozen=True)
class TopologyHazardState:
    topology_anchor_present: bool = False
    future_hazard_inferred: bool = False
    hard_gate_without_anchor: bool = False
    required_route_created: bool = False
    hazard_handled_or_scoped: bool = False
    legacy_history_possible: bool = False
    compatibility_disposition: bool = False
    final_claim: str = "none"

    def full_claim_allowed(self) -> bool:
        if self.hard_gate_without_anchor:
            return False
        if self.future_hazard_inferred and not self.hazard_handled_or_scoped:
            return False
        if self.legacy_history_possible and not self.compatibility_disposition:
            return False
        return True


class CorrectTopologyHazardGate:
    name = "CorrectTopologyHazardGate"
    reads = (
        "topology_anchor_present",
        "future_hazard_inferred",
        "hard_gate_without_anchor",
        "required_route_created",
        "hazard_handled_or_scoped",
        "legacy_history_possible",
        "compatibility_disposition",
        "final_claim",
    )
    writes = reads
    accepted_input_type = TopologyHazardInput
    input_description = "topology hazard observation or confidence claim"
    output_description = "topology hazard review state"

    def apply(self, input_obj: TopologyHazardInput, state: TopologyHazardState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "observe_topology_anchor":
            yield FunctionResult(
                TopologyHazardOutput("anchor_observed"),
                replace(state, topology_anchor_present=True, final_claim="none"),
                label="anchor_observed",
            )
        elif action == "infer_future_hazard":
            if state.topology_anchor_present:
                yield FunctionResult(
                    TopologyHazardOutput("anchored_hazard_inferred"),
                    replace(state, future_hazard_inferred=True, final_claim="none"),
                    label="anchored_hazard_inferred",
                )
            else:
                yield FunctionResult(
                    TopologyHazardOutput("unanchored_observation_only"),
                    replace(state, final_claim="none"),
                    label="unanchored_observation_only",
                )
        elif action == "create_required_route":
            if state.future_hazard_inferred:
                yield FunctionResult(
                    TopologyHazardOutput("required_route_created"),
                    replace(state, required_route_created=True, final_claim="none"),
                    label="required_route_created",
                )
            else:
                yield FunctionResult(
                    TopologyHazardOutput("route_not_applicable"),
                    state,
                    label="route_not_applicable",
                )
        elif action == "handle_or_scope_hazard":
            if state.required_route_created:
                yield FunctionResult(
                    TopologyHazardOutput("hazard_handled_or_scoped"),
                    replace(state, hazard_handled_or_scoped=True, final_claim="none"),
                    label="hazard_handled_or_scoped",
                )
            else:
                yield FunctionResult(
                    TopologyHazardOutput("handle_not_applicable"),
                    state,
                    label="handle_not_applicable",
                )
        elif action == "observe_legacy_history":
            yield FunctionResult(
                TopologyHazardOutput("legacy_history_observed"),
                replace(state, legacy_history_possible=True, final_claim="none"),
                label="legacy_history_observed",
            )
        elif action == "choose_compatibility_disposition":
            if state.legacy_history_possible:
                yield FunctionResult(
                    TopologyHazardOutput("compatibility_disposition_chosen"),
                    replace(state, compatibility_disposition=True, final_claim="none"),
                    label="compatibility_disposition_chosen",
                )
            else:
                yield FunctionResult(
                    TopologyHazardOutput("compatibility_not_applicable"),
                    state,
                    label="compatibility_not_applicable",
                )
        elif action == "claim_full_confidence":
            if state.full_claim_allowed():
                yield FunctionResult(
                    TopologyHazardOutput("full_claim_accepted"),
                    replace(state, final_claim="full"),
                    label="full_claim_accepted",
                )
            else:
                yield FunctionResult(
                    TopologyHazardOutput("scoped_or_blocked_claim"),
                    replace(state, final_claim="scoped_or_blocked"),
                    label="scoped_or_blocked_claim",
                )


class BrokenUnanchoredHardGate(CorrectTopologyHazardGate):
    name = "BrokenUnanchoredHardGate"

    def apply(self, input_obj: TopologyHazardInput, state: TopologyHazardState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "infer_future_hazard" and not state.topology_anchor_present:
            yield FunctionResult(
                TopologyHazardOutput("unanchored_hard_gate"),
                replace(state, hard_gate_without_anchor=True, final_claim="blocked"),
                label="unanchored_hard_gate",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenFullWithoutRoute(CorrectTopologyHazardGate):
    name = "BrokenFullWithoutRoute"

    def apply(self, input_obj: TopologyHazardInput, state: TopologyHazardState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_full_confidence":
            yield FunctionResult(
                TopologyHazardOutput("full_claim_accepted"),
                replace(state, final_claim="full"),
                label="full_claim_accepted",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenCompatibilityIgnored(CorrectTopologyHazardGate):
    name = "BrokenCompatibilityIgnored"

    def apply(self, input_obj: TopologyHazardInput, state: TopologyHazardState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_full_confidence" and state.legacy_history_possible:
            yield FunctionResult(
                TopologyHazardOutput("full_claim_accepted"),
                replace(state, final_claim="full"),
                label="full_claim_accepted",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, TopologyHazardOutput) and current_output.status in {
        "full_claim_accepted",
        "scoped_or_blocked_claim",
        "unanchored_hard_gate",
    }


def unanchored_hazards_do_not_become_hard_gates(state: TopologyHazardState, trace) -> InvariantResult:
    del trace
    if state.hard_gate_without_anchor:
        return InvariantResult.fail("unanchored AI risk became a hard FlowGuard gate")
    return InvariantResult.pass_()


def anchored_hazards_need_route_or_scope(state: TopologyHazardState, trace) -> InvariantResult:
    del trace
    if state.future_hazard_inferred and state.final_claim == "full" and not state.hazard_handled_or_scoped:
        return InvariantResult.fail("full confidence accepted before anchored topology hazard was handled or scoped")
    return InvariantResult.pass_()


def compatibility_history_gets_disposition(state: TopologyHazardState, trace) -> InvariantResult:
    del trace
    if state.legacy_history_possible and state.final_claim == "full" and not state.compatibility_disposition:
        return InvariantResult.fail("full confidence accepted before legacy/history compatibility disposition")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "unanchored_hazards_do_not_become_hard_gates",
        "Unanchored AI risk observations cannot act as hard FlowGuard gates.",
        unanchored_hazards_do_not_become_hard_gates,
    ),
    Invariant(
        "anchored_hazards_need_route_or_scope",
        "Anchored topology hazards require route work, handling, or scoped confidence before full confidence.",
        anchored_hazards_need_route_or_scope,
    ),
    Invariant(
        "compatibility_history_gets_disposition",
        "Old-shape/history topology requires compatibility disposition before full confidence.",
        compatibility_history_gets_disposition,
    ),
)

EXTERNAL_INPUTS = (
    TopologyHazardInput("observe_topology_anchor"),
    TopologyHazardInput("infer_future_hazard"),
    TopologyHazardInput("create_required_route"),
    TopologyHazardInput("handle_or_scope_hazard"),
    TopologyHazardInput("observe_legacy_history"),
    TopologyHazardInput("choose_compatibility_disposition"),
    TopologyHazardInput("claim_full_confidence"),
)

MAX_SEQUENCE_LENGTH = 5


def initial_state() -> TopologyHazardState:
    return TopologyHazardState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectTopologyHazardGate(),), name="topology_hazard_review_correct")


def build_broken_workflows() -> tuple[Workflow, ...]:
    return (
        Workflow((BrokenUnanchoredHardGate(),), name="topology_hazard_unanchored_hard_gate"),
        Workflow((BrokenFullWithoutRoute(),), name="topology_hazard_full_without_route"),
        Workflow((BrokenCompatibilityIgnored(),), name="topology_hazard_compatibility_ignored"),
    )


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "TopologyHazardInput",
    "TopologyHazardOutput",
    "TopologyHazardState",
    "build_broken_workflows",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]


# FlowGuard contract: explore the model above, prove its known-bad variants fail, and compare the real
# topology-hazard review with it (feature kit).  The clean plan reviews a release of a block with a side
# effect and lists one anchored ledger hazard that is handled; a full claim is accepted.  Each feature
# changes the listed hazards.  An unhandled or blocked anchored hazard must stop a full claim and be
# reported; an unanchored generic warning and another handled hazard must not.
from flowguard import (  # noqa: E402
    TOPOLOGY_CONFIDENCE_BLOCKED,
    TOPOLOGY_CONFIDENCE_FULL,
    TOPOLOGY_DISPOSITION_BLOCKED,
    TOPOLOGY_DISPOSITION_TEST_REQUIRED,
    TOPOLOGY_SEVERITY_BLOCKER,
    TopologyHazardCandidate,
    TopologyHazardReviewPlan,
    UsageIntent,
    infer_topology_digest,
    review_topology_hazards,
)
from flowguard.explorer import Explorer  # noqa: E402
from flowguard.kit import Feature, feature_conformance  # noqa: E402

MODEL_ID = "model_topology_hazard_review"
PARENT = "topology-hazard"
COMPONENTS = ["topology-hazard"]
IMPLEMENTED_BY = {"Digest": "flowguard/topology_hazard.py:infer_topology_digest",
                  "Review": "flowguard/topology_hazard.py:review_topology_hazards"}
TESTED_BY = {
    "unanchored_hazards_do_not_become_hard_gates": [
        "tests/test_topology_hazard.py:test_unanchored_ai_hazard_cannot_become_hard_gate",
        "tests/test_topology_hazard.py:test_unanchored_warning_does_not_switch_off_generated_hazards"],
    "anchored_hazards_need_route_or_scope": [
        "tests/test_topology_hazard.py:test_anchored_broad_side_effect_hazard_blocks_until_handled",
        "tests/test_topology_hazard.py:test_handled_anchored_hazard_passes"],
}
REQUIRED_LABELS = ("anchor_observed", "anchored_hazard_inferred", "required_route_created", "hazard_handled_or_scoped",
                   "compatibility_disposition_chosen", "full_claim_accepted", "scoped_or_blocked_claim")
BROKEN_LENGTH = {"topology_hazard_unanchored_hard_gate": 1, "topology_hazard_full_without_route": 3,
                 "topology_hazard_compatibility_ignored": 2}


class EffectBlock:
    name = "EffectBlock"
    reads = ("phase",)
    writes = ("saved_record",)
    side_effects = ("database_write",)

    def apply(self, input_obj, state):
        return ()


def _explorer(workflow, length, labels=()):
    return Explorer(workflow=workflow, initial_states=(initial_state(),), external_inputs=EXTERNAL_INPUTS,
                    invariants=INVARIANTS, max_sequence_length=length, terminal_predicate=terminal_predicate,
                    required_labels=labels, progress_steps=0)


def build_explorer() -> Explorer:
    return _explorer(build_correct_workflow(), 4, REQUIRED_LABELS)      # every label is reached within 4 inputs


def broken_variants() -> dict:
    return {workflow.name: _explorer(workflow, BROKEN_LENGTH[workflow.name]) for workflow in build_broken_workflows()}


def _clean_plan() -> TopologyHazardReviewPlan:
    digest = infer_topology_digest(workflow=Workflow((EffectBlock(),), name="effect"), external_inputs=("event",),
                                   usage_intent=UsageIntent(usage_modes=("release",), final_claim="release"))
    edge = digest.edges[0].edge_id
    return TopologyHazardReviewPlan("release", digest=digest, candidates=(TopologyHazardCandidate(
        "hazard:ledger", "Repeated save is recorded in the ledger.", topology_anchor_ids=(edge,),
        disposition=TOPOLOGY_DISPOSITION_TEST_REQUIRED, handled=True),))


def _candidate(hazard_id: str, description: str, *, anchored: bool = True, **values):
    def apply(plan: TopologyHazardReviewPlan) -> TopologyHazardReviewPlan:
        anchors = (plan.digest.edges[0].edge_id,) if anchored else ()
        return replace(plan, candidates=plan.candidates + (
            TopologyHazardCandidate(hazard_id, description, topology_anchor_ids=anchors, **values),))
    return apply


def _ledger_unhandled(plan: TopologyHazardReviewPlan) -> TopologyHazardReviewPlan:
    return replace(plan, candidates=tuple(replace(c, handled=False) if c.hazard_id == "hazard:ledger" else c
                                          for c in plan.candidates))


FEATURES = (
    # Listed anchored hazards replace the generated ones by design, so this one is explored alone.
    Feature("release_hazards_left_to_the_review", True, ("unresolved:generated",),
            lambda plan: replace(plan, candidates=()), exclusive=True),
    Feature("ledger_hazard_not_handled", True, ("unresolved:hazard:ledger",), _ledger_unhandled),
    Feature("retry_hazard_unhandled", True, ("unresolved:hazard:retry",),
            _candidate("hazard:retry", "A retry may write twice.", disposition=TOPOLOGY_DISPOSITION_TEST_REQUIRED)),
    Feature("blocked_hazard", True, ("unresolved:hazard:blocked",),
            _candidate("hazard:blocked", "Release blocked until reviewed.", disposition=TOPOLOGY_DISPOSITION_BLOCKED,
                       severity=TOPOLOGY_SEVERITY_BLOCKER)),
    Feature("unanchored_blocker_warning", False, (),
            _candidate("hazard:generic", "generic warning with no anchor", anchored=False,
                       disposition=TOPOLOGY_DISPOSITION_BLOCKED, confidence_effect=TOPOLOGY_CONFIDENCE_BLOCKED,
                       severity=TOPOLOGY_SEVERITY_BLOCKER)),
    Feature("second_handled_hazard", False, (),
            _candidate("hazard:replay", "Replay is recorded.", disposition=TOPOLOGY_DISPOSITION_TEST_REQUIRED,
                       handled=True)),
)


def _review(plan: TopologyHazardReviewPlan):
    report = review_topology_hazards(plan)
    listed = {candidate.hazard_id for candidate in plan.candidates}
    return report.confidence == TOPOLOGY_CONFIDENCE_FULL, tuple(
        f"unresolved:{hazard}" if hazard in listed else "unresolved:generated" for hazard in report.unresolved_hazard_ids)


def conformance():
    return feature_conformance(FEATURES, _clean_plan, _review)
