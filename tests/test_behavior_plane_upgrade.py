import unittest
from pathlib import Path

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
    BehaviorCommitment,
    BehaviorCommitmentLedger,
    BehaviorCommitmentRelation,
    BehaviorLookupBinding,
    behavior_commitment_relation_allowed,
    review_behavior_commitment_ledger,
)


ROOT = Path(__file__).resolve().parents[1]


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

if __name__ == "__main__":
    unittest.main()
