"""FlowGuard rollout model for lightweight post-runtime model-miss review.

Risk Purpose Header:
This FlowGuard model reviews the `model-first-function-flow` Skill update for
post-runtime model-miss review. It guards against point-fix-only model repairs,
over-detailed formal miss categories, and turning ordinary model misses into a
new registry/reviewer/mesh-heavy process. Future agents should run or update
this model before changing the lightweight model-miss workflow.

Run:
python examples/lightweight_model_miss_review/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from flowguard import FunctionResult, Invariant, InvariantResult, Scenario, ScenarioExpectation, Workflow
from flowguard.review import review_scenarios


ALLOWED_MISS_TYPES = {
    "boundary_missing",
    "state_too_coarse",
    "input_branch_missing",
    "invariant_too_weak",
    "evidence_overclaimed",
}


@dataclass(frozen=True)
class ReviewCase:
    name: str
    miss_type: str
    in_modeled_scope: bool = True
    observed_issue_represented: bool = True
    generalized_case_added: bool = True
    generalized_case_omitted_reason: str = ""
    requires_hazard_registry: bool = False
    requires_upgrade_reviewer: bool = False
    requires_default_model_mesh: bool = False
    requires_full_coverage_matrix: bool = False
    requires_evidence_level_field: bool = False


@dataclass(frozen=True)
class ReviewState:
    case_name: str = ""
    miss_type: str = ""
    in_modeled_scope: bool = True
    observed_issue_represented: bool = False
    generalized_case_added: bool = False
    generalized_case_omitted_reason: str = ""
    requires_hazard_registry: bool = False
    requires_upgrade_reviewer: bool = False
    requires_default_model_mesh: bool = False
    requires_full_coverage_matrix: bool = False
    requires_evidence_level_field: bool = False


GOOD_IN_SCOPE = ReviewCase(
    "good_in_scope_same_class_case",
    "state_too_coarse",
    observed_issue_represented=True,
    generalized_case_added=True,
)
GOOD_OUT_OF_SCOPE = ReviewCase(
    "good_out_of_scope_reason",
    "boundary_missing",
    in_modeled_scope=False,
    observed_issue_represented=False,
    generalized_case_added=False,
    generalized_case_omitted_reason="outside modeled boundary",
)
BROKEN_POINT_FIX_ONLY = ReviewCase(
    "broken_point_fix_only",
    "invariant_too_weak",
    observed_issue_represented=True,
    generalized_case_added=False,
)
BROKEN_DETAILED_CATEGORY = ReviewCase(
    "broken_old_detailed_category",
    "wrong_oracle",
    observed_issue_represented=True,
    generalized_case_added=True,
)
BROKEN_HEAVY_DEFAULTS = ReviewCase(
    "broken_heavy_defaults",
    "evidence_overclaimed",
    observed_issue_represented=True,
    generalized_case_added=True,
    requires_hazard_registry=True,
    requires_upgrade_reviewer=True,
    requires_default_model_mesh=True,
    requires_full_coverage_matrix=True,
    requires_evidence_level_field=True,
)
BROKEN_NO_OBSERVED_REPRESENTATION = ReviewCase(
    "broken_no_observed_representation",
    "input_branch_missing",
    observed_issue_represented=False,
    generalized_case_added=True,
)


class EvaluateModelMissReview:
    name = "EvaluateModelMissReview"
    reads = ("case_name",)
    writes = (
        "case_name",
        "miss_type",
        "in_modeled_scope",
        "observed_issue_represented",
        "generalized_case_added",
        "generalized_case_omitted_reason",
        "requires_hazard_registry",
        "requires_upgrade_reviewer",
        "requires_default_model_mesh",
        "requires_full_coverage_matrix",
        "requires_evidence_level_field",
    )
    accepted_input_type = ReviewCase
    input_description = "post-runtime model-miss review case"
    output_description = "review policy state"
    idempotency = "same case produces one policy state"

    def apply(self, input_obj: ReviewCase, _state: ReviewState):
        new_state = ReviewState(
            case_name=input_obj.name,
            miss_type=input_obj.miss_type,
            in_modeled_scope=input_obj.in_modeled_scope,
            observed_issue_represented=input_obj.observed_issue_represented,
            generalized_case_added=input_obj.generalized_case_added,
            generalized_case_omitted_reason=input_obj.generalized_case_omitted_reason,
            requires_hazard_registry=input_obj.requires_hazard_registry,
            requires_upgrade_reviewer=input_obj.requires_upgrade_reviewer,
            requires_default_model_mesh=input_obj.requires_default_model_mesh,
            requires_full_coverage_matrix=input_obj.requires_full_coverage_matrix,
            requires_evidence_level_field=input_obj.requires_evidence_level_field,
        )
        return (
            FunctionResult(
                output=input_obj,
                new_state=new_state,
                label=input_obj.name,
                reason="review case projected into the lightweight workflow contract",
            ),
        )


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def miss_type_is_one_of_five(state: ReviewState, _trace: object) -> InvariantResult:
    if not state.case_name:
        return InvariantResult.pass_()
    if state.miss_type not in ALLOWED_MISS_TYPES:
        return _fail(
            "miss_type_is_one_of_five",
            f"unexpected formal model-miss category: {state.miss_type!r}",
        )
    return InvariantResult.pass_()


def observed_issue_is_represented_or_out_of_scope(state: ReviewState, _trace: object) -> InvariantResult:
    if not state.case_name:
        return InvariantResult.pass_()
    if state.in_modeled_scope and not state.observed_issue_represented:
        return _fail(
            "observed_issue_is_represented_or_out_of_scope",
            "in-scope model miss did not represent the observed issue",
        )
    return InvariantResult.pass_()


def in_scope_miss_gets_same_class_case(state: ReviewState, _trace: object) -> InvariantResult:
    if not state.case_name:
        return InvariantResult.pass_()
    if state.in_modeled_scope and not state.generalized_case_added:
        return _fail(
            "in_scope_miss_gets_same_class_case",
            "in-scope model miss only patched the observed case",
        )
    if not state.in_modeled_scope and not state.generalized_case_added:
        if not state.generalized_case_omitted_reason:
            return _fail(
                "in_scope_miss_gets_same_class_case",
                "omitted generalized case without a reason",
            )
    return InvariantResult.pass_()


def ordinary_miss_avoids_heavy_defaults(state: ReviewState, _trace: object) -> InvariantResult:
    if not state.case_name:
        return InvariantResult.pass_()
    heavy_defaults = (
        state.requires_hazard_registry,
        state.requires_upgrade_reviewer,
        state.requires_default_model_mesh,
        state.requires_full_coverage_matrix,
        state.requires_evidence_level_field,
    )
    if any(heavy_defaults):
        return _fail(
            "ordinary_miss_avoids_heavy_defaults",
            "ordinary model-miss review introduced heavyweight default process",
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "miss_type_is_one_of_five",
        "Post-runtime model misses use five practical daily categories.",
        miss_type_is_one_of_five,
    ),
    Invariant(
        "observed_issue_is_represented_or_out_of_scope",
        "In-scope model misses still represent the observed issue.",
        observed_issue_is_represented_or_out_of_scope,
    ),
    Invariant(
        "in_scope_miss_gets_same_class_case",
        "In-scope model misses add one same-class generalized bad case when practical.",
        in_scope_miss_gets_same_class_case,
    ),
    Invariant(
        "ordinary_miss_avoids_heavy_defaults",
        "Ordinary model-miss review stays lightweight.",
        ordinary_miss_avoids_heavy_defaults,
    ),
)


def build_workflow() -> Workflow:
    return Workflow((EvaluateModelMissReview(),), name="lightweight_model_miss_review")


def _expect_ok(summary: str, labels: Sequence[str] = ()) -> ScenarioExpectation:
    return ScenarioExpectation(expected_status="ok", required_trace_labels=tuple(labels), summary=summary)


def _expect_violation(summary: str, names: Sequence[str]) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=tuple(names),
        summary=summary,
    )


def scenario(
    name: str,
    description: str,
    case: ReviewCase,
    expected: ScenarioExpectation,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        initial_state=ReviewState(),
        external_input_sequence=(case,),
        expected=expected,
        workflow=build_workflow(),
        invariants=INVARIANTS,
    )


def scenarios() -> tuple[Scenario, ...]:
    return (
        scenario(
            "LMR01_in_scope_adds_same_class_case",
            "In-scope misses keep the observed case and add one generalized bad case.",
            GOOD_IN_SCOPE,
            _expect_ok("OK; in-scope miss has observed and same-class evidence", (GOOD_IN_SCOPE.name,)),
        ),
        scenario(
            "LMR02_out_of_scope_records_reason",
            "Out-of-scope misses can omit the generalized case with a reason.",
            GOOD_OUT_OF_SCOPE,
            _expect_ok("OK; out-of-scope miss recorded reason", (GOOD_OUT_OF_SCOPE.name,)),
        ),
        scenario(
            "LMB01_point_fix_only_fails",
            "Broken repair only patches the observed case.",
            BROKEN_POINT_FIX_ONLY,
            _expect_violation(
                "VIOLATION in_scope_miss_gets_same_class_case",
                ("in_scope_miss_gets_same_class_case",),
            ),
        ),
        scenario(
            "LMB02_old_detailed_category_fails",
            "Broken repair keeps old detailed categories as formal daily types.",
            BROKEN_DETAILED_CATEGORY,
            _expect_violation("VIOLATION miss_type_is_one_of_five", ("miss_type_is_one_of_five",)),
        ),
        scenario(
            "LMB03_heavy_defaults_fail",
            "Broken repair turns ordinary model misses into heavyweight default process.",
            BROKEN_HEAVY_DEFAULTS,
            _expect_violation(
                "VIOLATION ordinary_miss_avoids_heavy_defaults",
                ("ordinary_miss_avoids_heavy_defaults",),
            ),
        ),
        scenario(
            "LMB04_missing_observed_issue_fails",
            "Broken repair adds a generalized case but loses the observed in-scope issue.",
            BROKEN_NO_OBSERVED_REPRESENTATION,
            _expect_violation(
                "VIOLATION observed_issue_is_represented_or_out_of_scope",
                ("observed_issue_is_represented_or_out_of_scope",),
            ),
        ),
    )


def run_review():
    return review_scenarios(scenarios())


__all__ = ["run_review", "scenarios"]
