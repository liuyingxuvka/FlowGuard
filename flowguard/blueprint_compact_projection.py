"""Bounded AI-facing projections that never serialize whole blueprint objects."""

from __future__ import annotations

from typing import Any, Mapping

from .evidence_receipts import fingerprint_value


BLUEPRINT_COMPACT_PROJECTION_SCHEMA = "flowguard.blueprint_compact_projection.v2"
PROJECT_BLUEPRINT_COMPACT_PROJECTION_SCHEMA = (
    "flowguard.project_blueprint_compact_projection.v1"
)
DEFAULT_MEMBER_LIMIT = 64
DEFAULT_BREAKDOWN_LIMIT = 16
DEFAULT_CANDIDATE_INDEX_LIMIT = 32
_PLANNED_EXECUTION_GAP_CODES = frozenset(
    {
        "missing_code_contract_test_evidence",
        "missing_test_evidence",
        "test_evidence_not_passing",
    }
)


def _stored(value: Any, name: str, default: Any = None) -> Any:
    """Read an already-materialized attribute without invoking a property."""

    namespace = getattr(value, "__dict__", None)
    if isinstance(namespace, dict) and name in namespace:
        return namespace[name]
    return default


def _required_stored(value: Any, name: str, *, context: str) -> Any:
    supplied = _stored(value, name)
    if supplied in (None, ""):
        raise ValueError(f"{context} omits already-materialized {name}")
    return supplied


def _required_stored_or_property(
    value: Any,
    name: str,
    *,
    context: str,
) -> Any:
    """Read a stored scalar or one explicitly declared property, with no fallback."""

    if name != "schema_version":
        raise ValueError(
            f"{context} requests an unsupported compact property: {name}"
        )

    supplied = _stored(value, name)
    if supplied in (None, ""):
        descriptor = getattr(type(value), name, None)
        if isinstance(descriptor, property):
            supplied = descriptor.__get__(value, type(value))
    if supplied in (None, ""):
        raise ValueError(f"{context} omits {name}")
    return supplied


def _bounded(values: Any, limit: int) -> tuple[list[str], int]:
    rows = sorted({str(value) for value in (values or ()) if str(value)})
    return rows[:limit], max(0, len(rows) - limit)


def _bounded_counts(
    counts: dict[str, int], limit: int
) -> tuple[dict[str, int], int]:
    rows = sorted(counts.items())
    return dict(rows[:limit]), max(0, len(rows) - limit)


def _gap_payload(gap: Any) -> dict[str, Any] | None:
    if gap is None:
        return None
    payload = {
        "layer": _stored(gap, "layer", ""),
        "object_kind": _stored(gap, "object_kind", ""),
        "object_id": _stored(gap, "object_id", ""),
        "status": _stored(gap, "status", ""),
        "owner_id": _stored(gap, "owner_id", ""),
        "evidence_ref": _stored(gap, "evidence_ref", ""),
        "message": _stored(gap, "message", ""),
    }
    gap_id = _stored(gap, "gap_id")
    if not gap_id:
        gap_id = "blueprint-gap:" + fingerprint_value(payload).split(":", 1)[-1]
    return {"gap_id": str(gap_id), **payload}


