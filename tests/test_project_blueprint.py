from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from flowguard.blueprint_topology import (
    BlueprintTopologyNode,
    BlueprintTopologyRelation,
)

from flowguard.implementation_blueprint import (
    BlueprintResourceReference,
    OracleReference,
    SemanticSpecReference,
)
from flowguard.implementation_inventory import (
    IMPLEMENTATION_DISPOSITION_SCOPED_OUT,
    ImplementationFileDisposition,
    SoftwareBoundary,
    implementation_surface_id,
    implementation_surface_key,
)
from flowguard.implementation_inventory_python import (
    PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
    discover_python_implementation_surfaces,
)
from flowguard.project_blueprint import (
    ProjectBlueprintDefinition,
    ProjectBlueprintEvidence,
    ProjectBlueprintOwner,
    ProjectEvidenceArtifact,
    PortableModelMemberCatalog,
    build_project_blueprint,
    load_project_blueprint_document,
    project_blueprint_document,
)
from flowguard.source_identity import source_file_fingerprint
from flowguard.software_blueprint_readiness import (
    BehaviorCaseContract,
    generate_candidate_blueprint,
)
from flowguard.test_inventory import (
    TEST_DISPOSITION_REQUIRED,
    TestFileDisposition,
    TestNodeDisposition,
    build_project_test_inventory,
)
from flowguard.test_inventory_python import (
    PYTHON_AST_TEST_ADAPTER_ID,
    discover_python_test_file,
)


