import subprocess
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

from flowguard import (
    FunctionResult,
    KnownBadProof,
    MAINTENANCE_ROUTE_MODEL_MATURATION,
    MAINTENANCE_SIGNAL_TOPOLOGY_HAZARD_GAP,
    MinimumModelContract,
    RISK_CONFIDENCE_BLOCKED,
    RISK_GATE_TOPOLOGY_HAZARD,
    RiskIntent,
    RiskEvidenceGate,
    RiskEvidenceLedgerPlan,
    RiskEvidenceRow,
    RiskProfile,
    BusinessPathIdentity,
    TOPOLOGY_LANDMARK_BUSINESS_PATH_CONFLICT,
    TOPOLOGY_LANDMARK_BUSINESS_PATH_DUPLICATE,
    TOPOLOGY_LANDMARK_BUSINESS_PATH_LEGACY_DISPOSITION,
    TOPOLOGY_LANDMARK_BUSINESS_PATH_UNPROVEN,
    TOPOLOGY_COMPAT_UNKNOWN,
    TOPOLOGY_CONFIDENCE_BLOCKED,
    TOPOLOGY_CONFIDENCE_FULL,
    TOPOLOGY_DISPOSITION_BLOCKED,
    TOPOLOGY_DISPOSITION_LEDGER_REQUIRED,
    TOPOLOGY_SEVERITY_BLOCKER,
    TOPOLOGY_USAGE_RELEASE,
    TopologyHazardCandidate,
    TopologyHazardReviewPlan,
    TemplateHarvestReview,
    TemplateReuseReview,
    UsageIntent,
    Workflow,
    infer_topology_digest,
    infer_topology_hazard_plan,
    review_maintenance_scan,
    review_risk_evidence_ledger,
    review_topology_hazards,
)
from flowguard.maintenance_scan import MaintenanceScanPlan, MaintenanceSignal
from flowguard.plan import FlowGuardCheckPlan
from flowguard.runner import run_model_first_checks


ROOT = Path(__file__).resolve().parents[1]


def formal_entry_kwargs():
    return {
        "risk_profile": RiskProfile(
            modeled_boundary="save topology",
            risk_classes=("side_effect",),
            risk_intent=RiskIntent(
                failure_modes=("save completes without durable record",),
                protected_error_classes=("missing_save_evidence",),
                protected_harms=("caller trusts a missing record",),
                must_model_state=("saved_record", "status"),
                must_model_side_effects=("record_write",),
                completion_evidence=("saved_label",),
                adversarial_inputs=("save event repeated",),
                hard_invariants=("save has durable evidence",),
                known_bad_cases=("save_without_record",),
                template_no_match_reason="topology hazard unit test uses a local save model",
                blindspots=("real storage replay is not part of this topology test",),
            ),
        ),
        "template_reuse_review": TemplateReuseReview(
            no_match_reason="topology hazard unit test uses a local save model",
            searched_layers=("public", "local"),
        ),
        "template_harvest_review": TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        "minimum_model_contract": MinimumModelContract(
            protected_error_classes=("missing_save_evidence",),
            modeled_state=("saved_record", "status"),
            modeled_side_effects=("record_write",),
            completion_evidence=("saved_label",),
            known_bad_cases=("save_without_record",),
        ),
        "known_bad_proofs": (
            KnownBadProof(
                "save_without_record",
                protected_error_class="missing_save_evidence",
                method="broken_workflow",
                observed_status="failed",
                observed_failure="save completion without evidence rejected",
                evidence_id="model:save_without_record",
            ),
        ),
    }


@dataclass(frozen=True)
class Event:
    kind: str = "submit"


@dataclass(frozen=True)
class State:
    status: str = "idle"
    saved_record: str = ""


class SaveRecord:
    name = "SaveRecord"
    reads = ("status",)
    writes = ("saved_record", "status")
    side_effects = ("database_write",)

    def apply(self, input_obj, state):
        return (FunctionResult(input_obj, State("done", "saved"), label="saved"),)


