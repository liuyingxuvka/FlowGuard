from __future__ import annotations

from dataclasses import dataclass, replace
import json
from unittest import mock

import pytest

import flowguard.software_blueprint_readiness as blueprint_readiness

from flowguard.evidence_receipts import (
    RECEIPT_STATUS_PASS,
    EvidenceReceipt,
    ReceiptVerificationResult,
    build_environment_fingerprint,
    fingerprint_value,
    snapshot_bytes,
)
from flowguard.implementation_blueprint import (
    BlueprintResourceReference,
    OracleReference,
    SemanticSpecReference,
)
from flowguard.affected_blueprint_reader import (
    AffectedBlueprintReadError,
    read_affected_blueprint,
)
from flowguard.software_blueprint_readiness import (
    BEHAVIOR_CASE_DIMENSIONS,
    BEHAVIOR_DIMENSIONS,
    BehaviorBlockContract,
    BehaviorCaseContract,
    BehaviorCoverageEdge,
    BehaviorDimensionContract,
    CoverageExecutionEvidence,
    DelegatedAssertionHelper,
    IntentSourceAuthority,
    ObservedResourceMember,
    PortableBehaviorBinding,
    ProjectIntentInventory,
    ProjectIntentContribution,
    ProjectResourceInventory,
    ProjectResourceMember,
    ProjectTestNodeDisposition,
    SoftwareBlueprintReadinessError,
    SupportingSurfaceRelation,
    generate_candidate_blueprint,
    materialize_behavior_blueprint_shards,
    normalize_behavior_blueprint,
    review_behavior_blueprint,
    review_static_blueprint_readiness,
)
from flowguard.validation_ownership import ValidationOwnerContract
from flowguard.model_path_quality import PathQualityResult, PathQualitySubject
from flowguard.target_system_blueprint import (
    ModelPathQualityBlueprintBinding,
    TargetSystemBlueprintError,
)


CURRENT_PATH_QUALITY_ID = "sha256:revision"


def _fp(label: str) -> str:
    return fingerprint_value({"path-quality-fixture": label})


@dataclass(frozen=True)
class AssertionFixture:
    assertion_id: str
    structure_fingerprint: str


@dataclass(frozen=True)
class TestNodeFixture:
    __test__ = False
    node_id: str
    assertions: tuple[AssertionFixture, ...]
    calls: tuple[str, ...] = ()


def dimensions(
    surface_id: str,
    *,
    shared_surfaces: tuple[str, ...] | None = None,
) -> tuple[BehaviorDimensionContract, ...]:
    applicability = shared_surfaces or (surface_id,)
    shared_suffix = "shared" if shared_surfaces else surface_id
    return tuple(
        BehaviorDimensionContract(
            dimension=name,
            disposition=(
                "modeled"
                if name in {"input", "output", "error", "completion"}
                else "not_applicable"
            ),
            semantics=f"declared {name} semantics for {shared_suffix}",
            rationale="accepted model-purpose boundary",
            provenance_fingerprints=(("model-purpose", "sha256:model"),),
            semantic_rule_ids=(f"rule:{shared_suffix}:{name}",),
            applicability_surface_ids=applicability,
        )
        for name in BEHAVIOR_DIMENSIONS
    )


def contract(
    surface_id: str = "surface:save",
    *,
    accepted: bool = True,
    shared_surfaces: tuple[str, ...] | None = None,
) -> BehaviorBlockContract:
    return BehaviorBlockContract(
        behavior_block_id=f"behavior:{surface_id}",
        implementation_surface_id=surface_id,
        model_element_id="model:save",
        model_fingerprint=_fp("model:save"),
        owner_contract_id="contract:save",
        owner_id="owner:save",
        function_relation="Input x State -> Set(Output x State)",
        dimensions=dimensions(surface_id, shared_surfaces=shared_surfaces),
        semantic_spec_ids=("semantic:save",),
        oracle_ids=("oracle:save",),
        intent_contribution_ids=("intent:fixture",),
        portable_binding_ids=(f"portable:{surface_id}",),
        protected_failure_ids=("failure:rejected",),
        accepted=accepted,
        acceptance_evidence_fingerprints=(
            (("model-purpose", "sha256:model"),) if accepted else ()
        ),
        source_fingerprint=f"sha256:source:{surface_id}",
    )


def path_quality_binding(
    block: BehaviorBlockContract,
    *,
    subject_lane: str = "observed",
    change_kind: str = "materially_changed",
    currentness_id: str = CURRENT_PATH_QUALITY_ID,
    current: bool = True,
    conclusion: str = "single_clear_path",
    unresolved_ids: tuple[str, ...] = (),
) -> ModelPathQualityBlueprintBinding:
    subject = PathQualitySubject(
        model_id=block.model_element_id,
        boundary_id=f"path-boundary:{block.model_element_id}",
        model_fingerprint=block.model_fingerprint,
        normalized_facts_fingerprint=_fp("normalized-facts"),
        retained_element_inventory_fingerprint=_fp("retained-elements"),
        purpose_fingerprint=_fp("purpose"),
        intent_fingerprint=_fp("intent"),
        obligation_fingerprint=_fp("obligations"),
        provider_fingerprint=_fp("provider"),
        dependency_fingerprint=_fp("dependencies"),
        code_fingerprint=_fp("code"),
        test_fingerprint=_fp("tests"),
        oracle_fingerprint=_fp("oracles"),
        evidence_fingerprint=_fp("evidence"),
        currentness_id=currentness_id,
    )
    result = PathQualityResult(
        result_id=f"path-quality:{block.model_element_id}",
        subject_fingerprint=subject.fingerprint,
        mode="lightweight",
        trigger_ids=(),
        finding_ids=(),
        candidate_ids=(),
        rewrite_rule_ids=(),
        conclusion=conclusion,
        unresolved_ids=unresolved_ids,
        selected_candidate_id="",
        selected_candidate_lane="",
        comparison_boundary_id="",
        candidate_set_fingerprint="",
        rewrite_set_fingerprint="",
        necessity_witness_set_fingerprint=_fp("necessity-witnesses"),
        detail_evidence_fingerprint=_fp("path-quality-detail"),
        producer_id="model_maturation",
        currentness_id=currentness_id,
        current=current,
    )
    return ModelPathQualityBlueprintBinding(
        model_element_id=block.model_element_id,
        subject_lane=subject_lane,
        change_kind=change_kind,
        subject=subject,
        result=result,
        affected_topology_evidence_fingerprint=(
            _fp("affected-topology") if change_kind == "unchanged" else ""
        ),
        affected_topology_currentness_id=(
            currentness_id if change_kind == "unchanged" else ""
        ),
    )


def portable(block: BehaviorBlockContract) -> PortableBehaviorBinding:
    return PortableBehaviorBinding(
        binding_id=block.portable_binding_ids[0],
        behavior_block_id=block.behavior_block_id,
        portable_model_id="portable-model:save",
        portable_model_fingerprint="sha256:portable",
        implementation_fingerprint=block.source_fingerprint,
        transition_ids=("transition:save",),
        property_ids=("property:save",),
        invariant_ids=("invariant:save",),
        input_field_mappings=(("value", "input:value"),),
        output_field_mappings=(("return", "output:return"),),
        state_field_mappings=(),
        assumption_ids=("assumption:accepted-input",),
        guarantee_ids=("guarantee:saved-output",),
        protected_failure_ids=block.protected_failure_ids,
        provider_fingerprints=(("portable-provider", "sha256:provider"),),
    )


def semantic_spec(
    blocks: tuple[BehaviorBlockContract, ...],
    *,
    source_content_fingerprint: str = "sha256:semantic-content",
) -> SemanticSpecReference:
    return SemanticSpecReference(
        semantic_spec_id="semantic:save",
        owner_id="owner:semantic",
        artifact_id="artifact:semantic:save",
        artifact_fingerprint="sha256:semantic-artifact",
        source_id="intent:model-purpose",
        source_owner_id="owner:model-purpose",
        source_content_fingerprint=source_content_fingerprint,
        covered_model_element_ids=tuple(block.model_element_id for block in blocks),
        covered_dimensions=(
            "input",
            "output",
            "state_effect",
            "error",
            "order",
            "retry",
            "timeout",
            "decision",
            "completion",
        ),
        semantics=(
            ("input", "accept the declared input boundary"),
            ("output", "return the declared outcome"),
            ("state_effect", "preserve exact state and effect expectations"),
            ("error", "reject the declared invalid input"),
            ("order", "preserve declared ordering"),
            ("retry", "preserve declared retry semantics"),
            ("timeout", "preserve declared timeout semantics"),
            ("decision", "preserve declared decision boundary"),
            ("completion", "preserve declared completion condition"),
        ),
        provenance_fingerprints=(
            ("model-purpose", "sha256:model"),
            ("intent:fixture-source", "sha256:intent-source"),
        ),
    )


def oracle_reference(
    blocks: tuple[BehaviorBlockContract, ...],
    *,
    source_content_fingerprint: str = "sha256:oracle-content",
) -> OracleReference:
    return OracleReference(
        oracle_id="oracle:save",
        owner_id="owner:oracle",
        artifact_id="artifact:oracle:save",
        artifact_fingerprint="sha256:oracle-artifact",
        source_id="oracle:test-design",
        source_owner_id="owner:test-design",
        source_content_fingerprint=source_content_fingerprint,
        covered_model_element_ids=tuple(block.model_element_id for block in blocks),
        covered_dimensions=(
            "input",
            "output",
            "state_effect",
            "error",
            "order",
            "retry",
            "timeout",
            "decision",
            "completion",
        ),
        semantics=(
            ("input", "exercise the declared input boundary"),
            ("output", "compare the exact declared outcome"),
            ("state_effect", "compare exact state and effects"),
            ("error", "compare exact error behavior"),
            ("order", "compare ordering"),
            ("retry", "compare retry behavior"),
            ("timeout", "compare timeout behavior"),
            ("decision", "compare the decision boundary"),
            ("completion", "compare completion"),
        ),
    )


