from __future__ import annotations

from dataclasses import replace

import flowguard
from flowguard import (
    BCL_ACTOR_END_USER,
    BCL_COMMITMENT_WORKFLOW,
    BCL_EVIDENCE_CURRENT_PASS,
    BCL_PLANE_PRODUCT_RUNTIME,
    BCL_SCOPE_FULL,
    BCL_SOURCE_API,
    BCL_SOURCE_UI,
    CANDIDATE_COLLAPSE_ADAPTER,
    CODE_CONTRACT_ROLE_FACADE,
    CONTRACT_MUTATION_OMITTED_FAMILY_MEMBER,
    CONTRACT_MUTATION_OMITTED_REDUCTION_CANDIDATE,
    CONTRACT_MUTATION_SIMILARITY_MATERIALIZATION,
    CONTRACT_MUTATION_UNMATERIALIZED_SIMILARITY_ID,
    FAMILY_EVIDENCE_PROVENANCE_DURABLE_RECONCILIATION,
    FAMILY_EVIDENCE_STATUS_PASSED,
    PPA_AUTHORITY_EXTERNAL_FACADE,
    PPA_BEHAVIOR_DELEGATE_TO_PRIMARY,
    PPA_CANDIDATE_COMPATIBILITY_FACADE,
    PPA_CLAIM_SCOPE_FULL,
    PPA_CONFIDENCE_FULL,
    PPA_DECISION_GREEN,
    PPA_DISPOSITION_PRESERVE_FACADE,
    PROOF_SAFE_BY_EQUIVALENCE,
    REUSE_DECISION_EXTEND_EXISTING,
    ROUTE_CODE_STRUCTURE_RECOMMENDATION,
    TARGET_ACTION_COLLAPSE,
    ArchitectureReductionCandidate,
    ArchitectureReductionPlan,
    BehaviorCommitment,
    BehaviorCommitmentLedger,
    BehaviorEvidenceBinding,
    BehaviorPathAuthorityBinding,
    BehaviorSourceSurface,
    CodeContract,
    ExistingIntentSurface,
    ExistingModelPreflight,
    ExistingOwnershipSnapshot,
    FallbackPathCandidate,
    ModelContextHit,
    ModelObligation,
    ModelTestAlignmentPlan,
    ObligationFamily,
    ObligationFamilyEvidence,
    ObligationFamilyMember,
    ObservableArchitectureContract,
    PrimaryPathAuthorityPlan,
    PrimaryPathContract,
    ProofArtifactRef,
    RuntimeNodeContract,
    RuntimeNodeObservation,
    RuntimePathAlignmentPlan,
    TestEvidence,
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    UIContentVisibilityItem,
    UIContentVisibilityPlan,
    UIProductConsistencyObservation,
    UIProductConsistencyPlan,
    UIProductConsistencyRule,
    UIProductSurface,
    UI_CONTENT_VISIBILITY_USER_VISIBLE,
    UI_PRODUCT_CLAIM_COMPLETE,
    UI_PRODUCT_CONSISTENCY_KINDS,
    UI_PRODUCT_CONSISTENCY_TYPOGRAPHY,
    behavior_commitment_contract_exhaustion_plan,
    default_ui_product_language_case_seeds,
    primary_path_authority_contract_exhaustion_plan,
    review_architecture_reduction,
    review_behavior_commitment_ledger,
    review_contract_exhaustion,
    review_existing_model_preflight,
    review_model_test_alignment,
    review_obligation_family_parity,
    review_primary_path_authority,
    review_runtime_path_alignment,
    review_test_mesh,
    review_ui_content_visibility,
    review_ui_product_consistency,
)


INTENT_ID = "intent:download-material"
COMMITMENT_ID = "commitment:download-material"
PRIMARY_PATH_ID = "path:download-material"
OBLIGATION_ID = "obligation:download-material"
OWNER_CONTRACT_ID = "download.material.primary"
UI_SURFACE_ID = "surface:download-page"
API_SURFACE_ID = "surface:download-api"
PRIMARY_CANDIDATE_ID = "candidate:download-primary"
API_CANDIDATE_ID = "candidate:download-api"
REVISION = "download-material:v1"


