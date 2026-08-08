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
CURRENT_MESH_SCHEMA = "flowguard.semantic_self_mesh.v3"
CURRENT_MANIFEST_SCHEMA = "flowguard.model_regression_manifest.v4"
CURRENT_MANIFEST_PATH = ".flowguard/model-regression-manifest.json"
ALLOWED_PROGRESS_EVIDENCE_SOURCES = frozenset(
    {"accepted_model_authority_activation", "current_child_model_receipts"}
)
REQUIRED_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "mesh_id",
        "claim_scope",
        "derivation_base_snapshot_path",
        "derivation_base_snapshot_fingerprint",
        "current_manifest_path",
        "observed_base_added_model_ids",
        "observed_base_removed_model_ids",
        "declared_model_count",
        "semantic_universe_fingerprint",
        "semantic_disposition_fingerprint",
        "semantic_relation_fingerprint",
        "semantic_model_status",
        "whole_system_completion_claim",
        "currentness_owner",
        "claim_boundary",
        "allowed_dispositions",
        "semantic_parents",
        "required_terminal_evidence",
        "models",
        "feedback_progress_contracts",
    }
)
REQUIRED_MODEL_FIELDS = frozenset(
    {
        "model_id",
        "disposition",
        "consumer_ids",
        "rationale",
        "structural_parent_id",
        "cross_boundary_parent_ids",
    }
)
OPTIONAL_MODEL_FIELDS = frozenset({"scope_rationale"})
REQUIRED_PARENT_FIELDS = frozenset({"parent_id", "purpose"})
REQUIRED_PROGRESS_CONTRACT_FIELDS = frozenset(
    {
        "relation_id",
        "contract_id",
        "contract_kind",
        "evidence_source_kind",
        "evidence_model_ids",
        "rationale",
    }
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
    if payload.get("schema_version") != CURRENT_MESH_SCHEMA:
        failures.append("schema_version_not_current")
    payload_fields = frozenset(str(key) for key in payload)
    missing_top_level_fields = REQUIRED_TOP_LEVEL_FIELDS - payload_fields
    unknown_top_level_fields = payload_fields - REQUIRED_TOP_LEVEL_FIELDS
    if missing_top_level_fields:
        failures.append(
            "required_top_level_fields_missing:"
            + ",".join(sorted(missing_top_level_fields))
        )
    if unknown_top_level_fields:
        failures.append(
            "unknown_top_level_fields:" + ",".join(sorted(unknown_top_level_fields))
        )

    manifest_path_text = str(payload.get("current_manifest_path", ""))
    if manifest_path_text != CURRENT_MANIFEST_PATH:
        failures.append("current_manifest_path_not_canonical")
    manifest_path = root / CURRENT_MANIFEST_PATH
    if not manifest_path.is_file():
        failures.append("current_manifest_missing")
        manifest_payload: Mapping[str, Any] = {}
    else:
        manifest_payload = _load_json(manifest_path)
    if manifest_payload.get("schema_version") != CURRENT_MANIFEST_SCHEMA:
        failures.append("current_manifest_schema_not_current")
    # The manifest supplies current membership only.  The authored mesh rows
    # below still own purpose, disposition, parentage, and consumer semantics;
    # a raw manifest can never self-certify those relations.
    manifest_rows = tuple(manifest_payload.get("models", ()))
    manifest_ids = tuple(str(row.get("model_id", "")) for row in manifest_rows)
    current_manifest_ids = frozenset(manifest_ids)
    if (
        not manifest_ids
        or "" in current_manifest_ids
        or len(manifest_ids) != len(current_manifest_ids)
    ):
        failures.append("current_manifest_model_identity_invalid")

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

    base_model_rows = tuple(base_payload.get("model_instances", ()))
    base_id_rows = tuple(
        str(item.get("logical_model_id", "")) for item in base_model_rows
    )
    base_ids = frozenset(base_id_rows)
    if not base_id_rows or "" in base_ids or len(base_id_rows) != len(base_ids):
        failures.append("derivation_base_model_identity_invalid")
    added_id_rows = tuple(
        str(value) for value in payload.get("observed_base_added_model_ids", ())
    )
    removed_id_rows = tuple(
        str(value) for value in payload.get("observed_base_removed_model_ids", ())
    )
    declared_added_ids = frozenset(added_id_rows)
    declared_removed_ids = frozenset(removed_id_rows)
    if (
        "" in declared_added_ids
        or len(added_id_rows) != len(declared_added_ids)
    ):
        failures.append("observed_base_added_model_identity_invalid")
    if (
        "" in declared_removed_ids
        or len(removed_id_rows) != len(declared_removed_ids)
    ):
        failures.append("observed_base_removed_model_identity_invalid")
    expected_added_ids = current_manifest_ids - base_ids
    expected_removed_ids = base_ids - current_manifest_ids
    if declared_added_ids != expected_added_ids:
        failures.append("observed_base_added_model_set_drift")
    if declared_removed_ids != expected_removed_ids:
        failures.append("observed_base_removed_model_set_drift")
    if declared_added_ids & declared_removed_ids:
        failures.append("observed_base_diff_overlap")

    model_rows = tuple(payload.get("models", ()))
    declared_ids = tuple(str(row.get("model_id", "")) for row in model_rows)
    declared_id_set = set(declared_ids)
    declared_count = payload.get("declared_model_count")
    if declared_count != len(model_rows):
        failures.append("declared_model_count_mismatch")
    if "" in declared_id_set:
        failures.append("empty_model_id")
    if len(declared_ids) != len(declared_id_set):
        failures.append("duplicate_model_id")
    missing_manifest_ids = current_manifest_ids - declared_id_set
    foreign_declared_ids = declared_id_set - current_manifest_ids
    if missing_manifest_ids:
        failures.append(
            "semantic_manifest_coverage_missing:"
            + ",".join(sorted(missing_manifest_ids))
        )
    if foreign_declared_ids:
        failures.append(
            "semantic_manifest_coverage_foreign:"
            + ",".join(sorted(foreign_declared_ids))
        )
    if declared_id_set != current_manifest_ids:
        failures.append("semantic_universe_not_exact")

    parent_rows = tuple(payload.get("semantic_parents", ()))
    parent_ids = {str(row.get("parent_id", "")) for row in parent_rows}
    if len(parent_ids) != len(parent_rows) or "" in parent_ids:
        failures.append("semantic_parent_identity_invalid")
    for parent in parent_rows:
        parent_fields = frozenset(str(key) for key in parent)
        if parent_fields != REQUIRED_PARENT_FIELDS:
            failures.append(
                f"semantic_parent_schema_invalid:{parent.get('parent_id', '')}"
            )
        if len(str(parent.get("purpose", "")).strip()) < 24:
            failures.append(f"semantic_parent_purpose_missing:{parent.get('parent_id', '')}")

    relation_count = 0
    disposition_counts: dict[str, int] = {}
    for row in model_rows:
        model_id = str(row.get("model_id", ""))
        row_fields = frozenset(str(key) for key in row)
        if not REQUIRED_MODEL_FIELDS.issubset(row_fields) or not row_fields.issubset(
            REQUIRED_MODEL_FIELDS | OPTIONAL_MODEL_FIELDS
        ):
            failures.append(f"semantic_model_row_schema_invalid:{model_id}")
        disposition = str(row.get("disposition", ""))
        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
        if disposition not in ALLOWED_DISPOSITIONS:
            failures.append(f"invalid_disposition:{model_id}")
        if len(str(row.get("rationale", "")).strip()) < 32:
            failures.append(f"rationale_missing_or_ceremonial:{model_id}")

        structural_parent_id = str(row.get("structural_parent_id", ""))
        cross_boundary_parent_ids = tuple(
            str(value) for value in row.get("cross_boundary_parent_ids", ())
        )
        if structural_parent_id not in parent_ids:
            failures.append(f"parent_relation_missing_or_unknown:{model_id}")
        if (
            len(cross_boundary_parent_ids)
            != len(set(cross_boundary_parent_ids))
            or structural_parent_id in cross_boundary_parent_ids
            or any(value not in parent_ids for value in cross_boundary_parent_ids)
        ):
            failures.append(f"cross_boundary_parent_invalid:{model_id}")
        relation_count += 1 + len(cross_boundary_parent_ids)

        consumer_ids = tuple(str(value) for value in row.get("consumer_ids", ()))
        if not consumer_ids:
            failures.append(f"consumer_relation_missing:{model_id}")
        if len(consumer_ids) != len(set(consumer_ids)):
            failures.append(f"consumer_relation_duplicate:{model_id}")
        for consumer_id in consumer_ids:
            if consumer_id.startswith("model:"):
                if consumer_id.removeprefix("model:") not in declared_id_set:
                    failures.append(f"consumer_model_unknown:{model_id}:{consumer_id}")
            elif consumer_id not in ALLOWED_CLAIM_CONSUMERS:
                failures.append(f"consumer_claim_unknown:{model_id}:{consumer_id}")
        relation_count += len(consumer_ids)

        if disposition == "scoped_out" and not row.get("scope_rationale"):
            failures.append(f"scoped_out_without_scope_rationale:{model_id}")

    feedback_contracts = tuple(payload.get("feedback_progress_contracts", ()))
    contract_relation_ids: set[str] = set()
    model_consumer_edges = {
        (
            str(row.get("model_id", "")),
            str(consumer_id).removeprefix("model:"),
        )
        for row in model_rows
        for consumer_id in row.get("consumer_ids", ())
        if str(consumer_id).startswith("model:")
    }
    valid_consumer_relation_ids = {
        (
            f"topology:{str(row.get('model_id', ''))}:"
            + (
                "model-obligation:"
                + str(consumer_id).removeprefix("model:")
                if str(consumer_id).startswith("model:")
                else str(consumer_id)
            )
        )
        for row in model_rows
        for consumer_id in row.get("consumer_ids", ())
    }
    for contract in feedback_contracts:
        relation_id = str(contract.get("relation_id", ""))
        contract_id = str(contract.get("contract_id", ""))
        contract_fields = frozenset(str(key) for key in contract)
        if contract_fields != REQUIRED_PROGRESS_CONTRACT_FIELDS:
            failures.append(f"feedback_progress_contract_schema_invalid:{relation_id}")
        evidence_source_kind = str(contract.get("evidence_source_kind", ""))
        evidence_model_ids = tuple(
            str(value) for value in contract.get("evidence_model_ids", ())
        )
        if (
            not relation_id
            or relation_id not in valid_consumer_relation_ids
            or relation_id in contract_relation_ids
        ):
            failures.append(f"feedback_progress_relation_invalid:{relation_id}")
        contract_relation_ids.add(relation_id)
        if not contract_id or contract.get("contract_kind") != "progress_measure":
            failures.append(f"feedback_progress_contract_invalid:{relation_id}")
        if evidence_source_kind not in ALLOWED_PROGRESS_EVIDENCE_SOURCES:
            failures.append(f"feedback_progress_source_invalid:{relation_id}")
        if evidence_source_kind == "current_child_model_receipts":
            if (
                not evidence_model_ids
                or len(evidence_model_ids) != len(set(evidence_model_ids))
                or any(value not in declared_id_set for value in evidence_model_ids)
            ):
                failures.append(f"feedback_progress_models_invalid:{relation_id}")
        elif evidence_model_ids:
            failures.append(f"feedback_progress_models_unexpected:{relation_id}")
        if len(str(contract.get("rationale", "")).strip()) < 32:
            failures.append(f"feedback_progress_rationale_missing:{relation_id}")
    adjacency: dict[str, set[str]] = {
        model_id: set() for model_id in declared_id_set
    }
    for producer_id, consumer_id in model_consumer_edges:
        adjacency.setdefault(producer_id, set()).add(consumer_id)
    cyclic_relation_ids: set[str] = set()
    for producer_id, consumer_id in model_consumer_edges:
        pending = [consumer_id]
        visited: set[str] = set()
        while pending:
            current = pending.pop()
            if current == producer_id:
                cyclic_relation_ids.add(
                    f"topology:{producer_id}:model-obligation:{consumer_id}"
                )
                break
            if current in visited:
                continue
            visited.add(current)
            pending.extend(adjacency.get(current, ()))
    missing_progress_relation_ids = cyclic_relation_ids - contract_relation_ids
    noncyclic_progress_relation_ids = contract_relation_ids - cyclic_relation_ids
    if missing_progress_relation_ids:
        failures.append(
            "feedback_progress_contract_missing:"
            + ",".join(sorted(missing_progress_relation_ids))
        )
    if noncyclic_progress_relation_ids:
        failures.append(
            "feedback_progress_contract_noncyclic_or_dangling:"
            + ",".join(sorted(noncyclic_progress_relation_ids))
        )
    if missing_progress_relation_ids or noncyclic_progress_relation_ids:
        failures.append("feedback_progress_contract_coverage_mismatch")

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
        {
            "models": [
                {
                    "model_id": str(row.get("model_id", "")),
                    "structural_parent_id": str(
                        row.get("structural_parent_id", "")
                    ),
                    "cross_boundary_parent_ids": sorted(
                        str(value)
                        for value in row.get("cross_boundary_parent_ids", ())
                    ),
                    "consumer_ids": sorted(
                        str(value) for value in row.get("consumer_ids", ())
                    ),
                }
                for row in sorted(
                    model_rows,
                    key=lambda value: str(value.get("model_id", "")),
                )
            ],
            "feedback_progress_contracts": [
                {
                    "relation_id": str(row.get("relation_id", "")),
                    "contract_id": str(row.get("contract_id", "")),
                    "contract_kind": str(row.get("contract_kind", "")),
                    "evidence_source_kind": str(
                        row.get("evidence_source_kind", "")
                    ),
                    "evidence_model_ids": sorted(
                        str(value)
                        for value in row.get("evidence_model_ids", ())
                    ),
                    "rationale": str(row.get("rationale", "")),
                }
                for row in sorted(
                    feedback_contracts,
                    key=lambda value: str(value.get("relation_id", "")),
                )
            ],
        }
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

    missing_current_owner = copy.deepcopy(baseline)
    missing_current_owner["models"] = missing_current_owner["models"][:-1]
    missing_current_owner["declared_model_count"] -= 1
    cases.append(
        (
            "missing_current_manifest_owner",
            missing_current_owner,
            "semantic_manifest_coverage_missing",
        )
    )

    foreign_owner = copy.deepcopy(baseline)
    foreign_row = copy.deepcopy(foreign_owner["models"][-1])
    foreign_row["model_id"] = "retired_parallel_authority"
    foreign_owner["models"].append(foreign_row)
    foreign_owner["declared_model_count"] += 1
    cases.append(
        (
            "foreign_owner",
            foreign_owner,
            "semantic_manifest_coverage_foreign",
        )
    )

    added_diff_drift = copy.deepcopy(baseline)
    added_diff_drift["observed_base_added_model_ids"] = [
        "retired_parallel_authority"
    ]
    cases.append(
        (
            "observed_base_added_diff_drift",
            added_diff_drift,
            "observed_base_added_model_set_drift",
        )
    )

    removed_diff_drift = copy.deepcopy(baseline)
    removed_diff_drift["observed_base_removed_model_ids"] = []
    cases.append(
        (
            "observed_base_removed_diff_drift",
            removed_diff_drift,
            "observed_base_removed_model_set_drift",
        )
    )

    dangling_consumer = copy.deepcopy(baseline)
    dangling_consumer["models"][0]["consumer_ids"] = [
        "model:retired_parallel_authority"
    ]
    cases.append(
        (
            "dangling_consumer",
            dangling_consumer,
            "consumer_model_unknown",
        )
    )

    missing_cycle_progress = copy.deepcopy(baseline)
    missing_cycle_progress["feedback_progress_contracts"] = (
        missing_cycle_progress["feedback_progress_contracts"][:-1]
    )
    cases.append(
        (
            "cycle_without_progress_contract",
            missing_cycle_progress,
            "feedback_progress_contract_missing",
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
