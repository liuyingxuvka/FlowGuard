"""Optional pytest-friendly assertions without importing pytest."""

from __future__ import annotations

from typing import Any


def assert_report_ok(report: Any) -> None:
    """Raise AssertionError with formatted report text when report.ok is false."""

    if getattr(report, "ok", False):
        return
    formatter = getattr(report, "format_text", None)
    detail = formatter() if formatter is not None else repr(report)
    raise AssertionError(detail)


def assert_no_executable_corpus_regression(report: Any) -> None:
    """Assert the durable 2100-case benchmark gate for pytest users."""

    assert_report_ok(report)
    expected = {
        "total_cases": 2100,
        "executable_cases": 2100,
        "not_executable_yet": 0,
        "real_model_cases": 2100,
        "generic_fallback_cases": 0,
        "failure_cases": 0,
    }
    mismatches = []
    for field, value in expected.items():
        observed = getattr(report, field, None)
        if observed != value:
            mismatches.append(f"{field}: expected {value!r}, observed {observed!r}")
    if mismatches:
        raise AssertionError("\n".join(mismatches))


__all__ = ["assert_no_executable_corpus_regression", "assert_report_ok"]