def cases(block: BehaviorBlockContract) -> tuple[BehaviorCaseContract, ...]:
    return (
        BehaviorCaseContract(
            case_id=f"case:{block.behavior_block_id}:good",
            behavior_block_id=block.behavior_block_id,
            case_kind="good",
            input_values=(("value", "accepted"),),
            initial_state=(),
            expected_output=(("return", "saved:accepted"),),
            expected_state=(),
            expected_effects=(),
            expected_errors=(),
            oracle_id="oracle:save",
            case_evidence_id="assertion:save",
            case_evidence_fingerprint="sha256:assertion",
            value_mode="literal",
        ),
        BehaviorCaseContract(
            case_id=f"case:{block.behavior_block_id}:boundary",
            behavior_block_id=block.behavior_block_id,
            case_kind="boundary",
            input_values=(("value", "boundary"),),
            initial_state=(),
            expected_output=(("return", "saved:boundary"),),
            expected_state=(),
            expected_effects=(),
            expected_errors=(),
            oracle_id="oracle:save",
            case_evidence_id="assertion:save",
            case_evidence_fingerprint="sha256:assertion",
            value_mode="literal",
        ),
        BehaviorCaseContract(
            case_id=f"case:{block.behavior_block_id}:bad",
            behavior_block_id=block.behavior_block_id,
            case_kind="bad",
            input_values=(("value", "rejected"),),
            initial_state=(),
            expected_output=(),
            expected_state=(),
            expected_effects=(),
            expected_errors=("failure:rejected",),
            oracle_id="oracle:save",
            case_evidence_id="assertion:save",
            case_evidence_fingerprint="sha256:assertion",
            value_mode="literal",
            protected_failure_ids=("failure:rejected",),
        ),
    )


def coverage(
    block: BehaviorBlockContract,
    *,
    test_node_id: str = "test:save",
    member_id: str = "assertion:save",
    member_fingerprint: str = "sha256:assertion",
) -> BehaviorCoverageEdge:
    good_case = cases(block)[0]
    return BehaviorCoverageEdge(
        coverage_id=f"coverage:{block.behavior_block_id}",
        behavior_block_id=block.behavior_block_id,
        implementation_surface_id=block.implementation_surface_id,
        model_obligation_id=block.model_element_id,
        semantic_spec_id="semantic:save",
        semantic_content_fingerprint="sha256:semantic-content",
        owner_contract_id=block.owner_contract_id,
        behavior_owner_id=block.owner_id,
        implementation_content_fingerprint=block.source_fingerprint,
        test_node_id=test_node_id,
        oracle_member_id=member_id,
        oracle_member_fingerprint=member_fingerprint,
        case_id=f"case:{block.behavior_block_id}:good",
        case_content_fingerprint=good_case.content_fingerprint,
        covered_dimensions=BEHAVIOR_DIMENSIONS,
        evidence_role="real_test_assertion",
        oracle_id="oracle:save",
        oracle_content_fingerprint="sha256:oracle-content",
    )


def exact_design(blocks: tuple[BehaviorBlockContract, ...]):
    exact_cases: list[BehaviorCaseContract] = []
    edges: list[BehaviorCoverageEdge] = []
    planned: dict[str, str] = {}
    for block in blocks:
        for source_case in cases(block):
            case_checker_id = f"checker-design:{source_case.case_id}"
            case_checker_fingerprint = fingerprint_value(
                {"case": source_case.to_dict(), "checker_id": case_checker_id}
            )
            planned[case_checker_id] = case_checker_fingerprint
            exact_case = replace(
                source_case,
                case_evidence_id=case_checker_id,
                case_evidence_fingerprint=case_checker_fingerprint,
                parameter_case_id=source_case.case_id,
            )
            exact_cases.append(exact_case)
            for dimension in BEHAVIOR_CASE_DIMENSIONS[exact_case.case_kind]:
                member_id = f"{case_checker_id}:{dimension}"
                member_fingerprint = fingerprint_value(
                    {
                        "case_evidence_fingerprint": case_checker_fingerprint,
                        "dimension": dimension,
                    }
                )
                planned[member_id] = member_fingerprint
                edges.append(
                    BehaviorCoverageEdge(
                        coverage_id=(
                            f"coverage:{block.behavior_block_id}:"
                            f"{exact_case.case_id}:{dimension}"
                        ),
                        behavior_block_id=block.behavior_block_id,
                        implementation_surface_id=block.implementation_surface_id,
                        model_obligation_id=block.model_element_id,
                        semantic_spec_id="semantic:save",
                        semantic_content_fingerprint="sha256:semantic-content",
                        owner_contract_id=block.owner_contract_id,
                        behavior_owner_id=block.owner_id,
                        implementation_content_fingerprint=block.source_fingerprint,
                        test_node_id="test:save",
                        oracle_member_id=member_id,
                        oracle_member_fingerprint=member_fingerprint,
                        case_id=exact_case.case_id,
                        case_content_fingerprint=exact_case.content_fingerprint,
                        covered_dimensions=(dimension,),
                        evidence_role="planned_checker",
                        oracle_id="oracle:save",
                        oracle_content_fingerprint="sha256:oracle-content",
                    )
                )
    return tuple(exact_cases), tuple(edges), planned


def execution_bundle(
    edges: tuple[BehaviorCoverageEdge, ...],
    *,
    owner_id: str = "owner:test",
    receipt_id: str = "receipt:behavior-owner:one",
    subject_kind: str = "validation_owner",
    subject_id: str | None = None,
    producer_id: str | None = None,
    covered_ids: tuple[str, ...] | None = None,
) -> tuple[ValidationOwnerContract, EvidenceReceipt, ReceiptVerificationResult]:
    obligations = (
        tuple(edge.coverage_id for edge in edges)
        if covered_ids is None
        else covered_ids
    )
    contract_value = ValidationOwnerContract(
        owner_id=owner_id,
        command=("python", "-m", "pytest", "tests/test_behavior.py"),
        input_patterns=("tests/test_behavior.py",),
        obligation_ids=obligations,
    )
    environment = build_environment_fingerprint(
        {
            "python_implementation": "CPython",
            "python_version": "3.12.10",
            "platform_system": "Windows",
            "platform_machine": "AMD64",
            "flowguard_version": "0.68.6",
        }
    )
    snapshot = snapshot_bytes(
        f"behavior-input:{owner_id}",
        b"behavior evidence input\n",
        path_token="<WORKSPACE>/tests/test_behavior.py",
        obligation_ids=obligations,
    )
    owner_subject = subject_id or f"validation-owner:{owner_id}"
    owner_producer = producer_id or f"validation-owner:{owner_id}"
    receipt = EvidenceReceipt(
        receipt_id=receipt_id,
        subject_id=owner_subject,
        subject_kind=subject_kind,
        producer_id=owner_producer,
        producer_version="0.68.6",
        claim_scope="full",
        command=contract_value.command,
        working_directory_token="<WORKSPACE>",
        started_at="2026-08-04T08:00:00+00:00",
        finished_at="2026-08-04T08:00:01+00:00",
        exit_code=0,
        environment_fingerprint=environment.fingerprint,
        environment_metadata=environment.metadata,
        contract_hash=fingerprint_value({"owner": owner_id, "contract": True}),
        check_manifest_hash=fingerprint_value({"owner": owner_id, "checks": True}),
        suite_map_hash=fingerprint_value({"owner": owner_id, "suite": True}),
        input_snapshots=(snapshot,),
        proof_artifact_id=f"proof:behavior-owner:{owner_id}",
        proof_artifact_fingerprint=fingerprint_value(
            {"owner": owner_id, "proof": True}
        ),
        result_status=RECEIPT_STATUS_PASS,
        result_fingerprint=fingerprint_value({"owner": owner_id, "result": True}),
        covered_obligations=obligations,
        claim_boundary="Only the exact named behavior coverage members.",
    )
    verification = ReceiptVerificationResult(
        receipt_id=receipt.receipt_id,
        receipt_fingerprint=receipt.fingerprint,
        current=True,
        eligible=True,
        status=RECEIPT_STATUS_PASS,
        findings=(),
        satisfied_obligations=obligations,
        minimum_revalidation=(),
    )
    return contract_value, receipt, verification


def resource_inventory() -> ProjectResourceInventory:
    categories = (
        "build",
        "runtime",
        "dependency",
        "configuration",
        "schema",
        "data",
        "asset",
        "migration",
        "external_service",
        "behavioral_oracle",
    )
    members: list[ProjectResourceMember] = []
    for category in categories:
        scoped_out = category == "external_service"
        kind = "verification" if category == "behavioral_oracle" else category
        reference = BlueprintResourceReference(
            resource_id=f"resource:{category}",
            kind=kind,
            owner_id="owner:fixture",
            artifact_id=f"artifact:{category}",
            purpose=f"preserve the fixture {category} obligation",
            lifecycle_role="not_applicable" if scoped_out else "blueprint_input",
            consuming_behavior_ids=("behavior:surface:save",),
            consuming_model_ids=("model:save",),
            disposition="scoped_out" if scoped_out else "current",
            artifact_fingerprint=None if scoped_out else f"sha256:{category}",
            rationale="no external service is declared" if scoped_out else None,
            semantics=(
                ()
                if scoped_out
                else (("blueprint_contract", f"materialize {category}"),)
            ),
        )
        observed = (
            None
            if scoped_out
            else ObservedResourceMember(
                resource_id=reference.resource_id,
                kind=reference.kind,
                owner_id=reference.owner_id,
                artifact_id=reference.artifact_id,
                subject_revision="sha256:revision",
                current_artifact_fingerprint=str(reference.artifact_fingerprint),
                provider_id="provider:resource",
                capability_id="resource_inventory",
                payload_id="resource_inventory",
            )
        )
        members.append(
            ProjectResourceMember(
                member_id=reference.resource_id,
                category=category,
                category_disposition="scoped_out" if scoped_out else "current",
                category_evidence_fingerprint=(
                    "sha256:external-service-absence"
                    if observed is None
                    else observed.fingerprint
                ),
                resource_reference=reference,
                consuming_behavior_ids=reference.consuming_behavior_ids,
                consuming_model_ids=reference.consuming_model_ids,
                rationale=(
                    "no external service is declared"
                    if scoped_out
                    else "independently discovered current project resource"
                ),
                observed_resource=observed,
            )
        )
    return ProjectResourceInventory(
        inventory_id="resources:one",
        boundary_fingerprint="sha256:boundary",
        members=tuple(members),
        discovery_fingerprints=(("boundary-scan", "sha256:scan"),),
    )


