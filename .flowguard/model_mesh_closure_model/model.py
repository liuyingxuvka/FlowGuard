"""Finite model-of-models for FlowGuard whole-system understanding closure.

This model keeps child state graphs opaque.  It models only the typed transfers
that a whole-FlowGuard understanding claim must close:

request facts -> owner demand -> semantic model mesh -> verified maturation ->
implementation admission -> risk decision -> terminal closure.

Modeled block shape: Input x State -> Set(Output x State).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import FrozenSet, Tuple

from flowguard import FunctionBlock, FunctionResult, Invariant


REQUIRED_TOKENS = frozenset(
    {
        "task_facts",
        "owner_resolutions",
        "semantic_model_mesh",
        "verified_maturation",
        "implementation_admission",
        "risk_decision",
    }
)


@dataclass(frozen=True)
class ClosureInput:
    token: str
    observed_snapshot_fingerprint: str = "sha256:current-observed-model-system"
    semantic_derivation_fingerprint: str = "sha256:current-observed-model-system"
    semantic_universe_fingerprint: str = "sha256:current-semantic-universe"
    semantic_disposition_fingerprint: str = "sha256:current-semantic-dispositions"
    semantic_relation_fingerprint: str = "sha256:current-semantic-relations"
    semantic_mesh_fingerprint: str = "sha256:current-semantic-self-mesh"
    semantic_gap_ids: tuple[str, ...] = ()
    evidence_status: str = "terminal_verified"
    evidence_identity_current: bool = True


@dataclass(frozen=True)
class ClosureState:
    produced: FrozenSet[str] = frozenset()
    consumed: FrozenSet[str] = frozenset()
    required: FrozenSet[str] = REQUIRED_TOKENS
    semantic_mesh_complete: bool = False
    maturation_verified: bool = False
    admission_separate: bool = False
    risk_current: bool = False
    terminal: bool = False
    normal_exit: bool = False
    violations: Tuple[str, ...] = ()

    @property
    def pending(self) -> FrozenSet[str]:
        return frozenset(self.required - self.consumed)


def _advance(
    input_value: ClosureInput,
    state: ClosureState,
    *,
    expected: str,
    emitted: str,
    label: str,
    **changes,
) -> tuple[FunctionResult, ...]:
    if input_value.token != expected:
        return (FunctionResult(input_value, state),)
    return (
        FunctionResult(
            replace(input_value, token=emitted),
            replace(
                state,
                produced=state.produced | {emitted},
                consumed=state.consumed | {expected},
                **changes,
            ),
            label=label,
        ),
    )


class StartUnderstanding(FunctionBlock):
    name = "StartUnderstanding"
    accepted_input_type = ClosureInput

    def apply(self, input_value, state):
        if input_value.token != "root_start":
            return (FunctionResult(input_value, state),)
        return (
            FunctionResult(
                replace(input_value, token="task_facts"),
                replace(state, produced=state.produced | {"task_facts"}),
                label="task_facts_observed",
            ),
        )


class CompileOwnerDemand(FunctionBlock):
    name = "CompileOwnerDemand"
    accepted_input_type = ClosureInput

    def apply(self, input_value, state):
        return _advance(
            input_value,
            state,
            expected="task_facts",
            emitted="owner_resolutions",
            label="owner_demand_resolved",
        )


class JoinSemanticModelMesh(FunctionBlock):
    name = "JoinSemanticModelMesh"
    accepted_input_type = ClosureInput

    def apply(self, input_value, state):
        if input_value.token != "owner_resolutions":
            return (FunctionResult(input_value, state),)
        violations = list(state.violations)
        if (
            not input_value.observed_snapshot_fingerprint.startswith("sha256:")
            or input_value.semantic_derivation_fingerprint
            != input_value.observed_snapshot_fingerprint
            or not input_value.semantic_universe_fingerprint.startswith("sha256:")
        ):
            violations.append("semantic_universe_not_exact")
        if (
            not input_value.semantic_disposition_fingerprint.startswith("sha256:")
            or not input_value.semantic_relation_fingerprint.startswith("sha256:")
        ):
            violations.append("semantic_relations_incomplete")
        if not input_value.semantic_mesh_fingerprint.startswith("sha256:"):
            violations.append("semantic_mesh_fingerprint_empty")
        if input_value.semantic_gap_ids:
            violations.append("semantic_gaps_open")
        complete = not violations
        emitted = "semantic_model_mesh" if complete else "semantic_model_mesh_rejected"
        return (
            FunctionResult(
                replace(input_value, token=emitted),
                replace(
                    state,
                    produced=state.produced | {emitted},
                    consumed=state.consumed | {"owner_resolutions"},
                    semantic_mesh_complete=complete,
                    violations=tuple(violations),
                ),
                label=emitted,
            ),
        )


class VerifyMaturation(FunctionBlock):
    name = "VerifyMaturation"
    accepted_input_type = ClosureInput

    def apply(self, input_value, state):
        if input_value.token != "semantic_model_mesh":
            return (FunctionResult(input_value, state),)
        verified = (
            state.semantic_mesh_complete
            and input_value.evidence_status == "terminal_verified"
            and input_value.evidence_identity_current
        )
        emitted = "verified_maturation" if verified else "maturation_evidence_rejected"
        violations = state.violations
        if not verified:
            violations = violations + ("maturation_evidence_not_current_terminal",)
        return (
            FunctionResult(
                replace(input_value, token=emitted),
                replace(
                    state,
                    produced=state.produced | {emitted},
                    consumed=state.consumed | {"semantic_model_mesh"},
                    maturation_verified=verified,
                    violations=violations,
                ),
                label=emitted,
            ),
        )


class DecideImplementationAdmission(FunctionBlock):
    name = "DecideImplementationAdmission"
    accepted_input_type = ClosureInput

    def apply(self, input_value, state):
        return _advance(
            input_value,
            state,
            expected="verified_maturation",
            emitted="implementation_admission",
            label="implementation_admission_separate",
            admission_separate=True,
        )


class DecideRisk(FunctionBlock):
    name = "DecideRisk"
    accepted_input_type = ClosureInput

    def apply(self, input_value, state):
        return _advance(
            input_value,
            state,
            expected="implementation_admission",
            emitted="risk_decision",
            label="risk_decision_current",
            risk_current=True,
        )


class FinishUnderstanding(FunctionBlock):
    name = "FinishUnderstanding"
    accepted_input_type = ClosureInput

    def apply(self, input_value, state):
        if input_value.token != "risk_decision":
            return (FunctionResult(input_value, state),)
        next_state = replace(
            state,
            consumed=state.consumed | {"risk_decision"},
            terminal=True,
            normal_exit=True,
        )
        return (
            FunctionResult(
                replace(input_value, token="understanding_closed"),
                next_state,
                label="understanding_closed",
            ),
        )


def closure_invariant(state, _trace):
    if state.violations:
        return False
    if state.terminal:
        return (
            state.normal_exit
            and state.semantic_mesh_complete
            and state.maturation_verified
            and state.admission_separate
            and state.risk_current
            and not state.pending
        )
    return True


def build_blocks():
    return (
        StartUnderstanding(),
        CompileOwnerDemand(),
        JoinSemanticModelMesh(),
        VerifyMaturation(),
        DecideImplementationAdmission(),
        DecideRisk(),
        FinishUnderstanding(),
    )


invariants = (
    Invariant(
        "whole_system_understanding_closure_is_semantic_and_terminal",
        "Whole-system closure consumes the exact semantic universe and current terminal evidence without pending transfers.",
        closure_invariant,
    ),
)


def initial_state() -> ClosureState:
    return ClosureState()


def external_inputs():
    return (ClosureInput("root_start"),)


terminal_predicate = lambda current_output, state, trace: bool(state.terminal)
