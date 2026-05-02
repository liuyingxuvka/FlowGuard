"""Run assumption-card safety checks."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.assumption_card_safety.model import run_assumption_policy_check  # noqa: E402


EXPECTED_BROKEN_VIOLATIONS = {
    "no_bad_assumption_acceptances",
    "no_internal_equivalence_claim_accepted",
    "accepted_assumptions_are_visible",
    "accepted_assumptions_keep_preconditions",
    "accepted_assumptions_are_not_modelable_conditions",
}


def main() -> int:
    correct_report = run_assumption_policy_check()
    broken_report = run_assumption_policy_check(broken=True)
    broken_violation_names = {
        violation.invariant_name
        for violation in broken_report.violations
    }

    print("== correct assumption policy ==")
    print(correct_report.format_text(max_examples=2))
    print()
    print("== broken accept-all policy ==")
    print(broken_report.format_text(max_examples=2))

    if not correct_report.ok:
        return 1
    if broken_report.ok:
        return 1
    if not EXPECTED_BROKEN_VIOLATIONS.issubset(broken_violation_names):
        missing = sorted(EXPECTED_BROKEN_VIOLATIONS - broken_violation_names)
        print(f"missing expected broken-policy violations: {missing}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
