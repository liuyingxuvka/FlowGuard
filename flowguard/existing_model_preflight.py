"""Existing FlowGuard model preflight helpers.

Existing-model preflight is a companion review before an agent discusses,
proposes, or modifies behavior in an existing modeled system. It does not
replace downstream routes such as ModelMesh, StructureMesh, UI Flow Structure,
or Model-Miss Review. It checks that the agent first grounded its reasoning in
the model map that already exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .model_angle_deliberation import (
    MODEL_ANGLE_CONFIDENCE_BLOCKED,
    MODEL_ANGLE_CONFIDENCE_SCOPED,
    ModelAngleDeliberation,
    review_model_angle_deliberations,
)
from .model_similarity import SimilarityHandoff, normalize_similarity_handoff


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
    fields_owned: tuple[str, ...] = ()
    parent_model_id: str = ""
    child_model_ids: tuple[str, ...] = ()
    layered_proof_evidence_id: str = ""
    parent_coverage_status: str = ""
    child_disjointness_status: str = ""
    child_reattachment_status: str = ""
    leaf_boundary_matrix_status: str = ""
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
        object.__setattr__(self, "fields_owned", _as_tuple(self.fields_owned))
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "child_model_ids", _as_tuple(self.child_model_ids))
        object.__setattr__(self, "layered_proof_evidence_id", str(self.layered_proof_evidence_id))
        object.__setattr__(self, "parent_coverage_status", str(self.parent_coverage_status))
        object.__setattr__(self, "child_disjointness_status", str(self.child_disjointness_status))
        object.__setattr__(self, "child_reattachment_status", str(self.child_reattachment_status))
        object.__setattr__(self, "leaf_boundary_matrix_status", str(self.leaf_boundary_matrix_status))
        object.__setattr__(self, "validation_evidence", _as_tuple(self.validation_evidence))
        object.__setattr__(self, "rationale", str(self.rationale))

    def has_ownership_evidence(self) -> bool:
        return bool(
            self.function_blocks
            or self.state_owned
            or self.side_effects_owned
            or self.public_entrypoints
            or self.fields_owned
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
            "fields_owned": list(self.fields_owned),
            "parent_model_id": self.parent_model_id,
            "child_model_ids": list(self.child_model_ids),
            "layered_proof_evidence_id": self.layered_proof_evidence_id,
            "parent_coverage_status": self.parent_coverage_status,
            "child_disjointness_status": self.child_disjointness_status,
            "child_reattachment_status": self.child_reattachment_status,
            "leaf_boundary_matrix_status": self.leaf_boundary_matrix_status,
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
    field_owners: tuple[tuple[str, str], ...] = ()
    responsibility_owners: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "function_block_owners", _as_pairs(self.function_block_owners))
        object.__setattr__(self, "state_owners", _as_pairs(self.state_owners))
        object.__setattr__(self, "side_effect_owners", _as_pairs(self.side_effect_owners))
        object.__setattr__(self, "public_entrypoint_owners", _as_pairs(self.public_entrypoint_owners))
        object.__setattr__(self, "field_owners", _as_pairs(self.field_owners))
        object.__setattr__(self, "responsibility_owners", _as_pairs(self.responsibility_owners))

    def has_any(self) -> bool:
        return bool(
            self.function_block_owners
            or self.state_owners
            or self.side_effect_owners
            or self.public_entrypoint_owners
            or self.field_owners
            or self.responsibility_owners
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_block_owners": [list(pair) for pair in self.function_block_owners],
            "state_owners": [list(pair) for pair in self.state_owners],
            "side_effect_owners": [list(pair) for pair in self.side_effect_owners],
            "public_entrypoint_owners": [list(pair) for pair in self.public_entrypoint_owners],
            "field_owners": [list(pair) for pair in self.field_owners],
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
    behavior_field_ids: tuple[str, ...] = ()
    field_lifecycle_required: bool = False
    field_lifecycle_model_ids: tuple[str, ...] = ()
    field_lifecycle_gap_ids: tuple[str, ...] = ()
    model_angle_review_required: bool = False
    model_angle_deliberations: tuple[ModelAngleDeliberation | Mapping[str, Any], ...] = ()
    model_angle_gap_ids: tuple[str, ...] = ()
    similarity_review_required: bool = False
    similarity_handoff: SimilarityHandoff | Mapping[str, Any] | None = None
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
        object.__setattr__(self, "behavior_field_ids", _as_tuple(self.behavior_field_ids))
        object.__setattr__(self, "field_lifecycle_required", bool(self.field_lifecycle_required))
        object.__setattr__(self, "field_lifecycle_model_ids", _as_tuple(self.field_lifecycle_model_ids))
        object.__setattr__(self, "field_lifecycle_gap_ids", _as_tuple(self.field_lifecycle_gap_ids))
        object.__setattr__(self, "model_angle_review_required", bool(self.model_angle_review_required))
        object.__setattr__(
            self,
            "model_angle_deliberations",
            tuple(
                item
                if isinstance(item, ModelAngleDeliberation)
                else ModelAngleDeliberation(**item)
                for item in self.model_angle_deliberations
            ),
        )
        object.__setattr__(self, "model_angle_gap_ids", _as_tuple(self.model_angle_gap_ids))
        object.__setattr__(self, "similarity_handoff", normalize_similarity_handoff(self.similarity_handoff))
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
            "behavior_field_ids": list(self.behavior_field_ids),
            "field_lifecycle_required": self.field_lifecycle_required,
            "field_lifecycle_model_ids": list(self.field_lifecycle_model_ids),
            "field_lifecycle_gap_ids": list(self.field_lifecycle_gap_ids),
            "model_angle_review_required": self.model_angle_review_required,
            "model_angle_deliberations": [item.to_dict() for item in self.model_angle_deliberations],
            "model_angle_gap_ids": list(self.model_angle_gap_ids),
            "similarity_review_required": self.similarity_review_required,
            "similarity_handoff": self.similarity_handoff.to_dict()
            if self.similarity_handoff
            else None,
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


def _missing_layered_status_fields(model: ModelContextHit) -> tuple[str, ...]:
    if not model.child_model_ids:
        return ()
    missing: list[str] = []
    for field_name in (
        "layered_proof_evidence_id",
        "parent_coverage_status",
        "child_disjointness_status",
        "child_reattachment_status",
        "leaf_boundary_matrix_status",
    ):
        if not getattr(model, field_name):
            missing.append(field_name)
    return tuple(missing)


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
        if "layered_proof_status_unknown" in codes:
            return "layered_proof_status_required"
        if "missing_field_lifecycle_ownership" in codes:
            return "field_lifecycle_ownership_required"
        if "field_lifecycle_gap_unresolved" in codes:
            return "field_lifecycle_gap_blocked"
        if any(code.startswith("model_angle_") for code in codes):
            return "model_angle_review_blocked"
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


def _model_id_from_path(path: Path, root: Path) -> str:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    parts = list(relative.parts)
    if len(parts) >= 3 and parts[0] == ".flowguard":
        return ":".join(parts[1:-1]) or path.stem
    return ":".join(parts[:-1] + [path.stem]) or path.stem


def _class_names(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)\b", text, re.MULTILINE)))


def _purpose_lines(text: str, limit: int = 3) -> tuple[str, ...]:
    lines: list[str] = []
    capture = False
    for raw_line in text.splitlines():
        line = raw_line.strip().strip("#").strip()
        if not line:
            if capture:
                break
            continue
        lowered = line.lower()
        if lowered.startswith("purpose:"):
            capture = True
            value = line.split(":", 1)[1].strip()
            if value:
                lines.append(value)
            continue
        if capture:
            if lowered.startswith(("guards against:", "use before editing:", "run:")):
                break
            lines.append(line)
        if len(lines) >= limit:
            break
    return tuple(lines)


def _matches_changed_paths(path: Path, text: str, changed_paths: Sequence[str]) -> bool:
    if not changed_paths:
        return True
    haystack = f"{path.as_posix()}\n{text}".lower()
    return any(str(item).lower().replace("\\", "/") in haystack for item in changed_paths)


def existing_model_preflight_from_project(
    root: str | Path,
    task_summary: str,
    *,
    preflight_id: str = "",
    changed_paths: Sequence[str] = (),
    downstream_routes: Sequence[str] = (),
    mode: str = PREFLIGHT_MODE_FULL,
) -> ExistingModelPreflight:
    """Create an ExistingModelPreflight input from lightweight project inventory.

    This helper collects likely model context only. Use
    `review_existing_model_preflight(...)` for the actual confidence decision.
    """

    root_path = Path(root)
    search_roots = tuple(
        path
        for path in (
            root_path / ".flowguard",
            root_path / "docs",
            root_path / "openspec",
        )
        if path.exists()
    )
    searched_paths = tuple(str(path.relative_to(root_path) if path.is_relative_to(root_path) else path) for path in search_roots)
    hits: list[ModelContextHit] = []
    flowguard_root = root_path / ".flowguard"
    if flowguard_root.exists():
        for path in sorted(flowguard_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "FlowGuard" not in text and "Workflow" not in text and "Invariant" not in text:
                continue
            if not _matches_changed_paths(path, text, changed_paths):
                continue
            model_id = _model_id_from_path(path, flowguard_root)
            classes = _class_names(text)
            responsibilities = _purpose_lines(text) or (model_id,)
            relative_path = str(path.relative_to(root_path))
            fields_owned = tuple(dict.fromkeys(re.findall(r"field:[A-Za-z0-9_.:-]+", text)))
            hits.append(
                ModelContextHit(
                    model_id=model_id,
                    model_path=relative_path,
                    evidence_tier="project_inventory",
                    evidence_current=True,
                    responsibilities=responsibilities,
                    function_blocks=classes,
                    fields_owned=fields_owned,
                    validation_evidence=(relative_path,),
                    rationale="Discovered from project FlowGuard inventory.",
                )
            )

    ownership_snapshot = None
    if hits:
        ownership_snapshot = ExistingOwnershipSnapshot(
            function_block_owners=tuple(
                (block, hit.model_id)
                for hit in hits
                for block in hit.function_blocks
            ),
            responsibility_owners=tuple(
                (responsibility, hit.model_id)
                for hit in hits
                for responsibility in hit.responsibilities
            ),
            field_owners=tuple(
                (field_id, hit.model_id)
                for hit in hits
                for field_id in hit.fields_owned
            ),
        )
    reuse_decision = REUSE_DECISION_REUSE_EXISTING if hits else REUSE_DECISION_NO_MODEL_FOUND
    no_model_found_reason = "" if hits else "No relevant FlowGuard model files were found in project inventory."
    rationale = (
        "Project inventory found existing FlowGuard model context."
        if hits
        else "Proceed with explicit no-model-found boundary before downstream modeling."
    )
    return ExistingModelPreflight(
        preflight_id or "project-inventory-preflight",
        task_summary,
        mode=mode,
        existing_modeled_system=True,
        model_search_performed=True,
        search_paths=searched_paths,
        relevant_models=tuple(hits),
        ownership_snapshot=ownership_snapshot,
        reuse_decision=reuse_decision,
        downstream_routes=tuple(downstream_routes),
        rationale=rationale,
        no_model_found_reason=no_model_found_reason,
    )


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
            if preflight.mode == PREFLIGHT_MODE_FULL:
                missing_layered_fields = _missing_layered_status_fields(model)
                if missing_layered_fields:
                    findings.append(
                        ExistingModelPreflightFinding(
                            "layered_proof_status_unknown",
                            "full preflight found a parent model but does not record parent coverage, child disjointness, child reattachment, leaf matrix status, and layered proof evidence id",
                            model_id=model.model_id,
                            metadata={
                                "missing_fields": missing_layered_fields,
                                "model": model.to_dict(),
                            },
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

    field_lifecycle_required = preflight.field_lifecycle_required or bool(preflight.behavior_field_ids)
    known_field_owner_ids = set(preflight.field_lifecycle_model_ids)
    for model in preflight.relevant_models:
        known_field_owner_ids.update(model.fields_owned)
    if preflight.ownership_snapshot:
        known_field_owner_ids.update(field_id for field_id, _owner in preflight.ownership_snapshot.field_owners)
    if field_lifecycle_required and not known_field_owner_ids:
        findings.append(
            ExistingModelPreflightFinding(
                "missing_field_lifecycle_ownership",
                "behavior-bearing fields are in scope but no field lifecycle model, field owner, or field ownership snapshot is recorded",
                metadata={
                    "behavior_field_ids": list(preflight.behavior_field_ids),
                    "downstream_routes": list(preflight.downstream_routes),
                },
            )
        )
    if field_lifecycle_required and "field_lifecycle_mesh" not in preflight.downstream_routes:
        findings.append(
            ExistingModelPreflightFinding(
                "missing_field_lifecycle_route",
                "behavior-bearing fields are in scope but field_lifecycle_mesh is not named as a downstream route",
                severity="warning",
                metadata={"behavior_field_ids": list(preflight.behavior_field_ids)},
            )
        )
    for gap_id in preflight.field_lifecycle_gap_ids:
        findings.append(
            ExistingModelPreflightFinding(
                "field_lifecycle_gap_unresolved",
                "existing field lifecycle preflight found an unresolved field model gap",
                item_id=gap_id,
                metadata={"field_lifecycle_gap_ids": list(preflight.field_lifecycle_gap_ids)},
            )
        )

    model_angle_required = preflight.model_angle_review_required or bool(
        preflight.model_angle_deliberations or preflight.model_angle_gap_ids
    )
    if model_angle_required:
        model_angle_report = review_model_angle_deliberations(
            f"{preflight.preflight_id}:model-angle",
            preflight.model_angle_deliberations,
            require_review=preflight.model_angle_review_required,
            broad_claim=preflight.mode == PREFLIGHT_MODE_FULL,
            allow_scoped_confidence=True,
        )
        for finding in model_angle_report.findings:
            severity = "warning"
            if finding.severity == "blocker" or model_angle_report.confidence == MODEL_ANGLE_CONFIDENCE_BLOCKED:
                severity = "blocker"
            elif model_angle_report.confidence == MODEL_ANGLE_CONFIDENCE_SCOPED:
                severity = "warning"
            findings.append(
                ExistingModelPreflightFinding(
                    f"model_angle_{finding.code}",
                    finding.message,
                    severity=severity,
                    model_id=",".join(
                        item.angle_id
                        for item in preflight.model_angle_deliberations
                        if item.angle_id == finding.angle_id
                    ),
                    item_id=finding.angle_id,
                    metadata={
                        "model_angle_finding": finding.to_dict(),
                        "model_angle_report": model_angle_report.to_dict(),
                    },
                )
            )
    for gap_id in preflight.model_angle_gap_ids:
        findings.append(
            ExistingModelPreflightFinding(
                "model_angle_gap_unresolved",
                "existing-model preflight found an unresolved model-angle gap",
                item_id=gap_id,
                metadata={"model_angle_gap_ids": list(preflight.model_angle_gap_ids)},
            )
        )

    similarity_handoff = preflight.similarity_handoff
    similarity_relation_ids = similarity_handoff.relation_ids if similarity_handoff else ()
    if preflight.mode == PREFLIGHT_MODE_FULL and preflight.similarity_review_required:
        if not similarity_relation_ids:
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_similarity_evidence",
                    "full preflight requires model-similarity review but names no current relation ids",
                )
            )
        if similarity_handoff and not similarity_handoff.evidence_current:
            findings.append(
                ExistingModelPreflightFinding(
                    "stale_similarity_evidence",
                    "full preflight requires model-similarity review but the similarity evidence is stale",
                    metadata={"similarity_relation_ids": list(similarity_relation_ids)},
                )
            )
        for gap in similarity_handoff.unresolved_gaps if similarity_handoff else ():
            findings.append(
                ExistingModelPreflightFinding(
                    "unresolved_similarity_gap",
                    "model-similarity review reported an unresolved gap for this boundary decision",
                    item_id=gap,
                    metadata={"similarity_relation_ids": list(similarity_relation_ids)},
                )
            )
        if similarity_handoff and similarity_relation_ids and not (
            similarity_handoff.maintenance_group_ids or similarity_handoff.false_friend_rationales
        ):
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_similarity_maintenance_group",
                    "current similarity relations should name the maintenance group or false-friend rationale that governs sibling review",
                    severity="warning",
                    metadata={"similarity_relation_ids": list(similarity_relation_ids)},
                )
            )
        if (
            similarity_handoff
            and similarity_handoff.impacted_model_ids
            and not similarity_handoff.change_impact_ids
        ):
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_similarity_change_impact",
                    "impacted sibling models from model-similarity review require change-impact ids before claiming all related work was checked",
                    metadata={"impacted_similarity_model_ids": list(similarity_handoff.impacted_model_ids)},
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
    if (
        preflight.reuse_decision == REUSE_DECISION_NEW_BOUNDARY
        and similarity_handoff
        and similarity_relation_ids
        and similarity_handoff.false_friend_rationales
        and not preflight.rationale
    ):
        findings.append(
            ExistingModelPreflightFinding(
                "false_friend_rationale_missing",
                "new boundary based on false-friend similarity must keep the separation rationale visible",
                metadata={"false_friend_rationales": list(similarity_handoff.false_friend_rationales)},
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
    "existing_model_preflight_from_project",
]