def intent_inventory() -> ProjectIntentInventory:
    contribution = ProjectIntentContribution(
        contribution_id="intent:fixture",
        source_kind="accepted_change_objective",
        source_id="intent:fixture-source",
        source_owner_id="owner:fixture-intent",
        source_fingerprint="sha256:intent-source",
        expectation_id="expectation:fixture",
        expectation_fingerprint="sha256:intent-expectation",
        disposition="accepted",
        target_ids=("model:save",),
        rationale="the fixture binds every behavior to its exact model owner",
    )
    return ProjectIntentInventory(
        inventory_id="intent:one",
        subject_revision="sha256:revision",
        observed_subject_revision="sha256:revision",
        contributions=(contribution,),
        source_authorities=(
            IntentSourceAuthority(
                source_kind=contribution.source_kind,
                source_id=contribution.source_id,
                source_owner_id=contribution.source_owner_id,
                subject_revision="sha256:revision",
                current_source_fingerprint=contribution.source_fingerprint,
                expectation_id=contribution.expectation_id,
                current_expectation_fingerprint=(
                    contribution.expectation_fingerprint
                ),
                target_ids=contribution.target_ids,
                provider_id="provider:intent",
                capability_id="intent_lineage",
                payload_id="intent_lineage",
            ),
        ),
        authority_provider_capabilities=(
            ("provider:intent", "intent_lineage"),
        ),
        required_model_target_ids=("model:save",),
    )


def review(
    blocks: tuple[BehaviorBlockContract, ...] | None = None,
    *,
    required_surfaces: tuple[str, ...] | None = None,
    edges: tuple[BehaviorCoverageEdge, ...] | None = None,
    case_contracts: tuple[BehaviorCaseContract, ...] | None = None,
    relations: tuple[SupportingSurfaceRelation, ...] | None = None,
    portable_bindings: tuple[PortableBehaviorBinding, ...] | None = None,
    semantic_references: tuple[SemanticSpecReference, ...] | None = None,
    oracle_references: tuple[OracleReference, ...] | None = None,
    intent_inventory_value: ProjectIntentInventory | None = None,
    observed_source_fingerprints: dict[str, str] | None = None,
    observed_owner_ids: dict[str, str] | None = None,
    supporting_owner_blocks: dict[str, str] | None = None,
    expected_portable_members: dict[str, dict[str, tuple[str, ...]]] | None = None,
    planned_checker_fingerprints: dict[str, str] | None = None,
    executions: tuple[CoverageExecutionEvidence, ...] | None = None,
    node_dispositions: tuple[ProjectTestNodeDisposition, ...] | None = None,
    evidence_receipts: tuple[EvidenceReceipt, ...] = (),
    receipt_verification_results: tuple[ReceiptVerificationResult, ...] = (),
    validation_owner_contracts: tuple[ValidationOwnerContract, ...] = (),
    path_quality_bindings: tuple[ModelPathQualityBlueprintBinding, ...] | None = None,
    expected_path_quality_currentness_id: str = CURRENT_PATH_QUALITY_ID,
):
    blocks = blocks or (contract(),)
    all_cases, default_edges, planned_checkers = exact_design(blocks)
    edges = edges or default_edges
    if executions is None:
        executions = tuple(
            CoverageExecutionEvidence(
                coverage_id=edge.coverage_id,
                execution_owner_id="owner:test",
                disposition="not_run",
            )
            for edge in edges
        )
    node = TestNodeFixture(
        "test:save",
        (AssertionFixture("assertion:save", "sha256:assertion"),),
    )
    if relations is None:
        relations = (
            SupportingSurfaceRelation(
                "surface:helper",
                blocks[0].behavior_block_id,
                "calls",
                "edge:helper",
                "sha256:helper",
                "current call edge binds this helper to one behavior",
            ),
        )
    owner_ids = tuple(block.owner_id for block in blocks)
    if node_dispositions is None:
        node_dispositions = (
            ProjectTestNodeDisposition(
                "test:save",
                (
                    "behavior_coverage"
                    if len(set(owner_ids)) == 1
                    else "cross_owner_integration"
                ),
                owner_ids,
                tuple(edge.coverage_id for edge in edges),
                "exact real test-member coverage",
            ),
        )
    return review_behavior_blueprint(
        inventory_fingerprint="sha256:inventory",
        required_behavior_surface_ids=(
            required_surfaces
            if required_surfaces is not None
            else tuple(block.implementation_surface_id for block in blocks)
        ),
        supporting_surface_ids=("surface:helper",) if relations else (),
        contracts=blocks,
        portable_bindings=(
            portable_bindings
            if portable_bindings is not None
            else tuple(portable(block) for block in blocks)
        ),
        case_contracts=(case_contracts if case_contracts is not None else all_cases),
        supporting_relations=relations,
        coverage_edges=edges,
        coverage_execution_evidence=executions,
        test_node_dispositions=node_dispositions,
        required_test_node_ids=("test:save",),
        semantic_specs=(
            semantic_references
            if semantic_references is not None
            else (semantic_spec(blocks),)
        ),
        oracles=(
            oracle_references
            if oracle_references is not None
            else (oracle_reference(blocks),)
        ),
        intent_inventory=(intent_inventory_value or intent_inventory()),
        implementation_source_fingerprints=(
            observed_source_fingerprints
            if observed_source_fingerprints is not None
            else {
                block.implementation_surface_id: block.source_fingerprint
                for block in blocks
            }
        ),
        implementation_owner_ids=(
            observed_owner_ids
            if observed_owner_ids is not None
            else {
                block.implementation_surface_id: block.owner_id for block in blocks
            }
        ),
        path_quality_bindings=(
            path_quality_bindings
            if path_quality_bindings is not None
            else tuple(
                path_quality_binding(block)
                for block in {
                    row.model_element_id: row for row in blocks
                }.values()
            )
        ),
        expected_path_quality_currentness_id=(
            expected_path_quality_currentness_id
        ),
        test_nodes=(node,),
        planned_checker_fingerprints=(
            planned_checker_fingerprints
            if planned_checker_fingerprints is not None
            else planned_checkers
        ),
        expected_portable_fingerprints={"portable-model:save": "sha256:portable"},
        expected_portable_members=expected_portable_members,
        supporting_surface_fingerprints=(
            {"surface:helper": "sha256:helper"} if relations else {}
        ),
        supporting_surface_owner_block_ids=(
            supporting_owner_blocks
            if supporting_owner_blocks is not None
            else {
                relation.supporting_surface_id: relation.behavior_block_id
                for relation in relations
            }
        ),
        evidence_receipts=evidence_receipts,
        receipt_verification_results=receipt_verification_results,
        validation_owner_contracts=validation_owner_contracts,
    )


def test_real_test_edge_and_not_run_execution_close_static_design() -> None:
    result = review()

    assert result.complete
    assert result.pre_code_status == "ready"
    assert result.executed_evidence_status == "not_run"
    assert result.coverage_edges[0].oracle_member_id.startswith("checker-design:")
    assert result.coverage_execution_evidence[0].disposition == "not_run"


def test_path_quality_is_exact_current_and_observed_before_readiness() -> None:
    block = contract()

    missing = review(path_quality_bindings=())
    assert missing.pre_code_status == "blocked"
    assert "path_quality_binding_missing" in {
        row.code for row in missing.findings
    }

    stale_currentness = review(
        path_quality_bindings=(
            path_quality_binding(block, currentness_id="revision:older"),
        )
    )
    assert stale_currentness.pre_code_status == "stale"
    assert "path_quality_currentness_stale" in {
        row.code for row in stale_currentness.findings
    }

    stale_model = review(
        (replace(block, model_fingerprint=_fp("model:save:changed")),),
        path_quality_bindings=(path_quality_binding(block),),
    )
    assert "path_quality_model_fingerprint_stale" in {
        row.code for row in stale_model.findings
    }

    unresolved = review(
        path_quality_bindings=(
            path_quality_binding(
                block,
                conclusion="unresolved",
                unresolved_ids=("missing_necessity_witness:state:retry",),
            ),
        )
    )
    assert unresolved.pre_code_status == "blocked"
    assert "path_quality_unresolved" in {
        row.code for row in unresolved.findings
    }

    normative = review(
        path_quality_bindings=(
            path_quality_binding(block, subject_lane="normative_target"),
        )
    )
    assert "path_quality_normative_only" in {
        row.code for row in normative.findings
    }

    unchanged = review(
        path_quality_bindings=(
            path_quality_binding(block, change_kind="unchanged"),
        )
    )
    assert unchanged.complete
    assert unchanged.path_quality_bindings[0].change_kind == "unchanged"


def test_path_quality_compact_result_cannot_survive_subject_or_reuse_drift() -> None:
    block = contract()
    binding = path_quality_binding(block)
    changed_provider_subject = replace(
        binding.subject,
        provider_fingerprint=_fp("provider:changed"),
    )
    with pytest.raises(
        TargetSystemBlueprintError,
        match="another subject",
    ):
        replace(binding, subject=changed_provider_subject)

    unchanged = path_quality_binding(block, change_kind="unchanged")
    with pytest.raises(
        TargetSystemBlueprintError,
        match="not exact-current",
    ):
        replace(
            unchanged,
            affected_topology_currentness_id="revision:older",
        )

    payload = binding.to_dict()
    assert payload["compact_current_fingerprint"]
    assert payload["detail_evidence_fingerprint"] == (
        binding.result.detail_evidence_fingerprint
    )
    tampered = {
        **payload,
        "detail_evidence_fingerprint": _fp("tampered-detail"),
    }
    with pytest.raises(
        TargetSystemBlueprintError,
        match="projection is stale",
    ):
        ModelPathQualityBlueprintBinding.from_dict(tampered)


def test_behavior_denominator_is_compared_in_both_directions() -> None:
    observed = contract("surface:observed")
    declared_only = contract("surface:declared-only")

    result = review(
        (observed, declared_only),
        required_surfaces=(observed.implementation_surface_id,),
        relations=(),
        observed_source_fingerprints={
            observed.implementation_surface_id: observed.source_fingerprint
        },
        observed_owner_ids={observed.implementation_surface_id: observed.owner_id},
    )

    assert "behavior_contract_surface_unobserved" in {
        finding.code for finding in result.findings
    }
    shrunk = review(
        (observed,),
        required_surfaces=(
            observed.implementation_surface_id,
            declared_only.implementation_surface_id,
        ),
        relations=(),
    )
    assert "behavior_contract_missing" in {
        finding.code for finding in shrunk.findings
    }


