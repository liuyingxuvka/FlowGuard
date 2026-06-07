"""Template text for FlowGuard model test alignment route."""

from __future__ import annotations

MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Reviews whether explicit FlowGuard model obligations, owner code external
contracts, and ordinary test evidence describe the same behavioral surface.

Guards against:
- model scenarios, invariants, hazards, or transitions with no test evidence;
- model state transitions that were never projected into testable matrix cells;
- model obligations with no code external contract owner;
- code functions or entrypoints that miss model-declared external behavior;
- code functions or entrypoints that add model-forbidden external behavior;
- tests that are not bound to any model obligation;
- tests that are not bound to the code contract they are meant to prove;
- tests that inspect only internal paths while claiming external contract proof;
- open finite boundaries with no representative unknown/other cases;
- unknown inputs accepted as normal flow or causing side effects before closure;
- duplicate tests claiming the same model obligation without clear intent;
- risky model paths covered only by happy-path tests;
- model-miss repairs that only test the observed bug without same-class evidence;
- behavior-bearing field lifecycle projections with no model obligation,
  owner code contract, or external-contract test evidence;
- old or replaced field behavior with no current disposition evidence;
- stale, skipped, failed, timeout, not-run, or overclaiming test evidence.

Use before editing:
test coverage claims, model confidence reports, model-backed feature work, or
release notes that claim model and test coverage agree.

Run:
python .flowguard/model_test_alignment/run_checks.py