def finding_codes(report) -> set[str]:
    return {finding.code for finding in report.findings}


def current_proof() -> ProofArtifactRef:
    return ProofArtifactRef(
        "proof:download-material",
        producer_route="runtime_path_evidence",
        command="python -m pytest tests/test_product_language_path_reuse.py -q",
        result_path=".flowguard/evidence/product-language-path-reuse/runtime.json",
        result_status="passed",
        exit_code=0,
        artifact_fingerprints={OWNER_CONTRACT_ID: "sha256:download-material-v1"},
        covered_obligation_ids=(OBLIGATION_ID,),
    )


def intent_surface(surface_id: str, surface_kind: str) -> ExistingIntentSurface:
    return ExistingIntentSurface(
        surface_id,
        surface_kind=surface_kind,
        business_intent_id=INTENT_ID,
        behavior_commitment_id=COMMITMENT_ID,
        business_path_id=PRIMARY_PATH_ID,
        primary_path_id=PRIMARY_PATH_ID,
        expected_terminal="download_ready_or_visible_error",
        state_writes=("download_status",),
        side_effects=("prepare_download",),
        owner_id="download-material-model",
        evidence_ids=(f"inventory:{surface_id}",),
    )


def preflight(*, expected_surface_ids=(UI_SURFACE_ID, API_SURFACE_ID), surfaces=None):
    return review_existing_model_preflight(
        ExistingModelPreflight(
            "download-material-preflight",
            "Reuse one validated download path across the page and API",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard/download-material",),
            relevant_models=(
                ModelContextHit(
                    "download-material-model",
                    function_blocks=("PrepareDownload",),
                    state_owned=("download_status",),
                    side_effects_owned=("prepare_download",),
                    public_entrypoints=("download.material",),
                ),
            ),
            ownership_snapshot=ExistingOwnershipSnapshot(
                function_block_owners=(("PrepareDownload", "download-material-model"),),
                state_owners=(("download_status", "download-material-model"),),
                side_effect_owners=(("prepare_download", "download-material-model"),),
            ),
            reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
            downstream_routes=("behavior_commitment_ledger", "primary_path_authority"),
            rationale="Both surfaces expose the same exact external purpose.",
            affected_business_intent_id=INTENT_ID,
            selected_commitment_id=COMMITMENT_ID,
            selected_primary_path_id=PRIMARY_PATH_ID,
            expected_surface_ids=expected_surface_ids,
            intent_surfaces=tuple(
                surfaces
                if surfaces is not None
                else (
                    intent_surface(UI_SURFACE_ID, "ui"),
                    intent_surface(API_SURFACE_ID, "api"),
                )
            ),
            surface_inventory_revision=REVISION,
            surface_inventory_evidence_ids=("inventory:download-material:v1",),
            require_complete_surface_inventory=True,
        )
    )


def commitment(commitment_id: str = COMMITMENT_ID) -> BehaviorCommitment:
    return BehaviorCommitment(
        commitment_id,
        business_intent_id=INTENT_ID,
        label="download material",
        commitment_kind=BCL_COMMITMENT_WORKFLOW,
        behavior_plane=BCL_PLANE_PRODUCT_RUNTIME,
        actor_kind=BCL_ACTOR_END_USER,
        actor="end user",
        trigger="requests a material download",
        preconditions=("material is available",),
        expected_result="download becomes available or a repairable error is visible",
        expected_terminal="download_ready_or_visible_error",
        state_writes=("download_status",),
        side_effects=("prepare_download",),
        failure_boundary="fail closed with a user-understandable recovery message",
        source_surface_ids=(UI_SURFACE_ID, API_SURFACE_ID),
        primary_owner_model_id="download-material-model",
        path_authority=BehaviorPathAuthorityBinding(
            path_sensitive=True,
            business_intent="download material",
            business_intent_id=INTENT_ID,
            behavior_commitment_id=commitment_id,
            ppa_report_id="ppa:download-material",
            ppa_decision=PPA_DECISION_GREEN,
            ppa_confidence=PPA_CONFIDENCE_FULL,
            ppa_ok=True,
            primary_path_id=PRIMARY_PATH_ID,
            fallback_candidate_ids=(API_CANDIDATE_ID,),
            ppa_coverage_receipt_ids=("contract_coverage:download-material",),
            ppa_coverage_shard_ids=("contract_shard:download-material",),
            ppa_risk_gate_ids=("risk_gate:download-material",),
            evidence_refs=("test:download-material",),
            runtime_observation_ids=("runtime:download-material",),
            proof_artifact_ids=("proof:download-material",),
            evidence_current=True,
        ),
        evidence=BehaviorEvidenceBinding(
            model_obligation_ids=(OBLIGATION_ID,),
            code_contract_ids=(OWNER_CONTRACT_ID,),
            test_evidence_ids=("test:download-material",),
            proof_artifact_ids=("proof:download-material",),
            risk_gate_ids=("risk_gate:behavior_commitment_coverage:download-material",),
            coverage_case_ids=("bcl.download-material.same-intent",),
            coverage_shard_ids=("contract_shard:behavior_commitment_ledger:download-material",),
            coverage_receipt_ids=("contract_coverage:behavior_commitment_ledger",),
            evidence_state=BCL_EVIDENCE_CURRENT_PASS,
            current=True,
        ),
        validation_boundary="preflight, PPA, runtime, UI, and MTA share the same identity",
        rationale="This is the single external promise; the API is a delegating surface.",
    )