def _finding_breakdowns(
    reports: tuple[tuple[str, Any], ...],
    *,
    limit: int = DEFAULT_BREAKDOWN_LIMIT,
) -> tuple[
    dict[str, int],
    list[dict[str, Any]],
    int,
    dict[str, int],
    list[dict[str, Any]],
    int,
]:
    """Separate static blockers from exact planned-but-not-run evidence gaps."""

    blocking_counts: dict[str, int] = {}
    blocking_examples: dict[str, dict[str, Any]] = {}
    execution_counts: dict[str, int] = {}
    execution_examples: dict[str, dict[str, Any]] = {}
    for report_name, report in reports:
        if report is None:
            continue
        for finding in tuple(_stored(report, "findings", ()) or ()):
            severity = str(_stored(finding, "severity", ""))
            if severity not in {"blocked", "blocker", "error", "stale"}:
                continue
            code = str(_stored(finding, "code", "unknown")) or "unknown"
            key = f"{report_name}:{code}:{severity}"
            planned_execution_gap = bool(
                report_name == "model_test_alignment"
                and _stored(report, "pre_code_status", "") == "ready"
                and _stored(report, "executed_evidence_status", "") == "not_run"
                and code in _PLANNED_EXECUTION_GAP_CODES
            )
            counts = execution_counts if planned_execution_gap else blocking_counts
            examples = (
                execution_examples if planned_execution_gap else blocking_examples
            )
            counts[key] = counts.get(key, 0) + 1
            if key not in examples:
                member_ids, omitted_members = _bounded(
                    _stored(finding, "member_ids", ()),
                    4,
                )
                examples[key] = {
                    "report": report_name,
                    "code": code,
                    "severity": severity,
                    "message": str(_stored(finding, "message", "")),
                    "member_ids": member_ids,
                    "omitted_member_id_count": omitted_members,
                }
    bounded_blocking_counts, omitted_blocking_kinds = _bounded_counts(
        blocking_counts,
        limit,
    )
    bounded_execution_counts, omitted_execution_kinds = _bounded_counts(
        execution_counts,
        limit,
    )
    return (
        bounded_blocking_counts,
        [blocking_examples[key] for key in bounded_blocking_counts],
        omitted_blocking_kinds,
        bounded_execution_counts,
        [execution_examples[key] for key in bounded_execution_counts],
        omitted_execution_kinds,
    )


def compact_understanding_projection(
    summary: Any,
    *,
    member_limit: int = DEFAULT_MEMBER_LIMIT,
) -> dict[str, Any]:
    if member_limit < 1:
        raise ValueError("member_limit must be positive")
    affected_ids = _stored(summary, "affected_ids")
    if affected_ids is None:
        affected_ids = _stored(summary, "affected_surface_ids", ())
    affected, affected_omitted = _bounded(affected_ids, member_limit)
    layers = tuple(_stored(summary, "layer_statuses", ()) or ())
    layer_payload = [
        {"layer": str(layer_id), "status": str(status)}
        for layer_id, status in layers[:member_limit]
    ]
    payload = {
        "schema_version": BLUEPRINT_COMPACT_PROJECTION_SCHEMA,
        "projection_kind": "understanding",
        "scope": str(_stored(summary, "scope", "")),
        "target_system_id": str(_stored(summary, "target_system_id", "")),
        "target_profile": str(_stored(summary, "target_profile", "")),
        "subject_revision": str(_stored(summary, "subject_revision", "")),
        "descriptor_fingerprint": str(
            _stored(summary, "descriptor_fingerprint", "")
        ),
        "blueprint_fingerprint": str(
            _stored(summary, "blueprint_fingerprint", "")
        ),
        "layer_statuses": layer_payload,
        "omitted_layer_count": max(0, len(layers) - member_limit),
        "status": str(_stored(summary, "status", "")),
        "deepest_proven_layer": str(
            _stored(summary, "deepest_proven_layer", "")
        ),
        "first_gap": _gap_payload(_stored(summary, "first_gap")),
        "gap_count": int(_stored(summary, "gap_count", 0) or 0),
        "affected_ids": affected,
        "omitted_affected_id_count": affected_omitted,
        "pre_code_status": str(
            _stored(summary, "pre_code_status", "not_applicable")
        ),
        "executed_evidence_status": str(
            _stored(summary, "executed_evidence_status", "not_applicable")
        ),
        "implementation_admitted": bool(
            _stored(summary, "implementation_admitted", False)
        ),
        "claim_boundary": (
            "Bounded projection of already-materialized normalized identity and "
            "affected readiness fields; it runs no provider, validation owner, "
            "or whole builder."
        ),
    }
    supplied = _stored(summary, "fingerprint")
    payload["fingerprint"] = str(supplied or fingerprint_value(payload))
    return payload