This template does not use TestMesh, StructureMesh, or ModelMesh. It compares
plain model obligations, required owner code external contracts, and plain test
evidence. If one obligation has several primary edge-path tests, split child
obligations or attach those tests to leaf matrix cells instead of relabeling one
as generic support.
"""

from __future__ import annotations

from flowguard import (
    CodeBoundaryContract,
    CodeBoundaryObservation,
    CodeContract,
    ModelObligation,
    ModelTestAlignmentPlan,
    ProofArtifactRef,
    RuntimeNodeObservation,
    TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    TEST_ASSERTION_SCOPE_INTERNAL_PATH,
    TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
    TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED,
    TEST_EVIDENCE_ROLE_TRANSITION_CELL,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    TestResultReuseTicket,
    TestEvidence,
    TransitionCoverageCell,
    TransitionCoverageMatrix,
    audit_python_code_contracts,
    audit_python_test_assertions,
    review_code_boundary_conformance,
    review_python_contract_source_audit,
    review_model_test_alignment,
    transition_coverage_to_code_contracts,
    transition_coverage_to_model_obligations,
    transition_obligation_id,
)


ACCEPT_TRANSITION_CELL_ID = "pending.submit->accepted"
ACCEPT_TRANSITION_OBLIGATION_ID = transition_obligation_id(ACCEPT_TRANSITION_CELL_ID)


def proof_artifact(evidence_id: str, *covered: str) -> ProofArtifactRef:
    result_path = f"tmp/{evidence_id}.json"
    return ProofArtifactRef(
        f"artifact:{evidence_id}",
        result_status="passed",
        exit_code=0,
        result_path=result_path,
        artifact_fingerprints={result_path: "sha256:template"},
        covered_obligation_ids=covered,
    )


def reuse_ticket(evidence_id: str, *covered: str) -> TestResultReuseTicket:
    return TestResultReuseTicket(
        evidence_id,
        previous_evidence_id=f"{evidence_id}@previous",
        reason="same command, source, tested artifact, dependency, environment, and result fingerprints",
        command_fingerprint="sha256:command",
        test_source_fingerprint="sha256:test-source",
        tested_artifact_fingerprint="sha256:tested-artifact",
        dependency_fingerprints={"flowguard": "template"},
        environment_fingerprint="python:template",
        result_fingerprint="sha256:result",
        covered_obligation_ids=covered,
    )


def transition_matrix() -> TransitionCoverageMatrix:
    return TransitionCoverageMatrix(
        "sample_checkout_transition_matrix",
        model_id="sample_checkout_model",
        cells=(
            TransitionCoverageCell(
                ACCEPT_TRANSITION_CELL_ID,
                source_state="pending",
                trigger="submit_valid_order",
                target_state="accepted",
                expected_output="Accepted",
                function_block="accept_order_transition",
                code_contract_id="checkout_accept_transition",
                runtime_node_id="checkout.accept_transition",
                required_test_kinds=(TEST_KIND_HAPPY_PATH,),
                rationale="Submitting a valid pending order reaches the accepted state.",
            ),
        ),
    )


def transition_code_contracts() -> tuple[CodeContract, ...]:
    projected = transition_coverage_to_code_contracts(transition_matrix())
    return tuple(
        CodeContract(
            contract.code_contract_id,
            path="checkout/service.py",
            symbol=contract.symbol,
            implements_obligations=contract.implements_obligations,
            external_inputs=contract.external_inputs,
            external_outputs=contract.external_outputs,
            state_reads=contract.state_reads,
            state_writes=contract.state_writes,
            side_effects=contract.side_effects,
        )
        for contract in projected
    )


def aligned_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="sample_checkout_model",
        require_proof_artifacts=True,
        obligations=(
            ModelObligation(
                "accept_valid_order",
                obligation_type="scenario",
                description="valid order reaches Accepted",
                external_inputs=("order_id", "payment_token"),
                external_outputs=("Accepted",),
                state_writes=("order_status",),
                required_test_kinds=(TEST_KIND_HAPPY_PATH,),
            ),
            ModelObligation(
                "reject_duplicate_order",
                obligation_type="hazard",
                description="duplicate order is rejected without a second side effect",
                external_inputs=("order_id",),
                external_outputs=("Rejected",),
                state_reads=("order_status",),
                side_effects=(),
                error_paths=("duplicate_order",),
                exact_external_contract=True,
                required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
            ),
            ModelObligation(
                "model_miss_duplicate_submit_family",
                obligation_type="model_miss",
                description="post-runtime duplicate-submit miss is closed by observed and same-class tests",
                model_miss_origin=True,
                requires_same_class_test_evidence=True,
                required_test_kinds=(TEST_KIND_HAPPY_PATH,),
            ),
            *transition_coverage_to_model_obligations(transition_matrix()),
        ),
        code_contracts=(
            CodeContract(
                "checkout_accept_order",
                path="checkout/service.py",
                symbol="accept_order",
                implements_obligations=("accept_valid_order",),
                external_inputs=("order_id", "payment_token"),
                external_outputs=("Accepted",),
                state_writes=("order_status",),
            ),
            *transition_code_contracts(),
            CodeContract(
                "checkout_reject_duplicate",
                path="checkout/service.py",
                symbol="reject_duplicate_order",
                implements_obligations=("reject_duplicate_order",),
                external_inputs=("order_id",),
                external_outputs=("Rejected",),
                state_reads=("order_status",),
                error_paths=("duplicate_order",),
            ),
            CodeContract(
                "checkout_duplicate_submit_family",
                path="checkout/service.py",
                symbol="reject_duplicate_order",
                implements_obligations=("model_miss_duplicate_submit_family",),
                external_inputs=("order_id",),
                external_outputs=("Rejected",),
                error_paths=("duplicate_order",),
            ),
        ),
        test_evidence=(
            TestEvidence(
                "test_accept_valid_order",
                test_name="test_accept_valid_order",
                path="tests/test_checkout.py",
                result_status="passed",
                test_kind=TEST_KIND_HAPPY_PATH,
                covered_obligations=("accept_valid_order",),
                covered_code_contracts=("checkout_accept_order",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                result_reused=True,
                reuse_ticket=reuse_ticket("test_accept_valid_order", "accept_valid_order"),
                proof_artifact=proof_artifact("test_accept_valid_order", "accept_valid_order"),
            ),
            TestEvidence(
                "test_pending_submit_reaches_accepted",
                test_name="test_pending_submit_reaches_accepted",
                path="tests/test_checkout.py",
                result_status="passed",
                test_kind=TEST_KIND_HAPPY_PATH,
                covered_obligations=(ACCEPT_TRANSITION_OBLIGATION_ID,),
                covered_code_contracts=("checkout_accept_transition",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                evidence_role=TEST_EVIDENCE_ROLE_TRANSITION_CELL,
                evidence_target_id=ACCEPT_TRANSITION_CELL_ID,
                proof_artifact=proof_artifact(
                    "test_pending_submit_reaches_accepted",
                    ACCEPT_TRANSITION_OBLIGATION_ID,
                ),
            ),
            TestEvidence(
                "test_reject_duplicate_order_happy",
                test_name="test_reject_duplicate_order_happy",
                path="tests/test_checkout.py",
                result_status="passed",
                test_kind=TEST_KIND_HAPPY_PATH,
                covered_obligations=("reject_duplicate_order",),
                covered_code_contracts=("checkout_reject_duplicate",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                proof_artifact=proof_artifact(
                    "test_reject_duplicate_order_happy",
                    "reject_duplicate_order",
                ),
            ),
            TestEvidence(
                "test_reject_duplicate_order_failure",
                test_name="test_reject_duplicate_order_failure",
                path="tests/test_checkout.py",
                result_status="passed",
                test_kind=TEST_KIND_FAILURE_PATH,
                covered_obligations=("reject_duplicate_order",),
                covered_code_contracts=("checkout_reject_duplicate",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                proof_artifact=proof_artifact(
                    "test_reject_duplicate_order_failure",
                    "reject_duplicate_order",
                ),
            ),
            TestEvidence(
                "test_observed_duplicate_submit_regression",
                test_name="test_observed_duplicate_submit_regression",
                path="tests/test_checkout.py",
                result_status="passed",
                test_kind=TEST_KIND_HAPPY_PATH,
                covered_obligations=("model_miss_duplicate_submit_family",),
                covered_code_contracts=("checkout_duplicate_submit_family",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                closure_evidence_role=TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
                proof_artifact=proof_artifact(
                    "test_observed_duplicate_submit_regression",
                    "model_miss_duplicate_submit_family",
                ),
            ),
            TestEvidence(
                "test_same_class_duplicate_submit_variants",
                test_name="test_same_class_duplicate_submit_variants",
                path="tests/test_checkout.py",
                result_status="passed",
                test_kind=TEST_KIND_HAPPY_PATH,
                covered_obligations=("model_miss_duplicate_submit_family",),
                covered_code_contracts=("checkout_duplicate_submit_family",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                closure_evidence_role=TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED,
                proof_artifact=proof_artifact(
                    "test_same_class_duplicate_submit_variants",
                    "model_miss_duplicate_submit_family",
                ),
            ),
        ),
        runtime_node_observations=(
            RuntimeNodeObservation(
                "obs:checkout.accept_transition",
                "checkout.accept_transition",
                model_id="sample_checkout_model",
                model_obligation_id=ACCEPT_TRANSITION_OBLIGATION_ID,
                code_contract_id="checkout_accept_transition",
                observed_output="Accepted",
                proof_artifact=proof_artifact(
                    "obs_checkout_accept_transition",
                    ACCEPT_TRANSITION_OBLIGATION_ID,
                ),
            ),
        ),
        boundary_contracts=(
            CodeBoundaryContract(
                "checkout_reject_duplicate_boundary",
                code_contract_id="checkout_reject_duplicate",
                model_obligation_id="reject_duplicate_order",
                allowed_inputs=("duplicate_order",),
                rejected_inputs=("unknown_event",),
                allowed_outputs=("Rejected", "RejectedInvalidInput"),
                allowed_error_paths=("duplicate_order", "invalid_input"),
                exact=True,
            ),
        ),
        boundary_observations=(
            CodeBoundaryObservation(
                "boundary_reject_duplicate_order",
                "checkout_reject_duplicate_boundary",
                input_case="duplicate_order",
                accepted=True,
                observed_output="Rejected",
                observed_error_path="duplicate_order",
            ),
            CodeBoundaryObservation(
                "boundary_reject_unknown_event",
                "checkout_reject_duplicate_boundary",
                input_case="unknown_event",
                accepted=False,
                observed_output="RejectedInvalidInput",
                observed_error_path="invalid_input",
            ),
        ),
    )


def broken_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="sample_checkout_model",
        obligations=(
            ModelObligation(
                "reject_duplicate_order",
                obligation_type="hazard",
                external_outputs=("Rejected",),
                side_effects=(),
                error_paths=("duplicate_order",),
                exact_external_contract=True,
                required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
            ),
            ModelObligation(
                "model_miss_duplicate_submit_family",
                obligation_type="model_miss",
                model_miss_origin=True,
                requires_same_class_test_evidence=True,
            ),
        ),
        code_contracts=(
            CodeContract(
                "checkout_reject_duplicate",
                path="checkout/service.py",
                symbol="reject_duplicate_order",
                implements_obligations=("reject_duplicate_order",),
                external_outputs=("Rejected",),
                side_effects=("publish_duplicate_metric",),
                error_paths=("duplicate_order",),
            ),
            CodeContract(
                "checkout_duplicate_submit_family",
                path="checkout/service.py",
                symbol="reject_duplicate_order",
                implements_obligations=("model_miss_duplicate_submit_family",),
                external_outputs=("Rejected",),
            ),
        ),
        test_evidence=(
            TestEvidence(
                "test_duplicate_only_happy",
                test_name="test_duplicate_only_happy",
                path="tests/test_checkout.py",
                result_status="passed",
                test_kind=TEST_KIND_HAPPY_PATH,
                covered_obligations=("reject_duplicate_order",),
                covered_code_contracts=("checkout_reject_duplicate",),
                assertion_scope=TEST_ASSERTION_SCOPE_INTERNAL_PATH,
            ),
            TestEvidence(
                "test_duplicate_external_happy",
                test_name="test_duplicate_external_happy",
                path="tests/test_checkout.py",
                result_status="passed",
                test_kind=TEST_KIND_HAPPY_PATH,
                covered_obligations=("reject_duplicate_order",),
                covered_code_contracts=("checkout_reject_duplicate",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
            ),
            TestEvidence(
                "test_unbound_helper",
                test_name="test_unbound_helper",
                path="tests/test_checkout.py",
                result_status="passed",
            ),
            TestEvidence(
                "test_observed_duplicate_submit_only",
                test_name="test_observed_duplicate_submit_only",
                path="tests/test_checkout.py",
                result_status="passed",
                covered_obligations=("model_miss_duplicate_submit_family",),
                covered_code_contracts=("checkout_duplicate_submit_family",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                closure_evidence_role=TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
            ),
        ),
        boundary_contracts=(
            CodeBoundaryContract(
                "checkout_reject_duplicate_boundary",
                code_contract_id="checkout_reject_duplicate",
                model_obligation_id="reject_duplicate_order",
                allowed_inputs=("duplicate_order",),
                rejected_inputs=("unknown_event",),
                allowed_outputs=("Rejected",),
                allowed_side_effects=(),
                allowed_error_paths=("duplicate_order",),
                exact=True,
            ),
        ),
        boundary_observations=(
            CodeBoundaryObservation(
                "boundary_duplicate_extra_metric",
                "checkout_reject_duplicate_boundary",
                input_case="duplicate_order",
                accepted=True,
                observed_output="Rejected",
                observed_side_effects=("publish_duplicate_metric",),
            ),
            CodeBoundaryObservation(
                "boundary_unknown_event_accepted",
                "checkout_reject_duplicate_boundary",
                input_case="unknown_event",
                accepted=True,
                observed_output="Rejected",
            ),
        ),
    )


ALIGNED_SOURCE = {
    "checkout/service.py": """
