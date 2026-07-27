from __future__ import annotations

import unittest

from flowguard import (
    BCL_DISPOSITION_DELEGATED,
    BCL_DISPOSITION_MODELED,
    BehaviorCommitment,
    BehaviorCommitmentLedger,
    BehaviorEvidenceBinding,
    FieldLifecyclePlan,
    FieldLifecycleRow,
    UIObservedSurfaceInventory,
    UIObservedSurfaceItem,
    WorkContext,
    WorkContextArtifact,
    build_expected_coverage_inventory,
    project_expected_item_to_behavior_surface,
    review_behavior_commitment_ledger,
    review_expected_coverage_inventory,
)


class ExpectedCoverageInventoryTests(unittest.TestCase):
    def inventory(self):
        context = WorkContext(
            context_id="planner:change",
            adapter_id="declared-files",
            native_work_id="change",
            native_owner_id="planner",
            project_root="C:/project",
            context_root="C:/project/plans",
            artifacts=(
                WorkContextArtifact(
                    "requirement:one",
                    "requirement",
                    "plans/requirement.md",
                    "sha256:requirement-content",
                    10,
                ),
            ),
            context_fingerprint="sha256:context",
            behavior_source_surface_ids=("surface:requirement:one",),
        )
        ui = UIObservedSurfaceInventory(
            "ui:observed",
            "application",
            "rev-1",
            observation_method="browser",
            source_interaction_model_id="ui:model",
            evidence_ref="evidence:ui",
            items=(
                UIObservedSurfaceItem(
                    "button:submit",
                    "button",
                    state_id="ready",
                    enabled=True,
                    mapped_control_id="control:submit",
                    evidence_ref="evidence:button",
                    rationale="visible enabled control",
                ),
            ),
            validation_boundaries=("browser click-through",),
            rationale="complete rendered surface",
        )
        fields = FieldLifecyclePlan(
            "fields:payload",
            discovered_field_ids=("field:status",),
            fields=(
                FieldLifecycleRow(
                    "field:status",
                    locations=("payload.status",),
                    reader_ids=("ui:model",),
                    writer_ids=("workflow:model",),
                    behavior_impacts=("output",),
                    disposition_evidence_refs=("evidence:field",),
                ),
            ),
        )
        return build_expected_coverage_inventory(
            "expected:all",
            boundary="application",
            revision="rev-1",
            discovery_evidence_ids=("discovery:rev-1",),
            work_contexts=(context,),
            ui_inventories=(ui,),
            field_plans=(fields,),
        )

    def test_native_inventories_form_one_stable_exact_set(self):
        inventory = self.inventory()
        report = review_expected_coverage_inventory(inventory)

        self.assertTrue(report.ok, report.to_dict())
        self.assertEqual(
            {
                "work-context:planner:change:requirement:one",
                "ui:ui:observed:button:submit",
                "field:fields:payload:field:status",
            },
            set(inventory.item_ids()),
        )
        self.assertTrue(inventory.inventory_fingerprint.startswith("sha256:"))

    def test_unmapped_work_context_remains_context_only(self):
        context = WorkContext(
            context_id="planner:context-only",
            adapter_id="declared-files",
            native_work_id="context-only",
            native_owner_id="planner",
            project_root="C:/project",
            context_root="C:/project/plans",
            artifacts=(
                WorkContextArtifact(
                    "task:one",
                    "task",
                    "plans/task.md",
                    "sha256:task-content",
                    8,
                ),
            ),
            context_fingerprint="sha256:context-only",
        )

        inventory = build_expected_coverage_inventory(
            "expected:context-only",
            boundary="application",
            revision="rev-1",
            discovery_evidence_ids=("discovery:rev-1",),
            work_contexts=(context,),
        )

        self.assertEqual((), inventory.items)

    def test_missing_expected_item_blocks_ledger_even_when_remaining_row_is_green(self):
        inventory = self.inventory()
        requirement = inventory.items[0]
        surface = project_expected_item_to_behavior_surface(
            requirement,
            inventory_revision=inventory.revision,
            coverage_disposition=BCL_DISPOSITION_MODELED,
            commitment_id="commitment:requirement",
            business_intent_id="intent:requirement",
        )
        commitment = BehaviorCommitment(
            "commitment:requirement",
            business_intent_id="intent:requirement",
            label="apply requirement",
            behavior_plane="product_runtime",
            actor_kind="end_user",
            actor="user",
            trigger="submits",
            expected_result="accepted or visible error",
            expected_terminal="accepted or visible error",
            failure_boundary="visible error",
            source_surface_ids=(surface.surface_id,),
            primary_owner_model_id="model:requirement",
            validation_boundary="model and test",
            rationale="external behavior",
            evidence=BehaviorEvidenceBinding(
                model_obligation_ids=("obligation:requirement",),
                code_contract_ids=("contract:requirement",),
                test_evidence_ids=("test:requirement",),
                evidence_state="current_pass",
                current=True,
            ),
        )
        ledger = BehaviorCommitmentLedger(
            "ledger",
            project_boundary=inventory.boundary,
            current_revision=inventory.revision,
            subject_lane="normative_target",
            expected_source_surface_ids=inventory.item_ids(),
            source_inventory_revision=inventory.revision,
            source_inventory_fingerprint=inventory.inventory_fingerprint,
            source_inventory_evidence_ids=inventory.discovery_evidence_ids,
            require_complete_source_inventory=True,
            expected_commitment_ids=(commitment.commitment_id,),
            expected_business_intent_ids=(commitment.business_intent_id,),
            source_surfaces=(surface,),
            commitments=(commitment,),
            claim_scope="full",
            owner="maintainer",
            validation_boundary="complete application",
            rationale="exact native inventory reconciliation",
        )

        report = review_behavior_commitment_ledger(ledger)

        self.assertFalse(report.ok)
        self.assertEqual(
            {
                "field:fields:payload:field:status",
                "ui:ui:observed:button:submit",
            },
            set(report.missing_source_surface_ids),
        )

    def test_specialist_items_can_delegate_without_becoming_second_commitments(self):
        inventory = self.inventory()
        ui_item = next(
            item for item in inventory.items if item.source_kind == "ui"
        )
        surface = project_expected_item_to_behavior_surface(
            ui_item,
            inventory_revision=inventory.revision,
            coverage_disposition=BCL_DISPOSITION_DELEGATED,
            delegated_owner_inventory_id="ui:observed",
            delegation_relation_type="specialist_inventory_owns",
            native_evidence_ids=("evidence:ui",),
        )

        self.assertEqual(BCL_DISPOSITION_DELEGATED, surface.coverage_disposition)
        self.assertFalse(surface.commitment_ids)
        self.assertEqual("ui:observed", surface.delegated_owner_inventory_id)


if __name__ == "__main__":
    unittest.main()
