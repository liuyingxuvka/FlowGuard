"""FlowGuard rollout model for code boundary conformance.

Risk Purpose Header:
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the Model-Test Alignment upgrade that checks whether real code
stays inside model-declared input/output boundaries.
Guards against: accepting forbidden inputs, producing undeclared outputs,
writing undeclared state, emitting undeclared side effects, trusting stale or
internal-path-only boundary evidence, and claiming alignment without runtime
boundary observations.

Run:
python .flowguard/code_boundary_conformance/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True)
class BoundaryCase:
    name: str
    report_ok: bool
    expected_codes: tuple[str, ...] = ()
    alignment_case: bool = False


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


def boundary_reports() -> tuple[tuple[str, object, bool, tuple[str, ...]], ...]:
    cases = (
        (
            "green_boundary",
            review_code_boundary_conformance((BOUNDARY,), good_observations()),
            True,
            (),
        ),
        (
            "forbidden_input_accepted",
            review_code_boundary_conformance(
                (BOUNDARY,),
                (
                    _obs("boundary_accept_valid_order", "valid_order"),
                    _obs("boundary_accept_unknown_event", "unknown_event"),
                ),
            ),
            False,
            ("boundary_forbidden_input_accepted",),
        ),
        (
            "extra_output_and_side_effect",
            review_code_boundary_conformance(
                (
                    CodeBoundaryContract(
                        **{
                            **BOUNDARY.to_dict(),
                            "allowed_outputs": ("Accepted",),
                            "allowed_side_effects": (),
                        }
                    ),
                ),
                (
                    _obs(
                        "boundary_accept_valid_order",
                        "valid_order",
                        observed_output="PartialSuccess",
                        observed_side_effects=("publish_accept", "publish_metric"),
                    ),
                    good_observations()[1],
                ),
            ),
            False,
            ("boundary_extra_output", "boundary_extra_side_effect"),
        ),
        (
            "missing_rejected_input_gate_evidence",
            review_code_boundary_conformance((BOUNDARY,), (_obs("boundary_accept_valid_order", "valid_order"),)),
            False,
            ("boundary_missing_rejected_input_evidence",),
        ),
        (
            "internal_path_only_boundary_observation",
            review_code_boundary_conformance(
                (BOUNDARY,),
                (
                    _obs("boundary_accept_valid_order", "valid_order"),
                    _obs(
                        "boundary_reject_unknown_event",
                        "unknown_event",
                        accepted=False,
                        observed_output="RejectedInvalidInput",
                        observed_error_path="invalid_input",
                        observed_state_writes=(),
                        observed_side_effects=(),
                        assertion_scope=TEST_ASSERTION_SCOPE_INTERNAL_PATH,
                    ),
                ),
            ),
            False,
            ("boundary_observation_internal_path_only",),
        ),
    )
    return cases


def alignment_report():
    plan = ModelTestAlignmentPlan(
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
        boundary_observations=(
            _obs("boundary_accept_valid_order", "valid_order", observed_output="AcceptedAndCached"),
            good_observations()[1],
        ),
    )
    return review_model_test_alignment(plan)


def run_rollout_review() -> tuple[tuple[str, bool, tuple[str, ...]], ...]:
    results: list[tuple[str, bool, tuple[str, ...]]] = []
    for name, report, expected_ok, expected_codes in boundary_reports():
        codes = tuple(finding.code for finding in report.findings)
        results.append((name, report.ok is expected_ok and all(code in codes for code in expected_codes), codes))

    report = alignment_report()
    codes = tuple(finding.code for finding in report.findings)
    results.append(
        (
            "alignment_blocks_on_boundary_failure",
            not report.ok and report.decision == "code_boundary_conformance_failed" and "boundary_extra_output" in codes,
            codes,
        )
    )
    return tuple(results)


__all__ = ["run_rollout_review"]
