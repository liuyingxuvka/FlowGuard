"""Coverage audit entry point for the durable problem-corpus benchmark."""

from __future__ import annotations

from flowguard.coverage import BenchmarkCoverageAudit, build_benchmark_coverage_audit

from .conformance_seeds import CONFORMANCE_SEED_FAMILIES
from .executable import review_executable_corpus


def review_benchmark_coverage() -> BenchmarkCoverageAudit:
    """Run the executable corpus and audit benchmark depth and matrix coverage."""

    report = review_executable_corpus()
    return build_benchmark_coverage_audit(
        report,
        variant_target=8,
        production_conformance_families=CONFORMANCE_SEED_FAMILIES,
        summary=(
            "Phase 11.2 benchmark hardening audit: every variant should have "
            "enough case pressure, every family should cover the required case "
            "kinds and bug classes, and conformance seed family coverage should "
            "remain visible in standalone coverage reports."
        ),
    )


__all__ = ["review_benchmark_coverage"]
