import unittest

import flowguard
from flowguard import (
    ProofArtifactRef,
    RuntimeNodeContract,
    RuntimeNodeObservation,
    RuntimePathAlignmentPlan,
    RuntimePathRecorder,
    RuntimePathRun,
    review_runtime_path_alignment,
)


def contract(node_id, **kwargs):
    defaults = {
        "model_id": "checkout.leaf",
        "model_path": ".flowguard/checkout_leaf/model.py",
        "leaf_model_id": "checkout.leaf",
        "model_obligation_id": "accept_valid_order",
        "code_contract_id": "checkout.submit",
        "boundary_id": "checkout.submit.boundary",
        "business_intent_id": "intent:checkout.submit-order",
        "behavior_commitment_id": "commitment:checkout.submit-order",
        "primary_path_id": "path:checkout.submit-order",
        "surface_id": "surface:checkout.submit",
        "candidate_id": "candidate:checkout.primary",
        "allowed_outputs": ("accepted",),
        "allowed_state_writes": ("order_status",),
        "sequence_index": 0,
    }
    defaults.update(kwargs)
    return RuntimeNodeContract(node_id, **defaults)


def observation(node_id, **kwargs):
    defaults = {
        "observation_id": f"obs:{node_id}",
        "run_id": "run:checkout:1",
        "model_id": "checkout.leaf",
        "model_path": ".flowguard/checkout_leaf/model.py",
        "leaf_model_id": "checkout.leaf",
        "model_obligation_id": "accept_valid_order",
        "code_contract_id": "checkout.submit",
        "boundary_id": "checkout.submit.boundary",
        "business_intent_id": "intent:checkout.submit-order",
        "behavior_commitment_id": "commitment:checkout.submit-order",
        "primary_path_id": "path:checkout.submit-order",
        "surface_id": "surface:checkout.submit",
        "candidate_id": "candidate:checkout.primary",
        "observed_output": "accepted",
        "observed_state_writes": ("order_status",),
        "evidence_id": f"evidence:{node_id}",
    }
    defaults.update(kwargs)
    return RuntimeNodeObservation(node_id=node_id, **defaults)


def proof_artifact():
    return ProofArtifactRef(
        "artifact:runtime-path",
        result_status="passed",
        exit_code=0,
        result_path="tmp/runtime_path.json",
        covered_obligation_ids=("accept_valid_order",),
    )


def finding_codes(report):
    return [finding.code for finding in report.findings]