def compact_self_qualification_projection(bundle: Any) -> dict[str, Any]:
    inventory = _stored(bundle, "inventory")
    tests = _stored(bundle, "test_inventory")
    behavior = _stored(bundle, "behavior_report")
    resources = _stored(bundle, "resource_inventory")
    intent = _stored(bundle, "intent_inventory")
    target = _stored(bundle, "target_system_report")
    readiness = _stored(bundle, "static_readiness")
    summary = _stored(bundle, "understanding_summary")
    normalized = _stored(bundle, "normalized_projection")
    bundle_ok = bool(getattr(bundle, "ok", False))
    (
        blocking_counts,
        blocking_examples,
        omitted_blocking_kinds,
        execution_gap_counts,
        execution_gap_examples,
        omitted_execution_gap_kinds,
    ) = _finding_breakdowns(
            (
                ("binding", _stored(bundle, "binding_report")),
                ("topology", _stored(bundle, "topology_report")),
                ("behavior", behavior),
                (
                    "model_test_alignment",
                    _stored(bundle, "model_test_alignment_report"),
                ),
                ("static_readiness", readiness),
            )
        )

    # Compact output consumes only identities already carried by the qualified
    # aggregate.  It must never activate a large cached-property fingerprint or
    # silently substitute another identity when the authoritative field is
    # absent.
    self_fingerprint = _required_stored(
        normalized,
        "blueprint_fingerprint",
        context="normalized projection",
    )
    target_fingerprint = _required_stored(
        summary,
        "blueprint_fingerprint",
        context="understanding summary",
    )
    behavior_fingerprint = _required_stored(
        readiness,
        "behavior_report_fingerprint",
        context="static readiness",
    )
    resource_fingerprint = _required_stored(
        readiness,
        "resource_inventory_fingerprint",
        context="static readiness",
    )
    intent_fingerprint = _required_stored(
        readiness,
        "intent_inventory_fingerprint",
        context="static readiness",
    )

    payload = {
        "schema_version": BLUEPRINT_COMPACT_PROJECTION_SCHEMA,
        "projection_kind": "self_qualification",
        "ok": bundle_ok,
        "self_blueprint_fingerprint": str(self_fingerprint),
        "target_blueprint_fingerprint": str(target_fingerprint),
        "implementation_inventory_fingerprint": str(
            _stored(inventory, "inventory_fingerprint", "")
        ),
        "test_inventory_fingerprint": str(
            _stored(tests, "inventory_fingerprint", "")
        ),
        "behavior_report_fingerprint": str(
            behavior_fingerprint
        ),
        "resource_inventory_fingerprint": str(
            resource_fingerprint
        ),
        "intent_inventory_fingerprint": str(
            intent_fingerprint
        ),
        "target_status": str(getattr(target, "status", "")),
        "static_readiness_status": str(_stored(readiness, "status", "")),
        "deepest_proven_layer": str(
            _stored(summary, "deepest_proven_layer", "")
        ),
        "first_gap": _gap_payload(_stored(summary, "first_gap")),
        "gap_count": int(_stored(summary, "gap_count", 0) or 0),
        "blocking_finding_counts": blocking_counts,
        "blocking_finding_examples": blocking_examples,
        "omitted_blocking_finding_kind_count": omitted_blocking_kinds,
        "execution_gap_counts": execution_gap_counts,
        "execution_gap_examples": execution_gap_examples,
        "omitted_execution_gap_kind_count": omitted_execution_gap_kinds,
        "implementation_admitted": bool(
            _stored(summary, "implementation_admitted", False)
        ),
        "counts": {
            "implementation_surfaces": len(_stored(inventory, "surfaces", ()) or ()),
            "required_implementation_surfaces": len(
                getattr(inventory, "required_surface_ids", ()) or ()
            ),
            "test_nodes": len(_stored(tests, "nodes", ()) or ()),
            "required_test_nodes": len(getattr(tests, "required_node_ids", ()) or ()),
            "behavior_blocks": len(_stored(behavior, "contracts", ()) or ()),
            "coverage_edges": len(_stored(behavior, "coverage_edges", ()) or ()),
            "behavior_findings": len(_stored(behavior, "findings", ()) or ()),
        },
        "resource_inventory_complete": getattr(resources, "complete", None),
        "intent_inventory_complete": getattr(intent, "complete", None),
        "claim_boundary": (
            "Bounded self-qualification status from one already-built self "
            "blueprint; no complete bundle or child report is serialized."
        ),
    }
    payload["fingerprint"] = fingerprint_value(payload)
    return payload


