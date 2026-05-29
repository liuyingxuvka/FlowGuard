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
