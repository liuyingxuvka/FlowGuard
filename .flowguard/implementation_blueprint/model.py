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
    CanonicalBlueprintProjection,
    ModelImplementationBinding,
    ModelImplementationBindingReport,
    OracleReference,
    SemanticSpecReference,
    SEMANTIC_AUTHORITY_OBSERVED_CANDIDATE,
    SoftwareBlueprintManifest,
    _make_shard,
    _qualify_blueprint_manifest,
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
from flowguard.model_path_quality import PathQualityResult, PathQualitySubject
from flowguard.software_blueprint_readiness import (
    BEHAVIOR_DIMENSIONS,
    BehaviorBlockContract,
    BehaviorCaseContract,
    BehaviorCoverageEdge,
    BehaviorDimensionContract,
    CoverageExecutionEvidence,
    DelegatedAssertionHelper,
    IntentSourceAuthority,
    ObservedResourceMember,
    ProjectIntentContribution,
    ProjectIntentInventory,
    ProjectResourceInventory,
    ProjectResourceMember,
    ProjectTestNodeDisposition,
    PortableBehaviorBinding,
    SupportingSurfaceRelation,
    materialize_behavior_blueprint_shards,
    normalize_behavior_blueprint,
    review_behavior_blueprint,
    review_static_blueprint_readiness,
)
from flowguard.target_system_blueprint import (
    CANONICAL_SOFTWARE_LAYER_PLAN,
    BlueprintLayerResult,
    BlueprintNativeReportRef,
    FrozenTargetSystemEvidence,
    ModelPathQualityBlueprintBinding,
    ProviderCapabilityBinding,
    TargetSystemDescriptor,
    TargetSystemProviderDeclaration,
    TargetSystemProviderResult,
    build_target_system_provider_registry,
    capture_target_system_snapshot,
    _assemble_target_system_blueprint,
)


STATIC_NOT_RUN = "not_run"
PROJECTION_NOT_RUN = "not_run"
PROJECTION_COMPLETE = "complete"
PROJECTION_BLOCKED = "blocked"
MODEL_CLAIM_BOUNDARY = (
    "The bounded fixture's inventory, manifest consistency, behavior readiness, "
    "target-system compiler, and generic projection integrity only; this model "
    "does not establish whole-project understanding, executed evidence, release "
    "readiness, or reconstruction capability."
)


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
class CurrentPassEvidence:
    """One candidate input to a claim that an obligation is current and passed."""

    evidence_id: str
    origin_kind: str
    subject_revision: str
    independently_verified: bool


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
    observed_snapshot_initialized_before_resource_observation: bool = True
    intent_subject_revision: str | None = None
    intent_observed_subject_revision: str | None = None
    expected_realized_owner_ids: tuple[str, ...] | None = None
    projected_realized_owner_ids: tuple[str, ...] | None = None
    intent_owner_denominator_complete: bool = True
    behavior_intent_binding_mode: str = "exact"
    independently_contracted_surface_ids: tuple[str, ...] | None = None
    current_pass_evidence: tuple[CurrentPassEvidence, ...] | None = None
    delegated_helper_mode: str = "none"
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
    static_manifest_status: str = STATIC_NOT_RUN
    behavior_status: str = STATIC_NOT_RUN
    readiness_status: str = STATIC_NOT_RUN
    target_system_status: str = STATIC_NOT_RUN
    projection_status: str = PROJECTION_NOT_RUN
    observed_snapshot_input_status: str = STATIC_NOT_RUN
    intent_snapshot_status: str = STATIC_NOT_RUN
    intent_owner_projection_status: str = STATIC_NOT_RUN
    semantic_intent_lineage_status: str = STATIC_NOT_RUN
    surface_classification_status: str = STATIC_NOT_RUN
    semantic_authority_status: str = STATIC_NOT_RUN
    current_pass_evidence_status: str = STATIC_NOT_RUN
    delegated_assertion_status: str = STATIC_NOT_RUN
    finding_codes: tuple[str, ...] = ()
    done_claim: str = "none"
    claim_boundary: str = ""

    def ready_for_done(self) -> bool:
        return (
            self.inventory_status == "complete"
            and self.binding_status == "complete"
            and self.static_manifest_status == "complete"
            and self.behavior_status == "complete"
            and self.readiness_status == "ready"
            and self.target_system_status == "pass"
            and self.projection_status == PROJECTION_COMPLETE
            and self.observed_snapshot_input_status == "current"
            and self.intent_snapshot_status == "current"
            and self.intent_owner_projection_status == "complete"
            and self.semantic_intent_lineage_status == "complete"
            and self.surface_classification_status == "complete"
            and self.semantic_authority_status == "independent"
            and self.current_pass_evidence_status == "independent"
            and self.delegated_assertion_status in {"current", "not_applicable"}
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
    calls: tuple[str, ...] = ()


MODEL_ELEMENT_ID = "model:save-record"
SURFACE_ID = "surface:save-record"
HELPER_SURFACE_ID = "surface:normalize-record"
AGGREGATE_SURFACE_ID = "surface:record-service"
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
DELEGATED_HELPER_ID = "fixture.assert_saved"
DELEGATED_HELPER_FINGERPRINT = _fingerprint(DELEGATED_HELPER_ID)
DELEGATED_TERMINAL_ID = "delegated-terminal:assert-saved"
DELEGATED_TERMINAL_FINGERPRINT = _fingerprint(DELEGATED_TERMINAL_ID)
CURRENT_TEST_INVENTORY_FINGERPRINT = _fingerprint("test-inventory:current")
CURRENT_ALIGNMENT_FINGERPRINT = _fingerprint("model-test-alignment:current")
CURRENT_SOURCE_INVENTORY_FINGERPRINT = _fingerprint("inventory:source-current")
CURRENT_PATH_QUALITY_ID = "currentness:save-record-path-quality"
INTENT_CONTRIBUTION_ID = "intent:save-record"
INTENT_SOURCE_ID = "intent-source:save-record"
INTENT_SOURCE_OWNER_ID = "owner:intent"
INTENT_SOURCE_FINGERPRINT = _fingerprint(INTENT_SOURCE_ID)
INTENT_EXPECTATION_ID = "expectation:save-record"
INTENT_EXPECTATION_FINGERPRINT = _fingerprint(INTENT_EXPECTATION_ID)
EXACT_REALIZED_OWNER_IDS = (
    MODEL_ELEMENT_ID,
    "model:test-save-record",
)
SELF_SEMANTIC_AUTHORITY_SOURCE_IDS = frozenset(
    {
        ".flowguard/implementation_blueprint/model.py",
        ".flowguard/implementation_blueprint/run_checks.py",
    }
)
FORBIDDEN_SELF_CURRENT_EVIDENCE_ORIGINS = frozenset(
    {"checked_in_declaration", "self_built_projection"}
)
DELEGATED_ASSERTION_FINDING_CODES = frozenset(
    {
        "ambiguous_delegated_assertion_helper",
        "coverage_cross_test_member",
        "coverage_oracle_member_missing",
        "delegated_assertion_helper_cycle",
        "delegated_assertion_helper_stale",
        "delegated_assertion_terminal_missing",
        "delegated_assertion_terminal_stale",
        "unregistered_assertion_helper",
    }
)


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


def _helper(
    *,
    owner: str = SURFACE_ID,
    disposition: str = IMPLEMENTATION_DISPOSITION_SUPPORTING,
) -> ImplementationSurface:
    return ImplementationSurface(
        surface_id=HELPER_SURFACE_ID,
        path="src/app.py",
        symbol="_normalize_record",
        surface_kind="helper",
        parent_surface_id="",
        content_fingerprint=CURRENT_HELPER_FINGERPRINT,
        structure_fingerprint=_fingerprint(f"structure:{HELPER_SURFACE_ID}"),
        disposition=disposition,
        owning_surface_id=owner,
        roles=("helper",),
        parameters=("value",),
        returns_value=True,
        line_start=12,
        line_end=14,
        discovery_adapter_id="python_ast_v1",
    )


def _aggregate(
    *,
    owner: str = SURFACE_ID,
    disposition: str = IMPLEMENTATION_DISPOSITION_SUPPORTING,
) -> ImplementationSurface:
    return ImplementationSurface(
        surface_id=AGGREGATE_SURFACE_ID,
        path="src/app.py",
        symbol="RecordService",
        surface_kind="class",
        parent_surface_id="",
        content_fingerprint=_fingerprint(AGGREGATE_SURFACE_ID),
        structure_fingerprint=_fingerprint(
            f"structure:{AGGREGATE_SURFACE_ID}"
        ),
        disposition=disposition,
        owning_surface_id=owner,
        roles=("aggregate",),
        line_start=16,
        line_end=30,
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
        surfaces=(
            surfaces
            if surfaces is not None
            else (_surface(), _aggregate(), _helper())
        ),
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
        source_id=INTENT_SOURCE_ID,
        source_owner_id=INTENT_SOURCE_OWNER_ID,
        source_content_fingerprint=INTENT_SOURCE_FINGERPRINT,
        covered_model_element_ids=(MODEL_ELEMENT_ID,),
        covered_dimensions=("error", "input", "output", "state_effect"),
        semantics=(
            ("error", "invalid input produces a typed validation error"),
            ("input", "one record value enters the save operation"),
            ("output", "the normalized record value is returned"),
            ("state_effect", "record:last is written before write_record publishes"),
        ),
        provenance_fingerprints=(
            (INTENT_SOURCE_ID, INTENT_SOURCE_FINGERPRINT),
            (INTENT_EXPECTATION_ID, INTENT_EXPECTATION_FINGERPRINT),
        ),
    )


def _oracle() -> OracleReference:
    return OracleReference(
        oracle_id=ORACLE_ID,
        owner_id="owner:test",
        artifact_id="artifact:oracle-save-record",
        artifact_fingerprint=CURRENT_ORACLE_FINGERPRINT,
        source_id="oracle-source:save-record",
        source_owner_id="owner:oracle-source",
        source_content_fingerprint=_fingerprint("oracle-source:save-record"),
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
        model_obligation_ids=(MODEL_ELEMENT_ID,),
        implementation_surface_id=SURFACE_ID,
        relation_kind="implements",
        owner_contract_id=OWNER_CONTRACT_ID,
        implementation_source_id=SURFACE_ID,
        implementation_owner_id="owner:implementation",
        implementation_content_fingerprint=implementation_fingerprint,
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


def _supporting_oracle_binding() -> ModelImplementationBinding:
    """Bind an oracle implementation as support, never as self-certified behavior."""

    return ModelImplementationBinding(
        binding_id="binding:supporting-oracle-runner",
        model_element_id=MODEL_ELEMENT_ID,
        model_obligation_ids=(MODEL_ELEMENT_ID,),
        implementation_surface_id=HELPER_SURFACE_ID,
        relation_kind="supports",
        owner_contract_id=OWNER_CONTRACT_ID,
        implementation_source_id=HELPER_SURFACE_ID,
        implementation_owner_id="owner:implementation",
        implementation_content_fingerprint=CURRENT_HELPER_FINGERPRINT,
        semantic_spec_ids=(SEMANTIC_SPEC_ID,),
        oracle_ids=(ORACLE_ID,),
        required_dimensions=("error", "input", "output", "state_effect"),
        test_evidence_ids=("test:save-record",),
        test_evidence_fingerprints=(
            ("test:save-record", CURRENT_TEST_FINGERPRINT),
        ),
        primary=False,
        delegating=True,
        model_fingerprint=CURRENT_MODEL_FINGERPRINT,
        implementation_fingerprint=CURRENT_HELPER_FINGERPRINT,
        owner_contract_fingerprint=CURRENT_CONTRACT_FINGERPRINT,
    )


def _scenario_intent_subject_revision(scenario: BlueprintScenario) -> str:
    return scenario.intent_subject_revision or CURRENT_SNAPSHOT_FINGERPRINT


def _scenario_intent_observed_revision(scenario: BlueprintScenario) -> str:
    return (
        scenario.intent_observed_subject_revision
        or CURRENT_SNAPSHOT_FINGERPRINT
    )


def _scenario_expected_realized_owner_ids(
    scenario: BlueprintScenario,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            scenario.expected_realized_owner_ids
            if scenario.expected_realized_owner_ids is not None
            else EXACT_REALIZED_OWNER_IDS
        )
    )


def _scenario_projected_realized_owner_ids(
    scenario: BlueprintScenario,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            scenario.projected_realized_owner_ids
            if scenario.projected_realized_owner_ids is not None
            else EXACT_REALIZED_OWNER_IDS
        )
    )


