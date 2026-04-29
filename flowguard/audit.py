"""Lightweight model quality audit helpers for FlowGuard models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from .core import FrozenMetadata, block_name, freeze_metadata
from .export import to_jsonable
from .risk import RiskProfile


FINDING_SEVERITIES = ("error", "warning", "suggestion")
AUDIT_STATUSES = ("pass", "pass_with_gaps", "failed")


@dataclass(frozen=True)
class ModelQualityFinding:
    """One model-quality finding from a lightweight audit."""

    severity: str
    category: str
    message: str
    recommendation: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        severity = str(self.severity).lower()
        if severity not in FINDING_SEVERITIES:
            raise ValueError(f"severity must be one of {FINDING_SEVERITIES!r}")
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "category", str(self.category))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "recommendation", str(self.recommendation or ""))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "recommendation": self.recommendation,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class ModelQualityAuditReport:
    """Warning-oriented model-quality audit report."""

    ok: bool
    status: str
    findings: tuple[ModelQualityFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        status = str(self.status).lower()
        if status not in AUDIT_STATUSES:
            raise ValueError(f"status must be one of {AUDIT_STATUSES!r}")
        object.__setattr__(self, "ok", bool(self.ok))
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "summary", str(self.summary or ""))

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard model quality audit ===",
            f"status: {self.status}",
            f"ok: {self.ok}",
            self.summary or _summary_for_findings(self.findings),
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"{finding.severity.upper()}: {finding.category}",
                    f"message: {finding.message}",
                ]
            )
            if finding.recommendation:
                lines.append(f"recommendation: {finding.recommendation}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def _as_tuple_or_none(values: Iterable[Any] | None) -> tuple[Any, ...] | None:
    if values is None:
        return None
    return tuple(values)


def _finding(
    severity: str,
    category: str,
    message: str,
    recommendation: str = "",
    metadata: dict[str, Any] | None = None,
) -> ModelQualityFinding:
    return ModelQualityFinding(
        severity=severity,
        category=category,
        message=message,
        recommendation=recommendation,
        metadata=metadata or {},
    )


def _summary_for_findings(findings: Sequence[ModelQualityFinding]) -> str:
    counts = {severity: 0 for severity in FINDING_SEVERITIES}
    for finding in findings:
        counts[finding.severity] += 1
    return (
        f"errors={counts['error']} warnings={counts['warning']} "
        f"suggestions={counts['suggestion']}"
    )


def _status_for_findings(findings: Sequence[ModelQualityFinding]) -> tuple[bool, str]:
    if any(finding.severity == "error" for finding in findings):
        return False, "failed"
    if any(finding.severity == "warning" for finding in findings):
        return True, "pass_with_gaps"
    return True, "pass"


def _invariant_text(invariant: Any) -> str:
    return (
        str(getattr(invariant, "name", ""))
        + " "
        + str(getattr(invariant, "description", ""))
    ).lower()


PROPERTY_CLASS_METADATA_KEYS = frozenset(
    {
        "property_class",
        "property_classes",
        "flowguard_property_class",
        "flowguard_property_classes",
    }
)


def _metadata_items(metadata: Any) -> tuple[tuple[Any, Any], ...]:
    if metadata is None:
        return ()
    if hasattr(metadata, "items"):
        raw_items = tuple(metadata.items())
    else:
        try:
            raw_items = tuple(metadata)
        except TypeError:
            return ()
    items: list[tuple[Any, Any]] = []
    for item in raw_items:
        try:
            key, value = item
        except (TypeError, ValueError):
            continue
        items.append((key, value))
    return tuple(items)


def _coerce_metadata_values(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    try:
        return tuple(value)
    except TypeError:
        return (value,)


def _invariant_property_classes(invariant: Any) -> frozenset[str]:
    values: list[str] = []
    for key, value in _metadata_items(getattr(invariant, "metadata", None)):
        if str(key).strip().lower() not in PROPERTY_CLASS_METADATA_KEYS:
            continue
        values.extend(
            str(item).strip().lower()
            for item in _coerce_metadata_values(value)
            if str(item).strip()
        )
    return frozenset(values)


def _has_invariant_keyword(invariants: Sequence[Any], keywords: Sequence[str]) -> bool:
    lowered = tuple(keyword.lower() for keyword in keywords)
    for invariant in invariants:
        text = _invariant_text(invariant)
        if any(keyword in text for keyword in lowered):
            return True
    return False


def _has_invariant_evidence(
    invariants: Sequence[Any],
    *,
    property_classes: Sequence[str],
    keywords: Sequence[str],
) -> bool:
    desired_classes = frozenset(
        str(item).strip().lower()
        for item in property_classes
        if str(item).strip()
    )
    for invariant in invariants:
        if desired_classes.intersection(_invariant_property_classes(invariant)):
            return True
    return _has_invariant_keyword(invariants, keywords)


def audit_model(
    *,
    workflow: Any = None,
    invariants: Iterable[Any] | None = None,
    external_inputs: Iterable[Any] | None = None,
    max_sequence_length: int | None = None,
    scenarios: Iterable[Any] | None = None,
    contracts: Iterable[Any] | None = None,
    progress_config: Any = None,
    conformance_config: Any = None,
    conformance_status: str | None = None,
    declared_risk_classes: Iterable[str] | None = None,
    skipped_steps: Iterable[str] | None = None,
    risk_profile: RiskProfile | dict[str, Any] | None = None,
) -> ModelQualityAuditReport:
    """Audit obvious model-quality gaps without blocking model execution.

    The audit is intentionally heuristic. Warnings and suggestions describe
    confidence boundaries; only structural problems that make the model clearly
    unusable are reported as errors.
    """

    findings: list[ModelQualityFinding] = []
    profile = _coerce_risk_profile(risk_profile)
    profile_risks = profile.risk_classes if profile is not None else ()
    risks = frozenset(
        str(item).strip().lower()
        for item in tuple(declared_risk_classes or ()) + tuple(profile_risks)
        if str(item).strip()
    )
    invariants_tuple = _as_tuple_or_none(invariants)
    inputs_tuple = _as_tuple_or_none(external_inputs)
    scenarios_tuple = _as_tuple_or_none(scenarios)
    contracts_tuple = _as_tuple_or_none(contracts)
    skipped_tuple = tuple(str(item) for item in (skipped_steps or ()))
    profile_skipped = profile.skipped_checks if profile is not None else ()

    if profile is not None:
        for warning in profile.validation_warnings:
            findings.append(
                _finding(
                    "suggestion",
                    "risk_profile_warning",
                    warning,
                    "Unknown risk classes are allowed, but audit heuristics only know the standard classes.",
                    {"modeled_boundary": profile.modeled_boundary},
                )
            )

    if workflow is None:
        findings.append(
            _finding(
                "suggestion",
                "missing_workflow",
                "workflow was not provided to audit_model, so block structure was not checked",
                "Pass workflow=... when you want block and metadata checks.",
            )
        )
    else:
        try:
            blocks = tuple(getattr(workflow, "blocks"))
        except Exception as exc:
            findings.append(
                _finding(
                    "error",
                    "invalid_workflow",
                    f"workflow blocks could not be read: {type(exc).__name__}: {exc}",
                    "Provide a Workflow-like object with a finite blocks tuple.",
                )
            )
            blocks = ()
        if not blocks:
            findings.append(
                _finding(
                    "error",
                    "workflow_without_blocks",
                    "workflow has no function blocks",
                    "Add at least one named FunctionBlock before running Explorer.",
                )
            )
        for index, block in enumerate(blocks):
            explicit_name = getattr(block, "name", "")
            if not explicit_name:
                findings.append(
                    _finding(
                        "warning",
                        "missing_metadata",
                        f"block at index {index} has no explicit name",
                        "Set block.name so counterexamples and reports are stable.",
                        {"block_index": index, "derived_name": block_name(block)},
                    )
                )
            for field_name in ("reads", "writes"):
                if not hasattr(block, field_name):
                    findings.append(
                        _finding(
                            "warning",
                            "missing_metadata",
                            f"block {block_name(block)!r} does not declare {field_name}",
                            "Declare reads/writes to make state ownership reviewable.",
                            {"block_index": index, "block_name": block_name(block), "field": field_name},
                        )
                    )

    repeated_risks = {
        "deduplication",
        "idempotency",
        "retry",
        "side_effect",
        "side_effects",
        "repeated_input",
    }
    if risks.intersection(repeated_risks):
        if max_sequence_length is None:
            findings.append(
                _finding(
                    "warning",
                    "missing_repeated_input",
                    "max_sequence_length was not provided for a repeated-input risk",
                    "Use max_sequence_length >= 2 when duplicates, retries, or side effects matter.",
                    {"risk_classes": tuple(sorted(risks))},
                )
            )
        elif max_sequence_length < 2:
            findings.append(
                _finding(
                    "warning",
                    "missing_repeated_input",
                    f"max_sequence_length={max_sequence_length} cannot explore repeated inputs",
                    "Use max_sequence_length >= 2 for deduplication, idempotency, retry, or side-effect risks.",
                    {"max_sequence_length": max_sequence_length, "risk_classes": tuple(sorted(risks))},
                )
            )
        if inputs_tuple is not None and len(inputs_tuple) <= 1 and max_sequence_length == 1:
            findings.append(
                _finding(
                    "warning",
                    "missing_repeated_input",
                    "only one external input and sequence length 1 leaves repeated-input behavior untested",
                    "Explore the same input twice or add a generated repeated-input scenario.",
                    {"external_input_count": len(inputs_tuple), "max_sequence_length": max_sequence_length},
                )
            )

    if inputs_tuple is None:
        findings.append(
            _finding(
                "suggestion",
                "missing_metadata",
                "external_inputs were not provided to audit_model",
                "Pass external_inputs=... to let the audit reason about input coverage.",
            )
        )

    if invariants_tuple is None or not invariants_tuple:
        findings.append(
            _finding(
                "warning",
                "missing_invariant",
                "no invariants were provided",
                "Add at least one invariant for the hard property the model is meant to protect.",
            )
        )
        invariant_pool: tuple[Any, ...] = ()
    else:
        invariant_pool = invariants_tuple

    if "cache" in risks and not _has_invariant_evidence(
        invariant_pool,
        property_classes=("cache", "cache_consistency", "source_consistency", "source_of_truth"),
        keywords=("cache", "source", "consistency", "matches_source", "source_of_truth"),
    ):
        findings.append(
            _finding(
                "warning",
                "missing_invariant",
                "cache risk is declared but no cache/source consistency invariant is apparent",
                "Add a cache consistency invariant, for example cache_matches_source(...).",
                {"risk_classes": tuple(sorted(risks))},
            )
        )

    if risks.intersection({"side_effect", "side_effects", "deduplication", "idempotency"}) and not _has_invariant_evidence(
        invariant_pool,
        property_classes=(
            "deduplication",
            "idempotency",
            "at_most_once",
            "side_effect",
            "side_effects",
            "uniqueness",
        ),
        keywords=("duplicate", "idempot", "at_most_once", "at most once", "once", "repeated", "side_effect"),
    ):
        findings.append(
            _finding(
                "warning",
                "missing_invariant",
                "side-effect or deduplication risk is declared but no duplicate/idempotency invariant is apparent",
                "Add no_duplicate_by(...), at_most_once_by(...), or an equivalent domain invariant.",
                {"risk_classes": tuple(sorted(risks))},
            )
        )

    scenario_risks = {
        "cache",
        "deduplication",
        "idempotency",
        "retry",
        "side_effect",
        "side_effects",
        "queue",
        "loop",
        "waiting",
    }
    if scenarios_tuple is None or not scenarios_tuple:
        severity = "warning" if risks.intersection(scenario_risks) else "suggestion"
        findings.append(
            _finding(
                severity,
                "missing_scenario",
                "no scenarios were provided to the model quality audit",
                "Use exact scenarios or ScenarioMatrixBuilder for high-value repeated-input cases.",
                {"risk_classes": tuple(sorted(risks))},
            )
        )

    if risks.intersection({"retry", "queue", "loop", "waiting"}) and progress_config is None:
        findings.append(
            _finding(
                "warning",
                "missing_progress_check",
                "retry/queue/loop/waiting risk is declared but no progress_config or progress check record was provided",
                "Run check_progress or record why progress review was skipped.",
                {"risk_classes": tuple(sorted(risks))},
            )
        )

    if risks.intersection({"module_boundary", "contract", "refinement", "ownership"}) and not contracts_tuple:
        findings.append(
            _finding(
                "warning",
                "missing_contract",
                "module-boundary risk is declared but no contracts were provided",
                "Use FunctionContract checks when ownership, forbidden writes, or projection refinement matter.",
                {"risk_classes": tuple(sorted(risks))},
            )
        )

    normalized_conformance = str(conformance_status or "").strip().lower()
    production_confidence_goal = (
        profile is not None and profile.confidence_goal == "production_conformance"
    )
    declared_conformance_risk = "conformance" in risks
    needs_production_confidence = production_confidence_goal or declared_conformance_risk
    if production_confidence_goal:
        conformance_gap_reason = "production confidence goal"
    elif declared_conformance_risk:
        conformance_gap_reason = "declared conformance risk"
    else:
        conformance_gap_reason = ""
    if normalized_conformance in {"not_run", "skipped", "skipped_with_reason"}:
        findings.append(
            _finding(
                "warning",
                "missing_conformance",
                (
                    f"production conformance is {normalized_conformance} for {conformance_gap_reason}; "
                    "skipped is not pass"
                    if needs_production_confidence
                    else f"production conformance is {normalized_conformance}; skipped is not pass"
                ),
                "Record the skip reason and avoid reporting model confidence as production confidence.",
                {"conformance_status": normalized_conformance},
            )
        )
    elif normalized_conformance in {"blocked", "not_feasible"}:
        findings.append(
            _finding(
                "warning",
                "missing_conformance",
                f"production conformance is {normalized_conformance}; skipped is not pass",
                "Keep the blocked/not-feasible status visible and avoid production-confidence claims.",
                {"conformance_status": normalized_conformance},
            )
        )
    elif conformance_config is None and conformance_status is None:
        severity = "warning" if needs_production_confidence else "suggestion"
        findings.append(
            _finding(
                severity,
                "missing_conformance",
                (
                    f"production conformance status was not provided for {conformance_gap_reason}"
                    if needs_production_confidence
                    else "production conformance status was not provided"
                ),
                "When production code exists and replay is feasible, run conformance replay or record why it was skipped.",
                {"confidence_goal": profile.confidence_goal if profile is not None else None},
            )
        )

    for skipped in skipped_tuple:
        findings.append(
            _finding(
                "warning",
                "skipped_step",
                f"skipped step recorded: {skipped}; skipped is not pass",
                "Keep skipped checks visible as confidence gaps rather than successful checks.",
                {"skipped_step": skipped},
            )
        )
    for skipped in profile_skipped:
        findings.append(
            _finding(
                "warning",
                "skipped_step",
                f"skipped check recorded: {skipped.name} ({skipped.status}); skipped is not pass",
                skipped.reason or "Record why this check was skipped.",
                skipped.to_dict(),
            )
        )

    ok, status = _status_for_findings(findings)
    return ModelQualityAuditReport(
        ok=ok,
        status=status,
        findings=tuple(findings),
        summary=_summary_for_findings(findings),
    )


def _coerce_risk_profile(value: RiskProfile | dict[str, Any] | None) -> RiskProfile | None:
    if value is None or isinstance(value, RiskProfile):
        return value
    if isinstance(value, dict):
        return RiskProfile.from_dict(value)
    raise TypeError("risk_profile must be a RiskProfile, dict, or None")


__all__ = [
    "AUDIT_STATUSES",
    "FINDING_SEVERITIES",
    "ModelQualityAuditReport",
    "ModelQualityFinding",
    "audit_model",
]
