import unittest
from dataclasses import dataclass

from flowguard import (
    FunctionResult,
    KnownBadProof,
    MinimumModelContract,
    RiskIntent,
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
    UsageIntent,
    Workflow,
    infer_topology_digest,
    infer_topology_hazard_plan,
    review_topology_hazards,
)
from flowguard.plan import FlowGuardCheckPlan
from flowguard.runner import run_model_first_checks




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
                blindspots=("real storage replay is not part of this topology test",),
            ),
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

def test_topology_scope_out_without_reason_blocks():
    from dataclasses import dataclass, replace
    from flowguard import (TOPOLOGY_DISPOSITION_SCOPED_OUT, TOPOLOGY_USAGE_RELEASE, FunctionResult, UsageIntent,
                           Workflow, derive_topology_hazard_candidates, infer_topology_hazard_plan,
                           review_topology_hazards)

    @dataclass(frozen=True)
    class Ev:
        action: str = "submit"

    @dataclass(frozen=True)
    class St:
        count: int = 0

    class Save:
        name = "Save"
        reads = ()
        writes = ("count",)
        side_effects = ("database_write",)

        def apply(self, input_obj, state):
            return (FunctionResult(input_obj, St(1), label="saved"),)

    def scoped(reason):
        plan = infer_topology_hazard_plan(
            workflow=Workflow((Save(),), name="save"), initial_states=(St(),), external_inputs=(Ev(),),
            usage_intent=UsageIntent(usage_modes=(TOPOLOGY_USAGE_RELEASE,), final_claim="release"))
        candidates = tuple(replace(c, disposition=TOPOLOGY_DISPOSITION_SCOPED_OUT, scoped_reason=reason)
                           for c in derive_topology_hazard_candidates(plan.digest))
        return review_topology_hazards(replace(plan, candidates=candidates))

    bare = scoped("")
    assert not bare.ok
    assert "topology_hazard_scoped_out_without_reason" in {f.code for f in bare.findings}
    reasoned = scoped("idempotency key covered by tests/test_orders.py::test_retry")
    assert "topology_hazard_scoped_out_without_reason" not in {f.code for f in reasoned.findings}


def test_single_state_writer_with_effect_is_not_shared():
    from flowguard import TOPOLOGY_USAGE_LOCAL

    plan = infer_topology_hazard_plan(
        workflow=Workflow((SaveRecord(),), name="save"),
        initial_states=(State(),), external_inputs=(),
        usage_intent=UsageIntent(usage_modes=(TOPOLOGY_USAGE_LOCAL,), final_claim="local"),
    )
    assert [item for item in plan.digest.landmarks if item.landmark_type == "shared_writer"] == []
    assert review_topology_hazards(plan).confidence == TOPOLOGY_CONFIDENCE_FULL


def test_two_distinct_state_writers_are_still_shared():
    from flowguard import TOPOLOGY_USAGE_LOCAL

    class SecondSave(SaveRecord):
        name = "SecondSave"
        side_effects = ()

    plan = infer_topology_hazard_plan(
        workflow=Workflow((SaveRecord(), SecondSave()), name="two saves"),
        initial_states=(State(),), external_inputs=(),
        usage_intent=UsageIntent(usage_modes=(TOPOLOGY_USAGE_LOCAL,), final_claim="local"),
    )
    shared = next(item for item in plan.digest.landmarks
                  if item.landmark_id == "landmark:shared-writer:saved_record")
    assert shared.anchor_ids == ("edge:0:SaveRecord", "edge:1:SecondSave")


if __name__ == "__main__":
    unittest.main()