def _scenario_independently_contracted_surface_ids(
    scenario: BlueprintScenario,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            scenario.independently_contracted_surface_ids
            if scenario.independently_contracted_surface_ids is not None
            else (SURFACE_ID,)
        )
    )


def _scenario_current_pass_evidence(
    scenario: BlueprintScenario,
) -> tuple[CurrentPassEvidence, ...]:
    if scenario.current_pass_evidence is not None:
        return scenario.current_pass_evidence
    return (
        CurrentPassEvidence(
            evidence_id="receipt:independent-blueprint-review",
            origin_kind="independent_terminal_receipt",
            subject_revision=CURRENT_SNAPSHOT_FINGERPRINT,
            independently_verified=True,
        ),
    )


def _intent_inventory(scenario: BlueprintScenario) -> ProjectIntentInventory:
    subject_revision = _scenario_intent_subject_revision(scenario)
    observed_revision = _scenario_intent_observed_revision(scenario)
    if scenario.missing_intent:
        return ProjectIntentInventory(
            inventory_id=f"intent:{scenario.scenario_id}",
            subject_revision=subject_revision,
            observed_subject_revision=observed_revision,
            contributions=(),
            source_authorities=(),
            authority_provider_capabilities=(
                ("provider:fixture-authority", "intent_lineage"),
            ),
            required_model_target_ids=tuple(
                _scenario_expected_realized_owner_ids(scenario)
            ),
        )
    target_ids = _scenario_projected_realized_owner_ids(scenario)
    contribution = ProjectIntentContribution(
        contribution_id=INTENT_CONTRIBUTION_ID,
        source_kind="accepted_change_objective",
        source_id=INTENT_SOURCE_ID,
        source_owner_id=INTENT_SOURCE_OWNER_ID,
        source_fingerprint=INTENT_SOURCE_FINGERPRINT,
        expectation_id=INTENT_EXPECTATION_ID,
        expectation_fingerprint=INTENT_EXPECTATION_FINGERPRINT,
        disposition="accepted",
        target_ids=target_ids,
        rationale=(
            "the accepted save-record intent projects every exact realized model owner"
        ),
    )
    authority = IntentSourceAuthority(
        source_kind=contribution.source_kind,
        source_id=contribution.source_id,
        source_owner_id=contribution.source_owner_id,
        subject_revision=subject_revision,
        current_source_fingerprint=contribution.source_fingerprint,
        expectation_id=contribution.expectation_id,
        current_expectation_fingerprint=contribution.expectation_fingerprint,
        target_ids=contribution.target_ids,
        provider_id="provider:fixture-authority",
        capability_id="intent_lineage",
        payload_id="intent_lineage",
    )
    return ProjectIntentInventory(
        inventory_id=f"intent:{scenario.scenario_id}",
        subject_revision=subject_revision,
        observed_subject_revision=observed_revision,
        contributions=(contribution,),
        source_authorities=(authority,),
        authority_provider_capabilities=(
            ("provider:fixture-authority", "intent_lineage"),
        ),
        required_model_target_ids=tuple(
            _scenario_expected_realized_owner_ids(scenario)
        ),
    )


