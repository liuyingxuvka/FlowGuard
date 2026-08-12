"""Read-only preview of the exact current model-system revision boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model_authority import ModelAuthorityError, canonical_fingerprint
from .model_authority_store import (
    _accepted_revision_schema,
    load_current_accepted_revision_set,
    load_observed_model_system,
)
from .model_intent_authority import (
    INITIAL_AUTHORITY_BOOTSTRAP_SCHEMA,
    LEGACY_CURRENT_REVISION_SCHEMA,
    LEGACY_CURRENT_REVISION_SCHEMAS,
    LegacyIntentAuditEntry,
    _bootstrap_source_audit,
    _current_model_owner_relations,
)
from .model_revision_set import (
    MODEL_REVISION_SET_CURRENT_SCHEMA,
    RevisionAffectedClosure,
    RevisionSnapshotDiff,
    derive_revision_affected_closure,
    derive_revision_snapshot_diff,
)
from .model_system_inventory import build_manifest_model_system_snapshot
from .project_manifest import ProjectManifestError


MODEL_REVISION_PLAN_SCHEMA = "flowguard.model_revision_plan.v2"
MODEL_REVISION_PLAN_COMPACT_PROJECTION_SCHEMA = (
    "flowguard.model_revision_plan.compact_projection.v2"
)
MODEL_REVISION_PLAN_CANDIDATE_OWNER_INVENTORY_SCHEMA = (
    "flowguard.model_revision_plan.candidate_owner_inventory.v1"
)
MODEL_REVISION_PLAN_LEGACY_ENTRY_INVENTORY_SCHEMA = (
    "flowguard.model_revision_plan.legacy_entry_inventory.v1"
)
MODEL_REVISION_PLAN_TRANSITION_PREDECESSOR_INVENTORY_SCHEMA = (
    "flowguard.model_revision_plan.transition_predecessor_inventory.v1"
)
MODEL_REVISION_PLAN_INTENT_INPUT_IDENTITY_SCHEMA = (
    "flowguard.model_revision_plan.intent_input_identity.v1"
)


@dataclass(frozen=True)
class ModelRevisionPlanCandidateOwner:
    """One exact owner in the independently derived candidate denominator."""

    model_owner_id: str
    logical_model_id: str
    realization_relation_id: str
    realization_relation_fingerprint: str

    def to_dict(self) -> dict[str, str]:
        return {
            "model_owner_id": self.model_owner_id,
            "logical_model_id": self.logical_model_id,
            "realization_relation_id": self.realization_relation_id,
            "realization_relation_fingerprint": (
                self.realization_relation_fingerprint
            ),
        }


@dataclass(frozen=True)
class ModelRevisionPlanTransitionPredecessor:
    """One active base contribution that a refinement must dispose."""

    prior_contribution_id: str
    prior_contribution_fingerprint: str

    def to_dict(self) -> dict[str, str]:
        return {
            "prior_contribution_id": self.prior_contribution_id,
            "prior_contribution_fingerprint": (
                self.prior_contribution_fingerprint
            ),
        }


@dataclass(frozen=True)
class _IntentPlanBoundary:
    """Base-authority facts needed before the live candidate is available."""

    accepted_revision_schema: str = ""
    accepted_revision_fingerprint: str = ""
    base_effective_intent_view_fingerprint: str = ""
    intent_mode: str = "blocked"
    required_command: str = ""
    required_legacy_intent_entries: tuple[LegacyIntentAuditEntry, ...] = ()
    required_transition_predecessors: tuple[
        ModelRevisionPlanTransitionPredecessor, ...
    ] = ()
    required_intent_input_kinds: tuple[str, ...] = ()


def _inventory_fingerprint(
    schema: str,
    rows: tuple[dict[str, Any], ...],
) -> str:
    return canonical_fingerprint({"schema": schema, "members": list(rows)})


@dataclass(frozen=True)
class ModelRevisionPlanBlocker:
    """One visible reason the live revision denominator cannot be trusted."""

    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class ModelRevisionPlan:
    """A stable, non-persisted base-to-live-candidate revision preview."""

    root: str
    requested_snapshot_id: str
    status: str
    observed_head_fingerprint: str = ""
    base_snapshot_id: str = ""
    base_snapshot_fingerprint: str = ""
    candidate_snapshot_fingerprint: str = ""
    base_model_ids: tuple[str, ...] = ()
    candidate_model_ids: tuple[str, ...] = ()
    accepted_revision_schema: str = ""
    accepted_revision_fingerprint: str = ""
    base_effective_intent_view_fingerprint: str = ""
    intent_mode: str = "blocked"
    required_command: str = ""
    candidate_model_owners: tuple[
        ModelRevisionPlanCandidateOwner, ...
    ] = ()
    candidate_model_owner_inventory_fingerprint: str = ""
    required_legacy_intent_entries: tuple[LegacyIntentAuditEntry, ...] = ()
    required_legacy_intent_entry_inventory_fingerprint: str = ""
    required_transition_predecessors: tuple[
        ModelRevisionPlanTransitionPredecessor, ...
    ] = ()
    required_transition_predecessor_inventory_fingerprint: str = ""
    required_intent_input_kinds: tuple[str, ...] = ()
    snapshot_diff: RevisionSnapshotDiff | None = None
    affected_closure: RevisionAffectedClosure | None = None
    blockers: tuple[ModelRevisionPlanBlocker, ...] = ()
    schema: str = MODEL_REVISION_PLAN_SCHEMA
    claim_boundary: str = (
        "This is a read-only preview derived from the sole observed authority "
        "and one stable live manifest candidate. It writes no snapshot, receipt, "
        "revision set, lease, lock, or pointer; runs no model or validation owner; "
        "and supplies no acceptance, activation, release, or completion evidence."
    )

    @property
    def intent_input_identity_fingerprint(self) -> str:
        """Bind the exact base, candidate denominator, and required input shape."""

        if (
            self.intent_mode not in {"bootstrap_required", "refine"}
            or not self.required_command
            or not self.candidate_snapshot_fingerprint
            or not self.candidate_model_owner_inventory_fingerprint
        ):
            return ""
        return canonical_fingerprint(
            {
                "schema": MODEL_REVISION_PLAN_INTENT_INPUT_IDENTITY_SCHEMA,
                "observed_head_fingerprint": self.observed_head_fingerprint,
                "accepted_revision_schema": self.accepted_revision_schema,
                "accepted_revision_fingerprint": (
                    self.accepted_revision_fingerprint
                ),
                "base_effective_intent_view_fingerprint": (
                    self.base_effective_intent_view_fingerprint
                ),
                "candidate_snapshot_fingerprint": (
                    self.candidate_snapshot_fingerprint
                ),
                "candidate_model_owner_inventory_fingerprint": (
                    self.candidate_model_owner_inventory_fingerprint
                ),
                "required_legacy_intent_entry_inventory_fingerprint": (
                    self.required_legacy_intent_entry_inventory_fingerprint
                ),
                "required_transition_predecessor_inventory_fingerprint": (
                    self.required_transition_predecessor_inventory_fingerprint
                ),
                "required_intent_input_kinds": list(
                    self.required_intent_input_kinds
                ),
                "required_command": self.required_command,
            }
        )

    @property
    def ok(self) -> bool:
        return self.status == "pass" and not self.blockers

    @property
    def change_present(self) -> bool:
        return bool(
            self.snapshot_diff is not None
            and (
                self.snapshot_diff.members
                or self.snapshot_diff.added_ids
                or self.snapshot_diff.removed_ids
                or self.snapshot_diff.fingerprint_changed_ids
            )
        )

    @property
    def changed_model_ids(self) -> tuple[str, ...]:
        if self.snapshot_diff is None:
            return ()
        return tuple(item.member_id for item in self.snapshot_diff.members)

    def _model_ids_for_operation(self, operation: str) -> tuple[str, ...]:
        if self.snapshot_diff is None:
            return ()
        return tuple(
            item.member_id
            for item in self.snapshot_diff.members
            if item.operation == operation
        )

    @property
    def changed_entity_ids(self) -> tuple[str, ...]:
        if self.snapshot_diff is None:
            return ()
        return tuple(
            sorted(
                {
                    *self.snapshot_diff.added_ids,
                    *self.snapshot_diff.removed_ids,
                    *self.snapshot_diff.fingerprint_changed_ids,
                }
            )
        )

    @property
    def required_owner_routes(self) -> tuple[str, ...]:
        if self.affected_closure is None:
            return ()
        return tuple(
            sorted(
                {
                    owner_route
                    for _affected_id, owner_route in (
                        self.affected_closure.owner_bindings
                    )
                }
            )
        )

    def to_dict(self) -> dict[str, Any]:
        diff = self.snapshot_diff
        closure = self.affected_closure
        return {
            "schema": self.schema,
            "status": self.status,
            "ok": self.ok,
            "root": self.root,
            "requested_snapshot_id": self.requested_snapshot_id,
            "observed_head_fingerprint": self.observed_head_fingerprint,
            "base_snapshot_id": self.base_snapshot_id,
            "base_snapshot_fingerprint": self.base_snapshot_fingerprint,
            "candidate_snapshot_id": (
                self.requested_snapshot_id
                if self.candidate_snapshot_fingerprint
                else ""
            ),
            "candidate_snapshot_fingerprint": (
                self.candidate_snapshot_fingerprint
            ),
            "base_model_count": len(self.base_model_ids),
            "candidate_model_count": len(self.candidate_model_ids),
            "base_model_ids": list(self.base_model_ids),
            "candidate_model_ids": list(self.candidate_model_ids),
            "accepted_revision_schema": self.accepted_revision_schema,
            "accepted_revision_fingerprint": (
                self.accepted_revision_fingerprint
            ),
            "base_effective_intent_view_fingerprint": (
                self.base_effective_intent_view_fingerprint
            ),
            "intent_mode": self.intent_mode,
            "required_command": self.required_command,
            "candidate_model_owner_count": len(
                self.candidate_model_owners
            ),
            "candidate_model_owner_ids": [
                item.model_owner_id for item in self.candidate_model_owners
            ],
            "candidate_model_owners": [
                item.to_dict() for item in self.candidate_model_owners
            ],
            "candidate_model_owner_inventory_fingerprint": (
                self.candidate_model_owner_inventory_fingerprint
            ),
            "required_legacy_intent_entry_count": len(
                self.required_legacy_intent_entries
            ),
            "required_legacy_intent_entries": [
                item.to_dict()
                for item in self.required_legacy_intent_entries
            ],
            "required_legacy_intent_entry_inventory_fingerprint": (
                self.required_legacy_intent_entry_inventory_fingerprint
            ),
            "required_transition_predecessor_count": len(
                self.required_transition_predecessors
            ),
            "required_transition_predecessors": [
                item.to_dict()
                for item in self.required_transition_predecessors
            ],
            "required_transition_predecessor_inventory_fingerprint": (
                self.required_transition_predecessor_inventory_fingerprint
            ),
            "required_intent_input_kinds": list(
                self.required_intent_input_kinds
            ),
            "intent_input_identity_fingerprint": (
                self.intent_input_identity_fingerprint
            ),
            "change_present": self.change_present,
            "changed_model_ids": list(self.changed_model_ids),
            "added_model_ids": list(self._model_ids_for_operation("add")),
            "removed_model_ids": list(
                self._model_ids_for_operation("remove")
            ),
            "replaced_model_ids": list(
                self._model_ids_for_operation("replace")
            ),
            "changed_entity_ids": list(self.changed_entity_ids),
            "snapshot_diff_fingerprint": diff.fingerprint if diff else "",
            "snapshot_diff": diff.to_dict() if diff else None,
            "affected_closure_fingerprint": (
                closure.fingerprint if closure else ""
            ),
            "affected_closure": closure.to_dict() if closure else None,
            "required_owner_routes": list(self.required_owner_routes),
            "blockers": [item.to_dict() for item in self.blockers],
            "writes_performed": False,
            "models_executed": False,
            "claim_boundary": self.claim_boundary,
        }

    def to_compact_dict(self) -> dict[str, Any]:
        """Project decision-critical identities without materializing detail rows."""

        diff = self.snapshot_diff
        closure = self.affected_closure
        return {
            "schema": self.schema,
            "projection_schema": (
                MODEL_REVISION_PLAN_COMPACT_PROJECTION_SCHEMA
            ),
            "status": self.status,
            "ok": self.ok,
            "root": self.root,
            "requested_snapshot_id": self.requested_snapshot_id,
            "observed_head_fingerprint": self.observed_head_fingerprint,
            "base_snapshot_id": self.base_snapshot_id,
            "base_snapshot_fingerprint": self.base_snapshot_fingerprint,
            "candidate_snapshot_id": (
                self.requested_snapshot_id
                if self.candidate_snapshot_fingerprint
                else ""
            ),
            "candidate_snapshot_fingerprint": (
                self.candidate_snapshot_fingerprint
            ),
            "base_model_count": len(self.base_model_ids),
            "candidate_model_count": len(self.candidate_model_ids),
            "accepted_revision_schema": self.accepted_revision_schema,
            "accepted_revision_fingerprint": (
                self.accepted_revision_fingerprint
            ),
            "base_effective_intent_view_fingerprint": (
                self.base_effective_intent_view_fingerprint
            ),
            "intent_mode": self.intent_mode,
            "required_command": self.required_command,
            "candidate_model_owner_count": len(
                self.candidate_model_owners
            ),
            "candidate_model_owner_inventory_fingerprint": (
                self.candidate_model_owner_inventory_fingerprint
            ),
            "required_legacy_intent_entry_count": len(
                self.required_legacy_intent_entries
            ),
            "required_legacy_intent_entry_inventory_fingerprint": (
                self.required_legacy_intent_entry_inventory_fingerprint
            ),
            "required_transition_predecessor_count": len(
                self.required_transition_predecessors
            ),
            "required_transition_predecessor_inventory_fingerprint": (
                self.required_transition_predecessor_inventory_fingerprint
            ),
            "required_intent_input_kinds": list(
                self.required_intent_input_kinds
            ),
            "intent_input_identity_fingerprint": (
                self.intent_input_identity_fingerprint
            ),
            "change_present": self.change_present,
            "added_model_ids": list(self._model_ids_for_operation("add")),
            "removed_model_ids": list(
                self._model_ids_for_operation("remove")
            ),
            "replaced_model_ids": list(
                self._model_ids_for_operation("replace")
            ),
            "snapshot_diff_fingerprint": diff.fingerprint if diff else "",
            "affected_closure_fingerprint": (
                closure.fingerprint if closure else ""
            ),
            "required_owner_routes": list(self.required_owner_routes),
            "blockers": [item.to_dict() for item in self.blockers],
            "writes_performed": False,
            "models_executed": False,
            "claim_boundary": self.claim_boundary,
        }


def _model_ids(snapshot: Any) -> tuple[str, ...]:
    return tuple(
        sorted(item.logical_model_id for item in snapshot.model_instances)
    )


def _derive_intent_plan_boundary(
    root: Path,
    head: Any,
    base_snapshot: Any,
) -> _IntentPlanBoundary:
    accepted_schema = _accepted_revision_schema(root, head)
    if not accepted_schema:
        raise ModelAuthorityError(
            "the accepted revision schema cannot be read exactly"
        )
    common = {
        "accepted_revision_schema": accepted_schema,
        "accepted_revision_fingerprint": (
            head.accepted_revision_set_fingerprint
        ),
    }
    if accepted_schema == INITIAL_AUTHORITY_BOOTSTRAP_SCHEMA or (
        accepted_schema in LEGACY_CURRENT_REVISION_SCHEMAS
    ):
        audit = _bootstrap_source_audit(root, head, base_snapshot)
        entries = tuple(audit.ancestry_intent_entries)
        return _IntentPlanBoundary(
            **common,
            intent_mode="bootstrap_required",
            required_command="model-revision-intent-bootstrap",
            required_legacy_intent_entries=entries,
            required_intent_input_kinds=(
                "receipt_id",
                "rationale",
                "claim_boundary",
                "current_design_contributions",
                "legacy_entry_dispositions",
            ),
        )
    if accepted_schema != MODEL_REVISION_SET_CURRENT_SCHEMA:
        raise ModelAuthorityError(
            "accepted revision schema cannot supply current intent planning: "
            f"{accepted_schema}"
        )
    revision = load_current_accepted_revision_set(
        root,
        head=head,
        snapshot=base_snapshot,
    )
    if revision is None:
        raise ModelAuthorityError(
            "current v5 authority unexpectedly lacks an accepted revision"
        )
    view = revision.current_effective_intent_view
    predecessors = tuple(
        ModelRevisionPlanTransitionPredecessor(
            prior_contribution_id=item.contribution_id,
            prior_contribution_fingerprint=item.fingerprint,
        )
        for item in sorted(
            view.active_contributions,
            key=lambda contribution: contribution.contribution_id,
        )
    )
    return _IntentPlanBoundary(
        **common,
        base_effective_intent_view_fingerprint=view.fingerprint,
        intent_mode="refine",
        required_command="model-revision-build",
        required_transition_predecessors=predecessors,
        required_intent_input_kinds=(
            "contributions",
            "dispositions",
            "effective_intent_transitions",
        ),
    )


def _candidate_model_owners(
    candidate_snapshot: Any,
) -> tuple[ModelRevisionPlanCandidateOwner, ...]:
    return tuple(
        ModelRevisionPlanCandidateOwner(
            model_owner_id=model_owner_id,
            logical_model_id=logical_model_id,
            realization_relation_id=relation_id,
            realization_relation_fingerprint=relation_fingerprint,
        )
        for (
            model_owner_id,
            logical_model_id,
            relation_id,
            relation_fingerprint,
        ) in _current_model_owner_relations(candidate_snapshot)
    )


def _plan_inventory_fingerprints(
    *,
    candidate_model_owners: tuple[ModelRevisionPlanCandidateOwner, ...],
    intent_boundary: _IntentPlanBoundary,
) -> tuple[str, str, str]:
    owner_fingerprint = (
        _inventory_fingerprint(
            MODEL_REVISION_PLAN_CANDIDATE_OWNER_INVENTORY_SCHEMA,
            tuple(item.to_dict() for item in candidate_model_owners),
        )
        if candidate_model_owners
        else ""
    )
    legacy_fingerprint = (
        _inventory_fingerprint(
            MODEL_REVISION_PLAN_LEGACY_ENTRY_INVENTORY_SCHEMA,
            tuple(
                item.to_dict()
                for item in intent_boundary.required_legacy_intent_entries
            ),
        )
        if intent_boundary.intent_mode == "bootstrap_required"
        else ""
    )
    predecessor_fingerprint = (
        _inventory_fingerprint(
            MODEL_REVISION_PLAN_TRANSITION_PREDECESSOR_INVENTORY_SCHEMA,
            tuple(
                item.to_dict()
                for item in intent_boundary.required_transition_predecessors
            ),
        )
        if intent_boundary.intent_mode == "refine"
        else ""
    )
    return owner_fingerprint, legacy_fingerprint, predecessor_fingerprint


def _blocked_plan(
    root: Path,
    snapshot_id: str,
    *,
    code: str,
    message: str,
    observed_head_fingerprint: str = "",
    base_snapshot: Any | None = None,
    candidate_snapshot: Any | None = None,
    snapshot_diff: RevisionSnapshotDiff | None = None,
    intent_boundary: _IntentPlanBoundary | None = None,
    candidate_model_owners: tuple[
        ModelRevisionPlanCandidateOwner, ...
    ] = (),
) -> ModelRevisionPlan:
    intent = intent_boundary or _IntentPlanBoundary()
    (
        owner_inventory_fingerprint,
        legacy_inventory_fingerprint,
        predecessor_inventory_fingerprint,
    ) = _plan_inventory_fingerprints(
        candidate_model_owners=candidate_model_owners,
        intent_boundary=intent,
    )
    return ModelRevisionPlan(
        root=str(root),
        requested_snapshot_id=snapshot_id,
        status="blocked",
        observed_head_fingerprint=observed_head_fingerprint,
        base_snapshot_id=(base_snapshot.snapshot_id if base_snapshot else ""),
        base_snapshot_fingerprint=(
            base_snapshot.fingerprint if base_snapshot else ""
        ),
        candidate_snapshot_fingerprint=(
            candidate_snapshot.fingerprint if candidate_snapshot else ""
        ),
        base_model_ids=_model_ids(base_snapshot) if base_snapshot else (),
        candidate_model_ids=(
            _model_ids(candidate_snapshot) if candidate_snapshot else ()
        ),
        accepted_revision_schema=intent.accepted_revision_schema,
        accepted_revision_fingerprint=(
            intent.accepted_revision_fingerprint
        ),
        base_effective_intent_view_fingerprint=(
            intent.base_effective_intent_view_fingerprint
        ),
        intent_mode=intent.intent_mode,
        required_command=intent.required_command,
        candidate_model_owners=candidate_model_owners,
        candidate_model_owner_inventory_fingerprint=(
            owner_inventory_fingerprint
        ),
        required_legacy_intent_entries=(
            intent.required_legacy_intent_entries
        ),
        required_legacy_intent_entry_inventory_fingerprint=(
            legacy_inventory_fingerprint
        ),
        required_transition_predecessors=(
            intent.required_transition_predecessors
        ),
        required_transition_predecessor_inventory_fingerprint=(
            predecessor_inventory_fingerprint
        ),
        required_intent_input_kinds=intent.required_intent_input_kinds,
        snapshot_diff=snapshot_diff,
        blockers=(ModelRevisionPlanBlocker(code=code, message=message),),
    )


def preview_current_model_revision(
    root: str | Path,
    *,
    snapshot_id: str,
) -> ModelRevisionPlan:
    """Preview one exact current revision without any write or execution owner."""

    root_path = Path(root).resolve()
    candidate_snapshot_id = str(snapshot_id).strip()
    if not candidate_snapshot_id:
        return _blocked_plan(
            root_path,
            candidate_snapshot_id,
            code="snapshot_id_required",
            message="a non-empty current candidate snapshot id is required",
        )

    expected_failures = (
        ModelAuthorityError,
        ProjectManifestError,
        OSError,
        TypeError,
        ValueError,
    )
    try:
        head, base = load_observed_model_system(root_path)
    except expected_failures as exc:
        return _blocked_plan(
            root_path,
            candidate_snapshot_id,
            code="observed_authority_unavailable",
            message=str(exc),
        )

    try:
        intent_boundary = _derive_intent_plan_boundary(
            root_path,
            head,
            base,
        )
    except expected_failures as exc:
        accepted_schema = ""
        try:
            accepted_schema = _accepted_revision_schema(root_path, head)
        except expected_failures:
            # The blocker must remain serializable even when the same corrupt
            # or unreadable authority input prevents a diagnostic-only schema
            # lookup.  The original error remains the useful failure reason.
            pass
        return _blocked_plan(
            root_path,
            candidate_snapshot_id,
            code="current_intent_plan_unavailable",
            message=str(exc),
            observed_head_fingerprint=head.fingerprint,
            base_snapshot=base,
            intent_boundary=_IntentPlanBoundary(
                accepted_revision_schema=accepted_schema,
                accepted_revision_fingerprint=(
                    head.accepted_revision_set_fingerprint
                ),
            ),
        )

    try:
        candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=candidate_snapshot_id,
            system_id=base.system_id,
            subject_lane=base.subject_lane,
            lifecycle=base.lifecycle,
        )
    except expected_failures as exc:
        return _blocked_plan(
            root_path,
            candidate_snapshot_id,
            code="live_candidate_unavailable",
            message=str(exc),
            observed_head_fingerprint=head.fingerprint,
            base_snapshot=base,
            intent_boundary=intent_boundary,
        )

    try:
        candidate_model_owners = _candidate_model_owners(candidate)
    except expected_failures as exc:
        return _blocked_plan(
            root_path,
            candidate_snapshot_id,
            code="candidate_model_owner_denominator_unavailable",
            message=str(exc),
            observed_head_fingerprint=head.fingerprint,
            base_snapshot=base,
            candidate_snapshot=candidate,
            intent_boundary=intent_boundary,
        )

    try:
        diff = derive_revision_snapshot_diff(base, candidate)
    except expected_failures as exc:
        return _blocked_plan(
            root_path,
            candidate_snapshot_id,
            code="snapshot_diff_unavailable",
            message=str(exc),
            observed_head_fingerprint=head.fingerprint,
            base_snapshot=base,
            candidate_snapshot=candidate,
            intent_boundary=intent_boundary,
            candidate_model_owners=candidate_model_owners,
        )

    try:
        closure = derive_revision_affected_closure(base, candidate, diff)
    except expected_failures as exc:
        return _blocked_plan(
            root_path,
            candidate_snapshot_id,
            code="affected_closure_unavailable",
            message=str(exc),
            observed_head_fingerprint=head.fingerprint,
            base_snapshot=base,
            candidate_snapshot=candidate,
            snapshot_diff=diff,
            intent_boundary=intent_boundary,
            candidate_model_owners=candidate_model_owners,
        )

    try:
        final_head, final_base = load_observed_model_system(root_path)
        if (
            final_head.fingerprint != head.fingerprint
            or final_base.identity_payload() != base.identity_payload()
        ):
            return _blocked_plan(
                root_path,
                candidate_snapshot_id,
                code="observed_authority_changed",
                message=(
                    "the sole observed authority changed during the read-only preview"
                ),
                observed_head_fingerprint=head.fingerprint,
                base_snapshot=base,
                candidate_snapshot=candidate,
                snapshot_diff=diff,
                intent_boundary=intent_boundary,
                candidate_model_owners=candidate_model_owners,
            )
        final_candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=candidate_snapshot_id,
            system_id=base.system_id,
            subject_lane=base.subject_lane,
            lifecycle=base.lifecycle,
        )
        if final_candidate.identity_payload() != candidate.identity_payload():
            return _blocked_plan(
                root_path,
                candidate_snapshot_id,
                code="live_candidate_changed",
                message=(
                    "live model inputs changed during the read-only preview"
                ),
                observed_head_fingerprint=head.fingerprint,
                base_snapshot=base,
                candidate_snapshot=candidate,
                snapshot_diff=diff,
                intent_boundary=intent_boundary,
                candidate_model_owners=candidate_model_owners,
            )
    except expected_failures as exc:
        return _blocked_plan(
            root_path,
            candidate_snapshot_id,
            code="preview_freshness_unavailable",
            message=str(exc),
            observed_head_fingerprint=head.fingerprint,
            base_snapshot=base,
            candidate_snapshot=candidate,
            snapshot_diff=diff,
            intent_boundary=intent_boundary,
            candidate_model_owners=candidate_model_owners,
        )

    (
        owner_inventory_fingerprint,
        legacy_inventory_fingerprint,
        predecessor_inventory_fingerprint,
    ) = _plan_inventory_fingerprints(
        candidate_model_owners=candidate_model_owners,
        intent_boundary=intent_boundary,
    )

    return ModelRevisionPlan(
        root=str(root_path),
        requested_snapshot_id=candidate_snapshot_id,
        status="pass",
        observed_head_fingerprint=head.fingerprint,
        base_snapshot_id=base.snapshot_id,
        base_snapshot_fingerprint=base.fingerprint,
        candidate_snapshot_fingerprint=candidate.fingerprint,
        base_model_ids=_model_ids(base),
        candidate_model_ids=_model_ids(candidate),
        accepted_revision_schema=(
            intent_boundary.accepted_revision_schema
        ),
        accepted_revision_fingerprint=(
            intent_boundary.accepted_revision_fingerprint
        ),
        base_effective_intent_view_fingerprint=(
            intent_boundary.base_effective_intent_view_fingerprint
        ),
        intent_mode=intent_boundary.intent_mode,
        required_command=intent_boundary.required_command,
        candidate_model_owners=candidate_model_owners,
        candidate_model_owner_inventory_fingerprint=(
            owner_inventory_fingerprint
        ),
        required_legacy_intent_entries=(
            intent_boundary.required_legacy_intent_entries
        ),
        required_legacy_intent_entry_inventory_fingerprint=(
            legacy_inventory_fingerprint
        ),
        required_transition_predecessors=(
            intent_boundary.required_transition_predecessors
        ),
        required_transition_predecessor_inventory_fingerprint=(
            predecessor_inventory_fingerprint
        ),
        required_intent_input_kinds=(
            intent_boundary.required_intent_input_kinds
        ),
        snapshot_diff=diff,
        affected_closure=closure,
    )


__all__ = [
    "MODEL_REVISION_PLAN_COMPACT_PROJECTION_SCHEMA",
    "MODEL_REVISION_PLAN_SCHEMA",
    "ModelRevisionPlan",
    "ModelRevisionPlanBlocker",
    "preview_current_model_revision",
]
