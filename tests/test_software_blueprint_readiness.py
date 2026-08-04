from __future__ import annotations

from dataclasses import dataclass, replace
import json
from unittest import mock

import pytest

import flowguard.software_blueprint_readiness as blueprint_readiness

from flowguard.evidence_receipts import fingerprint_value
from flowguard.implementation_blueprint import BlueprintResourceReference
from flowguard.software_blueprint_readiness import (
    BEHAVIOR_DIMENSIONS,
    BehaviorBlockContract,
    BehaviorCaseContract,
    BehaviorCoverageEdge,
    BehaviorDimensionContract,
    CoverageExecutionEvidence,
    DelegatedAssertionHelper,
    NoDeclaredIntentRationale,
    PortableBehaviorBinding,
    ProjectIntentInventory,
    ProjectResourceInventory,
    ProjectResourceMember,
    ProjectTestNodeDisposition,
    SoftwareBlueprintReadinessError,
    SupportingSurfaceRelation,
    generate_candidate_blueprint,
    load_affected_behavior_neighborhood,
    normalize_behavior_blueprint,
    review_behavior_blueprint,
    review_static_blueprint_readiness,
)


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
        owner_contract_id="contract:save",
        owner_id="owner:save",
        function_relation="Input x State -> Set(Output x State)",
        dimensions=dimensions(surface_id, shared_surfaces=shared_surfaces),
        semantic_spec_ids=("semantic:save",),
        oracle_ids=("oracle:save",),
        portable_binding_ids=(f"portable:{surface_id}",),
        protected_failure_ids=("failure:rejected",),
        accepted=accepted,
        acceptance_evidence_fingerprints=(
            (("model-purpose", "sha256:model"),) if accepted else ()
        ),
        source_fingerprint=f"sha256:source:{surface_id}",
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
    return BehaviorCoverageEdge(
        coverage_id=f"coverage:{block.behavior_block_id}",
        behavior_block_id=block.behavior_block_id,
        implementation_surface_id=block.implementation_surface_id,
        model_obligation_id=block.model_element_id,
        semantic_spec_id="semantic:save",
        owner_contract_id=block.owner_contract_id,
        test_node_id=test_node_id,
        oracle_member_id=member_id,
        oracle_member_fingerprint=member_fingerprint,
        case_id=f"case:{block.behavior_block_id}:good",
        covered_dimensions=BEHAVIOR_DIMENSIONS,
        evidence_role="real_test_assertion",
        oracle_id="oracle:save",
    )


CASE_DIMENSIONS = {
    "good": ("input", "state", "output", "effect", "order", "completion"),
    "boundary": ("input", "state", "output", "retry", "timeout", "completion"),
    "bad": ("input", "state", "effect", "error", "decision", "completion"),
}


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
            for dimension in CASE_DIMENSIONS[exact_case.case_kind]:
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
                        owner_contract_id=block.owner_contract_id,
                        test_node_id="test:save",
                        oracle_member_id=member_id,
                        oracle_member_fingerprint=member_fingerprint,
                        case_id=exact_case.case_id,
                        covered_dimensions=(dimension,),
                        evidence_role="planned_checker",
                        oracle_id="oracle:save",
                    )
                )
    return tuple(exact_cases), tuple(edges), planned


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
    return ProjectResourceInventory(
        inventory_id="resources:one",
        boundary_fingerprint="sha256:boundary",
        members=tuple(
            ProjectResourceMember(
                member_id=f"resource:{category}",
                category=category,
                category_disposition=(
                    "scoped_out" if category == "external_service" else "current"
                ),
                category_evidence_fingerprint=f"sha256:category:{category}",
                resource_reference=BlueprintResourceReference(
                    resource_id=f"resource:{category}",
                    kind=("verification" if category == "behavioral_oracle" else category),
                    owner_id="owner:fixture",
                    artifact_id=f"artifact:{category}",
                    purpose=f"preserve the fixture {category} obligation",
                    lifecycle_role=(
                        "not_applicable"
                        if category == "external_service"
                        else "blueprint_input"
                    ),
                    disposition=(
                        "scoped_out" if category == "external_service" else "current"
                    ),
                    artifact_fingerprint=(
                        None
                        if category == "external_service"
                        else f"sha256:{category}"
                    ),
                    rationale=(
                        "no external service is declared"
                        if category == "external_service"
                        else None
                    ),
                    semantics=(
                        ()
                        if category == "external_service"
                        else (("blueprint_contract", f"materialize {category}"),)
                    ),
                ),
                rationale=(
                    "no external service is declared"
                    if category == "external_service"
                    else "independently discovered current project resource"
                ),
            )
            for category in categories
        ),
        discovery_fingerprints=(("boundary-scan", "sha256:scan"),),
    )