def _authority_contract_review(
    scenario: BlueprintScenario,
) -> tuple[tuple[str, ...], dict[str, str]]:
    """Review the independent inputs that a blueprint cannot self-certify."""

    findings: set[str] = set()
    intent = _intent_inventory(scenario)
    if (
        intent.subject_revision != CURRENT_SNAPSHOT_FINGERPRINT
        or intent.observed_subject_revision != CURRENT_SNAPSHOT_FINGERPRINT
        or intent.subject_revision != intent.observed_subject_revision
    ):
        findings.add("intent_snapshot_identity_mismatch")

    if not scenario.missing_intent and (
        set(_scenario_projected_realized_owner_ids(scenario))
        != set(_scenario_expected_realized_owner_ids(scenario))
    ):
        findings.add("intent_realized_owner_omitted")
    if not scenario.intent_owner_denominator_complete:
        findings.add("intent_model_target_coverage_missing")
    if scenario.behavior_intent_binding_mode == "empty":
        findings.add("behavior_intent_coverage_missing")
    elif scenario.behavior_intent_binding_mode == "cross_owner":
        findings.add("behavior_intent_owner_mismatch")
    elif scenario.behavior_intent_binding_mode == "root_fallback":
        findings.add("behavior_intent_root_fallback")
    elif scenario.behavior_intent_binding_mode != "exact":
        findings.add("behavior_intent_binding_invalid")

    if not scenario.missing_intent and scenario.semantic_specs:
        contribution = intent.contributions[0]
        source_pair = (
            contribution.source_id,
            contribution.source_fingerprint,
        )
        expectation_pair = (
            contribution.expectation_id,
            contribution.expectation_fingerprint,
        )
        for reference in scenario.semantic_specs:
            provenance = set(reference.provenance_fingerprints)
            if source_pair not in provenance:
                findings.add("semantic_intent_source_unbound")
            if expectation_pair not in provenance:
                findings.add("semantic_intent_expectation_unbound")

    contracted_surface_ids = set(
        _scenario_independently_contracted_surface_ids(scenario)
    )
    structural_surface_kinds = {"module", "class", "helper"}
    if any(
        surface.surface_kind in structural_surface_kinds
        and surface.disposition == IMPLEMENTATION_DISPOSITION_MODEL
        and surface.surface_id not in contracted_surface_ids
        for surface in scenario.inventory.surfaces
    ):
        findings.add("structural_surface_promoted_without_contract")

    if any(
        reference.source_id in SELF_SEMANTIC_AUTHORITY_SOURCE_IDS
        for reference in scenario.semantic_specs
    ):
        findings.add("self_model_semantic_authority")

    current_evidence = _scenario_current_pass_evidence(scenario)
    if (
        not current_evidence
        or any(
            row.origin_kind in FORBIDDEN_SELF_CURRENT_EVIDENCE_ORIGINS
            or not row.independently_verified
            or row.subject_revision != CURRENT_SNAPSHOT_FINGERPRINT
            for row in current_evidence
        )
    ):
        findings.add("self_certified_current_pass")

    status = {
        "intent_snapshot_status": (
            "current"
            if "intent_snapshot_identity_mismatch" not in findings
            else "stale"
        ),
        "intent_owner_projection_status": (
            "complete"
            if not {
                "intent_realized_owner_omitted",
                "intent_model_target_coverage_missing",
            }.intersection(findings)
            else "incomplete"
        ),
        "semantic_intent_lineage_status": (
            "complete"
            if not {
                "semantic_intent_source_unbound",
                "semantic_intent_expectation_unbound",
                "behavior_intent_coverage_missing",
                "behavior_intent_owner_mismatch",
                "behavior_intent_root_fallback",
                "behavior_intent_binding_invalid",
            }.intersection(findings)
            else "blocked"
        ),
        "surface_classification_status": (
            "complete"
            if "structural_surface_promoted_without_contract" not in findings
            else "blocked"
        ),
        "semantic_authority_status": (
            "independent"
            if "self_model_semantic_authority" not in findings
            else "blocked"
        ),
        "current_pass_evidence_status": (
            "independent"
            if "self_certified_current_pass" not in findings
            else "blocked"
        ),
    }
    return tuple(sorted(findings)), status


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
        "delegated_direct_terminal": BlueprintScenario(
            "delegated_direct_terminal",
            _inventory("delegated-direct-terminal"),
            base_binding,
            semantic,
            oracles,
            delegated_helper_mode="direct_terminal",
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
                    source_id=SURFACE_ID,
                    source_owner_id="owner:implementation",
                    source_content_fingerprint=CURRENT_SURFACE_FINGERPRINT,
                ),
            ),
            oracles,
            expected_finding_codes=("semantic_source_not_independent",),
        ),
        "supporting_oracle_surface": BlueprintScenario(
            "supporting_oracle_surface",
            _inventory("supporting-oracle-surface"),
            (_binding(), _supporting_oracle_binding()),
            semantic,
            (
                replace(
                    _oracle(),
                    source_id=HELPER_SURFACE_ID,
                    source_owner_id="owner:implementation",
                    source_content_fingerprint=CURRENT_HELPER_FINGERPRINT,
                ),
            ),
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
        "resource_snapshot_uninitialized": BlueprintScenario(
            "resource_snapshot_uninitialized",
            _inventory("resource-snapshot-uninitialized"),
            base_binding,
            semantic,
            oracles,
            observed_snapshot_initialized_before_resource_observation=False,
            expected_finding_codes=(
                "resource_observation_snapshot_input_uninitialized",
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
        "delegated_terminal_stale": BlueprintScenario(
            "delegated_terminal_stale",
            _inventory("delegated-terminal-stale"),
            base_binding,
            semantic,
            oracles,
            delegated_helper_mode="stale_terminal",
            expected_finding_codes=("delegated_assertion_terminal_stale",),
        ),
        "delegated_terminal_ambiguous": BlueprintScenario(
            "delegated_terminal_ambiguous",
            _inventory("delegated-terminal-ambiguous"),
            base_binding,
            semantic,
            oracles,
            delegated_helper_mode="ambiguous_terminal",
            expected_finding_codes=(
                "ambiguous_delegated_assertion_helper",
            ),
        ),
        "delegated_terminal_unknown_branch": BlueprintScenario(
            "delegated_terminal_unknown_branch",
            _inventory("delegated-terminal-unknown-branch"),
            base_binding,
            semantic,
            oracles,
            delegated_helper_mode="unknown_branch",
            expected_finding_codes=(
                "delegated_assertion_terminal_missing",
            ),
        ),
        "delegated_terminal_cycle": BlueprintScenario(
            "delegated_terminal_cycle",
            _inventory("delegated-terminal-cycle"),
            base_binding,
            semantic,
            oracles,
            delegated_helper_mode="cyclic_branch",
            expected_finding_codes=("delegated_assertion_helper_cycle",),
        ),
        "delegated_terminal_nonterminal": BlueprintScenario(
            "delegated_terminal_nonterminal",
            _inventory("delegated-terminal-nonterminal"),
            base_binding,
            semantic,
            oracles,
            delegated_helper_mode="nonterminal_branch",
            expected_finding_codes=("unregistered_assertion_helper",),
        ),
        "delegated_coverage_sibling_owner": BlueprintScenario(
            "delegated_coverage_sibling_owner",
            _inventory("delegated-coverage-sibling-owner"),
            base_binding,
            semantic,
            oracles,
            delegated_helper_mode="sibling_coverage_owner",
            expected_finding_codes=("coverage_cross_test_member",),
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
        "intent_snapshot_identity_mismatch": BlueprintScenario(
            "intent_snapshot_identity_mismatch",
            _inventory("intent-snapshot-identity-mismatch"),
            base_binding,
            semantic,
            oracles,
            intent_subject_revision=CURRENT_SOURCE_INVENTORY_FINGERPRINT,
            expected_finding_codes=("intent_snapshot_identity_mismatch",),
        ),
        "intent_realized_owner_omitted": BlueprintScenario(
            "intent_realized_owner_omitted",
            _inventory("intent-realized-owner-omitted"),
            base_binding,
            semantic,
            oracles,
            projected_realized_owner_ids=(MODEL_ELEMENT_ID,),
            expected_finding_codes=("intent_realized_owner_omitted",),
        ),
        "intent_model_target_denominator_incomplete": BlueprintScenario(
            "intent_model_target_denominator_incomplete",
            _inventory("intent-model-target-denominator-incomplete"),
            base_binding,
            semantic,
            oracles,
            intent_owner_denominator_complete=False,
            expected_finding_codes=("intent_model_target_coverage_missing",),
        ),
        "behavior_intent_binding_empty": BlueprintScenario(
            "behavior_intent_binding_empty",
            _inventory("behavior-intent-binding-empty"),
            base_binding,
            semantic,
            oracles,
            behavior_intent_binding_mode="empty",
            expected_finding_codes=("behavior_intent_coverage_missing",),
        ),
        "behavior_intent_binding_cross_owner": BlueprintScenario(
            "behavior_intent_binding_cross_owner",
            _inventory("behavior-intent-binding-cross-owner"),
            base_binding,
            semantic,
            oracles,
            behavior_intent_binding_mode="cross_owner",
            expected_finding_codes=("behavior_intent_owner_mismatch",),
        ),
        "behavior_intent_binding_root_fallback": BlueprintScenario(
            "behavior_intent_binding_root_fallback",
            _inventory("behavior-intent-binding-root-fallback"),
            base_binding,
            semantic,
            oracles,
            behavior_intent_binding_mode="root_fallback",
            expected_finding_codes=("behavior_intent_root_fallback",),
        ),
        "semantic_intent_source_unbound": BlueprintScenario(
            "semantic_intent_source_unbound",
            _inventory("semantic-intent-source-unbound"),
            base_binding,
            (
                replace(
                    _semantic_spec(),
                    provenance_fingerprints=(
                        (
                            INTENT_EXPECTATION_ID,
                            INTENT_EXPECTATION_FINGERPRINT,
                        ),
                    ),
                ),
            ),
            oracles,
            expected_finding_codes=("semantic_intent_source_unbound",),
        ),
        "semantic_intent_expectation_unbound": BlueprintScenario(
            "semantic_intent_expectation_unbound",
            _inventory("semantic-intent-expectation-unbound"),
            base_binding,
            (
                replace(
                    _semantic_spec(),
                    provenance_fingerprints=(
                        (INTENT_SOURCE_ID, INTENT_SOURCE_FINGERPRINT),
                    ),
                ),
            ),
            oracles,
            expected_finding_codes=(
                "semantic_intent_expectation_unbound",
            ),
        ),
        "aggregate_surface_promoted": BlueprintScenario(
            "aggregate_surface_promoted",
            _inventory(
                "aggregate-surface-promoted",
                surfaces=(
                    _surface(),
                    _aggregate(
                        owner="",
                        disposition=IMPLEMENTATION_DISPOSITION_MODEL,
                    ),
                    _helper(),
                ),
            ),
            base_binding,
            semantic,
            oracles,
            expected_finding_codes=(
                "structural_surface_promoted_without_contract",
            ),
        ),
        "helper_surface_promoted": BlueprintScenario(
            "helper_surface_promoted",
            _inventory(
                "helper-surface-promoted",
                surfaces=(
                    _surface(),
                    _aggregate(),
                    _helper(
                        owner="",
                        disposition=IMPLEMENTATION_DISPOSITION_MODEL,
                    ),
                ),
            ),
            base_binding,
            semantic,
            oracles,
            expected_finding_codes=(
                "structural_surface_promoted_without_contract",
            ),
        ),
        "model_file_self_semantic_authority": BlueprintScenario(
            "model_file_self_semantic_authority",
            _inventory("model-file-self-semantic-authority"),
            base_binding,
            (
                replace(
                    _semantic_spec(),
                    source_id=".flowguard/implementation_blueprint/model.py",
                    source_owner_id="owner:self-model",
                    source_content_fingerprint=_fingerprint(
                        ".flowguard/implementation_blueprint/model.py"
                    ),
                ),
            ),
            oracles,
            expected_finding_codes=("self_model_semantic_authority",),
        ),
        "runner_file_self_semantic_authority": BlueprintScenario(
            "runner_file_self_semantic_authority",
            _inventory("runner-file-self-semantic-authority"),
            base_binding,
            (
                replace(
                    _semantic_spec(),
                    source_id=(
                        ".flowguard/implementation_blueprint/run_checks.py"
                    ),
                    source_owner_id="owner:self-runner",
                    source_content_fingerprint=_fingerprint(
                        ".flowguard/implementation_blueprint/run_checks.py"
                    ),
                ),
            ),
            oracles,
            expected_finding_codes=("self_model_semantic_authority",),
        ),
        "checked_in_declaration_current_pass": BlueprintScenario(
            "checked_in_declaration_current_pass",
            _inventory("checked-in-declaration-current-pass"),
            base_binding,
            semantic,
            oracles,
            current_pass_evidence=(
                CurrentPassEvidence(
                    evidence_id="declaration:checked-in-current",
                    origin_kind="checked_in_declaration",
                    subject_revision=CURRENT_SNAPSHOT_FINGERPRINT,
                    independently_verified=False,
                ),
            ),
            expected_finding_codes=("self_certified_current_pass",),
        ),
        "self_built_projection_current_pass": BlueprintScenario(
            "self_built_projection_current_pass",
            _inventory("self-built-projection-current-pass"),
            base_binding,
            semantic,
            oracles,
            current_pass_evidence=(
                CurrentPassEvidence(
                    evidence_id="projection:self-built-current",
                    origin_kind="self_built_projection",
                    subject_revision=CURRENT_SNAPSHOT_FINGERPRINT,
                    independently_verified=False,
                ),
            ),
            expected_finding_codes=("self_certified_current_pass",),
        ),
        "circular_behavior_evidence": BlueprintScenario(
            "circular_behavior_evidence",
            _inventory("circular-behavior-evidence"),
            base_binding,
            (
                replace(
                    _semantic_spec(),
                    source_id="authority-source:shared",
                    source_owner_id="owner:shared-authority",
                    source_content_fingerprint=_fingerprint(
                        "authority-source:shared"
                    ),
                ),
            ),
            (
                replace(
                    _oracle(),
                    source_id="authority-source:shared",
                    source_owner_id="owner:shared-authority",
                    source_content_fingerprint=_fingerprint(
                        "authority-source:shared"
                    ),
                ),
            ),
            circular_behavior_evidence=True,
            expected_finding_codes=(
                "semantic_oracle_source_not_independent",
            ),
        ),
    }


SCENARIOS = _scenarios()
GOOD_SCENARIO_IDS = (
    "complete",
    "delegated_direct_terminal",
    "supporting_oracle_surface",
)
BAD_SCENARIO_IDS = tuple(
    scenario_id for scenario_id in SCENARIOS
    if scenario_id not in GOOD_SCENARIO_IDS
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
            consuming_behavior_ids=("behavior:save-record",),
            consuming_model_ids=(MODEL_ELEMENT_ID,),
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
    projection = CanonicalBlueprintProjection(
        blueprint_fingerprint=manifest.fingerprint,
        shards=(
            _make_shard(
                "identity",
                (
                    {
                        "blueprint_id": manifest.blueprint_id,
                        "blueprint_fingerprint": manifest.fingerprint,
                        "member_ids": [manifest.blueprint_id],
                    },
                ),
            ),
            _make_shard("bindings", (report,)),
        ),
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


def _delegated_assertion_fixture(
    scenario: BlueprintScenario,
) -> tuple[
    tuple[DelegatedAssertionHelper, ...],
    dict[str, str],
    tuple[BlueprintTestNode, ...],
    tuple[str, str] | None,
]:
    """Return one exact helper graph and its coverage member for the scenario."""

    assertion = BlueprintAssertionMember(
        "assertion:save-record",
        CURRENT_TEST_FINGERPRINT,
    )
    if scenario.delegated_helper_mode == "none":
        return (
            (),
            {},
            (BlueprintTestNode("test:save-record", (assertion,)),),
            None,
        )

    test_node = BlueprintTestNode(
        "test:save-record",
        (assertion,),
        ("assert_saved",),
    )
    direct = DelegatedAssertionHelper(
        DELEGATED_HELPER_ID,
        test_node.node_id,
        DELEGATED_HELPER_FINGERPRINT,
        (),
        ((DELEGATED_TERMINAL_ID, DELEGATED_TERMINAL_FINGERPRINT),),
    )
    helpers: tuple[DelegatedAssertionHelper, ...] = (direct,)
    expected = {DELEGATED_HELPER_ID: DELEGATED_HELPER_FINGERPRINT}
    coverage_member = (DELEGATED_HELPER_ID, DELEGATED_HELPER_FINGERPRINT)

    if scenario.delegated_helper_mode == "stale_terminal":
        helpers = (
            replace(
                direct,
                terminal_member_fingerprints=(
                    ("assertion:save-record", _fingerprint("assertion:stale")),
                ),
            ),
        )
    elif scenario.delegated_helper_mode == "ambiguous_terminal":
        first = replace(
            direct,
            helper_id="fixture_a.assert_saved",
            source_fingerprint=_fingerprint("fixture_a.assert_saved"),
            terminal_member_fingerprints=(
                ("delegated-terminal:fixture-a", _fingerprint("terminal:fixture-a")),
            ),
        )
        second = replace(
            direct,
            helper_id="fixture_b.assert_saved",
            source_fingerprint=_fingerprint("fixture_b.assert_saved"),
            terminal_member_fingerprints=(
                ("delegated-terminal:fixture-b", _fingerprint("terminal:fixture-b")),
            ),
        )
        helpers = (first, second)
        expected = {
            first.helper_id: first.source_fingerprint,
            second.helper_id: second.source_fingerprint,
        }
        coverage_member = (first.helper_id, first.source_fingerprint)
    elif scenario.delegated_helper_mode == "unknown_branch":
        helpers = (replace(direct, callee_member_ids=("assert_missing",)),)
    elif scenario.delegated_helper_mode == "cyclic_branch":
        first = replace(
            direct,
            callee_member_ids=("fixture.assert_other",),
            terminal_member_fingerprints=(),
        )
        second = DelegatedAssertionHelper(
            "fixture.assert_other",
            test_node.node_id,
            _fingerprint("fixture.assert_other"),
            (DELEGATED_HELPER_ID,),
        )
        helpers = (first, second)
        expected = {
            first.helper_id: first.source_fingerprint,
            second.helper_id: second.source_fingerprint,
        }
    elif scenario.delegated_helper_mode == "nonterminal_branch":
        helpers = ()
        expected = {}
    elif scenario.delegated_helper_mode == "sibling_coverage_owner":
        helpers = (replace(direct, test_node_id="test:sibling"),)
    elif scenario.delegated_helper_mode != "direct_terminal":
        raise ValueError(
            "unknown implementation-blueprint delegated helper mode: "
            f"{scenario.delegated_helper_mode}"
        )

    return helpers, expected, (test_node,), coverage_member


def _behavior_readiness(
    scenario: BlueprintScenario,
    manifest: SoftwareBlueprintManifest,
    binding_report: ModelImplementationBindingReport,
):
    (
        delegated_helpers,
        delegated_helper_fingerprints,
        test_nodes,
        delegated_coverage_member,
    ) = _delegated_assertion_fixture(scenario)
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
    intent = _intent_inventory(scenario)
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
        model_fingerprint=CURRENT_MODEL_FINGERPRINT,
        owner_contract_id=OWNER_CONTRACT_ID,
        owner_id="owner:model",
        function_relation="Input x State -> Set(Output x State)",
        dimensions=dimensions,
        semantic_spec_ids=(SEMANTIC_SPEC_ID,),
        oracle_ids=(ORACLE_ID,),
        intent_contribution_ids=tuple(
            row.contribution_id
            for row in intent.contributions
            if row.disposition == "accepted"
        ),
        portable_binding_ids=("portable:save-record",),
        protected_failure_ids=("failure:invalid-record",),
        accepted=accepted,
        acceptance_evidence_fingerprints=acceptance_evidence,
        source_fingerprint=CURRENT_SURFACE_FINGERPRINT,
    )
    path_quality_subject = PathQualitySubject(
        model_id=MODEL_ELEMENT_ID,
        boundary_id=f"path-boundary:{MODEL_ELEMENT_ID}",
        model_fingerprint=CURRENT_MODEL_FINGERPRINT,
        normalized_facts_fingerprint=_fingerprint("path-quality:normalized-facts"),
        retained_element_inventory_fingerprint=_fingerprint(
            "path-quality:retained-elements"
        ),
        purpose_fingerprint=_fingerprint("path-quality:purpose"),
        intent_fingerprint=_fingerprint("path-quality:intent"),
        obligation_fingerprint=_fingerprint("path-quality:obligations"),
        provider_fingerprint=_fingerprint("path-quality:provider"),
        dependency_fingerprint=_fingerprint("path-quality:dependencies"),
        code_fingerprint=CURRENT_SURFACE_FINGERPRINT,
        test_fingerprint=CURRENT_TEST_FINGERPRINT,
        oracle_fingerprint=CURRENT_ORACLE_FINGERPRINT,
        evidence_fingerprint=_fingerprint("path-quality:evidence"),
        currentness_id=CURRENT_PATH_QUALITY_ID,
    )
    path_quality_result = PathQualityResult(
        result_id=f"path-quality:{MODEL_ELEMENT_ID}",
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
        necessity_witness_set_fingerprint=_fingerprint(
            "path-quality:necessity-witnesses"
        ),
        detail_evidence_fingerprint=_fingerprint("path-quality:detail"),
        producer_id="model_maturation",
        currentness_id=CURRENT_PATH_QUALITY_ID,
        current=True,
    )
    path_quality_binding = ModelPathQualityBlueprintBinding(
        model_element_id=MODEL_ELEMENT_ID,
        subject_lane="observed",
        change_kind="materially_changed",
        subject=path_quality_subject,
        result=path_quality_result,
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
                    semantic_content_fingerprint=(
                        scenario.semantic_specs[0].source_content_fingerprint
                    ),
                    owner_contract_id=OWNER_CONTRACT_ID,
                    behavior_owner_id="owner:model",
                    implementation_content_fingerprint=CURRENT_SURFACE_FINGERPRINT,
                    test_node_id="test:save-record",
                    oracle_member_id=member_id,
                    oracle_member_fingerprint=member_fingerprint,
                    case_id=case.case_id,
                    case_content_fingerprint=case.content_fingerprint,
                    covered_dimensions=(dimension,),
                    evidence_role="planned_checker",
                    oracle_id=ORACLE_ID,
                    oracle_content_fingerprint=(
                        scenario.oracles[0].source_content_fingerprint
                    ),
                )
            )
    if delegated_coverage_member is not None:
        coverage_rows[0] = replace(
            coverage_rows[0],
            oracle_member_id=delegated_coverage_member[0],
            oracle_member_fingerprint=delegated_coverage_member[1],
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
    supporting_surfaces = tuple(
        surface
        for surface in scenario.inventory.surfaces
        if surface.disposition == IMPLEMENTATION_DISPOSITION_SUPPORTING
    )
    behavior_block_ids_by_surface = {
        contract.implementation_surface_id: contract.behavior_block_id
    }
    behavior_report = review_behavior_blueprint(
        inventory_fingerprint=scenario.inventory.fingerprint,
        required_behavior_surface_ids=(SURFACE_ID,),
        supporting_surface_ids=tuple(
            surface.surface_id for surface in supporting_surfaces
        ),
        contracts=(contract,),
        portable_bindings=(portable,),
        case_contracts=cases,
        supporting_relations=tuple(
            SupportingSurfaceRelation(
                supporting_surface_id=surface.surface_id,
                behavior_block_id=contract.behavior_block_id,
                relation_kind=(
                    "calls" if surface.surface_kind == "helper" else "delegates"
                ),
                evidence_id=f"supporting-edge:{surface.surface_id}",
                evidence_fingerprint=surface.content_fingerprint,
                rationale=(
                    "the structural surface remains supporting and delegates to "
                    "the one independently contracted save-record behavior"
                ),
            )
            for surface in supporting_surfaces
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
        semantic_specs=scenario.semantic_specs,
        oracles=scenario.oracles,
        intent_inventory=intent,
        implementation_source_fingerprints={
            SURFACE_ID: CURRENT_SURFACE_FINGERPRINT
        },
        implementation_owner_ids={SURFACE_ID: "owner:model"},
        test_nodes=test_nodes,
        planned_checker_fingerprints=planned_checker_fingerprints,
        delegated_assertion_helpers=delegated_helpers,
        delegated_helper_fingerprints=delegated_helper_fingerprints,
        expected_portable_fingerprints={
            "portable:model-system": CURRENT_PORTABLE_OWNER_FINGERPRINT
        },
        supporting_surface_fingerprints={
            surface.surface_id: surface.content_fingerprint
            for surface in supporting_surfaces
        },
        supporting_surface_owner_block_ids={
            surface.surface_id: behavior_block_ids_by_surface.get(
                surface.owning_surface_id,
                "",
            )
            for surface in supporting_surfaces
        },
        path_quality_bindings=(path_quality_binding,),
        expected_path_quality_currentness_id=CURRENT_PATH_QUALITY_ID,
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
                consuming_behavior_ids=(contract.behavior_block_id,),
                consuming_model_ids=(MODEL_ELEMENT_ID,),
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
            consuming_behavior_ids=(contract.behavior_block_id,),
            consuming_model_ids=(MODEL_ELEMENT_ID,),
            observed_resource=(
                None
                if category == "external_service"
                else ObservedResourceMember(
                    resource_id=f"resource:{category}",
                    kind=(
                        "verification"
                        if category == "behavioral_oracle"
                        else category
                    ),
                    owner_id="owner:save-record",
                    artifact_id=f"artifact:{category}",
                    subject_revision=CURRENT_SNAPSHOT_FINGERPRINT,
                    current_artifact_fingerprint=_fingerprint(
                        f"resource:{category}"
                    ),
                    provider_id="provider:fixture-observation",
                    capability_id="resource_inventory",
                    payload_id="resource_inventory",
                )
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
    shared = {
        SEMANTIC_SPEC_ID: _semantic_spec().to_dict(),
        ORACLE_ID: _oracle().to_dict(),
        test_nodes[0].node_id: {"kind": "real_test_node"},
        "assertion:save-record": {"kind": "real_test_assertion"},
        **{
            helper.helper_id: {
                "kind": "delegated_assertion_helper",
                "fingerprint": helper.source_fingerprint,
                "test_node_id": helper.test_node_id,
                "callee_member_ids": list(helper.callee_member_ids),
                "terminal_member_fingerprints": [
                    list(row) for row in helper.terminal_member_fingerprints
                ],
            }
            for helper in delegated_helpers
        },
        **{
            member_id: {"kind": "planned_checker", "fingerprint": fingerprint}
            for member_id, fingerprint in planned_checker_fingerprints.items()
        },
        **{row.case_id: row.to_dict() for row in cases},
        **{
            row.coverage_id: {
                "kind": "behavior_coverage_edge",
                **row.to_dict(),
            }
            for row in coverage
        },
    }
    coverage_reference_shards = materialize_behavior_blueprint_shards(
        behavior_report,
        shared_objects=shared,
    )
    projection = normalize_behavior_blueprint(
        blueprint_fingerprint=manifest.fingerprint,
        behavior_report=behavior_report,
        shared_objects=shared,
        coverage_reference_shards=coverage_reference_shards,
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


def _delegated_assertion_status(
    scenario: BlueprintScenario,
    behavior_report,
) -> str:
    if scenario.delegated_helper_mode == "none":
        return "not_applicable"
    if DELEGATED_ASSERTION_FINDING_CODES.intersection(
        _finding_codes(behavior_report.findings)
    ):
        return "blocked"
    return "current"


def _target_system_report(behavior_report, readiness):
    descriptor = TargetSystemDescriptor(
        target_system_id="target:save-record-workflow",
        target_kind="mixed",
        target_profile="software",
        subject_revision=CURRENT_SNAPSHOT_FINGERPRINT,
        boundary_fingerprint=_fingerprint("boundary:save-record-target"),
        required_observation_capabilities=(
            "implementation_inventory",
            "test_inventory",
        ),
        required_authority_capabilities=(
            "behavior_semantics",
            "portable_behavior",
        ),
        claim_boundary="the bounded save-record software/workflow fixture only",
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
    frozen = FrozenTargetSystemEvidence(
        evidence_id="frozen:save-record",
        layer_plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        provider_registry=registry,
        provider_results=providers,
        snapshot=snapshot,
        claim_boundary=(
            "Only the exact synthetic provider results used by this bounded model."
        ),
    )
    return _assemble_target_system_blueprint(
        descriptor,
        frozen,
        downstream_layers=tuple(
            BlueprintLayerResult._derived(
                layer=layer,
                status="pass",
                evidence_ids=(
                    behavior_report.fingerprint,
                    readiness.fingerprint,
                    _fingerprint(f"native-report:{layer}"),
                ),
                native_reports=(
                    BlueprintNativeReportRef(
                        owner_id=f"model-native-owner:{layer}",
                        report_id=f"model-native-report:{layer}",
                        report_fingerprint=_fingerprint(
                            f"native-report:{layer}"
                        ),
                    ),
                ),
                pre_code_status="ready",
                executed_evidence_status="not_applicable",
            )
            for layer in CANONICAL_SOFTWARE_LAYER_PLAN.layer_ids[1:]
        ),
    )


class ReviewImplementationBlueprint:
    name = "ReviewImplementationBlueprint"
    reads = (
        "scenario_id",
        "phase",
        "inventory_status",
        "binding_status",
        "static_manifest_status",
        "behavior_status",
        "readiness_status",
        "target_system_status",
        "projection_status",
        "observed_snapshot_input_status",
        "intent_snapshot_status",
        "intent_owner_projection_status",
        "semantic_intent_lineage_status",
        "surface_classification_status",
        "semantic_authority_status",
        "current_pass_evidence_status",
        "delegated_assertion_status",
        "finding_codes",
        "done_claim",
        "claim_boundary",
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
            if not scenario.observed_snapshot_initialized_before_resource_observation:
                yield self._blocked(
                    state,
                    scenario,
                    ("resource_observation_snapshot_input_uninitialized",),
                    observed_snapshot_input_status="blocked",
                )
                return
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
            authority_findings, authority_status = _authority_contract_review(
                scenario
            )
            if authority_findings:
                yield self._blocked(
                    state,
                    scenario,
                    authority_findings,
                    inventory_status="complete",
                    observed_snapshot_input_status="current",
                    **authority_status,
                )
                return
            yield FunctionResult(
                BlueprintOutput("inventory_complete"),
                replace(
                    state,
                    scenario_id=scenario.scenario_id,
                    phase="inventory_complete",
                    inventory_status="complete",
                    observed_snapshot_input_status="current",
                    **authority_status,
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
            qualification = _qualify_blueprint_manifest(
                manifest,
                report,
                implementation_inventory=scenario.inventory,
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
            if not qualification.static_manifest_ready:
                yield self._blocked(
                    state,
                    scenario,
                    finding_codes,
                    static_manifest_status=(
                        qualification.static_manifest_status
                    ),
                )
                return
            yield FunctionResult(
                BlueprintOutput("manifest_qualification_complete"),
                replace(
                    state,
                    phase="manifest_complete",
                    static_manifest_status=(
                        qualification.static_manifest_status
                    ),
                    finding_codes=(),
                ),
                label="manifest_qualification_complete",
            )
            return

        if state.phase == "manifest_complete":
            behavior_report, readiness = _behavior_readiness(
                scenario,
                manifest,
                report,
            )
            delegated_assertion_status = _delegated_assertion_status(
                scenario,
                behavior_report,
            )
            finding_codes = _finding_codes(readiness.findings)
            if readiness.status != "ready":
                yield self._blocked(
                    state,
                    scenario,
                    finding_codes,
                    behavior_status=behavior_report.pre_code_status,
                    readiness_status=readiness.status,
                    delegated_assertion_status=delegated_assertion_status,
                )
                return
            yield FunctionResult(
                BlueprintOutput("behavior_readiness_complete"),
                replace(
                    state,
                    phase="readiness_complete",
                    behavior_status="complete",
                    readiness_status="ready",
                    delegated_assertion_status=delegated_assertion_status,
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
                    claim_boundary=(MODEL_CLAIM_BOUNDARY if accepted else ""),
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
            claim_boundary="",
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


def no_done_without_exact_blueprint_path(
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


def accepted_claim_matches_scope_boundary(
    state: BlueprintState,
    trace,
) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and state.claim_boundary != MODEL_CLAIM_BOUNDARY:
        return InvariantResult.fail(
            "accepted closure used a claim outside the bounded model boundary"
        )
    return InvariantResult.pass_()


def resource_observation_requires_current_observed_snapshot_input(
    state: BlueprintState,
    trace,
) -> InvariantResult:
    del trace
    resource_observation_reached = state.phase in {
        "inventory_complete",
        "binding_complete",
        "manifest_complete",
        "readiness_complete",
        "target_system_complete",
        "projection_complete",
        "done",
    }
    if (
        resource_observation_reached
        and state.observed_snapshot_input_status != "current"
    ):
        return InvariantResult.fail(
            "resource observation became reachable before the exact current observed-snapshot input was initialized"
        )
    return InvariantResult.pass_()


def accepted_intent_uses_observed_snapshot_identity(
    state: BlueprintState,
    trace,
) -> InvariantResult:
    del trace
    if state.done_claim != "accepted":
        return InvariantResult.pass_()
    scenario = SCENARIOS[state.scenario_id]
    intent = _intent_inventory(scenario)
    if (
        intent.subject_revision != CURRENT_SNAPSHOT_FINGERPRINT
        or intent.observed_subject_revision != CURRENT_SNAPSHOT_FINGERPRINT
        or intent.subject_revision != intent.observed_subject_revision
    ):
        return InvariantResult.fail(
            "accepted intent uses a source-inventory identity instead of the exact observed snapshot identity"
        )
    return InvariantResult.pass_()


def accepted_intent_projects_all_exact_realized_owners(
    state: BlueprintState,
    trace,
) -> InvariantResult:
    del trace
    if state.done_claim != "accepted":
        return InvariantResult.pass_()
    scenario = SCENARIOS[state.scenario_id]
    if set(_scenario_projected_realized_owner_ids(scenario)) != set(
        _scenario_expected_realized_owner_ids(scenario)
    ):
        return InvariantResult.fail(
            "accepted intent omits or invents an exact realized model owner"
        )
    return InvariantResult.pass_()


def behavior_semantics_bind_exact_intent_and_expectation(
    state: BlueprintState,
    trace,
) -> InvariantResult:
    del trace
    if state.done_claim != "accepted":
        return InvariantResult.pass_()
    scenario = SCENARIOS[state.scenario_id]
    intent = _intent_inventory(scenario)
    if not intent.contributions or not scenario.semantic_specs:
        return InvariantResult.fail(
            "accepted behavior lacks an exact intent contribution or semantic specification"
        )
    for contribution in intent.contributions:
        required_pairs = {
            (contribution.source_id, contribution.source_fingerprint),
            (
                contribution.expectation_id,
                contribution.expectation_fingerprint,
            ),
        }
        if any(
            not required_pairs.issubset(
                set(reference.provenance_fingerprints)
            )
            for reference in scenario.semantic_specs
        ):
            return InvariantResult.fail(
                "behavior semantics do not bind the exact accepted intent source and expectation identities"
            )
    return InvariantResult.pass_()


def structural_surfaces_need_independent_contract_for_behavior(
    state: BlueprintState,
    trace,
) -> InvariantResult:
    del trace
    if state.done_claim != "accepted":
        return InvariantResult.pass_()
    scenario = SCENARIOS[state.scenario_id]
    contracted = set(_scenario_independently_contracted_surface_ids(scenario))
    if any(
        surface.surface_kind in {"module", "class", "helper"}
        and surface.disposition == IMPLEMENTATION_DISPOSITION_MODEL
        and surface.surface_id not in contracted
        for surface in scenario.inventory.surfaces
    ):
        return InvariantResult.fail(
            "module, class aggregate, or nested/pure helper was promoted to behavior without an independent Input x State -> Set(Output x State) contract"
        )
    return InvariantResult.pass_()


def self_model_files_cannot_own_behavior_semantics(
    state: BlueprintState,
    trace,
) -> InvariantResult:
    del trace
    if state.done_claim != "accepted":
        return InvariantResult.pass_()
    scenario = SCENARIOS[state.scenario_id]
    if any(
        reference.source_id in SELF_SEMANTIC_AUTHORITY_SOURCE_IDS
        for reference in scenario.semantic_specs
    ):
        return InvariantResult.fail(
            "implementation_blueprint model.py or run_checks.py certifies its own behavior semantics"
        )
    return InvariantResult.pass_()


def current_pass_requires_independent_evidence(
    state: BlueprintState,
    trace,
) -> InvariantResult:
    del trace
    if state.done_claim != "accepted":
        return InvariantResult.pass_()
    evidence = _scenario_current_pass_evidence(SCENARIOS[state.scenario_id])
    if (
        not evidence
        or any(
            row.origin_kind in FORBIDDEN_SELF_CURRENT_EVIDENCE_ORIGINS
            or not row.independently_verified
            or row.subject_revision != CURRENT_SNAPSHOT_FINGERPRINT
            for row in evidence
        )
    ):
        return InvariantResult.fail(
            "a checked-in declaration or self-built projection certifies its own current pass"
        )
    return InvariantResult.pass_()


def accepted_delegated_checker_has_current_direct_terminal(
    state: BlueprintState,
    trace,
) -> InvariantResult:
    del trace
    if state.done_claim != "accepted":
        return InvariantResult.pass_()
    scenario = SCENARIOS[state.scenario_id]
    if scenario.delegated_helper_mode == "none":
        if state.delegated_assertion_status != "not_applicable":
            return InvariantResult.fail(
                "a blueprint without delegated assertion calls has a delegated status"
            )
        return InvariantResult.pass_()
    helpers, expected, test_nodes, coverage_member = (
        _delegated_assertion_fixture(scenario)
    )
    if (
        state.delegated_assertion_status != "current"
        or len(helpers) != 1
        or coverage_member is None
    ):
        return InvariantResult.fail(
            "accepted delegated coverage lacks one current helper owner"
        )
    helper = helpers[0]
    if (
        expected.get(helper.helper_id) != helper.source_fingerprint
        or helper.test_node_id != test_nodes[0].node_id
        or coverage_member
        != (helper.helper_id, helper.source_fingerprint)
        or helper.callee_member_ids
        or not helper.terminal_member_fingerprints
    ):
        return InvariantResult.fail(
            "accepted delegated coverage is not bound to a current direct terminal"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_done_without_exact_blueprint_path",
        "A done claim requires exact inventory, binding, behavior, target-system, and projection gates.",
        no_done_without_exact_blueprint_path,
    ),
    Invariant(
        "accepted_claim_matches_scope_boundary",
        "The accepted claim remains inside the bounded model boundary.",
        accepted_claim_matches_scope_boundary,
    ),
    Invariant(
        "resource_observation_requires_current_observed_snapshot_input",
        "Resource observation cannot begin before the exact current observed-snapshot input is initialized.",
        resource_observation_requires_current_observed_snapshot_input,
    ),
    Invariant(
        "accepted_intent_uses_observed_snapshot_identity",
        "Accepted intent is keyed to the exact observed snapshot, never the source inventory identity.",
        accepted_intent_uses_observed_snapshot_identity,
    ),
    Invariant(
        "accepted_intent_projects_all_exact_realized_owners",
        "Accepted intent projects every and only exact realized model owner.",
        accepted_intent_projects_all_exact_realized_owners,
    ),
    Invariant(
        "behavior_semantics_bind_exact_intent_and_expectation",
        "Every behavior semantic source binds exact accepted source and expectation identities and fingerprints.",
        behavior_semantics_bind_exact_intent_and_expectation,
    ),
    Invariant(
        "structural_surfaces_need_independent_contract_for_behavior",
        "Aggregate and helper surfaces remain supporting unless they own an independent behavior contract.",
        structural_surfaces_need_independent_contract_for_behavior,
    ),
    Invariant(
        "self_model_files_cannot_own_behavior_semantics",
        "The executable model and its runner cannot certify their own behavior semantics.",
        self_model_files_cannot_own_behavior_semantics,
    ),
    Invariant(
        "current_pass_requires_independent_evidence",
        "A checked-in declaration or self-built projection cannot certify its own current pass.",
        current_pass_requires_independent_evidence,
    ),
    Invariant(
        "accepted_delegated_checker_has_current_direct_terminal",
        "Accepted delegated coverage owns one current direct terminal in the same test node.",
        accepted_delegated_checker_has_current_direct_terminal,
    ),
)

GOOD_ACTION = BlueprintAction("advance_blueprint_review")
GOOD_ACTIONS = tuple(
    BlueprintAction("advance_blueprint_review", scenario_id=scenario_id)
    for scenario_id in GOOD_SCENARIO_IDS
)
BAD_ACTIONS = tuple(
    BlueprintAction("advance_blueprint_review", scenario_id=scenario_id)
    for scenario_id in BAD_SCENARIO_IDS
)
MAX_SEQUENCE_LENGTH = 7

NATIVE_PYTEST_SELECTORS = (
    "tests/test_software_blueprint_readiness.py::test_delegated_assertion_helpers_require_current_terminal_acyclic_paths",
    "tests/test_software_blueprint_readiness.py::test_placeholder_or_cross_test_member_cannot_close_coverage",
    "tests/test_implementation_blueprint.py::test_supporting_oracle_surface_can_delegate_without_self_certifying_behavior",
)
NATIVE_TEST_OBLIGATION_BINDINGS = (
    (
        "delegated_checker_requires_current_terminal_graph",
        NATIVE_PYTEST_SELECTORS[0],
    ),
    (
        "delegated_checker_cannot_borrow_sibling_test_ownership",
        NATIVE_PYTEST_SELECTORS[1],
    ),
    (
        "supporting_oracle_surface_is_traceability_not_self_certification",
        NATIVE_PYTEST_SELECTORS[2],
    ),
)


def native_test_obligation_bindings_are_executed() -> bool:
    obligation_ids = tuple(row[0] for row in NATIVE_TEST_OBLIGATION_BINDINGS)
    evidence_nodes = tuple(row[1] for row in NATIVE_TEST_OBLIGATION_BINDINGS)
    selected = set(NATIVE_PYTEST_SELECTORS)
    selected_files = {item for item in selected if "::" not in item}
    return (
        len(obligation_ids) == len(set(obligation_ids))
        and len(evidence_nodes) == len(set(evidence_nodes))
        and all(
            node in selected or node.split("::", 1)[0] in selected_files
            for node in evidence_nodes
        )
    )


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
    "GOOD_ACTIONS",
    "GOOD_SCENARIO_IDS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "SCENARIOS",
    "NATIVE_PYTEST_SELECTORS",
    "NATIVE_TEST_OBLIGATION_BINDINGS",
    "build_workflow",
    "initial_state",
    "native_test_obligation_bindings_are_executed",
    "terminal_predicate",
]