def compact_project_blueprint_projection(
    bundle: Any,
    *,
    member_limit: int = DEFAULT_MEMBER_LIMIT,
    breakdown_limit: int = DEFAULT_BREAKDOWN_LIMIT,
) -> dict[str, Any]:
    """Return a bounded project status without expanding the blueprint.

    This is the project counterpart to ``compact_self_qualification_projection``.
    It deliberately exposes denominator counts, layer/status claims, gaps, and
    export blockers while leaving the canonical shards in their existing owner.
    """

    if member_limit < 1 or breakdown_limit < 1:
        raise ValueError("compact projection limits must be positive")
    inventory = _stored(bundle, "inventory")
    tests = _stored(bundle, "test_inventory")
    behavior = _stored(bundle, "behavior_report")
    alignment = _stored(bundle, "model_test_alignment_report")
    static_readiness = _stored(bundle, "static_readiness")
    target_report = _stored(bundle, "target_system_report")
    understanding = _stored(bundle, "understanding_summary")
    blockers = tuple(
        getattr(bundle, "canonical_export_blockers", ()) or ()
    )
    # ``readiness_ledger`` is intentionally the one qualified property allowed
    # here: it is the already-derived project status and does not run work.
    ledger = getattr(bundle, "readiness_ledger", None)
    rows = tuple(_stored(ledger, "rows", ()) or ())
    gaps = tuple(_stored(ledger, "gaps", ()) or ())
    layer_statuses = [
        {
            "layer": str(_stored(row, "layer_id", "")),
            "status": str(_stored(row, "status", "")),
        }
        for row in rows[:member_limit]
    ]
    gap_ids, omitted_gap_ids = _bounded(
        (_stored(gap, "gap_id", "") for gap in gaps), member_limit
    )
    _, _, _, execution_counts, execution_examples, omitted_execution = _finding_breakdowns(
        (("model_test_alignment", alignment),),
        limit=breakdown_limit,
    )
    payload = {
        "schema_version": PROJECT_BLUEPRINT_COMPACT_PROJECTION_SCHEMA,
        "projection_kind": "project_blueprint",
        "project_blueprint_fingerprint": str(
            getattr(bundle, "fingerprint", "")
        ),
        "canonical_export_ready": bool(
            getattr(bundle, "canonical_export_ready", False)
        ),
        "canonical_export_blockers": list(blockers),
        "status": str(getattr(ledger, "status", "unknown")),
        "static_status": str(_stored(static_readiness, "status", "unknown")),
        "portable_status": (
            "ready"
            if bool(getattr(bundle, "canonical_export_ready", False))
            else "blocked"
        ),
        "execution_status": str(
            _stored(alignment, "executed_evidence_status", "not_run")
        ),
        "target_status": str(_stored(target_report, "status", "unknown")),
        "deepest_proven_layer": str(
            _stored(understanding, "deepest_proven_layer", "")
        ),
        "first_gap": _gap_payload(_stored(understanding, "first_gap")),
        "gap_count": int(_stored(ledger, "gap_count", len(gaps)) or 0),
        "gap_ids": gap_ids,
        "omitted_gap_id_count": omitted_gap_ids,
        "layer_statuses": layer_statuses,
        "omitted_layer_count": max(0, len(rows) - member_limit),
        "execution_gap_counts": execution_counts,
        "execution_gap_examples": execution_examples,
        "omitted_execution_gap_kind_count": omitted_execution,
        "counts": {
            "files": len(_stored(inventory, "file_dispositions", ()) or ()),
            "implementation_surfaces": len(_stored(inventory, "surfaces", ()) or ()),
            "required_implementation_surfaces": len(
                _stored(inventory, "required_surface_ids", ()) or ()
            ),
            "test_nodes": len(_stored(tests, "nodes", ()) or ()),
            "required_test_nodes": len(_stored(tests, "required_node_ids", ()) or ()),
            "behavior_blocks": len(_stored(behavior, "contracts", ()) or ()),
            "coverage_edges": len(_stored(behavior, "coverage_edges", ()) or ()),
        },
        "claim_boundary": (
            "Bounded project status from one qualified canonical bundle; it runs "
            "no provider, source, test owner, export, or reconstruction."
        ),
    }
    payload["projection_fingerprint"] = fingerprint_value(payload)
    return payload


