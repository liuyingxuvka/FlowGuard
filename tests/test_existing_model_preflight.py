import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard import (
    DuplicateBoundaryRisk,
    ExistingModelPreflight,
    ExistingOwnershipSnapshot,
    MODEL_ANGLE_ACTION_EXTEND_EXISTING,
    ModelContextHit,
    ModelAngleDeliberation,
    REUSE_DECISION_ADD_CHILD_MODEL,
    REUSE_DECISION_EXTEND_EXISTING,
    REUSE_DECISION_NO_MODEL_FOUND,
    REUSE_DECISION_REUSE_EXISTING,
    REUSE_DECISION_SKIP,
    existing_model_preflight_from_project,
    review_existing_model_preflight,
)
from flowguard.existing_model_preflight import ExistingIntentSurface


def model_hit(**kwargs) -> ModelContextHit:
    defaults = {
        "model_id": "router-flow",
        "model_path": ".flowguard/router/model.py",
        "evidence_id": "router:v1",
        "evidence_tier": "abstract_green",
        "responsibilities": ("route scheduling",),
        "function_blocks": ("RouteTask",),
        "state_owned": ("pending_tasks",),
        "side_effects_owned": ("dispatch_task",),
        "public_entrypoints": ("router.dispatch",),
        "validation_evidence": ("router scenario replay",),
    }
    defaults.update(kwargs)
    return ModelContextHit(**defaults)