def test_same_shape_boundary_operator_change_breaks_frozen_semantic_identity() -> None:
    block = contract()
    accepted_fingerprint = fingerprint_value({"boundary": "score >= threshold"})
    changed_fingerprint = fingerprint_value({"boundary": "score > threshold"})
    _case_rows, edges, _planned = exact_design((block,))
    frozen_edges = tuple(
        replace(edge, semantic_content_fingerprint=accepted_fingerprint)
        for edge in edges
    )

    accepted = review(
        (block,),
        edges=frozen_edges,
        semantic_references=(
            semantic_spec(
                (block,), source_content_fingerprint=accepted_fingerprint
            ),
        ),
    )
    assert accepted.pre_code_status == "ready"

    changed = review(
        (block,),
        edges=frozen_edges,
        semantic_references=(
            semantic_spec(
                (block,), source_content_fingerprint=changed_fingerprint
            ),
        ),
    )
    assert "coverage_semantic_content_mismatch" in {
        finding.code for finding in changed.findings
    }


def test_intent_semantic_and_implementation_lineage_uses_exact_identities() -> None:
    block = replace(contract(), intent_contribution_ids=("intent:save",))
    contribution = ProjectIntentContribution(
        contribution_id="intent:save",
        source_kind="explicit_change_objective",
        source_id="objective:save-boundary",
        source_owner_id="owner:product-intent",
        source_fingerprint="sha256:intent-source",
        expectation_id="expectation:save-boundary",
        expectation_fingerprint="sha256:intent-expectation",
        disposition="accepted",
        target_ids=(
            block.behavior_block_id,
            block.model_element_id,
            block.implementation_surface_id,
        ),
        rationale="the exact accepted save boundary",
    )
    inventory = ProjectIntentInventory(
        inventory_id="intent:bound",
        subject_revision="sha256:revision",
        observed_subject_revision="sha256:revision",
        contributions=(contribution,),
        source_authorities=(
            IntentSourceAuthority(
                source_kind=contribution.source_kind,
                source_id=contribution.source_id,
                source_owner_id=contribution.source_owner_id,
                subject_revision="sha256:revision",
                current_source_fingerprint=contribution.source_fingerprint,
                expectation_id=contribution.expectation_id,
                current_expectation_fingerprint=(
                    contribution.expectation_fingerprint
                ),
                target_ids=contribution.target_ids,
                provider_id="provider:intent",
                capability_id="intent_lineage",
                payload_id="intent_lineage",
            ),
        ),
        authority_provider_capabilities=(
            ("provider:intent", "intent_lineage"),
        ),
        required_model_target_ids=(block.model_element_id,),
    )
    bound_semantic = replace(
        semantic_spec((block,)),
        provenance_fingerprints=(
            (contribution.source_id, contribution.source_fingerprint),
        ),
    )
    bound = review(
        (block,),
        semantic_references=(bound_semantic,),
        intent_inventory_value=inventory,
    )
    assert bound.pre_code_status == "ready"

    wrong_lineage = review(
        (block,),
        semantic_references=(
            replace(
                bound_semantic,
                provenance_fingerprints=(
                    (contribution.source_id, "sha256:another-intent-source"),
                ),
            ),
        ),
        intent_inventory_value=inventory,
    )
    assert "semantic_intent_lineage_missing" in {
        finding.code for finding in wrong_lineage.findings
    }

    circular_intent = replace(
        contribution,
        source_fingerprint=block.source_fingerprint,
        source_owner_id=block.owner_id,
    )
    circular_authority = replace(
        inventory.source_authorities[0],
        source_owner_id=circular_intent.source_owner_id,
        current_source_fingerprint=circular_intent.source_fingerprint,
    )
    circular_inventory = replace(
        inventory,
        contributions=(circular_intent,),
        source_authorities=(circular_authority,),
    )
    circular = review(
        (block,),
        semantic_references=(
            replace(
                bound_semantic,
                provenance_fingerprints=(
                    (circular_intent.source_id, circular_intent.source_fingerprint),
                ),
            ),
        ),
        intent_inventory_value=circular_inventory,
    )
    assert "behavior_intent_source_not_independent" in {
        finding.code for finding in circular.findings
    }


def test_intent_authority_denominator_blocks_stale_provider_and_conflict() -> None:
    block = replace(contract(), intent_contribution_ids=("intent:save",))
    contribution = ProjectIntentContribution(
        contribution_id="intent:save",
        source_kind="explicit_change_objective",
        source_id="objective:save-boundary",
        source_owner_id="owner:product-intent",
        source_fingerprint="sha256:intent-source",
        expectation_id="expectation:save-boundary",
        expectation_fingerprint="sha256:intent-expectation",
        disposition="accepted",
        target_ids=(block.behavior_block_id, block.model_element_id),
        rationale="preserve the exact accepted save expectation",
    )
    authority = IntentSourceAuthority(
        source_kind=contribution.source_kind,
        source_id=contribution.source_id,
        source_owner_id=contribution.source_owner_id,
        subject_revision="sha256:revision",
        current_source_fingerprint=contribution.source_fingerprint,
        expectation_id=contribution.expectation_id,
        current_expectation_fingerprint=contribution.expectation_fingerprint,
        target_ids=contribution.target_ids,
        provider_id="provider:intent",
        capability_id="intent_lineage",
        payload_id="intent_lineage",
    )
    inventory = ProjectIntentInventory(
        inventory_id="intent:strict",
        subject_revision="sha256:revision",
        observed_subject_revision="sha256:revision",
        contributions=(contribution,),
        source_authorities=(authority,),
        authority_provider_capabilities=(
            ("provider:intent", "intent_lineage"),
        ),
        required_model_target_ids=(block.model_element_id,),
    )

    assert inventory.complete
    baseline_review_fingerprint = inventory.canonical_review_fingerprint
    assert baseline_review_fingerprint.startswith("sha256:")

    variants = (
        (
            replace(inventory, source_authorities=()),
            "intent_source_authority_missing",
        ),
        (
            replace(inventory, observed_subject_revision="sha256:new-revision"),
            "intent_inventory_subject_revision_mismatch",
        ),
        (
            replace(
                inventory,
                source_authorities=(replace(authority, status="stale"),),
            ),
            "intent_source_authority_not_current",
        ),
        (
            replace(
                inventory,
                source_authorities=(
                    replace(authority, current_source_fingerprint="sha256:old-source"),
                ),
            ),
            "intent_source_fingerprint_stale",
        ),
        (
            replace(
                inventory,
                authority_provider_capabilities=(
                    ("provider:another", "intent_lineage"),
                ),
            ),
            "intent_authority_provider_mismatch",
        ),
        (
            replace(inventory, contributions=()),
            "intent_source_unmodeled",
        ),
    )
    for variant, expected_code in variants:
        assert variant.canonical_review_fingerprint != baseline_review_fingerprint
        result = review(
            (block,),
            intent_inventory_value=variant,
            semantic_references=(
                replace(
                    semantic_spec((block,)),
                    provenance_fingerprints=(
                        (contribution.source_id, contribution.source_fingerprint),
                    ),
                ),
            ),
        )
        assert result.pre_code_status in {"blocked", "stale", "incomplete"}
        assert expected_code in {finding.code for finding in result.findings}

    conflicting = replace(
        contribution,
        contribution_id="intent:save-conflict",
        source_id="objective:save-conflict",
        source_owner_id="owner:conflicting-intent",
        expectation_fingerprint="sha256:conflicting-expectation",
    )
    conflicting_authority = replace(
        authority,
        source_id=conflicting.source_id,
        source_owner_id=conflicting.source_owner_id,
        current_source_fingerprint=conflicting.source_fingerprint,
        current_expectation_fingerprint=conflicting.expectation_fingerprint,
    )
    conflict_inventory = replace(
        inventory,
        contributions=(contribution, conflicting),
        source_authorities=(authority, conflicting_authority),
    )
    assert "intent_expectation_conflict" in {
        finding.code for finding in conflict_inventory.findings
    }
    assert not conflict_inventory.complete


def test_effective_intent_requires_the_complete_independent_model_denominator() -> None:
    inventory = intent_inventory()

    missing = replace(
        inventory,
        required_model_target_ids=("model:save", "model:delete"),
    )
    assert not missing.complete
    assert "intent_model_target_coverage_missing" in {
        finding.code for finding in missing.findings
    }

    contribution = replace(
        inventory.contributions[0],
        target_ids=("model:save", "model-obligation:foreign"),
    )
    authority = replace(
        inventory.source_authorities[0],
        target_ids=contribution.target_ids,
    )
    foreign = replace(
        inventory,
        contributions=(contribution,),
        source_authorities=(authority,),
    )
    assert not foreign.complete
    assert "intent_model_target_unobserved" in {
        finding.code for finding in foreign.findings
    }

    omitted_denominator = replace(inventory, required_model_target_ids=())
    behavior = review(
        (contract(),),
        intent_inventory_value=omitted_denominator,
    )
    assert "intent_model_target_denominator_missing_behavior_owner" in {
        finding.code for finding in behavior.findings
    }


def test_every_behavior_consumes_effective_intent_through_its_exact_model_owner() -> None:
    empty = review((replace(contract(), intent_contribution_ids=()),))
    assert "behavior_intent_coverage_missing" in {
        finding.code for finding in empty.findings
    }

    inventory = intent_inventory()
    foreign_contribution = replace(
        inventory.contributions[0],
        target_ids=("model:other",),
    )
    foreign_authority = replace(
        inventory.source_authorities[0],
        target_ids=foreign_contribution.target_ids,
    )
    foreign_inventory = replace(
        inventory,
        contributions=(foreign_contribution,),
        source_authorities=(foreign_authority,),
        required_model_target_ids=("model:other",),
    )
    cross_owner = review(
        (contract(),),
        intent_inventory_value=foreign_inventory,
    )
    assert "behavior_intent_owner_mismatch" in {
        finding.code for finding in cross_owner.findings
    }

    root_contribution = replace(
        inventory.contributions[0],
        target_ids=("root:target-system",),
    )
    root_authority = replace(
        inventory.source_authorities[0],
        target_ids=root_contribution.target_ids,
    )
    root_inventory = replace(
        inventory,
        contributions=(root_contribution,),
        source_authorities=(root_authority,),
        required_model_target_ids=("root:target-system",),
    )
    root_fallback = review(
        (contract(),),
        intent_inventory_value=root_inventory,
    )
    assert "behavior_intent_root_fallback" in {
        finding.code for finding in root_fallback.findings
    }

