"""Run conformance replay for flowguard's self-review orchestrator."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.flowguard_self_review.conformance import (  # noqa: E402
    generate_self_review_representative_traces,
    replay_self_review_trace,
)
from examples.flowguard_self_review.orchestrator import (  # noqa: E402
    BrokenNoConformanceOrchestrator,
    BrokenToolchainSubstituteOrchestrator,
    CorrectFlowguardOrchestrator,
)


def _print_report(title: str, report) -> None:
    print(f"\n== {title} ==")
    print(report.format_text(max_examples=1))


def main() -> int:
    traces = generate_self_review_representative_traces()
    conformance_trace = next(trace for trace in traces if trace.has_label("checks_passed") and "flowguard-conformance" in repr(trace.external_inputs))
    toolchain_trace = next(trace for trace in traces if trace.has_label("toolchain_missing"))

    correct_reports = [replay_self_review_trace(trace, CorrectFlowguardOrchestrator()) for trace in traces]
    broken_conformance = replay_self_review_trace(conformance_trace, BrokenNoConformanceOrchestrator())
    broken_toolchain = replay_self_review_trace(toolchain_trace, BrokenToolchainSubstituteOrchestrator())

    print("=== flowguard self-review conformance ===")
    print(f"representative_traces: {len(traces)}")
    print(f"correct_status: {'OK' if all(report.ok for report in correct_reports) else 'VIOLATION'}")
    _print_report("broken no-conformance orchestrator", broken_conformance)
    _print_report("broken toolchain-substitute orchestrator", broken_toolchain)

    return 0 if all(report.ok for report in correct_reports) and not broken_conformance.ok and not broken_toolchain.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