class ExistingModelPreflightTests(unittest.TestCase):
    def test_same_intent_surface_inventory_reuses_one_commitment_and_primary_path(self):
        surfaces = tuple(
            ExistingIntentSurface(
                surface_id,
                surface_kind=surface_kind,
                business_intent_id="intent:submit-order",
                behavior_commitment_id="commitment:submit-order",
                business_path_id="orders.submit",
                primary_path_id="path:submit-order",
                expected_terminal="accepted_or_visible_error",
                state_writes=("orders",),
                side_effects=("write_order",),
                owner_id="orders.submit.model",
                evidence_ids=(f"inventory:{surface_id}",),
            )
            for surface_id, surface_kind in (
                ("surface:ui-submit", "ui"),
                ("surface:api-submit", "api"),
            )
        )
        report = review_existing_model_preflight(
            ExistingModelPreflight(
                "submit-order-preflight",
                "Extend submit-order behavior without creating another authority",
                mode="full",
                model_search_performed=True,
                search_paths=(".flowguard/orders",),
                relevant_models=(model_hit(model_id="orders.submit.model"),),
                ownership_snapshot=ExistingOwnershipSnapshot(
                    function_block_owners=(("SubmitOrder", "orders.submit.model"),),
                ),
                reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
                downstream_routes=("model_similarity_consolidation", "primary_path_authority"),
                rationale="All same-intent surfaces reuse the registered commitment and path.",
                affected_business_intent_id="intent:submit-order",
                selected_commitment_id="commitment:submit-order",
                selected_primary_path_id="path:submit-order",
                expected_surface_ids=("surface:ui-submit", "surface:api-submit"),
                intent_surfaces=surfaces,
                surface_inventory_revision="submit-order-surfaces:v1",
                surface_inventory_evidence_ids=("inventory:submit-order-surfaces:v1",),
                require_complete_surface_inventory=True,
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(
            {"surface:ui-submit", "surface:api-submit"},
            set(report.covered_surface_ids),
        )
        self.assertEqual("path:submit-order", report.primary_path_id)

    def test_same_intent_surface_inventory_blocks_omitted_surface(self):
        report = review_existing_model_preflight(
            ExistingModelPreflight(
                "submit-order-preflight-omitted",
                "Review submit-order surfaces",
                mode="full",
                model_search_performed=True,
                search_paths=(".flowguard/orders",),
                relevant_models=(model_hit(model_id="orders.submit.model"),),
                ownership_snapshot=ExistingOwnershipSnapshot(
                    function_block_owners=(("SubmitOrder", "orders.submit.model"),),
                ),
                reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
                downstream_routes=("model_similarity_consolidation",),
                rationale="A complete same-intent inventory is required.",
                affected_business_intent_id="intent:submit-order",
                selected_commitment_id="commitment:submit-order",
                selected_primary_path_id="path:submit-order",
                expected_surface_ids=("surface:ui-submit", "surface:api-submit"),
                intent_surfaces=(
                    ExistingIntentSurface(
                        "surface:ui-submit",
                        surface_kind="ui",
                        business_intent_id="intent:submit-order",
                        behavior_commitment_id="commitment:submit-order",
                        business_path_id="orders.submit",
                        primary_path_id="path:submit-order",
                        expected_terminal="accepted_or_visible_error",
                        owner_id="orders.submit.model",
                        evidence_ids=("inventory:ui-submit",),
                    ),
                ),
                surface_inventory_revision="submit-order-surfaces:v1",
                surface_inventory_evidence_ids=("inventory:submit-order-surfaces:v1",),
                require_complete_surface_inventory=True,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn(
            "missing_expected_intent_surface",
            {finding.code for finding in report.findings},
        )

    def test_full_preflight_can_continue_when_existing_model_is_reused(self):
        preflight = ExistingModelPreflight(
            "router-preflight",
            "Extend router scheduling behavior",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard/router", "docs/model_mesh_protocol.md"),
            relevant_models=(model_hit(),),
            ownership_snapshot=ExistingOwnershipSnapshot(
                function_block_owners=(("RouteTask", "router-flow"),),
                state_owners=(("pending_tasks", "router-flow"),),
                side_effect_owners=(("dispatch_task", "router-flow"),),
                public_entrypoint_owners=(("router.dispatch", "router-flow"),),
            ),
            reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
            downstream_routes=("model_miss_review", "development_process_flow"),
            rationale="The existing router model owns task dispatch, so extend that boundary.",
        )

        report = review_existing_model_preflight(preflight)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("full_existing_model_preflight_can_continue", report.decision)
        self.assertEqual(0, report.blocker_count())

    def test_full_preflight_can_continue_with_field_lifecycle_ownership(self):
        preflight = ExistingModelPreflight(
            "router-fields",
            "Replace mode routing field",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard/router",),
            relevant_models=(model_hit(fields_owned=("field:mode",)),),
            ownership_snapshot=ExistingOwnershipSnapshot(
                function_block_owners=(("RouteTask", "router-flow"),),
                field_owners=(("field:mode", "router-flow"),),
            ),
            reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
            downstream_routes=("field_lifecycle_mesh", "model_test_alignment"),
            behavior_field_ids=("field:mode",),
            field_lifecycle_model_ids=("router-flow",),
            rationale="The router model owns the behavior field and the field lifecycle route will project it.",
        )

        report = review_existing_model_preflight(preflight)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("full_existing_model_preflight_can_continue", report.decision)

    def test_full_preflight_consumes_resolved_model_angle_review(self):
        preflight = ExistingModelPreflight(
            "router-model-angle",
            "Extend AI route behavior",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard/router",),
            relevant_models=(model_hit(),),
            ownership_snapshot=ExistingOwnershipSnapshot(
                function_block_owners=(("RouteTask", "router-flow"),),
                state_owners=(("pending_tasks", "router-flow"),),
            ),
            reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
            downstream_routes=("model_maturation_loop",),
            rationale="The router model owns the behavior, but the candidate angle was reviewed.",
            model_angle_review_required=True,
            model_angle_deliberations=(
                ModelAngleDeliberation(
                    "angle:ai-routing",
                    "AI route imagination",
                    current_model_sees="Existing preflight sees route ownership.",
                    current_model_misses="It may miss whether a new model angle is needed.",
                    failure_if_ignored="The agent can stay inside a too-narrow route.",
                    candidate_action=MODEL_ANGLE_ACTION_EXTEND_EXISTING,
                    existing_model_ids=("existing_model_preflight",),
                    proposed_model_boundary="Add open-ended candidate model-angle rows.",
                    resolved=True,
                ),
            ),
        )

        report = review_existing_model_preflight(preflight)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("full_existing_model_preflight_can_continue", report.decision)

    def test_full_preflight_blocks_unresolved_model_angle_review(self):
        preflight = ExistingModelPreflight(
            "router-model-angle-open",
            "Extend AI route behavior",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard/router",),
            relevant_models=(model_hit(),),
            ownership_snapshot=ExistingOwnershipSnapshot(
                function_block_owners=(("RouteTask", "router-flow"),),
                state_owners=(("pending_tasks", "router-flow"),),
            ),
            reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
            downstream_routes=("model_maturation_loop",),
            rationale="The router model owns the behavior, but a candidate angle remains open.",
            model_angle_review_required=True,
            model_angle_deliberations=(
                ModelAngleDeliberation(
                    "angle:ai-routing",
                    "AI route imagination",
                    current_model_sees="Existing preflight sees route ownership.",
                    current_model_misses="It may miss whether a new model angle is needed.",
                    failure_if_ignored="The agent can stay inside a too-narrow route.",
                    candidate_action=MODEL_ANGLE_ACTION_EXTEND_EXISTING,
                    existing_model_ids=("existing_model_preflight",),
                    proposed_model_boundary="Add open-ended candidate model-angle rows.",
                    resolved=False,
                ),
            ),
        )

        report = review_existing_model_preflight(preflight)

        self.assertFalse(report.ok)
        self.assertEqual("model_angle_review_blocked", report.decision)
        self.assertIn(
            "model_angle_unresolved_required_model_angle",
            {finding.code for finding in report.findings},
        )

    def test_behavior_field_requires_field_lifecycle_ownership(self):
        preflight = ExistingModelPreflight(
            "router-fields",
            "Replace mode routing field",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard/router",),
            relevant_models=(model_hit(fields_owned=()),),
            ownership_snapshot=ExistingOwnershipSnapshot(
                function_block_owners=(("RouteTask", "router-flow"),),
            ),
            reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
            downstream_routes=("model_test_alignment",),
            behavior_field_ids=("field:mode",),
            rationale="The router model owns the behavior, but no field owner was recorded.",
        )

        report = review_existing_model_preflight(preflight)

        self.assertFalse(report.ok)
        self.assertEqual("field_lifecycle_ownership_required", report.decision)
        self.assertIn("missing_field_lifecycle_ownership", {finding.code for finding in report.findings})
        self.assertIn("missing_field_lifecycle_route", {finding.code for finding in report.findings})

    def test_field_lifecycle_gap_blocks_preflight(self):
        preflight = ExistingModelPreflight(
            "router-fields",
            "Replace mode routing field",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard/router",),
            relevant_models=(model_hit(fields_owned=("field:mode",)),),
            reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
            downstream_routes=("field_lifecycle_mesh", "model_test_alignment"),
            behavior_field_ids=("field:mode",),
            field_lifecycle_model_ids=("router-flow",),
            field_lifecycle_gap_ids=("field:old_mode:disposition",),
            rationale="The router model owns the behavior field, but old field disposition is still open.",
        )

        report = review_existing_model_preflight(preflight)

        self.assertFalse(report.ok)
        self.assertEqual("field_lifecycle_gap_blocked", report.decision)
        self.assertIn("field_lifecycle_gap_unresolved", {finding.code for finding in report.findings})

    def test_light_discussion_grounding_can_continue(self):
        preflight = ExistingModelPreflight(
            "router-discussion",
            "Discuss whether routing behavior should change",
            mode="light",
            model_search_performed=True,
            search_paths=(".flowguard/router",),
            relevant_models=(model_hit(),),
            reuse_decision=REUSE_DECISION_REUSE_EXISTING,
            downstream_routes=("core_modeling",),
            rationale="Discussion is grounded in the router model.",
        )

        report = review_existing_model_preflight(preflight)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("light_model_grounding_can_continue", report.decision)

    def test_missing_model_search_blocks(self):
        preflight = ExistingModelPreflight(
            "router-preflight",
            "Implement scheduler",
            mode="full",
            relevant_models=(model_hit(),),
            reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
            downstream_routes=("development_process_flow",),
            rationale="Extend router model.",
        )

        report = review_existing_model_preflight(preflight)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("missing_model_search", codes)

    def test_full_preflight_requires_ownership_evidence(self):
        preflight = ExistingModelPreflight(
            "thin-preflight",
            "Implement scheduler",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard/router",),
            relevant_models=(model_hit(function_blocks=(), state_owned=(), side_effects_owned=(), public_entrypoints=(), responsibilities=()),),
            reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
            downstream_routes=("development_process_flow",),
            rationale="Extend router model.",
        )

        report = review_existing_model_preflight(preflight)

        self.assertFalse(report.ok)
        self.assertIn("missing_ownership_evidence", {finding.code for finding in report.findings})

    def test_parent_model_requires_layered_proof_status_in_full_preflight(self):
        preflight = ExistingModelPreflight(
            "missing-layered-proof-status",
            "Extend parent model coverage",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard/router",),
            relevant_models=(model_hit(child_model_ids=("validate-submit",)),),
            ownership_snapshot=ExistingOwnershipSnapshot(
                function_block_owners=(("dispatch", "router-flow"),),
                state_owners=(("queue", "router-flow"),),
            ),
            reuse_decision=REUSE_DECISION_ADD_CHILD_MODEL,
            downstream_routes=("model_mesh_maintenance",),
            rationale="The router parent has child model evidence that must be reattached.",
            proposed_new_boundaries=("validate-submit",),
        )

        report = review_existing_model_preflight(preflight)

        self.assertFalse(report.ok)
        self.assertEqual("layered_proof_status_required", report.decision)
        self.assertIn("layered_proof_status_unknown", {finding.code for finding in report.findings})

    def test_parent_model_with_layered_status_can_continue(self):
        preflight = ExistingModelPreflight(
            "layered-proof-status",
            "Extend parent model coverage",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard/router",),
            relevant_models=(
                model_hit(
                    child_model_ids=("validate-submit",),
                    layered_proof_evidence_id="router-layered:v1",
                    parent_coverage_status="passed",
                    child_disjointness_status="passed",
                    child_reattachment_status="passed",
                    leaf_boundary_matrix_status="passed",
                ),
            ),
            ownership_snapshot=ExistingOwnershipSnapshot(
                function_block_owners=(("dispatch", "router-flow"),),
                state_owners=(("queue", "router-flow"),),
            ),
            reuse_decision=REUSE_DECISION_ADD_CHILD_MODEL,
            downstream_routes=("model_mesh_maintenance",),
            rationale="The router parent has current layered proof status.",
            proposed_new_boundaries=("validate-submit",),
        )

        report = review_existing_model_preflight(preflight)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("full_existing_model_preflight_can_continue", report.decision)

    def test_duplicate_boundary_risk_must_be_resolved(self):
        preflight = ExistingModelPreflight(
            "duplicate-preflight",
            "Create another scheduler",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard/router",),
            relevant_models=(model_hit(),),
            ownership_snapshot=ExistingOwnershipSnapshot(
                state_owners=(("pending_tasks", "router-flow"),),
            ),
            reuse_decision=REUSE_DECISION_ADD_CHILD_MODEL,
            downstream_routes=("model_mesh_maintenance",),
            rationale="A child model may be needed.",
            proposed_new_boundaries=("parallel-scheduler",),
            duplicate_risks=(
                DuplicateBoundaryRisk(
                    "state",
                    "pending_tasks",
                    "router-flow",
                    proposed_owner_id="parallel-scheduler",
                ),
            ),
        )

        report = review_existing_model_preflight(preflight)

        self.assertFalse(report.ok)
        self.assertEqual("duplicate_boundary_risk_blocked", report.decision)
        self.assertIn("duplicate_boundary_risk_unresolved", {finding.code for finding in report.findings})

    def test_no_model_found_is_explicit(self):
        preflight = ExistingModelPreflight(
            "no-model",
            "Discuss a greenfield adapter",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard", "docs"),
            reuse_decision=REUSE_DECISION_NO_MODEL_FOUND,
            downstream_routes=("core_modeling",),
            no_model_found_reason="No existing model owns this adapter boundary.",
            rationale="Create a small model before code.",
        )

        report = review_existing_model_preflight(preflight)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("no_model_found_can_continue", report.decision)

    def test_skip_with_reason_is_allowed_for_trivial_work(self):
        preflight = ExistingModelPreflight(
            "skip-typo",
            "Fix typo",
            mode="light",
            reuse_decision=REUSE_DECISION_SKIP,
            skip_reason="Formatting-only edit with no behavior or model ownership change.",
            rationale="No model grounding needed for typo-only work.",
        )

        report = review_existing_model_preflight(preflight)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("preflight_skipped_with_reason", report.decision)

    def test_project_inventory_helper_finds_flowguard_model_context(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            model_dir = root / ".flowguard" / "router"
            model_dir.mkdir(parents=True)
            (model_dir / "model.py").write_text(
                '"""FlowGuard Risk Purpose Header\n'
                "Purpose: Review router task dispatch ownership.\n"
                '"""\n'
                "from flowguard import Workflow\n"
                "class RouteTask:\n"
                "    name = 'RouteTask'\n",
                encoding="utf-8",
            )

            preflight = existing_model_preflight_from_project(
                root,
                "Extend router dispatch",
                downstream_routes=("development_process_flow",),
            )
            report = review_existing_model_preflight(preflight)

            self.assertTrue(report.ok, report.format_text())
            self.assertEqual(REUSE_DECISION_REUSE_EXISTING, preflight.reuse_decision)
            self.assertEqual(("RouteTask",), preflight.relevant_models[0].function_blocks)
            self.assertIn(".flowguard", preflight.search_paths)

    def test_project_inventory_helper_records_no_model_found(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".flowguard").mkdir()

            preflight = existing_model_preflight_from_project(
                root,
                "Discuss a new adapter",
                downstream_routes=("core_modeling",),
            )
            report = review_existing_model_preflight(preflight)

            self.assertTrue(report.ok, report.format_text())
            self.assertEqual(REUSE_DECISION_NO_MODEL_FOUND, preflight.reuse_decision)
            self.assertIn("No relevant FlowGuard model files", preflight.no_model_found_reason)


if __name__ == "__main__":
    unittest.main()