def compact_reduction_projection(
    review: Any,
    *,
    breakdown_limit: int = DEFAULT_BREAKDOWN_LIMIT,
    member_limit: int = DEFAULT_MEMBER_LIMIT,
) -> dict[str, Any]:
    if breakdown_limit < 1 or member_limit < 1:
        raise ValueError("compact projection limits must be positive")
    review_fingerprint = _required_stored(
        review,
        "review_fingerprint",
        context="self architecture reduction review",
    )
    candidates = tuple(_stored(review, "candidates", ()) or ())
    typed_retain_candidate_ids = {
        str(candidate_id)
        for disposition in _stored(review, "retain_dispositions", ()) or ()
        for candidate_id in _stored(disposition, "candidate_ids", ()) or ()
        if str(candidate_id)
    }
    signal_counts: dict[str, int] = {}
    candidate_metadata_dispositions: dict[str, int] = {}
    candidate_necessity_dispositions: dict[str, int] = {}
    missing_proof_counts: dict[str, int] = {}
    unresolved_candidate_count = 0
    missing_proof_obligation_count = 0
    proof_required_candidate_count = 0
    retirement_review_candidate_count = 0
    for candidate in candidates:
        metadata = _stored(candidate, "metadata", {}) or {}
        signal = str(metadata.get("signal", "unclassified"))
        metadata_disposition = str(
            metadata.get("disposition", "unresolved")
        )
        candidate_id = str(_stored(candidate, "candidate_id", ""))
        necessity_disposition = (
            "retain"
            if candidate_id in typed_retain_candidate_ids
            else "contract"
            if metadata_disposition == "contract"
            else "unresolved"
        )
        if necessity_disposition == "unresolved":
            unresolved_candidate_count += 1
        obligations = metadata.get("missing_proof_obligations", ())
        if isinstance(obligations, (tuple, list, set, frozenset)):
            obligation_kinds = tuple(
                str(value) for value in obligations if str(value)
            )
            missing_proof_obligation_count += len(obligation_kinds)
            if obligation_kinds:
                proof_required_candidate_count += 1
            for obligation_kind in obligation_kinds:
                missing_proof_counts[obligation_kind] = (
                    missing_proof_counts.get(obligation_kind, 0) + 1
                )
        if str(_stored(candidate, "target_action", "")) == "retire_behavior":
            retirement_review_candidate_count += 1
        signal_counts[signal] = signal_counts.get(signal, 0) + 1
        candidate_metadata_dispositions[metadata_disposition] = (
            candidate_metadata_dispositions.get(metadata_disposition, 0) + 1
        )
        candidate_necessity_dispositions[necessity_disposition] = (
            candidate_necessity_dispositions.get(necessity_disposition, 0) + 1
        )
    bounded_signals, omitted_signals = _bounded_counts(
        signal_counts, breakdown_limit
    )
    (
        bounded_candidate_metadata_dispositions,
        omitted_candidate_metadata_dispositions,
    ) = _bounded_counts(candidate_metadata_dispositions, breakdown_limit)
    (
        bounded_candidate_necessity_dispositions,
        omitted_candidate_necessity_dispositions,
    ) = _bounded_counts(candidate_necessity_dispositions, breakdown_limit)
    bounded_missing_proof_counts, omitted_missing_proof_kinds = _bounded_counts(
        missing_proof_counts, breakdown_limit
    )
    necessity_gap_counts = dict(
        _stored(review, "necessity_gap_counts_by_kind", ()) or ()
    )
    bounded_necessity_gap_counts, omitted_necessity_gap_kinds = _bounded_counts(
        necessity_gap_counts, breakdown_limit
    )
    necessity_gap_examples = dict(
        _stored(review, "necessity_gap_examples_by_kind", ()) or ()
    )

    universe = _stored(review, "reduction_universe")
    universe_members = tuple(_stored(universe, "members", ()) or ())
    universe_dispositions: dict[str, int] = {}
    unresolved_member_kinds: dict[str, int] = {}
    for member in universe_members:
        disposition = str(_stored(member, "disposition", "unresolved"))
        universe_dispositions[disposition] = (
            universe_dispositions.get(disposition, 0) + 1
        )
        if disposition == "unresolved":
            member_kind = str(
                _stored(member, "member_kind", "unclassified")
                or "unclassified"
            )
            unresolved_member_kinds[member_kind] = (
                unresolved_member_kinds.get(member_kind, 0) + 1
            )
    bounded_universe_dispositions, omitted_universe_dispositions = _bounded_counts(
        universe_dispositions, breakdown_limit
    )
    (
        bounded_unresolved_member_kinds,
        omitted_unresolved_member_kinds,
    ) = _bounded_counts(unresolved_member_kinds, breakdown_limit)

    safe_ids, safe_omitted = _bounded(
        _stored(review, "safe_unapplied_candidate_ids", ()), member_limit
    )
    authorized_ids, authorized_omitted = _bounded(
        _stored(review, "action_authorized_candidate_ids", ()), member_limit
    )
    unresolved_ids, unresolved_omitted = _bounded(
        _stored(review, "unresolved_member_ids", ()), member_limit
    )
    unresolved_step_ids, unresolved_steps_omitted = _bounded(
        _stored(review, "unresolved_step_ids", ()), member_limit
    )
    reduction_report = _stored(review, "reduction_report")
    step_assessments = tuple(
        _stored(reduction_report, "step_assessments", ()) or ()
    )
    step_action_counts: dict[str, int] = {}
    unresolved_step_count = 0
    for assessment in step_assessments:
        action = str(_stored(assessment, "action", "unclassified"))
        step_action_counts[action] = step_action_counts.get(action, 0) + 1
        if action == "unresolved":
            unresolved_step_count += 1
    bounded_step_action_counts, omitted_step_actions = _bounded_counts(
        step_action_counts, breakdown_limit
    )
    next_routes, routes_omitted = _bounded(
        _stored(reduction_report, "required_next_routes", ()), member_limit
    )
    universe_fingerprint = _stored(
        review, "reduction_universe_fingerprint", ""
    ) or _stored(universe, "universe_fingerprint", "")
    status = str(_stored(review, "status", ""))
    candidate_index: list[dict[str, Any]] = []
    candidate_paths: dict[str, int] = {}
    for candidate in sorted(
        candidates,
        key=lambda row: str(_stored(row, "candidate_id", "")),
    )[: min(member_limit, DEFAULT_CANDIDATE_INDEX_LIMIT)]:
        metadata = _stored(candidate, "metadata", {}) or {}
        if not isinstance(metadata, Mapping):
            metadata = {}
        candidate_id = str(_stored(candidate, "candidate_id", ""))
        code_node_id = str(_stored(candidate, "code_node_id", ""))
        candidate_path = code_node_id.split(":", 1)[0] if code_node_id else ""
        if candidate_path:
            candidate_paths[candidate_path] = candidate_paths.get(candidate_path, 0) + 1
        missing = metadata.get("missing_proof_obligations", ())
        candidate_index.append(
            {
                "candidate_id": candidate_id,
                "signal": str(metadata.get("signal", "unclassified")),
                "code_node_id": code_node_id,
                "source_model_element": str(
                    _stored(candidate, "source_model_element", "")
                ),
                "target_action": str(_stored(candidate, "target_action", "")),
                "proof_status": str(_stored(candidate, "proof_status", "")),
                "required_next_route": str(
                    _stored(candidate, "required_next_route", "")
                ),
                "lifecycle_disposition": str(
                    _stored(candidate, "lifecycle_disposition", "")
                ),
                "metadata_disposition": str(metadata.get("disposition", "unresolved")),
                "missing_proof_obligations": [str(value) for value in missing or ()],
                "affected_public_entrypoints": [
                    str(value)
                    for value in (_stored(candidate, "affected_public_entrypoints", ()) or ())
                ],
                "affected_state": [
                    str(value)
                    for value in (_stored(candidate, "affected_state", ()) or ())
                ],
                "affected_side_effects": [
                    str(value)
                    for value in (_stored(candidate, "affected_side_effects", ()) or ())
                ],
            }
        )
    candidate_index_omitted = max(0, len(candidates) - len(candidate_index))
    payload = {
        "schema_version": str(
            _required_stored_or_property(
                review,
                "schema_version",
                context="self architecture reduction review",
            )
        ),
        "projection_schema_version": BLUEPRINT_COMPACT_PROJECTION_SCHEMA,
        "projection_kind": "reduction",
        "review_fingerprint": str(review_fingerprint),
        "status": status,
        "ok": bool(_stored(review, "ok", status == "pass")),
        "self_blueprint_fingerprint": str(
            _stored(review, "self_blueprint_fingerprint", "")
        ),
        "candidate_inventory_fingerprint": str(
            _stored(review, "candidate_inventory_fingerprint", "")
        ),
        "reduction_universe_fingerprint": str(universe_fingerprint),
        "candidate_count": len(candidates),
        "unresolved_candidate_count": unresolved_candidate_count,
        "proof_required_candidate_count": proof_required_candidate_count,
        "retirement_review_candidate_count": (
            retirement_review_candidate_count
        ),
        "missing_proof_obligation_count": missing_proof_obligation_count,
        "missing_proof_counts_by_kind": bounded_missing_proof_counts,
        "omitted_missing_proof_kind_count": omitted_missing_proof_kinds,
        "necessity_gap_counts_by_kind": bounded_necessity_gap_counts,
        "necessity_gap_examples_by_kind": {
            gap_id: list(necessity_gap_examples.get(gap_id, ()))
            for gap_id in bounded_necessity_gap_counts
        },
        "omitted_necessity_gap_kind_count": omitted_necessity_gap_kinds,
        "candidate_counts_by_signal": bounded_signals,
        "omitted_signal_count": omitted_signals,
        "candidate_index": candidate_index,
        "omitted_candidate_index_count": candidate_index_omitted,
        "candidate_counts_by_code_node_prefix": dict(sorted(candidate_paths.items())),
        "candidate_counts_by_necessity_disposition": (
            bounded_candidate_necessity_dispositions
        ),
        "omitted_candidate_necessity_disposition_count": (
            omitted_candidate_necessity_dispositions
        ),
        "candidate_counts_by_metadata_disposition": (
            bounded_candidate_metadata_dispositions
        ),
        "omitted_candidate_metadata_disposition_count": (
            omitted_candidate_metadata_dispositions
        ),
        # Current-name compatibility: this field has always counted only the
        # candidate metadata projection, never typed necessity authority.
        "candidate_counts_by_disposition": dict(
            bounded_candidate_metadata_dispositions
        ),
        "candidate_counts_by_disposition_basis": (
            "candidate.metadata.disposition"
        ),
        "omitted_candidate_disposition_count": (
            omitted_candidate_metadata_dispositions
        ),
        "universe_member_count": len(universe_members),
        "universe_counts_by_disposition": bounded_universe_dispositions,
        "omitted_universe_disposition_count": omitted_universe_dispositions,
        "unresolved_member_counts_by_kind": bounded_unresolved_member_kinds,
        "omitted_unresolved_member_kind_count": (
            omitted_unresolved_member_kinds
        ),
        "denominator_complete": bool(
            _stored(review, "denominator_complete", False)
        ),
        "candidate_review_complete": bool(
            _stored(review, "candidate_review_complete", False)
        ),
        "step_decision_complete": bool(
            _stored(review, "step_decision_complete", False)
        ),
        "audit_accounted": bool(_stored(review, "audit_accounted", False)),
        "audit_complete": bool(_stored(review, "audit_complete", False)),
        "action_authorized_candidate_ids": authorized_ids,
        "omitted_action_authorized_candidate_count": authorized_omitted,
        "cleanup_release_ready": bool(
            _stored(review, "cleanup_release_ready", False)
        ),
        "unresolved_member_ids": unresolved_ids,
        "omitted_unresolved_member_count": unresolved_omitted,
        "unresolved_step_ids": unresolved_step_ids,
        "omitted_unresolved_step_count": unresolved_steps_omitted,
        "step_assessment_count": len(step_assessments),
        "step_action_counts": bounded_step_action_counts,
        "omitted_step_action_count": omitted_step_actions,
        "unresolved_step_count": unresolved_step_count,
        "safe_unapplied_candidate_ids": safe_ids,
        "omitted_safe_unapplied_candidate_count": safe_omitted,
        "decision": str(_stored(reduction_report, "decision", "")),
        "required_next_routes": next_routes,
        "omitted_required_next_route_count": routes_omitted,
        "claim_boundary": str(getattr(review, "claim_boundary", "")),
    }
    payload["projection_fingerprint"] = fingerprint_value(payload)
    return payload