def behavior_ledger(*, commitments=None, surface_commitment_ids=(COMMITMENT_ID,)):
    rows = tuple(commitments if commitments is not None else (commitment(),))
    return review_behavior_commitment_ledger(
        BehaviorCommitmentLedger(
            "download-material-ledger",
            project_boundary="download material external behavior",
            current_revision=REVISION,
            claim_scope=BCL_SCOPE_FULL,
            owner="download maintainer",
            validation_boundary="complete exact-intent behavior review",
            rationale="Register one promise and map both public surfaces to it.",
            expected_commitment_ids=tuple(item.commitment_id for item in rows),
            expected_business_intent_ids=(INTENT_ID,),
            source_surfaces=(
                BehaviorSourceSurface(
                    UI_SURFACE_ID,
                    BCL_SOURCE_UI,
                    label="download page",
                    source_ref="ui/download-page",
                    commitment_ids=surface_commitment_ids,
                    business_intent_ids=(INTENT_ID,),
                    primary_path_id=PRIMARY_PATH_ID,
                    owner="download UI",
                    validation_boundary="page click-through",
                    rationale="The page exposes the primary user entry.",
                ),
                BehaviorSourceSurface(
                    API_SURFACE_ID,
                    BCL_SOURCE_API,
                    label="download API",
                    source_ref="api/download-material",
                    commitment_ids=surface_commitment_ids,
                    business_intent_ids=(INTENT_ID,),
                    primary_path_id=PRIMARY_PATH_ID,
                    delegates_to_primary_path=True,
                    owner="download API",
                    validation_boundary="facade delegation replay",
                    rationale="The API delegates to the same selected path.",
                ),
            ),
            commitments=rows,
        )
    )


def primary_path(path_id: str = PRIMARY_PATH_ID) -> PrimaryPathContract:
    return PrimaryPathContract(
        path_id,
        business_intent="download material",
        business_intent_id=INTENT_ID,
        behavior_commitment_id=COMMITMENT_ID,
        primary_entrypoint_id="download.material.primary",
        owner_model_id="download-material-model",
        owner_code_contract_id=OWNER_CONTRACT_ID,
        expected_terminal="download_ready_or_visible_error",
        preconditions=("material is available",),
        state_writes=("download_status",),
        side_effects=("prepare_download",),
        evidence_ids=("runtime:download-material",),
        runtime_evidence_state="current_pass",
        runtime_observation_ids=("runtime:download-material",),
        required_obligation_ids=(OBLIGATION_ID,),
        proof_artifact=current_proof(),
        source_surface_ids=(UI_SURFACE_ID,),
    )


