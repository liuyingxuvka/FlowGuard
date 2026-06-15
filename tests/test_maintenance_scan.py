import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard import (
    MAINTENANCE_ACTION_SUGGESTED,
    MAINTENANCE_ARTIFACT_CODE,
    MAINTENANCE_ARTIFACT_EVIDENCE,
    MAINTENANCE_ARTIFACT_MODEL,
    MAINTENANCE_ROUTE_AGENT_WORKFLOW_REHEARSAL,
    MAINTENANCE_ROUTE_ARCHITECTURE_REDUCTION,
    MAINTENANCE_ROUTE_DEVELOPMENT_PROCESS_FLOW,
    MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT,
    MAINTENANCE_ROUTE_MODEL_MATURATION,
    MAINTENANCE_ROUTE_MODEL_SIMILARITY,
    MAINTENANCE_ROUTE_STRUCTURE_MESH,
    MAINTENANCE_SCAN_DECISION_BLOCKED,
    MAINTENANCE_SCAN_DECISION_CLEAR,
    MAINTENANCE_SCAN_DECISION_REQUIRED,
    MAINTENANCE_SCAN_DECISION_SCOPED,
    MAINTENANCE_SCAN_DECISION_SUGGESTED,
    MAINTENANCE_SIGNAL_LARGE_MODULE,
    MAINTENANCE_SIGNAL_BUSINESS_PATH_CONFLICT,
    MAINTENANCE_SIGNAL_BUSINESS_PATH_DUPLICATE,
    MAINTENANCE_SIGNAL_BUSINESS_PATH_LEGACY_DISPOSITION,
    MAINTENANCE_SIGNAL_BUSINESS_PATH_UNPROVEN,
    MAINTENANCE_SIGNAL_MODEL_ANGLE_GAP,
    MAINTENANCE_SIGNAL_REDUCIBLE_BRANCH,
    MAINTENANCE_SIGNAL_STATE_CLOSURE_GAP,
    FlowGuardSection,
    FlowGuardSummaryReport,
    MaintenanceChangedArtifact,
    MaintenanceEvidence,
    MaintenanceObligation,
    MaintenanceScanPlan,
    MaintenanceSignal,
    MaintenanceSkippedRoute,
    maintenance_scan_plan_from_summary_report,
    maintenance_scan_template_files,
    review_maintenance_scan,
)
from flowguard.templates import write_template_files


ROOT = Path(__file__).resolve().parents[1]


def routes(report):
    return {action.route_id for action in report.actions}