def accept_order(order_id, payment_token):
    state = {}
    state["order_status"] = "Accepted"
    return "Accepted"

def accept_order_transition(submit_valid_order):
    pending = submit_valid_order
    accepted = "Accepted"
    _ = pending
    return "Accepted"

def reject_duplicate_order(order_id):
    if order_id:
        return "Rejected"
    raise duplicate_order()
""",
    "tests/test_checkout.py": """
def test_accept_valid_order():
    result = accept_order("order-1", "token")
    assert result == "Accepted"

def test_pending_submit_reaches_accepted():
    result = accept_order_transition("submit")
    assert result == "Accepted"

def test_reject_duplicate_order_happy():
    result = reject_duplicate_order("order-1")
    assert result == "Rejected"

def test_reject_duplicate_order_failure():
    result = reject_duplicate_order("order-1")
    assert result == "Rejected"

def test_observed_duplicate_submit_regression():
    assert reject_duplicate_order("observed-duplicate") == "Rejected"

def test_same_class_duplicate_submit_variants():
    assert reject_duplicate_order("duplicate-via-alt-entry") == "Rejected"
""",
}


BROKEN_SOURCE = {
    "checkout/service.py": """
def reject_duplicate_order(order_id):
    publish_duplicate_metric(order_id)
    return "Rejected"
