import hashlib
import unittest
from pathlib import Path

import flowguard
from flowguard import (
    BCL_ACTOR_AI_AGENT,
    BCL_ACTOR_AUTOMATION,
    BCL_ACTOR_END_USER,
    BCL_PLANE_AGENT_OPERATION,
    BCL_PLANE_DEVELOPMENT_PROCESS,
    BCL_PLANE_PRODUCT_RUNTIME,
    BCL_RELATION_GOVERNS,
    BCL_RELATION_INVOKES,
    BCL_RELATION_REQUIRES_EVIDENCE_FROM,
    BCL_RELATION_VALIDATES,
    MODEL_MISS_BACKFEED_COVERAGE_GAP,
    MODEL_MISS_BACKFEED_REUSE_EXISTING,
    BehaviorCommitment,
    BehaviorCommitmentLedger,
    BehaviorCommitmentRelation,
    BehaviorLookupBinding,
    UIModelMissRecord,
    UIModelMissReviewPlan,
    apply_model_miss_behavior_backfeed,
    backfeed_model_miss_to_behavior_ledger,
    behavior_commitment_relation_allowed,
    review_behavior_commitment_ledger,
    review_ui_model_misses,
)


ROOT = Path(__file__).resolve().parents[1]


def openspec_change_artifact(change_id: str, artifact_name: str) -> Path:
    active_path = ROOT / "openspec" / "changes" / change_id / artifact_name
    if active_path.exists():
        return active_path
    archived_paths = sorted(
        (ROOT / "openspec" / "changes" / "archive").glob(
            f"*-{change_id}/{artifact_name}"
        )
    )
    if archived_paths:
        return archived_paths[-1]
    return active_path


def row(
    commitment_id: str,
    *,
    plane: str,
    actor_kind: str,
    relations=(),
    lookup_binding=None,
) -> BehaviorCommitment:
    return BehaviorCommitment(
        commitment_id,
        label=commitment_id,
        behavior_plane=plane,
        actor_kind=actor_kind,
        actor=actor_kind,
        trigger="task reaches this registered boundary",
        expected_result="the declared owner completes or visibly fails the behavior",
        failure_boundary="no automatic alternate success path",
        source_refs=(f"specs/{commitment_id}.md",),
        primary_owner_model_id=f"model:{commitment_id}",
        relations=relations,
        lookup_binding=lookup_binding,
        validation_boundary="owner model and focused tests",
        rationale="plane partition test",
    )


def ledger(*rows: BehaviorCommitment) -> BehaviorCommitmentLedger:
    return BehaviorCommitmentLedger(
        "ledger:plane-upgrade",
        project_boundary="behavior-plane tests",
        current_revision="rev-1",
        commitments=rows,
        expected_commitment_ids=tuple(item.commitment_id for item in rows),
        owner="tests",
        validation_boundary="ledger review",
        rationale="prove planes stay separate while typed relations connect them",
    )


def finding_codes(report):
    return {finding.code for finding in report.findings}