def test_same_shape_outcome_owner_and_state_effect_swaps_are_visible() -> None:
    block = contract()
    exact_cases, edges, _planned = exact_design((block,))
    changed_outcome = replace(
        exact_cases[0], expected_output=(("return", "saved:another-owner"),)
    )
    outcome_result = review(
        (block,),
        edges=edges,
        case_contracts=(changed_outcome, *exact_cases[1:]),
    )
    assert "coverage_case_content_mismatch" in {
        finding.code for finding in outcome_result.findings
    }

    changed_state_effect = replace(
        exact_cases[1],
        expected_state=(("status", "wrong"),),
        expected_effects=("effect:wrong-owner",),
    )
    state_effect_result = review(
        (block,),
        edges=edges,
        case_contracts=(exact_cases[0], changed_state_effect, exact_cases[2]),
    )
    assert "coverage_case_content_mismatch" in {
        finding.code for finding in state_effect_result.findings
    }

    swapped_owner = replace(block, owner_id="owner:other")
    owner_result = review((swapped_owner,), edges=edges)
    assert "coverage_behavior_owner_mismatch" in {
        finding.code for finding in owner_result.findings
    }


@pytest.mark.parametrize("disposition", ("not_run", "not_applicable"))
def test_not_run_skip_or_xfail_dispositions_never_become_executed_pass(
    disposition: str,
) -> None:
    block = contract()
    _cases, edges, _planned = exact_design((block,))
    result = review(
        (block,),
        edges=edges,
        executions=tuple(
            CoverageExecutionEvidence(
                edge.coverage_id,
                "owner:test",
                disposition,
            )
            for edge in edges
        ),
    )

    assert result.pre_code_status == "ready"
    assert result.executed_evidence_status == "not_run"


def test_zero_collection_and_skipped_leaf_receipts_cannot_close_execution() -> None:
    block = contract()
    _cases, edges, _planned = exact_design((block,))
    owner_contract, collected_receipt, collected_verification = execution_bundle(edges)
    zero_receipt = replace(
        collected_receipt, covered_obligations=("collection:zero-matching-members",)
    )
    zero_verification = replace(
        collected_verification,
        receipt_fingerprint=zero_receipt.fingerprint,
        satisfied_obligations=("collection:zero-matching-members",),
    )
    zero = review(
        (block,),
        edges=edges,
        executions=tuple(
            CoverageExecutionEvidence(
                edge.coverage_id,
                owner_contract.owner_id,
                "pass",
                zero_receipt.receipt_id,
                zero_receipt.fingerprint,
            )
            for edge in edges
        ),
        evidence_receipts=(zero_receipt,),
        receipt_verification_results=(zero_verification,),
        validation_owner_contracts=(owner_contract,),
    )
    assert zero.executed_evidence_status == "blocked"
    assert {
        "coverage_execution_receipt_member_missing",
        "coverage_execution_verification_member_missing",
    }.issubset({finding.code for finding in zero.findings})

    full_owner, full_receipt, full_verification = execution_bundle(edges)
    skipped_receipt = replace(
        full_receipt,
        skipped_checks=("pytest:skipped-or-xfailed-required-member",),
    )
    skipped_verification = replace(
        full_verification,
        receipt_fingerprint=skipped_receipt.fingerprint,
    )
    skipped = review(
        (block,),
        edges=edges,
        executions=tuple(
            CoverageExecutionEvidence(
                edge.coverage_id,
                full_owner.owner_id,
                "pass",
                skipped_receipt.receipt_id,
                skipped_receipt.fingerprint,
            )
            for edge in edges
        ),
        evidence_receipts=(skipped_receipt,),
        receipt_verification_results=(skipped_verification,),
        validation_owner_contracts=(full_owner,),
    )
    assert skipped.executed_evidence_status == "blocked"
    assert "coverage_execution_receipt_not_terminal_pass" in {
        finding.code for finding in skipped.findings
    }


def test_exact_current_leaf_receipt_closes_executed_evidence() -> None:
    block = contract()
    _cases, edges, _planned = exact_design((block,))
    owner_contract, receipt, verification = execution_bundle(edges)
    result = review(
        (block,),
        edges=edges,
        executions=tuple(
            CoverageExecutionEvidence(
                edge.coverage_id,
                owner_contract.owner_id,
                "pass",
                receipt.receipt_id,
                receipt.fingerprint,
            )
            for edge in edges
        ),
        evidence_receipts=(receipt,),
        receipt_verification_results=(verification,),
        validation_owner_contracts=(owner_contract,),
    )

    assert result.pre_code_status == "ready"
    assert result.executed_evidence_status == "passed"


def test_validation_parent_receipt_cannot_impersonate_leaf_coverage() -> None:
    block = contract()
    _cases, edges, _planned = exact_design((block,))
    owner_contract, receipt, verification = execution_bundle(
        edges,
        receipt_id="receipt:validation-parent:full",
        subject_kind="validation_parent",
        subject_id="validation-parent:full",
        producer_id="validation-parent:full",
    )
    result = review(
        (block,),
        edges=edges,
        executions=tuple(
            CoverageExecutionEvidence(
                edge.coverage_id,
                owner_contract.owner_id,
                "pass",
                receipt.receipt_id,
                receipt.fingerprint,
            )
            for edge in edges
        ),
        evidence_receipts=(receipt,),
        receipt_verification_results=(verification,),
        validation_owner_contracts=(owner_contract,),
    )

    assert result.pre_code_status == "ready"
    assert result.executed_evidence_status == "blocked"
    assert "coverage_execution_parent_receipt_not_leaf" in {
        finding.code for finding in result.findings
    }


def test_one_receipt_cannot_be_reused_across_execution_owners() -> None:
    surfaces = ("surface:first", "surface:second")
    first = replace(
        contract(surfaces[0], shared_surfaces=surfaces),
        owner_id="owner:first",
        owner_contract_id="contract:first",
        model_element_id="model:first",
    )
    second = replace(
        contract(surfaces[1], shared_surfaces=surfaces),
        owner_id="owner:second",
        owner_contract_id="contract:second",
        model_element_id="model:second",
    )
    _cases, edges, _planned = exact_design((first, second))
    first_edges = tuple(
        edge for edge in edges if edge.behavior_block_id == first.behavior_block_id
    )
    second_edges = tuple(
        edge for edge in edges if edge.behavior_block_id == second.behavior_block_id
    )
    first_contract, receipt, verification = execution_bundle(
        edges,
        owner_id="execution:first",
    )
    second_contract = ValidationOwnerContract(
        owner_id="execution:second",
        command=first_contract.command,
        input_patterns=first_contract.input_patterns,
        obligation_ids=tuple(edge.coverage_id for edge in second_edges),
    )
    result = review(
        (first, second),
        edges=edges,
        relations=(),
        executions=tuple(
            CoverageExecutionEvidence(
                edge.coverage_id,
                (
                    first_contract.owner_id
                    if edge in first_edges
                    else second_contract.owner_id
                ),
                "pass",
                receipt.receipt_id,
                receipt.fingerprint,
            )
            for edge in edges
        ),
        evidence_receipts=(receipt,),
        receipt_verification_results=(verification,),
        validation_owner_contracts=(first_contract, second_contract),
    )

    assert result.executed_evidence_status == "blocked"
    assert "coverage_execution_receipt_reused_across_owners" in {
        finding.code for finding in result.findings
    }


def test_test_node_disposition_must_name_the_edge_node_and_exact_owner() -> None:
    block = contract()
    _cases, edges, _planned = exact_design((block,))
    result = review(
        (block,),
        edges=edges,
        node_dispositions=(
            ProjectTestNodeDisposition(
                "test:foreign",
                "behavior_coverage",
                ("owner:foreign",),
                tuple(edge.coverage_id for edge in edges),
                "deliberately wrong node and owner",
            ),
        ),
    )

    codes = {finding.code for finding in result.findings}
    assert "test_disposition_node_mismatch" in codes
    assert "test_disposition_owner_mismatch" in codes


def test_behavior_report_fingerprint_is_computed_once_for_immutable_report() -> None:
    result = review()

    with mock.patch(
        "flowguard.software_blueprint_readiness._fingerprint",
        wraps=blueprint_readiness._fingerprint,
    ) as fingerprint:
        first = result.fingerprint
        second = result.fingerprint

    assert first == second
    assert fingerprint.call_count == 1


def test_canonical_fingerprint_streams_without_materializing_full_json() -> None:
    payload = {
        "z": [{"unicode": "蓝图", "value": index} for index in range(100)],
        "a": {"nested": True},
    }
    expected_size = len(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )

    with mock.patch(
        "flowguard.software_blueprint_readiness.json.dumps",
        side_effect=AssertionError("full JSON materialization is forbidden"),
    ):
        fingerprint, logical_bytes = (
            blueprint_readiness._canonical_fingerprint_and_size(payload)
        )

    assert fingerprint == fingerprint_value(payload)
    assert logical_bytes == expected_size


def test_portable_binding_must_preserve_the_protected_failure_boundary() -> None:
    block = contract()
    result = review(
        (block,),
        portable_bindings=(replace(portable(block), protected_failure_ids=()),),
    )

    assert "portable_failure_boundary_mismatch" in {
        finding.code for finding in result.findings
    }


