from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
import subprocess

import pytest

import flowguard.implementation_blueprint as blueprint_module
from flowguard.evidence_receipts import fingerprint_value
from flowguard.implementation_blueprint import (
    BlueprintResourceReference,
    BlueprintFinding,
    BlueprintLayerResult,
    BlueprintManifestQualificationReport,
    BlueprintProjectionVerification,
    BlueprintShard,
    BlueprintValidationError,
    ModelImplementationBinding,
    OracleReference,
    SEMANTIC_AUTHORITY_OBSERVED_CANDIDATE,
    SemanticSpecReference,
    SoftwareBlueprintManifest,
    CanonicalBlueprintProjection,
    derive_affected_blueprint_neighborhood,
    _qualify_blueprint_manifest,
    review_model_implementation_bindings,
    verify_blueprint_projection,
    write_canonical_blueprint_projection,
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
    owner_id: str = "owner:implementation"


@dataclass(frozen=True)
class FakeInventory:
    inventory_id: str
    fingerprint: str
    surfaces: tuple[FakeSurface, ...]
    hidden_writer_ids: tuple[str, ...] = ()
    unresolved_surface_ids: tuple[str, ...] = ()
    parse_failure_ids: tuple[str, ...] = ()


def spec(
    spec_id: str = "spec:save",
    model_id: str = "model:save",
    *,
    authority_kind: str = "declared_behavior",
) -> SemanticSpecReference:
    return SemanticSpecReference(
        semantic_spec_id=spec_id,
        owner_id="owner:model",
        artifact_id=f"artifact:{spec_id}",
        artifact_fingerprint=f"fp:{spec_id}",
        source_id=f"intent-source:{spec_id}",
        source_owner_id="owner:intent",
        source_content_fingerprint=f"fp:intent-source:{spec_id}",
        covered_model_element_ids=(model_id,),
        covered_dimensions=("error", "input", "output", "state_effect"),
        semantics=(
            ("input", "accept the declared operation input contract"),
            ("output", "return the declared operation output contract"),
            ("error", "reject invalid input without reporting success"),
            ("state_effect", "apply the declared state write exactly once"),
        ),
        authority_kind=authority_kind,
        provenance_fingerprints=(("model-purpose", "fp:model-purpose"),),
    )


def oracle(oracle_id: str = "oracle:save", model_id: str = "model:save") -> OracleReference:
    return OracleReference(
        oracle_id=oracle_id,
        owner_id="owner:test",
        artifact_id=f"artifact:{oracle_id}",
        artifact_fingerprint=f"fp:{oracle_id}",
        source_id=f"oracle-source:{oracle_id}",
        source_owner_id="owner:oracle-source",
        source_content_fingerprint=f"fp:oracle-source:{oracle_id}",
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
        model_obligation_ids=(model_id,),
        implementation_surface_id=surface_id,
        relation_kind="implements",
        owner_contract_id="contract:save",
        implementation_source_id=surface_id,
        implementation_owner_id="owner:implementation",
        implementation_content_fingerprint=implementation_fingerprint,
        semantic_spec_ids=(spec_id,),
        oracle_ids=(oracle_id,),
        required_dimensions=("input", "output", "error", "state_effect"),
        test_evidence_ids=("test:save",),
        test_evidence_fingerprints=(("test:save", "fp:test:save"),),
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
        current_test_evidence_fingerprints={"test:save": "fp:test:save"},
    )


def resource(resource_id: str = "resource:runtime", kind: str = "runtime"):
    return BlueprintResourceReference(
        resource_id=resource_id,
        kind=kind,
        owner_id="owner:build",
        artifact_id=f"artifact:{resource_id}",
        purpose="satisfy the declared blueprint resource obligation",
        lifecycle_role="implementation_dependency",
        consuming_behavior_ids=("behavior:save",),
        consuming_model_ids=("model:save",),
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
        test_inventory_id="test-inventory:current",
        test_inventory_fingerprint="fp:test-inventory:current",
        model_test_alignment_report_id="alignment:current",
        model_test_alignment_report_fingerprint="fp:alignment:current",
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


def test_large_binding_and_manifest_fingerprints_are_computed_once(monkeypatch):
    calls = 0
    original = blueprint_module._fingerprinted

    def counted(value):
        nonlocal calls
        calls += 1
        return original(value)

    report = good_report()
    monkeypatch.setattr(blueprint_module, "_fingerprinted", counted)

    report_fingerprint = report.fingerprint
    assert report.fingerprint == report_fingerprint
    assert report.fingerprint == report_fingerprint

    current_manifest = manifest(report=report)
    manifest_fingerprint = current_manifest.fingerprint
    assert current_manifest.fingerprint == manifest_fingerprint
    assert current_manifest.fingerprint == manifest_fingerprint
    assert calls == 2


def test_binding_review_rejects_declared_items_outside_observed_denominators():
    inventory = FakeInventory(
        "inventory:one",
        "fp:inventory:one",
        (FakeSurface("surface:save", "fp:surface:save"),),
    )
    report = review_model_implementation_bindings(
        inventory,
        required_model_element_ids=("model:save",),
        bindings=(
            binding(),
            binding(
                "binding:extra",
                "model:extra",
                "surface:extra",
                "spec:save",
                "oracle:save",
                implementation_fingerprint="fp:surface:extra",
            ),
        ),
        semantic_specs=(spec(), spec("spec:unused", "model:save")),
        oracles=(oracle(), oracle("oracle:unused", "model:save")),
        current_test_evidence_fingerprints={"test:save": "fp:test:save"},
    )
    qualification = _qualify_blueprint_manifest(
        manifest(report),
        report,
        current_test_inventory_fingerprint="fp:test-inventory:current",
        current_model_test_alignment_report_fingerprint="fp:alignment:current",
    )

    assert {finding.code for finding in report.findings} >= {
        "declared_model_element_unobserved",
        "declared_implementation_surface_unobserved",
        "declared_semantic_spec_unobserved",
        "declared_oracle_unobserved",
    }
    assert qualification.layer_status("traceability") == "blocked"
    assert qualification.layer_status("independent_semantics") == "incomplete"
    assert qualification.layer_status("resource_oracle") == "incomplete"


def test_path_binding_without_semantics_and_oracles_is_only_traceability():
    inventory = FakeInventory(
        "inventory:one",
        "fp:inventory:one",
        (FakeSurface("surface:save", "fp:surface:save"),),
    )
    path_only = ModelImplementationBinding(
        binding_id="binding:path-only",
        model_element_id="model:save",
        model_obligation_ids=("model:save",),
        implementation_surface_id="surface:save",
        relation_kind="implements",
        owner_contract_id="contract:save",
        implementation_source_id="surface:save",
        implementation_owner_id="owner:implementation",
        implementation_content_fingerprint="fp:surface:save",
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


def test_same_source_identity_cannot_certify_independent_semantics():
    inventory = FakeInventory(
        "inventory:one",
        "fp:inventory:one",
        (FakeSurface("surface:save", "fp:surface:save"),),
    )
    report = review_model_implementation_bindings(
        inventory,
        required_model_element_ids=("model:save",),
        bindings=(binding(),),
        semantic_specs=(
            replace(
                spec(authority_kind=SEMANTIC_AUTHORITY_OBSERVED_CANDIDATE),
                source_id="surface:save",
                source_owner_id="owner:implementation",
                source_content_fingerprint="fp:surface:save",
            ),
        ),
        oracles=(oracle(),),
        current_test_evidence_fingerprints={"test:save": "fp:test:save"},
    )
    blueprint = manifest(report)
    qualification = _qualify_blueprint_manifest(
        blueprint,
        report,
        current_test_inventory_fingerprint="fp:test-inventory:current",
        current_model_test_alignment_report_fingerprint="fp:alignment:current",
    )

    assert "semantic_source_not_independent" in {
        finding.code for finding in report.findings
    }
    assert qualification.layer_status("inventory") == "complete"
    assert qualification.layer_status("traceability") == "complete"
    assert qualification.layer_status("independent_semantics") == "blocked"
    assert qualification.deepest_proven_layer == "traceability"


def test_supporting_oracle_surface_can_delegate_without_self_certifying_behavior():
    inventory = FakeInventory(
        "inventory:one",
        "fp:inventory:one",
        (
            FakeSurface("surface:save", "fp:surface:save"),
            FakeSurface(
                "surface:oracle-runner",
                "fp:oracle-runner",
                disposition="supporting",
                behavior_bearing=False,
                supporting_owner_surface_id="surface:save",
            ),
        ),
    )
    shared_oracle = replace(
        oracle(),
        source_id="surface:oracle-runner",
        source_owner_id="owner:implementation",
        source_content_fingerprint="fp:oracle-runner",
    )
    supporting = ModelImplementationBinding(
        binding_id="binding:oracle-runner",
        model_element_id="model:save",
        model_obligation_ids=("model:save",),
        implementation_surface_id="surface:oracle-runner",
        relation_kind="supports",
        owner_contract_id="contract:save",
        implementation_source_id="surface:oracle-runner",
        implementation_owner_id="owner:implementation",
        implementation_content_fingerprint="fp:oracle-runner",
        semantic_spec_ids=("spec:save",),
        oracle_ids=("oracle:save",),
        required_dimensions=("input", "output", "error", "state_effect"),
        test_evidence_ids=("test:save",),
        test_evidence_fingerprints=(("test:save", "fp:test:save"),),
        primary=False,
        delegating=True,
        implementation_fingerprint="fp:oracle-runner",
    )

    report = review_model_implementation_bindings(
        inventory,
        required_model_element_ids=("model:save",),
        required_implementation_surface_ids=(
            "surface:save",
            "surface:oracle-runner",
        ),
        bindings=(binding(), supporting),
        semantic_specs=(spec(),),
        oracles=(shared_oracle,),
        current_test_evidence_fingerprints={"test:save": "fp:test:save"},
    )

    assert report.ok
    assert report.model_obligation_ids == ("model:save",)
    assert not {
        "semantic_source_not_independent",
        "oracle_source_not_independent",
    } & {finding.code for finding in report.findings}

    mismatched = replace(
        supporting,
        model_obligation_ids=("behavior:unrelated",),
    )
    mismatched_report = review_model_implementation_bindings(
        inventory,
        required_model_element_ids=("model:save",),
        required_implementation_surface_ids=(
            "surface:save",
            "surface:oracle-runner",
        ),
        bindings=(binding(), mismatched),
        semantic_specs=(spec(),),
        oracles=(shared_oracle,),
        current_test_evidence_fingerprints={"test:save": "fp:test:save"},
    )
    assert "supporting_obligation_mismatch" in {
        finding.code for finding in mismatched_report.findings
    }


def test_missing_exact_test_binding_blocks_model_code_test_layer():
    inventory = FakeInventory(
        "inventory:one",
        "fp:inventory:one",
        (FakeSurface("surface:save", "fp:surface:save"),),
    )
    no_test = ModelImplementationBinding(
        **{
            **binding().to_dict(),
            "test_evidence_ids": (),
            "test_evidence_fingerprints": (),
        }
    )
    report = review_model_implementation_bindings(
        inventory,
        required_model_element_ids=("model:save",),
        bindings=(no_test,),
        semantic_specs=(spec(),),
        oracles=(oracle(),),
        current_test_evidence_fingerprints={},
    )

    assert "model_test_binding_missing" in {finding.code for finding in report.findings}


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
            purpose="execute the target",
            lifecycle_role="runtime_dependency",
            consuming_behavior_ids=("behavior:save",),
            consuming_model_ids=("model:save",),
        )
    external = BlueprintResourceReference(
        resource_id="service",
        kind="external_service",
        owner_id="owner",
        artifact_id="contract",
        purpose="supply the declared external service contract",
        lifecycle_role="external_dependency",
        consuming_behavior_ids=(),
        consuming_model_ids=(),
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
            purpose="configure the target",
            lifecycle_role="implementation_dependency",
            consuming_behavior_ids=("behavior:save",),
            consuming_model_ids=("model:save",),
            artifact_fingerprint="fp:config",
            semantics=(("password", "plaintext"),),
        )


def test_current_resource_without_exact_behavior_and_model_consumers_blocks() -> None:
    report = good_report()
    unbound = replace(
        resource(), consuming_behavior_ids=(), consuming_model_ids=()
    )
    qualification = _qualify_blueprint_manifest(
        manifest(report, resources=(unbound,)),
        report,
    )

    assert qualification.layer_status("resource_oracle") == "blocked"
    assert "resource_consumer_binding_missing" in {
        finding.code for finding in qualification.static_findings
    }


def test_semantic_oracle_and_implementation_sources_use_exact_identities() -> None:
    inventory = FakeInventory(
        "inventory:one",
        "fp:inventory:one",
        (FakeSurface("surface:save", "fp:surface:save"),),
    )
    shared_source = replace(
        oracle(),
        source_id="intent-source:spec:save",
        source_owner_id="owner:intent",
        source_content_fingerprint="fp:intent-source:spec:save",
    )
    report = review_model_implementation_bindings(
        inventory,
        required_model_element_ids=("model:save",),
        bindings=(binding(),),
        semantic_specs=(spec(),),
        oracles=(shared_source,),
        current_test_evidence_fingerprints={"test:save": "fp:test:save"},
    )

    assert "semantic_oracle_source_not_independent" in {
        finding.code for finding in report.findings
    }


def test_static_complete_uses_one_layered_readiness_result():
    report = good_report()
    blueprint = manifest(report)

    qualification = _qualify_blueprint_manifest(blueprint, report)

    assert qualification.static_manifest_status == "complete"
    assert qualification.static_manifest_ready
    assert qualification.deepest_proven_layer == "static_blueprint"
    assert qualification.layer_status("model_code_test") == "complete"
    assert "ok" not in qualification.to_dict()
    assert "claim_text" not in qualification.to_dict()
    assert qualification.claim_boundary.endswith(
        "implementation admission, or release readiness."
    )
    assert "empirical_status" not in qualification.to_dict()
    assert "target_generation_required" not in qualification.to_dict()


def test_manifest_qualification_report_cannot_be_caller_constructed() -> None:
    report = good_report()
    qualification = _qualify_blueprint_manifest(manifest(report), report)

    with pytest.raises(
        BlueprintValidationError,
        match="derived by the private qualifier",
    ):
        BlueprintManifestQualificationReport(
            blueprint_id=qualification.blueprint_id,
            blueprint_fingerprint=qualification.blueprint_fingerprint,
            static_manifest_status="complete",
            layers=tuple(
                BlueprintLayerResult(
                    layer_id=layer.layer_id,
                    status="complete",
                )
                for layer in qualification.layers
            ),
        )


def test_qualification_has_no_target_generation_switch():
    report = good_report()
    blueprint = manifest(report)

    with pytest.raises(TypeError, match="unexpected keyword argument"):
        _qualify_blueprint_manifest(
            blueprint,
            report,
            target_generation_requested=True,
        )


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
        test_inventory_id="test-inventory:current",
        test_inventory_fingerprint="fp:test-inventory:current",
        model_test_alignment_report_id="alignment:current",
        model_test_alignment_report_fingerprint="fp:alignment:current",
        portable_owner_fingerprints=(),
        resources=(),
        oracles=(),
        required_resource_ids=("resource:runtime",),
        required_resource_kinds=("runtime",),
        required_oracle_ids=("oracle:save",),
    )

    qualification = _qualify_blueprint_manifest(blueprint, report)

    assert qualification.static_manifest_status == "blocked"
    assert not qualification.static_manifest_ready
    assert {finding.code for finding in qualification.static_findings} >= {
        "required_resource_missing",
        "required_oracle_missing",
    }


def test_projection_shards_exclude_source_text():
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
    payload = ({"binding_id": "binding:save"},)
    digest = fingerprint_value(list(payload))
    shard = BlueprintShard(
        shard_id=f"bindings:{digest}",
        kind="bindings",
        relative_path=f"shards/bindings-{digest.removeprefix('sha256:')}.json",
        member_ids=("binding:save",),
        payload=payload,
        content_fingerprint=digest,
    )
    projection = CanonicalBlueprintProjection(
        blueprint_fingerprint="sha256:canonical-blueprint",
        shards=(shard,),
    )
    materialized = {
        shard.relative_path: {"payload": list(shard.payload)} for shard in projection.shards
    }
    assert verify_blueprint_projection(
        projection,
        expected_blueprint_fingerprint="sha256:canonical-blueprint",
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


def test_projection_writer_preserves_prior_verified_output_on_failure(
    tmp_path, monkeypatch
):
    first_payload = ({"binding_id": "binding:first"},)
    first_digest = fingerprint_value(list(first_payload))
    first_shard = BlueprintShard(
        shard_id=f"bindings:{first_digest}",
        kind="bindings",
        relative_path=f"shards/bindings-{first_digest.removeprefix('sha256:')}.json",
        member_ids=("binding:first",),
        payload=first_payload,
        content_fingerprint=first_digest,
    )
    first_projection = CanonicalBlueprintProjection(
        blueprint_fingerprint="sha256:first-blueprint",
        shards=(first_shard,),
    )
    output_root = tmp_path / "canonical-output"
    write_canonical_blueprint_projection(first_projection, output_root)
    before = {
        path.relative_to(output_root).as_posix(): path.read_bytes()
        for path in output_root.rglob("*")
        if path.is_file()
    }

    second_payload = ({"binding_id": "binding:second"},)
    second_digest = fingerprint_value(list(second_payload))
    second_projection = CanonicalBlueprintProjection(
        blueprint_fingerprint="sha256:second-blueprint",
        shards=(
            BlueprintShard(
                shard_id=f"bindings:{second_digest}",
                kind="bindings",
                relative_path=(
                    f"shards/bindings-{second_digest.removeprefix('sha256:')}.json"
                ),
                member_ids=("binding:second",),
                payload=second_payload,
                content_fingerprint=second_digest,
            ),
        ),
    )
    monkeypatch.setattr(
        "flowguard.implementation_blueprint.verify_blueprint_projection",
        lambda *_args, **_kwargs: BlueprintProjectionVerification(
            ok=False,
            status="blocked",
            findings=(
                BlueprintFinding(
                    "forced_stage_failure",
                    "staged projection did not verify",
                    severity="blocked",
                ),
            ),
        ),
    )

    with pytest.raises(BlueprintValidationError, match="did not verify"):
        write_canonical_blueprint_projection(second_projection, output_root)

    assert before == {
        path.relative_to(output_root).as_posix(): path.read_bytes()
        for path in output_root.rglob("*")
        if path.is_file()
    }
    assert not list(tmp_path.glob(".canonical-output.staging-*"))
    assert not list(tmp_path.glob(".canonical-output.backup-*"))


def _canonical_projection(name: str) -> CanonicalBlueprintProjection:
    payload = ({"binding_id": f"binding:{name}"},)
    digest = fingerprint_value(list(payload))
    return CanonicalBlueprintProjection(
        blueprint_fingerprint=f"sha256:{name}-blueprint",
        shards=(
            BlueprintShard(
                shard_id=f"bindings:{digest}",
                kind="bindings",
                relative_path=(
                    f"shards/bindings-{digest.removeprefix('sha256:')}.json"
                ),
                member_ids=(f"binding:{name}",),
                payload=payload,
                content_fingerprint=digest,
            ),
        ),
    )


def test_projection_writer_restores_prior_tree_when_activation_race_recreates_root(
    tmp_path, monkeypatch
):
    output_root = tmp_path / "canonical-output"
    write_canonical_blueprint_projection(
        _canonical_projection("first"), output_root
    )
    before = {
        path.relative_to(output_root).as_posix(): path.read_bytes()
        for path in output_root.rglob("*")
        if path.is_file()
    }
    real_replace = os.replace

    def fail_staging_activation(source, destination):
        source_path = blueprint_module.Path(source)
        destination_path = blueprint_module.Path(destination)
        if (
            source_path.name.startswith(".canonical-output.staging-")
            and destination_path == output_root.resolve()
        ):
            output_root.mkdir()
            raise OSError("forced activation race")
        return real_replace(source, destination)

    monkeypatch.setattr(blueprint_module.os, "replace", fail_staging_activation)
    with pytest.raises(OSError, match="forced activation race"):
        write_canonical_blueprint_projection(
            _canonical_projection("second"), output_root
        )

    assert before == {
        path.relative_to(output_root).as_posix(): path.read_bytes()
        for path in output_root.rglob("*")
        if path.is_file()
    }
    assert not list(tmp_path.glob(".canonical-output.staging-*"))
    assert not list(tmp_path.glob(".canonical-output.backup-*"))


def test_projection_writer_does_not_report_cleanup_failure_as_activation_failure(
    tmp_path, monkeypatch
):
    output_root = tmp_path / "canonical-output"
    write_canonical_blueprint_projection(
        _canonical_projection("first"), output_root
    )
    real_rmtree = blueprint_module.shutil.rmtree

    def fail_backup_cleanup(path, *args, **kwargs):
        if ".canonical-output.backup-" in blueprint_module.Path(path).name:
            raise OSError("forced backup cleanup failure")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(blueprint_module.shutil, "rmtree", fail_backup_cleanup)
    with pytest.warns(RuntimeWarning, match="backup cleanup did not complete"):
        written = write_canonical_blueprint_projection(
            _canonical_projection("second"), output_root
        )

    assert written
    manifest = json.loads((output_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["blueprint_fingerprint"] == "sha256:second-blueprint"
    assert list(tmp_path.glob(".canonical-output.backup-*"))


def test_projection_writer_rejects_foreign_empty_directory_without_replacing_tree(
    tmp_path,
):
    output_root = tmp_path / "canonical-output"
    write_canonical_blueprint_projection(
        _canonical_projection("first"), output_root
    )
    foreign = output_root / "foreign-empty"
    foreign.mkdir()

    with pytest.raises(BlueprintValidationError, match="unowned"):
        write_canonical_blueprint_projection(
            _canonical_projection("second"), output_root
        )

    assert foreign.is_dir()
    manifest = json.loads((output_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["blueprint_fingerprint"] == "sha256:first-blueprint"
    assert not list(tmp_path.glob(".canonical-output.staging-*"))


def test_projection_writer_rejects_foreign_directory_symlink(tmp_path):
    output_root = tmp_path / "canonical-output"
    write_canonical_blueprint_projection(
        _canonical_projection("first"), output_root
    )
    target = tmp_path / "foreign-target"
    target.mkdir()
    link = output_root / "foreign-link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink is unavailable: {exc}")

    with pytest.raises(BlueprintValidationError, match="reparse point"):
        write_canonical_blueprint_projection(
            _canonical_projection("second"), output_root
        )

    assert link.is_symlink()
    manifest = json.loads((output_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["blueprint_fingerprint"] == "sha256:first-blueprint"


@pytest.mark.skipif(os.name != "nt", reason="junctions are a Windows reparse type")
def test_projection_writer_rejects_foreign_directory_junction(tmp_path):
    output_root = tmp_path / "canonical-output"
    write_canonical_blueprint_projection(
        _canonical_projection("first"), output_root
    )
    target = tmp_path / "junction-target"
    target.mkdir()
    junction = output_root / "foreign-junction"
    result = subprocess.run(
        ["cmd", "/d", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        pytest.skip("directory junction creation is unavailable")
    try:
        with pytest.raises(BlueprintValidationError, match="reparse point"):
            write_canonical_blueprint_projection(
                _canonical_projection("second"), output_root
            )
        manifest = json.loads(
            (output_root / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["blueprint_fingerprint"] == "sha256:first-blueprint"
    finally:
        if os.path.lexists(junction):
            os.rmdir(junction)


def test_projection_writer_revalidates_exact_tree_immediately_before_swap(
    tmp_path, monkeypatch
):
    output_root = tmp_path / "canonical-output"
    write_canonical_blueprint_projection(
        _canonical_projection("first"), output_root
    )
    real_validate = blueprint_module._validated_existing_projection_snapshot
    calls = 0

    def inject_late_foreign_file(root):
        nonlocal calls
        if blueprint_module.Path(root) == output_root.resolve():
            calls += 1
            if calls == 2:
                (output_root / "late-foreign.txt").write_text(
                    "concurrent writer", encoding="utf-8"
                )
        return real_validate(root)

    monkeypatch.setattr(
        blueprint_module,
        "_validated_existing_projection_snapshot",
        inject_late_foreign_file,
    )
    with pytest.raises(BlueprintValidationError, match="unowned"):
        write_canonical_blueprint_projection(
            _canonical_projection("second"), output_root
        )

    manifest = json.loads((output_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["blueprint_fingerprint"] == "sha256:first-blueprint"
    assert (output_root / "late-foreign.txt").read_text(encoding="utf-8") == (
        "concurrent writer"
    )
    assert not list(tmp_path.glob(".canonical-output.staging-*"))
    assert not list(tmp_path.glob(".canonical-output.backup-*"))


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


def test_affected_neighborhood_closes_shared_semantics():
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
        resources=(resource(),),
    )
    assert neighborhood.affected_binding_ids == ("binding:list", "binding:save")
    assert neighborhood.affected_model_element_ids == ("model:list", "model:save")
    assert neighborhood.affected_resource_ids == ("resource:runtime",)