""",
    "tests/test_checkout.py": """
def test_duplicate_only_happy():
    result = helper_reject_duplicate("order-1")
    assert result == "Rejected"

def test_unbound_helper():
    assert helper_reject_duplicate("order-1") == "Rejected"
""",
}


def source_audit(plan: ModelTestAlignmentPlan, source_by_path: dict[str, str]):
    code_evidence = audit_python_code_contracts(plan.code_contracts, source_by_path)
    test_assertions = audit_python_test_assertions(plan.test_evidence, plan.code_contracts, source_by_path)
    return review_python_contract_source_audit(
        plan.code_contracts,
        plan.test_evidence,
        code_evidence,
        test_assertions,
    )


def run_checks():
    aligned = aligned_plan()
    broken = broken_plan()
    aligned_boundary = review_code_boundary_conformance(aligned.boundary_contracts, aligned.boundary_observations, aligned.code_contracts)
    broken_boundary = review_code_boundary_conformance(broken.boundary_contracts, broken.boundary_observations, broken.code_contracts)
    return (
        review_model_test_alignment(aligned),
        review_model_test_alignment(broken),
        aligned_boundary,
        broken_boundary,
        source_audit(aligned, ALIGNED_SOURCE),
        source_audit(broken, BROKEN_SOURCE),
    )
'''

MODEL_TEST_ALIGNMENT_RUN_CHECKS_TEMPLATE = '''"""Run the Model-Test Alignment template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    aligned, broken, aligned_boundary, broken_boundary, aligned_source, broken_source = run_checks()
    print(aligned.format_text())
    print()
    print(broken.format_text(max_findings=10))
    print()
    print(aligned_boundary.format_text())
    print()
    print(broken_boundary.format_text(max_findings=5))
    print()
    print(aligned_source.format_text())
    print()
    print(broken_source.format_text(max_findings=5))
    return 0 if aligned.ok and not broken.ok and aligned_boundary.ok and not broken_boundary.ok and aligned_source.ok and not broken_source.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

