import unittest

from flowguard import (
    CANDIDATE_DISPOSITION_COMPLETED,
    CANDIDATE_COLLAPSE_ADAPTER,
    CANDIDATE_KEEP_PUBLIC_FACADE,
    CANDIDATE_MERGE_HANDLERS,
    CANDIDATE_REMOVE_STATE_FIELD,
    COMPATIBILITY_ACTION_ARCHIVE,
    COMPATIBILITY_ACTION_COLLECT_EVIDENCE,
    COMPATIBILITY_ACTION_KEEP,
    COMPATIBILITY_ACTION_PRUNE,
    COMPATIBILITY_ACTION_REJECT,
    COMPATIBILITY_SURFACE_ARCHIVE_ONLY,
    COMPATIBILITY_SURFACE_BOUNDARY_ADAPTER,
    COMPATIBILITY_SURFACE_CURRENT_CONTRACT,
    COMPATIBILITY_SURFACE_EVIDENCE_NEEDED,
    COMPATIBILITY_SURFACE_NEGATIVE_LEGACY_TEST,
    COMPATIBILITY_SURFACE_PRUNE_CANDIDATE,
    PROOF_NEEDS_CONFORMANCE_REPLAY,
    PROOF_PROPERTY_ONLY_SAFE,
    PROOF_RISKY_KEEP,
    PROOF_SAFE_BY_EQUIVALENCE,
    PROOF_SAFE_BY_PUBLIC_FACADE,
    ROUTE_CODE_STRUCTURE_RECOMMENDATION,
    ROUTE_DEVELOPMENT_PROCESS_FLOW,
    ROUTE_MANUAL_REVIEW,
    ROUTE_STRUCTURE_MESH,
    TARGET_ACTION_COLLAPSE,
    TARGET_ACTION_KEEP_FACADE,
    TARGET_ACTION_MANUAL_REVIEW,
    TARGET_ACTION_MERGE,
    TARGET_ACTION_REMOVE,
    ArchitectureReductionCandidate,
    ArchitectureReductionPlan,
    ArchitectureReductionTrigger,
    CodeStructureRecommendation,
    CompatibilitySurfaceClassification,
    ObservableArchitectureContract,
    TargetModuleRecommendation,
    review_architecture_reduction,
)


def contract(**kwargs) -> ObservableArchitectureContract:
    defaults = {
        "source_model_id": "router-flow",
        "source_code_boundary_id": "router-package",
        "public_entrypoints": ("router.cli",),
        "observable_outputs": ("RouteResult",),
        "observable_state": ("route_status",),
        "observable_side_effects": ("write_event",),
        "validation_boundaries": ("focused parity tests",),
        "rationale": "public CLI behavior, state, and side effects define the contraction boundary",
    }
    defaults.update(kwargs)
    return ObservableArchitectureContract(**defaults)


def trigger(**kwargs) -> ArchitectureReductionTrigger:
    defaults = {
        "route_id": ROUTE_DEVELOPMENT_PROCESS_FLOW,
        "trigger_reason": "staged implementation added repeated adapters around the same behavior",
        "complexity_signal": "repeated_adapter",
        "recommended_timing": "before done claim",
    }
    defaults.update(kwargs)
    return ArchitectureReductionTrigger(**defaults)


def candidate(**kwargs) -> ArchitectureReductionCandidate:
    defaults = {
        "candidate_id": "collapse-normalizer-adapter",
        "candidate_type": CANDIDATE_COLLAPSE_ADAPTER,
        "code_node_id": "router.normalizer_adapter",
        "source_model_element": "NormalizeInput",
        "target_action": TARGET_ACTION_COLLAPSE,
        "proof_status": PROOF_SAFE_BY_EQUIVALENCE,
        "required_next_route": ROUTE_CODE_STRUCTURE_RECOMMENDATION,
        "rationale": "adapter forwards normalized input without owning state or side effects",
    }
    defaults.update(kwargs)
    return ArchitectureReductionCandidate(**defaults)


