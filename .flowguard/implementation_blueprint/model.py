"""Executable FlowGuard model for a source-independent software blueprint.

The model consumes the current implementation-inventory and
implementation-blueprint APIs.  It keeps static blueprint closure separate
from empirical reconstruction and never starts reconstruction implicitly.

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


STATIC_NOT_RUN = "not_run"
PROJECTION_NOT_RUN = "not_run"
PROJECTION_COMPLETE = "complete"
PROJECTION_BLOCKED = "blocked"
EMPIRICAL_NOT_RUN = "not_run"


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
    expected_finding_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlueprintAction:
    action_type: str
    scenario_id: str = "complete"
    reconstruction_requested: bool = False
    automatic_rebuild_requested: bool = False


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
    empirical_status: str = EMPIRICAL_NOT_RUN
    projection_status: str = PROJECTION_NOT_RUN
    finding_codes: tuple[str, ...] = ()
    reconstruction_requested: bool = False
    automatic_rebuild_attempted: bool = False
    reconstruction_executed: bool = False
    done_claim: str = "none"
    claim_text: str = ""

    def ready_for_done(self) -> bool:
        return (
            self.inventory_status == "complete"
            and self.binding_status == "complete"
            and self.static_status == "complete"
            and self.empirical_status == EMPIRICAL_NOT_RUN
            and self.projection_status == PROJECTION_COMPLETE
            and not self.reconstruction_requested
            and not self.automatic_rebuild_attempted
            and not self.reconstruction_executed
            and not self.finding_codes
        )


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
            "Static implementation discovery only; model bindings and empirical "
            "reconstruction remain separate authorities."
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


def _finding_codes(findings) -> tuple[str, ...]:
    return tuple(sorted({str(finding.code) for finding in findings}))


class ReviewImplementationBlueprint:
    name = "ReviewImplementationBlueprint"
    reads = (
        "scenario_id",
        "phase",
        "inventory_status",
        "binding_status",
        "static_status",
        "empirical_status",
        "projection_status",
        "finding_codes",
        "reconstruction_requested",
        "automatic_rebuild_attempted",
        "reconstruction_executed",
        "done_claim",
        "claim_text",
    )
    writes = reads
    accepted_input_type = BlueprintAction
    input_description = "one bounded blueprint-review action"
    output_description = "static/empirical blueprint state and bounded claim"
    idempotency = (
        "Static closure may complete with empirical reconstruction not run; "
        "reconstruction requires a separate explicit owner and evidence."
    )

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
        if input_obj.automatic_rebuild_requested:
            yield FunctionResult(
                BlueprintOutput("automatic_rebuild_attempt_blocked"),
                replace(
                    state,
                    scenario_id=scenario.scenario_id,
                    phase="blocked",
                    empirical_status=EMPIRICAL_NOT_RUN,
                    automatic_rebuild_attempted=True,
                    finding_codes=("automatic_reconstruction_forbidden",),
                    done_claim="rejected",
                    claim_text="blueprint review blocked; reconstruction not run",
                ),
                label="automatic_rebuild_attempt_blocked",
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
                reconstruction_required=input_obj.reconstruction_requested,
                current_observed_snapshot_fingerprint=CURRENT_SNAPSHOT_FINGERPRINT,
                current_semantic_mesh_fingerprint=CURRENT_MESH_FINGERPRINT,
                current_portable_owner_fingerprints={
                    "portable:model-system": CURRENT_PORTABLE_OWNER_FINGERPRINT
                },
                current_resource_fingerprints={
                    RESOURCE_ID: CURRENT_RUNTIME_FINGERPRINT
                },
                current_oracle_fingerprints={ORACLE_ID: CURRENT_ORACLE_FINGERPRINT},
            )
            finding_codes = _finding_codes(qualification.static_findings)
            if (
                qualification.static_status != "complete"
                or input_obj.reconstruction_requested
            ):
                if input_obj.reconstruction_requested and not finding_codes:
                    finding_codes = ("explicit_reconstruction_evidence_missing",)
                yield self._blocked(
                    state,
                    scenario,
                    finding_codes,
                    static_status=qualification.static_status,
                    empirical_status=qualification.empirical_status,
                    reconstruction_requested=input_obj.reconstruction_requested,
                )
                return
            yield FunctionResult(
                BlueprintOutput("static_complete_empirical_not_run"),
                replace(
                    state,
                    phase="static_complete",
                    static_status=qualification.static_status,
                    empirical_status=qualification.empirical_status,
                    reconstruction_requested=False,
                    finding_codes=(),
                    claim_text=qualification.claim_text,
                ),
                label="static_complete_empirical_not_run",
            )
            return

        if state.phase == "static_complete":
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
                        "blueprint complete; reconstruction not verified"
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
            claim_text="blueprint review blocked; reconstruction not run",
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
            "projection, or no-reconstruction gates"
        )
    return InvariantResult.pass_()


def reconstruction_is_never_implicit(
    state: BlueprintState,
    trace,
) -> InvariantResult:
    del trace
    if state.reconstruction_executed:
        return InvariantResult.fail(
            "blueprint review executed reconstruction without a separate explicit owner"
        )
    if state.automatic_rebuild_attempted and state.empirical_status != EMPIRICAL_NOT_RUN:
        return InvariantResult.fail(
            "automatic reconstruction attempt changed empirical status instead of remaining not_run"
        )
    return InvariantResult.pass_()


def static_and_empirical_status_stay_separate(
    state: BlueprintState,
    trace,
) -> InvariantResult:
    del trace
    if state.static_status == "complete" and state.done_claim == "accepted" and (
        state.empirical_status != EMPIRICAL_NOT_RUN
        or state.claim_text != "blueprint complete; reconstruction not verified"
    ):
        return InvariantResult.fail(
            "static blueprint completion was presented as empirical reconstruction evidence"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_static_done_without_exact_blueprint",
        "A done claim requires exact inventory, binding, static, projection, and no-rebuild gates.",
        no_static_done_without_exact_blueprint,
    ),
    Invariant(
        "reconstruction_is_never_implicit",
        "Static review never runs reconstruction automatically.",
        reconstruction_is_never_implicit,
    ),
    Invariant(
        "static_and_empirical_status_stay_separate",
        "Static completeness and empirical reconstruction remain separate statuses and claims.",
        static_and_empirical_status_stay_separate,
    ),
)

GOOD_ACTION = BlueprintAction("advance_blueprint_review")
BAD_ACTIONS = tuple(
    BlueprintAction("advance_blueprint_review", scenario_id=scenario_id)
    for scenario_id in BAD_SCENARIO_IDS
) + (
    BlueprintAction(
        "advance_blueprint_review",
        scenario_id="complete",
        automatic_rebuild_requested=True,
    ),
)
MAX_SEQUENCE_LENGTH = 5


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
