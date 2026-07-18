"""Test hierarchy and evidence mesh governance helpers.

TestMesh reviews whether a parent test gate can trust child suites or child
test scripts as owned validation regions. It does not run pytest, unittest,
Playwright, or shell commands. Project adapters run tests and pass structured
evidence here for hierarchy coverage, ownership, freshness, background
completion, and routine/release gate review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .hierarchy import (
    EVIDENCE_ABSTRACT_GREEN,
    EVIDENCE_CANDIDATE_ONLY,
    EVIDENCE_CONFORMANCE_GREEN,
    EVIDENCE_HAZARD_GREEN,
    EVIDENCE_LIVE_CURRENT_GREEN,
    EVIDENCE_MESH_GREEN,
    OWNERSHIP_CHILD,
    OWNERSHIP_PARENT,
    OWNERSHIP_READ_ONLY,
    OWNERSHIP_SHARED_KERNEL,
)
from .proof_artifact import ProofArtifactRef, coerce_proof_artifact_ref, proof_artifact_gap_codes
from .test_reuse import (
    TestResultReuseTicket,
    coerce_test_result_reuse_ticket,
    test_result_reuse_gap_codes,
)


TEST_STATUS_PASSED = "passed"
TEST_STATUS_FAILED = "failed"
TEST_STATUS_TIMEOUT = "timeout"
TEST_STATUS_SKIPPED = "skipped"
TEST_STATUS_NOT_RUN = "not_run"
TEST_STATUS_RUNNING = "running"
TEST_STATUS_ERROR = "error"

TEST_LAYER_CHILD = "child"
TEST_LAYER_PARENT = "parent"
TEST_LAYER_RELEASE = "release"
TEST_LAYER_PARENT_COVERAGE = "parent_coverage"
TEST_LAYER_CHILD_DISJOINTNESS = "child_disjointness"
TEST_LAYER_CHILD_REATTACHMENT = "child_reattachment"
TEST_LAYER_CODE_BOUNDARY_CONFORMANCE = "code_boundary_conformance"
TEST_LAYER_LEAF_BOUNDARY_MATRIX = "leaf_boundary_matrix"
TEST_LAYER_LEAF_MATRIX_CELL = "leaf_matrix_cell"
TEST_LAYER_CONTRACT_COMBINATION_SHARD = "contract_combination_shard"
LEAF_MATRIX_LAYERS = {
    TEST_LAYER_LEAF_BOUNDARY_MATRIX,
    TEST_LAYER_LEAF_MATRIX_CELL,
    TEST_LAYER_CONTRACT_COMBINATION_SHARD,
}

TEST_EVIDENCE_ORDER = {
    EVIDENCE_CANDIDATE_ONLY: 0,
    EVIDENCE_ABSTRACT_GREEN: 1,
    EVIDENCE_HAZARD_GREEN: 2,
    EVIDENCE_LIVE_CURRENT_GREEN: 3,
    EVIDENCE_CONFORMANCE_GREEN: 4,
    EVIDENCE_MESH_GREEN: 5,
}

TEST_SCOPE_ROUTINE = "routine"
TEST_SCOPE_RELEASE = "release"

_DIAGNOSTIC_BOUNDARIES = {"targeted", "declared_complete", "budgeted"}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


@dataclass(frozen=True)
class TestPartitionItem:
    """One parent test partition owned by a child suite/script or parent gate."""

    __test__ = False

    item_id: str
    item_type: str = "behavior"
    owner_suite_id: str = ""
    ownership: str = OWNERSHIP_CHILD
    description: str = ""
    touched_paths: tuple[str, ...] = ()
    inventory_revision: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "item_type", str(self.item_type))
        object.__setattr__(self, "owner_suite_id", str(self.owner_suite_id))
        object.__setattr__(self, "ownership", str(self.ownership))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "touched_paths", _as_tuple(self.touched_paths))
        object.__setattr__(self, "inventory_revision", str(self.inventory_revision))

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type,
            "owner_suite_id": self.owner_suite_id,
            "ownership": self.ownership,
            "description": self.description,
            "touched_paths": list(self.touched_paths),
            "inventory_revision": self.inventory_revision,
        }


@dataclass(frozen=True)
class TestSuiteEvidence:
    """Evidence summary for one child suite/script, parent, or release-only test."""

    __test__ = False

    suite_id: str
    command: str = ""
    layer: str = TEST_LAYER_CHILD
    result_status: str = TEST_STATUS_NOT_RUN
    evidence_tier: str = EVIDENCE_CANDIDATE_ONLY
    evidence_current: bool = True
    test_count: int = 0
    selected_count: int = 0
    skipped_count: int = 0
    planned_count: int = 0
    executed_count: int = 0
    failed_count: int = 0
    not_run_count: int = 0
    diagnostic_campaign_id: str = ""
    diagnostic_boundary: str = ""
    finding_ids: tuple[str, ...] = ()
    skipped_visible: bool = True
    timeout_seconds: float | None = None
    duration_seconds: float | None = None
    exit_code: int | None = None
    result_path: str = ""
    log_root: str = ""
    background: bool = False
    has_exit_artifact: bool = True
    has_result_artifact: bool = True
    progress_only: bool = False
    proof_artifact: ProofArtifactRef | Mapping[str, Any] | None = None
    result_reused: bool = False
    reuse_ticket: TestResultReuseTicket | Mapping[str, Any] | None = None
    release_required: bool = False
    owns_state: tuple[str, ...] = ()
    owns_side_effects: tuple[str, ...] = ()
    owned_leaf_cell_ids: tuple[str, ...] = ()
    owned_coverage_shard_ids: tuple[str, ...] = ()
    not_run_reason: str = ""
    stale_reasons: tuple[str, ...] = ()
    inventory_revision: str = ""
    owned_inventory_item_ids: tuple[str, ...] = ()
    run_id: str = ""
    terminal_status: str = ""
    result_fingerprint: str = ""
    covered_obligation_ids: tuple[str, ...] = ()
    artifact_version: str = ""
    verifier_version: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "suite_id", str(self.suite_id))
        object.__setattr__(self, "command", str(self.command))
        object.__setattr__(self, "layer", str(self.layer))
        object.__setattr__(self, "result_status", str(self.result_status))
        object.__setattr__(self, "evidence_tier", str(self.evidence_tier))
        object.__setattr__(self, "test_count", int(self.test_count))
        object.__setattr__(self, "selected_count", int(self.selected_count))
        object.__setattr__(self, "skipped_count", int(self.skipped_count))
        object.__setattr__(self, "planned_count", int(self.planned_count))
        object.__setattr__(self, "executed_count", int(self.executed_count))
        object.__setattr__(self, "failed_count", int(self.failed_count))
        object.__setattr__(self, "not_run_count", int(self.not_run_count))
        object.__setattr__(self, "diagnostic_campaign_id", str(self.diagnostic_campaign_id))
        object.__setattr__(self, "diagnostic_boundary", str(self.diagnostic_boundary))
        object.__setattr__(self, "finding_ids", _as_tuple(self.finding_ids))
        object.__setattr__(self, "result_path", str(self.result_path))
        object.__setattr__(self, "log_root", str(self.log_root))
        object.__setattr__(self, "proof_artifact", coerce_proof_artifact_ref(self.proof_artifact))
        object.__setattr__(self, "result_reused", bool(self.result_reused))
        object.__setattr__(self, "reuse_ticket", coerce_test_result_reuse_ticket(self.reuse_ticket))
        object.__setattr__(self, "owns_state", _as_tuple(self.owns_state))
        object.__setattr__(self, "owns_side_effects", _as_tuple(self.owns_side_effects))
        object.__setattr__(self, "owned_leaf_cell_ids", _as_tuple(self.owned_leaf_cell_ids))
        object.__setattr__(self, "owned_coverage_shard_ids", _as_tuple(self.owned_coverage_shard_ids))
        object.__setattr__(self, "not_run_reason", str(self.not_run_reason))
        object.__setattr__(self, "stale_reasons", _as_tuple(self.stale_reasons))
        object.__setattr__(self, "inventory_revision", str(self.inventory_revision))
        object.__setattr__(self, "owned_inventory_item_ids", _as_tuple(self.owned_inventory_item_ids))
        object.__setattr__(self, "run_id", str(self.run_id))
        object.__setattr__(self, "terminal_status", str(self.terminal_status))
        object.__setattr__(self, "result_fingerprint", str(self.result_fingerprint))
        object.__setattr__(self, "covered_obligation_ids", _as_tuple(self.covered_obligation_ids))
        object.__setattr__(self, "artifact_version", str(self.artifact_version))
        object.__setattr__(self, "verifier_version", str(self.verifier_version))

    def is_release_only(self) -> bool:
        return self.release_required or self.layer == TEST_LAYER_RELEASE

    def has_current_pass(self) -> bool:
        return (
            self.result_status == TEST_STATUS_PASSED
            and self.evidence_current
            and not self.progress_only
        )

    def final_receipt_gap_codes(self, required_obligation_ids: Sequence[str] = ()) -> tuple[str, ...]:
        gaps: list[str] = []
        if not self.run_id:
            gaps.append("final_receipt_run_id_missing")
        if self.terminal_status != TEST_STATUS_PASSED:
            gaps.append("final_receipt_terminal_status_missing")
        if self.exit_code != 0 or not self.has_exit_artifact:
            gaps.append("final_receipt_exit_code_missing")
        if not self.result_path or not self.has_result_artifact:
            gaps.append("final_receipt_result_artifact_missing")
        if not self.result_fingerprint:
            gaps.append("final_receipt_result_fingerprint_missing")
        if not self.artifact_version:
            gaps.append("final_receipt_artifact_version_missing")
        if not self.verifier_version:
            gaps.append("final_receipt_verifier_version_missing")
        missing_coverage = set(required_obligation_ids) - set(self.covered_obligation_ids)
        if missing_coverage:
            gaps.append("final_receipt_coverage_incomplete")
        if self.progress_only or self.result_status == TEST_STATUS_RUNNING:
            gaps.append("final_receipt_progress_only")
        return tuple(dict.fromkeys(gaps))

    def background_complete(self) -> bool:
        if not self.background:
            return True
        return not self.final_receipt_gap_codes(
            self.owned_inventory_item_ids
            or self.owned_leaf_cell_ids
            or self.owned_coverage_shard_ids
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "command": self.command,
            "layer": self.layer,
            "result_status": self.result_status,
            "evidence_tier": self.evidence_tier,
            "evidence_current": self.evidence_current,
            "test_count": self.test_count,
            "selected_count": self.selected_count,
            "skipped_count": self.skipped_count,
            "planned_count": self.planned_count,
            "executed_count": self.executed_count,
            "failed_count": self.failed_count,
            "not_run_count": self.not_run_count,
            "diagnostic_campaign_id": self.diagnostic_campaign_id,
            "diagnostic_boundary": self.diagnostic_boundary,
            "finding_ids": list(self.finding_ids),
            "skipped_visible": self.skipped_visible,
            "timeout_seconds": self.timeout_seconds,
            "duration_seconds": self.duration_seconds,
            "exit_code": self.exit_code,
            "result_path": self.result_path,
            "log_root": self.log_root,
            "background": self.background,
            "has_exit_artifact": self.has_exit_artifact,
            "has_result_artifact": self.has_result_artifact,
            "progress_only": self.progress_only,
            "proof_artifact": self.proof_artifact.to_dict() if self.proof_artifact else None,
            "result_reused": self.result_reused,
            "reuse_ticket": self.reuse_ticket.to_dict() if self.reuse_ticket else None,
            "release_required": self.release_required,
            "owns_state": list(self.owns_state),
            "owns_side_effects": list(self.owns_side_effects),
            "owned_leaf_cell_ids": list(self.owned_leaf_cell_ids),
            "owned_coverage_shard_ids": list(self.owned_coverage_shard_ids),
            "not_run_reason": self.not_run_reason,
            "stale_reasons": list(self.stale_reasons),
            "inventory_revision": self.inventory_revision,
            "owned_inventory_item_ids": list(self.owned_inventory_item_ids),
            "run_id": self.run_id,
            "terminal_status": self.terminal_status,
            "result_fingerprint": self.result_fingerprint,
            "covered_obligation_ids": list(self.covered_obligation_ids),
            "artifact_version": self.artifact_version,
            "verifier_version": self.verifier_version,
        }


@dataclass(frozen=True)
class TestTargetSplitDerivation:
    """Model-derived target child-suite layout for one parent TestMesh gate."""

    __test__ = False

    source_model_id: str
    target_suite_ids: tuple[str, ...] = ()
    covered_partition_item_ids: tuple[str, ...] = ()
    state_owner_fields: tuple[str, ...] = ()
    side_effect_owner_fields: tuple[str, ...] = ()
    source_model_path: str = ""
    rationale: str = ""
    derived_from_flowguard_model: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_model_id", str(self.source_model_id))
        object.__setattr__(self, "target_suite_ids", _as_tuple(self.target_suite_ids))
        object.__setattr__(self, "covered_partition_item_ids", _as_tuple(self.covered_partition_item_ids))
        object.__setattr__(self, "state_owner_fields", _as_tuple(self.state_owner_fields))
        object.__setattr__(self, "side_effect_owner_fields", _as_tuple(self.side_effect_owner_fields))
        object.__setattr__(self, "source_model_path", str(self.source_model_path))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_model_id": self.source_model_id,
            "target_suite_ids": list(self.target_suite_ids),
            "covered_partition_item_ids": list(self.covered_partition_item_ids),
            "state_owner_fields": list(self.state_owner_fields),
            "side_effect_owner_fields": list(self.side_effect_owner_fields),
            "source_model_path": self.source_model_path,
            "rationale": self.rationale,
            "derived_from_flowguard_model": self.derived_from_flowguard_model,
        }


@dataclass(frozen=True)
class TestMeshPlan:
    """A parent test boundary and the child evidence used for a decision."""

    __test__ = False

    parent_suite_id: str
    partition_items: tuple[TestPartitionItem, ...] = ()
    child_suites: tuple[TestSuiteEvidence, ...] = ()
    target_split_derivation: TestTargetSplitDerivation | None = None
    required_leaf_cell_ids: tuple[str, ...] = ()
    required_coverage_shard_ids: tuple[str, ...] = ()
    required_evidence_tier: str = EVIDENCE_ABSTRACT_GREEN
    require_proof_artifacts: bool = False
    decision_scope: str = TEST_SCOPE_ROUTINE
    release_deferred_allowed: bool = True
    allowed_shared_state: tuple[str, ...] = ()
    allowed_shared_side_effects: tuple[str, ...] = ()
    inventory_revision: str = ""
    required_inventory_item_ids: tuple[str, ...] = ()
    scoped_inventory_item_reasons: Mapping[str, str] = field(default_factory=dict)
    require_complete_inventory: bool = False
    require_final_receipts: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "parent_suite_id", str(self.parent_suite_id))
        object.__setattr__(self, "partition_items", tuple(self.partition_items))
        object.__setattr__(self, "child_suites", tuple(self.child_suites))
        object.__setattr__(self, "required_leaf_cell_ids", _as_tuple(self.required_leaf_cell_ids))
        object.__setattr__(self, "required_coverage_shard_ids", _as_tuple(self.required_coverage_shard_ids))
        object.__setattr__(self, "required_evidence_tier", str(self.required_evidence_tier))
        object.__setattr__(self, "require_proof_artifacts", bool(self.require_proof_artifacts))
        object.__setattr__(self, "decision_scope", str(self.decision_scope))
        object.__setattr__(self, "allowed_shared_state", _as_tuple(self.allowed_shared_state))
        object.__setattr__(self, "allowed_shared_side_effects", _as_tuple(self.allowed_shared_side_effects))
        object.__setattr__(self, "inventory_revision", str(self.inventory_revision))
        object.__setattr__(self, "required_inventory_item_ids", _as_tuple(self.required_inventory_item_ids))
        object.__setattr__(
            self,
            "scoped_inventory_item_reasons",
            {str(key): str(value) for key, value in dict(self.scoped_inventory_item_reasons).items()},
        )
        object.__setattr__(self, "require_complete_inventory", bool(self.require_complete_inventory))
        object.__setattr__(self, "require_final_receipts", bool(self.require_final_receipts))

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_suite_id": self.parent_suite_id,
            "partition_items": [item.to_dict() for item in self.partition_items],
            "child_suites": [suite.to_dict() for suite in self.child_suites],
            "target_split_derivation": (
                self.target_split_derivation.to_dict()
                if self.target_split_derivation is not None
                else None
            ),
            "required_leaf_cell_ids": list(self.required_leaf_cell_ids),
            "required_coverage_shard_ids": list(self.required_coverage_shard_ids),
            "required_evidence_tier": self.required_evidence_tier,
            "require_proof_artifacts": self.require_proof_artifacts,
            "decision_scope": self.decision_scope,
            "release_deferred_allowed": self.release_deferred_allowed,
            "allowed_shared_state": list(self.allowed_shared_state),
            "allowed_shared_side_effects": list(self.allowed_shared_side_effects),
            "inventory_revision": self.inventory_revision,
            "required_inventory_item_ids": list(self.required_inventory_item_ids),
            "scoped_inventory_item_reasons": to_jsonable(dict(self.scoped_inventory_item_reasons)),
            "require_complete_inventory": self.require_complete_inventory,
            "require_final_receipts": self.require_final_receipts,
        }


@dataclass(frozen=True)
class TestMeshFinding:
    """One coverage, evidence, background, or ownership finding."""

    code: str
    message: str
    severity: str = "blocker"
    suite_id: str = ""
    item_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "suite_id", str(self.suite_id))
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "suite_id": self.suite_id,
            "item_id": self.item_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class TestMeshReport:
    """Structured outcome of a TestMesh review."""

    ok: bool
    parent_suite_id: str
    decision: str
    decision_scope: str
    findings: tuple[TestMeshFinding, ...] = ()
    release_obligations: tuple[str, ...] = ()
    summary: str = ""
    inventory_revision: str = ""
    covered_inventory_item_ids: tuple[str, ...] = ()
    scoped_inventory_item_ids: tuple[str, ...] = ()
    missing_inventory_item_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "parent_suite_id", str(self.parent_suite_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "decision_scope", str(self.decision_scope))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "release_obligations", _as_tuple(self.release_obligations))
        object.__setattr__(self, "inventory_revision", str(self.inventory_revision))
        object.__setattr__(
            self,
            "covered_inventory_item_ids",
            _as_tuple(self.covered_inventory_item_ids),
        )
        object.__setattr__(
            self,
            "scoped_inventory_item_ids",
            _as_tuple(self.scoped_inventory_item_ids),
        )
        object.__setattr__(
            self,
            "missing_inventory_item_ids",
            _as_tuple(self.missing_inventory_item_ids),
        )
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: parent={self.parent_suite_id} scope={self.decision_scope} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard test mesh review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"parent: {self.parent_suite_id}",
            f"scope: {self.decision_scope}",
            f"decision: {self.decision}",
            f"findings: {len(self.findings)}",
        ]
        if self.release_obligations:
            lines.append("release_obligations:")
            for suite_id in self.release_obligations:
                lines.append(f"  - {suite_id}")
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"suite: {finding.suite_id or '(none)'}",
                    f"item: {finding.item_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "parent_suite_id": self.parent_suite_id,
            "decision": self.decision,
            "decision_scope": self.decision_scope,
            "findings": [finding.to_dict() for finding in self.findings],
            "release_obligations": list(self.release_obligations),
            "inventory_revision": self.inventory_revision,
            "covered_inventory_item_ids": list(self.covered_inventory_item_ids),
            "scoped_inventory_item_ids": list(self.scoped_inventory_item_ids),
            "missing_inventory_item_ids": list(self.missing_inventory_item_ids),
            "summary": self.summary,
        }


def _tier_value(tier: str) -> int:
    return TEST_EVIDENCE_ORDER.get(tier, -1)


def _blocker_findings(findings: Sequence[TestMeshFinding]) -> tuple[TestMeshFinding, ...]:
    return tuple(finding for finding in findings if finding.severity == "blocker")


def _decision_for_findings(findings: Sequence[TestMeshFinding]) -> str:
    blockers = _blocker_findings(findings)
    if not blockers:
        return "test_mesh_green_can_continue"
    priority = [
        ("test_inventory_revision_missing", "test_inventory_required"),
        ("test_inventory_required_items_missing", "test_inventory_required"),
        ("required_inventory_item_missing", "test_inventory_required"),
        ("required_inventory_item_owner_missing", "test_inventory_required"),
        ("test_inventory_revision_mismatch", "test_inventory_required"),
        ("final_receipt_run_id_missing", "final_receipt_required"),
        ("final_receipt_terminal_status_missing", "final_receipt_required"),
        ("final_receipt_exit_code_missing", "final_receipt_required"),
        ("final_receipt_result_artifact_missing", "final_receipt_required"),
        ("final_receipt_result_fingerprint_missing", "final_receipt_required"),
        ("final_receipt_coverage_incomplete", "final_receipt_required"),
        ("final_receipt_artifact_version_missing", "final_receipt_required"),
        ("final_receipt_verifier_version_missing", "final_receipt_required"),
        ("final_receipt_progress_only", "final_receipt_required"),
        ("suite_progress_only", "final_receipt_required"),
        ("missing_target_split_derivation", "target_split_derivation_required"),
        ("invalid_target_split_derivation", "target_split_derivation_required"),
        ("missing_target_suites", "target_split_derivation_required"),
        ("unknown_target_suite", "target_split_derivation_required"),
        ("incomplete_target_suites", "target_split_derivation_required"),
        ("incomplete_target_split_coverage", "target_split_derivation_required"),
        ("missing_target_state_owner_map", "target_split_derivation_required"),
        ("missing_target_side_effect_owner_map", "target_split_derivation_required"),
        ("missing_target_split_rationale", "target_split_derivation_required"),
        ("leaf_matrix_cell_owner_missing", "leaf_matrix_cell_evidence_required"),
        ("leaf_matrix_cell_evidence_missing", "leaf_matrix_cell_evidence_required"),
        ("contract_coverage_shard_owner_missing", "contract_coverage_shard_evidence_required"),
        ("contract_coverage_shard_evidence_missing", "contract_coverage_shard_evidence_required"),
        ("coverage_gap", "coverage_gap_blocked"),
        ("duplicate_partition_owner", "ownership_conflict"),
        ("duplicate_state_owner", "ownership_conflict"),
        ("duplicate_side_effect_owner", "ownership_conflict"),
        ("background_incomplete", "background_incomplete"),
        ("suite_failed", "test_failure_blocked"),
        ("suite_timeout", "test_timeout_blocked"),
        ("hidden_skipped_tests", "hidden_skipped_tests"),
        ("stale_test_evidence", "stale_test_evidence"),
        ("missing_test_reuse_ticket", "test_reuse_proof_required"),
        ("test_reuse_ticket_not_current", "test_reuse_proof_required"),
        ("test_reuse_missing_proof_artifact", "test_reuse_proof_required"),
        ("test_reuse_stale_proof_artifact", "test_reuse_proof_required"),
        ("test_reuse_progress_only_proof_artifact", "test_reuse_proof_required"),
        ("suite_missing_proof_artifact", "test_proof_artifact_required"),
        ("insufficient_evidence_tier", "insufficient_evidence"),
        ("release_suite_not_current", "missing_release_evidence"),
    ]
    codes = {finding.code for finding in blockers}
    for code, decision in priority:
        if code in codes:
            return decision
    return "test_mesh_blocked"


def _target_split_derivation_findings(plan: TestMeshPlan) -> list[TestMeshFinding]:
    findings: list[TestMeshFinding] = []
    if not plan.partition_items and not plan.child_suites:
        return findings

    derivation = plan.target_split_derivation
    if derivation is None:
        return [
            TestMeshFinding(
                "missing_target_split_derivation",
                "parent test gate lacks FlowGuard-derived target split structure",
                suite_id=plan.parent_suite_id,
            )
        ]

    if not derivation.derived_from_flowguard_model or not derivation.source_model_id:
        findings.append(
            TestMeshFinding(
                "invalid_target_split_derivation",
                "target test split derivation must name the FlowGuard source model",
                suite_id=plan.parent_suite_id,
                metadata=derivation.to_dict(),
            )
        )

    suite_ids = {suite.suite_id for suite in plan.child_suites}
    target_ids = set(derivation.target_suite_ids)
    if not target_ids:
        findings.append(
            TestMeshFinding(
                "missing_target_suites",
                "target test split derivation has no target child suites",
                suite_id=plan.parent_suite_id,
                metadata=derivation.to_dict(),
            )
        )
    else:
        unknown_targets = tuple(sorted(target_ids - suite_ids))
        if unknown_targets:
            findings.append(
                TestMeshFinding(
                    "unknown_target_suite",
                    "target test split derivation names unregistered child suites",
                    suite_id=plan.parent_suite_id,
                    metadata={"unknown_targets": unknown_targets, "derivation": derivation.to_dict()},
                )
            )
        missing_targets = tuple(sorted(suite_ids - target_ids))
        if missing_targets:
            findings.append(
                TestMeshFinding(
                    "incomplete_target_suites",
                    "target test split derivation omits registered child suites",
                    suite_id=plan.parent_suite_id,
                    metadata={"missing_targets": missing_targets, "derivation": derivation.to_dict()},
                )
            )

    partition_ids = {item.item_id for item in plan.partition_items}
    covered_ids = set(derivation.covered_partition_item_ids)
    missing_coverage = tuple(sorted(partition_ids - covered_ids))
    if missing_coverage:
        findings.append(
            TestMeshFinding(
                "incomplete_target_split_coverage",
                "target test split derivation does not cover all parent partition items",
                suite_id=plan.parent_suite_id,
                metadata={"missing_coverage": missing_coverage, "derivation": derivation.to_dict()},
            )
        )

    if not derivation.state_owner_fields and any(suite.owns_state for suite in plan.child_suites):
        findings.append(
            TestMeshFinding(
                "missing_target_state_owner_map",
                "target test split derivation omits state owner fields",
                suite_id=plan.parent_suite_id,
                metadata=derivation.to_dict(),
            )
        )
    if not derivation.side_effect_owner_fields and any(suite.owns_side_effects for suite in plan.child_suites):
        findings.append(
            TestMeshFinding(
                "missing_target_side_effect_owner_map",
                "target test split derivation omits side-effect owner fields",
                suite_id=plan.parent_suite_id,
                metadata=derivation.to_dict(),
            )
        )
    if not derivation.rationale:
        findings.append(
            TestMeshFinding(
                "missing_target_split_rationale",
                "target test split derivation lacks rationale",
                suite_id=plan.parent_suite_id,
                metadata=derivation.to_dict(),
            )
        )
    return findings


def _partition_findings(plan: TestMeshPlan) -> list[TestMeshFinding]:
    findings: list[TestMeshFinding] = []
    suite_ids = {suite.suite_id for suite in plan.child_suites}
    owners_by_item: dict[str, list[TestPartitionItem]] = {}
    for item in plan.partition_items:
        if item.ownership not in {
            OWNERSHIP_CHILD,
            OWNERSHIP_PARENT,
            OWNERSHIP_READ_ONLY,
            OWNERSHIP_SHARED_KERNEL,
        }:
            findings.append(
                TestMeshFinding(
                    "invalid_partition_ownership",
                    f"partition item {item.item_id} has invalid ownership {item.ownership!r}",
                    item_id=item.item_id,
                    metadata=item.to_dict(),
                )
            )
        if item.ownership == OWNERSHIP_CHILD:
            if not item.owner_suite_id:
                findings.append(
                    TestMeshFinding(
                        "coverage_gap",
                        f"partition item {item.item_id} has no owning child suite",
                        item_id=item.item_id,
                        metadata=item.to_dict(),
                    )
                )
            elif item.owner_suite_id not in suite_ids:
                findings.append(
                    TestMeshFinding(
                        "coverage_gap",
                        f"partition item {item.item_id} owner {item.owner_suite_id} is not registered",
                        suite_id=item.owner_suite_id,
                        item_id=item.item_id,
                        metadata=item.to_dict(),
                    )
                )
        if item.ownership in {OWNERSHIP_CHILD, OWNERSHIP_PARENT, OWNERSHIP_SHARED_KERNEL}:
            owners_by_item.setdefault(item.item_id, []).append(item)

    for item_id, owners in owners_by_item.items():
        owner_keys = {(owner.owner_suite_id, owner.ownership) for owner in owners}
        if len(owner_keys) > 1:
            findings.append(
                TestMeshFinding(
                    "duplicate_partition_owner",
                    f"partition item {item_id} has multiple owning suites",
                    item_id=item_id,
                    metadata={"owners": [owner.to_dict() for owner in owners]},
                )
            )
    return findings


def _inventory_findings(
    plan: TestMeshPlan,
) -> tuple[list[TestMeshFinding], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    findings: list[TestMeshFinding] = []
    required = set(plan.required_inventory_item_ids)
    scoped = set(plan.scoped_inventory_item_reasons)
    inventory_claimed = bool(plan.require_complete_inventory or required)
    if not inventory_claimed:
        return findings, (), (), ()
    if not plan.inventory_revision:
        findings.append(
            TestMeshFinding(
                "test_inventory_revision_missing",
                "complete required test inventory needs an explicit revision",
                suite_id=plan.parent_suite_id,
            )
        )
    if plan.require_complete_inventory and not required:
        findings.append(
            TestMeshFinding(
                "test_inventory_required_items_missing",
                "complete TestMesh inventory has no independently declared required item ids",
                suite_id=plan.parent_suite_id,
            )
        )
    for item_id, reason in plan.scoped_inventory_item_reasons.items():
        if not reason:
            findings.append(
                TestMeshFinding(
                    "test_inventory_scoped_reason_missing",
                    "scoped test inventory item requires a reason",
                    suite_id=plan.parent_suite_id,
                    item_id=item_id,
                )
            )

    partitions_by_id: dict[str, list[TestPartitionItem]] = {}
    for item in plan.partition_items:
        partitions_by_id.setdefault(item.item_id, []).append(item)
        if plan.inventory_revision and item.inventory_revision != plan.inventory_revision:
            findings.append(
                TestMeshFinding(
                    "test_inventory_revision_mismatch",
                    "test partition item revision does not match the required inventory revision",
                    suite_id=plan.parent_suite_id,
                    item_id=item.item_id,
                    metadata={"expected": plan.inventory_revision, "actual": item.inventory_revision},
                )
            )
    suites_by_id = {suite.suite_id: suite for suite in plan.child_suites}
    inventory_owners: dict[str, list[TestSuiteEvidence]] = {}
    for suite in plan.child_suites:
        if plan.inventory_revision and suite.inventory_revision != plan.inventory_revision:
            findings.append(
                TestMeshFinding(
                    "test_inventory_revision_mismatch",
                    "test suite evidence revision does not match the required inventory revision",
                    suite_id=suite.suite_id,
                    metadata={"expected": plan.inventory_revision, "actual": suite.inventory_revision},
                )
            )
        for item_id in suite.owned_inventory_item_ids:
            inventory_owners.setdefault(item_id, []).append(suite)

    covered: list[str] = []
    missing: list[str] = []
    for item_id in sorted(required):
        if item_id in scoped:
            continue
        partitions = partitions_by_id.get(item_id, ())
        if not partitions:
            missing.append(item_id)
            findings.append(
                TestMeshFinding(
                    "required_inventory_item_missing",
                    "required test inventory item is absent from the parent partition",
                    suite_id=plan.parent_suite_id,
                    item_id=item_id,
                )
            )
            continue
        owners = tuple(inventory_owners.get(item_id, ()))
        declared_owner_ids = {
            partition.owner_suite_id
            for partition in partitions
            if partition.owner_suite_id
        }
        valid_owners = tuple(
            suite
            for suite in owners
            if suite.suite_id in declared_owner_ids
            and suite.has_current_pass()
            and not suite.final_receipt_gap_codes((item_id,))
        )
        if not valid_owners:
            missing.append(item_id)
            findings.append(
                TestMeshFinding(
                    "required_inventory_item_owner_missing",
                    "required test inventory item lacks current owned final-receipt evidence",
                    suite_id=next(iter(declared_owner_ids), ""),
                    item_id=item_id,
                    metadata={
                        "declared_owner_ids": sorted(declared_owner_ids),
                        "inventory_owners": [suite.to_dict() for suite in owners],
                    },
                )
            )
        else:
            covered.append(item_id)
    if plan.require_complete_inventory:
        for item_id in sorted(set(partitions_by_id) - required - scoped):
            findings.append(
                TestMeshFinding(
                    "unexpected_test_inventory_item",
                    "partition item is outside the complete required inventory",
                    suite_id=plan.parent_suite_id,
                    item_id=item_id,
                )
            )
    return (
        findings,
        tuple(dict.fromkeys(covered)),
        tuple(sorted(required & scoped)),
        tuple(dict.fromkeys(missing)),
    )


def _duplicate_value_findings(
    suites: Sequence[TestSuiteEvidence],
    *,
    attr_name: str,
    allowed: Sequence[str],
    code: str,
    noun: str,
) -> list[TestMeshFinding]:
    findings: list[TestMeshFinding] = []
    owners: dict[str, list[str]] = {}
    allowed_set = set(allowed)
    for suite in suites:
        for value in getattr(suite, attr_name):
            if value in allowed_set:
                continue
            owners.setdefault(value, []).append(suite.suite_id)
    for value, suite_ids in sorted(owners.items()):
        if len(set(suite_ids)) > 1:
            findings.append(
                TestMeshFinding(
                    code,
                    f"{noun} {value} is owned by multiple suites",
                    metadata={noun: value, "suites": sorted(set(suite_ids))},
                )
            )
    return findings


def _suite_evidence_findings(plan: TestMeshPlan) -> tuple[list[TestMeshFinding], list[str]]:
    findings: list[TestMeshFinding] = []
    release_obligations: list[str] = []
    required_tier = _tier_value(plan.required_evidence_tier)
    for suite in plan.child_suites:
        campaign_active = bool(
            suite.planned_count
            or suite.executed_count
            or suite.failed_count
            or suite.not_run_count
            or suite.diagnostic_campaign_id
            or suite.diagnostic_boundary
            or suite.finding_ids
        )
        if campaign_active:
            if not suite.diagnostic_campaign_id:
                findings.append(
                    TestMeshFinding(
                        "diagnostic_campaign_id_missing",
                        f"suite {suite.suite_id} has diagnostic accounting without a stable campaign id",
                        suite_id=suite.suite_id,
                        metadata=suite.to_dict(),
                    )
                )
            if suite.diagnostic_boundary not in _DIAGNOSTIC_BOUNDARIES:
                findings.append(
                    TestMeshFinding(
                        "diagnostic_boundary_invalid",
                        f"suite {suite.suite_id} lacks a recognized diagnostic boundary",
                        suite_id=suite.suite_id,
                        metadata=suite.to_dict(),
                    )
                )
            counts = (
                suite.planned_count,
                suite.executed_count,
                suite.failed_count,
                suite.not_run_count,
            )
            if any(value < 0 for value in counts):
                findings.append(
                    TestMeshFinding(
                        "diagnostic_campaign_count_negative",
                        f"suite {suite.suite_id} has a negative diagnostic count",
                        suite_id=suite.suite_id,
                        metadata=suite.to_dict(),
                    )
                )
            if suite.planned_count != suite.executed_count + suite.not_run_count:
                findings.append(
                    TestMeshFinding(
                        "diagnostic_campaign_count_inconsistent",
                        f"suite {suite.suite_id} does not account every planned diagnostic as executed or not run",
                        suite_id=suite.suite_id,
                        metadata=suite.to_dict(),
                    )
                )
            if suite.failed_count > suite.executed_count:
                findings.append(
                    TestMeshFinding(
                        "diagnostic_failed_count_exceeds_executed",
                        f"suite {suite.suite_id} reports more failures than executed diagnostics",
                        suite_id=suite.suite_id,
                        metadata=suite.to_dict(),
                    )
                )
            if suite.not_run_count and not suite.not_run_reason:
                findings.append(
                    TestMeshFinding(
                        "diagnostic_not_run_reason_missing",
                        f"suite {suite.suite_id} hides why planned diagnostics were not run",
                        suite_id=suite.suite_id,
                        metadata=suite.to_dict(),
                    )
                )
            if suite.diagnostic_boundary == "declared_complete" and suite.not_run_count:
                findings.append(
                    TestMeshFinding(
                        "diagnostic_false_completeness",
                        f"suite {suite.suite_id} claims declared completeness with not-run diagnostics",
                        suite_id=suite.suite_id,
                        metadata=suite.to_dict(),
                    )
                )
            if suite.failed_count and not suite.finding_ids:
                findings.append(
                    TestMeshFinding(
                        "diagnostic_finding_missing",
                        f"suite {suite.suite_id} failures are not linked to stable raw findings",
                        suite_id=suite.suite_id,
                        metadata=suite.to_dict(),
                    )
                )
        release_only = suite.is_release_only()
        deferred_release = (
            plan.decision_scope == TEST_SCOPE_ROUTINE
            and plan.release_deferred_allowed
            and release_only
            and not suite.has_current_pass()
        )
        if deferred_release:
            release_obligations.append(suite.suite_id)
            findings.append(
                TestMeshFinding(
                    "release_suite_deferred",
                    f"release-only suite {suite.suite_id} is deferred for routine confidence",
                    severity="warning",
                    suite_id=suite.suite_id,
                    metadata=suite.to_dict(),
                )
            )
            continue

        if suite.background and not suite.background_complete():
            findings.append(
                TestMeshFinding(
                    "background_incomplete",
                    f"background suite {suite.suite_id} lacks final exit/result evidence",
                    suite_id=suite.suite_id,
                    metadata=suite.to_dict(),
                )
            )
        if suite.progress_only:
            findings.append(
                TestMeshFinding(
                    "suite_progress_only",
                    f"suite {suite.suite_id} reports liveness/progress rather than terminal evidence",
                    suite_id=suite.suite_id,
                    metadata=suite.to_dict(),
                )
            )
        receipt_required_ids = (
            suite.owned_inventory_item_ids
            or suite.owned_leaf_cell_ids
            or suite.owned_coverage_shard_ids
            or tuple(
                item.item_id
                for item in plan.partition_items
                if item.owner_suite_id == suite.suite_id
            )
        )
        if plan.require_final_receipts or plan.required_inventory_item_ids or suite.background:
            for gap_code in suite.final_receipt_gap_codes(receipt_required_ids):
                findings.append(
                    TestMeshFinding(
                        gap_code,
                        f"suite {suite.suite_id} final receipt is incomplete",
                        suite_id=suite.suite_id,
                        metadata={
                            "required_obligation_ids": list(receipt_required_ids),
                            "suite": suite.to_dict(),
                        },
                    )
                )
        if suite.result_status == TEST_STATUS_FAILED or suite.exit_code not in (None, 0):
            findings.append(
                TestMeshFinding(
                    "suite_failed",
                    f"suite {suite.suite_id} did not pass",
                    suite_id=suite.suite_id,
                    metadata=suite.to_dict(),
                )
            )
        elif suite.result_status == TEST_STATUS_TIMEOUT:
            findings.append(
                TestMeshFinding(
                    "suite_timeout",
                    f"suite {suite.suite_id} timed out",
                    suite_id=suite.suite_id,
                    metadata=suite.to_dict(),
                )
            )
        elif suite.result_status in {TEST_STATUS_NOT_RUN, TEST_STATUS_RUNNING, TEST_STATUS_ERROR, TEST_STATUS_SKIPPED}:
            code = "release_suite_not_current" if plan.decision_scope == TEST_SCOPE_RELEASE and release_only else "suite_not_current"
            findings.append(
                TestMeshFinding(
                    code,
                    f"suite {suite.suite_id} status is {suite.result_status}",
                    suite_id=suite.suite_id,
                    metadata=suite.to_dict(),
                )
            )
        if not suite.evidence_current:
            findings.append(
                TestMeshFinding(
                    "stale_test_evidence",
                    f"suite {suite.suite_id} evidence is stale",
                    suite_id=suite.suite_id,
                    metadata=suite.to_dict(),
                )
            )
        if suite.result_reused or suite.reuse_ticket is not None:
            owned_obligation_ids = suite.owned_leaf_cell_ids + suite.owned_coverage_shard_ids
            for code, message in test_result_reuse_gap_codes(
                suite.reuse_ticket,
                expected_evidence_id=suite.suite_id,
                required_obligation_ids=owned_obligation_ids,
            ):
                findings.append(
                    TestMeshFinding(
                        code,
                        message,
                        suite_id=suite.suite_id,
                        metadata=suite.to_dict(),
                    )
                )
            for code, message in proof_artifact_gap_codes(
                suite.proof_artifact,
                declared_status=suite.result_status,
                required_obligation_ids=owned_obligation_ids,
                require_result_path=True,
                require_fingerprints=True,
            ):
                findings.append(
                    TestMeshFinding(
                        f"test_reuse_{code}",
                        message,
                        suite_id=suite.suite_id,
                        metadata=suite.to_dict(),
                    )
                )
        if plan.require_proof_artifacts:
            owned_obligation_ids = suite.owned_leaf_cell_ids + suite.owned_coverage_shard_ids
            for code, message in proof_artifact_gap_codes(
                suite.proof_artifact,
                declared_status=suite.result_status,
                required_obligation_ids=owned_obligation_ids,
                require_result_path=True,
                require_fingerprints=True,
            ):
                findings.append(
                    TestMeshFinding(
                        f"suite_{code}",
                        message,
                        suite_id=suite.suite_id,
                        metadata=suite.to_dict(),
                    )
                )
        if suite.skipped_count and not suite.skipped_visible:
            findings.append(
                TestMeshFinding(
                    "hidden_skipped_tests",
                    f"suite {suite.suite_id} hides skipped tests inside a green summary",
                    suite_id=suite.suite_id,
                    metadata=suite.to_dict(),
                )
            )
        if _tier_value(suite.evidence_tier) < required_tier:
            findings.append(
                TestMeshFinding(
                    "insufficient_evidence_tier",
                    f"suite {suite.suite_id} evidence tier {suite.evidence_tier} is below {plan.required_evidence_tier}",
                    suite_id=suite.suite_id,
                    metadata=suite.to_dict(),
                )
            )
    return findings, release_obligations


def _leaf_matrix_evidence_findings(plan: TestMeshPlan) -> list[TestMeshFinding]:
    findings: list[TestMeshFinding] = []
    cell_owners: dict[str, list[TestSuiteEvidence]] = {}
    shard_owners: dict[str, list[TestSuiteEvidence]] = {}
    for suite in plan.child_suites:
        if suite.layer == TEST_LAYER_CONTRACT_COMBINATION_SHARD and not suite.owned_coverage_shard_ids:
            findings.append(
                TestMeshFinding(
                    "contract_coverage_shard_owner_missing",
                    f"contract coverage shard evidence suite {suite.suite_id} does not name the shards it proves",
                    suite_id=suite.suite_id,
                    metadata=suite.to_dict(),
                )
            )
        elif (
            suite.layer in LEAF_MATRIX_LAYERS
            and suite.layer != TEST_LAYER_CONTRACT_COMBINATION_SHARD
            and not suite.owned_leaf_cell_ids
        ):
            findings.append(
                TestMeshFinding(
                    "leaf_matrix_cell_owner_missing",
                    f"leaf matrix evidence suite {suite.suite_id} does not name the cells it proves",
                    suite_id=suite.suite_id,
                    metadata=suite.to_dict(),
                )
            )
        for cell_id in suite.owned_leaf_cell_ids:
            cell_owners.setdefault(cell_id, []).append(suite)
        for shard_id in suite.owned_coverage_shard_ids:
            shard_owners.setdefault(shard_id, []).append(suite)

    for cell_id in plan.required_leaf_cell_ids:
        owners = tuple(cell_owners.get(cell_id, ()))
        current_owners = tuple(
            suite
            for suite in owners
            if suite.has_current_pass() and suite.background_complete()
        )
        if not current_owners:
            findings.append(
                TestMeshFinding(
                    "leaf_matrix_cell_evidence_missing",
                    "parent test gate lacks current passing evidence for a required leaf matrix cell",
                    item_id=cell_id,
                    metadata={
                        "required_leaf_cell_id": cell_id,
                        "owners": [suite.to_dict() for suite in owners],
                    },
                )
            )
    for shard_id in plan.required_coverage_shard_ids:
        owners = tuple(shard_owners.get(shard_id, ()))
        current_owners = tuple(
            suite
            for suite in owners
            if suite.has_current_pass() and suite.background_complete()
        )
        if not current_owners:
            findings.append(
                TestMeshFinding(
                    "contract_coverage_shard_evidence_missing",
                    "parent test gate lacks current passing evidence for a required contract coverage shard",
                    item_id=shard_id,
                    metadata={
                        "required_coverage_shard_id": shard_id,
                        "owners": [suite.to_dict() for suite in owners],
                    },
                )
            )
    return findings


def review_test_mesh(plan: TestMeshPlan) -> TestMeshReport:
    """Review a test hierarchy without running the tests."""

    findings = _partition_findings(plan)
    inventory_values = _inventory_findings(plan)
    findings.extend(inventory_values[0])
    findings.extend(_target_split_derivation_findings(plan))
    findings.extend(
        _duplicate_value_findings(
            plan.child_suites,
            attr_name="owns_state",
            allowed=plan.allowed_shared_state,
            code="duplicate_state_owner",
            noun="state",
        )
    )
    findings.extend(
        _duplicate_value_findings(
            plan.child_suites,
            attr_name="owns_side_effects",
            allowed=plan.allowed_shared_side_effects,
            code="duplicate_side_effect_owner",
            noun="side_effect",
        )
    )
    suite_findings, release_obligations = _suite_evidence_findings(plan)
    findings.extend(suite_findings)
    findings.extend(_leaf_matrix_evidence_findings(plan))
    decision = _decision_for_findings(findings)
    blockers = _blocker_findings(findings)
    return TestMeshReport(
        ok=not blockers,
        parent_suite_id=plan.parent_suite_id,
        decision=decision,
        decision_scope=plan.decision_scope,
        findings=tuple(findings),
        release_obligations=tuple(release_obligations),
        inventory_revision=plan.inventory_revision,
        covered_inventory_item_ids=inventory_values[1],
        scoped_inventory_item_ids=inventory_values[2],
        missing_inventory_item_ids=inventory_values[3],
    )


__all__ = [
    "TEST_EVIDENCE_ORDER",
    "TEST_LAYER_CHILD",
    "TEST_LAYER_CHILD_DISJOINTNESS",
    "TEST_LAYER_CHILD_REATTACHMENT",
    "TEST_LAYER_CODE_BOUNDARY_CONFORMANCE",
    "TEST_LAYER_CONTRACT_COMBINATION_SHARD",
    "TEST_LAYER_LEAF_BOUNDARY_MATRIX",
    "TEST_LAYER_LEAF_MATRIX_CELL",
    "TEST_LAYER_PARENT",
    "TEST_LAYER_PARENT_COVERAGE",
    "TEST_LAYER_RELEASE",
    "TEST_SCOPE_RELEASE",
    "TEST_SCOPE_ROUTINE",
    "TEST_STATUS_ERROR",
    "TEST_STATUS_FAILED",
    "TEST_STATUS_NOT_RUN",
    "TEST_STATUS_PASSED",
    "TEST_STATUS_RUNNING",
    "TEST_STATUS_SKIPPED",
    "TEST_STATUS_TIMEOUT",
    "TestMeshFinding",
    "TestMeshPlan",
    "TestMeshReport",
    "TestPartitionItem",
    "TestSuiteEvidence",
    "TestTargetSplitDerivation",
    "review_test_mesh",
]
