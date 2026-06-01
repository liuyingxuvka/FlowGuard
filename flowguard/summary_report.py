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

LEDGER_SEVERITIES = (
    "failure",
    "blocker",
    "coverage_gap",
    "confidence_gap",
    "human_review",
    "info",
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
class FlowGuardFindingLedgerEntry:
    """One flattened finding from a summary section."""

    section_name: str
    section_status: str
    severity: str
    category: str
    message: str
    finding_index: int | None = None
    section_summary: str = ""
    next_step: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        severity = str(self.severity).lower()
        if severity not in LEDGER_SEVERITIES:
            raise ValueError(f"severity must be one of {LEDGER_SEVERITIES!r}")
        status = str(self.section_status).lower()
        if status not in SECTION_STATUSES:
            raise ValueError(f"section_status must be one of {SECTION_STATUSES!r}")
        object.__setattr__(self, "section_name", str(self.section_name))
        object.__setattr__(self, "section_status", status)
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "category", str(self.category))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "section_summary", str(self.section_summary or ""))
        object.__setattr__(self, "next_step", str(self.next_step or ""))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_name": self.section_name,
            "section_status": self.section_status,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "finding_index": self.finding_index,
            "section_summary": self.section_summary,
            "next_step": self.next_step,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class FlowGuardFindingLedger:
    """Coverage-first ledger for choosing the next repair path."""

    entries: tuple[FlowGuardFindingLedgerEntry, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        entries = tuple(self.entries)
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "summary", self.summary or _ledger_summary(entries))

    def by_severity(self, severity: str) -> tuple[FlowGuardFindingLedgerEntry, ...]:
        value = str(severity).lower()
        return tuple(entry for entry in self.entries if entry.severity == value)

    def format_text(self, max_entries: int = 12) -> str:
        lines = [
            "=== flowguard finding ledger ===",
            self.summary,
        ]
        for entry in self.entries[:max_entries]:
            lines.append(
                f"- {entry.severity}: {entry.section_name}: "
                f"{entry.category}: {entry.message}"
            )
        if len(self.entries) > max_entries:
            lines.append(f"- ... {len(self.entries) - max_entries} more")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


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

    @property
    def finding_ledger(self) -> FlowGuardFindingLedger:
        """Return a flattened coverage-first ledger for all section findings."""

        return build_finding_ledger(self.sections)

    def format_text(self, verbose: bool = False) -> str:
        lines = [
            "=== flowguard summary ===",
            f"overall_status: {self.overall_status}",
        ]
        if self.summary:
            lines.append(f"summary: {self.summary}")
        ledger = self.finding_ledger
        if ledger.entries:
            lines.append(f"finding_ledger: {ledger.summary}")
        for section in self.sections:
            suffix = f" - {section.summary}" if section.summary else ""
            lines.append(f"- {section.name}: {section.status}{suffix}")
            if (verbose or _section_always_shows_findings(section)) and section.findings:
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
            "finding_ledger": self.finding_ledger.to_dict(),
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


def _section_always_shows_findings(section: FlowGuardSection) -> bool:
    return section.name == "assumption_card" or (
        ("always_show_findings", True) in section.metadata
    )


def _ledger_summary(entries: tuple[FlowGuardFindingLedgerEntry, ...]) -> str:
    counts = {severity: 0 for severity in LEDGER_SEVERITIES}
    for entry in entries:
        counts[entry.severity] += 1
    nonzero = tuple(f"{severity}={count}" for severity, count in counts.items() if count)
    return f"entries={len(entries)} " + " ".join(nonzero) if entries else "entries=0"


def _ledger_severity(section: FlowGuardSection) -> str:
    if section.status == "failed":
        return "failure"
    if section.status == "blocked":
        return "blocker"
    if section.status in {"not_run", "skipped_with_reason"}:
        return "coverage_gap"
    if section.status == "needs_human_review":
        return "human_review"
    if section.status == "pass_with_gaps":
        return "confidence_gap"
    return "info"


def _ledger_category(section: FlowGuardSection, message: str) -> str:
    text = f"{section.name} {section.status} {message}".lower()
    if "needs_human_review" in text or section.status == "needs_human_review":
        return "human_review"
    if "missing_conformance" in text or "conformance" in text and "not provided" in text:
        return "conformance_gap"
    if section.status in {"not_run", "skipped_with_reason"} or "not_run" in text or "skipped" in text:
        return "missing_or_skipped_check"
    if section.status == "blocked":
        return "blocked_check"
    if "missing_invariant" in text or "missing_scenario" in text or "missing_progress" in text:
        return "model_coverage_gap"
    if "state_closure" in text or "topology_hazard" in text:
        return "model_coverage_gap"
    if section.status == "failed" or "violation" in text or "exception" in text:
        return "failure"
    if section.status == "pass_with_gaps":
        return "confidence_gap"
    return "finding"


def _ledger_next_step(section: FlowGuardSection, category: str) -> str:
    if section.status == "failed":
        return "Inspect the counterexample or violation, then decide whether to fix the real system, adjust the check flow, or extend the model."
    if category == "model_coverage_gap":
        return "Extend the model, invariant set, scenario oracle, or progress configuration before treating this as covered."
    if category == "conformance_gap":
        return "Run conformance replay or record why only model-level confidence is being claimed."
    if section.status in {"not_run", "skipped_with_reason", "blocked"}:
        return "Run the missing check when relevant, or keep the skip/blocker visible as a confidence gap."
    if section.status == "needs_human_review":
        return "Supply the missing policy expectation or oracle before promoting this to pass."
    if section.status == "pass_with_gaps":
        return "Review the confidence gap before treating the run as a clean pass."
    return "No action required unless this finding affects the current risk boundary."


def _format_ledger_message(finding: Any) -> str:
    if isinstance(finding, str):
        return finding
    return repr(finding)


def _ledger_entry(
    section: FlowGuardSection,
    message: str,
    finding_index: int | None,
) -> FlowGuardFindingLedgerEntry:
    category = _ledger_category(section, message)
    return FlowGuardFindingLedgerEntry(
        section_name=section.name,
        section_status=section.status,
        severity=_ledger_severity(section),
        category=category,
        message=message,
        finding_index=finding_index,
        section_summary=section.summary,
        next_step=_ledger_next_step(section, category),
    )


def build_finding_ledger(
    sections: Iterable[FlowGuardSection],
) -> FlowGuardFindingLedger:
    """Flatten section findings into a coverage-first repair ledger."""

    entries: list[FlowGuardFindingLedgerEntry] = []
    for section in tuple(sections):
        if section.findings:
            for index, finding in enumerate(section.findings, start=1):
                entries.append(_ledger_entry(section, _format_ledger_message(finding), index))
        elif section.status != "pass":
            message = section.summary or f"{section.name} reported {section.status}"
            entries.append(_ledger_entry(section, message, None))
    return FlowGuardFindingLedger(tuple(entries))


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
    "FlowGuardFindingLedger",
    "FlowGuardFindingLedgerEntry",
    "FlowGuardSummaryReport",
    "SECTION_STATUSES",
    "LEDGER_SEVERITIES",
    "build_finding_ledger",
    "build_flowguard_summary_report",
    "section_from_audit_report",
    "section_from_check_report",
    "section_from_ok_report",
    "section_from_scenario_report",
]
