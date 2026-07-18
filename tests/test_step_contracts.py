import unittest
from dataclasses import dataclass

from flowguard import (
    FunctionResult,
    KnownBadProof,
    MinimumModelContract,
    ModelTestAlignmentPlan,
    ProcessArtifact,
    ProcessEvidence,
    RiskIntent,
    RiskProfile,
    TemplateHarvestReview,
    TemplateReuseReview,
    Trace,
    TraceStep,
    Workflow,
    WorkflowStepContract,
    step_contract_metadata,
    step_contract_metadata_matches_rule,
)
from flowguard.development_process_flow import (
    PROCESS_ARTIFACT_CODE,
    PROCESS_EVIDENCE_PASSED,
    DevelopmentProcessPlan,
    review_development_process_flow,
)
from flowguard.model_test_alignment import (
    CodeContract,
    TEST_KIND_REPLAY,
    TEST_STATUS_PASSED,
    TestEvidence,
    review_model_test_alignment,
)
from flowguard.plan import FlowGuardCheckPlan
from flowguard.replay import ReplayObservation
from flowguard.runner import run_model_first_checks
from flowguard.step_contracts import (
    STEP_METADATA_PRODUCED_RECEIPTS,
    STEP_METADATA_RUNTIME_NODE_IDS,
    compile_step_contract_invariants,
    extract_step_contract_metadata,
    review_step_contract_trace,
    step_contracts_to_model_obligations,
    step_contracts_to_validation_requirements,
)
from flowguard.conformance import replay_trace


def formal_entry_kwargs():
    return {
        "risk_profile": RiskProfile(
            modeled_boundary="workflow step contracts",
            risk_classes=("side_effect",),
            risk_intent=RiskIntent(
                failure_modes=("done claimed without required inventory step",),
                protected_error_classes=("premature_completion",),
                protected_harms=("workflow is marked done before required receipts exist",),
                must_model_state=("step_receipts",),
                must_model_side_effects=("done_claim",),
                completion_evidence=("done_receipt",),
                adversarial_inputs=("claim done before inventory",),
                hard_invariants=("required steps precede done claim",),
                known_bad_cases=("done_without_inventory",),
                template_no_match_reason="step contract unit test owns this local boundary",
                blindspots=("production replay is covered by model-test alignment tests",),
            ),
        ),
        "template_reuse_review": TemplateReuseReview(
            no_match_reason="step contract unit test owns this local boundary",
            searched_layers=("public", "local"),
        ),
        "template_harvest_review": TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        "minimum_model_contract": MinimumModelContract(
            protected_error_classes=("premature_completion",),
            modeled_state=("step_receipts",),
            modeled_side_effects=("done_claim",),
            completion_evidence=("done_receipt",),
            known_bad_cases=("done_without_inventory",),
        ),
        "known_bad_proofs": (
            KnownBadProof(
                "done_without_inventory",
                protected_error_class="premature_completion",
                method="workflow_step_contract",
                observed_status="failed",
                observed_failure="required step contract failed",
                evidence_id="step_contract:done_without_inventory",
            ),
        ),
    }


def _step(label, metadata=None, reason=""):
    return TraceStep(
        external_input=label,
        function_name="step",
        function_input=label,
        function_output=label,
        old_state=(),
        new_state=(),
        label=label,
        reason=reason,
        metadata=metadata,
    )


def _contracts():
    return (
        WorkflowStepContract(
            "inventory",
            completion_labels=("inventory_done",),
            produces_receipts=("inventory_receipt",),
        ),
        WorkflowStepContract(
            "coverage",
            completion_labels=("coverage_done",),
            requires_receipts=("inventory_receipt",),
            produces_receipts=("coverage_receipt",),
            required_for_claims=("done_claimed",),
            artifact_ids=("code.checkout",),
        ),
        WorkflowStepContract(
            "regression",
            completion_labels=("regression_done",),
            requires_receipts=("coverage_receipt",),
            produces_receipts=("regression_receipt",),
            required_for_claims=("release_claimed",),
            required_test_kinds=(TEST_KIND_REPLAY,),
        ),
    )