def surface(**kwargs) -> CompatibilitySurfaceClassification:
    defaults = {
        "surface_id": "legacy-normalizer",
        "classification": COMPATIBILITY_SURFACE_PRUNE_CANDIDATE,
        "recommended_action": COMPATIBILITY_ACTION_PRUNE,
        "rationale": "legacy normalizer no longer owns current runtime behavior",
        "code_node_ids": ("router.normalizer_adapter",),
        "candidate_ids": ("collapse-normalizer-adapter",),
        "evidence_refs": ("tests/test_architecture_reduction.py",),
    }
    defaults.update(kwargs)
    return CompatibilitySurfaceClassification(**defaults)


def target_structure() -> CodeStructureRecommendation:
    return CodeStructureRecommendation(
        "router-reduced-structure",
        source_model_id="router-flow",
        parent_module_id="router",
        target_modules=(
            TargetModuleRecommendation(
                "router_core",
                owns_function_blocks=("NormalizeInput", "RouteCommand"),
                owns_state=("route_status",),
                owns_side_effects=("write_event",),
                validation_boundaries=("focused parity tests",),
                rationale="merged core owns the reduced model behavior",
            ),
        ),
        source_model_path=".flowguard/router/model.py",
        function_block_map=(("NormalizeInput", "router_core"), ("RouteCommand", "router_core")),
        state_owner_map=(("route_status", "router_core"),),
        side_effect_owner_map=(("write_event", "router_core"),),
        public_entrypoint_map=(("router.cli", "router_core"),),
        facade_module_id="router_core",
        validation_boundaries=("focused parity tests",),
        rationale="reduced model collapses pass-through adapter into router core",
    )


