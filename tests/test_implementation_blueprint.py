from __future__ import annotations

from dataclasses import dataclass

import pytest

from flowguard.evidence_receipts import fingerprint_value
from flowguard.implementation_blueprint import (
    BlueprintResourceReference,
    BlueprintShard,
    BlueprintValidationError,
    ModelImplementationBinding,
    OracleReference,
    ReconstructionEvidence,
    SemanticSpecReference,
    SoftwareBlueprintManifest,
    derive_affected_blueprint_neighborhood,
    project_software_blueprint,
    qualify_software_blueprint,
    review_model_implementation_bindings,
    verify_blueprint_projection,
)


@dataclass(frozen=True)
class FakeSurface:
    surface_id: str
    fingerprint: str
    disposition: str = "model_implementation"
    behavior_bearing: bool = True
    state_write_ids: tuple[str, ...] = ()
    effect_ids: tuple[str, ...] = ()
    supporting_owner_surface_id: str = ""


@dataclass(frozen=True)
class FakeInventory:
    inventory_id: str
    fingerprint: str
    surfaces: tuple[FakeSurface, ...]
    hidden_writer_ids: tuple[str, ...] = ()
    unresolved_surface_ids: tuple[str, ...] = ()
    parse_failure_ids: tuple[str, ...] = ()


def spec(spec_id: str = "spec:save", model_id: str = "model:save") -> SemanticSpecReference:
    return SemanticSpecReference(
        semantic_spec_id=spec_id,
        owner_id="owner:model",
        artifact_id=f"artifact:{spec_id}",
        artifact_fingerprint=f"fp:{spec_id}",
        covered_model_element_ids=(model_id,),
        covered_dimensions=("error", "input", "output", "state_effect"),
        semantics=(
            ("input", "accept the declared operation input contract"),
            ("output", "return the declared operation output contract"),
            ("error", "reject invalid input without reporting success"),
            ("state_effect", "apply the declared state write exactly once"),
        ),
    )


def oracle(oracle_id: str = "oracle:save", model_id: str = "model:save") -> OracleReference:
    return OracleReference(
        oracle_id=oracle_id,
        owner_id="owner:test",
        artifact_id=f"artifact:{oracle_id}",
        artifact_fingerprint=f"fp:{oracle_id}",
        covered_model_element_ids=(model_id,),
        covered_dimensions=("error", "input", "output", "state_effect"),
        semantics=(
            ("input", "exercise valid and invalid inputs"),
            ("output", "compare the returned value with the expected result"),
            ("error", "require invalid input to remain non-success"),
            ("state_effect", "inspect the declared state write"),
        ),
    )


def binding(
    binding_id: str = "binding:save",
    model_id: str = "model:save",
    surface_id: str = "surface:save",
    spec_id: str = "spec:save",
    oracle_id: str = "oracle:save",
    *,
    primary: bool = True,
    implementation_fingerprint: str = "fp:surface:save",
) -> ModelImplementationBinding:
    return ModelImplementationBinding(
        binding_id=binding_id,
        model_element_id=model_id,
        implementation_surface_id=surface_id,
        relation_kind="implements",
        owner_contract_id="contract:save",
        semantic_spec_ids=(spec_id,),
        oracle_ids=(oracle_id,),
        required_dimensions=("input", "output", "error", "state_effect"),
        primary=primary,
        implementation_fingerprint=implementation_fingerprint,
    )


def good_report():
    inventory = FakeInventory(
        "inventory:one",
        "fp:inventory:one",
        (FakeSurface("surface:save", "fp:surface:save", state_write_ids=("db",)),),
    )
    return review_model_implementation_bindings(
        inventory,
        required_model_element_ids=("model:save",),
        bindings=(binding(),),
        semantic_specs=(spec(),),
        oracles=(oracle(),),
    )


def resource(resource_id: str = "resource:runtime", kind: str = "runtime"):
    return BlueprintResourceReference(
        resource_id=resource_id,
        kind=kind,
        owner_id="owner:build",
        artifact_id=f"artifact:{resource_id}",
        artifact_fingerprint=f"fp:{resource_id}",
        semantics=(("requirement", "provide the declared runtime capability"),),
    )


