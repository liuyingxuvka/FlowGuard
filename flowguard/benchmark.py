"""Benchmark scorecards built from executable corpus reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .executable import ExecutableCorpusReport
from .export import to_jsonable


@dataclass(frozen=True)
class BenchmarkScorecard:
    """Aggregate mutation-style scorecard for real-model benchmark runs."""

    ok: bool
    total_cases: int
    real_model_cases: int
    generic_fallback_cases: int
    model_variant_total: int
    model_families_with_six_variants: int
    failure_cases: int
    status_counts: tuple[tuple[str, int], ...]
    model_family_counts: tuple[tuple[str, int], ...]
    failure_mode_counts: tuple[tuple[str, int], ...]
    model_variant_counts: tuple[tuple[str, int], ...]
    oracle_type_counts: tuple[tuple[str, int], ...]
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total_cases": self.total_cases,
            "real_model_cases": self.real_model_cases,
            "generic_fallback_cases": self.generic_fallback_cases,
            "model_variant_total": self.model_variant_total,
            "model_families_with_six_variants": self.model_families_with_six_variants,
            "failure_cases": self.failure_cases,
            "status_counts": dict(self.status_counts),
            "model_family_counts": dict(self.model_family_counts),
            "failure_mode_counts": dict(self.failure_mode_counts),
            "model_variant_counts": dict(self.model_variant_counts),
            "oracle_type_counts": dict(self.oracle_type_counts),
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)

    def format_text(self) -> str:
        lines = [
            "=== flowguard benchmark scorecard ===",
            "",
            f"status: {'OK' if self.ok else 'MISMATCH'}",
            f"total_cases: {self.total_cases}",
            f"real_model_cases: {self.real_model_cases}",
            f"generic_fallback_cases: {self.generic_fallback_cases}",
            f"model_variant_total: {self.model_variant_total}",
            f"model_families_with_six_variants: {self.model_families_with_six_variants}",
            f"failure_cases: {self.failure_cases}",
        ]
        if self.summary:
            lines.append(f"summary: {self.summary}")
        lines.extend(["", "Status counts:"])
        for name, count in self.status_counts:
            lines.append(f"  - {name}: {count}")
        lines.extend(["", "Model variants:"])
        for name, count in self.model_variant_counts:
            lines.append(f"  - {name}: {count}")
        return "\n".join(lines)


def build_benchmark_scorecard(report: ExecutableCorpusReport) -> BenchmarkScorecard:
    """Build a benchmark scorecard from an executable real-model report."""

    return BenchmarkScorecard(
        ok=report.ok,
        total_cases=report.total_cases,
        real_model_cases=report.real_model_cases,
        generic_fallback_cases=report.generic_fallback_cases,
        model_variant_total=report.model_variant_total,
        model_families_with_six_variants=report.model_families_with_six_variants,
        failure_cases=report.failure_cases,
        status_counts=report.status_counts,
        model_family_counts=report.model_family_counts,
        failure_mode_counts=report.failure_mode_counts,
        model_variant_counts=report.model_variant_counts,
        oracle_type_counts=report.oracle_type_counts,
        summary=report.summary,
    )


__all__ = ["BenchmarkScorecard", "build_benchmark_scorecard"]
