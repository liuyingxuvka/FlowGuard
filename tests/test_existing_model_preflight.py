import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard import (
    DuplicateBoundaryRisk,
    ExistingModelPreflight,
    ExistingOwnershipSnapshot,
    ModelContextHit,
    REUSE_DECISION_ADD_CHILD_MODEL,
    REUSE_DECISION_EXTEND_EXISTING,
    REUSE_DECISION_NO_MODEL_FOUND,
    REUSE_DECISION_REUSE_EXISTING,
    REUSE_DECISION_SKIP,
    existing_model_preflight_from_project,
    review_existing_model_preflight,
)


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