def manifest(report=None, resources=None, oracles=None):
    report = report or good_report()
    resources = tuple(resources or (resource(),))
    oracles = tuple(oracles or (oracle(),))
    return SoftwareBlueprintManifest(
        blueprint_id="blueprint:flowguard",
        observed_snapshot_id="snapshot:current",
        observed_snapshot_fingerprint="fp:snapshot:current",
        inventory_id=report.inventory_id,
        inventory_fingerprint=report.inventory_fingerprint,
        binding_report_id="binding-report:current",
        binding_report_fingerprint=report.fingerprint,
        semantic_mesh_id="mesh:current",
        semantic_mesh_fingerprint="fp:mesh:current",
        portable_owner_fingerprints=(("portable:system", "fp:portable:system"),),
        resources=resources,
        oracles=oracles,
        required_resource_ids=tuple(item.resource_id for item in resources),
        required_resource_kinds=tuple(item.kind for item in resources),
        required_oracle_ids=tuple(item.oracle_id for item in oracles),
    )


def test_binding_review_is_bidirectional_and_exposes_integration_protocol():
    report = good_report()

    assert report.ok
    assert report.status == "complete"
    assert report.implementation_surface_ids == ("surface:save",)
    assert report.model_obligation_ids == ("model:save",)
    assert report.semantic_spec_ids == ("spec:save",)
    assert report.oracle_ids == ("oracle:save",)
    assert report.fingerprint == fingerprint_value(report.to_dict())


def test_path_binding_without_semantics_and_oracles_is_only_traceability():
    inventory = FakeInventory(
        "inventory:one",
        "fp:inventory:one",
        (FakeSurface("surface:save", "fp:surface:save"),),
    )
    path_only = ModelImplementationBinding(
        binding_id="binding:path-only",
        model_element_id="model:save",
        implementation_surface_id="surface:save",
        relation_kind="implements",
        owner_contract_id="contract:save",
        semantic_spec_ids=(),
        oracle_ids=(),
    )

    report = review_model_implementation_bindings(
        inventory,
        required_model_element_ids=("model:save",),
        bindings=(path_only,),
        semantic_specs=(),
        oracles=(),
    )

    assert report.status == "incomplete"
    assert {finding.code for finding in report.findings} >= {
        "semantic_dimensions_incomplete",
        "oracle_dimensions_incomplete",
    }


def test_duplicate_primary_owners_and_unbound_discovered_surface_block():
    inventory = FakeInventory(
        "inventory:one",
        "fp:inventory:one",
        (
            FakeSurface("surface:save", "fp:surface:save"),
            FakeSurface("surface:hidden", "fp:surface:hidden"),
        ),
    )
    report = review_model_implementation_bindings(
        inventory,
        required_model_element_ids=("model:save",),
        bindings=(binding("binding:a"), binding("binding:b")),
        semantic_specs=(spec(),),
        oracles=(oracle(),),
    )

    assert report.status == "blocked"
    assert {finding.code for finding in report.findings} >= {
        "duplicate_primary_implementation",
        "unbound_behavior_surface",
    }


def test_independent_discovery_blockers_and_orphan_helpers_fail_closed():
    inventory = FakeInventory(
        "inventory:one",
        "fp:inventory:one",
        (
            FakeSurface("surface:save", "fp:surface:save"),
            FakeSurface(
                "surface:helper",
                "fp:surface:helper",
                disposition="supporting",
                behavior_bearing=False,
            ),
        ),
        hidden_writer_ids=("surface:dynamic-writer",),
    )
    report = review_model_implementation_bindings(
        inventory,
        required_model_element_ids=("model:save",),
        bindings=(binding(),),
        semantic_specs=(spec(),),
        oracles=(oracle(),),
    )

    assert report.status == "blocked"
    assert {finding.code for finding in report.findings} >= {
        "orphan_supporting_surface",
        "hidden_state_or_effect_writer",
    }