def test_sibling_blocks_cannot_borrow_case_design_or_coverage() -> None:
    first = contract("surface:save")
    second = contract("surface:load")
    all_cases, all_edges, _planned = exact_design((first, second))
    missing_second_boundary = tuple(
        case
        for case in all_cases
        if not (
            case.behavior_block_id == second.behavior_block_id
            and case.case_kind == "boundary"
        )
    )
    missing = review(
        (first, second),
        case_contracts=missing_second_boundary,
        relations=(),
    )
    assert "behavior_case_design_missing" in {
        finding.code for finding in missing.findings
    }

    second_edge = next(
        edge
        for edge in all_edges
        if edge.behavior_block_id == second.behavior_block_id
    )
    cross_block_edge = replace(
        second_edge,
        coverage_id=f"{second_edge.coverage_id}:cross-block",
        behavior_block_id=first.behavior_block_id,
        implementation_surface_id=first.implementation_surface_id,
        implementation_content_fingerprint=first.source_fingerprint,
    )
    crossed = review(
        (first, second),
        edges=(cross_block_edge,),
        relations=(),
    )
    assert "coverage_case_missing" in {
        finding.code for finding in crossed.findings
    }


def test_sibling_portable_member_union_must_exactly_close_the_model_catalog() -> None:
    first = contract("surface:first")
    second = contract("surface:second")
    first_binding = replace(
        portable(first),
        input_field_mappings=(("first", "input:first"),),
        output_field_mappings=(("return", "output:first"),),
    )
    second_binding = replace(
        portable(second),
        input_field_mappings=(("second", "input:second"),),
        output_field_mappings=(("return", "output:second"),),
    )
    exact_catalog = {
        "portable-model:save": {
            "transition_ids": ("transition:save",),
            "property_ids": ("property:save",),
            "invariant_ids": ("invariant:save",),
            "input_field_ids": ("input:first", "input:second"),
            "output_field_ids": ("output:first", "output:second"),
            "state_field_ids": (),
            "assumption_ids": ("assumption:accepted-input",),
            "guarantee_ids": ("guarantee:saved-output",),
            "protected_failure_ids": ("failure:rejected",),
        }
    }

    exact = review(
        (first, second),
        relations=(),
        portable_bindings=(first_binding, second_binding),
        expected_portable_members=exact_catalog,
    )
    assert exact.pre_code_status == "ready"

    missing_catalog = {
        "portable-model:save": {
            **exact_catalog["portable-model:save"],
            "input_field_ids": (
                "input:first",
                "input:second",
                "input:required-but-unbound",
            ),
        }
    }
    missing = review(
        (first, second),
        relations=(),
        portable_bindings=(first_binding, second_binding),
        expected_portable_members=missing_catalog,
    )
    assert "portable_member_unbound" in {
        finding.code for finding in missing.findings
    }

    missing_failure_catalog = {
        "portable-model:save": {
            **exact_catalog["portable-model:save"],
            "protected_failure_ids": (
                "failure:rejected",
                "failure:required-but-unbound",
            ),
        }
    }
    missing_failure = review(
        (first, second),
        relations=(),
        portable_bindings=(first_binding, second_binding),
        expected_portable_members=missing_failure_catalog,
    )
    assert "portable_member_unbound" in {
        finding.code for finding in missing_failure.findings
    }

    unknown = review(
        (first, second),
        relations=(),
        portable_bindings=(
            first_binding,
            replace(
                second_binding,
                input_field_mappings=(
                    *second_binding.input_field_mappings,
                    ("invented", "input:invented"),
                ),
            ),
        ),
        expected_portable_members=exact_catalog,
    )
    assert "portable_member_unknown" in {
        finding.code for finding in unknown.findings
    }

    unknown_failure = review(
        (first, second),
        relations=(),
        portable_bindings=(
            first_binding,
            replace(
                second_binding,
                protected_failure_ids=(
                    *second_binding.protected_failure_ids,
                    "failure:invented",
                ),
            ),
        ),
        expected_portable_members=exact_catalog,
    )
    assert "portable_member_unknown" in {
        finding.code for finding in unknown_failure.findings
    }


def test_sparse_surface_failure_edges_materialize_exact_case_and_coverage_counts() -> None:
    def scaled_counts(surface_count: int, failure_count: int) -> tuple[int, int]:
        blocks: list[BehaviorBlockContract] = []
        bindings: list[PortableBehaviorBinding] = []
        materialized_cases: list[BehaviorCaseContract] = []
        edges: list[BehaviorCoverageEdge] = []
        planned: dict[str, str] = {}
        for index in range(surface_count):
            failure_ids = (
                tuple(
                    f"failure:scaled:{failure_index:03d}"
                    for failure_index in range(failure_count)
                )
                if index == 0
                else ()
            )
            block = replace(
                contract(f"surface:scaled:{index:03d}"),
                protected_failure_ids=failure_ids,
            )
            binding = replace(
                portable(block),
                protected_failure_ids=failure_ids,
            )
            blocks.append(block)
            bindings.append(binding)
            source_cases = list(cases(block)[:2])
            bad_template = cases(block)[2]
            source_cases.extend(
                replace(
                    bad_template,
                    case_id=(
                        f"case:{block.behavior_block_id}:bad:"
                        f"{failure_index:03d}"
                    ),
                    expected_errors=(failure_id,),
                    protected_failure_ids=(failure_id,),
                )
                for failure_index, failure_id in enumerate(failure_ids)
            )
            for source_case in source_cases:
                checker_id = f"checker-design:{source_case.case_id}"
                checker_fingerprint = fingerprint_value(
                    {"case": source_case.to_dict(), "checker_id": checker_id}
                )
                planned[checker_id] = checker_fingerprint
                exact_case = replace(
                    source_case,
                    case_evidence_id=checker_id,
                    case_evidence_fingerprint=checker_fingerprint,
                    parameter_case_id=source_case.case_id,
                )
                materialized_cases.append(exact_case)
                for dimension in BEHAVIOR_CASE_DIMENSIONS[exact_case.case_kind]:
                    member_id = f"{checker_id}:{dimension}"
                    member_fingerprint = fingerprint_value(
                        {
                            "case_evidence_fingerprint": checker_fingerprint,
                            "dimension": dimension,
                        }
                    )
                    planned[member_id] = member_fingerprint
                    edges.append(
                        BehaviorCoverageEdge(
                            coverage_id=(
                                f"coverage:{block.behavior_block_id}:"
                                f"{exact_case.case_id}:{dimension}"
                            ),
                            behavior_block_id=block.behavior_block_id,
                            implementation_surface_id=(
                                block.implementation_surface_id
                            ),
                            model_obligation_id=block.model_element_id,
                            semantic_spec_id="semantic:save",
                            semantic_content_fingerprint=(
                                "sha256:semantic-content"
                            ),
                            owner_contract_id=block.owner_contract_id,
                            behavior_owner_id=block.owner_id,
                            implementation_content_fingerprint=(
                                block.source_fingerprint
                            ),
                            test_node_id="test:save",
                            oracle_member_id=member_id,
                            oracle_member_fingerprint=member_fingerprint,
                            case_id=exact_case.case_id,
                            case_content_fingerprint=(
                                exact_case.content_fingerprint
                            ),
                            covered_dimensions=(dimension,),
                            evidence_role="planned_checker",
                            oracle_id="oracle:save",
                            oracle_content_fingerprint="sha256:oracle-content",
                        )
                    )

        report = review(
            tuple(blocks),
            relations=(),
            portable_bindings=tuple(bindings),
            case_contracts=tuple(materialized_cases),
            edges=tuple(edges),
            planned_checker_fingerprints=planned,
        )
        assert report.pre_code_status == "ready", [
            finding.to_dict() for finding in report.findings
        ]
        return len(report.case_contracts), len(report.coverage_edges)

    for surface_count, failure_count in ((12, 1), (24, 2), (48, 4)):
        case_count, coverage_count = scaled_counts(
            surface_count,
            failure_count,
        )
        expected_cases = 2 * surface_count + failure_count
        assert case_count == expected_cases
        assert coverage_count == 6 * expected_cases


def test_placeholder_or_cross_test_member_cannot_close_coverage() -> None:
    block = contract()
    missing = review(edges=(coverage(block, member_id="placeholder:assertion"),))
    assert "coverage_oracle_member_missing" in {row.code for row in missing.findings}

    cross_node = review(edges=(coverage(block, test_node_id="test:other"),))
    assert {row.code for row in cross_node.findings} >= {
        "coverage_cross_test_member",
        "coverage_test_node_missing",
    }


def test_one_checker_cannot_claim_several_cases_or_dimensions() -> None:
    block = contract()
    broad = review(edges=(coverage(block),))
    assert "coverage_dimension_scope_ambiguous" in {
        row.code for row in broad.findings
    }

    good = replace(coverage(block), covered_dimensions=("input",))
    boundary = replace(
        good,
        coverage_id=f"{good.coverage_id}:boundary",
        case_id=f"case:{block.behavior_block_id}:boundary",
        covered_dimensions=("output",),
    )
    reused = review(edges=(good, boundary))
    assert "checker_scope_ambiguous" in {row.code for row in reused.findings}

    with pytest.raises(SoftwareBlueprintReadinessError, match="placeholder"):
        replace(
            cases(block)[0],
            expected_output=(("return", "owner-defined-valid-output"),),
        )

    stale_case = replace(
        cases(block)[0],
        case_evidence_fingerprint="sha256:stale",
    )
    stale = review_behavior_blueprint(
        inventory_fingerprint="sha256:inventory",
        required_behavior_surface_ids=(block.implementation_surface_id,),
        supporting_surface_ids=(),
        contracts=(block,),
        portable_bindings=(portable(block),),
        case_contracts=(stale_case,) + cases(block)[1:],
        supporting_relations=(),
        coverage_edges=(coverage(block),),
        coverage_execution_evidence=(
            CoverageExecutionEvidence(
                coverage(block).coverage_id,
                "owner:test",
                "not_run",
            ),
        ),
        test_node_dispositions=(
            ProjectTestNodeDisposition(
                "test:save",
                "behavior_coverage",
                ("owner:save",),
                (coverage(block).coverage_id,),
                "exact coverage",
            ),
        ),
        required_test_node_ids=("test:save",),
        semantic_specs=(semantic_spec((block,)),),
        oracles=(oracle_reference((block,)),),
        intent_inventory=intent_inventory(),
        implementation_source_fingerprints={
            block.implementation_surface_id: block.source_fingerprint
        },
        implementation_owner_ids={block.implementation_surface_id: block.owner_id},
        test_nodes=(
            TestNodeFixture(
                "test:save",
                (AssertionFixture("assertion:save", "sha256:assertion"),),
            ),
        ),
        expected_portable_fingerprints={"portable-model:save": "sha256:portable"},
    )
    assert "case_evidence_member_stale" in {row.code for row in stale.findings}