class RuntimePathEvidenceTests(unittest.TestCase):
    def test_matching_runtime_path_can_continue_and_formats_model_progress(self):
        plan = RuntimePathAlignmentPlan(
            "checkout-path",
            node_contracts=(contract("validate_order"),),
            observations=(observation("validate_order", progress_message="accepted valid order"),),
        )

        report = review_runtime_path_alignment(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("runtime_path_alignment_green", report.decision)
        progress = plan.observations[0].format_progress_line()
        self.assertIn("flowguard.runtime_path", progress)
        self.assertIn("model=checkout.leaf", progress)
        self.assertIn("model_path=.flowguard/checkout_leaf/model.py", progress)
        self.assertIn("node=validate_order", progress)
        self.assertIn("progress=accepted valid order", progress)
        self.assertEqual(".flowguard/checkout_leaf/model.py", plan.to_dict()["observations"][0]["model_path"])

    def test_missing_required_node_blocks_alignment(self):
        report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "checkout-path",
                node_contracts=(contract("validate_order"),),
                observations=(),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("runtime_node_missing_observation", finding_codes(report))

    def test_stale_non_passing_and_internal_observation_blocks_alignment(self):
        report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "checkout-path",
                node_contracts=(contract("validate_order"),),
                observations=(
                    observation(
                        "validate_order",
                        result_status="skipped",
                        evidence_current=False,
                        assertion_scope="internal_path",
                    ),
                ),
            )
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("runtime_node_observation_not_current_pass", codes)
        self.assertIn("runtime_node_internal_path_only", codes)
        self.assertIn("runtime_node_missing_observation", codes)

    def test_behavior_and_binding_mismatch_blocks_alignment(self):
        report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "checkout-path",
                node_contracts=(contract("validate_order"),),
                observations=(
                    observation(
                        "validate_order",
                        model_obligation_id="wrong_obligation",
                        observed_output="unexpected",
                        observed_state_writes=("other_state",),
                    ),
                ),
            )
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("runtime_node_obligation_mismatch", codes)
        self.assertIn("runtime_node_output_mismatch", codes)
        self.assertIn("runtime_node_state_write_mismatch", codes)

    def test_business_path_binding_is_checked_when_declared(self):
        ok_observation = observation(
            "validate_order",
            business_path_id="submit_order",
            business_intent="submit order",
            observed_terminal="accepted",
        )
        ok_report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "checkout-business-path-ok",
                node_contracts=(
                    contract(
                        "validate_order",
                        business_path_id="submit_order",
                        business_intent="submit order",
                        expected_terminal="accepted",
                    ),
                ),
                observations=(ok_observation,),
            )
        )
        wrong_report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "checkout-business-path-wrong",
                node_contracts=(
                    contract(
                        "validate_order",
                        business_path_id="submit_order",
                        business_intent="submit order",
                        expected_terminal="accepted",
                    ),
                ),
                observations=(
                    observation(
                        "validate_order",
                        business_path_id="cancel_order",
                        business_intent="cancel order",
                        observed_terminal="cancelled",
                    ),
                ),
            )
        )
        missing_report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "checkout-business-path-missing",
                node_contracts=(
                    contract(
                        "validate_order",
                        business_path_id="submit_order",
                        expected_terminal="accepted",
                    ),
                ),
                observations=(observation("validate_order"),),
            )
        )

        self.assertTrue(ok_report.ok, ok_report.format_text())
        self.assertIn("business_path=submit_order", ok_observation.format_progress_line())
        wrong_codes = finding_codes(wrong_report)
        self.assertFalse(wrong_report.ok)
        self.assertIn("runtime_node_business_path_mismatch", wrong_codes)
        self.assertIn("runtime_node_business_intent_mismatch", wrong_codes)
        self.assertIn("runtime_node_business_terminal_mismatch", wrong_codes)
        missing_codes = finding_codes(missing_report)
        self.assertIn("runtime_node_business_path_missing", missing_codes)
        self.assertIn("runtime_node_business_terminal_missing", missing_codes)

    def test_exact_path_rejects_uncontracted_and_out_of_order_nodes(self):
        report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "checkout-path",
                node_contracts=(
                    contract("validate_order", sequence_index=0),
                    contract("store_order", sequence_index=1),
                ),
                observations=(
                    observation("store_order", sequence_index=0),
                    observation("validate_order", sequence_index=1),
                    observation("audit_only", sequence_index=2),
                ),
                require_exact_path=True,
            )
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("runtime_path_order_mismatch", codes)
        self.assertIn("uncontracted_runtime_node_observed", codes)

    def test_exact_path_preserves_repeated_node_occurrences(self):
        plan = RuntimePathAlignmentPlan(
            "checkout-retry-path",
            node_contracts=(
                contract(
                    "attempt",
                    sequence_index=0,
                    expected_terminal="retrying",
                    allowed_state_writes=("attempt_count",),
                    allowed_side_effects=("retry_log",),
                ),
                contract("wait", sequence_index=1),
                contract(
                    "attempt",
                    sequence_index=2,
                    expected_terminal="accepted",
                    allowed_state_writes=("order_status",),
                    allowed_side_effects=("notify",),
                ),
            ),
            observations=(
                observation(
                    "attempt",
                    observation_id="obs:attempt:0",
                    sequence_index=0,
                    observed_terminal="retrying",
                    observed_state_writes=("attempt_count",),
                    observed_side_effects=("retry_log",),
                ),
                observation("wait", observation_id="obs:wait:1", sequence_index=1),
                observation(
                    "attempt",
                    observation_id="obs:attempt:2",
                    sequence_index=2,
                    observed_terminal="accepted",
                    observed_state_writes=("order_status",),
                    observed_side_effects=("notify",),
                ),
            ),
            require_exact_path=True,
        )

        report = review_runtime_path_alignment(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertNotIn("duplicate_runtime_node_contract", finding_codes(report))

    def test_exact_path_rejects_dropped_repeated_occurrence(self):
        report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "checkout-retry-missing",
                node_contracts=(
                    contract("attempt", sequence_index=0),
                    contract("wait", sequence_index=1),
                    contract("attempt", sequence_index=2),
                ),
                observations=(
                    observation(
                        "attempt",
                        observation_id="obs:attempt:0",
                        sequence_index=0,
                    ),
                    observation("wait", observation_id="obs:wait:1", sequence_index=1),
                ),
                require_exact_path=True,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("runtime_path_sequence_mismatch", finding_codes(report))

    def test_exact_path_checks_occurrence_specific_effects(self):
        report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "checkout-retry-effects",
                node_contracts=(
                    contract(
                        "attempt",
                        sequence_index=0,
                        allowed_state_writes=("attempt_count",),
                        allowed_side_effects=("retry_log",),
                    ),
                    contract(
                        "attempt",
                        sequence_index=1,
                        allowed_state_writes=("order_status",),
                        allowed_side_effects=("notify",),
                    ),
                ),
                observations=(
                    observation(
                        "attempt",
                        observation_id="obs:attempt:0",
                        sequence_index=0,
                        observed_state_writes=("attempt_count",),
                        observed_side_effects=("retry_log",),
                    ),
                    observation(
                        "attempt",
                        observation_id="obs:attempt:1",
                        sequence_index=1,
                        observed_state_writes=("order_status",),
                        observed_side_effects=(),
                    ),
                ),
                require_exact_path=True,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn(
            "runtime_path_occurrence_side_effects_mismatch",
            finding_codes(report),
        )

    def test_exact_path_reviews_explicit_runs_independently(self):
        run_kwargs = {
            "business_intent_id": "intent:checkout.submit-order",
            "behavior_commitment_id": "commitment:checkout.submit-order",
            "primary_path_id": "path:checkout.submit-order",
        }
        good_run = RuntimePathRun(
            "run:checkout:good",
            observations=(
                observation(
                    "validate_order",
                    observation_id="obs:good:validate",
                    run_id="run:checkout:good",
                    sequence_index=0,
                ),
                observation(
                    "store_order",
                    observation_id="obs:good:store",
                    run_id="run:checkout:good",
                    sequence_index=1,
                ),
            ),
            **run_kwargs,
        )
        wrong_run = RuntimePathRun(
            "run:checkout:wrong",
            observations=(
                observation(
                    "store_order",
                    observation_id="obs:wrong:store",
                    run_id="run:checkout:wrong",
                    sequence_index=0,
                ),
                observation(
                    "validate_order",
                    observation_id="obs:wrong:validate",
                    run_id="run:checkout:wrong",
                    sequence_index=1,
                ),
            ),
            **run_kwargs,
        )

        report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "checkout-two-runs",
                node_contracts=(
                    contract("validate_order", sequence_index=0),
                    contract("store_order", sequence_index=1),
                ),
                runs=(good_run, wrong_run),
                require_exact_path=True,
            )
        )

        self.assertFalse(report.ok)
        mismatches = [
            finding
            for finding in report.findings
            if finding.code == "runtime_path_order_mismatch"
        ]
        self.assertTrue(
            any(finding.metadata.get("run_id") == "run:checkout:wrong" for finding in mismatches)
        )

    def test_broad_runtime_claim_requires_stable_authority_ids(self):
        report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "checkout-missing-authority",
                node_contracts=(
                    contract(
                        "validate_order",
                        business_intent_id="",
                        behavior_commitment_id="",
                        primary_path_id="",
                    ),
                ),
                observations=(
                    observation(
                        "validate_order",
                        business_intent_id="",
                        behavior_commitment_id="",
                        primary_path_id="",
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("runtime_path_business_intent_id_missing", finding_codes(report))
        self.assertIn("runtime_path_behavior_commitment_id_missing", finding_codes(report))
        self.assertIn("runtime_path_primary_path_id_missing", finding_codes(report))

    def test_expected_runtime_inventory_reports_covered_scoped_and_missing_ids(self):
        report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "checkout-inventory",
                node_contracts=(contract("validate_order"),),
                observations=(observation("validate_order"),),
                inventory_revision="inventory:v1",
                expected_surface_ids=("surface:checkout.submit", "surface:checkout.cli"),
                expected_candidate_ids=("candidate:checkout.primary", "candidate:checkout.legacy"),
                scoped_surface_reasons={"surface:checkout.cli": "CLI is release-only in this review"},
                require_complete_inventory=True,
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(("surface:checkout.submit",), report.covered_surface_ids)
        self.assertEqual(("surface:checkout.cli",), report.scoped_surface_ids)
        self.assertEqual(("candidate:checkout.legacy",), report.missing_candidate_ids)
        self.assertIn("expected_runtime_candidate_unaccounted", finding_codes(report))

    def test_runtime_facade_requires_current_delegation_and_no_alternate_success(self):
        facade_contract = contract(
            "public_facade",
            surface_role="facade",
            delegates_to_primary_path_id="path:checkout.submit-order",
            delegation_evidence_id="delegation:facade:v1",
            delegation_evidence_current=True,
            delegation_only=True,
        )
        good = observation(
            "public_facade",
            surface_role="facade",
            delegates_to_primary_path_id="path:checkout.submit-order",
            delegation_evidence_id="delegation:facade:v1",
            delegation_evidence_current=True,
            delegation_observed=True,
        )
        bad = observation(
            "public_facade",
            surface_role="facade",
            delegates_to_primary_path_id="path:checkout.submit-order",
            delegation_evidence_id="delegation:facade:v1",
            delegation_evidence_current=True,
            delegation_observed=True,
            independent_business_success=True,
        )

        self.assertTrue(
            review_runtime_path_alignment(
                RuntimePathAlignmentPlan("facade-ok", node_contracts=(facade_contract,), observations=(good,))
            ).ok
        )
        bad_report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan("facade-bad", node_contracts=(facade_contract,), observations=(bad,))
        )
        self.assertFalse(bad_report.ok)
        self.assertIn("runtime_facade_alternate_success", finding_codes(bad_report))

    def test_strict_path_requires_matching_proof_artifact(self):
        ok_report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "checkout-path",
                node_contracts=(contract("validate_order"),),
                observations=(observation("validate_order", proof_artifact=proof_artifact()),),
                require_proof_artifacts=True,
            )
        )
        missing_report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "checkout-path",
                node_contracts=(contract("validate_order"),),
                observations=(observation("validate_order"),),
                require_proof_artifacts=True,
            )
        )

        self.assertTrue(ok_report.ok, ok_report.format_text())
        self.assertFalse(missing_report.ok)
        self.assertIn("missing_proof_artifact", finding_codes(missing_report))

    def test_recorder_captures_ordered_run(self):
        recorder = RuntimePathRecorder("run:checkout:1")
        recorder.record(
            "validate_order",
            model_id="checkout.leaf",
            model_path=".flowguard/checkout_leaf/model.py",
            model_obligation_id="accept_valid_order",
            observed_output="accepted",
        )
        recorder.record(
            "store_order",
            model_id="checkout.leaf",
            model_path=".flowguard/checkout_leaf/model.py",
            model_obligation_id="accept_valid_order",
            observed_output="stored",
        )
        run = recorder.to_run()

        self.assertIsInstance(run, RuntimePathRun)
        self.assertEqual(("validate_order", "store_order"), tuple(item.node_id for item in run.observations))
        self.assertIn("model=checkout.leaf", recorder.format_progress_lines())

    def test_public_api_exports_runtime_path_helpers_outside_core(self):
        expected = (
            "RuntimeNodeContract",
            "RuntimeNodeObservation",
            "RuntimePathRun",
            "RuntimePathAlignmentPlan",
            "RuntimePathFinding",
            "RuntimePathAlignmentReport",
            "RuntimePathRecorder",
            "review_runtime_path_alignment",
        )
        for name in expected:
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)
            self.assertNotIn(name, flowguard.CORE_API)


if __name__ == "__main__":
    unittest.main()