class ArchitectureReductionTests(unittest.TestCase):
    def test_complete_review_reports_ready_candidate_and_target_action(self):
        plan = ArchitectureReductionPlan(
            "router-reduction",
            observable_contract=contract(),
            candidates=(candidate(),),
            companion_route_triggers=(trigger(),),
            target_structure=target_structure(),
            rationale="complexity-growth review found one pass-through adapter",
        )

        report = review_architecture_reduction(plan)

        self.assertTrue(report.ok)
        self.assertEqual("architecture_reduction_ready", report.decision)
        self.assertEqual(("collapse-normalizer-adapter",), report.ready_candidate_ids)
        self.assertEqual(1, len(report.target_actions))
        self.assertEqual(TARGET_ACTION_COLLAPSE, report.target_actions[0].action)
        self.assertIn(ROUTE_CODE_STRUCTURE_RECOMMENDATION, report.required_next_routes)

    def test_completed_candidate_leaves_active_ready_queue(self):
        plan = ArchitectureReductionPlan(
            "router-reduction",
            observable_contract=contract(),
            candidates=(
                candidate(
                    lifecycle_disposition=CANDIDATE_DISPOSITION_COMPLETED,
                    completion_evidence_refs=("tests/test_architecture_reduction.py",),
                ),
            ),
            companion_route_triggers=(trigger(),),
            target_structure=target_structure(),
            rationale="completed contraction should remain visible without being re-queued",
        )

        report = review_architecture_reduction(plan)

        self.assertTrue(report.ok)
        self.assertEqual("completed_reduction_candidates", report.decision)
        self.assertEqual((), report.ready_candidate_ids)
        self.assertEqual(("collapse-normalizer-adapter",), report.completed_candidate_ids)
        self.assertEqual(0, len(report.target_actions))
        self.assertIn("completed_candidates: collapse-normalizer-adapter", report.format_text())

    def test_completed_candidate_requires_completion_evidence(self):
        plan = ArchitectureReductionPlan(
            "router-reduction",
            observable_contract=contract(),
            candidates=(candidate(lifecycle_disposition=CANDIDATE_DISPOSITION_COMPLETED),),
            companion_route_triggers=(trigger(),),
            rationale="closed candidates need proof before leaving active work",
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertEqual("completed_candidate_blocked", report.decision)
        self.assertIn("completed_candidate_missing_evidence", [finding.code for finding in report.findings])

    def test_missing_observable_contract_blocks(self):
        plan = ArchitectureReductionPlan(
            "router-reduction",
            observable_contract=contract(source_model_id="", public_entrypoints=(), validation_boundaries=()),
            candidates=(candidate(),),
            companion_route_triggers=(trigger(),),
            rationale="missing contract case",
        )

        report = review_architecture_reduction(plan)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertEqual("missing_observable_contract", report.decision)
        self.assertIn("missing_observable_contract", codes)

    def test_public_entrypoint_candidate_requires_structure_mesh(self):
        plan = ArchitectureReductionPlan(
            "router-public-reduction",
            observable_contract=contract(),
            candidates=(
                candidate(
                    candidate_id="merge-cli-handlers",
                    candidate_type=CANDIDATE_MERGE_HANDLERS,
                    code_node_id="router.cli_handlers",
                    source_model_element="RouteCommand",
                    target_action=TARGET_ACTION_MERGE,
                    affected_public_entrypoints=("router.cli",),
                    required_next_route=ROUTE_CODE_STRUCTURE_RECOMMENDATION,
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="public entrypoint candidate must route through StructureMesh",
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertEqual("structure_mesh_required", report.decision)
        self.assertIn("public_entrypoint_requires_structure_mesh", [finding.code for finding in report.findings])

    def test_keep_public_facade_candidate_is_ready_with_structure_mesh_route(self):
        plan = ArchitectureReductionPlan(
            "router-facade-reduction",
            observable_contract=contract(),
            candidates=(
                candidate(
                    candidate_id="keep-cli-facade",
                    candidate_type=CANDIDATE_KEEP_PUBLIC_FACADE,
                    code_node_id="router.__main__",
                    source_model_element="PublicCliEntrypoint",
                    target_action=TARGET_ACTION_KEEP_FACADE,
                    proof_status=PROOF_SAFE_BY_PUBLIC_FACADE,
                    required_next_route=ROUTE_STRUCTURE_MESH,
                    affected_public_entrypoints=("router.cli",),
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="public CLI facade must stay while internals contract",
        )

        report = review_architecture_reduction(plan)

        self.assertTrue(report.ok)
        self.assertEqual("architecture_reduction_ready", report.decision)
        self.assertEqual(("keep-cli-facade",), report.ready_candidate_ids)

    def test_observable_state_removal_blocks(self):
        plan = ArchitectureReductionPlan(
            "router-state-reduction",
            observable_contract=contract(observable_state=("route_status",)),
            candidates=(
                candidate(
                    candidate_id="remove-status",
                    candidate_type=CANDIDATE_REMOVE_STATE_FIELD,
                    code_node_id="RouterState.route_status",
                    source_model_element="route_status",
                    target_action=TARGET_ACTION_REMOVE,
                    required_next_route=ROUTE_STRUCTURE_MESH,
                    affected_state=("route_status",),
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="observable state cannot be removed",
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertEqual("observable_contract_blocked", report.decision)
        self.assertIn("removes_observable_state", [finding.code for finding in report.findings])

    def test_conformance_required_candidate_blocks_ready_claim(self):
        plan = ArchitectureReductionPlan(
            "router-replay-reduction",
            observable_contract=contract(),
            candidates=(candidate(proof_status=PROOF_NEEDS_CONFORMANCE_REPLAY),),
            companion_route_triggers=(trigger(),),
            rationale="candidate needs replay evidence",
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertEqual("conformance_required", report.decision)

    def test_property_only_candidate_stays_distinct_from_full_behavior_equivalence(self):
        plan = ArchitectureReductionPlan(
            "router-property-reduction",
            observable_contract=contract(),
            candidates=(
                candidate(
                    proof_status=PROOF_PROPERTY_ONLY_SAFE,
                    required_next_route=ROUTE_MANUAL_REVIEW,
                    target_action=TARGET_ACTION_MANUAL_REVIEW,
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="candidate only preserves selected invariants",
        )

        report = review_architecture_reduction(plan)

        self.assertTrue(report.ok)
        self.assertEqual("property_only_review", report.decision)
        self.assertEqual((), report.ready_candidate_ids)
        self.assertIn("property_only_reduction", [finding.code for finding in report.findings])

    def test_risky_candidate_is_visible_but_not_ready(self):
        plan = ArchitectureReductionPlan(
            "router-risky-reduction",
            observable_contract=contract(),
            candidates=(
                candidate(
                    proof_status=PROOF_RISKY_KEEP,
                    required_next_route=ROUTE_MANUAL_REVIEW,
                    target_action=TARGET_ACTION_MANUAL_REVIEW,
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="candidate looks duplicated but semantic intent differs",
        )

        report = review_architecture_reduction(plan)

        self.assertTrue(report.ok)
        self.assertEqual("no_ready_reduction_candidates", report.decision)
        self.assertIn("risky_candidate_kept", [finding.code for finding in report.findings])

    def test_blocked_target_structure_is_reported(self):
        broken_structure = CodeStructureRecommendation(
            "broken",
            source_model_id="router-flow",
            parent_module_id="router",
            rationale="missing target modules and maps",
        )
        plan = ArchitectureReductionPlan(
            "router-broken-target",
            observable_contract=contract(),
            candidates=(candidate(),),
            companion_route_triggers=(trigger(),),
            target_structure=broken_structure,
            rationale="target structure must still pass code structure review",
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertEqual("target_structure_blocked", report.decision)
        self.assertIn("target_structure_blocked", [finding.code for finding in report.findings])

    def test_compatibility_surface_is_reported_with_ready_candidate(self):
        plan = ArchitectureReductionPlan(
            "router-compat-reduction",
            observable_contract=contract(),
            candidates=(candidate(),),
            compatibility_surfaces=(
                surface(
                    field_ids=("field:old_mode",),
                    replacement_field_ids=("field:mode",),
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="legacy surface is classified before contraction",
        )

        report = review_architecture_reduction(plan)

        self.assertTrue(report.ok)
        self.assertEqual("architecture_reduction_ready", report.decision)
        self.assertEqual(("collapse-normalizer-adapter",), report.ready_candidate_ids)
        self.assertEqual(("legacy-normalizer",), tuple(item.surface_id for item in report.compatibility_surfaces))
        self.assertIn("compatibility_surfaces:", report.format_text())
        self.assertEqual(
            COMPATIBILITY_SURFACE_PRUNE_CANDIDATE,
            report.to_dict()["compatibility_surfaces"][0]["classification"],
        )
        self.assertEqual(("field:old_mode",), report.compatibility_surfaces[0].field_ids)

    def test_old_field_surface_requires_disposition_evidence(self):
        plan = ArchitectureReductionPlan(
            "router-field-compat-reduction",
            observable_contract=contract(),
            candidates=(candidate(),),
            compatibility_surfaces=(
                surface(
                    surface_id="old-mode-field",
                    field_ids=("field:old_mode",),
                    replacement_field_ids=("field:mode",),
                    evidence_refs=(),
                    owner_model_elements=(),
                    rationale="old mode field must not be pruned without disposition evidence",
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="field compatibility surfaces need explicit closure",
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertEqual("compatibility_surface_blocked", report.decision)
        self.assertIn("compatibility_field_surface_missing_evidence", [finding.code for finding in report.findings])

    def test_current_contract_surface_blocks_remove_or_collapse(self):
        plan = ArchitectureReductionPlan(
            "router-current-contract-reduction",
            observable_contract=contract(),
            candidates=(candidate(),),
            compatibility_surfaces=(
                surface(
                    classification=COMPATIBILITY_SURFACE_CURRENT_CONTRACT,
                    recommended_action=COMPATIBILITY_ACTION_KEEP,
                    rationale="normalizer is still the current input contract",
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="current contract cannot be collapsed as obsolete compatibility",
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertEqual("compatibility_surface_blocked", report.decision)
        self.assertEqual((), report.ready_candidate_ids)
        self.assertIn(
            "compatibility_surface_current_contract_blocks_contraction",
            [finding.code for finding in report.findings],
        )

    def test_public_boundary_adapter_surface_requires_structure_mesh(self):
        plan = ArchitectureReductionPlan(
            "router-boundary-adapter-reduction",
            observable_contract=contract(),
            candidates=(candidate(),),
            compatibility_surfaces=(
                surface(
                    classification=COMPATIBILITY_SURFACE_BOUNDARY_ADAPTER,
                    recommended_action=COMPATIBILITY_ACTION_KEEP,
                    public_entrypoints=("router.cli",),
                    rationale="CLI remains a boundary adapter for old callers",
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="public boundary adapter needs parity gate",
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertEqual("structure_mesh_required", report.decision)
        self.assertEqual((), report.ready_candidate_ids)
        self.assertIn(
            "compatibility_surface_public_entrypoint_requires_structure_mesh",
            [finding.code for finding in report.findings],
        )

    def test_negative_legacy_test_removal_requires_replacement_evidence(self):
        plan = ArchitectureReductionPlan(
            "router-negative-test-reduction",
            observable_contract=contract(),
            candidates=(
                candidate(
                    candidate_id="remove-legacy-test",
                    candidate_type=CANDIDATE_REMOVE_STATE_FIELD,
                    code_node_id="tests.legacy_input_rejection",
                    source_model_element="RejectLegacyInput",
                    target_action=TARGET_ACTION_REMOVE,
                    evidence_refs=(),
                ),
            ),
            compatibility_surfaces=(
                surface(
                    surface_id="legacy-input-rejection-test",
                    classification=COMPATIBILITY_SURFACE_NEGATIVE_LEGACY_TEST,
                    recommended_action=COMPATIBILITY_ACTION_REJECT,
                    candidate_ids=("remove-legacy-test",),
                    evidence_refs=(),
                    rationale="this test is the only evidence that legacy input is rejected",
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="negative legacy tests must not disappear as dead code",
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertEqual("compatibility_surface_blocked", report.decision)
        self.assertEqual((), report.ready_candidate_ids)
        self.assertIn(
            "compatibility_surface_negative_legacy_test_requires_evidence",
            [finding.code for finding in report.findings],
        )

    def test_archive_only_surface_with_runtime_authority_blocks(self):
        plan = ArchitectureReductionPlan(
            "router-archive-authority-reduction",
            observable_contract=contract(),
            candidates=(candidate(),),
            compatibility_surfaces=(
                surface(
                    classification=COMPATIBILITY_SURFACE_ARCHIVE_ONLY,
                    recommended_action=COMPATIBILITY_ACTION_ARCHIVE,
                    runtime_authority=True,
                    rationale="historical mapping still writes runtime state",
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="archive-only material cannot retain runtime authority",
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertEqual("compatibility_surface_blocked", report.decision)
        self.assertEqual((), report.ready_candidate_ids)
        self.assertIn(
            "compatibility_surface_archive_has_runtime_authority",
            [finding.code for finding in report.findings],
        )

    def test_evidence_needed_surface_blocks_ready_candidate(self):
        plan = ArchitectureReductionPlan(
            "router-missing-evidence-reduction",
            observable_contract=contract(),
            candidates=(candidate(),),
            compatibility_surfaces=(
                surface(
                    classification=COMPATIBILITY_SURFACE_EVIDENCE_NEEDED,
                    recommended_action=COMPATIBILITY_ACTION_COLLECT_EVIDENCE,
                    missing_evidence=("external caller inventory",),
                    rationale="external caller usage is unknown",
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="missing evidence must keep contraction blocked",
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertEqual("evidence_blocked", report.decision)
        self.assertEqual((), report.ready_candidate_ids)
        self.assertIn("compatibility_surface_evidence_needed", [finding.code for finding in report.findings])

    def test_negative_legacy_test_with_replacement_evidence_can_continue(self):
        plan = ArchitectureReductionPlan(
            "router-negative-test-replaced",
            observable_contract=contract(),
            candidates=(
                candidate(
                    candidate_id="remove-legacy-test",
                    candidate_type=CANDIDATE_REMOVE_STATE_FIELD,
                    code_node_id="tests.legacy_input_rejection",
                    source_model_element="RejectLegacyInput",
                    target_action=TARGET_ACTION_REMOVE,
                    evidence_refs=("tests/test_current_rejection.py",),
                ),
            ),
            compatibility_surfaces=(
                surface(
                    surface_id="legacy-input-rejection-test",
                    classification=COMPATIBILITY_SURFACE_NEGATIVE_LEGACY_TEST,
                    recommended_action=COMPATIBILITY_ACTION_REJECT,
                    candidate_ids=("remove-legacy-test",),
                    evidence_refs=("tests/test_current_rejection.py",),
                    rationale="replacement rejection evidence exists",
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="negative legacy evidence has a replacement",
        )

        report = review_architecture_reduction(plan)

        self.assertTrue(report.ok)
        self.assertEqual("architecture_reduction_ready", report.decision)
        self.assertEqual(("remove-legacy-test",), report.ready_candidate_ids)


if __name__ == "__main__":
    unittest.main()