def intent_inventory() -> ProjectIntentInventory:
    return ProjectIntentInventory(
        inventory_id="intent:one",
        subject_revision="sha256:revision",
        canonical_review_fingerprint="sha256:canonical-intent-review",
        contributions=(),
        no_declared_intent=NoDeclaredIntentRationale(
            rationale_id="no-intent:fixture",
            evidence_fingerprints=(("work-context-scan", "sha256:work"),),
            rationale="the fixture declares no external change intent",
        ),
    )


def review(
    blocks: tuple[BehaviorBlockContract, ...] | None = None,
    *,
    edges: tuple[BehaviorCoverageEdge, ...] | None = None,
    relations: tuple[SupportingSurfaceRelation, ...] | None = None,
    portable_bindings: tuple[PortableBehaviorBinding, ...] | None = None,
):
    blocks = blocks or (contract(),)
    all_cases, default_edges, planned_checkers = exact_design(blocks)
    edges = edges or default_edges
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
    return review_behavior_blueprint(
        inventory_fingerprint="sha256:inventory",
        required_behavior_surface_ids=tuple(
            block.implementation_surface_id for block in blocks
        ),
        supporting_surface_ids=("surface:helper",) if relations else (),
        contracts=blocks,
        portable_bindings=(
            portable_bindings
            if portable_bindings is not None
            else tuple(portable(block) for block in blocks)
        ),
        case_contracts=all_cases,
        supporting_relations=relations,
        coverage_edges=edges,
        coverage_execution_evidence=executions,
        test_node_dispositions=(
            ProjectTestNodeDisposition(
                "test:save",
                "behavior_coverage" if len(blocks) == 1 else "cross_owner_integration",
                tuple(block.owner_id for block in blocks),
                tuple(edge.coverage_id for edge in edges),
                "exact real test-member coverage",
            ),
        ),
        required_test_node_ids=("test:save",),
        test_nodes=(node,),
        planned_checker_fingerprints=planned_checkers,
        expected_portable_fingerprints={"portable-model:save": "sha256:portable"},
        supporting_surface_fingerprints=(
            {"surface:helper": "sha256:helper"} if relations else {}
        ),
    )


def test_real_test_edge_and_not_run_execution_close_static_design() -> None:
    result = review()

    assert result.complete
    assert result.coverage_edges[0].oracle_member_id.startswith("checker-design:")
    assert result.coverage_execution_evidence[0].disposition == "not_run"


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
        test_nodes=(
            TestNodeFixture(
                "test:save",
                (AssertionFixture("assertion:save", "sha256:assertion"),),
            ),
        ),
        expected_portable_fingerprints={"portable-model:save": "sha256:portable"},
    )
    assert "case_evidence_member_stale" in {row.code for row in stale.findings}


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
        test_nodes=(
            TestNodeFixture(
                "test:save",
                (AssertionFixture("assertion:save", "sha256:assertion"),),
            ),
        ),
        expected_portable_fingerprints={"portable-model:save": "sha256:portable"},
        supporting_surface_fingerprints={"surface:helper": "sha256:helper"},
    )
    assert {row.code for row in result.findings} >= {
        "portable_behavior_binding_stale",
        "supporting_ownership_edge_stale",
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
    projection = normalize_behavior_blueprint(
        blueprint_fingerprint="sha256:blueprint",
        behavior_report=behavior,
        shared_objects={"semantic:save": {"value": "declared"}},
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
    projection = normalize_behavior_blueprint(
        blueprint_fingerprint="sha256:blueprint",
        behavior_report=behavior,
        shared_objects=shared,
        shard_size=1,
        source_projection={"legacy_repeated": [shared] * 20},
    )
    neighborhood = load_affected_behavior_neighborhood(
        projection,
        behavior,
        shared,
        affected_surface_ids=("surface:helper",),
    )

    assert neighborhood.behavior_block_ids == ("behavior:surface:save",)
    assert len(neighborhood.coverage_ids) == 18
    assert all(
        coverage_id.startswith("coverage:behavior:surface:save:")
        for coverage_id in neighborhood.coverage_ids
    )
    assert "unrelated" not in dict(neighborhood.shared_objects)
    assert projection.logical_fingerprint

    affected_only = load_affected_behavior_neighborhood(
        projection,
        behavior,
        {key: value for key, value in shared.items() if key != "unrelated"},
        affected_surface_ids=("surface:save",),
    )
    assert affected_only.fingerprint == neighborhood.fingerprint

    stale = dict(shared)
    stale["semantic:save"] = {"kind": "changed"}
    with pytest.raises(SoftwareBlueprintReadinessError, match="exact current"):
        load_affected_behavior_neighborhood(
            projection,
            behavior,
            stale,
            affected_surface_ids=("surface:save",),
        )


@dataclass(frozen=True)
class CandidateSurface:
    surface_id: str = "surface:observed"
    path: str = "app.py"
    symbol: str = "save"
    content_fingerprint: str = "sha256:source"
    behavior_bearing: bool = True
    discovery_adapter_id: str = "provider:fake-observation"


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
