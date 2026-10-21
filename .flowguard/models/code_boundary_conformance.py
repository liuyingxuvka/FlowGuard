"""FlowGuard rollout model for code boundary conformance.

Purpose: review the Model-Test Alignment upgrade that checks whether real code
stays inside model-declared input/output boundaries.
Guards against: accepting forbidden inputs, producing undeclared outputs,
writing undeclared state, emitting undeclared side effects, trusting stale or
internal-path-only boundary evidence, and claiming alignment without runtime
boundary observations.

Run:
python -m flowguard map models code_boundary_conformance
"""

from __future__ import annotations

from dataclasses import replace

from flowguard import (
    CodeBoundaryContract,
    CodeBoundaryObservation,
    CodeContract,
    ModelObligation,
    ModelTestAlignmentPlan,
    TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    TEST_ASSERTION_SCOPE_INTERNAL_PATH,
    TestEvidence,
    review_code_boundary_conformance,
    review_model_test_alignment,
)


BOUNDARY = CodeBoundaryContract(
    "checkout.submit.boundary",
    code_contract_id="checkout.submit",
    model_obligation_id="accept_valid_order",
    allowed_inputs=("valid_order",),
    rejected_inputs=("unknown_event",),
    allowed_outputs=("Accepted", "RejectedInvalidInput"),
    allowed_state_writes=("order_status",),
    allowed_side_effects=("publish_accept",),
    allowed_error_paths=("invalid_input",),
)


def _obs(observation_id: str, input_case: str, **overrides: object) -> CodeBoundaryObservation:
    values = {
        "boundary_id": "checkout.submit.boundary",
        "input_case": input_case,
        "accepted": True,
        "observed_output": "Accepted",
        "observed_state_writes": ("order_status",),
        "observed_side_effects": ("publish_accept",),
    }
    values.update(overrides)
    return CodeBoundaryObservation(observation_id, **values)


def good_observations() -> tuple[CodeBoundaryObservation, ...]:
    return (
        _obs("boundary_accept_valid_order", "valid_order"),
        _obs(
            "boundary_reject_unknown_event",
            "unknown_event",
            accepted=False,
            observed_output="RejectedInvalidInput",
            observed_error_path="invalid_input",
            observed_state_writes=(),
            observed_side_effects=(),
        ),
    )


def alignment_plan(observations) -> ModelTestAlignmentPlan:
    """The complete plan: one obligation, its code contract and passing test, the boundary and its observations."""
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(
            ModelObligation(
                "accept_valid_order",
                external_inputs=("order",),
                external_outputs=("Accepted",),
                exact_external_contract=True,
            ),
        ),
        code_contracts=(
            CodeContract(
                "checkout.submit",
                implements_obligations=("accept_valid_order",),
                external_inputs=("order",),
                external_outputs=("Accepted",),
            ),
        ),
        test_evidence=(
            TestEvidence(
                "test_accept_valid_order",
                result_status="passed",
                covered_obligations=("accept_valid_order",),
                covered_code_contracts=("checkout.submit",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
            ),
        ),
        boundary_contracts=(BOUNDARY,),
        boundary_observations=tuple(observations),
    )


# FlowGuard contract (feature kit): each broken boundary observation is a feature that changes the good
# observations; the kit explores every feature alone and every pair, and conformance reviews each
# combination with the real model-test alignment review (which runs the boundary review).
from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants  # noqa: E402

MODEL_ID = "code_boundary_conformance"
COMPONENTS = ["model-test"]
IMPLEMENTED_BY = {"BoundaryReview": "flowguard/model_test_alignment.py:review_code_boundary_conformance",
                  "AlignmentReview": "flowguard/model_test_alignment.py:review_model_test_alignment"}
TESTED_BY = {"each_defect_rejected": [
    "tests/test_code_boundary_conformance.py:test_forbidden_input_acceptance_blocks_boundary_confidence",
    "tests/test_code_boundary_conformance.py:test_exact_boundary_blocks_extra_outputs_and_side_effects"]}
FAILED = "decision:code_boundary_conformance_failed"


def _change(observation_id: str, **values):
    def apply(observations: tuple) -> tuple:
        assert any(item.observation_id == observation_id for item in observations), observation_id
        return tuple(replace(item, **{key: value(item) if callable(value) else value for key, value in values.items()})
                     if item.observation_id == observation_id else item for item in observations)
    return apply


VALID, REJECT = "boundary_accept_valid_order", "boundary_reject_unknown_event"
FEATURES = (
    Feature("forbidden_input_accepted", True, ("boundary_forbidden_input_accepted", FAILED),
            lambda observations: observations + (_obs("boundary_accept_unknown_event", "unknown_event"),)),
    Feature("extra_output", True, ("boundary_extra_output", FAILED), _change(VALID, observed_output="PartialSuccess")),
    Feature("extra_side_effect", True, ("boundary_extra_side_effect", FAILED),
            _change(VALID, observed_side_effects=lambda item: item.observed_side_effects + ("publish_metric",))),
    Feature("missing_rejected_input_evidence", True, ("boundary_missing_rejected_input_evidence", FAILED),
            lambda observations: tuple(item for item in observations if item.observation_id != REJECT)),
    Feature("internal_path_only_observation", True, ("boundary_observation_internal_path_only", FAILED),
            lambda observations: observations + (_obs("boundary_internal_valid_order", "valid_order",
                                                      assertion_scope=TEST_ASSERTION_SCOPE_INTERNAL_PATH),)),
    Feature("repeated_valid_observation", False, (),
            lambda observations: observations + (_obs("boundary_accept_valid_order_again", "valid_order"),)),
)


def build_explorer():
    return feature_explorer(FEATURES)


def broken_variants():
    return feature_variants(FEATURES)


def _review(observations):
    report = review_model_test_alignment(alignment_plan(observations))
    return report.ok, tuple(finding.code for finding in report.findings) + (f"decision:{report.decision}",)


def conformance():
    return feature_conformance(FEATURES, good_observations, _review)
