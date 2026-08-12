from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from flowguard.blueprint_topology import (
    BlueprintTopologyNode,
    BlueprintTopologyPort,
    BlueprintTopologyPortMapping,
    BlueprintTopologyRelation,
    TOPOLOGY_ROOT_SENTINEL,
)
from flowguard.hierarchy import ChildModelEvidence, ChildReattachmentContract
from flowguard.evidence_receipts import fingerprint_value
from flowguard.model_path_quality import PathQualityResult, PathQualitySubject

from flowguard.implementation_blueprint import (
    AffectedBlueprintNeighborhood,
    BlueprintResourceReference,
    OracleReference,
    PROJECT_BLUEPRINT_PROJECTION_KINDS,
    SemanticSpecReference,
    project_canonical_software_blueprint,
)
from flowguard.implementation_inventory import (
    IMPLEMENTATION_DISPOSITION_SCOPED_OUT,
    ImplementationFileDisposition,
    ImplementationInventoryFinding,
    ImplementationSurface,
    SoftwareBoundary,
    implementation_surface_id,
    implementation_surface_key,
)
from flowguard.implementation_inventory_python import (
    PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
    discover_python_implementation_surfaces,
)
from flowguard.project_blueprint import (
    PROJECT_BLUEPRINT_DEFINITION_SCHEMA,
    ProjectBlueprintError,
    ProjectBlueprintDefinition,
    ProjectBlueprintEvidence,
    ProjectBlueprintOwner,
    ProjectEvidenceArtifact,
    PortableModelMemberCatalog,
    build_project_resource_inventory,
    collect_project_blueprint_provider_results,
    freeze_project_blueprint_evidence,
    load_project_blueprint_document,
    prepare_project_blueprint,
    project_blueprint_document,
    _qualify_project_blueprint,
    _canonical_consumer_surface_ids,
    _owner_surface_contracts,
    _project_test_node_dispositions,
)
from flowguard.source_identity import source_file_fingerprint
from flowguard.software_blueprint_readiness import (
    BEHAVIOR_CASE_DIMENSIONS,
    INTENT_INVENTORY_SCHEMA,
    BehaviorCaseContract,
    BehaviorCoverageEdge,
    IntentSourceAuthority,
    ObservedResourceMember,
    PortableBehaviorBinding,
    ProjectIntentContribution,
    ProjectIntentInventory,
    generate_candidate_blueprint,
    review_static_blueprint_readiness,
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
from flowguard.target_system_blueprint import (
    ModelPathQualityBlueprintBinding,
    SOFTWARE_TARGET_PROFILE,
    TargetSystemProviderDeclaration,
)


def test_canonical_consumer_edges_do_not_guess_ambiguous_short_names():
    def surface(surface_id: str, symbol: str, *, calls=(), path=""):
        return ImplementationSurface(
            surface_id=surface_id,
            path=path or f"src/{surface_id.removeprefix('surface:')}.py",
            symbol=symbol,
            surface_kind="function",
            parent_surface_id="",
            content_fingerprint=f"sha256:content:{surface_id}",
            structure_fingerprint=f"sha256:structure:{surface_id}",
            disposition="model_implementation",
            calls=calls,
        )

    caller = surface(
        "surface:caller",
        "pkg.caller",
        calls=("pkg.target", "duplicate"),
    )
    exact_target = surface("surface:target", "pkg.target")
    ambiguous_a = surface("surface:ambiguous-a", "pkg.a.duplicate")
    ambiguous_b = surface("surface:ambiguous-b", "pkg.b.duplicate")

    consumers = _canonical_consumer_surface_ids(
        (caller, exact_target, ambiguous_a, ambiguous_b)
    )

    assert consumers[exact_target.surface_id] == (caller.surface_id,)
    assert ambiguous_a.surface_id not in consumers
    assert ambiguous_b.surface_id not in consumers


def test_canonical_consumer_edges_resolve_only_exact_local_receiver_calls():
    def surface(surface_id: str, symbol: str, *, calls=(), path="src/model.py"):
        return ImplementationSurface(
            surface_id=surface_id,
            path=path,
            symbol=symbol,
            surface_kind="function",
            parent_surface_id="",
            content_fingerprint=f"sha256:content:{surface_id}",
            structure_fingerprint=f"sha256:structure:{surface_id}",
            disposition="model_implementation",
            calls=calls,
        )

    caller = surface(
        "surface:caller",
        "Model.run",
        calls=("self._helper", "Other.build", "value.to_dict"),
    )
    helper = surface("surface:helper", "Model._helper")
    class_target = surface("surface:class-target", "Other.build")
    arbitrary_receiver = surface("surface:arbitrary", "Result.to_dict")

    consumers = _canonical_consumer_surface_ids(
        (caller, helper, class_target, arbitrary_receiver)
    )

    assert consumers[helper.surface_id] == (caller.surface_id,)
    assert consumers[class_target.surface_id] == (caller.surface_id,)
    assert arbitrary_receiver.surface_id not in consumers


def test_canonical_consumer_edges_prefer_exact_same_file_short_name():
    def surface(
        surface_id: str,
        symbol: str,
        *,
        calls=(),
        state_reads=(),
        path="src/model.py",
    ):
        return ImplementationSurface(
            surface_id=surface_id,
            path=path,
            symbol=symbol,
            surface_kind="function",
            parent_surface_id="",
            content_fingerprint=f"sha256:content:{surface_id}",
            structure_fingerprint=f"sha256:structure:{surface_id}",
            disposition="model_implementation",
            calls=calls,
            state_reads=state_reads,
        )

    caller = surface("surface:caller", "main", calls=("run_case",))
    local_target = surface("surface:local", "run_case")
    foreign_target = surface(
        "surface:foreign",
        "run_case",
        path="src/other_model.py",
    )

    consumers = _canonical_consumer_surface_ids(
        (caller, local_target, foreign_target)
    )

    assert consumers[local_target.surface_id] == (caller.surface_id,)
    assert foreign_target.surface_id not in consumers

    module_consumer = surface(
        "surface:module",
        "<module>",
        state_reads=("run_case",),
    )
    reference_consumers = _canonical_consumer_surface_ids(
        (module_consumer, local_target, foreign_target)
    )
    assert reference_consumers[local_target.surface_id] == (
        module_consumer.surface_id,
    )
    assert foreign_target.surface_id not in reference_consumers


def test_canonical_consumer_edges_resolve_exact_cross_file_import(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    package.joinpath("provider.py").write_text(
        "def run_case():\n    return True\n",
        encoding="utf-8",
    )
    package.joinpath("caller.py").write_text(
        "from pkg.provider import run_case\n\ndef main():\n    return run_case()\n",
        encoding="utf-8",
    )

    def surface(surface_id: str, path: str, symbol: str, *, calls=()):
        return ImplementationSurface(
            surface_id=surface_id,
            path=path,
            symbol=symbol,
            surface_kind="function" if symbol != "<module>" else "module",
            parent_surface_id="",
            content_fingerprint=f"sha256:content:{surface_id}",
            structure_fingerprint=f"sha256:structure:{surface_id}",
            disposition="model_implementation",
            calls=calls,
        )

    caller = surface(
        "surface:caller",
        "pkg/caller.py",
        "main",
        calls=("run_case",),
    )
    target = surface("surface:target", "pkg/provider.py", "run_case")
    target_module = surface(
        "surface:target-module",
        "pkg/provider.py",
        "<module>",
    )
    same_name = surface(
        "surface:foreign",
        "pkg/other.py",
        "run_case",
    )

    consumers = _canonical_consumer_surface_ids(
        (caller, target, target_module, same_name),
        root=tmp_path,
    )

    assert consumers[target.surface_id] == (caller.surface_id,)
    assert consumers[target_module.surface_id] == (caller.surface_id,)
    assert same_name.surface_id not in consumers


def test_canonical_consumer_edges_resolve_annotated_receiver_property(tmp_path):
    source = tmp_path / "model.py"
    source.write_text(
        "class State:\n"
        "    @property\n"
        "    def ready(self):\n"
        "        return True\n\n"
        "def terminal(state: State):\n"
        "    return state.ready\n",
        encoding="utf-8",
    )

    def surface(
        surface_id: str,
        symbol: str,
        kind: str,
        *,
        state_reads=(),
    ):
        return ImplementationSurface(
            surface_id=surface_id,
            path="model.py",
            symbol=symbol,
            surface_kind=kind,
            parent_surface_id="",
            content_fingerprint=f"sha256:content:{surface_id}",
            structure_fingerprint=f"sha256:structure:{surface_id}",
            disposition="model_implementation",
            state_reads=state_reads,
        )

    state_class = surface("surface:state", "State", "class")
    ready = surface("surface:ready", "State.ready", "method")
    terminal = surface(
        "surface:terminal",
        "terminal",
        "function",
        state_reads=("state.ready",),
    )

    consumers = _canonical_consumer_surface_ids(
        (state_class, ready, terminal),
        root=tmp_path,
    )

    assert consumers[ready.surface_id] == (terminal.surface_id,)


def _coverage_edge(
    coverage_id: str,
    behavior_block_id: str,
    test_node_id: str,
) -> BehaviorCoverageEdge:
    return BehaviorCoverageEdge(
        coverage_id=coverage_id,
        behavior_block_id=behavior_block_id,
        implementation_surface_id=f"surface:{behavior_block_id}",
        model_obligation_id=f"model:{behavior_block_id}",
        semantic_spec_id=f"semantic:{behavior_block_id}",
        semantic_content_fingerprint=f"fp:semantic:{behavior_block_id}",
        owner_contract_id=f"contract:{behavior_block_id}",
        behavior_owner_id=f"declared-edge-owner:{behavior_block_id}",
        implementation_content_fingerprint=f"fp:implementation:{behavior_block_id}",
        test_node_id=test_node_id,
        oracle_member_id=f"checker:{coverage_id}",
        oracle_member_fingerprint=f"fp:checker:{coverage_id}",
        case_id=f"case:{coverage_id}",
        case_content_fingerprint=f"fp:case:{coverage_id}",
        covered_dimensions=("input",),
        evidence_role="planned_checker",
        oracle_id=f"oracle:{behavior_block_id}",
        oracle_content_fingerprint=f"fp:oracle:{behavior_block_id}",
    )


def test_shared_test_glob_is_supporting_and_does_not_grant_coverage_ownership():
    rows = _project_test_node_dispositions(
        required_test_node_ids=("test:shared-glob",),
        coverage_edges=(
            _coverage_edge("coverage:a", "behavior:a", "planned:a"),
            _coverage_edge("coverage:b", "behavior:b", "planned:b"),
        ),
        contract_owner_by_block={
            "behavior:a": "owner:a",
            "behavior:b": "owner:b",
        },
    )
    by_node = {row.test_node_id: row for row in rows}

    assert by_node["test:shared-glob"].disposition == "supporting"
    assert by_node["test:shared-glob"].owner_ids == ()
    assert by_node["test:shared-glob"].coverage_ids == ()
    assert by_node["planned:a"].owner_ids == ("owner:a",)
    assert by_node["planned:b"].owner_ids == ("owner:b",)


def test_cross_owner_disposition_requires_exact_rows_on_one_checker_identity():
    rows = _project_test_node_dispositions(
        required_test_node_ids=("test:integration",),
        coverage_edges=(
            _coverage_edge("coverage:a", "behavior:a", "test:integration"),
            _coverage_edge("coverage:b", "behavior:b", "test:integration"),
        ),
        contract_owner_by_block={
            "behavior:a": "owner:a",
            "behavior:b": "owner:b",
        },
    )

    assert len(rows) == 1
    assert rows[0].disposition == "cross_owner_integration"
    assert rows[0].owner_ids == ("owner:a", "owner:b")
    assert rows[0].coverage_ids == ("coverage:a", "coverage:b")


def test_same_owner_behavior_contracts_are_partitioned_by_block():
    model_id = "model:shared-service"
    owner_id = "owner:shared-service"
    surface_a = ImplementationSurface(
        surface_id="surface:save",
        path="src/service.py",
        symbol="save",
        surface_kind="function",
        parent_surface_id="surface:module",
        content_fingerprint="fp:service",
        structure_fingerprint="fp:save",
        disposition="model_implementation",
        roles=("behavior",),
        parameters=("value",),
        returns_value=True,
    )
    surface_b = ImplementationSurface(
        surface_id="surface:load",
        path="src/service.py",
        symbol="load",
        surface_kind="function",
        parent_surface_id="surface:module",
        content_fingerprint="fp:service",
        structure_fingerprint="fp:load",
        disposition="model_implementation",
        roles=("behavior",),
        parameters=("key", "revision"),
        returns_value=True,
    )
    semantic = SemanticSpecReference(
        semantic_spec_id="semantic:shared-service",
        owner_id=owner_id,
        artifact_id="intent:shared-service",
        artifact_fingerprint="fp:semantic",
        source_id="intent:shared-service",
        source_owner_id="owner:intent",
        source_content_fingerprint="fp:intent",
        covered_model_element_ids=(model_id,),
        covered_dimensions=("input", "output", "error"),
        semantics=(
            ("input", "accept the declared surface inputs"),
            ("output", "return the declared surface result"),
            ("error", "preserve rejected input"),
        ),
        provenance_fingerprints=(("intent", "fp:intent"),),
    )
    oracle = OracleReference(
        oracle_id="oracle:shared-service",
        owner_id=owner_id,
        artifact_id="test:shared-service",
        artifact_fingerprint="fp:oracle",
        source_id="test:shared-service",
        source_owner_id="owner:test",
        source_content_fingerprint="fp:test",
        covered_model_element_ids=(model_id,),
        covered_dimensions=("input", "output", "error"),
        semantics=(
            ("input", "check accepted and rejected inputs"),
            ("output", "check returned values"),
            ("error", "check rejected input"),
        ),
    )

    def portable_binding(
        surface: ImplementationSurface,
        input_fields: tuple[str, ...],
    ) -> PortableBehaviorBinding:
        return PortableBehaviorBinding(
            binding_id=f"portable-binding:{surface.surface_id}",
            behavior_block_id=f"behavior-block:{surface.surface_id}",
            portable_model_id="portable-model:shared-service",
            portable_model_fingerprint="fp:portable",
            implementation_fingerprint=surface.content_fingerprint,
            transition_ids=("transition:accepted", "transition:rejected"),
            property_ids=("property:result",),
            invariant_ids=("invariant:no-false-success",),
            input_field_mappings=tuple(
                (field, f"member:{surface.surface_id}:input:{field}")
                for field in input_fields
            ),
            output_field_mappings=(
                ("return", f"member:{surface.surface_id}:output:return"),
            ),
            state_field_mappings=(),
            assumption_ids=("assumption:serializable",),
            guarantee_ids=("guarantee:result",),
            protected_failure_ids=("failure:rejected",),
            provider_fingerprints=(
                ("model", "fp:model"),
                ("surface", surface.structure_fingerprint),
            ),
        )

    def behavior_case(
        surface: ImplementationSurface,
        case_kind: str,
    ) -> BehaviorCaseContract:
        case_id = f"case:{surface.surface_id}:{case_kind}"
        checker_id = f"checker:{case_id}"
        failure_id = "failure:rejected" if case_kind == "bad" else ""
        return BehaviorCaseContract(
            case_id=case_id,
            behavior_block_id=f"behavior-block:{surface.surface_id}",
            case_kind=case_kind,
            input_values=tuple((field, case_kind) for field in surface.parameters),
            initial_state=(),
            expected_output=(
                (("return", f"result:{case_kind}"),) if not failure_id else ()
            ),
            expected_state=(),
            expected_effects=(),
            expected_errors=((failure_id,) if failure_id else ()),
            oracle_id=oracle.oracle_id,
            case_evidence_id=checker_id,
            case_evidence_fingerprint=f"fp:{checker_id}",
            value_mode="literal",
            protected_failure_ids=((failure_id,) if failure_id else ()),
            parameter_case_id=f"source:{case_kind}",
        )

    binding_a = portable_binding(surface_a, ("value",))
    binding_b = portable_binding(surface_b, ("key", "revision"))
    cases = tuple(
        behavior_case(surface, case_kind)
        for surface in (surface_a, surface_b)
        for case_kind in ("good", "boundary", "bad")
    )
    checker_designs = tuple(
        (case.case_evidence_id, case.case_evidence_fingerprint)
        for case in cases
    )
    owner = ProjectBlueprintOwner(
        model_element_id=model_id,
        owner_id=owner_id,
        owner_contract_id="contract:shared-service",
        model_fingerprint="fp:model",
        owner_contract_fingerprint="fp:contract",
        portable_model_id="portable-model:shared-service",
        portable_model_fingerprint="fp:portable",
        portable_transition_ids=("transition:accepted", "transition:rejected"),
        portable_property_ids=("property:result",),
        portable_invariant_ids=("invariant:no-false-success",),
        portable_input_field_mappings=binding_a.input_field_mappings,
        portable_output_field_mappings=binding_a.output_field_mappings,
        portable_state_field_mappings=(),
        portable_assumption_ids=("assumption:serializable",),
        portable_guarantee_ids=("guarantee:result",),
        protected_failure_ids=("failure:rejected",),
        portable_behavior_bindings=(binding_a, binding_b),
        implementation_surface_ids=(surface_a.surface_id, surface_b.surface_id),
        primary_surface_id=surface_a.surface_id,
        semantic_specs=(semantic,),
        oracles=(oracle,),
        test_evidence_fingerprints=(("test:shared-service", "fp:test"),),
        native_evidence_fingerprints=(),
        behavior_accepted=True,
        behavior_acceptance_evidence_fingerprints=(("intent", "fp:intent"),),
        behavior_case_contracts=cases,
        checker_design_fingerprints=checker_designs,
    )

    selected_a_binding, selected_a_cases = _owner_surface_contracts(
        owner, surface_a
    )
    selected_b_binding, selected_b_cases = _owner_surface_contracts(
        owner, surface_b
    )
    assert selected_a_binding == binding_a
    assert selected_b_binding == binding_b
    assert {case.case_kind for case in selected_a_cases} == {
        "good",
        "boundary",
        "bad",
    }
    assert {case.behavior_block_id for case in selected_a_cases} == {
        f"behavior-block:{surface_a.surface_id}"
    }
    assert {case.behavior_block_id for case in selected_b_cases} == {
        f"behavior-block:{surface_b.surface_id}"
    }
    assert dict(selected_b_binding.input_field_mappings) == {
        "key": "member:surface:load:input:key",
        "revision": "member:surface:load:input:revision",
    }

    foreign_case = replace(
        cases[0],
        case_id="case:foreign:good",
        behavior_block_id="behavior-block:surface:foreign",
        case_evidence_id="checker:foreign",
        case_evidence_fingerprint="fp:checker:foreign",
    )
    with pytest.raises(
        ProjectBlueprintError,
        match="block without a portable binding",
    ):
        replace(
            owner,
            behavior_case_contracts=(*owner.behavior_case_contracts, foreign_case),
            checker_design_fingerprints=(
                *owner.checker_design_fingerprints,
                (foreign_case.case_evidence_id, foreign_case.case_evidence_fingerprint),
            ),
        )

    duplicate_case = replace(
        cases[-1],
        case_id=cases[0].case_id,
    )
    with pytest.raises(ProjectBlueprintError, match="case identity is duplicated"):
        replace(
            owner,
            behavior_case_contracts=(*cases[:-1], duplicate_case),
        )

    stale_binding_b = replace(
        binding_b,
        input_field_mappings=(
            ("key", "member:surface:load:input:key"),
        ),
    )
    with pytest.raises(
        ProjectBlueprintError,
        match="portable input mapping differs from the exact behavior surface fields",
    ):
        _owner_surface_contracts(
            replace(
                owner,
                portable_behavior_bindings=(binding_a, stale_binding_b),
            ),
            surface_b,
        )


def test_external_python_project_uses_generic_read_only_builder(tmp_path: Path):
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text(
        "def save(value):\n"
        "    if value == 'rejected':\n"
        "        raise ValueError('rejected-input')\n"
        "    return {'saved': value}\n",
        encoding="utf-8",
    )
    source_fp = source_file_fingerprint(source)
    test_source = tmp_path / "tests" / "test_service.py"
    test_source.parent.mkdir()
    test_source.write_text(
        "import pytest\n\n"
        "from src.service import save\n\n"
        "def test_save():\n"
        "    assert save('value') == {'saved': 'value'}\n"
        "    with pytest.raises(ValueError, match='rejected-input'):\n"
        "        save('rejected')\n",
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
    model_fingerprint = fingerprint_value({"model": model_id})
    semantic = SemanticSpecReference(
        semantic_spec_id="semantic:save-service",
        owner_id="owner:save-service",
        artifact_id="requirements:save-service",
        artifact_fingerprint="fp:requirements",
        source_id="requirements:save-service",
        source_owner_id="owner:requirements",
        source_content_fingerprint="fp:requirements",
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
        provenance_fingerprints=(
            ("requirements:save-service", "fp:requirements"),
            ("objective:save-service", "fp:intent-source"),
        ),
    )
    oracle = OracleReference(
        oracle_id="oracle:save-service",
        owner_id="owner:save-service",
        artifact_id="test:test_save",
        artifact_fingerprint="fp:test-save",
        source_id="test-spec:save-service",
        source_owner_id="owner:test-spec",
        source_content_fingerprint="fp:test-save",
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
        for dimension in BEHAVIOR_CASE_DIMENSIONS[case_kind]:
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
                model_fingerprint=model_fingerprint,
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
                portable_behavior_bindings=(
                    PortableBehaviorBinding(
                        binding_id=f"portable-binding:{save_id}",
                        behavior_block_id=behavior_block_id,
                        portable_model_id="portable-model:save-service",
                        portable_model_fingerprint="fp:kernel",
                        implementation_fingerprint=source_fp,
                        transition_ids=(
                            "transition:save:accepted",
                            "transition:save:rejected",
                        ),
                        property_ids=("property:save:result",),
                        invariant_ids=("invariant:save:no-false-success",),
                        input_field_mappings=(("value", "input:value"),),
                        output_field_mappings=(("return", "output:return"),),
                        state_field_mappings=(),
                        assumption_ids=("assumption:value-serializable",),
                        guarantee_ids=("guarantee:saved-result",),
                        protected_failure_ids=("failure:rejected-input",),
                        provider_fingerprints=(
                            ("independent-owner-model", model_fingerprint),
                            ("implementation-observation", "fp:surface-save"),
                        ),
                    ),
                ),
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
        target_profile=SOFTWARE_TARGET_PROFILE,
        observation_providers=(
            TargetSystemProviderDeclaration(
                PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
                "observation",
                "python_ast_implementation_inventory",
                "1",
                ("implementation_inventory",),
                "Declared Python implementation inventory only.",
            ),
            TargetSystemProviderDeclaration(
                PYTHON_AST_TEST_ADAPTER_ID,
                "observation",
                "python_ast_test_inventory",
                "1",
                ("test_inventory",),
                "Declared Python test inventory only.",
            ),
            TargetSystemProviderDeclaration(
                "provider:declared-resource",
                "observation",
                "declared_resource_inventory",
                "1",
                ("resource_inventory",),
                "Declared resource inventory only.",
            ),
        ),
        authority_providers=(
            TargetSystemProviderDeclaration(
                "provider:observed-model",
                "authority",
                "observed_model_system",
                "1",
                ("model_authority", "model_topology"),
                "Observed model authority only.",
            ),
            TargetSystemProviderDeclaration(
                "provider:declared-semantics",
                "authority",
                "declared_behavior_semantics",
                "1",
                ("behavior_semantics", "oracle_inventory"),
                "Declared behavior semantics and oracles only.",
            ),
            TargetSystemProviderDeclaration(
                "provider:declared-intent",
                "authority",
                "declared_intent_lineage",
                "1",
                ("intent_lineage",),
                "Declared intent lineage only.",
            ),
            TargetSystemProviderDeclaration(
                "provider:portable-kernel",
                "authority",
                "portable_behavior_kernel",
                "1",
                ("portable_behavior",),
                "Portable behavior kernel only.",
            ),
        ),
    )
    resource = BlueprintResourceReference(
        resource_id="resource:python",
        kind="runtime",
        owner_id="owner:save-service",
        artifact_id="runtime:python",
        purpose="execute the example service",
        lifecycle_role="runtime_dependency",
        consuming_behavior_ids=(behavior_block_id,),
        consuming_model_ids=(model_id,),
        artifact_fingerprint="fp:python",
        semantics=(("requirement", "provide a compatible Python runtime"),),
    )
    scoped_resources = tuple(
        BlueprintResourceReference(
            resource_id=f"resource:{category}:not-applicable",
            kind=("verification" if category == "behavioral_oracle" else category),
            owner_id="owner:save-service",
            artifact_id=f"target-boundary:{category}",
            purpose=f"record that {category} is outside this bounded example",
            lifecycle_role="not_applicable",
            consuming_behavior_ids=(),
            consuming_model_ids=(),
            disposition="scoped_out",
            rationale=(
                "the independently declared example has no current "
                f"{category} resource"
            ),
        )
        for category in (
            "build",
            "dependency",
            "configuration",
            "schema",
            "data",
            "asset",
            "migration",
            "behavioral_oracle",
        )
    )
    observed_resource = ObservedResourceMember(
        resource_id=resource.resource_id,
        kind=resource.kind,
        owner_id=resource.owner_id,
        artifact_id=resource.artifact_id,
        subject_revision="fp:snapshot",
        current_artifact_fingerprint=str(resource.artifact_fingerprint),
        provider_id="provider:declared-resource",
        capability_id="resource_inventory",
        payload_id="resource_inventory",
    )
    scoped_observations = tuple(
        ObservedResourceMember(
            resource_id=row.resource_id,
            kind=row.kind,
            owner_id=row.owner_id,
            artifact_id=row.artifact_id,
            subject_revision="fp:snapshot",
            current_artifact_fingerprint=f"fp:{row.resource_id}",
            provider_id="provider:declared-resource",
            capability_id="resource_inventory",
            payload_id="resource_inventory",
        )
        for row in scoped_resources
    )
    intent_contribution = ProjectIntentContribution(
        contribution_id="intent:save-service",
        source_kind="explicit_change_objective",
        source_id="objective:save-service",
        source_owner_id="owner:product-intent",
        source_fingerprint="fp:intent-source",
        expectation_id="expectation:save-service",
        expectation_fingerprint="fp:intent-expectation",
        disposition="accepted",
        target_ids=(behavior_block_id, model_id, save_id),
        rationale="preserve the accepted external save-service behavior",
    )
    project_intent_inventory = ProjectIntentInventory(
        inventory_id="intent-inventory:external-demo",
        subject_revision="fp:snapshot",
        observed_subject_revision="fp:snapshot",
        contributions=(intent_contribution,),
        source_authorities=(
            IntentSourceAuthority(
                source_kind=intent_contribution.source_kind,
                source_id=intent_contribution.source_id,
                source_owner_id=intent_contribution.source_owner_id,
                subject_revision="fp:snapshot",
                current_source_fingerprint=intent_contribution.source_fingerprint,
                expectation_id=intent_contribution.expectation_id,
                current_expectation_fingerprint=(
                    intent_contribution.expectation_fingerprint
                ),
                target_ids=intent_contribution.target_ids,
                provider_id="provider:declared-intent",
                capability_id="intent_lineage",
                payload_id="intent_lineage",
            ),
        ),
        authority_provider_capabilities=(
            ("provider:declared-intent", "intent_lineage"),
        ),
        required_model_target_ids=(model_id,),
    )
    path_quality_subject = PathQualitySubject(
        model_id=model_id,
        boundary_id=f"path-boundary:{model_id}",
        model_fingerprint=model_fingerprint,
        normalized_facts_fingerprint=fingerprint_value({"facts": model_id}),
        retained_element_inventory_fingerprint=fingerprint_value(
            {"retained": model_id}
        ),
        purpose_fingerprint=fingerprint_value({"purpose": model_id}),
        intent_fingerprint=fingerprint_value({"intent": model_id}),
        obligation_fingerprint=fingerprint_value({"obligation": model_id}),
        provider_fingerprint=fingerprint_value({"provider": model_id}),
        dependency_fingerprint=fingerprint_value({"dependency": model_id}),
        code_fingerprint=source_fp,
        test_fingerprint=test_file.source_fingerprint,
        oracle_fingerprint=fingerprint_value({"oracle": model_id}),
        evidence_fingerprint=fingerprint_value({"evidence": model_id}),
        currentness_id="fp:snapshot",
    )
    path_quality_result = PathQualityResult(
        result_id=f"path-quality:{model_id}",
        subject_fingerprint=path_quality_subject.fingerprint,
        mode="lightweight",
        trigger_ids=(),
        finding_ids=(),
        candidate_ids=(),
        rewrite_rule_ids=(),
        conclusion="single_clear_path",
        unresolved_ids=(),
        selected_candidate_id="",
        selected_candidate_lane="",
        comparison_boundary_id="",
        candidate_set_fingerprint="",
        rewrite_set_fingerprint="",
        necessity_witness_set_fingerprint=fingerprint_value(
            {"necessity": model_id}
        ),
        detail_evidence_fingerprint=fingerprint_value(
            {"path-quality-detail": model_id}
        ),
        producer_id="model_maturation",
        currentness_id=path_quality_subject.currentness_id,
    )
    path_quality_binding = ModelPathQualityBlueprintBinding(
        model_element_id=model_id,
        subject_lane="observed",
        change_kind="materially_changed",
        subject=path_quality_subject,
        result=path_quality_result,
    )
    evidence = ProjectBlueprintEvidence(
        observed_snapshot_id="snapshot:external-demo",
        observed_snapshot_fingerprint="fp:snapshot",
        semantic_mesh_id="mesh:external-demo",
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
                protected_failure_ids=("failure:rejected-input",),
            ),
        ),
        resources=(resource, *scoped_resources),
        observed_resources=(observed_resource, *scoped_observations),
        intent_inventory=project_intent_inventory,
        test_inventory=test_inventory,
        topology_nodes=(
            BlueprintTopologyNode(
                node_id=model_id,
                disposition="connected",
                structural_role="child",
                purpose="own the save behavior and its exact implementation surfaces",
                structural_parent_id="model:external-demo",
                implementation_surface_ids=(module_id, save_id),
                output_ports=(
                    BlueprintTopologyPort(
                        "output:saved-result",
                        "schema:saved-result",
                        "fp:schema:saved-result",
                    ),
                ),
            ),
            BlueprintTopologyNode(
                node_id="model:external-demo",
                disposition="connected",
                structural_role="root",
                purpose="consume the save result at the target-system boundary",
                structural_parent_id=TOPOLOGY_ROOT_SENTINEL,
                input_ports=(
                    BlueprintTopologyPort(
                        "input:saved-result",
                        "schema:saved-result",
                        "fp:schema:saved-result",
                    ),
                ),
            ),
        ),
        topology_relations=(
            BlueprintTopologyRelation(
                relation_id="relation:save-to-system",
                producer_id=model_id,
                consumer_id="model:external-demo",
                relation_kind="child_to_parent",
                interface_mappings=(
                    BlueprintTopologyPortMapping(
                        "output:saved-result", "input:saved-result"
                    ),
                ),
                evidence_fingerprint="fp:save-topology",
                consumed_child_evidence_id="evidence:save-child",
                consumed_runtime_path_evidence_ids=(test_node.node_id,),
                rationale="the target-system parent consumes the child save result",
            ),
        ),
        child_models=(
            ChildModelEvidence(
                model_id=model_id,
                model_fingerprint=model_fingerprint,
                evidence_id="evidence:save-child",
                outputs_emitted=("output:saved-result",),
                validation_evidence=(test_node.node_id,),
                runtime_path_evidence_ids=(test_node.node_id,),
                evidence_tier="conformance_green",
                evidence_current=True,
            ),
        ),
        reattachment_contracts=(
            ChildReattachmentContract(
                child_model_id=model_id,
                consumed_evidence_id="evidence:save-child",
                consumed_path_quality_result_fingerprint=(
                    path_quality_result.fingerprint
                ),
                consumed_runtime_path_evidence_ids=(test_node.node_id,),
                expected_outputs=("output:saved-result",),
                rationale="the parent consumes the exact save child output",
            ),
        ),
        current_relation_evidence_fingerprints=(
            ("relation:save-to-system", "fp:save-topology"),
        ),
        current_refinement_fingerprints=(),
        current_progress_evidence_fingerprints=(),
        current_child_evidence_fingerprints=(
            ("evidence:save-child", "fp:save-child-receipt"),
        ),
        native_evidence_artifacts=(
            ProjectEvidenceArtifact(
                evidence_id="check:save-service",
                artifact_path="tests/test_service.py",
                artifact_fingerprint=test_file.source_fingerprint,
                kind="native_check",
            ),
        ),
        path_quality_bindings=(path_quality_binding,),
    )
    discovery_adapters = {
        PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
    }
    test_discovery_adapters = {
        PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file
    }

    def prepare_and_freeze(current_definition, current_evidence):
        preparation = prepare_project_blueprint(
            tmp_path,
            current_definition,
            current_evidence,
            discovery_adapters=discovery_adapters,
            test_discovery_adapters=test_discovery_adapters,
        )
        provider_results = collect_project_blueprint_provider_results(preparation)
        frozen = freeze_project_blueprint_evidence(preparation, provider_results)
        return preparation, frozen

    fake_module_block_id = f"behavior-block:{module_id}"
    fake_module_binding = replace(
        definition.owners[0].portable_behavior_bindings[0],
        binding_id=f"portable-binding:{module_id}",
        behavior_block_id=fake_module_block_id,
        input_field_mappings=(),
        output_field_mappings=(),
        state_field_mappings=(),
    )
    fake_module_cases = tuple(
        replace(
            case,
            case_id=f"case:module:{case.case_kind}",
            behavior_block_id=fake_module_block_id,
            case_evidence_id=f"checker-design:case:module:{case.case_kind}",
            case_evidence_fingerprint=(
                f"fp:checker-design:case:module:{case.case_kind}"
            ),
            parameter_case_id=f"case:module:{case.case_kind}",
        )
        for case in definition.owners[0].behavior_case_contracts
    )
    fake_module_checker_designs = tuple(
        (case.case_evidence_id, case.case_evidence_fingerprint)
        for case in fake_module_cases
    )
    fake_supporting_behavior_owner = replace(
        definition.owners[0],
        portable_behavior_bindings=(
            *definition.owners[0].portable_behavior_bindings,
            fake_module_binding,
        ),
        behavior_case_contracts=(
            *definition.owners[0].behavior_case_contracts,
            *fake_module_cases,
        ),
        checker_design_fingerprints=(
            *definition.owners[0].checker_design_fingerprints,
            *fake_module_checker_designs,
        ),
    )
    with pytest.raises(
        ProjectBlueprintError,
        match=(
            "portable binding behavior-block denominator differs from "
            "independently observed behavior surfaces"
        ),
    ) as fake_supporting_error:
        prepare_project_blueprint(
            tmp_path,
            replace(definition, owners=(fake_supporting_behavior_owner,)),
            evidence,
            discovery_adapters=discovery_adapters,
            test_discovery_adapters=test_discovery_adapters,
        )
    assert f"extra=['{fake_module_block_id}']" in str(fake_supporting_error.value)

    preparation, frozen_target_evidence = prepare_and_freeze(definition, evidence)
    document_path = tmp_path.parent / f"{tmp_path.name}-project-blueprint.json"
    document = project_blueprint_document(
        definition, evidence, frozen_target_evidence
    )
    assert document["schema_version"] == PROJECT_BLUEPRINT_DEFINITION_SCHEMA
    assert document["evidence"]["intent_inventory"]["schema_version"] == (
        INTENT_INVENTORY_SCHEMA
    )
    assert document["evidence"]["intent_inventory"][
        "required_model_target_ids"
    ] == ["model:save-service"]
    document_path.write_text(json.dumps(document), encoding="utf-8")
    loaded_definition, loaded_evidence, loaded_frozen = load_project_blueprint_document(
        document_path
    )
    assert loaded_definition == definition
    assert loaded_evidence == evidence
    assert loaded_frozen == frozen_target_evidence

    legacy_parent = dict(document)
    legacy_parent["schema_version"] = "flowguard.project_blueprint_definition.v9"
    document_path.write_text(json.dumps(legacy_parent), encoding="utf-8")
    with pytest.raises(
        ProjectBlueprintError,
        match="project blueprint document schema is not current",
    ):
        load_project_blueprint_document(document_path)

    legacy_child = json.loads(json.dumps(document))
    legacy_child["evidence"]["intent_inventory"]["schema_version"] = (
        "flowguard.project_intent_inventory.v4"
    )
    legacy_child["evidence"]["intent_inventory"].pop(
        "required_model_target_ids"
    )
    document_path.write_text(json.dumps(legacy_child), encoding="utf-8")
    with pytest.raises(
        ProjectBlueprintError,
        match="project intent inventory schema is not current",
    ):
        load_project_blueprint_document(document_path)

    missing_path_quality = json.loads(json.dumps(document))
    missing_path_quality["evidence"].pop("path_quality_bindings")
    document_path.write_text(
        json.dumps(missing_path_quality), encoding="utf-8"
    )
    with pytest.raises(
        ProjectBlueprintError,
        match="project blueprint evidence fields are not exact-current",
    ):
        load_project_blueprint_document(document_path)
    document_path.write_text(json.dumps(document), encoding="utf-8")

    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    bundle = _qualify_project_blueprint(
        preparation,
        frozen_target_evidence,
        affected_surface_ids=(save_id,),
    )
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    assert bundle.qualification.static_manifest_status == "complete", json.dumps(bundle.to_dict())
    assert bundle.qualification.static_manifest_ready
    assert (
        bundle.manifest.semantic_mesh_fingerprint
        == bundle.topology_report.fingerprint
    )
    assert "semantic_mesh_fingerprint" not in evidence.to_dict()
    assert bundle.qualification.deepest_proven_layer == "static_blueprint"
    assert len(bundle.binding_report.required_model_element_ids) == 1
    assert len(bundle.binding_report.semantic_specs) == 1
    assert len(bundle.binding_report.oracles) == 1
    primary = next(
        row for row in bundle.binding_report.bindings if row.implementation_surface_id == save_id
    )
    assert primary.primary and primary.relation_kind == "implements"
    supporting_binding = next(
        row
        for row in bundle.binding_report.bindings
        if row.implementation_surface_id == module_id
    )
    assert not supporting_binding.primary
    assert supporting_binding.delegating
    assert supporting_binding.relation_kind == "supports"
    assert supporting_binding.semantic_spec_ids == primary.semantic_spec_ids
    assert supporting_binding.oracle_ids == primary.oracle_ids
    assert supporting_binding.model_obligation_ids == primary.model_obligation_ids
    assert supporting_binding.required_dimensions == primary.required_dimensions
    assert bundle.binding_report.model_obligation_ids == (
        f"behavior-block:{save_id}",
    )
    assert set(bundle.binding_report.required_implementation_surface_ids) == {
        module_id,
        save_id,
    }
    save_contract = next(
        row
        for row in bundle.behavior_report.contracts
        if row.implementation_surface_id == save_id
    )
    assert save_contract.semantic_spec_ids == primary.semantic_spec_ids
    assert save_contract.oracle_ids == primary.oracle_ids
    assert bundle.behavior_report.supporting_surface_ids == (module_id,)
    assert len(bundle.behavior_report.supporting_relations) == 1
    supporting_relation = bundle.behavior_report.supporting_relations[0]
    assert supporting_relation.supporting_surface_id == module_id
    assert supporting_relation.behavior_block_id == f"behavior-block:{save_id}"
    assert supporting_relation.relation_kind == "delegates"
    runtime_resource = next(
        row
        for row in bundle.resource_inventory.members
        if row.member_id == "resource:python"
    )
    assert runtime_resource.category_disposition == "current"
    assert runtime_resource.category_evidence_fingerprint == observed_resource.fingerprint
    assert runtime_resource.resource_reference == resource
    assert runtime_resource.observed_resource == observed_resource
    assert runtime_resource.resource_reference.owner_id == "owner:save-service"
    assert runtime_resource.resource_reference.purpose == "execute the example service"
    assert runtime_resource.resource_reference.lifecycle_role == "runtime_dependency"
    assert dict(runtime_resource.resource_reference.semantics) == {
        "requirement": "provide a compatible Python runtime"
    }
    def resource_readiness(
        current_evidence: ProjectBlueprintEvidence,
    ):
        inventory = build_project_resource_inventory(
            definition, current_evidence
        )
        return review_static_blueprint_readiness(
            blueprint_fingerprint=preparation.manifest.fingerprint,
            behavior_report=preparation.behavior_report,
            resource_inventory=inventory,
            intent_inventory=preparation.intent_inventory,
            topology_fingerprint=preparation.topology_report.fingerprint,
            normalized_projection_fingerprint=(
                preparation.normalized_projection.fingerprint
            ),
        )

    declared_only = resource_readiness(
        replace(evidence, observed_resources=())
    )
    assert declared_only.status == "blocked"
    assert "resource_declared_but_unobserved" in {
        finding.code for finding in declared_only.findings
    }

    observed_only = resource_readiness(replace(evidence, resources=()))
    assert observed_only.status == "blocked"
    assert "resource_observed_but_undeclared" in {
        finding.code for finding in observed_only.findings
    }
    assert any(
        row.member_id == observed_resource.resource_id
        for row in build_project_resource_inventory(
            definition, replace(evidence, resources=())
        ).members
    )

    invalid_observations = (
        (
            replace(observed_resource, subject_revision="fp:older-snapshot"),
            "resource_subject_revision_stale",
        ),
        (
            replace(observed_resource, status="stale"),
            "resource_observation_not_current",
        ),
        (
            replace(observed_resource, provider_id="provider:wrong-resource"),
            "resource_observation_provider_missing",
        ),
        (
            replace(observed_resource, capability_id="test_inventory"),
            "resource_observation_capability_mismatch",
        ),
        (
            replace(observed_resource, payload_id="resource:other-payload"),
            "resource_observation_payload_mismatch",
        ),
        (
            replace(
                observed_resource,
                current_artifact_fingerprint="fp:stale-python",
            ),
            "resource_artifact_fingerprint_stale",
        ),
    )
    for invalid_observation, expected_code in invalid_observations:
        result = resource_readiness(
            replace(evidence, observed_resources=(invalid_observation,))
        )
        assert result.status in {"blocked", "stale"}
        assert expected_code in {finding.code for finding in result.findings}

    assert bundle.static_readiness.status == "ready", json.dumps(
        bundle.static_readiness.to_dict(), sort_keys=True
    )
    assert bundle.behavior_report.path_quality_bindings == (
        path_quality_binding,
    )
    assert bundle.target_system_report.path_quality_bindings == (
        path_quality_binding,
    )
    assert bundle.understanding_summary.path_quality_bindings == (
        path_quality_binding,
    )
    assert bundle.topology_report.ok
    unregistered_child_evidence = replace(
        evidence,
        current_child_evidence_fingerprints=(),
    )
    unregistered_preparation, unregistered_frozen = prepare_and_freeze(
        definition,
        unregistered_child_evidence,
    )
    unregistered_bundle = _qualify_project_blueprint(
        unregistered_preparation,
        unregistered_frozen,
    )
    assert not unregistered_bundle.topology_report.ok
    assert {
        "topology_child_evidence_binding_mismatch",
        "topology_evidence_ghost",
        "topology_evidence_owner_mismatch",
    }.issubset(
        {finding.code for finding in unregistered_bundle.topology_report.findings}
    )
    assert bundle.model_test_alignment_report.pre_code_status == "ready"
    behavior_finding_codes = {
        finding.code for finding in bundle.behavior_report.findings
    }
    assert not {
        "behavior_test_design_missing",
        "coverage_test_disposition_missing",
        "test_disposition_owner_mismatch",
    } & behavior_finding_codes
    assert bundle.behavior_report.executed_evidence_status == "not_run"
    disposition_by_node = {
        row.test_node_id: row
        for row in bundle.behavior_report.test_node_dispositions
    }
    assert disposition_by_node[test_node.node_id].disposition == "supporting"
    assert disposition_by_node[test_node.node_id].owner_ids == ()
    planned_test_node_ids = {
        case.case_evidence_id for case in behavior_cases
    }
    assert planned_test_node_ids.issubset(disposition_by_node)
    assert all(
        disposition_by_node[node_id].disposition == "behavior_coverage"
        and disposition_by_node[node_id].owner_ids == ("owner:save-service",)
        for node_id in planned_test_node_ids
    )
    assert all(
        edge.evidence_role == "planned_checker"
        and edge.test_node_id in planned_test_node_ids
        for edge in bundle.behavior_report.coverage_edges
    )
    assert all(
        row.disposition == "not_run"
        for row in bundle.behavior_report.coverage_execution_evidence
    )
    assert (
        bundle.readiness_ledger.executed_evidence_status == "not_run"
    )
    assert (
        bundle.readiness_ledger.implementation_admitted
        is bundle.understanding_summary.implementation_admitted
    )
    assert (
        bundle.model_test_alignment_report.fingerprint
        != bundle.binding_report.fingerprint
    )
    affected = bundle.affected_neighborhood(affected_surface_ids=(save_id,))
    affected_objects = dict(affected.objects)
    assert f"topology-index:{model_id}" in affected_objects
    assert "topology-relation:relation:save-to-system" in affected_objects
    assert f"topology-node:{model_id}" in affected_objects
    assert "topology-node:model:external-demo" in affected_objects
    assert f"model-test-alignment-owner:{model_id}" in affected_objects
    assert any(
        object_id.startswith(f"model-path-quality:{model_id}:")
        for object_id in affected_objects
    )
    assert affected.shard_ids
    assert len(affected_objects) < len(bundle.normalized_shared_objects)

    substituted_topology = replace(
        bundle,
        topology_report=replace(
            bundle.topology_report,
            topology_id="blueprint-topology:counterfeit",
        ),
    )
    assert not substituted_topology.ok
    assert any(
        gap.object_kind == "native_report_substitution"
        for gap in substituted_topology.readiness_ledger.gaps
    )

    undeclared_case_owner = replace(
        definition.owners[0],
        behavior_case_contracts=(),
        checker_design_fingerprints=(),
    )
    with pytest.raises(
        ProjectBlueprintError,
        match=(
            "behavior-case block denominator differs from independently observed "
            "behavior surfaces.*missing="
        ),
    ):
        prepare_and_freeze(
            replace(definition, owners=(undeclared_case_owner,)), evidence
        )

    counterfeit_owner = replace(
        definition.owners[0],
        portable_transition_ids=(
            *definition.owners[0].portable_transition_ids,
            "transition:save:not-in-current-model",
        ),
        portable_behavior_bindings=(
            replace(
                definition.owners[0].portable_behavior_bindings[0],
                transition_ids=(
                    *definition.owners[0]
                    .portable_behavior_bindings[0]
                    .transition_ids,
                    "transition:save:not-in-current-model",
                ),
            ),
        ),
    )
    counterfeit_preparation, counterfeit_frozen = prepare_and_freeze(
        replace(definition, owners=(counterfeit_owner,)), evidence
    )
    counterfeit_bundle = _qualify_project_blueprint(
        counterfeit_preparation, counterfeit_frozen
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
    disconnected_preparation, disconnected_frozen = prepare_and_freeze(
        definition, disconnected_evidence
    )
    disconnected_bundle = _qualify_project_blueprint(
        disconnected_preparation, disconnected_frozen
    )
    assert not disconnected_bundle.topology_report.ok
    assert disconnected_bundle.static_readiness.status == "blocked"

    uncovered_id = "external:workflow-transition:unowned"
    uncovered_surface = ImplementationSurface(
        surface_id=uncovered_id,
        path="src/service.py",
        symbol="workflow.submit",
        surface_kind="non_code",
        parent_surface_id="",
        content_fingerprint=source_fp,
        structure_fingerprint="fp:workflow-submit",
        disposition="model_implementation",
        roles=("workflow_step", "transition"),
        parameters=("state", "event"),
        state_writes=("state",),
        returns_value=True,
        discovery_adapter_id="adapter:synthetic-workflow",
    )
    uncovered_inventory = replace(
        preparation.inventory,
        surfaces=(*preparation.inventory.surfaces, uncovered_surface),
    )
    uncovered_preparation = prepare_project_blueprint(
        tmp_path,
        definition,
        evidence,
        discovery_adapters=discovery_adapters,
        test_discovery_adapters=test_discovery_adapters,
        implementation_inventory=uncovered_inventory,
    )
    uncovered_frozen = freeze_project_blueprint_evidence(
        uncovered_preparation,
        collect_project_blueprint_provider_results(uncovered_preparation),
    )
    uncovered_bundle = _qualify_project_blueprint(
        uncovered_preparation,
        uncovered_frozen,
    )
    assert uncovered_id in uncovered_bundle.behavior_report.required_behavior_surface_ids
    assert "behavior_contract_missing" in {
        row.code for row in uncovered_bundle.behavior_report.findings
    }

    blocked_inventory = replace(
        preparation.inventory,
        findings=(
            *preparation.inventory.findings,
            ImplementationInventoryFinding(
                "adapter_identity_mismatch",
                "the observed adapter identity differs from the frozen plan",
                path="src/service.py",
            ),
        ),
    )
    blocked_preparation = prepare_project_blueprint(
        tmp_path,
        definition,
        evidence,
        discovery_adapters=discovery_adapters,
        test_discovery_adapters=test_discovery_adapters,
        implementation_inventory=blocked_inventory,
    )
    blocked_frozen = freeze_project_blueprint_evidence(
        blocked_preparation,
        collect_project_blueprint_provider_results(blocked_preparation),
    )
    blocked_bundle = _qualify_project_blueprint(
        blocked_preparation,
        blocked_frozen,
    )
    assert not blocked_bundle.implementation_inventory_audit.ok
    assert blocked_bundle.readiness_ledger.first_gap is not None
    assert blocked_bundle.readiness_ledger.first_gap.layer == "implementation_inventory"
    assert blocked_bundle.deepest_proven_layer == "evidence_qualification"
    assert any(
        gap.object_kind == "implementation_inventory_finding"
        and gap.object_id.startswith("adapter_identity_mismatch:")
        for gap in blocked_bundle.readiness_ledger.gaps
    )
    candidate = generate_candidate_blueprint(bundle.inventory)
    assert candidate.status == "incomplete"
    assert candidate.behavior_contracts
    assert all(not row.accepted for row in candidate.behavior_contracts)
    assert before == after

    for capability_id in (
        "implementation_inventory",
        "test_inventory",
        "model_topology",
        "intent_lineage",
    ):
        provider = next(
            row
            for row in frozen_target_evidence.provider_results
            if capability_id in row.capability_ids
        )
        counterfeit = replace(
            provider,
            payload_fingerprints=tuple(
                (
                    payload_id,
                    (
                        "sha256:counterfeit-current-native-payload"
                        if payload_id == capability_id
                        else payload_fingerprint
                    ),
                )
                for payload_id, payload_fingerprint in provider.payload_fingerprints
            ),
        )
        counterfeit_results = tuple(
            counterfeit if row.provider_id == provider.provider_id else row
            for row in frozen_target_evidence.provider_results
        )
        counterfeit_frozen = freeze_project_blueprint_evidence(
            preparation,
            counterfeit_results,
        )
        counterfeit_bundle = _qualify_project_blueprint(
            preparation,
            counterfeit_frozen,
        )
        assert counterfeit_bundle.target_system_report.layers[0].status == "stale"
        assert any(
            gap.object_kind == "current_native_provider_result"
            and gap.object_id
            == f"{provider.provider_id}#payload_fingerprints:{capability_id}"
            for gap in counterfeit_bundle.readiness_ledger.gaps
        )

    provider = frozen_target_evidence.provider_results[0]

    def assert_provider_divergence(counterfeit, divergence: str) -> None:
        counterfeit_results = tuple(
            counterfeit if row.provider_id == provider.provider_id else row
            for row in frozen_target_evidence.provider_results
        )
        counterfeit_frozen = freeze_project_blueprint_evidence(
            preparation,
            counterfeit_results,
        )
        counterfeit_bundle = _qualify_project_blueprint(
            preparation,
            counterfeit_frozen,
        )
        assert not counterfeit_bundle.ok
        assert any(
            gap.object_kind == "current_native_provider_result"
            and gap.object_id == f"{provider.provider_id}#{divergence}"
            for gap in counterfeit_bundle.readiness_ledger.gaps
        )

    first_input_id, _first_input_fingerprint = provider.input_fingerprints[0]
    assert_provider_divergence(
        replace(
            provider,
            input_fingerprints=tuple(
                (
                    input_id,
                    (
                        "sha256:counterfeit-provider-input"
                        if input_id == first_input_id
                        else input_fingerprint
                    ),
                )
                for input_id, input_fingerprint in provider.input_fingerprints
            ),
        ),
        f"input_fingerprints:{first_input_id}",
    )
    first_binding = provider.capability_bindings[0]
    assert_provider_divergence(
        replace(
            provider,
            capability_bindings=(
                replace(
                    first_binding,
                    input_ids=(*first_binding.input_ids, "counterfeit:input"),
                ),
                *provider.capability_bindings[1:],
            ),
        ),
        f"capability_bindings:{first_binding.capability_id}",
    )
    assert_provider_divergence(
        replace(
            provider,
            status="incomplete",
            findings=("counterfeit provider finding",),
        ),
        "status",
    )
    assert_provider_divergence(
        replace(provider, provider_kind="counterfeit-provider-kind"),
        "provider_kind",
    )
    assert_provider_divergence(
        replace(provider, provider_version="counterfeit-provider-version"),
        "provider_version",
    )

    missing_provider_frozen = replace(
        frozen_target_evidence,
        provider_results=tuple(
            row
            for row in frozen_target_evidence.provider_results
            if row.provider_id != provider.provider_id
        ),
    )
    missing_provider_bundle = _qualify_project_blueprint(
        preparation,
        missing_provider_frozen,
    )
    assert any(
        gap.object_id == f"{provider.provider_id}#provider_result:missing"
        for gap in missing_provider_bundle.readiness_ledger.gaps
    )

    extra_provider = replace(provider, provider_id="provider:counterfeit-extra")
    extra_provider_frozen = replace(
        frozen_target_evidence,
        provider_results=(*frozen_target_evidence.provider_results, extra_provider),
    )
    extra_provider_bundle = _qualify_project_blueprint(
        preparation,
        extra_provider_frozen,
    )
    assert any(
        gap.object_id == "provider:counterfeit-extra#provider_result:extra"
        for gap in extra_provider_bundle.readiness_ledger.gaps
    )

    registry_drift_frozen = replace(
        frozen_target_evidence,
        provider_registry=replace(
            frozen_target_evidence.provider_registry,
            registry_id="provider-registry:counterfeit",
        ),
    )
    registry_drift_bundle = _qualify_project_blueprint(
        preparation,
        registry_drift_frozen,
    )
    assert any(
        gap.object_kind == "current_native_provider_registry"
        and gap.object_id.endswith("#registry_id")
        for gap in registry_drift_bundle.readiness_ledger.gaps
    )

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
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["target_system_report"]["status"] == "pass"
    assert payload["canonical_projection_complete"] is True
    assert payload["readiness_ledger"]["executed_evidence_status"] == "not_run"
    assert "empirical_status" not in payload["qualification"]
    assert before == after

    canonical_projection = project_canonical_software_blueprint(bundle)
    coverage_ids = {
        row.coverage_id for row in bundle.behavior_report.coverage_edges
    }
    referenced_coverage_ids = {
        coverage_id
        for shard_id, payload in bundle.normalized_shards
        for coverage_id in payload["coverage_ids"]
        if payload["shard_id"] == shard_id
    }
    stored_coverage_objects = {
        object_id: payload
        for object_id, payload in bundle.normalized_shared_objects
        if isinstance(payload, dict)
        and payload.get("kind") == "behavior_coverage_edge"
    }
    assert referenced_coverage_ids == coverage_ids == set(stored_coverage_objects)
    assert all(
        set(payload)
        == {
            "schema_version",
            "kind",
            "shard_id",
            "coverage_ids",
            "referenced_object_ids",
        }
        and payload["coverage_ids"] == payload["referenced_object_ids"]
        for _shard_id, payload in bundle.normalized_shards
    )
    canonical_by_kind = {
        shard.kind: shard for shard in canonical_projection.shards
    }
    exported_behavior = canonical_by_kind["behavior_model"].payload[0]
    assert "coverage_edges" not in exported_behavior
    assert set(exported_behavior["coverage_edge_fingerprints"]) == coverage_ids
    assert all(
        "coverage_edges" not in payload
        and set(payload)
        == {
            "schema_version",
            "kind",
            "shard_id",
            "coverage_ids",
            "referenced_object_ids",
        }
        for payload in canonical_by_kind["behavior_shards"].payload
    )
    exported_full_coverage = {
        row["object_id"]: row["value"]
        for row in canonical_by_kind["shared_objects"].payload
        if isinstance(row.get("value"), dict)
        and row["value"].get("kind") == "behavior_coverage_edge"
    }
    assert exported_full_coverage == stored_coverage_objects
    reused_projection = project_canonical_software_blueprint(
        bundle,
        previous_projection=canonical_projection,
    )
    assert reused_projection.fingerprint == canonical_projection.fingerprint
    assert set(reused_projection.reused_shard_ids) == {
        shard.shard_id for shard in canonical_projection.shards
    }
    affected_projection = project_canonical_software_blueprint(
        bundle,
        previous_projection=canonical_projection,
        affected_neighborhood=AffectedBlueprintNeighborhood(
            changed_member_ids=(bundle.binding_report.bindings[0].binding_id,),
            affected_binding_ids=(),
            affected_model_element_ids=(),
            affected_implementation_surface_ids=(),
            affected_semantic_spec_ids=(),
            affected_oracle_ids=(),
            affected_resource_ids=(),
        ),
    )
    assert affected_projection.fingerprint == canonical_projection.fingerprint
    assert any(
        shard_id.startswith("bindings:")
        for shard_id in affected_projection.regenerated_shard_ids
    )
    assert affected_projection.reused_shard_ids

    tampered_understanding = replace(
        bundle,
        understanding_summary=replace(
            bundle.understanding_summary,
            gap_count=bundle.understanding_summary.gap_count + 1,
        ),
    )
    assert tampered_understanding.fingerprint != bundle.fingerprint
    assert "stale:understanding_summary:target_report" in (
        tampered_understanding.canonical_projection_blockers
    )
    with pytest.raises(ValueError, match="missing export layers"):
        project_canonical_software_blueprint(tampered_understanding)
    missing_understanding = replace(bundle, understanding_summary=None)
    assert "missing:understanding_summary" in (
        missing_understanding.canonical_projection_blockers
    )

    first_object_id, first_object_payload = bundle.normalized_shared_objects[0]
    tampered_objects = replace(
        bundle,
        normalized_shared_objects=(
            (first_object_id, {"tampered": first_object_payload}),
            *bundle.normalized_shared_objects[1:],
        ),
    )
    assert tampered_objects.fingerprint != bundle.fingerprint
    assert "stale:affected_index:shared_objects" in (
        tampered_objects.canonical_projection_blockers
    )
    extra_objects = replace(
        bundle,
        normalized_shared_objects=(
            *bundle.normalized_shared_objects,
            ("unregistered:object", {"unexpected": True}),
        ),
    )
    assert extra_objects.fingerprint != bundle.fingerprint
    assert "stale:affected_index:shared_objects" in (
        extra_objects.canonical_projection_blockers
    )

    first_shard_id, first_shard_payload = bundle.normalized_shards[0]
    tampered_shards = replace(
        bundle,
        normalized_shards=(
            (first_shard_id, ({"tampered": True}, *first_shard_payload)),
            *bundle.normalized_shards[1:],
        ),
    )
    assert tampered_shards.fingerprint != bundle.fingerprint
    assert "stale:affected_index:shards" in (
        tampered_shards.canonical_projection_blockers
    )

    tampered_definition = replace(
        bundle,
        definition=replace(
            bundle.definition,
            claim_boundary=bundle.definition.claim_boundary + " (different target)",
        ),
    )
    assert "stale:target_system_report:canonical_inputs" in (
        tampered_definition.canonical_projection_blockers
    )
    tampered_project_evidence = replace(
        bundle,
        project_evidence=replace(
            bundle.project_evidence,
            observed_snapshot_fingerprint="sha256:" + "7" * 64,
        ),
    )
    assert "stale:target_system_report:canonical_inputs" in (
        tampered_project_evidence.canonical_projection_blockers
    )
    tampered_frozen_evidence = replace(
        bundle,
        frozen_target_evidence=replace(
            bundle.frozen_target_evidence,
            snapshot=replace(
                bundle.frozen_target_evidence.snapshot,
                snapshot_id=(
                    bundle.frozen_target_evidence.snapshot.snapshot_id + ":different"
                ),
            ),
        ),
    )
    assert "stale:target_system_report:canonical_inputs" in (
        tampered_frozen_evidence.canonical_projection_blockers
    )
    tampered_affected_index = replace(
        bundle,
        normalized_affected_index=replace(
            bundle.normalized_affected_index,
            blueprint_fingerprint="sha256:" + "8" * 64,
        ),
    )
    assert "stale:affected_index:canonical_inputs" in (
        tampered_affected_index.canonical_projection_blockers
    )
    tampered_logical_fingerprint = "sha256:" + "9" * 64
    tampered_normalized_projection = replace(
        bundle,
        normalized_projection=replace(
            bundle.normalized_projection,
            logical_fingerprint=tampered_logical_fingerprint,
        ),
        normalized_affected_index=replace(
            bundle.normalized_affected_index,
            logical_fingerprint=tampered_logical_fingerprint,
        ),
    )
    assert "stale:normalized_projection:canonical_inputs" in (
        tampered_normalized_projection.canonical_projection_blockers
    )

    first_member_shard_id, first_member_ids = (
        bundle.normalized_projection.shard_member_ids[0]
    )
    tampered_shard_members = (
        (first_member_shard_id, (*first_member_ids, "behavior:invented-member")),
        *bundle.normalized_projection.shard_member_ids[1:],
    )
    tampered_member_index = replace(
        bundle,
        normalized_projection=replace(
            bundle.normalized_projection,
            shard_member_ids=tampered_shard_members,
        ),
        normalized_affected_index=replace(
            bundle.normalized_affected_index,
            shard_member_ids=tampered_shard_members,
        ),
    )
    assert "stale:normalized_projection:canonical_inputs" in (
        tampered_member_index.canonical_projection_blockers
    )

    target_object_id = bundle.normalized_affected_index.target_object_id
    target_object_payload = dict(bundle.normalized_shared_objects)[target_object_id]
    changed_target_payload = {
        **target_object_payload,
        "target_profile": "tampered-profile",
    }
    changed_object_fingerprints = dict(
        bundle.normalized_affected_index.object_fingerprints
    )
    changed_object_fingerprints[target_object_id] = fingerprint_value(
        changed_target_payload
    )
    self_consistent_target_tamper = replace(
        bundle,
        normalized_shared_objects=tuple(
            (
                object_id,
                changed_target_payload
                if object_id == target_object_id
                else payload,
            )
            for object_id, payload in bundle.normalized_shared_objects
        ),
        normalized_affected_index=replace(
            bundle.normalized_affected_index,
            object_fingerprints=tuple(sorted(changed_object_fingerprints.items())),
        ),
    )
    assert "stale:affected_index:canonical_inputs" in (
        self_consistent_target_tamper.canonical_projection_blockers
    )

    assert bundle.normalized_affected_index.topology_invalidation_edges
    missing_topology_edge = replace(
        bundle,
        normalized_affected_index=replace(
            bundle.normalized_affected_index,
            topology_invalidation_edges=(
                bundle.normalized_affected_index.topology_invalidation_edges[1:]
            ),
        ),
    )
    assert "stale:affected_index:canonical_inputs" in (
        missing_topology_edge.canonical_projection_blockers
    )
    for invalid_bundle in (
        tampered_definition,
        tampered_project_evidence,
        tampered_frozen_evidence,
        tampered_affected_index,
        tampered_normalized_projection,
        tampered_member_index,
        self_consistent_target_tamper,
        missing_topology_edge,
    ):
        with pytest.raises(ValueError, match="missing export layers"):
            project_canonical_software_blueprint(invalid_bundle)

    export_root = tmp_path.parent / "external-demo-blueprint-export"
    export_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "flowguard",
            "project-blueprint-export",
            "--root",
            str(tmp_path),
            "--definition",
            str(document_path),
            "--output",
            str(export_root),
            "--json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    assert export_result.returncode != 0
    assert "invalid choice" in export_result.stderr
    assert not export_root.exists()

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
        prepare_project_blueprint(
            tmp_path,
            definition,
            stale_native,
            discovery_adapters=discovery_adapters,
            test_discovery_adapters=test_discovery_adapters,
        )

    test_source.write_text(
        "from src.service import save\n\n"
        "def test_save():\n"
        "    assert save('changed') == {'saved': 'changed'}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="test inventory is not exact-current"):
        prepare_project_blueprint(
            tmp_path,
            definition,
            evidence,
            discovery_adapters=discovery_adapters,
            test_discovery_adapters=test_discovery_adapters,
        )

    assert replace(definition, target_kind="mixed").target_kind == "mixed"
