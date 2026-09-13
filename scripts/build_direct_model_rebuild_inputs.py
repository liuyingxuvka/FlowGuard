"""Create explicit current-model rebuild inputs after manual intent review.

This helper is deliberately not an upgrade reader.  It requires the caller to
name every model that was reviewed.  Unnamed models block instead of being
silently inherited.  Unchanged rows are emitted as explicit ``retain``
transitions; changed rows receive a new contribution id and an explicit
``supersede`` transition.  The old contribution is used only as provenance for
the new decision and never remains authoritative by accident.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
import sys
from typing import Iterable, Mapping, Sequence

# When this helper is launched by an absolute/relative script path, Python's
# default import root is ``scripts/`` rather than the repository.  Keep the
# author-side helper self-contained so its explicit change-manifest loader is
# resolved from this exact checkout, not from an installed or foreign copy.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.model_authority_store import (
    load_current_accepted_revision_set,
    load_observed_model_system,
)
from flowguard.model_authority import load_accepted_boundary_contract
from flowguard.model_authority import (
    build_boundary_contract_from_snapshot,
    write_content_addressed_boundary_contract,
)
from flowguard.model_intent import ModelIntentDisposition
from flowguard.model_intent_authority import EffectiveIntentTransition
from flowguard.model_path_quality import PathQualityResult, PathQualitySubject
from flowguard.model_revision_set import derive_revision_snapshot_diff
from flowguard.model_system_inventory import build_manifest_model_system_snapshot
from flowguard.self_path_quality import compile_flowguard_self_path_quality_material
from flowguard.source_identity import source_file_fingerprint
from flowguard.validation_ownership import (
    manifest_fingerprint,
    validation_input_manifest,
)


def _write_json(path: Path, payload: object) -> None:
    """Write one canonical artifact, or accept the exact same bytes."""

    if path.is_symlink():
        raise RuntimeError(f"refusing to write through symlink: {path}")
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != data:
            raise RuntimeError(f"output already exists with different content: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def _normalise_review_manifest_rows(
    value: object,
    field_name: str,
) -> tuple[dict[str, str], ...]:
    """Validate an embedded change-manifest input table without discovery."""

    if not isinstance(value, list):
        raise RuntimeError(f"review map {field_name} must be an array")
    rows: dict[str, str] = {}
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping) or set(raw) != {"path", "sha256"}:
            raise RuntimeError(
                f"review map {field_name}[{index}] must contain only path and sha256"
            )
        relative = str(raw.get("path") or "").replace("\\", "/")
        parts = tuple(part for part in relative.split("/") if part)
        if (
            not parts
            or relative.startswith("/")
            or any(part in {".", ".."} for part in parts)
        ):
            raise RuntimeError(f"review map {field_name} has unsafe path: {relative}")
        fingerprint = str(raw.get("sha256") or "")
        if not fingerprint.startswith("sha256:") or len(fingerprint) != 71:
            raise RuntimeError(
                f"review map {field_name}[{index}].sha256 is invalid"
            )
        previous = rows.get(relative)
        if previous is not None:
            raise RuntimeError(
                f"review map {field_name} contains duplicate path rows: {relative}"
            )
        rows[relative] = fingerprint
    return tuple(
        {"path": path, "sha256": rows[path]}
        for path in sorted(rows)
    )


def _load_review_map(
    path: Path,
    root: Path,
    *,
    expected_work_id: str = "",
) -> Mapping[str, object]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"review map is missing or symlinked: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"review map is unreadable: {path}") from exc
    if not isinstance(payload, Mapping):
        raise RuntimeError("review map must be a JSON object")
    if str(payload.get("schema_version", "")) != "flowguard.model_review_map.v1":
        raise RuntimeError("review map schema is not current")
    expected = str(payload.get("review_map_fingerprint", ""))
    body = dict(payload)
    body.pop("review_map_fingerprint", None)
    actual = "sha256:" + hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if expected != actual:
        raise RuntimeError("review map fingerprint is not current")
    declared_root = str(payload.get("root") or "").strip()
    declared_work_id = str(payload.get("work_id") or "").strip()
    if (
        not declared_root
        or not Path(declared_root).is_absolute()
        or Path(declared_root).resolve() != root.resolve()
    ):
        raise RuntimeError("review map root is missing or does not match the requested root")
    if not declared_work_id:
        raise RuntimeError("review map work_id is required for an observed map")
    if expected_work_id and declared_work_id != expected_work_id:
        raise RuntimeError("review map work_id does not match the change manifest")
    allowed = payload.get("allowed_model_ids")
    if not isinstance(allowed, list) or any(not str(item).strip() for item in allowed):
        raise RuntimeError("review map allowed_model_ids is incomplete")
    # A self-consistent review-map hash is not enough: every current map must
    # carry the producer's frozen input observation.  The former compact
    # fixture shape (no tested manifest) was a historical reader and allowed
    # an arbitrary self-hashed authorization map to enter the rebuild path.
    tested = payload.get("tested_input_manifest")
    tested_fp = str(payload.get("tested_input_manifest_fingerprint") or "")
    if not isinstance(tested, list) or not tested_fp:
        raise RuntimeError("review map tested input observation is required")
    observed = _normalise_review_manifest_rows(tested, "tested_input_manifest")
    if manifest_fingerprint(observed) != tested_fp:
        raise RuntimeError("review map tested input fingerprint is stale")
    current = validation_input_manifest(root)
    if manifest_fingerprint(current) != tested_fp:
        raise RuntimeError("review map tested input is no longer current")
    embedded_current = payload.get("current_input_manifest")
    embedded_baseline = payload.get("baseline_input_manifest")
    if embedded_current is not None:
        current_rows = _normalise_review_manifest_rows(
            embedded_current, "current_input_manifest"
        )
        live = validation_input_manifest(root)
        if current_rows != live:
            raise RuntimeError("review map current input manifest is stale")
        if tested is not None and current_rows != observed:
            raise RuntimeError(
                "review map current input manifest differs from tested input observation"
            )
    else:
        current_rows = None
    if embedded_baseline is not None:
        baseline_rows = _normalise_review_manifest_rows(
            embedded_baseline, "baseline_input_manifest"
        )
        if current_rows is None:
            raise RuntimeError("review map baseline requires current input manifest")
        baseline_by_path = {row["path"]: row["sha256"] for row in baseline_rows}
        current_by_path = {row["path"]: row["sha256"] for row in current_rows}
        expected_changed = tuple(
            sorted(
                path
                for path in set(baseline_by_path) | set(current_by_path)
                if baseline_by_path.get(path) != current_by_path.get(path)
            )
        )
        declared_changed = tuple(
            sorted(
                str(item).replace("\\", "/")
                for item in payload.get("planned_changed_paths", ())
            )
        )
        if declared_changed != expected_changed:
            raise RuntimeError(
                "review map planned_changed_paths do not match embedded input manifests"
            )
    return payload


def _changed_models(diff) -> tuple[str, ...]:
    return tuple(
        sorted(
            member.member_id
            for member in diff.members
            if member.operation in {"add", "replace"}
        )
    )


def _relation_model_endpoint_deltas(
    relation_id: str,
    *,
    base_snapshot=None,
    candidate_snapshot=None,
) -> tuple[str, ...]:
    """Return model endpoints whose identity changed on one relation.

    Replacing one model changes the serialized endpoint fingerprint on every
    edge touching it.  The other endpoint is still the same model, however,
    and must not become a new intent owner merely because it shares that edge.
    Compare the typed endpoint identities so relation ownership follows the
    endpoint that actually changed.  Add/remove relations conservatively mark
    model endpoints present on only one side as changed.
    """

    records: dict[str, tuple[object | None, object | None]] = {}
    for side, snapshot in ((0, base_snapshot), (1, candidate_snapshot)):
        if snapshot is None:
            continue
        for relation in getattr(snapshot, "relations", ()):
            prior = records.get(relation.relation_id, (None, None))
            rows = list(prior)
            rows[side] = relation
            records[relation.relation_id] = (rows[0], rows[1])
    base_relation, candidate_relation = records.get(relation_id, (None, None))

    def endpoint_rows(relation) -> dict[str, str]:
        if relation is None:
            return {}
        rows: dict[str, str] = {}
        for endpoint in (
            getattr(relation, "source", None),
            getattr(relation, "target", None),
        ):
            if endpoint is None or endpoint.endpoint_kind != "model_instance":
                continue
            # Small helper fixtures may model only endpoint identity.  The
            # endpoint id is a stable same-side sentinel in that case and
            # preserves the relation-only fallback behavior.
            endpoint_id = str(endpoint.endpoint_id)
            rows[endpoint_id] = str(
                getattr(endpoint, "fingerprint", endpoint_id)
            )
        return rows

    before = endpoint_rows(base_relation)
    after = endpoint_rows(candidate_relation)
    changed = {
        endpoint_id.removeprefix("model:")
        for endpoint_id in set(before) | set(after)
        if before.get(endpoint_id) != after.get(endpoint_id)
    }
    return tuple(sorted(item for item in changed if item))


def _intent_review_models(
    diff,
    changed_models: Iterable[str],
    *,
    base_snapshot=None,
    candidate_snapshot=None,
) -> tuple[str, ...]:
    """Return model owners that must receive an explicit intent disposition.

    Most revision-local intent is attached to a replaced model instance.  A
    topology-only update is different: changing the source manifest identity
    also changes the ``semantic-system-contains`` edges, while the
    ``authoritative_model_system`` instance itself may remain byte-identical.
    Those edges are still semantic changes and cannot be silently dropped or
    assigned to an unrelated replaced sibling.  Include the stable authority
    owner whenever that relation family changes; the official revision
    builder then records the relation change against the model that owns the
    system topology.
    """

    values = set(str(item) for item in changed_models if str(item))

    # A source-inventory refresh can change the evidence fingerprint of a
    # relation while leaving the model instance bytes untouched.  Such a
    # relation still belongs to the model at its typed endpoint and therefore
    # requires a current intent receipt for that owner.  Do not ask the
    # handoff agent to guess these owners from relation-id substrings.
    relation_records: dict[str, list[object]] = {}
    for snapshot in (base_snapshot, candidate_snapshot):
        if snapshot is None:
            continue
        for relation in getattr(snapshot, "relations", ()):
            relation_records.setdefault(relation.relation_id, []).append(relation)
    for relation_id in diff.changed_relation_ids:
        changed_endpoints = _relation_model_endpoint_deltas(
            relation_id,
            base_snapshot=base_snapshot,
            candidate_snapshot=candidate_snapshot,
        )
        if changed_endpoints:
            # The direct member diff already contains these model owners.  A
            # relation-only diff may not, so retain the explicit endpoint
            # delta here; never add an unchanged sibling just because it
            # shares an edge with a replaced model.
            values.update(changed_endpoints)
            continue
        owners = {
            endpoint.endpoint_id.removeprefix("model:")
            for relation in relation_records.get(relation_id, ())
            for endpoint in (relation.source, relation.target)
            if endpoint.endpoint_kind == "model_instance"
        }
        values.update(owner for owner in owners if owner)
        # Surface-to-commitment edges have no model endpoint; their canonical
        # owner is the behavior commitment ledger.  Keep this explicit rather
        # than silently treating every untyped relation as authoritative.
        if relation_id.startswith("relation:surface-produces-for-commitment:"):
            values.add("behavior_commitment_ledger")
    if any(
        str(relation_id).startswith("relation:semantic-system-contains:")
        for relation_id in diff.changed_relation_ids
    ):
        values.add("authoritative_model_system")

    # Keep the review denominator identical to the relation-owner denominator.
    # A relation may have two model endpoints, but ``_relation_targets``
    # deliberately attributes that one obligation to one deterministic owner.
    # Including every endpoint here creates accepted intent contributions that
    # have no changed relation or gap, which the revision builder correctly
    # rejects as disconnected.  Filter those endpoint-only additions against
    # the actual assignment result before emitting the review set.
    assigned = _relation_targets(
        diff,
        tuple(sorted(values)),
        base_snapshot=base_snapshot,
        candidate_snapshot=candidate_snapshot,
    )
    values = set(changed_models)
    values.update(
        model_id
        for model_id, relation_ids in assigned.items()
        if relation_ids
    )
    return tuple(sorted(values))


def _relation_targets(
    diff,
    changed_models: Iterable[str],
    manual_assignments: Mapping[str, Sequence[str]] | None = None,
    *,
    base_snapshot=None,
    candidate_snapshot=None,
) -> dict[str, tuple[str, ...]]:
    models = tuple(sorted(changed_models))
    rows: dict[str, list[str]] = {model: [] for model in models}
    assignments = {
        str(model): tuple(str(relation_id) for relation_id in relation_ids)
        for model, relation_ids in (manual_assignments or {}).items()
    }
    unknown_models = sorted(set(assignments) - set(models))
    if unknown_models:
        raise RuntimeError(
            "manual relation assignment names an unreviewed model: "
            + ", ".join(unknown_models)
        )
    changed_relation_ids = set(diff.changed_relation_ids)
    assigned_ids: dict[str, str] = {}
    for model, relation_ids in assignments.items():
        for relation_id in relation_ids:
            if relation_id not in changed_relation_ids:
                raise RuntimeError(
                    f"manual relation assignment names a non-current changed relation: {relation_id}"
                )
            previous = assigned_ids.get(relation_id)
            if previous is not None and previous != model:
                raise RuntimeError(
                    f"changed relation is assigned to multiple models: {relation_id}"
                )
            assigned_ids[relation_id] = model
            rows[model].append(relation_id)
    # Relation ids are not required to contain a model id.  Once a semantic
    # parent partition is materialized, for example, the root-to-domain edge
    # is owned by the authoritative model even though both endpoints are
    # ``parent_closure`` artifacts.  Prefer the typed endpoints from the
    # actual base/candidate relations over substring guesses; this keeps a
    # weaker handoff agent from having to inspect hundreds of ids manually.
    relation_records: dict[str, list[object]] = {}
    for snapshot in (base_snapshot, candidate_snapshot):
        if snapshot is None:
            continue
        for relation in getattr(snapshot, "relations", ()):
            relation_records.setdefault(relation.relation_id, []).append(relation)

    def endpoint_models(relation_id: str) -> tuple[str, ...]:
        # Preserve the typed edge direction.  When a relation joins two
        # changed model instances, the source endpoint is the declared owner
        # for directed and bidirectional relations; this is semantic edge
        # ownership, not lexical/ID ordering.  A relation with only a target
        # model naturally falls back to that target.
        values: list[str] = []
        for relation in relation_records.get(relation_id, ()):
            for endpoint in (relation.source, relation.target):
                if endpoint.endpoint_kind == "model_instance":
                    model_id = endpoint.endpoint_id.removeprefix("model:")
                    if model_id in models and model_id not in values:
                        values.append(model_id)
        return tuple(values)

    def changed_endpoint_models(relation_id: str) -> tuple[str, ...]:
        """Prefer model endpoints whose typed fingerprint changed."""

        return tuple(
            model_id
            for model_id in _relation_model_endpoint_deltas(
                relation_id,
                base_snapshot=base_snapshot,
                candidate_snapshot=candidate_snapshot,
            )
            if model_id in models
        )

    def semantic_owner(relation_id: str) -> str | None:
        if relation_id.startswith("relation:surface-produces-for-commitment:"):
            if "behavior_commitment_ledger" in models:
                return "behavior_commitment_ledger"
        # These prefixes are emitted by model_system_inventory and have a
        # stable owning model even when the relation itself joins only native
        # parent-closure endpoints.
        if relation_id.startswith("relation:semantic-system-contains:"):
            if "authoritative_model_system" in models:
                return "authoritative_model_system"
        if relation_id.startswith("relation:semantic-cross-boundary-support:"):
            suffix = relation_id.split("relation:semantic-cross-boundary-support:", 1)[1]
            source = suffix.split(":semantic-parent:", 1)[0]
            if source in models:
                return source
        if relation_id.startswith("relation:semantic-model-affects-consumer:"):
            suffix = relation_id.split("relation:semantic-model-affects-consumer:", 1)[1]
            source = suffix.split(":", 1)[0]
            if source in models:
                return source
        if relation_id.startswith("relation:system-contains:"):
            source = relation_id.split("relation:system-contains:", 1)[1]
            if source in models:
                return source
        # A topology declaration can add or remove an edge whose model
        # endpoints are not in this revision's changed-model set.  That edge
        # is still an obligation of the authoritative topology owner; without
        # this fallback every unchanged sibling would demand a manual
        # relation assignment after one hierarchy edit.
        if (
            relation_id.startswith("relation:semantic-")
            or relation_id.startswith("relation:system-contains:")
        ) and "authoritative_model_system" in models:
            return "authoritative_model_system"
        return None

    # Manual assignments are an explicit escape hatch for a domain owner, not
    # permission to attach an opaque relation to an arbitrary changed model.
    # Validate them against the same typed endpoint/governance mapping used by
    # automatic selection.  This prevents a weak handoff agent from choosing
    # an owner merely because its name appears in a relation id.
    for model, relation_ids in assignments.items():
        for relation_id in relation_ids:
            allowed_models = set(endpoint_models(relation_id))
            governed_model = semantic_owner(relation_id)
            if governed_model is not None:
                allowed_models.add(governed_model)
            if model not in allowed_models:
                raise RuntimeError(
                    "manual relation assignment is not a declared typed "
                    f"governance owner: {model}:{relation_id}"
                )

    unassigned: list[str] = []
    for relation_id in diff.changed_relation_ids:
        if relation_id in assigned_ids:
            continue
        # If an edge changed only because one endpoint model was replaced,
        # assign it to that endpoint.  Falling back to the original typed
        # source/target order remains correct for a true relation-only change
        # and preserves the explicit single-owner rule.
        matches = list(changed_endpoint_models(relation_id)) or list(
            endpoint_models(relation_id)
        )
        if not matches:
            owner = semantic_owner(relation_id)
            if owner is not None:
                matches = [owner]
        # There is deliberately no lexical/substring fallback here.  A
        # relation that is not present in the supplied base/candidate typed
        # snapshots (and is not one of the explicit governance prefixes
        # above) has no licensed owner.  Failing closed keeps a weak handoff
        # agent from assigning an obligation merely because an opaque id
        # happens to contain a model name.
        # A relation connecting two changed model endpoints is one changed
        # obligation, not two independent obligations.  Attribute it to the
        # typed source endpoint (or the sole endpoint) so the revision builder
        # sees one declared owner without an alphabetic-ID guess.  Callers can
        # still provide a manual assignment when the domain intentionally
        # assigns ownership to a different endpoint.
        if len(matches) > 1:
            matches = [matches[0]]
        if len(matches) == 1:
            rows[matches[0]].append(relation_id)
        else:
            unassigned.append(relation_id)
    if unassigned:
        raise RuntimeError(
            "changed relation ids need an explicit manual model assignment: "
            + ", ".join(unassigned)
        )
    return {model: tuple(sorted(values)) for model, values in rows.items()}


def build_inputs(
    root: Path,
    *,
    snapshot_id: str,
    revision_token: str,
    reviewed_models: tuple[str, ...],
    intent_output: Path,
    path_quality_output: Path,
    relation_assignments: Mapping[str, Sequence[str]] | None = None,
    accepted_boundary_contract=None,
    review_map: Mapping[str, object] | None = None,
    derive_reviewed_from_review_map: bool = False,
) -> dict[str, object]:
    head, base = load_observed_model_system(root)
    revision = load_current_accepted_revision_set(root, head=head, snapshot=base)
    if revision is None:
        raise RuntimeError("a current accepted revision is required for direct rebuild")
    candidate = build_manifest_model_system_snapshot(
        root,
        snapshot_id=snapshot_id,
        system_id=base.system_id,
        subject_lane=base.subject_lane,
        lifecycle=base.lifecycle,
        accepted_boundary_contract=accepted_boundary_contract,
    )
    diff = derive_revision_snapshot_diff(base, candidate)
    changed = _changed_models(diff)
    intent_review_models = _intent_review_models(
        diff,
        changed,
        base_snapshot=base,
        candidate_snapshot=candidate,
    )
    if review_map is not None:
        allowed = {str(item) for item in review_map.get("allowed_model_ids", ())}
        unreviewed = sorted(set(intent_review_models) - allowed)
        if unreviewed:
            raise RuntimeError(
                "review map does not authorize changed models: " + ", ".join(unreviewed)
            )
    if derive_reviewed_from_review_map and not reviewed_models:
        # Prepare-only is an evidence-input producer, not a second manual
        # review prompt.  The candidate diff remains the source of truth for
        # the exact changed owners; the signed review map only authorizes that
        # derived set.  Normal rebuild callers must still name the set
        # explicitly, so an empty accidental invocation cannot pass.
        reviewed = intent_review_models
    else:
        reviewed = tuple(sorted(set(reviewed_models)))
    if reviewed != intent_review_models:
        raise RuntimeError(
            "manual review set must exactly equal changed model set; "
            f"changed={intent_review_models}; reviewed={reviewed}"
        )
    relation_targets = _relation_targets(
        diff,
        intent_review_models,
        relation_assignments,
        base_snapshot=base,
        candidate_snapshot=candidate,
    )
    active = revision.current_effective_intent_view.active_contributions
    active_by_model = {
        item.logical_model_id.removeprefix("model:"): item for item in active
    }
    missing = tuple(sorted(set(intent_review_models) - set(active_by_model)))
    if missing:
        raise RuntimeError("changed models have no prior reviewed intent: " + ", ".join(missing))

    contributions = []
    dispositions = []
    transitions = []
    replacement_counts: dict[str, int] = {}
    # A previous interrupted/partial direct rebuild may already have placed
    # contributions carrying this transaction token in the current accepted
    # set.  The new contribution must still be a distinct replacement: an
    # intent record is invalid if it supersedes itself.  Keep the fixed
    # transaction token, but deterministically advance the per-model suffix
    # past every occupied or already-generated id.
    occupied_contribution_ids = {item.contribution_id for item in active}
    generated_contribution_ids: set[str] = set()
    for prior in active:
        model_name = prior.logical_model_id.removeprefix("model:")
        if model_name not in intent_review_models:
            transitions.append(
                EffectiveIntentTransition(
                    prior_contribution_id=prior.contribution_id,
                    prior_contribution_fingerprint=prior.fingerprint,
                    action="retain",
                    replacement_contribution_ids=(),
                    reason=(
                        "Manual current-standard review retained this historical "
                        "intent as provenance-compatible; no automatic inheritance "
                        "or legacy reader is authorized."
                    ),
                )
            )
            continue
        replacement_counts[model_name] = replacement_counts.get(model_name, 0) + 1
        new_id = (
            f"current-design:{revision_token}:{model_name}:"
            f"{replacement_counts[model_name]}"
        )
        while new_id in occupied_contribution_ids or new_id in generated_contribution_ids:
            replacement_counts[model_name] += 1
            new_id = (
                f"current-design:{revision_token}:{model_name}:"
                f"{replacement_counts[model_name]}"
            )
        generated_contribution_ids.add(new_id)
        # A direct current rewrite must re-bind the reviewed contribution to
        # the bytes that are current *now*.  Keeping the predecessor's source
        # fingerprint would make the official builder reject the explicit
        # review as stale; silently retaining it would be an accidental
        # compatibility path.  The caller has already named this model in the
        # exact reviewed-model set, so refreshing this project-file identity
        # is part of that manual current decision.  WorkContext-backed
        # contributions remain strict: their declared context/artifact
        # identity is validated by the official builder and is never guessed.
        refreshed_source_fingerprint = prior.source_fingerprint
        if not prior.work_context_id:
            source_path = (root / prior.source_ref).resolve(strict=True)
            if root not in source_path.parents:
                raise RuntimeError(
                    "reviewed intent source escapes the project root: "
                    + prior.source_ref
                )
            refreshed_source_fingerprint = source_file_fingerprint(source_path)
        new_contribution = replace(
            prior,
            contribution_id=new_id,
            supersedes_contribution_ids=(prior.contribution_id,),
            effective_revision=revision_token,
            source_fingerprint=refreshed_source_fingerprint,
            rationale=(
                "Manual review of the historical specification accepted this "
                "intent as the current design source for a direct model rebuild. "
                "The implementation identity changed, so the old contribution "
                "is superseded explicitly; no compatibility or automatic "
                "inheritance path exists."
            ),
        )
        contributions.append(new_contribution)
        dispositions.append(
            ModelIntentDisposition(
                contribution_id=new_id,
                contribution_fingerprint=new_contribution.fingerprint,
                disposition="accepted",
                changed_obligation_ids=(),
                changed_state_ids=(),
                changed_transition_ids=(),
                changed_invariant_ids=(),
                changed_relation_ids=relation_targets[model_name],
                scoped_gap_ids=(),
                conflict_ids=(),
                unresolved_effect_ids=(),
                unreachable_terminal_state_ids=(),
                unconsumed_output_ids=(),
                reason=(
                    "Manual review accepted the historical intent as current "
                    "provenance for the changed implementation; all changed "
                    "semantic relations are explicitly assigned to this intent."
                ),
            )
        )
        transitions.append(
            EffectiveIntentTransition(
                prior_contribution_id=prior.contribution_id,
                prior_contribution_fingerprint=prior.fingerprint,
                action="supersede",
                replacement_contribution_ids=(new_id,),
                reason=(
                    "Direct current-standard rebuild after observed implementation "
                    "identity drift; the predecessor remains provenance only and "
                    "is not automatically inherited."
                ),
            )
        )

    _write_json(
        intent_output,
        {
            "contributions": [item.to_dict() for item in sorted(contributions, key=lambda x: x.contribution_id)],
            "dispositions": [item.to_dict() for item in sorted(dispositions, key=lambda x: x.contribution_id)],
            "effective_intent_transitions": [item.to_dict() for item in sorted(transitions, key=lambda x: x.prior_contribution_id)],
        },
    )

    material = compile_flowguard_self_path_quality_material(
        root,
        candidate,
    )
    _write_json(
        path_quality_output,
        {
            "subjects": [item.to_dict() for item in material.review.subjects],
            "results": [item.to_dict() for item in material.review.results],
        },
    )
    return {
        "status": "pass",
        "base_snapshot_fingerprint": base.fingerprint,
        "candidate_snapshot_fingerprint": candidate.fingerprint,
        "changed_models": list(intent_review_models),
        "snapshot_changed_models": list(changed),
        "active_intent_count": len(active),
        "explicit_retain_count": len(active) - len(contributions),
        "explicit_supersede_count": len(contributions),
        "intent_output": str(intent_output),
        "path_quality_output": str(path_quality_output),
        "path_quality_result_count": len(material.review.results),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--revision-token", required=True)
    parser.add_argument("--reviewed-model", action="append", default=[])
    parser.add_argument("--review-map", type=Path)
    parser.add_argument("--boundary-contract", type=Path)
    parser.add_argument(
        "--model-parent-receipt",
        type=Path,
        help="Exact model-parent receipt consumed by the generated revision commands.",
    )
    parser.add_argument(
        "--receipt-root",
        type=Path,
        help="Receipt root consumed by the generated owner-evidence/revision commands.",
    )
    parser.add_argument(
        "--change-manifest",
        type=Path,
        help="Explicit flowguard.patch_change_manifest.v1 used to bind the review map.",
    )
    parser.add_argument(
        "--task-id",
        default="",
        help="Stable revision task id to place in the generated command array.",
    )
    parser.add_argument(
        "--refresh-boundary-binding",
        action="store_true",
        help="Rebind the supplied boundary contract to the current typed snapshot.",
    )
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument(
        "--relation-assignment",
        action="append",
        default=[],
        metavar="MODEL=RELATION_ID",
        help="Explicitly assign an ambiguous changed relation to a reviewed model; repeat for multiple relations.",
    )
    parser.add_argument("--intent-output", type=Path)
    parser.add_argument("--path-quality-output", type=Path)
    args = parser.parse_args()
    if args.prepare_only:
        if args.review_map is None or args.output_root is None or args.boundary_contract is None:
            parser.error("--prepare-only requires --review-map, --boundary-contract, and --output-root")
    elif not args.reviewed_model:
        parser.error("normal rebuild requires at least one --reviewed-model")
    elif args.intent_output is None or args.path_quality_output is None:
        parser.error("normal rebuild requires --intent-output and --path-quality-output")
    relation_assignments: dict[str, list[str]] = {}
    for raw_assignment in args.relation_assignment:
        if "=" not in raw_assignment:
            parser.error("--relation-assignment must use MODEL=RELATION_ID")
        model, relation_id = raw_assignment.split("=", 1)
        model = model.strip()
        relation_id = relation_id.strip()
        if not model or not relation_id:
            parser.error("--relation-assignment must use non-empty MODEL=RELATION_ID")
        relation_assignments.setdefault(model, []).append(relation_id)
    try:
        change_manifest = None
        if args.change_manifest is not None:
            from scripts.check_closure_patch_regressions import _load_change_manifest

            change_manifest = _load_change_manifest(
                args.change_manifest.resolve(), args.root.resolve()
            )
        boundary_contract = (
            load_accepted_boundary_contract(args.boundary_contract.resolve())
            if args.boundary_contract is not None
            else None
        )
        review_map = (
            _load_review_map(
                args.review_map.resolve(),
                args.root.resolve(),
                expected_work_id=(
                    str(change_manifest.get("work_id", ""))
                    if change_manifest is not None
                    else ""
                ),
            )
            if args.review_map is not None
            else None
        )
        if args.prepare_only:
            output_root = args.output_root.resolve()
            output_root.mkdir(parents=True, exist_ok=True)
            intent_output = output_root / "intent-inventory.json"
            path_quality_output = output_root / "path-quality.json"
        else:
            intent_output = args.intent_output.resolve()
            path_quality_output = args.path_quality_output.resolve()
        if args.prepare_only and args.refresh_boundary_binding:
            if boundary_contract is None:
                raise RuntimeError("refresh-boundary-binding requires a current boundary contract")
            _current_head, current_base = load_observed_model_system(args.root.resolve())
            candidate_without_boundary = build_manifest_model_system_snapshot(
                args.root.resolve(),
                snapshot_id=args.snapshot_id,
                system_id=current_base.system_id,
                subject_lane=current_base.subject_lane,
                lifecycle=current_base.lifecycle,
                accepted_boundary_contract=None,
            )
            refreshed_boundary = build_boundary_contract_from_snapshot(
                candidate_without_boundary,
                contract_id=boundary_contract.contract_id,
                model_id=boundary_contract.model_id,
                axis_payloads=boundary_contract.axis_payloads,
                interaction_group_payloads=boundary_contract.interaction_group_payloads,
                group_relation_ids=boundary_contract.group_relation_ids,
            )
            write_content_addressed_boundary_contract(
                args.root.resolve(), refreshed_boundary
            )
            boundary_contract = refreshed_boundary
        payload = build_inputs(
            args.root.resolve(),
            snapshot_id=args.snapshot_id,
            revision_token=args.revision_token,
            reviewed_models=tuple(args.reviewed_model),
            relation_assignments=relation_assignments,
            accepted_boundary_contract=boundary_contract,
            review_map=review_map,
            derive_reviewed_from_review_map=args.prepare_only,
            intent_output=intent_output,
            path_quality_output=path_quality_output,
        )
        if args.prepare_only:
            boundary_output = args.output_root.resolve() / "boundary-contract.json"
            if boundary_contract is None:
                raise RuntimeError("prepare-only requires a current boundary contract")
            _write_json(boundary_output, boundary_contract.to_dict())
            manifest = {
                "schema_version": "flowguard.direct_model_rebuild_inputs.v1",
                "boundary_contract_path": str(boundary_output),
                "intent_inventory_path": str(intent_output),
                "path_quality_material_path": str(path_quality_output),
                "candidate_snapshot_fingerprint": payload["candidate_snapshot_fingerprint"],
                "snapshot_id": args.snapshot_id,
                "revision_token": args.revision_token,
                "review_map_fingerprint": str(review_map["review_map_fingerprint"]),
            }
            if change_manifest is not None:
                manifest.update(
                    {
                        "change_manifest_path": str(change_manifest["path"]),
                        "change_manifest_fingerprint": str(
                            change_manifest["change_manifest_fingerprint"]
                        ),
                        "work_id": str(change_manifest["work_id"]),
                    }
                )
            if args.model_parent_receipt is not None:
                parent = args.model_parent_receipt.resolve()
                receipt_root = (
                    args.receipt_root.resolve()
                    if args.receipt_root is not None
                    else parent.parent
                )
                native_output = args.output_root.resolve() / "native-owner-evidence.json"
                manifest.update(
                    {
                        "model_parent_receipt_path": str(parent),
                        "owner_evidence_argv": [
                            sys.executable,
                            "-B",
                            "-m",
                            "flowguard",
                            "model-revision-owner-evidence",
                            "--root",
                            str(args.root.resolve()),
                            "--model-parent-receipt",
                            str(parent),
                            "--snapshot-id",
                            args.snapshot_id,
                            "--receipt-root",
                            str(receipt_root),
                            "--boundary-contract",
                            str(boundary_output),
                            "--output",
                            str(native_output),
                            "--json",
                        ],
                        "revision_build_argv": [
                            sys.executable,
                            "-B",
                            "-m",
                            "flowguard",
                            "model-revision-build",
                            "--root",
                            str(args.root.resolve()),
                            "--model-parent-receipt",
                            str(parent),
                            "--snapshot-id",
                            args.snapshot_id,
                            "--revision-set-id",
                            str(args.revision_token),
                            "--task-id",
                            str(args.task_id),
                            "--receipt-root",
                            str(receipt_root),
                            "--boundary-contract",
                            str(boundary_output),
                            "--native-owner-evidence",
                            str(native_output),
                            "--path-quality-material",
                            str(path_quality_output),
                            "--intent-inventory",
                            str(intent_output),
                            "--output-root",
                            str(args.output_root.resolve() / "revision-artifacts"),
                            "--json",
                        ],
                        "activation_argv_template": [
                            sys.executable,
                            "-B",
                            "-m",
                            "flowguard",
                            "model-revision-activate",
                            "--root",
                            str(args.root.resolve()),
                            "--candidate-snapshot",
                            "<candidate_snapshot_path>",
                            "--revision-set",
                            "<revision_set_path>",
                            "--receipt-id",
                            "activation:flowguard-usability-closure-20260911",
                            "--json",
                        ],
                    }
                )
            _write_json(args.output_root.resolve() / "inputs-manifest.json", manifest)
            payload = {**payload, "inputs_manifest": str(args.output_root.resolve() / "inputs-manifest.json")}
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