class TopologyHazardTests(unittest.TestCase):
    def test_digest_derives_topology_landmarks_from_model_shape_and_usage(self):
        digest = infer_topology_digest(
            workflow=Workflow((SaveRecord(),), name="save"),
            initial_states=(State(),),
            external_inputs=(Event(),),
            usage_intent=UsageIntent(
                usage_modes=(TOPOLOGY_USAGE_RELEASE,),
                final_claim="release",
                persistent_history_possible=True,
                compatibility_policy=TOPOLOGY_COMPAT_UNKNOWN,
            ),
        )

        landmark_types = {landmark.landmark_type for landmark in digest.landmarks}

        self.assertIn("side_effect_repeat", landmark_types)
        self.assertIn("legacy_or_compatibility_path", landmark_types)
        self.assertIn("external_confirmation_boundary", landmark_types)

    def test_business_path_landmarks_surface_duplicate_conflict_unproven_and_legacy_gaps(self):
        plan = infer_topology_hazard_plan(
            workflow=Workflow((SaveRecord(),), name="checkout"),
            external_inputs=(Event(),),
            usage_intent=UsageIntent(usage_modes=(TOPOLOGY_USAGE_RELEASE,), final_claim="release"),
            business_paths=(
                BusinessPathIdentity(
                    "submit",
                    business_intent="submit order",
                    trigger="submit",
                    expected_terminal="accepted",
                    state_writes=("order_status",),
                    side_effects=("write_order",),
                    evidence_ids=("runtime:submit",),
                ),
                BusinessPathIdentity(
                    "submit_alias",
                    business_intent="submit order",
                    trigger="submit",
                    expected_terminal="accepted",
                    state_writes=("order_status",),
                    side_effects=("write_order",),
                ),
                BusinessPathIdentity(
                    "submit_reject",
                    business_intent="submit order",
                    trigger="submit",
                    expected_terminal="rejected",
                    state_writes=("order_status",),
                    side_effects=("write_rejection",),
                    evidence_ids=("runtime:reject",),
                ),
                BusinessPathIdentity(
                    "submit_v2",
                    business_intent="submit order v2",
                    trigger="upgrade",
                    expected_terminal="accepted",
                    state_writes=("order_status",),
                    side_effects=("write_order_v2",),
                    supersedes=("submit_v1",),
                    evidence_ids=("runtime:v2",),
                ),
            ),
        )

        landmark_types = {landmark.landmark_type for landmark in plan.digest.landmarks}
        report = review_topology_hazards(plan)

        self.assertIn(TOPOLOGY_LANDMARK_BUSINESS_PATH_DUPLICATE, landmark_types)
        self.assertIn(TOPOLOGY_LANDMARK_BUSINESS_PATH_CONFLICT, landmark_types)
        self.assertIn(TOPOLOGY_LANDMARK_BUSINESS_PATH_UNPROVEN, landmark_types)
        self.assertIn(TOPOLOGY_LANDMARK_BUSINESS_PATH_LEGACY_DISPOSITION, landmark_types)
        self.assertFalse(report.ok)
        self.assertIn("business_path:submit", plan.digest.anchor_ids())
        self.assertTrue(
            any("business-path" in candidate.hazard_id for candidate in report.candidates),
            report.format_text(),
        )

    def test_unanchored_ai_hazard_cannot_become_hard_gate(self):
        digest = infer_topology_digest(
            workflow=Workflow((SaveRecord(),), name="save"),
            initial_states=(State(),),
            external_inputs=(Event(),),
        )
        report = review_topology_hazards(
            TopologyHazardReviewPlan(
                "unanchored",
                digest=digest,
                candidates=(
                    TopologyHazardCandidate(
                        "hazard:generic",
                        "Generic future risk with no model anchor.",
                        disposition=TOPOLOGY_DISPOSITION_BLOCKED,
                        confidence_effect=TOPOLOGY_CONFIDENCE_BLOCKED,
                        severity=TOPOLOGY_SEVERITY_BLOCKER,
                    ),
                ),
                auto_generate_candidates=False,
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(TOPOLOGY_CONFIDENCE_FULL, report.confidence)
        self.assertIn("unanchored_hazard_observation_only", {finding.code for finding in report.findings})

    def test_anchored_broad_side_effect_hazard_blocks_until_handled(self):
        plan = infer_topology_hazard_plan(
            workflow=Workflow((SaveRecord(),), name="save"),
            initial_states=(State(),),
            external_inputs=(Event(),),
            usage_intent=UsageIntent(usage_modes=(TOPOLOGY_USAGE_RELEASE,), final_claim="release"),
        )
        report = review_topology_hazards(plan)

        self.assertFalse(report.ok)
        self.assertEqual(TOPOLOGY_CONFIDENCE_BLOCKED, report.confidence)
        self.assertTrue(report.unresolved_hazard_ids)

    def test_handled_anchored_hazard_passes(self):
        digest = infer_topology_digest(
            workflow=Workflow((SaveRecord(),), name="save"),
            initial_states=(State(),),
            external_inputs=(Event(),),
        )
        edge_id = digest.edges[0].edge_id
        report = review_topology_hazards(
            TopologyHazardReviewPlan(
                "handled",
                digest=digest,
                candidates=(
                    TopologyHazardCandidate(
                        "hazard:handled",
                        "Handled ledger risk.",
                        topology_anchor_ids=(edge_id,),
                        disposition=TOPOLOGY_DISPOSITION_LEDGER_REQUIRED,
                        handled=True,
                    ),
                ),
                auto_generate_candidates=False,
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(TOPOLOGY_CONFIDENCE_FULL, report.confidence)

    def test_runner_adds_topology_hazard_section(self):
        summary = run_model_first_checks(
            FlowGuardCheckPlan(
                workflow=Workflow((SaveRecord(),), name="save"),
                initial_states=(State(),),
                external_inputs=(Event(),),
                max_sequence_length=1,
                **formal_entry_kwargs(),
            )
        )
        sections = {section.name: section for section in summary.sections}
        metadata = dict(summary.metadata)

        self.assertIn("topology_hazard", sections)
        self.assertIn("topology_hazard_report", metadata)

    def test_maintenance_scan_routes_topology_hazard_gap(self):
        report = review_maintenance_scan(
            MaintenanceScanPlan(
                "topology-gap",
                signals=(
                    MaintenanceSignal(
                        "topology:coarse-done",
                        MAINTENANCE_SIGNAL_TOPOLOGY_HAZARD_GAP,
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn(MAINTENANCE_ROUTE_MODEL_MATURATION, {action.route_id for action in report.actions})

    def test_risk_ledger_consumes_topology_hazard_review(self):
        report = review_risk_evidence_ledger(
            RiskEvidenceLedgerPlan(
                "ledger",
                rows=(
                    RiskEvidenceRow(
                        "future-use-risk",
                        model_obligation_id="model:future-use",
                        proof_evidence_ids=("proof:ok",),
                        gates=(RiskEvidenceGate(RISK_GATE_TOPOLOGY_HAZARD),),
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_topology_hazard_review", {finding.code for finding in report.findings})

        blocked = review_risk_evidence_ledger(
            RiskEvidenceLedgerPlan(
                "ledger",
                rows=(
                    RiskEvidenceRow(
                        "future-use-risk",
                        model_obligation_id="model:future-use",
                        proof_evidence_ids=("proof:ok",),
                        gates=(
                            RiskEvidenceGate(
                                RISK_GATE_TOPOLOGY_HAZARD,
                                "topology:review",
                                confidence=RISK_CONFIDENCE_BLOCKED,
                            ),
                        ),
                    ),
                ),
            )
        )

        self.assertIn("topology_hazard_review_blocked", {finding.code for finding in blocked.findings})

    def test_self_model_checks_pass(self):
        result = subprocess.run(
            [sys.executable, ".flowguard/model_topology_hazard_review/run_checks.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("correct_topology_hazard_review: observed=OK expected=OK match=yes", result.stdout)
        self.assertIn(
            "topology_hazard_unanchored_hard_gate: observed=VIOLATION expected=VIOLATION",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
