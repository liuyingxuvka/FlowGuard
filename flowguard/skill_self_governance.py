"""Receipt-bound parent governance for the seventeen FlowGuard skills.

The parent in this module never accepts caller-authored ``current`` or
``pass`` flags.  It loads immutable child receipts, verifies every child
against an independently supplied current context, and consumes the exact
receipt identities and fingerprints.  Repository-local evidence is stored by
``flowguard.evidence_receipts`` under ``.flowguard/evidence/skill-suite``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Mapping, Sequence

from .evidence_receipts import (
    ChildReceiptRequirement,
    ConsumedChildReceipt,
    EvidenceReceipt,
    InputSnapshot,
    RECEIPT_STATUS_PASS,
    ReceiptVerificationContext,
    ReceiptVerificationResult,
    build_environment_fingerprint,
    fingerprint_value,
    list_evidence_receipts,
    save_evidence_receipt,
    snapshot_file,
    verify_evidence_receipt,
)
from .route_topology import RouteHandoff, route_handoffs
from .self_maintenance import SelfMaintenanceChildReport
from .skill_native_checks import build_current_native_receipt_context
from .skill_suite import validate_skill_suite


SUITE_MAP_PATH = Path(".skillguard/flowguard-suite/suite-map.json")
SELF_GOVERNANCE_SUBJECT = "flowguard-skill-self-governance"
SELF_GOVERNANCE_PRODUCER = "flowguard.skill_self_governance"
SELF_GOVERNANCE_CLAIM_SCOPE = "full"

LAYER_ENGINE_AND_CORE = "engine_and_core_tests"
LAYER_SKILL_CONTRACTS = "skill_contract_governance"
LAYER_FULL_SELF_GOVERNANCE = "full_self_governance"
GOVERNANCE_LAYERS = (
    LAYER_ENGINE_AND_CORE,
    LAYER_SKILL_CONTRACTS,
    LAYER_FULL_SELF_GOVERNANCE,
)

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_BLOCKED = "blocked"
STATUS_NOT_RUN = "not_run"

FULL_GOVERNANCE_OBLIGATIONS = (
    "flowguard.self_governance.engine_and_core_tests",
    "flowguard.self_governance.skill_contract_governance",
    "flowguard.self_governance.full_self_governance",
)


def skill_contract_obligation_id(skill_id: str) -> str:
    """Return the stable umbrella obligation consumed for one deep contract."""

    return f"flowguard.skill_contract.{str(skill_id)}.deep"


def _as_tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values if str(value))


def _package_version() -> str:
    try:
        return importlib_metadata.version("flowguard")
    except importlib_metadata.PackageNotFoundError:
        return "0+local"


@dataclass(frozen=True)
class GovernanceChildRequirement:
    """One canonical suite member and the obligation its receipt must prove."""

    subject_id: str
    owner_route: str
    obligation_id: str
    role: str = "public_satellite"

    def to_dict(self) -> dict[str, str]:
        return {
            "subject_id": self.subject_id,
            "owner_route": self.owner_route,
            "obligation_id": self.obligation_id,
            "role": self.role,
        }


def load_governance_requirements(
    repository_root: str | Path = ".",
    *,
    suite_map_path: str | Path = SUITE_MAP_PATH,
) -> tuple[GovernanceChildRequirement, ...]:
    """Load the canonical required suite membership without a second inventory."""

    root = Path(repository_root).resolve()
    path = Path(suite_map_path)
    if not path.is_absolute():
        path = root / path
    data = json.loads(path.read_text(encoding="utf-8"))
    members = data.get("included_skills", ())
    requirements = tuple(
        GovernanceChildRequirement(
            subject_id=str(member["name"]),
            owner_route=str(member.get("owner", "")),
            obligation_id=skill_contract_obligation_id(str(member["name"])),
            role=str(member.get("role", "public_satellite")),
        )
        for member in members
        if bool(member.get("required", True))
    )
    subject_ids = tuple(item.subject_id for item in requirements)
    if len(subject_ids) != 17:
        raise ValueError(f"full FlowGuard self-governance requires exactly 17 suite members, found {len(subject_ids)}")
    if len(set(subject_ids)) != len(subject_ids):
        raise ValueError("suite map contains duplicate required skill ids")
    return requirements


@dataclass(frozen=True)
class GovernanceLayerResult:
    layer_id: str
    status: str
    evidence_receipt_ids: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    skipped_checks: tuple[str, ...] = ()
    residual_risk: tuple[str, ...] = ()
    claim_boundary: str = ""

    @property
    def ok(self) -> bool:
        return self.status == STATUS_PASS and not self.blockers and not self.skipped_checks

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "status": self.status,
            "evidence_receipt_ids": list(self.evidence_receipt_ids),
            "blockers": list(self.blockers),
            "skipped_checks": list(self.skipped_checks),
            "residual_risk": list(self.residual_risk),
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class SkillSelfGovernanceReport:
    requirements: tuple[GovernanceChildRequirement, ...]
    child_reports: tuple[SelfMaintenanceChildReport, ...]
    child_verification_results: tuple[ReceiptVerificationResult, ...]
    layers: tuple[GovernanceLayerResult, ...]
    blockers: tuple[str, ...] = ()
    skipped_checks: tuple[str, ...] = ()
    residual_risk: tuple[str, ...] = ()
    minimum_revalidation: tuple[str, ...] = ()
    typed_downstream: tuple[RouteHandoff, ...] = ()
    self_governance_receipt: EvidenceReceipt | None = None
    self_governance_receipt_hash: str = ""
    claim_boundary: str = (
        "A full result proves only the exact seventeen receipt-bound skill contracts in the current repository; "
        "release, installation, distribution, or future agent behavior need their own current evidence."
    )

    @property
    def ok(self) -> bool:
        return (
            len(self.layers) == len(GOVERNANCE_LAYERS)
            and all(layer.ok for layer in self.layers)
            and not self.blockers
            and self.self_governance_receipt is not None
        )

    @property
    def status(self) -> str:
        return STATUS_PASS if self.ok else STATUS_BLOCKED

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_skill_self_governance_report",
            "status": self.status,
            "ok": self.ok,
            "required_child_count": len(self.requirements),
            "requirements": [item.to_dict() for item in self.requirements],
            "child_reports": [item.to_dict() for item in self.child_reports],
            "child_verification_results": [item.to_dict() for item in self.child_verification_results],
            "layers": [item.to_dict() for item in self.layers],
            "blockers": list(self.blockers),
            "skipped_checks": list(self.skipped_checks),
            "residual_risk": list(self.residual_risk),
            "minimum_revalidation": list(self.minimum_revalidation),
            "typed_downstream": [item.to_dict() for item in self.typed_downstream],
            "self_governance_receipt_hash": self.self_governance_receipt_hash,
            "self_governance_receipt": (
                self.self_governance_receipt.to_dict() if self.self_governance_receipt is not None else None
            ),
            "claim_boundary": self.claim_boundary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)

    def format_text(self) -> str:
        lines = [
            "=== FlowGuard skill self-governance ===",
            f"status: {self.status}",
            f"required_children: {len(self.requirements)}",
        ]
        lines.extend(f"- {layer.layer_id}: {layer.status}" for layer in self.layers)
        if self.blockers:
            lines.append("blockers:")
            lines.extend(f"- {item}" for item in self.blockers)
        if self.minimum_revalidation:
            lines.append("minimum_revalidation:")
            lines.extend(f"- {item}" for item in self.minimum_revalidation)
        lines.append(f"receipt_hash: {self.self_governance_receipt_hash or 'not-emitted'}")
        lines.append(f"claim_boundary: {self.claim_boundary}")
        return "\n".join(lines)


def verification_context_from_dict(data: Mapping[str, Any]) -> ReceiptVerificationContext:
    """Parse a context manifest produced independently from a child receipt."""

    snapshots_raw = data.get("input_snapshots", {})
    if isinstance(snapshots_raw, Sequence) and not isinstance(snapshots_raw, (str, bytes, bytearray)):
        snapshots = {str(item["artifact_id"]): InputSnapshot.from_dict(item) for item in snapshots_raw}
    else:
        snapshots = {
            str(key): value if isinstance(value, InputSnapshot) else InputSnapshot.from_dict(value)
            for key, value in dict(snapshots_raw).items()
        }
    return ReceiptVerificationContext(
        input_snapshots=snapshots,
        contract_hash=str(data.get("contract_hash", "")),
        check_manifest_hash=str(data.get("check_manifest_hash", "")),
        suite_map_hash=str(data.get("suite_map_hash", "")),
        producer_id=str(data.get("producer_id", "")),
        producer_version=str(data.get("producer_version", "")),
        environment_fingerprint=str(data.get("environment_fingerprint", "")),
        proof_artifact_fingerprint=str(data.get("proof_artifact_fingerprint", "")),
        result_fingerprint=str(data.get("result_fingerprint", "")),
        command=tuple(str(item) for item in data.get("command", ())),
        working_directory_token=str(data.get("working_directory_token", "")),
        proof_artifact_id=str(data.get("proof_artifact_id", "")),
        required_obligation_ids=_as_tuple(data.get("required_obligation_ids", ())),
        eligible_claim_scopes=_as_tuple(data.get("eligible_claim_scopes", ("full",))),
    )


def load_verification_contexts(path: str | Path) -> dict[str, ReceiptVerificationContext]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    values = data.get("contexts", data)
    if not isinstance(values, Mapping):
        raise ValueError("verification context manifest must be an object keyed by receipt or subject id")
    return {str(key): verification_context_from_dict(value) for key, value in values.items()}


def _latest_receipts_by_subject(receipts: Sequence[EvidenceReceipt]) -> dict[str, EvidenceReceipt]:
    latest: dict[str, EvidenceReceipt] = {}
    for receipt in receipts:
        previous = latest.get(receipt.subject_id)
        if previous is None or (receipt.finished_at, receipt.receipt_id) > (previous.finished_at, previous.receipt_id):
            latest[receipt.subject_id] = receipt
    return latest


def _input_fingerprint(receipt: EvidenceReceipt) -> str:
    return fingerprint_value([item.to_dict() for item in receipt.input_snapshots])


def _layer(
    layer_id: str,
    child_reports: Sequence[SelfMaintenanceChildReport],
    *,
    full_layer: bool = False,
) -> GovernanceLayerResult:
    evidence_ids = tuple(item.receipt_id for item in child_reports if item.receipt_id)
    failures = tuple(item for item in child_reports if not item.is_current_pass())
    blockers = tuple(
        f"{item.child_id}:{item.closure_status}:receipt must be current, eligible, exact pass, full scope, and obligation-bound"
        for item in failures
    )
    skipped = tuple(
        f"{item.child_id}:{check}"
        for item in child_reports
        for check in item.skipped_checks
    )
    if not failures and not skipped and child_reports:
        status = STATUS_PASS
    elif full_layer:
        status = STATUS_BLOCKED
    elif not child_reports:
        status = STATUS_NOT_RUN
    else:
        status = STATUS_FAIL
    return GovernanceLayerResult(
        layer_id=layer_id,
        status=status,
        evidence_receipt_ids=evidence_ids,
        blockers=blockers,
        skipped_checks=skipped,
        residual_risk=(
            "Receipt evidence is environment-local and does not predict future agent behavior.",
        ),
        claim_boundary=(
            "Exact current receipt evidence for this layer only; no release or distribution claim is implied."
        ),
    )


def _parent_receipt(
    repository_root: Path,
    requirements: Sequence[GovernanceChildRequirement],
    receipts: Sequence[EvidenceReceipt],
    verification_results: Mapping[str, ReceiptVerificationResult],
    typed_downstream: Sequence[RouteHandoff],
) -> EvidenceReceipt:
    suite_map = repository_root / SUITE_MAP_PATH
    module_path = repository_root / "flowguard/skill_self_governance.py"
    snapshots = (
        snapshot_file(
            "flowguard-suite-map",
            suite_map,
            workspace_root=repository_root,
            obligation_ids=FULL_GOVERNANCE_OBLIGATIONS,
        ),
        snapshot_file(
            "skill-self-governance-parent",
            module_path,
            workspace_root=repository_root,
            obligation_ids=FULL_GOVERNANCE_OBLIGATIONS,
        ),
    )
    child_fingerprints = {item.receipt_id: item.fingerprint for item in receipts}
    requirements_hash = fingerprint_value([item.to_dict() for item in requirements])
    suite_hash = validate_skill_suite(repository_root).inventory_hash
    proof_payload = {
        "requirements_hash": requirements_hash,
        "child_receipts": child_fingerprints,
        "verification": {key: value.to_dict() for key, value in sorted(verification_results.items())},
        "typed_downstream": [item.to_dict() for item in typed_downstream],
    }
    proof_hash = fingerprint_value(proof_payload)
    environment = build_environment_fingerprint(
        {
            "python_implementation": "CPython",
            "python_version": __import__("platform").python_version(),
            "platform_system": __import__("platform").system(),
            "platform_machine": __import__("platform").machine(),
            "flowguard_version": _package_version(),
        }
    )
    started_at = min(item.started_at for item in receipts)
    finished_at = max(item.finished_at for item in receipts)
    receipt_id = f"receipt:self-governance:{proof_hash.split(':', 1)[-1][:24]}"
    return EvidenceReceipt(
        receipt_id=receipt_id,
        subject_id=SELF_GOVERNANCE_SUBJECT,
        subject_kind="skill_suite_parent",
        producer_id=SELF_GOVERNANCE_PRODUCER,
        producer_version=_package_version(),
        claim_scope=SELF_GOVERNANCE_CLAIM_SCOPE,
        command=("python", "scripts/check_flowguard_self_governance.py", "--json"),
        working_directory_token="<WORKSPACE>",
        started_at=started_at,
        finished_at=finished_at,
        exit_code=0,
        environment_fingerprint=environment.fingerprint,
        environment_metadata=environment.metadata,
        contract_hash=requirements_hash,
        check_manifest_hash=fingerprint_value(
            {"producer": SELF_GOVERNANCE_PRODUCER, "obligations": FULL_GOVERNANCE_OBLIGATIONS}
        ),
        suite_map_hash=suite_hash,
        input_snapshots=snapshots,
        proof_artifact_id="proof:flowguard-skill-self-governance",
        proof_artifact_fingerprint=proof_hash,
        result_status=RECEIPT_STATUS_PASS,
        result_fingerprint=proof_hash,
        covered_obligations=FULL_GOVERNANCE_OBLIGATIONS,
        required_child_receipts=tuple(
            ChildReceiptRequirement(
                receipt_id=receipt.receipt_id,
                subject_id=requirement.subject_id,
                obligation_ids=(requirement.obligation_id,),
                eligible_claim_scopes=("full",),
                expected_receipt_fingerprint=receipt.fingerprint,
            )
            for requirement, receipt in zip(requirements, receipts)
        ),
        consumed_child_receipts=tuple(
            ConsumedChildReceipt(receipt.receipt_id, receipt.fingerprint) for receipt in receipts
        ),
        claim_boundary=(
            "The parent consumed the exact seventeen current deep-contract receipts. Distribution, installation, "
            "release, and future agent behavior remain outside this receipt."
        ),
        metadata={"typed_downstream": [item.to_dict() for item in typed_downstream]},
    )


def run_skill_self_governance(
    repository_root: str | Path = ".",
    *,
    receipts: Sequence[EvidenceReceipt] | None = None,
    verification_contexts: Mapping[str, ReceiptVerificationContext] | None = None,
    output_directory: str | Path | None = None,
    save_parent_receipt: bool = True,
) -> SkillSelfGovernanceReport:
    """Verify and exactly consume all seventeen required child receipts."""

    root = Path(repository_root).resolve()
    requirements = load_governance_requirements(root)
    receipt_values = tuple(
        receipts
        if receipts is not None
        else list_evidence_receipts(root, output_directory=output_directory)
    )
    contexts = dict(verification_contexts or {})
    latest = _latest_receipts_by_subject(receipt_values)
    child_reports: list[SelfMaintenanceChildReport] = []
    verification_results: list[ReceiptVerificationResult] = []
    consumed_receipts: list[EvidenceReceipt] = []
    blockers: list[str] = []
    minimum_revalidation: list[str] = []

    for requirement in requirements:
        receipt = latest.get(requirement.subject_id)
        if receipt is None:
            blockers.append(f"missing_child_receipt:{requirement.subject_id}")
            minimum_revalidation.append(f"run-child:{requirement.subject_id}")
            child_reports.append(
                SelfMaintenanceChildReport.unbound(
                    child_id=requirement.subject_id,
                    owner_guard=requirement.owner_route,
                    artifact_kind="skill_contract",
                    missing_inputs=(requirement.obligation_id,),
                    next_actions=(f"run-child:{requirement.subject_id}",),
                    unsafe_claim_boundary="A missing receipt cannot support any self-governance claim.",
                )
            )
            continue
        context = (
            contexts.get(receipt.receipt_id)
            or contexts.get(requirement.subject_id)
            or build_current_native_receipt_context(receipt, root)
        )
        if context is not None:
            context = ReceiptVerificationContext(
                input_snapshots=context.input_snapshots,
                contract_hash=context.contract_hash,
                check_manifest_hash=context.check_manifest_hash,
                suite_map_hash=context.suite_map_hash,
                producer_id=context.producer_id,
                producer_version=context.producer_version,
                environment_fingerprint=context.environment_fingerprint,
                proof_artifact_fingerprint=context.proof_artifact_fingerprint,
                result_fingerprint=context.result_fingerprint,
                command=context.command,
                working_directory_token=context.working_directory_token,
                proof_artifact_id=context.proof_artifact_id,
                required_obligation_ids=(requirement.obligation_id,),
                eligible_claim_scopes=("full",),
                child_receipts=context.child_receipts,
                child_verification_results=context.child_verification_results,
                latest_child_receipt_ids=context.latest_child_receipt_ids,
            )
        result = verify_evidence_receipt(receipt, context)
        verification_results.append(result)
        child_reports.append(
            SelfMaintenanceChildReport.from_verified_receipt(
                receipt,
                result,
                child_id=requirement.subject_id,
                owner_guard=requirement.owner_route,
                artifact_kind="skill_contract",
            )
        )
        if not result.ok or receipt.claim_scope != "full" or requirement.obligation_id not in result.satisfied_obligations:
            blockers.append(f"child_not_current_exact_pass:{requirement.subject_id}:{result.status}")
            minimum_revalidation.extend(result.minimum_revalidation or (f"rerun-producer:{requirement.subject_id}",))
        else:
            consumed_receipts.append(receipt)

    by_child = {item.child_id: item for item in child_reports}
    kernel_reports = tuple(
        item for item in child_reports if item.child_id == "model-first-function-flow"
    )
    all_reports = tuple(by_child[item.subject_id] for item in requirements)
    engine_layer = _layer(LAYER_ENGINE_AND_CORE, kernel_reports)
    contract_layer = _layer(LAYER_SKILL_CONTRACTS, all_reports)
    full_layer = _layer(LAYER_FULL_SELF_GOVERNANCE, all_reports, full_layer=True)
    layers = (engine_layer, contract_layer, full_layer)
    typed_downstream = route_handoffs(
        "model_test_alignment",
        "test_mesh_maintenance",
        "development_process_flow",
    )

    parent_receipt: EvidenceReceipt | None = None
    parent_hash = ""
    if not blockers and len(consumed_receipts) == len(requirements) and all(layer.ok for layer in layers):
        result_by_id = {item.receipt_id: item for item in verification_results}
        parent_receipt = _parent_receipt(
            root,
            requirements,
            consumed_receipts,
            result_by_id,
            typed_downstream,
        )
        parent_hash = parent_receipt.fingerprint
        if save_parent_receipt:
            save_evidence_receipt(parent_receipt, root, output_directory=output_directory)

    report = SkillSelfGovernanceReport(
        requirements=requirements,
        child_reports=tuple(child_reports),
        child_verification_results=tuple(verification_results),
        layers=layers,
        blockers=tuple(dict.fromkeys(blockers)),
        skipped_checks=tuple(
            dict.fromkeys(check for child in child_reports for check in child.skipped_checks)
        ),
        residual_risk=(
            "Model regression scheduling, installation parity, documentation parity, versioning, and publication remain downstream gates.",
        ),
        minimum_revalidation=tuple(dict.fromkeys(minimum_revalidation)),
        typed_downstream=typed_downstream,
        self_governance_receipt=parent_receipt,
        self_governance_receipt_hash=parent_hash,
    )
    return report


__all__ = [
    "FULL_GOVERNANCE_OBLIGATIONS",
    "GOVERNANCE_LAYERS",
    "GovernanceChildRequirement",
    "GovernanceLayerResult",
    "LAYER_ENGINE_AND_CORE",
    "LAYER_FULL_SELF_GOVERNANCE",
    "LAYER_SKILL_CONTRACTS",
    "SELF_GOVERNANCE_SUBJECT",
    "SkillSelfGovernanceReport",
    "load_governance_requirements",
    "load_verification_contexts",
    "run_skill_self_governance",
    "skill_contract_obligation_id",
    "verification_context_from_dict",
]