def test_external_python_project_uses_generic_read_only_builder(tmp_path: Path):
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def save(value):\n    return {'saved': value}\n", encoding="utf-8")
    source_fp = source_file_fingerprint(source)
    test_source = tmp_path / "tests" / "test_service.py"
    test_source.parent.mkdir()
    test_source.write_text(
        "from src.service import save\n\n"
        "def test_save():\n"
        "    assert save('value') == {'saved': 'value'}\n",
        encoding="utf-8",
    )
    test_file = TestFileDisposition(
        path="tests/test_service.py",
        source_fingerprint=source_file_fingerprint(test_source),
        disposition=TEST_DISPOSITION_REQUIRED,
        reason="declared current project test",
        adapter_id=PYTHON_AST_TEST_ADAPTER_ID,
    )
    discovered_tests = build_project_test_inventory(
        tmp_path,
        inventory_id="tests:external-demo:discovery",
        subject_revision="revision:one",
        test_patterns=("tests/test_*.py",),
        file_dispositions=(test_file,),
        node_dispositions=(),
        discovery_adapters={PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file},
    )
    test_node = discovered_tests.nodes[0]
    test_inventory = build_project_test_inventory(
        tmp_path,
        inventory_id="tests:external-demo",
        subject_revision="revision:one",
        test_patterns=("tests/test_*.py",),
        file_dispositions=(test_file,),
        node_dispositions=(
            TestNodeDisposition(
                test_node.pytest_nodeid,
                TEST_DISPOSITION_REQUIRED,
                reason="oracle-bearing current project test",
            ),
        ),
        discovery_adapters={PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file},
    )
    test_node = test_inventory.nodes[0]
    module_id = implementation_surface_id("src/service.py", "<module>", "module")
    save_id = implementation_surface_id("src/service.py", "save", "function")
    model_id = "model:save-service"
    semantic = SemanticSpecReference(
        semantic_spec_id="semantic:save-service",
        owner_id="owner:save-service",
        artifact_id="requirements:save-service",
        artifact_fingerprint="fp:requirements",
        covered_model_element_ids=(model_id,),
        covered_dimensions=("input", "output", "error", "order", "retry", "timeout"),
        semantics=(
            ("input", "accept one value"),
            ("output", "return a saved result containing that value"),
            ("error", "never report success when the input is rejected"),
            ("order", "not applicable: one synchronous operation"),
            ("retry", "not applicable: retry is owned by the caller"),
            ("timeout", "not applicable: no external wait"),
        ),
        provenance_fingerprints=(("requirements:save-service", "fp:requirements"),),
    )
    oracle = OracleReference(
        oracle_id="oracle:save-service",
        owner_id="owner:save-service",
        artifact_id="test:test_save",
        artifact_fingerprint="fp:test-save",
        covered_model_element_ids=(model_id,),
        covered_dimensions=("input", "output", "error", "order", "retry", "timeout"),
        semantics=(
            ("input", "exercise accepted and rejected values"),
            ("output", "assert the saved result"),
            ("error", "assert rejected values do not succeed"),
            ("order", "not applicable: one synchronous operation"),
            ("retry", "not applicable: no retry loop"),
            ("timeout", "not applicable: no timeout owner"),
        ),
    )
    behavior_block_id = f"behavior-block:{save_id}"
    case_specs = (
        ("case:save:good", "good", "accepted", ""),
        ("case:save:boundary", "boundary", "boundary", ""),
        ("case:save:bad", "bad", "rejected", "failure:rejected-input"),
    )
    checker_designs: dict[str, str] = {}
    behavior_cases: list[BehaviorCaseContract] = []
    dimensions_by_kind = {
        "good": ("input", "state", "output", "effect", "order", "completion"),
        "boundary": ("input", "state", "output", "retry", "timeout", "completion"),
        "bad": ("input", "state", "effect", "error", "decision", "completion"),
    }
    for case_id, case_kind, value, failure_id in case_specs:
        checker_id = f"checker-design:{case_id}"
        checker_designs[checker_id] = f"fp:{checker_id}"
        behavior_cases.append(
            BehaviorCaseContract(
                case_id=case_id,
                behavior_block_id=behavior_block_id,
                case_kind=case_kind,
                input_values=(("value", value),),
                initial_state=(),
                expected_output=(
                    (("return", f"saved:{value}"),) if not failure_id else ()
                ),
                expected_state=(),
                expected_effects=(),
                expected_errors=((failure_id,) if failure_id else ()),
                oracle_id=oracle.oracle_id,
                case_evidence_id=checker_id,
                case_evidence_fingerprint=checker_designs[checker_id],
                value_mode="literal",
                protected_failure_ids=((failure_id,) if failure_id else ()),
                parameter_case_id=case_id,
            )
        )
        for dimension in dimensions_by_kind[case_kind]:
            member_id = f"{checker_id}:{dimension}"
            checker_designs[member_id] = f"fp:{member_id}"
    definition = ProjectBlueprintDefinition(
        blueprint_id="blueprint:external-demo",
        inventory_id="inventory:external-demo",
        boundary=SoftwareBoundary(
            boundary_id="boundary:external-demo",
            subject_revision="revision:one",
            production_patterns=("src/**/*.py",),
            test_oracle_patterns=("tests/test_*.py",),
        ),
        file_dispositions=(
            ImplementationFileDisposition(
                path="src/service.py",
                category="production",
                content_fingerprint=source_fp,
                disposition="model_implementation",
                reason="declared current implementation",
                requires_adapter=True,
                adapter_id=PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
            ),
            ImplementationFileDisposition(
                path="tests/test_service.py",
                category="test_oracle",
                content_fingerprint=test_file.source_fingerprint,
                disposition=IMPLEMENTATION_DISPOSITION_SCOPED_OUT,
                reason="owned by the independent project test inventory",
            ),
        ),
        surface_dispositions=(
            (implementation_surface_key("src/service.py", "<module>"), "supporting"),
            (implementation_surface_key("src/service.py", "save"), "model_implementation"),
        ),
        supporting_owners=((implementation_surface_key("src/service.py", "<module>"), save_id),),
        dynamic_allowances=(),
        owners=(
            ProjectBlueprintOwner(
                model_element_id=model_id,
                owner_id="owner:save-service",
                owner_contract_id="contract:save-service",
                model_fingerprint="fp:model-save",
                owner_contract_fingerprint="fp:contract-save",
                portable_model_id="portable-model:save-service",
                portable_model_fingerprint="fp:kernel",
                portable_transition_ids=(
                    "transition:save:accepted",
                    "transition:save:rejected",
                ),
                portable_property_ids=("property:save:result",),
                portable_invariant_ids=("invariant:save:no-false-success",),
                portable_input_field_mappings=(("value", "input:value"),),
                portable_output_field_mappings=(("return", "output:return"),),
                portable_state_field_mappings=(),
                portable_assumption_ids=("assumption:value-serializable",),
                portable_guarantee_ids=("guarantee:saved-result",),
                protected_failure_ids=("failure:rejected-input",),
                implementation_surface_ids=(module_id, save_id),
                primary_surface_id=save_id,
                semantic_specs=(semantic,),
                oracles=(oracle,),
                test_evidence_fingerprints=(
                    (test_node.node_id, test_node.structure_fingerprint),
                ),
                native_evidence_fingerprints=(
                    ("check:save-service", test_file.source_fingerprint),
                ),
                behavior_accepted=True,
                behavior_acceptance_evidence_fingerprints=(
                    ("requirements:save-service", "fp:requirements"),
                    ("owner-contract", "fp:contract-save"),
                ),
                behavior_case_contracts=tuple(behavior_cases),
                checker_design_fingerprints=tuple(checker_designs.items()),
            ),
        ),
        claim_boundary="Declared software static blueprint only.",
        target_kind="software",
        observation_providers=(
            (
                PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
                ("implementation_inventory",),
            ),
            (PYTHON_AST_TEST_ADAPTER_ID, ("test_inventory",)),
            ("provider:declared-resource", ("resource_inventory",)),
        ),
        authority_providers=(
            (
                "provider:observed-model",
                ("model_authority", "model_topology"),
            ),
            (
                "provider:declared-semantics",
                ("behavior_semantics", "oracle_inventory"),
            ),
            ("provider:declared-intent", ("intent_lineage",)),
            ("provider:portable-kernel", ("portable_behavior",)),
        ),
    )
    resource = BlueprintResourceReference(
        resource_id="resource:python",
        kind="runtime",
        owner_id="owner:save-service",
        artifact_id="runtime:python",
        purpose="execute the example service",
        lifecycle_role="runtime_dependency",
        artifact_fingerprint="fp:python",
        semantics=(("requirement", "provide a compatible Python runtime"),),
    )
    evidence = ProjectBlueprintEvidence(
        observed_snapshot_id="snapshot:external-demo",
        observed_snapshot_fingerprint="fp:snapshot",
        semantic_mesh_id="mesh:external-demo",
        semantic_mesh_fingerprint="fp:mesh",
        portable_owner_fingerprints=(("portable:kernel", "fp:kernel"),),
        portable_member_catalogs=(
            PortableModelMemberCatalog(
                portable_model_id="portable-model:save-service",
                portable_model_fingerprint="fp:kernel",
                transition_ids=("transition:save:accepted", "transition:save:rejected"),
                property_ids=("property:save:result",),
                invariant_ids=("invariant:save:no-false-success",),
                input_field_ids=("input:value",),
                output_field_ids=("output:return",),
                state_field_ids=(),
                assumption_ids=("assumption:value-serializable",),
                guarantee_ids=("guarantee:saved-result",),
            ),
        ),
        resources=(resource,),
        test_inventory=test_inventory,
        topology_nodes=(
            BlueprintTopologyNode(
                node_id=model_id,
                disposition="connected",
                purpose="own the save behavior and its exact implementation surfaces",
                implementation_surface_ids=(module_id, save_id),
            ),
            BlueprintTopologyNode(
                node_id="model:external-demo",
                disposition="connected",
                purpose="consume the save result at the target-system boundary",
            ),
        ),
        topology_relations=(
            BlueprintTopologyRelation(
                relation_id="relation:save-to-system",
                producer_id=model_id,
                consumer_id="model:external-demo",
                relation_kind="child_to_parent",
                interface_mappings=(("output:saved-result", "input:saved-result"),),
                evidence_fingerprint="fp:save-topology",
                rationale="the target-system parent consumes the child save result",
            ),
        ),
        native_evidence_artifacts=(
            ProjectEvidenceArtifact(
                evidence_id="check:save-service",
                artifact_path="tests/test_service.py",
                artifact_fingerprint=test_file.source_fingerprint,
                kind="native_check",
            ),
        ),
    )
    document_path = tmp_path.parent / f"{tmp_path.name}-project-blueprint.json"
    document_path.write_text(
        json.dumps(project_blueprint_document(definition, evidence)),
        encoding="utf-8",
    )
    loaded_definition, loaded_evidence = load_project_blueprint_document(document_path)
    assert loaded_definition == definition
    assert loaded_evidence == evidence

    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    bundle = build_project_blueprint(
        tmp_path,
        definition,
        evidence,
        discovery_adapters={
            PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
        },
        test_discovery_adapters={
            PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file
        },
    )
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    assert bundle.qualification.static_status == "complete", json.dumps(bundle.to_dict())
    assert bundle.qualification.empirical_status == "not_run"
    assert bundle.qualification.deepest_proven_layer == "static_blueprint"
    assert len(bundle.binding_report.required_model_element_ids) == 1
    assert len(bundle.binding_report.semantic_specs) == 1
    assert len(bundle.binding_report.oracles) == 1
    primary = next(
        row for row in bundle.binding_report.bindings if row.implementation_surface_id == save_id
    )
    assert primary.primary and primary.relation_kind == "implements"
    assert module_id not in {
        row.implementation_surface_id for row in bundle.binding_report.bindings
    }
    assert not bundle.behavior_report.supporting_relations
    assert module_id not in bundle.behavior_report.supporting_surface_ids
    runtime_resource = next(
        row
        for row in bundle.resource_inventory.members
        if row.member_id == "resource:python"
    )
    assert runtime_resource.category_disposition == "current"
    assert runtime_resource.category_evidence_fingerprint == resource.fingerprint
    assert runtime_resource.resource_reference == resource
    assert runtime_resource.resource_reference.owner_id == "owner:save-service"
    assert runtime_resource.resource_reference.purpose == "execute the example service"
    assert runtime_resource.resource_reference.lifecycle_role == "runtime_dependency"
    assert dict(runtime_resource.resource_reference.semantics) == {
        "requirement": "provide a compatible Python runtime"
    }
    assert bundle.static_readiness.status == "blocked"
    assert bundle.topology_report.ok
    assert bundle.model_test_alignment_report.pre_code_status == "ready"
    assert (
        bundle.model_test_alignment_report.fingerprint
        != bundle.binding_report.fingerprint
    )
    affected = bundle.affected_neighborhood(affected_surface_ids=(save_id,))
    affected_objects = dict(affected.shared_objects)
    assert f"topology-index:{model_id}" in affected_objects
    assert "topology-relation:relation:save-to-system" in affected_objects
    assert f"model-test-alignment-owner:{model_id}" in affected_objects
    assert len(affected_objects) < len(bundle.normalized_shared_objects)

    undeclared_case_owner = replace(
        definition.owners[0],
        behavior_case_contracts=(),
        checker_design_fingerprints=(),
    )
    undeclared_case_bundle = build_project_blueprint(
        tmp_path,
        replace(definition, owners=(undeclared_case_owner,)),
        evidence,
        discovery_adapters={
            PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
        },
        test_discovery_adapters={
            PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file
        },
    )
    assert "behavior_case_design_missing" in {
        row.code for row in undeclared_case_bundle.behavior_report.findings
    }

    counterfeit_owner = replace(
        definition.owners[0],
        portable_transition_ids=(
            *definition.owners[0].portable_transition_ids,
            "transition:save:not-in-current-model",
        ),
    )
    counterfeit_bundle = build_project_blueprint(
        tmp_path,
        replace(definition, owners=(counterfeit_owner,)),
        evidence,
        discovery_adapters={
            PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
        },
        test_discovery_adapters={
            PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file
        },
    )
    assert "portable_member_unknown" in {
        row.code for row in counterfeit_bundle.behavior_report.findings
    }

    disconnected_evidence = replace(
        evidence,
        topology_relations=(
            replace(
                evidence.topology_relations[0],
                consumer_id="model:missing-parent",
            ),
        ),
    )
    disconnected_bundle = build_project_blueprint(
        tmp_path,
        definition,
        disconnected_evidence,
        discovery_adapters={
            PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
        },
        test_discovery_adapters={
            PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file
        },
    )
    assert not disconnected_bundle.topology_report.ok
    assert disconnected_bundle.static_readiness.status == "blocked"
    candidate = generate_candidate_blueprint(bundle.inventory)
    assert candidate.status == "incomplete"
    assert candidate.behavior_contracts
    assert all(not row.accepted for row in candidate.behavior_contracts)
    assert before == after

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "flowguard",
            "project-blueprint-audit",
            "--root",
            str(tmp_path),
            "--definition",
            str(document_path),
            "--json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["target_system_report"]["status"] == "blocked"
    assert "empirical_status" not in payload["qualification"]
    assert before == after

    stale_native = replace(
        evidence,
        native_evidence_artifacts=(
            replace(
                evidence.native_evidence_artifacts[0],
                artifact_fingerprint="sha256:" + "0" * 64,
            ),
        ),
    )
    with pytest.raises(ValueError, match="project evidence artifact is stale"):
        build_project_blueprint(
            tmp_path,
            definition,
            stale_native,
            discovery_adapters={
                PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
            },
            test_discovery_adapters={
                PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file
            },
        )

    test_source.write_text(
        "from src.service import save\n\n"
        "def test_save():\n"
        "    assert save('changed') == {'saved': 'changed'}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="test inventory is not exact-current"):
        build_project_blueprint(
            tmp_path,
            definition,
            evidence,
            discovery_adapters={
                PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
            },
            test_discovery_adapters={
                PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file
            },
        )

    assert replace(definition, target_kind="mixed").target_kind == "mixed"
