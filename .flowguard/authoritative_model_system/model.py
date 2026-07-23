"""Executable model for FlowGuard project model-system authority.

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard

Purpose: prove that observed, target, and experimental model systems remain
distinct; that one or many model changes activate atomically against a frozen
base; and that an observed-system rollback cannot move model authority before
the implementation and its effects are restored or compensated.

Modeled block shape: Input x State -> Set(Output x State).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    Scenario,
    ScenarioExpectation,
    Workflow,
)
from flowguard.review import review_scenarios


@dataclass(frozen=True)
class AuthorityCase:
    name: str
    subject_lanes_distinct: bool = True
    one_observed_head: bool = True
    candidate_isolated: bool = True
    authority_derived_from_pointer: bool = True
    finite_coverage_boundary: bool = True
    coverage_set_equality: bool = True
    affected_closure_complete: bool = True
    aggregate_evidence_complete: bool = True
    expected_head_matches: bool = True
    immutable_records_before_pointer: bool = True
    pointer_changes_once: bool = True
    no_partial_member_activation: bool = True
    implementation_effects_restored: bool = True
    old_snapshot_revalidated: bool = True
    irreversible_effect_not_exact_rollback: bool = True
    observed_subject_matches_software: bool = True


@dataclass(frozen=True)
class AuthorityState:
    case_name: str = ""
    subject_lanes_distinct: bool = False
    one_observed_head: bool = False
    candidate_isolated: bool = False
    authority_derived_from_pointer: bool = False
    finite_coverage_boundary: bool = False
    coverage_set_equality: bool = False
    affected_closure_complete: bool = False
    aggregate_evidence_complete: bool = False
    expected_head_matches: bool = False
    immutable_records_before_pointer: bool = False
    pointer_changes_once: bool = False
    no_partial_member_activation: bool = False
    implementation_effects_restored: bool = False
    old_snapshot_revalidated: bool = False
    irreversible_effect_not_exact_rollback: bool = False
    observed_subject_matches_software: bool = False


class EvaluateAuthorityRevision:
    name = "EvaluateAuthorityRevision"
    reads = ("AuthorityState",)
    writes = tuple(AuthorityState.__dataclass_fields__)
    accepted_input_type = AuthorityCase
    input_description = "project model-system authority revision case"
    output_description = "evaluated authority and rollback state"
    idempotency = "same frozen case produces the same authority state"

    def apply(self, input_obj: AuthorityCase, _state: AuthorityState):
        values = {"case_name": input_obj.name}
        values.update(
            {
                field_name: getattr(input_obj, field_name)
                for field_name in AuthorityState.__dataclass_fields__
                if field_name != "case_name"
            }
        )
        state = AuthorityState(**values)
        return (
            FunctionResult(
                output=input_obj,
                new_state=state,
                label=input_obj.name,
                reason="projected revision, activation, and rollback gates",
            ),
        )


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def lanes_and_head_are_unambiguous(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.subject_lanes_distinct:
        return _fail(
            "lanes_and_head_are_unambiguous",
            "observed, target, and experiment subjects are conflated",
        )
    if not state.one_observed_head:
        return _fail(
            "lanes_and_head_are_unambiguous",
            "project has zero or multiple observed implementation heads",
        )
    if not state.authority_derived_from_pointer:
        return _fail(
            "lanes_and_head_are_unambiguous",
            "current authority is inferred from a mutable label or discovery",
        )
    return _pass()


def candidates_never_mutate_observed_authority(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.candidate_isolated:
        return _fail(
            "candidates_never_mutate_observed_authority",
            "candidate construction changed the observed head",
        )
    return _pass()


def coverage_claim_is_finite_set_equality(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.finite_coverage_boundary:
        return _fail(
            "coverage_claim_is_finite_set_equality",
            "coverage claim has no finite fingerprinted universe",
        )
    if not state.coverage_set_equality:
        return _fail(
            "coverage_claim_is_finite_set_equality",
            "required and covered ids are not equal in every dimension",
        )
    return _pass()


def revision_set_closes_as_one_unit(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.affected_closure_complete:
        return _fail(
            "revision_set_closes_as_one_unit",
            "affected parent, sibling, relation, commitment, field, contract, or test is missing",
        )
    if not state.aggregate_evidence_complete:
        return _fail(
            "revision_set_closes_as_one_unit",
            "required revision-set evidence is failed, stale, skipped, or not run",
        )
    if not state.no_partial_member_activation:
        return _fail(
            "revision_set_closes_as_one_unit",
            "one revision-set member activated independently",
        )
    return _pass()


def activation_is_compare_and_swap_pointer_last(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.expected_head_matches:
        return _fail(
            "activation_is_compare_and_swap_pointer_last",
            "observed head drifted after candidate construction",
        )
    if not state.immutable_records_before_pointer:
        return _fail(
            "activation_is_compare_and_swap_pointer_last",
            "candidate, decision, or activation evidence was not persisted first",
        )
    if not state.pointer_changes_once:
        return _fail(
            "activation_is_compare_and_swap_pointer_last",
            "activation exposed a partial or repeated current-head transition",
        )
    return _pass()


def observed_head_matches_real_software(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.observed_subject_matches_software:
        return _fail(
            "observed_head_matches_real_software",
            "observed snapshot does not describe the implemented software revision",
        )
    return _pass()


def rollback_restores_reality_before_authority(
    state: AuthorityState, _trace: object
) -> InvariantResult:
    if not state.case_name:
        return _pass()
    if not state.implementation_effects_restored:
        return _fail(
            "rollback_restores_reality_before_authority",
            "code, configuration, data, or external effects were not restored or compensated",
        )
    if not state.old_snapshot_revalidated:
        return _fail(
            "rollback_restores_reality_before_authority",
            "old observed snapshot was not revalidated after implementation restoration",
        )
    if not state.irreversible_effect_not_exact_rollback:
        return _fail(
            "rollback_restores_reality_before_authority",
            "irreversible effects were mislabeled as exact rollback",
        )
    return _pass()


INVARIANTS = (
    Invariant(
        "lanes_and_head_are_unambiguous",
        "Observed, target, and experiment lanes are distinct and one pointer owns current authority.",
        lanes_and_head_are_unambiguous,
    ),
    Invariant(
        "candidates_never_mutate_observed_authority",
        "Candidate construction cannot mutate the observed implementation head.",
        candidates_never_mutate_observed_authority,
    ),
    Invariant(
        "coverage_claim_is_finite_set_equality",
        "Complete coverage is set equality within a finite fingerprinted boundary.",
        coverage_claim_is_finite_set_equality,
    ),
    Invariant(
        "revision_set_closes_as_one_unit",
        "All affected revision members and evidence close or none activates.",
        revision_set_closes_as_one_unit,
    ),
    Invariant(
        "activation_is_compare_and_swap_pointer_last",
        "Activation validates the expected head and writes the pointer last once.",
        activation_is_compare_and_swap_pointer_last,
    ),
    Invariant(
        "observed_head_matches_real_software",
        "The observed snapshot identifies the real implemented software revision.",
        observed_head_matches_real_software,
    ),
    Invariant(
        "rollback_restores_reality_before_authority",
        "Operational rollback restores or compensates reality and revalidates it before moving authority.",
        rollback_restores_reality_before_authority,
    ),
)


def _expect_ok(summary: str) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="ok",
        required_trace_labels=("complete_authority_transaction",),
        summary=summary,
    )


def _expect_violation(name: str, summary: str) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=(name,),
        summary=summary,
    )


def _scenario(
    name: str,
    description: str,
    case: AuthorityCase,
    expected: ScenarioExpectation,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        workflow=Workflow(
            (EvaluateAuthorityRevision(),),
            name="authoritative_model_system_revision",
        ),
        initial_state=AuthorityState(),
        external_input_sequence=(case,),
        invariants=INVARIANTS,
        expected=expected,
    )


GOOD = AuthorityCase("complete_authority_transaction")
SCENARIOS = (
    _scenario(
        "complete_transaction_passes",
        "A bounded, evidence-complete multi-model activation and return path passes.",
        GOOD,
        _expect_ok("complete model-system transaction passes"),
    ),
    _scenario(
        "target_cannot_be_current_by_label",
        "A mutable current label cannot make a target authoritative.",
        AuthorityCase(
            "target_current_by_label",
            authority_derived_from_pointer=False,
        ),
        _expect_violation(
            "lanes_and_head_are_unambiguous",
            "mutable current label is rejected",
        ),
    ),
    _scenario(
        "candidate_isolation_required",
        "Experiment construction cannot mutate the observed head.",
        AuthorityCase("candidate_mutates_observed", candidate_isolated=False),
        _expect_violation(
            "candidates_never_mutate_observed_authority",
            "candidate mutation is rejected",
        ),
    ),
    _scenario(
        "unbounded_full_coverage_rejected",
        "Full coverage without a finite universe is invalid.",
        AuthorityCase("unbounded_coverage", finite_coverage_boundary=False),
        _expect_violation(
            "coverage_claim_is_finite_set_equality",
            "unbounded coverage is rejected",
        ),
    ),
    _scenario(
        "partial_multi_model_activation_rejected",
        "A passing member cannot activate independently.",
        AuthorityCase(
            "partial_member_activation",
            no_partial_member_activation=False,
        ),
        _expect_violation(
            "revision_set_closes_as_one_unit",
            "partial activation is rejected",
        ),
    ),
    _scenario(
        "affected_sibling_must_close",
        "A relation change must include affected siblings and evidence.",
        AuthorityCase(
            "missing_affected_sibling",
            affected_closure_complete=False,
        ),
        _expect_violation(
            "revision_set_closes_as_one_unit",
            "incomplete affected closure is rejected",
        ),
    ),
    _scenario(
        "stale_base_blocks_activation",
        "A candidate based on an older observed head cannot activate.",
        AuthorityCase("stale_base", expected_head_matches=False),
        _expect_violation(
            "activation_is_compare_and_swap_pointer_last",
            "stale-base activation is rejected",
        ),
    ),
    _scenario(
        "pointer_first_crash_is_rejected",
        "The current pointer cannot move before immutable evidence exists.",
        AuthorityCase(
            "pointer_before_receipts",
            immutable_records_before_pointer=False,
        ),
        _expect_violation(
            "activation_is_compare_and_swap_pointer_last",
            "pointer-first activation is rejected",
        ),
    ),
    _scenario(
        "observed_snapshot_must_match_implementation",
        "A target snapshot cannot masquerade as observed after code remains old.",
        AuthorityCase(
            "observed_subject_mismatch",
            observed_subject_matches_software=False,
        ),
        _expect_violation(
            "observed_head_matches_real_software",
            "observed subject mismatch is rejected",
        ),
    ),
    _scenario(
        "pointer_only_operational_rollback_rejected",
        "Model authority cannot roll back while implementation effects remain new.",
        AuthorityCase(
            "pointer_only_rollback",
            implementation_effects_restored=False,
        ),
        _expect_violation(
            "rollback_restores_reality_before_authority",
            "pointer-only rollback is rejected",
        ),
    ),
    _scenario(
        "irreversible_effect_needs_forward_repair",
        "Irreversible effects cannot be called an exact rollback.",
        AuthorityCase(
            "irreversible_exact_rollback_claim",
            irreversible_effect_not_exact_rollback=False,
        ),
        _expect_violation(
            "rollback_restores_reality_before_authority",
            "false exact rollback is rejected",
        ),
    ),
)


def run_review():
    return review_scenarios(SCENARIOS)


if __name__ == "__main__":
    report = run_review()
    print(report.format_text())
    raise SystemExit(0 if report.ok else 1)
