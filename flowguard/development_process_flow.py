"""Development lifecycle process-flow governance helpers.

DevelopmentProcessFlow is the development-process simulator front door and the
execution-freshness owner. It reviews whether a development lifecycle can trust
current validation evidence after ordered artifact writes, verifier changes,
peer writes, and routine/release claims. It may reference evidence ids from
ModelMesh, TestMesh, StructureMesh, Model-Test Alignment, LongCheck, and
Conformance Adoption, but it does not inspect or replace those route internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .proof_artifact import ProofArtifactRef, coerce_proof_artifact_ref, proof_artifact_gap_codes


PROCESS_SCOPE_ROUTINE = "routine"
PROCESS_SCOPE_RELEASE = "release"

PROCESS_EVIDENCE_PASSED = "passed"
PROCESS_EVIDENCE_FAILED = "failed"
PROCESS_EVIDENCE_TIMEOUT = "timeout"
PROCESS_EVIDENCE_SKIPPED = "skipped"
PROCESS_EVIDENCE_NOT_RUN = "not_run"
PROCESS_EVIDENCE_RUNNING = "running"
PROCESS_EVIDENCE_ERROR = "error"

PROCESS_CLAIM_ACTIONS = {
    "claim_done",
    "claim_release",
    "claim_archive",
    "claim_publish",
    "publish",
    "archive",
    "release",
}

PROCESS_ARTIFACT_REQUIREMENT = "requirement"
PROCESS_ARTIFACT_DESIGN = "design"
PROCESS_ARTIFACT_MODEL = "model"
PROCESS_ARTIFACT_FIELD_LIFECYCLE = "field_lifecycle"
PROCESS_ARTIFACT_FIELD_PROJECTION = "field_projection"
PROCESS_ARTIFACT_REPLACEMENT_DISPOSITION = "replacement_disposition"
PROCESS_ARTIFACT_BUG_REPAIR_CLOSURE = "bug_repair_closure"
PROCESS_ARTIFACT_CODE = "code"
PROCESS_ARTIFACT_TEST = "test"
PROCESS_ARTIFACT_DOC = "doc"
PROCESS_ARTIFACT_RELEASE = "release"
PROCESS_ARTIFACT_REPORT = "report"
PROCESS_ARTIFACT_ADAPTER = "adapter"
PROCESS_ARTIFACT_UI_OBSERVED_INVENTORY = "ui_observed_inventory"
PROCESS_ARTIFACT_UI_FUNCTIONAL_CHAIN = "ui_functional_chain"
PROCESS_ARTIFACT_UI_FUNCTIONAL_CAPABILITY_COVERAGE = "ui_functional_capability_coverage"
PROCESS_ARTIFACT_UI_SOURCE_BASELINE_GATE = "ui_source_baseline_gate"
PROCESS_ARTIFACT_UI_DONE_CLAIM = "ui_done_claim"
PROCESS_ARTIFACT_UI_HUMAN_OPERABILITY = "ui_human_operability"

PROCESS_EVIDENCE_FIELD_LIFECYCLE = "field_lifecycle_mesh"
PROCESS_EVIDENCE_FIELD_PROJECTION = "field_projection"
PROCESS_EVIDENCE_MODEL_MISS_REVIEW = "model_miss_review"
PROCESS_EVIDENCE_BUG_REPAIR_CLOSURE = "bug_repair_closure"
PROCESS_EVIDENCE_UI_OBSERVED_INVENTORY = "ui_observed_inventory"
PROCESS_EVIDENCE_UI_FUNCTIONAL_CHAIN = "ui_functional_chain"
PROCESS_EVIDENCE_UI_FUNCTIONAL_CAPABILITY_COVERAGE = "ui_functional_capability_coverage"
PROCESS_EVIDENCE_UI_SOURCE_BASELINE_GATE = "ui_source_baseline_gate"
PROCESS_EVIDENCE_UI_IMPLEMENTATION_VALIDATION = "ui_implementation_validation"
PROCESS_EVIDENCE_UI_DONE_CLAIM_REVIEW = "ui_done_claim_review"
PROCESS_EVIDENCE_UI_HUMAN_OPERABILITY = "ui_human_operability"
PROCESS_EVIDENCE_UI_TASK_COVERAGE = "ui_task_coverage"
PROCESS_EVIDENCE_UI_AFFORDANCE_REVIEW = "ui_affordance_review"
PROCESS_EVIDENCE_UI_ACTION_GRAMMAR = "ui_action_grammar"
PROCESS_EVIDENCE_UI_DIALOG_RETURN = "ui_dialog_return"
PROCESS_EVIDENCE_UI_KEYBOARD_FOCUS = "ui_keyboard_focus"
PROCESS_EVIDENCE_UI_HUMAN_WALKTHROUGH = "ui_human_walkthrough"


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _as_version_mapping(values: Mapping[str, Any] | None) -> dict[str, str]:
    if values is None:
        return {}
    return {str(key): str(value) for key, value in values.items()}


@dataclass(frozen=True)
class ProcessArtifact:
    """One versioned lifecycle artifact."""

    artifact_id: str
    artifact_type: str = PROCESS_ARTIFACT_CODE
    current_version: str = "1"
    path: str = ""
    owner: str = ""
    upstream_artifact_ids: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", str(self.artifact_id))
        object.__setattr__(self, "artifact_type", str(self.artifact_type))
        object.__setattr__(self, "current_version", str(self.current_version))
        object.__setattr__(self, "path", str(self.path))
        object.__setattr__(self, "owner", str(self.owner))
        object.__setattr__(self, "upstream_artifact_ids", _as_tuple(self.upstream_artifact_ids))
        object.__setattr__(self, "description", str(self.description))

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "current_version": self.current_version,
            "path": self.path,
            "owner": self.owner,
            "upstream_artifact_ids": list(self.upstream_artifact_ids),
            "description": self.description,
        }


@dataclass(frozen=True)
class ActionEffect:
    """One explicit artifact or evidence effect from a process action."""

    target_id: str
    effect_type: str = "write"
    target_type: str = "artifact"
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", str(self.target_id))
        object.__setattr__(self, "effect_type", str(self.effect_type))
        object.__setattr__(self, "target_type", str(self.target_type))
        object.__setattr__(self, "description", str(self.description))

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "effect_type": self.effect_type,
            "target_type": self.target_type,
            "description": self.description,
        }


@dataclass(frozen=True)
class ProcessAction:
    """One ordered development, validation, or claim action."""

    action_id: str
    action_type: str = "work"
    reads_artifacts: tuple[str, ...] = ()
    writes_artifacts: tuple[str, ...] = ()
    invalidates_artifacts: tuple[str, ...] = ()
    invalidates_evidence: tuple[str, ...] = ()
    produced_evidence_ids: tuple[str, ...] = ()
    required_evidence_ids: tuple[str, ...] = ()
    required_validation_ids: tuple[str, ...] = ()
    effects: tuple[ActionEffect, ...] = ()
    order_after: tuple[str, ...] = ()
    actor: str = "agent"
    status: str = "done"
    decision_scope: str = PROCESS_SCOPE_ROUTINE
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", str(self.action_id))
        object.__setattr__(self, "action_type", str(self.action_type))
        object.__setattr__(self, "reads_artifacts", _as_tuple(self.reads_artifacts))
        object.__setattr__(self, "writes_artifacts", _as_tuple(self.writes_artifacts))
        object.__setattr__(self, "invalidates_artifacts", _as_tuple(self.invalidates_artifacts))
        object.__setattr__(self, "invalidates_evidence", _as_tuple(self.invalidates_evidence))
        object.__setattr__(self, "produced_evidence_ids", _as_tuple(self.produced_evidence_ids))
        object.__setattr__(self, "required_evidence_ids", _as_tuple(self.required_evidence_ids))
        object.__setattr__(self, "required_validation_ids", _as_tuple(self.required_validation_ids))
        object.__setattr__(self, "effects", tuple(self.effects))
        object.__setattr__(self, "order_after", _as_tuple(self.order_after))
        object.__setattr__(self, "actor", str(self.actor))
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "decision_scope", str(self.decision_scope))
        object.__setattr__(self, "description", str(self.description))

    def is_claim(self) -> bool:
        return self.action_type in PROCESS_CLAIM_ACTIONS or bool(
            self.required_evidence_ids or self.required_validation_ids
        )

    def all_written_artifacts(self) -> tuple[str, ...]:
        effect_writes = tuple(
            effect.target_id
            for effect in self.effects
            if effect.target_type == "artifact" and effect.effect_type in {"write", "invalidate"}
        )
        return tuple(dict.fromkeys(self.writes_artifacts + self.invalidates_artifacts + effect_writes))

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "reads_artifacts": list(self.reads_artifacts),
            "writes_artifacts": list(self.writes_artifacts),
            "invalidates_artifacts": list(self.invalidates_artifacts),
            "invalidates_evidence": list(self.invalidates_evidence),
            "produced_evidence_ids": list(self.produced_evidence_ids),
            "required_evidence_ids": list(self.required_evidence_ids),
            "required_validation_ids": list(self.required_validation_ids),
            "effects": [effect.to_dict() for effect in self.effects],
            "order_after": list(self.order_after),
            "actor": self.actor,
            "status": self.status,
            "decision_scope": self.decision_scope,
            "description": self.description,
        }


@dataclass(frozen=True)
class ProcessEvidence:
    """One validation evidence record bound to covered artifact versions."""

    evidence_id: str
    evidence_kind: str = "test"
    producer_route: str = "development_process_flow"
    status: str = PROCESS_EVIDENCE_NOT_RUN
    covers_artifacts: tuple[str, ...] = ()
    covered_versions: Mapping[str, Any] = field(default_factory=dict)
    verifier_artifacts: tuple[str, ...] = ()
    validation_requirement_ids: tuple[str, ...] = ()
    produced_by_action_id: str = ""
    command: str = ""
    result_path: str = ""
    proof_artifact: ProofArtifactRef | Mapping[str, Any] | None = None
    background: bool = False
    has_exit_artifact: bool = True
    has_result_artifact: bool = True
    progress_only: bool = False
    skipped_count: int = 0
    skipped_visible: bool = True
    release_required: bool = False
    stale_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "evidence_kind", str(self.evidence_kind))
        object.__setattr__(self, "producer_route", str(self.producer_route))
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "covers_artifacts", _as_tuple(self.covers_artifacts))
        object.__setattr__(self, "covered_versions", _as_version_mapping(self.covered_versions))
        object.__setattr__(self, "verifier_artifacts", _as_tuple(self.verifier_artifacts))
        object.__setattr__(self, "validation_requirement_ids", _as_tuple(self.validation_requirement_ids))
        object.__setattr__(self, "produced_by_action_id", str(self.produced_by_action_id))
        object.__setattr__(self, "command", str(self.command))
        object.__setattr__(self, "result_path", str(self.result_path))
        object.__setattr__(self, "proof_artifact", coerce_proof_artifact_ref(self.proof_artifact))
        object.__setattr__(self, "skipped_count", int(self.skipped_count))
        object.__setattr__(self, "stale_reasons", _as_tuple(self.stale_reasons))

    def background_complete(self) -> bool:
        if not self.background:
            return True
        return self.has_exit_artifact and self.has_result_artifact and not self.progress_only

    def covered_artifact_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(self.covers_artifacts + self.verifier_artifacts))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_kind": self.evidence_kind,
            "producer_route": self.producer_route,
            "status": self.status,
            "covers_artifacts": list(self.covers_artifacts),
            "covered_versions": dict(self.covered_versions),
            "verifier_artifacts": list(self.verifier_artifacts),
            "validation_requirement_ids": list(self.validation_requirement_ids),
            "produced_by_action_id": self.produced_by_action_id,
            "command": self.command,
            "result_path": self.result_path,
            "proof_artifact": self.proof_artifact.to_dict() if self.proof_artifact else None,
            "background": self.background,
            "has_exit_artifact": self.has_exit_artifact,
            "has_result_artifact": self.has_result_artifact,
            "progress_only": self.progress_only,
            "skipped_count": self.skipped_count,
            "skipped_visible": self.skipped_visible,
            "release_required": self.release_required,
            "stale_reasons": list(self.stale_reasons),
        }


@dataclass(frozen=True)
class FreshnessRule:
    """Explicit lifecycle propagation rule from upstream changes to evidence."""

    rule_id: str
    upstream_artifact_id: str
    invalidates_artifact_ids: tuple[str, ...] = ()
    invalidates_evidence_kinds: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", str(self.rule_id))
        object.__setattr__(self, "upstream_artifact_id", str(self.upstream_artifact_id))
        object.__setattr__(self, "invalidates_artifact_ids", _as_tuple(self.invalidates_artifact_ids))
        object.__setattr__(self, "invalidates_evidence_kinds", _as_tuple(self.invalidates_evidence_kinds))
        object.__setattr__(self, "description", str(self.description))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "upstream_artifact_id": self.upstream_artifact_id,
            "invalidates_artifact_ids": list(self.invalidates_artifact_ids),
            "invalidates_evidence_kinds": list(self.invalidates_evidence_kinds),
            "description": self.description,
        }


@dataclass(frozen=True)
class ValidationRequirement:
    """A lifecycle validation obligation needed for a claim scope."""

    requirement_id: str
    required_artifact_ids: tuple[str, ...] = ()
    required_evidence_kinds: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    scope: str = PROCESS_SCOPE_ROUTINE
    release_required: bool = False
    v_model_pair: bool = False
    command: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "requirement_id", str(self.requirement_id))
        object.__setattr__(self, "required_artifact_ids", _as_tuple(self.required_artifact_ids))
        object.__setattr__(self, "required_evidence_kinds", _as_tuple(self.required_evidence_kinds))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "scope", str(self.scope))
        object.__setattr__(self, "command", str(self.command))
        object.__setattr__(self, "description", str(self.description))

    def is_release_only(self) -> bool:
        return self.release_required or self.scope == PROCESS_SCOPE_RELEASE

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "required_artifact_ids": list(self.required_artifact_ids),
            "required_evidence_kinds": list(self.required_evidence_kinds),
            "evidence_ids": list(self.evidence_ids),
            "scope": self.scope,
            "release_required": self.release_required,
            "v_model_pair": self.v_model_pair,
            "command": self.command,
            "description": self.description,
        }


@dataclass(frozen=True)
class DevelopmentProcessPlan:
    """A lifecycle process and the evidence used for a routine/release claim."""

    process_id: str
    artifacts: tuple[ProcessArtifact, ...] = ()
    actions: tuple[ProcessAction, ...] = ()
    evidence: tuple[ProcessEvidence, ...] = ()
    validation_requirements: tuple[ValidationRequirement, ...] = ()
    freshness_rules: tuple[FreshnessRule, ...] = ()
    decision_scope: str = PROCESS_SCOPE_ROUTINE
    require_proof_artifacts: bool = False
    release_deferred_allowed: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "process_id", str(self.process_id))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "actions", tuple(self.actions))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "validation_requirements", tuple(self.validation_requirements))
        object.__setattr__(self, "freshness_rules", tuple(self.freshness_rules))
        object.__setattr__(self, "decision_scope", str(self.decision_scope))

    def to_dict(self) -> dict[str, Any]:
        return {
            "process_id": self.process_id,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "actions": [action.to_dict() for action in self.actions],
            "evidence": [evidence.to_dict() for evidence in self.evidence],
            "validation_requirements": [
                requirement.to_dict() for requirement in self.validation_requirements
            ],
            "freshness_rules": [rule.to_dict() for rule in self.freshness_rules],
            "decision_scope": self.decision_scope,
            "require_proof_artifacts": self.require_proof_artifacts,
            "release_deferred_allowed": self.release_deferred_allowed,
        }


@dataclass(frozen=True)
class RevalidationRecommendation:
    """One recommended validation rerun or evidence refresh."""

    requirement_id: str
    evidence_id: str = ""
    command: str = ""
    scope: str = PROCESS_SCOPE_ROUTINE
    artifact_ids: tuple[str, ...] = ()
    reason: str = ""
    producer_route: str = ""
    proof_artifact_required: bool = False
    freshness_gap_codes: tuple[str, ...] = ()
    blocks_claim_scopes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "requirement_id", str(self.requirement_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "command", str(self.command))
        object.__setattr__(self, "scope", str(self.scope))
        object.__setattr__(self, "artifact_ids", _as_tuple(self.artifact_ids))
        object.__setattr__(self, "reason", str(self.reason))
        object.__setattr__(self, "producer_route", str(self.producer_route))
        object.__setattr__(self, "proof_artifact_required", bool(self.proof_artifact_required))
        object.__setattr__(self, "freshness_gap_codes", _as_tuple(self.freshness_gap_codes))
        object.__setattr__(self, "blocks_claim_scopes", _as_tuple(self.blocks_claim_scopes))

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "evidence_id": self.evidence_id,
            "command": self.command,
            "scope": self.scope,
            "artifact_ids": list(self.artifact_ids),
            "reason": self.reason,
            "producer_route": self.producer_route,
            "proof_artifact_required": self.proof_artifact_required,
            "freshness_gap_codes": list(self.freshness_gap_codes),
            "blocks_claim_scopes": list(self.blocks_claim_scopes),
        }


@dataclass(frozen=True)
class ProcessFlowFinding:
    """One lifecycle ordering, evidence, freshness, or claim finding."""

    code: str
    message: str
    severity: str = "blocker"
    action_id: str = ""
    evidence_id: str = ""
    artifact_id: str = ""
    requirement_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "action_id", str(self.action_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "artifact_id", str(self.artifact_id))
        object.__setattr__(self, "requirement_id", str(self.requirement_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "action_id": self.action_id,
            "evidence_id": self.evidence_id,
            "artifact_id": self.artifact_id,
            "requirement_id": self.requirement_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class DevelopmentProcessFlowReport:
    """Structured outcome of a development lifecycle review."""

    ok: bool
    process_id: str
    decision: str
    decision_scope: str
    findings: tuple[ProcessFlowFinding, ...] = ()
    release_obligations: tuple[str, ...] = ()
    revalidation_recommendations: tuple[RevalidationRecommendation, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "process_id", str(self.process_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "decision_scope", str(self.decision_scope))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "release_obligations", _as_tuple(self.release_obligations))
        object.__setattr__(
            self,
            "revalidation_recommendations",
            tuple(self.revalidation_recommendations),
        )
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: process={self.process_id} scope={self.decision_scope} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard development process flow review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"process: {self.process_id}",
            f"scope: {self.decision_scope}",
            f"decision: {self.decision}",
            f"findings: {len(self.findings)}",
        ]
        if self.release_obligations:
            lines.append("release_obligations:")
            for item_id in self.release_obligations:
                lines.append(f"  - {item_id}")
        if self.revalidation_recommendations:
            lines.append("revalidation:")
            for recommendation in self.revalidation_recommendations:
                detail = recommendation.evidence_id or recommendation.requirement_id
                suffix_parts = []
                if recommendation.producer_route:
                    suffix_parts.append(f"route={recommendation.producer_route}")
                if recommendation.proof_artifact_required:
                    suffix_parts.append("proof_artifact_required=true")
                if recommendation.freshness_gap_codes:
                    suffix_parts.append(
                        "gaps=" + ",".join(recommendation.freshness_gap_codes)
                    )
                if recommendation.blocks_claim_scopes:
                    suffix_parts.append(
                        "blocks=" + ",".join(recommendation.blocks_claim_scopes)
                    )
                suffix = f" ({'; '.join(suffix_parts)})" if suffix_parts else ""
                lines.append(f"  - {detail}: {recommendation.reason}{suffix}")
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"action: {finding.action_id or '(none)'}",
                    f"evidence: {finding.evidence_id or '(none)'}",
                    f"artifact: {finding.artifact_id or '(none)'}",
                    f"requirement: {finding.requirement_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "process_id": self.process_id,
            "decision": self.decision,
            "decision_scope": self.decision_scope,
            "findings": [finding.to_dict() for finding in self.findings],
            "release_obligations": list(self.release_obligations),
            "revalidation_recommendations": [
                recommendation.to_dict()
                for recommendation in self.revalidation_recommendations
            ],
            "summary": self.summary,
        }


def _blocker_findings(findings: Sequence[ProcessFlowFinding]) -> tuple[ProcessFlowFinding, ...]:
    return tuple(finding for finding in findings if finding.severity == "blocker")


def _decision_for_findings(findings: Sequence[ProcessFlowFinding]) -> str:
    blockers = _blocker_findings(findings)
    if not blockers:
        return "development_process_flow_green_can_continue"
    priority = [
        ("unknown_artifact_reference", "process_reference_blocked"),
        ("unknown_evidence_reference", "process_reference_blocked"),
        ("unknown_validation_requirement", "process_reference_blocked"),
        ("out_of_order_process_step", "process_order_blocked"),
        ("duplicate_artifact_id", "process_registry_blocked"),
        ("stale_evidence_after_artifact_change", "revalidation_required"),
        ("test_changed_after_test_pass", "revalidation_required"),
        ("model_changed_after_alignment_pass", "revalidation_required"),
        ("field_lifecycle_changed_after_field_evidence", "revalidation_required"),
        ("field_projection_changed_after_alignment_pass", "revalidation_required"),
        ("replacement_disposition_changed_after_closure_pass", "revalidation_required"),
        ("bug_repair_closure_changed_after_review_pass", "revalidation_required"),
        ("requirement_change_without_downstream_revalidation", "revalidation_required"),
        ("direct_evidence_invalidation", "revalidation_required"),
        ("unknown_writer_invalidates_evidence", "peer_write_review_required"),
        ("ambiguous_freshness_policy", "freshness_policy_required"),
        ("missing_v_model_validation_pair", "missing_validation_evidence"),
        ("missing_required_revalidation", "missing_revalidation"),
        ("release_claim_with_stale_evidence", "release_claim_blocked"),
        ("progress_only_validation_claimed_complete", "validation_incomplete"),
        ("hidden_skipped_validation_claimed_pass", "validation_incomplete"),
        ("failed_validation_claimed_current", "validation_failed"),
        ("validation_evidence_not_current", "validation_not_current"),
        ("release_evidence_not_current", "missing_release_evidence"),
    ]
    codes = {finding.code for finding in blockers}
    for code, decision in priority:
        if code in codes:
            return decision
    return "development_process_flow_blocked"


def _artifact_maps(plan: DevelopmentProcessPlan) -> tuple[dict[str, ProcessArtifact], list[ProcessFlowFinding]]:
    artifacts: dict[str, ProcessArtifact] = {}
    findings: list[ProcessFlowFinding] = []
    for artifact in plan.artifacts:
        if artifact.artifact_id in artifacts:
            findings.append(
                ProcessFlowFinding(
                    "duplicate_artifact_id",
                    f"artifact {artifact.artifact_id} is registered more than once",
                    artifact_id=artifact.artifact_id,
                )
            )
        artifacts[artifact.artifact_id] = artifact
    return artifacts, findings


def _validate_references(
    plan: DevelopmentProcessPlan,
    artifacts: Mapping[str, ProcessArtifact],
) -> list[ProcessFlowFinding]:
    findings: list[ProcessFlowFinding] = []
    evidence_ids = {evidence.evidence_id for evidence in plan.evidence}
    requirement_ids = {requirement.requirement_id for requirement in plan.validation_requirements}
    action_ids = {action.action_id for action in plan.actions}

    def unknown_artifact(ref: str, *, action_id: str = "", evidence_id: str = "", requirement_id: str = "") -> None:
        if ref and ref not in artifacts:
            findings.append(
                ProcessFlowFinding(
                    "unknown_artifact_reference",
                    f"unknown artifact reference {ref}",
                    action_id=action_id,
                    evidence_id=evidence_id,
                    artifact_id=ref,
                    requirement_id=requirement_id,
                )
            )

    for artifact in artifacts.values():
        for upstream_id in artifact.upstream_artifact_ids:
            unknown_artifact(upstream_id)

    for action in plan.actions:
        for dependency in action.order_after:
            if dependency not in action_ids:
                findings.append(
                    ProcessFlowFinding(
                        "out_of_order_process_step",
                        f"action {action.action_id} depends on unknown or unordered action {dependency}",
                        action_id=action.action_id,
                        metadata=action.to_dict(),
                    )
                )
        for ref in action.reads_artifacts + action.writes_artifacts + action.invalidates_artifacts:
            unknown_artifact(ref, action_id=action.action_id)
        for evidence_id in action.invalidates_evidence + action.produced_evidence_ids + action.required_evidence_ids:
            if evidence_id not in evidence_ids:
                findings.append(
                    ProcessFlowFinding(
                        "unknown_evidence_reference",
                        f"action {action.action_id} references unknown evidence {evidence_id}",
                        action_id=action.action_id,
                        evidence_id=evidence_id,
                        metadata=action.to_dict(),
                    )
                )
        for requirement_id in action.required_validation_ids:
            if requirement_id not in requirement_ids:
                findings.append(
                    ProcessFlowFinding(
                        "unknown_validation_requirement",
                        f"action {action.action_id} references unknown validation requirement {requirement_id}",
                        action_id=action.action_id,
                        requirement_id=requirement_id,
                        metadata=action.to_dict(),
                    )
                )

    for evidence in plan.evidence:
        for ref in evidence.covered_artifact_ids():
            unknown_artifact(ref, evidence_id=evidence.evidence_id)
        for ref in evidence.covered_versions:
            unknown_artifact(ref, evidence_id=evidence.evidence_id)
        if evidence.produced_by_action_id and evidence.produced_by_action_id not in action_ids:
            findings.append(
                ProcessFlowFinding(
                    "out_of_order_process_step",
                    f"evidence {evidence.evidence_id} is produced by unknown action {evidence.produced_by_action_id}",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        for requirement_id in evidence.validation_requirement_ids:
            if requirement_id not in requirement_ids:
                findings.append(
                    ProcessFlowFinding(
                        "unknown_validation_requirement",
                        f"evidence {evidence.evidence_id} references unknown validation requirement {requirement_id}",
                        evidence_id=evidence.evidence_id,
                        requirement_id=requirement_id,
                    )
                )

    for requirement in plan.validation_requirements:
        for ref in requirement.required_artifact_ids:
            unknown_artifact(ref, requirement_id=requirement.requirement_id)
        for evidence_id in requirement.evidence_ids:
            if evidence_id not in evidence_ids:
                findings.append(
                    ProcessFlowFinding(
                        "unknown_evidence_reference",
                        f"validation requirement {requirement.requirement_id} references unknown evidence {evidence_id}",
                        evidence_id=evidence_id,
                        requirement_id=requirement.requirement_id,
                    )
                )

    for rule in plan.freshness_rules:
        unknown_artifact(rule.upstream_artifact_id)
        for ref in rule.invalidates_artifact_ids:
            unknown_artifact(ref)
    return findings


def _action_index(plan: DevelopmentProcessPlan) -> dict[str, int]:
    return {action.action_id: index for index, action in enumerate(plan.actions)}


def _stale_code_for_artifact(artifact: ProcessArtifact | None, evidence: ProcessEvidence) -> str:
    if artifact is None:
        return "stale_evidence_after_artifact_change"
    if artifact.artifact_type == PROCESS_ARTIFACT_TEST or artifact.artifact_id in evidence.verifier_artifacts:
        return "test_changed_after_test_pass"
    if artifact.artifact_type == PROCESS_ARTIFACT_MODEL and evidence.evidence_kind == "model_test_alignment":
        return "model_changed_after_alignment_pass"
    if artifact.artifact_type == PROCESS_ARTIFACT_FIELD_LIFECYCLE:
        return "field_lifecycle_changed_after_field_evidence"
    if artifact.artifact_type == PROCESS_ARTIFACT_FIELD_PROJECTION:
        return "field_projection_changed_after_alignment_pass"
    if artifact.artifact_type == PROCESS_ARTIFACT_REPLACEMENT_DISPOSITION:
        return "replacement_disposition_changed_after_closure_pass"
    if artifact.artifact_type == PROCESS_ARTIFACT_BUG_REPAIR_CLOSURE:
        return "bug_repair_closure_changed_after_review_pass"
    if artifact.artifact_type == PROCESS_ARTIFACT_UI_OBSERVED_INVENTORY:
        return "ui_observed_inventory_changed_after_evidence"
    if artifact.artifact_type == PROCESS_ARTIFACT_UI_FUNCTIONAL_CHAIN:
        return "ui_functional_chain_changed_after_evidence"
    if artifact.artifact_type == PROCESS_ARTIFACT_UI_FUNCTIONAL_CAPABILITY_COVERAGE:
        return "ui_functional_capability_coverage_changed_after_evidence"
    if artifact.artifact_type == PROCESS_ARTIFACT_UI_SOURCE_BASELINE_GATE:
        return "ui_source_baseline_gate_changed_after_evidence"
    if artifact.artifact_type == PROCESS_ARTIFACT_UI_DONE_CLAIM:
        return "ui_done_claim_changed_after_review_pass"
    if artifact.artifact_type == PROCESS_ARTIFACT_UI_HUMAN_OPERABILITY:
        return "ui_human_operability_changed_after_evidence"
    return "stale_evidence_after_artifact_change"


def _evidence_stale_reasons(
    plan: DevelopmentProcessPlan,
    artifacts: Mapping[str, ProcessArtifact],
    evidence: ProcessEvidence,
) -> dict[str, tuple[str, str]]:
    reasons: dict[str, tuple[str, str]] = {}
    for reason in evidence.stale_reasons:
        reasons[f"declared:{reason}"] = ("stale_evidence_after_artifact_change", reason)

    for artifact_id in evidence.covered_artifact_ids():
        artifact = artifacts.get(artifact_id)
        if artifact is None:
            continue
        covered_version = evidence.covered_versions.get(artifact_id)
        if covered_version is None:
            reasons[f"missing-version:{artifact_id}"] = (
                "stale_evidence_after_artifact_change",
                f"evidence does not record covered version for {artifact_id}",
            )
        elif covered_version != artifact.current_version:
            code = _stale_code_for_artifact(artifact, evidence)
            reasons[f"version:{artifact_id}"] = (
                code,
                f"evidence covers {artifact_id}@{covered_version}, current is {artifact.current_version}",
            )

    produced_index = _action_index(plan).get(evidence.produced_by_action_id, -1)
    for action_index, action in enumerate(plan.actions):
        if action_index <= produced_index:
            continue
        for evidence_id in action.invalidates_evidence:
            if evidence_id == evidence.evidence_id:
                reasons[f"direct:{action.action_id}"] = (
                    "direct_evidence_invalidation",
                    f"action {action.action_id} directly invalidates evidence {evidence.evidence_id}",
                )
        written = set(action.all_written_artifacts())
        if not written:
            continue
        if set(evidence.covered_artifact_ids()) & written:
            artifact_id = sorted(set(evidence.covered_artifact_ids()) & written)[0]
            artifact = artifacts.get(artifact_id)
            code = _stale_code_for_artifact(artifact, evidence)
            reasons[f"write:{action.action_id}:{artifact_id}"] = (
                code,
                f"action {action.action_id} changed {artifact_id} after evidence {evidence.evidence_id}",
            )
        if action.actor in {"", "unknown", "peer", "peer_agent", "peer-agent"} and set(evidence.covered_artifact_ids()) & written:
            artifact_id = sorted(set(evidence.covered_artifact_ids()) & written)[0]
            reasons[f"peer:{action.action_id}:{artifact_id}"] = (
                "unknown_writer_invalidates_evidence",
                f"unknown or peer writer {action.action_id} changed {artifact_id} after evidence {evidence.evidence_id}",
            )

    for rule in plan.freshness_rules:
        for action_index, action in enumerate(plan.actions):
            if action_index <= produced_index:
                continue
            if rule.upstream_artifact_id not in action.all_written_artifacts():
                continue
            covers_invalidated_artifact = bool(set(rule.invalidates_artifact_ids) & set(evidence.covers_artifacts))
            covers_invalidated_kind = not rule.invalidates_evidence_kinds or evidence.evidence_kind in rule.invalidates_evidence_kinds
            if covers_invalidated_artifact and covers_invalidated_kind:
                reasons[f"rule:{rule.rule_id}:{action.action_id}"] = (
                    "requirement_change_without_downstream_revalidation",
                    f"freshness rule {rule.rule_id} invalidates {evidence.evidence_id} after {action.action_id}",
                )
    return reasons


def _evidence_quality_findings(evidence: ProcessEvidence, *, require_proof_artifacts: bool = False) -> list[ProcessFlowFinding]:
    findings: list[ProcessFlowFinding] = []
    if evidence.progress_only or not evidence.background_complete():
        findings.append(
            ProcessFlowFinding(
                "progress_only_validation_claimed_complete",
                f"evidence {evidence.evidence_id} has progress output without final completion evidence",
                evidence_id=evidence.evidence_id,
                metadata=evidence.to_dict(),
            )
        )
    if evidence.skipped_count and not evidence.skipped_visible:
        findings.append(
            ProcessFlowFinding(
                "hidden_skipped_validation_claimed_pass",
                f"evidence {evidence.evidence_id} hides skipped validation",
                evidence_id=evidence.evidence_id,
                metadata=evidence.to_dict(),
            )
        )
    if evidence.status == PROCESS_EVIDENCE_FAILED:
        findings.append(
            ProcessFlowFinding(
                "failed_validation_claimed_current",
                f"evidence {evidence.evidence_id} failed",
                evidence_id=evidence.evidence_id,
                metadata=evidence.to_dict(),
            )
        )
    elif evidence.status in {
        PROCESS_EVIDENCE_TIMEOUT,
        PROCESS_EVIDENCE_SKIPPED,
        PROCESS_EVIDENCE_NOT_RUN,
        PROCESS_EVIDENCE_RUNNING,
        PROCESS_EVIDENCE_ERROR,
    }:
        findings.append(
            ProcessFlowFinding(
                "validation_evidence_not_current",
                f"evidence {evidence.evidence_id} status is {evidence.status}",
                evidence_id=evidence.evidence_id,
                metadata=evidence.to_dict(),
            )
        )
    if require_proof_artifacts:
        for code, message in proof_artifact_gap_codes(
            evidence.proof_artifact,
            declared_status=evidence.status,
            required_obligation_ids=evidence.validation_requirement_ids,
            require_result_path=True,
            require_fingerprints=True,
        ):
            findings.append(
                ProcessFlowFinding(
                    code.replace("proof_artifact", "process_proof_artifact"),
                    message,
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
    return findings


def _evidence_is_current(
    evidence: ProcessEvidence,
    stale_reasons: Mapping[str, tuple[str, str]],
) -> bool:
    return (
        evidence.status == PROCESS_EVIDENCE_PASSED
        and not stale_reasons
        and not evidence.progress_only
        and evidence.background_complete()
        and not (evidence.skipped_count and not evidence.skipped_visible)
    )


def _requirement_candidate_evidence(
    requirement: ValidationRequirement,
    evidence_rows: Sequence[ProcessEvidence],
) -> tuple[ProcessEvidence, ...]:
    candidates: list[ProcessEvidence] = []
    required_artifacts = set(requirement.required_artifact_ids)
    required_kinds = set(requirement.required_evidence_kinds)
    explicit_ids = set(requirement.evidence_ids)
    for evidence in evidence_rows:
        if explicit_ids and evidence.evidence_id not in explicit_ids:
            continue
        if required_kinds and evidence.evidence_kind not in required_kinds:
            continue
        if required_artifacts and not required_artifacts.issubset(set(evidence.covers_artifacts)):
            continue
        if requirement.requirement_id in evidence.validation_requirement_ids or not evidence.validation_requirement_ids or explicit_ids:
            candidates.append(evidence)
    return tuple(candidates)


def _requirement_findings(
    plan: DevelopmentProcessPlan,
    stale_by_evidence: Mapping[str, Mapping[str, tuple[str, str]]],
) -> tuple[list[ProcessFlowFinding], list[str], list[RevalidationRecommendation]]:
    findings: list[ProcessFlowFinding] = []
    release_obligations: list[str] = []
    recommendations: list[RevalidationRecommendation] = []

    for requirement in plan.validation_requirements:
        release_only = requirement.is_release_only()
        candidates = _requirement_candidate_evidence(requirement, plan.evidence)
        current_candidates = tuple(
            evidence
            for evidence in candidates
            if _evidence_is_current(evidence, stale_by_evidence.get(evidence.evidence_id, {}))
        )
        deferred_release = (
            plan.decision_scope == PROCESS_SCOPE_ROUTINE
            and plan.release_deferred_allowed
            and release_only
            and not current_candidates
        )
        if deferred_release:
            release_obligations.append(requirement.requirement_id)
            findings.append(
                ProcessFlowFinding(
                    "release_evidence_deferred",
                    f"release validation requirement {requirement.requirement_id} is deferred for routine confidence",
                    severity="warning",
                    requirement_id=requirement.requirement_id,
                    metadata=requirement.to_dict(),
                )
            )
            continue
        if current_candidates:
            continue

        code = "missing_required_revalidation"
        if requirement.v_model_pair:
            code = "missing_v_model_validation_pair"
        if plan.decision_scope == PROCESS_SCOPE_RELEASE and release_only:
            code = "release_evidence_not_current"
        findings.append(
            ProcessFlowFinding(
                code,
                f"validation requirement {requirement.requirement_id} has no current passing evidence",
                requirement_id=requirement.requirement_id,
                metadata={
                    "requirement": requirement.to_dict(),
                    "candidate_evidence": [evidence.to_dict() for evidence in candidates],
                },
            )
        )
        evidence_id = candidates[0].evidence_id if candidates else ""
        candidate = candidates[0] if candidates else None
        stale_reasons = stale_by_evidence.get(evidence_id, {}) if evidence_id else {}
        reason = "missing current evidence"
        if stale_reasons:
            reason = next(iter(stale_reasons.values()))[1]
        blocks_claim_scopes = [requirement.scope]
        if plan.decision_scope not in blocks_claim_scopes:
            blocks_claim_scopes.append(plan.decision_scope)
        recommendations.append(
            RevalidationRecommendation(
                requirement.requirement_id,
                evidence_id=evidence_id,
                command=requirement.command or (candidate.command if candidate else ""),
                scope=requirement.scope,
                artifact_ids=requirement.required_artifact_ids,
                reason=reason,
                producer_route=candidate.producer_route if candidate else "",
                proof_artifact_required=plan.require_proof_artifacts,
                freshness_gap_codes=tuple(code for code, _message in stale_reasons.values()),
                blocks_claim_scopes=tuple(blocks_claim_scopes),
            )
        )
    return findings, release_obligations, recommendations


def _claim_findings(
    plan: DevelopmentProcessPlan,
    stale_by_evidence: Mapping[str, Mapping[str, tuple[str, str]]],
) -> list[ProcessFlowFinding]:
    findings: list[ProcessFlowFinding] = []
    evidence_by_id = {evidence.evidence_id: evidence for evidence in plan.evidence}
    requirements_by_id = {
        requirement.requirement_id: requirement
        for requirement in plan.validation_requirements
    }
    for action in plan.actions:
        if not action.is_claim():
            continue
        for evidence_id in action.required_evidence_ids:
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                continue
            stale_reasons = stale_by_evidence.get(evidence_id, {})
            if stale_reasons:
                findings.append(
                    ProcessFlowFinding(
                        "release_claim_with_stale_evidence",
                        f"claim {action.action_id} relies on stale evidence {evidence_id}",
                        action_id=action.action_id,
                        evidence_id=evidence_id,
                        metadata={"action": action.to_dict(), "stale_reasons": dict(stale_reasons)},
                    )
                )
            elif not _evidence_is_current(evidence, stale_reasons):
                findings.append(
                    ProcessFlowFinding(
                        "missing_required_revalidation",
                        f"claim {action.action_id} lacks current evidence {evidence_id}",
                        action_id=action.action_id,
                        evidence_id=evidence_id,
                        metadata={"action": action.to_dict(), "evidence": evidence.to_dict()},
                    )
                )
        for requirement_id in action.required_validation_ids:
            requirement = requirements_by_id.get(requirement_id)
            if requirement is None:
                continue
            candidates = _requirement_candidate_evidence(requirement, plan.evidence)
            if not any(
                _evidence_is_current(evidence, stale_by_evidence.get(evidence.evidence_id, {}))
                for evidence in candidates
            ):
                findings.append(
                    ProcessFlowFinding(
                        "missing_required_revalidation",
                        f"claim {action.action_id} lacks current evidence for requirement {requirement_id}",
                        action_id=action.action_id,
                        requirement_id=requirement_id,
                        metadata={"action": action.to_dict(), "requirement": requirement.to_dict()},
                    )
                )
    return findings


def _ambiguous_policy_findings(
    plan: DevelopmentProcessPlan,
    artifacts: Mapping[str, ProcessArtifact],
) -> list[ProcessFlowFinding]:
    findings: list[ProcessFlowFinding] = []
    rule_upstreams = {rule.upstream_artifact_id for rule in plan.freshness_rules}
    written = {artifact_id for action in plan.actions for artifact_id in action.all_written_artifacts()}
    has_claim = any(action.is_claim() for action in plan.actions) or bool(plan.validation_requirements)
    if not has_claim:
        return findings
    for artifact in artifacts.values():
        for upstream_id in artifact.upstream_artifact_ids:
            if upstream_id in written and upstream_id not in rule_upstreams:
                findings.append(
                    ProcessFlowFinding(
                        "ambiguous_freshness_policy",
                        f"artifact {artifact.artifact_id} depends on {upstream_id}, but no freshness rule explains invalidation",
                        artifact_id=artifact.artifact_id,
                        metadata={"artifact": artifact.to_dict(), "upstream_id": upstream_id},
                    )
                )
    return findings


def review_development_process_flow(plan: DevelopmentProcessPlan) -> DevelopmentProcessFlowReport:
    """Review a development lifecycle plan without running its checks."""

    artifacts, findings = _artifact_maps(plan)
    findings.extend(_validate_references(plan, artifacts))
    stale_by_evidence: dict[str, dict[str, tuple[str, str]]] = {}
    for evidence in plan.evidence:
        stale_reasons = _evidence_stale_reasons(plan, artifacts, evidence)
        stale_by_evidence[evidence.evidence_id] = stale_reasons
        for reason_key, (code, message) in stale_reasons.items():
            artifact_id = ""
            if ":" in reason_key:
                artifact_id = reason_key.rsplit(":", 1)[-1]
                if artifact_id not in artifacts:
                    artifact_id = ""
            findings.append(
                ProcessFlowFinding(
                    code,
                    message,
                    evidence_id=evidence.evidence_id,
                    artifact_id=artifact_id,
                    metadata={"evidence": evidence.to_dict(), "reason_key": reason_key},
                )
            )
        findings.extend(_evidence_quality_findings(evidence, require_proof_artifacts=plan.require_proof_artifacts))

    findings.extend(_ambiguous_policy_findings(plan, artifacts))
    requirement_findings, release_obligations, recommendations = _requirement_findings(plan, stale_by_evidence)
    findings.extend(requirement_findings)
    findings.extend(_claim_findings(plan, stale_by_evidence))

    blockers = _blocker_findings(findings)
    return DevelopmentProcessFlowReport(
        ok=not blockers,
        process_id=plan.process_id,
        decision=_decision_for_findings(findings),
        decision_scope=plan.decision_scope,
        findings=tuple(findings),
        release_obligations=tuple(release_obligations),
        revalidation_recommendations=tuple(recommendations),
    )


def derive_revalidation_plan(plan: DevelopmentProcessPlan) -> tuple[RevalidationRecommendation, ...]:
    """Return the minimum revalidation recommendations from a lifecycle review."""

    return review_development_process_flow(plan).revalidation_recommendations


__all__ = [
    "PROCESS_ARTIFACT_ADAPTER",
    "PROCESS_ARTIFACT_CODE",
    "PROCESS_ARTIFACT_DESIGN",
    "PROCESS_ARTIFACT_DOC",
    "PROCESS_ARTIFACT_BUG_REPAIR_CLOSURE",
    "PROCESS_ARTIFACT_FIELD_LIFECYCLE",
    "PROCESS_ARTIFACT_FIELD_PROJECTION",
    "PROCESS_ARTIFACT_MODEL",
    "PROCESS_ARTIFACT_REPLACEMENT_DISPOSITION",
    "PROCESS_ARTIFACT_RELEASE",
    "PROCESS_ARTIFACT_REPORT",
    "PROCESS_ARTIFACT_REQUIREMENT",
    "PROCESS_ARTIFACT_TEST",
    "PROCESS_ARTIFACT_UI_SOURCE_BASELINE_GATE",
    "PROCESS_ARTIFACT_UI_DONE_CLAIM",
    "PROCESS_ARTIFACT_UI_FUNCTIONAL_CAPABILITY_COVERAGE",
    "PROCESS_ARTIFACT_UI_FUNCTIONAL_CHAIN",
    "PROCESS_ARTIFACT_UI_HUMAN_OPERABILITY",
    "PROCESS_ARTIFACT_UI_OBSERVED_INVENTORY",
    "PROCESS_CLAIM_ACTIONS",
    "PROCESS_EVIDENCE_ERROR",
    "PROCESS_EVIDENCE_FAILED",
    "PROCESS_EVIDENCE_BUG_REPAIR_CLOSURE",
    "PROCESS_EVIDENCE_FIELD_LIFECYCLE",
    "PROCESS_EVIDENCE_FIELD_PROJECTION",
    "PROCESS_EVIDENCE_UI_SOURCE_BASELINE_GATE",
    "PROCESS_EVIDENCE_MODEL_MISS_REVIEW",
    "PROCESS_EVIDENCE_NOT_RUN",
    "PROCESS_EVIDENCE_PASSED",
    "PROCESS_EVIDENCE_RUNNING",
    "PROCESS_EVIDENCE_SKIPPED",
    "PROCESS_EVIDENCE_TIMEOUT",
    "PROCESS_EVIDENCE_UI_DONE_CLAIM_REVIEW",
    "PROCESS_EVIDENCE_UI_ACTION_GRAMMAR",
    "PROCESS_EVIDENCE_UI_AFFORDANCE_REVIEW",
    "PROCESS_EVIDENCE_UI_DIALOG_RETURN",
    "PROCESS_EVIDENCE_UI_FUNCTIONAL_CAPABILITY_COVERAGE",
    "PROCESS_EVIDENCE_UI_FUNCTIONAL_CHAIN",
    "PROCESS_EVIDENCE_UI_HUMAN_OPERABILITY",
    "PROCESS_EVIDENCE_UI_HUMAN_WALKTHROUGH",
    "PROCESS_EVIDENCE_UI_IMPLEMENTATION_VALIDATION",
    "PROCESS_EVIDENCE_UI_KEYBOARD_FOCUS",
    "PROCESS_EVIDENCE_UI_OBSERVED_INVENTORY",
    "PROCESS_EVIDENCE_UI_TASK_COVERAGE",
    "PROCESS_SCOPE_RELEASE",
    "PROCESS_SCOPE_ROUTINE",
    "ActionEffect",
    "DevelopmentProcessFlowReport",
    "DevelopmentProcessPlan",
    "FreshnessRule",
    "ProcessAction",
    "ProcessArtifact",
    "ProcessEvidence",
    "ProcessFlowFinding",
    "RevalidationRecommendation",
    "ValidationRequirement",
    "derive_revalidation_plan",
    "review_development_process_flow",
]