MODEL_TEST_ALIGNMENT_NOTES_TEMPLATE = """# FlowGuard Model-Test Alignment Notes

Use this scaffold to compare a FlowGuard model's explicit obligations with
required owner code external contracts, ordinary test evidence, and conservative
Python source audits for those contracts. When the model says the real code
surface has a finite input/output boundary, also add code-boundary conformance
observations from runtime tests, replay, or a harness.

## Inputs

List model obligations:

- scenario ids;
- invariant ids;
- hazard ids;
- field lifecycle projection ids from FieldLifecycleMesh;
- state-transition or input/output contract ids;
- external inputs and outputs;
- state reads and writes;
- side effects and error paths;
- whether the external contract is exact, so extra code-visible behavior blocks
  confidence;
- required test kinds such as happy path, failure path, edge path, negative
  path, or replay.

List code external contracts for every required model obligation in the review:

- code contract id;
- path, symbol, and surface type;
- whether the surface is the obligation owner, helper, adapter, facade, or
  read-only support;
- implemented model obligation ids;
- external inputs and outputs;
- state reads and writes;
- side effects and error paths.

For field-bearing changes, pass FieldLifecycleMesh reports or projections into
`ModelTestAlignmentPlan.field_lifecycle_reports` or
`field_lifecycle_projections`. The alignment route will convert those
projections into model obligations and required owner code contracts, then the
ordinary test evidence must prove the same external behavior.

List test evidence:

- evidence id;
- test name and path;
- command or runner;
- pass, fail, timeout, skipped, not-run, running, or error status;
- freshness and stale reasons;
- covered model obligation ids.
- covered code contract ids;
- assertion scope, especially whether the test proves the external contract or
  only an internal path.

List code-boundary conformance evidence when a code surface must be closed:

- `CodeBoundaryContract` rows declare allowed input cases, rejected input cases,
  allowed outputs, state writes, side effects, and error paths.
- `CodeBoundaryObservation` rows record what real code did for one input case:
  accepted or rejected, returned output, error path, state writes, and side
  effects.
- `review_code_boundary_conformance(...)` blocks when forbidden inputs are
  accepted, allowed inputs are rejected, missing input-gate evidence is reused,
  or real code produces undeclared output, state write, side effect, or error.
- Boundary observations are runtime evidence. They do not replace conformance
  replay when ordered production traces, durable state, or adapter projection
  are part of the claim.
- When finite inputs may be incomplete, include state closure evidence:
  representative unknown/other, malformed, missing-field, old-schema, or
  external-unknown cases plus safe reject/block/isolate/model-maturation
  handling before side effects.

Optionally run the conservative source audit:

- `audit_python_code_contracts(...)` returns `PythonCodeContractEvidence` from
  real Python functions: symbol presence, parameters, return statements,
  raises, state writes, and side-effect-looking calls.
- `audit_python_test_assertions(...)` returns `PythonTestAssertionEvidence`
  from real Python tests: whether the test calls the target code contract and
  contains assertions.
- `review_python_contract_source_audit(...)` flags source-level gaps before the
  declared rows are trusted. This is not a full semantic proof.
- Code audits inspect function signatures, return values, raises, assignments, and calls.
  They can flag a missing Python symbol, missing input, missing output, missing
  state write, and extra side effect.
- Test audits check that tests must call the declared code contract symbol and
  contain an assert or unittest assertion; helper/internal path evidence and no
  assert evidence stay visible as source-level gaps.

## Boundary

Model-Test Alignment does not split tests, refactor source code, or read mesh
reports. It compares declared obligations, required external code contracts,
and evidence. Use TestMesh only when a large validation flow needs parent/child
test hierarchy ownership. Use StructureMesh only when a large script, module,
command, or API surface is being split.
"""