def test_current_fingerprint_comparison_marks_only_static_binding_stale():
    inventory = FakeInventory(
        "inventory:one",
        "fp:inventory:one",
        (FakeSurface("surface:save", "fp:new"),),
    )
    report = review_model_implementation_bindings(
        inventory,
        required_model_element_ids=("model:save",),
        bindings=(binding(implementation_fingerprint="fp:old"),),
        semantic_specs=(spec(),),
        oracles=(oracle(),),
    )

    assert report.status == "stale"
    assert "stale_implementation_binding" in {finding.code for finding in report.findings}


def test_resources_require_fingerprints_or_explicit_external_disposition_and_no_secrets():
    with pytest.raises(BlueprintValidationError, match="fingerprint"):
        BlueprintResourceReference(
            resource_id="runtime",
            kind="runtime",
            owner_id="owner",
            artifact_id="artifact",
        )
    external = BlueprintResourceReference(
        resource_id="service",
        kind="external_service",
        owner_id="owner",
        artifact_id="contract",
        disposition="external",
        rationale="provided by deployment environment",
    )
    assert external.disposition == "external"
    with pytest.raises(BlueprintValidationError, match="secrets"):
        BlueprintResourceReference(
            resource_id="config",
            kind="configuration",
            owner_id="owner",
            artifact_id="config",
            artifact_fingerprint="fp:config",
            semantics=(("password", "plaintext"),),
        )


def test_static_complete_and_empirical_not_run_remain_separate_claims():
    report = good_report()
    blueprint = manifest(report)

    qualification = qualify_software_blueprint(blueprint, report)

    assert qualification.static_status == "complete"
    assert qualification.empirical_status == "not_run"
    assert qualification.ok
    assert qualification.claim_text == "blueprint complete; reconstruction not verified"


def test_required_reconstruction_and_mismatched_receipt_do_not_change_static_result():
    report = good_report()
    blueprint = manifest(report)
    not_run = qualify_software_blueprint(
        blueprint, report, reconstruction_required=True
    )
    assert not not_run.ok
    assert not_run.static_status == "complete"
    assert not_run.empirical_status == "not_run"

    evidence = ReconstructionEvidence(
        receipt_id="receipt:wrong",
        blueprint_fingerprint="fp:other-blueprint",
        environment_fingerprint="fp:environment",
        isolated_environment=True,
        source_access_policy="no production source access",
        covered_oracle_ids=("oracle:save",),
        evidence_fingerprint="fp:evidence",
        status="pass",
    )
    qualification = qualify_software_blueprint(
        blueprint,
        report,
        reconstruction_evidence=evidence,
        reconstruction_required=True,
    )

    assert qualification.static_status == "complete"
    assert qualification.empirical_status == "blocked"
    assert not qualification.ok


def test_missing_resource_and_oracle_are_static_blockers():
    report = good_report()
    blueprint = SoftwareBlueprintManifest(
        blueprint_id="blueprint:flowguard",
        observed_snapshot_id="snapshot:current",
        observed_snapshot_fingerprint="fp:snapshot:current",
        inventory_id=report.inventory_id,
        inventory_fingerprint=report.inventory_fingerprint,
        binding_report_id="binding-report:current",
        binding_report_fingerprint=report.fingerprint,
        semantic_mesh_id="mesh:current",
        semantic_mesh_fingerprint="fp:mesh:current",
        portable_owner_fingerprints=(),
        resources=(),
        oracles=(),
        required_resource_ids=("resource:runtime",),
        required_resource_kinds=("runtime",),
        required_oracle_ids=("oracle:save",),
    )

    qualification = qualify_software_blueprint(blueprint, report)

    assert qualification.static_status == "blocked"
    assert {finding.code for finding in qualification.static_findings} >= {
        "required_resource_missing",
        "required_oracle_missing",
    }