def api_facade() -> FallbackPathCandidate:
    return FallbackPathCandidate(
        API_CANDIDATE_ID,
        fallback_for_path_id=PRIMARY_PATH_ID,
        business_intent="download material",
        business_intent_id=INTENT_ID,
        behavior_commitment_id=COMMITMENT_ID,
        source_surface_id=API_SURFACE_ID,
        delegates_to_path_id=PRIMARY_PATH_ID,
        candidate_surface=PPA_CANDIDATE_COMPATIBILITY_FACADE,
        candidate_behavior=PPA_BEHAVIOR_DELEGATE_TO_PRIMARY,
        classification=PPA_AUTHORITY_EXTERNAL_FACADE,
        disposition=PPA_DISPOSITION_PRESERVE_FACADE,
        evidence_refs=("runtime:download-api-delegates",),
        compatibility_intent="Keep the API entry while delegating to the selected path.",
    )


def path_authority(*, primary_paths=None):
    return review_primary_path_authority(
        PrimaryPathAuthorityPlan(
            "download-material-authority",
            primary_paths=tuple(primary_paths if primary_paths is not None else (primary_path(),)),
            fallback_candidates=(api_facade(),),
            claim_scope=PPA_CLAIM_SCOPE_FULL,
            coverage_case_ids=("ppa.download-material.no-fallback",),
            coverage_shard_ids=("contract_shard:download-material",),
            coverage_receipt_ids=("contract_coverage:download-material",),
            risk_gate_ids=("risk_gate:download-material",),
            expected_business_intent_ids=(INTENT_ID,),
            expected_candidate_ids=(API_CANDIDATE_ID,),
            expected_surface_ids=(UI_SURFACE_ID, API_SURFACE_ID),
            inventory_revision=REVISION,
            inventory_evidence_ids=("inventory:download-material:v1",),
            preflight_id="download-material-preflight",
            behavior_commitment_ledger_id="download-material-ledger",
            existing_current_path_ids=(PRIMARY_PATH_ID,),
            require_complete_candidate_inventory=True,
            require_material_runtime_evidence=True,
        )
    )


def runtime_contract(node_id: str, *, facade: bool = False) -> RuntimeNodeContract:
    return RuntimeNodeContract(
        node_id,
        model_id="download-material-model",
        model_path=".flowguard/download-material/model.py",
        leaf_model_id="download-material-model",
        model_obligation_id=OBLIGATION_ID,
        code_contract_id="download.material.api" if facade else OWNER_CONTRACT_ID,
        boundary_id="download.material.boundary",
        business_path_id=PRIMARY_PATH_ID,
        business_intent="download material",
        business_intent_id=INTENT_ID,
        behavior_commitment_id=COMMITMENT_ID,
        expected_terminal="download_ready_or_visible_error",
        primary_path_id=PRIMARY_PATH_ID,
        surface_id=API_SURFACE_ID if facade else UI_SURFACE_ID,
        candidate_id=API_CANDIDATE_ID if facade else PRIMARY_CANDIDATE_ID,
        surface_role="facade" if facade else "owner",
        delegates_to_primary_path_id=PRIMARY_PATH_ID if facade else "",
        delegation_evidence_id="runtime:download-api-delegates" if facade else "",
        delegation_evidence_current=facade,
        delegation_only=facade,
        require_no_fallback=True,
        allowed_outputs=("download_ready",),
        allowed_state_writes=("download_status",),
    )


def runtime_observation(node_id: str, *, facade: bool = False, primary_path_id=PRIMARY_PATH_ID):
    return RuntimeNodeObservation(
        f"observation:{node_id}",
        node_id,
        run_id="run:download-material:v1",
        model_id="download-material-model",
        model_path=".flowguard/download-material/model.py",
        leaf_model_id="download-material-model",
        model_obligation_id=OBLIGATION_ID,
        code_contract_id="download.material.api" if facade else OWNER_CONTRACT_ID,
        boundary_id="download.material.boundary",
        business_path_id=PRIMARY_PATH_ID,
        business_intent="download material",
        business_intent_id=INTENT_ID,
        behavior_commitment_id=COMMITMENT_ID,
        primary_path_id=primary_path_id,
        surface_id=API_SURFACE_ID if facade else UI_SURFACE_ID,
        candidate_id=API_CANDIDATE_ID if facade else PRIMARY_CANDIDATE_ID,
        surface_role="facade" if facade else "owner",
        delegates_to_primary_path_id=PRIMARY_PATH_ID if facade else "",
        delegation_evidence_id="runtime:download-api-delegates" if facade else "",
        delegation_evidence_current=facade,
        delegation_observed=facade,
        observed_output="download_ready",
        observed_terminal="download_ready_or_visible_error",
        observed_state_writes=("download_status",),
        evidence_id=f"evidence:{node_id}",
    )