def test_planned_case_checker_identity_cannot_be_reused_across_siblings() -> None:
    first = contract("surface:first")
    second = contract("surface:second")
    exact_cases, _edges, _planned = exact_design((first, second))
    first_good = next(
        case
        for case in exact_cases
        if case.behavior_block_id == first.behavior_block_id
        and case.case_kind == "good"
    )
    second_good = next(
        case
        for case in exact_cases
        if case.behavior_block_id == second.behavior_block_id
        and case.case_kind == "good"
    )
    reused = tuple(
        (
            replace(
                case,
                case_evidence_id=first_good.case_evidence_id,
                case_evidence_fingerprint=first_good.case_evidence_fingerprint,
            )
            if case.case_id == second_good.case_id
            else case
        )
        for case in exact_cases
    )

    result = review((first, second), case_contracts=reused, relations=())

    assert "planned_case_checker_scope_ambiguous" in {
        finding.code for finding in result.findings
    }


def test_unaccepted_and_generic_copied_semantics_remain_incomplete() -> None:
    unaccepted = contract(accepted=False)
    result = review((unaccepted,))
    assert "behavior_contract_unaccepted" in {row.code for row in result.findings}

    first = contract("surface:first", shared_surfaces=("surface:first",))
    second = contract("surface:second", shared_surfaces=("surface:second",))
    copied = tuple(
        replace(
            dimension,
            semantics=dimension.semantics.replace("surface:second", "surface:first"),
        )
        for dimension in second.dimensions
    )
    second = replace(second, dimensions=copied)
    result = review((first, second), relations=())
    assert "generic_semantics_reused_across_blocks" in {
        row.code for row in result.findings
    }


def test_portable_binding_and_helper_edge_freshness_are_enforced() -> None:
    block = contract()
    result = review_behavior_blueprint(
        inventory_fingerprint="sha256:inventory",
        required_behavior_surface_ids=(block.implementation_surface_id,),
        supporting_surface_ids=("surface:helper",),
        contracts=(block,),
        portable_bindings=(
            replace(portable(block), portable_model_fingerprint="sha256:old"),
        ),
        case_contracts=cases(block),
        supporting_relations=(
            SupportingSurfaceRelation(
                "surface:helper",
                block.behavior_block_id,
                "calls",
                "edge:helper",
                "sha256:old-helper",
                "declared call edge",
            ),
        ),
        coverage_edges=(coverage(block),),
        coverage_execution_evidence=(
            CoverageExecutionEvidence(
                coverage(block).coverage_id,
                "owner:test",
                "not_run",
            ),
        ),
        test_node_dispositions=(
            ProjectTestNodeDisposition(
                "test:save",
                "behavior_coverage",
                ("owner:save",),
                (coverage(block).coverage_id,),
                "exact coverage",
            ),
        ),
        required_test_node_ids=("test:save",),
        semantic_specs=(semantic_spec((block,)),),
        oracles=(oracle_reference((block,)),),
        intent_inventory=intent_inventory(),
        implementation_source_fingerprints={
            block.implementation_surface_id: block.source_fingerprint
        },
        implementation_owner_ids={block.implementation_surface_id: block.owner_id},
        test_nodes=(
            TestNodeFixture(
                "test:save",
                (AssertionFixture("assertion:save", "sha256:assertion"),),
            ),
        ),
        expected_portable_fingerprints={"portable-model:save": "sha256:portable"},
        supporting_surface_fingerprints={"surface:helper": "sha256:helper"},
        supporting_surface_owner_block_ids={
            "surface:helper": block.behavior_block_id
        },
    )
    assert {row.code for row in result.findings} >= {
        "portable_behavior_binding_stale",
        "supporting_ownership_edge_stale",
    }


def test_supporting_relation_must_match_the_independent_exact_owner() -> None:
    first = contract("surface:first")
    second = contract("surface:second")
    relation = SupportingSurfaceRelation(
        "surface:helper",
        first.behavior_block_id,
        "delegates",
        "edge:helper",
        "sha256:helper",
        "the provider supplied one exact supporting owner",
    )

    result = review(
        (first, second),
        relations=(relation,),
        supporting_owner_blocks={
            "surface:helper": second.behavior_block_id,
        },
    )

    assert "supporting_owner_mismatch" in {
        row.code for row in result.findings
    }


def test_execution_receipt_rules_remain_separate_from_design() -> None:
    with pytest.raises(SoftwareBlueprintReadinessError, match="non-pass"):
        CoverageExecutionEvidence(
            "coverage:one",
            "owner:test",
            "not_run",
            "receipt:one",
            "sha256:receipt",
        )
    with pytest.raises(SoftwareBlueprintReadinessError, match="passing"):
        CoverageExecutionEvidence("coverage:one", "owner:test", "pass")


def test_delegated_assertion_helpers_require_current_terminal_acyclic_paths() -> None:
    block = contract()
    exact_cases, exact_edges, planned_checkers = exact_design((block,))
    helper_edge = replace(
        exact_edges[0],
        oracle_member_id="assert_saved",
        oracle_member_fingerprint="sha256:helper",
    )
    all_edges = (helper_edge, *exact_edges[1:])
    node = TestNodeFixture(
        "test:save",
        (AssertionFixture("assertion:save", "sha256:assertion"),),
        ("assert_saved",),
    )

    def delegated_review(helpers=(), expected=None, test_node=node):
        return review_behavior_blueprint(
            inventory_fingerprint="sha256:inventory",
            required_behavior_surface_ids=(block.implementation_surface_id,),
            supporting_surface_ids=(),
            contracts=(block,),
            portable_bindings=(portable(block),),
            case_contracts=exact_cases,
            supporting_relations=(),
            coverage_edges=all_edges,
            coverage_execution_evidence=tuple(
                CoverageExecutionEvidence(
                    edge.coverage_id,
                    "owner:test",
                    "not_run",
                )
                for edge in all_edges
            ),
            test_node_dispositions=(
                ProjectTestNodeDisposition(
                    "test:save",
                    "behavior_coverage",
                    ("owner:save",),
                    tuple(edge.coverage_id for edge in all_edges),
                    "delegated exact coverage",
                ),
            ),
            required_test_node_ids=("test:save",),
            semantic_specs=(semantic_spec((block,)),),
            oracles=(oracle_reference((block,)),),
            intent_inventory=intent_inventory(),
            implementation_source_fingerprints={
                block.implementation_surface_id: block.source_fingerprint
            },
            implementation_owner_ids={
                block.implementation_surface_id: block.owner_id
            },
            path_quality_bindings=(path_quality_binding(block),),
            expected_path_quality_currentness_id=CURRENT_PATH_QUALITY_ID,
            test_nodes=(test_node,),
            planned_checker_fingerprints=planned_checkers,
            delegated_assertion_helpers=helpers,
            delegated_helper_fingerprints=expected or {},
            expected_portable_fingerprints={
                "portable-model:save": "sha256:portable"
            },
        )

    helper = DelegatedAssertionHelper(
        "assert_saved",
        "test:save",
        "sha256:helper",
        ("assertion:save",),
    )
    assert delegated_review(
        (helper,), {"assert_saved": "sha256:helper"}
    ).complete

    direct_terminal_only = replace(
        helper,
        callee_member_ids=(),
        terminal_member_fingerprints=(
            ("delegated-terminal:assert_saved:1:0", "sha256:terminal"),
        ),
    )
    assert delegated_review(
        (direct_terminal_only,), {"assert_saved": "sha256:helper"}
    ).complete

    conflicting_direct_terminal = replace(
        direct_terminal_only,
        terminal_member_fingerprints=(("assertion:save", "sha256:changed"),),
    )
    conflict = delegated_review(
        (conflicting_direct_terminal,), {"assert_saved": "sha256:helper"}
    )
    assert not conflict.complete
    assert "delegated_assertion_terminal_stale" in {
        row.code for row in conflict.findings
    }

    unknown_branch = delegated_review(
        (
            replace(
                direct_terminal_only,
                callee_member_ids=("assert_missing",),
            ),
        ),
        {"assert_saved": "sha256:helper"},
    )
    assert not unknown_branch.complete
    assert "delegated_assertion_terminal_missing" in {
        row.code for row in unknown_branch.findings
    }

    stale = delegated_review(
        (helper,), {"assert_saved": "sha256:changed"}
    )
    assert "delegated_assertion_helper_stale" in {
        row.code for row in stale.findings
    }

    cycle = delegated_review(
        (
            replace(helper, callee_member_ids=("assert_other",)),
            DelegatedAssertionHelper(
                "assert_other",
                "test:save",
                "sha256:other",
                ("assert_saved",),
            ),
        )
    )
    assert "delegated_assertion_helper_cycle" in {
        row.code for row in cycle.findings
    }

    ambiguous = delegated_review(
        (
            replace(
                direct_terminal_only,
                helper_id="pkg.first::assert_saved",
                source_fingerprint="sha256:first-helper",
            ),
            replace(
                direct_terminal_only,
                helper_id="pkg.second::assert_saved",
                source_fingerprint="sha256:second-helper",
            ),
        )
    )
    assert not ambiguous.complete
    assert "ambiguous_delegated_assertion_helper" in {
        row.code for row in ambiguous.findings
    }

    unregistered = delegated_review((), test_node=node)
    assert "unregistered_assertion_helper" in {
        row.code for row in unregistered.findings
    }

    mock_terminal = delegated_review(
        (),
        test_node=replace(node, calls=("run.assert_called_once",)),
    )
    assert "unregistered_assertion_helper" not in {
        row.code for row in mock_terminal.findings
    }


def test_static_readiness_is_ready_with_design_only() -> None:
    behavior = review()
    shared = {"semantic:save": {"value": "declared"}}
    shared.update(
        {
            row.coverage_id: {"kind": "behavior_coverage_edge", **row.to_dict()}
            for row in behavior.coverage_edges
        }
    )
    shards = materialize_behavior_blueprint_shards(
        behavior, shared_objects=shared
    )
    projection = normalize_behavior_blueprint(
        blueprint_fingerprint="sha256:blueprint",
        behavior_report=behavior,
        shared_objects=shared,
        coverage_reference_shards=shards,
    )
    readiness = review_static_blueprint_readiness(
        blueprint_fingerprint="sha256:blueprint",
        behavior_report=behavior,
        resource_inventory=resource_inventory(),
        intent_inventory=intent_inventory(),
        topology_fingerprint="sha256:topology",
        normalized_projection_fingerprint=projection.fingerprint,
    )

    assert readiness.status == "ready"
    assert "empirical_reconstruction_status" not in readiness.to_dict()


