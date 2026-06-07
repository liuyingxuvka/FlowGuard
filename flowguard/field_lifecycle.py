"""Field lifecycle mesh helpers.

This module records every in-scope field at leaf level, then projects
behavior-bearing fields into existing FlowGuard route evidence. It does not
replace Model-Test Alignment, Architecture Reduction, Model-Miss Review, or
DevelopmentProcessFlow; it provides the field inventory and handoff rows those
routes can consume.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .model_test_alignment import (
    CodeContract,
    ModelObligation,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    TEST_KIND_NEGATIVE_PATH,
    TEST_KIND_REPLAY,
)


FIELD_ROLE_STATE = "state"
FIELD_ROLE_ROUTING = "routing"
FIELD_ROLE_PERMISSION = "permission"
FIELD_ROLE_FEATURE_FLAG = "feature_flag"
FIELD_ROLE_SCHEMA_VERSION = "schema_version"
FIELD_ROLE_PERSISTED = "persisted"
FIELD_ROLE_PRESENTATION = "presentation"
FIELD_ROLE_METADATA = "metadata"
FIELD_ROLE_PROMPT_CONFIG = "prompt_config"
FIELD_ROLES = (
    FIELD_ROLE_STATE,
    FIELD_ROLE_ROUTING,
    FIELD_ROLE_PERMISSION,
    FIELD_ROLE_FEATURE_FLAG,
    FIELD_ROLE_SCHEMA_VERSION,
    FIELD_ROLE_PERSISTED,
    FIELD_ROLE_PRESENTATION,
    FIELD_ROLE_METADATA,
    FIELD_ROLE_PROMPT_CONFIG,
)

FIELD_LIFECYCLE_ACTIVE = "active"
FIELD_LIFECYCLE_NEW = "new"
FIELD_LIFECYCLE_OLD = "old"
FIELD_LIFECYCLE_REPLACED = "replaced"
FIELD_LIFECYCLE_DEPRECATED = "deprecated"
FIELD_LIFECYCLE_DERIVED = "derived"
FIELD_LIFECYCLE_ARCHIVE_ONLY = "archive_only"
FIELD_LIFECYCLES = (
    FIELD_LIFECYCLE_ACTIVE,
    FIELD_LIFECYCLE_NEW,
    FIELD_LIFECYCLE_OLD,
    FIELD_LIFECYCLE_REPLACED,
    FIELD_LIFECYCLE_DEPRECATED,
    FIELD_LIFECYCLE_DERIVED,
    FIELD_LIFECYCLE_ARCHIVE_ONLY,
)

FIELD_IMPACT_NONE = "none"
FIELD_IMPACT_STATE = "state"
FIELD_IMPACT_ROUTING = "routing"
FIELD_IMPACT_PERMISSION = "permission"
FIELD_IMPACT_SIDE_EFFECT = "side_effect"
FIELD_IMPACT_EXTERNAL_CONTRACT = "external_contract"
FIELD_IMPACT_SCHEMA = "schema"
FIELD_IMPACT_REPLAY = "replay"
FIELD_IMPACT_MIGRATION = "migration"
FIELD_IMPACTS = (
    FIELD_IMPACT_NONE,
    FIELD_IMPACT_STATE,
    FIELD_IMPACT_ROUTING,
    FIELD_IMPACT_PERMISSION,
    FIELD_IMPACT_SIDE_EFFECT,
    FIELD_IMPACT_EXTERNAL_CONTRACT,
    FIELD_IMPACT_SCHEMA,
    FIELD_IMPACT_REPLAY,
    FIELD_IMPACT_MIGRATION,
)
BEHAVIOR_FIELD_IMPACTS = tuple(impact for impact in FIELD_IMPACTS if impact != FIELD_IMPACT_NONE)

FIELD_DISPOSITION_UNKNOWN = "unknown"
FIELD_DISPOSITION_DELETED = "deleted"
FIELD_DISPOSITION_BLOCKED = "blocked"
FIELD_DISPOSITION_MIGRATED = "migrated"
FIELD_DISPOSITION_DELEGATED = "delegated_to_new_field"
FIELD_DISPOSITION_SAME_CONTRACT_REPAIRED = "same_contract_repaired"
FIELD_DISPOSITION_EXPLICITLY_PRESERVED = "explicitly_preserved"
FIELD_DISPOSITION_OUT_OF_SCOPE = "out_of_scope"
FIELD_DISPOSITIONS = (
    FIELD_DISPOSITION_UNKNOWN,
    FIELD_DISPOSITION_DELETED,
    FIELD_DISPOSITION_BLOCKED,
    FIELD_DISPOSITION_MIGRATED,
    FIELD_DISPOSITION_DELEGATED,
    FIELD_DISPOSITION_SAME_CONTRACT_REPAIRED,
    FIELD_DISPOSITION_EXPLICITLY_PRESERVED,
    FIELD_DISPOSITION_OUT_OF_SCOPE,
)
PASSING_FIELD_DISPOSITIONS = (
    FIELD_DISPOSITION_DELETED,
    FIELD_DISPOSITION_BLOCKED,
    FIELD_DISPOSITION_MIGRATED,
    FIELD_DISPOSITION_DELEGATED,
    FIELD_DISPOSITION_SAME_CONTRACT_REPAIRED,
    FIELD_DISPOSITION_EXPLICITLY_PRESERVED,
    FIELD_DISPOSITION_OUT_OF_SCOPE,
)

FIELD_CONFIDENCE_FULL = "full"
FIELD_CONFIDENCE_SCOPED = "scoped"
FIELD_CONFIDENCE_BLOCKED = "blocked"
FIELD_DECISION_FULL = "field_lifecycle_full"
FIELD_DECISION_SCOPED = "field_lifecycle_scoped"
FIELD_DECISION_BLOCKED = "field_lifecycle_blocked"

FIELD_FINDING_INFO = "info"
FIELD_FINDING_GAP = "gap"
FIELD_FINDING_BLOCKER = "blocker"

FIELD_ROUTE_MODEL_FIRST = "model_first_function_flow"
FIELD_ROUTE_MODEL_TEST_ALIGNMENT = "model_test_alignment"
FIELD_ROUTE_CODE_STRUCTURE = "code_structure_recommendation"
FIELD_ROUTE_ARCHITECTURE_REDUCTION = "architecture_reduction"
FIELD_ROUTE_MODEL_MISS_REVIEW = "model_miss_review"
FIELD_ROUTE_DEVELOPMENT_PROCESS_FLOW = "development_process_flow"
FIELD_ROUTE_CLOSURE_CONTRACT = "flowguard_closure_contract"
FIELD_ROUTE_MODEL_MESH = "model_mesh"
FIELD_ROUTE_TEST_MESH = "test_mesh"
FIELD_ROUTE_RUNTIME_GATEWAY = "runtime_gateway_adoption"

FIELD_EVIDENCE_REF_GATE = "gate"
FIELD_EVIDENCE_REF_TEST = "test"
FIELD_EVIDENCE_REF_REPLAY = "replay"
FIELD_EVIDENCE_REF_KINDS = (
    FIELD_EVIDENCE_REF_GATE,
    FIELD_EVIDENCE_REF_TEST,
    FIELD_EVIDENCE_REF_REPLAY,
)

BROAD_FIELD_CLAIM_SCOPES = (
    "full",
    "runtime",
    "runtime_gateway",
    "production",
    "release",
    "closure",
    "broad",
)


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values if str(value))


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return tuple(result)


def _field_claim_scope_requires_route_refs(claim_scope: str) -> bool:
    normalized = str(claim_scope).strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in BROAD_FIELD_CLAIM_SCOPES


def _evidence_ref_kind(ref: str) -> str:
    prefix = str(ref).split(":", 1)[0].strip().lower()
    if prefix in {"gate", "boundary", "runtime_gate", "runtime_gateway"}:
        return FIELD_EVIDENCE_REF_GATE
    if prefix in {"test", "negative_test", "failure_test"}:
        return FIELD_EVIDENCE_REF_TEST
    if prefix in {"replay", "runtime_replay", "conformance_replay"}:
        return FIELD_EVIDENCE_REF_REPLAY
    return ""


def _evidence_ref_kinds(refs: Sequence[str]) -> set[str]:
    return {kind for kind in (_evidence_ref_kind(ref) for ref in refs) if kind}


def _projection_requires_negative_test_ref(projection: "FieldProjection") -> bool:
    return bool({TEST_KIND_FAILURE_PATH, TEST_KIND_NEGATIVE_PATH} & set(projection.required_test_kinds))


def _projection_requires_replay_ref(row: "FieldLifecycleRow", projection: "FieldProjection") -> bool:
    return TEST_KIND_REPLAY in projection.required_test_kinds or FIELD_IMPACT_REPLAY in row.behavior_impacts


@dataclass(frozen=True)
class FieldLifecycleGroup:
    """Parent or child field group, such as entity, payload, schema, or config."""

    group_id: str
    boundary_kind: str = ""
    parent_group_id: str = ""
    field_ids: tuple[str, ...] = ()
    child_group_ids: tuple[str, ...] = ()
    owner_route: str = ""
    evidence_refs: tuple[str, ...] = ()
    rationale: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "group_id", str(self.group_id))
        object.__setattr__(self, "boundary_kind", str(self.boundary_kind))
        object.__setattr__(self, "parent_group_id", str(self.parent_group_id))
        object.__setattr__(self, "field_ids", _as_tuple(self.field_ids))
        object.__setattr__(self, "child_group_ids", _as_tuple(self.child_group_ids))
        object.__setattr__(self, "owner_route", str(self.owner_route))
        object.__setattr__(self, "evidence_refs", _as_tuple(self.evidence_refs))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "boundary_kind": self.boundary_kind,
            "parent_group_id": self.parent_group_id,
            "field_ids": list(self.field_ids),
            "child_group_ids": list(self.child_group_ids),
            "owner_route": self.owner_route,
            "evidence_refs": list(self.evidence_refs),
            "rationale": self.rationale,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class FieldProjection:
    """Projection from one field row into model/code/test route obligations."""

    projection_id: str
    field_id: str
    model_obligation_id: str = ""
    transition_cell_id: str = ""
    code_contract_id: str = ""
    required_test_kinds: tuple[str, ...] = (TEST_KIND_HAPPY_PATH,)
    external_inputs: tuple[str, ...] = ()
    external_outputs: tuple[str, ...] = ()
    state_reads: tuple[str, ...] = ()
    state_writes: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    error_paths: tuple[str, ...] = ()
    risk_level: str = "normal"
    evidence_refs: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", str(self.projection_id))
        object.__setattr__(self, "field_id", str(self.field_id))
        object.__setattr__(self, "model_obligation_id", str(self.model_obligation_id))
        object.__setattr__(self, "transition_cell_id", str(self.transition_cell_id))
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "required_test_kinds", _as_tuple(self.required_test_kinds))
        object.__setattr__(self, "external_inputs", _as_tuple(self.external_inputs))
        object.__setattr__(self, "external_outputs", _as_tuple(self.external_outputs))
        object.__setattr__(self, "state_reads", _as_tuple(self.state_reads))
        object.__setattr__(self, "state_writes", _as_tuple(self.state_writes))
        object.__setattr__(self, "side_effects", _as_tuple(self.side_effects))
        object.__setattr__(self, "error_paths", _as_tuple(self.error_paths))
        object.__setattr__(self, "risk_level", str(self.risk_level))
        object.__setattr__(self, "evidence_refs", _as_tuple(self.evidence_refs))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_model_obligation(self) -> ModelObligation | None:
        if not self.model_obligation_id:
            return None
        return ModelObligation(
            self.model_obligation_id,
            obligation_type="field_lifecycle",
            description=self.rationale or f"field {self.field_id} lifecycle behavior",
            required=True,
            external_inputs=self.external_inputs,
            external_outputs=self.external_outputs,
            state_reads=self.state_reads,
            state_writes=self.state_writes,
            side_effects=self.side_effects,
            error_paths=self.error_paths,
            required_test_kinds=self.required_test_kinds,
            risk_level=self.risk_level,
            exact_external_contract=True,
        )

    def to_code_contract(self) -> CodeContract | None:
        if not self.code_contract_id or not self.model_obligation_id:
            return None
        return CodeContract(
            self.code_contract_id,
            implements_obligations=(self.model_obligation_id,),
            external_inputs=self.external_inputs,
            external_outputs=self.external_outputs,
            state_reads=self.state_reads,
            state_writes=self.state_writes,
            side_effects=self.side_effects,
            error_paths=self.error_paths,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_id": self.projection_id,
            "field_id": self.field_id,
            "model_obligation_id": self.model_obligation_id,
            "transition_cell_id": self.transition_cell_id,
            "code_contract_id": self.code_contract_id,
            "required_test_kinds": list(self.required_test_kinds),
            "external_inputs": list(self.external_inputs),
            "external_outputs": list(self.external_outputs),
            "state_reads": list(self.state_reads),
            "state_writes": list(self.state_writes),
            "side_effects": list(self.side_effects),
            "error_paths": list(self.error_paths),
            "risk_level": self.risk_level,
            "evidence_refs": list(self.evidence_refs),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class FieldLifecycleRow:
    """Leaf row for one field in the field lifecycle mesh."""

    field_id: str
    field_name: str = ""
    locations: tuple[str, ...] = ()
    group_id: str = ""
    role: str = FIELD_ROLE_METADATA
    lifecycle: str = FIELD_LIFECYCLE_ACTIVE
    behavior_impacts: tuple[str, ...] = ()
    reader_ids: tuple[str, ...] = ()
    writer_ids: tuple[str, ...] = ()
    replacement_field_id: str = ""
    old_field_ids: tuple[str, ...] = ()
    disposition: str = FIELD_DISPOSITION_UNKNOWN
    compatibility_intent: str = ""
    disposition_evidence_refs: tuple[str, ...] = ()
    projection: FieldProjection | Mapping[str, Any] | None = None
    scoped_out_reason: str = ""
    required: bool = True
    current: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "field_id", str(self.field_id))
        object.__setattr__(self, "field_name", str(self.field_name or self.field_id))
        object.__setattr__(self, "locations", _as_tuple(self.locations))
        object.__setattr__(self, "group_id", str(self.group_id))
        role = str(self.role or FIELD_ROLE_METADATA)
        object.__setattr__(self, "role", role)
        lifecycle = str(self.lifecycle or FIELD_LIFECYCLE_ACTIVE)
        object.__setattr__(self, "lifecycle", lifecycle)
        object.__setattr__(self, "behavior_impacts", _as_tuple(self.behavior_impacts))
        object.__setattr__(self, "reader_ids", _as_tuple(self.reader_ids))
        object.__setattr__(self, "writer_ids", _as_tuple(self.writer_ids))
        object.__setattr__(self, "replacement_field_id", str(self.replacement_field_id))
        object.__setattr__(self, "old_field_ids", _as_tuple(self.old_field_ids))
        disposition = str(self.disposition or FIELD_DISPOSITION_UNKNOWN)
        object.__setattr__(self, "disposition", disposition)
        object.__setattr__(self, "compatibility_intent", str(self.compatibility_intent))
        object.__setattr__(self, "disposition_evidence_refs", _as_tuple(self.disposition_evidence_refs))
        projection = self.projection
        if projection is not None and not isinstance(projection, FieldProjection):
            projection = FieldProjection(**dict(projection))
        object.__setattr__(self, "projection", projection)
        object.__setattr__(self, "scoped_out_reason", str(self.scoped_out_reason))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def behavior_bearing(self) -> bool:
        return any(impact in BEHAVIOR_FIELD_IMPACTS for impact in self.behavior_impacts)

    @property
    def old_or_replacement_like(self) -> bool:
        return bool(
            self.replacement_field_id
            or self.old_field_ids
            or self.lifecycle in {FIELD_LIFECYCLE_OLD, FIELD_LIFECYCLE_REPLACED, FIELD_LIFECYCLE_DEPRECATED}
        )

    @property
    def disposition_closed(self) -> bool:
        if not self.old_or_replacement_like:
            return True
        if self.disposition == FIELD_DISPOSITION_OUT_OF_SCOPE:
            return bool(self.scoped_out_reason)
        if self.disposition == FIELD_DISPOSITION_EXPLICITLY_PRESERVED:
            return bool(self.compatibility_intent and self.disposition_evidence_refs)
        if self.disposition in {
            FIELD_DISPOSITION_DELETED,
            FIELD_DISPOSITION_BLOCKED,
            FIELD_DISPOSITION_MIGRATED,
            FIELD_DISPOSITION_DELEGATED,
            FIELD_DISPOSITION_SAME_CONTRACT_REPAIRED,
        }:
            return bool(self.disposition_evidence_refs)
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "field_name": self.field_name,
            "locations": list(self.locations),
            "group_id": self.group_id,
            "role": self.role,
            "lifecycle": self.lifecycle,
            "behavior_impacts": list(self.behavior_impacts),
            "reader_ids": list(self.reader_ids),
            "writer_ids": list(self.writer_ids),
            "replacement_field_id": self.replacement_field_id,
            "old_field_ids": list(self.old_field_ids),
            "disposition": self.disposition,
            "compatibility_intent": self.compatibility_intent,
            "disposition_evidence_refs": list(self.disposition_evidence_refs),
            "projection": self.projection.to_dict() if self.projection else None,
            "scoped_out_reason": self.scoped_out_reason,
            "required": self.required,
            "current": self.current,
            "behavior_bearing": self.behavior_bearing,
            "old_or_replacement_like": self.old_or_replacement_like,
            "disposition_closed": self.disposition_closed,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class FieldLifecyclePlan:
    """Input plan for reviewing field lifecycle coverage."""

    mesh_id: str
    discovered_field_ids: tuple[str, ...] = ()
    groups: tuple[FieldLifecycleGroup, ...] = ()
    fields: tuple[FieldLifecycleRow, ...] = ()
    claim_scope: str = "bounded"
    allow_scoped_confidence: bool = True
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "mesh_id", str(self.mesh_id))
        object.__setattr__(self, "discovered_field_ids", _as_tuple(self.discovered_field_ids))
        object.__setattr__(self, "groups", tuple(self.groups))
        object.__setattr__(self, "fields", tuple(self.fields))
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(self, "notes", str(self.notes))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mesh_id": self.mesh_id,
            "discovered_field_ids": list(self.discovered_field_ids),
            "groups": [group.to_dict() for group in self.groups],
            "fields": [field_row.to_dict() for field_row in self.fields],
            "claim_scope": self.claim_scope,
            "allow_scoped_confidence": self.allow_scoped_confidence,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class FieldLifecycleFinding:
    """One field lifecycle gap or handoff."""

    code: str
    message: str
    severity: str = FIELD_FINDING_GAP
    field_id: str = ""
    group_id: str = ""
    owner_route: str = ""
    action: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity or FIELD_FINDING_GAP))
        object.__setattr__(self, "field_id", str(self.field_id))
        object.__setattr__(self, "group_id", str(self.group_id))
        object.__setattr__(self, "owner_route", str(self.owner_route))
        object.__setattr__(self, "action", str(self.action))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "field_id": self.field_id,
            "group_id": self.group_id,
            "owner_route": self.owner_route,
            "action": self.action,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class FieldLifecycleReport:
    """Review result for a field lifecycle mesh."""

    ok: bool
    mesh_id: str
    decision: str
    confidence: str
    findings: tuple[FieldLifecycleFinding, ...] = ()
    projections: tuple[FieldProjection, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "projections", tuple(self.projections))
        object.__setattr__(self, "summary", str(self.summary))

    def format_text(self) -> str:
        lines = [
            "=== flowguard field lifecycle mesh ===",
            f"mesh_id: {self.mesh_id}",
            f"status: {'pass' if self.ok else 'blocked'}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"summary: {self.summary}",
            f"projections: {len(self.projections)}",
        ]
        if self.findings:
            lines.append("findings:")
            for finding in self.findings:
                route = f" route={finding.owner_route}" if finding.owner_route else ""
                field_text = f" field={finding.field_id}" if finding.field_id else ""
                action = f" action={finding.action}" if finding.action else ""
                lines.append(f"- {finding.severity}: {finding.code}:{field_text}{route}: {finding.message}{action}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "mesh_id": self.mesh_id,
            "decision": self.decision,
            "confidence": self.confidence,
            "findings": [finding.to_dict() for finding in self.findings],
            "projections": [projection.to_dict() for projection in self.projections],
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def review_field_lifecycle(plan: FieldLifecyclePlan) -> FieldLifecycleReport:
    """Review whether field lifecycle coverage is complete enough for a claim."""

    findings: list[FieldLifecycleFinding] = []
    rows_by_id = {row.field_id: row for row in plan.fields}
    group_ids = {group.group_id for group in plan.groups}
    broad_claim = _field_claim_scope_requires_route_refs(plan.claim_scope)

    for field_id in plan.discovered_field_ids:
        if field_id not in rows_by_id:
            findings.append(
                FieldLifecycleFinding(
                    "field_lifecycle_missing_field_row",
                    "discovered field has no field lifecycle row",
                    FIELD_FINDING_BLOCKER,
                    field_id=field_id,
                    owner_route=FIELD_ROUTE_MODEL_FIRST,
                    action="add a FieldLifecycleRow or narrow the discovered field boundary",
                )
            )

    for group in plan.groups:
        for field_id in group.field_ids:
            if field_id not in rows_by_id:
                findings.append(
                    FieldLifecycleFinding(
                        "field_group_references_unknown_field",
                        "field group references a field that has no leaf row",
                        FIELD_FINDING_BLOCKER,
                        field_id=field_id,
                        group_id=group.group_id,
                        owner_route=FIELD_ROUTE_MODEL_FIRST,
                        action="add the missing leaf row or remove the stale group reference",
                    )
                )

    projections: list[FieldProjection] = []
    for row in plan.fields:
        if row.group_id and row.group_id not in group_ids:
            findings.append(
                FieldLifecycleFinding(
                    "field_group_missing",
                    "field row references a missing parent group",
                    FIELD_FINDING_GAP,
                    field_id=row.field_id,
                    group_id=row.group_id,
                    owner_route=FIELD_ROUTE_MODEL_MESH,
                    action="add or repair the parent field group",
                    metadata=row.to_dict(),
                )
            )
        if not row.current and row.required:
            findings.append(
                FieldLifecycleFinding(
                    "field_lifecycle_evidence_stale",
                    "required field lifecycle row is not current",
                    FIELD_FINDING_BLOCKER,
                    field_id=row.field_id,
                    owner_route=FIELD_ROUTE_DEVELOPMENT_PROCESS_FLOW,
                    action="refresh field lifecycle evidence and rerun dependent routes",
                    metadata=row.to_dict(),
                )
            )
        if row.behavior_bearing:
            if row.projection is None and not row.scoped_out_reason:
                findings.append(
                    FieldLifecycleFinding(
                        "behavior_field_projection_missing",
                        "behavior-bearing field has no model/code/test projection or scoped-out reason",
                        FIELD_FINDING_BLOCKER,
                        field_id=row.field_id,
                        owner_route=FIELD_ROUTE_MODEL_TEST_ALIGNMENT,
                        action="project the field into a model obligation, transition cell, code contract, or scoped-out reason",
                        metadata=row.to_dict(),
                    )
                )
            elif row.projection is not None:
                projections.append(row.projection)
                if not row.projection.model_obligation_id:
                    findings.append(
                        FieldLifecycleFinding(
                            "field_model_obligation_missing",
                            "field projection has no model obligation id",
                            FIELD_FINDING_BLOCKER,
                            field_id=row.field_id,
                            owner_route=FIELD_ROUTE_MODEL_FIRST,
                            action="bind the field to a model obligation",
                            metadata=row.projection.to_dict(),
                        )
                    )
                if not row.projection.code_contract_id:
                    findings.append(
                        FieldLifecycleFinding(
                            "field_code_contract_missing",
                            "field projection has no owner code contract id",
                            FIELD_FINDING_BLOCKER,
                            field_id=row.field_id,
                            owner_route=FIELD_ROUTE_MODEL_TEST_ALIGNMENT,
                            action="bind the field obligation to a CodeContract",
                            metadata=row.projection.to_dict(),
                        )
                    )
                if broad_claim:
                    evidence_kinds = _evidence_ref_kinds(row.projection.evidence_refs)
                    if FIELD_EVIDENCE_REF_GATE not in evidence_kinds:
                        findings.append(
                            FieldLifecycleFinding(
                                "field_gate_evidence_missing",
                                "broad behavior field projection has no gate evidence reference",
                                FIELD_FINDING_BLOCKER,
                                field_id=row.field_id,
                                owner_route=FIELD_ROUTE_RUNTIME_GATEWAY,
                                action="add a gate:, boundary:, or runtime_gateway: evidence ref or narrow the claim scope",
                                metadata=row.projection.to_dict(),
                            )
                        )
                    if (
                        _projection_requires_negative_test_ref(row.projection)
                        and FIELD_EVIDENCE_REF_TEST not in evidence_kinds
                    ):
                        findings.append(
                            FieldLifecycleFinding(
                                "field_negative_test_evidence_missing",
                                "broad behavior field projection requires failure or negative test evidence but has no test evidence reference",
                                FIELD_FINDING_BLOCKER,
                                field_id=row.field_id,
                                owner_route=FIELD_ROUTE_MODEL_TEST_ALIGNMENT,
                                action="add a test:, negative_test:, or failure_test: evidence ref or narrow the claim scope",
                                metadata=row.projection.to_dict(),
                            )
                        )
                    if (
                        _projection_requires_replay_ref(row, row.projection)
                        and FIELD_EVIDENCE_REF_REPLAY not in evidence_kinds
                    ):
                        findings.append(
                            FieldLifecycleFinding(
                                "field_replay_evidence_missing",
                                "broad behavior field projection requires replay evidence but has no replay evidence reference",
                                FIELD_FINDING_BLOCKER,
                                field_id=row.field_id,
                                owner_route=FIELD_ROUTE_MODEL_TEST_ALIGNMENT,
                                action="add a replay: or conformance_replay: evidence ref or narrow the claim scope",
                                metadata=row.projection.to_dict(),
                            )
                        )
        elif not row.scoped_out_reason and row.role in {
            FIELD_ROLE_PRESENTATION,
            FIELD_ROLE_METADATA,
        }:
            findings.append(
                FieldLifecycleFinding(
                    "non_behavior_field_scope_missing",
                    "non-behavior field is accounted but lacks a scoped-out reason",
                    FIELD_FINDING_GAP,
                    field_id=row.field_id,
                    owner_route=FIELD_ROUTE_MODEL_FIRST,
                    action="record why this field stays out of the high-level model",
                    metadata=row.to_dict(),
                )
            )
        if row.old_or_replacement_like and not row.disposition_closed:
            findings.append(
                FieldLifecycleFinding(
                    "old_field_disposition_open",
                    "old, replaced, deprecated, or compatibility-like field has no closing disposition evidence",
                    FIELD_FINDING_BLOCKER,
                    field_id=row.field_id,
                    owner_route=FIELD_ROUTE_ARCHITECTURE_REDUCTION,
                    action="delete, block, migrate, delegate, repair, explicitly preserve, or scope out the old field with evidence",
                    metadata=row.to_dict(),
                )
            )

    blockers = tuple(finding for finding in findings if finding.severity == FIELD_FINDING_BLOCKER)
    gaps = tuple(finding for finding in findings if finding.severity == FIELD_FINDING_GAP)
    if blockers:
        decision = FIELD_DECISION_BLOCKED
        confidence = FIELD_CONFIDENCE_BLOCKED
        ok = False
        summary = "Field lifecycle has blockers for full confidence."
    elif gaps:
        decision = FIELD_DECISION_SCOPED
        confidence = FIELD_CONFIDENCE_SCOPED
        ok = plan.allow_scoped_confidence
        summary = "Field lifecycle has scoped gaps."
    else:
        decision = FIELD_DECISION_FULL
        confidence = FIELD_CONFIDENCE_FULL
        ok = True
        summary = "All discovered fields are accounted and behavior-bearing fields are projected."

    return FieldLifecycleReport(
        ok=ok,
        mesh_id=plan.mesh_id,
        decision=decision,
        confidence=confidence,
        findings=tuple(findings),
        projections=tuple(projections),
        summary=summary,
    )


def field_lifecycle_to_model_obligations(
    projections: Sequence[FieldProjection] | FieldLifecycleReport,
) -> tuple[ModelObligation, ...]:
    """Project field lifecycle rows into Model-Test Alignment obligations."""

    projection_rows = projections.projections if isinstance(projections, FieldLifecycleReport) else tuple(projections)
    result: list[ModelObligation] = []
    for projection in projection_rows:
        obligation = projection.to_model_obligation()
        if obligation is not None:
            result.append(obligation)
    return tuple(result)


def field_lifecycle_to_code_contracts(
    projections: Sequence[FieldProjection] | FieldLifecycleReport,
) -> tuple[CodeContract, ...]:
    """Project field lifecycle rows into Model-Test Alignment code contracts."""

    projection_rows = projections.projections if isinstance(projections, FieldLifecycleReport) else tuple(projections)
    result: list[CodeContract] = []
    for projection in projection_rows:
        contract = projection.to_code_contract()
        if contract is not None:
            result.append(contract)
    return tuple(result)


__all__ = [
    "BEHAVIOR_FIELD_IMPACTS",
    "FIELD_CONFIDENCE_BLOCKED",
    "FIELD_CONFIDENCE_FULL",
    "FIELD_CONFIDENCE_SCOPED",
    "FIELD_DECISION_BLOCKED",
    "FIELD_DECISION_FULL",
    "FIELD_DECISION_SCOPED",
    "FIELD_DISPOSITION_BLOCKED",
    "FIELD_DISPOSITION_DELEGATED",
    "FIELD_DISPOSITION_DELETED",
    "FIELD_DISPOSITION_EXPLICITLY_PRESERVED",
    "FIELD_DISPOSITION_MIGRATED",
    "FIELD_DISPOSITION_OUT_OF_SCOPE",
    "FIELD_DISPOSITION_SAME_CONTRACT_REPAIRED",
    "FIELD_DISPOSITION_UNKNOWN",
    "FIELD_DISPOSITIONS",
    "FIELD_EVIDENCE_REF_GATE",
    "FIELD_EVIDENCE_REF_KINDS",
    "FIELD_EVIDENCE_REF_REPLAY",
    "FIELD_EVIDENCE_REF_TEST",
    "FIELD_FINDING_BLOCKER",
    "FIELD_FINDING_GAP",
    "FIELD_FINDING_INFO",
    "FIELD_IMPACT_EXTERNAL_CONTRACT",
    "FIELD_IMPACT_MIGRATION",
    "FIELD_IMPACT_NONE",
    "FIELD_IMPACT_PERMISSION",
    "FIELD_IMPACT_REPLAY",
    "FIELD_IMPACT_ROUTING",
    "FIELD_IMPACT_SCHEMA",
    "FIELD_IMPACT_SIDE_EFFECT",
    "FIELD_IMPACT_STATE",
    "FIELD_IMPACTS",
    "FIELD_LIFECYCLE_ACTIVE",
    "FIELD_LIFECYCLE_ARCHIVE_ONLY",
    "FIELD_LIFECYCLE_DEPRECATED",
    "FIELD_LIFECYCLE_DERIVED",
    "FIELD_LIFECYCLE_NEW",
    "FIELD_LIFECYCLE_OLD",
    "FIELD_LIFECYCLE_REPLACED",
    "FIELD_LIFECYCLES",
    "FIELD_ROLE_FEATURE_FLAG",
    "FIELD_ROLE_METADATA",
    "FIELD_ROLE_PERMISSION",
    "FIELD_ROLE_PERSISTED",
    "FIELD_ROLE_PRESENTATION",
    "FIELD_ROLE_PROMPT_CONFIG",
    "FIELD_ROLE_ROUTING",
    "FIELD_ROLE_SCHEMA_VERSION",
    "FIELD_ROLE_STATE",
    "FIELD_ROLES",
    "FIELD_ROUTE_ARCHITECTURE_REDUCTION",
    "FIELD_ROUTE_CLOSURE_CONTRACT",
    "FIELD_ROUTE_CODE_STRUCTURE",
    "FIELD_ROUTE_DEVELOPMENT_PROCESS_FLOW",
    "FIELD_ROUTE_MODEL_FIRST",
    "FIELD_ROUTE_MODEL_MESH",
    "FIELD_ROUTE_MODEL_MISS_REVIEW",
    "FIELD_ROUTE_MODEL_TEST_ALIGNMENT",
    "FIELD_ROUTE_RUNTIME_GATEWAY",
    "FIELD_ROUTE_TEST_MESH",
    "PASSING_FIELD_DISPOSITIONS",
    "FieldLifecycleFinding",
    "FieldLifecycleGroup",
    "FieldLifecyclePlan",
    "FieldLifecycleReport",
    "FieldLifecycleRow",
    "FieldProjection",
    "field_lifecycle_to_code_contracts",
    "field_lifecycle_to_model_obligations",
    "review_field_lifecycle",
]
