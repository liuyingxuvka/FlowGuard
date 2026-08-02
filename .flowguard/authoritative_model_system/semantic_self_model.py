"""Native review for the finite FlowGuard whole-system semantic self mesh.

The checked-in JSON is a model candidate.  This review proves its finite shape
and its rejection rules; it deliberately does not publish or simulate a
terminal whole-system completion receipt.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


ALLOWED_DISPOSITIONS = frozenset(
    {"connected", "intentional_leaf", "delegated_or_supporting", "scoped_out"}
)
ALLOWED_CLAIM_CONSUMERS = frozenset(
    {"claim:whole-flowguard-self-understanding", "claim:flowguard-release-readiness"}
)
EXPECTED_CANDIDATE_ADDED_MODEL_IDS: frozenset[str] = frozenset(
    {"implementation_blueprint"}
)


@dataclass(frozen=True)
class SemanticMeshReview:
    ok: bool
    model_count: int
    disposition_counts: Mapping[str, int]
    parent_count: int
    relation_count: int
    failures: tuple[str, ...]
    completion_licensed: bool
    claim_boundary: str

    def format_text(self) -> str:
        disposition_text = ", ".join(
            f"{key}={self.disposition_counts[key]}"
            for key in sorted(self.disposition_counts)
        )
        lines = [
            "FlowGuard semantic self-mesh review",
            f"status={'pass' if self.ok else 'fail'}",
            f"models={self.model_count}; parents={self.parent_count}; relations={self.relation_count}",
            f"dispositions={disposition_text}",
            f"whole_system_completion_licensed={str(self.completion_licensed).lower()}",
            f"claim_boundary={self.claim_boundary}",
        ]
        lines.extend(f"failure={failure}" for failure in self.failures)
        return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fingerprint(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _review_payload(root: Path, payload: Mapping[str, Any]) -> SemanticMeshReview:
    failures: list[str] = []
    if payload.get("schema_version") != "flowguard.semantic_self_mesh.v1":
        failures.append("schema_version_not_current")

    base_path_text = str(payload.get("derivation_base_snapshot_path", ""))
    base_fingerprint = str(payload.get("derivation_base_snapshot_fingerprint", ""))
    if not base_path_text:
        failures.append("derivation_base_path_missing")
        base_payload: Mapping[str, Any] = {}
    else:
        base_path = root / base_path_text
        if not base_path.is_file():
            failures.append("derivation_base_snapshot_missing")
            base_payload = {}
        else:
            base_payload = _load_json(base_path)
    if not base_fingerprint:
        failures.append("derivation_base_fingerprint_empty")
    elif base_payload and base_payload.get("fingerprint") != base_fingerprint:
        failures.append("derivation_base_fingerprint_mismatch")
    elif base_path_text and Path(base_path_text).stem != base_fingerprint.removeprefix("sha256:"):
        failures.append("derivation_base_path_fingerprint_mismatch")

    base_ids = {
        str(item.get("logical_model_id", ""))
        for item in base_payload.get("model_instances", ())
        if item.get("logical_model_id")
    }
    candidate_added_ids = frozenset(
        str(value) for value in payload.get("candidate_added_model_ids", ())
    )
    if candidate_added_ids != EXPECTED_CANDIDATE_ADDED_MODEL_IDS:
        failures.append("candidate_added_model_set_drift")
    if candidate_added_ids & base_ids:
        failures.append("candidate_added_model_already_in_base")
    expected_ids = base_ids | candidate_added_ids
    model_rows = tuple(payload.get("models", ()))
    declared_ids = tuple(str(row.get("model_id", "")) for row in model_rows)
    declared_id_set = set(declared_ids)
    declared_count = payload.get("declared_model_count")
    if declared_count != len(model_rows):
        failures.append("declared_model_count_mismatch")
    if len(declared_ids) != len(declared_id_set):
        failures.append("duplicate_model_id")
    if declared_id_set != expected_ids:
        failures.append("semantic_universe_not_exact")

    parent_rows = tuple(payload.get("semantic_parents", ()))
    parent_ids = {str(row.get("parent_id", "")) for row in parent_rows}
    if len(parent_ids) != len(parent_rows) or "" in parent_ids:
        failures.append("semantic_parent_identity_invalid")
    for parent in parent_rows:
        if len(str(parent.get("purpose", "")).strip()) < 24:
            failures.append(f"semantic_parent_purpose_missing:{parent.get('parent_id', '')}")

    relation_count = 0
    disposition_counts: dict[str, int] = {}
    for row in model_rows:
        model_id = str(row.get("model_id", ""))
        disposition = str(row.get("disposition", ""))
        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
        if disposition not in ALLOWED_DISPOSITIONS:
            failures.append(f"invalid_disposition:{model_id}")
        if len(str(row.get("rationale", "")).strip()) < 32:
            failures.append(f"rationale_missing_or_ceremonial:{model_id}")

        row_parent_ids = tuple(str(value) for value in row.get("parent_ids", ()))
        if not row_parent_ids or any(value not in parent_ids for value in row_parent_ids):
            failures.append(f"parent_relation_missing_or_unknown:{model_id}")
        relation_count += len(row_parent_ids)

        consumer_ids = tuple(str(value) for value in row.get("consumer_ids", ()))
        if not consumer_ids:
            failures.append(f"consumer_relation_missing:{model_id}")
        for consumer_id in consumer_ids:
            if consumer_id.startswith("model:"):
                if consumer_id.removeprefix("model:") not in declared_id_set:
                    failures.append(f"consumer_model_unknown:{model_id}:{consumer_id}")
            elif consumer_id not in ALLOWED_CLAIM_CONSUMERS:
                failures.append(f"consumer_claim_unknown:{model_id}:{consumer_id}")
        relation_count += len(consumer_ids)

        if disposition == "scoped_out" and not row.get("scope_rationale"):
            failures.append(f"scoped_out_without_scope_rationale:{model_id}")

    universe_fingerprint = _fingerprint(sorted(declared_ids))
    disposition_fingerprint = _fingerprint(
        [
            {
                "model_id": str(row.get("model_id", "")),
                "disposition": str(row.get("disposition", "")),
                "rationale": str(row.get("rationale", "")),
            }
            for row in sorted(model_rows, key=lambda value: str(value.get("model_id", "")))
        ]
    )
    relation_fingerprint = _fingerprint(
        [
            {
                "model_id": str(row.get("model_id", "")),
                "parent_ids": sorted(str(value) for value in row.get("parent_ids", ())),
                "consumer_ids": sorted(str(value) for value in row.get("consumer_ids", ())),
            }
            for row in sorted(model_rows, key=lambda value: str(value.get("model_id", "")))
        ]
    )
    if payload.get("semantic_universe_fingerprint") != universe_fingerprint:
        failures.append("semantic_universe_fingerprint_mismatch")
    if payload.get("semantic_disposition_fingerprint") != disposition_fingerprint:
        failures.append("semantic_disposition_fingerprint_mismatch")
    if payload.get("semantic_relation_fingerprint") != relation_fingerprint:
        failures.append("semantic_relation_fingerprint_mismatch")

    expected_dispositions = set(payload.get("allowed_dispositions", ()))
    if expected_dispositions != ALLOWED_DISPOSITIONS:
        failures.append("allowed_disposition_set_drift")
    if payload.get("semantic_model_status") != "candidate_defined_not_verified":
        failures.append("semantic_candidate_status_overclaimed")
    if payload.get("whole_system_completion_claim") != "not_licensed_until_current_terminal_evidence":
        failures.append("checked_in_artifact_claims_terminal_completion")
    required_evidence = tuple(payload.get("required_terminal_evidence", ()))
    if not required_evidence or any(not str(value).strip() for value in required_evidence):
        failures.append("terminal_evidence_requirements_missing")

    return SemanticMeshReview(
        ok=not failures,
        model_count=len(model_rows),
        disposition_counts=disposition_counts,
        parent_count=len(parent_rows),
        relation_count=relation_count,
        failures=tuple(failures),
        completion_licensed=False,
        claim_boundary=str(payload.get("claim_boundary", "")),
    )


def review_semantic_self_mesh(root: Path) -> SemanticMeshReview:
    path = root / ".flowguard/authoritative_model_system/semantic_model_mesh.json"
    return _review_payload(root, _load_json(path))


def run_known_bad_review(root: Path) -> tuple[bool, tuple[str, ...]]:
    path = root / ".flowguard/authoritative_model_system/semantic_model_mesh.json"
    baseline = _load_json(path)
    cases: list[tuple[str, dict[str, Any], str]] = []

    inventory_only = copy.deepcopy(baseline)
    for row in inventory_only["models"]:
        row["parent_ids"] = []
        row["consumer_ids"] = []
    cases.append(("inventory_only", inventory_only, "parent_relation_missing_or_unknown"))

    five_model_slice = copy.deepcopy(baseline)
    five_model_slice["models"] = five_model_slice["models"][:5]
    five_model_slice["declared_model_count"] = 5
    cases.append(("five_model_slice", five_model_slice, "semantic_universe_not_exact"))

    empty_fingerprint = copy.deepcopy(baseline)
    empty_fingerprint["derivation_base_snapshot_fingerprint"] = ""
    cases.append(("empty_fingerprint", empty_fingerprint, "derivation_base_fingerprint_empty"))

    unverified_claim = copy.deepcopy(baseline)
    unverified_claim["whole_system_completion_claim"] = "verified"
    cases.append(
        ("unverified_artifact", unverified_claim, "checked_in_artifact_claims_terminal_completion")
    )

    unexpected_candidate_addition = copy.deepcopy(baseline)
    unexpected_candidate_addition["candidate_added_model_ids"] = ["parallel_authority"]
    cases.append(
        (
            "unexpected_candidate_addition",
            unexpected_candidate_addition,
            "candidate_added_model_set_drift",
        )
    )

    relation_count_drift = copy.deepcopy(baseline)
    for row in relation_count_drift["models"]:
        if row["model_id"] == "authoritative_model_system":
            row["consumer_ids"] = row["consumer_ids"][:-1]
            break
    cases.append(
        (
            "semantic_relation_count_drift",
            relation_count_drift,
            "semantic_relation_fingerprint_mismatch",
        )
    )

    failures: list[str] = []
    for case_id, candidate, expected_failure_prefix in cases:
        report = _review_payload(root, candidate)
        rejected_for_expected_reason = any(
            failure.startswith(expected_failure_prefix) for failure in report.failures
        )
        if report.ok or report.completion_licensed or not rejected_for_expected_reason:
            failures.append(case_id)
    return not failures, tuple(failures)
