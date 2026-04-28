"""Structured reports for executable corpus reviews."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable
from .trace import Trace


@dataclass(frozen=True)
class ExecutableCaseResult:
    """Expected-vs-observed result for one executable problem case."""

    case_id: str
    title: str
    case_kind: str
    workflow_family: str
    failure_mode: str
    oracle_type: str
    expected_status: str
    expected_violation_names: tuple[str, ...]
    observed_status: str
    observed_violation_names: tuple[str, ...]
    status: str
    execution_kind: str
    mapped_checker: str
    evidence: tuple[str, ...]
    counterexample_trace: Trace | None = None
    graph_evidence: Any = None
    not_executable_reason: str = ""
    limitation_reason: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "title", str(self.title))
        object.__setattr__(self, "case_kind", str(self.case_kind))
        object.__setattr__(self, "workflow_family", str(self.workflow_family))
        object.__setattr__(self, "failure_mode", str(self.failure_mode))
        object.__setattr__(self, "oracle_type", str(self.oracle_type))
        object.__setattr__(self, "expected_status", str(self.expected_status))
        object.__setattr__(
            self,
            "expected_violation_names",
            tuple(str(item) for item in self.expected_violation_names),
        )
        object.__setattr__(self, "observed_status", str(self.observed_status))
        object.__setattr__(
            self,
            "observed_violation_names",
            tuple(str(item) for item in self.observed_violation_names),
        )
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "execution_kind", str(self.execution_kind))
        object.__setattr__(self, "mapped_checker", str(self.mapped_checker))
        object.__setattr__(self, "evidence", tuple(str(item) for item in self.evidence))
        object.__setattr__(self, "not_executable_reason", str(self.not_executable_reason))
        object.__setattr__(self, "limitation_reason", str(self.limitation_reason))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def executable(self) -> bool:
        return self.status != "not_executable_yet"

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "case_kind": self.case_kind,
            "workflow_family": self.workflow_family,
            "failure_mode": self.failure_mode,
            "oracle_type": self.oracle_type,
            "expected_status": self.expected_status,
            "expected_violation_names": list(self.expected_violation_names),
            "observed_status": self.observed_status,
            "observed_violation_names": list(self.observed_violation_names),
            "status": self.status,
            "execution_kind": self.execution_kind,
            "mapped_checker": self.mapped_checker,
            "evidence": list(self.evidence),
            "counterexample_trace": (
                self.counterexample_trace.to_dict()
                if self.counterexample_trace is not None
                else None
            ),
            "graph_evidence": to_jsonable(self.graph_evidence),
            "not_executable_reason": self.not_executable_reason,
            "limitation_reason": self.limitation_reason,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class ExecutableCorpusReport:
    """Aggregate report for executable corpus review."""

    ok: bool
    total_cases: int
    executable_cases: int
    not_executable_yet: int
    coverage_ratio: float
    coverage_complete: bool
    accepted_executable_cases: int
    strong_pass_cases: int
    expected_violations_observed: int
    failure_cases: int
    status_counts: tuple[tuple[str, int], ...]
    execution_kind_counts: tuple[tuple[str, int], ...]
    case_kind_counts: tuple[tuple[str, int], ...]
    workflow_family_counts: tuple[tuple[str, int], ...]
    failure_mode_counts: tuple[tuple[str, int], ...]
    oracle_type_counts: tuple[tuple[str, int], ...]
    case_source_counts: tuple[tuple[str, int], ...]
    gap_focus_counts: tuple[tuple[str, int], ...]
    pressure_focus_counts: tuple[tuple[str, int], ...]
    not_executable_reasons: tuple[tuple[str, int], ...]
    real_model_cases: int
    generic_fallback_cases: int
    model_variant_total: int
    model_families_with_six_variants: int
    model_binding_counts: tuple[tuple[str, int], ...]
    model_family_counts: tuple[tuple[str, int], ...]
    model_variant_counts: tuple[tuple[str, int], ...]
    results: tuple[ExecutableCaseResult, ...]
    summary: str = ""

    def count_status(self, status: str) -> int:
        return int(dict(self.status_counts).get(status, 0))

    def count_execution_kind(self, execution_kind: str) -> int:
        return int(dict(self.execution_kind_counts).get(execution_kind, 0))

    def count_case_source(self, case_source: str) -> int:
        return int(dict(self.case_source_counts).get(case_source, 0))

    def count_gap_focus(self, gap_focus: str) -> int:
        return int(dict(self.gap_focus_counts).get(gap_focus, 0))

    def count_pressure_focus(self, pressure_focus: str) -> int:
        return int(dict(self.pressure_focus_counts).get(pressure_focus, 0))

    def format_text(self, max_results: int = 8) -> str:
        lines = [
            "=== flowguard executable corpus review ===",
            "",
            f"status: {'OK' if self.ok else 'MISMATCH'}",
            f"total_cases: {self.total_cases}",
            f"executable_cases: {self.executable_cases}",
            f"not_executable_yet: {self.not_executable_yet}",
            f"coverage_ratio: {self.coverage_ratio:.3f}",
            f"coverage_complete: {self.coverage_complete}",
            f"accepted_executable_cases: {self.accepted_executable_cases}",
            f"strong_pass_cases: {self.strong_pass_cases}",
            f"expected_violations_observed: {self.expected_violations_observed}",
            f"failure_cases: {self.failure_cases}",
            f"real_model_cases: {self.real_model_cases}",
            f"generic_fallback_cases: {self.generic_fallback_cases}",
            f"model_variant_total: {self.model_variant_total}",
            f"model_families_with_six_variants: {self.model_families_with_six_variants}",
        ]
        if self.summary:
            lines.append(f"summary: {self.summary}")

        lines.extend(["", "Status counts:"])
        for name, count in self.status_counts:
            lines.append(f"  - {name}: {count}")

        lines.extend(["", "Execution kinds:"])
        for name, count in self.execution_kind_counts:
            lines.append(f"  - {name}: {count}")

        if self.not_executable_reasons:
            lines.extend(["", "Not executable reasons:"])
            for name, count in self.not_executable_reasons:
                lines.append(f"  - {name}: {count}")

        if self.model_binding_counts:
            lines.extend(["", "Model bindings:"])
            for name, count in self.model_binding_counts:
                lines.append(f"  - {name}: {count}")

        if self.model_family_counts:
            lines.extend(["", "Model families:"])
            for name, count in self.model_family_counts[:12]:
                lines.append(f"  - {name}: {count}")
            if len(self.model_family_counts) > 12:
                lines.append(f"  - ... {len(self.model_family_counts) - 12} more")

        if self.model_variant_counts:
            lines.extend(["", "Model variants:"])
            for name, count in self.model_variant_counts[:12]:
                lines.append(f"  - {name}: {count}")
            if len(self.model_variant_counts) > 12:
                lines.append(f"  - ... {len(self.model_variant_counts) - 12} more")

        lines.extend(["", "Case kinds:"])
        for name, count in self.case_kind_counts:
            lines.append(f"  - {name}: {count}")

        if self.case_source_counts:
            lines.extend(["", "Corpus sections:"])
            for name, count in self.case_source_counts:
                lines.append(f"  - {name}: {count}")

        if self.gap_focus_counts:
            lines.extend(["", "Gap focus areas:"])
            for name, count in self.gap_focus_counts:
                lines.append(f"  - {name}: {count}")

        if self.pressure_focus_counts:
            lines.extend(["", "Pressure focus areas:"])
            for name, count in self.pressure_focus_counts:
                lines.append(f"  - {name}: {count}")

        lines.extend(["", "Sample results:"])
        for result in self.results[:max_results]:
            lines.append(
                f"  - {result.case_id}: {result.status} "
                f"({result.execution_kind}; expected={result.expected_status}; observed={result.observed_status})"
            )
        return "\n".join(lines)

    def to_dict(self, include_results: bool = True) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total_cases": self.total_cases,
            "executable_cases": self.executable_cases,
            "not_executable_yet": self.not_executable_yet,
            "coverage_ratio": self.coverage_ratio,
            "coverage_complete": self.coverage_complete,
            "accepted_executable_cases": self.accepted_executable_cases,
            "strong_pass_cases": self.strong_pass_cases,
            "expected_violations_observed": self.expected_violations_observed,
            "failure_cases": self.failure_cases,
            "status_counts": dict(self.status_counts),
            "execution_kind_counts": dict(self.execution_kind_counts),
            "case_kind_counts": dict(self.case_kind_counts),
            "workflow_family_counts": dict(self.workflow_family_counts),
            "failure_mode_counts": dict(self.failure_mode_counts),
            "oracle_type_counts": dict(self.oracle_type_counts),
            "case_source_counts": dict(self.case_source_counts),
            "gap_focus_counts": dict(self.gap_focus_counts),
            "pressure_focus_counts": dict(self.pressure_focus_counts),
            "not_executable_reasons": dict(self.not_executable_reasons),
            "real_model_cases": self.real_model_cases,
            "generic_fallback_cases": self.generic_fallback_cases,
            "model_variant_total": self.model_variant_total,
            "model_families_with_six_variants": self.model_families_with_six_variants,
            "model_binding_counts": dict(self.model_binding_counts),
            "model_family_counts": dict(self.model_family_counts),
            "model_variant_counts": dict(self.model_variant_counts),
            "results": [result.to_dict() for result in self.results] if include_results else [],
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2, include_results: bool = True) -> str:
        return json.dumps(
            to_jsonable(self.to_dict(include_results=include_results)),
            indent=indent,
            sort_keys=True,
        )


def _sorted_counts(values: Iterable[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(Counter(values).items(), key=lambda item: item[0]))


def _metadata_value(result: ExecutableCaseResult, key: str, default: str = "") -> str:
    for item_key, value in result.metadata:
        if item_key == key:
            return str(value)
    return default


def build_executable_corpus_report(
    results: Iterable[ExecutableCaseResult],
    *,
    total_cases: int | None = None,
    summary: str = "",
) -> ExecutableCorpusReport:
    """Build an aggregate report from executable case results."""

    result_tuple = tuple(results)
    total = len(result_tuple) if total_cases is None else int(total_cases)
    executable_cases = sum(1 for result in result_tuple if result.executable)
    not_executable = sum(1 for result in result_tuple if not result.executable)
    accepted_statuses = {
        "pass",
        "expected_violation_observed",
        "known_limitation",
        "needs_human_review",
    }
    failure_statuses = {
        "unexpected_violation",
        "missing_expected_violation",
        "oracle_mismatch",
        "failed",
        "not_executable_yet",
    }
    accepted_executable_cases = sum(
        1 for result in result_tuple if result.executable and result.status in accepted_statuses
    )
    strong_pass_cases = sum(1 for result in result_tuple if result.status == "pass")
    expected_violations = sum(
        1 for result in result_tuple if result.status == "expected_violation_observed"
    )
    failure_cases = sum(1 for result in result_tuple if result.status in failure_statuses)
    coverage_ratio = executable_cases / total if total else 0.0
    coverage_complete = executable_cases == total and not_executable == 0
    model_bindings = tuple(
        _metadata_value(result, "model_binding_kind", "unspecified")
        for result in result_tuple
    )
    real_model_cases = sum(1 for binding in model_bindings if binding == "real_domain_model")
    generic_fallback_cases = sum(
        1
        for result, binding in zip(result_tuple, model_bindings)
        if binding in {"generic_template", "generic_fallback"}
        or _metadata_value(result, "generic_fallback", "false").lower() == "true"
        or result.mapped_checker in {"Workflow+ScenarioReview+Invariant", "LoopCheck"}
    )
    model_family_to_variants: dict[str, set[str]] = {}
    for result in result_tuple:
        family = _metadata_value(result, "model_family", result.workflow_family)
        variant_id = _metadata_value(result, "variant_id", _metadata_value(result, "model_variant", "unspecified"))
        model_family_to_variants.setdefault(family, set()).add(variant_id)
    model_variant_total = len(
        {
            (family, variant)
            for family, variants in model_family_to_variants.items()
            for variant in variants
            if variant and variant != "unspecified"
        }
    )
    model_families_with_six_variants = sum(
        1 for variants in model_family_to_variants.values() if len(variants) == 6
    )
    bad_statuses = {
        "unexpected_violation",
        "missing_expected_violation",
        "oracle_mismatch",
        "not_executable_yet",
    }
    ok = (
        len(result_tuple) == total
        and executable_cases == total
        and not_executable == 0
        and real_model_cases == total
        and generic_fallback_cases == 0
        and (not total or model_variant_total >= 150)
        and (not total or model_families_with_six_variants >= 25)
        and not any(result.status in bad_statuses for result in result_tuple)
    )
    return ExecutableCorpusReport(
        ok=ok,
        total_cases=total,
        executable_cases=executable_cases,
        not_executable_yet=not_executable,
        coverage_ratio=coverage_ratio,
        coverage_complete=coverage_complete,
        accepted_executable_cases=accepted_executable_cases,
        strong_pass_cases=strong_pass_cases,
        expected_violations_observed=expected_violations,
        failure_cases=failure_cases,
        status_counts=_sorted_counts(result.status for result in result_tuple),
        execution_kind_counts=_sorted_counts(result.execution_kind for result in result_tuple),
        case_kind_counts=_sorted_counts(result.case_kind for result in result_tuple),
        workflow_family_counts=_sorted_counts(result.workflow_family for result in result_tuple),
        failure_mode_counts=_sorted_counts(result.failure_mode for result in result_tuple),
        oracle_type_counts=_sorted_counts(result.oracle_type for result in result_tuple),
        case_source_counts=_sorted_counts(
            _metadata_value(result, "corpus_section", "unspecified")
            for result in result_tuple
        ),
        gap_focus_counts=_sorted_counts(
            focus
            for focus in (_metadata_value(result, "gap_focus_area") for result in result_tuple)
            if focus
        ),
        pressure_focus_counts=_sorted_counts(
            focus
            for focus in (_metadata_value(result, "pressure_focus_area") for result in result_tuple)
            if focus
        ),
        not_executable_reasons=_sorted_counts(
            result.not_executable_reason
            for result in result_tuple
            if result.status == "not_executable_yet"
        ),
        real_model_cases=real_model_cases,
        generic_fallback_cases=generic_fallback_cases,
        model_variant_total=model_variant_total,
        model_families_with_six_variants=model_families_with_six_variants,
        model_binding_counts=_sorted_counts(model_bindings),
        model_family_counts=_sorted_counts(
            _metadata_value(result, "model_family", result.workflow_family)
            for result in result_tuple
        ),
        model_variant_counts=_sorted_counts(
            _metadata_value(result, "variant_id", _metadata_value(result, "model_variant", "unspecified"))
            for result in result_tuple
        ),
        results=result_tuple,
        summary=summary,
    )


__all__ = [
    "ExecutableCaseResult",
    "ExecutableCorpusReport",
    "build_executable_corpus_report",
]