MODEL_TEST_ALIGNMENT_FULL_MODEL_TEMPLATE = MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE
MODEL_TEST_ALIGNMENT_FULL_RUN_CHECKS_TEMPLATE = MODEL_TEST_ALIGNMENT_RUN_CHECKS_TEMPLATE
MODEL_TEST_ALIGNMENT_FULL_NOTES_TEMPLATE = MODEL_TEST_ALIGNMENT_NOTES_TEMPLATE

MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: compact alignment of one model obligation, one owner code contract,
one required test, and one replay/negative evidence item.
Guards against: claiming model coverage when the owner code contract, plain
test evidence, same-class or negative check, or replay evidence is missing.
Use before editing: field, state, input/output, side-effect, or runtime-shape
changes whose model obligations need direct code/test binding.
Run: python .flowguard/model_test_alignment/run_checks.py
Modeled block shape: Input x State -> Set(Output x State).
"""

from __future__ import annotations

from dataclasses import dataclass


PASSING_STATUSES = {"passed"}


@dataclass(frozen=True)
class CompactAlignmentPlan:
    plan_id: str
    model_obligation_id: str
    owner_code_contract_id: str
    test_evidence_id: str
    test_status: str
    test_covers_model_obligation: bool
    test_covers_owner_code_contract: bool
    same_class_or_negative_test_present: bool
    replay_evidence_id: str
    replay_status: str


@dataclass(frozen=True)
class CompactAlignmentReport:
    plan_id: str
    ok: bool
    findings: tuple[str, ...]

    def format_text(self) -> str:
        lines = [f"flowguard model-test alignment: {self.plan_id}", f"status: {'PASS' if self.ok else 'FAIL'}"]
        lines.extend(f"- {finding}" for finding in self.findings)
        return "\\n".join(lines)


def review_compact_alignment(plan: CompactAlignmentPlan) -> CompactAlignmentReport:
    findings: list[str] = []
    if not plan.model_obligation_id:
        findings.append("missing_model_obligation")
    if not plan.owner_code_contract_id:
        findings.append("missing_owner_code_contract")
    if not plan.test_evidence_id:
        findings.append("missing_required_test_kind")
    if plan.test_status not in PASSING_STATUSES:
        findings.append("test_evidence_not_passing")
    if not plan.test_covers_model_obligation:
        findings.append("test_missing_model_obligation")
    if not plan.test_covers_owner_code_contract:
        findings.append("test_missing_owner_code_contract")
    if not plan.same_class_or_negative_test_present:
        findings.append("missing_same_class_test_evidence")
    if not plan.replay_evidence_id or plan.replay_status not in PASSING_STATUSES:
        findings.append("missing_replay_evidence")
    return CompactAlignmentReport(plan.plan_id, not findings, tuple(findings))


def aligned_plan() -> CompactAlignmentPlan:
    return CompactAlignmentPlan(
        plan_id="aligned",
        model_obligation_id="model:missing-field-rejected",
        owner_code_contract_id="contract:parse_request",
        test_evidence_id="test:test_missing_field_is_rejected",
        test_status="passed",
        test_covers_model_obligation=True,
        test_covers_owner_code_contract=True,
        same_class_or_negative_test_present=True,
        replay_evidence_id="replay:runtime-shape-missing-field",
        replay_status="passed",
    )


def broken_plan() -> CompactAlignmentPlan:
    return CompactAlignmentPlan(
        plan_id="broken",
        model_obligation_id="model:missing-field-rejected",
        owner_code_contract_id="contract:parse_request",
        test_evidence_id="",
        test_status="not_run",
        test_covers_model_obligation=False,
        test_covers_owner_code_contract=False,
        same_class_or_negative_test_present=False,
        replay_evidence_id="",
        replay_status="not_run",
    )


def run_checks():
    return review_compact_alignment(aligned_plan()), review_compact_alignment(broken_plan())
'''

MODEL_TEST_ALIGNMENT_RUN_CHECKS_TEMPLATE = '''"""Run the compact Model-Test Alignment template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    aligned, broken = run_checks()
    print(aligned.format_text())
    print()
    print(broken.format_text())
    print()
    print("plain model obligations -> owner code external contracts -> plain test evidence -> replay evidence")
    print("escalate to model-test-alignment-full-template for code-boundary conformance, source audit, state closure evidence, TestResultReuseTicket, or TransitionCoverageMatrix")
    return 0 if aligned.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

MODEL_TEST_ALIGNMENT_NOTES_TEMPLATE = """# FlowGuard Model-Test Alignment Notes

This compact default compares one model obligation with its owner code external
contract (`CodeContract` in the full API), passing test evidence, same-class or
negative evidence, and replay evidence. It is the right first scaffold when the
goal is to prove a field, state, input/output, or side-effect obligation is
actually guarded by runtime code and tests.

Escalate to `model-test-alignment-full-template` when the claim needs
code-boundary conformance rows, conservative Python source audit,
state-closure evidence for unknown/old-schema cases, reused test-result
tickets, transition coverage matrices, FieldLifecycleMesh projections, or
large TestMesh/StructureMesh handoffs.
"""

__all__ = [
    'MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE',
    'MODEL_TEST_ALIGNMENT_RUN_CHECKS_TEMPLATE',
    'MODEL_TEST_ALIGNMENT_NOTES_TEMPLATE',
    'MODEL_TEST_ALIGNMENT_FULL_MODEL_TEMPLATE',
    'MODEL_TEST_ALIGNMENT_FULL_RUN_CHECKS_TEMPLATE',
    'MODEL_TEST_ALIGNMENT_FULL_NOTES_TEMPLATE',
]
