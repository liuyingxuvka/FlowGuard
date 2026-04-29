"""Combined Phase 11.2 benchmark hardening report."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from flowguard.coverage import BenchmarkCoverageAudit, build_benchmark_coverage_audit
from flowguard.export import to_jsonable

from .conformance_seeds import ConformanceSeedReport, review_conformance_seeds
from .executable import review_executable_corpus
from .family_scenarios import FamilyScenarioSeedReport, review_priority_family_scenarios


@dataclass(frozen=True)
class BenchmarkHardeningReport:
    ok: bool
    coverage_audit: BenchmarkCoverageAudit
    family_scenario_report: FamilyScenarioSeedReport
    conformance_seed_report: ConformanceSeedReport
    summary: str = ""

    def format_text(self) -> str:
        return "\n\n".join(
            (
                "=== flowguard benchmark hardening report ===\n"
                f"\nstatus: {'OK' if self.ok else 'GAP'}"
                + (f"\nsummary: {self.summary}" if self.summary else ""),
                self.coverage_audit.format_text(),
                self.family_scenario_report.format_text(),
                self.conformance_seed_report.format_text(),
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "coverage_audit": self.coverage_audit.to_dict(),
            "family_scenario_report": self.family_scenario_report.to_dict(),
            "conformance_seed_report": self.conformance_seed_report.to_dict(),
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


def review_benchmark_hardening() -> BenchmarkHardeningReport:
    """Run the Phase 11.2 durable benchmark hardening review."""

    conformance_report = review_conformance_seeds()
    coverage_audit = build_benchmark_coverage_audit(
        review_executable_corpus(),
        variant_target=8,
        production_conformance_families={
            result.family for result in conformance_report.results
        },
        summary=(
            "Phase 11.2 benchmark hardening audit with conformance seed family "
            "coverage included."
        ),
    )
    family_scenario_report = review_priority_family_scenarios()
    ok = coverage_audit.ok and family_scenario_report.ok and conformance_report.ok
    return BenchmarkHardeningReport(
        ok=ok,
        coverage_audit=coverage_audit,
        family_scenario_report=family_scenario_report,
        conformance_seed_report=conformance_report,
        summary=(
            "Durable benchmark baseline: variant depth, family bug-class matrix, "
            "priority non-job-matching scenarios, and production conformance seeds."
        ),
    )


__all__ = ["BenchmarkHardeningReport", "review_benchmark_hardening"]