class WorkflowStepContractTests(unittest.TestCase):
    def test_review_good_trace_tracks_current_receipts(self):
        trace = Trace(
            steps=(
                _step("inventory_done"),
                _step("coverage_done"),
                _step("regression_done"),
                _step("done_claimed"),
                _step("release_claimed"),
            )
        )

        report = review_step_contract_trace(trace, _contracts())

        self.assertTrue(report.ok, report.format_text())
        self.assertIn("coverage_receipt", report.current_receipts)
        self.assertIn("regression_receipt", report.current_receipts)

    def test_review_reports_missing_prerequisite_receipt(self):
        trace = Trace(steps=(_step("coverage_done"),))

        report = review_step_contract_trace(trace, _contracts())

        self.assertFalse(report.ok)
        self.assertEqual("missing_prerequisite_receipt", report.findings[0].code)
        self.assertEqual("inventory_receipt", report.findings[0].receipt_id)

    def test_review_reports_stale_receipt_before_claim(self):
        trace = Trace(
            steps=(
                _step("inventory_done"),
                _step("coverage_done"),
                _step(
                    "edit_after_coverage",
                    metadata=step_contract_metadata(invalidated_receipts=("coverage_receipt",)),
                ),
                _step("done_claimed"),
            )
        )

        report = review_step_contract_trace(trace, _contracts())

        self.assertFalse(report.ok)
        self.assertIn("coverage_receipt", report.stale_receipts)
        self.assertEqual("missing_claim_receipt", report.findings[0].code)

    def test_review_reports_forbidden_skipped_step(self):
        trace = Trace(
            steps=(
                _step(
                    "claim_release_without_regression",
                    metadata=step_contract_metadata(skipped_step_ids=("regression",)),
                ),
            )
        )

        report = review_step_contract_trace(trace, _contracts())

        self.assertFalse(report.ok)
        self.assertEqual("forbidden_step_skipped", report.findings[0].code)

    def test_step_contract_metadata_carries_runtime_node_ids(self):
        metadata = step_contract_metadata(
            "coverage",
            runtime_node_ids=("runtime:coverage", "runtime:coverage"),
        )
        contract = WorkflowStepContract("coverage", runtime_node_ids=("runtime:coverage",))

        self.assertEqual(("runtime:coverage",), metadata[STEP_METADATA_RUNTIME_NODE_IDS])
        self.assertEqual(
            ("runtime:coverage",),
            extract_step_contract_metadata(metadata)[STEP_METADATA_RUNTIME_NODE_IDS],
        )
        self.assertEqual(["runtime:coverage"], contract.to_dict()["runtime_node_ids"])

    def test_compiled_invariant_fails_for_premature_claim(self):
        trace = Trace(steps=(_step("done_claimed"),))
        invariant = compile_step_contract_invariants(_contracts())[0]

        result = invariant.check((), trace)

        self.assertFalse(result.ok)
        self.assertIn("requires current receipt", result.message)

    def test_runner_integrates_step_contract_invariants(self):
        @dataclass(frozen=True)
        class State:
            seen: tuple[str, ...] = ()

        class Inventory:
            name = "inventory"
            reads = ()
            writes = ()

            def apply(self, input_obj, state):
                return (FunctionResult(input_obj, state, label="inventory_done"),)

        class ClaimDone:
            name = "claim_done"
            reads = ()
            writes = ()

            def apply(self, input_obj, state):
                return (FunctionResult(input_obj, state, label="done_claimed"),)

        summary = run_model_first_checks(
            FlowGuardCheckPlan(
                workflow=Workflow((Inventory(), ClaimDone()), name="skips_coverage"),
                initial_states=(State(),),
                external_inputs=("go",),
                max_sequence_length=1,
                step_contracts=_contracts(),
                **formal_entry_kwargs(),
            )
        )
        sections = {section.name: section for section in summary.sections}

        self.assertEqual("failed", summary.overall_status)
        self.assertEqual("failed", sections["model_check"].status)
        self.assertEqual("failed", sections["workflow_step_contracts"].status)
        self.assertIn("step_contracts: 3", dict(summary.metadata)["plan"].format_text())

    def test_projection_to_development_process_flow_requirements(self):
        requirements = step_contracts_to_validation_requirements(_contracts())
        requirement = next(item for item in requirements if "coverage" in item.requirement_id)
        plan = DevelopmentProcessPlan(
            "step-contract-process",
            artifacts=(ProcessArtifact("code.checkout", PROCESS_ARTIFACT_CODE, "1"),),
            evidence=(
                ProcessEvidence(
                    "coverage-evidence",
                    evidence_kind="workflow_step",
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("code.checkout",),
                    covered_versions={"code.checkout": "1"},
                    validation_requirement_ids=(requirement.requirement_id,),
                ),
            ),
            validation_requirements=(requirement,),
        )

        report = review_development_process_flow(plan)

        self.assertTrue(report.ok, report.format_text())

    def test_projection_to_model_test_alignment_obligations(self):
        obligations = step_contracts_to_model_obligations(_contracts())
        obligation = next(item for item in obligations if item.obligation_id == "workflow_step:regression")
        report = review_model_test_alignment(
            ModelTestAlignmentPlan(
                "workflow-step-model",
                obligations=(obligation,),
                code_contracts=(
                    CodeContract(
                        "workflow.regression",
                        implements_obligations=(obligation.obligation_id,),
                        external_outputs=obligation.external_outputs,
                        state_reads=obligation.state_reads,
                        state_writes=obligation.state_writes,
                    ),
                ),
                test_evidence=(
                    TestEvidence(
                        "regression-replay",
                        result_status=TEST_STATUS_PASSED,
                        test_kind=TEST_KIND_REPLAY,
                        covered_obligations=(obligation.obligation_id,),
                        covered_code_contracts=("workflow.regression",),
                    ),
                ),
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("workflow_step", obligation.obligation_type)

    def test_conformance_rule_reports_missing_observed_receipt_metadata(self):
        trace = Trace(
            steps=(
                _step(
                    "coverage_done",
                    metadata=step_contract_metadata(
                        "coverage",
                        produced_receipts=("coverage_receipt",),
                    ),
                ),
            )
        )

        class Adapter:
            def reset(self, initial_state):
                return None

            def apply_step(self, step):
                return ReplayObservation(
                    function_name=step.function_name,
                    observed_output=step.function_input,
                    observed_state=(),
                    label=step.function_input,
                    metadata={STEP_METADATA_PRODUCED_RECEIPTS: ()},
                )

        report = replay_trace(trace, Adapter(), rules=(step_contract_metadata_matches_rule(),))

        self.assertFalse(report.ok)
        self.assertIn("step contract metadata mismatch", report.violations[0].message)


if __name__ == "__main__":
    unittest.main()