def test_normalization_constructs_behavior_reference_once_and_preserves_output() -> None:
    behavior = review()
    shared = {
        row.coverage_id: {"kind": "behavior_coverage_edge", **row.to_dict()}
        for row in behavior.coverage_edges
    }
    shards = materialize_behavior_blueprint_shards(
        behavior, shared_objects=shared
    )
    expected = normalize_behavior_blueprint(
        blueprint_fingerprint="sha256:blueprint",
        behavior_report=behavior,
        shared_objects=shared,
        coverage_reference_shards=shards,
    )
    original = type(behavior).to_normalized_reference_dict

    with mock.patch.object(
        type(behavior),
        "to_normalized_reference_dict",
        autospec=True,
        side_effect=original,
    ) as normalized_reference:
        actual = normalize_behavior_blueprint(
            blueprint_fingerprint="sha256:blueprint",
            behavior_report=behavior,
            shared_objects=shared,
            coverage_reference_shards=shards,
        )

    assert normalized_reference.call_count == 1
    assert actual.to_dict() == expected.to_dict()
    assert actual.fingerprint == expected.fingerprint


def test_normalization_and_affected_loading_preserve_exact_objects() -> None:
    behavior = review()
    shared = {
        "semantic:save": {"kind": "semantic"},
        "oracle:save": {"kind": "oracle"},
        "portable:surface:save": {"kind": "portable"},
        "test:save": {"kind": "test"},
        "assertion:save": {"kind": "assertion"},
        "case:behavior:surface:save:good": {"kind": "case"},
        "unrelated": {"kind": "other"},
    }
    shared.update(
        {
            row.coverage_id: {"kind": "behavior_coverage_edge", **row.to_dict()}
            for row in behavior.coverage_edges
        }
    )
    shard_rows = materialize_behavior_blueprint_shards(
        behavior, shared_objects=shared, shard_size=1
    )
    projection = normalize_behavior_blueprint(
        blueprint_fingerprint="sha256:blueprint",
        behavior_report=behavior,
        shared_objects=shared,
        coverage_reference_shards=shard_rows,
        shard_size=1,
        source_projection={"legacy_repeated": [shared] * 20},
    )
    shards = dict(shard_rows)
    neighborhood = read_affected_blueprint(
        projection,
        affected_ids=("surface:save",),
        load_shard=shards.__getitem__,
        load_object=shared.__getitem__,
    )

    assert len(neighborhood.shard_ids) == 18
    assert all(
        shard_id.startswith("coverage:")
        for shard_id in neighborhood.shard_ids
    )
    assert "unrelated" not in dict(neighborhood.objects)
    assert {
        row.coverage_id for row in behavior.coverage_edges
    }.issubset(neighborhood.object_ids)
    assert all(
        set(payload)
        == {
            "schema_version",
            "kind",
            "shard_id",
            "coverage_ids",
            "referenced_object_ids",
        }
        for _shard_id, payload in neighborhood.shards
    )
    assert projection.logical_fingerprint

    affected_only = read_affected_blueprint(
        projection,
        affected_ids=("surface:save",),
        load_shard=shards.__getitem__,
        load_object={
            key: value for key, value in shared.items() if key != "unrelated"
        }.__getitem__,
    )
    assert affected_only.fingerprint == neighborhood.fingerprint

    stale = dict(shared)
    stale["semantic:save"] = {"kind": "changed"}
    with pytest.raises(AffectedBlueprintReadError, match="fingerprint mismatch"):
        read_affected_blueprint(
            projection,
            affected_ids=("surface:save",),
            load_shard=shards.__getitem__,
            load_object=stale.__getitem__,
        )


def test_normalization_requires_one_exact_coverage_object_owner_and_reference_shape() -> None:
    behavior = review()
    shared = {
        row.coverage_id: {"kind": "behavior_coverage_edge", **row.to_dict()}
        for row in behavior.coverage_edges
    }
    shards = materialize_behavior_blueprint_shards(
        behavior, shared_objects=shared, shard_size=4
    )

    missing = dict(shared)
    missing.pop(behavior.coverage_edges[0].coverage_id)
    with pytest.raises(
        SoftwareBlueprintReadinessError,
        match="denominator is not exact-current",
    ):
        materialize_behavior_blueprint_shards(
            behavior, shared_objects=missing, shard_size=4
        )

    extra = {
        **shared,
        "coverage:extra": {
            "kind": "behavior_coverage_edge",
            "coverage_id": "coverage:extra",
        },
    }
    with pytest.raises(
        SoftwareBlueprintReadinessError,
        match="denominator is not exact-current",
    ):
        materialize_behavior_blueprint_shards(
            behavior, shared_objects=extra, shard_size=4
        )

    changed = dict(shared)
    first_id = behavior.coverage_edges[0].coverage_id
    changed[first_id] = {**changed[first_id], "evidence_role": "changed"}
    with pytest.raises(
        SoftwareBlueprintReadinessError,
        match="not exact-current",
    ):
        materialize_behavior_blueprint_shards(
            behavior, shared_objects=changed, shard_size=4
        )

    wrong_shards = list(shards)
    wrong_id, wrong_payload = wrong_shards[0]
    wrong_shards[0] = (
        wrong_id,
        {**wrong_payload, "coverage_ids": list(reversed(wrong_payload["coverage_ids"]))},
    )
    with pytest.raises(
        SoftwareBlueprintReadinessError,
        match="reference shards are not exact-current",
    ):
        normalize_behavior_blueprint(
            blueprint_fingerprint="sha256:blueprint",
            behavior_report=behavior,
            shared_objects=shared,
            coverage_reference_shards=wrong_shards,
            shard_size=4,
        )

    legacy_full_payload_shards = list(shards)
    legacy_id, legacy_payload = legacy_full_payload_shards[0]
    legacy_full_payload_shards[0] = (
        legacy_id,
        {
            **legacy_payload,
            "coverage_edges": [
                shared[coverage_id]
                for coverage_id in legacy_payload["coverage_ids"]
            ],
        },
    )
    with pytest.raises(
        SoftwareBlueprintReadinessError,
        match="reference shards are not exact-current",
    ):
        normalize_behavior_blueprint(
            blueprint_fingerprint="sha256:blueprint",
            behavior_report=behavior,
            shared_objects=shared,
            coverage_reference_shards=legacy_full_payload_shards,
            shard_size=4,
        )


def test_normalized_projection_scales_linearly_and_affected_read_stays_bounded() -> None:
    measurements: list[tuple[int, int, int, int]] = []
    for block_count in (4, 8, 16):
        blocks = tuple(
            contract(f"surface:scale:{index:03d}")
            for index in range(block_count)
        )
        behavior = review(blocks, relations=())
        shared = {
            row.coverage_id: {
                "kind": "behavior_coverage_edge",
                **row.to_dict(),
            }
            for row in behavior.coverage_edges
        }
        shard_rows = materialize_behavior_blueprint_shards(
            behavior,
            shared_objects=shared,
            shard_size=18,
        )
        projection = normalize_behavior_blueprint(
            blueprint_fingerprint=f"sha256:scale:{block_count}",
            behavior_report=behavior,
            shared_objects=shared,
            coverage_reference_shards=shard_rows,
            shard_size=18,
        )
        affected = read_affected_blueprint(
            projection,
            affected_ids=(blocks[0].implementation_surface_id,),
            load_shard=dict(shard_rows).__getitem__,
            load_object=shared.__getitem__,
        )

        assert len(behavior.contracts) == block_count
        assert len(behavior.case_contracts) == 3 * block_count
        assert len(behavior.coverage_edges) == 18 * block_count
        assert len(shard_rows) == block_count
        assert len(projection.object_fingerprints) == 18 * block_count
        assert len(affected.shard_ids) == 1
        assert len(affected.object_ids) == 18
        assert len(
            json.dumps(affected.to_dict(), sort_keys=True).encode("utf-8")
        ) < 256 * 1024
        measurements.append(
            (
                len(behavior.coverage_edges),
                len(projection.object_fingerprints),
                projection.logical_bytes,
                projection.physical_bytes,
            )
        )

    one, two, four = measurements
    assert two[0] == one[0] * 2 and four[0] == one[0] * 4
    assert two[1] == one[1] * 2 and four[1] == one[1] * 4
    assert two[2] <= one[2] * 2.2
    assert four[2] <= one[2] * 4.4
    assert two[3] <= one[3] * 2.2
    assert four[3] <= one[3] * 4.4


@dataclass(frozen=True)
class CandidateSurface:
    surface_id: str = "surface:observed"
    path: str = "app.py"
    symbol: str = "save"
    content_fingerprint: str = "sha256:source"
    behavior_bearing: bool = True
    discovery_adapter_id: str = "provider:fake-observation"
    disposition: str = ""


@dataclass(frozen=True)
class CandidateInventory:
    inventory_fingerprint: str = "sha256:inventory"
    surfaces: tuple[CandidateSurface, ...] = (CandidateSurface(),)


def test_candidate_generation_is_unresolved_and_missing_provider_blocks() -> None:
    candidate = generate_candidate_blueprint(CandidateInventory())
    assert candidate.status == "incomplete"
    assert candidate.behavior_contracts[0].accepted is False

    missing = generate_candidate_blueprint(
        CandidateInventory(
            surfaces=(replace(CandidateSurface(), discovery_adapter_id=""),)
        ),
        target_kind="workflow",
    )
    assert missing.status == "blocked"
    assert "missing observation provider" in missing.blockers[0]

    classified_support = generate_candidate_blueprint(
        CandidateInventory(
            surfaces=(
                replace(
                    CandidateSurface(),
                    disposition="supporting",
                    behavior_bearing=True,
                ),
            )
        )
    )
    assert classified_support.behavior_contracts == ()
    assert classified_support.unresolved_ids == (
        "candidate:behavior-denominator-empty",
    )