class MaintenanceScanTests(unittest.TestCase):
    def test_clear_scan_is_not_validation(self):
        report = review_maintenance_scan(MaintenanceScanPlan("clear"))

        self.assertTrue(report.ok)
        self.assertEqual(MAINTENANCE_SCAN_DECISION_CLEAR, report.decision)
        self.assertIn("not model/test/replay validation", report.summary)

    def test_changed_model_and_code_requires_alignment_for_broad_claim(self):
        report = review_maintenance_scan(
            MaintenanceScanPlan(
                "model-code",
                claim_scope="done",
                changed_artifacts=(
                    MaintenanceChangedArtifact("model", MAINTENANCE_ARTIFACT_MODEL),
                    MaintenanceChangedArtifact("code", MAINTENANCE_ARTIFACT_CODE),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(MAINTENANCE_SCAN_DECISION_SCOPED, report.decision)
        self.assertIn(MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT, routes(report))
        self.assertEqual(("model_test_alignment:changed_model_code_test_boundary",), report.unresolved_required_action_ids)

    def test_current_owner_evidence_resolves_required_action(self):
        report = review_maintenance_scan(
            MaintenanceScanPlan(
                "resolved",
                claim_scope="done",
                changed_artifacts=(
                    MaintenanceChangedArtifact("model", MAINTENANCE_ARTIFACT_MODEL),
                    MaintenanceChangedArtifact("code", MAINTENANCE_ARTIFACT_CODE),
                ),
                evidence=(
                    MaintenanceEvidence(
                        "alignment-current",
                        MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT,
                        status="passed",
                        current=True,
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(MAINTENANCE_SCAN_DECISION_REQUIRED, report.decision)
        self.assertEqual((), report.unresolved_required_action_ids)
        self.assertEqual(("alignment-current",), report.actions[0].owner_evidence_ids)

    def test_strict_broad_claim_blocks_unresolved_required_action(self):
        report = review_maintenance_scan(
            MaintenanceScanPlan(
                "strict",
                claim_scope="release",
                allow_scoped_confidence=False,
                changed_artifacts=(
                    MaintenanceChangedArtifact("model", MAINTENANCE_ARTIFACT_MODEL),
                    MaintenanceChangedArtifact("code", MAINTENANCE_ARTIFACT_CODE),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(MAINTENANCE_SCAN_DECISION_BLOCKED, report.decision)

    def test_stale_evidence_routes_to_development_process(self):
        report = review_maintenance_scan(
            MaintenanceScanPlan(
                "stale",
                claim_scope="publish",
                changed_artifacts=(
                    MaintenanceChangedArtifact("full-pytest", MAINTENANCE_ARTIFACT_EVIDENCE, current=False),
                ),
            )
        )

        self.assertIn(MAINTENANCE_ROUTE_DEVELOPMENT_PROCESS_FLOW, routes(report))

    def test_unaccepted_skipped_route_requires_workflow_rehearsal(self):
        report = review_maintenance_scan(
            MaintenanceScanPlan(
                "skipped",
                skipped_routes=(MaintenanceSkippedRoute("structure_mesh_maintenance"),),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(MAINTENANCE_SCAN_DECISION_REQUIRED, report.decision)
        self.assertIn(MAINTENANCE_ROUTE_AGENT_WORKFLOW_REHEARSAL, routes(report))

    def test_reduction_and_structure_signals_route_without_replacing_owners(self):
        report = review_maintenance_scan(
            MaintenanceScanPlan(
                "structure",
                signals=(
                    MaintenanceSignal("dup", MAINTENANCE_SIGNAL_REDUCIBLE_BRANCH),
                    MaintenanceSignal("large", MAINTENANCE_SIGNAL_LARGE_MODULE),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(MAINTENANCE_SCAN_DECISION_REQUIRED, report.decision)
        self.assertIn(MAINTENANCE_ROUTE_ARCHITECTURE_REDUCTION, routes(report))
        self.assertIn(MAINTENANCE_ROUTE_STRUCTURE_MESH, routes(report))
        action_by_route = {action.route_id: action for action in report.actions}
        self.assertEqual(MAINTENANCE_ACTION_SUGGESTED, action_by_route[MAINTENANCE_ROUTE_ARCHITECTURE_REDUCTION].strength)

    def test_state_closure_gap_routes_to_model_maturation(self):
        report = review_maintenance_scan(
            MaintenanceScanPlan(
                "state-closure",
                signals=(
                    MaintenanceSignal(
                        "unknown-state",
                        MAINTENANCE_SIGNAL_STATE_CLOSURE_GAP,
                        description="Runner found an automatic state/input closure confidence gap.",
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(MAINTENANCE_SCAN_DECISION_REQUIRED, report.decision)
        self.assertIn(MAINTENANCE_ROUTE_MODEL_MATURATION, routes(report))

    def test_model_angle_gap_routes_to_model_maturation(self):
        report = review_maintenance_scan(
            MaintenanceScanPlan(
                "model-angle",
                signals=(
                    MaintenanceSignal(
                        "angle-open",
                        MAINTENANCE_SIGNAL_MODEL_ANGLE_GAP,
                        description="Model-angle deliberation found an unresolved candidate model boundary.",
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(MAINTENANCE_SCAN_DECISION_REQUIRED, report.decision)
        self.assertIn(MAINTENANCE_ROUTE_MODEL_MATURATION, routes(report))

    def test_business_path_signals_route_to_existing_owners(self):
        report = review_maintenance_scan(
            MaintenanceScanPlan(
                "business-paths",
                signals=(
                    MaintenanceSignal("dup-path", MAINTENANCE_SIGNAL_BUSINESS_PATH_DUPLICATE),
                    MaintenanceSignal("conflict-path", MAINTENANCE_SIGNAL_BUSINESS_PATH_CONFLICT),
                    MaintenanceSignal("unproven-path", MAINTENANCE_SIGNAL_BUSINESS_PATH_UNPROVEN),
                    MaintenanceSignal("legacy-path", MAINTENANCE_SIGNAL_BUSINESS_PATH_LEGACY_DISPOSITION),
                ),
            )
        )

        action_by_signal = {signal_id: action for action in report.actions for signal_id in action.signal_ids}
        self.assertFalse(report.ok)
        self.assertEqual(MAINTENANCE_ROUTE_MODEL_SIMILARITY, action_by_signal["dup-path"].route_id)
        self.assertEqual(MAINTENANCE_ACTION_SUGGESTED, action_by_signal["dup-path"].strength)
        self.assertEqual(MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT, action_by_signal["conflict-path"].route_id)
        self.assertEqual(MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT, action_by_signal["unproven-path"].route_id)
        self.assertEqual(MAINTENANCE_ROUTE_ARCHITECTURE_REDUCTION, action_by_signal["legacy-path"].route_id)

    def test_summary_report_bridge_routes_structured_gap_to_scan_action(self):
        summary = FlowGuardSummaryReport.from_sections(
            (
                FlowGuardSection(
                    "conformance",
                    "not_run",
                    "conformance_status not provided",
                ),
            )
        )

        plan = maintenance_scan_plan_from_summary_report(
            summary,
            plan_id="summary-bridge",
            claim_scope="done",
        )
        report = review_maintenance_scan(plan)

        self.assertTrue(report.ok)
        self.assertEqual(MAINTENANCE_SCAN_DECISION_SUGGESTED, report.decision)
        self.assertEqual((MAINTENANCE_ROUTE_DEVELOPMENT_PROCESS_FLOW,), tuple(action.route_id for action in report.actions))
        action = report.actions[0]
        self.assertEqual("scoped_until_resolved", action.claim_effect)
        self.assertIn("proof_artifact", action.required_input_kinds)
        self.assertIn("missing_conformance_proof", action.proof_gap_codes)

    def test_signal_metadata_is_preserved_on_maintenance_action(self):
        report = review_maintenance_scan(
            MaintenanceScanPlan(
                "metadata",
                signals=(
                    MaintenanceSignal(
                        "alignment-gap",
                        "model_code_test_mismatch",
                        route_id=MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT,
                        required_input_kinds=("code_contract", "test_evidence"),
                        proof_gap_codes=("missing_external_contract_test",),
                        claim_effect="blocked_until_resolved",
                        suggested_commands=("run model-test alignment",),
                        source_obligation_ids=("summary:model_check:1",),
                    ),
                ),
            )
        )

        action = report.actions[0]
        self.assertEqual(("code_contract", "test_evidence"), action.required_input_kinds)
        self.assertEqual(("missing_external_contract_test",), action.proof_gap_codes)
        self.assertEqual("blocked_until_resolved", action.claim_effect)
        self.assertEqual(("run model-test alignment",), action.suggested_commands)
        self.assertEqual(("summary:model_check:1",), action.source_obligation_ids)

    def test_prior_obligation_reopens_when_changed_anchor_is_touched(self):
        report = review_maintenance_scan(
            MaintenanceScanPlan(
                "prior-obligation",
                changed_artifacts=(
                    MaintenanceChangedArtifact(
                        "checkout-module",
                        MAINTENANCE_ARTIFACT_CODE,
                        path="src/flowguard/checkout.py",
                    ),
                ),
                prior_obligations=(
                    MaintenanceObligation(
                        "structure:checkout",
                        owner_route=MAINTENANCE_ROUTE_STRUCTURE_MESH,
                        reason_code="large_module",
                        anchor_paths=("flowguard/checkout.py",),
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(("structure:checkout",), report.reopened_obligation_ids)
        self.assertEqual(("structure:checkout",), report.visible_obligation_ids)
        self.assertIn(MAINTENANCE_ROUTE_STRUCTURE_MESH, routes(report))

    def test_unanchored_prior_obligation_is_visible_but_not_reopened(self):
        report = review_maintenance_scan(
            MaintenanceScanPlan(
                "prior-observation",
                changed_artifacts=(
                    MaintenanceChangedArtifact("checkout-module", MAINTENANCE_ARTIFACT_CODE),
                ),
                prior_obligations=(
                    MaintenanceObligation(
                        "structure:unanchored",
                        owner_route=MAINTENANCE_ROUTE_STRUCTURE_MESH,
                        reason_code="large_module",
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(MAINTENANCE_SCAN_DECISION_CLEAR, report.decision)
        self.assertEqual((), report.reopened_obligation_ids)
        self.assertEqual(("structure:unanchored",), report.visible_obligation_ids)

    def test_current_owner_evidence_resolves_reopened_prior_obligation(self):
        report = review_maintenance_scan(
            MaintenanceScanPlan(
                "prior-obligation-resolved",
                changed_artifacts=(
                    MaintenanceChangedArtifact(
                        "checkout-module",
                        MAINTENANCE_ARTIFACT_CODE,
                        path="src/flowguard/checkout.py",
                    ),
                ),
                prior_obligations=(
                    MaintenanceObligation(
                        "structure:checkout",
                        owner_route=MAINTENANCE_ROUTE_STRUCTURE_MESH,
                        reason_code="large_module",
                        anchor_paths=("flowguard/checkout.py",),
                    ),
                ),
                evidence=(
                    MaintenanceEvidence(
                        "structure-current",
                        MAINTENANCE_ROUTE_STRUCTURE_MESH,
                        status="passed",
                        current=True,
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(MAINTENANCE_SCAN_DECISION_REQUIRED, report.decision)
        self.assertEqual(("structure-current",), report.actions[0].owner_evidence_ids)
        self.assertEqual((), report.unresolved_required_action_ids)

    def test_template_cli_and_written_example_run(self):
        printed = subprocess.run(
            [sys.executable, "-m", "flowguard", "maintenance-scan-template"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, printed.returncode, printed.stderr)
        data = json.loads(printed.stdout)
        self.assertEqual("maintenance_scan", data["template"])
        self.assertIn(".flowguard/maintenance_scan/run_scan.py", {item["path"] for item in data["files"]})

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_template_files(root, maintenance_scan_template_files())
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
            result = subprocess.run(
                [sys.executable, "run_scan.py"],
                cwd=root / ".flowguard" / "maintenance_scan",
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("clear: maintenance_scan_clear", result.stdout)
            self.assertIn("alignment_needed: maintenance_scan_scoped_confidence", result.stdout)
            self.assertIn("structure_needed: maintenance_scan_actions_required", result.stdout)

    def test_self_model_checks_pass(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, ".flowguard/maintenance_scan_router/run_checks.py"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(
            "correct_maintenance_scan_router: observed=OK expected=OK match=yes",
            result.stdout,
        )
        self.assertIn("maintenance_scan_bad_claim: observed=VIOLATION expected=VIOLATION", result.stdout)


if __name__ == "__main__":
    unittest.main()
