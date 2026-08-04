"""Pure, read-only projection of FlowGuard understanding readiness.

This module deliberately does not run model owners, verify receipts, or write
evidence.  It only composes explicitly supplied current artifacts and keeps
understanding sufficiency, user choice, and implementation admission separate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .evidence_receipts import fingerprint_value


UNDERSTANDING_READINESS_SCHEMA_VERSION = "flowguard.understanding_readiness.v1"

UNDERSTANDING_NOT_RUN = "not_run"
UNDERSTANDING_UNRESOLVED = "unresolved"
UNDERSTANDING_SCOPED_VERIFIED = "scoped_verified"
UNDERSTANDING_VERIFIED = "verified"
UNDERSTANDING_STALE = "stale"
UNDERSTANDING_BLOCKED = "blocked"
UNDERSTANDING_STATUSES = frozenset(
    {
        UNDERSTANDING_NOT_RUN,
        UNDERSTANDING_UNRESOLVED,
        UNDERSTANDING_SCOPED_VERIFIED,
        UNDERSTANDING_VERIFIED,
        UNDERSTANDING_STALE,
        UNDERSTANDING_BLOCKED,
    }
)

USER_CHOICE_MODEL_FIRST = "model_first"
USER_CHOICE_DIRECT = "direct_user_choice"
USER_CHOICE_NO_CODE = "no_code"
USER_EXECUTION_CHOICES = frozenset(
    {USER_CHOICE_MODEL_FIRST, USER_CHOICE_DIRECT, USER_CHOICE_NO_CODE}
)

ADMISSION_NOT_REQUESTED = "not_requested"
ADMISSION_READY = "ready"
ADMISSION_READY_SCOPED = "ready_scoped"
ADMISSION_NO_CODE = "no_code_requested"
ADMISSION_STALE = "stale"
ADMISSION_BLOCKED = "blocked"
IMPLEMENTATION_ADMISSION_STATUSES = frozenset(
    {
        ADMISSION_NOT_REQUESTED,
        ADMISSION_READY,
        ADMISSION_READY_SCOPED,
        ADMISSION_NO_CODE,
        ADMISSION_STALE,
        ADMISSION_BLOCKED,
    }
)

_SCOPED_FACT = "scoped_out"
_UNRESOLVED_FACTS = frozenset({"unknown", "omitted", "contradictory", "unmapped"})


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise TypeError("understanding status artifacts must be mappings")
    return MappingProxyType(dict(value))


def _tuple_mappings(
    values: Sequence[Mapping[str, Any]] | None,
) -> tuple[Mapping[str, Any], ...]:
    return tuple(_mapping(value) for value in (values or ()))


def _strings(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = (values,)
    return tuple(sorted({str(value) for value in values if str(value)}))


def _artifact_fingerprint(value: Mapping[str, Any]) -> str:
    payload = dict(value)
    payload.pop("fingerprint", None)
    return fingerprint_value(payload)


def _first_text(value: Mapping[str, Any], *names: str) -> str:
    for name in names:
        candidate = value.get(name)
        if candidate is not None and str(candidate):
            return str(candidate)
    return ""


@dataclass(frozen=True)
class UnderstandingReadinessInput:
    """Explicit artifact set supplied to the pure readiness composer."""

    task_facts: Mapping[str, Any] = field(default_factory=dict)
    model_identity: Mapping[str, Any] = field(default_factory=dict)
    coverage_demand: Mapping[str, Any] = field(default_factory=dict)
    owner_resolutions: tuple[Mapping[str, Any], ...] = ()
    maturation_report: Mapping[str, Any] = field(default_factory=dict)
    receipt_verification: Mapping[str, Any] = field(default_factory=dict)
    implementation_admission: Mapping[str, Any] = field(default_factory=dict)
    blueprint_summary: Mapping[str, Any] = field(default_factory=dict)
    blueprint_scope_required: str = "none"
    user_choice: str = USER_CHOICE_MODEL_FIRST
    flowguard_claim_requested: bool = True

    def __post_init__(self) -> None:
        for name in (
            "task_facts",
            "model_identity",
            "coverage_demand",
            "maturation_report",
            "receipt_verification",
            "implementation_admission",
            "blueprint_summary",
        ):
            object.__setattr__(self, name, _mapping(getattr(self, name)))
        object.__setattr__(
            self,
            "owner_resolutions",
            _tuple_mappings(self.owner_resolutions),
        )
        object.__setattr__(self, "user_choice", str(self.user_choice))
        object.__setattr__(
            self, "flowguard_claim_requested", bool(self.flowguard_claim_requested)
        )
        if self.user_choice not in USER_EXECUTION_CHOICES:
            raise ValueError(f"unknown user execution choice: {self.user_choice}")
        object.__setattr__(
            self,
            "blueprint_scope_required",
            str(self.blueprint_scope_required),
        )
        if self.blueprint_scope_required not in {"none", "affected", "whole"}:
            raise ValueError("blueprint scope required must be none, affected, or whole")


@dataclass(frozen=True)
class UnderstandingReadinessStatus:
    understanding_sufficiency: str
    user_choice: str
    implementation_admission: str
    identity: Mapping[str, str] = field(default_factory=dict)
    gap_codes: tuple[str, ...] = ()
    blocker_codes: tuple[str, ...] = ()
    mismatch_fields: tuple[str, ...] = ()
    scoped_fact_ids: tuple[str, ...] = ()
    blueprint_status: str = "not_required"
    blueprint_scope: str = "none"
    blueprint_deepest_proven_layer: str = ""
    blueprint_first_gap: str = ""
    blueprint_gap_count: int = 0
    schema_version: str = UNDERSTANDING_READINESS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.understanding_sufficiency not in UNDERSTANDING_STATUSES:
            raise ValueError(
                f"unknown understanding status: {self.understanding_sufficiency}"
            )
        if self.user_choice not in USER_EXECUTION_CHOICES:
            raise ValueError(f"unknown user execution choice: {self.user_choice}")
        if self.implementation_admission not in IMPLEMENTATION_ADMISSION_STATUSES:
            raise ValueError(
                f"unknown implementation admission: {self.implementation_admission}"
            )
        object.__setattr__(self, "identity", MappingProxyType(dict(self.identity)))
        if self.blueprint_status not in {
            "not_required",
            "not_run",
            "pass",
            "incomplete",
            "stale",
            "blocked",
        }:
            raise ValueError(f"unknown blueprint status: {self.blueprint_status}")
        if self.blueprint_scope not in {"none", "affected", "whole"}:
            raise ValueError(f"unknown blueprint scope: {self.blueprint_scope}")
        if not isinstance(self.blueprint_gap_count, int) or self.blueprint_gap_count < 0:
            raise ValueError("blueprint gap count must be a non-negative integer")
        for name in (
            "gap_codes",
            "blocker_codes",
            "mismatch_fields",
            "scoped_fact_ids",
        ):
            object.__setattr__(self, name, _strings(getattr(self, name)))

    @property
    def ok(self) -> bool:
        understanding_ok = self.understanding_sufficiency in {
            UNDERSTANDING_VERIFIED,
            UNDERSTANDING_SCOPED_VERIFIED,
        }
        admission_ok = self.implementation_admission in {
            ADMISSION_READY,
            ADMISSION_READY_SCOPED,
            ADMISSION_NO_CODE,
            ADMISSION_NOT_REQUESTED,
        }
        return understanding_ok and admission_ok

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "understanding_sufficiency": self.understanding_sufficiency,
            "user_choice": self.user_choice,
            "implementation_admission": self.implementation_admission,
            "identity": dict(self.identity),
            "gap_codes": list(self.gap_codes),
            "blocker_codes": list(self.blocker_codes),
            "mismatch_fields": list(self.mismatch_fields),
            "scoped_fact_ids": list(self.scoped_fact_ids),
            "blueprint_status": self.blueprint_status,
            "blueprint_scope": self.blueprint_scope,
            "blueprint_deepest_proven_layer": self.blueprint_deepest_proven_layer,
            "blueprint_first_gap": self.blueprint_first_gap,
            "blueprint_gap_count": self.blueprint_gap_count,
        }


def compose_understanding_status(
    inputs: UnderstandingReadinessInput,
) -> UnderstandingReadinessStatus:
    """Compose status without executing, verifying, publishing, or writing."""

    if not isinstance(inputs, UnderstandingReadinessInput):
        raise TypeError("inputs must be UnderstandingReadinessInput")

    facts = inputs.task_facts
    model = inputs.model_identity
    demand = inputs.coverage_demand
    maturation = inputs.maturation_report
    receipt = inputs.receipt_verification
    admission = inputs.implementation_admission
    blueprint = inputs.blueprint_summary

    gaps: list[str] = []
    blockers: list[str] = []
    mismatches: list[str] = []

    blueprint_status = "not_required"
    blueprint_scope = "none"
    blueprint_deepest = ""
    blueprint_first_gap = ""
    blueprint_gap_count = 0

    task_id = _first_text(facts, "task_id")
    task_fingerprint = _artifact_fingerprint(facts) if facts else ""
    demand_id = _first_text(demand, "demand_id")
    demand_fingerprint = _artifact_fingerprint(demand) if demand else ""
    resolution_basis_fingerprint = _first_text(
        demand, "resolution_basis_fingerprint"
    ) or demand_fingerprint
    model_id = _first_text(model, "model_id", "snapshot_id", "revision_id")
    model_fingerprint = _first_text(
        model,
        "candidate_model_fingerprint",
        "model_fingerprint",
        "revision_fingerprint",
        "fingerprint",
    )

    for label, artifact, computed in (
        ("task_facts", facts, task_fingerprint),
        ("coverage_demand", demand, demand_fingerprint),
    ):
        declared = _first_text(artifact, "fingerprint")
        if declared and declared != computed:
            mismatches.append(f"{label}.fingerprint")

    for name, value in (
        ("task_facts", facts),
        ("model_identity", model),
        ("coverage_demand", demand),
        ("maturation_report", maturation),
        ("receipt_verification", receipt),
    ):
        if not value:
            gaps.append(f"not_run:{name}")

    if inputs.blueprint_scope_required != "none":
        if not blueprint:
            gaps.append("not_run:blueprint_summary")
            blueprint_status = "not_run"
        else:
            declared_blueprint_fingerprint = _first_text(blueprint, "fingerprint")
            computed_blueprint_fingerprint = _artifact_fingerprint(blueprint)
            if (
                declared_blueprint_fingerprint
                and declared_blueprint_fingerprint != computed_blueprint_fingerprint
            ):
                mismatches.append("blueprint_summary.fingerprint")
            blueprint_scope = _first_text(blueprint, "scope")
            if blueprint_scope not in {"affected", "whole"}:
                blockers.append("blueprint_summary_scope_invalid")
                blueprint_scope = "none"
            if (
                inputs.blueprint_scope_required == "whole"
                and blueprint_scope != "whole"
            ):
                blockers.append("whole_blueprint_summary_required")
            layer_statuses = blueprint.get("layer_statuses", {})
            if not isinstance(layer_statuses, Mapping):
                blockers.append("blueprint_layer_statuses_invalid")
                layer_statuses = {}
            blueprint_status = str(layer_statuses.get("static_blueprint", "incomplete"))
            if blueprint_status not in {"pass", "incomplete", "stale", "blocked"}:
                blockers.append("blueprint_static_status_invalid")
                blueprint_status = "blocked"
            blueprint_deepest = _first_text(blueprint, "deepest_proven_layer")
            raw_first_gap = blueprint.get("first_gap")
            if isinstance(raw_first_gap, Mapping):
                blueprint_first_gap = ":".join(
                    value
                    for value in (
                        _first_text(raw_first_gap, "layer"),
                        _first_text(raw_first_gap, "object_kind"),
                        _first_text(raw_first_gap, "object_id"),
                    )
                    if value
                )
            raw_gap_count = blueprint.get("gap_count", 0)
            if not isinstance(raw_gap_count, int) or raw_gap_count < 0:
                blockers.append("blueprint_gap_count_invalid")
            else:
                blueprint_gap_count = raw_gap_count
            if blueprint_status != "pass":
                gaps.append(
                    "blueprint_static_"
                    + blueprint_status
                    + (f":{blueprint_first_gap}" if blueprint_first_gap else "")
                )

    if facts and not task_id:
        blockers.append("invalid_task_identity")
    if model and (not model_id or not model_fingerprint.startswith("sha256:")):
        blockers.append("invalid_model_identity")
    if demand:
        if _first_text(demand, "task_id") != task_id:
            mismatches.append("coverage_demand.task_id")
        if _first_text(demand, "task_fingerprint") != task_fingerprint:
            mismatches.append("coverage_demand.task_fingerprint")

    observations = demand.get("fact_observations", ()) or facts.get(
        "fact_observations", ()
    )
    scoped_fact_ids: list[str] = []
    for raw in observations:
        if not isinstance(raw, Mapping):
            blockers.append("invalid_fact_observation")
            continue
        fact_id = _first_text(raw, "fact_id")
        disposition = _first_text(raw, "disposition")
        if disposition == _SCOPED_FACT:
            scoped_fact_ids.append(fact_id)
        elif disposition in _UNRESOLVED_FACTS:
            gaps.append(f"task_fact_{disposition}:{fact_id}")

    required_owners: set[str] = set()
    triggered_rows: list[Mapping[str, Any]] = []
    for raw in demand.get("rows", ()) if demand else ():
        if not isinstance(raw, Mapping) or not raw.get("triggered"):
            continue
        triggered_rows.append(raw)
        owner = _first_text(raw, "owner_route")
        if owner:
            required_owners.add(owner)
        disposition = _first_text(raw, "disposition")
        if disposition == "blocked":
            blockers.extend(_strings(raw.get("blocker_codes")) or (f"blocked:{owner}",))

    resolutions_by_owner: dict[str, Mapping[str, Any]] = {}
    resolution_ids: list[str] = []
    resolution_fingerprints: list[str] = []
    for resolution in inputs.owner_resolutions:
        owner = _first_text(resolution, "owner_route", "owner_id")
        if not owner:
            blockers.append("owner_resolution_missing_owner")
            continue
        if owner in resolutions_by_owner:
            blockers.append(f"duplicate_owner_resolution:{owner}")
            continue
        resolutions_by_owner[owner] = resolution
        resolution_id = _first_text(resolution, "resolution_id")
        resolution_fingerprint = _artifact_fingerprint(resolution)
        resolution_ids.append(resolution_id)
        resolution_fingerprints.append(resolution_fingerprint)
        declared_resolution_fingerprint = _first_text(resolution, "fingerprint")
        if (
            declared_resolution_fingerprint
            and declared_resolution_fingerprint != resolution_fingerprint
        ):
            mismatches.append(f"owner_resolution[{owner}].fingerprint")
        resolution_task_id = _first_text(resolution, "task_id")
        if resolution_task_id and resolution_task_id != task_id:
            mismatches.append(f"owner_resolution[{owner}].task_id")
        resolution_demand_id = _first_text(resolution, "demand_id")
        if resolution_demand_id and resolution_demand_id != demand_id:
            mismatches.append(f"owner_resolution[{owner}].demand_id")
        resolution_demand_fingerprint = _first_text(
            resolution, "demand_fingerprint", "coverage_demand_fingerprint"
        )
        if (
            resolution_demand_fingerprint
            and resolution_demand_fingerprint != resolution_basis_fingerprint
        ):
            mismatches.append(f"owner_resolution[{owner}].demand_fingerprint")

    missing_resolution_owners = required_owners - set(resolutions_by_owner)
    if required_owners and not inputs.owner_resolutions:
        gaps.append("not_run:owner_resolutions")
    for owner in sorted(missing_resolution_owners):
        gaps.append(f"missing_owner_resolution:{owner}")
    for row in triggered_rows:
        owner = _first_text(row, "owner_route")
        if _first_text(row, "disposition") == "blocked":
            continue
        resolution = resolutions_by_owner.get(owner)
        if resolution is None:
            gaps.append(f"unresolved_coverage:{owner}")
            continue
        if _first_text(resolution, "disposition") == "blocked":
            blockers.extend(
                _strings(resolution.get("blocker_codes"))
                or (f"blocked_owner_resolution:{owner}",)
            )
            continue
        obligations = set(_strings(resolution.get("obligation_ids")))
        if not set(_strings(row.get("coverage_ids"))).issubset(obligations):
            blockers.append(f"owner_resolution_obligation_gap:{owner}")

    if maturation:
        if _first_text(maturation, "task_id") != task_id:
            mismatches.append("maturation_report.task_id")
        if _first_text(maturation, "coverage_demand_fingerprint") != demand_fingerprint:
            mismatches.append("maturation_report.coverage_demand_fingerprint")
        maturation_model_fingerprint = _first_text(
            maturation, "candidate_model_fingerprint", "model_fingerprint"
        )
        if maturation_model_fingerprint != model_fingerprint:
            mismatches.append("maturation_report.candidate_model_fingerprint")
        if _first_text(maturation, "decision") != "model_maturation_closed_for_task":
            gaps.append("maturation_not_closed_for_task")
        gaps.extend(
            f"maturation_open_gap:{value}"
            for value in _strings(maturation.get("open_gap_fingerprints"))
        )
        for field_name, current_values in (
            ("owner_resolution_ids", resolution_ids),
            ("owner_resolution_fingerprints", resolution_fingerprints),
            ("owner_resolution_owner_ids", resolutions_by_owner),
        ):
            declared_values = _strings(maturation.get(field_name))
            if current_values and not declared_values:
                gaps.append(f"maturation_missing_{field_name}")
            elif declared_values != _strings(current_values):
                mismatches.append(f"maturation_report.{field_name}")

    verified = receipt.get("verified_maturation") if receipt else None
    receipt_ref = receipt.get("receipt_ref") if receipt else None
    receipt_result = receipt.get("receipt_verification") if receipt else None
    if receipt and not isinstance(verified, Mapping):
        gaps.append("receipt_has_no_verified_maturation")
        verified = {}
    if receipt and (
        not isinstance(receipt_ref, Mapping)
        or not isinstance(receipt_result, Mapping)
    ):
        blockers.append("receipt_verification_material_missing")
        receipt_ref = {}
        receipt_result = {}
    if isinstance(receipt_ref, Mapping) and isinstance(receipt_result, Mapping):
        ref_id = _first_text(receipt_ref, "receipt_id")
        ref_fingerprint = _first_text(receipt_ref, "receipt_fingerprint")
        if not ref_id or not ref_fingerprint.startswith("sha256:"):
            blockers.append("receipt_reference_invalid")
        if _first_text(receipt_result, "receipt_id") != ref_id:
            mismatches.append("receipt_verification.receipt_id")
        if _first_text(receipt_result, "receipt_fingerprint") != ref_fingerprint:
            mismatches.append("receipt_verification.receipt_fingerprint")
        if not receipt_result.get("current"):
            mismatches.append("receipt_verification.current")
        verified_confidence = (
            _first_text(verified, "confidence")
            if isinstance(verified, Mapping)
            else ""
        )
        receipt_status = _first_text(receipt_result, "status")
        verification_eligible = bool(receipt_result.get("eligible"))
        scoped_verification = (
            verified_confidence == "scoped" and receipt_status == "scoped"
        )
        if not scoped_verification and (
            not verification_eligible or receipt_status != "pass"
        ):
            blockers.append("receipt_verification_not_eligible")
    if isinstance(verified, Mapping) and verified:
        scoped_verification = _first_text(verified, "confidence") == "scoped"
        if not receipt.get("ok") and not scoped_verification:
            blockers.append("receipt_verification_not_ok")
        if not verified.get("current"):
            mismatches.append("verified_maturation.current")
        if _first_text(verified, "task_id") != task_id:
            mismatches.append("verified_maturation.task_id")
        if _first_text(verified, "candidate_model_fingerprint") != model_fingerprint:
            mismatches.append("verified_maturation.candidate_model_fingerprint")
        if _first_text(verified, "coverage_demand_fingerprint") != demand_fingerprint:
            mismatches.append("verified_maturation.coverage_demand_fingerprint")
        if _first_text(verified, "decision") != "model_maturation_closed_for_task":
            blockers.append("verified_maturation_not_closed")
        if _strings(verified.get("open_gap_fingerprints")):
            blockers.append("verified_maturation_has_open_gaps")
        for field_name, current_values in (
            ("owner_resolution_ids", resolution_ids),
            ("owner_resolution_fingerprints", resolution_fingerprints),
            ("owner_resolution_owner_ids", resolutions_by_owner),
        ):
            declared_values = _strings(verified.get(field_name))
            if current_values and not declared_values:
                blockers.append(f"verified_maturation_missing_{field_name}")
            elif declared_values != _strings(current_values):
                mismatches.append(f"verified_maturation.{field_name}")
        if isinstance(receipt_ref, Mapping):
            if _first_text(verified, "receipt_id") != _first_text(
                receipt_ref, "receipt_id"
            ):
                mismatches.append("verified_maturation.receipt_id")
            if _first_text(verified, "receipt_fingerprint") != _first_text(
                receipt_ref, "receipt_fingerprint"
            ):
                mismatches.append("verified_maturation.receipt_fingerprint")
    if receipt:
        blockers.extend(
            f"receipt_semantic:{value}"
            for value in _strings(receipt.get("semantic_finding_codes"))
        )

    if mismatches:
        sufficiency = UNDERSTANDING_STALE
    elif blockers:
        sufficiency = UNDERSTANDING_BLOCKED
    elif any(code.startswith("not_run:") for code in gaps):
        sufficiency = UNDERSTANDING_NOT_RUN
    elif gaps:
        sufficiency = UNDERSTANDING_UNRESOLVED
    else:
        confidence = _first_text(verified, "confidence") if isinstance(verified, Mapping) else ""
        sufficiency = (
            UNDERSTANDING_SCOPED_VERIFIED
            if scoped_fact_ids or confidence == "scoped"
            else UNDERSTANDING_VERIFIED
        )

    if inputs.user_choice == USER_CHOICE_NO_CODE:
        admission_status = ADMISSION_NO_CODE
    elif not inputs.flowguard_claim_requested:
        admission_status = ADMISSION_NOT_REQUESTED
    elif sufficiency == UNDERSTANDING_STALE:
        admission_status = ADMISSION_STALE
    elif sufficiency not in {UNDERSTANDING_VERIFIED, UNDERSTANDING_SCOPED_VERIFIED}:
        admission_status = ADMISSION_BLOCKED
    else:
        upstream_admission = _first_text(admission, "status")
        expected = (
            ADMISSION_READY_SCOPED
            if sufficiency == UNDERSTANDING_SCOPED_VERIFIED
            else ADMISSION_READY
        )
        if not admission:
            gaps.append("not_run:implementation_admission")
            admission_status = ADMISSION_BLOCKED
        elif upstream_admission == ADMISSION_STALE:
            admission_status = ADMISSION_STALE
        elif upstream_admission not in {ADMISSION_READY, ADMISSION_READY_SCOPED}:
            blockers.append("implementation_admission_not_ready")
            admission_status = ADMISSION_BLOCKED
        else:
            admission_status = expected

    identity = {
        "task_id": task_id,
        "task_fingerprint": task_fingerprint,
        "model_id": model_id,
        "model_fingerprint": model_fingerprint,
        "coverage_demand_id": demand_id,
        "coverage_demand_fingerprint": demand_fingerprint,
        "owner_resolution_set_fingerprint": (
            fingerprint_value(sorted(resolution_fingerprints))
            if resolution_fingerprints
            else ""
        ),
        "maturation_evidence_id": _first_text(maturation, "evidence_id", "plan_id"),
        "receipt_id": (
            _first_text(verified, "receipt_id")
            if isinstance(verified, Mapping)
            else ""
        ),
        "admission_id": _first_text(admission, "admission_id"),
        "blueprint_id": _first_text(blueprint, "blueprint_fingerprint"),
        "blueprint_summary_fingerprint": _first_text(blueprint, "fingerprint"),
    }
    return UnderstandingReadinessStatus(
        sufficiency,
        inputs.user_choice,
        admission_status,
        identity=identity,
        gap_codes=tuple(gaps),
        blocker_codes=tuple(blockers),
        mismatch_fields=tuple(mismatches),
        scoped_fact_ids=tuple(scoped_fact_ids),
        blueprint_status=blueprint_status,
        blueprint_scope=blueprint_scope,
        blueprint_deepest_proven_layer=blueprint_deepest,
        blueprint_first_gap=blueprint_first_gap,
        blueprint_gap_count=blueprint_gap_count,
    )


__all__ = [
    "ADMISSION_BLOCKED",
    "ADMISSION_NO_CODE",
    "ADMISSION_NOT_REQUESTED",
    "ADMISSION_READY",
    "ADMISSION_READY_SCOPED",
    "ADMISSION_STALE",
    "IMPLEMENTATION_ADMISSION_STATUSES",
    "UNDERSTANDING_BLOCKED",
    "UNDERSTANDING_NOT_RUN",
    "UNDERSTANDING_READINESS_SCHEMA_VERSION",
    "UNDERSTANDING_SCOPED_VERIFIED",
    "UNDERSTANDING_STALE",
    "UNDERSTANDING_STATUSES",
    "UNDERSTANDING_UNRESOLVED",
    "UNDERSTANDING_VERIFIED",
    "USER_CHOICE_DIRECT",
    "USER_CHOICE_MODEL_FIRST",
    "USER_CHOICE_NO_CODE",
    "USER_EXECUTION_CHOICES",
    "UnderstandingReadinessInput",
    "UnderstandingReadinessStatus",
    "compose_understanding_status",
]