def runtime_alignment(*, observations=None):
    contracts = (runtime_contract("download-primary"), runtime_contract("download-api", facade=True))
    observed = tuple(
        observations
        if observations is not None
        else (
            runtime_observation("download-primary"),
            runtime_observation("download-api", facade=True),
        )
    )
    return review_runtime_path_alignment(
        RuntimePathAlignmentPlan(
            "download-material-runtime",
            model_id="download-material-model",
            node_contracts=contracts,
            observations=observed,
            business_intent_id=INTENT_ID,
            behavior_commitment_id=COMMITMENT_ID,
            primary_path_id=PRIMARY_PATH_ID,
            inventory_revision=REVISION,
            expected_surface_ids=(UI_SURFACE_ID, API_SURFACE_ID),
            expected_candidate_ids=(PRIMARY_CANDIDATE_ID, API_CANDIDATE_ID),
            require_complete_inventory=True,
        )
    )


def ui_plan() -> UIProductConsistencyPlan:
    rule_ids = tuple(f"rule:{kind}" for kind in UI_PRODUCT_CONSISTENCY_KINDS)
    surfaces = tuple(
        UIProductSurface(
            surface_id,
            surface_kind,
            business_bearing=True,
            business_intent_id=INTENT_ID,
            behavior_commitment_id=COMMITMENT_ID,
            primary_path_id=PRIMARY_PATH_ID,
            consistency_rule_ids=rule_ids,
            current_revision=REVISION,
            evidence_refs=(f"evidence:{surface_id}",),
            rationale="Repeated download surfaces share one product language and authority.",
        )
        for surface_id, surface_kind in ((UI_SURFACE_ID, "page"), (API_SURFACE_ID, "dialog"))
    )
    canonical_values = {
        "component": "download-action",
        "navigation": "material-actions",
        "interaction": "request-download",
        "feedback": "download-preparing",
        "recovery": "return-to-material",
        "transition": "ready-to-preparing",
    }
    rules = tuple(
        UIProductConsistencyRule(
            f"rule:{kind}",
            kind,
            f"download:{kind}",
            canonical_surface_id=UI_SURFACE_ID,
            expected_surface_ids=(UI_SURFACE_ID, API_SURFACE_ID),
            canonical_value=canonical_values.get(kind, ""),
            hierarchy_role="primary_action_label" if kind == UI_PRODUCT_CONSISTENCY_TYPOGRAPHY else "",
            typography_token_id="action-primary" if kind == UI_PRODUCT_CONSISTENCY_TYPOGRAPHY else "",
            typography_scale="1rem" if kind == UI_PRODUCT_CONSISTENCY_TYPOGRAPHY else "",
            typography_weight="600" if kind == UI_PRODUCT_CONSISTENCY_TYPOGRAPHY else "",
            business_intent_id=INTENT_ID,
            behavior_commitment_id=COMMITMENT_ID,
            primary_path_id=PRIMARY_PATH_ID,
            rationale="Canonical product rule for the repeated download action.",
        )
        for kind in UI_PRODUCT_CONSISTENCY_KINDS
    )
    observations = tuple(
        UIProductConsistencyObservation(
            f"observation:{kind}:{surface_id}",
            f"rule:{kind}",
            surface_id,
            observed_value=canonical_values.get(kind, ""),
            hierarchy_role="primary_action_label" if kind == UI_PRODUCT_CONSISTENCY_TYPOGRAPHY else "",
            typography_token_id="action-primary" if kind == UI_PRODUCT_CONSISTENCY_TYPOGRAPHY else "",
            typography_scale="1rem" if kind == UI_PRODUCT_CONSISTENCY_TYPOGRAPHY else "",
            typography_weight="600" if kind == UI_PRODUCT_CONSISTENCY_TYPOGRAPHY else "",
            business_intent_id=INTENT_ID,
            behavior_commitment_id=COMMITMENT_ID,
            primary_path_id=PRIMARY_PATH_ID,
            evidence_ref=f"evidence:{kind}:{surface_id}",
            covered_revision=REVISION,
            rationale="Observed surface matches the canonical semantic rule.",
        )
        for kind in UI_PRODUCT_CONSISTENCY_KINDS
        for surface_id in (UI_SURFACE_ID, API_SURFACE_ID)
    )
    return UIProductConsistencyPlan(
        "download-material-product-language",
        claim_scope=UI_PRODUCT_CLAIM_COMPLETE,
        current_revision=REVISION,
        expected_surface_ids=(UI_SURFACE_ID, API_SURFACE_ID),
        surfaces=surfaces,
        rules=rules,
        observations=observations,
        source_interaction_model_id="download-material-ui-flow",
        validation_boundaries=("cross-surface product-language review",),
        rationale="The complete review compares every surface and semantic kind.",
    )


