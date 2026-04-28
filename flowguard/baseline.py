"""Evidence baseline scorecards for upgrade readiness reviews."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable


ACCEPTED_STATUSES = frozenset(
    {
        "pass",
        "expected_violation_observed",
        "needs_human_review",
        "known_limitation",
    }
)
FAILURE_STATUSES = frozenset(
    {
        "unexpected_violation",
        "missing_expected_violation",
        "oracle_mismatch",
        "failed",
    }
)


@dataclass(frozen=True)
class EvidenceCaseResult:
    """One expected-vs-observed baseline case."""

    name: str
    group: str
    bug_class: str
    expected: str
    observed: str
    status: str
    evidence: tuple[str, ...] = ()
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "group", str(self.group))
        object.__setattr__(self, "bug_class", str(self.bug_class))
        object.__setattr__(self, "expected", str(self.expected))
        object.__setattr__(self, "observed", str(self.observed))
        object.__setattr__(self, "status", str(self.status).lower())
        object.__setattr__(self, "evidence", tuple(str(item) for item in self.evidence))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def ok(self) -> bool:
        return self.status in ACCEPTED_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "group": self.group,
            "bug_class": self.bug_class,
            "expected": self.expected,
            "observed": self.observed,
            "status": self.status,
            "evidence": list(self.evidence),
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class EvidenceBaselineReport:
    """Aggregate evidence baseline for deciding whether an upgrade helped."""

    ok: bool
    total_cases: int
    target_cases: int
    meets_target: bool
    status_counts: tuple[tuple[str, int], ...]
    group_counts: tuple[tuple[str, int], ...]
    bug_class_counts: tuple[tuple[str, int], ...]
    results: tuple[EvidenceCaseResult, ...]
    summary: str = ""

    @property
    def failed_cases(self) -> tuple[EvidenceCaseResult, ...]:
        return tuple(result for result in self.results if result.status in FAILURE_STATUSES)

    def count_status(self, status: str) -> int:
        counts = dict(self.status_counts)
        return int(counts.get(status, 0))

    def count_group(self, group: str) -> int:
        counts = dict(self.group_counts)
        return int(counts.get(group, 0))

    def count_bug_class(self, bug_class: str) -> int:
        counts = dict(self.bug_class_counts)
        return int(counts.get(bug_class, 0))

    def format_text(self, max_failures: int = 5) -> str:
        lines = [
            "=== flowguard evidence baseline ===",
            "",
            f"status: {'OK' if self.ok else 'MISMATCH'}",
            f"total_cases: {self.total_cases}",
            f"target_cases: {self.target_cases}",
            f"meets_target: {self.meets_target}",
        ]
        if self.summary:
            lines.append(f"summary: {self.summary}")

        lines.extend(["", "Status counts:"])
        for status, count in self.status_counts:
            lines.append(f"  - {status}: {count}")

        lines.extend(["", "Group counts:"])
        for group, count in self.group_counts:
            lines.append(f"  - {group}: {count}")

        lines.extend(["", "Bug-class counts:"])
        for bug_class, count in self.bug_class_counts:
            lines.append(f"  - {bug_class}: {count}")

        failures = self.failed_cases
        if failures:
            lines.extend(["", "Failures:"])
            for result in failures[:max_failures]:
                lines.extend(
                    [
                        f"  - {result.name}",
                        f"    expected: {result.expected}",
                        f"    observed: {result.observed}",
                        f"    status: {result.status}",
                    ]
                )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total_cases": self.total_cases,
            "target_cases": self.target_cases,
            "meets_target": self.meets_target,
            "summary": self.summary,
            "status_counts": dict(self.status_counts),
            "group_counts": dict(self.group_counts),
            "bug_class_counts": dict(self.bug_class_counts),
            "results": [result.to_dict() for result in self.results],
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


def _sorted_counts(values: Iterable[str]) -> tuple[tuple[str, int], ...]:
    counts = Counter(values)
    return tuple(sorted(counts.items(), key=lambda item: item[0]))


def build_evidence_baseline_report(
    results: Iterable[EvidenceCaseResult],
    *,
    target_cases: int = 100,
    summary: str = "",
) -> EvidenceBaselineReport:
    """Build a deterministic scorecard from evidence cases."""

    normalized = tuple(results)
    total_cases = len(normalized)
    meets_target = total_cases >= target_cases
    status_counts = _sorted_counts(result.status for result in normalized)
    group_counts = _sorted_counts(result.group for result in normalized)
    bug_class_counts = _sorted_counts(result.bug_class for result in normalized)
    has_failures = any(result.status in FAILURE_STATUSES for result in normalized)
    ok = meets_target and not has_failures
    return EvidenceBaselineReport(
        ok=ok,
        total_cases=total_cases,
        target_cases=target_cases,
        meets_target=meets_target,
        status_counts=status_counts,
        group_counts=group_counts,
        bug_class_counts=bug_class_counts,
        results=normalized,
        summary=summary,
    )


__all__ = [
    "ACCEPTED_STATUSES",
    "FAILURE_STATUSES",
    "EvidenceBaselineReport",
    "EvidenceCaseResult",
    "build_evidence_baseline_report",
]
