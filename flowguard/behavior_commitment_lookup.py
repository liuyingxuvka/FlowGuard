"""Deterministic, plane-first lookup over the canonical behavior ledger.

This module is an internal service of the existing Behavior Commitment Ledger
and Existing Model Preflight routes.  It does not execute commitments and does
not create a new FlowGuard route.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .behavior_commitment import (
    BCL_BEHAVIOR_PLANES,
    BCL_HIT_ROLE_EVIDENCE_SOURCE,
    BCL_HIT_ROLE_GOVERNING_PROCESS,
    BCL_HIT_ROLE_INVOKED_TARGET,
    BCL_HIT_ROLE_PRIMARY,
    BCL_HIT_ROLE_VALIDATION_TARGET,
    BCL_LOOKUP_STATUS_BLOCKED,
    BCL_LOOKUP_STATUS_PERFORMED,
    BCL_PLANE_AGENT_OPERATION,
    BCL_PLANE_DEVELOPMENT_PROCESS,
    BCL_PLANE_PRODUCT_RUNTIME,
    BCL_RELATION_GOVERNS,
    BCL_RELATION_INVOKES,
    BCL_RELATION_REQUIRES_EVIDENCE_FROM,
    BCL_RELATION_VALIDATES,
    BehaviorCommitment,
    BehaviorCommitmentLedger,
    behavior_commitment_ledger_fingerprint,
    behavior_commitment_ledger_from_mapping,
    load_behavior_commitment_ledger,
)
from .export import to_jsonable


_TOKEN_PATTERN = re.compile(r"[\w:./-]+", re.UNICODE)
_PLANE_HINTS = {
    BCL_PLANE_PRODUCT_RUNTIME: {
        "product_runtime",
        "application",
        "end_user",
        "user_visible",
        "public_api",
        "runtime_behavior",
    },
    BCL_PLANE_AGENT_OPERATION: {
        "agent_operation",
        "ai_agent",
        "codex",
        "tool_call",
        "port_bridge",
        "health_check",
        "agent_workflow",
    },
    BCL_PLANE_DEVELOPMENT_PROCESS: {
        "development_process",
        "release_process",
        "validation_process",
        "project_upgrade",
        "install_parity",
        "development_workflow",
    },
}


def _as_tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values if str(value))


def _tokens(*values: str) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        lowered = str(value).strip().lower().replace("\\", "/")
        for token in _TOKEN_PATTERN.findall(lowered):
            variants = (token,) + tuple(part for part in re.split(r"[:./-]+", token) if part)
            for variant in variants:
                if variant and variant not in seen:
                    seen.add(variant)
                    result.append(variant)
    return tuple(result)


def _contains_normalized(haystack: str, needle: str) -> bool:
    normalized_haystack = str(haystack).lower().replace("\\", "/")
    normalized_needle = str(needle).lower().replace("\\", "/").strip()
    return bool(normalized_needle and normalized_needle in normalized_haystack)


@dataclass(frozen=True)
class BehaviorLookupQuery:
    """One bounded task-time lookup request."""

    task_summary: str = ""
    primary_plane: str = ""
    canonical_terms: tuple[str, ...] = ()
    changed_paths: tuple[str, ...] = ()
    tool_ids: tuple[str, ...] = ()
    error_signatures: tuple[str, ...] = ()
    workflow_families: tuple[str, ...] = ()
    top_k: int = 5

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_summary", str(self.task_summary))
        object.__setattr__(self, "primary_plane", str(self.primary_plane))
        object.__setattr__(self, "canonical_terms", _as_tuple(self.canonical_terms))
        object.__setattr__(self, "changed_paths", _as_tuple(self.changed_paths))
        object.__setattr__(self, "tool_ids", _as_tuple(self.tool_ids))
        object.__setattr__(self, "error_signatures", _as_tuple(self.error_signatures))
        object.__setattr__(self, "workflow_families", _as_tuple(self.workflow_families))
        object.__setattr__(self, "top_k", max(1, min(int(self.top_k or 5), 50)))

    def query_tokens(self) -> tuple[str, ...]:
        return _tokens(self.task_summary, *self.canonical_terms, *self.workflow_families)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_summary": self.task_summary,
            "primary_plane": self.primary_plane,
            "canonical_terms": list(self.canonical_terms),
            "changed_paths": list(self.changed_paths),
            "tool_ids": list(self.tool_ids),
            "error_signatures": list(self.error_signatures),
            "workflow_families": list(self.workflow_families),
            "top_k": self.top_k,
        }


@dataclass(frozen=True)
class BehaviorCommitmentHit:
    """One explainable primary, candidate, or typed-related commitment hit."""

    commitment_id: str
    behavior_plane: str
    primary_owner_model_id: str
    score: int
    match_reasons: tuple[str, ...] = ()
    hit_role: str = BCL_HIT_ROLE_PRIMARY
    relation_type: str = ""
    relation_path: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "commitment_id", str(self.commitment_id))
        object.__setattr__(self, "behavior_plane", str(self.behavior_plane))
        object.__setattr__(self, "primary_owner_model_id", str(self.primary_owner_model_id))
        object.__setattr__(self, "score", int(self.score))
        object.__setattr__(self, "match_reasons", _as_tuple(self.match_reasons))
        object.__setattr__(self, "hit_role", str(self.hit_role))
        object.__setattr__(self, "relation_type", str(self.relation_type))
        object.__setattr__(self, "relation_path", _as_tuple(self.relation_path))

    def to_dict(self) -> dict[str, Any]:
        return {
            "commitment_id": self.commitment_id,
            "behavior_plane": self.behavior_plane,
            "primary_owner_model_id": self.primary_owner_model_id,
            "score": self.score,
            "match_reasons": list(self.match_reasons),
            "hit_role": self.hit_role,
            "relation_type": self.relation_type,
            "relation_path": list(self.relation_path),
        }


@dataclass(frozen=True)
class BehaviorLookupReport:
    """Plane-first lookup result consumed by Existing Model Preflight."""

    status: str
    selected_plane: str = ""
    plane_candidates: tuple[str, ...] = ()
    primary_hits: tuple[BehaviorCommitmentHit, ...] = ()
    related_hits: tuple[BehaviorCommitmentHit, ...] = ()
    candidate_hits: tuple[BehaviorCommitmentHit, ...] = ()
    plane_ambiguity: bool = False
    ledger_fingerprint: str = ""
    status_reason: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "selected_plane", str(self.selected_plane))
        object.__setattr__(self, "plane_candidates", _as_tuple(self.plane_candidates))
        object.__setattr__(self, "primary_hits", tuple(self.primary_hits))
        object.__setattr__(self, "related_hits", tuple(self.related_hits))
        object.__setattr__(self, "candidate_hits", tuple(self.candidate_hits))
        object.__setattr__(self, "status_reason", str(self.status_reason))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def ok(self) -> bool:
        return self.status == BCL_LOOKUP_STATUS_PERFORMED and not self.plane_ambiguity

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_behavior_commitment_lookup_report",
            "status": self.status,
            "selected_plane": self.selected_plane,
            "plane_candidates": list(self.plane_candidates),
            "primary_hits": [hit.to_dict() for hit in self.primary_hits],
            "related_hits": [hit.to_dict() for hit in self.related_hits],
            "candidate_hits": [hit.to_dict() for hit in self.candidate_hits],
            "plane_ambiguity": self.plane_ambiguity,
            "ledger_fingerprint": self.ledger_fingerprint,
            "status_reason": self.status_reason,
            "metadata": to_jsonable(dict(self.metadata)),
        }

    def format_text(self) -> str:
        lines = [
            "=== flowguard behavior commitment lookup ===",
            f"status: {self.status}",
            f"selected_plane: {self.selected_plane or '(none)'}",
            f"plane_ambiguity: {self.plane_ambiguity}",
            f"ledger_fingerprint: {self.ledger_fingerprint or '(none)'}",
        ]
        if self.status_reason:
            lines.append(f"status_reason: {self.status_reason}")
        for heading, hits in (
            ("primary_hits", self.primary_hits),
            ("related_hits", self.related_hits),
            ("candidate_hits", self.candidate_hits),
        ):
            lines.append(f"{heading}: {len(hits)}")
            for hit in hits:
                lines.append(
                    "  - "
                    f"{hit.commitment_id} plane={hit.behavior_plane} "
                    f"role={hit.hit_role} score={hit.score} "
                    f"reasons={','.join(hit.match_reasons) or '(none)'}"
                )
        return "\n".join(lines)


def _score_commitment(
    commitment: BehaviorCommitment,
    query: BehaviorLookupQuery,
) -> tuple[int, tuple[str, ...]]:
    binding = commitment.lookup_binding
    query_tokens = set(query.query_tokens())
    task_text = " ".join(
        (query.task_summary, *query.canonical_terms, *query.error_signatures, *query.tool_ids)
    )
    score = 0
    reasons: list[str] = []

    commitment_id_tokens = set(_tokens(commitment.commitment_id))
    if commitment.commitment_id.lower() in {term.lower() for term in query.canonical_terms}:
        score += 120
        reasons.append("exact_commitment_id")
    elif query_tokens & commitment_id_tokens:
        score += 25
        reasons.append("commitment_id_token")

    for signature in binding.error_signatures:
        if any(_contains_normalized(value, signature) for value in (*query.error_signatures, task_text)):
            score += 100
            reasons.append(f"error_signature:{signature}")
            break
    for tool_id in binding.tool_ids:
        if tool_id.lower() in {value.lower() for value in query.tool_ids} or _contains_normalized(task_text, tool_id):
            score += 90
            reasons.append(f"tool_id:{tool_id}")
            break
    for pattern in binding.path_patterns:
        if any(_contains_normalized(path, pattern) or _contains_normalized(pattern, path) for path in query.changed_paths):
            score += 80
            reasons.append(f"path_pattern:{pattern}")
            break
    for family in binding.workflow_families:
        if family.lower() in {value.lower() for value in query.workflow_families} or family.lower() in query_tokens:
            score += 70
            reasons.append(f"workflow_family:{family}")
            break

    binding_terms = set(_tokens(*binding.task_terms))
    term_matches = sorted(query_tokens & binding_terms)
    if term_matches:
        score += 45 + min(20, 5 * (len(term_matches) - 1))
        reasons.extend(f"task_term:{term}" for term in term_matches)

    descriptive_tokens = set(
        _tokens(
            commitment.label,
            commitment.trigger,
            commitment.expected_result,
            commitment.failure_boundary,
            *commitment.source_refs,
        )
    )
    text_matches = sorted(query_tokens & descriptive_tokens)
    if text_matches:
        score += min(30, 5 * len(text_matches))
        reasons.extend(f"commitment_text:{term}" for term in text_matches[:6])
    return score, tuple(dict.fromkeys(reasons))


def _explicit_plane(query: BehaviorLookupQuery) -> tuple[str, tuple[str, ...]]:
    if query.primary_plane:
        return (
            (query.primary_plane, (query.primary_plane,))
            if query.primary_plane in BCL_BEHAVIOR_PLANES
            else ("", ())
        )
    tokens = set(query.query_tokens())
    candidates = tuple(
        plane for plane, hints in _PLANE_HINTS.items() if tokens & hints
    )
    return (candidates[0], candidates) if len(candidates) == 1 else ("", candidates)


def _ranked_hits(
    ledger: BehaviorCommitmentLedger,
    query: BehaviorLookupQuery,
) -> tuple[BehaviorCommitmentHit, ...]:
    hits: list[BehaviorCommitmentHit] = []
    for commitment in ledger.commitments:
        if not commitment.in_scope or commitment.behavior_plane not in BCL_BEHAVIOR_PLANES:
            continue
        score, reasons = _score_commitment(commitment, query)
        if score <= 0:
            continue
        hits.append(
            BehaviorCommitmentHit(
                commitment.commitment_id,
                commitment.behavior_plane,
                commitment.primary_owner_model_id,
                score,
                reasons,
            )
        )
    return tuple(sorted(hits, key=lambda hit: (-hit.score, hit.commitment_id)))


def _select_plane(
    query: BehaviorLookupQuery,
    ranked: Sequence[BehaviorCommitmentHit],
) -> tuple[str, tuple[str, ...], bool]:
    explicit, explicit_candidates = _explicit_plane(query)
    if query.primary_plane and not explicit:
        return "", (), True
    if explicit:
        return explicit, explicit_candidates, False
    if len(explicit_candidates) > 1:
        return "", explicit_candidates, True
    if not ranked:
        return "", (), False
    best_by_plane: dict[str, int] = {}
    for hit in ranked:
        best_by_plane[hit.behavior_plane] = max(best_by_plane.get(hit.behavior_plane, 0), hit.score)
    ordered = sorted(best_by_plane.items(), key=lambda item: (-item[1], item[0]))
    best_score = ordered[0][1]
    tied = tuple(plane for plane, score in ordered if score == best_score)
    if len(tied) != 1:
        return "", tied, True
    # A single shared noun can also appear in one commitment id and create a
    # small artificial lead.  Keep that case ambiguous: plane selection must
    # come from explicit task context or materially stronger structured clues,
    # not from an identifier-token tie breaker.
    if len(ordered) > 1 and best_score - ordered[1][1] <= 25:
        return "", tuple(plane for plane, _score in ordered), True
    return ordered[0][0], (ordered[0][0],), False


def _related_role(relation_type: str, *, incoming: bool, source_plane: str) -> str:
    if incoming and source_plane == BCL_PLANE_DEVELOPMENT_PROCESS:
        return BCL_HIT_ROLE_GOVERNING_PROCESS
    if relation_type == BCL_RELATION_INVOKES:
        return BCL_HIT_ROLE_INVOKED_TARGET if not incoming else BCL_HIT_ROLE_EVIDENCE_SOURCE
    if relation_type == BCL_RELATION_VALIDATES:
        return BCL_HIT_ROLE_VALIDATION_TARGET if not incoming else BCL_HIT_ROLE_EVIDENCE_SOURCE
    if relation_type == BCL_RELATION_GOVERNS:
        return BCL_HIT_ROLE_GOVERNING_PROCESS if incoming else BCL_HIT_ROLE_VALIDATION_TARGET
    if relation_type == BCL_RELATION_REQUIRES_EVIDENCE_FROM:
        return BCL_HIT_ROLE_EVIDENCE_SOURCE
    return BCL_HIT_ROLE_EVIDENCE_SOURCE


def _related_hits(
    ledger: BehaviorCommitmentLedger,
    primary_hits: Sequence[BehaviorCommitmentHit],
    *,
    top_k: int,
) -> tuple[BehaviorCommitmentHit, ...]:
    by_id = {commitment.commitment_id: commitment for commitment in ledger.commitments}
    primary_ids = {hit.commitment_id for hit in primary_hits}
    best: dict[tuple[str, str], BehaviorCommitmentHit] = {}
    for primary in primary_hits:
        source = by_id.get(primary.commitment_id)
        if source is None:
            continue
        for relation in source.relations:
            target = by_id.get(relation.target_commitment_id)
            if target is None or target.commitment_id in primary_ids or target.behavior_plane == source.behavior_plane:
                continue
            hit = BehaviorCommitmentHit(
                target.commitment_id,
                target.behavior_plane,
                target.primary_owner_model_id,
                primary.score,
                (f"outgoing_relation:{relation.relation_type}",),
                _related_role(relation.relation_type, incoming=False, source_plane=source.behavior_plane),
                relation.relation_type,
                (source.commitment_id, target.commitment_id),
            )
            best[(hit.commitment_id, hit.hit_role)] = hit
        for candidate in ledger.commitments:
            if candidate.commitment_id in primary_ids or candidate.behavior_plane == source.behavior_plane:
                continue
            for relation in candidate.relations:
                if relation.target_commitment_id != source.commitment_id:
                    continue
                hit = BehaviorCommitmentHit(
                    candidate.commitment_id,
                    candidate.behavior_plane,
                    candidate.primary_owner_model_id,
                    primary.score,
                    (f"incoming_relation:{relation.relation_type}",),
                    _related_role(relation.relation_type, incoming=True, source_plane=candidate.behavior_plane),
                    relation.relation_type,
                    (candidate.commitment_id, source.commitment_id),
                )
                best[(hit.commitment_id, hit.hit_role)] = hit
    return tuple(sorted(best.values(), key=lambda hit: (-hit.score, hit.hit_role, hit.commitment_id))[:top_k])


def query_behavior_commitments(
    ledger: BehaviorCommitmentLedger | Mapping[str, Any],
    query: BehaviorLookupQuery | Mapping[str, Any],
) -> BehaviorLookupReport:
    """Query the ledger without executing any commitment or model."""

    normalized_ledger = behavior_commitment_ledger_from_mapping(ledger)
    normalized_query = query if isinstance(query, BehaviorLookupQuery) else BehaviorLookupQuery(**dict(query))
    fingerprint = behavior_commitment_ledger_fingerprint(normalized_ledger)
    ranked = _ranked_hits(normalized_ledger, normalized_query)
    selected_plane, plane_candidates, ambiguous = _select_plane(normalized_query, ranked)
    if ambiguous:
        candidate_hits = tuple(
            hit for hit in ranked if not plane_candidates or hit.behavior_plane in plane_candidates
        )[: normalized_query.top_k]
        return BehaviorLookupReport(
            BCL_LOOKUP_STATUS_PERFORMED,
            plane_candidates=plane_candidates,
            candidate_hits=candidate_hits,
            plane_ambiguity=True,
            ledger_fingerprint=fingerprint,
            status_reason="primary behavior plane is ambiguous",
        )
    primary_hits = tuple(
        hit for hit in ranked if not selected_plane or hit.behavior_plane == selected_plane
    )[: normalized_query.top_k]
    related = _related_hits(normalized_ledger, primary_hits, top_k=normalized_query.top_k)
    return BehaviorLookupReport(
        BCL_LOOKUP_STATUS_PERFORMED,
        selected_plane=selected_plane,
        plane_candidates=plane_candidates,
        primary_hits=primary_hits,
        related_hits=related,
        ledger_fingerprint=fingerprint,
    )


def query_behavior_commitments_from_path(
    path: str | Path,
    query: BehaviorLookupQuery | Mapping[str, Any],
) -> BehaviorLookupReport:
    """Load and query a canonical ledger, preserving load failure as status."""

    try:
        ledger = load_behavior_commitment_ledger(path)
        return query_behavior_commitments(ledger, query)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return BehaviorLookupReport(
            BCL_LOOKUP_STATUS_BLOCKED,
            status_reason=f"canonical behavior ledger unavailable: {type(exc).__name__}: {exc}",
            metadata={"ledger_path": str(path)},
        )


__all__ = [
    "BehaviorCommitmentHit",
    "BehaviorLookupQuery",
    "BehaviorLookupReport",
    "query_behavior_commitments",
    "query_behavior_commitments_from_path",
]