def model_test_alignment():
    owner = CodeContract(
        OWNER_CONTRACT_ID,
        path="download/service.py",
        symbol="DownloadService.prepare",
        implements_obligations=(OBLIGATION_ID,),
        external_outputs=("download_ready",),
        state_writes=("download_status",),
        business_intent_id=INTENT_ID,
        behavior_commitment_id=COMMITMENT_ID,
        primary_path_id=PRIMARY_PATH_ID,
    )
    facade = CodeContract(
        "download.material.api",
        path="download/api.py",
        symbol="download_material",
        role=CODE_CONTRACT_ROLE_FACADE,
        implements_obligations=(OBLIGATION_ID,),
        external_outputs=("download_ready",),
        state_writes=("download_status",),
        business_intent_id=INTENT_ID,
        behavior_commitment_id=COMMITMENT_ID,
        primary_path_id=PRIMARY_PATH_ID,
        delegates_to_code_contract_id=OWNER_CONTRACT_ID,
        delegation_evidence_id="runtime:download-api-delegates",
        delegation_evidence_current=True,
        delegation_only=True,
    )
    return review_model_test_alignment(
        ModelTestAlignmentPlan(
            "download-material-model",
            obligations=(
                ModelObligation(
                    OBLIGATION_ID,
                    required_test_kinds=("happy_path",),
                    external_outputs=("download_ready",),
                    state_writes=("download_status",),
                    business_intent_id=INTENT_ID,
                    behavior_commitment_id=COMMITMENT_ID,
                    primary_path_id=PRIMARY_PATH_ID,
                    required_runtime_node_ids=("download-primary",),
                ),
            ),
            code_contracts=(owner, facade),
            test_evidence=(
                TestEvidence(
                    "test:download-material",
                    result_status="passed",
                    covered_obligations=(OBLIGATION_ID,),
                    covered_code_contracts=(OWNER_CONTRACT_ID,),
                    business_intent_id=INTENT_ID,
                    behavior_commitment_id=COMMITMENT_ID,
                    primary_path_id=PRIMARY_PATH_ID,
                ),
            ),
            runtime_node_contracts=(runtime_contract("download-primary"),),
            runtime_node_observations=(runtime_observation("download-primary"),),
            require_runtime_path_evidence=True,
            require_stable_authority_ids=True,
        )
    )


def test_same_intent_chain_reuses_one_commitment_path_and_product_language():
    reports = {
        "preflight": preflight(),
        "ledger": behavior_ledger(),
        "path": path_authority(),
        "runtime": runtime_alignment(),
        "ui": review_ui_product_consistency(ui_plan()),
        "alignment": model_test_alignment(),
    }

    failures = {name: report.format_text() for name, report in reports.items() if not report.ok}
    assert not failures, failures
    assert reports["preflight"].business_intent_id == INTENT_ID
    assert reports["preflight"].behavior_commitment_id == COMMITMENT_ID
    assert reports["preflight"].primary_path_id == PRIMARY_PATH_ID
    assert reports["path"].primary_path_id == PRIMARY_PATH_ID
    assert reports["runtime"].primary_path_id == PRIMARY_PATH_ID
    assert set(reports["ui"].covered_surface_ids) == {UI_SURFACE_ID, API_SURFACE_ID}
    assert COMMITMENT_ID in reports["ledger"].covered_commitment_ids