def test_projection_is_deterministic_and_excludes_source_text():
    report = good_report()
    blueprint = manifest(report)

    inventory = FakeInventory(
        "inventory:one",
        "fp:inventory:one",
        (FakeSurface("surface:save", "fp:surface:save"),),
    )
    first = project_software_blueprint(
        blueprint, report, implementation_inventory=inventory
    )
    second = project_software_blueprint(
        blueprint, report, implementation_inventory=inventory
    )

    assert first.fingerprint == second.fingerprint
    assert [shard.content_fingerprint for shard in first.shards] == [
        shard.content_fingerprint for shard in second.shards
    ]
    with pytest.raises(BlueprintValidationError, match="source text"):
        payload = ({"source_text": "def private(): pass"},)
        digest = fingerprint_value(list(payload))
        BlueprintShard(
            shard_id=f"source:{digest}",
            kind="source",
            relative_path="shards/source.json",
            member_ids=(),
            payload=payload,
            content_fingerprint=digest,
        )


def test_projection_verification_rejects_missing_and_tampered_materialized_shards():
    report = good_report()
    blueprint = manifest(report)
    projection = project_software_blueprint(
        blueprint,
        report,
        implementation_inventory=FakeInventory(
            "inventory:one",
            "fp:inventory:one",
            (FakeSurface("surface:save", "fp:surface:save"),),
        ),
    )
    materialized = {
        shard.relative_path: {"payload": list(shard.payload)} for shard in projection.shards
    }
    assert verify_blueprint_projection(
        projection,
        expected_blueprint_fingerprint=blueprint.fingerprint,
        materialized_shards=materialized,
    ).ok

    missing = dict(materialized)
    missing.pop(projection.shards[0].relative_path)
    result = verify_blueprint_projection(projection, materialized_shards=missing)
    assert not result.ok
    assert "projection_shard_missing" in {finding.code for finding in result.findings}

    tampered = dict(materialized)
    tampered[projection.shards[-1].relative_path] = {"payload": [{"changed": True}]}
    result = verify_blueprint_projection(projection, materialized_shards=tampered)
    assert not result.ok
    assert "projection_shard_tampered" in {finding.code for finding in result.findings}


def test_shard_paths_cannot_escape_projection_root():
    payload = ({"binding_id": "binding:one"},)
    digest = fingerprint_value(list(payload))
    with pytest.raises(BlueprintValidationError, match="escapes"):
        BlueprintShard(
            shard_id=f"bindings:{digest}",
            kind="bindings",
            relative_path="../outside.json",
            member_ids=("binding:one",),
            payload=payload,
            content_fingerprint=digest,
        )


def test_affected_neighborhood_closes_shared_semantics_and_reuses_unaffected_shards():
    first_binding = binding()
    second_binding = binding(
        binding_id="binding:list",
        model_id="model:list",
        surface_id="surface:list",
        spec_id="spec:save",  # shared semantics connect the sibling
        oracle_id="oracle:list",
        implementation_fingerprint="fp:surface:list",
    )
    neighborhood = derive_affected_blueprint_neighborhood(
        (first_binding, second_binding),
        changed_member_ids=("surface:save",),
    )
    assert neighborhood.affected_binding_ids == ("binding:list", "binding:save")
    assert neighborhood.affected_model_element_ids == ("model:list", "model:save")

    report = good_report()
    blueprint = manifest(report)
    inventory = FakeInventory(
        "inventory:one",
        "fp:inventory:one",
        (FakeSurface("surface:save", "fp:surface:save"),),
    )
    first_projection = project_software_blueprint(
        blueprint, report, implementation_inventory=inventory
    )
    second_projection = project_software_blueprint(
        blueprint,
        report,
        implementation_inventory=inventory,
        previous_projection=first_projection,
        affected_neighborhood=derive_affected_blueprint_neighborhood(
            report.bindings, changed_member_ids=("binding:save",)
        ),
    )

    assert second_projection.fingerprint == first_projection.fingerprint
    assert len(second_projection.reused_shard_ids) >= 2
    assert any(shard_id.startswith("bindings:") for shard_id in second_projection.regenerated_shard_ids)
