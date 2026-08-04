"""Executable FlowGuard model for a source-independent software blueprint.

The model consumes the current implementation-inventory and
implementation-blueprint APIs and proves the static blueprint path itself.

Run: python .flowguard/implementation_blueprint/run_checks.py
Modeled block shape: Input x State -> Set(Output x State).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.evidence_receipts import fingerprint_value
from flowguard.implementation_blueprint import (
    BlueprintResourceReference,
    ModelImplementationBinding,
    ModelImplementationBindingReport,
    OracleReference,
    SemanticSpecReference,
    SEMANTIC_AUTHORITY_OBSERVED_CANDIDATE,
    SoftwareBlueprintManifest,
    SoftwareBlueprintProjection,
    project_software_blueprint,
    qualify_software_blueprint,
    review_model_implementation_bindings,
    verify_blueprint_projection,
)
from flowguard.implementation_inventory import (
    IMPLEMENTATION_DISPOSITION_MODEL,
    IMPLEMENTATION_DISPOSITION_SUPPORTING,
    IMPLEMENTATION_DISPOSITION_UNRESOLVED,
    ImplementationFileDisposition,
    ImplementationInventoryFinding,
    ImplementationSurface,
    ImplementationSurfaceInventory,
    SoftwareBoundary,
    review_implementation_surface_inventory,
)
from flowguard.software_blueprint_readiness import (
    BEHAVIOR_DIMENSIONS,
    BehaviorBlockContract,
    BehaviorCaseContract,
    BehaviorCoverageEdge,
    BehaviorDimensionContract,
    CoverageExecutionEvidence,
    NoDeclaredIntentRationale,
    ProjectIntentInventory,
    ProjectResourceInventory,
    ProjectResourceMember,
    ProjectTestNodeDisposition,
    PortableBehaviorBinding,
    SupportingSurfaceRelation,
    normalize_behavior_blueprint,
    review_behavior_blueprint,
    review_static_blueprint_readiness,
)
from flowguard.target_system_blueprint import (
    BLUEPRINT_LAYER_ORDER,
    BlueprintLayerResult,
    ProviderCapabilityBinding,
    TargetSystemDescriptor,
    TargetSystemProviderDeclaration,
    TargetSystemProviderResult,
    build_target_system_provider_registry,
    capture_target_system_snapshot,
    compile_target_system_blueprint,
)


STATIC_NOT_RUN = "not_run"
PROJECTION_NOT_RUN = "not_run"
PROJECTION_COMPLETE = "complete"
PROJECTION_BLOCKED = "blocked"


def _fingerprint(label: str) -> str:
    return fingerprint_value({"identity": label})


@dataclass(frozen=True)
class IndependentInventory:
    """Blueprint protocol view over the independent inventory authority."""

    inventory: ImplementationSurfaceInventory
    hidden_writer_ids: tuple[str, ...] = ()
    unresolved_surface_ids: tuple[str, ...] = ()
    parse_failure_ids: tuple[str, ...] = ()

    @property
    def inventory_id(self) -> str:
        return self.inventory.inventory_id

    @property
    def fingerprint(self) -> str:
        return self.inventory.inventory_fingerprint

    @property
    def surfaces(self) -> tuple[ImplementationSurface, ...]:
        return self.inventory.surfaces

    @property
    def findings(self) -> tuple[ImplementationInventoryFinding, ...]:
        return self.inventory.findings


@dataclass(frozen=True)
class BlueprintScenario:
    scenario_id: str
    inventory: IndependentInventory
    bindings: tuple[ModelImplementationBinding, ...]
    semantic_specs: tuple[SemanticSpecReference, ...]
    oracles: tuple[OracleReference, ...]
    missing_resources: bool = False
    tamper_projection: bool = False
    behavior_unaccepted: bool = False
    missing_intent: bool = False
    circular_behavior_evidence: bool = False
    expected_finding_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlueprintAction:
    action_type: str
    scenario_id: str = "complete"


@dataclass(frozen=True)
class BlueprintOutput:
    status: str


@dataclass(frozen=True)
class BlueprintState:
    scenario_id: str = ""
    phase: str = "start"
    inventory_status: str = STATIC_NOT_RUN
    binding_status: str = STATIC_NOT_RUN
    static_status: str = STATIC_NOT_RUN
    behavior_status: str = STATIC_NOT_RUN
    readiness_status: str = STATIC_NOT_RUN
    target_system_status: str = STATIC_NOT_RUN
    projection_status: str = PROJECTION_NOT_RUN
    finding_codes: tuple[str, ...] = ()
    done_claim: str = "none"
    claim_text: str = ""

    def ready_for_done(self) -> bool:
        return (
            self.inventory_status == "complete"
            and self.binding_status == "complete"
            and self.static_status == "complete"
            and self.behavior_status == "complete"
            and self.readiness_status == "ready"
            and self.target_system_status == "pass"
            and self.projection_status == PROJECTION_COMPLETE
            and not self.finding_codes
        )


@dataclass(frozen=True)
class BlueprintAssertionMember:
    assertion_id: str
    structure_fingerprint: str


@dataclass(frozen=True)
class BlueprintTestNode:
    node_id: str
    assertions: tuple[BlueprintAssertionMember, ...]


MODEL_ELEMENT_ID = "model:save-record"
SURFACE_ID = "surface:save-record"
HELPER_SURFACE_ID = "surface:normalize-record"
HIDDEN_WRITER_SURFACE_ID = "surface:hidden-writer"
SEMANTIC_SPEC_ID = "semantic:save-record"
ORACLE_ID = "oracle:save-record"
OWNER_CONTRACT_ID = "contract:save-record"
RESOURCE_ID = "resource:python-runtime"

CURRENT_MODEL_FINGERPRINT = _fingerprint(MODEL_ELEMENT_ID)
CURRENT_CONTRACT_FINGERPRINT = _fingerprint(OWNER_CONTRACT_ID)
CURRENT_SEMANTIC_FINGERPRINT = _fingerprint(SEMANTIC_SPEC_ID)
CURRENT_ORACLE_FINGERPRINT = _fingerprint(ORACLE_ID)
CURRENT_SURFACE_FINGERPRINT = _fingerprint(SURFACE_ID)
CURRENT_HELPER_FINGERPRINT = _fingerprint(HELPER_SURFACE_ID)
CURRENT_RUNTIME_FINGERPRINT = _fingerprint(RESOURCE_ID)
CURRENT_SNAPSHOT_FINGERPRINT = _fingerprint("snapshot:observed-current")
CURRENT_MESH_FINGERPRINT = _fingerprint("mesh:semantic-current")
CURRENT_PORTABLE_OWNER_FINGERPRINT = _fingerprint("portable:model-system")
CURRENT_TEST_FINGERPRINT = _fingerprint("test:save-record")
CURRENT_TEST_INVENTORY_FINGERPRINT = _fingerprint("test-inventory:current")
CURRENT_ALIGNMENT_FINGERPRINT = _fingerprint("model-test-alignment:current")


def _surface(
    surface_id: str = SURFACE_ID,
    *,
    symbol: str = "save_record",
    surface_kind: str = "function",
    disposition: str = IMPLEMENTATION_DISPOSITION_MODEL,
    owning_surface_id: str = "",
    roles: tuple[str, ...] = ("effect_writer", "state_writer"),
    state_writes: tuple[str, ...] = ("record:last",),
    side_effect_candidates: tuple[str, ...] = ("write_record",),
) -> ImplementationSurface:
    content_fingerprint = (
        CURRENT_SURFACE_FINGERPRINT
        if surface_id == SURFACE_ID
        else _fingerprint(surface_id)
    )
    return ImplementationSurface(
        surface_id=surface_id,
        path="src/app.py",
        symbol=symbol,
        surface_kind=surface_kind,
        parent_surface_id="",
        content_fingerprint=content_fingerprint,
        structure_fingerprint=_fingerprint(f"structure:{surface_id}"),
        disposition=disposition,
        owning_surface_id=owning_surface_id,
        roles=roles,
        parameters=("value",) if surface_id == SURFACE_ID else (),
        calls=("write_record",) if surface_id == SURFACE_ID else (),
        state_writes=state_writes,
        side_effect_candidates=side_effect_candidates,
        returns_value=surface_id == SURFACE_ID,
        line_start=1,
        line_end=10,
        discovery_adapter_id="python_ast_v1",
    )


def _helper(*, owner: str = SURFACE_ID) -> ImplementationSurface:
    return ImplementationSurface(
        surface_id=HELPER_SURFACE_ID,
        path="src/app.py",
        symbol="_normalize_record",
        surface_kind="helper",
        parent_surface_id="",
        content_fingerprint=CURRENT_HELPER_FINGERPRINT,
        structure_fingerprint=_fingerprint(f"structure:{HELPER_SURFACE_ID}"),
        disposition=IMPLEMENTATION_DISPOSITION_SUPPORTING,
        owning_surface_id=owner,
        roles=("helper",),
        parameters=("value",),
        returns_value=True,
        line_start=12,
        line_end=14,
        discovery_adapter_id="python_ast_v1",
    )


def _inventory(
    scenario_id: str,
    *,
    surfaces: tuple[ImplementationSurface, ...] | None = None,
    findings: tuple[ImplementationInventoryFinding, ...] = (),
    extra_files: tuple[ImplementationFileDisposition, ...] = (),
    hidden_writer_ids: tuple[str, ...] = (),
    parse_failure_ids: tuple[str, ...] = (),
) -> IndependentInventory:
    file_dispositions = (
        ImplementationFileDisposition(
            path="src/app.py",
            category="production",
            content_fingerprint=_fingerprint("file:src/app.py"),
            disposition=IMPLEMENTATION_DISPOSITION_MODEL,
            reason="production implementation",
            requires_adapter=True,
            adapter_id="python_ast_v1",
        ),
        *extra_files,
    )
    inventory = ImplementationSurfaceInventory(
        inventory_id=f"inventory:{scenario_id}",
        boundary=SoftwareBoundary(
            boundary_id="boundary:implementation-blueprint",
            subject_revision=_fingerprint(f"revision:{scenario_id}"),
            production_patterns=("src/**/*.py",),
            config_patterns=("config/*.json",),
        ),
        manifest_fingerprint=_fingerprint(f"manifest:{scenario_id}"),
        file_dispositions=tuple(file_dispositions),
        surfaces=surfaces if surfaces is not None else (_surface(), _helper()),
        findings=findings,
        claim_boundary=(
            "Static implementation discovery for the bounded source inventory only; "
            "model, test, intent, and resource bindings remain separate authorities."
        ),
    )
    return IndependentInventory(
        inventory=inventory,
        hidden_writer_ids=hidden_writer_ids,
        parse_failure_ids=parse_failure_ids,
    )


def _semantic_spec() -> SemanticSpecReference:
    return SemanticSpecReference(
        semantic_spec_id=SEMANTIC_SPEC_ID,
        owner_id="owner:model",
        artifact_id="artifact:semantic-save-record",
        artifact_fingerprint=CURRENT_SEMANTIC_FINGERPRINT,
        covered_model_element_ids=(MODEL_ELEMENT_ID,),
        covered_dimensions=("error", "input", "output", "state_effect"),
        semantics=(
            ("error", "invalid input produces a typed validation error"),
            ("input", "one record value enters the save operation"),
            ("output", "the normalized record value is returned"),
            ("state_effect", "record:last is written before write_record publishes"),
        ),
        provenance_fingerprints=(("requirements:save-record", CURRENT_MODEL_FINGERPRINT),),
    )


def _oracle() -> OracleReference:
    return OracleReference(
        oracle_id=ORACLE_ID,
        owner_id="owner:test",
        artifact_id="artifact:oracle-save-record",
        artifact_fingerprint=CURRENT_ORACLE_FINGERPRINT,
        covered_model_element_ids=(MODEL_ELEMENT_ID,),
        covered_dimensions=("error", "input", "output", "state_effect"),
        semantics=(
            ("error", "invalid values are rejected with the declared error"),
            ("input", "the oracle supplies one bounded record value"),
            ("output", "the observed result equals the normalized value"),
            ("state_effect", "state and publish effects match the declared order"),
        ),
    )


def _binding(
    binding_id: str = "binding:save-record",
    *,
    semantic_spec_ids: tuple[str, ...] = (SEMANTIC_SPEC_ID,),
    oracle_ids: tuple[str, ...] = (ORACLE_ID,),
    implementation_fingerprint: str = CURRENT_SURFACE_FINGERPRINT,
    test_evidence_ids: tuple[str, ...] = ("test:save-record",),
) -> ModelImplementationBinding:
    return ModelImplementationBinding(
        binding_id=binding_id,
        model_element_id=MODEL_ELEMENT_ID,
        implementation_surface_id=SURFACE_ID,
        relation_kind="implements",
        owner_contract_id=OWNER_CONTRACT_ID,
        semantic_spec_ids=semantic_spec_ids,
        oracle_ids=oracle_ids,
        required_dimensions=("error", "input", "output", "state_effect"),
        test_evidence_ids=test_evidence_ids,
        test_evidence_fingerprints=(
            (("test:save-record", CURRENT_TEST_FINGERPRINT),)
            if test_evidence_ids
            else ()
        ),
        primary=True,
        model_fingerprint=CURRENT_MODEL_FINGERPRINT,
        implementation_fingerprint=implementation_fingerprint,
        owner_contract_fingerprint=CURRENT_CONTRACT_FINGERPRINT,
    )


def _scenarios() -> dict[str, BlueprintScenario]:
    semantic = (_semantic_spec(),)
    oracles = (_oracle(),)
    base_binding = (_binding(),)

    omitted_file = ImplementationFileDisposition(
        path="config/app.json",
        category="config",
        content_fingerprint=_fingerprint("file:config/app.json"),
        disposition=IMPLEMENTATION_DISPOSITION_UNRESOLVED,
        reason="missing explicit file disposition",
    )
    parse_finding = ImplementationInventoryFinding(
        "python_parse_failure",
        "Python source could not be parsed into a finite surface inventory.",
        path="src/app.py",
    )
    dynamic_finding = ImplementationInventoryFinding(
        "dynamic_python_surface",
        "Dynamic dispatch leaves the called implementation surface uncertain.",
        path="src/app.py",
        surface_id=SURFACE_ID,
    )
    hidden_writer = _surface(
        HIDDEN_WRITER_SURFACE_ID,
        symbol="_write_hidden_state",
        roles=("effect_writer", "state_writer"),
        state_writes=("hidden:last",),
        side_effect_candidates=("publish_hidden",),
    )

    return {
        "complete": BlueprintScenario(
            "complete", _inventory("complete"), base_binding, semantic, oracles
        ),
        "omitted_file": BlueprintScenario(
            "omitted_file",
            _inventory("omitted-file", extra_files=(omitted_file,)),
            base_binding,
            semantic,
            oracles,
            expected_finding_codes=("unresolved_file_disposition",),
        ),
        "parse_failure": BlueprintScenario(
            "parse_failure",
            _inventory(
                "parse-failure",
                findings=(parse_finding,),
                parse_failure_ids=("src/app.py",),
            ),
            base_binding,
            semantic,
            oracles,
            expected_finding_codes=("python_parse_failure",),
        ),
        "dynamic_uncertainty": BlueprintScenario(
            "dynamic_uncertainty",
            _inventory("dynamic-uncertainty", findings=(dynamic_finding,)),
            base_binding,
            semantic,
            oracles,
            expected_finding_codes=("dynamic_python_surface",),
        ),
        "orphan_helper": BlueprintScenario(
            "orphan_helper",
            _inventory("orphan-helper", surfaces=(_surface(), _helper(owner=""))),
            base_binding,
            semantic,
            oracles,
            expected_finding_codes=("missing_supporting_owner",),
        ),
        "hidden_writer_effect": BlueprintScenario(
            "hidden_writer_effect",
            _inventory(
                "hidden-writer",
                surfaces=(_surface(), _helper(), hidden_writer),
                hidden_writer_ids=(HIDDEN_WRITER_SURFACE_ID,),
            ),
            base_binding,
            semantic,
            oracles,
            expected_finding_codes=(
                "hidden_state_or_effect_writer",
                "unbound_behavior_surface",
            ),
        ),
        "duplicate_primary": BlueprintScenario(
            "duplicate_primary",
            _inventory("duplicate-primary"),
            (_binding("binding:primary-a"), _binding("binding:primary-b")),
            semantic,
            oracles,
            expected_finding_codes=("duplicate_primary_implementation",),
        ),
        "path_only_binding": BlueprintScenario(
            "path_only_binding",
            _inventory("path-only-binding"),
            (_binding(semantic_spec_ids=(), oracle_ids=()),),
            (),
            (),
            expected_finding_codes=(
                "oracle_dimensions_incomplete",
                "semantic_dimensions_incomplete",
            ),
        ),
        "source_observation_semantics": BlueprintScenario(
            "source_observation_semantics",
            _inventory("source-observation-semantics"),
            base_binding,
            (
                replace(
                    _semantic_spec(),
                    authority_kind=SEMANTIC_AUTHORITY_OBSERVED_CANDIDATE,
                    provenance_fingerprints=(),
                ),
            ),
            oracles,
            expected_finding_codes=("source_observation_not_independent",),
        ),
        "missing_exact_test": BlueprintScenario(
            "missing_exact_test",
            _inventory("missing-exact-test"),
            (_binding(test_evidence_ids=()),),
            semantic,
            oracles,
            expected_finding_codes=("model_test_binding_missing",),
        ),
        "stale_fingerprint": BlueprintScenario(
            "stale_fingerprint",
            _inventory("stale-fingerprint"),
            (_binding(implementation_fingerprint=_fingerprint("surface:previous")),),
            semantic,
            oracles,
            expected_finding_codes=("stale_implementation_binding",),
        ),
        "missing_resource": BlueprintScenario(
            "missing_resource",
            _inventory("missing-resource"),
            base_binding,
            semantic,
            oracles,
            missing_resources=True,
            expected_finding_codes=(
                "required_resource_kind_missing",
                "required_resource_missing",
            ),
        ),
        "tampered_shard": BlueprintScenario(
            "tampered_shard",
            _inventory("tampered-shard"),
            base_binding,
            semantic,
            oracles,
            tamper_projection=True,
            expected_finding_codes=("projection_shard_tampered",),
        ),
        "behavior_contract_unaccepted": BlueprintScenario(
            "behavior_contract_unaccepted",
            _inventory("behavior-contract-unaccepted"),
            base_binding,
            semantic,
            oracles,
            behavior_unaccepted=True,
            expected_finding_codes=("behavior_contract_unaccepted",),
        ),
        "intent_inventory_missing": BlueprintScenario(
            "intent_inventory_missing",
            _inventory("intent-inventory-missing"),
            base_binding,
            semantic,
            oracles,
            missing_intent=True,
            expected_finding_codes=("intent_inventory_incomplete",),
        ),
        "circular_behavior_evidence": BlueprintScenario(
            "circular_behavior_evidence",
            _inventory("circular-behavior-evidence"),
            base_binding,
            semantic,
            oracles,
            circular_behavior_evidence=True,
            expected_finding_codes=(
                "same_source_semantic_oracle_circularity",
            ),
        ),
    }


SCENARIOS = _scenarios()
BAD_SCENARIO_IDS = tuple(
    scenario_id for scenario_id in SCENARIOS if scenario_id != "complete"
)


def _binding_report(scenario: BlueprintScenario) -> ModelImplementationBindingReport:
    return review_model_implementation_bindings(
        scenario.inventory,
        required_model_element_ids=(MODEL_ELEMENT_ID,),
        bindings=scenario.bindings,
        semantic_specs=scenario.semantic_specs,
        oracles=scenario.oracles,
        current_model_fingerprints={MODEL_ELEMENT_ID: CURRENT_MODEL_FINGERPRINT},
        current_contract_fingerprints={
            OWNER_CONTRACT_ID: CURRENT_CONTRACT_FINGERPRINT
        },
        current_semantic_spec_fingerprints={
            reference.semantic_spec_id: reference.artifact_fingerprint
            for reference in scenario.semantic_specs
        },
        current_oracle_fingerprints={
            reference.oracle_id: reference.artifact_fingerprint
            for reference in scenario.oracles
        },
        current_test_evidence_fingerprints={
            "test:save-record": CURRENT_TEST_FINGERPRINT
        },
    )


def _manifest(
    scenario: BlueprintScenario,
    report: ModelImplementationBindingReport,
) -> SoftwareBlueprintManifest:
    resources = () if scenario.missing_resources else (
        BlueprintResourceReference(
            resource_id=RESOURCE_ID,
            kind="runtime",
            owner_id="owner:runtime",
            artifact_id="artifact:python-runtime",
            purpose="execute the declared blueprint entrypoint and dependencies",
            lifecycle_role="runtime_dependency",
            artifact_fingerprint=CURRENT_RUNTIME_FINGERPRINT,
            semantics=(
                (
                    "runtime_contract",
                    "A current Python runtime executes the blueprint entrypoint and dependencies.",
                ),
            ),
        ),
    )
    return SoftwareBlueprintManifest(
        blueprint_id=f"blueprint:{scenario.scenario_id}",
        observed_snapshot_id="snapshot:observed-current",
        observed_snapshot_fingerprint=CURRENT_SNAPSHOT_FINGERPRINT,
        inventory_id=report.inventory_id,
        inventory_fingerprint=report.inventory_fingerprint,
        binding_report_id=f"binding-report:{scenario.scenario_id}",
        binding_report_fingerprint=report.fingerprint,
        semantic_mesh_id="mesh:semantic-current",
        semantic_mesh_fingerprint=CURRENT_MESH_FINGERPRINT,
        test_inventory_id="test-inventory:current",
        test_inventory_fingerprint=CURRENT_TEST_INVENTORY_FINGERPRINT,
        model_test_alignment_report_id="model-test-alignment:current",
        model_test_alignment_report_fingerprint=CURRENT_ALIGNMENT_FINGERPRINT,
        portable_owner_fingerprints=(
            ("portable:model-system", CURRENT_PORTABLE_OWNER_FINGERPRINT),
        ),
        resources=resources,
        oracles=scenario.oracles,
        required_resource_ids=(RESOURCE_ID,),
        required_resource_kinds=("runtime",),
        required_oracle_ids=(ORACLE_ID,),
    )


def _projection_verification(
    scenario: BlueprintScenario,
    manifest: SoftwareBlueprintManifest,
    report: ModelImplementationBindingReport,
):
    projection = project_software_blueprint(
        manifest,
        report,
        implementation_inventory=scenario.inventory,
    )
    materialized = {
        shard.relative_path: {"payload": list(shard.payload)}
        for shard in projection.shards
    }
    if scenario.tamper_projection:
        target = projection.shards[-1]
        materialized[target.relative_path] = {"payload": [{"tampered": True}]}
    return verify_blueprint_projection(
        projection,
        expected_blueprint_fingerprint=manifest.fingerprint,
        expected_projection_fingerprint=projection.fingerprint,
        materialized_shards=materialized,
    )


def _behavior_readiness(
    scenario: BlueprintScenario,
    manifest: SoftwareBlueprintManifest,
    binding_report: ModelImplementationBindingReport,
):
    dimensions = tuple(
        BehaviorDimensionContract(
            dimension=dimension,
            disposition=(
                "modeled"
                if dimension in {"input", "state", "output", "effect", "error", "completion"}
                else "not_applicable"
            ),
            semantics=f"the save-record contract declares exact {dimension} behavior",
            rationale="the independently declared semantic and oracle contract owns this dimension",
            provenance_fingerprints=(("model-purpose", CURRENT_MODEL_FINGERPRINT),),
            semantic_rule_ids=(f"semantic-rule:save-record:{dimension}",),
            applicability_surface_ids=(SURFACE_ID,),
        )
        for dimension in BEHAVIOR_DIMENSIONS
    )
    accepted = not scenario.behavior_unaccepted
    acceptance_evidence = (
        (("source-observation", CURRENT_SURFACE_FINGERPRINT),)
        if scenario.circular_behavior_evidence
        else (("model-purpose", CURRENT_MODEL_FINGERPRINT),)
    ) if accepted else ()
    contract = BehaviorBlockContract(
        behavior_block_id="behavior:save-record",
        implementation_surface_id=SURFACE_ID,
        model_element_id=MODEL_ELEMENT_ID,
        owner_contract_id=OWNER_CONTRACT_ID,
        owner_id="owner:model",
        function_relation="Input x State -> Set(Output x State)",
        dimensions=dimensions,
        semantic_spec_ids=(SEMANTIC_SPEC_ID,),
        oracle_ids=(ORACLE_ID,),
        portable_binding_ids=("portable:save-record",),
        protected_failure_ids=("failure:invalid-record",),
        accepted=accepted,
        acceptance_evidence_fingerprints=acceptance_evidence,
        source_fingerprint=CURRENT_SURFACE_FINGERPRINT,
    )
    portable = PortableBehaviorBinding(
        binding_id="portable:save-record",
        behavior_block_id=contract.behavior_block_id,
        portable_model_id="portable:model-system",
        portable_model_fingerprint=CURRENT_PORTABLE_OWNER_FINGERPRINT,
        implementation_fingerprint=CURRENT_SURFACE_FINGERPRINT,
        transition_ids=("transition:save-record:write",),
        property_ids=("property:save-record:contract",),
        invariant_ids=("invariant:save-record:contract",),
        input_field_mappings=(("value", "input:value"),),
        output_field_mappings=(("return", "output:normalized-value"),),
        state_field_mappings=(("record:last", "state:last-record"),),
        assumption_ids=("assumption:record-valid-or-rejected",),
        guarantee_ids=("guarantee:normalized-or-typed-error",),
        protected_failure_ids=("failure:invalid-record",),
        provider_fingerprints=(("model-purpose", CURRENT_MODEL_FINGERPRINT),),
    )
    cases = (
        BehaviorCaseContract(
            "case:save-record:good",
            contract.behavior_block_id,
            "good",
            (("value", "record:valid"),),
            (("record:last", "record:previous"),),
            (("return", "record:normalized-valid"),),
            (("record:last", "record:normalized-valid"),),
            ("write_record",),
            (),
            ORACLE_ID,
            "assertion:save-record",
            CURRENT_TEST_FINGERPRINT,
            "literal",
        ),
        BehaviorCaseContract(
            "case:save-record:boundary",
            contract.behavior_block_id,
            "boundary",
            (("value", "record:minimally-valid"),),
            (("record:last", "record:previous"),),
            (("return", "record:normalized-minimal"),),
            (("record:last", "record:normalized-minimal"),),
            ("write_record",),
            (),
            ORACLE_ID,
            "assertion:save-record",
            CURRENT_TEST_FINGERPRINT,
            "literal",
        ),
        BehaviorCaseContract(
            "case:save-record:bad",
            contract.behavior_block_id,
            "bad",
            (("value", "record:invalid"),),
            (("record:last", "record:previous"),),
            (),
            (("record:last", "record:previous"),),
            (),
            ("failure:invalid-record",),
            ORACLE_ID,
            "assertion:save-record",
            CURRENT_TEST_FINGERPRINT,
            "literal",
            ("failure:invalid-record",),
        ),
    )
    planned_checker_fingerprints: dict[str, str] = {}
    exact_cases: list[BehaviorCaseContract] = []
    for case in cases:
        checker_id = f"checker-design:{case.case_id}"
        checker_fingerprint = _fingerprint(checker_id)
        planned_checker_fingerprints[checker_id] = checker_fingerprint
        exact_cases.append(
            replace(
                case,
                case_evidence_id=checker_id,
                case_evidence_fingerprint=checker_fingerprint,
                parameter_case_id=case.case_id,
            )
        )
    cases = tuple(exact_cases)
    dimensions_by_case_kind = {
        "good": ("input", "state", "output", "effect", "order", "completion"),
        "boundary": ("input", "state", "output", "retry", "timeout", "completion"),
        "bad": ("input", "state", "effect", "error", "decision", "completion"),
    }
    coverage_rows: list[BehaviorCoverageEdge] = []
    for case in cases:
        for dimension in dimensions_by_case_kind[case.case_kind]:
            member_id = f"{case.case_evidence_id}:{dimension}"
            member_fingerprint = _fingerprint(member_id)
            planned_checker_fingerprints[member_id] = member_fingerprint
            coverage_rows.append(
                BehaviorCoverageEdge(
                    coverage_id=f"coverage:save-record:{case.case_kind}:{dimension}",
                    behavior_block_id=contract.behavior_block_id,
                    implementation_surface_id=SURFACE_ID,
                    model_obligation_id=MODEL_ELEMENT_ID,
                    semantic_spec_id=SEMANTIC_SPEC_ID,
                    owner_contract_id=OWNER_CONTRACT_ID,
                    test_node_id="test:save-record",
                    oracle_member_id=member_id,
                    oracle_member_fingerprint=member_fingerprint,
                    case_id=case.case_id,
                    covered_dimensions=(dimension,),
                    evidence_role="planned_checker",
                    oracle_id=ORACLE_ID,
                )
            )
    coverage = tuple(coverage_rows)
    execution = tuple(
        CoverageExecutionEvidence(
            row.coverage_id,
            "owner:test-save-record",
            "not_run",
        )
        for row in coverage
    )
    test_node = BlueprintTestNode(
        "test:save-record",
        (BlueprintAssertionMember("assertion:save-record", CURRENT_TEST_FINGERPRINT),),
    )
    behavior_report = review_behavior_blueprint(
        inventory_fingerprint=scenario.inventory.fingerprint,
        required_behavior_surface_ids=(SURFACE_ID,),
        supporting_surface_ids=(HELPER_SURFACE_ID,),
        contracts=(contract,),
        portable_bindings=(portable,),
        case_contracts=cases,
        supporting_relations=(
            SupportingSurfaceRelation(
                HELPER_SURFACE_ID,
                contract.behavior_block_id,
                "calls",
                "supporting-edge:normalize-record",
                CURRENT_HELPER_FINGERPRINT,
                "the pure normalizer helper has this unique behavior owner",
            ),
        ),
        coverage_edges=coverage,
        coverage_execution_evidence=execution,
        test_node_dispositions=(
            ProjectTestNodeDisposition(
                "test:save-record",
                "behavior_coverage",
                ("owner:model",),
                tuple(row.coverage_id for row in coverage),
                "the admitted exact test belongs to the one save-record block",
            ),
        ),
        required_test_node_ids=("test:save-record",),
        test_nodes=(test_node,),
        planned_checker_fingerprints=planned_checker_fingerprints,
        expected_portable_fingerprints={
            "portable:model-system": CURRENT_PORTABLE_OWNER_FINGERPRINT
        },
        supporting_surface_fingerprints={
            HELPER_SURFACE_ID: CURRENT_HELPER_FINGERPRINT
        },
    )
    resource_members = tuple(
        ProjectResourceMember(
            member_id=f"resource:{category}",
            category=category,
            category_disposition=(
                "scoped_out" if category == "external_service" else "current"
            ),
            category_evidence_fingerprint=_fingerprint(f"category:{category}"),
            resource_reference=BlueprintResourceReference(
                resource_id=f"resource:{category}",
                kind=("verification" if category == "behavioral_oracle" else category),
                owner_id="owner:save-record",
                artifact_id=f"artifact:{category}",
                purpose=f"preserve the fixture {category} blueprint obligation",
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
                    else _fingerprint(f"resource:{category}")
                ),
                rationale=(
                    "the bounded fixture declares no external service"
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
                "the bounded fixture declares no external service"
                if category == "external_service"
                else "the independent fixture inventory admits this current resource"
            ),
        )
        for category in (
            "build", "runtime", "dependency", "configuration", "schema",
            "data", "asset", "migration", "external_service", "behavioral_oracle",
        )
    )
    resources = ProjectResourceInventory(
        inventory_id="resources:save-record",
        boundary_fingerprint=_fingerprint("boundary:save-record"),
        members=resource_members,
        discovery_fingerprints=(("independent-inventory", scenario.inventory.fingerprint),),
    )
    intent = ProjectIntentInventory(
        inventory_id="intent:save-record",
        subject_revision=CURRENT_SNAPSHOT_FINGERPRINT,
        canonical_review_fingerprint=_fingerprint("intent-review:save-record"),
        contributions=(),
        no_declared_intent=(
            None
            if scenario.missing_intent
            else NoDeclaredIntentRationale(
                "no-intent:save-record-fixture",
                (("fixture-declaration", CURRENT_MODEL_FINGERPRINT),),
                "the bounded model fixture declares no external change intent",
            )
        ),
    )
    shared = {
        SEMANTIC_SPEC_ID: _semantic_spec().to_dict(),
        ORACLE_ID: _oracle().to_dict(),
        test_node.node_id: {"kind": "real_test_node"},
        "assertion:save-record": {"kind": "real_test_assertion"},
        **{
            member_id: {"kind": "planned_checker", "fingerprint": fingerprint}
            for member_id, fingerprint in planned_checker_fingerprints.items()
        },
        **{row.case_id: row.to_dict() for row in cases},
        **{row.coverage_id: row.to_dict() for row in coverage},
    }
    projection = normalize_behavior_blueprint(
        blueprint_fingerprint=manifest.fingerprint,
        behavior_report=behavior_report,
        shared_objects=shared,
        source_projection=binding_report.to_dict(),
    )
    readiness = review_static_blueprint_readiness(
        blueprint_fingerprint=manifest.fingerprint,
        behavior_report=behavior_report,
        resource_inventory=resources,
        intent_inventory=intent,
        topology_fingerprint=CURRENT_MESH_FINGERPRINT,
        normalized_projection_fingerprint=projection.fingerprint,
    )
    return behavior_report, readiness


def _finding_codes(findings) -> tuple[str, ...]:
    return tuple(sorted({str(finding.code) for finding in findings}))


def _target_system_report(behavior_report, readiness):
    descriptor = TargetSystemDescriptor(
        "target:save-record-workflow",
        "mixed",
        CURRENT_SNAPSHOT_FINGERPRINT,
        _fingerprint("boundary:save-record-target"),
        ("implementation_inventory", "test_inventory"),
        ("behavior_semantics", "portable_behavior"),
        "the bounded save-record software/workflow fixture only",
    )
    providers = (
        TargetSystemProviderResult(
            "provider:fixture-observation",
            "observation",
            "declared_mixed_observation",
            "1",
            descriptor.target_system_id,
            descriptor.subject_revision,
            ("implementation_inventory", "test_inventory"),
            (("boundary", descriptor.boundary_fingerprint),),
            (("behavior", behavior_report.fingerprint),),
            tuple(
                ProviderCapabilityBinding(
                    capability_id,
                    ("boundary",),
                    ("behavior",),
                )
                for capability_id in ("implementation_inventory", "test_inventory")
            ),
            claim_boundary=descriptor.claim_boundary,
        ),
        TargetSystemProviderResult(
            "provider:fixture-authority",
            "authority",
            "declared_model_authority",
            "1",
            descriptor.target_system_id,
            descriptor.subject_revision,
            ("behavior_semantics", "portable_behavior"),
            (("model", CURRENT_MODEL_FINGERPRINT),),
            (("readiness", readiness.fingerprint),),
            tuple(
                ProviderCapabilityBinding(
                    capability_id,
                    ("model",),
                    ("readiness",),
                )
                for capability_id in ("behavior_semantics", "portable_behavior")
            ),
            claim_boundary=descriptor.claim_boundary,
        ),
    )
    registry = build_target_system_provider_registry(
        "provider-registry:save-record",
        tuple(
            TargetSystemProviderDeclaration(
                row.provider_id,
                row.provider_role,
                row.provider_kind,
                row.provider_version,
                row.capability_ids,
                row.claim_boundary,
            )
            for row in providers
        ),
    )
    snapshot = capture_target_system_snapshot(
        "target-snapshot:save-record",
        descriptor,
        registry,
        providers,
    )
    return compile_target_system_blueprint(
        descriptor,
        providers,
        downstream_layers=tuple(
            BlueprintLayerResult(
                layer,
                "pass",
                (behavior_report.fingerprint, readiness.fingerprint),
            )
            for layer in BLUEPRINT_LAYER_ORDER[1:]
        ),
        provider_registry=registry,
        snapshot=snapshot,
    )


class ReviewImplementationBlueprint:
    name = "ReviewImplementationBlueprint"
    reads = (
        "scenario_id",
        "phase",
        "inventory_status",
        "binding_status",
        "static_status",
        "behavior_status",
        "readiness_status",
        "target_system_status",
        "projection_status",
        "finding_codes",
        "done_claim",
        "claim_text",
    )
    writes = reads
    accepted_input_type = BlueprintAction
    input_description = "one bounded blueprint-review action"
    output_description = "static blueprint state and bounded claim"
    idempotency = "The same source and authority identities produce the same static review."

    def apply(
        self,
        input_obj: BlueprintAction,
        state: BlueprintState,
    ) -> Iterable[FunctionResult]:
        if input_obj.action_type != "advance_blueprint_review":
            yield FunctionResult(
                BlueprintOutput("unknown_action_blocked"),
                replace(state, phase="blocked", finding_codes=("unknown_action",)),
                label="unknown_action_blocked",
            )
            return
        scenario = SCENARIOS.get(input_obj.scenario_id)
        if scenario is None:
            yield FunctionResult(
                BlueprintOutput("unknown_scenario_blocked"),
                replace(state, phase="blocked", finding_codes=("unknown_scenario",)),
                label="unknown_scenario_blocked",
            )
            return
        if state.scenario_id and state.scenario_id != scenario.scenario_id:
            yield FunctionResult(
                BlueprintOutput("scenario_switch_blocked"),
                replace(state, phase="blocked", finding_codes=("scenario_switch",)),
                label="scenario_switch_blocked",
            )
            return
        if state.phase == "start":
            report = review_implementation_surface_inventory(
                scenario.inventory.inventory
            )
            finding_codes = _finding_codes(report.findings)
            if not report.ok:
                yield self._blocked(
                    state,
                    scenario,
                    finding_codes,
                    inventory_status=report.status,
                )
                return
            yield FunctionResult(
                BlueprintOutput("inventory_complete"),
                replace(
                    state,
                    scenario_id=scenario.scenario_id,
                    phase="inventory_complete",
                    inventory_status="complete",
                    finding_codes=(),
                ),
                label="inventory_complete",
            )
            return

        report = _binding_report(scenario)
        if state.phase == "inventory_complete":
            finding_codes = _finding_codes(report.findings)
            if report.status != "complete":
                yield self._blocked(
                    state,
                    scenario,
                    finding_codes,
                    binding_status=report.status,
                )
                return
            yield FunctionResult(
                BlueprintOutput("binding_complete"),
                replace(
                    state,
                    phase="binding_complete",
                    binding_status="complete",
                    finding_codes=(),
                ),
                label="binding_complete",
            )
            return

        manifest = _manifest(scenario, report)
        if state.phase == "binding_complete":
            qualification = qualify_software_blueprint(
                manifest,
                report,
                implementation_inventory=scenario.inventory,
                reconstruction_required=False,
                current_observed_snapshot_fingerprint=CURRENT_SNAPSHOT_FINGERPRINT,
                current_semantic_mesh_fingerprint=CURRENT_MESH_FINGERPRINT,
                current_test_inventory_fingerprint=CURRENT_TEST_INVENTORY_FINGERPRINT,
                current_model_test_alignment_report_fingerprint=CURRENT_ALIGNMENT_FINGERPRINT,
                current_portable_owner_fingerprints={
                    "portable:model-system": CURRENT_PORTABLE_OWNER_FINGERPRINT
                },
                current_resource_fingerprints={
                    RESOURCE_ID: CURRENT_RUNTIME_FINGERPRINT
                },
                current_oracle_fingerprints={ORACLE_ID: CURRENT_ORACLE_FINGERPRINT},
            )
            finding_codes = _finding_codes(qualification.static_findings)
            if qualification.static_status != "complete":
                yield self._blocked(
                    state,
                    scenario,
                    finding_codes,
                    static_status=qualification.static_status,
                )
                return
            yield FunctionResult(
                BlueprintOutput("static_blueprint_complete"),
                replace(
                    state,
                    phase="static_complete",
                    static_status=qualification.static_status,
                    finding_codes=(),
                    claim_text="static blueprint complete",
                ),
                label="static_blueprint_complete",
            )
            return

        if state.phase == "static_complete":
            behavior_report, readiness = _behavior_readiness(
                scenario,
                manifest,
                report,
            )
            finding_codes = _finding_codes(readiness.findings)
            if readiness.status != "ready":
                yield self._blocked(
                    state,
                    scenario,
                    finding_codes,
                    behavior_status=behavior_report.behavior_closure_status,
                    readiness_status=readiness.status,
                )
                return
            yield FunctionResult(
                BlueprintOutput("behavior_readiness_complete"),
                replace(
                    state,
                    phase="readiness_complete",
                    behavior_status="complete",
                    readiness_status="ready",
                    finding_codes=(),
                ),
                label="behavior_readiness_complete",
            )
            return

        if state.phase == "readiness_complete":
            behavior_report, readiness = _behavior_readiness(
                scenario,
                manifest,
                report,
            )
            target_report = _target_system_report(behavior_report, readiness)
            if not target_report.ok:
                yield self._blocked(
                    state,
                    scenario,
                    tuple(row.object_id for row in target_report.gaps),
                    target_system_status=target_report.status,
                )
                return
            yield FunctionResult(
                BlueprintOutput("target_system_blueprint_complete"),
                replace(
                    state,
                    phase="target_system_complete",
                    target_system_status="pass",
                    finding_codes=(),
                ),
                label="target_system_blueprint_complete",
            )
            return

        if state.phase == "target_system_complete":
            verification = _projection_verification(scenario, manifest, report)
            finding_codes = _finding_codes(verification.findings)
            if not verification.ok:
                yield self._blocked(
                    state,
                    scenario,
                    finding_codes,
                    projection_status=PROJECTION_BLOCKED,
                )
                return
            yield FunctionResult(
                BlueprintOutput("projection_verified"),
                replace(
                    state,
                    phase="projection_complete",
                    projection_status=PROJECTION_COMPLETE,
                    finding_codes=(),
                ),
                label="projection_verified",
            )
            return

        if state.phase == "projection_complete":
            accepted = state.ready_for_done()
            claim = "accepted" if accepted else "rejected"
            yield FunctionResult(
                BlueprintOutput(f"done_{claim}"),
                replace(
                    state,
                    phase="done",
                    done_claim=claim,
                    claim_text=(
                        "static blueprint complete"
                        if accepted
                        else "blueprint completion rejected"
                    ),
                ),
                label=f"done_{claim}",
            )

    @staticmethod
    def _blocked(
        state: BlueprintState,
        scenario: BlueprintScenario,
        finding_codes: tuple[str, ...],
        **updates,
    ) -> FunctionResult:
        next_state = replace(
            state,
            scenario_id=scenario.scenario_id,
            phase="blocked",
            finding_codes=finding_codes,
            done_claim="rejected",
            claim_text="blueprint review blocked",
            **updates,
        )
        label = f"{scenario.scenario_id}_blocked"
        return FunctionResult(
            BlueprintOutput(label),
            next_state,
            label=label,
        )


def terminal_predicate(current_output, state, trace) -> bool:
    del trace
    return state.phase in {"done", "blocked"} or (
        isinstance(current_output, BlueprintOutput)
        and (
            current_output.status.startswith("done_")
            or current_output.status.endswith("_blocked")
        )
    )


def no_static_done_without_exact_blueprint(
    state: BlueprintState,
    trace,
) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and not state.ready_for_done():
        return InvariantResult.fail(
            "blueprint completion bypassed inventory, binding, static qualification, "
            "behavior, target-system, or projection gates"
        )
    return InvariantResult.pass_()


def accepted_claim_matches_static_closure(
    state: BlueprintState,
    trace,
) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and state.claim_text != "static blueprint complete":
        return InvariantResult.fail(
            "accepted static closure used a claim outside the modeled blueprint boundary"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_static_done_without_exact_blueprint",
        "A done claim requires exact inventory, binding, behavior, target-system, and projection gates.",
        no_static_done_without_exact_blueprint,
    ),
    Invariant(
        "accepted_claim_matches_static_closure",
        "The accepted claim remains inside the modeled static blueprint boundary.",
        accepted_claim_matches_static_closure,
    ),
)

GOOD_ACTION = BlueprintAction("advance_blueprint_review")
BAD_ACTIONS = tuple(
    BlueprintAction("advance_blueprint_review", scenario_id=scenario_id)
    for scenario_id in BAD_SCENARIO_IDS
)
MAX_SEQUENCE_LENGTH = 7


def initial_state() -> BlueprintState:
    return BlueprintState()


def build_workflow() -> Workflow:
    return Workflow((ReviewImplementationBlueprint(),), name="implementation_blueprint")


__all__ = [
    "BAD_ACTIONS",
    "BAD_SCENARIO_IDS",
    "BlueprintAction",
    "BlueprintOutput",
    "BlueprintScenario",
    "BlueprintState",
    "GOOD_ACTION",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "SCENARIOS",
    "build_workflow",
    "initial_state",
    "terminal_predicate",
]
