"""Independent denominator for FlowGuard's read-only self-reduction review."""

from __future__ import annotations

import ast
import heapq
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from .evidence_receipts import fingerprint_value
from .architecture_reduction import (
    ARCHITECTURE_REDUCTION_STEP_ACTIONS,
    STEP_ACTION_UNRESOLVED,
)


SELF_REDUCTION_UNIVERSE_SCHEMA = "flowguard.self_reduction_universe.v4"
SELF_REDUCTION_RETAIN_DISPOSITION_SCHEMA = (
    "flowguard.self_reduction_retain_disposition.v3"
)
SELF_REDUCTION_CANDIDATE_BINDING_SCHEMA = (
    "flowguard.self_reduction_candidate_binding.v4"
)
SELF_REDUCTION_CURRENT_NECESSITY_WITNESS_SCHEMA = (
    "flowguard.self_reduction_current_necessity_witness.v4"
)
SELF_REDUCTION_DISPOSITIONS = frozenset({"retain", "contract", "unresolved"})
SELF_REDUCTION_RETAIN_BASES = frozenset(
    {
        "current_declared_authority",
        "current_necessity_witness",
        "current_owner_evidence",
        "different_current_semantics",
        "independent_validation_roles",
    }
)
_IMPLEMENTATION_MEMBER_KINDS = frozenset(
    {"implementation_surface", "public_entrypoint", "export"}
)
_REDUCTION_SIGNAL_KINDS = frozenset(
    {
        "adapter_signal",
        "branch_signal",
        "builder_signal",
        "command_route_signal",
        "helper_signal",
        "maintenance_name_signal",
        "oversized_boundary_signal",
        "repeated_shape_signal",
        "serialization_signal",
        "validation_signal",
        "wrapper_facade_signal",
    }
)


class SelfReductionUniverseError(ValueError):
    """Raised when the independent reduction denominator is malformed."""


@dataclass(frozen=True)
class SelfReductionCandidateBinding:
    """Content identity for one independently discovered contraction relation."""

    candidate_id: str
    signal: str
    member_ids: tuple[str, ...]
    source_signal_ids: tuple[str, ...]
    observable_contract_fingerprint: str
    caller_ids: tuple[str, ...] = ()
    public_entrypoint_ids: tuple[str, ...] = ()
    caller_resolution_gap_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("candidate_id", "signal", "observable_contract_fingerprint"):
            if not str(getattr(self, name, "")).strip():
                raise SelfReductionUniverseError(
                    f"candidate binding requires {name}"
                )
        for name in ("member_ids", "source_signal_ids"):
            values = tuple(
                sorted({str(value) for value in getattr(self, name) if str(value)})
            )
            if not values:
                raise SelfReductionUniverseError(
                    f"candidate binding requires {name}"
                )
            object.__setattr__(self, name, values)
        for name in ("caller_ids", "public_entrypoint_ids"):
            object.__setattr__(
                self,
                name,
                tuple(
                    sorted(
                        {
                            str(value)
                            for value in getattr(self, name)
                            if str(value)
                        }
                    )
                ),
            )
        if not set(self.public_entrypoint_ids) <= set(self.member_ids):
            raise SelfReductionUniverseError(
                "candidate public entrypoints must belong to its member set"
            )
        object.__setattr__(
            self,
            "caller_resolution_gap_ids",
            tuple(
                sorted(
                    {
                        str(value)
                        for value in self.caller_resolution_gap_ids
                        if str(value)
                    }
                )
            ),
        )

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SELF_REDUCTION_CANDIDATE_BINDING_SCHEMA,
            "candidate_id": self.candidate_id,
            "signal": self.signal,
            "member_ids": list(self.member_ids),
            "source_signal_ids": list(self.source_signal_ids),
            "observable_contract_fingerprint": (
                self.observable_contract_fingerprint
            ),
            "caller_ids": list(self.caller_ids),
            "public_entrypoint_ids": list(self.public_entrypoint_ids),
            "caller_resolution_gap_ids": list(
                self.caller_resolution_gap_ids
            ),
        }


@dataclass(frozen=True)
class SelfReductionCurrentNecessityWitness:
    """Direct-current reason one implementation surface still carries work."""

    witness_id: str
    subject_revision: str
    implementation_inventory_fingerprint: str
    test_inventory_fingerprint: str
    intent_inventory_fingerprint: str
    behavior_report_fingerprint: str
    binding_report_fingerprint: str
    member_id: str
    binding_kind: str
    behavior_block_id: str
    model_element_id: str
    owner_contract_id: str
    owner_id: str
    intent_contribution_ids: tuple[str, ...]
    intent_authority_fingerprints: tuple[str, ...]
    current_goal_rationales: tuple[str, ...]
    semantic_obligation_fingerprint: str
    semantic_dimensions: tuple[tuple[str, str], ...]
    caller_ids: tuple[str, ...]
    caller_inventory_complete: bool
    semantic_spec_ids: tuple[str, ...]
    oracle_ids: tuple[str, ...]
    behavior_case_ids: tuple[str, ...]
    coverage_ids: tuple[str, ...]
    test_node_ids: tuple[str, ...]
    model_validation_evidence_ids: tuple[str, ...]
    current_receipt_ids: tuple[str, ...]
    behavior_commitment_ids: tuple[str, ...] = ()
    bcl_review_fingerprint: str = ""
    path_quality_binding_fingerprint: str = ""
    supporting_relation_evidence_id: str = ""
    supporting_relation_fingerprint: str = ""
    evidence_fingerprints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "witness_id",
            "subject_revision",
            "implementation_inventory_fingerprint",
            "test_inventory_fingerprint",
            "intent_inventory_fingerprint",
            "behavior_report_fingerprint",
            "binding_report_fingerprint",
            "member_id",
            "binding_kind",
            "behavior_block_id",
            "model_element_id",
            "owner_contract_id",
            "owner_id",
            "semantic_obligation_fingerprint",
        ):
            if not str(getattr(self, name, "")).strip():
                raise SelfReductionUniverseError(
                    f"current necessity witness requires {name}"
                )
        if self.binding_kind not in {"direct_contract", "supporting_relation"}:
            raise SelfReductionUniverseError(
                "current necessity witness has an unknown binding kind"
            )
        for name in (
            "intent_contribution_ids",
            "intent_authority_fingerprints",
            "current_goal_rationales",
            "caller_ids",
            "semantic_spec_ids",
            "oracle_ids",
            "behavior_case_ids",
            "coverage_ids",
            "test_node_ids",
            "model_validation_evidence_ids",
            "current_receipt_ids",
            "behavior_commitment_ids",
            "evidence_fingerprints",
        ):
            values = tuple(
                sorted({str(value) for value in getattr(self, name) if str(value)})
            )
            object.__setattr__(self, name, values)
        if not (
            self.intent_contribution_ids
            and self.intent_authority_fingerprints
            and self.current_goal_rationales
            and self.semantic_spec_ids
            and self.oracle_ids
            and (
                self.test_node_ids
                or self.model_validation_evidence_ids
            )
            and self.evidence_fingerprints
        ):
            raise SelfReductionUniverseError(
                "current necessity witness lacks current intent, semantics, oracle, validation, or evidence"
            )
        semantic_dimensions = tuple(
            sorted(
                {
                    (str(dimension), str(value))
                    for dimension, value in self.semantic_dimensions
                    if str(dimension) and str(value)
                }
            )
        )
        if not semantic_dimensions:
            raise SelfReductionUniverseError(
                "current necessity witness requires source-independent semantics"
            )
        object.__setattr__(self, "semantic_dimensions", semantic_dimensions)
        object.__setattr__(
            self,
            "caller_inventory_complete",
            bool(self.caller_inventory_complete),
        )
        if self.binding_kind == "supporting_relation":
            if not (
                self.supporting_relation_evidence_id
                and self.supporting_relation_fingerprint
            ):
                raise SelfReductionUniverseError(
                    "supporting necessity witness requires exact relation evidence"
                )
        elif self.supporting_relation_evidence_id or self.supporting_relation_fingerprint:
            raise SelfReductionUniverseError(
                "direct necessity witness cannot carry supporting-relation evidence"
            )
        if bool(self.behavior_commitment_ids) != bool(self.bcl_review_fingerprint):
            raise SelfReductionUniverseError(
                "external commitment ids and current BCL review must be present together"
            )
        if self.path_quality_binding_fingerprint and not (
            self.path_quality_binding_fingerprint.startswith("sha256:")
        ):
            raise SelfReductionUniverseError(
                "current necessity witness path-quality identity must be canonical"
            )

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SELF_REDUCTION_CURRENT_NECESSITY_WITNESS_SCHEMA,
            "witness_id": self.witness_id,
            "subject_revision": self.subject_revision,
            "implementation_inventory_fingerprint": self.implementation_inventory_fingerprint,
            "test_inventory_fingerprint": self.test_inventory_fingerprint,
            "intent_inventory_fingerprint": self.intent_inventory_fingerprint,
            "behavior_report_fingerprint": self.behavior_report_fingerprint,
            "binding_report_fingerprint": self.binding_report_fingerprint,
            "member_id": self.member_id,
            "binding_kind": self.binding_kind,
            "behavior_block_id": self.behavior_block_id,
            "model_element_id": self.model_element_id,
            "owner_contract_id": self.owner_contract_id,
            "owner_id": self.owner_id,
            "intent_contribution_ids": list(self.intent_contribution_ids),
            "intent_authority_fingerprints": list(
                self.intent_authority_fingerprints
            ),
            "current_goal_rationales": list(self.current_goal_rationales),
            "semantic_obligation_fingerprint": self.semantic_obligation_fingerprint,
            "semantic_dimensions": dict(self.semantic_dimensions),
            "caller_ids": list(self.caller_ids),
            "caller_inventory_complete": self.caller_inventory_complete,
            "semantic_spec_ids": list(self.semantic_spec_ids),
            "oracle_ids": list(self.oracle_ids),
            "behavior_case_ids": list(self.behavior_case_ids),
            "coverage_ids": list(self.coverage_ids),
            "test_node_ids": list(self.test_node_ids),
            "model_validation_evidence_ids": list(
                self.model_validation_evidence_ids
            ),
            "current_receipt_ids": list(self.current_receipt_ids),
            "behavior_commitment_ids": list(self.behavior_commitment_ids),
            "bcl_review_fingerprint": self.bcl_review_fingerprint,
            "path_quality_binding_fingerprint": (
                self.path_quality_binding_fingerprint
            ),
            "supporting_relation_evidence_id": self.supporting_relation_evidence_id,
            "supporting_relation_fingerprint": self.supporting_relation_fingerprint,
            "evidence_fingerprints": list(self.evidence_fingerprints),
        }


@dataclass(frozen=True)
class SelfReductionRetainDisposition:
    """One typed retain decision derived from current facts outside candidate scan."""

    disposition_id: str
    subject_revision: str
    implementation_inventory_fingerprint: str
    test_inventory_fingerprint: str
    universe_fingerprint: str
    member_ids: tuple[str, ...]
    basis: str
    owner_refs: tuple[str, ...]
    evidence_fingerprints: tuple[str, ...]
    rationale: str
    candidate_ids: tuple[str, ...] = ()
    member_owner_bindings: tuple[tuple[str, str], ...] = ()
    necessity_witnesses: tuple[SelfReductionCurrentNecessityWitness, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "disposition_id",
            "subject_revision",
            "implementation_inventory_fingerprint",
            "test_inventory_fingerprint",
            "universe_fingerprint",
            "rationale",
        ):
            if not str(getattr(self, name, "")).strip():
                raise SelfReductionUniverseError(
                    f"retain disposition requires {name}"
                )
        if self.basis not in SELF_REDUCTION_RETAIN_BASES:
            raise SelfReductionUniverseError(
                f"unknown retain disposition basis: {self.basis}"
            )
        for name in ("member_ids", "owner_refs", "evidence_fingerprints"):
            values = tuple(
                sorted({str(value) for value in getattr(self, name) if str(value)})
            )
            if not values:
                raise SelfReductionUniverseError(
                    f"retain disposition requires {name}"
            )
            object.__setattr__(self, name, values)
        candidate_ids = tuple(
            sorted({str(value) for value in self.candidate_ids if str(value)})
        )
        object.__setattr__(self, "candidate_ids", candidate_ids)
        member_owner_bindings = tuple(
            sorted(
                {
                    (str(member_id), str(owner_id))
                    for member_id, owner_id in self.member_owner_bindings
                    if str(member_id) and str(owner_id)
                }
            )
        )
        object.__setattr__(
            self,
            "member_owner_bindings",
            member_owner_bindings,
        )
        witnesses = tuple(
            sorted(self.necessity_witnesses, key=lambda row: row.member_id)
        )
        if any(
            not isinstance(row, SelfReductionCurrentNecessityWitness)
            for row in witnesses
        ):
            raise SelfReductionUniverseError(
                "retain disposition necessity witnesses must use the current typed format"
            )
        if len({row.member_id for row in witnesses}) != len(witnesses):
            raise SelfReductionUniverseError(
                "retain disposition duplicates a current necessity witness"
            )
        object.__setattr__(self, "necessity_witnesses", witnesses)
        if self.basis in {
            "current_necessity_witness",
            "different_current_semantics",
            "independent_validation_roles",
        }:
            if {row.member_id for row in witnesses} != set(self.member_ids):
                raise SelfReductionUniverseError(
                    "necessity-backed retain disposition requires one witness per member"
                )
            if {member_id for member_id, _ in member_owner_bindings} != set(
                self.member_ids
            ):
                raise SelfReductionUniverseError(
                    "necessity-backed retain disposition requires one current owner per member"
                )
        if self.basis in {
            "different_current_semantics",
            "independent_validation_roles",
        }:
            if not candidate_ids:
                raise SelfReductionUniverseError(
                    "candidate-level retain disposition requires candidate ids"
                )
            if set(candidate_ids) & set(self.owner_refs):
                raise SelfReductionUniverseError(
                    "candidate identity cannot act as retain authority"
                )
        if self.basis == "different_current_semantics":
            semantic_fingerprints = tuple(
                row.semantic_obligation_fingerprint for row in witnesses
            )
            if len(set(semantic_fingerprints)) != len(semantic_fingerprints):
                raise SelfReductionUniverseError(
                    "different-semantics retain disposition contains repeated semantics"
                )
        elif self.basis == "independent_validation_roles":
            if len(self.member_ids) != 2:
                raise SelfReductionUniverseError(
                    "independent validation retention requires one model/checker pair"
                )
        elif self.basis == "current_necessity_witness":
            if candidate_ids:
                raise SelfReductionUniverseError(
                    "member necessity retain disposition cannot depend on a candidate"
                )
        elif candidate_ids or member_owner_bindings or witnesses:
            raise SelfReductionUniverseError(
                "candidate and witness bindings require a necessity-backed retain disposition"
            )

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SELF_REDUCTION_RETAIN_DISPOSITION_SCHEMA,
            "disposition_id": self.disposition_id,
            "subject_revision": self.subject_revision,
            "implementation_inventory_fingerprint": (
                self.implementation_inventory_fingerprint
            ),
            "test_inventory_fingerprint": self.test_inventory_fingerprint,
            "universe_fingerprint": self.universe_fingerprint,
            "member_ids": list(self.member_ids),
            "basis": self.basis,
            "owner_refs": list(self.owner_refs),
            "evidence_fingerprints": list(self.evidence_fingerprints),
            "rationale": self.rationale,
            "candidate_ids": list(self.candidate_ids),
            "member_owner_bindings": [
                [member_id, owner_id]
                for member_id, owner_id in self.member_owner_bindings
            ],
            "necessity_witnesses": [
                row.to_dict() for row in self.necessity_witnesses
            ],
        }


