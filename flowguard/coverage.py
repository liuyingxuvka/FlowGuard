"""Coverage audits for durable executable benchmark baselines."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from .executable import ExecutableCaseResult, ExecutableCorpusReport
from .export import to_jsonable


DEFAULT_REQUIRED_CASE_KINDS = (
    "positive_correct_case",
    "negative_broken_case",
    "boundary_edge_case",
    "invalid_initial_state_case",
    "loop_or_stuck_case",
)


DEFAULT_REQUIRED_BUG_CLASSES = (
    "duplicate_side_effect",
    "repeated_processing_without_refresh",
    "cache_source_mismatch",
    "missing_source_traceability",
    "wrong_state_owner",
    "missing_decision",
    "contradictory_decision",
    "duplicate_decision",
    "lease_violation",
    "downstream_non_consumable",
    "invalid_transition",
)


@dataclass(frozen=True)
class BenchmarkCoverageAudit:
    """Structured depth and family-coverage audit for executable benchmarks."""

    ok: bool
    total_cases: int
    variant_target: int
    variant_total: int
    variant_min_cases: int
    variant_max_cases: int
    variants_below_target: tuple[tuple[str, int], ...]
    required_case_kinds: tuple[str, ...]
    families_missing_required_case_kinds: tuple[tuple[str, tuple[str, ...]], ...]
    required_bug_classes: tuple[str, ...]
    families_missing_required_bug_classes: tuple[tuple[str, tuple[str, ...]], ...]
    family_case_kind_matrix: tuple[tuple[str, tuple[str, ...]], ...]
    family_bug_class_matrix: tuple[tuple[str, tuple[str, ...]], ...]
    single_family_dominance_ratio: float
    job_matching_case_count: int
    job_matching_dominance_ratio: float
    production_conformance_family_count: int = 0
    production_conformance_families: tuple[str, ...] = ()
    summary: str = ""

    def format_text(self, max_rows: int = 12) -> str:
        lines = [
            "=== flowguard benchmark coverage audit ===",
            "",
            f"status: {'OK' if self.ok else 'GAP'}",
            f"total_cases: {self.total_cases}",
            f"variant_target: {self.variant_target}",
            f"variant_total: {self.variant_total}",
            f"variant_min_cases: {self.variant_min_cases}",
            f"variant_max_cases: {self.variant_max_cases}",
            f"variants_below_target: {len(self.variants_below_target)}",
            f"families_missing_required_case_kinds: {len(self.families_missing_required_case_kinds)}",
            f"families_missing_required_bug_classes: {len(self.families_missing_required_bug_classes)}",
            f"single_family_dominance_ratio: {self.single_family_dominance_ratio:.3f}",
            f"job_matching_case_count: {self.job_matching_case_count}",
            f"job_matching_dominance_ratio: {self.job_matching_dominance_ratio:.3f}",
            f"production_conformance_family_count: {self.production_conformance_family_count}",
        ]
        if self.summary:
            lines.append(f"summary: {self.summary}")

        if self.variants_below_target:
            lines.extend(["", "Variants below target:"])
            for name, count in self.variants_below_target[:max_rows]:
                lines.append(f"  - {name}: {count}")
            if len(self.variants_below_target) > max_rows:
                lines.append(f"  - ... {len(self.variants_below_target) - max_rows} more")

        if self.families_missing_required_case_kinds:
            lines.extend(["", "Families missing required case kinds:"])
            for family, missing in self.families_missing_required_case_kinds[:max_rows]:
                lines.append(f"  - {family}: {', '.join(missing)}")

        if self.families_missing_required_bug_classes:
            lines.extend(["", "Families missing required bug classes:"])
            for family, missing in self.families_missing_required_bug_classes[:max_rows]:
                lines.append(f"  - {family}: {', '.join(missing)}")

        if self.production_conformance_families:
            lines.extend(["", "Production conformance seed families:"])
            for family in self.production_conformance_families:
                lines.append(f"  - {family}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total_cases": self.total_cases,
            "variant_target": self.variant_target,
            "variant_total": self.variant_total,
            "variant_min_cases": self.variant_min_cases,
            "variant_max_cases": self.variant_max_cases,
            "variants_below_target": dict(self.variants_below_target),
            "required_case_kinds": list(self.required_case_kinds),
            "families_missing_required_case_kinds": {
                family: list(missing)
                for family, missing in self.families_missing_required_case_kinds
            },
            "required_bug_classes": list(self.required_bug_classes),
            "families_missing_required_bug_classes": {
                family: list(missing)
                for family, missing in self.families_missing_required_bug_classes
            },
            "family_case_kind_matrix": {
                family: list(values) for family, values in self.family_case_kind_matrix
            },
            "family_bug_class_matrix": {
                family: list(values) for family, values in self.family_bug_class_matrix
            },
            "single_family_dominance_ratio": self.single_family_dominance_ratio,
            "job_matching_case_count": self.job_matching_case_count,
            "job_matching_dominance_ratio": self.job_matching_dominance_ratio,
            "production_conformance_family_count": self.production_conformance_family_count,
            "production_conformance_families": list(self.production_conformance_families),
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


def _metadata_value(result: ExecutableCaseResult, key: str, default: str = "") -> str:
    for item_key, value in result.metadata:
        if item_key == key:
            return str(value)
    return default


def _sorted_missing(
    matrix: dict[str, set[str]],
    required_values: Iterable[str],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    required = set(required_values)
    rows = []
    for family in sorted(matrix):
        missing = tuple(sorted(required - matrix[family]))
        if missing:
            rows.append((family, missing))
    return tuple(rows)


def build_benchmark_coverage_audit(
    report: ExecutableCorpusReport,
    *,
    variant_target: int = 8,
    required_case_kinds: Iterable[str] = DEFAULT_REQUIRED_CASE_KINDS,
    required_bug_classes: Iterable[str] = DEFAULT_REQUIRED_BUG_CLASSES,
    production_conformance_families: Iterable[str] = (),
    summary: str = "",
) -> BenchmarkCoverageAudit:
    """Build a product-grade coverage audit from an executable corpus report."""

    results = report.results
    variant_counts = Counter(
        _metadata_value(result, "variant_id", _metadata_value(result, "model_variant", "unspecified"))
        for result in results
    )
    variant_total = len([name for name in variant_counts if name and name != "unspecified"])
    variant_min = min(variant_counts.values(), default=0)
    variant_max = max(variant_counts.values(), default=0)
    below_target = tuple(
        sorted(
            (
                (variant, count)
                for variant, count in variant_counts.items()
                if variant and variant != "unspecified" and count < variant_target
            ),
            key=lambda item: (item[1], item[0]),
        )
    )

    case_kind_matrix: dict[str, set[str]] = defaultdict(set)
    bug_class_matrix: dict[str, set[str]] = defaultdict(set)
    family_counts: Counter[str] = Counter()
    job_matching_count = 0
    for result in results:
        family = _metadata_value(result, "model_family", result.workflow_family)
        family_counts[family] += 1
        if family == "job_matching" or result.workflow_family == "job_matching":
            job_matching_count += 1
        case_kind_matrix[family].add(result.case_kind)
        bug_class = _metadata_value(
            result,
            "bug_class",
            _metadata_value(result, "structural_category", result.failure_mode),
        )
        bug_class_matrix[family].add(bug_class)

    required_case_kind_tuple = tuple(required_case_kinds)
    required_bug_class_tuple = tuple(required_bug_classes)
    missing_case_kinds = _sorted_missing(case_kind_matrix, required_case_kind_tuple)
    missing_bug_classes = _sorted_missing(bug_class_matrix, required_bug_class_tuple)
    total_cases = report.total_cases
    single_family_dominance = (
        max(family_counts.values(), default=0) / total_cases if total_cases else 0.0
    )
    job_matching_dominance = job_matching_count / total_cases if total_cases else 0.0
    conformance_families = tuple(sorted(set(production_conformance_families)))

    ok = (
        report.ok
        and variant_total >= 150
        and variant_min >= variant_target
        and not below_target
        and not missing_case_kinds
        and not missing_bug_classes
    )
    return BenchmarkCoverageAudit(
        ok=ok,
        total_cases=total_cases,
        variant_target=variant_target,
        variant_total=variant_total,
        variant_min_cases=variant_min,
        variant_max_cases=variant_max,
        variants_below_target=below_target,
        required_case_kinds=required_case_kind_tuple,
        families_missing_required_case_kinds=missing_case_kinds,
        required_bug_classes=required_bug_class_tuple,
        families_missing_required_bug_classes=missing_bug_classes,
        family_case_kind_matrix=tuple(
            sorted((family, tuple(sorted(values))) for family, values in case_kind_matrix.items())
        ),
        family_bug_class_matrix=tuple(
            sorted((family, tuple(sorted(values))) for family, values in bug_class_matrix.items())
        ),
        single_family_dominance_ratio=single_family_dominance,
        job_matching_case_count=job_matching_count,
        job_matching_dominance_ratio=job_matching_dominance,
        production_conformance_family_count=len(conformance_families),
        production_conformance_families=conformance_families,
        summary=summary,
    )


__all__ = [
    "BenchmarkCoverageAudit",
    "DEFAULT_REQUIRED_BUG_CLASSES",
    "DEFAULT_REQUIRED_CASE_KINDS",
    "build_benchmark_coverage_audit",
]
