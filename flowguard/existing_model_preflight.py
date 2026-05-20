"""Existing FlowGuard model preflight helpers.

Existing-model preflight is a companion review before an agent discusses,
proposes, or modifies behavior in an existing modeled system. It does not
replace downstream routes such as ModelMesh, StructureMesh, UI Flow Structure,
or Model-Miss Review. It checks that the agent first grounded its reasoning in
the model map that already exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable


PREFLIGHT_MODE_LIGHT = "light"
PREFLIGHT_MODE_FULL = "full"
PREFLIGHT_MODES = {PREFLIGHT_MODE_LIGHT, PREFLIGHT_MODE_FULL}

REUSE_DECISION_REUSE_EXISTING = "reuse_existing"
REUSE_DECISION_EXTEND_EXISTING = "extend_existing"
REUSE_DECISION_ADD_CHILD_MODEL = "add_child_model"
REUSE_DECISION_NEW_BOUNDARY = "new_boundary"
REUSE_DECISION_NO_MODEL_FOUND = "no_model_found"
REUSE_DECISION_SKIP = "skip_with_reason"
REUSE_DECISIONS = {
    REUSE_DECISION_REUSE_EXISTING,
    REUSE_DECISION_EXTEND_EXISTING,
    REUSE_DECISION_ADD_CHILD_MODEL,
    REUSE_DECISION_NEW_BOUNDARY,
    REUSE_DECISION_NO_MODEL_FOUND,
    REUSE_DECISION_SKIP,
}

DUPLICATE_RISK_RESOLUTIONS = {
    "reuse_existing",
    "extend_existing",
    "new_boundary_rationale",
    "out_of_scope",
    "blocked",
}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _as_pairs(values: Sequence[tuple[str, str]] | None) -> tuple[tuple[str, str], ...]:
    if values is None:
        return ()
    return tuple((str(left), str(right)) for left, right in values)


@dataclass(frozen=True)
class ModelContextHit:
    """One existing model that may own part of the requested change."""

    model_id: str
    model_path: str = ""
    evidence_id: str = ""
    evidence_tier: str = "candidate_only"
    evidence_current: bool = True
    responsibilities: tuple[str, ...] = ()
    function_blocks: tuple[str, ...] = ()
    state_owned: tuple[str, ...] = ()
    side_effects_owned: tuple[str, ...] = ()
    public_entrypoints: tuple[str, ...] = ()
    parent_model_id: str = ""
    child_model_ids: tuple[str, ...] = ()
    validation_evidence: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "model_path", str(self.model_path))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "evidence_tier", str(self.evidence_tier))
        object.__setattr__(self, "responsibilities", _as_tuple(self.responsibilities))
        object.__setattr__(self, "function_blocks", _as_tuple(self.function_blocks))
        object.__setattr__(self, "state_owned", _as_tuple(self.state_owned))
        object.__setattr__(self, "side_effects_owned", _as_tuple(self.side_effects_owned))
        object.__setattr__(self, "public_entrypoints", _as_tuple(self.public_entrypoints))
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "child_model_ids", _as_tuple(self.child_model_ids))
        object.__setattr__(self, "validation_evidence", _as_tuple(self.validation_evidence))
        object.__setattr__(self, "rationale", str(self.rationale))

    def has_ownership_evidence(self) -> bool:
        return bool(
            self.function_blocks
            or self.state_owned
            or self.side_effects_owned
            or self.public_entrypoints
            or self.responsibilities
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_path": self.model_path,
            "evidence_id": self.evidence_id,
            "evidence_tier": self.evidence_tier,
            "evidence_current": self.evidence_current,
            "responsibilities": list(self.responsibilities),
            "function_blocks": list(self.function_blocks),
            "state_owned": list(self.state_owned),
            "side_effects_owned": list(self.side_effects_owned),
            "public_entrypoints": list(self.public_entrypoints),
            "parent_model_id": self.parent_model_id,
            "child_model_ids": list(self.child_model_ids),
            "validation_evidence": list(self.validation_evidence),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ExistingOwnershipSnapshot:
    """Ownership summary extracted from existing FlowGuard model hits."""

    function_block_owners: tuple[tuple[str, str], ...] = ()
    state_owners: tuple[tuple[str, str], ...] = ()
    side_effect_owners: tuple[tuple[str, str], ...] = ()
    public_entrypoint_owners: tuple[tuple[str, str], ...] = ()
    responsibility_owners: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "function_block_owners", _as_pairs(self.function_block_owners))
        object.__setattr__(self, "state_owners", _as_pairs(self.state_owners))
        object.__setattr__(self, "side_effect_owners", _as_pairs(self.side_effect_owners))
        object.__setattr__(self, "public_entrypoint_owners", _as_pairs(self.public_entrypoint_owners))
        object.__setattr__(self, "responsibility_owners", _as_pairs(self.responsibility_owners))

    def has_any(self) -> bool:
        return bool(
            self.function_block_owners
            or self.state_owners
            or self.side_effect_owners
            or self.public_entrypoint_owners
            or self.responsibility_owners
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_block_owners": [list(pair) for pair in self.function_block_owners],
            "state_owners": [list(pair) for pair in self.state_owners],
            "side_effect_owners": [list(pair) for pair in self.side_effect_owners],
            "public_entrypoint_owners": [list(pair) for pair in self.public_entrypoint_owners],
            "responsibility_owners": [list(pair) for pair in self.responsibility_owners],
        }


@dataclass(frozen=True)
class DuplicateBoundaryRisk:
    """A proposed boundary overlaps an existing model responsibility."""

    item_type: str
    item_id: str
    existing_owner_id: str
    proposed_owner_id: str = ""
    resolution: str = ""
    rationale: str = ""
    resolved: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_type", str(self.item_type))
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "existing_owner_id", str(self.existing_owner_id))
        object.__setattr__(self, "proposed_owner_id", str(self.proposed_owner_id))
        object.__setattr__(self, "resolution", str(self.resolution))
        object.__setattr__(self, "rationale", str(self.rationale))

    def is_resolved(self) -> bool:
        if self.resolved:
            return True
        return self.resolution in DUPLICATE_RISK_RESOLUTIONS and bool(self.rationale)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_type": self.item_type,
            "item_id": self.item_id,
            "existing_owner_id": self.existing_owner_id,
            "proposed_owner_id": self.proposed_owner_id,
            "resolution": self.resolution,
            "rationale": self.rationale,
            "resolved": self.resolved,
        }


@dataclass(frozen=True)
class ExistingModelPreflight:
    """A light or full report grounding work in existing FlowGuard models."""

    preflight_id: str
    task_summary: str
    mode: str = PREFLIGHT_MODE_FULL
    existing_modeled_system: bool = True
    model_search_performed: bool = False
    search_paths: tuple[str, ...] = ()
    relevant_models: tuple[ModelContextHit, ...] = ()
    ownership_snapshot: ExistingOwnershipSnapshot | None = None
    reuse_decision: str = ""
    downstream_routes: tuple[str, ...] = ()
    rationale: str = ""
    no_model_found_reason: str = ""
    proposed_new_boundaries: tuple[str, ...] = ()
    duplicate_risks: tuple[DuplicateBoundaryRisk, ...] = ()
    skip_reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "preflight_id", str(self.preflight_id))
        object.__setattr__(self, "task_summary", str(self.task_summary))
        object.__setattr__(self, "mode", str(self.mode))
        object.__setattr__(self, "search_paths", _as_tuple(self.search_paths))
        object.__setattr__(self, "relevant_models", tuple(self.relevant_models))
        object.__setattr__(self, "reuse_decision", str(self.reuse_decision))
        object.__setattr__(self, "downstream_routes", _as_tuple(self.downstream_routes))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "no_model_found_reason", str(self.no_model_found_reason))
        object.__setattr__(self, "proposed_new_boundaries", _as_tuple(self.proposed_new_boundaries))
        object.__setattr__(self, "duplicate_risks", tuple(self.duplicate_risks))
        object.__setattr__(self, "skip_reason", str(self.skip_reason))

    def to_dict(self) -> dict[str, Any]:
        return {
            "preflight_id": self.preflight_id,
            "task_summary": self.task_summary,
            "mode": self.mode,
            "existing_modeled_system": self.existing_modeled_system,
            "model_search_performed": self.model_search_performed,
            "search_paths": list(self.search_paths),
            "relevant_models": [model.to_dict() for model in self.relevant_models],
            "ownership_snapshot": self.ownership_snapshot.to_dict()
            if self.ownership_snapshot
            else None,
            "reuse_decision": self.reuse_decision,
            "downstream_routes": list(self.downstream_routes),
            "rationale": self.rationale,
            "no_model_found_reason": self.no_model_found_reason,
            "proposed_new_boundaries": list(self.proposed_new_boundaries),
            "duplicate_risks": [risk.to_dict() for risk in self.duplicate_risks],
            "skip_reason": self.skip_reason,
        }


@dataclass(frozen=True)
class ExistingModelPreflightFinding:
    """One preflight review finding."""

    code: str
    message: str
    severity: str = "blocker"
    model_id: str = ""
    item_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "model_id": self.model_id,
            "item_id": self.item_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ExistingModelPreflightReport:
    """Structured outcome of an existing-model preflight review."""

    ok: bool
    preflight_id: str
    decision: str
    findings: tuple[ExistingModelPreflightFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "preflight_id", str(self.preflight_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: preflight={self.preflight_id} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard existing model preflight review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"preflight: {self.preflight_id}",
            f"decision: {self.decision}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"model: {finding.model_id or '(none)'}",
                    f"item: {finding.item_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "preflight_id": self.preflight_id,
            "decision": self.decision,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


def _blocker_findings(
    findings: Sequence[ExistingModelPreflightFinding],
) -> tuple[ExistingModelPreflightFinding, ...]:
    return tuple(finding for finding in findings if finding.severity == "blocker")


def _has_ownership_evidence(preflight: ExistingModelPreflight) -> bool:
    if preflight.ownership_snapshot and preflight.ownership_snapshot.has_any():
        return True
    return any(model.has_ownership_evidence() for model in preflight.relevant_models)


def _decision_for_findings(
    preflight: ExistingModelPreflight,
    findings: Sequence[ExistingModelPreflightFinding],
) -> str:
    blockers = _blocker_findings(findings)
    if preflight.skip_reason and not blockers:
        return "preflight_skipped_with_reason"
    if blockers:
        codes = {finding.code for finding in blockers}
        if "missing_model_search" in codes:
            return "model_search_required"
        if "missing_ownership_evidence" in codes:
            return "ownership_snapshot_required"
        if "duplicate_boundary_risk_unresolved" in codes:
            return "duplicate_boundary_risk_blocked"
        if "new_boundary_without_rationale" in codes:
            return "new_boundary_rationale_required"
        if "no_model_found_reason_missing" in codes:
            return "no_model_found_requires_reason"
        return "existing_model_preflight_blocked"
    if preflight.reuse_decision == REUSE_DECISION_NO_MODEL_FOUND:
        return "no_model_found_can_continue"
    if preflight.mode == PREFLIGHT_MODE_LIGHT:
        return "light_model_grounding_can_continue"
    return "full_existing_model_preflight_can_continue"


def review_existing_model_preflight(
    preflight: ExistingModelPreflight,
) -> ExistingModelPreflightReport:
    """Review an existing-model preflight report."""

    findings: list[ExistingModelPreflightFinding] = []

    if not preflight.preflight_id:
        findings.append(
            ExistingModelPreflightFinding(
                "missing_preflight_id",
                "existing-model preflight has no id",
            )
        )
    if not preflight.task_summary:
        findings.append(
            ExistingModelPreflightFinding(
                "missing_task_summary",
                "existing-model preflight has no task summary",
            )
        )
    if preflight.mode not in PREFLIGHT_MODES:
        findings.append(
            ExistingModelPreflightFinding(
                "invalid_preflight_mode",
                f"existing-model preflight mode {preflight.mode!r} is not recognized",
            )
        )
    if preflight.reuse_decision and preflight.reuse_decision not in REUSE_DECISIONS:
        findings.append(
            ExistingModelPreflightFinding(
                "invalid_reuse_decision",
                f"reuse decision {preflight.reuse_decision!r} is not recognized",
            )
        )

    if preflight.skip_reason:
        if preflight.reuse_decision and preflight.reuse_decision != REUSE_DECISION_SKIP:
            findings.append(
                ExistingModelPreflightFinding(
                    "skip_decision_mismatch",
                    "preflight skip reason conflicts with a non-skip reuse decision",
                )
            )
        if not preflight.rationale:
            findings.append(
                ExistingModelPreflightFinding(
                    "skip_without_rationale",
                    "preflight skip must explain why model grounding is unnecessary",
                )
            )
        blockers = _blocker_findings(findings)
        return ExistingModelPreflightReport(
            ok=not blockers,
            preflight_id=preflight.preflight_id,
            decision=_decision_for_findings(preflight, findings),
            findings=tuple(findings),
        )

    if not preflight.model_search_performed:
        findings.append(
            ExistingModelPreflightFinding(
                "missing_model_search",
                "preflight claims model grounding without searching existing FlowGuard models",
            )
        )
    if not preflight.search_paths:
        findings.append(
            ExistingModelPreflightFinding(
                "missing_search_paths",
                "preflight does not record the model search path or inventory consulted",
            )
        )

    if preflight.relevant_models:
        if preflight.reuse_decision == REUSE_DECISION_NO_MODEL_FOUND:
            findings.append(
                ExistingModelPreflightFinding(
                    "model_found_decision_mismatch",
                    "preflight found relevant models but reuse decision says no model was found",
                )
            )
        if preflight.mode == PREFLIGHT_MODE_FULL and not _has_ownership_evidence(preflight):
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_ownership_evidence",
                    "full preflight found models but does not record FunctionBlock, state, side-effect, entrypoint, or responsibility ownership",
                )
            )
        for model in preflight.relevant_models:
            if not model.model_id:
                findings.append(
                    ExistingModelPreflightFinding(
                        "missing_model_id",
                        "model context hit has no model id",
                        metadata=model.to_dict(),
                    )
                )
            if not model.evidence_current:
                findings.append(
                    ExistingModelPreflightFinding(
                        "stale_model_evidence",
                        "model context hit has stale evidence and needs downstream freshness handling",
                        severity="warning",
                        model_id=model.model_id,
                        metadata=model.to_dict(),
                    )
                )
    else:
        if preflight.reuse_decision != REUSE_DECISION_NO_MODEL_FOUND:
            findings.append(
                ExistingModelPreflightFinding(
                    "no_model_found_decision_required",
                    "preflight found no relevant models but did not record no_model_found",
                )
            )
        if not preflight.no_model_found_reason:
            findings.append(
                ExistingModelPreflightFinding(
                    "no_model_found_reason_missing",
                    "preflight found no relevant models but does not explain the search result",
                )
            )

    if not preflight.reuse_decision:
        findings.append(
            ExistingModelPreflightFinding(
                "missing_reuse_decision",
                "preflight does not decide whether to reuse, extend, add child model, create a new boundary, or record no_model_found",
            )
        )

    if preflight.mode == PREFLIGHT_MODE_FULL:
        if not preflight.downstream_routes:
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_downstream_route",
                    "full preflight does not name the downstream FlowGuard route",
                )
            )
        if not preflight.rationale:
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_preflight_rationale",
                    "full preflight does not explain the reuse or route decision",
                )
            )

    if preflight.reuse_decision in {
        REUSE_DECISION_ADD_CHILD_MODEL,
        REUSE_DECISION_NEW_BOUNDARY,
    } and not (preflight.proposed_new_boundaries and preflight.rationale):
        findings.append(
            ExistingModelPreflightFinding(
                "new_boundary_without_rationale",
                "new model or ownership boundary needs a named boundary and rationale for why existing models cannot carry it",
            )
        )

    for risk in preflight.duplicate_risks:
        if not risk.item_id or not risk.item_type or not risk.existing_owner_id:
            findings.append(
                ExistingModelPreflightFinding(
                    "incomplete_duplicate_boundary_risk",
                    "duplicate boundary risk must name the item type, item id, and existing owner",
                    item_id=risk.item_id,
                    metadata=risk.to_dict(),
                )
            )
        if not risk.is_resolved():
            findings.append(
                ExistingModelPreflightFinding(
                    "duplicate_boundary_risk_unresolved",
                    "duplicate model, state, side-effect, FunctionBlock, entrypoint, or responsibility ownership is not resolved",
                    model_id=risk.existing_owner_id,
                    item_id=risk.item_id,
                    metadata=risk.to_dict(),
                )
            )

    blockers = _blocker_findings(findings)
    return ExistingModelPreflightReport(
        ok=not blockers,
        preflight_id=preflight.preflight_id,
        decision=_decision_for_findings(preflight, findings),
        findings=tuple(findings),
    )


__all__ = [
    "DUPLICATE_RISK_RESOLUTIONS",
    "ExistingModelPreflight",
    "ExistingModelPreflightFinding",
    "ExistingModelPreflightReport",
    "ExistingOwnershipSnapshot",
    "DuplicateBoundaryRisk",
    "ModelContextHit",
    "PREFLIGHT_MODE_FULL",
    "PREFLIGHT_MODE_LIGHT",
    "PREFLIGHT_MODES",
    "REUSE_DECISION_ADD_CHILD_MODEL",
    "REUSE_DECISION_EXTEND_EXISTING",
    "REUSE_DECISION_NEW_BOUNDARY",
    "REUSE_DECISION_NO_MODEL_FOUND",
    "REUSE_DECISION_REUSE_EXISTING",
    "REUSE_DECISION_SKIP",
    "REUSE_DECISIONS",
    "review_existing_model_preflight",
]