class BehaviorPlaneUpgradeTests(unittest.TestCase):
    def test_public_guidance_explains_planes_lookup_and_non_guarantee_boundary(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        ledger_docs = (ROOT / "docs" / "behavior_commitment_ledger.md").read_text(
            encoding="utf-8"
        )
        preflight_docs = (ROOT / "docs" / "existing_model_preflight.md").read_text(
            encoding="utf-8"
        )
        combined = "\n".join((readme, ledger_docs, preflight_docs))

        for value in (
            "product_runtime",
            "agent_operation",
            "development_process",
            "behavior-commitment-query",
            "primary_commitment_hits",
            "related_commitment_hits",
            "ledger_fingerprint",
        ):
            self.assertIn(value, combined)
        self.assertIn("does not force every ordinary action", combined)
        self.assertIn("cannot guarantee", combined)
        self.assertNotIn("evidence engine, or\n  CLI command", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_verification_contract_uses_receipt_authority_without_self_maintenance_hash_coupling(self):
        contract_path = openspec_change_artifact(
            "partition-behavior-commitments-by-execution-plane",
            "verification-contract.yaml",
        )
        contract = contract_path.read_text(encoding="utf-8")

        for value in (
            "default_replacement_field_lifecycle",
            "model_test_code_alignment",
            "owner.models.full",
            "owner.tests.full",
            "owner.change.aggregate",
            "portable-receipt.v1",
            ".flowguard/default_replacement_field_lifecycle/**/*.py",
            ".flowguard/model_test_code_alignment/**/*.py",
            "README.md",
            "CHANGELOG.md",
        ):
            self.assertIn(value, contract)
        self_maintenance_model = (
            ROOT / ".flowguard" / "self_maintenance_mesh" / "model.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("verification_contract_sha256", self_maintenance_model)
        self.assertNotIn("required_verification_check_ids", self_maintenance_model)

    def test_relation_matrix_preserves_directional_layer_ownership(self):
        self.assertTrue(
            behavior_commitment_relation_allowed(
                BCL_PLANE_AGENT_OPERATION,
                BCL_PLANE_PRODUCT_RUNTIME,
                BCL_RELATION_INVOKES,
            )
        )
        self.assertTrue(
            behavior_commitment_relation_allowed(
                BCL_PLANE_DEVELOPMENT_PROCESS,
                BCL_PLANE_AGENT_OPERATION,
                BCL_RELATION_GOVERNS,
            )
        )
        self.assertTrue(
            behavior_commitment_relation_allowed(
                BCL_PLANE_DEVELOPMENT_PROCESS,
                BCL_PLANE_PRODUCT_RUNTIME,
                BCL_RELATION_REQUIRES_EVIDENCE_FROM,
            )
        )
        self.assertFalse(
            behavior_commitment_relation_allowed(
                BCL_PLANE_PRODUCT_RUNTIME,
                BCL_PLANE_AGENT_OPERATION,
                BCL_RELATION_INVOKES,
            )
        )
        self.assertFalse(
            behavior_commitment_relation_allowed(
                BCL_PLANE_AGENT_OPERATION,
                BCL_PLANE_DEVELOPMENT_PROCESS,
                BCL_RELATION_GOVERNS,
            )
        )

    def test_valid_product_agent_process_chain_passes_same_ledger_review(self):
        product = row(
            "commitment:product-download",
            plane=BCL_PLANE_PRODUCT_RUNTIME,
            actor_kind=BCL_ACTOR_END_USER,
        )
        agent = row(
            "commitment:agent-download-operation",
            plane=BCL_PLANE_AGENT_OPERATION,
            actor_kind=BCL_ACTOR_AI_AGENT,
            relations=(
                BehaviorCommitmentRelation(
                    product.commitment_id,
                    BCL_RELATION_INVOKES,
                    "The AI invokes the product download but does not become its owner.",
                ),
            ),
        )
        process = row(
            "commitment:download-release-validation",
            plane=BCL_PLANE_DEVELOPMENT_PROCESS,
            actor_kind=BCL_ACTOR_AUTOMATION,
            relations=(
                BehaviorCommitmentRelation(
                    agent.commitment_id,
                    BCL_RELATION_VALIDATES,
                    "Release validation consumes the AI-operation receipt.",
                ),
            ),
        )

        report = review_behavior_commitment_ledger(ledger(product, agent, process))

        self.assertTrue(report.ok, report.format_text())

    def test_cross_plane_relation_requires_rationale(self):
        product = row(
            "commitment:product-download",
            plane=BCL_PLANE_PRODUCT_RUNTIME,
            actor_kind=BCL_ACTOR_END_USER,
        )
        agent = row(
            "commitment:agent-download-operation",
            plane=BCL_PLANE_AGENT_OPERATION,
            actor_kind=BCL_ACTOR_AI_AGENT,
            relations=(
                BehaviorCommitmentRelation(product.commitment_id, BCL_RELATION_INVOKES),
            ),
        )

        report = review_behavior_commitment_ledger(ledger(product, agent))

        self.assertIn(
            "commitment_cross_plane_relation_missing_rationale",
            finding_codes(report),
        )

    def test_wrong_relation_direction_is_blocked_even_with_rationale(self):
        agent = row(
            "commitment:agent-download-operation",
            plane=BCL_PLANE_AGENT_OPERATION,
            actor_kind=BCL_ACTOR_AI_AGENT,
        )
        product = row(
            "commitment:product-download",
            plane=BCL_PLANE_PRODUCT_RUNTIME,
            actor_kind=BCL_ACTOR_END_USER,
            relations=(
                BehaviorCommitmentRelation(
                    agent.commitment_id,
                    BCL_RELATION_INVOKES,
                    "This wording cannot make product runtime own an AI operation.",
                ),
            ),
        )

        report = review_behavior_commitment_ledger(ledger(product, agent))

        self.assertIn("commitment_relation_plane_mismatch", finding_codes(report))

    def test_unclassified_or_display_label_actor_values_do_not_enter_runtime(self):
        invalid = row(
            "commitment:ambiguous",
            plane="unclassified",
            actor_kind="AI助手",
        )

        report = review_behavior_commitment_ledger(ledger(invalid))

        self.assertIn("commitment_behavior_plane_missing_or_invalid", finding_codes(report))
        self.assertIn("commitment_actor_kind_missing_or_invalid", finding_codes(report))

    def test_plane_upgrade_does_not_add_a_parallel_flowguard_route(self):
        route_ids = set(flowguard.FLOWGUARD_ROUTE_API)

        self.assertNotIn("behavior_commitment_lookup", route_ids)
        self.assertNotIn("agent_operation_flowguard", route_ids)
        self.assertIn("behavior_commitment_ledger", route_ids)
        self.assertIn("existing_model_preflight", route_ids)

    def test_model_miss_reuses_same_plane_commitment_and_keeps_related_context_typed(self):
        product = row(
            "commitment:product-ui-proxy",
            plane=BCL_PLANE_PRODUCT_RUNTIME,
            actor_kind=BCL_ACTOR_END_USER,
            lookup_binding=BehaviorLookupBinding(task_terms=("UI proxy",)),
        )
        agent = row(
            "commitment:agent-port-bridge",
            plane=BCL_PLANE_AGENT_OPERATION,
            actor_kind=BCL_ACTOR_AI_AGENT,
            lookup_binding=BehaviorLookupBinding(
                task_terms=("port bridge",),
                error_signatures=("ECONNREFUSED:4173",),
            ),
            relations=(
                BehaviorCommitmentRelation(
                    product.commitment_id,
                    BCL_RELATION_INVOKES,
                    "The AI port bridge invokes, but does not own, the product proxy.",
                ),
            ),
        )
        process = row(
            "commitment:process-ui-handoff-check",
            plane=BCL_PLANE_DEVELOPMENT_PROCESS,
            actor_kind=BCL_ACTOR_AUTOMATION,
            relations=(
                BehaviorCommitmentRelation(
                    agent.commitment_id,
                    BCL_RELATION_VALIDATES,
                    "The development process validates the operational receipt.",
                ),
            ),
        )
        miss = UIModelMissRecord(
            "miss:port-bridge",
            previous_claim_id="claim:ui-ready",
            previous_green_reason="the UI server itself was healthy",
            observed_failure="ECONNREFUSED:4173 after handing the UI to the next port",
            observed_failure_evidence_ref="log:port-bridge-failure",
            affected_capability_ids=("capability:ui-handoff",),
            same_class_capability_ids=("capability:ui-handoff",),
            required_test_ids=("test:port-bridge",),
            root_cause_backpropagation="model the missing connect-and-health-check operation",
            code_owner="agent-ui-handoff",
            rationale="the failed promise belongs to the AI operation, not the product download",
            affected_behavior_plane=BCL_PLANE_AGENT_OPERATION,
            error_signatures=("ECONNREFUSED:4173",),
            error_evidence_ids=("log:port-bridge-failure",),
        )

        backfeed = backfeed_model_miss_to_behavior_ledger(
            miss,
            ledger(product, agent, process),
        )
        bound = apply_model_miss_behavior_backfeed(miss, backfeed)
        report = review_ui_model_misses(
            UIModelMissReviewPlan(
                "plan:port-bridge",
                (bound,),
                require_behavior_binding=True,
            )
        )

        self.assertEqual(MODEL_MISS_BACKFEED_REUSE_EXISTING, backfeed.disposition)
        self.assertEqual(agent.commitment_id, bound.affected_commitment_id)
        self.assertEqual(agent.primary_owner_model_id, bound.primary_owner_model_id)
        self.assertEqual(
            {product.commitment_id, process.commitment_id},
            {context.commitment_id for context in bound.related_behavior_context},
        )
        self.assertTrue(report.ok, report.to_dict())

    def test_model_miss_proposes_coverage_gap_only_after_same_plane_lookup_has_no_hit(self):
        existing = row(
            "commitment:product-download",
            plane=BCL_PLANE_PRODUCT_RUNTIME,
            actor_kind=BCL_ACTOR_END_USER,
            lookup_binding=BehaviorLookupBinding(task_terms=("download",)),
        )
        miss = UIModelMissRecord(
            "miss:unknown-agent-operation",
            observed_failure="agent forgot to combine artifacts before publishing",
            affected_behavior_plane=BCL_PLANE_AGENT_OPERATION,
            error_signatures=("artifact composition missing",),
            error_evidence_ids=("log:publish-miss",),
        )

        backfeed = backfeed_model_miss_to_behavior_ledger(miss, ledger(existing))
        bound = apply_model_miss_behavior_backfeed(miss, backfeed)

        self.assertEqual(MODEL_MISS_BACKFEED_COVERAGE_GAP, backfeed.disposition)
        self.assertTrue(bound.behavior_coverage_gap_candidate)
        self.assertEqual("", bound.affected_commitment_id)


if __name__ == "__main__":
    unittest.main()