def _namespace(prefix: str, value: Any) -> str:
    text = str(value)
    return text if text.startswith(prefix + ":") else f"{prefix}:{text}"


def _select_containing_surfaces(
    *,
    surfaces: tuple[Any, ...],
    queried_lines_by_path: dict[str, set[int]],
) -> dict[tuple[str, int], Any]:
    """Resolve many syntax sites to their narrowest current surface in one pass."""

    intervals_by_path: dict[str, list[tuple[int, int, str, int, Any]]] = {}
    for ordinal, surface in enumerate(surfaces):
        path = str(getattr(surface, "path", ""))
        if path not in queried_lines_by_path:
            continue
        line_start = int(getattr(surface, "line_start", 0))
        line_end = int(getattr(surface, "line_end", 0))
        if str(getattr(surface, "surface_kind", "")) in {"file", "module"}:
            # Python's ``ast.Module`` has no native ``end_lineno``.  The
            # implementation inventory therefore records its declaration at
            # line one, while its semantic scope is the complete file.  Use
            # the already-frozen query denominator to extend only this
            # containment projection; nested class/function surfaces still
            # win because the selector chooses the narrowest interval.
            line_start = 1
            line_end = max(
                line_end,
                max(queried_lines_by_path[path], default=1),
            )
        intervals_by_path.setdefault(path, []).append(
            (
                line_start,
                line_end,
                str(getattr(surface, "surface_id", "")),
                ordinal,
                surface,
            )
        )

    selected: dict[tuple[str, int], Any] = {}
    for path, queried_lines in queried_lines_by_path.items():
        intervals = sorted(
            intervals_by_path.get(path, ()),
            key=lambda row: (row[0], row[1], row[2], row[3]),
        )
        active: list[tuple[int, str, int, int, Any]] = []
        interval_index = 0
        for line in sorted(queried_lines):
            while (
                interval_index < len(intervals)
                and intervals[interval_index][0] <= line
            ):
                line_start, line_end, surface_id, ordinal, surface = intervals[
                    interval_index
                ]
                heapq.heappush(
                    active,
                    (
                        line_end - line_start,
                        surface_id,
                        line_end,
                        ordinal,
                        surface,
                    ),
                )
                interval_index += 1
            while active and active[0][2] < line:
                heapq.heappop(active)
            if active:
                selected[(path, line)] = active[0][4]
    return selected


@dataclass(frozen=True)
class SelfReductionUniverseMember:
    member_id: str
    member_kind: str
    disposition: str
    rationale: str
    source_ref: str = ""
    evidence_fingerprints: tuple[str, ...] = ()
    path: str = ""
    symbol: str = ""
    signal_kinds: tuple[str, ...] = ()
    step_action: str = ""
    static_operation_count: int = 0
    analysis_payload_bytes: int = 0
    cost_source_ref: str = ""
    branch_count: int = 0
    branch_fingerprint: str = ""
    materialized_branch_site_ids: tuple[str, ...] = ()
    command_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.member_id or not self.member_kind or not self.rationale.strip():
            raise SelfReductionUniverseError(
                "reduction universe member identity is incomplete"
            )
        if self.disposition not in SELF_REDUCTION_DISPOSITIONS:
            raise SelfReductionUniverseError(
                f"unknown reduction disposition: {self.disposition}"
            )
        object.__setattr__(
            self,
            "evidence_fingerprints",
            tuple(
                sorted(
                    {
                        str(value)
                        for value in self.evidence_fingerprints
                        if str(value)
                    }
                )
            ),
        )
        signal_kinds = tuple(
            sorted({str(value) for value in self.signal_kinds if str(value)})
        )
        unknown_signal_kinds = set(signal_kinds) - _REDUCTION_SIGNAL_KINDS
        if unknown_signal_kinds:
            raise SelfReductionUniverseError(
                "unknown reduction signal kinds: "
                + ", ".join(sorted(unknown_signal_kinds))
            )
        object.__setattr__(self, "signal_kinds", signal_kinds)
        object.__setattr__(
            self,
            "materialized_branch_site_ids",
            tuple(
                sorted(
                    {
                        str(value)
                        for value in self.materialized_branch_site_ids
                        if str(value)
                    }
                )
            ),
        )
        object.__setattr__(
            self,
            "command_ids",
            tuple(sorted({str(value) for value in self.command_ids if str(value)})),
        )
        for name in (
            "static_operation_count",
            "analysis_payload_bytes",
            "branch_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise SelfReductionUniverseError(
                    f"{name} must be a non-negative integer"
                )
        if signal_kinds:
            if self.member_kind not in _IMPLEMENTATION_MEMBER_KINDS:
                raise SelfReductionUniverseError(
                    "only implementation surfaces may carry merged reduction signals"
                )
            if self.step_action not in ARCHITECTURE_REDUCTION_STEP_ACTIONS:
                raise SelfReductionUniverseError(
                    f"reduction signal requires a current step action: {self.member_id}"
                )
            if not self.cost_source_ref:
                raise SelfReductionUniverseError(
                    f"reduction signal requires cost_source_ref: {self.member_id}"
                )
            if not (self.static_operation_count or self.analysis_payload_bytes):
                raise SelfReductionUniverseError(
                    f"reduction signal requires operation or payload cost: {self.member_id}"
                )
        elif self.step_action:
            raise SelfReductionUniverseError(
                "only signal-bearing implementation surfaces may carry a step action"
            )
        if self.branch_count and not self.branch_fingerprint:
            raise SelfReductionUniverseError(
                "branch-bearing implementation surface requires branch_fingerprint"
            )
        if self.branch_count and "branch_signal" not in signal_kinds:
            raise SelfReductionUniverseError(
                "branch summary requires branch_signal on the canonical surface"
            )
        if self.materialized_branch_site_ids and (
            not self.branch_count
            or "branch_signal" not in signal_kinds
        ):
            raise SelfReductionUniverseError(
                "materialized branch sites require a branch-bearing surface"
            )
        if len(self.materialized_branch_site_ids) > self.branch_count:
            raise SelfReductionUniverseError(
                "materialized branch detail exceeds the complete surface branch count"
            )
        if self.command_ids and "command_route_signal" not in signal_kinds:
            raise SelfReductionUniverseError(
                "command identities require command_route_signal on the canonical surface"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "member_kind": self.member_kind,
            "disposition": self.disposition,
            "rationale": self.rationale,
            "source_ref": self.source_ref,
            "evidence_fingerprints": list(self.evidence_fingerprints),
            "path": self.path,
            "symbol": self.symbol,
            "signal_kinds": list(self.signal_kinds),
            "step_action": self.step_action,
            "static_operation_count": self.static_operation_count,
            "analysis_payload_bytes": self.analysis_payload_bytes,
            "cost_source_ref": self.cost_source_ref,
            "branch_count": self.branch_count,
            "branch_fingerprint": self.branch_fingerprint,
            "materialized_branch_site_ids": list(
                self.materialized_branch_site_ids
            ),
            "command_ids": list(self.command_ids),
        }


@dataclass(frozen=True)
class SelfReductionUniverse:
    implementation_inventory_fingerprint: str
    required_implementation_surface_ids: tuple[str, ...]
    members: tuple[SelfReductionUniverseMember, ...]
    source_complete: bool
    source_gap_ids: tuple[str, ...]
    branch_site_count: int = 0
    unbound_branch_site_count: int = 0
    branch_fingerprint: str = ""
    branch_expansion_mode: str = "summary"
    command_routes: tuple[tuple[str, str], ...] = ()
    oversized_boundaries: tuple[tuple[str, tuple[str, ...]], ...] = ()
    universe_fingerprint: str = ""

    def __post_init__(self) -> None:
        required = tuple(
            sorted(
                {
                    str(value)
                    for value in self.required_implementation_surface_ids
                    if str(value)
                }
            )
        )
        object.__setattr__(self, "required_implementation_surface_ids", required)
        members = tuple(sorted(self.members, key=lambda row: row.member_id))
        object.__setattr__(self, "members", members)
        member_ids = tuple(row.member_id for row in members)
        if len(member_ids) != len(set(member_ids)):
            raise SelfReductionUniverseError(
                "reduction universe contains duplicate member ids"
            )
        gaps = tuple(sorted({str(value) for value in self.source_gap_ids if str(value)}))
        object.__setattr__(self, "source_gap_ids", gaps)
        for name in ("branch_site_count", "unbound_branch_site_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise SelfReductionUniverseError(
                    f"{name} must be a non-negative integer"
                )
        if self.unbound_branch_site_count > self.branch_site_count:
            raise SelfReductionUniverseError(
                "unbound branch count exceeds complete branch denominator"
            )
        if self.branch_site_count and not self.branch_fingerprint:
            raise SelfReductionUniverseError(
                "branch denominator requires branch_fingerprint"
            )
        observed_branch_count = sum(row.branch_count for row in members)
        if observed_branch_count + self.unbound_branch_site_count != self.branch_site_count:
            raise SelfReductionUniverseError(
                "surface branch summaries plus unbound sites do not preserve the complete branch denominator"
            )
        if self.branch_expansion_mode not in {
            "summary",
            "affected",
            "explicit_deep",
        }:
            raise SelfReductionUniverseError(
                f"unknown branch expansion mode: {self.branch_expansion_mode}"
            )
        command_routes = tuple(
            sorted(
                {
                    (str(command_id), str(handler_surface_id))
                    for command_id, handler_surface_id in self.command_routes
                    if str(command_id)
                }
            )
        )
        if len(command_routes) != len({row[0] for row in command_routes}):
            raise SelfReductionUniverseError(
                "command route identity has more than one handler binding"
            )
        object.__setattr__(self, "command_routes", command_routes)
        member_by_id = {row.member_id: row for row in members}
        for command_id, handler_surface_id in command_routes:
            if not handler_surface_id:
                continue
            handler = member_by_id.get(handler_surface_id)
            if handler is None or command_id not in handler.command_ids:
                raise SelfReductionUniverseError(
                    "command route is not bound to its one canonical surface record"
                )
        oversized_boundaries = tuple(
            sorted(
                (
                    str(path),
                    tuple(
                        sorted(
                            {
                                str(value)
                                for value in hotspot_ids
                                if str(value)
                            }
                        )
                    ),
                )
                for path, hotspot_ids in self.oversized_boundaries
                if str(path)
            )
        )
        if len(oversized_boundaries) != len(
            {row[0] for row in oversized_boundaries}
        ):
            raise SelfReductionUniverseError(
                "oversized boundary path is duplicated"
            )
        object.__setattr__(self, "oversized_boundaries", oversized_boundaries)
        for path, hotspot_ids in oversized_boundaries:
            if not set(hotspot_ids) <= set(self.required_implementation_surface_ids):
                raise SelfReductionUniverseError(
                    "oversized hotspots leave the required implementation denominator"
                )
            owner_count = sum(
                1
                for row in members
                if row.path == path
                and "oversized_boundary_signal" in row.signal_kinds
            )
            if owner_count != 1:
                raise SelfReductionUniverseError(
                    "oversized file must have exactly one canonical signal owner"
                )
        if self.branch_expansion_mode == "summary" and any(
            row.materialized_branch_site_ids for row in members
        ):
            raise SelfReductionUniverseError(
                "summary branch mode cannot materialize individual branch sites"
            )
        if self.branch_expansion_mode == "explicit_deep" and any(
            row.branch_count != len(row.materialized_branch_site_ids)
            for row in members
            if row.branch_count
        ):
            raise SelfReductionUniverseError(
                "explicit-deep branch mode must materialize every bound branch site"
            )
        expected = fingerprint_value(self.identity_payload())
        if self.universe_fingerprint and self.universe_fingerprint != expected:
            raise SelfReductionUniverseError(
                "reduction universe fingerprint mismatch"
            )
        object.__setattr__(self, "universe_fingerprint", expected)

    @property
    def schema_version(self) -> str:
        return SELF_REDUCTION_UNIVERSE_SCHEMA

    @property
    def fingerprint(self) -> str:
        return self.universe_fingerprint

    @property
    def implementation_surface_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                row.member_id
                for row in self.members
                if row.member_kind in _IMPLEMENTATION_MEMBER_KINDS
            )
        )

    @property
    def reduction_signal_ids(self) -> tuple[str, ...]:
        return tuple(
            row.member_id
            for row in self.members
            if row.signal_kinds
        )

    @property
    def unresolved_member_ids(self) -> tuple[str, ...]:
        return tuple(
            row.member_id
            for row in self.members
            if row.disposition == "unresolved"
        )

    @property
    def audit_accounted(self) -> bool:
        return (
            self.implementation_surface_ids
            == self.required_implementation_surface_ids
            and all(
                row.disposition in SELF_REDUCTION_DISPOSITIONS
                for row in self.members
            )
            and set(self.source_gap_ids)
            <= {row.member_id for row in self.members}
        )

    @property
    def complete(self) -> bool:
        return self.source_complete and self.audit_accounted

    @property
    def cleanup_resolved(self) -> bool:
        return self.complete and not self.unresolved_member_ids

    @property
    def claim_boundary(self) -> str:
        return (
            "This universe accounts for independently observed self-maintenance "
            "members. A retain/contract/unresolved disposition is accounting, not "
            "automatic deletion authority. Step cost only prioritizes review; "
            "contract still requires external equivalence and safety-owner proof."
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "implementation_inventory_fingerprint": (
                self.implementation_inventory_fingerprint
            ),
            "required_implementation_surface_ids": list(
                self.required_implementation_surface_ids
            ),
            "members": [row.to_dict() for row in self.members],
            "source_complete": self.source_complete,
            "source_gap_ids": list(self.source_gap_ids),
            "branch_site_count": self.branch_site_count,
            "unbound_branch_site_count": self.unbound_branch_site_count,
            "branch_fingerprint": self.branch_fingerprint,
            "branch_expansion_mode": self.branch_expansion_mode,
            "command_routes": [
                {
                    "command_id": command_id,
                    "handler_surface_id": handler_surface_id,
                }
                for command_id, handler_surface_id in self.command_routes
            ],
            "oversized_boundaries": [
                {
                    "path": path,
                    "hotspot_surface_ids": list(hotspot_surface_ids),
                }
                for path, hotspot_surface_ids in self.oversized_boundaries
            ],
            "claim_boundary": self.claim_boundary,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "audit_accounted": self.audit_accounted,
            "complete": self.complete,
            "cleanup_resolved": self.cleanup_resolved,
            "unresolved_member_ids": list(self.unresolved_member_ids),
            "universe_fingerprint": self.universe_fingerprint,
        }


