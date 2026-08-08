"""Canonical receipt publication and verification for model maturation.

Downstream consumers receive :class:`VerifiedModelMaturation`, whose public
constructor is disabled. The only normal producer is independent verification
of a canonical :class:`EvidenceReceipt`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .evidence_receipts import (
    EvidenceReceipt,
    InputSnapshot,
    RECEIPT_STATUS_BLOCKED,
    RECEIPT_STATUS_PASS,
    RECEIPT_STATUS_SCOPED,
    ReceiptVerificationContext,
    ReceiptVerificationResult,
    fingerprint_value,
    load_evidence_receipt,
    save_evidence_receipt,
    verify_evidence_receipt,
)
from .model_maturation import (
    MODEL_MATURATION_CONFIDENCE_FULL,
    MODEL_MATURATION_CONFIDENCE_SCOPED,
    MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
    ModelMaturationReport,
)
from .model_path_quality import (
    PathQualityResult,
    PathQualitySubject,
    normalize_path_quality_material,
    path_quality_result_set_fingerprint,
)


MODEL_MATURATION_RECEIPT_SCHEMA_VERSION = "flowguard.model_maturation_receipt.v2"
MODEL_MATURATION_RECEIPT_SUBJECT_KIND = "flowguard_model_maturation"
MODEL_MATURATION_RECEIPT_CLAIM_SCOPE = "task_model_maturation"


def _tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = (values,)
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True)
class ModelMaturationReceiptRef:
    receipt_id: str
    receipt_fingerprint: str

    def __post_init__(self) -> None:
        if not self.receipt_id or not self.receipt_fingerprint.startswith("sha256:"):
            raise ValueError("maturation receipt reference requires exact id and fingerprint")

    def to_dict(self) -> dict[str, str]:
        return {
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
        }


@dataclass(frozen=True)
class ModelMaturationReceiptPublication:
    producer_id: str
    producer_version: str
    command: tuple[str, ...]
    started_at: str
    finished_at: str
    environment_metadata: Mapping[str, str]
    contract_hash: str
    check_manifest_hash: str
    suite_map_hash: str
    input_snapshots: tuple[InputSnapshot, ...]
    covered_obligation_ids: tuple[str, ...]
    working_directory_token: str = "<WORKSPACE>"
    claim_scope: str = MODEL_MATURATION_RECEIPT_CLAIM_SCOPE
    supersedes_receipt_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.producer_id or not self.producer_version:
            raise ValueError("maturation publication requires a producer identity")
        if not self.input_snapshots or not self.covered_obligation_ids:
            raise ValueError("maturation publication requires inputs and obligations")
        object.__setattr__(self, "command", tuple(str(value) for value in self.command))
        object.__setattr__(self, "input_snapshots", tuple(self.input_snapshots))
        object.__setattr__(self, "covered_obligation_ids", _tuple(self.covered_obligation_ids))
        object.__setattr__(self, "supersedes_receipt_ids", _tuple(self.supersedes_receipt_ids))
        object.__setattr__(self, "environment_metadata", MappingProxyType(dict(self.environment_metadata)))


@dataclass(frozen=True)
class ModelMaturationVerificationContext:
    receipt_context: ReceiptVerificationContext
    task_id: str
    model_id: str
    candidate_model_fingerprint: str
    coverage_demand_fingerprint: str
    coverage_universe_id: str
    coverage_universe_fingerprint: str
    input_fingerprint: str
    evidence_fingerprint: str
    required_path_quality_model_ids: tuple[str, ...] = ()
    path_quality_subjects: tuple[PathQualitySubject, ...] = ()
    path_quality_results: tuple[PathQualityResult, ...] = ()
    path_quality_result_set_fingerprint: str = ""
    owner_resolution_ids: tuple[str, ...] = ()
    owner_resolution_fingerprints: tuple[str, ...] = ()
    owner_resolution_owner_ids: tuple[str, ...] = ()
    required_receipt_fingerprint: str = ""

    def __post_init__(self) -> None:
        required_models, subjects, results = normalize_path_quality_material(
            self.required_path_quality_model_ids,
            self.path_quality_subjects,
            self.path_quality_results,
        )
        expected_result_set_fingerprint = path_quality_result_set_fingerprint(
            required_models,
            subjects,
            results,
        )
        if (
            self.path_quality_result_set_fingerprint
            and self.path_quality_result_set_fingerprint
            != expected_result_set_fingerprint
        ):
            raise ValueError(
                "maturation verification path-quality result set is stale"
            )
        object.__setattr__(
            self, "required_path_quality_model_ids", required_models
        )
        object.__setattr__(self, "path_quality_subjects", subjects)
        object.__setattr__(self, "path_quality_results", results)
        object.__setattr__(
            self,
            "path_quality_result_set_fingerprint",
            expected_result_set_fingerprint,
        )
        object.__setattr__(self, "owner_resolution_ids", _tuple(self.owner_resolution_ids))
        object.__setattr__(
            self,
            "owner_resolution_fingerprints",
            _tuple(self.owner_resolution_fingerprints),
        )
        object.__setattr__(
            self,
            "owner_resolution_owner_ids",
            _tuple(self.owner_resolution_owner_ids),
        )


@dataclass(frozen=True, init=False)
class VerifiedModelMaturation:
    """Verifier-created maturation projection; it cannot be directly constructed."""

    receipt_id: str
    receipt_fingerprint: str
    evidence_id: str
    task_id: str
    model_id: str
    candidate_model_fingerprint: str
    coverage_demand_fingerprint: str
    coverage_universe_id: str
    coverage_universe_fingerprint: str
    input_fingerprint: str
    evidence_fingerprint: str
    decision: str
    confidence: str
    terminal_reason: str
    open_gap_fingerprints: tuple[str, ...]
    required_path_quality_model_ids: tuple[str, ...]
    path_quality_result_set_fingerprint: str
    path_quality_summaries: tuple[Mapping[str, Any], ...]
    current: bool
    eligible_for_full_claim: bool
    verification_status: str
    verification_finding_codes: tuple[str, ...]
    owner_resolution_ids: tuple[str, ...]
    owner_resolution_fingerprints: tuple[str, ...]
    owner_resolution_owner_ids: tuple[str, ...]

    def __new__(cls):
        raise TypeError("VerifiedModelMaturation is created only by receipt verification")

    def supports_full_confidence(self) -> bool:
        return bool(
            self.current
            and self.eligible_for_full_claim
            and self.decision == MODEL_MATURATION_DECISION_CLOSED_FOR_TASK
            and self.confidence == MODEL_MATURATION_CONFIDENCE_FULL
            and self.terminal_reason == MODEL_MATURATION_DECISION_CLOSED_FOR_TASK
            and not self.open_gap_fingerprints
            and bool(self.required_path_quality_model_ids)
            and len(self.path_quality_summaries)
            == len(self.required_path_quality_model_ids)
            and {
                str(item.get("model_id", ""))
                for item in self.path_quality_summaries
            }
            == set(self.required_path_quality_model_ids)
            and all(
                bool(item.get("current"))
                and str(item.get("conclusion", "")) != "unresolved"
                and not tuple(item.get("unresolved_ids", ()))
                and str(item.get("selected_candidate_lane", ""))
                != "normative_target"
                and str(item.get("subject_fingerprint", "")).startswith(
                    "sha256:"
                )
                and str(item.get("result_fingerprint", "")).startswith(
                    "sha256:"
                )
                and str(item.get("detail_evidence_fingerprint", "")).startswith(
                    "sha256:"
                )
                for item in self.path_quality_summaries
            )
            and bool(self.owner_resolution_ids)
            and len(self.owner_resolution_ids)
            == len(self.owner_resolution_fingerprints)
            == len(self.owner_resolution_owner_ids)
            and len(set(self.owner_resolution_ids)) == len(self.owner_resolution_ids)
            and len(set(self.owner_resolution_owner_ids))
            == len(self.owner_resolution_owner_ids)
            and all(
                value.startswith("sha256:")
                for value in self.owner_resolution_fingerprints
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "evidence_id": self.evidence_id,
            "task_id": self.task_id,
            "model_id": self.model_id,
            "candidate_model_fingerprint": self.candidate_model_fingerprint,
            "coverage_demand_fingerprint": self.coverage_demand_fingerprint,
            "coverage_universe_id": self.coverage_universe_id,
            "coverage_universe_fingerprint": self.coverage_universe_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "evidence_fingerprint": self.evidence_fingerprint,
            "decision": self.decision,
            "confidence": self.confidence,
            "terminal_reason": self.terminal_reason,
            "open_gap_fingerprints": list(self.open_gap_fingerprints),
            "required_path_quality_model_ids": list(
                self.required_path_quality_model_ids
            ),
            "path_quality_result_set_fingerprint": (
                self.path_quality_result_set_fingerprint
            ),
            "path_quality_summaries": [
                {
                    **dict(item),
                    "unresolved_ids": list(item.get("unresolved_ids", ())),
                }
                for item in self.path_quality_summaries
            ],
            "current": self.current,
            "eligible_for_full_claim": self.eligible_for_full_claim,
            "verification_status": self.verification_status,
            "verification_finding_codes": list(self.verification_finding_codes),
            "owner_resolution_ids": list(self.owner_resolution_ids),
            "owner_resolution_fingerprints": list(self.owner_resolution_fingerprints),
            "owner_resolution_owner_ids": list(self.owner_resolution_owner_ids),
        }


@dataclass(frozen=True)
class ModelMaturationReceiptVerification:
    receipt_ref: ModelMaturationReceiptRef
    receipt_verification: ReceiptVerificationResult
    verified_maturation: VerifiedModelMaturation | None
    semantic_finding_codes: tuple[str, ...] = ()

    @property
    def current(self) -> bool:
        return bool(self.verified_maturation and self.verified_maturation.current)

    @property
    def ok(self) -> bool:
        return bool(
            self.verified_maturation
            and self.verified_maturation.supports_full_confidence()
            and not self.semantic_finding_codes
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_ref": self.receipt_ref.to_dict(),
            "receipt_verification": self.receipt_verification.to_dict(),
            "verified_maturation": (
                self.verified_maturation.to_dict() if self.verified_maturation else None
            ),
            "semantic_finding_codes": list(self.semantic_finding_codes),
            "ok": self.ok,
        }


def _maturation_metadata(report: ModelMaturationReport) -> dict[str, Any]:
    return {
        "schema_version": MODEL_MATURATION_RECEIPT_SCHEMA_VERSION,
        "evidence_id": report.evidence_id,
        "task_id": report.task_id,
        "model_id": report.model_id,
        "candidate_model_fingerprint": report.candidate_model_fingerprint,
        "coverage_demand_fingerprint": report.coverage_demand_fingerprint,
        "coverage_universe_id": report.coverage_universe_id,
        "coverage_universe_fingerprint": report.coverage_universe_fingerprint,
        "input_fingerprint": report.input_fingerprint,
        "evidence_fingerprint": report.evidence_fingerprint,
        "decision": report.decision,
        "confidence": report.confidence,
        "terminal_reason": report.terminal_reason,
        "open_gap_fingerprints": list(report.open_gap_fingerprints),
        "required_path_quality_model_ids": list(
            report.required_path_quality_model_ids
        ),
        "path_quality_subjects": [
            item.to_dict() for item in report.path_quality_subjects
        ],
        "path_quality_results": [
            item.to_compact_dict() for item in report.path_quality_results
        ],
        "path_quality_result_set_fingerprint": (
            report.path_quality_result_set_fingerprint
        ),
        "owner_resolution_ids": list(report.owner_resolution_ids),
        "owner_resolution_fingerprints": list(report.owner_resolution_fingerprints),
        "owner_resolution_owner_ids": list(report.owner_resolution_owner_ids),
    }


def _path_quality_closure_findings(
    required_model_ids: Sequence[str],
    subjects: Sequence[PathQualitySubject],
    results: Sequence[PathQualityResult],
    *,
    primary_model_id: str,
    candidate_model_fingerprint: str,
) -> tuple[str, ...]:
    findings: list[str] = []
    required = tuple(sorted(str(value) for value in required_model_ids))
    if not required:
        findings.append("maturation_path_quality_denominator_missing")
    subjects_by_model = {item.model_id: item for item in subjects}
    if set(subjects_by_model) != set(required):
        findings.append("maturation_path_quality_subject_coverage_mismatch")
    results_by_subject = {item.subject_fingerprint: item for item in results}
    expected_subjects = {
        item.fingerprint for item in subjects_by_model.values()
    }
    if set(results_by_subject) != expected_subjects:
        findings.append("maturation_path_quality_result_coverage_mismatch")
    for model_id in required:
        subject = subjects_by_model.get(model_id)
        if subject is None:
            continue
        if (
            model_id == primary_model_id
            and subject.model_fingerprint != candidate_model_fingerprint
        ):
            findings.append("maturation_path_quality_primary_subject_stale")
        result = results_by_subject.get(subject.fingerprint)
        if result is None:
            continue
        if not result.current:
            findings.append("maturation_path_quality_result_stale")
        if result.currentness_id != subject.currentness_id:
            findings.append("maturation_path_quality_currentness_mismatch")
        if result.conclusion == "unresolved" or result.unresolved_ids:
            findings.append("maturation_path_quality_unresolved")
        if result.selected_candidate_lane == "normative_target":
            findings.append("maturation_path_quality_normative_target_not_observed")
    return tuple(dict.fromkeys(findings))


def build_model_maturation_receipt(
    report: ModelMaturationReport,
    publication: ModelMaturationReceiptPublication,
) -> EvidenceReceipt:
    """Build one canonical receipt from a terminal maturation report."""

    metadata = _maturation_metadata(report)
    required_identity = (
        report.evidence_id,
        report.task_id,
        report.model_id,
        report.candidate_model_fingerprint,
        report.coverage_demand_fingerprint,
        report.coverage_universe_id,
        report.coverage_universe_fingerprint,
        report.input_fingerprint,
        report.evidence_fingerprint,
        report.decision,
        report.confidence,
        report.terminal_reason,
    )
    if not all(required_identity):
        raise ValueError("terminal maturation report is missing receipt identity")
    claims_full = bool(
        report.decision == MODEL_MATURATION_DECISION_CLOSED_FOR_TASK
        and report.confidence == MODEL_MATURATION_CONFIDENCE_FULL
        and not report.open_gap_fingerprints
    )
    path_quality_findings = _path_quality_closure_findings(
        report.required_path_quality_model_ids,
        report.path_quality_subjects,
        report.path_quality_results,
        primary_model_id=report.model_id,
        candidate_model_fingerprint=report.candidate_model_fingerprint,
    )
    if claims_full and path_quality_findings:
        raise ValueError(
            "full maturation receipt requires exact current resolved path-quality "
            "closure: " + ", ".join(path_quality_findings)
        )
    if claims_full and not (
        report.owner_resolution_ids
        and len(report.owner_resolution_ids)
        == len(report.owner_resolution_fingerprints)
        == len(report.owner_resolution_owner_ids)
        and all(
            value.startswith("sha256:")
            for value in report.owner_resolution_fingerprints
        )
    ):
        raise ValueError(
            "full maturation receipt requires exact canonical owner resolution identities"
        )
    if claims_full:
        result_status = RECEIPT_STATUS_PASS
        blockers: tuple[str, ...] = ()
    elif report.confidence == MODEL_MATURATION_CONFIDENCE_SCOPED:
        result_status = RECEIPT_STATUS_SCOPED
        blockers = ()
    else:
        result_status = RECEIPT_STATUS_BLOCKED
        blockers = (report.terminal_reason, *report.open_gap_fingerprints)
    result_fingerprint = fingerprint_value(report.to_dict())
    receipt_seed = fingerprint_value(
        {
            "subject": f"model-maturation:{report.task_id}",
            "metadata": metadata,
            "result_fingerprint": result_fingerprint,
            "producer_id": publication.producer_id,
        }
    )
    receipt_id = f"model-maturation-receipt:{receipt_seed.split(':', 1)[1][:24]}"
    environment = dict(publication.environment_metadata)
    return EvidenceReceipt(
        receipt_id=receipt_id,
        subject_id=f"model-maturation:{report.task_id}",
        subject_kind=MODEL_MATURATION_RECEIPT_SUBJECT_KIND,
        producer_id=publication.producer_id,
        producer_version=publication.producer_version,
        claim_scope=publication.claim_scope,
        command=publication.command,
        working_directory_token=publication.working_directory_token,
        started_at=publication.started_at,
        finished_at=publication.finished_at,
        exit_code=0,
        environment_fingerprint=fingerprint_value(environment),
        environment_metadata=environment,
        contract_hash=publication.contract_hash,
        check_manifest_hash=publication.check_manifest_hash,
        suite_map_hash=publication.suite_map_hash,
        input_snapshots=publication.input_snapshots,
        proof_artifact_id=report.evidence_id,
        proof_artifact_fingerprint=report.evidence_fingerprint,
        result_status=result_status,
        result_fingerprint=result_fingerprint,
        covered_obligations=publication.covered_obligation_ids,
        supersedes_receipt_ids=publication.supersedes_receipt_ids,
        blockers=blockers,
        claim_boundary=(
            "Exact task-local model maturation only; implementation permission, "
            "broad risk confidence, installation, Git, and release remain separate."
        ),
        metadata={"model_maturation": metadata},
    )


def publish_model_maturation_receipt(
    report: ModelMaturationReport,
    publication: ModelMaturationReceiptPublication,
    repository_root: str | Path = ".",
    *,
    output_directory: str | Path | None = None,
) -> ModelMaturationReceiptRef:
    receipt = build_model_maturation_receipt(report, publication)
    save_evidence_receipt(receipt, repository_root, output_directory=output_directory)
    return ModelMaturationReceiptRef(receipt.receipt_id, receipt.fingerprint)


def _verified_from(
    receipt: EvidenceReceipt,
    verification: ReceiptVerificationResult,
    metadata: Mapping[str, Any],
) -> VerifiedModelMaturation:
    required_models, subjects, results = normalize_path_quality_material(
        metadata.get("required_path_quality_model_ids", ()),
        metadata.get("path_quality_subjects", ()),
        metadata.get("path_quality_results", ()),
    )
    subjects_by_model = {item.model_id: item for item in subjects}
    results_by_subject = {item.subject_fingerprint: item for item in results}
    summaries: list[Mapping[str, Any]] = []
    for model_id in required_models:
        subject = subjects_by_model.get(model_id)
        result = results_by_subject.get(subject.fingerprint) if subject else None
        if subject is None or result is None:
            continue
        summaries.append(
            MappingProxyType(
                {
                    "model_id": model_id,
                    "subject_fingerprint": subject.fingerprint,
                    "result_fingerprint": result.fingerprint,
                    "mode": result.mode,
                    "trigger_ids": result.trigger_ids,
                    "conclusion": result.conclusion,
                    "unresolved_ids": result.unresolved_ids,
                    "selected_candidate_lane": result.selected_candidate_lane,
                    "detail_evidence_fingerprint": (
                        result.detail_evidence_fingerprint
                    ),
                    "producer_id": result.producer_id,
                    "currentness_id": result.currentness_id,
                    "current": result.current,
                }
            )
        )
    value = object.__new__(VerifiedModelMaturation)
    values = {
        "receipt_id": receipt.receipt_id,
        "receipt_fingerprint": receipt.fingerprint,
        "evidence_id": str(metadata["evidence_id"]),
        "task_id": str(metadata["task_id"]),
        "model_id": str(metadata["model_id"]),
        "candidate_model_fingerprint": str(metadata["candidate_model_fingerprint"]),
        "coverage_demand_fingerprint": str(metadata["coverage_demand_fingerprint"]),
        "coverage_universe_id": str(metadata["coverage_universe_id"]),
        "coverage_universe_fingerprint": str(metadata["coverage_universe_fingerprint"]),
        "input_fingerprint": str(metadata["input_fingerprint"]),
        "evidence_fingerprint": str(metadata["evidence_fingerprint"]),
        "decision": str(metadata["decision"]),
        "confidence": str(metadata["confidence"]),
        "terminal_reason": str(metadata["terminal_reason"]),
        "open_gap_fingerprints": _tuple(metadata.get("open_gap_fingerprints", ())),
        "required_path_quality_model_ids": required_models,
        "path_quality_result_set_fingerprint": str(
            metadata["path_quality_result_set_fingerprint"]
        ),
        "path_quality_summaries": tuple(summaries),
        "current": verification.current,
        "eligible_for_full_claim": verification.eligible,
        "verification_status": verification.status,
        "verification_finding_codes": verification.finding_codes,
        "owner_resolution_ids": _tuple(metadata.get("owner_resolution_ids", ())),
        "owner_resolution_fingerprints": _tuple(
            metadata.get("owner_resolution_fingerprints", ())
        ),
        "owner_resolution_owner_ids": _tuple(
            metadata.get("owner_resolution_owner_ids", ())
        ),
    }
    for name, item in values.items():
        object.__setattr__(value, name, item)
    return value


def verify_model_maturation_receipt(
    receipt_ref: ModelMaturationReceiptRef,
    context: ModelMaturationVerificationContext,
    repository_root: str | Path = ".",
    *,
    output_directory: str | Path | None = None,
) -> ModelMaturationReceiptVerification:
    """Load canonical content, independently derive freshness, then project."""

    receipt = load_evidence_receipt(
        receipt_ref.receipt_id,
        repository_root,
        output_directory=output_directory,
    )
    generic = verify_evidence_receipt(receipt, context.receipt_context)
    findings: list[str] = []
    if receipt.fingerprint != receipt_ref.receipt_fingerprint:
        findings.append("maturation_receipt_reference_fingerprint_mismatch")
    if context.required_receipt_fingerprint and receipt.fingerprint != context.required_receipt_fingerprint:
        findings.append("maturation_required_receipt_fingerprint_mismatch")
    if receipt.subject_id != f"model-maturation:{context.task_id}":
        findings.append("maturation_receipt_subject_mismatch")
    if receipt.subject_kind != MODEL_MATURATION_RECEIPT_SUBJECT_KIND:
        findings.append("maturation_receipt_subject_kind_mismatch")
    raw = receipt.metadata.get("model_maturation", {})
    if not isinstance(raw, Mapping):
        raw = {}
        findings.append("maturation_receipt_metadata_missing")
    expected = {
        "schema_version": MODEL_MATURATION_RECEIPT_SCHEMA_VERSION,
        "task_id": context.task_id,
        "model_id": context.model_id,
        "candidate_model_fingerprint": context.candidate_model_fingerprint,
        "coverage_demand_fingerprint": context.coverage_demand_fingerprint,
        "coverage_universe_id": context.coverage_universe_id,
        "coverage_universe_fingerprint": context.coverage_universe_fingerprint,
        "input_fingerprint": context.input_fingerprint,
        "evidence_fingerprint": context.evidence_fingerprint,
        "path_quality_result_set_fingerprint": (
            context.path_quality_result_set_fingerprint
        ),
    }
    for name, value in expected.items():
        if str(raw.get(name, "")) != str(value):
            findings.append(f"maturation_{name}_mismatch")
    required_metadata = (
        "evidence_id",
        "decision",
        "confidence",
        "terminal_reason",
        "open_gap_fingerprints",
        "required_path_quality_model_ids",
        "path_quality_subjects",
        "path_quality_results",
        "path_quality_result_set_fingerprint",
        "owner_resolution_ids",
        "owner_resolution_fingerprints",
        "owner_resolution_owner_ids",
    )
    for name in required_metadata:
        if name not in raw:
            findings.append(f"maturation_{name}_missing")
    receipt_path_quality_subjects: tuple[PathQualitySubject, ...] = ()
    receipt_path_quality_results: tuple[PathQualityResult, ...] = ()
    try:
        (
            receipt_required_path_quality_models,
            receipt_path_quality_subjects,
            receipt_path_quality_results,
        ) = normalize_path_quality_material(
            raw.get("required_path_quality_model_ids", ()),
            raw.get("path_quality_subjects", ()),
            raw.get("path_quality_results", ()),
        )
    except (TypeError, ValueError):
        receipt_required_path_quality_models = ()
        findings.append("maturation_path_quality_material_invalid")
    if (
        receipt_required_path_quality_models
        != context.required_path_quality_model_ids
    ):
        findings.append("maturation_required_path_quality_model_ids_mismatch")
    if tuple(item.to_dict() for item in receipt_path_quality_subjects) != tuple(
        item.to_dict() for item in context.path_quality_subjects
    ):
        findings.append("maturation_path_quality_subjects_mismatch")
    if tuple(item.to_compact_dict() for item in receipt_path_quality_results) != tuple(
        item.to_compact_dict() for item in context.path_quality_results
    ):
        findings.append("maturation_path_quality_results_mismatch")
    if receipt_path_quality_subjects or receipt_path_quality_results or receipt_required_path_quality_models:
        receipt_result_set_fingerprint = path_quality_result_set_fingerprint(
            receipt_required_path_quality_models,
            receipt_path_quality_subjects,
            receipt_path_quality_results,
        )
        if (
            str(raw.get("path_quality_result_set_fingerprint", ""))
            != receipt_result_set_fingerprint
        ):
            findings.append("maturation_path_quality_result_set_invalid")
    expected_resolution_values = {
        "owner_resolution_ids": context.owner_resolution_ids,
        "owner_resolution_fingerprints": context.owner_resolution_fingerprints,
        "owner_resolution_owner_ids": context.owner_resolution_owner_ids,
    }
    for name, values in expected_resolution_values.items():
        if _tuple(raw.get(name, ())) != _tuple(values):
            findings.append(f"maturation_{name}_mismatch")
    semantic_findings = tuple(dict.fromkeys(findings))
    verified = None
    if generic.current and not semantic_findings and raw:
        verified = _verified_from(receipt, generic, raw)
    return ModelMaturationReceiptVerification(
        receipt_ref,
        generic,
        verified,
        semantic_findings,
    )


__all__ = [
    "MODEL_MATURATION_RECEIPT_CLAIM_SCOPE",
    "MODEL_MATURATION_RECEIPT_SCHEMA_VERSION",
    "ModelMaturationReceiptPublication",
    "ModelMaturationReceiptRef",
    "ModelMaturationReceiptVerification",
    "ModelMaturationVerificationContext",
    "VerifiedModelMaturation",
    "build_model_maturation_receipt",
    "publish_model_maturation_receipt",
    "verify_model_maturation_receipt",
]
