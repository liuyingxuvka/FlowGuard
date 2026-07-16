"""Model-topology hazard review for future-use risk discovery.

This route keeps the "experienced engineer" step grounded in the model shape.
It does not run an LLM itself. It records the topology digest, usage intent,
and hazard candidates that a Codex skill or project adapter can derive. A
candidate only affects confidence when it is anchored to a concrete state,
edge, side effect, terminal, legacy path, or external boundary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Iterable, Mapping, Sequence

from .export import to_jsonable


TOPOLOGY_NODE_STATE = "state"
TOPOLOGY_NODE_BLOCK = "block"
TOPOLOGY_NODE_INPUT = "input"
TOPOLOGY_NODE_OUTPUT = "output"
TOPOLOGY_NODE_USAGE = "usage"
TOPOLOGY_NODE_BUSINESS_PATH = "business_path"

TOPOLOGY_EDGE_WORKFLOW = "workflow_edge"
TOPOLOGY_EDGE_STATE_WRITE = "state_write"
TOPOLOGY_EDGE_SIDE_EFFECT = "side_effect"
TOPOLOGY_EDGE_EXTERNAL_BOUNDARY = "external_boundary"
TOPOLOGY_EDGE_LEGACY_PATH = "legacy_path"

TOPOLOGY_LANDMARK_SHARED_WRITER = "shared_writer"
TOPOLOGY_LANDMARK_SIDE_EFFECT_REPEAT = "side_effect_repeat"
TOPOLOGY_LANDMARK_EXTERNAL_CONFIRMATION = "external_confirmation_boundary"
TOPOLOGY_LANDMARK_COARSE_TERMINAL = "coarse_terminal_state"
TOPOLOGY_LANDMARK_LEGACY_COMPATIBILITY = "legacy_or_compatibility_path"
TOPOLOGY_LANDMARK_PARENT_CHILD_COMPRESSION = "parent_child_compression"
TOPOLOGY_LANDMARK_BUSINESS_PATH_DUPLICATE = "business_path_duplicate"
TOPOLOGY_LANDMARK_BUSINESS_PATH_CONFLICT = "business_path_conflict"
TOPOLOGY_LANDMARK_BUSINESS_PATH_UNPROVEN = "business_path_unproven"
TOPOLOGY_LANDMARK_BUSINESS_PATH_LEGACY_DISPOSITION = "business_path_legacy_disposition"

TOPOLOGY_USAGE_UNKNOWN = "unknown"
TOPOLOGY_USAGE_LOCAL = "local"
TOPOLOGY_USAGE_CLI = "cli"
TOPOLOGY_USAGE_LIBRARY = "library"
TOPOLOGY_USAGE_PLUGIN = "plugin"
TOPOLOGY_USAGE_SERVICE = "service"
TOPOLOGY_USAGE_RELEASE = "release"
TOPOLOGY_USAGE_MIGRATION = "migration"

TOPOLOGY_COMPAT_UNKNOWN = "unknown"
TOPOLOGY_COMPAT_LATEST_SCHEMA_FIRST = "latest_schema_first_cleanup"
TOPOLOGY_COMPAT_PRESERVE = "preserve_compatibility"
TOPOLOGY_COMPAT_MIGRATE = "migrate_old_shape"
TOPOLOGY_COMPAT_BLOCK = "block_old_shape"
TOPOLOGY_COMPAT_DELETE = "delete_old_path"
TOPOLOGY_COMPAT_SCOPED_OUT = "scoped_out_with_reason"

TOPOLOGY_DISPOSITION_OBSERVATION = "observation_only"
TOPOLOGY_DISPOSITION_MODEL_PATCH = "model_patch_required"
TOPOLOGY_DISPOSITION_TEST_REQUIRED = "test_required"
TOPOLOGY_DISPOSITION_LEDGER_REQUIRED = "risk_ledger_required"
TOPOLOGY_DISPOSITION_COMPATIBILITY_DECISION = "compatibility_decision_required"
TOPOLOGY_DISPOSITION_MODEL_MATURATION = "model_maturation_required"
TOPOLOGY_DISPOSITION_DEVELOPMENT_PROCESS = "development_process_required"
TOPOLOGY_DISPOSITION_SCOPED_OUT = "scoped_out"
TOPOLOGY_DISPOSITION_BLOCKED = "blocked"

TOPOLOGY_CONFIDENCE_FULL = "full"
TOPOLOGY_CONFIDENCE_SCOPED = "scoped"
TOPOLOGY_CONFIDENCE_BLOCKED = "blocked"
TOPOLOGY_CONFIDENCE_OBSERVATION = "observation"

TOPOLOGY_SEVERITY_INFO = "info"
TOPOLOGY_SEVERITY_CONFIDENCE_GAP = "confidence_gap"
TOPOLOGY_SEVERITY_BLOCKER = "blocker"

TOPOLOGY_DECISION_PASS = "topology_hazard_pass"
TOPOLOGY_DECISION_SCOPED = "topology_hazard_scoped_confidence"
TOPOLOGY_DECISION_BLOCKED = "topology_hazard_blocked"

TOPOLOGY_ROUTE_MODEL_MATURATION = "model_maturation_loop"
TOPOLOGY_ROUTE_MODEL_TEST_ALIGNMENT = "model_test_alignment"
TOPOLOGY_ROUTE_RISK_LEDGER = "risk_evidence_ledger"
TOPOLOGY_ROUTE_DEVELOPMENT_PROCESS = "development_process_flow"
TOPOLOGY_ROUTE_ARCHITECTURE_REDUCTION = "architecture_reduction"
TOPOLOGY_ROUTE_MODEL_SIMILARITY = "model_similarity_consolidation"

TOPOLOGY_HARD_DISPOSITIONS = {
    TOPOLOGY_DISPOSITION_MODEL_PATCH,
    TOPOLOGY_DISPOSITION_TEST_REQUIRED,
    TOPOLOGY_DISPOSITION_LEDGER_REQUIRED,
    TOPOLOGY_DISPOSITION_COMPATIBILITY_DECISION,
    TOPOLOGY_DISPOSITION_MODEL_MATURATION,
    TOPOLOGY_DISPOSITION_DEVELOPMENT_PROCESS,
    TOPOLOGY_DISPOSITION_BLOCKED,
}

TOPOLOGY_BROAD_CLAIMS = {"done", "release", "publish", "production", "full", "archive"}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values if str(value))


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return tuple(result)


def _type_name(value: Any) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


def _field_names(value: Any) -> tuple[str, ...]:
    if is_dataclass(value):
        return tuple(field.name for field in fields(value))
    if hasattr(value, "__dict__"):
        return tuple(str(name) for name in vars(value).keys())
    return ()


def _field_values(value: Any) -> tuple[str, ...]:
    names = _field_names(value)
    values: list[str] = []
    for name in names:
        try:
            values.append(str(getattr(value, name)))
        except Exception:
            continue
    return tuple(values)


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    normalized = text.lower()
    return any(keyword in normalized for keyword in keywords)


def _block_name(block: Any, index: int) -> str:
    return str(getattr(block, "name", "") or type(block).__name__ or f"block_{index}")


def _block_tuple(block: Any, attr: str) -> tuple[str, ...]:
    return _as_tuple(getattr(block, attr, ()) or ())


def _block_side_effects(block: Any) -> tuple[str, ...]:
    explicit = _as_tuple(getattr(block, "side_effects", ()) or ())
    if explicit:
        return explicit
    candidates = _block_tuple(block, "writes")
    side_keywords = (
        "api",
        "cache",
        "database",
        "db",
        "email",
        "file",
        "network",
        "payment",
        "persist",
        "publish",
        "release",
        "save",
        "write",
    )
    return tuple(item for item in candidates if _contains_any(item, side_keywords))


def _broad_usage(usage: "UsageIntent") -> bool:
    if usage.final_claim in TOPOLOGY_BROAD_CLAIMS:
        return True
    return bool(
        set(usage.usage_modes).intersection(
            {
                TOPOLOGY_USAGE_LIBRARY,
                TOPOLOGY_USAGE_PLUGIN,
                TOPOLOGY_USAGE_RELEASE,
                TOPOLOGY_USAGE_SERVICE,
            }
        )
    )


@dataclass(frozen=True)
class BusinessPathIdentity:
    """Stable identity for an important modeled business path."""

    path_id: str
    business_intent: str = ""
    trigger: str = ""
    preconditions: tuple[str, ...] = ()
    expected_terminal: str = ""
    state_writes: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    source_labels: tuple[str, ...] = ()
    equivalent_to: tuple[str, ...] = ()
    exclusive_with: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    compatibility_disposition: str = TOPOLOGY_COMPAT_UNKNOWN
    authority_role: str = ""
    fallback_for: str = ""
    invoked_on_primary_failure: bool = False
    returns_success_after_primary_failure: bool = False
    fallback_disposition: str = ""
    evidence_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        path_id = str(self.path_id)
        if not path_id:
            raise ValueError("path_id is required")
        object.__setattr__(self, "path_id", path_id)
        object.__setattr__(self, "business_intent", str(self.business_intent))
        object.__setattr__(self, "trigger", str(self.trigger))
        object.__setattr__(self, "preconditions", _as_tuple(self.preconditions))
        object.__setattr__(self, "expected_terminal", str(self.expected_terminal))
        object.__setattr__(self, "state_writes", _as_tuple(self.state_writes))
        object.__setattr__(self, "side_effects", _as_tuple(self.side_effects))
        object.__setattr__(self, "source_labels", _as_tuple(self.source_labels))
        object.__setattr__(self, "equivalent_to", _as_tuple(self.equivalent_to))
        object.__setattr__(self, "exclusive_with", _as_tuple(self.exclusive_with))
        object.__setattr__(self, "supersedes", _as_tuple(self.supersedes))
        object.__setattr__(
            self,
            "compatibility_disposition",
            str(self.compatibility_disposition or TOPOLOGY_COMPAT_UNKNOWN),
        )
        object.__setattr__(self, "authority_role", str(self.authority_role))
        object.__setattr__(self, "fallback_for", str(self.fallback_for))
        object.__setattr__(self, "invoked_on_primary_failure", bool(self.invoked_on_primary_failure))
        object.__setattr__(
            self,
            "returns_success_after_primary_failure",
            bool(self.returns_success_after_primary_failure),
        )
        object.__setattr__(self, "fallback_disposition", str(self.fallback_disposition))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def anchor_id(self) -> str:
        return f"business_path:{self.path_id}"

    def has_current_source(self) -> bool:
        return bool(self.source_labels or self.evidence_ids)

    def identity_key(self) -> tuple[str, str, str]:
        return (
            self.business_intent.strip().lower(),
            self.trigger.strip().lower(),
            self.expected_terminal.strip().lower(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_id": self.path_id,
            "business_intent": self.business_intent,
            "trigger": self.trigger,
            "preconditions": list(self.preconditions),
            "expected_terminal": self.expected_terminal,
            "state_writes": list(self.state_writes),
            "side_effects": list(self.side_effects),
            "source_labels": list(self.source_labels),
            "equivalent_to": list(self.equivalent_to),
            "exclusive_with": list(self.exclusive_with),
            "supersedes": list(self.supersedes),
            "compatibility_disposition": self.compatibility_disposition,
            "authority_role": self.authority_role,
            "fallback_for": self.fallback_for,
            "invoked_on_primary_failure": self.invoked_on_primary_failure,
            "returns_success_after_primary_failure": self.returns_success_after_primary_failure,
            "fallback_disposition": self.fallback_disposition,
            "evidence_ids": list(self.evidence_ids),
            "metadata": to_jsonable(dict(self.metadata)),
        }


def _coerce_business_path(value: BusinessPathIdentity | Mapping[str, Any] | Any) -> BusinessPathIdentity:
    if isinstance(value, BusinessPathIdentity):
        return value
    if isinstance(value, Mapping):
        return BusinessPathIdentity(**value)
    return BusinessPathIdentity(
        path_id=getattr(value, "path_id", "") or getattr(value, "id", ""),
        business_intent=getattr(value, "business_intent", "") or getattr(value, "intent", ""),
        trigger=getattr(value, "trigger", ""),
        preconditions=getattr(value, "preconditions", ()),
        expected_terminal=getattr(value, "expected_terminal", "") or getattr(value, "terminal", ""),
        state_writes=getattr(value, "state_writes", ()) or getattr(value, "writes", ()),
        side_effects=getattr(value, "side_effects", ()),
        source_labels=getattr(value, "source_labels", ()),
        equivalent_to=getattr(value, "equivalent_to", ()),
        exclusive_with=getattr(value, "exclusive_with", ()),
        supersedes=getattr(value, "supersedes", ()),
        compatibility_disposition=getattr(value, "compatibility_disposition", TOPOLOGY_COMPAT_UNKNOWN),
        evidence_ids=getattr(value, "evidence_ids", ()),
        metadata=getattr(value, "metadata", {}) or {},
    )


def _paths_exclusive(left: BusinessPathIdentity, right: BusinessPathIdentity) -> bool:
    return right.path_id in left.exclusive_with or left.path_id in right.exclusive_with


def _paths_share_applicability(left: BusinessPathIdentity, right: BusinessPathIdentity) -> bool:
    if left.trigger and right.trigger and left.trigger != right.trigger:
        return False
    if not left.preconditions or not right.preconditions:
        return True
    return bool(set(left.preconditions).intersection(right.preconditions))


@dataclass(frozen=True)
class UsageIntent:
    """Project and final-claim context used to interpret model topology."""

    intent_id: str = "usage"
    usage_modes: tuple[str, ...] = (TOPOLOGY_USAGE_UNKNOWN,)
    final_claim: str = "bounded"
    goal: str = ""
    external_users_possible: bool = False
    persistent_history_possible: bool = False
    compatibility_policy: str = TOPOLOGY_COMPAT_UNKNOWN
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        modes = _as_tuple(self.usage_modes) or (TOPOLOGY_USAGE_UNKNOWN,)
        object.__setattr__(self, "intent_id", str(self.intent_id))
        object.__setattr__(self, "usage_modes", modes)
        object.__setattr__(self, "final_claim", str(self.final_claim or "bounded"))
        object.__setattr__(self, "goal", str(self.goal))
        object.__setattr__(self, "external_users_possible", bool(self.external_users_possible))
        object.__setattr__(self, "persistent_history_possible", bool(self.persistent_history_possible))
        object.__setattr__(self, "compatibility_policy", str(self.compatibility_policy or TOPOLOGY_COMPAT_UNKNOWN))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "usage_modes": list(self.usage_modes),
            "final_claim": self.final_claim,
            "goal": self.goal,
            "external_users_possible": self.external_users_possible,
            "persistent_history_possible": self.persistent_history_possible,
            "compatibility_policy": self.compatibility_policy,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class TopologyNode:
    """One node in a topology digest."""

    node_id: str
    node_kind: str
    label: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", str(self.node_id))
        object.__setattr__(self, "node_kind", str(self.node_kind))
        object.__setattr__(self, "label", str(self.label))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_kind": self.node_kind,
            "label": self.label,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class TopologyEdge:
    """One edge or responsibility relation in a topology digest."""

    edge_id: str
    edge_kind: str
    source_id: str
    target_id: str
    label: str = ""
    block_name: str = ""
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    repeatable: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", str(self.edge_id))
        object.__setattr__(self, "edge_kind", str(self.edge_kind))
        object.__setattr__(self, "source_id", str(self.source_id))
        object.__setattr__(self, "target_id", str(self.target_id))
        object.__setattr__(self, "label", str(self.label))
        object.__setattr__(self, "block_name", str(self.block_name))
        object.__setattr__(self, "reads", _as_tuple(self.reads))
        object.__setattr__(self, "writes", _as_tuple(self.writes))
        object.__setattr__(self, "side_effects", _as_tuple(self.side_effects))
        object.__setattr__(self, "repeatable", bool(self.repeatable))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "edge_kind": self.edge_kind,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "label": self.label,
            "block_name": self.block_name,
            "reads": list(self.reads),
            "writes": list(self.writes),
            "side_effects": list(self.side_effects),
            "repeatable": self.repeatable,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class TopologyLandmark:
    """One model-shape landmark that can justify future-risk inference."""

    landmark_id: str
    landmark_type: str
    anchor_ids: tuple[str, ...] = ()
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "landmark_id", str(self.landmark_id))
        object.__setattr__(self, "landmark_type", str(self.landmark_type))
        object.__setattr__(self, "anchor_ids", _as_tuple(self.anchor_ids))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "landmark_id": self.landmark_id,
            "landmark_type": self.landmark_type,
            "anchor_ids": list(self.anchor_ids),
            "description": self.description,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class TopologyDigest:
    """A compact model-topology map that an AI reviewer can read."""

    digest_id: str
    workflow_name: str = ""
    nodes: tuple[TopologyNode, ...] = ()
    edges: tuple[TopologyEdge, ...] = ()
    landmarks: tuple[TopologyLandmark, ...] = ()
    usage_intent: UsageIntent = field(default_factory=UsageIntent)
    business_paths: tuple[BusinessPathIdentity, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "digest_id", str(self.digest_id))
        object.__setattr__(self, "workflow_name", str(self.workflow_name))
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "edges", tuple(self.edges))
        object.__setattr__(self, "landmarks", tuple(self.landmarks))
        object.__setattr__(self, "business_paths", tuple(_coerce_business_path(path) for path in self.business_paths))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def anchor_ids(self) -> tuple[str, ...]:
        return _unique(
            tuple(node.node_id for node in self.nodes)
            + tuple(edge.edge_id for edge in self.edges)
            + tuple(landmark.landmark_id for landmark in self.landmarks)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "digest_id": self.digest_id,
            "workflow_name": self.workflow_name,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "landmarks": [landmark.to_dict() for landmark in self.landmarks],
            "usage_intent": self.usage_intent.to_dict(),
            "business_paths": [path.to_dict() for path in self.business_paths],
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class TopologyHazardCandidate:
    """One future-use risk hypothesis grounded in model topology."""

    hazard_id: str
    summary: str
    rationale: str = ""
    future_failure_mode: str = ""
    topology_anchor_ids: tuple[str, ...] = ()
    source_landmark_ids: tuple[str, ...] = ()
    disposition: str = TOPOLOGY_DISPOSITION_OBSERVATION
    required_routes: tuple[str, ...] = ()
    confidence_effect: str = TOPOLOGY_CONFIDENCE_OBSERVATION
    severity: str = TOPOLOGY_SEVERITY_INFO
    handled: bool = False
    scoped_reason: str = ""
    model_obligation_id: str = ""
    proof_evidence_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hazard_id", str(self.hazard_id))
        object.__setattr__(self, "summary", str(self.summary))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "future_failure_mode", str(self.future_failure_mode))
        object.__setattr__(self, "topology_anchor_ids", _as_tuple(self.topology_anchor_ids))
        object.__setattr__(self, "source_landmark_ids", _as_tuple(self.source_landmark_ids))
        object.__setattr__(self, "disposition", str(self.disposition))
        object.__setattr__(self, "required_routes", _as_tuple(self.required_routes))
        object.__setattr__(self, "confidence_effect", str(self.confidence_effect))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "handled", bool(self.handled))
        object.__setattr__(self, "scoped_reason", str(self.scoped_reason))
        object.__setattr__(self, "model_obligation_id", str(self.model_obligation_id))
        object.__setattr__(self, "proof_evidence_ids", _as_tuple(self.proof_evidence_ids))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def anchored(self) -> bool:
        return bool(self.topology_anchor_ids or self.source_landmark_ids)

    def hard_disposition(self) -> bool:
        return self.disposition in TOPOLOGY_HARD_DISPOSITIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "hazard_id": self.hazard_id,
            "summary": self.summary,
            "rationale": self.rationale,
            "future_failure_mode": self.future_failure_mode,
            "topology_anchor_ids": list(self.topology_anchor_ids),
            "source_landmark_ids": list(self.source_landmark_ids),
            "disposition": self.disposition,
            "required_routes": list(self.required_routes),
            "confidence_effect": self.confidence_effect,
            "severity": self.severity,
            "handled": self.handled,
            "scoped_reason": self.scoped_reason,
            "model_obligation_id": self.model_obligation_id,
            "proof_evidence_ids": list(self.proof_evidence_ids),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class TopologyHazardFinding:
    """One topology hazard review finding."""

    code: str
    message: str
    severity: str = TOPOLOGY_SEVERITY_CONFIDENCE_GAP
    hazard_id: str = ""
    anchor_ids: tuple[str, ...] = ()
    required_routes: tuple[str, ...] = ()
    action: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "hazard_id", str(self.hazard_id))
        object.__setattr__(self, "anchor_ids", _as_tuple(self.anchor_ids))
        object.__setattr__(self, "required_routes", _as_tuple(self.required_routes))
        object.__setattr__(self, "action", str(self.action))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "hazard_id": self.hazard_id,
            "anchor_ids": list(self.anchor_ids),
            "required_routes": list(self.required_routes),
            "action": self.action,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class TopologyHazardReviewPlan:
    """Inputs to a topology hazard review."""

    plan_id: str
    digest: TopologyDigest
    candidates: tuple[TopologyHazardCandidate, ...] = ()
    auto_generate_candidates: bool = True
    allow_scoped_confidence: bool = True
    final_claim: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "auto_generate_candidates", bool(self.auto_generate_candidates))
        object.__setattr__(self, "allow_scoped_confidence", bool(self.allow_scoped_confidence))
        object.__setattr__(self, "final_claim", str(self.final_claim or self.digest.usage_intent.final_claim))

    def broad_claim(self) -> bool:
        return self.final_claim in TOPOLOGY_BROAD_CLAIMS or _broad_usage(self.digest.usage_intent)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "digest": self.digest.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "auto_generate_candidates": self.auto_generate_candidates,
            "allow_scoped_confidence": self.allow_scoped_confidence,
            "final_claim": self.final_claim,
        }


@dataclass(frozen=True)
class TopologyHazardReport:
    """Result of reviewing topology-anchored future-use hazards."""

    ok: bool
    plan_id: str
    decision: str
    confidence: str
    digest: TopologyDigest
    candidates: tuple[TopologyHazardCandidate, ...] = ()
    findings: tuple[TopologyHazardFinding, ...] = ()
    unresolved_hazard_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "unresolved_hazard_ids", _as_tuple(self.unresolved_hazard_ids))
        object.__setattr__(self, "summary", str(self.summary))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan_id": self.plan_id,
            "decision": self.decision,
            "confidence": self.confidence,
            "digest": self.digest.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "findings": [finding.to_dict() for finding in self.findings],
            "unresolved_hazard_ids": list(self.unresolved_hazard_ids),
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def format_text(self) -> str:
        status = (
            "pass"
            if self.ok and self.confidence == TOPOLOGY_CONFIDENCE_FULL
            else "pass_with_gaps"
            if self.ok
            else "blocked"
        )
        lines = [
            "=== flowguard topology hazard review ===",
            f"plan_id: {self.plan_id}",
            f"status: {status}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"summary: {self.summary}",
            f"landmarks: {len(self.digest.landmarks)}",
            f"candidates: {len(self.candidates)}",
        ]
        if self.findings:
            lines.append("findings:")
            for finding in self.findings:
                lines.append(f"- {finding.severity}: {finding.code}: {finding.message}")
                if finding.action:
                    lines.append(f"  action: {finding.action}")
        if self.unresolved_hazard_ids:
            lines.append("unresolved_hazard_ids: " + ", ".join(self.unresolved_hazard_ids))
        return "\n".join(lines)


def infer_usage_intent(
    *,
    goal: str = "",
    final_claim: str = "",
    project_kind: str = "",
    compatibility_policy: str = TOPOLOGY_COMPAT_UNKNOWN,
    external_users_possible: bool | None = None,
    persistent_history_possible: bool | None = None,
) -> UsageIntent:
    """Infer a conservative usage intent from small text hints."""

    text = " ".join((goal, final_claim, project_kind)).lower()
    modes: list[str] = []
    if _contains_any(text, ("release", "publish", "tag", "package")):
        modes.append(TOPOLOGY_USAGE_RELEASE)
    if _contains_any(text, ("service", "server", "api", "production", "deploy", "online")):
        modes.append(TOPOLOGY_USAGE_SERVICE)
    if _contains_any(text, ("library", "package", "public api", "sdk")):
        modes.append(TOPOLOGY_USAGE_LIBRARY)
    if _contains_any(text, ("plugin", "skill", "codex")):
        modes.append(TOPOLOGY_USAGE_PLUGIN)
    if _contains_any(text, ("cli", "command line", "script")):
        modes.append(TOPOLOGY_USAGE_CLI)
    if _contains_any(text, ("migration", "upgrade", "schema", "legacy", "old")):
        modes.append(TOPOLOGY_USAGE_MIGRATION)
    if not modes:
        modes.append(TOPOLOGY_USAGE_UNKNOWN)
    external = bool(external_users_possible) if external_users_possible is not None else bool(
        set(modes).intersection({TOPOLOGY_USAGE_LIBRARY, TOPOLOGY_USAGE_PLUGIN, TOPOLOGY_USAGE_RELEASE, TOPOLOGY_USAGE_SERVICE})
    )
    persistent = bool(persistent_history_possible) if persistent_history_possible is not None else _contains_any(
        text,
        ("compat", "history", "legacy", "old", "schema", "stored", "persistent", "migration"),
    )
    return UsageIntent(
        usage_modes=tuple(modes),
        final_claim=final_claim or ("release" if TOPOLOGY_USAGE_RELEASE in modes else "bounded"),
        goal=goal,
        external_users_possible=external,
        persistent_history_possible=persistent,
        compatibility_policy=compatibility_policy,
    )


def infer_topology_digest(
    *,
    workflow: Any,
    initial_states: Sequence[Any] = (),
    external_inputs: Sequence[Any] = (),
    usage_intent: UsageIntent | None = None,
    business_paths: Sequence[BusinessPathIdentity | Mapping[str, Any] | Any] = (),
    digest_id: str = "",
) -> TopologyDigest:
    """Build a small topology digest from a FlowGuard workflow and examples."""

    blocks = tuple(getattr(workflow, "blocks", ()) or ())
    workflow_name = str(getattr(workflow, "name", "") or type(workflow).__name__)
    usage = usage_intent or UsageIntent()
    path_identities = tuple(_coerce_business_path(path) for path in business_paths)
    nodes: list[TopologyNode] = [
        TopologyNode("usage:intent", TOPOLOGY_NODE_USAGE, usage.final_claim, {"usage_modes": usage.usage_modes})
    ]
    for index, block in enumerate(blocks):
        reads = _block_tuple(block, "reads")
        writes = _block_tuple(block, "writes")
        nodes.append(
            TopologyNode(
                f"block:{index}:{_block_name(block, index)}",
                TOPOLOGY_NODE_BLOCK,
                _block_name(block, index),
                {"reads": reads, "writes": writes},
            )
        )
    for index, state in enumerate(initial_states):
        nodes.append(
            TopologyNode(
                f"state:{index}:{_type_name(state)}",
                TOPOLOGY_NODE_STATE,
                _type_name(state),
                {"fields": _field_names(state), "values": _field_values(state)},
            )
        )
    for index, input_obj in enumerate(external_inputs):
        nodes.append(
            TopologyNode(
                f"input:{index}:{_type_name(input_obj)}",
                TOPOLOGY_NODE_INPUT,
                _type_name(input_obj),
                {"fields": _field_names(input_obj), "values": _field_values(input_obj)},
            )
        )
    for path in path_identities:
        nodes.append(
            TopologyNode(
                path.anchor_id(),
                TOPOLOGY_NODE_BUSINESS_PATH,
                path.business_intent or path.path_id,
                path.to_dict(),
            )
        )

    edges: list[TopologyEdge] = []
    for index, block in enumerate(blocks):
        name = _block_name(block, index)
        source = "usage:intent" if index == 0 else f"block:{index - 1}:{_block_name(blocks[index - 1], index - 1)}"
        target = f"block:{index}:{name}"
        reads = _block_tuple(block, "reads")
        writes = _block_tuple(block, "writes")
        side_effects = _block_side_effects(block)
        edges.append(
            TopologyEdge(
                f"edge:{index}:{name}",
                TOPOLOGY_EDGE_WORKFLOW,
                source,
                target,
                label=name,
                block_name=name,
                reads=reads,
                writes=writes,
                side_effects=side_effects,
                repeatable=bool(external_inputs),
            )
        )
        if side_effects:
            edges.append(
                TopologyEdge(
                    f"effect:{index}:{name}",
                    TOPOLOGY_EDGE_SIDE_EFFECT,
                    target,
                    f"output:{index}:{name}",
                    label="observable side effect",
                    block_name=name,
                    reads=reads,
                    writes=writes,
                    side_effects=side_effects,
                    repeatable=bool(external_inputs),
                )
            )

    landmarks = list(_infer_landmarks(nodes, edges, usage, path_identities))
    return TopologyDigest(
        digest_id=digest_id or f"topology:{workflow_name}",
        workflow_name=workflow_name,
        nodes=tuple(nodes),
        edges=tuple(edges),
        landmarks=tuple(landmarks),
        usage_intent=usage,
        business_paths=path_identities,
    )


def _infer_landmarks(
    nodes: Sequence[TopologyNode],
    edges: Sequence[TopologyEdge],
    usage: UsageIntent,
    business_paths: Sequence[BusinessPathIdentity] = (),
) -> tuple[TopologyLandmark, ...]:
    landmarks: list[TopologyLandmark] = []
    write_owners: dict[str, list[str]] = {}
    for edge in edges:
        for write in edge.writes:
            write_owners.setdefault(write, []).append(edge.edge_id)
    for write, owner_ids in sorted(write_owners.items()):
        if len(owner_ids) > 1:
            landmarks.append(
                TopologyLandmark(
                    f"landmark:shared-writer:{write}",
                    TOPOLOGY_LANDMARK_SHARED_WRITER,
                    tuple(owner_ids),
                    f"multiple topology edges write {write!r}",
                )
            )

    for edge in edges:
        if edge.side_effects and edge.repeatable and edge.edge_kind != TOPOLOGY_EDGE_SIDE_EFFECT:
            landmarks.append(
                TopologyLandmark(
                    f"landmark:side-effect-repeat:{edge.edge_id}",
                    TOPOLOGY_LANDMARK_SIDE_EFFECT_REPEAT,
                    (edge.edge_id,),
                    "repeatable edge owns observable side effects",
                )
            )
        text = " ".join((edge.edge_id, edge.label, edge.block_name, " ".join(edge.writes), " ".join(edge.side_effects)))
        if _contains_any(text, ("confirm", "external", "callback", "remote", "deploy", "publish")):
            landmarks.append(
                TopologyLandmark(
                    f"landmark:external-confirmation:{edge.edge_id}",
                    TOPOLOGY_LANDMARK_EXTERNAL_CONFIRMATION,
                    (edge.edge_id,),
                    "edge appears to cross an external confirmation boundary",
                )
            )
        if _contains_any(text, ("legacy", "old", "compat", "schema", "migration", "upgrade")):
            landmarks.append(
                TopologyLandmark(
                    f"landmark:legacy:{edge.edge_id}",
                    TOPOLOGY_LANDMARK_LEGACY_COMPATIBILITY,
                    (edge.edge_id,),
                    "edge appears to involve old-shape or compatibility topology",
                )
            )

    for node in nodes:
        text = " ".join((node.node_id, node.label, " ".join(str(value) for value in node.metadata.values())))
        if _contains_any(text, ("done", "complete", "success", "final")):
            landmarks.append(
                TopologyLandmark(
                    f"landmark:coarse-terminal:{node.node_id}",
                    TOPOLOGY_LANDMARK_COARSE_TERMINAL,
                    (node.node_id,),
                    "node suggests a broad terminal/success state",
                )
            )
        if _contains_any(text, ("parent", "child", "mesh")):
            landmarks.append(
                TopologyLandmark(
                    f"landmark:parent-child:{node.node_id}",
                    TOPOLOGY_LANDMARK_PARENT_CHILD_COMPRESSION,
                    (node.node_id,),
                    "node suggests parent/child model compression",
                )
            )

    if usage.persistent_history_possible or usage.compatibility_policy != TOPOLOGY_COMPAT_UNKNOWN:
        landmarks.append(
            TopologyLandmark(
                "landmark:usage:history",
                TOPOLOGY_LANDMARK_LEGACY_COMPATIBILITY,
                ("usage:intent",),
                "usage intent includes old data, old API, schema, or compatibility history",
            )
        )
    if _broad_usage(usage):
        landmarks.append(
            TopologyLandmark(
                "landmark:usage:external-boundary",
                TOPOLOGY_LANDMARK_EXTERNAL_CONFIRMATION,
                ("usage:intent",),
                "usage intent asks for broad release, production, package, plugin, or service confidence",
            )
        )
    landmarks.extend(_infer_business_path_landmarks(business_paths))
    return tuple(landmarks)


def _infer_business_path_landmarks(
    business_paths: Sequence[BusinessPathIdentity],
) -> tuple[TopologyLandmark, ...]:
    landmarks: list[TopologyLandmark] = []
    by_id = {path.path_id: path for path in business_paths}

    for path in business_paths:
        if not path.has_current_source():
            landmarks.append(
                TopologyLandmark(
                    f"landmark:business-path-unproven:{path.path_id}",
                    TOPOLOGY_LANDMARK_BUSINESS_PATH_UNPROVEN,
                    (path.anchor_id(),),
                    "business path lacks source labels or current evidence ids",
                    {"path_id": path.path_id},
                )
            )
        if path.supersedes and path.compatibility_disposition == TOPOLOGY_COMPAT_UNKNOWN:
            landmarks.append(
                TopologyLandmark(
                    f"landmark:business-path-legacy:{path.path_id}",
                    TOPOLOGY_LANDMARK_BUSINESS_PATH_LEGACY_DISPOSITION,
                    (path.anchor_id(),) + tuple(f"business_path:{old_id}" for old_id in path.supersedes),
                    "business path supersedes old paths without an explicit compatibility disposition",
                    {"path_id": path.path_id, "supersedes": path.supersedes},
                )
            )

    duplicate_pairs: set[tuple[str, str]] = set()
    for path in business_paths:
        for equivalent_id in path.equivalent_to:
            if equivalent_id in by_id:
                duplicate_pairs.add(tuple(sorted((path.path_id, equivalent_id))))

    by_identity: dict[tuple[str, str, str], list[BusinessPathIdentity]] = {}
    for path in business_paths:
        key = path.identity_key()
        if key[0] and (key[1] or key[2]):
            by_identity.setdefault(key, []).append(path)
    for paths in by_identity.values():
        if len(paths) < 2:
            continue
        for left_index, left in enumerate(paths):
            for right in paths[left_index + 1 :]:
                if not _paths_exclusive(left, right):
                    duplicate_pairs.add(tuple(sorted((left.path_id, right.path_id))))

    for left_id, right_id in sorted(duplicate_pairs):
        left = by_id[left_id]
        right = by_id[right_id]
        landmarks.append(
            TopologyLandmark(
                f"landmark:business-path-duplicate:{left_id}:{right_id}",
                TOPOLOGY_LANDMARK_BUSINESS_PATH_DUPLICATE,
                (left.anchor_id(), right.anchor_id()),
                "business paths appear to perform the same business job",
                {
                    "path_ids": (left_id, right_id),
                    "left": left.to_dict(),
                    "right": right.to_dict(),
                },
            )
        )

    for left_index, left in enumerate(business_paths):
        for right in business_paths[left_index + 1 :]:
            if _paths_exclusive(left, right) or not _paths_share_applicability(left, right):
                continue
            shared_state = tuple(sorted(set(left.state_writes).intersection(right.state_writes)))
            shared_effects = tuple(sorted(set(left.side_effects).intersection(right.side_effects)))
            terminal_conflict = bool(
                left.expected_terminal
                and right.expected_terminal
                and left.expected_terminal != right.expected_terminal
            )
            side_effect_conflict = bool(left.side_effects and right.side_effects and set(left.side_effects) != set(right.side_effects))
            if (shared_state or shared_effects) and (terminal_conflict or side_effect_conflict):
                landmarks.append(
                    TopologyLandmark(
                        f"landmark:business-path-conflict:{left.path_id}:{right.path_id}",
                        TOPOLOGY_LANDMARK_BUSINESS_PATH_CONFLICT,
                        (left.anchor_id(), right.anchor_id()),
                        "business paths share applicability and ownership but disagree on terminal or side effects",
                        {
                            "path_ids": (left.path_id, right.path_id),
                            "shared_state_writes": shared_state,
                            "shared_side_effects": shared_effects,
                            "left_terminal": left.expected_terminal,
                            "right_terminal": right.expected_terminal,
                        },
                    )
                )
    return tuple(landmarks)


def derive_topology_hazard_candidates(digest: TopologyDigest) -> tuple[TopologyHazardCandidate, ...]:
    """Derive conservative candidate hazards from topology landmarks."""

    candidates: list[TopologyHazardCandidate] = []
    broad = _broad_usage(digest.usage_intent)
    for landmark in digest.landmarks:
        if landmark.landmark_type == TOPOLOGY_LANDMARK_SHARED_WRITER:
            candidates.append(
                TopologyHazardCandidate(
                    f"hazard:shared-writer:{landmark.landmark_id}",
                    "Multiple model edges write the same state surface.",
                    rationale="Shared writers can hide overwrite, stale sibling, or ownership drift when future use changes path order.",
                    future_failure_mode="A later path updates the same state surface without the earlier proof still applying.",
                    topology_anchor_ids=landmark.anchor_ids,
                    source_landmark_ids=(landmark.landmark_id,),
                    disposition=TOPOLOGY_DISPOSITION_MODEL_MATURATION,
                    required_routes=(TOPOLOGY_ROUTE_MODEL_MATURATION,),
                    confidence_effect=TOPOLOGY_CONFIDENCE_SCOPED,
                    severity=TOPOLOGY_SEVERITY_CONFIDENCE_GAP,
                )
            )
        elif landmark.landmark_type == TOPOLOGY_LANDMARK_SIDE_EFFECT_REPEAT:
            candidates.append(
                TopologyHazardCandidate(
                    f"hazard:repeatable-side-effect:{landmark.landmark_id}",
                    "A repeatable topology edge owns an observable side effect.",
                    rationale="A model that passes one local path may still overclaim if repeated real use replays the side effect.",
                    future_failure_mode="Repeated use produces duplicate or stale side effects not represented by the proof boundary.",
                    topology_anchor_ids=landmark.anchor_ids,
                    source_landmark_ids=(landmark.landmark_id,),
                    disposition=TOPOLOGY_DISPOSITION_LEDGER_REQUIRED,
                    required_routes=(TOPOLOGY_ROUTE_RISK_LEDGER, TOPOLOGY_ROUTE_MODEL_TEST_ALIGNMENT),
                    confidence_effect=TOPOLOGY_CONFIDENCE_BLOCKED if broad else TOPOLOGY_CONFIDENCE_SCOPED,
                    severity=TOPOLOGY_SEVERITY_BLOCKER if broad else TOPOLOGY_SEVERITY_CONFIDENCE_GAP,
                )
            )
        elif landmark.landmark_type == TOPOLOGY_LANDMARK_EXTERNAL_CONFIRMATION:
            candidates.append(
                TopologyHazardCandidate(
                    f"hazard:external-boundary:{landmark.landmark_id}",
                    "The model has a broad or external confirmation boundary.",
                    rationale="Local success can overclaim future confidence when the final state depends on an external environment.",
                    future_failure_mode="The project reports success before external use, release, deployment, or callback evidence exists.",
                    topology_anchor_ids=landmark.anchor_ids,
                    source_landmark_ids=(landmark.landmark_id,),
                    disposition=TOPOLOGY_DISPOSITION_DEVELOPMENT_PROCESS,
                    required_routes=(TOPOLOGY_ROUTE_DEVELOPMENT_PROCESS, TOPOLOGY_ROUTE_RISK_LEDGER),
                    confidence_effect=TOPOLOGY_CONFIDENCE_SCOPED,
                    severity=TOPOLOGY_SEVERITY_CONFIDENCE_GAP,
                )
            )
        elif landmark.landmark_type == TOPOLOGY_LANDMARK_COARSE_TERMINAL:
            candidates.append(
                TopologyHazardCandidate(
                    f"hazard:coarse-terminal:{landmark.landmark_id}",
                    "A broad terminal or success node may compress hidden future states.",
                    rationale="Experienced review should not treat a coarse done/success state as proof that recovery, partial success, or external confirmation is modeled.",
                    future_failure_mode="A hidden post-success failure appears after local green evidence.",
                    topology_anchor_ids=landmark.anchor_ids,
                    source_landmark_ids=(landmark.landmark_id,),
                    disposition=TOPOLOGY_DISPOSITION_MODEL_MATURATION,
                    required_routes=(TOPOLOGY_ROUTE_MODEL_MATURATION,),
                    confidence_effect=TOPOLOGY_CONFIDENCE_SCOPED,
                    severity=TOPOLOGY_SEVERITY_CONFIDENCE_GAP,
                )
            )
        elif landmark.landmark_type == TOPOLOGY_LANDMARK_LEGACY_COMPATIBILITY:
            effect = (
                TOPOLOGY_CONFIDENCE_BLOCKED
                if digest.usage_intent.compatibility_policy == TOPOLOGY_COMPAT_UNKNOWN and broad
                else TOPOLOGY_CONFIDENCE_SCOPED
            )
            candidates.append(
                TopologyHazardCandidate(
                    f"hazard:compatibility:{landmark.landmark_id}",
                    "Old-shape or compatibility topology needs an explicit disposition.",
                    rationale="A model with old/new or historical surfaces must decide whether history is preserved, migrated, blocked, deleted, or latest-schema-first cleaned.",
                    future_failure_mode="Future users, old data, old config, or old artifacts reach a path the model silently removed or still accepts.",
                    topology_anchor_ids=landmark.anchor_ids,
                    source_landmark_ids=(landmark.landmark_id,),
                    disposition=TOPOLOGY_DISPOSITION_COMPATIBILITY_DECISION,
                    required_routes=(TOPOLOGY_ROUTE_ARCHITECTURE_REDUCTION, TOPOLOGY_ROUTE_RISK_LEDGER),
                    confidence_effect=effect,
                    severity=TOPOLOGY_SEVERITY_BLOCKER if effect == TOPOLOGY_CONFIDENCE_BLOCKED else TOPOLOGY_SEVERITY_CONFIDENCE_GAP,
                )
            )
        elif landmark.landmark_type == TOPOLOGY_LANDMARK_PARENT_CHILD_COMPRESSION:
            candidates.append(
                TopologyHazardCandidate(
                    f"hazard:parent-child:{landmark.landmark_id}",
                    "Parent/child topology appears compressed.",
                    rationale="A parent model can pass while future child evidence or old child obligations are no longer attached.",
                    future_failure_mode="Child-local green evidence is counted as parent confidence without current reattachment.",
                    topology_anchor_ids=landmark.anchor_ids,
                    source_landmark_ids=(landmark.landmark_id,),
                    disposition=TOPOLOGY_DISPOSITION_MODEL_MATURATION,
                    required_routes=(TOPOLOGY_ROUTE_MODEL_MATURATION,),
                    confidence_effect=TOPOLOGY_CONFIDENCE_SCOPED,
                    severity=TOPOLOGY_SEVERITY_CONFIDENCE_GAP,
                )
            )
        elif landmark.landmark_type == TOPOLOGY_LANDMARK_BUSINESS_PATH_DUPLICATE:
            candidates.append(
                TopologyHazardCandidate(
                    f"hazard:business-path-duplicate:{landmark.landmark_id}",
                    "Two business paths appear to do the same useful job.",
                    rationale="Duplicate business paths increase model and software support cost unless one is removed, folded, or explicitly preserved for compatibility.",
                    future_failure_mode="Future changes update one useful path while a duplicate path remains reachable, stale, or falsely counted as separate evidence.",
                    topology_anchor_ids=landmark.anchor_ids,
                    source_landmark_ids=(landmark.landmark_id,),
                    disposition=TOPOLOGY_DISPOSITION_COMPATIBILITY_DECISION,
                    required_routes=(
                        TOPOLOGY_ROUTE_ARCHITECTURE_REDUCTION,
                        TOPOLOGY_ROUTE_MODEL_SIMILARITY,
                        TOPOLOGY_ROUTE_RISK_LEDGER,
                    ),
                    confidence_effect=TOPOLOGY_CONFIDENCE_SCOPED,
                    severity=TOPOLOGY_SEVERITY_CONFIDENCE_GAP,
                    metadata=landmark.metadata,
                )
            )
        elif landmark.landmark_type == TOPOLOGY_LANDMARK_BUSINESS_PATH_CONFLICT:
            effect = TOPOLOGY_CONFIDENCE_BLOCKED if broad else TOPOLOGY_CONFIDENCE_SCOPED
            candidates.append(
                TopologyHazardCandidate(
                    f"hazard:business-path-conflict:{landmark.landmark_id}",
                    "Business paths may conflict for the same trigger or ownership surface.",
                    rationale="A green local model can still be wrong if two routes compete for the same business input, state write, side effect, or terminal result.",
                    future_failure_mode="The real workflow follows a different path than the modeled claim, or two paths race to write incompatible state.",
                    topology_anchor_ids=landmark.anchor_ids,
                    source_landmark_ids=(landmark.landmark_id,),
                    disposition=TOPOLOGY_DISPOSITION_MODEL_MATURATION,
                    required_routes=(
                        TOPOLOGY_ROUTE_MODEL_MATURATION,
                        TOPOLOGY_ROUTE_MODEL_TEST_ALIGNMENT,
                        TOPOLOGY_ROUTE_RISK_LEDGER,
                    ),
                    confidence_effect=effect,
                    severity=TOPOLOGY_SEVERITY_BLOCKER if effect == TOPOLOGY_CONFIDENCE_BLOCKED else TOPOLOGY_SEVERITY_CONFIDENCE_GAP,
                    metadata=landmark.metadata,
                )
            )
        elif landmark.landmark_type == TOPOLOGY_LANDMARK_BUSINESS_PATH_UNPROVEN:
            candidates.append(
                TopologyHazardCandidate(
                    f"hazard:business-path-unproven:{landmark.landmark_id}",
                    "A business path lacks source or runtime evidence binding.",
                    rationale="Path-sensitive confidence needs evidence for the specific useful path, not only for a nearby node or generic success state.",
                    future_failure_mode="The model reports success while only a different path has been exercised or inspected.",
                    topology_anchor_ids=landmark.anchor_ids,
                    source_landmark_ids=(landmark.landmark_id,),
                    disposition=TOPOLOGY_DISPOSITION_TEST_REQUIRED,
                    required_routes=(TOPOLOGY_ROUTE_MODEL_TEST_ALIGNMENT, TOPOLOGY_ROUTE_RISK_LEDGER),
                    confidence_effect=TOPOLOGY_CONFIDENCE_BLOCKED if broad else TOPOLOGY_CONFIDENCE_SCOPED,
                    severity=TOPOLOGY_SEVERITY_BLOCKER if broad else TOPOLOGY_SEVERITY_CONFIDENCE_GAP,
                    metadata=landmark.metadata,
                )
            )
        elif landmark.landmark_type == TOPOLOGY_LANDMARK_BUSINESS_PATH_LEGACY_DISPOSITION:
            candidates.append(
                TopologyHazardCandidate(
                    f"hazard:business-path-legacy:{landmark.landmark_id}",
                    "An old/new business path relationship lacks an explicit disposition.",
                    rationale="Replacement paths must say whether old paths are deleted, blocked, migrated, delegated, or preserved for compatibility.",
                    future_failure_mode="An old path stays reachable without evidence, or a deleted path is still assumed by users, artifacts, or tests.",
                    topology_anchor_ids=landmark.anchor_ids,
                    source_landmark_ids=(landmark.landmark_id,),
                    disposition=TOPOLOGY_DISPOSITION_COMPATIBILITY_DECISION,
                    required_routes=(
                        TOPOLOGY_ROUTE_ARCHITECTURE_REDUCTION,
                        TOPOLOGY_ROUTE_DEVELOPMENT_PROCESS,
                        TOPOLOGY_ROUTE_RISK_LEDGER,
                    ),
                    confidence_effect=TOPOLOGY_CONFIDENCE_BLOCKED if broad else TOPOLOGY_CONFIDENCE_SCOPED,
                    severity=TOPOLOGY_SEVERITY_BLOCKER if broad else TOPOLOGY_SEVERITY_CONFIDENCE_GAP,
                    metadata=landmark.metadata,
                )
            )
    return tuple(candidates)


def infer_topology_hazard_plan(
    *,
    workflow: Any,
    initial_states: Sequence[Any] = (),
    external_inputs: Sequence[Any] = (),
    usage_intent: UsageIntent | None = None,
    business_paths: Sequence[BusinessPathIdentity | Mapping[str, Any] | Any] = (),
    plan_id: str = "",
    candidates: Sequence[TopologyHazardCandidate] = (),
    final_claim: str = "",
) -> TopologyHazardReviewPlan:
    """Build a review plan from a workflow and optional supplied candidates."""

    digest = infer_topology_digest(
        workflow=workflow,
        initial_states=initial_states,
        external_inputs=external_inputs,
        usage_intent=usage_intent,
        business_paths=business_paths,
        digest_id=plan_id and f"{plan_id}:digest",
    )
    return TopologyHazardReviewPlan(
        plan_id=plan_id or "auto_topology_hazard_review",
        digest=digest,
        candidates=tuple(candidates),
        final_claim=final_claim or digest.usage_intent.final_claim,
    )


def review_topology_hazards(plan: TopologyHazardReviewPlan) -> TopologyHazardReport:
    """Review topology-anchored future-use hazard candidates."""

    candidates = plan.candidates
    if not candidates and plan.auto_generate_candidates:
        candidates = derive_topology_hazard_candidates(plan.digest)

    findings: list[TopologyHazardFinding] = []
    unresolved: list[str] = []
    anchor_set = set(plan.digest.anchor_ids())
    for candidate in candidates:
        known_anchors = tuple(anchor for anchor in candidate.topology_anchor_ids if anchor in anchor_set)
        missing_anchors = tuple(anchor for anchor in candidate.topology_anchor_ids if anchor not in anchor_set)
        if candidate.hard_disposition() and not candidate.anchored():
            findings.append(
                TopologyHazardFinding(
                    "unanchored_hazard_observation_only",
                    "hazard candidate has no topology anchor and cannot act as a hard gate",
                    severity=TOPOLOGY_SEVERITY_INFO,
                    hazard_id=candidate.hazard_id,
                    action="bind the risk to a model state, edge, side effect, terminal, legacy path, or external boundary before requiring work",
                )
            )
            continue
        if missing_anchors:
            findings.append(
                TopologyHazardFinding(
                    "unknown_topology_anchor",
                    "hazard references topology anchors not present in the digest",
                    severity=TOPOLOGY_SEVERITY_BLOCKER,
                    hazard_id=candidate.hazard_id,
                    anchor_ids=missing_anchors,
                    action="refresh the digest or correct the hazard anchor ids",
                )
            )
            unresolved.append(candidate.hazard_id)
            continue
        if candidate.disposition == TOPOLOGY_DISPOSITION_OBSERVATION:
            continue
        if candidate.disposition == TOPOLOGY_DISPOSITION_SCOPED_OUT:
            if candidate.scoped_reason:
                findings.append(
                    TopologyHazardFinding(
                        "topology_hazard_scoped_out",
                        candidate.scoped_reason,
                        severity=TOPOLOGY_SEVERITY_CONFIDENCE_GAP,
                        hazard_id=candidate.hazard_id,
                        anchor_ids=known_anchors,
                        required_routes=candidate.required_routes,
                    )
                )
            else:
                findings.append(
                    TopologyHazardFinding(
                        "topology_hazard_scoped_out_without_reason",
                        "anchored topology hazard was scoped out without a concrete reason",
                        severity=TOPOLOGY_SEVERITY_BLOCKER,
                        hazard_id=candidate.hazard_id,
                        anchor_ids=known_anchors,
                    )
                )
                unresolved.append(candidate.hazard_id)
            continue
        if candidate.handled:
            continue
        severity = (
            TOPOLOGY_SEVERITY_BLOCKER
            if candidate.confidence_effect == TOPOLOGY_CONFIDENCE_BLOCKED
            or candidate.disposition == TOPOLOGY_DISPOSITION_BLOCKED
            or candidate.severity == TOPOLOGY_SEVERITY_BLOCKER
            else TOPOLOGY_SEVERITY_CONFIDENCE_GAP
        )
        findings.append(
            TopologyHazardFinding(
                "topology_hazard_unresolved",
                candidate.summary,
                severity=severity,
                hazard_id=candidate.hazard_id,
                anchor_ids=known_anchors or candidate.source_landmark_ids,
                required_routes=candidate.required_routes,
                action=f"resolve disposition {candidate.disposition}",
                metadata={
                    "future_failure_mode": candidate.future_failure_mode,
                    "rationale": candidate.rationale,
                    "confidence_effect": candidate.confidence_effect,
                },
            )
        )
        unresolved.append(candidate.hazard_id)

    blockers = tuple(finding for finding in findings if finding.severity == TOPOLOGY_SEVERITY_BLOCKER)
    gaps = tuple(finding for finding in findings if finding.severity == TOPOLOGY_SEVERITY_CONFIDENCE_GAP)
    if blockers:
        decision = TOPOLOGY_DECISION_BLOCKED
        confidence = TOPOLOGY_CONFIDENCE_BLOCKED
        ok = False
        summary = "Topology-anchored future-use hazards remain blocked."
    elif gaps:
        decision = TOPOLOGY_DECISION_SCOPED
        confidence = TOPOLOGY_CONFIDENCE_SCOPED
        ok = plan.allow_scoped_confidence
        summary = "Topology-anchored future-use hazards remain scoped."
    else:
        decision = TOPOLOGY_DECISION_PASS
        confidence = TOPOLOGY_CONFIDENCE_FULL
        ok = True
        summary = "No unresolved topology-anchored future-use hazards."
    return TopologyHazardReport(
        ok=ok,
        plan_id=plan.plan_id,
        decision=decision,
        confidence=confidence,
        digest=plan.digest,
        candidates=tuple(candidates),
        findings=tuple(findings),
        unresolved_hazard_ids=_unique(unresolved),
        summary=summary,
    )


__all__ = [
    "TOPOLOGY_COMPAT_BLOCK",
    "TOPOLOGY_COMPAT_DELETE",
    "TOPOLOGY_COMPAT_LATEST_SCHEMA_FIRST",
    "TOPOLOGY_COMPAT_MIGRATE",
    "TOPOLOGY_COMPAT_PRESERVE",
    "TOPOLOGY_COMPAT_SCOPED_OUT",
    "TOPOLOGY_COMPAT_UNKNOWN",
    "TOPOLOGY_CONFIDENCE_BLOCKED",
    "TOPOLOGY_CONFIDENCE_FULL",
    "TOPOLOGY_CONFIDENCE_OBSERVATION",
    "TOPOLOGY_CONFIDENCE_SCOPED",
    "TOPOLOGY_DECISION_BLOCKED",
    "TOPOLOGY_DECISION_PASS",
    "TOPOLOGY_DECISION_SCOPED",
    "TOPOLOGY_DISPOSITION_BLOCKED",
    "TOPOLOGY_DISPOSITION_COMPATIBILITY_DECISION",
    "TOPOLOGY_DISPOSITION_DEVELOPMENT_PROCESS",
    "TOPOLOGY_DISPOSITION_LEDGER_REQUIRED",
    "TOPOLOGY_DISPOSITION_MODEL_MATURATION",
    "TOPOLOGY_DISPOSITION_MODEL_PATCH",
    "TOPOLOGY_DISPOSITION_OBSERVATION",
    "TOPOLOGY_DISPOSITION_SCOPED_OUT",
    "TOPOLOGY_DISPOSITION_TEST_REQUIRED",
    "TOPOLOGY_EDGE_EXTERNAL_BOUNDARY",
    "TOPOLOGY_EDGE_LEGACY_PATH",
    "TOPOLOGY_EDGE_SIDE_EFFECT",
    "TOPOLOGY_EDGE_STATE_WRITE",
    "TOPOLOGY_EDGE_WORKFLOW",
    "TOPOLOGY_LANDMARK_BUSINESS_PATH_CONFLICT",
    "TOPOLOGY_LANDMARK_BUSINESS_PATH_DUPLICATE",
    "TOPOLOGY_LANDMARK_BUSINESS_PATH_LEGACY_DISPOSITION",
    "TOPOLOGY_LANDMARK_BUSINESS_PATH_UNPROVEN",
    "TOPOLOGY_LANDMARK_COARSE_TERMINAL",
    "TOPOLOGY_LANDMARK_EXTERNAL_CONFIRMATION",
    "TOPOLOGY_LANDMARK_LEGACY_COMPATIBILITY",
    "TOPOLOGY_LANDMARK_PARENT_CHILD_COMPRESSION",
    "TOPOLOGY_LANDMARK_SHARED_WRITER",
    "TOPOLOGY_LANDMARK_SIDE_EFFECT_REPEAT",
    "TOPOLOGY_NODE_BUSINESS_PATH",
    "TOPOLOGY_NODE_BLOCK",
    "TOPOLOGY_NODE_INPUT",
    "TOPOLOGY_NODE_OUTPUT",
    "TOPOLOGY_NODE_STATE",
    "TOPOLOGY_NODE_USAGE",
    "TOPOLOGY_ROUTE_ARCHITECTURE_REDUCTION",
    "TOPOLOGY_ROUTE_DEVELOPMENT_PROCESS",
    "TOPOLOGY_ROUTE_MODEL_MATURATION",
    "TOPOLOGY_ROUTE_MODEL_SIMILARITY",
    "TOPOLOGY_ROUTE_MODEL_TEST_ALIGNMENT",
    "TOPOLOGY_ROUTE_RISK_LEDGER",
    "TOPOLOGY_SEVERITY_BLOCKER",
    "TOPOLOGY_SEVERITY_CONFIDENCE_GAP",
    "TOPOLOGY_SEVERITY_INFO",
    "TOPOLOGY_USAGE_CLI",
    "TOPOLOGY_USAGE_LIBRARY",
    "TOPOLOGY_USAGE_LOCAL",
    "TOPOLOGY_USAGE_MIGRATION",
    "TOPOLOGY_USAGE_PLUGIN",
    "TOPOLOGY_USAGE_RELEASE",
    "TOPOLOGY_USAGE_SERVICE",
    "TOPOLOGY_USAGE_UNKNOWN",
    "BusinessPathIdentity",
    "TopologyDigest",
    "TopologyEdge",
    "TopologyHazardCandidate",
    "TopologyHazardFinding",
    "TopologyHazardReport",
    "TopologyHazardReviewPlan",
    "TopologyLandmark",
    "TopologyNode",
    "UsageIntent",
    "derive_topology_hazard_candidates",
    "infer_topology_digest",
    "infer_topology_hazard_plan",
    "infer_usage_intent",
    "review_topology_hazards",
]
