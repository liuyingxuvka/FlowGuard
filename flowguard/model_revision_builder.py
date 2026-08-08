"""Build one accepted current model revision without activating authority."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .evidence_receipts import (
    RECEIPT_STATUS_PASS,
    EvidenceReceipt,
    ReceiptVerificationResult,
    fingerprint_value,
    load_evidence_receipt,
    verify_evidence_receipt,
)
from .model_authority import (
    REVISION_EVIDENCE_PASS,
    REVISION_EVIDENCE_REQUIRED,
    ModelAuthorityError,
    ModelSystemSnapshot,
)
from .model_authority_store import (
    load_current_accepted_revision_set,
    load_observed_model_system,
)
from .model_intent import (
    ModelIntentContribution,
    ModelIntentDisposition,
    verify_model_intent_sources,
)
from .model_intent_authority import (
    EffectiveIntentBootstrapReceipt,
    EffectiveIntentTransition,
    bootstrap_current_effective_intent_view,
    build_current_effective_intent_view,
    build_current_intent_bootstrap_receipt,
    fold_effective_intent_contributions,
    validate_candidate_intent_source_input_bindings,
    validate_current_effective_intent_refinement,
    validate_current_effective_intent_view,
)
from .model_path_quality import PathQualityResult, PathQualitySubject
from .model_regressions import (
    ModelRegressionManifest,
    _model_parent_owner_contract,
    _model_owner_contract,
    audit_intent_source_input_bindings,
    audit_manifest,
    select_entries,
)
from .model_revision_set import (
    ModelRevisionSet,
    RevisionEvidenceRef,
    RevisionRemovalDisposition,
    derive_revision_affected_closure,
    derive_revision_snapshot_diff,
)
from .model_system_inventory import build_manifest_model_system_snapshot
from .project_manifest import project_manifest_lock
from .source_identity import source_file_fingerprint
from .validation_ownership import (
    OWNER_RECEIPT_KIND,
    OWNER_REUSE_CURRENT,
    ValidationOwnerContract,
    ValidationOwnerObservation,
    _assert_owner_receipt_integrity,
    build_child_bound_owner_receipt_context,
    build_owner_current,
    observe_validation_owners,
)


MODEL_REVISION_BUILD_REPORT_SCHEMA = "flowguard.model_revision_build_report.v1"
MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA = (
    "flowguard.model_regression_parent_receipt.v2"
)
MODEL_REGRESSION_PARENT_ARTIFACT_TYPE = (
    "flowguard_model_regression_parent_receipt"
)
_PARENT_FIELDS = frozenset(
    {
        "artifact_type",
        "schema_version",
        "claim_scope",
        "tier",
        "status",
        "manifest_sha256",
        "selected_model_ids",
        "skipped_model_ids",
        "children",
        "execution_receipt_id",
        "execution_receipt_fingerprint",
        "claim_boundary",
        "parent_receipt_fingerprint",
    }
)
_CHILD_FIELDS = frozenset(
    {"model_id", "receipt_id", "receipt_fingerprint"}
)


@dataclass(frozen=True)
class ModelRevisionBuildReport:
    root: str
    parent_receipt_path: str
    parent_receipt_fingerprint: str
    observed_head_fingerprint: str
    candidate_snapshot_path: str
    candidate_snapshot_fingerprint: str
    revision_set_path: str
    revision_set_fingerprint: str
    revision_set_id: str
    task_id: str
    snapshot_id: str
    affected_owner_routes: tuple[str, ...]
    missing_owner_routes: tuple[str, ...]
    missing_path_quality_model_ids: tuple[str, ...]
    affected_id_count: int
    status: str = "incomplete"
    schema: str = MODEL_REVISION_BUILD_REPORT_SCHEMA
    claim_boundary: str = (
        "Generation freezes one current-format candidate/revision pair. The "
        "model-regression parent proves only its parent execution; acceptance "
        "additionally requires one exact current leaf receipt per affected "
        "native owner and exact current observed path-quality results covering "
        "at least every added or replaced model. An explicitly supplied larger "
        "current candidate denominator is accepted only as one fully checked set. "
        "It does not execute models, activate authority, update "
        "the observed head, or prove release readiness."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "root": self.root,
            "parent_receipt_path": self.parent_receipt_path,
            "parent_receipt_fingerprint": self.parent_receipt_fingerprint,
            "observed_head_fingerprint": self.observed_head_fingerprint,
            "candidate_snapshot_path": self.candidate_snapshot_path,
            "candidate_snapshot_fingerprint": (
                self.candidate_snapshot_fingerprint
            ),
            "revision_set_path": self.revision_set_path,
            "revision_set_fingerprint": self.revision_set_fingerprint,
            "revision_set_id": self.revision_set_id,
            "task_id": self.task_id,
            "snapshot_id": self.snapshot_id,
            "affected_owner_routes": list(self.affected_owner_routes),
            "missing_owner_routes": list(self.missing_owner_routes),
            "missing_path_quality_model_ids": list(
                self.missing_path_quality_model_ids
            ),
            "affected_id_count": self.affected_id_count,
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class _VerifiedModelParent:
    fingerprint: str
    observation: ValidationOwnerObservation
    contracts_by_model: Mapping[str, ValidationOwnerContract]
    currents_by_model: Mapping[str, Any]
    receipts_by_model: Mapping[str, EvidenceReceipt]
    verifications_by_model: Mapping[str, ReceiptVerificationResult]


def _reject_duplicate_json_keys(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ModelAuthorityError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ModelAuthorityError(f"non-finite JSON number: {value}")
            ),
        )
    except (OSError, json.JSONDecodeError, ModelAuthorityError) as exc:
        raise ModelAuthorityError(f"cannot load JSON artifact {path}: {exc}") from exc


def load_revision_removal_dispositions(
    path: str | Path,
) -> tuple[RevisionRemovalDisposition, ...]:
    """Load the current typed removal-disposition array with no legacy reader."""

    source = Path(path).resolve()
    payload = _read_json(source)
    if not isinstance(payload, list):
        raise ModelAuthorityError("removal dispositions must be a JSON array")
    return tuple(RevisionRemovalDisposition.from_dict(item) for item in payload)


def _string_array(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ModelAuthorityError(f"{field_name} must be an array of strings")
    result = tuple(value)
    if len(result) != len(set(result)):
        raise ModelAuthorityError(f"{field_name} must not contain duplicates")
    return result


def _parent_children(value: Any) -> tuple[Mapping[str, str], ...]:
    if not isinstance(value, list):
        raise ModelAuthorityError("model parent children must be an array")
    rows: list[Mapping[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ModelAuthorityError(
                f"model parent child {index} must be an object"
            )
        if set(item) != _CHILD_FIELDS:
            raise ModelAuthorityError(
                "model parent child fields must match the current schema exactly"
            )
        row = {name: str(item[name]) for name in _CHILD_FIELDS}
        if any(not value for value in row.values()):
            raise ModelAuthorityError("model parent child fields must be non-empty")
        rows.append(row)
    model_ids = tuple(row["model_id"] for row in rows)
    if len(model_ids) != len(set(model_ids)):
        raise ModelAuthorityError("model parent children must identify unique models")
    return tuple(rows)


def _verify_model_parent_receipt(
    root: Path,
    parent_receipt_path: Path,
    receipt_root: Path,
) -> _VerifiedModelParent:
    payload = _read_json(parent_receipt_path)
    if not isinstance(payload, Mapping):
        raise ModelAuthorityError("model parent receipt must be a JSON object")
    if set(payload) != _PARENT_FIELDS:
        missing = sorted(_PARENT_FIELDS - set(payload))
        unknown = sorted(set(payload) - _PARENT_FIELDS)
        raise ModelAuthorityError(
            "model parent receipt fields do not match the current schema: "
            f"missing={missing}, unknown={unknown}"
        )
    if payload["artifact_type"] != MODEL_REGRESSION_PARENT_ARTIFACT_TYPE:
        raise ModelAuthorityError("artifact is not a model-regression parent receipt")
    if payload["schema_version"] != MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA:
        raise ModelAuthorityError("model parent receipt schema is not current")
    if (
        payload["claim_scope"] != "full"
        or payload["tier"] != "full"
        or payload["status"] != RECEIPT_STATUS_PASS
    ):
        raise ModelAuthorityError(
            "model parent receipt must be terminal pass with full claim scope and tier"
        )
    skipped_ids = _string_array(payload["skipped_model_ids"], "skipped_model_ids")
    if skipped_ids:
        raise ModelAuthorityError("full model parent receipt contains skipped models")

    declared_fingerprint = str(payload["parent_receipt_fingerprint"])
    identity_payload = {
        key: value
        for key, value in payload.items()
        if key != "parent_receipt_fingerprint"
    }
    if fingerprint_value(identity_payload) != declared_fingerprint:
        raise ModelAuthorityError("model parent receipt fingerprint is stale")

    manifest = ModelRegressionManifest.load(root)
    audit = audit_manifest(root, manifest)
    if not audit.ok:
        raise ModelAuthorityError(
            "current model-regression manifest is invalid: "
            + "; ".join(audit.errors)
        )
    if str(payload["manifest_sha256"]) != source_file_fingerprint(manifest.path):
        raise ModelAuthorityError("model parent receipt manifest fingerprint is stale")
    entries = select_entries(manifest, tier="full")
    selected_ids = tuple(entry.model_id for entry in entries)
    if _string_array(payload["selected_model_ids"], "selected_model_ids") != selected_ids:
        raise ModelAuthorityError(
            "model parent selected ids do not equal the current full manifest"
        )
    children = _parent_children(payload["children"])
    children_by_model = {row["model_id"]: row for row in children}
    if tuple(row["model_id"] for row in children) != tuple(sorted(selected_ids)):
        raise ModelAuthorityError(
            "model parent children do not cover the current full manifest exactly"
        )

    contracts = tuple(_model_owner_contract(root, manifest, entry) for entry in entries)
    observation = observe_validation_owners(
        root,
        contracts,
        receipt_root=receipt_root,
    )
    rows = observation.rows
    currents = observation.current_by_owner
    reusable = observation.receipt_by_owner
    observed_verifications = observation.verification_by_owner
    noncurrent = tuple(
        row.owner_id for row in rows if row.disposition != OWNER_REUSE_CURRENT
    )
    if noncurrent:
        raise ModelAuthorityError(
            "model parent child evidence is not exact-current for owners: "
            + ", ".join(noncurrent)
        )

    exact_children: list[EvidenceReceipt] = []
    child_verifications: list[ReceiptVerificationResult] = []
    for model_id in selected_ids:
        owner_id = f"model:{model_id}"
        receipt = reusable[owner_id]
        declared = children_by_model[model_id]
        if (
            declared["receipt_id"] != receipt.receipt_id
            or declared["receipt_fingerprint"] != receipt.fingerprint
        ):
            raise ModelAuthorityError(
                f"model parent child is not the exact current receipt: {model_id}"
            )
        expected_obligations = (f"model-regression:{model_id}",)
        if (
            receipt.result_status != RECEIPT_STATUS_PASS
            or receipt.exit_code != 0
            or receipt.claim_scope != "full"
            or receipt.covered_obligations != expected_obligations
            or receipt.skipped_checks
            or receipt.blockers
        ):
            raise ModelAuthorityError(
                f"model parent child is not terminal full exact-obligation pass: {model_id}"
            )
        child_verification = observed_verifications[owner_id]
        if not child_verification.ok:
            raise ModelAuthorityError(
                f"model parent child failed independent current verification: {model_id}"
            )
        exact_children.append(receipt)
        child_verifications.append(child_verification)

    execution_receipt_id = str(payload["execution_receipt_id"])
    execution_receipt_fingerprint = str(
        payload["execution_receipt_fingerprint"]
    )
    if not execution_receipt_id or not execution_receipt_fingerprint:
        raise ModelAuthorityError(
            "passing model parent lacks its canonical execution receipt"
        )
    try:
        execution_receipt = load_evidence_receipt(
            execution_receipt_id,
            root,
            output_directory=receipt_root,
        )
        _assert_owner_receipt_integrity(execution_receipt)
    except (OSError, ValueError) as exc:
        raise ModelAuthorityError(
            f"model parent execution receipt is unavailable or invalid: {exc}"
        ) from exc
    if (
        execution_receipt.fingerprint != execution_receipt_fingerprint
        or execution_receipt.subject_id
        != "validation-owner:model-regression-parent"
        or execution_receipt.subject_kind != OWNER_RECEIPT_KIND
    ):
        raise ModelAuthorityError(
            "model parent execution receipt identity does not match its canonical store object"
        )
    parent_contract = _model_parent_owner_contract(
        manifest,
        entries,
        claim_scope="full",
        tier="full",
    )
    parent_current = build_owner_current(
        root,
        parent_contract,
        all_contracts=(parent_contract,),
    )
    parent_context = build_child_bound_owner_receipt_context(
        parent_current,
        execution_receipt,
        root,
        receipt_root,
        child_receipts=tuple(exact_children),
        child_verification_results=tuple(child_verifications),
    )
    parent_verification = verify_evidence_receipt(
        execution_receipt,
        parent_context,
    )
    if not parent_verification.ok:
        raise ModelAuthorityError(
            "model parent execution receipt is not an exact-current full composition: "
            + ", ".join(item.code for item in parent_verification.findings)
        )
    return _VerifiedModelParent(
        fingerprint=declared_fingerprint,
        observation=observation,
        contracts_by_model={
            entry.model_id: currents[f"model:{entry.model_id}"].contract
            for entry in entries
        },
        currents_by_model={
            entry.model_id: currents[f"model:{entry.model_id}"]
            for entry in entries
        },
        receipts_by_model={
            entry.model_id: reusable[f"model:{entry.model_id}"]
            for entry in entries
        },
        verifications_by_model={
            entry.model_id: observed_verifications[f"model:{entry.model_id}"]
            for entry in entries
        },
    )


def _owner_toolchain_fingerprint(receipt: EvidenceReceipt) -> str:
    return fingerprint_value(
        {
            "producer_id": receipt.producer_id,
            "producer_version": receipt.producer_version,
            "contract_hash": receipt.contract_hash,
            "check_manifest_hash": receipt.check_manifest_hash,
            "suite_map_hash": receipt.suite_map_hash,
            "command": list(receipt.command),
        }
    )


def _native_owner_revision_evidence(
    *,
    ids_by_owner: Mapping[str, Sequence[str]],
    candidate: ModelSystemSnapshot,
    affected_closure_fingerprint: str,
    contracts: Sequence[ValidationOwnerContract],
    receipts: Sequence[EvidenceReceipt],
    verification_results: Sequence[ReceiptVerificationResult],
) -> tuple[tuple[RevisionEvidenceRef, ...], tuple[str, ...]]:
    expected_owners = set(ids_by_owner)
    contracts_by_owner: dict[str, list[ValidationOwnerContract]] = {}
    for contract in contracts:
        contracts_by_owner.setdefault(contract.owner_id, []).append(contract)
    foreign_contract_owners = tuple(
        sorted(set(contracts_by_owner) - expected_owners)
    )
    if foreign_contract_owners:
        raise ModelAuthorityError(
            "native owner contracts contain foreign routes: "
            + ", ".join(foreign_contract_owners)
        )
    duplicate_contract_owners = tuple(
        sorted(
            owner_id
            for owner_id, rows in contracts_by_owner.items()
            if len(rows) != 1
        )
    )
    if duplicate_contract_owners:
        raise ModelAuthorityError(
            "native owner contracts must be unique: "
            + ", ".join(duplicate_contract_owners)
        )

    receipts_by_owner: dict[str, list[EvidenceReceipt]] = {}
    receipt_ids: set[str] = set()
    receipt_fingerprints: set[str] = set()
    for receipt in receipts:
        if receipt.subject_kind == "validation_parent":
            raise ModelAuthorityError(
                "validation-parent receipt cannot substitute for native owner evidence"
            )
        if receipt.subject_kind != OWNER_RECEIPT_KIND:
            raise ModelAuthorityError(
                "native owner evidence must use validation_owner leaf receipts"
            )
        prefix = "validation-owner:"
        if not receipt.subject_id.startswith(prefix):
            raise ModelAuthorityError(
                "native owner receipt subject does not identify its owner route"
            )
        owner_route = receipt.subject_id[len(prefix) :]
        if owner_route not in expected_owners:
            raise ModelAuthorityError(
                f"native owner receipt has foreign route: {owner_route}"
            )
        if receipt.producer_id != receipt.subject_id:
            raise ModelAuthorityError(
                f"native owner receipt producer mismatch: {owner_route}"
            )
        if receipt.receipt_id in receipt_ids or receipt.fingerprint in receipt_fingerprints:
            raise ModelAuthorityError(
                "native owner leaf receipt cannot be reused across owner routes"
            )
        receipt_ids.add(receipt.receipt_id)
        receipt_fingerprints.add(receipt.fingerprint)
        receipts_by_owner.setdefault(owner_route, []).append(receipt)

    verifications_by_receipt: dict[str, list[ReceiptVerificationResult]] = {}
    for result in verification_results:
        verifications_by_receipt.setdefault(result.receipt_id, []).append(result)
    supplied_receipt_ids = {
        receipt.receipt_id for receipt in receipts
    }
    foreign_verification_ids = tuple(
        sorted(set(verifications_by_receipt) - supplied_receipt_ids)
    )
    if foreign_verification_ids:
        raise ModelAuthorityError(
            "native owner verification references foreign receipts: "
            + ", ".join(foreign_verification_ids)
        )
    duplicate_verification_ids = tuple(
        sorted(
            receipt_id
            for receipt_id, rows in verifications_by_receipt.items()
            if len(rows) != 1
        )
    )
    if duplicate_verification_ids:
        raise ModelAuthorityError(
            "native owner receipts require one verification result: "
            + ", ".join(duplicate_verification_ids)
        )

    required_refs: list[RevisionEvidenceRef] = []
    missing_owners: list[str] = []
    for owner_route in sorted(expected_owners):
        contract_rows = contracts_by_owner.get(owner_route, [])
        receipt_rows = receipts_by_owner.get(owner_route, [])
        if len(contract_rows) != 1 or len(receipt_rows) != 1:
            missing_owners.append(owner_route)
            continue
        contract = contract_rows[0]
        receipt = receipt_rows[0]
        verification_rows = verifications_by_receipt.get(receipt.receipt_id, [])
        if len(verification_rows) != 1:
            missing_owners.append(owner_route)
            continue
        verification = verification_rows[0]
        affected_ids = tuple(sorted(ids_by_owner[owner_route]))
        if not set(affected_ids).issubset(contract.obligation_ids):
            raise ModelAuthorityError(
                f"native owner contract omits affected ids: {owner_route}"
            )
        if (
            receipt.result_status != RECEIPT_STATUS_PASS
            or receipt.exit_code != 0
            or receipt.claim_scope != "full"
            or receipt.skipped_checks
            or receipt.blockers
        ):
            raise ModelAuthorityError(
                f"native owner receipt is not terminal full pass: {owner_route}"
            )
        if not set(affected_ids).issubset(receipt.covered_obligations):
            raise ModelAuthorityError(
                f"native owner receipt omits affected ids: {owner_route}"
            )
        if verification.receipt_fingerprint != receipt.fingerprint:
            raise ModelAuthorityError(
                f"native owner verification fingerprint mismatch: {owner_route}"
            )
        if (
            not verification.current
            or not verification.eligible
            or verification.status != RECEIPT_STATUS_PASS
        ):
            raise ModelAuthorityError(
                f"native owner verification is not exact-current pass: {owner_route}"
            )
        if not set(affected_ids).issubset(
            verification.satisfied_obligations
        ):
            raise ModelAuthorityError(
                f"native owner verification omits affected ids: {owner_route}"
            )
        required_refs.append(
            RevisionEvidenceRef(
                receipt_id=receipt.receipt_id,
                receipt_fingerprint=receipt.fingerprint,
                owner_route=owner_route,
                subject_fingerprint=candidate.fingerprint,
                obligation_ids=receipt.covered_obligations,
                affected_closure_fingerprint=affected_closure_fingerprint,
                covered_affected_ids=affected_ids,
                candidate_snapshot_fingerprint=candidate.fingerprint,
                toolchain_fingerprint=_owner_toolchain_fingerprint(receipt),
                environment_fingerprint=receipt.environment_fingerprint,
                status=REVISION_EVIDENCE_REQUIRED,
                current=True,
                eligible=True,
            )
        )
    return tuple(required_refs), tuple(missing_owners)


def _content_addressed_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _write_content_addressed_pair(
    output_root: Path,
    candidate: ModelSystemSnapshot,
    revision: ModelRevisionSet,
) -> tuple[Path, Path]:
    candidate_path = (
        output_root
        / "snapshots"
        / f"{candidate.fingerprint.split(':', 1)[1]}.json"
    )
    revision_path = (
        output_root
        / "revisions"
        / f"{revision.fingerprint.split(':', 1)[1]}.json"
    )
    artifacts = (
        (candidate_path, _content_addressed_bytes(candidate.to_dict())),
        (revision_path, _content_addressed_bytes(revision.to_dict())),
    )
    for path, encoded in artifacts:
        if path.exists() and path.read_bytes() != encoded:
            raise ModelAuthorityError(
                f"content-addressed model revision path contains different bytes: {path}"
            )
    temporary_paths: list[Path] = []
    created_paths: list[Path] = []
    try:
        for path, encoded in artifacts:
            if path.exists():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".json.tmp")
            if temporary.exists():
                raise ModelAuthorityError(
                    f"model revision temporary path already exists: {temporary}"
                )
            temporary.write_bytes(encoded)
            temporary_paths.append(temporary)
        for path, _encoded in artifacts:
            temporary = path.with_suffix(".json.tmp")
            if temporary in temporary_paths:
                temporary.replace(path)
                created_paths.append(path)
    except Exception:
        for path in reversed(created_paths):
            if path.exists():
                path.unlink()
        raise
    finally:
        for temporary in temporary_paths:
            if temporary.exists():
                temporary.unlink()
    return candidate_path, revision_path


def _unique_intent_source_inputs(
    *inventories: Iterable[ModelIntentContribution],
) -> tuple[ModelIntentContribution, ...]:
    by_id: dict[str, ModelIntentContribution] = {}
    for inventory in inventories:
        for contribution in inventory:
            if not isinstance(contribution, ModelIntentContribution):
                raise ModelAuthorityError(
                    "intent source inventory requires typed current contributions"
                )
            existing = by_id.get(contribution.contribution_id)
            if existing is not None and existing.fingerprint != contribution.fingerprint:
                raise ModelAuthorityError(
                    "one intent contribution id has conflicting content across "
                    f"revision and current view: {contribution.contribution_id}"
                )
            by_id[contribution.contribution_id] = contribution
    return tuple(sorted(by_id.values(), key=lambda item: item.contribution_id))


def _validate_bootstrap_revision_delta(
    active_contributions: tuple[ModelIntentContribution, ...],
    revision_contributions: tuple[ModelIntentContribution, ...],
    revision_dispositions: tuple[ModelIntentDisposition, ...],
) -> None:
    active_by_id = {
        item.contribution_id: item for item in active_contributions
    }
    revision_by_id = {
        item.contribution_id: item for item in revision_contributions
    }
    dispositions_by_id = {
        item.contribution_id: item for item in revision_dispositions
    }
    if len(revision_by_id) != len(revision_contributions) or len(
        dispositions_by_id
    ) != len(revision_dispositions):
        raise ModelAuthorityError(
            "bootstrap revision intent requires unique contribution and disposition ids"
        )
    if set(revision_by_id) != set(dispositions_by_id):
        raise ModelAuthorityError(
            "bootstrap revision intent requires one exact disposition per contribution"
        )
    for contribution_id, disposition in dispositions_by_id.items():
        revision_contribution = revision_by_id[contribution_id]
        if disposition.contribution_fingerprint != revision_contribution.fingerprint:
            raise ModelAuthorityError(
                "bootstrap revision disposition fingerprint mismatch: "
                f"{contribution_id}"
            )
        active_contribution = active_by_id.get(contribution_id)
        if (
            active_contribution is not None
            and active_contribution.fingerprint != revision_contribution.fingerprint
        ):
            raise ModelAuthorityError(
                "bootstrap current design and revision delta reuse an id with different content: "
                f"{contribution_id}"
            )
        if disposition.disposition == "accepted" and (
            active_contribution is None
            or active_contribution.fingerprint != revision_contribution.fingerprint
        ):
            raise ModelAuthorityError(
                "accepted bootstrap revision intent must also exist in the current design view: "
                f"{contribution_id}"
            )


def build_current_model_revision(
    root: str | Path,
    *,
    model_parent_receipt: str | Path,
    revision_set_id: str,
    task_id: str,
    snapshot_id: str,
    receipt_root: str | Path | None = None,
    output_root: str | Path | None = None,
    removal_dispositions: Iterable[RevisionRemovalDisposition] = (),
    intent_contributions: Iterable[ModelIntentContribution] = (),
    intent_dispositions: Iterable[ModelIntentDisposition] = (),
    effective_intent_transitions: Iterable[EffectiveIntentTransition] = (),
    current_design_intent_contributions: Iterable[
        ModelIntentContribution
    ] = (),
    effective_intent_bootstrap_receipt: (
        EffectiveIntentBootstrapReceipt | None
    ) = None,
    native_owner_contracts: Iterable[ValidationOwnerContract] = (),
    native_owner_receipts: Iterable[EvidenceReceipt] = (),
    native_owner_verification_results: Iterable[ReceiptVerificationResult] = (),
    path_quality_subjects: Iterable[PathQualitySubject | Mapping[str, Any]] = (),
    path_quality_results: Iterable[PathQualityResult | Mapping[str, Any]] = (),
    no_declared_intent_rationale_id: str = "",
    no_declared_intent_evidence_fingerprints: Iterable[tuple[str, str]] = (),
    no_declared_intent_rationale: str = "",
    decision_reason: str = (
        "The model-regression parent is exact-current and every affected "
        "native owner contributes its own exact-current terminal-pass leaf receipt."
    ),
) -> ModelRevisionBuildReport:
    """Build a proposed or accepted revision while leaving authority untouched."""

    root_path = Path(root).resolve()
    parent_path = Path(model_parent_receipt).resolve()
    receipt_store = (
        Path(receipt_root).resolve()
        if receipt_root is not None
        else root_path / ".flowguard" / "evidence" / "model-owner-receipts"
    )
    destination = (
        Path(output_root).resolve()
        if output_root is not None
        else root_path / ".flowguard" / "model-mesh"
    )
    dispositions = tuple(removal_dispositions)
    contributions = tuple(intent_contributions)
    contribution_dispositions = tuple(intent_dispositions)
    lineage_transitions = tuple(effective_intent_transitions)
    current_design_contributions = tuple(
        current_design_intent_contributions
    )
    owner_contracts = tuple(native_owner_contracts)
    owner_receipts = tuple(native_owner_receipts)
    owner_verifications = tuple(native_owner_verification_results)
    path_subjects = tuple(path_quality_subjects)
    path_results = tuple(path_quality_results)
    if any(not isinstance(item, RevisionRemovalDisposition) for item in dispositions):
        raise ModelAuthorityError(
            "removal dispositions must be current typed RevisionRemovalDisposition records"
        )

    manifest_path = root_path / ".flowguard" / "project.toml"
    with project_manifest_lock(manifest_path):
        head, base = load_observed_model_system(root_path)
        if effective_intent_bootstrap_receipt is not None:
            if not current_design_contributions:
                raise ModelAuthorityError(
                    "explicit intent bootstrap requires current design contributions"
                )
            if lineage_transitions:
                raise ModelAuthorityError(
                    "intent bootstrap cannot also consume prior-view transitions"
                )
            _validate_bootstrap_revision_delta(
                current_design_contributions,
                contributions,
                contribution_dispositions,
            )
            active_contributions = current_design_contributions
            base_effective_view = None
        else:
            if current_design_contributions:
                raise ModelAuthorityError(
                    "current design bootstrap contributions require an explicit bootstrap receipt"
                )
            current_revision = load_current_accepted_revision_set(
                root_path,
                head=head,
                snapshot=base,
            )
            if current_revision is None:
                raise ModelAuthorityError(
                    "the first cumulative intent revision requires an explicit bootstrap receipt"
                )
            base_effective_view = (
                current_revision.current_effective_intent_view
            )
            active_contributions = fold_effective_intent_contributions(
                base_effective_view,
                contributions,
                contribution_dispositions,
                lineage_transitions,
            )
        intent_source_inputs = _unique_intent_source_inputs(
            active_contributions,
            contributions,
        )
        frozen_intent_sources = verify_model_intent_sources(
            root_path,
            intent_source_inputs,
        )
        frozen_sources_by_id = {
            item.contribution_id: item for item in frozen_intent_sources
        }
        frozen_active_sources = tuple(
            frozen_sources_by_id[item.contribution_id]
            for item in active_contributions
        )
        manifest = ModelRegressionManifest.load(root_path)
        binding_errors = audit_intent_source_input_bindings(
            root_path,
            manifest,
            active_contributions,
            frozen_active_sources,
        )
        if binding_errors:
            raise ModelAuthorityError(
                "candidate intent-source model-input binding is incomplete: "
                + "; ".join(binding_errors)
            )
        verified_parent = _verify_model_parent_receipt(
            root_path,
            parent_path,
            receipt_store,
        )
        candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=snapshot_id,
            system_id=base.system_id,
            subject_lane=base.subject_lane,
            lifecycle=base.lifecycle,
        )
        validate_candidate_intent_source_input_bindings(
            candidate,
            active_contributions,
            frozen_active_sources,
        )
        if effective_intent_bootstrap_receipt is not None:
            receipt = effective_intent_bootstrap_receipt
            rebuilt_receipt = build_current_intent_bootstrap_receipt(
                root_path,
                receipt_id=receipt.receipt_id,
                candidate_snapshot=candidate,
                current_design_contributions=active_contributions,
                rationale=receipt.rationale,
                legacy_entry_dispositions=(
                    receipt.legacy_entry_dispositions
                ),
                claim_boundary=receipt.claim_boundary,
            )
            if rebuilt_receipt != receipt:
                raise ModelAuthorityError(
                    "effective intent bootstrap receipt is stale or foreign"
                )
            current_effective_intent_view = (
                bootstrap_current_effective_intent_view(
                    candidate,
                    active_contributions,
                    frozen_active_sources,
                    receipt,
                )
            )
        else:
            current_effective_intent_view = (
                build_current_effective_intent_view(
                    base_effective_view,
                    candidate,
                    active_contributions,
                    frozen_active_sources,
                    lineage_transitions,
                )
            )
        validate_current_effective_intent_view(
            candidate,
            current_effective_intent_view,
        )
        if base_effective_view is not None:
            validate_current_effective_intent_refinement(
                root_path,
                base_view=base_effective_view,
                candidate_snapshot=candidate,
                revision_contributions=contributions,
                revision_dispositions=contribution_dispositions,
                candidate_view=current_effective_intent_view,
            )
        diff = derive_revision_snapshot_diff(base, candidate)
        closure = derive_revision_affected_closure(base, candidate, diff)
        if not closure.affected_ids:
            raise ModelAuthorityError(
                "current manifest does not differ from the observed model authority"
            )
        if owner_contracts or owner_receipts or owner_verifications:
            # Keep this import local: the producer reuses the builder's parent
            # verification helpers, while the builder consumes the producer's
            # strict wire bundle only after both modules are initialized.
            from .model_revision_owner_evidence import (
                ModelRevisionOwnerEvidenceBundle,
                assert_verified_model_revision_owner_evidence_current,
                verify_model_revision_owner_evidence_bundle,
            )

            try:
                supplied_bundle = ModelRevisionOwnerEvidenceBundle(
                    contracts=owner_contracts,
                    receipts=owner_receipts,
                    verification_results=owner_verifications,
                )
            except ValueError as exc:
                raise ModelAuthorityError(
                    f"native owner evidence bundle is incomplete or malformed: {exc}"
                ) from exc
            independently_verified = verify_model_revision_owner_evidence_bundle(
                root_path,
                model_parent_receipt=parent_path,
                snapshot_id=snapshot_id,
                bundle=supplied_bundle,
                receipt_root=receipt_store,
                verified_parent=verified_parent,
            )
            frozen_identities = (
                (
                    "model-regression parent",
                    verified_parent.fingerprint,
                    independently_verified.parent_receipt_fingerprint,
                ),
                (
                    "observed authority head",
                    head.fingerprint,
                    independently_verified.observed_head_fingerprint,
                ),
                (
                    "candidate snapshot",
                    candidate.fingerprint,
                    independently_verified.candidate_snapshot_fingerprint,
                ),
                (
                    "snapshot diff",
                    diff.fingerprint,
                    independently_verified.snapshot_diff_fingerprint,
                ),
                (
                    "affected closure",
                    closure.fingerprint,
                    independently_verified.affected_closure_fingerprint,
                ),
            )
            changed_identities = tuple(
                name
                for name, builder_fingerprint, verified_fingerprint in frozen_identities
                if builder_fingerprint != verified_fingerprint
            )
            if changed_identities:
                raise ModelAuthorityError(
                    "native owner evidence was verified against different revision "
                    "inputs: " + ", ".join(changed_identities)
                )
            owner_contracts = independently_verified.bundle.contracts
            owner_receipts = independently_verified.bundle.receipts
            owner_verifications = (
                independently_verified.bundle.verification_results
            )
        ids_by_owner: dict[str, list[str]] = {}
        for affected_id, owner_route in closure.owner_bindings:
            ids_by_owner.setdefault(owner_route, []).append(affected_id)
        required, missing_owner_routes = _native_owner_revision_evidence(
            ids_by_owner=ids_by_owner,
            candidate=candidate,
            affected_closure_fingerprint=closure.fingerprint,
            contracts=owner_contracts,
            receipts=owner_receipts,
            verification_results=owner_verifications,
        )
        proposed = ModelRevisionSet(
            revision_set_id=revision_set_id,
            task_id=task_id,
            expected_head_fingerprint=head.fingerprint,
            base_snapshot_fingerprint=base.fingerprint,
            candidate_snapshot_fingerprint=candidate.fingerprint,
            members=diff.members,
            affected_closure_ids=closure.affected_ids,
            affected_closure_fingerprint=closure.fingerprint,
            affected_edge_ids=closure.edge_ids,
            affected_owner_bindings=closure.owner_bindings,
            snapshot_diff_fingerprint=diff.fingerprint,
            changed_root_ids=diff.changed_root_ids,
            changed_relation_ids=diff.changed_relation_ids,
            changed_source_surface_ids=diff.changed_source_surface_ids,
            changed_commitment_ids=diff.changed_commitment_ids,
            changed_field_ids=diff.changed_field_ids,
            changed_side_effect_ids=diff.changed_side_effect_ids,
            changed_contract_ids=diff.changed_contract_ids,
            changed_test_ids=diff.changed_test_ids,
            changed_system_property_ids=diff.changed_system_property_ids,
            changed_coverage_ids=diff.changed_coverage_ids,
            changed_gap_ids=diff.changed_gap_ids,
            changed_owner_artifact_ids=diff.changed_owner_artifact_ids,
            added_ids=diff.added_ids,
            removed_ids=diff.removed_ids,
            fingerprint_changed_ids=diff.fingerprint_changed_ids,
            removal_dispositions=dispositions,
            required_path_quality_model_ids=(
                ()
                if path_subjects or path_results
                else tuple(
                    sorted(
                        item.member_id
                        for item in diff.members
                        if item.operation in {"add", "replace"}
                    )
                )
            ),
            path_quality_subjects=path_subjects,
            path_quality_results=path_results,
            intent_contributions=contributions,
            intent_dispositions=contribution_dispositions,
            current_effective_intent_view=current_effective_intent_view,
            no_declared_intent_rationale_id=no_declared_intent_rationale_id,
            no_declared_intent_evidence_fingerprints=tuple(
                no_declared_intent_evidence_fingerprints
            ),
            no_declared_intent_rationale=no_declared_intent_rationale,
            required_evidence_refs=required,
        )
        revision = proposed
        if not missing_owner_routes and proposed.path_quality_acceptance_ready:
            revision = proposed.accept(
                (
                    replace(item, status=REVISION_EVIDENCE_PASS)
                    for item in required
                ),
                reason=decision_reason,
            )
        final_head, _final_base = load_observed_model_system(root_path)
        if final_head.fingerprint != head.fingerprint:
            raise ModelAuthorityError(
                "observed authority head changed during revision generation"
            )
        final_candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=snapshot_id,
            system_id=base.system_id,
            subject_lane=base.subject_lane,
            lifecycle=base.lifecycle,
        )
        validate_candidate_intent_source_input_bindings(
            final_candidate,
            active_contributions,
            frozen_active_sources,
        )
        if final_candidate.identity_payload() != candidate.identity_payload():
            raise ModelAuthorityError(
                "live model inputs changed during revision generation"
            )
        validate_current_effective_intent_view(
            final_candidate,
            current_effective_intent_view,
        )
        if owner_contracts or owner_receipts or owner_verifications:
            # Recheck only the identities consumed by the already verified
            # frozen bundle.  Candidate semantics were rebuilt immediately
            # above, so repeating the complete model-parent/child verifier here
            # would add no independent evidence.
            assert_verified_model_revision_owner_evidence_current(
                root_path,
                independently_verified,
            )
        try:
            final_intent_sources = verify_model_intent_sources(
                root_path,
                intent_source_inputs,
            )
        except ModelAuthorityError as exc:
            raise ModelAuthorityError(
                "intent source changed before revision publication: "
                f"{exc}"
            ) from exc
        if final_intent_sources != frozen_intent_sources:
            raise ModelAuthorityError(
                "intent source identity changed before revision publication"
            )
        if base_effective_view is not None:
            validate_current_effective_intent_refinement(
                root_path,
                base_view=base_effective_view,
                candidate_snapshot=final_candidate,
                revision_contributions=contributions,
                revision_dispositions=contribution_dispositions,
                candidate_view=current_effective_intent_view,
            )
        candidate_path, revision_path = _write_content_addressed_pair(
            destination,
            candidate,
            revision,
        )

    return ModelRevisionBuildReport(
        root=str(root_path),
        parent_receipt_path=str(parent_path),
        parent_receipt_fingerprint=verified_parent.fingerprint,
        observed_head_fingerprint=head.fingerprint,
        candidate_snapshot_path=str(candidate_path),
        candidate_snapshot_fingerprint=candidate.fingerprint,
        revision_set_path=str(revision_path),
        revision_set_fingerprint=revision.fingerprint,
        revision_set_id=revision.revision_set_id,
        task_id=revision.task_id,
        snapshot_id=candidate.snapshot_id,
        affected_owner_routes=tuple(sorted(ids_by_owner)),
        missing_owner_routes=missing_owner_routes,
        missing_path_quality_model_ids=revision.path_quality_blocked_model_ids,
        affected_id_count=len(closure.affected_ids),
        status=("pass" if revision.status == "accepted" else "incomplete"),
    )


__all__ = [
    "MODEL_REVISION_BUILD_REPORT_SCHEMA",
    "ModelRevisionBuildReport",
    "build_current_model_revision",
    "load_revision_removal_dispositions",
]
