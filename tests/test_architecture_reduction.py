import unittest
from dataclasses import replace

from flowguard import (
    CANDIDATE_DISPOSITION_COMPLETED,
    CANDIDATE_COLLAPSE_ADAPTER,
    CANDIDATE_KEEP_PUBLIC_FACADE,
    CANDIDATE_MERGE_HANDLERS,
    CANDIDATE_REMOVE_BRANCH,
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

from flowguard.architecture_reduction import (
    ARCHITECTURE_REDUCTION_STEP_ACTIONS,
    ARCHITECTURE_REDUCTION_STEP_ASSESSMENT_SCHEMA,
    ARCHITECTURE_REDUCTION_STEP_COST_SCHEMA,
    ARCHITECTURE_RETIREMENT_GOVERNED_IDENTITY_ROLES,
    ARCHITECTURE_RETIREMENT_REQUIRED_ROUTES,
    PROOF_AUTHORIZED_RETIREMENT,
    RETIREMENT_DISPOSITION_MIGRATE,
    RETIREMENT_DISPOSITION_RETIRE,
    RETIREMENT_OWNER_STATUS_EXACT_CURRENT,
    RETIREMENT_RESPONSIBILITY_BEHAVIOR,
    RETIREMENT_RESPONSIBILITY_CODE,
    RETIREMENT_RESPONSIBILITY_COMMITMENT,
    RETIREMENT_RESPONSIBILITY_CONSUMER,
    RETIREMENT_RESPONSIBILITY_MODEL,
    RETIREMENT_RESPONSIBILITY_NEGATIVE_CASE,
    RETIREMENT_RESPONSIBILITY_PROMPT,
    RETIREMENT_RESPONSIBILITY_PUBLIC_SURFACE,
    RETIREMENT_RESPONSIBILITY_RELEASE_CLAIM,
    RETIREMENT_RESPONSIBILITY_ROUTE,
    RETIREMENT_RESPONSIBILITY_SKILL,
    RETIREMENT_RESPONSIBILITY_TEST,
    RETIREMENT_RESPONSIBILITY_TOPOLOGY_RELATION,
    TARGET_ACTION_RETIRE_BEHAVIOR,
    STEP_ACTION_DELEGATE,
    STEP_ACTION_EXPLICIT_ON_DEMAND,
    STEP_ACTION_MERGE,
    STEP_ACTION_REMOVE,
    STEP_ACTION_RETAIN,
    STEP_ACTION_UNRESOLVED,
    STEP_KIND_PAYLOAD_MATERIALIZATION,
    STEP_KIND_VALIDATION,
    ArchitectureRetirementProof,
    ArchitectureReductionStepAssessment,
    ArchitectureReductionStepCost,
    RetirementResponsibilityDisposition,
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


RETIREMENT_RESPONSIBILITY_IDS = {
    RETIREMENT_RESPONSIBILITY_COMMITMENT: ("commitment:legacy-search",),
    RETIREMENT_RESPONSIBILITY_BEHAVIOR: ("behavior:legacy-search",),
    RETIREMENT_RESPONSIBILITY_CODE: ("code:legacy-search",),
    RETIREMENT_RESPONSIBILITY_TEST: ("test:legacy-search",),
    RETIREMENT_RESPONSIBILITY_MODEL: ("model:legacy-search",),
    RETIREMENT_RESPONSIBILITY_PUBLIC_SURFACE: ("surface:legacy-search",),
    RETIREMENT_RESPONSIBILITY_CONSUMER: ("consumer:legacy-search",),
    RETIREMENT_RESPONSIBILITY_NEGATIVE_CASE: ("negative:invalid-query",),
    RETIREMENT_RESPONSIBILITY_ROUTE: ("route:legacy-search",),
    RETIREMENT_RESPONSIBILITY_SKILL: ("skill:legacy-search",),
    RETIREMENT_RESPONSIBILITY_PROMPT: ("prompt:legacy-search",),
    RETIREMENT_RESPONSIBILITY_TOPOLOGY_RELATION: ("topology:legacy-search",),
    RETIREMENT_RESPONSIBILITY_RELEASE_CLAIM: ("claim:legacy-search",),
}


def retirement_disposition(
    responsibility_kind: str,
    responsibility_id: str,
) -> RetirementResponsibilityDisposition:
    if responsibility_kind == RETIREMENT_RESPONSIBILITY_NEGATIVE_CASE:
        return RetirementResponsibilityDisposition(
            responsibility_kind,
            responsibility_id,
            RETIREMENT_DISPOSITION_MIGRATE,
            "the rejection rule remains necessary and moves to the current validation owner",
            evidence_refs=("evidence:negative-case-replay",),
            replacement_owner_id="owner:current-validation",
            replacement_owner_status=RETIREMENT_OWNER_STATUS_EXACT_CURRENT,
            oracle_id="oracle:reject-invalid-query",
            protection_required=True,
        )
    return RetirementResponsibilityDisposition(
        responsibility_kind,
        responsibility_id,
        RETIREMENT_DISPOSITION_RETIRE,
        "the current goal and exact-current inventory show this responsibility has no remaining authority",
        evidence_refs=(f"evidence:{responsibility_kind}:current",),
    )


def retirement_proof(**kwargs) -> ArchitectureRetirementProof:
    defaults = {
        "retirement_id": "retirement:legacy-search:v1",
        "current_goal_rationale": (
            "the current product goal uses one direct search route, so the historical "
            "parallel search behavior no longer owns a supported outcome"
        ),
        "inventory_revision": "retirement-inventory:v1",
        "inventory_current": True,
        "owner_resolution_status": RETIREMENT_OWNER_STATUS_EXACT_CURRENT,
        "retired_commitment_ids": RETIREMENT_RESPONSIBILITY_IDS[
            RETIREMENT_RESPONSIBILITY_COMMITMENT
        ],
        "retired_behavior_ids": RETIREMENT_RESPONSIBILITY_IDS[
            RETIREMENT_RESPONSIBILITY_BEHAVIOR
        ],
        "code_binding_ids": RETIREMENT_RESPONSIBILITY_IDS[
            RETIREMENT_RESPONSIBILITY_CODE
        ],
        "test_binding_ids": RETIREMENT_RESPONSIBILITY_IDS[
            RETIREMENT_RESPONSIBILITY_TEST
        ],
        "model_binding_ids": RETIREMENT_RESPONSIBILITY_IDS[
            RETIREMENT_RESPONSIBILITY_MODEL
        ],
        "public_surface_ids": RETIREMENT_RESPONSIBILITY_IDS[
            RETIREMENT_RESPONSIBILITY_PUBLIC_SURFACE
        ],
        "consumer_ids": RETIREMENT_RESPONSIBILITY_IDS[
            RETIREMENT_RESPONSIBILITY_CONSUMER
        ],
        "negative_case_ids": RETIREMENT_RESPONSIBILITY_IDS[
            RETIREMENT_RESPONSIBILITY_NEGATIVE_CASE
        ],
        "route_ids": RETIREMENT_RESPONSIBILITY_IDS[
            RETIREMENT_RESPONSIBILITY_ROUTE
        ],
        "skill_ids": RETIREMENT_RESPONSIBILITY_IDS[
            RETIREMENT_RESPONSIBILITY_SKILL
        ],
        "prompt_ids": RETIREMENT_RESPONSIBILITY_IDS[
            RETIREMENT_RESPONSIBILITY_PROMPT
        ],
        "topology_relation_ids": RETIREMENT_RESPONSIBILITY_IDS[
            RETIREMENT_RESPONSIBILITY_TOPOLOGY_RELATION
        ],
        "release_claim_ids": RETIREMENT_RESPONSIBILITY_IDS[
            RETIREMENT_RESPONSIBILITY_RELEASE_CLAIM
        ],
        "responsibility_dispositions": tuple(
            retirement_disposition(kind, responsibility_id)
            for kind, responsibility_ids in RETIREMENT_RESPONSIBILITY_IDS.items()
            for responsibility_id in responsibility_ids
        ),
        "replacement_owner_ids": ("owner:current-validation",),
        "required_validation_routes": tuple(
            sorted(ARCHITECTURE_RETIREMENT_REQUIRED_ROUTES)
        ),
        "governed_identity_fingerprints": {
            role: "sha256:" + (f"{index:064x}"[-64:])
            for index, role in enumerate(
                sorted(ARCHITECTURE_RETIREMENT_GOVERNED_IDENTITY_ROLES),
                start=1,
            )
        },
        "evidence_refs": (
            "evidence:observed-model-current",
            "evidence:consumer-inventory-current",
        ),
    }
    defaults.update(kwargs)
    return ArchitectureRetirementProof(**defaults)


def retirement_candidate(**kwargs) -> ArchitectureReductionCandidate:
    defaults = {
        "candidate_id": "retire-legacy-search",
        "candidate_type": CANDIDATE_REMOVE_BRANCH,
        "code_node_id": "router.legacy_search",
        "source_model_element": "LegacySearch",
        "target_action": TARGET_ACTION_RETIRE_BEHAVIOR,
        "proof_status": PROOF_AUTHORIZED_RETIREMENT,
        "required_next_route": ROUTE_STRUCTURE_MESH,
        "rationale": "retire one historical route after every responsibility is dispositioned",
        "affected_public_entrypoints": ("router.cli",),
        "affected_state": ("route_status",),
        "affected_side_effects": ("write_event",),
        "evidence_refs": ("evidence:retirement-review",),
        "business_intent_id": "intent:direct-search",
        "behavior_commitment_id": "commitment:legacy-search",
        "primary_path_id": "path:legacy-search",
        "inventory_revision": "retirement-inventory:v1",
        "retirement_proof": retirement_proof(),
    }
    defaults.update(kwargs)
    return ArchitectureReductionCandidate(**defaults)


def retirement_plan(
    retirement: ArchitectureReductionCandidate | None = None,
    **kwargs,
) -> ArchitectureReductionPlan:
    selected = retirement or retirement_candidate()
    defaults = {
        "reduction_id": "retire-legacy-search",
        "observable_contract": contract(),
        "candidates": (selected,),
        "companion_route_triggers": (trigger(),),
        "rationale": "current goals authorize retiring one historically accumulated branch",
        "inventory_revision": "retirement-inventory:v1",
        "inventory_source_ref": "preflight:retirement-inventory:v1",
        "inventory_current": True,
        "expected_candidate_ids": (selected.candidate_id,),
        "require_complete_inventory": True,
    }
    defaults.update(kwargs)
    return ArchitectureReductionPlan(**defaults)


def step_cost(**kwargs) -> ArchitectureReductionStepCost:
    defaults = {
        "measurement_id": "cost:validation-step:v1",
        "subject_revision": "source:v1",
        "source_ref": "inventory:source:v1",
        "measurement_mode": "static_inventory_projection",
        "operation_count": 9,
        "payload_bytes": 4096,
        "estimated_token_count": 1024,
        "invocation_count": 3,
        "current": True,
        "rationale": "exact current static operations and emitted review bytes",
    }
    defaults.update(kwargs)
    return ArchitectureReductionStepCost(**defaults)


def step_assessment(**kwargs) -> ArchitectureReductionStepAssessment:
    defaults = {
        "assessment_id": "step-assessment:validate-input:v1",
        "parent_route_id": "route:router",
        "step_id": "router.validate_input",
        "step_kind": STEP_KIND_VALIDATION,
        "action": STEP_ACTION_RETAIN,
        "proof_status": PROOF_RISKY_KEEP,
        "rationale": "the step remains the sole current rejection-rule owner",
        "current_owner_ids": ("owner:router-validation",),
        "necessity_evidence_refs": ("commitment:reject-invalid-input",),
        "caller_inventory_complete": True,
        "cost_evidence": (step_cost(),),
        "safety_inventory_complete": True,
        "safety_responsibility_ids": ("negative-case:invalid-input",),
        "safety_owner_bindings": {
            "negative-case:invalid-input": "router.validate_input"
        },
        "safety_evidence_refs": ("oracle:reject-invalid-input",),
    }
    defaults.update(kwargs)
    return ArchitectureReductionStepAssessment(**defaults)


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
                    business_intent_id="intent:router.route",
                    behavior_commitment_id="commitment:router.route",
                    primary_path_id="path:router.primary",
                    owner_code_contract_id="router.route.owner",
                    delegates_to_code_contract_id="router.route.owner",
                    delegates_to_primary_path_id="path:router.primary",
                    delegation_evidence_id="runtime:router.cli:v1",
                    delegation_evidence_current=True,
                    delegation_only=True,
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="public CLI facade must stay while internals contract",
        )

        report = review_architecture_reduction(plan)

        self.assertTrue(report.ok)
        self.assertEqual("architecture_reduction_ready", report.decision)
        self.assertEqual(("keep-cli-facade",), report.ready_candidate_ids)

    def test_expected_candidate_inventory_blocks_omitted_candidate(self):
        plan = ArchitectureReductionPlan(
            "router-inventory-reduction",
            observable_contract=contract(),
            candidates=(candidate(inventory_revision="candidates:v2"),),
            expected_candidate_ids=("collapse-normalizer-adapter", "merge-cli-handlers"),
            inventory_revision="candidates:v2",
            inventory_source_ref="preflight:router:v2",
            require_complete_inventory=True,
            companion_route_triggers=(trigger(),),
            rationale="candidate completeness uses an independent preflight inventory",
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertEqual("candidate_inventory_blocked", report.decision)
        self.assertIn("expected_reduction_candidate_missing", [finding.code for finding in report.findings])
        self.assertEqual(("merge-cli-handlers",), report.missing_candidate_ids)

    def test_canonical_relation_handoff_cannot_finish_with_empty_candidate_inventory(self):
        plan = ArchitectureReductionPlan(
            "router-canonical-relation-reduction",
            observable_contract=contract(),
            candidates=(),
            canonical_relation_handoff={
                "relations": ({
                    "relation_id": "relation:duplicate-router-handler",
                    "relation_type": "duplicate_boundary",
                    "source_endpoint_kind": "model",
                    "source_endpoint_id": "router",
                    "target_endpoint_kind": "code_boundary",
                    "target_endpoint_id": "router-handler",
                    "source_ids": ("semantic-mesh:router:v3",),
                },),
                "code_obligation_ids": ("relation-code:router-handler",),
            },
            inventory_revision="candidates:v3",
            inventory_source_ref="canonical-relation:router:v3",
            companion_route_triggers=(trigger(),),
            rationale="duplicate handoff must materialize a reduction candidate",
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertEqual("candidate_inventory_blocked", report.decision)
        self.assertIn("canonical_relation_candidate_inventory_empty", [finding.code for finding in report.findings])

    def test_retained_facade_with_independent_authority_is_blocked(self):
        plan = ArchitectureReductionPlan(
            "router-facade-parallel-success",
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
                    business_intent_id="intent:router.route",
                    behavior_commitment_id="commitment:router.route",
                    primary_path_id="path:router.primary",
                    owner_code_contract_id="router.route.owner",
                    delegates_to_code_contract_id="router.route.owner",
                    delegates_to_primary_path_id="path:router.primary",
                    delegation_evidence_id="runtime:router.cli:v1",
                    delegation_evidence_current=True,
                    delegation_only=False,
                    independent_business_authority=True,
                ),
            ),
            companion_route_triggers=(trigger(),),
            rationale="retained facade cannot own a second success path",
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertEqual("facade_delegation_blocked", report.decision)
        self.assertIn("facade_independent_business_authority", [finding.code for finding in report.findings])

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

    def test_complete_current_retirement_proof_allows_intentional_behavior_change(self):
        proof = retirement_proof()

        report = review_architecture_reduction(
            retirement_plan(retirement_candidate(retirement_proof=proof))
        )

        self.assertTrue(report.ok)
        self.assertEqual("architecture_reduction_ready", report.decision)
        self.assertEqual(("retire-legacy-search",), report.ready_candidate_ids)
        self.assertEqual(TARGET_ACTION_RETIRE_BEHAVIOR, report.target_actions[0].action)
        self.assertEqual(proof.fingerprint, report.target_actions[0].retirement_proof.fingerprint)
        self.assertTrue(
            ARCHITECTURE_RETIREMENT_REQUIRED_ROUTES.issubset(
                report.required_next_routes
            )
        )
        self.assertNotIn(
            "removes_observable_state",
            {finding.code for finding in report.findings},
        )
        self.assertNotIn(
            "observable_side_effect_without_equivalence",
            {finding.code for finding in report.findings},
        )
        self.assertEqual(proof, ArchitectureRetirementProof.from_dict(proof.to_dict()))

    def test_retirement_proof_requires_every_consumer_disposition(self):
        proof = retirement_proof()
        incomplete = replace(
            proof,
            responsibility_dispositions=tuple(
                item
                for item in proof.responsibility_dispositions
                if item.responsibility_kind != RETIREMENT_RESPONSIBILITY_CONSUMER
            ),
        )

        report = review_architecture_reduction(
            retirement_plan(retirement_candidate(retirement_proof=incomplete))
        )

        self.assertFalse(report.ok)
        self.assertEqual((), report.ready_candidate_ids)
        self.assertIn(
            "retirement_responsibility_disposition_incomplete",
            {finding.code for finding in report.findings},
        )

    def test_retirement_action_is_withheld_when_complete_inventory_has_a_gap(self):
        report = review_architecture_reduction(
            retirement_plan(
                expected_candidate_ids=(
                    "retire-legacy-search",
                    "retire-unmaterialized-route",
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual((), report.ready_candidate_ids)
        self.assertEqual((), report.target_actions)
        self.assertIn(
            "expected_reduction_candidate_missing",
            {finding.code for finding in report.findings},
        )

    def test_retirement_blocks_stale_ambiguous_or_unknown_authority(self):
        cases = {
            "stale inventory": (
                replace(retirement_proof(), inventory_current=False),
                "retirement_inventory_stale",
            ),
            "ambiguous owner": (
                replace(
                    retirement_proof(),
                    owner_resolution_status="ambiguous",
                ),
                "retirement_owner_resolution_not_current",
            ),
            "unknown identity": (
                replace(
                    retirement_proof(),
                    governed_identity_fingerprints={
                        **retirement_proof().governed_identity_fingerprints,
                        "unknown_inventory": "sha256:" + "f" * 64,
                    },
                ),
                "retirement_governed_identities_incomplete",
            ),
        }

        for label, (proof, expected_code) in cases.items():
            with self.subTest(label=label):
                report = review_architecture_reduction(
                    retirement_plan(retirement_candidate(retirement_proof=proof))
                )
                self.assertFalse(report.ok)
                self.assertEqual((), report.ready_candidate_ids)
                self.assertIn(
                    expected_code,
                    {finding.code for finding in report.findings},
                )

    def test_retirement_forbids_alias_compatibility_and_fallback_dispositions(self):
        for disposition in ("alias", "compatibility", "fallback"):
            with self.subTest(disposition=disposition):
                proof = retirement_proof()
                rows = tuple(
                    replace(item, disposition=disposition)
                    if item.responsibility_kind == RETIREMENT_RESPONSIBILITY_CONSUMER
                    else item
                    for item in proof.responsibility_dispositions
                )
                report = review_architecture_reduction(
                    retirement_plan(
                        retirement_candidate(
                            retirement_proof=replace(
                                proof,
                                responsibility_dispositions=rows,
                            )
                        )
                    )
                )

                self.assertFalse(report.ok)
                self.assertEqual((), report.ready_candidate_ids)
                self.assertIn(
                    "retirement_compatibility_or_fallback_forbidden",
                    {finding.code for finding in report.findings},
                )

    def test_retirement_preserves_required_negative_case_under_current_owner(self):
        proof = retirement_proof()
        rows = tuple(
            replace(
                item,
                disposition=RETIREMENT_DISPOSITION_RETIRE,
                replacement_owner_id="",
                replacement_owner_status="not_applicable",
                oracle_id="",
            )
            if item.responsibility_kind == RETIREMENT_RESPONSIBILITY_NEGATIVE_CASE
            else item
            for item in proof.responsibility_dispositions
        )
        orphaned = replace(
            proof,
            responsibility_dispositions=rows,
            replacement_owner_ids=(),
        )

        report = review_architecture_reduction(
            retirement_plan(retirement_candidate(retirement_proof=orphaned))
        )
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertEqual((), report.ready_candidate_ids)
        self.assertIn("retained_protection_without_current_owner", codes)
        self.assertIn("retirement_negative_case_orphaned", codes)

    def test_retirement_cannot_survive_as_a_kept_compatibility_surface(self):
        report = review_architecture_reduction(
            retirement_plan(
                compatibility_surfaces=(
                    surface(
                        surface_id="legacy-search-surface",
                        classification=COMPATIBILITY_SURFACE_CURRENT_CONTRACT,
                        recommended_action=COMPATIBILITY_ACTION_KEEP,
                        code_node_ids=("router.legacy_search",),
                        candidate_ids=("retire-legacy-search",),
                        rationale="this contradictory classification still keeps the old route current",
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual((), report.ready_candidate_ids)
        self.assertIn(
            "retirement_compatibility_surface_retained",
            {finding.code for finding in report.findings},
        )

    def test_retirement_serialization_accepts_only_exact_current_schema(self):
        payload = retirement_proof().to_dict()
        with_extra_field = {**payload, "legacy_alias": "retirement:v0"}
        stale_fingerprint = {
            **payload,
            "current_goal_rationale": "a changed rationale invalidates the frozen identity",
        }

        with self.assertRaisesRegex(ValueError, "current schema exactly"):
            ArchitectureRetirementProof.from_dict(with_extra_field)
        with self.assertRaisesRegex(ValueError, "fingerprint is stale"):
            ArchitectureRetirementProof.from_dict(stale_fingerprint)

    def test_ordinary_equivalence_action_cannot_attach_retirement_authority(self):
        report = review_architecture_reduction(
            ArchitectureReductionPlan(
                "ordinary-collapse",
                observable_contract=contract(),
                candidates=(candidate(retirement_proof=retirement_proof()),),
                companion_route_triggers=(trigger(),),
                rationale="ordinary contraction remains governed by equivalence",
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual((), report.ready_candidate_ids)
        self.assertIn(
            "retirement_proof_on_contract_action",
            {finding.code for finding in report.findings},
        )

    def test_retained_route_internal_step_has_typed_necessity_and_cost_evidence(self):
        retained = step_assessment()
        report = review_architecture_reduction(
            ArchitectureReductionPlan(
                "router-internal-step-review",
                observable_contract=contract(),
                candidates=(candidate(),),
                companion_route_triggers=(trigger(),),
                rationale="review the retained route and its internal validation step",
                step_assessments=(retained,),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual((retained,), report.step_assessments)
        self.assertEqual((retained.step_id,), report.cost_priority_step_ids)
        payload = retained.to_dict()
        self.assertEqual(
            ARCHITECTURE_REDUCTION_STEP_ASSESSMENT_SCHEMA,
            payload["schema_version"],
        )
        self.assertEqual(
            ARCHITECTURE_REDUCTION_STEP_COST_SCHEMA,
            payload["cost_evidence"][0]["schema_version"],
        )
        self.assertEqual(
            retained,
            ArchitectureReductionStepAssessment.from_dict(payload),
        )
        self.assertEqual(
            {
                STEP_ACTION_RETAIN,
                STEP_ACTION_MERGE,
                STEP_ACTION_DELEGATE,
                STEP_ACTION_REMOVE,
                STEP_ACTION_EXPLICIT_ON_DEMAND,
                STEP_ACTION_UNRESOLVED,
            },
            ARCHITECTURE_REDUCTION_STEP_ACTIONS,
        )

    def test_high_cost_does_not_authorize_step_removal_without_equivalence(self):
        high_cost = step_cost(
            measurement_id="cost:large-payload:v1",
            operation_count=100_000,
            payload_bytes=50_000_000,
            estimated_token_count=12_500_000,
        )
        removal_candidate = candidate(
            candidate_id="remove-large-projection",
            candidate_type=CANDIDATE_REMOVE_BRANCH,
            code_node_id="router.large_projection",
            target_action=TARGET_ACTION_REMOVE,
            proof_status=PROOF_RISKY_KEEP,
            required_next_route=ROUTE_STRUCTURE_MESH,
        )
        assessment = step_assessment(
            assessment_id="step-assessment:large-projection:v1",
            step_id="router.large_projection",
            step_kind=STEP_KIND_PAYLOAD_MATERIALIZATION,
            action=STEP_ACTION_REMOVE,
            proof_status=PROOF_RISKY_KEEP,
            candidate_id=removal_candidate.candidate_id,
            current_owner_ids=(),
            necessity_evidence_refs=(),
            equivalence_evidence_refs=(),
            caller_ids=(),
            replacement_step_ids=(),
            cost_evidence=(high_cost,),
            safety_responsibility_ids=(),
            safety_owner_bindings={},
            safety_evidence_refs=(),
            unresolved_gap_ids=("current_observable_equivalence",),
            rationale="the payload is expensive, but cost alone cannot prove removal safe",
        )

        report = review_architecture_reduction(
            ArchitectureReductionPlan(
                "large-projection-review",
                observable_contract=contract(),
                candidates=(removal_candidate,),
                companion_route_triggers=(trigger(),),
                rationale="prioritize the expensive step without weakening proof",
                step_assessments=(assessment,),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn(
            "step_contraction_equivalence_missing",
            {finding.code for finding in report.findings},
        )
        self.assertEqual((), report.ready_candidate_ids)

    def test_unique_safety_owner_blocks_remove_even_with_equivalence(self):
        removal_candidate = candidate(
            candidate_id="remove-validation-step",
            candidate_type=CANDIDATE_REMOVE_BRANCH,
            code_node_id="router.validate_input",
            target_action=TARGET_ACTION_REMOVE,
            proof_status=PROOF_SAFE_BY_EQUIVALENCE,
            required_next_route=ROUTE_STRUCTURE_MESH,
            evidence_refs=("equivalence:validation:v1",),
        )
        assessment = step_assessment(
            action=STEP_ACTION_REMOVE,
            proof_status=PROOF_SAFE_BY_EQUIVALENCE,
            candidate_id=removal_candidate.candidate_id,
            equivalence_evidence_refs=("equivalence:validation:v1",),
            current_owner_ids=(),
            necessity_evidence_refs=(),
            safety_owner_bindings={
                "negative-case:invalid-input": "router.validate_input"
            },
            rationale="removal still leaves its negative-case oracle bound to the removed step",
        )
        report = review_architecture_reduction(
            ArchitectureReductionPlan(
                "unsafe-validation-removal",
                observable_contract=contract(),
                candidates=(removal_candidate,),
                companion_route_triggers=(trigger(),),
                rationale="verify exact safety ownership before contraction",
                step_assessments=(assessment,),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn(
            "step_unique_safety_owner_removed",
            {finding.code for finding in report.findings},
        )
        self.assertEqual((), report.ready_candidate_ids)

    def test_on_demand_step_requires_explicit_trigger_and_equivalence(self):
        on_demand_candidate = candidate(
            candidate_id="defer-deep-scan",
            candidate_type=CANDIDATE_COLLAPSE_ADAPTER,
            code_node_id="router.deep_scan",
            target_action=TARGET_ACTION_COLLAPSE,
            proof_status=PROOF_SAFE_BY_EQUIVALENCE,
            evidence_refs=("equivalence:deep-scan:v1",),
        )
        assessment = step_assessment(
            assessment_id="step-assessment:deep-scan:v1",
            step_id="router.deep_scan",
            step_kind=STEP_KIND_PAYLOAD_MATERIALIZATION,
            action=STEP_ACTION_EXPLICIT_ON_DEMAND,
            proof_status=PROOF_SAFE_BY_EQUIVALENCE,
            candidate_id=on_demand_candidate.candidate_id,
            equivalence_evidence_refs=("equivalence:deep-scan:v1",),
            current_owner_ids=(),
            necessity_evidence_refs=(),
            safety_responsibility_ids=(),
            safety_owner_bindings={},
            safety_evidence_refs=(),
            on_demand_trigger_ids=(),
            rationale="the deep scan may move behind an explicit request only with a trigger",
        )
        report = review_architecture_reduction(
            ArchitectureReductionPlan(
                "deep-scan-on-demand",
                observable_contract=contract(),
                candidates=(on_demand_candidate,),
                companion_route_triggers=(trigger(),),
                rationale="make expensive optional work explicit",
                step_assessments=(assessment,),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn(
            "step_on_demand_trigger_missing",
            {finding.code for finding in report.findings},
        )

    def test_step_assessment_serialization_rejects_extra_and_stale_fields(self):
        assessment_payload = step_assessment().to_dict()
        cost_payload = step_cost().to_dict()

        with self.assertRaisesRegex(ValueError, "current schema exactly"):
            ArchitectureReductionStepAssessment.from_dict(
                {**assessment_payload, "legacy_action": "prune"}
            )
        with self.assertRaisesRegex(ValueError, "fingerprint is stale"):
            ArchitectureReductionStepAssessment.from_dict(
                {**assessment_payload, "rationale": "changed after freeze"}
            )
        with self.assertRaisesRegex(ValueError, "current schema exactly"):
            ArchitectureReductionStepCost.from_dict(
                {**cost_payload, "score": 99}
            )
        with self.assertRaisesRegex(ValueError, "fingerprint is stale"):
            ArchitectureReductionStepCost.from_dict(
                {**cost_payload, "payload_bytes": cost_payload["payload_bytes"] + 1}
            )


if __name__ == "__main__":
    unittest.main()
