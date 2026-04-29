"""Lightweight unified FlowGuard summary reports."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable


SECTION_STATUSES = (
    "pass",
    "pass_with_gaps",
    "failed",
    "not_run",
    "skipped_with_reason",
    "blocked",
    "needs_human_review",
)


@dataclass(frozen=True)
class FlowGuardSection:
    """One section in a unified FlowGuard summary."""

    name: str
    status: str
    summary: str = ""
    findings: tuple[Any, ...] = field(default_factory=tuple)
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        status = str(self.status).lower()
        if status not in SECTION_STATUSES:
            raise ValueError(f"status must be one of {SECTION_STATUSES!r}")
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "summary", str(self.summary or ""))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "findings": to_jsonable(self.findings),
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class FlowGuardSummaryReport:
    """Aggregate model, audit, scenario, progress, contract, and conformance status."""

    overall_status: str
    sections: tuple[FlowGuardSection, ...] = ()
    summary: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        status = str(self.overall_status).lower()
        if status not in SECTION_STATUSES:
            raise ValueError(f"overall_status must be one of {SECTION_STATUSES!r}")
        object.__setattr__(self, "overall_status", status)
        object.__setattr__(self, "sections", tuple(self.sections))
        object.__setattr__(self, "summary", str(self.summary or ""))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @classmethod
    def from_sections(
        cls,
        sections: Iterable[FlowGuardSection],
        summary: str = "",
        metadata: dict[str, Any] | Iterable[tuple[str, Any]] | None = None,
    ) -> "FlowGuardSummaryReport":
        sections_tuple = tuple(sections)
        return cls(
            overall_status=_overall_status(sections_tuple),
            sections=sections_tuple,
            summary=summary or _summary_for_sections(sections_tuple),
            metadata=metadata,
        )

    def format_text(self, verbose: bool = False) -> str:
        lines = [
            "=== flowguard summary ===",
            f"overall_status: {self.overall_status}",
        ]
        if self.summary:
            lines.append(f"summary: {self.summary}")
        for section in self.sections:
            suffix = f" - {section.summary}" if section.summary else ""
            lines.append(f"- {section.name}: {section.status}{suffix}")
            if verbose and section.findings:
                for finding in section.findings:
                    lines.append(f"  - {finding}")
            elif section.findings and section.status != "pass":
                lines.append(f"  findings: {len(section.findings)}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "summary": self.summary,
            "sections": [section.to_dict() for section in self.sections],
            "metadata": to_jsonable(self.metadata),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def _overall_status(sections: tuple[FlowGuardSection, ...]) -> str:
    if not sections:
        return "not_run"
    statuses = {section.status for section in sections}
    if "failed" in statuses:
        return "failed"
    if "blocked" in statuses:
        return "blocked"
    if statuses == {"pass"}:
        return "pass"
    if statuses == {"needs_human_review"}:
        return "needs_human_review"
    return "pass_with_gaps"


def _summary_for_sections(sections: tuple[FlowGuardSection, ...]) -> str:
    counts = {status: 0 for status in SECTION_STATUSES}
    for section in sections:
        counts[section.status] += 1
    nonzero = tuple(f"{status}={count}" for status, count in counts.items() if count)
    return " ".join(nonzero) if nonzero else "no sections"


def _check_report_findings(report: Any) -> tuple[str, ...]:
    findings: list[str] = []
    for violation in getattr(report, "violations", ()):
        findings.append(
            f"invariant {getattr(violation, 'invariant_name', '(unknown)')}: "
            f"{getattr(violation, 'message', '')}"
        )
    for dead in getattr(report, "dead_branches", ()):
        findings.append(
            f"dead_branch {getattr(dead, 'function_name', '(workflow)')}: "
            f"{getattr(dead, 'reason', '')}"
        )
    for exc in getattr(report, "exception_branches", ()):
        findings.append(
            f"exception {getattr(exc, 'error_type', 'Exception')} in "
            f"{getattr(exc, 'function_name', '(workflow)')}: {getattr(exc, 'message', '')}"
        )
    for failure in getattr(report, "reachability_failures", ()):
        findings.append(
            f"reachability {getattr(failure, 'name', '(unknown)')}: "
            f"{getattr(failure, 'message', '') or getattr(failure, 'description', '')}"
        )
    return tuple(findings)


def section_from_check_report(
    report: Any,
    *,
    name: str = "model_check",
) -> FlowGuardSection:
    """Build a section from an Explorer CheckReport-like object."""

    findings = _check_report_findings(report)
    return FlowGuardSection(
        name=name,
        status="pass" if getattr(report, "ok", False) else "failed",
        summary=getattr(report, "summary", ""),
        findings=findings,
        metadata={"report": report},
    )


def section_from_audit_report(report: Any, *, name: str = "model_quality_audit") -> FlowGuardSection:
    """Build a section from a ModelQualityAuditReport-like object."""

    findings = tuple(
        f"{getattr(finding, 'severity', '')}: {getattr(finding, 'category', '')}: "
        f"{getattr(finding, 'message', '')}"
        for finding in getattr(report, "findings", ())
    )
    return FlowGuardSection(
        name=name,
        status=getattr(report, "status", "not_run"),
        summary=getattr(report, "summary", ""),
        findings=findings,
        metadata={"report": report},
    )


def section_from_scenario_report(report: Any, *, name: str = "scenario_review") -> FlowGuardSection:
    """Build a section from a ScenarioReviewReport-like object."""

    if not getattr(report, "ok", False):
        status = "failed"
    elif getattr(report, "needs_human_review", 0) or getattr(report, "known_limitations", 0):
        status = "pass_with_gaps"
    else:
        status = "pass"
    findings = tuple(
        f"{getattr(result, 'scenario_name', '(unknown)')}: {getattr(result, 'status', '')}"
        for result in getattr(report, "results", ())
        if getattr(result, "status", "pass") != "pass"
    )
    summary = (
        f"total={getattr(report, 'total_scenarios', 0)} "
        f"passed={getattr(report, 'passed', 0)} "
        f"needs_human_review={getattr(report, 'needs_human_review', 0)}"
    )
    return FlowGuardSection(
        name=name,
        status=status,
        summary=summary,
        findings=findings,
        metadata={"report": report},
    )


def section_from_ok_report(report: Any, *, name: str, summary: str = "") -> FlowGuardSection:
    """Build a generic section from a report with an `ok` attribute."""

    return FlowGuardSection(
        name=name,
        status="pass" if getattr(report, "ok", False) else "failed",
        summary=summary or getattr(report, "summary", ""),
        findings=_generic_report_findings(report),
        metadata={"report": report},
    )


def _generic_report_findings(report: Any) -> tuple[str, ...]:
    raw_findings = tuple(getattr(report, "findings", ()) or ())
    if raw_findings:
        return tuple(_format_generic_finding(finding) for finding in raw_findings)
    raw_violations = tuple(getattr(report, "violations", ()) or ())
    return tuple(_format_generic_finding(violation) for violation in raw_violations)


def _format_generic_finding(finding: Any) -> str:
    name = getattr(finding, "name", None) or getattr(finding, "rule_name", None)
    message = getattr(finding, "message", None)
    if name and message:
        return f"{name}: {message}"
    if message:
        return str(message)
    return repr(finding)


def build_flowguard_summary_report(
    *,
    model_check_report: Any = None,
    audit_report: Any = None,
    scenario_report: Any = None,
    progress_report: Any = None,
    contract_report: Any = None,
    conformance_report: Any = None,
    sections: Iterable[FlowGuardSection] = (),
    not_run_sections: Iterable[str] = (),
) -> FlowGuardSummaryReport:
    """Build a unified helper report from optional FlowGuard reports."""

    collected: list[FlowGuardSection] = list(sections)
    if model_check_report is not None:
        collected.append(section_from_check_report(model_check_report))
    if audit_report is not None:
        collected.append(section_from_audit_report(audit_report))
    if scenario_report is not None:
        collected.append(section_from_scenario_report(scenario_report))
    if progress_report is not None:
        collected.append(section_from_ok_report(progress_report, name="progress_check"))
    if contract_report is not None:
        collected.append(section_from_ok_report(contract_report, name="contract_check"))
    if conformance_report is not None:
        collected.append(section_from_ok_report(conformance_report, name="conformance_replay"))
    for section_name in not_run_sections:
        collected.append(
            FlowGuardSection(
                name=str(section_name),
                status="not_run",
                summary="not provided or not run",
                findings=("not_run is a confidence gap, not a failure",),
                metadata={"not_run": True},
            )
        )
    return FlowGuardSummaryReport.from_sections(collected)


__all__ = [
    "FlowGuardSection",
    "FlowGuardSummaryReport",
    "SECTION_STATUSES",
    "build_flowguard_summary_report",
    "section_from_audit_report",
    "section_from_check_report",
    "section_from_ok_report",
    "section_from_scenario_report",
]
