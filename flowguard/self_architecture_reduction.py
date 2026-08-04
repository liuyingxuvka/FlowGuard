"""Read-only architecture-reduction audit bound to FlowGuard's self blueprint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .architecture_reduction import (
    CANDIDATE_MANUAL_REVIEW,
    PROOF_RISKY_KEEP,
    ROUTE_MODEL_TEST_ALIGNMENT,
    ROUTE_STRUCTURE_MESH,
    TARGET_ACTION_MANUAL_REVIEW,
    ArchitectureReductionCandidate,
    ArchitectureReductionPlan,
    ArchitectureReductionReport,
    ArchitectureReductionTrigger,
    ObservableArchitectureContract,
    review_architecture_reduction,
)
from .evidence_receipts import fingerprint_value
from .self_blueprint import FlowGuardSelfBlueprintBundle, build_flowguard_self_blueprint


SELF_ARCHITECTURE_REDUCTION_SCHEMA = (
    "flowguard.self_architecture_reduction_review.v2"
)


def _reverse_call_alias_index(
    surfaces: tuple[Any, ...],
) -> tuple[dict[str, frozenset[str]], dict[str, frozenset[str]]]:
    """Index exact and final-segment call aliases once for caller lookup."""

    exact: dict[str, set[str]] = {}
    by_short_name: dict[str, set[str]] = {}
    for caller in surfaces:
        caller_id = str(caller.surface_id)
        for raw_call in getattr(caller, "calls", ()):
            call = str(raw_call)
            exact.setdefault(call, set()).add(caller_id)
            by_short_name.setdefault(call.rsplit(".", 1)[-1], set()).add(
                caller_id
            )
    return (
        {key: frozenset(value) for key, value in exact.items()},
        {key: frozenset(value) for key, value in by_short_name.items()},
    )


def _indexed_caller_ids(
    members: tuple[Any, ...],
    *,
    exact_callers: dict[str, frozenset[str]],
    short_name_callers: dict[str, frozenset[str]],
) -> tuple[str, ...]:
    """Resolve the same caller relation as the prior nested scan."""

    caller_ids: set[str] = set()
    for member in members:
        symbol = str(getattr(member, "symbol", member.surface_id))
        short_name = symbol.rsplit(".", 1)[-1]
        caller_ids.update(exact_callers.get(symbol, ()))
        caller_ids.update(exact_callers.get(short_name, ()))
        caller_ids.update(short_name_callers.get(short_name, ()))
    return tuple(sorted(caller_ids))


@dataclass(frozen=True)
class SelfArchitectureReductionReview:
    self_blueprint_fingerprint: str
    implementation_inventory_fingerprint: str
    behavior_report_fingerprint: str
    candidate_inventory_fingerprint: str
    candidates: tuple[ArchitectureReductionCandidate, ...]
    reduction_report: ArchitectureReductionReport
    denominator_complete: bool
    safe_unapplied_candidate_ids: tuple[str, ...]
    status: str

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    @property
    def schema_version(self) -> str:
        return SELF_ARCHITECTURE_REDUCTION_SCHEMA

    @property
    def claim_boundary(self) -> str:
        return (
            "This read-only review finds structural contraction candidates "
            "from the exact current self blueprint. Similarity and size are "
            "not behavior-equivalence proof, and this review edits no code."
        )

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "self_blueprint_fingerprint": self.self_blueprint_fingerprint,
            "implementation_inventory_fingerprint": (
                self.implementation_inventory_fingerprint
            ),
            "behavior_report_fingerprint": self.behavior_report_fingerprint,
            "candidate_inventory_fingerprint": (
                self.candidate_inventory_fingerprint
            ),
            "candidates": [row.to_dict() for row in self.candidates],
            "reduction_report": self.reduction_report.to_dict(),
            "denominator_complete": self.denominator_complete,
            "safe_unapplied_candidate_ids": list(
                self.safe_unapplied_candidate_ids
            ),
            "status": self.status,
            "claim_boundary": self.claim_boundary,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "ok": self.ok, "fingerprint": self.fingerprint}


def _self_reduction_candidates(
    bundle: FlowGuardSelfBlueprintBundle,
) -> tuple[tuple[ArchitectureReductionCandidate, ...], str]:
    surfaces = tuple(bundle.inventory.surfaces)
    surface_by_id = {row.surface_id: row for row in surfaces}
    required_surface_ids = set(bundle.inventory.required_surface_ids)
    exact_callers, short_name_callers = _reverse_call_alias_index(surfaces)
    by_path: dict[str, list[Any]] = {}
    for surface in surfaces:
        if surface.surface_id not in required_surface_ids:
            continue
        by_path.setdefault(surface.path, []).append(surface)

    candidate_payloads: list[dict[str, Any]] = []

    def append_group(
        signal: str,
        members: list[Any] | tuple[Any, ...],
        *,
        group_key: str,
        disposition: str = "unresolved",
        extra: dict[str, Any] | None = None,
    ) -> None:
        exact_members = tuple(sorted(members, key=lambda row: row.surface_id))
        if not exact_members:
            return
        payload = {
            "signal": signal,
            "group_key": group_key,
            "disposition": disposition,
            "paths": tuple(sorted({row.path for row in exact_members})),
            "member_ids": tuple(row.surface_id for row in exact_members),
            "caller_ids": _indexed_caller_ids(
                exact_members,
                exact_callers=exact_callers,
                short_name_callers=short_name_callers,
            ),
            "public_entrypoint_ids": tuple(
                row.surface_id
                for row in exact_members
                if "entrypoint" in getattr(row, "roles", ())
                or row.surface_kind == "entrypoint"
            ),
        }
        if extra:
            payload.update(extra)
        candidate_payloads.append(payload)
    for path, members in sorted(by_path.items()):
        max_line = max((row.line_end for row in members), default=0)
        if len(members) < 150 and max_line < 2500:
            continue
        append_group(
            "oversized_module",
            members,
            group_key=path,
            extra={"surface_count": len(members), "max_line": max_line},
        )

    behavior_surface_ids = {
        row.implementation_surface_id for row in bundle.behavior_report.contracts
    }
    by_shape: dict[str, list[Any]] = {}
    for surface_id in behavior_surface_ids:
        surface = surface_by_id[surface_id]
        by_shape.setdefault(surface.structure_fingerprint, []).append(surface)
    for structure_fingerprint, members in sorted(by_shape.items()):
        paths = {row.path for row in members}
        if len(members) < 3 or len(paths) < 2:
            continue
        append_group(
            "repeated_behavior_shape",
            members,
            group_key=structure_fingerprint,
            extra={"structure_fingerprint": structure_fingerprint},
        )

    required_surfaces = tuple(
        row
        for row in surfaces
        if row.surface_id in required_surface_ids
        and row.surface_kind not in {"module", "class"}
    )

    def grouped_candidates(
        signal: str,
        selected: tuple[Any, ...],
        key_builder: Any,
        *,
        public_is_retain: bool = False,
    ) -> None:
        groups: dict[str, list[Any]] = {}
        for surface in selected:
            key = str(key_builder(surface))
            if key:
                groups.setdefault(key, []).append(surface)
        for key, members in sorted(groups.items()):
            if len(members) < 2 or len({row.path for row in members}) < 2:
                continue
            disposition = (
                "retain"
                if public_is_retain
                and any(
                    "entrypoint" in getattr(row, "roles", ())
                    or row.surface_kind == "entrypoint"
                    for row in members
                )
                else "unresolved"
            )
            append_group(
                signal,
                members,
                group_key=key,
                disposition=disposition,
            )

    entrypoints = tuple(
        row
        for row in required_surfaces
        if "entrypoint" in getattr(row, "roles", ())
        or row.surface_kind == "entrypoint"
    )
    grouped_candidates(
        "duplicate_route",
        entrypoints,
        lambda row: "|".join(getattr(row, "calls", ()))
        or row.structure_fingerprint,
        public_is_retain=True,
    )
    grouped_candidates(
        "duplicate_branch",
        tuple(row for row in required_surfaces if len(getattr(row, "calls", ())) >= 2),
        lambda row: "|".join(getattr(row, "calls", ())),
    )
    grouped_candidates(
        "adapter_layer",
        tuple(
            row
            for row in required_surfaces
            if any(
                token
                in (row.path + "#" + getattr(row, "symbol", row.surface_id)).lower()
                for token in ("adapter", "provider", "discover")
            )
        ),
        lambda row: "|".join(getattr(row, "calls", ()))
        or row.structure_fingerprint,
    )
    grouped_candidates(
        "wrapper_or_facade",
        tuple(
            row
            for row in required_surfaces
            if len(getattr(row, "calls", ())) <= 1
            and not getattr(row, "symbol", row.surface_id)
            .rsplit(".", 1)[-1]
            .startswith("_")
        ),
        lambda row: "|".join(getattr(row, "calls", ()))
        or row.structure_fingerprint,
        public_is_retain=True,
    )
    grouped_candidates(
        "helper_path",
        tuple(
            row
            for row in required_surfaces
            if getattr(row, "symbol", row.surface_id)
            .rsplit(".", 1)[-1]
            .startswith("_")
        ),
        lambda row: "|".join(getattr(row, "calls", ()))
        or row.structure_fingerprint,
    )
    grouped_candidates(
        "validation_path",
        tuple(
            row
            for row in required_surfaces
            if any(
                token
                in getattr(row, "symbol", row.surface_id)
                .rsplit(".", 1)[-1]
                .lower()
                for token in ("check", "review", "validate", "verify", "audit")
            )
        ),
        lambda row: "|".join(getattr(row, "calls", ()))
        or row.structure_fingerprint,
    )

    inventory_payload = {
        "implementation_inventory_fingerprint": bundle.inventory.inventory_fingerprint,
        "behavior_report_fingerprint": bundle.behavior_report.fingerprint,
        "signal_policy": {
            "oversized_module": {"surface_count_gte": 150, "max_line_gte": 2500},
            "repeated_behavior_shape": {
                "member_count_gte": 3,
                "distinct_path_count_gte": 2,
            },
            "duplicate_route": "same current call/structure signature across entrypoints",
            "duplicate_branch": "same ordered multi-call branch signature",
            "adapter_layer": "same adapter/provider/discovery delegation signature",
            "wrapper_or_facade": "same zero/one-call public delegation signature",
            "helper_path": "same private helper delegation signature",
            "validation_path": "same validation/review/check delegation signature",
        },
        "candidate_payloads": candidate_payloads,
    }
    inventory_fingerprint = fingerprint_value(inventory_payload)
    candidates: list[ArchitectureReductionCandidate] = []
    for index, payload in enumerate(candidate_payloads, 1):
        signal = str(payload["signal"])
        node_id = str(payload["member_ids"][0])
        next_route = (
            ROUTE_STRUCTURE_MESH
            if payload.get("public_entrypoint_ids")
            or signal
            in {
                "oversized_module",
                "duplicate_route",
                "adapter_layer",
                "wrapper_or_facade",
                "helper_path",
            }
            else ROUTE_MODEL_TEST_ALIGNMENT
        )
        candidates.append(
            ArchitectureReductionCandidate(
                candidate_id=f"self-reduction:{signal}:{index:04d}",
                candidate_type=CANDIDATE_MANUAL_REVIEW,
                code_node_id=node_id,
                source_model_element=(
                    "self-blueprint:" + bundle.manifest.fingerprint
                ),
                target_action=TARGET_ACTION_MANUAL_REVIEW,
                proof_status=PROOF_RISKY_KEEP,
                required_next_route=next_route,
                rationale=(
                    "The independent inventory found a size or repeated-shape "
                    "signal, but the current evidence does not prove observable "
                    "behavior equivalence, so automatic contraction is forbidden."
                ),
                evidence_refs=(
                    bundle.manifest.fingerprint,
                    bundle.behavior_report.fingerprint,
                    inventory_fingerprint,
                ),
                inventory_revision=inventory_fingerprint,
                metadata=payload,
                affected_public_entrypoints=tuple(
                    payload.get("public_entrypoint_ids", ())
                ),
            )
        )
    return tuple(candidates), inventory_fingerprint


def review_flowguard_self_architecture_reduction(
    root: str = ".",
    *,
    self_blueprint: FlowGuardSelfBlueprintBundle | None = None,
) -> SelfArchitectureReductionReview:
    """Audit current self-model contraction opportunities without changing files."""

    bundle = self_blueprint or build_flowguard_self_blueprint(root)
    candidates, inventory_fingerprint = _self_reduction_candidates(bundle)
    entrypoints = tuple(
        sorted(
            row.surface_id
            for row in bundle.inventory.surfaces
            if "entrypoint" in row.roles or row.surface_kind == "entrypoint"
        )
    ) or ("flowguard.public_api", "python -m flowguard")
    plan = ArchitectureReductionPlan(
        reduction_id="flowguard:self-architecture-reduction",
        observable_contract=ObservableArchitectureContract(
            source_model_id=bundle.manifest.fingerprint,
            source_code_boundary_id=bundle.inventory.inventory_fingerprint,
            public_entrypoints=entrypoints,
            observable_outputs=(
                "flowguard.self_blueprint.bundle",
                "flowguard.cli.machine_output",
            ),
            observable_state=(
                "observed_model_authority",
                "current_evidence_pointers",
            ),
            observable_side_effects=("explicit_command_owned_writes",),
            validation_boundaries=(
                bundle.qualification.static_fingerprint,
                bundle.static_readiness.fingerprint,
            ),
            rationale=(
                "Any contraction must preserve the exact current self-blueprint, "
                "public entrypoints, machine output, state authority, and evidence gates."
            ),
        ),
        candidates=candidates,
        companion_route_triggers=(
            ArchitectureReductionTrigger(
                route_id=ROUTE_STRUCTURE_MESH,
                trigger_reason=(
                    "The self-blueprint inventory independently reports module size "
                    "and repeated behavior-shape signals."
                ),
                complexity_signal="self_blueprint_candidate_inventory",
                recommended_timing="before release completion",
            ),
        ),
        rationale=(
            "Use the exact self blueprint to prevent unchecked architectural growth "
            "without treating resemblance as proof or rewriting code automatically."
        ),
        inventory_revision=inventory_fingerprint,
        inventory_source_ref=(
            "self-blueprint:" + bundle.inventory.inventory_fingerprint
        ),
        inventory_current=True,
        expected_candidate_ids=tuple(row.candidate_id for row in candidates),
        require_complete_inventory=True,
    )
    reduction_report = review_architecture_reduction(plan)
    expected = tuple(sorted(row.candidate_id for row in candidates))
    covered = tuple(sorted(reduction_report.covered_candidate_ids))
    denominator_complete = expected == covered
    safe_unapplied = tuple(sorted(reduction_report.ready_candidate_ids))
    status = (
        "pass"
        if bundle.ok
        and reduction_report.ok
        and denominator_complete
        and not safe_unapplied
        else "blocked"
    )
    return SelfArchitectureReductionReview(
        self_blueprint_fingerprint=bundle.manifest.fingerprint,
        implementation_inventory_fingerprint=bundle.inventory.inventory_fingerprint,
        behavior_report_fingerprint=bundle.behavior_report.fingerprint,
        candidate_inventory_fingerprint=inventory_fingerprint,
        candidates=candidates,
        reduction_report=reduction_report,
        denominator_complete=denominator_complete,
        safe_unapplied_candidate_ids=safe_unapplied,
        status=status,
    )


__all__ = [
    "SELF_ARCHITECTURE_REDUCTION_SCHEMA",
    "SelfArchitectureReductionReview",
    "review_flowguard_self_architecture_reduction",
]