def derive_self_reduction_universe(
    bundle: Any,
    *,
    root: str | Path = ".",
    branch_expansion_surface_ids: tuple[str, ...] = (),
    explicit_deep: bool = False,
) -> SelfReductionUniverse:
    """Build the complete cleanup denominator before candidate classification."""

    inventory = getattr(bundle, "inventory", None)
    if inventory is None:
        raise SelfReductionUniverseError(
            "self reduction universe requires an implementation inventory"
        )
    inventory_fingerprint = str(
        getattr(inventory, "inventory_fingerprint", "")
    )
    required_surface_ids = tuple(
        sorted(
            {
                str(value)
                for value in getattr(inventory, "required_surface_ids", ())
                if str(value)
            }
        )
    )
    members: dict[str, SelfReductionUniverseMember] = {}
    source_gap_ids: set[str] = set()
    source_complete = True
    root_path = Path(root).resolve()

    def add(
        member_id: str,
        member_kind: str,
        disposition: str,
        rationale: str,
        *,
        source_ref: str = "",
        evidence_fingerprints: tuple[str, ...] = (),
        path: str = "",
        symbol: str = "",
    ) -> None:
        row = SelfReductionUniverseMember(
            member_id=member_id,
            member_kind=member_kind,
            disposition=disposition,
            rationale=rationale,
            source_ref=source_ref,
            evidence_fingerprints=evidence_fingerprints,
            path=path,
            symbol=symbol,
        )
        existing = members.get(member_id)
        if existing is None:
            members[member_id] = row
            return
        if (
            existing.member_kind != row.member_kind
            or existing.disposition != row.disposition
        ):
            raise SelfReductionUniverseError(
                f"reduction universe member has conflicting ownership: {member_id}"
            )
        members[member_id] = SelfReductionUniverseMember(
            member_id=member_id,
            member_kind=row.member_kind,
            disposition=row.disposition,
            rationale=existing.rationale,
            source_ref=existing.source_ref or row.source_ref,
            evidence_fingerprints=(
                existing.evidence_fingerprints + row.evidence_fingerprints
            ),
            path=existing.path or row.path,
            symbol=existing.symbol or row.symbol,
        )

    if not inventory_fingerprint:
        source_complete = False
        gap_id = "inventory-gap:" + fingerprint_value(
            {"code": "implementation_inventory_fingerprint_missing"}
        ).split(":", 1)[-1]
        source_gap_ids.add(gap_id)
        add(
            gap_id,
            "inventory_gap",
            "unresolved",
            "The self-cleanup denominator has no implementation-inventory identity.",
            source_ref="implementation_inventory",
        )
    if not required_surface_ids:
        source_complete = False
        gap_id = "inventory-gap:" + fingerprint_value(
            {"code": "required_implementation_surface_denominator_empty"}
        ).split(":", 1)[-1]
        source_gap_ids.add(gap_id)
        add(
            gap_id,
            "inventory_gap",
            "unresolved",
            "The self-cleanup inventory contains no required implementation surfaces, so an empty candidate scan cannot prove a clean architecture.",
            source_ref="implementation_inventory.required_surface_ids",
        )

    inventory_audit = getattr(bundle, "implementation_inventory_audit", None)
    if inventory_audit is None:
        source_complete = False
        audit_gap_id = "inventory-gap:" + fingerprint_value(
            {"code": "implementation_inventory_audit_missing"}
        ).split(":", 1)[-1]
        source_gap_ids.add(audit_gap_id)
        add(
            audit_gap_id,
            "inventory_gap",
            "unresolved",
            "The independent implementation-inventory audit is missing.",
            source_ref="implementation_inventory_audit",
        )
    else:
        audit_fingerprint = str(getattr(inventory_audit, "fingerprint", ""))
        audit_inventory_fingerprint = str(
            getattr(inventory_audit, "inventory_fingerprint", "")
        )
        audit_ok = bool(getattr(inventory_audit, "ok", False))
        add(
            "inventory-audit:" + (audit_fingerprint or "missing"),
            "inventory_audit",
            "retain" if audit_ok else "unresolved",
            "The cleanup denominator consumes the independent inventory audit rather than trusting inventory declarations alone.",
            source_ref=audit_inventory_fingerprint,
            evidence_fingerprints=(audit_fingerprint,),
        )
        if audit_inventory_fingerprint != inventory_fingerprint or not audit_ok:
            source_complete = False
            audit_gap_id = "inventory-gap:" + fingerprint_value(
                {
                    "code": "implementation_inventory_audit_not_current",
                    "expected": inventory_fingerprint,
                    "observed": audit_inventory_fingerprint,
                    "audit_fingerprint": audit_fingerprint,
                }
            ).split(":", 1)[-1]
            source_gap_ids.add(audit_gap_id)
            add(
                audit_gap_id,
                "inventory_gap",
                "unresolved",
                "The independent implementation-inventory audit is blocked or belongs to another inventory.",
                source_ref="implementation_inventory_audit",
                evidence_fingerprints=(audit_fingerprint,),
            )
        for finding in getattr(inventory_audit, "findings", ()):
            finding_payload = {
                "code": str(getattr(finding, "code", "inventory_audit_gap")),
                "path": str(getattr(finding, "path", "")),
                "surface_id": str(getattr(finding, "surface_id", "")),
                "message": str(getattr(finding, "message", "")),
            }
            # The inventory audit includes the source inventory findings.  Use
            # the same content-addressed identity as the raw inventory pass so
            # one underlying finding occupies one denominator row; audit-only
            # findings still remain distinct by their payload.
            gap_id = "inventory-gap:" + fingerprint_value(
                finding_payload
            ).split(":", 1)[-1]
            source_gap_ids.add(gap_id)
            add(
                gap_id,
                "inventory_gap",
                "unresolved",
                finding_payload["message"] or finding_payload["code"],
                source_ref=(
                    finding_payload["path"] or finding_payload["surface_id"]
                ),
                evidence_fingerprints=(audit_fingerprint,),
            )

    def add_surface_signal(
        signal_kind: str,
        surface: Any,
        rationale: str,
        *,
        disposition: str = "unresolved",
    ) -> None:
        surface_id = str(getattr(surface, "surface_id", ""))
        if not surface_id:
            return
        del rationale, disposition
        existing = members.get(surface_id)
        if existing is None or existing.member_kind not in _IMPLEMENTATION_MEMBER_KINDS:
            raise SelfReductionUniverseError(
                f"reduction signal has no canonical implementation surface: {surface_id}"
            )
        signal_kinds = tuple(sorted({*existing.signal_kinds, signal_kind}))
        command_ids = existing.command_ids
        analysis_payload = {
            "surface_id": surface_id,
            "signal_kinds": signal_kinds,
            "branch_count": existing.branch_count,
            "branch_fingerprint": existing.branch_fingerprint,
            "command_ids": command_ids,
        }
        members[surface_id] = replace(
            existing,
            signal_kinds=signal_kinds,
            step_action=STEP_ACTION_UNRESOLVED,
            static_operation_count=(
                max(1, len(tuple(getattr(surface, "calls", ()))))
                + existing.branch_count
                + len(command_ids)
            ),
            analysis_payload_bytes=len(
                json.dumps(
                    analysis_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ),
            cost_source_ref=surface_id,
        )

    surface_by_id = {
        str(row.surface_id): row for row in getattr(inventory, "surfaces", ())
    }
    for surface_id in required_surface_ids:
        surface = surface_by_id.get(surface_id)
        if surface is None:
            source_complete = False
            gap_id = "inventory-gap:" + fingerprint_value(
                {"code": "required_surface_missing", "surface_id": surface_id}
            ).split(":", 1)[-1]
            source_gap_ids.add(gap_id)
            add(
                gap_id,
                "inventory_gap",
                "unresolved",
                f"Required implementation surface is absent: {surface_id}",
                source_ref=surface_id,
            )
            continue
        roles = set(getattr(surface, "roles", ()))
        if "entrypoint" in roles or getattr(surface, "surface_kind", "") == "entrypoint":
            kind = "public_entrypoint"
            disposition = "unresolved"
            rationale = (
                "The public entrypoint is in the cleanup denominator, but only an "
                "independently verified retain disposition or facade proof may "
                "close it."
            )
        elif "export" in roles:
            kind = "export"
            disposition = "unresolved"
            rationale = (
                "The exported surface is in the cleanup denominator, but only an "
                "independently verified retain disposition or consumer-parity "
                "proof may close it."
            )
        else:
            kind = "implementation_surface"
            disposition = "unresolved"
            rationale = (
                "The required implementation surface is accounted for, but no "
                "independent behavior-preservation proof authorizes contraction."
            )
        add(
            surface_id,
            kind,
            disposition,
            rationale,
            source_ref=f"{getattr(surface, 'path', '')}#{getattr(surface, 'symbol', '')}",
            evidence_fingerprints=tuple(
                str(value)
                for value in (
                    getattr(surface, "content_fingerprint", ""),
                    getattr(surface, "structure_fingerprint", ""),
                )
                if str(value)
            ),
            path=str(getattr(surface, "path", "")),
            symbol=str(getattr(surface, "symbol", "")),
        )
        symbol = str(getattr(surface, "symbol", ""))
        short_name = symbol.rsplit(".", 1)[-1].lower()
        path_symbol = (
            str(getattr(surface, "path", "")) + "#" + symbol
        ).lower()
        calls = tuple(str(value) for value in getattr(surface, "calls", ()))
        if (
            "entrypoint" in roles
            or getattr(surface, "surface_kind", "") == "entrypoint"
            or (short_name.startswith("_run_") and short_name.endswith("_command"))
        ):
            add_surface_signal(
                "command_route_signal",
                surface,
                "Each public or command dispatch route is an independent cleanup signal that requires an independently verified terminal disposition.",
            )
        if str(getattr(surface, "discovery_adapter_id", "")) or any(
            token in path_symbol for token in ("adapter", "provider", "discover")
        ):
            add_surface_signal(
                "adapter_signal",
                surface,
                "Adapter and provider boundaries are enumerated separately before any layer contraction is considered.",
            )
        if len(calls) <= 1 and not short_name.startswith("_"):
            add_surface_signal(
                "wrapper_facade_signal",
                surface,
                "A thin-looking wrapper or facade is still an external-consumer boundary until delegation proof says otherwise.",
            )
        if short_name.startswith("_"):
            add_surface_signal(
                "helper_signal",
                surface,
                "Private helpers are enumerated independently even when no reduction candidate is produced.",
            )
        if any(
            token in short_name
            for token in ("check", "review", "validate", "verify", "audit")
        ):
            add_surface_signal(
                "validation_signal",
                surface,
                "Validation paths stay explicit so duplicate validation cannot disappear from the cleanup denominator.",
            )
        if any(
            token in short_name
            for token in ("build", "compile", "construct", "create", "derive")
        ):
            add_surface_signal(
                "builder_signal",
                surface,
                "Builder paths stay explicit so repeated construction authority can be reviewed without assuming equivalence.",
            )
        if any(
            token in short_name
            for token in ("serialize", "deserialize", "to_dict", "from_dict", "dump", "load")
        ):
            add_surface_signal(
                "serialization_signal",
                surface,
                "Serialization paths stay explicit because matching shapes do not prove matching contracts.",
            )
        if any(
            token in path_symbol
            for token in ("fallback", "alias", "compat", "legacy", "deprecated")
        ):
            add_surface_signal(
                "maintenance_name_signal",
                surface,
                "A maintenance-related name is only a review signal; it does not prove that the surface is a live legacy route.",
            )

    surfaces_by_path: dict[str, list[Any]] = {}
    surfaces_by_shape: dict[str, list[Any]] = {}
    repeated_shape_surface_ids: set[str] = set()
    oversized_boundaries: list[tuple[str, tuple[str, ...]]] = []
    for surface_id in required_surface_ids:
        surface = surface_by_id.get(surface_id)
        if surface is None:
            continue
        surfaces_by_path.setdefault(str(getattr(surface, "path", "")), []).append(
            surface
        )
        surfaces_by_shape.setdefault(
            str(getattr(surface, "structure_fingerprint", "")), []
        ).append(surface)
    for path, path_surfaces in surfaces_by_path.items():
        if len(path_surfaces) < 150 and max(
            (int(getattr(row, "line_end", 0)) for row in path_surfaces),
            default=0,
        ) < 2500:
            continue
        ranked_hotspots = tuple(
            sorted(
                path_surfaces,
                key=lambda row: (
                    -max(
                        0,
                        int(getattr(row, "line_end", 0))
                        - int(getattr(row, "line_start", 0)),
                    ),
                    -len(tuple(getattr(row, "calls", ()))),
                    str(getattr(row, "surface_id", "")),
                ),
            )
        )
        hotspot_surface_ids = tuple(
            str(getattr(row, "surface_id", ""))
            for row in ranked_hotspots[:12]
            if str(getattr(row, "surface_id", ""))
        )
        if not hotspot_surface_ids:
            continue
        oversized_boundaries.append((path, hotspot_surface_ids))
        boundary_owner = next(
            (
                row
                for row in ranked_hotspots
                if str(getattr(row, "surface_kind", "")) in {"file", "module"}
            ),
            ranked_hotspots[0],
        )
        add_surface_signal(
            "oversized_boundary_signal",
            boundary_owner,
            f"The implementation boundary {path} crosses the independent size threshold and is represented once with bounded hotspots.",
        )
    for shape, shape_surfaces in surfaces_by_shape.items():
        if (
            not shape
            or len(shape_surfaces) < 3
            or len({str(getattr(row, "path", "")) for row in shape_surfaces}) < 2
        ):
            continue
        for surface in shape_surfaces:
            repeated_shape_surface_ids.add(str(getattr(surface, "surface_id", "")))
            add_surface_signal(
                "repeated_shape_signal",
                surface,
                "This behavior-bearing structure participates in an independently enumerated repeated-shape group; resemblance is not equivalence proof.",
            )

    for finding in getattr(inventory, "findings", ()):
        finding_payload = {
            "code": str(getattr(finding, "code", "inventory_gap")),
            "path": str(getattr(finding, "path", "")),
            "surface_id": str(getattr(finding, "surface_id", "")),
            "message": str(getattr(finding, "message", "")),
        }
        gap_id = "inventory-gap:" + fingerprint_value(finding_payload).split(":", 1)[-1]
        source_gap_ids.add(gap_id)
        if str(getattr(finding, "severity", "blocker")) == "blocker":
            source_complete = False
        add(
            gap_id,
            "inventory_gap",
            "unresolved",
            finding_payload["message"] or finding_payload["code"],
            source_ref=finding_payload["path"] or finding_payload["surface_id"],
        )

    for file_row in getattr(inventory, "file_dispositions", ()):
        adapter_id = str(getattr(file_row, "adapter_id", ""))
        path = str(getattr(file_row, "path", ""))
        if adapter_id:
            add(
                f"adapter-declaration:{adapter_id}:{path}",
                "adapter_declaration",
                "retain",
                "Each declared discovery adapter remains in the independent denominator even when its current result is empty.",
                source_ref=path,
                evidence_fingerprints=(
                    str(getattr(file_row, "content_fingerprint", "")),
                ),
                path=path,
                symbol=adapter_id,
            )
        if bool(getattr(file_row, "requires_adapter", False)) and not str(
            getattr(file_row, "adapter_id", "")
        ):
            source_complete = False
            gap_id = "inventory-gap:" + fingerprint_value(
                {"code": "required_adapter_missing", "path": path}
            ).split(":", 1)[-1]
            source_gap_ids.add(gap_id)
            add(
                gap_id,
                "inventory_gap",
                "unresolved",
                f"Required discovery adapter is missing for {path}",
                source_ref=path,
            )

    # Command and branch syntax is scanned once per file.  The complete branch
    # denominator stays in the top-level count/fingerprint, while ordinary
    # surfaces keep only their local count/fingerprint.  Exact sites are
    # materialized only for affected, duplicate/conflicting, or explicit-deep
    # surfaces.
    branch_sites: list[dict[str, Any]] = []
    command_sites: list[dict[str, Any]] = []
    required_surfaces = tuple(
        surface_by_id[surface_id]
        for surface_id in required_surface_ids
        if surface_id in surface_by_id
    )
    scanned_paths: set[str] = set()
    for surface in required_surfaces:
        relative_path = str(getattr(surface, "path", ""))
        if not relative_path.endswith(".py") or relative_path in scanned_paths:
            continue
        scanned_paths.add(relative_path)
        source_path = (root_path / relative_path).resolve()
        try:
            source_path.relative_to(root_path)
        except ValueError:
            continue
        if not source_path.is_file():
            continue
        try:
            syntax = ast.parse(source_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError) as exc:
            source_complete = False
            gap_id = "inventory-gap:" + fingerprint_value(
                {
                    "code": "reduction_syntax_scan_failed",
                    "path": relative_path,
                    "error": type(exc).__name__,
                }
            ).split(":", 1)[-1]
            source_gap_ids.add(gap_id)
            add(
                gap_id,
                "inventory_gap",
                "unresolved",
                f"The independent command/branch scan failed for {relative_path}.",
                source_ref=relative_path,
            )
            continue
        for node in ast.walk(syntax):
            if isinstance(node, ast.Call):
                function_name = ""
                if isinstance(node.func, ast.Attribute):
                    function_name = node.func.attr
                elif isinstance(node.func, ast.Name):
                    function_name = node.func.id
                if (
                    function_name == "add_parser"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                    and node.args[0].value.strip()
                ):
                    command_id = node.args[0].value.strip()
                    command_sites.append(
                        {
                            "command_id": command_id,
                            "path": relative_path,
                            "line": int(getattr(node, "lineno", 0)),
                            "column": int(getattr(node, "col_offset", 0)),
                        }
                    )
            if isinstance(node, (ast.If, ast.Match, ast.Try)):
                branch_kind = type(node).__name__.lower()
                line = int(getattr(node, "lineno", 0))
                column = int(getattr(node, "col_offset", 0))
                branch_sites.append(
                    {
                        "site_id": (
                            f"branch:{relative_path}:{line}:{column}:{branch_kind}"
                        ),
                        "branch_kind": branch_kind,
                        "path": relative_path,
                        "line": line,
                        "column": column,
                    }
                )

    target_report = getattr(bundle, "target_system_report", None)
    behavior_report = getattr(bundle, "behavior_report", None)
    resource_inventory = getattr(bundle, "resource_inventory", None)
    test_inventory = getattr(bundle, "test_inventory", None)

    queried_lines_by_path: dict[str, set[int]] = {}
    for site in (*branch_sites, *command_sites):
        queried_lines_by_path.setdefault(str(site["path"]), set()).add(
            int(site["line"])
        )
    containing_surface = _select_containing_surfaces(
        surfaces=required_surfaces,
        queried_lines_by_path=queried_lines_by_path,
    )
    branch_sites_by_surface: dict[str, list[dict[str, Any]]] = {}
    unbound_branch_sites: list[dict[str, Any]] = []
    for site in branch_sites:
        owner = containing_surface.get((str(site["path"]), int(site["line"])))
        surface_id = str(getattr(owner, "surface_id", "")) if owner else ""
        if not surface_id:
            unbound_branch_sites.append(site)
            continue
        branch_sites_by_surface.setdefault(surface_id, []).append(site)

    command_occurrences: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for site in command_sites:
        owner = containing_surface.get((str(site["path"]), int(site["line"])))
        surface_id = str(getattr(owner, "surface_id", "")) if owner else ""
        command_occurrences.setdefault(str(site["command_id"]), []).append(
            (surface_id, site)
        )
    command_routes: list[tuple[str, str]] = []
    command_ids_by_surface: dict[str, set[str]] = {}
    for command_id, occurrences in sorted(command_occurrences.items()):
        handler_ids = {surface_id for surface_id, _ in occurrences if surface_id}
        handler_surface_id = next(iter(handler_ids)) if len(handler_ids) == 1 else ""
        command_routes.append((command_id, handler_surface_id))
        if handler_surface_id:
            command_ids_by_surface.setdefault(handler_surface_id, set()).add(
                command_id
            )
            add_surface_signal(
                "command_route_signal",
                surface_by_id[handler_surface_id],
                "The CLI command is represented by its one canonical handler surface.",
            )
        else:
            source_complete = False
            gap_payload = {
                "code": "command_route_owner_missing_or_conflicting",
                "command_id": command_id,
                "sites": [site for _, site in occurrences],
            }
            gap_id = "inventory-gap:" + fingerprint_value(gap_payload).split(":", 1)[-1]
            source_gap_ids.add(gap_id)
            add(
                gap_id,
                "inventory_gap",
                "unresolved",
                f"CLI command {command_id} has no singular canonical handler surface.",
                source_ref=command_id,
            )

    conflict_surface_ids: set[str] = set()
    for source in (inventory, inventory_audit, behavior_report, test_inventory):
        for finding in getattr(source, "findings", ()) if source else ():
            finding_text = (
                str(getattr(finding, "code", ""))
                + " "
                + str(getattr(finding, "message", ""))
            ).lower()
            surface_id = str(getattr(finding, "surface_id", ""))
            if (
                surface_id in surface_by_id
                and ("duplicate" in finding_text or "conflict" in finding_text)
                and ("model" in finding_text or "test" in finding_text)
            ):
                conflict_surface_ids.add(surface_id)

    requested_expansion_ids = {
        str(value) for value in branch_expansion_surface_ids if str(value)
    }
    for missing_surface_id in sorted(requested_expansion_ids - set(surface_by_id)):
        source_complete = False
        gap_id = "inventory-gap:" + fingerprint_value(
            {
                "code": "branch_expansion_surface_missing",
                "surface_id": missing_surface_id,
            }
        ).split(":", 1)[-1]
        source_gap_ids.add(gap_id)
        add(
            gap_id,
            "inventory_gap",
            "unresolved",
            "A requested branch-detail surface is absent from the complete implementation denominator.",
            source_ref=missing_surface_id,
        )
    expanded_surface_ids = (
        set(branch_sites_by_surface)
        if explicit_deep
        else requested_expansion_ids
        | repeated_shape_surface_ids
        | conflict_surface_ids
    )
    branch_expansion_mode = (
        "explicit_deep"
        if explicit_deep
        else "affected"
        if expanded_surface_ids & set(branch_sites_by_surface)
        else "summary"
    )

    for surface_id, sites in sorted(branch_sites_by_surface.items()):
        ordered_sites = tuple(
            sorted(
                sites,
                key=lambda site: (
                    str(site["path"]),
                    int(site["line"]),
                    int(site["column"]),
                    str(site["branch_kind"]),
                ),
            )
        )
        surface = surface_by_id[surface_id]
        add_surface_signal(
            "branch_signal",
            surface,
            "Concrete control-flow remains in the full branch denominator without becoming one record per branch.",
        )
        existing = members[surface_id]
        command_ids = tuple(sorted(command_ids_by_surface.get(surface_id, ())))
        branch_fingerprint = fingerprint_value(
            {
                "schema_version": "flowguard.self_reduction_branch_surface.v1",
                "surface_id": surface_id,
                "sites": ordered_sites,
            }
        )
        materialized_ids = (
            tuple(str(site["site_id"]) for site in ordered_sites)
            if surface_id in expanded_surface_ids
            else ()
        )
        analysis_payload = {
            "surface_id": surface_id,
            "signal_kinds": existing.signal_kinds,
            "branch_count": len(ordered_sites),
            "branch_fingerprint": branch_fingerprint,
            "command_ids": command_ids,
        }
        members[surface_id] = replace(
            existing,
            branch_count=len(ordered_sites),
            branch_fingerprint=branch_fingerprint,
            materialized_branch_site_ids=materialized_ids,
            command_ids=command_ids,
            static_operation_count=(
                max(1, len(tuple(getattr(surface, "calls", ()))))
                + len(ordered_sites)
                + len(command_ids)
            ),
            analysis_payload_bytes=len(
                json.dumps(
                    analysis_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ),
        )

    for surface_id, command_ids in sorted(command_ids_by_surface.items()):
        if surface_id in branch_sites_by_surface:
            continue
        surface = surface_by_id[surface_id]
        existing = members[surface_id]
        ordered_command_ids = tuple(sorted(command_ids))
        analysis_payload = {
            "surface_id": surface_id,
            "signal_kinds": existing.signal_kinds,
            "branch_count": existing.branch_count,
            "branch_fingerprint": existing.branch_fingerprint,
            "command_ids": ordered_command_ids,
        }
        members[surface_id] = replace(
            existing,
            command_ids=ordered_command_ids,
            static_operation_count=(
                max(1, len(tuple(getattr(surface, "calls", ()))))
                + existing.branch_count
                + len(ordered_command_ids)
            ),
            analysis_payload_bytes=len(
                json.dumps(
                    analysis_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ),
        )

    if unbound_branch_sites:
        source_complete = False
        unbound_payload = {
            "code": "branch_sites_unbound",
            "site_ids": tuple(
                sorted(str(site["site_id"]) for site in unbound_branch_sites)
            ),
        }
        gap_id = "inventory-gap:" + fingerprint_value(unbound_payload).split(":", 1)[-1]
        source_gap_ids.add(gap_id)
        add(
            gap_id,
            "inventory_gap",
            "unresolved",
            "Some concrete branch sites are outside every current implementation surface; their count and fingerprint remain in the denominator.",
            source_ref="implementation_inventory.required_surface_ids",
        )
    for source_name, source in (
        ("target_system_report", target_report),
        ("behavior_report", behavior_report),
        ("resource_inventory", resource_inventory),
        ("test_inventory", test_inventory),
    ):
        if source is not None:
            continue
        source_complete = False
        gap_id = "inventory-gap:" + fingerprint_value(
            {"code": "universe_source_missing", "source": source_name}
        ).split(":", 1)[-1]
        source_gap_ids.add(gap_id)
        add(
            gap_id,
            "inventory_gap",
            "unresolved",
            f"Self reduction universe source is missing: {source_name}",
            source_ref=source_name,
        )

    provider_results = (
        tuple(getattr(target_report, "provider_results", ()))
        if target_report
        else ()
    )
    capabilities_by_role: dict[str, set[str]] = {
        "observation": set(),
        "authority": set(),
    }
    for provider in provider_results:
        role = str(getattr(provider, "provider_role", ""))
        if role in capabilities_by_role and str(
            getattr(provider, "status", "current")
        ) == "current":
            capabilities_by_role[role].update(
                str(value)
                for value in getattr(provider, "capability_ids", ())
                if str(value)
            )
    descriptor = getattr(target_report, "descriptor", None)
    for role, requirement_name in (
        ("observation", "required_observation_capabilities"),
        ("authority", "required_authority_capabilities"),
    ):
        for capability in sorted(
            str(value)
            for value in getattr(descriptor, requirement_name, ())
            if str(value)
        ):
            available = capability in capabilities_by_role[role]
            requirement_id = f"provider-requirement:{role}:{capability}"
            add(
                requirement_id,
                "provider_requirement",
                "retain" if available else "unresolved",
                (
                    "The declared provider capability has a current frozen result."
                    if available
                    else "The declared provider capability has no current frozen result."
                ),
                source_ref=str(getattr(descriptor, "target_system_id", "")),
            )
            if not available:
                source_complete = False
                source_gap_ids.add(requirement_id)

    for provider in provider_results:
        provider_id = str(getattr(provider, "provider_id", ""))
        if not provider_id:
            continue
        add(
            _namespace("provider", provider_id),
            "provider",
            "retain",
            "The frozen provider boundary remains retained by its external authority.",
            source_ref=provider_id,
            evidence_fingerprints=(str(getattr(provider, "fingerprint", "")),),
        )
        for capability_id in getattr(provider, "capability_ids", ()):
            capability = str(capability_id)
            if not capability:
                continue
            add(
                f"provider-capability:{provider_id}:{capability}",
                "provider_capability",
                "retain",
                "The frozen provider capability stays retained with its exact adapter boundary.",
                source_ref=provider_id,
                evidence_fingerprints=(
                    str(getattr(provider, "fingerprint", "")),
                ),
            )

    for contract in getattr(behavior_report, "contracts", ()) if behavior_report else ():
        implementation_surface_id = str(
            getattr(contract, "implementation_surface_id", "")
        )
        if implementation_surface_id and (
            implementation_surface_id not in required_surface_ids
            or implementation_surface_id not in surface_by_id
        ):
            source_complete = False
            gap_id = "inventory-gap:" + fingerprint_value(
                {
                    "code": "behavior_owner_surface_unobserved",
                    "behavior_block_id": str(
                        getattr(contract, "behavior_block_id", "")
                    ),
                    "implementation_surface_id": implementation_surface_id,
                }
            ).split(":", 1)[-1]
            source_gap_ids.add(gap_id)
            add(
                gap_id,
                "inventory_gap",
                "unresolved",
                "A behavior owner references an implementation surface outside the independently observed denominator.",
                source_ref=implementation_surface_id,
                evidence_fingerprints=(
                    str(getattr(contract, "source_fingerprint", "")),
                ),
            )
        model_id = str(getattr(contract, "model_element_id", ""))
        if model_id:
            add(
                _namespace("model", model_id),
                "model_owner",
                "unresolved",
                "The model owner is accounted for but cannot be contracted without current refinement proof.",
                source_ref=str(getattr(contract, "behavior_block_id", "")),
                evidence_fingerprints=(
                    str(getattr(contract, "source_fingerprint", "")),
                ),
            )
        for prefix, value in (
            ("owner", getattr(contract, "owner_id", "")),
            ("owner-contract", getattr(contract, "owner_contract_id", "")),
        ):
            if not str(value):
                continue
            add(
                _namespace(prefix, value),
                "model_owner",
                "unresolved",
                "The declared behavior owner remains unresolved until ownership and consumer parity prove a safe contraction.",
                source_ref=str(getattr(contract, "behavior_block_id", "")),
                evidence_fingerprints=(
                    str(getattr(contract, "source_fingerprint", "")),
                ),
            )

    # Behavior coverage ownership, native execution ownership, and terminal
    # execution evidence are separate contracts.  One native execution owner
    # is represented once even when it owns many planned coverage rows.  Its
    # exact design identity proves that the owner exists; passing receipts stay
    # separate and are never required to invent that design identity.
    coverage_rows_by_execution_owner: dict[str, list[Any]] = {}
    for evidence in (
        getattr(behavior_report, "coverage_execution_evidence", ())
        if behavior_report
        else ()
    ):
        owner_id = str(getattr(evidence, "execution_owner_id", ""))
        if owner_id:
            coverage_rows_by_execution_owner.setdefault(owner_id, []).append(
                evidence
            )
    for owner_id, evidence_rows in sorted(
        coverage_rows_by_execution_owner.items()
    ):
        coverage_ids = tuple(
            sorted(
                {
                    str(getattr(evidence, "coverage_id", ""))
                    for evidence in evidence_rows
                    if str(getattr(evidence, "coverage_id", ""))
                }
            )
        )
        design_fingerprint = fingerprint_value(
            {
                "execution_owner_id": owner_id,
                "coverage_ids": list(coverage_ids),
            }
        )
        receipt_fingerprints = tuple(
            sorted(
                {
                    str(getattr(evidence, "receipt_fingerprint", ""))
                    for evidence in evidence_rows
                    if str(getattr(evidence, "receipt_fingerprint", ""))
                }
            )
        )
        add(
            _namespace("check", owner_id),
            "check_owner",
            "unresolved",
            "The native check owner is accounted for by one exact aggregate design identity; terminal execution evidence remains separate.",
            source_ref=owner_id,
            evidence_fingerprints=(design_fingerprint, *receipt_fingerprints),
        )

    # Test-node disposition owners are behavior owners, not native execution
    # owners.  Supporting and legally scoped-out tests therefore may have an
    # empty owner set; every required test remains independently represented
    # below by its current source identity.
    for disposition in (
        getattr(behavior_report, "test_node_dispositions", ())
        if behavior_report
        else ()
    ):
        test_node_id = str(getattr(disposition, "test_node_id", ""))
        owner_ids = tuple(
            str(value)
            for value in getattr(disposition, "owner_ids", ())
            if str(value)
        )
        disposition_kind = str(getattr(disposition, "disposition", ""))
        if disposition_kind in {"supporting", "scoped_out"}:
            continue
        disposition_fingerprint = fingerprint_value(
            {
                "test_node_id": test_node_id,
                "disposition": disposition_kind,
                "owner_ids": list(owner_ids),
                "coverage_ids": sorted(
                    str(value)
                    for value in getattr(disposition, "coverage_ids", ())
                    if str(value)
                ),
                "rationale": str(getattr(disposition, "rationale", "")),
            }
        )
        if (
            disposition_kind in {"behavior_coverage", "cross_owner_integration"}
            and not owner_ids
        ):
            owner_gap_id = f"coverage-owner-missing:{test_node_id or 'unknown'}"
            source_gap_ids.add(owner_gap_id)
            source_complete = False
            add(
                owner_gap_id,
                "coverage_owner_gap",
                "unresolved",
                "An exact behavior-coverage disposition has no required behavior owner.",
                source_ref=test_node_id,
                evidence_fingerprints=(disposition_fingerprint,),
            )
            continue
        if disposition_kind in {"blocked", "duplicate"}:
            disposition_gap_id = (
                f"test-disposition-{disposition_kind}:"
                f"{test_node_id or 'unknown'}"
            )
            source_gap_ids.add(disposition_gap_id)
            source_complete = False
            add(
                disposition_gap_id,
                "test_disposition_gap",
                "unresolved",
                "A blocked or duplicate test disposition requires an explicit current resolution.",
                source_ref=test_node_id,
                evidence_fingerprints=(disposition_fingerprint,),
            )

    for resource in (
        getattr(resource_inventory, "members", ()) if resource_inventory else ()
    ):
        resource_id = str(getattr(resource, "member_id", ""))
        if not resource_id:
            continue
        add(
            _namespace("resource", resource_id),
            "resource",
            "unresolved",
            "The required resource remains accounted for until all consuming behavior proves a safe lifecycle change.",
            source_ref=resource_id,
            evidence_fingerprints=(
                str(getattr(resource, "category_evidence_fingerprint", "")),
            ),
        )

    required_test_ids = set(
        str(value)
        for value in getattr(test_inventory, "required_node_ids", ())
        if str(value)
    ) if test_inventory else set()
    test_by_id = {
        str(getattr(node, "node_id", "")): node
        for node in getattr(test_inventory, "nodes", ())
        if str(getattr(node, "node_id", ""))
    } if test_inventory else {}
    for test_id in sorted(required_test_ids):
        node = test_by_id.get(test_id)
        if node is None:
            source_complete = False
            gap_id = "inventory-gap:" + fingerprint_value(
                {"code": "required_test_missing", "test_id": test_id}
            ).split(":", 1)[-1]
            source_gap_ids.add(gap_id)
            add(
                gap_id,
                "inventory_gap",
                "unresolved",
                f"Required test node is absent: {test_id}",
                source_ref=test_id,
            )
            continue
        add(
            _namespace("test", test_id),
            "test",
            "unresolved",
            "The required test is accounted for; removal needs exact obligation and checker parity.",
            source_ref=test_id,
            evidence_fingerprints=(
                str(getattr(node, "source_fingerprint", "")),
            ),
        )

    ordered_branch_sites = tuple(
        sorted(
            branch_sites,
            key=lambda site: (
                str(site["path"]),
                int(site["line"]),
                int(site["column"]),
                str(site["branch_kind"]),
            ),
        )
    )
    branch_fingerprint = (
        fingerprint_value(
            {
                "schema_version": "flowguard.self_reduction_branch_denominator.v1",
                "sites": ordered_branch_sites,
            }
        )
        if ordered_branch_sites
        else ""
    )
    return SelfReductionUniverse(
        implementation_inventory_fingerprint=inventory_fingerprint,
        required_implementation_surface_ids=required_surface_ids,
        members=tuple(members.values()),
        source_complete=source_complete,
        source_gap_ids=tuple(source_gap_ids),
        branch_site_count=len(ordered_branch_sites),
        unbound_branch_site_count=len(unbound_branch_sites),
        branch_fingerprint=branch_fingerprint,
        branch_expansion_mode=branch_expansion_mode,
        command_routes=tuple(command_routes),
        oversized_boundaries=tuple(oversized_boundaries),
    )


def derive_self_reduction_retain_dispositions(
    bundle: Any,
    universe: SelfReductionUniverse,
    *,
    candidate_bindings: tuple[SelfReductionCandidateBinding, ...],
    external_commitment_bindings: Mapping[
        str, tuple[Mapping[str, Any], ...]
    ] | None = None,
    necessity_gap_sink: MutableMapping[str, tuple[str, ...]] | None = None,
) -> tuple[SelfReductionRetainDisposition, ...]:
    """Derive retain authority from current facts, never from candidate absence."""

    inventory = getattr(bundle, "inventory", None)
    test_inventory = getattr(bundle, "test_inventory", None)
    behavior_report = getattr(bundle, "behavior_report", None)
    intent_inventory = getattr(bundle, "intent_inventory", None)
    binding_report = getattr(bundle, "binding_report", None)
    if inventory is None or test_inventory is None or behavior_report is None:
        raise SelfReductionUniverseError(
            "retain disposition derivation requires current inventory, tests, and behavior"
        )
    subject_revision = str(
        getattr(getattr(inventory, "boundary", None), "subject_revision", "")
    )
    inventory_fingerprint = str(
        getattr(inventory, "inventory_fingerprint", "")
    )
    test_inventory_fingerprint = str(
        getattr(test_inventory, "inventory_fingerprint", "")
    )
    if (
        not subject_revision
        or inventory_fingerprint != universe.implementation_inventory_fingerprint
        or not test_inventory_fingerprint
    ):
        raise SelfReductionUniverseError(
            "retain disposition derivation is not bound to the current subject inventories"
        )

    surface_by_id = {
        str(getattr(surface, "surface_id", "")): surface
        for surface in getattr(inventory, "surfaces", ())
        if str(getattr(surface, "surface_id", ""))
    }
    contracts_by_surface: dict[str, list[Any]] = {}
    contracts_by_block: dict[str, list[Any]] = {}
    for contract in getattr(behavior_report, "contracts", ()):
        surface_id = str(getattr(contract, "implementation_surface_id", ""))
        if surface_id:
            contracts_by_surface.setdefault(surface_id, []).append(contract)
        behavior_block_id = str(getattr(contract, "behavior_block_id", ""))
        if behavior_block_id:
            contracts_by_block.setdefault(behavior_block_id, []).append(contract)
    supporting_relations_by_surface: dict[str, list[Any]] = {}
    for relation in getattr(behavior_report, "supporting_relations", ()):
        surface_id = str(getattr(relation, "supporting_surface_id", ""))
        if surface_id:
            supporting_relations_by_surface.setdefault(surface_id, []).append(
                relation
            )
    behavior_fingerprint = str(getattr(behavior_report, "fingerprint", ""))
    intent_inventory_fingerprint = str(
        getattr(intent_inventory, "fingerprint", "")
    )
    binding_report_fingerprint = str(
        getattr(binding_report, "fingerprint", "")
    )
    external_commitment_bindings = external_commitment_bindings or {}
    if any(
        not isinstance(binding, SelfReductionCandidateBinding)
        for binding in candidate_bindings
    ):
        raise TypeError(
            "candidate bindings require SelfReductionCandidateBinding rows"
        )
    known_surface_ids = set(universe.implementation_surface_ids)
    known_signal_surface_ids = set(universe.reduction_signal_ids)
    for binding in candidate_bindings:
        unknown_members = set(binding.member_ids) - known_surface_ids
        unknown_signal_surfaces = (
            set(binding.source_signal_ids) - known_signal_surface_ids
        )
        if unknown_members:
            raise SelfReductionUniverseError(
                "candidate binding references unknown implementation surfaces: "
                + ", ".join(sorted(unknown_members))
            )
        if unknown_signal_surfaces:
            raise SelfReductionUniverseError(
                "candidate binding references surfaces without current signals: "
                + ", ".join(sorted(unknown_signal_surfaces))
            )
        if not set(binding.source_signal_ids) <= set(binding.member_ids):
            raise SelfReductionUniverseError(
                "candidate binding signal surfaces must be members of the same candidate"
            )
    member_ids_by_exact_authority: dict[
        tuple[str, tuple[str, ...], tuple[str, ...], str],
        set[str],
    ] = {}
    source_gap_ids = set(universe.source_gap_ids)

    current_owner_binding_by_surface: dict[
        str,
        tuple[str, tuple[str, ...], tuple[str, ...]] | None,
    ] = {}

    def derive_current_owner_binding(
        source_surface: Any,
    ) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
        """Return one exact current owner and its source-surface evidence."""

        surface_id = str(getattr(source_surface, "surface_id", ""))
        content_fingerprint = str(
            getattr(source_surface, "content_fingerprint", "")
        )
        structure_fingerprint = str(
            getattr(source_surface, "structure_fingerprint", "")
        )
        if not all(
            (
                surface_id,
                content_fingerprint,
                structure_fingerprint,
                behavior_fingerprint,
            )
        ):
            return None

        bindings: dict[
            tuple[str, str, str],
            tuple[str, set[str], set[str]],
        ] = {}

        def add_binding(contract: Any, relation: Any | None = None) -> None:
            behavior_block_id = str(
                getattr(contract, "behavior_block_id", "")
            )
            owner_contract_id = str(
                getattr(contract, "owner_contract_id", "")
            )
            owner_id = str(getattr(contract, "owner_id", ""))
            model_element_id = str(
                getattr(contract, "model_element_id", "")
            )
            contract_surface_id = str(
                getattr(contract, "implementation_surface_id", "")
            )
            contract_source_fingerprint = str(
                getattr(contract, "source_fingerprint", "")
            )
            contract_surface = surface_by_id.get(contract_surface_id)
            contract_structure_fingerprint = str(
                getattr(contract_surface, "structure_fingerprint", "")
            )
            if not all(
                (
                    behavior_block_id,
                    owner_contract_id,
                    owner_id,
                    model_element_id,
                    contract_surface_id,
                    contract_source_fingerprint,
                    contract_structure_fingerprint,
                )
            ) or getattr(contract, "accepted", True) is not True or (
                contract_surface is None
                or str(getattr(contract_surface, "content_fingerprint", ""))
                != contract_source_fingerprint
            ):
                return
            if relation is None:
                if contract_source_fingerprint != content_fingerprint:
                    return
                relation_evidence_id = ""
                relation_evidence_fingerprint = ""
            else:
                relation_evidence_id = str(
                    getattr(relation, "evidence_id", "")
                )
                relation_evidence_fingerprint = str(
                    getattr(relation, "evidence_fingerprint", "")
                )
                if (
                    not relation_evidence_id
                    or relation_evidence_fingerprint != structure_fingerprint
                ):
                    return
            key = (behavior_block_id, owner_contract_id, owner_id)
            existing = bindings.get(key)
            if existing is None:
                bindings[key] = (
                    owner_id,
                    set(),
                    set(),
                )
            _, owner_refs, evidence_fingerprints = bindings[key]
            owner_refs.update(
                value
                for value in (
                    surface_id,
                    contract_surface_id,
                    behavior_block_id,
                    owner_contract_id,
                    owner_id,
                    model_element_id,
                    relation_evidence_id,
                )
                if value
            )
            evidence_fingerprints.update(
                value
                for value in (
                    content_fingerprint,
                    structure_fingerprint,
                    behavior_fingerprint,
                    contract_source_fingerprint,
                    contract_structure_fingerprint,
                    str(getattr(contract, "fingerprint", "")),
                    relation_evidence_fingerprint,
                )
                if value
            )

        direct_contracts = tuple(contracts_by_surface.get(surface_id, ()))
        supporting_relations = tuple(
            supporting_relations_by_surface.get(surface_id, ())
        )
        if len(direct_contracts) + len(supporting_relations) != 1:
            return None
        for contract in direct_contracts:
            add_binding(contract)
        for relation in supporting_relations:
            related_contracts = tuple(
                contracts_by_block.get(
                    str(getattr(relation, "behavior_block_id", "")), ()
                )
            )
            if len(related_contracts) != 1:
                return None
            add_binding(related_contracts[0], relation)
        if len(bindings) != 1:
            return None
        (
            primary_owner_id,
            owner_refs,
            evidence_fingerprints,
        ) = next(iter(bindings.values()))
        if not primary_owner_id or not owner_refs or not evidence_fingerprints:
            return None
        return (
            primary_owner_id,
            tuple(sorted(owner_refs)),
            tuple(sorted(evidence_fingerprints)),
        )

    def current_owner_binding(
        source_surface: Any,
    ) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
        surface_id = str(getattr(source_surface, "surface_id", ""))
        if surface_id not in current_owner_binding_by_surface:
            current_owner_binding_by_surface[surface_id] = (
                derive_current_owner_binding(source_surface)
            )
        return current_owner_binding_by_surface[surface_id]

    bindings_by_surface: dict[str, list[Any]] = {}
    semantic_specs_by_id: dict[str, Any] = {}
    oracles_by_id: dict[str, Any] = {}
    if binding_report is not None and bool(getattr(binding_report, "ok", False)):
        for binding in getattr(binding_report, "bindings", ()):
            binding_surface_id = str(
                getattr(binding, "implementation_surface_id", "")
            )
            if binding_surface_id:
                bindings_by_surface.setdefault(binding_surface_id, []).append(
                    binding
                )
        semantic_specs_by_id = {
            str(getattr(spec, "semantic_spec_id", "")): spec
            for spec in getattr(binding_report, "semantic_specs", ())
            if str(getattr(spec, "semantic_spec_id", ""))
        }
        oracles_by_id = {
            str(getattr(oracle, "oracle_id", "")): oracle
            for oracle in getattr(binding_report, "oracles", ())
            if str(getattr(oracle, "oracle_id", ""))
        }

    contributions_by_id = {
        str(getattr(row, "contribution_id", "")): row
        for row in getattr(intent_inventory, "contributions", ())
        if str(getattr(row, "contribution_id", ""))
    }
    intent_authorities = tuple(
        getattr(intent_inventory, "source_authorities", ())
    )
    test_node_by_id = {
        str(getattr(row, "node_id", "")): row
        for row in getattr(test_inventory, "nodes", ())
        if str(getattr(row, "node_id", ""))
    }
    behavior_cases_by_block: dict[str, list[Any]] = {}
    for case in getattr(behavior_report, "case_contracts", ()):
        case_block_id = str(getattr(case, "behavior_block_id", ""))
        if case_block_id:
            behavior_cases_by_block.setdefault(case_block_id, []).append(case)
    coverage_by_block_and_surface: dict[tuple[str, str], list[Any]] = {}
    for edge in getattr(behavior_report, "coverage_edges", ()):
        edge_block_id = str(getattr(edge, "behavior_block_id", ""))
        edge_surface_id = str(
            getattr(edge, "implementation_surface_id", "")
        )
        if edge_block_id and edge_surface_id:
            coverage_by_block_and_surface.setdefault(
                (edge_block_id, edge_surface_id),
                [],
            ).append(edge)
    execution_by_coverage_id = {
        str(getattr(row, "coverage_id", "")): row
        for row in getattr(
            behavior_report,
            "coverage_execution_evidence",
            (),
        )
        if str(getattr(row, "coverage_id", ""))
    }
    path_quality_by_model: dict[str, list[Any]] = {}
    for row in getattr(behavior_report, "path_quality_bindings", ()):
        model_element_id = str(getattr(row, "model_element_id", ""))
        if model_element_id:
            path_quality_by_model.setdefault(model_element_id, []).append(row)
    blocked_path_quality_model_ids = {
        str(member_id)
        for finding in getattr(behavior_report, "findings", ())
        if str(getattr(finding, "code", "")).startswith("path_quality_")
        for member_id in getattr(finding, "member_ids", ())
        if str(member_id)
    }
    candidate_gap_ids_by_member: dict[str, set[str]] = {}
    for candidate_binding in candidate_bindings:
        for member_id in candidate_binding.member_ids:
            candidate_gap_ids_by_member.setdefault(member_id, set()).update(
                candidate_binding.caller_resolution_gap_ids
            )

    def exact_contract_relation(
        surface_id: str,
    ) -> tuple[Any, Any | None, str] | None:
        direct_contracts = tuple(contracts_by_surface.get(surface_id, ()))
        relations = tuple(supporting_relations_by_surface.get(surface_id, ()))
        if len(direct_contracts) + len(relations) != 1:
            return None
        if direct_contracts:
            return direct_contracts[0], None, "direct_contract"
        relation = relations[0]
        related_contracts = tuple(
            contracts_by_block.get(
                str(getattr(relation, "behavior_block_id", "")),
                (),
            )
        )
        if len(related_contracts) != 1:
            return None
        return related_contracts[0], relation, "supporting_relation"

    def current_intent_authority_fingerprint(contribution: Any) -> str:
        expected_key = (
            str(getattr(contribution, "source_kind", "")),
            str(getattr(contribution, "source_id", "")),
            str(getattr(contribution, "source_owner_id", "")),
            str(getattr(contribution, "expectation_id", "")),
        )
        matches = tuple(
            authority
            for authority in intent_authorities
            if (
                str(getattr(authority, "source_kind", "")),
                str(getattr(authority, "source_id", "")),
                str(getattr(authority, "source_owner_id", "")),
                str(getattr(authority, "expectation_id", "")),
            )
            == expected_key
            and str(getattr(authority, "status", "")) == "current"
        )
        if len(matches) != 1:
            return ""
        authority = matches[0]
        if (
            str(getattr(authority, "current_source_fingerprint", ""))
            != str(getattr(contribution, "source_fingerprint", ""))
            or str(
                getattr(authority, "current_expectation_fingerprint", "")
            )
            != str(getattr(contribution, "expectation_fingerprint", ""))
            or tuple(getattr(authority, "target_ids", ()))
            != tuple(getattr(contribution, "target_ids", ()))
        ):
            return ""
        return str(
            getattr(authority, "fingerprint", "")
            or fingerprint_value(
                {
                    "source_kind": expected_key[0],
                    "source_id": expected_key[1],
                    "source_owner_id": expected_key[2],
                    "expectation_id": expected_key[3],
                    "current_source_fingerprint": getattr(
                        authority,
                        "current_source_fingerprint",
                        "",
                    ),
                    "current_expectation_fingerprint": getattr(
                        authority,
                        "current_expectation_fingerprint",
                        "",
                    ),
                    "target_ids": tuple(getattr(authority, "target_ids", ())),
                }
            )
        )

    def current_necessity_witness(
        member_id: str,
    ) -> SelfReductionCurrentNecessityWitness | None:
        def reject(*gap_ids: str) -> None:
            if necessity_gap_sink is not None:
                necessity_gap_sink[member_id] = tuple(
                    sorted({gap_id for gap_id in gap_ids if gap_id})
                )
            return None

        surface = surface_by_id.get(member_id)
        if surface is None or not (
            subject_revision
            and inventory_fingerprint
            and test_inventory_fingerprint
            and intent_inventory_fingerprint
            and behavior_fingerprint
            and binding_report_fingerprint
            and bool(getattr(intent_inventory, "complete", False))
            and bool(getattr(binding_report, "ok", False))
        ):
            return reject("surface_or_global_currentness_missing")
        owner_binding = current_owner_binding(surface)
        contract_relation = exact_contract_relation(member_id)
        exact_bindings = tuple(bindings_by_surface.get(member_id, ()))
        if owner_binding is None or contract_relation is None or len(exact_bindings) != 1:
            return reject("owner_contract_or_exact_binding_missing")
        contract, relation, binding_kind = contract_relation
        implementation_binding = exact_bindings[0]
        behavior_block_id = str(getattr(contract, "behavior_block_id", ""))
        model_element_id = str(getattr(contract, "model_element_id", ""))
        owner_contract_id = str(getattr(contract, "owner_contract_id", ""))
        owner_id = str(getattr(contract, "owner_id", ""))
        if (
            str(getattr(implementation_binding, "model_element_id", ""))
            != model_element_id
            or str(getattr(implementation_binding, "owner_contract_id", ""))
            != owner_contract_id
            or str(
                getattr(implementation_binding, "implementation_surface_id", "")
            )
            != member_id
            or str(
                getattr(
                    implementation_binding,
                    "implementation_content_fingerprint",
                    "",
                )
            )
            != str(getattr(surface, "content_fingerprint", ""))
        ):
            return reject("implementation_binding_mismatch")

        path_quality_binding_fingerprint = ""
        if path_quality_by_model:
            path_quality_rows = tuple(
                path_quality_by_model.get(model_element_id, ())
            )
            if (
                len(path_quality_rows) != 1
                or model_element_id in blocked_path_quality_model_ids
                or bool(getattr(path_quality_rows[0], "ready", False)) is not True
            ):
                return reject("path_quality_binding_not_ready")
            path_quality_binding_fingerprint = str(
                getattr(
                    path_quality_rows[0],
                    "compact_current_fingerprint",
                    "",
                )
            )
            if not path_quality_binding_fingerprint.startswith("sha256:"):
                return reject("path_quality_fingerprint_missing")

        contribution_ids = tuple(
            sorted(
                {
                    str(value)
                    for value in getattr(contract, "intent_contribution_ids", ())
                    if str(value)
                }
            )
        )
        contributions = tuple(
            contributions_by_id.get(contribution_id)
            for contribution_id in contribution_ids
        )
        if not contribution_ids or any(row is None for row in contributions):
            return reject("intent_contribution_missing")
        typed_contributions = tuple(row for row in contributions if row is not None)
        if any(
            str(getattr(row, "disposition", "")) != "accepted"
            or model_element_id not in tuple(getattr(row, "target_ids", ()))
            for row in typed_contributions
        ):
            return reject("intent_contribution_not_current_for_model")
        intent_authority_fingerprints = tuple(
            current_intent_authority_fingerprint(row)
            for row in typed_contributions
        )
        if not all(intent_authority_fingerprints):
            return reject("intent_authority_fingerprint_missing")

        semantic_spec_ids = tuple(
            sorted(
                {
                    str(value)
                    for value in getattr(
                        implementation_binding,
                        "semantic_spec_ids",
                        (),
                    )
                    if str(value)
                }
            )
        )
        if semantic_spec_ids != tuple(
            sorted(
                {
                    str(value)
                    for value in getattr(contract, "semantic_spec_ids", ())
                    if str(value)
                }
            )
        ):
            return reject("semantic_spec_binding_mismatch")
        semantic_specs = tuple(
            semantic_specs_by_id.get(spec_id) for spec_id in semantic_spec_ids
        )
        if not semantic_spec_ids or any(spec is None for spec in semantic_specs):
            return reject("semantic_spec_missing")
        semantic_dimensions: dict[str, str] = {}
        for spec in (row for row in semantic_specs if row is not None):
            if model_element_id not in tuple(
                getattr(spec, "covered_model_element_ids", ())
            ):
                return reject("semantic_spec_model_coverage_missing")
            for dimension, value in tuple(getattr(spec, "semantics", ())):
                dimension = str(dimension)
                value = str(value)
                existing_value = semantic_dimensions.get(dimension)
                if existing_value is not None and existing_value != value:
                    return reject("semantic_dimension_conflict")
                semantic_dimensions[dimension] = value
        if not semantic_dimensions:
            return reject("semantic_dimensions_missing")

        oracle_ids = tuple(
            sorted(
                {
                    str(value)
                    for value in getattr(implementation_binding, "oracle_ids", ())
                    if str(value)
                }
            )
        )
        if oracle_ids != tuple(
            sorted(
                {
                    str(value)
                    for value in getattr(contract, "oracle_ids", ())
                    if str(value)
                }
            )
        ) or any(oracle_id not in oracles_by_id for oracle_id in oracle_ids):
            return reject("oracle_binding_missing_or_mismatched")
        declared_test_evidence_ids = tuple(
            sorted(
                {
                    str(value)
                    for value in getattr(
                        implementation_binding,
                        "test_evidence_ids",
                        (),
                    )
                    if str(value)
                }
            )
        )
        test_node_ids = tuple(
            test_id
            for test_id in declared_test_evidence_ids
            if test_id in test_node_by_id
        )
        model_validation_evidence_ids = tuple(
            test_id
            for test_id in declared_test_evidence_ids
            if test_id.startswith("check:model-regression:")
        )
        native_validation_evidence_ids = tuple(
            test_id
            for test_id in declared_test_evidence_ids
            if test_id.startswith("check:")
            and not test_id.startswith("check:model-regression:")
        )
        unknown_test_evidence_ids = tuple(
            test_id
            for test_id in declared_test_evidence_ids
            if test_id not in test_node_by_id
            and test_id not in model_validation_evidence_ids
            and test_id not in native_validation_evidence_ids
        )
        if (
            unknown_test_evidence_ids
            or not (
                test_node_ids
                or model_validation_evidence_ids
            )
        ):
            return reject("test_or_model_validation_evidence_missing")
        if path_quality_by_model:
            expected_model_validation_id = (
                "check:model-regression:"
                + model_element_id.removeprefix("model-obligation:")
            )
            if model_validation_evidence_ids != (
                expected_model_validation_id,
            ):
                return reject("model_validation_evidence_identity_mismatch")
        elif model_validation_evidence_ids:
            # A model-regression identity is useful only when the same bundle
            # supplies its exact current path-quality binding.  A label alone
            # must never stand in for current model evidence.
            return reject("model_validation_path_quality_binding_missing")
        declared_test_evidence_fingerprints = dict(
            getattr(
                implementation_binding,
                "test_evidence_fingerprints",
                (),
            )
        )
        if any(
            not str(
                declared_test_evidence_fingerprints.get(evidence_id, "")
            )
            for evidence_id in (
                *model_validation_evidence_ids,
                *native_validation_evidence_ids,
            )
        ):
            return reject("model_validation_evidence_fingerprint_missing")

        planned_coverage_rows = tuple(
            coverage_by_block_and_surface.get(
                (behavior_block_id, member_id),
                (),
            )
        )
        planned_coverage_test_ids = {
            str(getattr(row, "test_node_id", ""))
            for row in planned_coverage_rows
            if str(getattr(row, "test_node_id", ""))
        }
        # Planned checker identities describe what the behavior design says
        # must be checked; ordinary test nodes and model-regression identities
        # describe the current executable evidence.  They are deliberately
        # separate namespaces and therefore must never be required to share an
        # id.  Planned coverage remains visible in the behavior model, but it
        # must not manufacture ordinary code-test coverage or a passing
        # execution receipt.  Only coverage whose exact checker identity is
        # also a current executable test node may enter the witness.
        coverage_rows = tuple(
            row
            for row in planned_coverage_rows
            if str(getattr(row, "test_node_id", "")) in set(test_node_ids)
        )
        coverage_ids = tuple(
            sorted(
                {
                    str(getattr(row, "coverage_id", ""))
                    for row in coverage_rows
                    if str(getattr(row, "coverage_id", ""))
                }
            )
        )
        current_receipt_ids = tuple(
            sorted(
                {
                    str(getattr(execution_by_coverage_id[coverage_id], "receipt_id", ""))
                    for coverage_id in coverage_ids
                    if coverage_id in execution_by_coverage_id
                    and str(
                        getattr(
                            execution_by_coverage_id[coverage_id],
                            "disposition",
                            "",
                        )
                    )
                    == "pass"
                    and str(
                        getattr(
                            execution_by_coverage_id[coverage_id],
                            "receipt_id",
                            "",
                        )
                    )
                }
            )
        )
        behavior_case_ids = tuple(
            sorted(
                {
                    str(getattr(row, "case_id", ""))
                    for row in behavior_cases_by_block.get(behavior_block_id, ())
                    if str(getattr(row, "case_id", ""))
                }
            )
        )

        implementation_binding_id = str(
            getattr(implementation_binding, "binding_id", "")
        )
        external_rows = tuple(
            row
            for row in external_commitment_bindings.get(model_element_id, ())
            if str(row.get("implementation_surface_id", "")) == member_id
            and str(row.get("binding_id", "")) == implementation_binding_id
        )
        external_semantics: list[Mapping[str, Any]] = []
        behavior_commitment_ids: list[str] = []
        bcl_review_fingerprints: set[str] = set()
        external_binding_fingerprints: set[str] = set()
        surface_code_contract_id = "code-contract:" + implementation_binding_id
        for row in external_rows:
            commitment_id = str(row.get("commitment_id", ""))
            review_fingerprint = str(row.get("review_fingerprint", ""))
            external_model_element_id = str(
                row.get("model_element_id", "")
            )
            external_owner_contract_id = str(
                row.get("owner_contract_id", "")
            )
            external_surface_id = str(
                row.get("implementation_surface_id", "")
            )
            external_binding_id = str(row.get("binding_id", ""))
            code_contract_ids = tuple(
                sorted(
                    {
                        str(value)
                        for value in row.get("code_contract_ids", ())
                        if str(value)
                    }
                )
            )
            test_evidence_ids = tuple(
                sorted(
                    {
                        str(value)
                        for value in row.get("test_evidence_ids", ())
                        if str(value)
                    }
                )
            )
            binding_fingerprint = str(
                row.get("binding_fingerprint", "")
            )
            semantics = row.get("semantics")
            if (
                not commitment_id
                or not review_fingerprint
                or external_model_element_id != model_element_id
                or external_owner_contract_id != owner_contract_id
                or external_surface_id != member_id
                or external_binding_id != implementation_binding_id
                or owner_contract_id not in set(code_contract_ids)
                or surface_code_contract_id not in set(code_contract_ids)
                or test_evidence_ids != declared_test_evidence_ids
                or not binding_fingerprint
                or not isinstance(semantics, Mapping)
            ):
                return reject("external_commitment_binding_mismatch")
            behavior_commitment_ids.append(commitment_id)
            bcl_review_fingerprints.add(review_fingerprint)
            external_binding_fingerprints.add(binding_fingerprint)
            external_semantics.append(dict(semantics))
        if len(bcl_review_fingerprints) > 1:
            return reject("external_commitment_review_conflict")
        binding_consumers = tuple(
            sorted(
                {
                    str(value)
                    for value in getattr(
                        implementation_binding,
                        "consumer_surface_ids",
                        (),
                    )
                    if str(value)
                }
            )
        )
        # Candidate-level caller sets describe the group, not an exact member.
        # Copying that aggregate onto every member would let one member's caller
        # manufacture current-necessity authority for a different member.  Only
        # the exact implementation binding can prove this member's consumers.
        caller_ids = binding_consumers
        caller_inventory_complete = not candidate_gap_ids_by_member.get(
            member_id
        )
        # Caller edges answer a contraction question: what would be affected
        # if this surface were merged or removed?  They are not a universal
        # prerequisite for representing current software.  Framework
        # callbacks, protocol methods, properties, and externally invoked
        # surfaces can be exact-current through intent, semantics, bindings,
        # validation, and path-quality evidence without a statically resolved
        # Python caller.  Candidate reduction keeps caller parity and any
        # unresolved caller gaps as mandatory proof obligations.

        semantic_payload = {
            "schema_version": "flowguard.self_reduction_semantic_obligation.v1",
            "declared_semantics": dict(sorted(semantic_dimensions.items())),
            "external_semantics": sorted(
                external_semantics,
                key=lambda row: json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        }
        semantic_obligation_fingerprint = fingerprint_value(semantic_payload)
        relation_evidence_id = (
            str(getattr(relation, "evidence_id", "")) if relation else ""
        )
        relation_fingerprint = (
            str(getattr(relation, "evidence_fingerprint", ""))
            if relation
            else ""
        )
        evidence_fingerprints = tuple(
            sorted(
                {
                    inventory_fingerprint,
                    test_inventory_fingerprint,
                    intent_inventory_fingerprint,
                    behavior_fingerprint,
                    binding_report_fingerprint,
                    str(getattr(surface, "content_fingerprint", "")),
                    str(getattr(surface, "structure_fingerprint", "")),
                    str(
                        getattr(
                            surface_by_id.get(
                                str(
                                    getattr(
                                        contract,
                                        "implementation_surface_id",
                                        "",
                                    )
                                )
                            ),
                            "content_fingerprint",
                            "",
                        )
                    ),
                    str(
                        getattr(
                            surface_by_id.get(
                                str(
                                    getattr(
                                        contract,
                                        "implementation_surface_id",
                                        "",
                                    )
                                )
                            ),
                            "structure_fingerprint",
                            "",
                        )
                    ),
                    str(getattr(contract, "fingerprint", "")),
                    str(getattr(implementation_binding, "fingerprint", "")),
                    *(str(getattr(spec, "fingerprint", "")) for spec in semantic_specs if spec is not None),
                    *(str(getattr(oracles_by_id[oracle_id], "fingerprint", "")) for oracle_id in oracle_ids),
                    *(str(getattr(test_node_by_id[test_id], "source_fingerprint", "")) for test_id in test_node_ids),
                    *(
                        str(
                            declared_test_evidence_fingerprints.get(
                                evidence_id,
                                "",
                            )
                        )
                        for evidence_id in (
                            *model_validation_evidence_ids,
                            *native_validation_evidence_ids,
                        )
                    ),
                    *intent_authority_fingerprints,
                    relation_fingerprint,
                    *bcl_review_fingerprints,
                    *external_binding_fingerprints,
                    path_quality_binding_fingerprint,
                }
                - {""}
            )
        )
        witness_seed = {
            "subject_revision": subject_revision,
            "implementation_inventory_fingerprint": inventory_fingerprint,
            "test_inventory_fingerprint": test_inventory_fingerprint,
            "intent_inventory_fingerprint": intent_inventory_fingerprint,
            "behavior_report_fingerprint": behavior_fingerprint,
            "binding_report_fingerprint": binding_report_fingerprint,
            "member_id": member_id,
            "binding_kind": binding_kind,
            "behavior_block_id": behavior_block_id,
            "model_element_id": model_element_id,
            "owner_contract_id": owner_contract_id,
            "owner_id": owner_id,
            "intent_contribution_ids": contribution_ids,
            "intent_authority_fingerprints": intent_authority_fingerprints,
            "current_goal_rationales": tuple(
                sorted(str(getattr(row, "rationale", "")) for row in typed_contributions)
            ),
            "semantic_obligation_fingerprint": semantic_obligation_fingerprint,
            "semantic_dimensions": tuple(sorted(semantic_dimensions.items())),
            "caller_ids": caller_ids,
            "caller_inventory_complete": caller_inventory_complete,
            "semantic_spec_ids": semantic_spec_ids,
            "oracle_ids": oracle_ids,
            "behavior_case_ids": behavior_case_ids,
            "coverage_ids": coverage_ids,
            "test_node_ids": test_node_ids,
            "model_validation_evidence_ids": (
                model_validation_evidence_ids
            ),
            "current_receipt_ids": current_receipt_ids,
            "behavior_commitment_ids": tuple(sorted(behavior_commitment_ids)),
            "bcl_review_fingerprint": next(iter(bcl_review_fingerprints), ""),
            "path_quality_binding_fingerprint": (
                path_quality_binding_fingerprint
            ),
            "supporting_relation_evidence_id": relation_evidence_id,
            "supporting_relation_fingerprint": relation_fingerprint,
            "evidence_fingerprints": evidence_fingerprints,
        }
        witness = SelfReductionCurrentNecessityWitness(
            witness_id=(
                "self-reduction-necessity:"
                + fingerprint_value(witness_seed).split(":", 1)[1]
            ),
            **witness_seed,
        )
        if necessity_gap_sink is not None:
            necessity_gap_sink.pop(member_id, None)
        return witness

    current_necessity_witness_by_member = {
        member_id: witness
        for member_id in known_surface_ids
        if (witness := current_necessity_witness(member_id)) is not None
    }

    records: list[SelfReductionRetainDisposition] = []
    for member in universe.members:
        if member.member_id in source_gap_ids:
            continue
        basis = ""
        owner_refs: set[str] = set()
        evidence = {
            value
            for value in (
                *member.evidence_fingerprints,
                inventory_fingerprint,
            )
            if value
        }
        rationale = ""
        surface = surface_by_id.get(member.member_id)

        if member.member_kind in _IMPLEMENTATION_MEMBER_KINDS:
            witness = current_necessity_witness_by_member.get(member.member_id)
            if witness is None:
                continue
            basis = "current_necessity_witness"
            owner_refs.update(
                value
                for value in (
                    witness.member_id,
                    witness.behavior_block_id,
                    witness.model_element_id,
                    witness.owner_contract_id,
                    witness.owner_id,
                    *witness.intent_contribution_ids,
                    *witness.caller_ids,
                    *witness.semantic_spec_ids,
                    *witness.oracle_ids,
                    *witness.behavior_commitment_ids,
                    witness.supporting_relation_evidence_id,
                )
                if value
            )
            evidence.update(witness.evidence_fingerprints)
            evidence.update(
                {
                    witness.fingerprint,
                    witness.semantic_obligation_fingerprint,
                }
            )
            rationale = (
                "A complete current necessity witness binds this exact "
                "implementation surface to current intent, source-independent "
                "semantics, one owner, and model-code-test evidence while "
                "preserving caller and external-commitment context for any "
                "later contraction decision."
            )
            seed = {
                "subject_revision": subject_revision,
                "inventory_fingerprint": inventory_fingerprint,
                "test_inventory_fingerprint": test_inventory_fingerprint,
                "universe_fingerprint": universe.fingerprint,
                "member_ids": (member.member_id,),
                "basis": basis,
                "owner_refs": tuple(sorted(owner_refs)),
                "evidence_fingerprints": tuple(sorted(evidence)),
                "member_owner_bindings": (
                    (member.member_id, witness.owner_id),
                ),
                "necessity_witness_fingerprints": (witness.fingerprint,),
                "rationale": rationale,
            }
            records.append(
                SelfReductionRetainDisposition(
                    disposition_id=(
                        "self-reduction-retain:"
                        + fingerprint_value(seed).split(":", 1)[1]
                    ),
                    subject_revision=subject_revision,
                    implementation_inventory_fingerprint=inventory_fingerprint,
                    test_inventory_fingerprint=test_inventory_fingerprint,
                    universe_fingerprint=universe.fingerprint,
                    member_ids=(member.member_id,),
                    basis=basis,
                    owner_refs=tuple(sorted(owner_refs)),
                    evidence_fingerprints=tuple(sorted(evidence)),
                    rationale=rationale,
                    member_owner_bindings=((member.member_id, witness.owner_id),),
                    necessity_witnesses=(witness,),
                )
            )
            continue
        if member.disposition == "retain":
            basis = "current_declared_authority"
            owner_refs.add(member.source_ref or member.member_id)
            rationale = (
                "A current independently discovered authority fact explicitly "
                "owns this non-contraction member."
            )
        elif (
            member.member_kind not in _IMPLEMENTATION_MEMBER_KINDS
            and member.member_kind not in _REDUCTION_SIGNAL_KINDS
            and member.evidence_fingerprints
        ):
            basis = "current_owner_evidence"
            owner_refs.add(member.source_ref or member.member_id)
            rationale = (
                "A current typed model, test, resource, provider, or checker fact "
                "independently owns this denominator member."
            )

        if not basis or not owner_refs or not evidence:
            continue
        authority_key = (
            basis,
            tuple(sorted(owner_refs)),
            tuple(sorted(evidence)),
            rationale,
        )
        member_ids_by_exact_authority.setdefault(authority_key, set()).add(
            member.member_id
        )

    for authority_key, grouped_member_ids in sorted(
        member_ids_by_exact_authority.items()
    ):
        basis, owner_refs, evidence_fingerprints, rationale = authority_key
        member_ids = tuple(sorted(grouped_member_ids))
        seed = {
            "subject_revision": subject_revision,
            "inventory_fingerprint": inventory_fingerprint,
            "test_inventory_fingerprint": test_inventory_fingerprint,
            "universe_fingerprint": universe.fingerprint,
            "member_ids": member_ids,
            "basis": basis,
            "owner_refs": owner_refs,
            "evidence_fingerprints": evidence_fingerprints,
            "rationale": rationale,
        }
        disposition_id = (
            "self-reduction-retain:"
            + fingerprint_value(seed).split(":", 1)[1]
        )
        records.append(
            SelfReductionRetainDisposition(
                disposition_id=disposition_id,
                subject_revision=subject_revision,
                implementation_inventory_fingerprint=inventory_fingerprint,
                test_inventory_fingerprint=test_inventory_fingerprint,
                universe_fingerprint=universe.fingerprint,
                member_ids=member_ids,
                basis=basis,
                owner_refs=owner_refs,
                evidence_fingerprints=evidence_fingerprints,
                rationale=rationale,
            )
        )

    for binding in candidate_bindings:
        if len(binding.member_ids) < 2:
            continue
        witnesses = tuple(
            current_necessity_witness_by_member.get(member_id)
            for member_id in binding.member_ids
        )
        if any(witness is None for witness in witnesses):
            continue
        typed_witnesses = tuple(
            witness for witness in witnesses if witness is not None
        )
        semantic_fingerprints = tuple(
            witness.semantic_obligation_fingerprint
            for witness in typed_witnesses
        )
        member_paths = tuple(
            Path(str(surface_by_id[member_id].path))
            for member_id in binding.member_ids
        )
        independent_validation_roles = bool(
            len(member_paths) == 2
            and member_paths[0].parent == member_paths[1].parent
            and {path.name for path in member_paths}
            == {"model.py", "run_checks.py"}
        )
        different_current_semantics = bool(
            len(set(semantic_fingerprints)) == len(semantic_fingerprints)
        )
        if not different_current_semantics and not independent_validation_roles:
            continue
        basis = (
            "independent_validation_roles"
            if independent_validation_roles
            else "different_current_semantics"
        )
        owner_refs = tuple(
            sorted(
                {
                    owner_ref
                    for witness in typed_witnesses
                    for owner_ref in (
                        witness.member_id,
                        witness.behavior_block_id,
                        witness.model_element_id,
                        witness.owner_contract_id,
                        witness.owner_id,
                        *witness.intent_contribution_ids,
                        *witness.caller_ids,
                        *witness.semantic_spec_ids,
                        *witness.oracle_ids,
                        *witness.behavior_commitment_ids,
                        witness.supporting_relation_evidence_id,
                    )
                    if owner_ref
                }
            )
        )
        evidence_fingerprints = tuple(
            sorted(
                {
                    inventory_fingerprint,
                    test_inventory_fingerprint,
                    behavior_fingerprint,
                    *(witness.fingerprint for witness in typed_witnesses),
                    *semantic_fingerprints,
                    *(evidence_fingerprint
                      for witness in typed_witnesses
                      for evidence_fingerprint in witness.evidence_fingerprints
                      if evidence_fingerprint),
                }
            )
        )
        member_owner_bindings = tuple(
            sorted(
                (witness.member_id, witness.owner_id)
                for witness in typed_witnesses
            )
        )
        rationale = (
            "The model implementation and its independently executable checker "
            "have complete current necessity witnesses, but sharing the helper "
            "that defines the checked operation would couple the oracle to the "
            "implementation; candidate identity scopes the comparison but does "
            "not supply retain authority."
            if independent_validation_roles
            else "Every member of this structural candidate has a complete current "
            "necessity witness and a pairwise different source-independent "
            "semantic obligation; candidate identity scopes the comparison but "
            "does not supply retain authority."
        )
        seed = {
            "subject_revision": subject_revision,
            "inventory_fingerprint": inventory_fingerprint,
            "test_inventory_fingerprint": test_inventory_fingerprint,
            "universe_fingerprint": universe.fingerprint,
            "candidate_ids": (binding.candidate_id,),
            "member_ids": binding.member_ids,
            "basis": basis,
            "owner_refs": owner_refs,
            "evidence_fingerprints": evidence_fingerprints,
            "member_owner_bindings": member_owner_bindings,
            "necessity_witness_fingerprints": tuple(
                witness.fingerprint for witness in typed_witnesses
            ),
            "rationale": rationale,
        }
        records.append(
            SelfReductionRetainDisposition(
                disposition_id=(
                    "self-reduction-retain:"
                    + fingerprint_value(seed).split(":", 1)[1]
                ),
                subject_revision=subject_revision,
                implementation_inventory_fingerprint=inventory_fingerprint,
                test_inventory_fingerprint=test_inventory_fingerprint,
                universe_fingerprint=universe.fingerprint,
                member_ids=binding.member_ids,
                basis=basis,
                owner_refs=owner_refs,
                evidence_fingerprints=evidence_fingerprints,
                rationale=rationale,
                candidate_ids=(binding.candidate_id,),
                member_owner_bindings=member_owner_bindings,
                necessity_witnesses=typed_witnesses,
            )
        )
    return tuple(sorted(records, key=lambda row: row.disposition_id))


__all__ = [
    "SELF_REDUCTION_CANDIDATE_BINDING_SCHEMA",
    "SELF_REDUCTION_CURRENT_NECESSITY_WITNESS_SCHEMA",
    "SELF_REDUCTION_DISPOSITIONS",
    "SELF_REDUCTION_RETAIN_BASES",
    "SELF_REDUCTION_RETAIN_DISPOSITION_SCHEMA",
    "SELF_REDUCTION_UNIVERSE_SCHEMA",
    "SelfReductionCandidateBinding",
    "SelfReductionCurrentNecessityWitness",
    "SelfReductionRetainDisposition",
    "SelfReductionUniverse",
    "SelfReductionUniverseError",
    "SelfReductionUniverseMember",
    "derive_self_reduction_retain_dispositions",
    "derive_self_reduction_universe",
]