def compact_reduction_candidate_detail(review: Any, candidate_id: str) -> dict[str, Any]:
    """Return one complete candidate row without expanding the full report."""

    requested = str(candidate_id).strip()
    if not requested:
        raise ValueError("candidate_id must be non-empty")
    candidates = tuple(_stored(review, "candidates", ()) or ())
    candidate = next(
        (
            row
            for row in candidates
            if str(_stored(row, "candidate_id", "")) == requested
        ),
        None,
    )
    if candidate is None:
        raise ValueError(f"unknown architecture-reduction candidate: {requested}")
    metadata = _stored(candidate, "metadata", {}) or {}
    if not isinstance(metadata, Mapping):
        raise ValueError("candidate metadata is not a current object")
    payload = {
        "schema_version": BLUEPRINT_COMPACT_PROJECTION_SCHEMA,
        "projection_kind": "reduction_candidate_detail",
        "review_fingerprint": str(
            _required_stored(
                review,
                "review_fingerprint",
                context="self architecture reduction review",
            )
        ),
        "candidate": {
            "candidate_id": requested,
            "candidate_type": str(_stored(candidate, "candidate_type", "")),
            "code_node_id": str(_stored(candidate, "code_node_id", "")),
            "source_model_element": str(
                _stored(candidate, "source_model_element", "")
            ),
            "target_action": str(_stored(candidate, "target_action", "")),
            "proof_status": str(_stored(candidate, "proof_status", "")),
            "required_next_route": str(
                _stored(candidate, "required_next_route", "")
            ),
            "rationale": str(_stored(candidate, "rationale", "")),
            "affected_public_entrypoints": list(
                _stored(candidate, "affected_public_entrypoints", ()) or ()
            ),
            "affected_state": list(_stored(candidate, "affected_state", ()) or ()),
            "affected_side_effects": list(
                _stored(candidate, "affected_side_effects", ()) or ()
            ),
            "evidence_refs": list(_stored(candidate, "evidence_refs", ()) or ()),
            "lifecycle_disposition": str(
                _stored(candidate, "lifecycle_disposition", "")
            ),
            "metadata": dict(metadata),
        },
        "claim_boundary": (
            "One exact current ArchitectureReduction candidate and its proof "
            "neighborhood; no full report, code edit, or authorization is created."
        ),
    }
    payload["fingerprint"] = fingerprint_value(payload)
    return payload


class BlueprintCompactProjection:
    """Namespace for the three bounded AI-facing projection contracts."""

    understanding = staticmethod(compact_understanding_projection)
    self_qualification = staticmethod(compact_self_qualification_projection)
    project = staticmethod(compact_project_blueprint_projection)
    reduction = staticmethod(compact_reduction_projection)


__all__ = [
    "BLUEPRINT_COMPACT_PROJECTION_SCHEMA",
    "PROJECT_BLUEPRINT_COMPACT_PROJECTION_SCHEMA",
    "BlueprintCompactProjection",
    "compact_project_blueprint_projection",
    "compact_reduction_projection",
    "compact_reduction_candidate_detail",
    "compact_self_qualification_projection",
    "compact_understanding_projection",
]