def test_duplicate_or_omitted_same_intent_authority_is_blocked_by_existing_owners():
    missing_surface = preflight(surfaces=(intent_surface(UI_SURFACE_ID, "ui"),))
    duplicate_commitment = commitment("commitment:download-material-parallel")
    duplicate_ledger = behavior_ledger(
        commitments=(commitment(), duplicate_commitment),
        surface_commitment_ids=(COMMITMENT_ID, duplicate_commitment.commitment_id),
    )
    duplicate_path = path_authority(
        primary_paths=(
            primary_path(),
            primary_path("path:download-material-parallel"),
        )
    )
    wrong_runtime = runtime_alignment(
        observations=(
            runtime_observation("download-primary", primary_path_id="path:download-material-parallel"),
            runtime_observation("download-api", facade=True),
        )
    )

    assert not missing_surface.ok
    assert "missing_expected_intent_surface" in finding_codes(missing_surface)
    assert not duplicate_ledger.ok
    assert "duplicate_exact_intent_commitment" in finding_codes(duplicate_ledger)
    assert not duplicate_path.ok
    assert "duplicate_primary_runtime_authority" in finding_codes(duplicate_path)
    assert not wrong_runtime.ok
    assert "runtime_node_primary_path_mismatch" in finding_codes(wrong_runtime)


def test_internal_ui_fields_and_cross_surface_typography_drift_are_blocked():
    content_report = review_ui_content_visibility(
        UIContentVisibilityPlan(
            "download-internal-field-leak",
            current_revision=REVISION,
            candidate_content_ids=("content:commitment-id",),
            items=(
                UIContentVisibilityItem(
                    "content:commitment-id",
                    source_field_ids=("behavior_commitment_id",),
                    visibility_class=UI_CONTENT_VISIBILITY_USER_VISIBLE,
                    rationale="Known-bad internal identity exposure.",
                ),
            ),
            validation_boundaries=("content admission",),
            rationale="Internal authority fields do not become ordinary UI copy.",
        )
    )
    plan = ui_plan()
    drifted = replace(
        plan,
        observations=tuple(
            replace(
                observation,
                typography_token_id="dialog-one-off",
                typography_scale="0.875rem",
            )
            if observation.rule_id == "rule:typography" and observation.surface_id == API_SURFACE_ID
            else observation
            for observation in plan.observations
        ),
    )
    typography_report = review_ui_product_consistency(drifted)

    assert not content_report.ok
    assert "internal_product_content_leak" in finding_codes(content_report)
    assert not typography_report.ok
    assert "typography_role_drift" in finding_codes(typography_report)


