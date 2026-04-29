"""Priority-family scenario seed reports for the problem corpus benchmark."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from flowguard.export import to_jsonable

from .real_models import classify_failure_mode, review_real_model_corpus


PRIORITY_SCENARIO_FAMILIES = (
    "task_queue_leasing",
    "retry_side_effect",
    "cache_materialized_view",
    "file_import_transform_export",
    "event_webhook_ingestion",
    "payment_billing_refund",
)


@dataclass(frozen=True)
class FamilyScenarioSeedResult:
    family: str
    total_cases: int
    pass_cases: int
    expected_violations_observed: int
    failure_cases: int
    case_kinds: tuple[str, ...]
    bug_classes: tuple[str, ...]
    variant_count: int

    @property
    def ok(self) -> bool:
        return (
            self.total_cases > 0
            and self.pass_cases > 0
            and self.expected_violations_observed > 0
            and self.failure_cases == 0
            and len(self.case_kinds) >= 5
            and len(self.bug_classes) >= 8
            and self.variant_count == 6
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "total_cases": self.total_cases,
            "pass_cases": self.pass_cases,
            "expected_violations_observed": self.expected_violations_observed,
            "failure_cases": self.failure_cases,
            "case_kinds": list(self.case_kinds),
            "bug_classes": list(self.bug_classes),
            "variant_count": self.variant_count,
            "ok": self.ok,
        }


@dataclass(frozen=True)
class FamilyScenarioSeedReport:
    ok: bool
    priority_family_count: int
    results: tuple[FamilyScenarioSeedResult, ...]
    summary: str = ""

    def format_text(self) -> str:
        lines = [
            "=== flowguard priority-family scenario seeds ===",
            "",
            f"status: {'OK' if self.ok else 'GAP'}",
            f"priority_family_count: {self.priority_family_count}",
        ]
        if self.summary:
            lines.append(f"summary: {self.summary}")
        lines.extend(["", "Families:"])
        for result in self.results:
            lines.append(
                "  - "
                f"{result.family}: total={result.total_cases}, "
                f"pass={result.pass_cases}, "
                f"expected_violations={result.expected_violations_observed}, "
                f"variants={result.variant_count}, "
                f"bug_classes={len(result.bug_classes)}, "
                f"status={'OK' if result.ok else 'GAP'}"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "priority_family_count": self.priority_family_count,
            "results": [result.to_dict() for result in self.results],
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


def review_priority_family_scenarios(
    families: tuple[str, ...] = PRIORITY_SCENARIO_FAMILIES,
) -> FamilyScenarioSeedReport:
    """Summarize non-job-matching scenario pressure for priority families."""

    executable_report = review_real_model_corpus()
    by_family: dict[str, list] = defaultdict(list)
    for result in executable_report.results:
        if result.workflow_family in families:
            by_family[result.workflow_family].append(result)

    seed_results: list[FamilyScenarioSeedResult] = []
    for family in families:
        results = by_family.get(family, [])
        statuses = Counter(result.status for result in results)
        variants = {
            dict(result.metadata).get("variant_id", "")
            for result in results
            if dict(result.metadata).get("variant_id", "")
        }
        bug_classes = {
            dict(result.metadata).get("bug_class", classify_failure_mode(result.failure_mode))
            for result in results
        }
        seed_results.append(
            FamilyScenarioSeedResult(
                family=family,
                total_cases=len(results),
                pass_cases=statuses.get("pass", 0),
                expected_violations_observed=statuses.get("expected_violation_observed", 0),
                failure_cases=sum(
                    statuses.get(name, 0)
                    for name in (
                        "unexpected_violation",
                        "missing_expected_violation",
                        "oracle_mismatch",
                        "failed",
                        "not_executable_yet",
                    )
                ),
                case_kinds=tuple(sorted({result.case_kind for result in results})),
                bug_classes=tuple(sorted(bug_classes)),
                variant_count=len(variants),
            )
        )

    return FamilyScenarioSeedReport(
        ok=all(result.ok for result in seed_results) and len(seed_results) == len(families),
        priority_family_count=len(seed_results),
        results=tuple(seed_results),
        summary=(
            "Phase 11.2 priority-family scenario seeds: high-value "
            "non-job-matching workflow families must carry their own scenario evidence."
        ),
    )


__all__ = [
    "FamilyScenarioSeedReport",
    "FamilyScenarioSeedResult",
    "PRIORITY_SCENARIO_FAMILIES",
    "review_priority_family_scenarios",
]
