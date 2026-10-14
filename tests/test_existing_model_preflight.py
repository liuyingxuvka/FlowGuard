import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from flowguard import (
    BehaviorCommitmentHit,
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
    project_existing_model_preflight_blueprint_handoff,
    review_existing_model_preflight,
)
from flowguard.existing_model_preflight import (
    ExistingIntentSurface,
)


def _write_lookup_ledger(root):
    """Let the invocation-shared reader load actual canonical ledger bytes."""
    from flowguard.behavior_commitment import (
        BehaviorCommitmentLedger, write_behavior_commitment_ledger,
    )
    write_behavior_commitment_ledger(
        root / ".flowguard/behavior/inventory/ledger.json",
        BehaviorCommitmentLedger("ledger:preflight-navigation-fixture"),
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
    def _green_preflight_report(self):
        hit = model_hit()
        preflight = ExistingModelPreflight(
            "preflight:blueprint",
            "qualify the whole-software blueprint",
            model_search_performed=True,
            search_paths=(".flowguard",),
            relevant_models=(hit,),
            ownership_snapshot=ExistingOwnershipSnapshot(
                function_block_owners=(("RouteTask", hit.model_id),),
                public_entrypoint_owners=(("router.dispatch", hit.model_id),),
            ),
            reuse_decision=REUSE_DECISION_REUSE_EXISTING,
            downstream_routes=("model_test_alignment",),
            rationale="reuse current owner",
        )
        return review_existing_model_preflight(preflight)

    def test_ordinary_preflight_does_not_require_or_load_whole_software_inventory(self):
        report = self._green_preflight_report()
        handoff = project_existing_model_preflight_blueprint_handoff(
            report,
            blueprint_requested=False,
        )
        self.assertTrue(handoff.ok)
        self.assertFalse(handoff.blueprint_requested)
        self.assertEqual("", handoff.implementation_inventory_fingerprint)
        self.assertEqual(("model_first_function_flow",), handoff.downstream_owner_routes)

    def test_blueprint_preflight_binds_independent_inventory_identity(self):
        report = self._green_preflight_report()
        inventory = SimpleNamespace(
            ok=True,
            inventory_fingerprint="sha256:inventory",
            required_surface_ids=("surface:router.dispatch",),
            findings=(),
        )
        handoff = project_existing_model_preflight_blueprint_handoff(
            report,
            blueprint_requested=True,
            implementation_inventory_report=inventory,
        )
        self.assertTrue(handoff.ok)
        self.assertEqual("sha256:inventory", handoff.implementation_inventory_fingerprint)
        self.assertEqual(("surface:router.dispatch",), handoff.implementation_surface_ids)
        self.assertIn("model_test_alignment", handoff.downstream_owner_routes)

    def test_blueprint_preflight_cannot_treat_missing_inventory_as_complete(self):
        handoff = project_existing_model_preflight_blueprint_handoff(
            self._green_preflight_report(),
            blueprint_requested=True,
        )
        self.assertFalse(handoff.ok)
        self.assertIn("implementation_inventory:missing", handoff.unresolved_surface_ids)

    def owner_projection_report(self, owner_id: str, *models: ModelContextHit):
        return review_existing_model_preflight(
            ExistingModelPreflight(
                "owner-identity",
                "Resolve the current commitment owner",
                mode="full",
                model_search_performed=True,
                search_paths=(".flowguard",),
                behavior_lookup_required=True,
                behavior_lookup_status="performed",
                primary_behavior_plane="agent_operation",
                primary_commitment_hits=(
                    BehaviorCommitmentHit(
                        "commitment:route",
                        "agent_operation",
                        owner_id,
                        100,
                    ),
                ),
                ledger_fingerprint="sha256:ledger",
                relevant_models=models,
                ownership_snapshot=ExistingOwnershipSnapshot(
                    function_block_owners=(("RouteTask", models[0].model_id),),
                ),
                reuse_decision=REUSE_DECISION_REUSE_EXISTING,
                downstream_routes=("development_process_flow",),
                rationale="The exact current owner should be reused.",
            )
        )

    def test_commitment_owner_path_matches_observed_logical_hit(self):
        report = self.owner_projection_report(
            ".flowguard/minimum_valuable_model_entry/model.py",
            model_hit(
                model_id="minimum_valuable_model_entry",
                model_path=".flowguard/minimum_valuable_model_entry/model.py",
                evidence_id="model-authority:sha256:minimum-entry",
            ),
        )

        self.assertNotIn(
            "behavior_lookup_owner_model_not_projected",
            {finding.code for finding in report.findings},
        )

    def test_commitment_owner_logical_id_matches(self):
        for owner_id in ("router-flow", "model:router-flow"):
            with self.subTest(owner_id=owner_id):
                report = self.owner_projection_report(owner_id, model_hit())
                self.assertNotIn(
                    "behavior_lookup_owner_model_not_projected",
                    {finding.code for finding in report.findings},
                )

    def test_commitment_owner_fingerprint_matches(self):
        report = self.owner_projection_report(
            "sha256:router-current",
            model_hit(evidence_id="model-authority:sha256:router-current"),
        )
        self.assertNotIn(
            "behavior_lookup_owner_model_not_projected",
            {finding.code for finding in report.findings},
        )

    def test_absolute_and_repository_relative_owner_paths_match(self):
        report = self.owner_projection_report(
            "C:/workspace/project/.flowguard/router/model.py",
            model_hit(model_path=".flowguard/router/model.py"),
        )
        self.assertNotIn(
            "behavior_lookup_owner_model_not_projected",
            {finding.code for finding in report.findings},
        )

    def test_similar_basename_and_wrong_fingerprint_do_not_match(self):
        for owner_id in (
            ".flowguard/other/router/model.py",
            "sha256:not-router-current",
        ):
            with self.subTest(owner_id=owner_id):
                report = self.owner_projection_report(
                    owner_id,
                    model_hit(evidence_id="model-authority:sha256:router-current"),
                )
                self.assertIn(
                    "behavior_lookup_owner_model_not_projected",
                    {finding.code for finding in report.findings},
                )

    def test_ambiguous_owner_identity_blocks(self):
        report = self.owner_projection_report(
            ".flowguard/router/model.py",
            model_hit(model_id="router-flow-a"),
            model_hit(model_id="router-flow-b"),
        )
        self.assertIn(
            "behavior_lookup_owner_model_ambiguous",
            {finding.code for finding in report.findings},
        )

    def test_stale_or_mutable_work_context_is_scoped_gap(self):
        context = {
            "adapter_id": "openspec",
            "context_id": "openspec:change-one",
            "native_work_id": "change-one",
            "native_owner_id": "openspec",
            "subject_lane": "development_process",
            "provider_owns_product_behavior": False,
            "read_only": False,
            "current": False,
            "context_fingerprint": "sha256:context",
            "artifact_ids": ["proposal", "design", "spec", "tasks", "status"],
        }
        preflight = ExistingModelPreflight(
            "work-context",
            "Review a provider work package",
            behavior_lookup_required=True,
            behavior_lookup_status="performed",
            primary_behavior_plane="development_process",
            ledger_fingerprint="sha256:ledger",
            work_contexts=(context,),
        )
        report = review_existing_model_preflight(preflight)
        self.assertIn(
            "work_context_not_current",
            {finding.code for finding in report.findings},
        )
        self.assertIn(
            "work_context_write_authority_forbidden",
            {finding.code for finding in report.findings},
        )
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
                downstream_routes=("primary_path_authority",),
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
                downstream_routes=("primary_path_authority",),
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

    def test_retired_review_and_fallback_inputs_are_absent(self):
        preflight = ExistingModelPreflight(
            "router-current-relations",
            "Extend current router behavior",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard/router",),
            relevant_models=(model_hit(),),
            ownership_snapshot=ExistingOwnershipSnapshot(
                function_block_owners=(("RouteTask", "router-flow"),),
                state_owners=(("pending_tasks", "router-flow"),),
            ),
            reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
            downstream_routes=("development_process_flow",),
            rationale="The exact current router owner carries the change.",
            canonical_relation_handoff={
                "relations": ({
                    "relation_id": "relation:router-to-dispatch",
                    "relation_type": "depends_on",
                    "source_endpoint_kind": "model",
                    "source_endpoint_id": "router-flow",
                    "target_endpoint_kind": "code_boundary",
                    "target_endpoint_id": "dispatch",
                    "source_ids": ("semantic-mesh:router-current",),
                },),
                "evidence_current": True,
            },
        )

        report = review_existing_model_preflight(preflight)

        self.assertTrue(report.ok, report.format_text())
        field_names = set(ExistingModelPreflight.__dataclass_fields__)
        serialized = preflight.to_dict()
        for retired_alias in (
            "selected_currentness",
            "execution_status",
            "as_of_map",
        ):
            self.assertNotIn(retired_alias, serialized)
        self.assertEqual(
            preflight.selected_source_currentness,
            serialized["selected_source_currentness"],
        )
        self.assertEqual(
            preflight.execution_evidence_status,
            serialized["execution_evidence_status"],
        )
        self.assertEqual(dict(preflight.as_of), serialized["as_of"])
        for retired_field in (
            "model_angle_review_required",
            "model_angle_deliberations",
            "model_angle_gap_ids",
            "similarity_review_required",
            "behavior_lookup_reason",
        ):
            self.assertNotIn(retired_field, field_names)
            self.assertNotIn(retired_field, serialized)
        self.assertEqual(
            ["relation:router-to-dispatch"],
            [
                relation["relation_id"]
                for relation in serialized["canonical_relation_handoff"]["relations"]
            ],
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

    def test_project_inventory_without_authority_is_candidate_only(self):
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

            self.assertFalse(report.ok, report.format_text())
            self.assertEqual(REUSE_DECISION_NO_MODEL_FOUND, preflight.reuse_decision)
            self.assertEqual("adoption_candidate", preflight.grounding_state)
            self.assertFalse(preflight.existing_modeled_system)
            self.assertFalse(preflight.authority_required)
            self.assertEqual(("RouteTask",), preflight.relevant_models[0].function_blocks)
            self.assertFalse(preflight.relevant_models[0].evidence_current)
            self.assertEqual("adoption_candidate", preflight.relevant_models[0].evidence_tier)
            self.assertIsNone(preflight.ownership_snapshot)
            self.assertEqual("not_adopted", preflight.authority_status)
            self.assertEqual("adoption_candidate", report.decision)
            self.assertIn(
                "adoption_candidate_not_current",
                {finding.code for finding in report.findings},
            )
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

            self.assertFalse(report.ok, report.format_text())
            self.assertEqual(REUSE_DECISION_NO_MODEL_FOUND, preflight.reuse_decision)
            self.assertEqual("not_adopted", preflight.authority_status)
            self.assertEqual("adoption_candidate", preflight.grounding_state)
            self.assertEqual("adoption_candidate", report.decision)
            self.assertIn("No validated current model authority", preflight.no_model_found_reason)


def test_existing_model_new_boundary_without_rationale():
    from dataclasses import replace
    from flowguard import REUSE_DECISION_NEW_BOUNDARY, ExistingModelPreflight, review_existing_model_preflight

    base = ExistingModelPreflight(
        "pre", "add scheduler", mode="light", model_search_performed=True,
        search_paths=(".flowguard/map.json",), reuse_decision=REUSE_DECISION_NEW_BOUNDARY,
        proposed_new_boundaries=("scheduler",), downstream_routes=("development_process_flow",))
    assert "new_boundary_without_rationale" in {f.code for f in review_existing_model_preflight(base).findings}
    explained = replace(base, rationale="the router cannot own time-based retries; scheduler owns only timers")
    assert "new_boundary_without_rationale" not in {f.code for f in review_existing_model_preflight(explained).findings}


if __name__ == "__main__":
    unittest.main()