def test_family_reduction_and_background_inventory_cannot_be_shrunk_or_faked():
    family_report = review_obligation_family_parity(
        (
            ObligationFamily(
                "download-family",
                members=(
                    ObligationFamilyMember("page", obligation_ids=("obligation:download-page",)),
                ),
                required_mechanisms=("same-primary-path",),
                allowed_provenance=(FAMILY_EVIDENCE_PROVENANCE_DURABLE_RECONCILIATION,),
                expected_member_ids=("page", "api"),
                inventory_revision=REVISION,
                inventory_source_ref="preflight:download-material",
                require_complete_inventory=True,
            ),
        ),
        (
            ObligationFamilyEvidence(
                "evidence:download-page",
                family_id="download-family",
                member_id="page",
                mechanism_id="same-primary-path",
                provenance=FAMILY_EVIDENCE_PROVENANCE_DURABLE_RECONCILIATION,
                result_status=FAMILY_EVIDENCE_STATUS_PASSED,
                covered_obligations=("obligation:download-page",),
            ),
        ),
    )
    reduction_report = review_architecture_reduction(
        ArchitectureReductionPlan(
            "download-reduction",
            observable_contract=ObservableArchitectureContract(
                source_model_id="download-material-model",
                source_code_boundary_id="download-package",
                public_entrypoints=("download.material",),
                observable_outputs=("download_ready",),
                validation_boundaries=("download parity tests",),
                rationale="Preserve the selected public behavior.",
            ),
            candidates=(
                ArchitectureReductionCandidate(
                    "collapse-download-adapter",
                    candidate_type=CANDIDATE_COLLAPSE_ADAPTER,
                    code_node_id="download.adapter",
                    source_model_element="PrepareDownload",
                    target_action=TARGET_ACTION_COLLAPSE,
                    proof_status=PROOF_SAFE_BY_EQUIVALENCE,
                    required_next_route=ROUTE_CODE_STRUCTURE_RECOMMENDATION,
                    inventory_revision=REVISION,
                    rationale="The adapter delegates without owning behavior.",
                ),
            ),
            expected_candidate_ids=("collapse-download-adapter", "merge-download-handler"),
            inventory_revision=REVISION,
            inventory_source_ref="preflight:download-material",
            require_complete_inventory=True,
            rationale="A caller cannot omit the inconvenient duplicate handler.",
        )
    )
    mesh_report = review_test_mesh(
        TestMeshPlan(
            parent_suite_id="download-regression",
            partition_items=(TestPartitionItem("download-chain", owner_suite_id="download-chain"),),
            child_suites=(
                TestSuiteEvidence(
                    "download-chain",
                    result_status="running",
                    evidence_tier="abstract_green",
                    background=True,
                    progress_only=True,
                    has_exit_artifact=False,
                    has_result_artifact=False,
                    test_count=1,
                    selected_count=1,
                ),
            ),
            target_split_derivation=TestTargetSplitDerivation(
                "download-material-model",
                target_suite_ids=("download-chain",),
                covered_partition_item_ids=("download-chain",),
                rationale="The parent model assigns the chain to one child suite.",
            ),
        )
    )

    assert not family_report.ok
    assert "expected_family_member_missing" in finding_codes(family_report)
    assert not reduction_report.ok
    assert "expected_reduction_candidate_missing" in finding_codes(reduction_report)
    assert not mesh_report.ok
    assert "background_incomplete" in finding_codes(mesh_report)


def test_exhaustion_contracts_include_identity_omission_and_ui_language_faults():
    behavior_plan = behavior_commitment_contract_exhaustion_plan(max_combinations=50000)
    path_plan = primary_path_authority_contract_exhaustion_plan(max_combinations=50000)
    behavior_report = review_contract_exhaustion(behavior_plan)
    path_report = review_contract_exhaustion(path_plan)
    behavior_axes = {axis.axis_id for axis in behavior_plan.axes}
    path_axes = {axis.axis_id for axis in path_plan.axes}
    ui_cases = {seed.mutation_kind: seed for seed in default_ui_product_language_case_seeds()}

    assert behavior_report.ok, behavior_report.format_text()
    assert path_report.ok, path_report.format_text()
    assert {"exact_intent_identity_state", "primary_path_binding_shape", "surface_authority_role"} <= behavior_axes
    assert {"business_intent_identity", "primary_path_selection", "candidate_inventory_state", "runtime_proof_state"} <= path_axes
    assert {"illegal_visibility_class", "internal_content_leak", "semantic_drift", "invalid_behavior_authority_exception", "valid_presentation_exception"} <= set(ui_cases)
    assert ui_cases["valid_presentation_exception"].expected_ok
    assert not ui_cases["internal_content_leak"].expected_ok
    mutation_names = {
        CONTRACT_MUTATION_OMITTED_FAMILY_MEMBER,
        CONTRACT_MUTATION_OMITTED_REDUCTION_CANDIDATE,
        CONTRACT_MUTATION_SIMILARITY_MATERIALIZATION,
        CONTRACT_MUTATION_UNMATERIALIZED_SIMILARITY_ID,
    }
    assert mutation_names == {
        "omitted_family_member",
        "omitted_reduction_candidate",
        "similarity_materialization",
        "unmaterialized_similarity_id",
    }
    assert all(name in flowguard.CONTRACT_EXHAUSTION_MESH_API for name in (
        "CONTRACT_MUTATION_OMITTED_FAMILY_MEMBER",
        "CONTRACT_MUTATION_OMITTED_REDUCTION_CANDIDATE",
        "CONTRACT_MUTATION_SIMILARITY_MATERIALIZATION",
        "CONTRACT_MUTATION_UNMATERIALIZED_SIMILARITY_ID",
    ))
